"""Type-safe slash command system."""

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from rich.console import Console

from toy_agent.agent import Agent
from toy_agent.settings import SETTINGS, EditMode


class CommandResult(Enum):
    """Result of executing a slash command."""

    HANDLED = "handled"  # Command executed, continue REPL
    EXIT = "exit"  # Exit the CLI


@dataclass
class CommandContext:
    """Context passed to command handlers."""

    agent: Agent
    console: Console
    args: list[str]  # Arguments after the command name (e.g., ["/settings", "edit_mode", "ask"])


# Type alias for command handlers
CommandHandler = Callable[[CommandContext], CommandResult]


class CommandRegistry:
    """Registry mapping command names to their handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, CommandHandler] = {}

    def register(self, name: str) -> Callable[[CommandHandler], CommandHandler]:
        """Decorator to register a command handler."""

        def decorator(handler: CommandHandler) -> CommandHandler:
            self._handlers[name] = handler
            return handler

        return decorator

    def execute(self, ctx: CommandContext) -> CommandResult | None:
        """Execute a command. Returns None if command not found."""
        if not ctx.args:
            return None

        command = ctx.args[0]
        handler = self._handlers.get(command)

        if handler is None:
            return None

        return handler(ctx)

    def has_command(self, name: str) -> bool:
        """Check if a command is registered."""
        return name in self._handlers


# Global command registry
commands = CommandRegistry()


# ─────────────────────────────────────────────────────────────────────────────
# Command Handlers
# ─────────────────────────────────────────────────────────────────────────────


@commands.register("/help")
def cmd_help(ctx: CommandContext) -> CommandResult:
    """Show available commands."""
    ctx.console.print("\n[bold]Available Commands:[/bold]")
    ctx.console.print("  [cyan]/help[/cyan]              Show this help message")
    ctx.console.print(
        "  [cyan]/settings edit_mode[/cyan] [dim]<ask|always|never>[/dim]  Configure edit confirmation"
    )
    ctx.console.print("  [cyan]/clear[/cyan]             Clear conversation history")
    ctx.console.print("  [cyan]/exit[/cyan]              Exit the CLI")
    ctx.console.print()
    return CommandResult.HANDLED


@commands.register("/settings")
def cmd_settings(ctx: CommandContext) -> CommandResult:
    """Configure settings."""
    args = ctx.args

    if len(args) < 3:
        ctx.console.print("[yellow]Usage: /settings edit_mode <ask|always|never>[/yellow]")
        return CommandResult.HANDLED

    setting_name = args[1]

    match setting_name:
        case "edit_mode":
            try:
                edit_mode = EditMode(args[2])
                SETTINGS.edit_mode = edit_mode
                ctx.console.print(f"[green]Edit mode set to:[/green] {edit_mode.value}")
            except ValueError:
                ctx.console.print("[red]Invalid edit mode. Choose: ask, always, never[/red]")
        case _:
            ctx.console.print(f"[red]Unknown setting: {setting_name}[/red]")

    return CommandResult.HANDLED


@commands.register("/clear")
def cmd_clear(ctx: CommandContext) -> CommandResult:
    """Clear conversation history."""
    ctx.agent.clear_history()
    ctx.console.print("[green]Conversation history cleared.[/green]")
    return CommandResult.HANDLED


@commands.register("/exit")
def cmd_exit(ctx: CommandContext) -> CommandResult:
    """Exit the CLI."""
    return CommandResult.EXIT
