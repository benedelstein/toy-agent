import json
from enum import Enum
from pathlib import Path


class EditMode(Enum):
    ASK = "ask"
    ALWAYS = "always"
    NEVER = "never"


# Settings file location (like .claude/settings.local.json)
SETTINGS_DIR = Path(".toy-agent")
SETTINGS_FILE = SETTINGS_DIR / "settings.json"


class Settings:
    edit_mode: EditMode = EditMode.ASK
    allowed_bash_commands: list[str]

    def __init__(self) -> None:
        self.edit_mode = EditMode.ASK
        self.allowed_bash_commands = []
        self._load()

    def _load(self) -> None:
        """Load settings from .toy-agent/settings.json if it exists."""
        if not SETTINGS_FILE.exists():
            return

        try:
            with open(SETTINGS_FILE) as f:
                data = json.load(f)

            if "edit_mode" in data:
                self.edit_mode = EditMode(data["edit_mode"])
            if "allowed_bash_commands" in data:
                self.allowed_bash_commands = data["allowed_bash_commands"]
        except (json.JSONDecodeError, ValueError, KeyError):
            # Invalid settings file, use defaults
            pass

    def _save(self) -> None:
        """Save settings to .toy-agent/settings.json."""
        SETTINGS_DIR.mkdir(exist_ok=True)

        data = {
            "edit_mode": self.edit_mode.value,
            "allowed_bash_commands": self.allowed_bash_commands,
        }

        with open(SETTINGS_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def is_bash_command_allowed(self, command: str) -> bool:
        """Check if a bash command matches any allowed pattern.

        Patterns are command prefixes - e.g., 'find' matches 'find .' and 'find /path'.
        """
        command_parts = command.strip().split()
        if not command_parts:
            return False

        base_command = command_parts[0]

        for pattern in self.allowed_bash_commands:
            # Exact match on base command (e.g., "find" matches "find .")
            if pattern == base_command:
                return True
            # Full command prefix match (e.g., "git status" matches "git status --short")
            if command.strip().startswith(pattern):
                return True

        return False

    def add_allowed_bash_command(self, pattern: str) -> None:
        """Add a bash command pattern to the allow list and save."""
        if pattern not in self.allowed_bash_commands:
            self.allowed_bash_commands.append(pattern)
            self._save()


# Initialize settings (loads from file if exists)
SETTINGS = Settings()
