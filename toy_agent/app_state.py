from dataclasses import dataclass, field
from time import time

from .todo import Todo


@dataclass
class FileEvent:
    """Represents a file event from the file watcher."""
    event_type: str
    file_path: str
    timestamp: float


@dataclass
class AppState:
    """Global application state."""
    todos: list[Todo] = field(default_factory=list)
    file_events: list[FileEvent] = field(default_factory=list)

    def add_file_event(self, event_type: str, file_path: str) -> None:
        """Add a file event, deduplicating by file path."""
        # If file already has an event, just update timestamp
        for event in self.file_events:
            if event.file_path == file_path:
                event.timestamp = time()
                event.event_type = event_type
                return
        self.file_events.append(FileEvent(event_type, file_path, time()))

    def get_and_clear_recent_events(self, ttl_seconds: float = 60.0) -> list[FileEvent]:
        """Get events from the last ttl_seconds, then clear all events."""
        now = time()
        recent = [e for e in self.file_events if (now - e.timestamp) <= ttl_seconds]
        self.file_events.clear()
        return recent
