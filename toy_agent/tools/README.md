# Toy Agent Tools

A collection of tools for building AI agents with persistent bash sessions, file operations, and system utilities.

## Features

### 🔧 Available Tools

- **Bash Tool** - Execute bash commands in a persistent session
  - Maintains state across commands (environment variables, working directory, etc.)
  - Interactive command confirmation
  - Session restart capability
  
- **Text Editor Tool** - View, create, and edit text files
  - View entire files or specific line ranges
  - String replacement with exact matching
  - Insert text at specific line positions
  - Support for directories and image files
  
- **Read File Tool** - Read file contents in the current directory
  
- **Grep Tool** - Search files for patterns
  - Support for multiple flags (`-i`, `-v`, `-n`, `-l`, `-c`, `-r`, `-w`, `-E`, `-F`)
  - Pattern matching in files
  
- **Ping Tool** - Network connectivity testing
  - Check host availability
  - Connection statistics
  
- **Output Tool** - Format and deliver final results to users

## Architecture

### Core Components

#### `Tool` Base Class
All tools inherit from the `Tool` base class which provides:
- Standardized input/output schemas using Pydantic
- Execution interface with `ToolResult` wrapper
- Anthropic API integration support

#### `BashSession`
A persistent bash session manager that:
- Runs commands in a single bash process
- Uses background threads to read stdout/stderr
- Implements command markers to detect completion
- Supports session restart

#### Tool Results
Each tool returns a `ToolResult[T]` which contains:
- `success`: Boolean indicating operation success
- `data`: The typed output data (if successful)
- `error`: Error message (if failed)

## Project Structure

```
tools/
├── __init__.py              # Package exports
├── tool.py                  # Base Tool and ToolResult classes
├── bash_tool.py             # Bash command execution
├── bash_session.py          # Persistent bash session manager
├── grep_tool.py             # File search functionality
├── ping_tool.py             # Network connectivity tool
├── output_tool.py           # Output formatting
├── read_file_tool.py        # File reading
└── text_editor_tool.py      # Text editing operations
```

## Usage

### Basic Example

```python
from tools import BASH_TOOL, READ_FILE_TOOL, TEXT_EDITOR_TOOL

# Execute a bash command
result = BASH_TOOL.execute({"command": "ls -la"})
if result.success:
    print(result.data.stdout)

# Read a file
result = READ_FILE_TOOL.execute({"path": "example.txt"})
if result.success:
    print(result.data.content)

# Edit a file
TEXT_EDITOR_TOOL.execute({
    "command": "str_replace",
    "path": "example.txt",
    "old_str": "old text",
    "new_str": "new text"
})
```

### Bash Session Example

```python
from tools import BashSession

session = BashSession()

# Commands maintain state
session.execute_command("cd /tmp")
session.execute_command("export MY_VAR=hello")
result = session.execute_command("echo $MY_VAR")
print(result["stdout"])  # Output: hello

# Restart session to clear state
session.restart()
```

### Using with Anthropic API

Tools can be converted to Anthropic's tool format:

```python
from tools import BASH_TOOL, TEXT_EDITOR_TOOL

tools = [
    BASH_TOOL.to_anthropic_tool(),
    TEXT_EDITOR_TOOL.to_anthropic_tool(),
]

# Use with Anthropic's API
# client.messages.create(model="...", tools=tools, ...)
```

## Installation

```bash
# Install dependencies
pip install pydantic anthropic

# Import the tools
from tools import (
    BASH_TOOL,
    GREP_TOOL,
    PING_TOOL,
    OUTPUT_TOOL,
    READ_FILE_TOOL,
    TEXT_EDITOR_TOOL,
)
```

## Safety Features

### Bash Tool Safety
- **Interactive Confirmation**: Commands require user confirmation before execution
- **Skip Option**: Press 'q' to skip dangerous commands
- **Session Isolation**: Commands run in isolated bash process
- **Timeout Protection**: Commands have configurable timeouts (default: 10s)

### File Operations Safety
- **Exact Matching**: String replacement requires exact, unique matches
- **No Silent Failures**: Operations fail explicitly if conditions aren't met

## Development

### Creating a Custom Tool

```python
from pydantic import BaseModel
from tools.tool import Tool, ToolResult

class MyInput(BaseModel):
    param: str

class MyOutput(BaseModel):
    result: str

class MyTool(Tool):
    def __init__(self):
        super().__init__(
            tool_name="my_tool",
            description="My custom tool",
            input_schema=MyInput,
            output_schema=MyOutput,
            run=self._run
        )
    
    def _run(self, i: dict) -> MyOutput:
        return MyOutput(result=f"Processed: {i['param']}")
    
    def execute(self, input: dict) -> ToolResult[MyOutput]:
        try:
            result = self._run(input)
            return ToolResult(data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))

MY_TOOL = MyTool()
```

## TODO

- [ ] Strongly type bash tool input (currently uses dict)
- [ ] Add allowlist for auto-approved commands
- [ ] Implement configurable timeout per command
- [ ] Add command history tracking
- [ ] Improve error handling and reporting

## License

MIT

## Contributing

Contributions welcome! Please ensure all tools follow the established patterns:
1. Inherit from `Tool` base class
2. Use Pydantic models for input/output
3. Return `ToolResult` wrapper
4. Implement `to_anthropic_tool()` method
5. Export instance in `__init__.py`
