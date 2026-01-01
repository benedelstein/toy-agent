import os
from pydantic import BaseModel
from tools.tool import Tool
from events import EventEmitter, FileViewedEvent


class ReadFileInput(BaseModel):
    path: str


class ReadFileOutput(BaseModel):
    contents: str


class ReadFileTool(Tool):
    def __init__(self, emitter: EventEmitter):
        super().__init__(
            tool_name="read_file",
            description="""Read a file in the current directory. Use this when you need to view the contents of a file. 
            Always use this instead of the bash_tool (do not use cat or other bash commands to read files).
            Call like so {{'path': 'path/to/file'}}
            """,
            input_schema=ReadFileInput,
            output_schema=ReadFileOutput,
            run=self._run_read_file,
            emitter=emitter
        )

    def _run_read_file(self, input: ReadFileInput) -> ReadFileOutput:
        from tools.utils import validate_path_within_project
        path = validate_path_within_project(input.path)

        # Emit file viewed event
        self.emitter.emit(FileViewedEvent(path=path))

        if not os.path.exists(path):
            raise ValueError(f"File {path} does not exist")

        with open(path, "r") as file:
            return ReadFileOutput(contents=file.read())


def create_read_file_tool(emitter: EventEmitter) -> ReadFileTool:
    return ReadFileTool(emitter=emitter)
