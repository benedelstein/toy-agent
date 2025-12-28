import os
from pydantic import BaseModel
from tools.tool import Tool

class ReadFileInput(BaseModel):
    path: str

class ReadFileOutput(BaseModel):
    contents: str

def read_file(input: ReadFileInput) -> ReadFileOutput:
    from tools.utils import validate_path_within_project
    path = validate_path_within_project(input.path)

    if not os.path.exists(path):
        raise ValueError(f"File {path} does not exist")

    with open(path, "r") as file:
        return ReadFileOutput(contents=file.read())

READ_FILE_TOOL = Tool(
    tool_name="read_file",
    description="Read a file in the current directory. Use this when you need to view the contents of a file.Call like so {{'path': 'path/to/file'}}",
    input_schema=ReadFileInput,
    output_schema=ReadFileOutput,
    run=read_file
)