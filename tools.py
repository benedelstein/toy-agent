from dataclasses import dataclass
import subprocess
from typing import Callable, Generic, TypeVar, cast
from anthropic.types import ToolBash20250124Param, ToolParam, ToolUnionParam
from anthropic.types.beta import BetaToolBash20241022Param
from pydantic import BaseModel

from bash_session import BashSession

InputType = TypeVar("InputType", bound=BaseModel)
OutputType = TypeVar("OutputType", bound=BaseModel)

@dataclass
class Tool(Generic[InputType, OutputType]):
    tool_name: str
    description: str
    input_schema: type[InputType]
    output_schema: type[OutputType]
    run: Callable[[InputType], OutputType]
    
    def to_anthropic_tool(self) -> ToolUnionParam:
        return ToolParam(
            name=self.tool_name,
            description=self.description,
            input_schema=self.input_schema.model_json_schema(),
            type="custom"
        )
    
    def execute(self, input: dict) -> dict:
        input_model = self.input_schema.model_validate(input)
        output = self.run(cast(InputType, input_model))
        return output.model_dump()

class OutputToolInput(BaseModel):
    result: str
class OutputToolOutput(BaseModel):
    result: str
    
def run_output(input: OutputToolInput) -> OutputToolOutput:
    return OutputToolOutput(result=input.result)
        
OUTPUT_TOOL = Tool(
    tool_name="output",
    description="Output the final result to the user.",
    input_schema=OutputToolInput,
    output_schema=OutputToolOutput,
    run=run_output
)

class PingInput(BaseModel):
    url: str

class PingOutput(BaseModel):
    response: str
    
def run_ping(input: PingInput) -> PingOutput:
    url = input.url
    result = subprocess.run(
        ["ping", "-c", "5", url],
        text=True,
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
        timeout=10
    )
    return PingOutput(response=result.stdout)

PING_TOOL = Tool(
    tool_name="ping",
    description=f"Ping a host. Call like so {{'url': 'example.com'}}",
    input_schema=PingInput,
    output_schema=PingOutput,
    run=run_ping
)

class BashInput(BaseModel):
    command: str
class BashOutput(BaseModel):
    stdout: str
    stderr: str

class BashTool(Tool):
    session: BashSession
    def __init__(self):
        super().__init__(
            tool_name="bash",
            description="",  # not used
            input_schema=BashInput,  # not used
            output_schema=BashOutput,
            run=self._run_bash
        )
    
    def to_anthropic_tool(self) -> ToolUnionParam:
        return ToolBash20250124Param(
            name="bash",
            type="bash_20250124"
        )
    
    def _run_bash(self, i: dict) -> dict:
        if i.get("restart"):
            self.session.restart()
            return {"result": "Bash session restarted"}
        # confirm the command
        print(f"Running bash command: {i['command']}")
        # here you could present the menu with options to skip the command or run it
        # or always allow it (add command to some list of allowed commands)
        a = input("Press Enter to continue or 'q' to skip")
        if a == "q":
            return {"result": "Command skipped"}
        result = subprocess.run(
            i["command"],
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        return {"stdout": result.stdout, "stderr": result.stderr}
    
    def execute(self, input: dict) -> dict:
        # Skip pydantic validation for built-in tools
        return self._run_bash(input)
    
    
BASH_TOOL = BashTool()