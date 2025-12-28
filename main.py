import sys
from typing import Literal
import os
import anthropic
import dotenv
from agent import Agent
from settings import SETTINGS, EditMode
from tools import BASH_TOOL, READ_FILE_TOOL, TEXT_EDITOR_TOOL, GLOB_TOOL, GREP_TOOL, PING_TOOL, SubAgentTool
from tools.sub_agent_tool import agent_types

dotenv.load_dotenv()

def load_system_prompt() -> str:
    """Load system prompt with CLAUDE.md context if available."""
    base_prompt = "You are a helpful coding assistant."
    
    claude_md_path = os.path.join(os.path.dirname(__file__), "CLAUDE.md")
    if os.path.exists(claude_md_path):
        with open(claude_md_path, "r") as f:
            claude_context = f.read()
        return f"{base_prompt}\n\n{claude_context}"
    
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
            tools=[PING_TOOL, GLOB_TOOL, GREP_TOOL, READ_FILE_TOOL, BASH_TOOL], 
            thinking_enabled=False, 
            system_prompt=load_system_prompt(),
            model="claude-haiku-4-5"
        )
    elif agent_type == "plan":
        return Agent(
            settings=SETTINGS,
            client=client,
            tools=[PING_TOOL, GLOB_TOOL, GREP_TOOL, READ_FILE_TOOL, BASH_TOOL], 
            thinking_enabled=True, 
            system_prompt=load_system_prompt(),
            model="claude-sonnet-4-5"
        )


SUB_AGENT_TOOL = SubAgentTool(
    create_agent=create_agent
)

if __name__ == "__main__":
    agent = Agent(
        settings=SETTINGS,
        client=client,
        tools=[PING_TOOL, GLOB_TOOL, GREP_TOOL, READ_FILE_TOOL, TEXT_EDITOR_TOOL, BASH_TOOL, SUB_AGENT_TOOL], 
        thinking_enabled=True, 
        system_prompt=load_system_prompt()
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