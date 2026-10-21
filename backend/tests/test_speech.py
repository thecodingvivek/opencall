import io
import unittest
import wave
from unittest.mock import Mock, patch

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
        self.sdk.transcribe_bytes.return_value = {'success': True, 'transcript': ' Hello world '}
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
        args, kwargs = self.sdk.transcribe_bytes.call_args
        self.assertEqual(args[0], wav_bytes())
        self.assertEqual(kwargs['filename'], 'recording.wav')
        self.assertEqual(kwargs['language_code'], 'te-IN')
        self.assertEqual(kwargs['request_id'], result['request_id'])

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
        self.sdk.transcribe_bytes.side_effect = Exception('private provider details')
        response = self.upload()
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('private', response.text)

    def test_empty_transcript_is_valid(self):
        self.sdk.transcribe_bytes.return_value = {'success': True, 'transcript': ''}
        response = self.upload()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['transcript'], '')

    def test_provider_failure_response_rejected(self):
        self.sdk.transcribe_bytes.return_value = {'success': False, 'transcript': ''}
        self.assertEqual(self.upload().status_code, 502)


class SynthesisTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.factory_patch = patch('app.api.routes.speech.get_gnani_tts_client')
        self.factory = self.factory_patch.start()
        self.addCleanup(self.factory_patch.stop)
        self.sdk = Mock()
        self.sdk.synthesize.return_value = wav_bytes()
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
        args, kwargs = self.sdk.synthesize.call_args
        self.assertEqual(args, ('Hello world',))
        self.assertEqual(kwargs['model'], 'timbre-v2.5')
        self.assertEqual(kwargs['language'], 'en-IN')
        self.assertEqual(kwargs['voice'], 'Kaveri')
        self.assertEqual(kwargs['request_id'], response.headers['x-api-request-id'])
        self.assertEqual(kwargs['audio_config'].container, 'wav')
        self.assertEqual(kwargs['audio_config'].sample_rate, 48000)
        self.assertNotIn('output_file', kwargs)

    def test_language_specific_voices(self):
        for language, voice in {
            'hi-IN': 'Nalini', 'te-IN': 'Suhana', 'ta-IN': 'Asmita',
            'kn-IN': 'Saanvi', 'ml-IN': 'Reshma', 'mr-IN': 'Zahira',
            'gu-IN': 'Falak', 'bn-IN': 'Kirra', 'pa-IN': 'Mehuli',
        }.items():
            with self.subTest(language=language):
                self.assertEqual(self.synthesize(language=language).status_code, 200)
                self.assertEqual(self.sdk.synthesize.call_args.kwargs['voice'], voice)
                self.assertEqual(self.sdk.synthesize.call_args.kwargs['language'], language)

    def test_selected_voice_reaches_provider(self):
        response = self.client.post('/api/v1/speech/synthesize', json={
            'text': 'Hello world', 'language_code': 'en-IN', 'voice': 'Pranav',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.sdk.synthesize.call_args.kwargs['voice'], 'Pranav')

    def test_invalid_or_mismatched_voice_does_not_call_provider(self):
        for voice in ('Unknown', 'Nalini', '', '   '):
            response = self.client.post('/api/v1/speech/synthesize', json={
                'text': 'Hello world', 'language_code': 'en-IN', 'voice': voice,
            })
            self.assertEqual(response.status_code, 422)
        self.factory.assert_not_called()

    def test_voice_catalog_contract(self):
        response = self.client.get('/api/v1/speech/voices?language_code=te-IN')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'language_code': 'te-IN', 'default_voice': 'Suhana',
            'voices': ['Suhana', 'Lehara', 'Lavanya', 'Yukti', 'Varuni'],
        })
        self.assertEqual(self.client.get('/api/v1/speech/voices?language_code=invalid').status_code, 422)
        self.factory.assert_not_called()

    def test_catalog_voices_are_accepted_by_installed_sdk(self):
        from gnani.tts import GnaniTTSClient
        from app.api.routes.speech import TTS_VOICES
        supported = set(GnaniTTSClient.supported_voices('timbre-v2.5'))
        for voices in TTS_VOICES.values():
            self.assertTrue(set(voices) <= supported)

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
        self.sdk.synthesize.side_effect = Exception('private provider details')
        response = self.synthesize()
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('private', response.text)

    def test_invalid_provider_audio_is_rejected(self):
        for audio in (b'', b'not audio', b'{"error":"private details"}'):
            with self.subTest(audio=audio):
                self.sdk.synthesize.return_value = audio
                response = self.synthesize()
                self.assertEqual(response.status_code, 502)
                self.assertNotIn('private', response.text)


if __name__ == '__main__':
    unittest.main()
