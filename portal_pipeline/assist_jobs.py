"""Author: Yazad Madan. Bounded draft jobs and debounced local question sorting."""
import threading
from datetime import datetime, timezone
from pathlib import Path

from shared_storage import file_lock

# Config
SORT_DEBOUNCE_SECONDS = 30
MAX_CONCURRENT_JOBS = 3
ERROR_FILENAME = "questions_sort_errors.log"
JOB_SLOTS = threading.BoundedSemaphore(MAX_CONCURRENT_JOBS)
SCHEDULERS = {}
SCHEDULERS_LOCK = threading.Lock()


def log_error(data, error):
    try:
        path = Path(data) / ERROR_FILENAME
        with file_lock(path):
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(f"{datetime.now(timezone.utc).isoformat()} {type(error).__name__}\n")
    except Exception:
        pass


class SortScheduler:
    def __init__(self, service):
        self.service = service
        self.lock = threading.Lock()
        self.timer = None
        self.generation = 0
        self.running = False
        self.pending = False
        self.closed = False

    def schedule(self):
        with self.lock:
            if self.closed:
                return
            self.generation += 1
            self.pending = False
            if self.timer is not None:
                self.timer.cancel()
            self.timer = threading.Timer(SORT_DEBOUNCE_SECONDS, self._due, args=(self.generation,))
            self.timer.daemon = True
            self.timer.start()

    def _due(self, generation):
        with self.lock:
            if self.closed or generation != self.generation:
                return
            self.timer = None
            if self.running:
                self.pending = True
                return
            self.running = True
        self._run()

    def _run(self):
        while True:
            try:
                import questions_sort
                questions_sort.promote(self.service)
            except Exception as error:
                log_error(self.service.data, error)
            with self.lock:
                if self.pending and not self.closed:
                    self.pending = False
                    continue
                self.running = False
                return

    def close(self):
        with self.lock:
            self.closed = True
            self.pending = False
            if self.timer is not None:
                self.timer.cancel()
                self.timer = None


def schedule(service):
    with SCHEDULERS_LOCK:
        scheduler = SCHEDULERS.setdefault(service.data, SortScheduler(service))
    scheduler.schedule()


def close(data):
    with SCHEDULERS_LOCK:
        scheduler = SCHEDULERS.pop(Path(data).resolve(), None)
    if scheduler is not None:
        scheduler.close()
