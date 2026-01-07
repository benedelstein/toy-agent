# Toy Agent - A simple agentic coding assistant
from .agent import Agent
from .settings import Settings, SETTINGS, EditMode
from .events import EventEmitter

__version__ = "0.1.0"
__all__ = ["Agent", "Settings", "SETTINGS", "EditMode", "EventEmitter"]
