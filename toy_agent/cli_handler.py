import sys
from dataclasses import dataclass, field
from typing import Callable

from prompt_toolkit import PromptSession
from prompt_toolkit.application import Application
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style as PTStyle
from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax

from toy_agent.logger import logger

from .events import (
    AgentCompletedEvent,
    AgentStartedEvent,
    AssistantMessageEvent,
    BashConfirmationHandler,
    BashConfirmationResult,
    CommandOutputEvent,
    ConfirmationHandler,
    ContentBlockStartEvent,
    ContentBlockStopEvent,
    Event,
    EventHandler,
    FileViewedEvent,
    FinalOutputEvent,
    InputHandler,
    MenuConfirmationHandler,
    MenuConfirmationResult,
    MenuOption,
    TextDeltaEvent,
    ThinkingDeltaEvent,
    TodosUpdatedEvent,
    ToolCompletedEvent,
    ToolErrorEvent,
    ToolStartedEvent,
    UnknownContentEvent,
    WebSearchErrorEvent,
)

# ─────────────────────────────────────────────────────────────────────────────
# Slash Command Infrastructure
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SlashCommand:
    """Definition of a slash command with optional subcommands."""

    name: str
    description: str
    subcommands: list[str] = field(default_factory=list)


SLASH_COMMANDS: list[SlashCommand] = [
    SlashCommand("/help", "Show available commands"),
    SlashCommand("/settings", "Configure settings", ["edit_mode"]),
    SlashCommand("/debug", "Toggle debug mode"),
    SlashCommand("/clear", "Clear conversation history"),
    SlashCommand("/exit", "Exit the CLI"),
]

# Subcommand options for nested completion
SUBCOMMAND_OPTIONS: dict[str, list[str]] = {
    "edit_mode": ["ask", "always", "never"],
}


class SlashCommandCompleter(Completer):
    """Autocomplete for slash commands with nested subcommand support."""

    def __init__(self, commands: list[SlashCommand]):
        self.commands = commands

    def get_completions(self, document: Document, complete_event):
        text = document.text_before_cursor

        # Only complete if starts with /
        if not text.startswith("/"):
            return

        parts = text.split()

        if len(parts) == 0 or (len(parts) == 1 and not text.endswith(" ")):
            # Completing the command name
            word = parts[0] if parts else "/"
            for cmd in self.commands:
                if cmd.name.startswith(word):
                    yield Completion(
                        cmd.name,
                        start_position=-len(word),
                        display=cmd.name,
                        display_meta=cmd.description,
                    )
        elif len(parts) >= 1:
            # Find the command
            cmd_name = parts[0]
            cmd = next((c for c in self.commands if c.name == cmd_name), None)
            if not cmd:
                return

            if len(parts) == 1 or (len(parts) == 2 and not text.endswith(" ")):
                # Completing first subcommand
                partial = parts[1] if len(parts) > 1 else ""
                for subcmd in cmd.subcommands:
                    if subcmd.startswith(partial):
                        yield Completion(
                            subcmd,
                            start_position=-len(partial),
                            display=subcmd,
                        )
            elif len(parts) == 2 or (len(parts) == 3 and not text.endswith(" ")):
                # Completing subcommand options (e.g., edit_mode values)
                subcmd = parts[1]
                if subcmd in SUBCOMMAND_OPTIONS:
                    partial = parts[2] if len(parts) > 2 else ""
                    for option in SUBCOMMAND_OPTIONS[subcmd]:
                        if option.startswith(partial):
                            yield Completion(
                                option,
                                start_position=-len(partial),
                                display=option,
                            )


