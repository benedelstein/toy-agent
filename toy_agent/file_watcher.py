"""File watcher for IDE integration - monitors file access and modifications."""
import threading
from pathlib import Path
from typing import Callable, Set

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


class FileEventHandler(FileSystemEventHandler):
    """Handle file system events and notify the agent."""

    def __init__(self, callback: Callable[[str, str], None], project_root: Path):
        self.callback = callback
        self.project_root = project_root
        self.recently_viewed: Set[str] = set()

    def on_opened(self, event: FileSystemEvent) -> None:
        """Handle file open events (macOS/Linux with appropriate tools)."""
        if not event.is_directory:
            # Ensure src_path is a string
            src_path = event.src_path.decode('utf-8') if isinstance(event.src_path, bytes) else event.src_path
            rel_path = Path(src_path).relative_to(self.project_root)
            print(f"File opened: {rel_path}")
            self.callback("opened", str(rel_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        # Ensure src_path is a string
        src_path = event.src_path.decode('utf-8') if isinstance(event.src_path, bytes) else event.src_path

        if not event.is_directory and src_path.endswith(('.py', '.md', '.txt', '.json')):
            rel_path = Path(src_path).relative_to(self.project_root)
            # Debounce multiple modify events
            if str(rel_path) not in self.recently_viewed:
                self.recently_viewed.add(str(rel_path))
                self.callback("modified", str(rel_path))
                # Clear after short delay
                threading.Timer(1.0, lambda: self.recently_viewed.discard(str(rel_path))).start()


class FileWatcher:
    """Watch for file access and modifications in the project."""

    def __init__(self, project_root: str, callback: Callable[[str, str], None]):
        self.project_root = Path(project_root)
        self.callback = callback
        self.observer = Observer()
        self.handler = FileEventHandler(callback, self.project_root)

    def start(self):
        """Start watching for file events."""
        self.observer.schedule(self.handler, str(self.project_root), recursive=True)
        self.observer.start()

    def stop(self):
        """Stop watching for file events."""
        self.observer.stop()
        self.observer.join()


# Example integration with agent
def inject_file_event(event_type: str, file_path: str, agent):
    """Inject a system message about file events into the agent's history."""
    system_msg = f"<system>The user {event_type} the file {file_path} in their editor.</system>"

    # Add to agent's message history as a system notification
    # This would need to be implemented in your Agent class
    if hasattr(agent, 'inject_system_message'):
        agent.inject_system_message(system_msg)
