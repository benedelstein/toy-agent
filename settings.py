from enum import Enum

class EditMode(Enum):
    ASK = "ask"
    ALWAYS = "always"
    NEVER = "never"

class Settings:
    edit_mode: EditMode = EditMode.ASK

SETTINGS = Settings()
