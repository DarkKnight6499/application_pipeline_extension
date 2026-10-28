"""Author: Yazad Madan. Process locks and atomic writes with external staging files."""
import contextlib
import hashlib
import json
import os
import tempfile
import threading
import time
from pathlib import Path

# Config
LOCK_TIMEOUT_SECONDS = 900
LOCK_POLL_SECONDS = 0.1
LOCK_DIR = Path(tempfile.gettempdir()) / "portal-pipeline-locks"
SAME_VOLUME_TEMP_DIR = Path(os.environ.get("PORTAL_TEMP_DIR", Path(__file__).resolve().parents[2] / ".portal-tmp"))
TEMP_PREFIX = "portal-"
TEMP_SUFFIX = ".tmp"
REPLACE_TIMEOUT_SECONDS = 5
REPOSITORY_DIR = Path(__file__).resolve().parents[1]
_THREAD_LOCKS = {}
_THREAD_GUARD = threading.Lock()


@contextlib.contextmanager
def file_lock(key, timeout=LOCK_TIMEOUT_SECONDS):
    """Hold an OS lock; process exit releases it without stale-lock recovery."""
    identity = os.path.normcase(str(key.resolve())) if isinstance(key, Path) else str(key)
    name = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    with _THREAD_GUARD:
        local = _THREAD_LOCKS.setdefault(name, threading.Lock())
    deadline = time.monotonic() + timeout
    if not local.acquire(timeout=timeout):
        raise TimeoutError("Timed out waiting for the shared portal lock.")
    try:
        LOCK_DIR.mkdir(parents=True, exist_ok=True)
        with (LOCK_DIR / name).open("a+b") as handle:
            while True:
                try:
                    handle.seek(0)
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Timed out waiting for the shared portal lock.") from None
                    time.sleep(LOCK_POLL_SECONDS)
            try:
                yield
            finally:
                handle.seek(0)
                if os.name == "nt":
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        local.release()


def atomic_text(path, text):
    """Stage outside the repository on the destination volume before replacing."""
    path = Path(path).resolve()
    root = Path(tempfile.gettempdir()).resolve()
    if os.name == "nt" and root.drive.lower() != path.drive.lower():
        root = SAME_VOLUME_TEMP_DIR.resolve()
    if os.name == "nt" and root.drive.lower() != path.drive.lower():
        raise ValueError("PORTAL_TEMP_DIR must be on the destination volume outside the repository.")
    if root.is_relative_to(REPOSITORY_DIR):
        raise ValueError("PORTAL_TEMP_DIR must be outside the repository.")
    root.mkdir(parents=True, exist_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=root, prefix=TEMP_PREFIX,
                                         suffix=TEMP_SUFFIX, delete=False) as handle:
            name = handle.name
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        deadline = time.monotonic() + REPLACE_TIMEOUT_SECONDS
        while True:
            try:
                os.replace(name, path)
                break
            except PermissionError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(LOCK_POLL_SECONDS)
    finally:
        if name and Path(name).exists():
            Path(name).unlink()


def atomic_json(path, data):
    atomic_text(path, json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True))
