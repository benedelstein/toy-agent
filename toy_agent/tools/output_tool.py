from pydantic import BaseModel

from ..events import EventEmitter
from .tool import Tool


class OutputToolInput(BaseModel):
    result: str


class OutputToolOutput(BaseModel):
    result: str


def run_output(input: OutputToolInput) -> OutputToolOutput:
    return OutputToolOutput(result=input.result)


def create_output_tool(emitter: EventEmitter) -> Tool:
    return Tool(
        tool_name="output",
        description="Output the final result to the user. Use this tool when you have completed a task and want to provide a structured response. For simple conversational responses, you may also just respond with plain text.",
        input_schema=OutputToolInput,
        output_schema=OutputToolOutput,
        run=run_output,
        emitter=emitter,
    )
