import os
from functools import lru_cache
from dataclasses import dataclass

MARKER_FILES = ['.git', 'pyproject.toml', 'setup.py', 'setup.cfg']

@lru_cache(maxsize=1)
def get_project_root() -> str:
    """Walk up from current file until we find a marker file."""
    current = os.path.dirname(os.path.abspath(__file__))
    while current != os.path.dirname(current):  # stop at filesystem root
        if any(os.path.exists(os.path.join(current, marker)) for marker in MARKER_FILES):
            return current
        current = os.path.dirname(current)
    raise RuntimeError("Could not find project root")


def is_path_within_project(path: str) -> bool:
    """Check if a path is within the project root."""
    abs_path = os.path.abspath(path)
    project_root = get_project_root()
    return abs_path.startswith(project_root + os.sep) or abs_path == project_root


def validate_path_within_project(path: str) -> str:
    """
    Validate that a path is within the project root.
    Returns the absolute path if valid, raises ValueError if not.
    """
    abs_path = os.path.abspath(path)
    if not is_path_within_project(abs_path):
        raise ValueError(f"Path {abs_path} is not within the project root {get_project_root()}")
    return abs_path


@dataclass
class FileViewResult:
    """Result of viewing a file with optional line range."""
    content: str
    total_lines: int
    start_line: int  # 1-indexed
    end_line: int    # 1-indexed, inclusive


def read_file_with_line_numbers(
    path: str,
    start_line: int | None = None,
    end_line: int | None = None,
    include_line_numbers: bool = True,
) -> FileViewResult:
    """
    Read a file and optionally format with line numbers.
    
    Args:
        path: Path to the file (should be validated before calling)
        start_line: 1-indexed line to start from (None = beginning)
        end_line: 1-indexed line to end at, inclusive. Use -1 for end of file. (None = end)
        include_line_numbers: Whether to prepend line numbers to each line
        
    Returns:
        FileViewResult with formatted content and metadata
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If line range is invalid
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"File {path} does not exist")
    
    if os.path.isdir(path):
        raise ValueError(f"Path {path} is a directory, not a file")
    
    with open(path, "r") as file:
        lines = file.readlines()
    
    total_lines = len(lines)
    
    # Handle end_line: -1 means end of file, None means end of file
    if end_line == -1 or end_line is None:
        actual_end_line = total_lines
    else:
        actual_end_line = end_line
    
    # Default start_line to 1 if not provided
    actual_start_line = start_line if start_line is not None else 1
    
    # Convert to 0-indexed for slicing
    start_idx = actual_start_line - 1
    end_idx = actual_end_line
    
    # Validate line range
    if start_idx < 0:
        raise ValueError(f"start_line must be >= 1, got {actual_start_line}")
    if start_idx >= total_lines and total_lines > 0:
        raise ValueError(f"start_line {actual_start_line} is beyond end of file ({total_lines} lines)")
    if end_idx > total_lines:
        end_idx = total_lines
        actual_end_line = total_lines
    if start_idx >= end_idx and total_lines > 0:
        raise ValueError(f"end_line ({actual_end_line}) must be >= start_line ({actual_start_line})")
    
    selected_lines = lines[start_idx:end_idx]
    
    if include_line_numbers:
        # Calculate padding based on the largest line number
        max_line_num = actual_end_line
        padding = len(str(max_line_num))
        
        # Format each line with its number
        numbered_lines = []
        for i, line in enumerate(selected_lines):
            line_num = actual_start_line + i
            # Remove trailing newline, add it back after formatting
            line_content = line.rstrip('\n')
            numbered_lines.append(f"{line_num:>{padding}}  {line_content}\n")
        
        content = "".join(numbered_lines)
    else:
        content = "".join(selected_lines)
    
    return FileViewResult(
        content=content,
        total_lines=total_lines,
        start_line=actual_start_line,
        end_line=actual_end_line,
    )
