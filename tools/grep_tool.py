import os
from pydantic import BaseModel
from tools.tool import Tool
from events import EventEmitter
from typing import Literal
import subprocess


class GrepInput(BaseModel):
    pattern: str
    file: str
    flags: list[Literal["-i", "-v", "-n", "-l", "-c", "-r", "-w", "-E", "-F"]] = []


class GrepOutput(BaseModel):
    result: str


def run_grep(input: GrepInput) -> GrepOutput:
    from tools.utils import validate_path_within_project
    absolute_path = validate_path_within_project(input.file)
    cmd = ["grep"] + input.flags + [input.pattern, absolute_path]

    result = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        timeout=10
    )
    return GrepOutput(result=result.stdout)


def create_grep_tool(emitter: EventEmitter) -> Tool:
    return Tool(
        tool_name="grep",
        description="Search a file in this directory for a pattern. Call like so {{'pattern': 'pattern', 'file': 'file', 'flags': '-i'}}",
        input_schema=GrepInput,
        output_schema=GrepOutput,
        run=run_grep,
        emitter=emitter
    )
