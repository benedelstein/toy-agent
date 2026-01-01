from __future__ import annotations
from typing import TYPE_CHECKING, Callable, Literal
from pydantic import BaseModel, Field
from anthropic.types import ToolUnionParam, ToolParam
from tools.tool import Tool, ToolResult
from events import EventEmitter, ToolStartedEvent, ToolCompletedEvent, ToolErrorEvent

if TYPE_CHECKING:
    from agent import Agent

agent_types = Literal["explore", "plan"]


class SubAgentInput(BaseModel):
    agent_type: agent_types = Field(description="The type of sub-agent to create, specialized for different tasks.")
    prompt: str = Field(description="The prompt to send to the sub-agent")


class SubAgentOutput(BaseModel):
    result: str


class SubAgentTool(Tool):
    """A tool that spawns a sub-agent to handle complex tasks."""

    def __init__(
        self,
        emitter: EventEmitter,
        create_agent: Callable[[agent_types, EventEmitter], Agent],
    ):
        self.create_agent = create_agent
        super().__init__(
            tool_name="sub_agent",
            description="""
            A tool that spawns a sub-agent to handle complex tasks. Use this tool to offload tasks to a new agent with fresh context and specialized focus.
            For example, you may want to use this to explore part of a codebase. The `agent_type` parameter determines what the subagent is used for.
            The `prompt` parameter tells the agent what to focus on. Be very descriptive in your prompt!
            For example, for a `plan` agent, you should write out a detailed spec for what you want it to plan - describe the problem in detail, point to any relevant files, and describe the desired solution.
            Mention any details or suggestions that the user has provided.
            """,
            input_schema=SubAgentInput,
            output_schema=SubAgentOutput,
            run=self._run_sub_agent,
            emitter=emitter
        )

    def _run_sub_agent(self, input: SubAgentInput) -> SubAgentOutput:
        # Pass emitter to create_agent so sub-agent gets the same emitter
        agent = self.create_agent(input.agent_type, self.emitter)
        result = agent.run(prompt=input.prompt, max_iterations=None)
        return SubAgentOutput(result=result)

    def to_anthropic_tool(self) -> ToolUnionParam:
        return ToolParam(
            name=self.tool_name,
            description=self.description,
            input_schema=SubAgentInput.model_json_schema(),
            type="custom"
        )

    def execute(self, input: dict) -> ToolResult[SubAgentOutput]:
        self.emitter.emit(ToolStartedEvent(tool_name=self.tool_name, input=input))

        try:
            input_model = SubAgentInput.model_validate(input)
            result = self._run_sub_agent(input_model)

            self.emitter.emit(ToolCompletedEvent(
                tool_name=self.tool_name,
                output=result.model_dump() if result else None
            ))
            return ToolResult(data=result)
        except Exception as e:
            self.emitter.emit(ToolErrorEvent(tool_name=self.tool_name, error=str(e)))
            return ToolResult(success=False, error=str(e))


def create_sub_agent_tool(
    emitter: EventEmitter,
    create_agent: Callable[[agent_types, EventEmitter], Agent]
) -> SubAgentTool:
    return SubAgentTool(emitter=emitter, create_agent=create_agent)