class CLIEventHandler(EventHandler):
    """Default CLI event handler that prints formatted output"""

    def __init__(self, verbose: bool = False, stream_output: bool = True):
        self.verbose = verbose
        self.stream_output = stream_output  # Whether to stream text deltas
        self.console = Console()
        self._status = None  # Track active status spinner
        self._streaming_text = False  # Track if we're mid-stream
        self._text_prefix_printed = False  # Track if we printed the text prefix

    def handle(self, event: Event) -> None:
        # Pattern match on strongly typed events - type checker validates field access
        match event:
            case AgentStartedEvent():
                # Start loading spinner
                self._status = self.console.status(
                    "Thinking... (ctrl+c to interrupt)", spinner="earth"
                )
                self._status.start()

            case AgentCompletedEvent():
                # Stop loading spinner
                logger.debug("Agent completed")
                if self._status:
                    self._status.stop()
                    self._status = None

            case AssistantMessageEvent(text=text):
                # Skip if we already streamed this text
                logger.debug("Assistant message event received\n")
                if not self.stream_output:
                    markdown = Markdown("💬 " + text)
                    self.console.print(markdown)

            case CommandOutputEvent(message=msg, style=style):
                logger.debug("Command output event received\n")
                match style:
                    case "error":
                        self.console.print(f"[red]{msg}[/red]")
                    case "success":
                        self.console.print(f"[green]{msg}[/green]")
                    case "info":
                        self.console.print(f"[cyan]{msg}[/cyan]")
                    case _:
                        self.console.print(msg)

            case ToolErrorEvent(tool_name=name, error=err):
                logger.debug("Tool error event received\n")
                self.console.print(f"🛠️ [bold red]Tool {name} error:[/bold red] {err}")

            case FileViewedEvent(path=path):
                self.console.print(f"🔍 [bold blue]View:[/bold blue] {path}")

            case WebSearchErrorEvent(error_code=code):
                self.console.print(f"🛠️ [bold red]Web search error:[/bold red] {code}")

            case UnknownContentEvent(content_type=ct):
                self.console.print(f"🛠️ [bold red]Unknown content type:[/bold red] {ct}")

            case FinalOutputEvent(result=result):
                logger.debug("Final output event received")
                # Indent newlines to align with text after emoji (3 spaces)
                indented_result = result.replace("\n", "\n   ")
                markdown = Markdown("💡 " + indented_result)
                self.console.print(markdown)

            case TodosUpdatedEvent(todos=todos):
                self.console.print("--------------------------------")
                self.console.print("Todos:")
                for todo in todos:
                    status_mark = "✔" if todo.status.value == "completed" else " "
                    self.console.print(f"[{status_mark}]: {todo.title}")
                self.console.print("--------------------------------")

            case ToolStartedEvent(tool_name=name, input=input):
                if self.verbose:
                    self.console.print(
                        f"🛠️ [bold blue]Using {name}...[/bold blue]: {str(input)[0:100]}"
                    )

            case ToolCompletedEvent(tool_name=name):
                if self.verbose:
                    self.console.print(f"🛠️ [bold green]{name} completed[/bold green]")

            # Streaming events
            case ContentBlockStartEvent(block_type=block_type):
                # Stop spinner on any content block start
                if self._status:
                    self._status.stop()
                    self._status = None

                if block_type == "text" and self.stream_output:
                    # Print the prefix once using stdout directly
                    if not self._text_prefix_printed:
                        sys.stdout.write("💬 ")
                        sys.stdout.flush()
                        self._text_prefix_printed = True
                    self._streaming_text = True

            case TextDeltaEvent(text=text):
                if self.stream_output and self._streaming_text:
                    # Print text delta directly to stdout for real-time streaming
                    # Add indentation after newlines to align with text after emoji
                    indented_text = text.replace("\n", "\n   ")
                    sys.stdout.write(indented_text)
                    sys.stdout.flush()

            case ContentBlockStopEvent():
                if self._streaming_text:
                    # End the streaming line
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                    self._streaming_text = False
                    self._text_prefix_printed = False

            case ThinkingDeltaEvent():
                # Optionally display thinking (currently silent)
                pass


class CLIConfirmationHandler(ConfirmationHandler):
    """CLI confirmation handler using input()"""

    def __init__(self):
        self.console = Console()

    def request_confirmation(
        self, tool_name: str, action: str, path: str | None, preview: str
    ) -> tuple[bool, str | None]:
        """Prompt user for confirmation via CLI"""

        # Display the preview
        if path:
            self.console.print(
                f"🛠️ Confirm '[bold blue]{action}[/bold blue]' on file '[bold blue]{path}[/bold blue]'"
            )
        else:
            self.console.print(f"🛠️ [bold blue]Confirming:[/bold blue] {action}")

        # Use Rich Syntax highlighting for diff output
        if preview.startswith("---") or preview.startswith("@@"):
            syntax = Syntax(preview, "diff", theme="monokai", line_numbers=True)  # type: ignore
            self.console.print(syntax)
        else:
            self.console.print(preview)

        # Get user input
        answer = self.console.input(
            "[bold]🛠️ Press Enter to continue or 'q <reason>' to skip > [/bold]"
        )

        if answer.strip().lower().startswith("q"):
            reason = answer.strip()[1:].strip() or "no reason given"
            return (False, reason)

        return (True, None)


