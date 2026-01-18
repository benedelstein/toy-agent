import argparse
import os
from pathlib import Path

import anthropic
import dotenv

from toy_agent.agent import Agent, AgentInterrupted
from toy_agent.app_state import AppState
from toy_agent.cli_handler import CLIConfirmationHandler, CLIEventHandler, CLIInputHandler
from toy_agent.commands import CommandContext, CommandResult, commands
from toy_agent.events import CommandOutputEvent, EventEmitter, FinalOutputEvent
from toy_agent.logger import logger
from toy_agent.settings import SETTINGS, EditMode
from toy_agent.tools import (
    create_bash_tool,
    create_glob_tool,
    create_grep_tool,
    create_ping_tool,
    create_read_file_tool,
    create_sub_agent_tool,
    create_text_editor_tool,
    create_write_todos_tool,
)
from toy_agent.tools.github_tool import create_pull_request_tool
from toy_agent.tools.sub_agent_tool import agent_types

dotenv.load_dotenv()

# Initialize logger from environment variable (after dotenv loads)
logger.set_debug(os.getenv("TOY_AGENT_DEBUG", "").lower() in ("1", "true", "yes"))

app_state = AppState()
client = anthropic.Client()

# Create event system
emitter = EventEmitter()
emitter.add_handler(CLIEventHandler(verbose=False))
emitter.set_confirmation_handler(CLIConfirmationHandler())


def get_status_info():
    """Return current status info for the input bar"""
    match SETTINGS.edit_mode:
        case EditMode.ASK:
            edit_str = "ask before edits"
        case EditMode.ALWAYS:
            edit_str = "⏵⏵ accept edits"
        case EditMode.NEVER:
            edit_str = "✗✗ block edits"

    return {
        "edit": edit_str,
        "cwd": Path.cwd().name,
    }


emitter.set_input_handler(CLIInputHandler(prompt_prefix="❯", get_status_info=get_status_info))


def load_prompt_file(prompt_name: str) -> str:
    """Load a prompt file from the prompts/ directory."""
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", f"{prompt_name}.md")
    with open(prompt_path, "r") as f:
        return f.read()


def load_system_prompt(prompt_name: str) -> str:
    """Load system prompt with agents.md context if available."""
    base_prompt = load_prompt_file(prompt_name)

    # Look for agents.md in the current working directory
    project_root = os.getcwd()
    agents_md_path = os.path.join(project_root, "agents.md")
    if os.path.exists(agents_md_path):
        with open(agents_md_path, "r") as f:
            agents_context = f.read()
        return f"{base_prompt}\n\n<repo_context>\n{agents_context}\n</repo_context>"

    return base_prompt


def build_prompt_with_file_context(
    prompt: str, app_state: AppState, ttl_seconds: float = 60.0
) -> str:
    """Prepend file context to prompt if there are recent file events."""
    events = app_state.get_and_clear_recent_events(ttl_seconds=ttl_seconds)
    if not events:
        return prompt

    context_lines = [
        f"<file_context>user {e.event_type} ./{e.file_path} in their IDE</file_context>"
        for e in events
    ]
    result = "\n".join(context_lines) + "\n\n" + prompt
    logger.debug(f"Prompt with file context:\n{result}")
    return result


def handle_prompt(prompt: str, agent: Agent) -> str | None:
    """Handle user prompt, including slash commands."""
    # Handle slash commands via registry
    if prompt.startswith("/"):
        ctx = CommandContext(
            agent=agent,
            emitter=emitter,
            args=prompt.split(),
        )

        result = commands.execute(ctx)

        if result is None:
            emitter.emit(
                CommandOutputEvent(
                    message=f"Unknown command: {ctx.args[0]}. Type /help for available commands.",
                    style="error",
                )
            )
            return None

        match result:
            case CommandResult.EXIT:
                raise KeyboardInterrupt  # Trigger clean exit
            case CommandResult.HANDLED:
                return None

    # Inject file context from recent file events
    prompt_with_context = build_prompt_with_file_context(prompt, app_state)

    # Regular prompt - run through agent
    try:
        response = agent.run(prompt=prompt_with_context, max_iterations=None)
        return response
    except AgentInterrupted:
        emitter.emit(CommandOutputEvent(message="Interrupted - returning to prompt", style="error"))
        return None


