from pydantic import BaseModel
from app_state import AppState
from tools.tool import Tool
from todo import Todo
from events import EventEmitter, TodosUpdatedEvent


class TodoToolInput(BaseModel):
    todos: list[Todo]


class TodoToolOutput(BaseModel):
    success: bool


class WriteTodosTool(Tool):
    def __init__(self, emitter: EventEmitter, app_state: AppState):
        self.app_state = app_state
        super().__init__(
            tool_name="write_todos",
            description="""
            A tool to manage a task todo list. Use this tool to keep track of multi-step tasks with complex substeps.
            When you complete a todo, also call this tool to mark it as completed.
            Each time you want to add to the list, update a todo, or clear the list, pass the entire desired list state into the tool.

            This tool is useful for maintain context on complex tasks with. Before you begin a task, plan out your todo substeps using this tool.
            """,
            input_schema=TodoToolInput,
            output_schema=TodoToolOutput,
            run=self._run_update_todos,
            emitter=emitter
        )

    def _run_update_todos(self, input: TodoToolInput) -> TodoToolOutput:
        self.app_state.todos = input.todos

        # Emit todos updated event
        self.emitter.emit(TodosUpdatedEvent(todos=input.todos))

        return TodoToolOutput(success=True)


def create_write_todos_tool(emitter: EventEmitter, app_state: AppState) -> WriteTodosTool:
    return WriteTodosTool(emitter=emitter, app_state=app_state)
