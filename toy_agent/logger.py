"""Global logging utility for toy-agent."""

from typing import Any


class Logger:
    """Simple logger that respects debug mode from settings."""

    def __init__(self):
        self._debug_enabled = False

    def set_debug(self, enabled: bool) -> None:
        """Enable or disable debug logging."""
        self._debug_enabled = enabled

    @property
    def debug_enabled(self) -> bool:
        """Check if debug mode is enabled."""
        return self._debug_enabled

    def debug(self, *args: Any, **kwargs: Any) -> None:
        """Print debug message if debug mode is enabled."""
        if self._debug_enabled:
            print("[DEBUG]", *args, **kwargs)

    def info(self, *args: Any, **kwargs: Any) -> None:
        """Print info message (always shown)."""
        print("[INFO]", *args, **kwargs)

    def error(self, *args: Any, **kwargs: Any) -> None:
        """Print error message (always shown)."""
        print("[ERROR]", *args, **kwargs)


# Global logger instance
logger = Logger()
