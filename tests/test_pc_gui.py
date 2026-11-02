"""Test del pannello con Tk vero: si saltano dove Tkinter o un display non sono disponibili."""

import gc
import os
import threading
import time

import pytest

tk = pytest.importorskip("tkinter")

import pc_controllo  # noqa: E402
from pc_controllo import ControlPanel  # noqa: E402


@pytest.fixture(autouse=True)
def collect_tk_objects_on_main_thread():
    # Le variabili Tk di una finestra chiusa vanno liberate dal thread principale: se il garbage collector
    # le raccoglie in un thread di rete, Tcl si interrompe (limite di Tkinter, non del pannello).
    yield
    gc.collect()


@pytest.fixture
def panel(tmp_path, monkeypatch):
    monkeypatch.setenv("GIOCO_PC_CONFIG", str(tmp_path / "config.json"))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
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


class FakeDownloadClient:
    base = "http://127.0.0.1:9"

    def __init__(self, fail=()):
        self.fail = set(fail)

    def download(self, dirname, name, dest, progress=None, cancel=None):
        if name in self.fail:
            raise pc_controllo.ApiError(404, "file_non_trovato", f"{dirname}/{name} non esiste")
        with open(dest, "wb") as handle:
            handle.write(b"x" * 10)
        if progress is not None:
            progress(10, 10)
        return 10


def test_multi_download_uses_unique_names_and_reports(panel, tmp_path, monkeypatch):
    (tmp_path / "IMG_1.png").write_bytes(b"gia presente")
    panel.client = FakeDownloadClient(fail={"IMG_3.png"})
    panel._set_connected(True)
    panel._show_files({"dir": "photos", "files": [{"name": n, "size": 10} for n in ("IMG_1.png", "IMG_2.png", "IMG_3.png")]})
    panel.files_tree.selection_set(panel.files_tree.get_children())
    monkeypatch.setattr(pc_controllo.filedialog, "askdirectory", lambda **kwargs: str(tmp_path))
    panel.download_selected()
    assert pump_until(panel, lambda: panel._download_batch is None and "Download finito" in log_text(panel))
    assert (tmp_path / "IMG_1.png").read_bytes() == b"gia presente"
    assert (tmp_path / "IMG_1 (2).png").read_bytes() == b"x" * 10
    assert (tmp_path / "IMG_2.png").exists() and not (tmp_path / "IMG_3.png").exists()
    assert panel.transfer_var.get() == "2 scaricati, 1 non riusciti"
    assert panel.download_dir == str(tmp_path)


def test_single_download_asks_file_name(panel, tmp_path, monkeypatch):
    panel.client = FakeDownloadClient()
    panel._set_connected(True)
    panel._show_files({"dir": "photos", "files": [{"name": "IMG_1.png", "size": 10}]})
    panel.files_tree.selection_set(panel.files_tree.get_children())
    target = tmp_path / "scelto.png"
    monkeypatch.setattr(pc_controllo.filedialog, "asksaveasfilename", lambda **kwargs: str(target))
    panel.download_selected()
    assert pump_until(panel, lambda: target.exists() and panel._download_batch is None)
    assert panel.transfer_var.get() == "1 scaricati"


def test_settings_persist_between_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("GIOCO_PC_CONFIG", str(tmp_path / "config.json"))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("nessun display per Tk")
    root.withdraw()
    first = ControlPanel(root)
    first.host_var.set("192.168.1.23")
    first.port_var.set("8081")
    first.token_var.set("Ab3_x9Qz")
    first.repo_var.set("io/altro")
    first.github_token_var.set("segreto")
    first._remember_current_connection()
    first.close()
    del first
    gc.collect()
    saved = (tmp_path / "config.json").read_text()
    assert "segreto" not in saved

    root = tk.Tk()
    root.withdraw()
    second = ControlPanel(root)
    try:
        assert (second.host_var.get(), second.port_var.get(), second.token_var.get()) == ("192.168.1.23", "8081", "Ab3_x9Qz")
        assert second.repo_var.get() == "io/altro"
        assert list(second.host_box.cget("values")) == ["192.168.1.23:8081"]
        second.host_var.set("")
        second.host_box.current(0)
        second._on_history_selected()
        assert (second.host_var.get(), second.port_var.get()) == ("192.168.1.23", "8081")
        second.remember_github_token_var.set(True)
        second.github_token_var.set("segreto")
    finally:
        second.close()
    del second
    gc.collect()
    root = tk.Tk()
    root.withdraw()
    third = ControlPanel(root)
    try:
        assert third.github_token_var.get() == "segreto"
    finally:
        third.close()


class FakeEvent:
    def __init__(self, widget, state=0):
        self.widget = widget
        self.state = state


def entries(widget):
    for child in widget.winfo_children():
        if isinstance(child, pc_controllo.ttk.Entry):
            yield child
        yield from entries(child)


def test_every_shortcut_is_bound(panel):
    for shortcut in pc_controllo.SHORTCUTS.values():
        for sequence in pc_controllo.shortcut_sequences(shortcut):
            assert panel.root.bind(sequence), sequence


