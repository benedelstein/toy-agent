"""File watcher for IDE integration - monitors file modifications."""
import threading
import time
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


# File extensions to watch
WATCHED_EXTENSIONS = {'.py', '.md', '.txt', '.json', '.yaml', '.yml', '.toml', '.ts', '.js', '.tsx', '.jsx', '.html', '.css'}

# Paths/patterns to ignore
IGNORED_PATTERNS = {'__pycache__', '.git', '.pytest_cache', 'node_modules', '.venv', 'venv', '.mypy_cache', '.ruff_cache'}


class FileEventHandler(FileSystemEventHandler):
    """Handle file system events with proper debouncing."""

    def __init__(self, callback: Callable[[str, str], None], project_root: Path):
        self.callback = callback
        self.project_root = project_root
        self._last_events: dict[str, float] = {}
        self._lock = threading.Lock()
        self._debounce_seconds = 1.0

    def _should_ignore(self, path: Path) -> bool:
        """Check if path should be ignored."""
        parts = path.parts
        for pattern in IGNORED_PATTERNS:
            if pattern in parts:
                return True
        return False

    def _should_watch(self, path: Path) -> bool:
        """Check if file extension should be watched."""
        return path.suffix.lower() in WATCHED_EXTENSIONS

    def _handle_event(self, event: FileSystemEvent, event_type: str) -> None:
        """Handle a file event with debouncing."""
        if event.is_directory:
            return

        # Normalize path
        src_path = event.src_path.decode('utf-8') if isinstance(event.src_path, bytes) else event.src_path
        path = Path(src_path)

        # Check filters
        if self._should_ignore(path) or not self._should_watch(path):
            return

        try:
            rel_path = path.relative_to(self.project_root)
        except ValueError:
            return  # Path not under project root

        rel_path_str = str(rel_path)
        now = time.time()

        # Debounce: skip if we've seen this file recently
        with self._lock:
            last_time = self._last_events.get(rel_path_str, 0)
            if now - last_time < self._debounce_seconds:
                return
            self._last_events[rel_path_str] = now

        self.callback(event_type, rel_path_str)

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        self._handle_event(event, "modified")

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        self._handle_event(event, "created")


class FileWatcher:
    """Watch for file modifications in the project."""

    def __init__(self, project_root: str, callback: Callable[[str, str], None]):
        self.project_root = Path(project_root)
        self.callback = callback
        self.observer = Observer()
        self.handler = FileEventHandler(callback, self.project_root)

    def start(self) -> None:
        """Start watching for file events."""
        self.observer.schedule(self.handler, str(self.project_root), recursive=True)
        self.observer.start()

    def stop(self) -> None:
        """Stop watching for file events."""
        self.observer.stop()
        self.observer.join()
