import os
import sys
from pathlib import Path

import anthropic
import dotenv
from rich.console import Console

from toy_agent.agent import Agent, AgentInterrupted
from toy_agent.app_state import AppState
from toy_agent.cli_handler import CLIConfirmationHandler, CLIEventHandler, CLIInputHandler
from toy_agent.commands import CommandContext, CommandResult, commands
from toy_agent.events import EventEmitter, FinalOutputEvent
from toy_agent.settings import SETTINGS
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

app_state = AppState()
client = anthropic.Client()

# Create event system
emitter = EventEmitter()
emitter.add_handler(CLIEventHandler(verbose=False))
emitter.set_confirmation_handler(CLIConfirmationHandler())


def get_status_info():
    """Return current status info for the input bar"""
    return {
        "edit": SETTINGS.edit_mode.value,
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

    # Look for agents.md in the project root (one level up from this file's directory)
    project_root = os.path.dirname(os.path.dirname(__file__))
    agents_md_path = os.path.join(project_root, "agents.md")
    if os.path.exists(agents_md_path):
        with open(agents_md_path, "r") as f:
            agents_context = f.read()
        return f"{base_prompt}\n\n{agents_context}"

    return base_prompt


def handle_prompt(prompt: str, agent: Agent) -> str | None:
    """Handle user prompt, including slash commands."""
    console = Console()

    # Handle slash commands via registry
    if prompt.startswith("/"):
        ctx = CommandContext(
            agent=agent,
            console=console,
            args=prompt.split(),
        )

        result = commands.execute(ctx)

        if result is None:
            console.print(
                f"[red]Unknown command: {ctx.args[0]}[/red]. Type /help for available commands."
            )
            return None

        match result:
            case CommandResult.EXIT:
                raise KeyboardInterrupt  # Trigger clean exit
            case CommandResult.HANDLED:
                return None

    # Regular prompt - run through agent
    with console.status("Thinking...", spinner="earth") as status:
        try:
            response = agent.run(prompt=prompt, max_iterations=None)
            status.stop()
            return response
        except AgentInterrupted:
            status.stop()
            console.print("[yellow]Interrupted - returning to prompt[/yellow]")
            return None


def create_agent(agent_type: agent_types, agent_emitter: EventEmitter) -> Agent:
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
            create_sub_agent_tool(emitter, create_agent),
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
            # For now, just print the file events
            print(f"[File Event] User {event_type}: {file_path}")

        project_root = str(Path.cwd())
        file_watcher = FileWatcher(project_root, handle_file_event)
        file_watcher.start()
        print(f"File watcher enabled for: {project_root}")
    except ImportError:
        print("File watcher dependencies not installed. Run: pip install watchdog")
    if len(sys.argv) > 1:
        prompt = sys.argv[1]
        result = agent.run(prompt=prompt, max_iterations=None)
        emitter.emit(FinalOutputEvent(result=result))

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
            print("File watcher stopped.")


if __name__ == "__main__":
    main()
