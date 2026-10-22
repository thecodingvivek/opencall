import io
import unittest
import wave
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient
from app.main import app


def wav_bytes(seconds=1, channels=1, rate=16000):
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b'\0\0' * rate * seconds * channels)
    return buffer.getvalue()


class SpeechTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.factory_patch = patch('app.api.routes.speech.get_gnani_stt_client')
        self.factory = self.factory_patch.start()
        self.addCleanup(self.factory_patch.stop)
        self.sdk = Mock()
        self.recognize_patch = patch('app.api.routes.speech.recognize', new_callable=AsyncMock)
        self.recognize = self.recognize_patch.start()
        self.addCleanup(self.recognize_patch.stop)
        self.recognize.return_value = ' Hello world '
        self.factory.return_value = self.sdk

    def upload(self, audio=None, language='en-IN'):
        return self.client.post('/api/v1/speech/transcribe',
            files={'audio': ('recording.wav', wav_bytes() if audio is None else audio, 'audio/wav')},
            data={'language_code': language})

    def test_transcription_contract(self):
        response = self.upload(language='te-IN')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['transcript'], 'Hello world')
        self.assertEqual(result['language_code'], 'te-IN')
        self.assertTrue(result['request_id'])
        self.factory.assert_called_once_with(language='te-IN')
        args = self.recognize.call_args.args
        self.assertIs(args[0], self.sdk)
        self.assertEqual(args[1], b'\0\0' * 16000)

    def test_invalid_uploads_do_not_call_gnani(self):
        for audio in (b'', b'not audio', wav_bytes(seconds=0), wav_bytes(seconds=61),
                      wav_bytes(channels=2), wav_bytes(rate=44100), wav_bytes()[:-100]):
            with self.subTest(length=len(audio)):
                self.assertEqual(self.upload(audio).status_code, 422)
        self.factory.assert_not_called()

    def test_large_upload_rejected(self):
        self.assertEqual(self.upload(b'x' * (8 * 1024 * 1024 + 1)).status_code, 413)
        self.factory.assert_not_called()

    def test_invalid_language_rejected(self):
        self.assertEqual(self.upload(language='invalid').status_code, 422)
        self.factory.assert_not_called()

    def test_missing_sdk_or_configuration(self):
        for error in (ModuleNotFoundError(), RuntimeError('private config details')):
            self.factory.side_effect = error
            response = self.upload()
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('private', response.text)

    def test_upstream_failure_is_safe(self):
        self.recognize.side_effect = Exception('private provider details')
        response = self.upload()
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('private', response.text)

    def test_empty_transcript_is_valid(self):
        self.recognize.return_value = ''
        response = self.upload()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['transcript'], '')

    def test_provider_failure_response_rejected(self):
        self.recognize.side_effect = ValueError('Invalid transcription event')
        self.assertEqual(self.upload().status_code, 502)


class SynthesisTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.factory_patch = patch('app.api.routes.speech.get_gnani_tts_client')
        self.factory = self.factory_patch.start()
        self.addCleanup(self.factory_patch.stop)
        self.sdk = Mock()
        self.synthesis_patch = patch('app.api.routes.speech.synthesize_audio', new_callable=AsyncMock)
        self.synthesis = self.synthesis_patch.start()
        self.addCleanup(self.synthesis_patch.stop)
        self.synthesis.return_value = wav_bytes()
        self.factory.return_value = self.sdk

    def synthesize(self, text='Hello world', language='en-IN'):
        return self.client.post('/api/v1/speech/synthesize',
            json={'text': text, 'language_code': language})

    def test_wav_response_and_provider_contract(self):
        response = self.synthesize('  Hello world  ')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, wav_bytes())
        self.assertEqual(response.headers['content-type'], 'audio/wav')
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.factory.assert_called_once_with(voice='Shivani', language='en-IN')
        self.synthesis.assert_awaited_once_with(self.sdk, 'Hello world')
        self.assertTrue(response.headers['x-api-request-id'])

    def test_multilingual_default_voice(self):
        for language in ('en-IN', 'hi-IN', 'te-IN', 'ta-IN', 'kn-IN', 'ml-IN',
                         'mr-IN', 'gu-IN', 'bn-IN', 'pa-IN'):
            with self.subTest(language=language):
                self.assertEqual(self.synthesize(language=language).status_code, 200)
                self.assertEqual(self.factory.call_args.kwargs['voice'], 'Shivani')
                self.assertEqual(self.factory.call_args.kwargs['language'], language)

    def test_selected_voice_reaches_provider(self):
        response = self.client.post('/api/v1/speech/synthesize', json={
            'text': 'Hello world', 'language_code': 'en-IN', 'voice': 'Avinash',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.factory.call_args.kwargs['voice'], 'Avinash')

    def test_unknown_or_legacy_voice_does_not_call_provider(self):
        for voice in ('Unknown', 'Nalini', 'Kaveri', 'Pranav', '', '   '):
            response = self.client.post('/api/v1/speech/synthesize', json={
                'text': 'Hello world', 'language_code': 'en-IN', 'voice': voice,
            })
            self.assertEqual(response.status_code, 422)
        self.factory.assert_not_called()

    def test_voice_catalog_contract(self):
        response = self.client.get('/api/v1/speech/voices?language_code=te-IN')
        self.assertEqual(response.status_code, 200)
        catalog = response.json()
        self.assertEqual(catalog['language_code'], 'te-IN')
        self.assertEqual(catalog['default_voice'], 'Shivani')
        self.assertEqual(len(catalog['voices']), 13)
        self.assertIn('Lakshmi', catalog['voices'])
        english = self.client.get('/api/v1/speech/voices?language_code=en-IN').json()
        self.assertEqual(catalog['voices'], english['voices'])
        self.assertEqual(self.client.get('/api/v1/speech/voices?language_code=invalid').status_code, 422)
        self.factory.assert_not_called()

    def test_supported_delivery_tags(self):
        for tag in ('excited', 'whispers', 'shouting', 'laugh', 'giggle', 'sigh',
                    'exhales', 'sniffles', 'yawns', 'coughs', 'clears throat', 'slow', 'pauses'):
            with self.subTest(tag=tag):
                response = self.client.post('/api/v1/speech/synthesize', json={
                    'text': 'Hello world', 'language_code': 'en-IN', 'delivery': tag,
                })
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.synthesis.call_args.args[1], f'<{tag}> Hello world')

    def test_unsupported_delivery_is_rejected(self):
        response = self.client.post('/api/v1/speech/synthesize', json={
            'text': 'Hello world', 'delivery': 'sad',
        })
        self.assertEqual(response.status_code, 422)
        self.factory.assert_not_called()

    def test_invalid_text_and_language_do_not_call_provider(self):
        for payload in ({'text': ''}, {'text': '   '}, {'text': 'x' * 5001},
                        {'text': 'Hello', 'language_code': 'invalid'}, {}):
            with self.subTest(payload_length=len(str(payload))):
                response = self.client.post('/api/v1/speech/synthesize', json=payload)
                self.assertEqual(response.status_code, 422)
        self.factory.assert_not_called()

    def test_missing_sdk_or_key(self):
        for error in (ModuleNotFoundError(), RuntimeError('private config details')):
            self.factory.side_effect = error
            response = self.synthesize()
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('private', response.text)

    def test_upstream_failure_is_safe(self):
        self.synthesis.side_effect = Exception('private provider details')
        response = self.synthesize()
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('private', response.text)

    def test_invalid_provider_audio_is_rejected(self):
        for audio in (b'', b'not audio', b'{"error":"private details"}'):
            with self.subTest(audio=audio):
                self.synthesis.return_value = audio
                response = self.synthesize()
                self.assertEqual(response.status_code, 502)
                self.assertNotIn('private', response.text)



if __name__ == '__main__':
    unittest.main()