def test_shortcut_sequences_cover_caps_lock():
    assert pc_controllo.shortcut_sequences(pc_controllo.Shortcut("Control-f", "Ctrl+F")) == ["<Control-f>", "<Control-F>"]
    assert pc_controllo.shortcut_sequences(pc_controllo.Shortcut("F5", "F5")) == ["<F5>"]
    assert pc_controllo.shortcut_sequences(pc_controllo.Shortcut("Escape", "Esc")) == ["<Escape>"]


def test_editing_shortcuts_do_not_fire_while_typing(panel):
    calls = []
    token_entry = next(entry for entry in entries(panel.root) if str(entry.cget("textvariable")) == str(panel.token_var))
    unsafe = panel._shortcut_handler(pc_controllo.SHORTCUTS["photo"], lambda: calls.append("foto"))
    safe = panel._shortcut_handler(pc_controllo.SHORTCUTS["save_settings"], lambda: calls.append("salva"))
    assert unsafe(FakeEvent(token_entry)) is None
    assert safe(FakeEvent(token_entry)) == "break"
    assert unsafe(FakeEvent(panel.files_tree)) == "break"
    assert unsafe(FakeEvent(panel.dir_box)) == "break"
    assert unsafe(FakeEvent(panel.log_text)) == "break"
    assert calls == ["salva", "foto", "foto", "foto"]


def test_shortcut_ignores_disabled_command(panel):
    seen = []
    panel.client = pc_controllo.PhoneClient("127.0.0.1", 9, "t")
    panel._refresh_command_buttons()
    panel.photo_button.configure(command=lambda: seen.append("foto"))
    panel._busy_commands.add("foto")
    panel._refresh_command_buttons()
    panel._shortcut_actions()["photo"]()
    assert seen == []
    panel._busy_commands.clear()
    panel._refresh_command_buttons()
    panel._shortcut_actions()["photo"]()
    assert seen == ["foto"]


def test_ctrl_return_in_field_is_left_to_shortcut(panel, monkeypatch):
    calls = []
    monkeypatch.setattr(panel, "toggle_connection", lambda: calls.append("connetti"))
    panel._on_field_return(FakeEvent(panel.host_box, state=0x4))
    assert calls == []
    panel._on_field_return(FakeEvent(panel.host_box))
    assert calls == ["connetti"]


def test_escape_cancels_download_first_and_asks_before_stopping_deploy(panel, monkeypatch):
    asked = []
    monkeypatch.setattr(pc_controllo.messagebox, "askyesno", lambda *args, **kwargs: asked.append(args) or False)
    batch = pc_controllo.DownloadBatch(FakeDownloadClient(), [], lambda *args: None, lambda text: None)
    panel._download_batch = batch
    panel._runner = pc_controllo.ProcessRunner()
    panel.cancel_current()
    assert batch.cancelled and asked == [] and not panel._runner.cancelled
    panel._download_batch = None
    panel.cancel_current()
    assert len(asked) == 1 and not panel._runner.cancelled
    monkeypatch.setattr(pc_controllo.messagebox, "askyesno", lambda *args, **kwargs: True)
    panel.cancel_current()
    assert panel._runner.cancelled
    panel._runner = None


def test_menu_mirrors_buttons(panel):
    panel.client = pc_controllo.PhoneClient("127.0.0.1", 9, "t")
    panel._set_connected(True)
    panel.status = {"mode": "video"}
    panel._refresh_command_buttons()
    panel.video_button.configure(text="Ferma video")
    phone = panel.menubar.nametowidget(panel.menubar.entrycget(1, "menu"))
    # Il postcommand è ciò che Tk esegue appena prima di aprire il menu.
    panel.root.tk.call(phone.cget("postcommand"))
    labels = {
        phone.entrycget(i, "label"): str(phone.entrycget(i, "state"))
        for i in range(phone.index("end") + 1)
        if phone.type(i) == "command"
    }
    assert labels["Ferma video"] == "normal"
    assert labels["Avvia audio"] == "disabled"
    assert labels["Disconnetti"] == "normal"


def test_log_can_be_cleared_and_exported(panel, tmp_path, monkeypatch):
    panel.log("riga da esportare")
    target = tmp_path / "log.txt"
    monkeypatch.setattr(pc_controllo.filedialog, "asksaveasfilename", lambda **kwargs: str(target))
    panel.export_log()
    assert "riga da esportare" in target.read_text(encoding="utf-8")
    panel.clear_log()
    assert log_text(panel).strip() == ""


def test_about_lists_versions_and_settings_path(panel):
    text = panel.about_text()
    assert pc_controllo.__version__ in text
    assert panel.settings_store.path in text
    assert "Python" in text and "Tk" in text


def test_close_leaves_no_pending_after_jobs(panel):
    panel._schedule_status(60000)
    panel.close()
    assert panel.root.tk.call("after", "info") in ("", ())
