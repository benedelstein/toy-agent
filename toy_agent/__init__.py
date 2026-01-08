# Toy Agent - A simple agentic coding assistant
from .agent import Agent
from .events import EventEmitter
from .settings import SETTINGS, EditMode, Settings

__version__ = "0.1.0"
__all__ = ["Agent", "Settings", "SETTINGS", "EditMode", "EventEmitter"]
