import os
from typing import Annotated, Literal, Union
from anthropic.types import ToolTextEditor20250728Param, ToolUnionParam
from pydantic import BaseModel, Field, RootModel
from settings import SETTINGS, Settings, EditMode
from tools import ToolResult
from tools.tool import Tool
    
class TextEditorViewCommand(BaseModel):
    command: Literal["view"]
    path: str

class TextEditorStrReplaceCommand(BaseModel):
    command: Literal["str_replace"]
    path: str
    old_str: str
    new_str: str

class TextEditorCreateCommand(BaseModel):
    command: Literal["create"]
    path: str
    file_text: str
    
class TextEditorInsertCommand(BaseModel):
    command: Literal["insert"]
    path: str
    insert_line: int
    new_str: str
    
TextEditorCommand = Annotated[
    Union[TextEditorViewCommand, TextEditorStrReplaceCommand, TextEditorCreateCommand, TextEditorInsertCommand],
    Field(discriminator="command")
]

class TextEditorInput(RootModel[TextEditorCommand]):
    root: TextEditorCommand

class TextEditorOutput(BaseModel):
    content: str

# https://platform.claude.com/docs/en/agents-and-tools/tool-use/text-editor-tool
class TextEditorTool(Tool):
    # max characters to display when viewing a file
    # if omitted, will display the full file
    max_characters: int | None
    settings: Settings
    
    def __init__(self, settings: Settings, max_characters: int | None = None):
        self.max_characters = max_characters
        self.settings = settings
        super().__init__(
            tool_name=self.to_anthropic_tool()["name"],
            description="Edit a file in the current directory. Call like so {{'path': 'path/to/file', 'content': 'content', 'overwrite': True}}",
            input_schema=TextEditorInput, # defined by anthropic api
            output_schema=TextEditorOutput,
            run=self._run_text_editor
        )
    
    def _run_text_editor(self, input: TextEditorInput) -> TextEditorOutput:
        cmd = input.root
        if cmd.command == "view":
            print(f"🛠️ 🔍 View file {cmd.path}")
            self._validate_file(cmd.path)
            with open(cmd.path, "r") as file:
                return TextEditorOutput(content=file.read())

        elif cmd.command == "str_replace":
            self._validate_file(cmd.path)
            # Read file to show preview before making changes
            with open(cmd.path, "r") as file:
                content = file.read()
            # Generate preview showing what will be replaced
            preview = self._generate_replace_preview(content, cmd.old_str, cmd.new_str)
            self._confirm_command(cmd.command, cmd.path, preview)
            self._run_replace(cmd)
            return TextEditorOutput(content=f"Replaced in {cmd.path}")
            
        elif cmd.command == "create":
            self._validate_file(cmd.path, should_exist=False)
            self._confirm_command(cmd.command, cmd.path, cmd.file_text)
            with open(cmd.path, "w") as file:
                file.write(cmd.file_text)
            return TextEditorOutput(content=f"File {cmd.path} created")
            
        elif cmd.command == "insert":
            self._validate_file(cmd.path)
            self._confirm_command(cmd.command, cmd.path, cmd.new_str)
            with open(cmd.path, "a") as file:
                # go to the line
                file.seek(cmd.insert_line)
                file.write(cmd.new_str)
            return TextEditorOutput(content=f"Line {cmd.insert_line} inserted")
        else:
            raise ValueError(f"Invalid command: {cmd.command}")
        
    def _generate_replace_preview(self, content: str, old_str: str, new_str: str) -> str:
        """Generate a diff-style preview showing what will be replaced."""
        # Check if the old_str exists and is unique
        count = content.count(old_str)
        if count > 1:
            return f"⚠️  WARNING: String appears {count} times in file (must be unique)"
        if count == 0:
            return f"⚠️  ERROR: String not found in file"
        
        # Find context around the match
        match_index = content.find(old_str)
        
        # Get surrounding lines for context
        lines_before = content[:match_index].splitlines()
        lines_after = content[match_index + len(old_str):].splitlines()
        
        # Show up to 3 lines of context before and after
        context_before = lines_before[-3:] if len(lines_before) > 3 else lines_before
        context_after = lines_after[:3] if len(lines_after) > 3 else lines_after
        
        # Build the preview
        preview_lines = []
        preview_lines.append("\n" + "="*60)
        preview_lines.append("📝 PREVIEW OF CHANGES:")
        preview_lines.append("="*60)
        
        # Add context before
        for line in context_before:
            preview_lines.append(f"  {line}")
        
        # Show what will be removed (in red/with -)
        old_lines = old_str.splitlines()
        for line in old_lines:
            preview_lines.append(f"- {line}")
        
        # Show what will be added (in green/with +)
        new_lines = new_str.splitlines()
        for line in new_lines:
            preview_lines.append(f"+ {line}")
        
        # Add context after
        for line in context_after:
            preview_lines.append(f"  {line}")
        
        preview_lines.append("="*60 + "\n")
        
        return "\n".join(preview_lines)
    
    def _run_replace(self, cmd: TextEditorStrReplaceCommand) -> bool:
        with open(cmd.path, "r") as file:
                content = file.read()
        count = content.count(cmd.old_str)
        if count > 1:
            raise ValueError(f"String '{cmd.old_str}' appears multiple times in {cmd.path}. Make it more specific.")
        if count == 0:
            raise ValueError(f"String '{cmd.old_str}' not found in {cmd.path}")
        new_content = content.replace(cmd.old_str, cmd.new_str, 1)
        with open(cmd.path, "w") as file:
            file.write(new_content)
        return True    

    def _validate_file(self, path: str, should_exist: bool = True) -> bool:
        from tools.utils import validate_path_within_project
        abs_path = validate_path_within_project(path)

        exists = os.path.exists(abs_path)
        if should_exist != exists:
            raise ValueError(f"File {abs_path} {'already exists' if exists else 'does not exist'}")
        return True
    
    def _confirm_command(self, command: str, path: str, contents: str):
        match self.settings.edit_mode:
            case EditMode.NEVER:
                raise ValueError(f"Command '{command}' on file '{path}' is disabled in settings")
            case EditMode.ALWAYS:
                return True
            case EditMode.ASK:
                pass
        print(f"🛠️ Confirming command '{command}' on file '{path}'\n{contents}...")
        answer = input(f"🛠️ Press Enter to continue or 'q' to skip > ")
        if answer.strip().lower() == "q":
            raise ValueError(f"🛠️ Command '{command}' on file '{path}' skipped")
        return True
    
    def to_anthropic_tool(self) -> ToolUnionParam:
        return ToolTextEditor20250728Param(
            name="str_replace_based_edit_tool",
            type="text_editor_20250728",
            max_characters=self.max_characters,
        )
        
    def execute(self, input: dict) -> ToolResult[TextEditorOutput]:
        try:
            input_model = self.input_schema.model_validate(input)
            result = self._run_text_editor(input_model)
            return ToolResult(data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
        
        
TEXT_EDITOR_TOOL = TextEditorTool(settings=SETTINGS)