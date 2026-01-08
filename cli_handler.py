from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Callable

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.styles import Style as PTStyle
from rich.console import Console
from rich.text import Text

from events import (
    AssistantMessageEvent,
    ConfirmationHandler,
    Event,
    EventHandler,
    FileViewedEvent,
    FinalOutputEvent,
    TodosUpdatedEvent,
    ToolCompletedEvent,
    ToolErrorEvent,
    ToolStartedEvent,
    UnknownContentEvent,
    WebSearchErrorEvent,
)


class CLIEventHandler(EventHandler):
    """Default CLI event handler that prints formatted output"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def handle(self, event: Event) -> None:
        # Pattern match on strongly typed events - type checker validates field access
        match event:
            case AssistantMessageEvent(text=text):
                print(f"💬 {text}")

            case ToolErrorEvent(tool_name=name, error=err):
                print(f"🛠️ Tool {name} error: {err}")

            case FileViewedEvent(path=path):
                print(f"🔍 View file: {path}")

            case WebSearchErrorEvent(error_code=code):
                print(f"web search error: {code}")

            case UnknownContentEvent(content_type=ct):
                print(f"unknown content type: {ct}")

            case FinalOutputEvent(result=result):
                print(f"💡 {result}")

            case TodosUpdatedEvent(todos=todos):
                print("--------------------------------")
                print("Todos:")
                for todo in todos:
                    status_mark = "✔" if todo.status.value == "completed" else " "
                    print(f"[{status_mark}]: {todo.title}")
                print("--------------------------------")

            case ToolStartedEvent(tool_name=name):
                if self.verbose:
                    print(f"🛠️ Starting {name}...")

            case ToolCompletedEvent(tool_name=name):
                if self.verbose:
                    print(f"✅ {name} completed")


class CLIConfirmationHandler(ConfirmationHandler):
    """CLI confirmation handler using input()"""

    def request_confirmation(
        self, tool_name: str, action: str, path: str | None, preview: str
    ) -> tuple[bool, str | None]:
        """Prompt user for confirmation via CLI"""

        # Display the preview
        if path:
            print(f"🛠️ Confirming command '{action}' on file '{path}'")
        else:
            print(f"🛠️ Confirming: {action}")
        print(preview)

        # Get user input
        answer = input("🛠️ Press Enter to continue or 'q [reason]' to skip > ")

        if answer.strip().lower().startswith("q"):
            reason = answer.strip()[1:].strip() or "no reason given"
            return (False, reason)

        return (True, None)


# ─────────────────────────────────────────────────────────────────────────────
# Slash Command Infrastructure
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SlashCommand:
    """Represents a slash command with optional subcommands."""

    name: str
    description: str
    subcommands: list["SlashCommand"] = field(default_factory=list)


SLASH_COMMANDS: list[SlashCommand] = [
    SlashCommand(name="help", description="Show available commands"),
    SlashCommand(
        name="settings",
        description="Configure settings",
        subcommands=[
            SlashCommand(
                name="edit_mode",
                description="Set edit mode",
                subcommands=[
                    SlashCommand(name="ask", description="Ask before edits"),
                    SlashCommand(name="always", description="Always allow edits"),
                    SlashCommand(name="never", description="Never allow edits"),
                ],
            ),
        ],
    ),
    SlashCommand(name="clear", description="Clear conversation history"),
    SlashCommand(name="exit", description="Exit the CLI"),
]


class SlashCommandCompleter(Completer):
    """Autocomplete for slash commands."""

    def __init__(self, commands: list[SlashCommand]):
        self.commands = commands

    def get_completions(
        self, document: Document, complete_event: object
    ) -> Generator[Completion, None, None]:
        text = document.text_before_cursor

        # Only complete if starts with /
        if not text.startswith("/"):
            return

        parts = text[1:].split(" ")

        # Find which commands to show based on current input
        current_commands = self.commands

        # Navigate through command hierarchy
        for part in parts[:-1]:
            for cmd in current_commands:
                if cmd.name == part:
                    current_commands = cmd.subcommands
                    break
            else:
                return  # No matching command found

        # Get the partial text being typed
        partial = parts[-1] if parts else ""

        # Yield matching completions
        for cmd in current_commands:
            if cmd.name.startswith(partial):
                yield Completion(
                    cmd.name,
                    start_position=-len(partial),
                    display=cmd.name,
                    display_meta=cmd.description,
                )


# ─────────────────────────────────────────────────────────────────────────────
# Styled CLI Input Handler
# ─────────────────────────────────────────────────────────────────────────────


class CLIInputHandler:
    """Styled input handler with Claude Code-like appearance."""

    def __init__(self, get_status_info: Callable[[], dict[str, str]] | None = None):
        """
        Initialize the input handler.

        Args:
            get_status_info: Optional callback that returns status info dict
                           (e.g., {"edit": "ask", "cwd": "toy-agent"})
        """
        self.get_status_info = get_status_info
        self.console = Console()
        self.completer = SlashCommandCompleter(SLASH_COMMANDS)

        # prompt_toolkit style
        self.pt_style = PTStyle.from_dict(
            {
                "prompt": "#e5c07b bold",  # Orange/yellow chevron
                "bottom-toolbar": "bg:#2d2d44 #888888",
                "bottom-toolbar.key": "#61afef bold",
                "completion-menu": "bg:#1e1e2e #cdd6f4",
                "completion-menu.completion": "bg:#1e1e2e #cdd6f4",
                "completion-menu.completion.current": "bg:#45475a #ffffff",
                "completion-menu.meta": "#888888 italic",
                "completion-menu.meta.current": "#aaaaaa italic",
            }
        )

        self.session = PromptSession(
            completer=self.completer,
            style=self.pt_style,
            complete_while_typing=True,
        )

    def _get_bottom_toolbar(self) -> FormattedText:
        """Generate the bottom toolbar content."""
        return FormattedText(
            [
                ("class:bottom-toolbar.key", " Ctrl+C "),
                ("class:bottom-toolbar", "interrupt  "),
                ("class:bottom-toolbar.key", "/help "),
                ("class:bottom-toolbar", "commands  "),
                ("class:bottom-toolbar.key", "Ctrl+D "),
                ("class:bottom-toolbar", "exit "),
            ]
        )

    def _print_context_bar(self) -> None:
        """Print the context bar above the prompt using Rich."""
        if not self.get_status_info:
            return

        status = self.get_status_info()
        if not status:
            return

        # Build styled text
        parts = []
        for key, value in status.items():
            if parts:
                parts.append(("dim", " │ "))
            parts.append(("dim", f"{key}: "))
            parts.append(("cyan", value))

        text = Text()
        for style, content in parts:
            text.append(content, style=style)

        self.console.print(text)

    def request_input(self) -> str:
        """
        Request input from the user with styled prompt.

        Returns:
            The user's input string.

        Raises:
            EOFError: If user presses Ctrl+D
            KeyboardInterrupt: If user presses Ctrl+C
        """
        # Print context bar
        self._print_context_bar()

        # Get input with styled prompt
        return self.session.prompt(
            [("class:prompt", "❯ ")],
            bottom_toolbar=self._get_bottom_toolbar,
        )
