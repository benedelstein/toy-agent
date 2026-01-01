from pydantic import BaseModel
from tools.tool import Tool
from events import EventEmitter


class OutputToolInput(BaseModel):
    result: str


class OutputToolOutput(BaseModel):
    result: str


def run_output(input: OutputToolInput) -> OutputToolOutput:
    return OutputToolOutput(result=input.result)


def create_output_tool(emitter: EventEmitter) -> Tool:
    return Tool(
        tool_name="output",
        description="Output the final result to the user. Use this tool when you are ready to deliver a response - **do not** use the regular text output response type.",
        input_schema=OutputToolInput,
        output_schema=OutputToolOutput,
        run=run_output,
        emitter=emitter
    )
