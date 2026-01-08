from pydantic import BaseModel, Field

from ..events import EventEmitter, FileViewedEvent
from .tool import Tool
from .utils import read_file_with_line_numbers, validate_path_within_project


class ReadFileInput(BaseModel):
    path: str
    start_line: int | None = Field(
        None,
        description="The 1-indexed line number to start reading from. If not provided, read from the beginning.",
    )
    end_line: int | None = Field(
        None,
        description="The 1-indexed line number to stop reading at (inclusive). If not provided, read to the end of the file.",
    )


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
        abs_path = validate_path_within_project(input.path)

        # Emit file viewed event
        self.emitter.emit(FileViewedEvent(path=input.path))

        result = read_file_with_line_numbers(
            path=abs_path,
            start_line=input.start_line,
            end_line=input.end_line,
            include_line_numbers=False,  # read_file returns raw content without line numbers
        )
        return ReadFileOutput(contents=result.content)


def create_read_file_tool(emitter: EventEmitter) -> ReadFileTool:
    return ReadFileTool(emitter=emitter)
