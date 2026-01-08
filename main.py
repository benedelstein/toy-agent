import os
import sys

import anthropic
import dotenv

from agent import Agent
from app_state import AppState
from cli_handler import SLASH_COMMANDS, CLIConfirmationHandler, CLIEventHandler, CLIInputHandler
from events import EventEmitter, FinalOutputEvent
from settings import SETTINGS, EditMode
from tools import (
    create_bash_tool,
    create_glob_tool,
    create_grep_tool,
    create_ping_tool,
    create_read_file_tool,
    create_sub_agent_tool,
    create_text_editor_tool,
    create_write_todos_tool,
)
from tools.github_tool import create_pull_request_tool
from tools.sub_agent_tool import agent_types

dotenv.load_dotenv()

app_state = AppState()
client = anthropic.Client()

# Create event system
emitter = EventEmitter()
emitter.add_handler(CLIEventHandler(verbose=False))
emitter.set_confirmation_handler(CLIConfirmationHandler())


def load_prompt_file(prompt_name: str) -> str:
    """Load a prompt file from the prompts/ directory."""
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", f"{prompt_name}.md")
    with open(prompt_path, "r") as f:
        return f.read()


def load_system_prompt(prompt_name: str) -> str:
    """Load system prompt with agents.md context if available."""
    base_prompt = load_prompt_file(prompt_name)

    # TODO: may want to search from git repo root instead
    agents_md_path = os.path.join(os.path.dirname(__file__), "agents.md")
    if os.path.exists(agents_md_path):
        with open(agents_md_path, "r") as f:
            agents_context = f.read()
        return f"{base_prompt}\n\n{agents_context}"

    return base_prompt


def get_status_info() -> dict[str, str]:
    """Return status info for the context bar."""
    return {
        "edit": SETTINGS.edit_mode.value,
        "cwd": os.path.basename(os.getcwd()),
    }


def print_help() -> None:
    """Print available slash commands."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title="Available Commands", show_header=True, header_style="bold cyan")
    table.add_column("Command", style="yellow")
    table.add_column("Description")

    def add_commands(commands: list, prefix: str = "") -> None:
        for cmd in commands:
            full_name = f"/{prefix}{cmd.name}" if prefix else f"/{cmd.name}"
            table.add_row(full_name, cmd.description)
            if cmd.subcommands:
                add_commands(cmd.subcommands, f"{prefix}{cmd.name} ")

    add_commands(SLASH_COMMANDS)
    console.print(table)


def handle_prompt(prompt: str, agent: Agent) -> str | None:
    """Handle user input, returning None for handled slash commands."""
    if prompt.startswith("/"):
        parts = prompt.split()
        command = parts[0]

        if command == "/help":
            print_help()
            return None

        if command == "/exit":
            print("Goodbye!")
            sys.exit(0)

        if command == "/clear":
            agent.clear_history()
            return "Conversation cleared."

        if command == "/settings":
            if len(parts) >= 3 and parts[1] == "edit_mode":
                try:
                    SETTINGS.edit_mode = EditMode(parts[2])
                    return f"Edit mode set to {parts[2]}"
                except ValueError:
                    return f"Invalid edit mode: {parts[2]}. Use: ask, always, or never"
            return "Usage: /settings edit_mode <ask|always|never>"

        return f"Unknown command: {command}. Type /help for available commands."

    return agent.run(prompt=prompt, max_iterations=None)


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


if __name__ == "__main__":
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
    if len(sys.argv) > 1:
        prompt = sys.argv[1]
        result = agent.run(prompt=prompt, max_iterations=None)
        emitter.emit(FinalOutputEvent(result=result))

    # Create styled input handler
    input_handler = CLIInputHandler(get_status_info=get_status_info)

    while True:
        try:
            prompt = input_handler.request_input()
            if not prompt.strip():
                continue
            result = handle_prompt(prompt, agent)
            if result is not None:
                emitter.emit(FinalOutputEvent(result=result))
            print()  # Add newline after output
        except KeyboardInterrupt:
            print("\nInterrupted. Press Ctrl+D to exit.")
            continue
        except EOFError:
            print("\nGoodbye!")
            break
