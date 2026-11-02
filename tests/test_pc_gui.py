"""Test del pannello con Tk vero: si saltano dove Tkinter o un display non sono disponibili."""

import os
import threading
import time

import pytest

tk = pytest.importorskip("tkinter")

import pc_controllo  # noqa: E402
from pc_controllo import ControlPanel  # noqa: E402


@pytest.fixture
def panel(tmp_path, monkeypatch):
    monkeypatch.setenv("GIOCO_PC_CONFIG", str(tmp_path / "config.json"))
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("nessun display per Tk")
    root.withdraw()
    widget = ControlPanel(root)
    yield widget
    if not widget._closing:
        widget.close()


def pump_until(panel, condition, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        panel.root.update()
        if condition():
            return True
        time.sleep(0.01)
    return False


def log_text(panel):
    return panel.log_text.get("1.0", "end")


def test_pump_survives_a_failing_callback(panel):
    seen = []

    def broken():
        raise KeyError("percent")

    panel.ui_call(broken)
    panel.ui_call(seen.append, "dopo")
    assert pump_until(panel, lambda: seen == ["dopo"])
    assert "errore interno: KeyError: 'percent'" in log_text(panel)


def test_tk_callback_exception_goes_to_log(panel):
    panel.root.after(0, lambda: 1 / 0)
    assert pump_until(panel, lambda: "errore nell'interfaccia: ZeroDivisionError" in log_text(panel))


def test_results_of_old_session_are_dropped(panel):
    seen = []
    release = threading.Event()
    panel.run_in_thread("prova", lambda: release.wait(5) or "vecchio", seen.append, session=panel._session)
    panel._session += 1
    release.set()
    pump_until(panel, lambda: False, timeout=0.5)
    assert seen == []


def test_errors_without_handler_are_logged(panel):
    panel.run_in_thread("foto", lambda: (_ for _ in ()).throw(pc_controllo.ApiError(409, "occupato", "in corso")))
    assert pump_until(panel, lambda: "foto: in corso (occupato, HTTP 409)" in log_text(panel))


def test_malformed_status_does_not_break_panel(panel):
    panel._apply_status({"mode": "video", "battery": {"charging": True}, "camera": {"rotation": "90", "torch": 1}})
    assert panel.status_vars["battery"].get() == "non disponibile"
    assert panel.video_button.cget("text") == "Ferma video"
    assert panel.rotation == 0


def test_malformed_file_list_is_skipped(panel):
    panel._show_files({"dir": "photos", "files": [{"name": "IMG_1.png", "size": 5, "modified": "ieri"}, {"size": 3}, 7]})
    items = panel.files_tree.get_children()
    assert [panel.files_tree.item(item, "text") for item in items] == ["IMG_1.png"]
