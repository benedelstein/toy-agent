import json

import anthropic
from anthropic.lib.streaming import MessageStreamManager
from anthropic.types import (
    ContentBlockParam,
    MessageParam,
    ModelParam,
    ServerToolUseBlockParam,
    TextBlockParam,
    ThinkingBlockParam,
    ThinkingConfigDisabledParam,
    ThinkingConfigEnabledParam,
    ToolChoiceAutoParam,
    ToolChoiceToolParam,
    ToolResultBlockParam,
    ToolUseBlockParam,
    WebSearchResultBlockParam,
    WebSearchToolRequestErrorParam,
    WebSearchToolResultBlockParam,
)

from .events import (
    AgentCompletedEvent,
    AgentStartedEvent,
    AssistantMessageEvent,
    ContentBlockStartEvent,
    ContentBlockStopEvent,
    EventEmitter,
    TextDeltaEvent,
    ThinkingDeltaEvent,
    WebSearchErrorEvent,
)
from .settings import Settings
from .tools import Tool, ToolResult
from .tools.output_tool import create_output_tool

# Tool name constant for text editor filtering
TEXT_EDITOR_TOOL_NAME = "str_replace_based_edit_tool"


class AgentInterrupted(Exception):
    """Raised when the agent loop is interrupted by the user."""

    pass


