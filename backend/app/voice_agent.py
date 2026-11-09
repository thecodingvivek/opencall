"""Compatibility import; prefer voiceagent.worker with the repository on PYTHONPATH."""
import sys
from voiceagent import worker

if __name__ == "__main__":
    worker.cli.run_app(worker.server)
else:
    sys.modules[__name__] = worker
