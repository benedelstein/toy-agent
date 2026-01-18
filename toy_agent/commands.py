"""Type-safe slash command system."""

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from toy_agent.agent import Agent
from toy_agent.events import CommandOutputEvent, EventEmitter
from toy_agent.logger import logger
from toy_agent.settings import SETTINGS, EditMode


class CommandResult(Enum):
    """Result of executing a slash command."""

    HANDLED = "handled"  # Command executed, continue REPL
    EXIT = "exit"  # Exit the CLI


@dataclass
class CommandContext:
    """Context passed to command handlers."""

    agent: Agent
    emitter: EventEmitter
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
    help_text = """
Available Commands:
  /help              Show this help message
  /settings edit_mode <ask|always|never>  Configure edit confirmation
  /debug             Toggle debug mode (shows file events, context injection)
  /clear             Clear conversation history
  /exit              Exit the CLI
"""
    ctx.emitter.emit(CommandOutputEvent(message=help_text, style="info"))
    return CommandResult.HANDLED


@commands.register("/settings")
def cmd_settings(ctx: CommandContext) -> CommandResult:
    """Configure settings."""
    args = ctx.args

    if len(args) < 3:
        ctx.emitter.emit(
            CommandOutputEvent(
                message="Usage: /settings edit_mode <ask|always|never>", style="error"
            )
        )
        return CommandResult.HANDLED

    setting_name = args[1]

    match setting_name:
        case "edit_mode":
            try:
                edit_mode = EditMode(args[2])
                SETTINGS.edit_mode = edit_mode
                ctx.emitter.emit(
                    CommandOutputEvent(
                        message=f"Edit mode set to: {edit_mode.value}", style="success"
                    )
                )
            except ValueError:
                ctx.emitter.emit(
                    CommandOutputEvent(
                        message="Invalid edit mode. Choose: ask, always, never", style="error"
                    )
                )
        case _:
            ctx.emitter.emit(
                CommandOutputEvent(message=f"Unknown setting: {setting_name}", style="error")
            )

    return CommandResult.HANDLED


@commands.register("/clear")
def cmd_clear(ctx: CommandContext) -> CommandResult:
    """Clear conversation history."""
    ctx.agent.clear_history()
    ctx.emitter.emit(CommandOutputEvent(message="Conversation history cleared.", style="success"))
    return CommandResult.HANDLED


@commands.register("/debug")
def cmd_debug(ctx: CommandContext) -> CommandResult:
    """Toggle debug mode."""
    # Toggle debug mode
    logger.set_debug(not logger.debug_enabled)
    status = "enabled" if logger.debug_enabled else "disabled"
    ctx.emitter.emit(CommandOutputEvent(message=f"Debug mode {status}", style="success"))
    return CommandResult.HANDLED


@commands.register("/exit")
def cmd_exit(ctx: CommandContext) -> CommandResult:
    """Exit the CLI."""
    return CommandResult.EXIT