class Agent:
    client: anthropic.Client
    settings: Settings

    def __init__(
        self,
        settings: Settings,
        client: anthropic.Client,
        system_prompt: str | None = None,
        tools: list[Tool] | None = None,
        thinking_enabled: bool = True,
        model: ModelParam = "claude-sonnet-4-5",
        emitter: EventEmitter | None = None,
    ):
        self.settings = settings
        self.model = model
        self.client = client
        self.system_prompt = system_prompt
        self.tools = tools
        self.history: list[MessageParam] = []
        self.thinking_enabled = thinking_enabled
        self.tool_dict: dict[str, Tool] = {tool.tool_name: tool for tool in tools} if tools else {}
        self.emitter = emitter or EventEmitter()
        self._interrupted = False

        # Create output tool with this agent's emitter
        self.output_tool = create_output_tool(self.emitter)

    def clear_history(self) -> None:
        """Clear the conversation history."""
        self.history = []

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
                    filtered = [
                        block
                        for block in content
                        if isinstance(block, dict) and block["type"] != "thinking"
                    ]
                    if filtered:
                        messages.append(MessageParam(role="assistant", content=filtered))
                else:
                    messages.append(msg)
            else:
                messages.append(msg)
        return messages

    def _get_tools_and_thinking(self, require_output: bool) -> tuple[list[Tool] | None, bool]:
        """Prepare tools list and determine if thinking should be enabled."""
        actual_tools: list[Tool] | None = []
        if require_output:
            # force the output tool to be called
            actual_tools = [self.output_tool]
        elif self.tools:
            # filter out edit tool if edit mode is never
            if self.settings.edit_mode == "never":
                actual_tools.extend(
                    [tool for tool in self.tools if tool.tool_name != TEXT_EDITOR_TOOL_NAME]
                )
            else:
                actual_tools.extend(self.tools)
            actual_tools.append(self.output_tool)  # may also call the output early
        else:
            actual_tools = None

        # Can't use thinking when forcing a specific tool
        use_thinking = self.thinking_enabled and not require_output
        return actual_tools, use_thinking

    def _call_llm_streaming(self, require_output: bool = False) -> MessageStreamManager:
        """Call the LLM and return a streaming context manager."""
        actual_tools, use_thinking = self._get_tools_and_thinking(require_output)
        messages = self._get_messages_for_api(use_thinking)
        thinking_config = (
            ThinkingConfigEnabledParam(type="enabled", budget_tokens=10000)
            if use_thinking
            else ThinkingConfigDisabledParam(type="disabled")
        )
        tool_choice = (
            ToolChoiceToolParam(name=self.output_tool.tool_name, type="tool")
            if require_output
            else ToolChoiceAutoParam(type="auto")
        )
        return self.client.messages.stream(
            max_tokens=10001,
            model=self.model,
            messages=messages,
            thinking=thinking_config,
            system=self.system_prompt if self.system_prompt else anthropic.omit,
            tool_choice=tool_choice,
            tools=[tool.to_anthropic_tool() for tool in actual_tools]
            if actual_tools
            else anthropic.omit,
        )

    def _handle_tool_call(self, tool_name: str, input: dict) -> ToolResult:
        if tool_name == self.output_tool.tool_name:
            return self.output_tool.execute(input)
        tool = self.tool_dict.get(tool_name)
        if tool is None:
            raise ValueError(f"Tool {tool_name} not found")
        return tool.execute(input)

    def _handle_iteration(self, require_output: bool = False) -> str | None:
        # Collect all content blocks into a single assistant message
        assistant_content: list[ContentBlockParam] = []
        tool_calls: list[tuple[str, str, dict]] = []  # (tool_id, tool_name, input)
        output_result: str | None = None
        text_only_content: list[str] = []  # Collect text content for text-only responses

        # Track current content blocks being streamed
        current_blocks: dict[int, dict] = {}  # index -> accumulated block data

        with self._call_llm_streaming(require_output=require_output) as stream:
            for event in stream:
                if event.type == "content_block_start":
                    idx = event.index
                    block = event.content_block
                    self.emitter.emit(ContentBlockStartEvent(index=idx, block_type=block.type))

                    if block.type == "thinking":
                        current_blocks[idx] = {
                            "type": "thinking",
                            "thinking": block.thinking,
                            "signature": block.signature,
                        }
                    elif block.type == "text":
                        current_blocks[idx] = {"type": "text", "text": ""}
                    elif block.type == "tool_use":
                        current_blocks[idx] = {
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input_json": "",
                        }
                    elif block.type == "server_tool_use":
                        current_blocks[idx] = {
                            "type": "server_tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input_json": "",
                        }

                elif event.type == "content_block_delta":
                    idx = event.index
                    delta = event.delta

                    if delta.type == "thinking_delta":
                        current_blocks[idx]["thinking"] += delta.thinking
                        self.emitter.emit(ThinkingDeltaEvent(thinking=delta.thinking))
                    elif delta.type == "signature_delta":
                        current_blocks[idx]["signature"] = delta.signature
                    elif delta.type == "text_delta":
                        current_blocks[idx]["text"] += delta.text
                        self.emitter.emit(TextDeltaEvent(text=delta.text))
                    elif delta.type == "input_json_delta":
                        current_blocks[idx]["input_json"] += delta.partial_json

                elif event.type == "content_block_stop":
                    idx = event.index
                    block_data = current_blocks.get(idx)
                    self.emitter.emit(ContentBlockStopEvent(index=idx))

                    if block_data:
                        if block_data["type"] == "thinking":
                            assistant_content.append(
                                ThinkingBlockParam(
                                    type="thinking",
                                    thinking=block_data["thinking"],
                                    signature=block_data["signature"],
                                )
                            )
                        elif block_data["type"] == "text":
                            text = block_data["text"]
                            # Emit the full message event for compatibility
                            self.emitter.emit(AssistantMessageEvent(text=text))
                            text_only_content.append(text)
                            assistant_content.append(TextBlockParam(type="text", text=text))
                        elif block_data["type"] == "tool_use":
                            tool_input = json.loads(block_data["input_json"] or "{}")
                            assistant_content.append(
                                ToolUseBlockParam(
                                    type="tool_use",
                                    id=block_data["id"],
                                    name=block_data["name"],
                                    input=tool_input,
                                )
                            )
                            tool_calls.append((block_data["id"], block_data["name"], tool_input))
                        elif block_data["type"] == "server_tool_use":
                            tool_input = json.loads(block_data["input_json"] or "{}")
                            assistant_content.append(
                                ServerToolUseBlockParam(
                                    type="server_tool_use",
                                    id=block_data["id"],
                                    name=block_data["name"],
                                    input=tool_input,
                                )
                            )

                elif event.type == "message_start":
                    # Message started, nothing to do
                    pass

                elif event.type == "message_delta":
                    # Message metadata update (stop_reason, usage)
                    pass

                elif event.type == "message_stop":
                    # Message complete - get final message for web search results
                    final_message = stream.get_final_message()
                    for content in final_message.content:
                        if content.type == "web_search_tool_result":
                            if isinstance(content.content, list):
                                result_blocks: list[WebSearchResultBlockParam] = []
                                for result in content.content:
                                    result_blocks.append(
                                        WebSearchResultBlockParam(
                                            type="web_search_result",
                                            title=result.title,
                                            url=result.url,
                                            encrypted_content=result.encrypted_content,
                                            page_age=result.page_age,
                                        )
                                    )
                                assistant_content.append(
                                    WebSearchToolResultBlockParam(
                                        type="web_search_tool_result",
                                        content=result_blocks,
                                        tool_use_id=content.tool_use_id,
                                    )
                                )
                            else:
                                self.emitter.emit(
                                    WebSearchErrorEvent(error_code=content.content.error_code)
                                )
                                assistant_content.append(
                                    WebSearchToolResultBlockParam(
                                        type="web_search_tool_result",
                                        tool_use_id=content.tool_use_id,
                                        content=WebSearchToolRequestErrorParam(
                                            type="web_search_tool_result_error",
                                            error_code=content.content.error_code,
                                        ),
                                    )
                                )

        # Add the assistant message with all content blocks
        if assistant_content:
            self.history.append(MessageParam(role="assistant", content=assistant_content))

        # If there are no tool calls and only text content, treat as final response
        if not tool_calls and text_only_content:
            return "\n".join(text_only_content)

        # Now execute tools and add results as user messages
        if tool_calls:
            tool_results: list[ToolResultBlockParam] = []

            for tool_id, tool_name, tool_input in tool_calls:
                tool_result = self._handle_tool_call(tool_name, tool_input)
                result_dict = tool_result.to_dict()

                # Always add tool result to maintain valid conversation state
                tool_results.append(
                    ToolResultBlockParam(
                        type="tool_result",
                        tool_use_id=tool_id,
                        is_error=tool_result.is_error,
                        content=json.dumps(result_dict),
                    )
                )

                # Check if this is the output tool
                if tool_name == "output" and tool_result.data:
                    output_result = tool_result.data.result

            # Add all tool results as a single user message
            self.history.append(MessageParam(role="user", content=tool_results))

        return output_result

    def interrupt(self):
        """Signal the agent to stop at the next opportunity."""
        self._interrupted = True

    def run(self, prompt: str, max_iterations: int | None = 10) -> str:
        iteration = 0
        self._interrupted = False
        self.emitter.emit(AgentStartedEvent(prompt=prompt))

        try:
            self.history.append(MessageParam(role="user", content=prompt))
            while max_iterations is None or iteration < max_iterations:
                if self._interrupted:
                    self._interrupted = False
                    self.emitter.emit(AgentCompletedEvent(result=None, interrupted=True))
                    raise AgentInterrupted("Agent interrupted by user")
                iteration += 1
                try:
                    result = self._handle_iteration(require_output=iteration == max_iterations)
                except KeyboardInterrupt:
                    self.emitter.emit(AgentCompletedEvent(result=None, interrupted=True))
                    raise AgentInterrupted("Agent interrupted by user")
                if result is not None:
                    self.emitter.emit(AgentCompletedEvent(result=result))
                    return result
            raise Exception("Error: max iterations reached")
        except Exception as e:
            # Emit completion event even on error if we haven't already
            if not isinstance(e, AgentInterrupted):
                self.emitter.emit(AgentCompletedEvent(result=None, interrupted=False))
            raise

    def reset(self):
        self.__init__(settings=self.settings, client=self.client, emitter=self.emitter)
