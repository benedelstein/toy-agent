from dataclasses import dataclass, field

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style as PTStyle
from rich.console import Console
from rich.markdown import Markdown

from .events import (
    AssistantMessageEvent,
    ConfirmationHandler,
    Event,
    EventHandler,
    FileViewedEvent,
    FinalOutputEvent,
    InputHandler,
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

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.console = Console()

    def handle(self, event: Event) -> None:
        # Pattern match on strongly typed events - type checker validates field access
        match event:
            case AssistantMessageEvent(text=text):
                markdown = Markdown("💬 " + text)
                self.console.print(markdown)

            case ToolErrorEvent(tool_name=name, error=err):
                self.console.print(f"🛠️ [bold red]Tool {name} error:[/bold red] {err}")

            case FileViewedEvent(path=path):
                self.console.print(f"🔍 [bold blue]View:[/bold blue] {path}")

            case WebSearchErrorEvent(error_code=code):
                self.console.print(f"🛠️ [bold red]Web search error:[/bold red] {code}")

            case UnknownContentEvent(content_type=ct):
                self.console.print(f"🛠️ [bold red]Unknown content type:[/bold red] {ct}")

            case FinalOutputEvent(result=result):
                markdown = Markdown("💡 " + result)
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
                    self.console.print(f"🛠️ [bold blue]Using {name}...[/bold blue]: {str(input)[0:100]}")

            case ToolCompletedEvent(tool_name=name):
                if self.verbose:
                    self.console.print(f"🛠️ [bold green]{name} completed[/bold green]")


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
            self.console.print(f"🛠️ Confirming command '[bold blue]{action}[/bold blue]' on file '[bold blue]{path}[/bold blue]'")
        else:
            self.console.print(f"🛠️ [bold blue]Confirming:[/bold blue] {action}")
        self.console.print(preview)

        # Get user input
        answer = self.console.input("[bold]🛠️ Press Enter to continue or 'q <reason>' to skip > [/bold]")

        if answer.strip().lower().startswith("q"):
            reason = answer.strip()[1:].strip() or "no reason given"
            return (False, reason)

        return (True, None)


class CLIInputHandler(InputHandler):
    """CLI input handler with styled input bar like Claude Code CLI"""

    def __init__(self, prompt_prefix: str = "❯", get_status_info: callable = None):
        self.prompt_prefix = prompt_prefix
        self.console = Console()
        self.get_status_info = get_status_info  # Callback to get current status (e.g., edit mode)

        # Create completer for slash commands
        self.completer = SlashCommandCompleter(SLASH_COMMANDS)

        # Claude Code-inspired style theme
        self.pt_style = PTStyle.from_dict({
            'prompt': '#e5c07b bold',  # Orange/yellow chevron
            'bottom-toolbar': 'bg:#2d2d44 #666666',
            'bottom-toolbar.key': '#61afef bold',  # Blue for shortcuts
            'completion-menu': 'bg:#1e1e2e #cdd6f4',
            'completion-menu.completion': 'bg:#1e1e2e #cdd6f4',
            'completion-menu.completion.current': 'bg:#45475a #ffffff',
            'completion-menu.meta': 'bg:#1e1e2e #888888 italic',
            'completion-menu.meta.completion.current': 'bg:#45475a #aaaaaa italic',
        })

        # Create persistent session for better UX
        self.session = PromptSession(
            completer=self.completer,
            style=self.pt_style,
            complete_while_typing=True,
        )

    def _get_toolbar(self) -> HTML:
        """Generate bottom toolbar with keyboard hints."""
        return HTML(
            '<b>Ctrl+C</b> interrupt  │  '
            '<b>/help</b> commands  │  '
            '<b>Ctrl+D</b> exit'
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
                [('class:prompt', f'{self.prompt_prefix} ')],
                bottom_toolbar=self._get_toolbar,
            )
        except (EOFError, KeyboardInterrupt):
            raise KeyboardInterrupt

        return user_input
