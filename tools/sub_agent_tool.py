from __future__ import annotations
from typing import TYPE_CHECKING, Callable, Literal
from pydantic import BaseModel, Field
from anthropic.types import ToolUnionParam, ToolParam
from tools.tool import Tool, ToolResult

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
        create_agent: Callable[[agent_types], Agent],
    ):
        self.create_agent = create_agent
        super().__init__(
            tool_name="sub_agent",
            description="""
            A tool that spawns a sub-agent to handle complex tasks. Use this tool to offload tasks to a new agent with fresh context and specialized focus.
            For example, you may want to use this to explore part of a codebase. The `agent_type` parameter determines what the subagent is used for.
            """,
            input_schema=SubAgentInput,
            output_schema=SubAgentOutput,
            run=self._run_sub_agent
        )

    def _run_sub_agent(self, input: SubAgentInput) -> SubAgentOutput:
        agent = self.create_agent(input.agent_type)
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
        try:
            input_model = SubAgentInput.model_validate(input)
            result = self._run_sub_agent(input_model)
            return ToolResult(data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
