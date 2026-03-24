# /src/mcp_server/file_watcher.py
import logging
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer

if TYPE_CHECKING:
    from .index_manager import IndexManager

log = logging.getLogger(__name__)

# Extensions that should trigger stale marking
WATCHED_EXTENSIONS = {
    ".ts", ".tsx", ".js", ".jsx",
    ".vue", ".py", ".php", ".rs",
    ".sh", ".toml", ".md",
}

# Directories to ignore completely (watchdog sees all events, we filter)
IGNORED_DIRS = {
    "node_modules", ".nuxt", ".output", ".git",
    "dist", "coverage", "sandwiches", "__pycache__",
}


class _ChangeHandler(FileSystemEventHandler):
    """
    Translates filesystem events into stale marks on IndexManager.

    Debounce logic: after the first qualifying event, we wait DEBOUNCE_SECONDS
    before actually marking stale.  This prevents a cascade of marks during
    e.g. a git checkout or yarn install.
    """

    DEBOUNCE_SECONDS = 5.0

    def __init__(self, manager: "IndexManager"):
        super().__init__()
        self._manager = manager
        self._pending_timer: threading.Timer | None = None
        self._lock = threading.Lock()   # guards _pending_timer only

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return

        path = Path(event.src_path)

        # Ignore hidden paths and known generated directories
        parts = path.parts
        if any(p.startswith(".") for p in parts):
            return
        if any(p in IGNORED_DIRS for p in parts):
            return

        ext = path.suffix.lower()
        if ext not in WATCHED_EXTENSIONS:
            return

        log.debug(f"FileWatcher: {event.event_type} {path.name}")
        self._schedule_mark(str(path.name))

    def _schedule_mark(self, reason: str) -> None:
        with self._lock:
            if self._pending_timer is not None:
                self._pending_timer.cancel()
            self._pending_timer = threading.Timer(
                self.DEBOUNCE_SECONDS,
                self._do_mark,
                args=(reason,),
            )
            self._pending_timer.daemon = True
            self._pending_timer.start()

    def _do_mark(self, reason: str) -> None:
        with self._lock:
            self._pending_timer = None
        self._manager.mark_stale(reason)


class FileWatcher:
    """
    Wraps watchdog Observer for a project directory.

    Usage:
        watcher = FileWatcher(manager, project_root)
        watcher.start()
        ...
        watcher.stop()
    """

    def __init__(self, manager: "IndexManager", project_root: Path):
        self._manager = manager
        self._root = project_root
        self._observer: Observer | None = None

    def start(self) -> None:
        if self._observer is not None:
            return
        handler = _ChangeHandler(self._manager)
        self._observer = Observer()
        self._observer.schedule(handler, str(self._root), recursive=True)
        self._observer.daemon = True
        self._observer.start()
        log.info(f"FileWatcher started on {self._root}")

    def stop(self) -> None:
        if self._observer is None:
            return
        self._observer.stop()
        self._observer.join(timeout=5)
        self._observer = None
        log.info("FileWatcher stopped")

    @property
    def running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()
