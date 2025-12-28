import sys
from typing import Literal
import anthropic
import dotenv
from agent import Agent
from settings import SETTINGS, EditMode
from tools import READ_FILE_TOOL, TEXT_EDITOR_TOOL, GREP_TOOL, PING_TOOL

dotenv.load_dotenv()

if __name__ == "__main__":
    client = anthropic.Client()
    agent = Agent(
        settings=SETTINGS,
        client=client,
        tools=[PING_TOOL, GREP_TOOL, READ_FILE_TOOL, TEXT_EDITOR_TOOL], 
        thinking_enabled=True, 
        system_prompt="You are a helpful coding assistant."
    )
    if len(sys.argv) > 1:
        prompt = sys.argv[1]
        result = agent.run(prompt=prompt, max_iterations=None)
        print("💡", result)
    else:
        pass
    # TODO: DIFFERENT STOP CONDITIONS. 
    # - when max iterations is hit
    # - when it calls a specific tool
    # - force a certain number of iterations
    while True:
        prompt = input("> ")
        if prompt.startswith("/"):
            command = prompt.split(" ")[0]
            if command == "/settings":
                settings = prompt.split(" ")[1]
                if settings == "edit_mode":
                    edit_mode = prompt.split(" ")[2]
                    try:
                        SETTINGS.edit_mode = EditMode(edit_mode)
                    except ValueError:
                        print(f"🛠️ Invalid edit mode: {edit_mode}. Valid options: {[e.value for e in EditMode]}")
                        continue
                    print(f"🛠️ Edit mode set to {edit_mode}")
                    continue
        result = agent.run(prompt=prompt, max_iterations=None)
        print("💡", result, "\n")