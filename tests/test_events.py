from dataclasses import dataclass

import pytest

from toy_agent.events import (
    BashConfirmationResult,
    EventEmitter,
    MenuConfirmationResult,
    MenuOption,
    ToolStartedEvent,
)


@dataclass
class RecordingHandler:
    seen: list

    def handle(self, event) -> None:
        self.seen.append(event)


class StubConfirmationHandler:
    def request_confirmation(self, tool_name: str, action: str, path: str | None, preview: str):
        return (False, f"Denied {tool_name}")


class StubBashConfirmationHandler:
    def request_bash_confirmation(self, command: str, preview: str) -> BashConfirmationResult:
        return BashConfirmationResult(approved=False, deny_reason="Not allowed")


class StubMenuConfirmationHandler:
    def request_menu_confirmation(
        self,
        title: str,
        preview: str,
        options: list[MenuOption],
    ) -> MenuConfirmationResult:
        return MenuConfirmationResult(selected_value="deny", approved=False, deny_reason="No")


class StubInputHandler:
    def request_input(self, prompt: str) -> str:
        return "user input"


def test_emit_sends_events_to_registered_handlers() -> None:
    emitter = EventEmitter()
    seen: list[ToolStartedEvent] = []
    handler = RecordingHandler(seen=seen)
    emitter.add_handler(handler)

    event = ToolStartedEvent(tool_name="grep", input={"pattern": "foo"})
    emitter.emit(event)

    assert seen == [event]


def test_default_confirmation_behaviors_when_handlers_missing() -> None:
    emitter = EventEmitter()

    assert emitter.request_confirmation("edit", "write", None, "preview") == (True, None)
    assert emitter.request_bash_confirmation("ls", "preview") == BashConfirmationResult(
        approved=True
    )

    menu_result = emitter.request_menu_confirmation(
        "choose",
        "preview",
        [MenuOption(label="Allow", description="desc", value="allow")],
    )
    assert menu_result == MenuConfirmationResult(selected_value="allow", approved=True)


def test_custom_handlers_are_used() -> None:
    emitter = EventEmitter()
    emitter.set_confirmation_handler(StubConfirmationHandler())
    emitter.set_bash_confirmation_handler(StubBashConfirmationHandler())
    emitter.set_menu_confirmation_handler(StubMenuConfirmationHandler())
    emitter.set_input_handler(StubInputHandler())

    assert emitter.request_confirmation("bash", "run", None, "cmd") == (False, "Denied bash")
    assert emitter.request_bash_confirmation("rm -rf", "preview") == BashConfirmationResult(
        approved=False,
        deny_reason="Not allowed",
    )
    assert emitter.request_menu_confirmation("title", "preview", []) == MenuConfirmationResult(
        selected_value="deny",
        approved=False,
        deny_reason="No",
    )
    assert emitter.request_input("> ") == "user input"


def test_request_input_raises_without_handler() -> None:
    emitter = EventEmitter()

    with pytest.raises(RuntimeError, match="No input handler registered"):
        emitter.request_input("> ")
