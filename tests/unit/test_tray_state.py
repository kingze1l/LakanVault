# tray state machine no real pystray gui
from __future__ import annotations

from lakanvault.tray.state import TrayController, TrayStatus


def test_initial_status_is_stopped() -> None:
    ctl = TrayController(host="127.0.0.1", port=8080)
    assert ctl.status == TrayStatus.STOPPED
    assert ctl.dashboard_url == "http://127.0.0.1:8080/status"
    assert ctl.review_url == "http://127.0.0.1:8080/review"


def test_start_sets_running_when_ready() -> None:
    started: list[bool] = []

    def start() -> bool:
        started.append(True)
        return True

    ctl = TrayController(host="127.0.0.1", port=8080)
    assert ctl.start_gateway(start) is True
    assert started == [True]
    assert ctl.status == TrayStatus.RUNNING


def test_start_sets_error_when_ready_fails() -> None:
    ctl = TrayController(host="127.0.0.1", port=8080)
    assert ctl.start_gateway(lambda: False) is False
    assert ctl.status == TrayStatus.ERROR


def test_stop_returns_to_stopped() -> None:
    stopped: list[bool] = []
    ctl = TrayController(host="127.0.0.1", port=8080)
    ctl.start_gateway(lambda: True)
    ctl.stop_gateway(lambda: stopped.append(True) or True)
    assert stopped == [True]
    assert ctl.status == TrayStatus.STOPPED


def test_set_status_warning_and_error() -> None:
    ctl = TrayController(host="127.0.0.1", port=9090)
    ctl.set_status(TrayStatus.WARNING)
    assert ctl.status == TrayStatus.WARNING
    ctl.set_status(TrayStatus.ERROR)
    assert ctl.status == TrayStatus.ERROR
    assert ctl.dashboard_url == "http://127.0.0.1:9090/status"


def test_open_dashboard_and_review_call_opener() -> None:
    opened: list[str] = []
    ctl = TrayController(host="127.0.0.1", port=8080)
    ctl.open_dashboard(lambda url: opened.append(url))
    ctl.open_review(lambda url: opened.append(url))
    assert opened == [
        "http://127.0.0.1:8080/status",
        "http://127.0.0.1:8080/review",
    ]


def test_status_color_map() -> None:
    assert TrayStatus.RUNNING.color_rgb == (0, 180, 80)
    assert TrayStatus.WARNING.color_rgb == (220, 160, 40)
    assert TrayStatus.ERROR.color_rgb == (220, 60, 60)
    assert TrayStatus.STOPPED.color_rgb == (120, 120, 120)
    assert TrayStatus.STARTING.color_rgb == (120, 120, 120)


def test_poll_advances_last_event_id() -> None:
    ctl = TrayController(host="127.0.0.1", port=8080)
    calls: list[str] = []

    def fake_fetch(url: str) -> dict:
        calls.append(url)
        if "recent" in url:
            return {
                "events": [
                    {
                        "id": 3,
                        "ts": 1.0,
                        "action": "mask",
                        "source": "review",
                        "entity_types": ["EMAIL_ADDRESS"],
                    },
                    {
                        "id": 4,
                        "ts": 2.0,
                        "action": "block",
                        "source": "proxy",
                        "entity_types": ["SECRET"],
                    },
                ]
            }
        return {"paused": False, "blocked": 1, "warned": 0, "masked": 1, "activity": []}

    events = ctl.poll_protect_events(fetch_json=fake_fetch)
    assert len(events) == 2
    assert ctl.last_event_id == 4
    assert ctl.paused is False
    assert any("since_id=0" in u for u in calls)


def test_notify_for_events_skips_when_paused() -> None:
    ctl = TrayController()
    ctl.start_gateway(lambda: True)
    ctl._paused = True  # noqa: SLF001 — test pause gate
    notes: list[tuple[str, str]] = []
    out = ctl.notify_for_events(
        [{"id": 1, "action": "block", "source": "review", "entity_types": ["X"]}],
        lambda title, body: notes.append((title, body)),
    )
    assert out == []
    assert notes == []


def test_notify_block_events_are_returned_for_toast() -> None:
    ctl = TrayController()
    ctl.start_gateway(lambda: True)
    notes: list[tuple[str, str]] = []
    out = ctl.notify_for_events(
        [
            {"id": 1, "action": "warn", "source": "review", "entity_types": ["X"]},
            {"id": 2, "action": "block", "source": "proxy", "entity_types": ["SECRET"]},
        ],
        lambda title, body: notes.append((title, body)),
    )
    assert [e["action"] for e in out] == ["warn", "block"]
    assert any(e["action"] == "block" for e in out)


def test_notify_for_events_updates_status() -> None:
    ctl = TrayController()
    ctl.start_gateway(lambda: True)
    notes: list[tuple[str, str]] = []
    out = ctl.notify_for_events(
        [
            {
                "id": 1,
                "action": "mask",
                "source": "review",
                "entity_types": ["EMAIL_ADDRESS"],
            }
        ],
        lambda title, body: notes.append((title, body)),
    )
    assert len(out) == 1
    assert notes[0][0] == "LakanVault — MASK"
    assert ctl.status == TrayStatus.WARNING

    ctl.notify_for_events(
        [{"id": 2, "action": "block", "source": "proxy", "entity_types": ["SECRET"]}],
        lambda title, body: notes.append((title, body)),
    )
    assert ctl.status == TrayStatus.ERROR
