"""Session persistence using JSONL event log format.

Each session is a .jsonl file where each line is a timestamped event:
  {"timestamp": "...", "type": "session_start", "payload": {...}}
  {"timestamp": "...", "type": "message", "payload": {"role": "user", "content": "..."}}
  {"timestamp": "...", "type": "message", "payload": {"role": "assistant", "content": [...]}}
  {"timestamp": "...", "type": "session_end", "payload": {...}}
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from anthropic.types import MessageParam

from .settings import SETTINGS_DIR

SESSIONS_DIR = SETTINGS_DIR / "sessions"


def _extract_text_from_content(content: object) -> str:
    """Extract text from a message content list."""
    if not isinstance(content, list):
        return ""
    for block in content:
        if isinstance(block, str):
            return block
        if isinstance(block, dict):
            block_text = block.get("text")
            if isinstance(block_text, str) and block_text:
                return block_text
    return ""


def _extract_summary(history: list[MessageParam]) -> str:
    """Extract first user message text, truncated to ~80 chars."""
    for msg in history:
        if msg["role"] != "user":
            continue
        content = msg["content"]
        if isinstance(content, str):
            text = content
        else:
            text = _extract_text_from_content(content)
        if text:
            return text[:80].replace("\n", " ").strip()
    return "(empty session)"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_event(f: object, event_type: str, payload: object) -> None:
    """Write a single JSONL event line."""
    line = json.dumps({"timestamp": _now_iso(), "type": event_type, "payload": payload})
    f.write(line + "\n")  # type: ignore[union-attr]


class SessionStore:
    """JSONL-based storage for agent conversation history."""

    def __init__(self, sessions_dir: Path | None = None) -> None:
        self.sessions_dir = sessions_dir or SESSIONS_DIR

    def _ensure_dir(self) -> None:
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.jsonl"

    @staticmethod
    def _generate_id() -> str:
        now = datetime.now(timezone.utc)
        short_uuid = uuid.uuid4().hex[:4]
        return f"{now.strftime('%Y%m%d-%H%M%S')}-{short_uuid}"

    def save(self, history: list[MessageParam], session_id: str | None = None) -> str:
        """Save full history as a JSONL event log. Returns session_id."""
        self._ensure_dir()

        if session_id is None:
            session_id = self._generate_id()

        file_path = self._session_path(session_id)
        summary = _extract_summary(history)

        with open(file_path, "w") as f:
            _write_event(
                f,
                "session_start",
                {
                    "session_id": session_id,
                    "summary": summary,
                    "message_count": len(history),
                },
            )
            for msg in history:
                _write_event(f, "message", msg)
            _write_event(f, "session_end", {})

        return session_id

    def append_message(self, session_id: str, message: MessageParam) -> None:
        """Append a single message event to an existing session."""
        file_path = self._session_path(session_id)
        with open(file_path, "a") as f:
            _write_event(f, "message", message)

    def load(self, session_id: str) -> list[MessageParam]:
        """Load history by replaying message events from a JSONL session file."""
        file_path = self._session_path(session_id)
        if not file_path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")

        history: list[MessageParam] = []
        with open(file_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                event = json.loads(line)
                if event.get("type") == "message":
                    history.append(event["payload"])
        return history

    def list_sessions(self) -> list[dict[str, str | int]]:
        """Return metadata for all sessions, sorted most recent first."""
        if not self.sessions_dir.exists():
            return []

        sessions: list[dict[str, str | int]] = []
        for file_path in self.sessions_dir.glob("*.jsonl"):
            try:
                # Read only the first line (session_start) for metadata
                with open(file_path) as f:
                    first_line = f.readline().strip()
                if not first_line:
                    continue
                event = json.loads(first_line)
                if event.get("type") != "session_start":
                    continue
                payload = event["payload"]
                sessions.append(
                    {
                        "session_id": payload["session_id"],
                        "created_at": event.get("timestamp", ""),
                        "message_count": payload.get("message_count", 0),
                        "summary": payload.get("summary", ""),
                    }
                )
            except (json.JSONDecodeError, KeyError, OSError):
                continue

        sessions.sort(key=lambda s: str(s.get("created_at", "")), reverse=True)
        return sessions

    def delete(self, session_id: str) -> bool:
        """Delete a session file. Returns True if deleted."""
        file_path = self._session_path(session_id)
        if file_path.exists():
            file_path.unlink()
            return True
        return False
