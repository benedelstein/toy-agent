from pydantic import BaseModel
from tools.tool import Tool, ToolResult
from tools.bash_session import BashSession
from anthropic.types import ToolUnionParam, ToolBash20250124Param
from events import EventEmitter, ToolStartedEvent, ToolCompletedEvent, ToolErrorEvent


class BashInput(BaseModel):
    command: str | None = None  # will be omitted if restart is true
    restart: bool | None = None  # will be omitted if command is provided


class BashOutput(BaseModel):
    stdout: str | None = None
    stderr: str | None = None
    is_error: bool = False


class BashTool(Tool):
    session: BashSession

    def __init__(self, emitter: EventEmitter, session: BashSession | None = None):
        self.session = session or BashSession()
        super().__init__(
            tool_name="bash",
            description="",  # not used - anthropic api overrides it.
            input_schema=BashInput,  # not used
            output_schema=BashOutput,
            run=self._run_bash,
            emitter=emitter
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

        # Use emitter for confirmation
        approved, reason = self.emitter.request_confirmation(
            tool_name="bash",
            action="execute",
            path=None,
            preview=f"Running bash command: {i.command}"
        )
        if not approved:
            return BashOutput(
                is_error=True,
                stderr=f"Command skipped: {i.command} - {reason or 'no reason given'}"
            )

        result = self.session.execute_command(i.command)
        return BashOutput(stdout=result["stdout"], stderr=result["stderr"])

    def execute(self, input: dict) -> ToolResult[BashOutput]:
        self.emitter.emit(ToolStartedEvent(tool_name=self.tool_name, input=input))

        try:
            input_model = self.input_schema.model_validate(input)
            result = self._run_bash(input_model)
            if result.is_error:
                self.emitter.emit(ToolErrorEvent(tool_name=self.tool_name, error=result.stderr or "Unknown error"))
                return ToolResult(success=False, error=result.stderr)

            self.emitter.emit(ToolCompletedEvent(
                tool_name=self.tool_name,
                output=result.model_dump() if result else None
            ))
            return ToolResult(data=result)
        except Exception as e:
            self.emitter.emit(ToolErrorEvent(tool_name=self.tool_name, error=str(e)))
            return ToolResult(success=False, error=str(e))


def create_bash_tool(emitter: EventEmitter) -> BashTool:
    return BashTool(emitter=emitter)
