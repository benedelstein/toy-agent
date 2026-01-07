from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.style import Style
from rich.live import Live
from prompt_toolkit import prompt
from prompt_toolkit.styles import Style as PTStyle
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

    def __init__(self, prompt_prefix: str = "> ", get_status_info: callable = None):
        self.prompt_prefix = prompt_prefix
        self.console = Console()
        self.get_status_info = get_status_info  # Callback to get current status (e.g., edit mode)

        # prompt_toolkit style for the input
        self.pt_style = PTStyle.from_dict({
            'prompt': 'ansicyan bold',
        })

    def request_input(self, prompt_text: str) -> str:
        """Request input from user via CLI with styled input bar"""
        display_prompt = prompt_text if prompt_text else self.prompt_prefix

        # Print status info above the input
        if self.get_status_info:
            status_info = self.get_status_info()
            if status_info:
                status_parts = []
                for key, value in status_info.items():
                    status_parts.append(f"[dim]{key}:[/dim] [cyan]{value}[/cyan]")
                status_text = "  ".join(status_parts)
                self.console.print(f"  {status_text}")

        # Use prompt_toolkit for input
        try:
            user_input = prompt(
                [('class:prompt', f'{display_prompt} ')],
                style=self.pt_style,
            )
        except (EOFError, KeyboardInterrupt):
            raise KeyboardInterrupt

        return user_input