class CLIInputHandler(InputHandler):
    """CLI input handler with styled input bar like Claude Code CLI"""

    def __init__(
        self,
        prompt_prefix: str = "❯",
        get_status_info: Callable[[], dict[str, str]] | None = None,
    ):
        self.prompt_prefix = prompt_prefix
        self.console = Console()
        self.get_status_info = get_status_info  # Callback to get current status (e.g., edit mode)

        # Create completer for slash commands
        self.completer = SlashCommandCompleter(SLASH_COMMANDS)

        # Claude Code-inspired style theme
        self.pt_style = PTStyle.from_dict(
            {
                "prompt": "#e5c07b bold",  # Orange/yellow chevron
                "bottom-toolbar": "bg:#2d2d44 #666666",
                "bottom-toolbar.key": "#61afef bold",  # Blue for shortcuts
                "completion-menu": "bg:#1e1e2e #cdd6f4",
                "completion-menu.completion": "bg:#1e1e2e #cdd6f4",
                "completion-menu.completion.current": "bg:#45475a #ffffff",
                "completion-menu.meta": "bg:#1e1e2e #888888 italic",
                "completion-menu.meta.completion.current": "bg:#45475a #aaaaaa italic",
            }
        )

        # Create persistent session for better UX
        self.session = PromptSession(
            completer=self.completer,
            style=self.pt_style,
            complete_while_typing=True,
        )

    def _get_toolbar(self) -> HTML:
        """Generate bottom toolbar with keyboard hints."""
        return HTML(
            "<b>Ctrl+C</b> interrupt  │  <b>/help</b> commands  │  <b>Ctrl+C</b> twice to exit"
        )

    def _print_context_bar(self) -> None:
        """Print context bar above the prompt using Rich."""
        if not self.get_status_info:
            return

        status_info = self.get_status_info()
        if not status_info:
            return

        # Build status line
        status_parts = []
        for key, value in status_info.items():
            status_parts.append(f"[dim]{key}:[/dim] [#61afef]{value}[/#61afef]")

        status_text = "  │  ".join(status_parts)
        self.console.print(f"  {status_text}")

    def request_input(self, prompt_text: str) -> str:
        """Request input from user via CLI with styled input bar"""
        # Print context bar above the prompt
        self._print_context_bar()

        # Use prompt_toolkit PromptSession for input with autocomplete
        try:
            user_input = self.session.prompt(
                [("class:prompt", f"{self.prompt_prefix} ")],
                bottom_toolbar=self._get_toolbar,
            )
        except (EOFError, KeyboardInterrupt):
            raise KeyboardInterrupt

        return user_input


# ─────────────────────────────────────────────────────────────────────────────
# Generic Menu Selection with Arrow-Key Navigation
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class MenuSelectionResult:
    """Result of a menu selection."""

    selected_index: int
    selected_value: str
    deny_reason: str | None = None


