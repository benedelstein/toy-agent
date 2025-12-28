from pydantic import BaseModel
from tools.tool import Tool, ToolResult
from tools.bash_session import BashSession
from anthropic.types import ToolUnionParam, ToolBash20250124Param
import subprocess

class BashInput(BaseModel):
    command: str | None = None # will be omitted if restart is true
    restart: bool | None = None # will be omitted if command is provided

class BashOutput(BaseModel):
    stdout: str | None = None
    stderr: str | None = None
    is_error: bool = False

class BashTool(Tool):
    session: BashSession

    def __init__(self, session: BashSession):
        self.session = session
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
    
    def _run_bash(self, i: BashInput) -> BashOutput:
        if i.restart:
            self.session.restart()
            return BashOutput()
        if i.command is None:
            raise ValueError("Command is required")
        # confirm the command
        print(f"Running bash command: {i.command}")
        # TODO: here you could present the menu with options to skip the command or run it
        # or always allow it (add command to some list of allowed commands)
        a = input("Press Enter to continue or 'q [reason]' to skip > ")
        if a.strip().lower().startswith("q"):
            reason = a.strip()[1:].strip() or "no reason given"
            return BashOutput(is_error=True, stderr=f"Command skipped: {i.command} - {reason}")
        result = self.session.execute_command(i.command)
        return BashOutput(stdout=result["stdout"], stderr=result["stderr"])
    
    def execute(self, input: dict) -> ToolResult[BashOutput]:
        try:
            input_model = self.input_schema.model_validate(input)
            result = self._run_bash(input_model)
            if result.is_error:
                return ToolResult(success=False, error=result.stderr)
            return ToolResult(data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    

BASH_TOOL = BashTool(session=BashSession())