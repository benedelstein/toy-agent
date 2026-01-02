import os

from pydantic import BaseModel, Field

from events import EventEmitter, FileViewedEvent
from tools.tool import Tool


class ReadFileInput(BaseModel):
    path: str
    start_line: int | None = Field(None, description="The 1-indexed line number to start reading from. If not provided, read from the beginning.")
    end_line: int | None = Field(None, description="The 1-indexed line number to stop reading at (inclusive). If not provided, read to the end of the file.")


class ReadFileOutput(BaseModel):
    contents: str


class ReadFileTool(Tool):
    def __init__(self, emitter: EventEmitter):
        super().__init__(
            tool_name="read_file",
            description="""Read a file in the current directory. Use this when you need to view the contents of a file.
            Always use this instead of the bash_tool (do not use cat or other bash commands to read files).
            Call like so {{'path': 'path/to/file'}}
            Optionally specify start_line and end_line (1-indexed, inclusive) to read a specific range:
            {{'path': 'path/to/file', 'start_line': 10, 'end_line': 25}}
            
            Do not use this to view directories. It can only view individual files.
            """,
            input_schema=ReadFileInput,
            output_schema=ReadFileOutput,
            run=self._run_read_file,
            emitter=emitter,
        )

    def _run_read_file(self, input: ReadFileInput) -> ReadFileOutput:
        from tools.utils import validate_path_within_project

        path = validate_path_within_project(input.path)

        # Emit file viewed event
        self.emitter.emit(FileViewedEvent(path=path))

        if not os.path.exists(path):
            raise ValueError(f"File {path} does not exist")

        with open(path, "r") as file:
            lines = file.readlines()

        # If no line range specified, return entire file
        if input.start_line is None and input.end_line is None:
            return ReadFileOutput(contents="".join(lines))

        # Convert to 0-indexed, default start to 1 if not provided
        start_idx = (input.start_line or 1) - 1
        end_idx = input.end_line if input.end_line is not None else len(lines)

        # Validate line range
        if start_idx < 0:
            raise ValueError(f"start_line must be >= 1, got {input.start_line}")
        if end_idx > len(lines):
            end_idx = len(lines)
        if start_idx >= len(lines):
            raise ValueError(f"start_line {input.start_line} is beyond end of file ({len(lines)} lines)")
        if start_idx >= end_idx:
            raise ValueError(f"end_line ({input.end_line}) must be >= start_line ({input.start_line})")

        selected_lines = lines[start_idx:end_idx]
        return ReadFileOutput(contents="".join(selected_lines))


def create_read_file_tool(emitter: EventEmitter) -> ReadFileTool:
    return ReadFileTool(emitter=emitter)
