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


if __name__ == '__main__':
    unittest.main()
