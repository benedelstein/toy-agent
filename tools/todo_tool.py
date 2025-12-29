from pydantic import BaseModel
from app_state import AppState
from tools.tool import Tool
from todo import Todo, TodoStatus

class TodoToolInput(BaseModel):
    todos: list[Todo]

class TodoToolOutput(BaseModel):
    success: bool
    
def update_todos(app_state: AppState, todos: list[Todo]) -> TodoToolOutput:
    app_state.todos = todos
    print("--------------------------------")
    print("Todos:")
    for todo in todos:
        print(f"[{todo.status == TodoStatus.COMPLETED and '✔' or ' '}]: {todo.title}")
    print("--------------------------------")
    return TodoToolOutput(success=True)
    
def create_write_todos_tool(app_state: AppState) -> Tool:
    return Tool(
        tool_name="write_todos",
        description="""
        A tool to manage a task todo list. Use this tool to keep track of multi-step tasks with complex substeps.
        When you complete a todo, also call this tool to mark it as completed.
        Each time you want to add to the list, update a todo, or clear the list, pass the entire desired list state into the tool.
        
        This tool is useful for maintain context on complex tasks with. Before you begin a task, plan out your todo substeps using this tool.
        """,
        input_schema=TodoToolInput,
        output_schema=TodoToolOutput,
        run=lambda input: update_todos(app_state, input.todos)
    )
