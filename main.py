import sys
import os
import anthropic
import dotenv
from agent import Agent
from settings import SETTINGS, EditMode
from tools import BASH_TOOL, READ_FILE_TOOL, TEXT_EDITOR_TOOL, GLOB_TOOL, GREP_TOOL, PING_TOOL, SubAgentTool, create_write_todos_tool
from tools.github_tool import CREATE_PULL_REQUEST_TOOL
from tools.sub_agent_tool import agent_types
from app_state import AppState

dotenv.load_dotenv()

app_state = AppState()

def load_prompt_file(prompt_name: str) -> str:
    """Load a prompt file from the prompts/ directory."""
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", f"{prompt_name}.md")
    with open(prompt_path, "r") as f:
        return f.read()

def load_system_prompt(prompt_name: str) -> str:
    """Load system prompt with agents.md context if available."""
    base_prompt = load_prompt_file(prompt_name)
    
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

client = anthropic.Client()
 
def create_agent(agent_type: agent_types) -> Agent:
    if agent_type == "explore":
        return Agent(
            settings=SETTINGS,
            client=client,
            tools=[GLOB_TOOL, GREP_TOOL, READ_FILE_TOOL, BASH_TOOL], 
            thinking_enabled=False, 
            system_prompt=load_system_prompt(prompt_name="explore_agent"),
            model="claude-haiku-4-5"
        )
    elif agent_type == "plan":
        return Agent(
            settings=SETTINGS,
            client=client,
            tools=[GLOB_TOOL, GREP_TOOL, READ_FILE_TOOL, BASH_TOOL], 
            thinking_enabled=True, 
            system_prompt=load_system_prompt(prompt_name="plan_agent"),
            model="claude-sonnet-4-5"
        )


SUB_AGENT_TOOL = SubAgentTool(
    create_agent=create_agent
)
WRITE_TODOS_TOOL = create_write_todos_tool(app_state)

if __name__ == "__main__":
    agent = Agent(
        settings=SETTINGS,
        client=client,
        tools=[
            PING_TOOL,
            GLOB_TOOL,
            GREP_TOOL,
            READ_FILE_TOOL, # do we need this if text_editor_tool also supports reading. yes if in plan mode. 
            TEXT_EDITOR_TOOL,
            BASH_TOOL,
            SUB_AGENT_TOOL,
            WRITE_TODOS_TOOL,
            CREATE_PULL_REQUEST_TOOL
        ], 
        thinking_enabled=True, 
        model="claude-opus-4-5",
        system_prompt=load_system_prompt(prompt_name="main_agent")
    )
    if len(sys.argv) > 1:
        prompt = sys.argv[1]
        result = agent.run(prompt=prompt, max_iterations=None)
        print("💡", result)
    else:
        pass
    while True:
        prompt = input("> ")
        result = handle_prompt(prompt, agent)
        print("💡", result, "\n")