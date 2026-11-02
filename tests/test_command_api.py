import http.client
import json
import os
import threading
import time

import pytest

from main import (
    MAX_BODY_BYTES,
    CommandApi,
    CommandError,
    FrameBroker,
    MainThreadRunner,
    MjpegServer,
    is_api_path,
    parse_torch_body,
)

TOKEN = "Ab3_x9Qz"


class FakeController:
    """Registra chiamate e thread; i metodi restituiscono payload come AppController."""

    def __init__(self, media_dirs=None):
        self.calls = []
        self.threads = []
        self._media_dirs = media_dirs or {}
        self.fail_with = None

    def _record(self, name, payload):
        self.calls.append(name)
        self.threads.append(threading.current_thread())
        if self.fail_with is not None:
            raise self.fail_with
        return payload

    def photo(self):
        return self._record("photo", {"file": {"dir": "photos", "name": "IMG_1.png", "size": 10, "modified": 1}})

    def video_start(self):
        return self._record("video_start", {"mode": "video", "file": {"dir": "videos", "name": "VID_1.mp4"}})

    def video_stop(self):
        return self._record("video_stop", {"mode": "idle", "saved": True, "seconds": 2.0, "file": None})

    def audio_start(self):
        return self._record("audio_start", {"mode": "audio", "file": {"dir": "audio", "name": "AUD_1.m4a"}})

    def audio_stop(self):
        return self._record("audio_stop", {"mode": "idle", "saved": False, "seconds": 0.1, "file": None})

    def torch(self, on):
        return self._record(f"torch_{'on' if on else 'off'}", {"torch": on})

    def status(self):
        return self._record("status", {"mode": "idle", "recording_seconds": 0.0})

    def media_dirs(self):
        self.calls.append("media_dirs")
        return self._media_dirs


def immediate_runner():
    return MainThreadRunner(schedule=lambda fn: fn(), timeout=2)


@pytest.fixture
def media(tmp_path):
    dirs = {}
    for name in ("photos", "videos", "audio"):
        folder = tmp_path / name
        folder.mkdir()
        dirs[name] = str(folder)
    (tmp_path / "photos" / "IMG_old.png").write_bytes(b"old")
    os.utime(tmp_path / "photos" / "IMG_old.png", (1_000, 1_000))
    (tmp_path / "photos" / "IMG_new.png").write_bytes(b"\x89PNG-new")
    os.utime(tmp_path / "photos" / "IMG_new.png", (2_000, 2_000))
    (tmp_path / "photos" / ".nascosto").write_bytes(b"x")
    (tmp_path / "videos" / "VID_1.mp4").write_bytes(b"mp4" * 100_000)
    (tmp_path / "segreto.txt").write_bytes(b"fuori")
    return dirs


@pytest.fixture
def api_server(media):
    controller = FakeController(media)
    api = CommandApi(controller, immediate_runner())
    server = MjpegServer(FrameBroker(), dict, ports=(0,), host="127.0.0.1", token=TOKEN, api=api)
    server.start()
    yield controller, server
    server.stop()


