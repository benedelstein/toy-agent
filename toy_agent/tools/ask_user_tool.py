from pydantic import BaseModel, Field

from ..events import EventEmitter
from .tool import Tool


class AskUserInput(BaseModel):
    question: str = Field(
        description="The question to ask the user. Be specific and concise."
    )


class AskUserOutput(BaseModel):
    response: str = Field(description="The user's response to the question.")


def create_ask_user_tool(emitter: EventEmitter) -> Tool[AskUserInput, AskUserOutput]:
    def run_ask_user(input: AskUserInput) -> AskUserOutput:
        response = emitter.request_input(f"🤔 {input.question}\n> ")
        return AskUserOutput(response=response)

    return Tool(
        tool_name="ask_user",
        description=(
            "Ask the user a question and wait for their response. "
            "Use this tool when you need clarification, want to confirm a plan before proceeding, "
            "or need the user to make a decision. Do not use this tool for trivial questions - "
            "only when the answer will meaningfully affect your approach."
        ),
        input_schema=AskUserInput,
        output_schema=AskUserOutput,
        run=run_ask_user,
        emitter=emitter,
    )
