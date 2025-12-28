import os
from functools import lru_cache

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
