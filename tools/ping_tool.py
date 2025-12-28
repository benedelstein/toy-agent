from pydantic import BaseModel
from tools.tool import Tool
import subprocess

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
    description=f"Ping a host for connectivity stats. Call like so {{'url': 'example.com'}}",
    input_schema=PingInput,
    output_schema=PingOutput,
    run=run_ping
)