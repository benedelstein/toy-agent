from pydantic import BaseModel, Field
from enum import Enum

class TodoStatus(Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

class Todo(BaseModel):
    title: str
    description: str
    status: TodoStatus = Field(default=TodoStatus.TODO, description="The status of the todo. Mark the todo as 'completed' when it is done.")