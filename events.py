from dataclasses import dataclass, field
from typing import Annotated, Literal, Protocol, Union
from pydantic import Field


# Strongly typed event classes with discriminated union
@dataclass
class ToolStartedEvent:
    tool_name: str
    input: dict
    type: Literal["tool_started"] = field(default="tool_started", repr=False)


@dataclass
class ToolCompletedEvent:
    tool_name: str
    output: dict | None
    type: Literal["tool_completed"] = field(default="tool_completed", repr=False)


@dataclass
class ToolErrorEvent:
    tool_name: str
    error: str
    type: Literal["tool_error"] = field(default="tool_error", repr=False)


@dataclass
class AssistantMessageEvent:
    text: str
    type: Literal["assistant_message"] = field(default="assistant_message", repr=False)


@dataclass
class FileViewedEvent:
    path: str
    type: Literal["file_viewed"] = field(default="file_viewed", repr=False)


@dataclass
class WebSearchErrorEvent:
    error_code: str
    type: Literal["web_search_error"] = field(default="web_search_error", repr=False)


@dataclass
class UnknownContentEvent:
    content_type: str
    type: Literal["unknown_content"] = field(default="unknown_content", repr=False)


@dataclass
class FinalOutputEvent:
    result: str
    type: Literal["final_output"] = field(default="final_output", repr=False)


@dataclass
class TodosUpdatedEvent:
    todos: list  # List of Todo objects
    type: Literal["todos_updated"] = field(default="todos_updated", repr=False)


# Discriminated union - type checker knows which fields are available
Event = Annotated[
    Union[
        ToolStartedEvent,
        ToolCompletedEvent,
        ToolErrorEvent,
        AssistantMessageEvent,
        FileViewedEvent,
        WebSearchErrorEvent,
        UnknownContentEvent,
        FinalOutputEvent,
        TodosUpdatedEvent,
    ],
    Field(discriminator="type"),
]


class EventHandler(Protocol):
    """Protocol for event handlers"""

    def handle(self, event: Event) -> None: ...


class ConfirmationHandler(Protocol):
    """Protocol for confirmation callbacks - returns True to proceed, False to skip"""

    def request_confirmation(
        self, tool_name: str, action: str, path: str | None, preview: str
    ) -> tuple[bool, str | None]:
        """
        Returns (approved, reason).
        - approved: True to proceed, False to skip
        - reason: Optional reason if skipped
        """
        ...


class EventEmitter:
    """Simple event emitter for agent/tool events"""

    def __init__(self):
        self._handlers: list[EventHandler] = []
        self._confirmation_handler: ConfirmationHandler | None = None

    def add_handler(self, handler: EventHandler) -> None:
        """Register an event handler"""
        self._handlers.append(handler)

    def remove_handler(self, handler: EventHandler) -> None:
        """Unregister an event handler"""
        self._handlers.remove(handler)

    def set_confirmation_handler(self, handler: ConfirmationHandler) -> None:
        """Set the confirmation callback handler"""
        self._confirmation_handler = handler

    def emit(self, event: Event) -> None:
        """Emit an event to all registered handlers"""
        for handler in self._handlers:
            handler.handle(event)

    def request_confirmation(
        self, tool_name: str, action: str, path: str | None, preview: str
    ) -> tuple[bool, str | None]:
        """Request user confirmation via the registered handler"""
        if self._confirmation_handler is None:
            # Default: always approve if no handler set
            return (True, None)
        return self._confirmation_handler.request_confirmation(
            tool_name, action, path, preview
        )