def create_subagent(agent_type: agent_types, agent_emitter: EventEmitter) -> Agent:
    if agent_type == "explore":
        return Agent(
            settings=SETTINGS,
            client=client,
            tools=[
                create_glob_tool(agent_emitter),
                create_grep_tool(agent_emitter),
                create_read_file_tool(agent_emitter),
                create_bash_tool(agent_emitter),
            ],
            thinking_enabled=False,
            system_prompt=load_system_prompt(prompt_name="explore_agent"),
            model="claude-haiku-4-5",
            emitter=agent_emitter,
        )
    elif agent_type == "plan":
        return Agent(
            settings=SETTINGS,
            client=client,
            tools=[
                create_glob_tool(agent_emitter),
                create_grep_tool(agent_emitter),
                create_read_file_tool(agent_emitter),
                create_bash_tool(agent_emitter),
            ],
            thinking_enabled=True,
            system_prompt=load_system_prompt(prompt_name="plan_agent"),
            model="claude-sonnet-4-5",
            emitter=agent_emitter,
        )


def main():
    """Main entry point for the toy-agent CLI."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Toy Agent - Agentic coding assistant")
    parser.add_argument(
        "prompt", nargs="?", help="Initial prompt to run (if not provided, starts interactive mode)"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    # Enable debug mode from CLI arg (overrides environment variable)
    if args.debug:
        logger.set_debug(True)
        logger.debug("Debug mode enabled via CLI argument")

    agent = Agent(
        settings=SETTINGS,
        client=client,
        tools=[
            create_ping_tool(emitter),
            create_glob_tool(emitter),
            create_grep_tool(emitter),
            create_read_file_tool(emitter),
            create_text_editor_tool(emitter, SETTINGS),
            create_bash_tool(emitter),
            create_sub_agent_tool(emitter, create_subagent),
            create_write_todos_tool(emitter, app_state),
            create_pull_request_tool(emitter),
        ],
        thinking_enabled=True,
        model="claude-opus-4-5",
        system_prompt=load_system_prompt(prompt_name="main_agent"),
        emitter=emitter,
    )

    # Initialize file watcher for IDE integration
    file_watcher = None
    try:
        from toy_agent.file_watcher import FileWatcher

        def handle_file_event(event_type: str, file_path: str):
            app_state.add_file_event(event_type, file_path)

        project_root = str(Path.cwd())
        file_watcher = FileWatcher(project_root, handle_file_event)
        file_watcher.start()
    except ImportError:
        print("File watcher dependencies not installed. Run: pip install watchdog")

    # If prompt provided via CLI, run it and exit
    if args.prompt:
        result = agent.run(prompt=args.prompt, max_iterations=None)
        emitter.emit(FinalOutputEvent(result=result))
        return

    import time

    last_interrupt_time: float | None = None
    interrupt_debounce = 1.0  # seconds

    try:
        while True:
            try:
                prompt = emitter.request_input("> ")
                if not prompt.strip():
                    continue
                result = handle_prompt(prompt, agent)
                if result is not None:
                    emitter.emit(FinalOutputEvent(result=result))
                print()  # Add newline after output # TODO: REMOVE
            except KeyboardInterrupt:
                now = time.time()
                if (
                    last_interrupt_time is not None
                    and (now - last_interrupt_time) <= interrupt_debounce
                ):
                    # Second Ctrl+C within debounce - exit
                    raise
                last_interrupt_time = now
                print("\nPress Ctrl+C again within 1s to quit...")
                continue
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        if file_watcher:
            file_watcher.stop()


if __name__ == "__main__":
    main()
