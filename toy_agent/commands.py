"""Type-safe slash command system."""

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from toy_agent.agent import Agent
from toy_agent.events import CommandOutputEvent, EventEmitter
from toy_agent.logger import logger
from toy_agent.session_store import SessionStore
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
  /save              Save current session to disk
  /sessions          List saved sessions
  /resume <id>       Resume a saved session
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


@commands.register("/save")
def cmd_save(ctx: CommandContext) -> CommandResult:
    """Save current session to disk."""
    if not ctx.agent.history:
        ctx.emitter.emit(
            CommandOutputEvent(message="Nothing to save — conversation is empty.", style="error")
        )
        return CommandResult.HANDLED

    store = SessionStore()
    session_id = store.save(ctx.agent.history, session_id=ctx.agent.current_session_id)
    ctx.agent.current_session_id = session_id
    msg_count = len(ctx.agent.history)
    ctx.emitter.emit(
        CommandOutputEvent(
            message=f"Session saved: {session_id} ({msg_count} messages)", style="success"
        )
    )
    return CommandResult.HANDLED


@commands.register("/sessions")
def cmd_sessions(ctx: CommandContext) -> CommandResult:
    """List saved sessions."""
    store = SessionStore()
    sessions = store.list_sessions()

    if not sessions:
        ctx.emitter.emit(CommandOutputEvent(message="No saved sessions found.", style="info"))
        return CommandResult.HANDLED

    lines = ["Saved sessions:", ""]
    for s in sessions:
        lines.append(f"  {s['session_id']}  ({s['message_count']} msgs)  {s['summary']}")
    lines.append("")
    lines.append("Resume with: /resume <session_id>")

    ctx.emitter.emit(CommandOutputEvent(message="\n".join(lines), style="info"))
    return CommandResult.HANDLED


@commands.register("/resume")
def cmd_resume(ctx: CommandContext) -> CommandResult:
    """Resume a saved session."""
    if len(ctx.args) < 2:
        ctx.emitter.emit(
            CommandOutputEvent(
                message="Usage: /resume <session_id>. Use /sessions to list available sessions.",
                style="error",
            )
        )
        return CommandResult.HANDLED

    session_id = ctx.args[1]
    store = SessionStore()

    try:
        history = store.load(session_id)
    except FileNotFoundError:
        ctx.emitter.emit(
            CommandOutputEvent(
                message=f"Session not found: {session_id}. Use /sessions to list available sessions.",
                style="error",
            )
        )
        return CommandResult.HANDLED

    ctx.agent.history = history
    ctx.agent.current_session_id = session_id
    ctx.emitter.emit(
        CommandOutputEvent(
            message=f"Resumed session {session_id} ({len(history)} messages)", style="success"
        )
    )
    return CommandResult.HANDLED


@commands.register("/exit")
def cmd_exit(ctx: CommandContext) -> CommandResult:
    """Exit the CLI."""
    return CommandResult.EXIT
