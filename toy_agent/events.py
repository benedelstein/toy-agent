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


@dataclass
class CommandOutputEvent:
    message: str
    style: Literal["default", "error", "success", "info"] = "default"
    type: Literal["command_output"] = field(default="command_output", repr=False)


@dataclass
class AgentStartedEvent:
    prompt: str
    type: Literal["agent_started"] = field(default="agent_started", repr=False)


@dataclass
class AgentCompletedEvent:
    result: str | None
    interrupted: bool = False
    type: Literal["agent_completed"] = field(default="agent_completed", repr=False)


# Streaming events
@dataclass
class TextDeltaEvent:
    """Emitted for each text chunk during streaming."""

    text: str
    type: Literal["text_delta"] = field(default="text_delta", repr=False)


@dataclass
class ThinkingDeltaEvent:
    """Emitted for each thinking chunk during streaming."""

    thinking: str
    type: Literal["thinking_delta"] = field(default="thinking_delta", repr=False)


@dataclass
class ContentBlockStartEvent:
    """Emitted when a content block starts during streaming."""

    index: int
    block_type: str  # "text", "thinking", "tool_use"
    type: Literal["content_block_start"] = field(default="content_block_start", repr=False)


@dataclass
class ContentBlockStopEvent:
    """Emitted when a content block completes during streaming."""

    index: int
    type: Literal["content_block_stop"] = field(default="content_block_stop", repr=False)


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
        CommandOutputEvent,
        AgentStartedEvent,
        AgentCompletedEvent,
        TextDeltaEvent,
        ThinkingDeltaEvent,
        ContentBlockStartEvent,
        ContentBlockStopEvent,
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


@dataclass
class BashConfirmationResult:
    """Result of bash command confirmation with always-allow option."""

    approved: bool
    always_allow: bool = False  # If True, add command to allow list
    allow_pattern: str | None = None  # The pattern to always allow (e.g., "find")
    deny_reason: str | None = None  # Reason if denied


class BashConfirmationHandler(Protocol):
    """Protocol for bash command confirmation with always-allow option."""

    def request_bash_confirmation(self, command: str, preview: str) -> BashConfirmationResult:
        """
        Request confirmation for a bash command with options:
        - Allow (once)
        - Allow and always allow this command type
        - Deny (with optional reason)
        """
        ...


@dataclass
class MenuOption:
    """An option in a menu selection."""

    label: str
    description: str
    value: str


@dataclass
class MenuConfirmationResult:
    """Result of a menu confirmation with flexible options."""

    selected_value: str  # The value of the selected option
    approved: bool  # Convenience: True if not denied
    deny_reason: str | None = None  # Reason if denied


class MenuConfirmationHandler(Protocol):
    """Protocol for generic menu-based confirmation with customizable options."""

    def request_menu_confirmation(
        self,
        title: str,
        preview: str,
        options: list[MenuOption],
    ) -> MenuConfirmationResult:
        """
        Request confirmation via a menu with customizable options.
        - title: The title/context to display
        - preview: Content preview (e.g., diff, file content)
        - options: List of MenuOption with label, description, and value
        - returns: MenuConfirmationResult with selected value and approval status
        """
        ...


class InputHandler(Protocol):
    """Protocol for requesting user input"""

    def request_input(self, prompt: str) -> str:
        """
        Request input from the user.
        - prompt: The prompt to display to the user
        - returns: The user's input string
        """
        ...


class EventEmitter:
    """Simple event emitter for agent/tool events"""

    def __init__(self):
        self._handlers: list[EventHandler] = []
        self._confirmation_handler: ConfirmationHandler | None = None
        self._bash_confirmation_handler: BashConfirmationHandler | None = None
        self._menu_confirmation_handler: MenuConfirmationHandler | None = None
        self._input_handler: InputHandler | None = None

    def add_handler(self, handler: EventHandler) -> None:
        """Register an event handler"""
        self._handlers.append(handler)

    def remove_handler(self, handler: EventHandler) -> None:
        """Unregister an event handler"""
        self._handlers.remove(handler)

    def set_confirmation_handler(self, handler: ConfirmationHandler) -> None:
        """Set the confirmation callback handler"""
        self._confirmation_handler = handler

    def set_bash_confirmation_handler(self, handler: BashConfirmationHandler) -> None:
        """Set the bash confirmation handler"""
        self._bash_confirmation_handler = handler

    def set_menu_confirmation_handler(self, handler: MenuConfirmationHandler) -> None:
        """Set the menu confirmation handler"""
        self._menu_confirmation_handler = handler

    def set_input_handler(self, handler: InputHandler) -> None:
        """Set the input handler"""
        self._input_handler = handler

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
        return self._confirmation_handler.request_confirmation(tool_name, action, path, preview)

    def request_bash_confirmation(self, command: str, preview: str) -> BashConfirmationResult:
        """Request bash command confirmation with always-allow option."""
        if self._bash_confirmation_handler is None:
            # Default: approve once if no handler set
            return BashConfirmationResult(approved=True)
        return self._bash_confirmation_handler.request_bash_confirmation(command, preview)

    def request_menu_confirmation(
        self,
        title: str,
        preview: str,
        options: list[MenuOption],
    ) -> MenuConfirmationResult:
        """Request confirmation via a menu with customizable options."""
        if self._menu_confirmation_handler is None:
            # Default: approve if no handler set (select first option)
            return MenuConfirmationResult(
                selected_value=options[0].value if options else "allow",
                approved=True,
            )
        return self._menu_confirmation_handler.request_menu_confirmation(title, preview, options)

    def request_input(self, prompt: str) -> str:
        """Request user input via the registered handler"""
        if self._input_handler is None:
            raise RuntimeError("No input handler registered")
        return self._input_handler.request_input(prompt)
