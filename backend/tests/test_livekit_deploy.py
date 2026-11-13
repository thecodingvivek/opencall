import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.prepare_livekit_build import prepare
from scripts.verify_livekit_deployment import verify


class LiveKitDeploymentTests(unittest.TestCase):
    def test_build_context_is_python_only_and_excludes_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            build = Path(tmp) / 'build'
            prepare(build)
            self.assertTrue((build / 'Dockerfile').is_file())
            self.assertTrue((build / 'voiceagent/worker.py').is_file())
            self.assertTrue((build / 'backend/app/main.py').is_file())
            self.assertIn('livekit-agents[codecs]==', (build / 'requirements.txt').read_text())
            self.assertFalse((build / 'package.json').exists())
            self.assertFalse((build / 'voiceagent/.env').exists())
            self.assertFalse(any(build.rglob('*.crt')))
            self.assertFalse(any(build.rglob('service.json')))

    def test_verify_requires_matching_commit_and_running_replica(self):
        versions = {'versions': [{'current': True, 'active': True, 'version': 'v1',
                                  'attributes': {'git_commit': 'expected'}}]}
        scheduling = {'agents': [{'version': 'v1', 'agentDeployments': [{'version': 'v1', 'status': 'Scheduling'}]}]}
        running = {'agents': [{'version': 'v1', 'agentDeployments': [{'version': 'v1', 'status': 'Running'}]}]}
        with patch('scripts.verify_livekit_deployment.read_json', side_effect=[versions, scheduling, versions, running]), \
             patch('scripts.verify_livekit_deployment.time.sleep'):
            verify(Path('/tmp/build'), 'expected')

    def test_verify_rejects_previous_commit(self):
        versions = {'versions': [{'current': True, 'active': True, 'version': 'old',
                                  'attributes': {'git_commit': 'previous'}}]}
        running = {'agents': [{'version': 'old', 'agentDeployments': [{'version': 'old', 'status': 'Running'}]}]}
        with patch('scripts.verify_livekit_deployment.read_json', side_effect=[versions, running]), \
             patch('scripts.verify_livekit_deployment.time.monotonic', side_effect=[0, 1, 301]), \
             patch('scripts.verify_livekit_deployment.time.sleep'):
            with self.assertRaises(TimeoutError):
                verify(Path('/tmp/build'), 'expected')
