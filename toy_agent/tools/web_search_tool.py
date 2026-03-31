import html
import re
import urllib.error
import urllib.parse
import urllib.request

from pydantic import BaseModel, Field

from ..events import EventEmitter
from .tool import Tool


class WebSearchInput(BaseModel):
    query: str = Field(description="The search query to look up on the web")
    max_results: int = Field(default=10, description="Maximum number of results to return")


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str


class WebSearchOutput(BaseModel):
    results: list[SearchResult]
    query: str


def _strip_html_tags(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return text.strip()


def _extract_url_from_ddg_link(href: str) -> str:
    """Extract the actual URL from a DuckDuckGo redirect link."""
    match = re.search(r"uddg=([^&]+)", href)
    if match:
        return urllib.parse.unquote(match.group(1))
    return href


def _parse_lite_results(html_content: str, max_results: int) -> list[SearchResult]:
    """Parse search results from DuckDuckGo lite HTML page."""
    results: list[SearchResult] = []

    # DuckDuckGo lite returns results in a table-based layout
    # Result links have class="result-link"
    link_pattern = re.compile(
        r'<a[^>]+class="result-link"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL
    )
    # Snippets are in <td> elements with class="result-snippet"
    snippet_pattern = re.compile(
        r'<td[^>]+class="result-snippet"[^>]*>(.*?)</td>', re.DOTALL
    )

    links = link_pattern.findall(html_content)
    snippets = snippet_pattern.findall(html_content)

    for i, (href, title_html) in enumerate(links):
        if i >= max_results:
            break

        title = _strip_html_tags(title_html)
        url = _extract_url_from_ddg_link(href)
        snippet = _strip_html_tags(snippets[i]) if i < len(snippets) else ""

        if title and url:
            results.append(SearchResult(title=title, url=url, snippet=snippet))

    return results


def run_web_search(input: WebSearchInput) -> WebSearchOutput:
    """Search the web using DuckDuckGo lite (no API key required)."""
    encoded_query = urllib.parse.quote_plus(input.query)
    url = f"https://lite.duckduckgo.com/lite/?q={encoded_query}"

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; ToyAgent/1.0)",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            html_content = response.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Web search failed: {e}") from e

    results = _parse_lite_results(html_content, input.max_results)

    return WebSearchOutput(results=results, query=input.query)


def create_web_search_tool(emitter: EventEmitter) -> Tool[WebSearchInput, WebSearchOutput]:
    return Tool(
        tool_name="web_search",
        description="Search the web for information. Returns a list of results with titles, URLs, and snippets. Use this when you need to find up-to-date information from the internet.",
        input_schema=WebSearchInput,
        output_schema=WebSearchOutput,
        run=run_web_search,
        emitter=emitter,
    )