def show_menu_selection(
    options: list[MenuOption],
    deny_option_value: str = "deny",
) -> MenuSelectionResult:
    """
    Generic menu selection with arrow-key navigation.

    Args:
        options: List of MenuOption to display
        deny_option_value: The value that triggers reason input (default: "deny")

    Returns:
        MenuSelectionResult with selected index, value, and optional deny reason
    """
    # State for the menu
    selected_index = 0
    deny_reason = ""
    entering_reason = False

    # Find the deny option index for escape/ctrl+c behavior
    deny_index = next(
        (i for i, opt in enumerate(options) if opt.value == deny_option_value),
        len(options) - 1,  # Default to last option if no deny option found
    )

    # Key bindings
    kb = KeyBindings()

    @kb.add("up")
    def move_up(event) -> None:  # type: ignore
        nonlocal selected_index, entering_reason
        if not entering_reason:
            selected_index = (selected_index - 1) % len(options)

    @kb.add("down")
    def move_down(event) -> None:  # type: ignore
        nonlocal selected_index, entering_reason
        if not entering_reason:
            selected_index = (selected_index + 1) % len(options)

    @kb.add("enter")
    def confirm(event) -> None:  # type: ignore
        nonlocal entering_reason
        if options[selected_index].value == deny_option_value and not entering_reason:
            entering_reason = True
        else:
            event.app.exit(result=selected_index)

    @kb.add("escape")
    def cancel(event) -> None:  # type: ignore
        nonlocal entering_reason, selected_index
        if entering_reason:
            entering_reason = False
        else:
            # Treat escape as deny
            selected_index = deny_index
            event.app.exit(result=selected_index)

    @kb.add("c-c")
    def ctrl_c(event) -> None:  # type: ignore
        nonlocal selected_index
        # Treat Ctrl+C as deny
        selected_index = deny_index
        event.app.exit(result=selected_index)

    # Handle text input for deny reason
    @kb.add("<any>")
    def handle_key(event) -> None:  # type: ignore
        nonlocal deny_reason, entering_reason
        if entering_reason:
            key = event.data
            if key == "\x7f":  # Backspace
                deny_reason = deny_reason[:-1]
            elif len(key) == 1 and key.isprintable():
                deny_reason += key

    def get_formatted_text() -> list[tuple[str, str]]:
        """Generate the menu display."""
        lines: list[tuple[str, str]] = []
        lines.append(("", "\n"))

        for i, opt in enumerate(options):
            if i == selected_index:
                prefix = "  > "
                style = "bold #61afef"  # Blue highlight
            else:
                prefix = "    "
                style = ""

            lines.append((style, f"{prefix}{opt.label}\n"))
            if i == selected_index:
                lines.append(("italic #888888", f"      {opt.description}\n"))

        # Show deny reason input if entering reason
        if entering_reason:
            lines.append(("", "\n"))
            lines.append(("bold", "  Reason (optional, press Enter to confirm): "))
            lines.append(("#e5c07b", deny_reason))
            lines.append(("", "_\n"))

        lines.append(("", "\n"))
        lines.append(("dim", "  Use ↑↓ to navigate, Enter to select, Esc to cancel\n"))

        return lines

    # Create the application
    layout = Layout(HSplit([Window(FormattedTextControl(get_formatted_text))]))

    style = PTStyle.from_dict(
        {
            "": "#ffffff",
        }
    )

    app: Application[int] = Application(
        layout=layout,
        key_bindings=kb,
        style=style,
        full_screen=False,
    )

    # Run the application
    try:
        result_index = app.run()
    except (EOFError, KeyboardInterrupt):
        result_index = deny_index

    if result_index is None:
        result_index = deny_index

    return MenuSelectionResult(
        selected_index=result_index,
        selected_value=options[result_index].value,
        deny_reason=deny_reason if deny_reason else None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Generic Menu Confirmation Handler
# ─────────────────────────────────────────────────────────────────────────────


class CLIMenuConfirmationHandler(MenuConfirmationHandler):
    """CLI menu confirmation handler with arrow-key selection for generic confirmations."""

    def __init__(self) -> None:
        self.console = Console()

    def request_menu_confirmation(
        self,
        title: str,
        preview: str,
        options: list[MenuOption],
    ) -> MenuConfirmationResult:
        """Show interactive menu for generic confirmation."""
        # Display the title
        self.console.print(f"\n🛠️ [bold blue]{title}[/bold blue]")

        # Display the preview with appropriate formatting
        if preview:
            if preview.startswith("---") or preview.startswith("@@"):
                # It's a diff - use syntax highlighting
                syntax = Syntax(preview, "diff", theme="monokai", line_numbers=True)  # type: ignore
                self.console.print(syntax)
            else:
                # Regular preview - show with indentation
                self.console.print(
                    f"   [dim]{preview[:500]}{'...' if len(preview) > 500 else ''}[/dim]"
                )

        # Use the generic menu selection
        result = show_menu_selection(options, deny_option_value="deny")

        # Determine if approved based on selected value
        approved = result.selected_value != "deny"

        return MenuConfirmationResult(
            selected_value=result.selected_value,
            approved=approved,
            deny_reason=result.deny_reason,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Bash Confirmation Handler (uses generic menu)
# ─────────────────────────────────────────────────────────────────────────────


class CLIBashConfirmationHandler(BashConfirmationHandler):
    """CLI bash confirmation handler with arrow-key selection menu."""

    def __init__(self) -> None:
        self.console = Console()

    def _get_base_command(self, command: str) -> str:
        """Extract the base command (first word) from a full command."""
        parts = command.strip().split()
        return parts[0] if parts else command

    def _create_options(self, base_command: str) -> list[MenuOption]:
        """Create the menu options."""
        return [
            MenuOption(
                label="Allow",
                description="Run this command once",
                value="allow",
            ),
            MenuOption(
                label=f"Always allow '{base_command}' commands",
                description="Add to allow list for this session",
                value="always",
            ),
            MenuOption(
                label="Deny",
                description="Skip this command",
                value="deny",
            ),
        ]

    def request_bash_confirmation(self, command: str, preview: str) -> BashConfirmationResult:
        """Show interactive menu for bash command confirmation."""
        base_command = self._get_base_command(command)
        options = self._create_options(base_command)

        # Display the command preview
        self.console.print(f"\n🛠️ [bold blue]Bash command:[/bold blue] {command}")
        if preview and preview != f"Running bash command: {command}":
            self.console.print(f"   [dim]{preview}[/dim]")

        # Use the generic menu selection
        result = show_menu_selection(options, deny_option_value="deny")

        if result.selected_value == "allow":
            return BashConfirmationResult(approved=True)
        elif result.selected_value == "always":
            return BashConfirmationResult(
                approved=True,
                always_allow=True,
                allow_pattern=base_command,
            )
        else:  # deny
            return BashConfirmationResult(
                approved=False,
                deny_reason=result.deny_reason,
            )
