"""File watcher for IDE integration - monitors file views (close events), modifications, and creations."""

import threading
import time
from pathlib import Path
from typing import Callable

import pathspec
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .logger import logger

# Always ignore these directories even if not in .gitignore
ALWAYS_IGNORED_DIRS = {
    ".git",
}


class FileEventHandler(FileSystemEventHandler):
    """Handle file system events with proper debouncing."""

    def __init__(self, callback: Callable[[str, str], None], project_root: Path):
        self.callback = callback
        self.project_root = project_root
        self._last_events: dict[str, float] = {}
        self._lock = threading.Lock()
        self._debounce_seconds = 1.0
        self._gitignore_spec = self._load_gitignore()

    def _load_gitignore(self) -> pathspec.PathSpec | None:
        """Load and parse .gitignore file if it exists."""
        gitignore_path = self.project_root / ".gitignore"
        if not gitignore_path.exists():
            return None

        try:
            with open(gitignore_path, "r") as f:
                patterns = f.read().splitlines()
            return pathspec.PathSpec.from_lines("gitwildmatch", patterns)
        except Exception:
            return None

    def _should_ignore(self, path: Path) -> bool:
        """Check if path should be ignored based on .gitignore and hardcoded patterns."""
        # Always ignore .git directory
        parts = path.parts
        for dir_name in ALWAYS_IGNORED_DIRS:
            if dir_name in parts:
                return True

        # Check against .gitignore patterns
        if self._gitignore_spec is not None:
            try:
                rel_path = path.relative_to(self.project_root)
                if self._gitignore_spec.match_file(str(rel_path)):
                    return True
            except ValueError:
                pass  # Path not under project root

        return False

    def _handle_event(self, event: FileSystemEvent, event_type: str) -> None:
        """Handle a file event with debouncing."""
        if event.is_directory:
            return

        # Normalize path
        src_path = (
            event.src_path.decode("utf-8") if isinstance(event.src_path, bytes) else event.src_path
        )
        path = Path(src_path)

        # Check if should be ignored
        if self._should_ignore(path):
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

        logger.debug(f"File event: {event_type} {rel_path_str}")
        self.callback(event_type, rel_path_str)

    def on_closed(self, event: FileSystemEvent) -> None:
        """Handle file close events (more reliable than on_opened)."""
        self._handle_event(event, "viewed")

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        self._handle_event(event, "modified")

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        self._handle_event(event, "created")


class FileWatcher:
    """Watch for file views (close events), modifications, and creations in the project."""

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
