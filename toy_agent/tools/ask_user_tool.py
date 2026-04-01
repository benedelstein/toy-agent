from pydantic import BaseModel, Field

from ..events import EventEmitter
from .tool import Tool


class AskUserInput(BaseModel):
    question: str = Field(description="The question to ask the user.")


class AskUserOutput(BaseModel):
    answer: str = Field(description="The user's response.")


class AskUserTool(Tool["AskUserInput", "AskUserOutput"]):
    def __init__(self, emitter: EventEmitter):
        super().__init__(
            tool_name="ask_user",
            description=(
                "Ask the user a question and wait for their response. "
                "Use this tool when you need clarification, want to confirm a plan before proceeding, "
                "or need the user to make a decision. "
                "Do not use this tool for routine status updates — only when you genuinely need input."
            ),
            input_schema=AskUserInput,
            output_schema=AskUserOutput,
            run=self._run,
            emitter=emitter,
        )

    def _run(self, input: AskUserInput) -> AskUserOutput:
        answer = self.emitter.request_input(input.question)
        return AskUserOutput(answer=answer)


def create_ask_user_tool(emitter: EventEmitter) -> AskUserTool:
    return AskUserTool(emitter=emitter)
