from dataclasses import dataclass
from typing import Callable, Generic, TypeVar, cast
from anthropic.types import ToolParam, ToolUnionParam
from pydantic import BaseModel
from events import EventEmitter, ToolStartedEvent, ToolCompletedEvent, ToolErrorEvent

InputType = TypeVar("InputType", bound=BaseModel)
OutputType = TypeVar("OutputType", bound=BaseModel)


class ToolResult(BaseModel, Generic[OutputType]):
    """Wrapper for tool results that includes error handling"""
    success: bool = True
    data: OutputType | None = None
    error: str | None = None

    @property
    def is_error(self) -> bool:
        return not self.success

    def to_dict(self) -> dict:
        """Convert to dict for Anthropic API content field"""
        if self.is_error:
            return {"error": self.error}
        elif self.data:
            return self.data.model_dump()
        return {}

@dataclass
class Tool(Generic[InputType, OutputType]):
    tool_name: str
    description: str
    input_schema: type[InputType]
    output_schema: type[OutputType]
    run: Callable[[InputType], OutputType]
    emitter: EventEmitter

    def to_anthropic_tool(self) -> ToolUnionParam:
        return ToolParam(
            name=self.tool_name,
            description=self.description,
            input_schema=self.input_schema.model_json_schema(),
            type="custom"
        )

    def execute(self, input: dict) -> ToolResult[OutputType]:
        self.emitter.emit(ToolStartedEvent(tool_name=self.tool_name, input=input))

        try:
            input_model = self.input_schema.model_validate(input)
            output = self.run(cast(InputType, input_model))

            self.emitter.emit(ToolCompletedEvent(
                tool_name=self.tool_name,
                output=output.model_dump() if output else None
            ))

            return ToolResult(data=output)
        except Exception as e:
            self.emitter.emit(ToolErrorEvent(tool_name=self.tool_name, error=str(e)))
            return ToolResult(success=False, error=str(e))
