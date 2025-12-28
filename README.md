# Toy Agent

## Overview

Simple coding agent using the Anthropic API.

### Core Agent Capabilities
- **Agentic Loop**: Continuously iterates between the LLM and tool execution until task completion
- **Extended Thinking**: Optional thinking blocks that allow Claude to reason through problems before responding
- **Tool Use**: Flexible tool system with structured input/output validation via Pydantic
- **Conversation History**: Maintains full conversation context across iterations
- **Error Handling**: Robust error handling for tool execution failures
- **Interactive & CLI Modes**: Run as an interactive REPL or with command-line arguments

### Built-in Tools

The framework includes several pre-built tools:

1. **Read File Tool** (`read_file`)
   - Read file contents from the current project directory
   - Path validation to ensure files are within project boundaries

2. **Text Editor Tool** (`str_replace_based_edit_tool`)
   - View file contents with optional character limits
   - Create new files
   - String-based find-and-replace editing
   - Insert text at specific line numbers
   - Uses Anthropic's native text editor tool type

3. **Grep Tool** (`grep`)
   - Search for patterns in files using grep
   - Support for common grep flags (-i, -v, -n, -l, -c, -r, -w, -E, -F)
   - Project-scoped file access

4. **Ping Tool** (`ping`)
   - Test network connectivity to hosts
   - Returns detailed ping statistics

5. **Bash Tool** (`bash`)
   - Execute bash commands in a persistent session
   - Interactive confirmation for security
   - Session management (restart capability)
   - Non-blocking I/O with background threads

6. **Output Tool** (`output`)
   - Special tool that signals task completion
   - Returns final response to the user
   - Can be called automatically at max iterations or by the agent when ready

## Architecture

### Agent Class (`agent.py`)
The core `Agent` class handles:
- System prompt configuration
- Tool registration and management
- Message history tracking
- LLM API calls with thinking configuration
- Tool execution and result handling
- Iteration management with configurable limits

### Tool System (`tools/`)
Clean separation of concerns with:
- **Base Tool Classes** (`tool.py`): Generic `Tool` and `ToolResult` classes with Pydantic validation
- **Individual Tools**: Each tool in its own module with typed input/output schemas
- **Utilities** (`utils.py`): Project root detection and path validation for security

### Key Design Patterns
- **Type Safety**: Extensive use of Pydantic BaseModels for structured I/O
- **Generic Types**: Tool base class uses TypeVars for flexible typing
- **Security**: Path validation ensures tools only access files within project
- **Extensibility**: Easy to add new tools by following the established pattern

## How It Works

1. **Initialization**: Create an Agent with optional system prompt, tools, and thinking configuration
2. **User Input**: Provide a prompt either via CLI argument or interactive mode
3. **Agentic Loop**:
   - Agent calls Claude API with conversation history and available tools
   - Claude responds with text and/or tool use requests
   - Agent executes requested tools and appends results to history
   - Loop continues until the `output` tool is called or max iterations reached
4. **Response**: Agent returns the final result from the `output` tool

## Usage

### Interactive Mode
```bash
python main.py
```

Start an interactive REPL session where you can have extended conversations with the agent.

### CLI Mode
```bash
python main.py "your prompt here"
```

Execute a single prompt and get a response.

### Programmatic Usage
```python
from agent import Agent
from tools import PING_TOOL, READ_FILE_TOOL, TEXT_EDITOR_TOOL

agent = Agent(
    tools=[PING_TOOL, READ_FILE_TOOL, TEXT_EDITOR_TOOL],
    thinking_enabled=True,
    system_prompt="You are a helpful coding assistant."
)

result = agent.run(
    prompt="Read the main.py file and explain what it does",
    max_iterations=10
)
print(result)
```

## Requirements

- Python >= 3.11
- anthropic >= 0.75.0
- python-dotenv >= 0.9.9

Install dependencies:
```bash
uv sync
```

## Configuration

Set your Anthropic API key in a `.env` file:
```
ANTHROPIC_API_KEY=your_api_key_here
```

## Project Structure

```
toy-agent/
├── agent.py             # Core Agent class
├── main.py              # CLI entry point and interactive REPL
├── tools/               # Tool implementations
│   ├── __init__.py      # Tool exports
│   ├── tool.py          # Base Tool and ToolResult classes
│   ├── bash_tool.py     # Bash command execution
│   ├── bash_session.py  # Persistent bash session manager
│   ├── grep_tool.py     # File pattern searching
│   ├── ping_tool.py     # Network connectivity testing
│   ├── read_file_tool.py # File reading
│   ├── text_editor_tool.py # File editing
│   ├── output_tool.py   # Task completion signaling
│   └── utils.py         # Path validation utilities
├── pyproject.toml       # Project metadata and dependencies
└── README.md            # This file
```

## Future Enhancements

- Configurable stop conditions
- Tool whitelisting/blacklisting per agent instance
- Streaming responses
- Token usage tracking and budgets
- Additional tool integrations
- Multi-agent coordination

## License

This is a demonstration project for educational purposes.
