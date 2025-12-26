import sys
import anthropic
from anthropic.types import ContentBlock, MessageParam, ServerToolUseBlockParam, ThinkingBlockParam, ThinkingConfigEnabledParam, ToolBash20250124Param, ToolChoiceAnyParam, ToolChoiceAutoParam, ToolChoiceNoneParam, ToolChoiceToolParam, ToolParam, ToolResultBlockParam, ToolUseBlockParam, WebSearchResultBlockParam, WebSearchTool20250305Param, WebSearchToolRequestErrorParam, WebSearchToolResultBlockParam, server_tool_usage
from anthropic.types.message_create_params import ToolChoiceToolChoiceTool
import dotenv
import json
from tools import BASH_TOOL, OUTPUT_TOOL, PING_TOOL, Tool
dotenv.load_dotenv()

client = anthropic.Anthropic()

# # TODO: define types with dataclass and pydantic
# # TODO: DONT use anthropic's tool types, build from scratch. can we just output structured json.?
# # or is this a primitive

class Agent:
    client = anthropic.Anthropic()
    def __init__(self, system_prompt: str | None = None, tools: list[Tool] | None = None):
        self.system_prompt = system_prompt
        self.tools = tools
        self.history: list[MessageParam] = []
        self.tool_dict: dict[str, Tool] = {tool.tool_name: tool for tool in tools} if tools else {}

    def _call_llm(self, require_output: bool = False) -> list[ContentBlock]:
        actual_tools = []
        if require_output:
            # force the output tool to be called
            actual_tools = [OUTPUT_TOOL]
        elif self.tools:
            actual_tools.extend(self.tools)
            actual_tools.append(OUTPUT_TOOL) # may also call the output early. if we want, we could add some setting to disable early outputs.
        else:
            actual_tools = None
        for message in self.history:
            print(f"history line: {message}")
        
        response = client.messages.create(
            max_tokens=10000,
            model="claude-sonnet-4-5",
            messages=self.history,
            system=self.system_prompt if self.system_prompt else anthropic.omit,
            tool_choice=ToolChoiceToolParam(name=OUTPUT_TOOL.tool_name, type="tool") if require_output else ToolChoiceAutoParam(type="auto"),
            tools=[tool.to_anthropic_tool() for tool in actual_tools] if actual_tools else anthropic.omit
        )
        return response.content

    def _handle_tool_call(self, tool_name: str, input: dict) -> dict:
        if tool_name == OUTPUT_TOOL.tool_name:
            return OUTPUT_TOOL.execute(input)
        tool = self.tool_dict[tool_name]
        if tool is None:
            raise ValueError(f"Tool {tool_name} not found")
    
        return tool.execute(input)

    def _handle_iteration(self, require_output: bool = False) -> str | None:
        response = self._call_llm(require_output=require_output)
        print(f"response contains {len(response)} content blocks")
        for content in response:
            if content.type == "tool_use":
                self.history.append(
                    MessageParam(
                        role="assistant", 
                        content=[ToolUseBlockParam(type="tool_use", id=content.id, name=content.name, input=content.input)]
                    )
                )
                print(f"handling tool call: {content.name} {content.input}")
                tool_response = self._handle_tool_call(content.name, content.input)
                self.history.append(
                    MessageParam(
                        role="user", # tool results must be user messages 
                        content=[
                            ToolResultBlockParam(
                                type="tool_result", 
                                tool_use_id=content.id, 
                                content=json.dumps(tool_response)
                            )
                        ]
                    )
                )
                if content.name == "output":
                    # TODO: make this more constrained
                    return tool_response["result"]
                
            elif content.type == "text":
                # could also use this as the output ?
                print(f"text response: {content.text}")
                self.history.append(
                    MessageParam(
                        role="assistant",
                        content=content.text
                    )
                )
            elif content.type == "server_tool_use":
                # the api used a tool call server-side. Just record the context.
                print(f"server tool called: {content.name}")
                print(content.input)
                content.input
                self.history.append(
                    MessageParam(
                        role="assistant",  # TODO: should this be user too? 
                        content=[ServerToolUseBlockParam(type="server_tool_use", id=content.id, name=content.name, input=content.input)]
                    )
                )
            elif content.type == "web_search_tool_result":
                print(f"web search tool result")
                # Check if it's an error or list of results
                if isinstance(content.content, list):
                    result_blocks: list[WebSearchResultBlockParam] = []
                    for result in content.content:
                        result_blocks.append(WebSearchResultBlockParam(
                            type="web_search_result",
                            title=result.title,
                            url=result.url,
                            encrypted_content=result.encrypted_content,
                            page_age=result.page_age
                        ))
                    self.history.append(
                        MessageParam(
                            role="assistant",
                            content=[
                                WebSearchToolResultBlockParam(
                                    type="web_search_tool_result",
                                    content=result_blocks,
                                    tool_use_id=content.tool_use_id
                                )
                            ]
                        )
                    )
                else:
                    # It's a WebSearchToolResultError
                    print(f"web search error: {content.content.error_code}")
                    self.history.append(
                        MessageParam(
                            role="assistant",
                            content=[WebSearchToolResultBlockParam(
                                type="web_search_tool_result",
                                tool_use_id=content.tool_use_id,
                                content=WebSearchToolRequestErrorParam(
                                    type="web_search_tool_result_error",
                                    error_code=content.content.error_code
                                )
                            )]
                        )
                    )
            elif content.type == "thinking":
                self.history.append(
                    MessageParam(
                        role="assistant", 
                        content=[ThinkingBlockParam(type="thinking", signature=content.signature, thinking=content.thinking)]
                    )
                )
            else:
                print(f"unknown content type: {content.type}")
        return None

    def run(self, prompt: str, max_iterations: int | None = 10) -> str:
        iteration = 0
        self.history = []
        self.history.append(MessageParam(role="user", content=prompt))
        while max_iterations is None or iteration < max_iterations:
            iteration += 1
            result = self._handle_iteration(require_output=iteration == max_iterations)
            if result is not None:
                return result
        raise Exception("Error: max iterations reached")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        prompt = sys.argv[1]
    else:
        prompt = input("Enter a prompt: ")
    agent = Agent(tools=[PING_TOOL, BASH_TOOL])
    # TODO: DIFFERENT STOP CONDITIONS. 
    # - when max iterations is hit
    # - when it calls a specific tool
    # - force a certain number of iterations
    result = agent.run(prompt=prompt, max_iterations=3)
    print(result)