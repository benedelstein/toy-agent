from toy_agent import app_state as app_state_module
from toy_agent.app_state import AppState


def test_add_file_event_deduplicates_by_path(monkeypatch) -> None:
    monkeypatch.setattr(app_state_module, "time", lambda: 100.0)
    app_state = AppState()

    app_state.add_file_event("modified", "src/file.py")

    monkeypatch.setattr(app_state_module, "time", lambda: 200.0)
    app_state.add_file_event("created", "src/file.py")

    assert len(app_state.file_events) == 1
    assert app_state.file_events[0].event_type == "created"
    assert app_state.file_events[0].file_path == "src/file.py"
    assert app_state.file_events[0].timestamp == 200.0


def test_get_and_clear_recent_events_respects_ttl(monkeypatch) -> None:
    timestamps = iter([100.0, 10.0, 105.0])
    monkeypatch.setattr(app_state_module, "time", lambda: next(timestamps))

    app_state = AppState()
    app_state.add_file_event("modified", "src/recent.py")
    app_state.add_file_event("modified", "src/stale.py")

    recent = app_state.get_and_clear_recent_events(ttl_seconds=15.0)

    assert len(recent) == 1
    assert recent[0].file_path == "src/recent.py"
    assert app_state.file_events == []