def request(port, method, path, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request(method, path, body=body, headers=headers or {})
    response = conn.getresponse()
    data = response.read()
    conn.close()
    return response, data


def post_json(port, path, body=b""):
    response, data = request(port, "POST", path, body=body)
    assert response.getheader("Content-Type") == "application/json; charset=utf-8"
    return response.status, json.loads(data)


@pytest.mark.parametrize(
    ("path", "call"),
    [
        ("/cmd/photo", "photo"),
        ("/cmd/video/start", "video_start"),
        ("/cmd/video/stop", "video_stop"),
        ("/cmd/audio/start", "audio_start"),
        ("/cmd/audio/stop", "audio_stop"),
        ("/status", "status"),
    ],
)
def test_commands_route_to_controller(api_server, path, call):
    controller, server = api_server
    status, payload = post_json(server.port, f"{path}?t={TOKEN}")
    assert status == 200
    assert payload["ok"] is True
    assert controller.calls == [call]


@pytest.mark.parametrize(("body", "call", "torch"), [(b"on", "torch_on", True), (b" OFF\n", "torch_off", False)])
def test_torch_reads_body(api_server, body, call, torch):
    controller, server = api_server
    status, payload = post_json(server.port, f"/cmd/torch?t={TOKEN}", body)
    assert (status, payload) == (200, {"ok": True, "torch": torch})
    assert controller.calls == [call]


def test_torch_rejects_other_bodies(api_server):
    controller, server = api_server
    status, payload = post_json(server.port, f"/cmd/torch?t={TOKEN}", b"accesa")
    assert status == 400
    assert payload == {"ok": False, "error": "richiesta", "message": "corpo atteso: on oppure off"}
    assert controller.calls == []


@pytest.mark.parametrize("query", ["", "?t=", "?t=sbagliato"])
def test_post_without_token_is_403_json(api_server, query):
    controller, server = api_server
    status, payload = post_json(server.port, f"/cmd/photo{query}")
    assert status == 403
    assert payload == {"ok": False, "error": "token", "message": "token mancante o errato"}
    assert controller.calls == []


@pytest.mark.parametrize("path", ["/cmd/photo", "/status", "/files", "/files/get", "/cmd/qualsiasi"])
def test_get_on_api_paths_is_405(api_server, path):
    controller, server = api_server
    response, data = request(server.port, "GET", f"{path}?t={TOKEN}")
    assert response.status == 405
    assert response.getheader("Allow") == "POST"
    assert json.loads(data) == {"ok": False, "error": "metodo", "message": "usa POST"}
    assert controller.calls == []


def test_get_without_token_on_api_path_stays_403_text(api_server):
    _, server = api_server
    response, data = request(server.port, "GET", "/status")
    assert (response.status, data) == (403, b"token mancante o errato\n")


def test_unknown_post_is_404(api_server):
    _, server = api_server
    status, payload = post_json(server.port, f"/cmd/zoom?t={TOKEN}")
    assert status == 404
    assert payload["error"] == "sconosciuto"


def test_post_body_too_large_is_413(api_server):
    controller, server = api_server
    status, payload = post_json(server.port, f"/cmd/torch?t={TOKEN}", b"x" * (MAX_BODY_BYTES + 1))
    assert status == 413
    assert payload["error"] == "troppo_grande"
    assert controller.calls == []


def test_post_with_bad_content_length_is_400(api_server):
    _, server = api_server
    response, data = request(server.port, "POST", f"/cmd/photo?t={TOKEN}", headers={"Content-Length": "dieci"})
    assert response.status == 400
    assert json.loads(data)["error"] == "richiesta"


def test_controller_errors_become_json(api_server):
    controller, server = api_server
    controller.fail_with = CommandError(409, "occupato", "registrazione audio in corso")
    status, payload = post_json(server.port, f"/cmd/video/start?t={TOKEN}")
    assert (status, payload) == (409, {"ok": False, "error": "occupato", "message": "registrazione audio in corso"})


def test_unexpected_errors_become_500(api_server):
    controller, server = api_server
    controller.fail_with = RuntimeError("guasto")
    status, payload = post_json(server.port, f"/cmd/photo?t={TOKEN}")
    assert (status, payload) == (500, {"ok": False, "error": "errore", "message": "RuntimeError: guasto"})


def test_no_api_configured_is_503():
    server = MjpegServer(FrameBroker(), dict, ports=(0,), host="127.0.0.1", token=TOKEN)
    server.start()
    try:
        status, payload = post_json(server.port, f"/cmd/photo?t={TOKEN}")
    finally:
        server.stop()
    assert status == 503
    assert payload["error"] == "non_disponibile"


def test_files_lists_newest_first_without_hidden(api_server):
    controller, server = api_server
    status, payload = post_json(server.port, f"/files?t={TOKEN}&dir=photos")
    assert status == 200
    assert payload == {
        "ok": True,
        "dir": "photos",
        "files": [
            {"name": "IMG_new.png", "size": 8, "modified": 2000},
            {"name": "IMG_old.png", "size": 3, "modified": 1000},
        ],
    }
    assert controller.calls == ["media_dirs"]


@pytest.mark.parametrize("query", ["", "&dir=", "&dir=../", "&dir=Pictures"])
def test_files_rejects_unknown_dir(api_server, query):
    _, server = api_server
    status, payload = post_json(server.port, f"/files?t={TOKEN}{query}")
    assert status == 400
    assert payload["error"] == "richiesta"


def test_files_without_media_dirs_is_503():
    api = CommandApi(FakeController({}), immediate_runner())
    server = MjpegServer(FrameBroker(), dict, ports=(0,), host="127.0.0.1", token=TOKEN, api=api)
    server.start()
    try:
        status, payload = post_json(server.port, f"/files?t={TOKEN}&dir=photos")
    finally:
        server.stop()
    assert status == 503
    assert payload["error"] == "non_disponibile"


def test_files_get_downloads_bytes(api_server):
    _, server = api_server
    response, data = request(server.port, "POST", f"/files/get?t={TOKEN}&path=videos/VID_1.mp4")
    assert response.status == 200
    assert response.getheader("Content-Type") == "video/mp4"
    assert response.getheader("Content-Length") == str(300_000)
    assert response.getheader("Content-Disposition") == 'attachment; filename="VID_1.mp4"'
    assert data == b"mp4" * 100_000


@pytest.mark.parametrize(
    "path",
    ["photos/../segreto.txt", "../segreto.txt", "photos/.nascosto", "photos/", "photos", "photos/a/b", "foto/IMG_new.png"],
)
def test_files_get_rejects_paths_outside_media(api_server, path):
    _, server = api_server
    status, payload = post_json(server.port, f"/files/get?t={TOKEN}&path={path}")
    assert status == 400
    assert payload["error"] == "richiesta"


def test_files_get_missing_file_is_404(api_server):
    _, server = api_server
    status, payload = post_json(server.port, f"/files/get?t={TOKEN}&path=photos/IMG_mai.png")
    assert status == 404
    assert payload["error"] == "file_non_trovato"


def test_files_get_rejects_symlink_escape(api_server, media, tmp_path):
    _, server = api_server
    os.symlink(tmp_path / "segreto.txt", os.path.join(media["photos"], "link.png"))
    status, payload = post_json(server.port, f"/files/get?t={TOKEN}&path=photos/link.png")
    assert status == 400


@pytest.mark.parametrize(
    "path", ["/cmd/photo", "/cmd/video/start", "/status", "/files", "/files/get"]
)
def test_is_api_path(path):
    assert is_api_path(path)


@pytest.mark.parametrize("path", ["/", "/index.html", "/stream.mjpg", "/snapshot.jpg", "/info.json", "/statusx"])
def test_is_not_api_path(path):
    assert not is_api_path(path)


def test_parse_torch_body_values():
    assert parse_torch_body(b"on") is True
    assert parse_torch_body(b"Off ") is False
    with pytest.raises(CommandError):
        parse_torch_body(b"")


def tick_until(done, timeout=5.0):
    from kivy.clock import Clock

    deadline = time.monotonic() + timeout
    while not done() and time.monotonic() < deadline:
        Clock.tick()


def test_runner_executes_on_kivy_thread_and_returns_result():
    runner = MainThreadRunner(timeout=5)
    result = {}

    def from_server_thread():
        result["value"] = runner.call(lambda: threading.current_thread())

    worker = threading.Thread(target=from_server_thread)
    worker.start()
    tick_until(lambda: "value" in result)
    worker.join(5)
    assert result["value"] is threading.main_thread()


def test_runner_reraises_errors_in_caller():
    runner = MainThreadRunner(timeout=5)
    result = {}

    def from_server_thread():
        try:
            runner.call(lambda: (_ for _ in ()).throw(CommandError(409, "occupato", "x")))
        except CommandError as exc:
            result["error"] = exc.code

    worker = threading.Thread(target=from_server_thread)
    worker.start()
    tick_until(lambda: "error" in result)
    worker.join(5)
    assert result["error"] == "occupato"


def test_runner_timeout_cancels_command_not_yet_started():
    from kivy.clock import Clock

    ran = []
    runner = MainThreadRunner(timeout=0.2)
    with pytest.raises(CommandError) as info:
        runner.call(lambda: ran.append(True))
    assert info.value.status == 504
    assert "annullato" in info.value.message
    for _ in range(5):
        Clock.tick()
    assert ran == []


def test_runner_reports_unknown_outcome_when_command_runs_too_long():
    started = threading.Event()
    release = threading.Event()

    def schedule(fn):
        threading.Thread(target=fn, daemon=True).start()

    def slow():
        started.set()
        release.wait(5)
        return {}

    runner = MainThreadRunner(schedule=schedule, timeout=0.2)
    try:
        with pytest.raises(CommandError) as info:
            runner.call(slow)
    finally:
        release.set()
    assert started.is_set()
    assert "esito sconosciuto" in info.value.message


def test_http_command_runs_on_kivy_thread_not_server_thread(media):
    controller = FakeController(media)
    api = CommandApi(controller, MainThreadRunner(timeout=5))
    server = MjpegServer(FrameBroker(), dict, ports=(0,), host="127.0.0.1", token=TOKEN, api=api)
    server.start()
    result = {}

    def client():
        result["response"] = post_json(server.port, f"/cmd/photo?t={TOKEN}")

    worker = threading.Thread(target=client)
    try:
        worker.start()
        tick_until(lambda: "response" in result)
        worker.join(5)
    finally:
        server.stop()
    assert result["response"][0] == 200
    assert controller.threads == [threading.main_thread()]


def test_http_files_do_not_wait_for_kivy_thread(media):
    controller = FakeController(media)
    never = MainThreadRunner(schedule=lambda fn: None, timeout=0.2)
    api = CommandApi(controller, never)
    server = MjpegServer(FrameBroker(), dict, ports=(0,), host="127.0.0.1", token=TOKEN, api=api)
    server.start()
    try:
        status, payload = post_json(server.port, f"/files?t={TOKEN}&dir=videos")
        timeout_status, timeout_payload = post_json(server.port, f"/status?t={TOKEN}")
    finally:
        server.stop()
    assert status == 200
    assert payload["files"][0]["name"] == "VID_1.mp4"
    assert timeout_status == 504
    assert timeout_payload["error"] == "timeout"


def test_existing_get_endpoints_unchanged_with_api(api_server):
    _, server = api_server
    response, body = request(server.port, "GET", f"/?t={TOKEN}")
    assert response.status == 200
    assert b"/stream.mjpg" in body
    response, body = request(server.port, "GET", f"/info.json?t={TOKEN}")
    assert response.status == 200
