from typing import Literal, TypedDict


class ToolSearchToolParam(TypedDict):
    """TypedDict for tool search tool parameters"""
    type: Literal["tool_search_tool_regex_20251115", "tool_search_tool_bm25_20251119"]
    name: str
    max_results: int


class ToolSearchTool:
    """Tool search tool for enabling Claude to search available tools.

    This is a server-side tool that requires the 'advanced-tool-use-2025-11-20' beta header.
    """

    def __init__(self, variant: Literal["regex", "bm25"] = "regex", max_results: int = 10):
        """Initialize tool search tool.

        Args:
            variant: Either "regex" or "bm25" to specify the search algorithm
            max_results: Maximum number of search results to return (default 10)
        """
        self.variant = variant
        self.max_results = max_results

        # Set the tool type based on variant
        if variant == "regex":
            self.tool_type: Literal["tool_search_tool_regex_20251115", "tool_search_tool_bm25_20251119"] = "tool_search_tool_regex_20251115"
            self.tool_name = "tool_search_tool_regex"
        elif variant == "bm25":
            self.tool_type = "tool_search_tool_bm25_20251119"
            self.tool_name = "tool_search_tool_bm25"
        else:
            raise ValueError(f"Invalid variant: {variant}. Must be 'regex' or 'bm25'")

    def to_anthropic_tool(self) -> ToolSearchToolParam:
        """Convert to Anthropic tool parameter format.

        Returns:
            TypedDict with type, name, and max_results fields
        """
        return ToolSearchToolParam(
            type=self.tool_type,
            name=self.tool_name,
            max_results=self.max_results,
        )


def create_tool_search_regex_tool(max_results: int = 10) -> ToolSearchTool:
    """Create a tool search tool using regex variant.

    Args:
        max_results: Maximum number of search results to return (default 10)

    Returns:
        ToolSearchTool configured for regex search
    """
    return ToolSearchTool(variant="regex", max_results=max_results)


def create_tool_search_bm25_tool(max_results: int = 10) -> ToolSearchTool:
    """Create a tool search tool using BM25 variant.

    Args:
        max_results: Maximum number of search results to return (default 10)

    Returns:
        ToolSearchTool configured for BM25 search
    """
    return ToolSearchTool(variant="bm25", max_results=max_results)
