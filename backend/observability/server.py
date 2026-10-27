"""Run the local Phoenix UI/collector with storage kept inside this folder."""
import os
from pathlib import Path
import runpy
import sys

from .config import get_observability_settings


def main():
    settings = get_observability_settings()
    directory = Path(__file__).resolve().parent / "data"
    directory.mkdir(parents=True, exist_ok=True)
    os.environ["PHOENIX_WORKING_DIR"] = str(directory)
    os.environ["PHOENIX_HOST"] = "127.0.0.1"
    os.environ["PHOENIX_PORT"] = str(settings.port)
    # Use Phoenix as a local collector/UI; skip its unrelated assistant and
    # external docs connection so local startup does not wait for network access.
    os.environ.setdefault("PHOENIX_DISABLE_AGENT_ASSISTANT", "true")
    os.environ.setdefault("PHOENIX_LOG_MIGRATIONS", "false")
    sys.argv = ["phoenix", "serve"]
    runpy.run_module("phoenix.server.main", run_name="__main__")


if __name__ == "__main__":
    main()
