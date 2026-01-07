from pydantic import BaseModel, Field
from app_state import AppState
from tools.tool import Tool
from todo import Todo, TodoStatus
from events import EventEmitter, TodosUpdatedEvent


class EditTodoInput(BaseModel):
    index: int = Field(description="The index of the todo to edit (0-based)")
    title: str | None = Field(default=None, description="New title for the todo (optional)")
    description: str | None = Field(default=None, description="New description for the todo (optional)")
    status: TodoStatus | None = Field(default=None, description="New status for the todo (optional)")


class EditTodoOutput(BaseModel):
    success: bool
    message: str
    edited_todo: Todo | None = None


class EditTodoTool(Tool):
    """A fake todo editing tool that edits a single todo by index."""

    def __init__(self, emitter: EventEmitter, app_state: AppState):
        self.app_state = app_state
        super().__init__(
            tool_name="edit_todo",
            description="""
            Edit a single todo item by its index. This is a convenient way to update
            individual todos without having to rewrite the entire list.

            You can update any combination of title, description, and status.
            Only the fields you provide will be updated; others remain unchanged.

            This is a "fake" edit in that it simulates granular editing while
            actually updating the underlying todo list.
            """,
            input_schema=EditTodoInput,
            output_schema=EditTodoOutput,
            run=self._run_edit_todo,
            emitter=emitter
        )

    def _run_edit_todo(self, input: EditTodoInput) -> EditTodoOutput:
        # Check if index is valid
        if input.index < 0 or input.index >= len(self.app_state.todos):
            return EditTodoOutput(
                success=False,
                message=f"Invalid index {input.index}. Valid range is 0-{len(self.app_state.todos) - 1}" if self.app_state.todos else "No todos exist to edit",
                edited_todo=None
            )

        # Get the existing todo
        existing_todo = self.app_state.todos[input.index]

        # Create updated todo with new values (or keep existing)
        updated_todo = Todo(
            title=input.title if input.title is not None else existing_todo.title,
            description=input.description if input.description is not None else existing_todo.description,
            status=input.status if input.status is not None else existing_todo.status
        )

        # Update the todo in the list
        self.app_state.todos[input.index] = updated_todo

        # Emit todos updated event
        self.emitter.emit(TodosUpdatedEvent(todos=self.app_state.todos))

        return EditTodoOutput(
            success=True,
            message=f"Successfully edited todo at index {input.index}",
            edited_todo=updated_todo
        )


def create_edit_todo_tool(emitter: EventEmitter, app_state: AppState) -> EditTodoTool:
    return EditTodoTool(emitter=emitter, app_state=app_state)
