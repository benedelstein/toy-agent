import os
from typing import Annotated, Literal, Union

from anthropic.types import ToolTextEditor20250728Param, ToolUnionParam
from pydantic import BaseModel, Field, RootModel

from ..events import (
    EventEmitter,
    FileViewedEvent,
    ToolCompletedEvent,
    ToolErrorEvent,
    ToolStartedEvent,
)
from ..settings import EditMode, Settings
from . import ToolResult
from .tool import Tool
from .utils import read_file_with_line_numbers, validate_path_within_project


class TextEditorViewCommand(BaseModel):
    command: Literal["view"]
    path: str
    # 1-indexed line range to view. if secondvalue is -1, view to the end of the file
    view_range: tuple[int, int] | None = None


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
    insert_text: str


TextEditorCommand = Annotated[
    Union[
        TextEditorViewCommand,
        TextEditorStrReplaceCommand,
        TextEditorCreateCommand,
        TextEditorInsertCommand,
    ],
    Field(discriminator="command"),
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

    def __init__(
        self, emitter: EventEmitter, settings: Settings, max_characters: int | None = None
    ):
        self.max_characters = max_characters
        self.settings = settings
        super().__init__(
            tool_name="str_replace_based_edit_tool",
            description="Edit a file in the current directory. Call like so {{'path': 'path/to/file', 'content': 'content', 'overwrite': True}}",
            input_schema=TextEditorInput,  # defined by anthropic api
            output_schema=TextEditorOutput,
            run=self._run_text_editor,
            emitter=emitter,
        )

    def _run_text_editor(self, input: TextEditorInput) -> TextEditorOutput:
        cmd = input.root
        if cmd.command == "view":
            self.emitter.emit(FileViewedEvent(path=cmd.path))
            self._validate_path(cmd.path)

            # Check if it's a directory
            if os.path.isdir(cmd.path):
                return TextEditorOutput(content=self._list_directory(cmd.path))

            # Parse view_range if specified
            start_line = None
            end_line = None
            if cmd.view_range is not None:
                start_line, end_line = cmd.view_range

            result = read_file_with_line_numbers(
                path=cmd.path,
                start_line=start_line,
                end_line=end_line,
                include_line_numbers=False,
            )
            return TextEditorOutput(content=result.content)

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
            self._confirm_command(cmd.command, cmd.path, cmd.insert_text)
            with open(cmd.path, "a") as file:
                # go to the line
                file.seek(cmd.insert_line)
                file.write(cmd.insert_text)
            return TextEditorOutput(content=f"Line {cmd.insert_line} inserted")
        else:
            raise ValueError(f"Invalid command: {cmd.command}")

    def _generate_replace_preview(self, content: str, old_str: str, new_str: str) -> str:
        """Generate a diff-style preview showing what will be replaced."""
        # Check if the old_str exists and is unique
        count = content.count(old_str)
        if count > 1:
            return f"WARNING: String appears {count} times in file (must be unique)"
        if count == 0:
            return "ERROR: String not found in file"

        # Find context around the match
        match_index = content.find(old_str)

        # Get surrounding lines for context
        lines_before = content[:match_index].splitlines()
        lines_after = content[match_index + len(old_str) :].splitlines()

        # Show up to 3 lines of context before and after
        context_before = lines_before[-3:] if len(lines_before) > 3 else lines_before
        context_after = lines_after[:3] if len(lines_after) > 3 else lines_after

        # Build the preview
        preview_lines = []
        preview_lines.append("\n" + "=" * 60)
        preview_lines.append("PREVIEW OF CHANGES:")
        preview_lines.append("=" * 60)

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

        preview_lines.append("=" * 60 + "\n")

        return "\n".join(preview_lines)

    def _run_replace(self, cmd: TextEditorStrReplaceCommand) -> bool:
        with open(cmd.path, "r") as file:
            content = file.read()
        count = content.count(cmd.old_str)
        if count > 1:
            raise ValueError(
                f"String '{cmd.old_str}' appears multiple times in {cmd.path}. Make it more specific."
            )
        if count == 0:
            raise ValueError(f"String '{cmd.old_str}' not found in {cmd.path}")
        new_content = content.replace(cmd.old_str, cmd.new_str, 1)
        with open(cmd.path, "w") as file:
            file.write(new_content)
        return True

    def _validate_path(self, path: str, should_exist: bool = True) -> bool:
        """Validate a path (file or directory) exists and is within project."""
        abs_path = validate_path_within_project(path)

        exists = os.path.exists(abs_path)
        if should_exist != exists:
            raise ValueError(f"Path {abs_path} {'already exists' if exists else 'does not exist'}")
        return True

    def _validate_file(self, path: str, should_exist: bool = True) -> bool:
        """Validate a file exists and is within project."""
        abs_path = validate_path_within_project(path)

        exists = os.path.exists(abs_path)
        if should_exist != exists:
            raise ValueError(f"File {abs_path} {'already exists' if exists else 'does not exist'}")
        return True

    def _list_directory(self, path: str, max_depth: int = 2) -> str:
        """List files and directories up to max_depth levels deep, ignoring hidden items and node_modules."""
        abs_path = validate_path_within_project(path)

        IGNORED_NAMES = {"node_modules", "__pycache__", ".git", ".venv", "venv", ".env"}

        lines = []

        def walk_directory(current_path: str, prefix: str = "", depth: int = 0):
            if depth > max_depth:
                return

            try:
                entries = sorted(os.listdir(current_path))
            except PermissionError:
                return

            # Filter out hidden files and ignored directories
            entries = [e for e in entries if not e.startswith(".") and e not in IGNORED_NAMES]

            dirs = []
            files = []
            for entry in entries:
                full_path = os.path.join(current_path, entry)
                if os.path.isdir(full_path):
                    dirs.append(entry)
                else:
                    files.append(entry)

            # List directories first, then files
            all_entries = [(d, True) for d in dirs] + [(f, False) for f in files]

            for i, (entry, is_dir) in enumerate(all_entries):
                is_last = i == len(all_entries) - 1
                connector = "└── " if is_last else "├── "

                if is_dir:
                    lines.append(f"{prefix}{connector}{entry}/")
                    # Recurse into directory
                    extension = "    " if is_last else "│   "
                    walk_directory(os.path.join(current_path, entry), prefix + extension, depth + 1)
                else:
                    lines.append(f"{prefix}{connector}{entry}")

        # Add the root directory name
        dir_name = os.path.basename(abs_path) or abs_path
        lines.append(f"{dir_name}/")
        walk_directory(abs_path)

        return "\n".join(lines)

    def _confirm_command(self, command: str, path: str, contents: str):
        match self.settings.edit_mode:
            case EditMode.NEVER:
                raise ValueError(f"Command '{command}' on file '{path}' is disabled in settings")
            case EditMode.ALWAYS:
                return True
            case EditMode.ASK:
                pass

        # Use emitter for confirmation
        approved, reason = self.emitter.request_confirmation(
            tool_name="str_replace_based_edit_tool", action=command, path=path, preview=contents
        )
        if not approved:
            raise ValueError(
                f"Command '{command}' on file '{path}' skipped - user-provided reason: {reason or 'no reason given'}"
            )
        return True

    def to_anthropic_tool(self) -> ToolUnionParam:
        return ToolTextEditor20250728Param(
            name="str_replace_based_edit_tool",
            type="text_editor_20250728",
            max_characters=self.max_characters,
        )

    def execute(self, input: dict) -> ToolResult[TextEditorOutput]:
        self.emitter.emit(ToolStartedEvent(tool_name=self.tool_name, input=input))

        try:
            input_model = self.input_schema.model_validate(input)
            result = self._run_text_editor(input_model)

            self.emitter.emit(
                ToolCompletedEvent(
                    tool_name=self.tool_name, output=result.model_dump() if result else None
                )
            )
            return ToolResult(data=result)
        except Exception as e:
            self.emitter.emit(ToolErrorEvent(tool_name=input["command"], error=str(e)))
            return ToolResult(success=False, error=str(e))


def create_text_editor_tool(emitter: EventEmitter, settings: Settings) -> TextEditorTool:
    return TextEditorTool(emitter=emitter, settings=settings)
