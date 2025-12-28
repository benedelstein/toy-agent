# Guide for LLMs Working in the Toy-Agent Repository

## Repository Overview

This is **Toy-Agent**, a simple but powerful agentic coding assistant framework built on the Anthropic API. It implements an agentic loop where Claude iteratively uses tools to complete tasks. Your role as an LLM working in this codebase is to help improve, extend, or debug this framework.

## Core Architecture

### The Agent Loop (agent.py)
The `Agent` class is the heart of the system:
- Maintains conversation history (`self.history`) as a list of `MessageParam`
- Calls Claude API with tools, thinking configuration, and system prompts
- Executes tools based on Claude's responses
- Continues iterating until the `output` tool is called or max iterations reached
- **Key method**: `run(prompt, max_iterations)` - entry point for task execution

### Tool System (tools/)
Tools follow a consistent pattern:
1. **Base classes** (`tool.py`): Generic `Tool[InputType, OutputType]` and `ToolResult[OutputType]`
2. **Type safety**: All tools use Pydantic `BaseModel` for input/output schemas
3. **Error handling**: `ToolResult` wraps success/failure states
4. **Anthropic integration**: Tools convert to `ToolParam` for the API

### Settings & Configuration (settings.py)
- `EditMode` enum: Controls file editing behavior (`ask`, `always`, `never`)
- `SETTINGS` singleton: Global configuration accessible to tools
- Used primarily by `TEXT_EDITOR_TOOL` for confirmation flows

## Available Tools

When working in this repo, you have access to:

1. **read_file** - Read file contents (use for examining code)
2. **str_replace_based_edit_tool** - View, create, edit files with string replacement or line insertion
3. **grep** - Search for patterns in files (useful for finding references)
4. **ping** - Test network connectivity (less useful for code work)
5. **bash** - Execute bash commands (not shown in default main.py setup)
6. **output** - Signal task completion with final result

## Working Patterns

### When Reading Code
1. Start with `read_file` on the main entry point (usually `main.py` or `agent.py`)
2. Use `grep` to find specific patterns, function names, or imports
3. Read related files to understand dependencies and flow
4. Pay attention to type hints - this codebase uses extensive typing

### When Editing Code
1. **Always read first**: Use `read_file` to see the current state
2. **Find the exact string**: Locate the precise code to modify
3. **Use str_replace**: Provide the EXACT `old_str` (whitespace-sensitive) and the `new_str`
4. **One change at a time**: Make focused, atomic changes
5. **Respect existing patterns**: Match the coding style (imports at top, type hints, etc.)

### When Creating New Tools
Follow the established pattern:
```python
from pydantic import BaseModel
from tools.tool import Tool, ToolResult

class MyToolInput(BaseModel):
    param1: str
    param2: int

class MyToolOutput(BaseModel):
    result: str

def run_my_tool(input: MyToolInput) -> MyToolOutput:
    # Implementation here
    return MyToolOutput(result="...")

MY_TOOL = Tool(
    tool_name="my_tool",
    description="What the tool does",
    input_schema=MyToolInput,
    output_schema=MyToolOutput,
    run=run_my_tool
)
```

Then export it from `tools/__init__.py` and add to agent initialization in `main.py`.

### When Extending the Agent
Key extension points:
- **System prompts**: Customize agent behavior via `system_prompt` parameter
- **Tool selection**: Pass different tool lists to `Agent.__init__`
- **Thinking config**: Control extended thinking with `thinking_enabled` parameter
- **Settings**: Add new configuration options to `Settings` class
- **Stop conditions**: Modify `_handle_iteration` to implement custom stopping logic

## Code Style & Conventions

1. **Type hints everywhere**: Use proper type annotations (e.g., `str | None` not `Optional[str]`)
2. **Pydantic for validation**: All structured data uses `BaseModel`
3. **Explicit over implicit**: Be clear about types, return values, error cases
4. **Modular design**: One tool per file, clear separation of concerns
5. **Error handling**: Use `ToolResult` pattern for tool errors
6. **Path security**: Always use `validate_path_within_project()` for file operations

## Important Implementation Details

### Message History Structure
- Messages alternate between `role="user"` and `role="assistant"`
- Assistant messages can contain: `text`, `thinking`, `tool_use` blocks
- Tool results are added as user messages with `tool_result` content
- Thinking blocks are stripped when `thinking_enabled=False`

### Tool Execution Flow
1. Agent calls `_call_llm()` to get Claude's response
2. Response contains content blocks (text, thinking, tool_use)
3. All content added to history as single assistant message
4. Tools executed synchronously, results batched into user message
5. Loop continues unless `output` tool called or text-only response

### The Output Tool
Special tool that signals completion:
- Always included in available tools (unless requiring output)
- Can be called early by Claude or forced at max iterations
- Returns final result string to the caller
- Text-only responses (no tool calls) also treated as completion

### Edit Mode Settings
The `TEXT_EDITOR_TOOL` respects edit mode:
- `ask`: Prompts user for confirmation (default)
- `always`: Auto-approves all edits
- `never`: Blocks all edits (tool filtered from available tools)
- Set via `/settings edit_mode <mode>` in interactive mode

## Testing Your Changes

1. **Use the CLI mode**: `python main.py "your test prompt"`
2. **Interactive mode**: `python main.py` then type prompts
3. **Test with small prompts first**: Verify basic functionality
4. **Check error handling**: Try invalid inputs, missing files, etc.
5. **Review conversation history**: Ensure messages are properly formatted

## Common Pitfalls to Avoid

1. ❌ **Don't approximate `old_str`**: Must be EXACT match including whitespace
2. ❌ **Don't modify multiple files simultaneously**: Do one at a time
3. ❌ **Don't assume file contents**: Always read before editing
4. ❌ **Don't break type safety**: Maintain all type hints
5. ❌ **Don't bypass path validation**: Use utils for file security
6. ❌ **Don't forget imports**: Add new imports at top of file
7. ❌ **Don't break the tool protocol**: Input/output must be Pydantic models

## Debugging Tips

1. **Message history issues**: Check `_get_messages_for_api()` logic
2. **Tool not working**: Verify Pydantic schema matches Anthropic format
3. **Import errors**: Ensure exports in `__init__.py` files
4. **Type errors**: Use `cast()` when needed, but prefer proper typing
5. **Path issues**: Remember paths are relative to project root

## Environment Setup

- Python >= 3.11 required
- Dependencies managed via `uv` (see `pyproject.toml`)
- `.env` file must contain `ANTHROPIC_API_KEY`
- Run with: `python main.py [prompt]`

## Philosophy of This Codebase

1. **Simplicity over complexity**: Keep it understandable and hackable
2. **Type safety**: Catch errors at development time, not runtime
3. **Extensibility**: Easy to add new tools and capabilities
4. **Security**: Validate paths, handle errors, confirm destructive actions
5. **Developer experience**: Clear error messages, good defaults

## When You're Done

Use the `output` tool to provide your final response, including:
- Summary of changes made
- Files modified/created
- Testing recommendations
- Any follow-up considerations

Remember: You're working in a meta-environment where an LLM (Claude) is used to build tools for other LLMs. Keep the abstractions clean and the patterns consistent.
