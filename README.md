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
- **Composable UI**: The ui handler is decoupled from the agent, allowing for easy swapping of UI.
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
uv run toy_agent/main.py
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

## Testing

install globally
```bash
uv tool install --editable .
```
