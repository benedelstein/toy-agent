from events import (
    Event,
    EventHandler,
    ConfirmationHandler,
    ToolStartedEvent,
    ToolCompletedEvent,
    ToolErrorEvent,
    AssistantMessageEvent,
    FileViewedEvent,
    WebSearchErrorEvent,
    UnknownContentEvent,
    FinalOutputEvent,
    TodosUpdatedEvent,
)


class CLIEventHandler(EventHandler):
    """Default CLI event handler that prints formatted output"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def handle(self, event: Event) -> None:
        # Pattern match on strongly typed events - type checker validates field access
        match event:
            case AssistantMessageEvent(text=text):
                print(f"💬 {text}")

            case ToolErrorEvent(tool_name=name, error=err):
                print(f"🛠️ Tool {name} error: {err}")

            case FileViewedEvent(path=path):
                print(f"🔍 View file: {path}")

            case WebSearchErrorEvent(error_code=code):
                print(f"web search error: {code}")

            case UnknownContentEvent(content_type=ct):
                print(f"unknown content type: {ct}")

            case FinalOutputEvent(result=result):
                print(f"💡 {result}")

            case TodosUpdatedEvent(todos=todos):
                print("--------------------------------")
                print("Todos:")
                for todo in todos:
                    status_mark = "✔" if todo.status.value == "completed" else " "
                    print(f"[{status_mark}]: {todo.title}")
                print("--------------------------------")

            case ToolStartedEvent(tool_name=name):
                if self.verbose:
                    print(f"🛠️ Starting {name}...")

            case ToolCompletedEvent(tool_name=name):
                if self.verbose:
                    print(f"✅ {name} completed")


class CLIConfirmationHandler(ConfirmationHandler):
    """CLI confirmation handler using input()"""

    def request_confirmation(
        self, tool_name: str, action: str, path: str | None, preview: str
    ) -> tuple[bool, str | None]:
        """Prompt user for confirmation via CLI"""

        # Display the preview
        if path:
            print(f"🛠️ Confirming command '{action}' on file '{path}'")
        else:
            print(f"🛠️ Confirming: {action}")
        print(preview)

        # Get user input
        answer = input("🛠️ Press Enter to continue or 'q [reason]' to skip > ")

        if answer.strip().lower().startswith("q"):
            reason = answer.strip()[1:].strip() or "no reason given"
            return (False, reason)

        return (True, None)
