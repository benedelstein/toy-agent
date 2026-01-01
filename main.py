import sys
import os
import anthropic
import dotenv
from agent import Agent
from settings import SETTINGS, EditMode
from tools import (
    create_bash_tool,
    create_glob_tool,
    create_grep_tool,
    create_ping_tool,
    create_read_file_tool,
    create_text_editor_tool,
    create_sub_agent_tool,
    create_write_todos_tool,
)
from tools.github_tool import create_pull_request_tool
from tools.sub_agent_tool import agent_types
from app_state import AppState
from events import EventEmitter, FinalOutputEvent
from cli_handler import CLIEventHandler, CLIConfirmationHandler

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


def handle_prompt(prompt: str, agent: Agent) -> str:
    if prompt.startswith("/"):
        command = prompt.split(" ")[0]
        if command == "/settings":
            settings = prompt.split(" ")[1]
            if settings == "edit_mode":
                edit_mode = prompt.split(" ")[2]
                SETTINGS.edit_mode = EditMode(edit_mode)
                return "Edit mode set to " + edit_mode
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
            emitter=agent_emitter
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
            emitter=agent_emitter
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
        emitter=emitter
    )
    if len(sys.argv) > 1:
        prompt = sys.argv[1]
        result = agent.run(prompt=prompt, max_iterations=None)
        emitter.emit(FinalOutputEvent(result=result))
    else:
        pass
    while True:
        prompt = input("> ")
        result = handle_prompt(prompt, agent)
        emitter.emit(FinalOutputEvent(result=result))
        print()  # Add newline after output
