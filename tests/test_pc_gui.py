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


def test_status_failures_change_indicator_and_log_once(panel):
    panel.client = pc_controllo.PhoneClient("127.0.0.1", 9, "t")
    error = pc_controllo.ApiError(0, "rete", "telefono non raggiungibile: timeout")
    for _ in range(4):
        panel._status_failed(error)
    assert panel.connection_state == "unreachable"
    text = log_text(panel)
    assert text.count("stato: telefono non raggiungibile") == 1
    assert text.count("Il telefono non risponde") == 1
    panel._apply_status({"mode": "idle"})
    assert panel.connection_state == "connected"
    assert "Telefono di nuovo raggiungibile." in log_text(panel)


def test_token_rejection_is_recognised(panel):
    panel.client = pc_controllo.PhoneClient("127.0.0.1", 9, "t")
    panel._status_failed(pc_controllo.ApiError(403, "token", "token mancante o errato"))
    panel._status_failed(pc_controllo.ApiError(403, "token", "token mancante o errato"))
    assert panel.connection_state == "rejected"
    assert log_text(panel).count("Token rifiutato") == 1


def test_command_button_disabled_while_running_and_by_mode(panel):
    release = threading.Event()
    panel.client = pc_controllo.PhoneClient("127.0.0.1", 9, "t")
    panel._refresh_command_buttons()
    assert panel.photo_button.instate(["!disabled"])
    panel._command("foto", lambda client: release.wait(5) or {"file": None}, lambda r: "fatto")
    assert panel.photo_button.instate(["disabled"])
    panel._command("foto", lambda client: {"file": None}, lambda r: "doppio")
    release.set()
    assert pump_until(panel, lambda: panel.photo_button.instate(["!disabled"]))
    assert "doppio" not in log_text(panel)
    panel.status = {"mode": "video"}
    panel._refresh_command_buttons()
    assert panel.audio_button.instate(["disabled"]) and panel.video_button.instate(["!disabled"])


def test_pasted_phone_url_fills_fields(panel):
    panel.host_var.set("http://192.168.1.23:8081/?t=Ab3_x9Qz")
    client = panel._read_fields()
    assert client.base == "http://192.168.1.23:8081"
    assert (panel.host_var.get(), panel.port_var.get(), panel.token_var.get()) == ("192.168.1.23", "8081", "Ab3_x9Qz")
