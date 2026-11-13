"""Wait until the deployed commit is current and its cloud worker is running."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def read_json(command: str, build: Path):
    result = subprocess.run(['lk', 'agent', command, '--json'], cwd=build,
                            check=True, capture_output=True, text=True, timeout=30)
    return json.loads(result.stdout)


def verify(build: Path, commit: str, timeout: int = 300) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        versions = read_json('versions', build).get('versions', [])
        current = next((v for v in versions if v.get('current') and v.get('active')), None)
        status = read_json('status', build).get('agents', [])
        if current and current.get('attributes', {}).get('git_commit') == commit and status:
            agent = status[0]
            deployments = agent.get('agentDeployments', [])
            if (agent.get('version') == current.get('version') and deployments
                    and all(d.get('status') == 'Running' and d.get('version') == current.get('version')
                            for d in deployments)):
                print(f"Commit {commit} is running as LiveKit version {current['version']}.", flush=True)
                return
        print('Waiting for the requested commit and running worker...', flush=True)
        time.sleep(10)
    raise TimeoutError('LiveKit did not report the requested commit running within five minutes')


if __name__ == '__main__':
    verify(Path(sys.argv[1]), os.environ['GITHUB_SHA'])
