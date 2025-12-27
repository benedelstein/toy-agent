from enum import KEEP
import sys
import anthropic
from anthropic.types import ContentBlock, ContentBlockParam, MessageParam, ServerToolUseBlockParam, TextBlockParam, ThinkingBlockParam, ThinkingConfigDisabledParam, ThinkingConfigEnabledParam, ToolChoiceAutoParam, ToolChoiceToolParam, ToolResultBlockParam, ToolUseBlockParam, WebSearchResultBlockParam, WebSearchToolRequestErrorParam, WebSearchToolResultBlockParam
from anthropic.types.message_create_params import ToolChoiceToolChoiceTool
import dotenv
import json
from tools import READ_FILE_TOOL, TEXT_EDITOR_TOOL, Tool, ToolResult, BASH_TOOL, GREP_TOOL, PING_TOOL, OUTPUT_TOOL
dotenv.load_dotenv()

client = anthropic.Anthropic()

class Agent:
    client = anthropic.Anthropic()
    def __init__(self, system_prompt: str | None = None, tools: list[Tool] | None = None, thinking_enabled: bool = True):
        self.system_prompt = system_prompt
        self.tools = tools
        self.history: list[MessageParam] = []
        self.thinking_enabled = thinking_enabled
        self.tool_dict: dict[str, Tool] = {tool.tool_name: tool for tool in tools} if tools else {}

    def _get_messages_for_api(self, use_thinking: bool) -> list[MessageParam]:
        """Build messages list, stripping thinking blocks if thinking is disabled."""
        if use_thinking:
            return self.history

        # Strip thinking blocks from all assistant messages
        messages: list[MessageParam] = []
        for msg in self.history:
            if msg["role"] == "assistant":
                content = msg.get("content", [])
                if isinstance(content, list):
                    # Filter out thinking blocks (blocks are TypedDicts, not Block classes)
                    filtered = [block for block in content if isinstance(block, dict) and block["type"] != "thinking"]
                    if filtered:
                        messages.append(MessageParam(role="assistant", content=filtered))
                else:
                    messages.append(msg)
            else:
                messages.append(msg)
        return messages

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

        # Can't use thinking when forcing a specific tool
        use_thinking = self.thinking_enabled and not require_output
        messages = self._get_messages_for_api(use_thinking)

        response = client.messages.create(
            max_tokens=10001,
            model="claude-sonnet-4-5",
            messages=messages,
            thinking=ThinkingConfigEnabledParam(type="enabled", budget_tokens=10000) if use_thinking else ThinkingConfigDisabledParam(type="disabled"),
            system=self.system_prompt if self.system_prompt else anthropic.omit,
            tool_choice=ToolChoiceToolParam(name=OUTPUT_TOOL.tool_name, type="tool") if require_output else ToolChoiceAutoParam(type="auto"),
            tools=[tool.to_anthropic_tool() for tool in actual_tools] if actual_tools else anthropic.omit,
        )
        return response.content

    def _handle_tool_call(self, tool_name: str, input: dict) -> ToolResult:
        if tool_name == OUTPUT_TOOL.tool_name:
            return OUTPUT_TOOL.execute(input)
        tool = self.tool_dict[tool_name]
        if tool is None:
            raise ValueError(f"Tool {tool_name} not found")
        return tool.execute(input)

    def _handle_iteration(self, require_output: bool = False) -> str | None:
        response = self._call_llm(require_output=require_output)

        # Collect all content blocks into a single assistant message
        assistant_content: list[ContentBlockParam] = []
        tool_calls: list[tuple[str, str, dict]] = []  # (tool_id, tool_name, input)
        output_result: str | None = None

        for content in response:
            if content.type == "thinking":
                assistant_content.append(
                    ThinkingBlockParam(type="thinking", thinking=content.thinking, signature=content.signature)
                )
            elif content.type == "text":
                print(f"💬 {content.text}")
                assistant_content.append(
                    TextBlockParam(type="text", text=content.text)
                )
            elif content.type == "tool_use":
                assistant_content.append(
                    ToolUseBlockParam(type="tool_use", id=content.id, name=content.name, input=content.input)
                )
                tool_calls.append((content.id, content.name, content.input))
            elif content.type == "server_tool_use":
                assistant_content.append(
                    ServerToolUseBlockParam(type="server_tool_use", id=content.id, name=content.name, input=content.input)
                )
            elif content.type == "web_search_tool_result":
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
                    assistant_content.append(
                        WebSearchToolResultBlockParam(
                            type="web_search_tool_result",
                            content=result_blocks,
                            tool_use_id=content.tool_use_id
                        )
                    )
                else:
                    print(f"web search error: {content.content.error_code}")
                    assistant_content.append(
                        WebSearchToolResultBlockParam(
                            type="web_search_tool_result",
                            tool_use_id=content.tool_use_id,
                            content=WebSearchToolRequestErrorParam(
                                type="web_search_tool_result_error",
                                error_code=content.content.error_code
                            )
                        )
                    )
            else:
                print(f"unknown content type: {content.type}")

        # Add the assistant message with all content blocks
        if assistant_content:
            self.history.append(
                MessageParam(role="assistant", content=assistant_content)
            )

        # Now execute tools and add results as user messages
        if tool_calls:
            tool_results: list[ToolResultBlockParam] = []
            for tool_id, tool_name, tool_input in tool_calls:
                tool_result = self._handle_tool_call(tool_name, tool_input)
                result_dict = tool_result.to_dict()
                if tool_result.is_error:
                    print(f"🛠️ Tool {tool_name} error: {tool_result.error}")
                tool_results.append(
                    ToolResultBlockParam(
                        type="tool_result",
                        tool_use_id=tool_id,
                        is_error=tool_result.is_error,
                        content=json.dumps(result_dict)
                    )
                )
                # Check if this is the output tool
                if tool_name == "output" and tool_result.data:
                    output_result = tool_result.data.result

            # Add all tool results as a single user message
            self.history.append(
                MessageParam(role="user", content=tool_results)
            )

        return output_result

    def run(self, prompt: str, max_iterations: int | None = 10) -> str:
        iteration = 0
        self.history.append(MessageParam(role="user", content=prompt))
        while max_iterations is None or iteration < max_iterations:
            iteration += 1
            result = self._handle_iteration(require_output=iteration == max_iterations)
            if result is not None:
                return result
        raise Exception("Error: max iterations reached")
    
    def reset(self):
        self.__init__()

if __name__ == "__main__":
    agent = Agent(
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
        result = agent.run(prompt=prompt, max_iterations=None)
        print("💡", result, "\n")