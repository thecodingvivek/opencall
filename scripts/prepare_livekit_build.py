"""Create a Python-only, credential-free LiveKit Cloud build context."""
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
IGNORE = shutil.ignore_patterns('.env', '.env.*', '__pycache__', '*.pyc', 'data', '*.crt', '*.pem', 'service.json', '.agents')


def prepare(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    for directory in ('backend/app', 'backend/tools', 'voiceagent'):
        shutil.copytree(ROOT / directory, destination / directory, ignore=IGNORE)
    for name in ('backend/requirements.txt', 'Dockerfile', '.dockerignore', 'livekit.toml'):
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    # The CLI identifies the agent runtime from the top-level requirements.
    requirements = (ROOT / 'backend/requirements.txt').read_text().splitlines()
    agent = next((line for line in requirements if line.startswith('livekit-agents[codecs]==')), None)
    if not agent:
        raise ValueError('Pinned LiveKit Agents dependency is missing')
    (destination / 'requirements.txt').write_text(f'{agent}\n-r backend/requirements.txt\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('destination', type=Path)
    prepare(parser.parse_args().destination)
