import json

import anthropic
from anthropic.lib.streaming import MessageStreamManager
from anthropic.types import (
    ContentBlockParam,
    MessageParam,
    ModelParam,
    RedactedThinkingBlockParam,
    ServerToolUseBlockParam,
    TextBlockParam,
    ThinkingBlockParam,
    ThinkingConfigDisabledParam,
    ThinkingConfigEnabledParam,
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
        self._session_id: str | None = None

    @property
    def current_session_id(self) -> str | None:
        return self._session_id

    @current_session_id.setter
    def current_session_id(self, value: str | None) -> None:
        self._session_id = value

    def clear_history(self) -> None:
        """Clear the conversation history."""
        self.history = []
        self._session_id = None

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

    def _get_tools(self) -> list[Tool] | None:
        """Prepare tools list based on settings."""
        if not self.tools:
            return None

        # filter out edit tool if edit mode is never
        if self.settings.edit_mode == "never":
            return [tool for tool in self.tools if tool.tool_name != TEXT_EDITOR_TOOL_NAME]
        return list(self.tools)

    def _call_llm_streaming(self) -> MessageStreamManager:
        """Call the LLM and return a streaming context manager."""
        actual_tools = self._get_tools()
        messages = self._get_messages_for_api(self.thinking_enabled)
        thinking_config = (
            ThinkingConfigEnabledParam(type="enabled", budget_tokens=10000)
            if self.thinking_enabled
            else ThinkingConfigDisabledParam(type="disabled")
        )
        return self.client.messages.stream(
            max_tokens=10001,
            model=self.model,
            messages=messages,
            thinking=thinking_config,
            system=self.system_prompt if self.system_prompt else anthropic.omit,
            tools=[tool.to_anthropic_tool() for tool in actual_tools]
            if actual_tools
            else anthropic.omit,
        )

    def _handle_tool_call(self, tool_name: str, input: dict) -> ToolResult:
        tool = self.tool_dict.get(tool_name)
        if tool is None:
            raise ValueError(f"Tool {tool_name} not found")
        return tool.execute(input)

    def _handle_iteration(self) -> str | None:
        # Collect all content blocks into a single assistant message
        assistant_content: list[ContentBlockParam] = []
        tool_calls: list[tuple[str, str, dict]] = []  # (tool_id, tool_name, input)
        text_only_content: list[str] = []  # Collect text content for text-only responses

        # Track current content blocks being streamed
        current_blocks: dict[int, dict] = {}  # index -> accumulated block data

        with self._call_llm_streaming() as stream:
            for event in stream:
                if event.type == "content_block_start":
                    idx = event.index
                    block = event.content_block
                    self.emitter.emit(ContentBlockStartEvent(index=idx, block_type=block.type))

                    # initialize block to empty state. deltas will update the values.
                    if block.type == "thinking":
                        current_blocks[idx] = {
                            "type": "thinking",
                            "thinking": "",  # Initially empty
                            "signature": "",  # Comes via signature_delta
                        }
                    elif block.type == "text":
                        current_blocks[idx] = {"type": "text", "text": "", "citations": None}
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
                    elif block.type == "web_search_tool_result":
                        current_blocks[idx] = {
                            "type": "web_search_tool_result",
                            "tool_use_id": block.tool_use_id,
                            "content": [],
                        }
                    elif block.type == "redacted_thinking":
                        current_blocks[idx] = {"type": "redacted_thinking", "data": ""}

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
                    elif delta.type == "citations_delta":
                        if current_blocks[idx]["citations"] is None:
                            current_blocks[idx]["citations"] = []
                        current_blocks[idx]["citations"].append(delta.citation)

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
                        elif block_data["type"] == "web_search_tool_result":
                            assistant_content.append(
                                WebSearchToolResultBlockParam(
                                    type="web_search_tool_result",
                                    content=block_data["content"],
                                    tool_use_id=block_data["tool_use_id"],
                                )
                            )
                        elif block_data["type"] == "redacted_thinking":
                            assistant_content.append(
                                RedactedThinkingBlockParam(
                                    type="redacted_thinking",
                                    data=block_data["data"],
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

        # Execute tools and add results as user messages
        if tool_calls:
            tool_results: list[ToolResultBlockParam] = []

            for tool_id, tool_name, tool_input in tool_calls:
                tool_result = self._handle_tool_call(tool_name, tool_input)
                result_dict = tool_result.to_dict()

                tool_results.append(
                    ToolResultBlockParam(
                        type="tool_result",
                        tool_use_id=tool_id,
                        is_error=tool_result.is_error,
                        content=json.dumps(result_dict),
                    )
                )

            # Add all tool results as a single user message
            self.history.append(MessageParam(role="user", content=tool_results))

        return None

    def interrupt(self):
        """Signal the agent to stop at the next opportunity."""
        self._interrupted = True

    def run(self, prompt: str) -> str:
        self._interrupted = False
        self.emitter.emit(AgentStartedEvent(prompt=prompt))

        try:
            self.history.append(MessageParam(role="user", content=prompt))
            while True:
                if self._interrupted:
                    self._interrupted = False
                    self.emitter.emit(AgentCompletedEvent(result=None, interrupted=True))
                    raise AgentInterrupted("Agent interrupted by user")
                try:
                    result = self._handle_iteration()
                except KeyboardInterrupt:
                    self.emitter.emit(AgentCompletedEvent(result=None, interrupted=True))
                    raise AgentInterrupted("Agent interrupted by user")
                if result is not None:
                    self.emitter.emit(AgentCompletedEvent(result=result))
                    return result
        except Exception as e:
            # Emit completion event even on error if we haven't already
            if not isinstance(e, AgentInterrupted):
                self.emitter.emit(AgentCompletedEvent(result=None, interrupted=False))
            raise

    def reset(self):
        self.__init__(settings=self.settings, client=self.client, emitter=self.emitter)
