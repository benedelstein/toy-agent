"""Session persistence: save and resume agent conversation history."""

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


class SessionStore:
    """JSON-based storage for agent conversation history."""

    def __init__(self, sessions_dir: Path | None = None) -> None:
        self.sessions_dir = sessions_dir or SESSIONS_DIR

    def _ensure_dir(self) -> None:
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _generate_id() -> str:
        now = datetime.now(timezone.utc)
        short_uuid = uuid.uuid4().hex[:4]
        return f"{now.strftime('%Y%m%d-%H%M%S')}-{short_uuid}"

    @staticmethod
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

    def save(self, history: list[MessageParam], session_id: str | None = None) -> str:
        """Save history to disk. Returns session_id."""
        self._ensure_dir()

        if session_id is None:
            session_id = self._generate_id()

        now = datetime.now(timezone.utc).isoformat()
        data = {
            "session_id": session_id,
            "created_at": now,
            "updated_at": now,
            "summary": self._extract_summary(history),
            "message_count": len(history),
            "history": history,
        }

        file_path = self.sessions_dir / f"{session_id}.json"

        # If overwriting, preserve original created_at
        if file_path.exists():
            try:
                with open(file_path) as f:
                    existing = json.load(f)
                data["created_at"] = existing.get("created_at", now)
            except (json.JSONDecodeError, OSError):
                pass

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

        return session_id

    def load(self, session_id: str) -> list[MessageParam]:
        """Load history from a session file."""
        file_path = self.sessions_dir / f"{session_id}.json"
        if not file_path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")

        with open(file_path) as f:
            data = json.load(f)

        history: list[MessageParam] = data["history"]
        return history

    def list_sessions(self) -> list[dict[str, str | int]]:
        """Return metadata for all sessions, sorted most recent first."""
        if not self.sessions_dir.exists():
            return []

        sessions: list[dict[str, str | int]] = []
        for file_path in self.sessions_dir.glob("*.json"):
            try:
                with open(file_path) as f:
                    data = json.load(f)
                sessions.append(
                    {
                        "session_id": data["session_id"],
                        "created_at": data.get("created_at", ""),
                        "message_count": data.get("message_count", 0),
                        "summary": data.get("summary", ""),
                    }
                )
            except (json.JSONDecodeError, KeyError, OSError):
                continue

        sessions.sort(key=lambda s: str(s.get("created_at", "")), reverse=True)
        return sessions

    def delete(self, session_id: str) -> bool:
        """Delete a session file. Returns True if deleted."""
        file_path = self.sessions_dir / f"{session_id}.json"
        if file_path.exists():
            file_path.unlink()
            return True
        return False
