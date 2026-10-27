"""Short TinyDB transactions shared by API threads and LiveKit worker processes."""
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock

from tinydb import TinyDB
from tinydb.storages import MemoryStorage

_lock = RLock()


@contextmanager
def database(path: Path):
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Each transaction opens a fresh instance, avoiding stale TinyDB query caches.
    with _lock, path.with_suffix(path.suffix + ".lock").open("a") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            with TinyDB(storage=MemoryStorage) as db:
                before = json.loads(path.read_text()) if path.exists() else {}
                db.storage.write(deepcopy(before))
                yield db
                after = db.storage.read()
                if after != before:
                    # Commit all table updates together.
                    temporary_path = None
                    try:
                        with NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as temporary:
                            temporary_path = Path(temporary.name)
                            json.dump(after, temporary, ensure_ascii=False)
                            temporary.flush()
                            os.fsync(temporary.fileno())
                        os.replace(temporary_path, path)
                    finally:
                        if temporary_path is not None:
                            temporary_path.unlink(missing_ok=True)
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
