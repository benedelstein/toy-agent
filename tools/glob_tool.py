import glob as glob_module
import os
from pydantic import BaseModel, Field
from tools.tool import Tool
from events import EventEmitter


class GlobInput(BaseModel):
    pattern: str = Field(description="Glob pattern to match files (e.g., '*.py', '**/*.txt', 'src/**/*.js')")
    recursive: bool = Field(default=False, description="Whether to use recursive globbing (allows ** pattern)")


class GlobOutput(BaseModel):
    matches: list[str] = Field(description="List of file paths matching the pattern")
    count: int = Field(description="Number of matches found")


def run_glob(input: GlobInput) -> GlobOutput:
    """
    Find files matching a glob pattern.
    Supports standard glob patterns:
    - * matches any characters within a filename
    - ? matches a single character
    - [seq] matches any character in seq
    - ** matches directories recursively (when recursive=True)
    """
    from tools.utils import get_project_root, is_path_within_project

    # Change to project root for consistent behavior
    project_root = get_project_root()
    original_dir = os.getcwd()

    try:
        os.chdir(project_root)

        # Use glob with recursive option
        if input.recursive:
            matches = glob_module.glob(input.pattern, recursive=True)
        else:
            matches = glob_module.glob(input.pattern)

        # Convert to absolute paths and filter to only those within project
        absolute_matches = []
        for match in matches:
            abs_path = os.path.abspath(match)
            if is_path_within_project(abs_path):
                # Return relative paths for cleaner output
                rel_path = os.path.relpath(abs_path, project_root)
                absolute_matches.append(rel_path)

        # Sort for consistent output
        absolute_matches.sort()

        return GlobOutput(matches=absolute_matches, count=len(absolute_matches))
    finally:
        os.chdir(original_dir)


def create_glob_tool(emitter: EventEmitter) -> Tool:
    return Tool(
        tool_name="glob",
        description="Find files matching a glob pattern. Use '*' for any characters, '?' for single character, '**' for recursive directory matching (set recursive=True). Example: {'pattern': '*.py'} or {'pattern': 'src/**/*.js', 'recursive': True}",
        input_schema=GlobInput,
        output_schema=GlobOutput,
        run=run_glob,
        emitter=emitter
    )
