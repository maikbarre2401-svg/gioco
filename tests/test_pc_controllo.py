import io
import threading
import time

import pytest

import pc_controllo
from main import CommandApi, CommandError, FrameBroker, MainThreadRunner, MjpegServer
from pc_controllo import ApiError, PhoneClient, as_int, describe_status, format_timestamp, human_size, iter_mjpeg

TOKEN = "Ab3_x9Qz"


class Controller:
    def __init__(self, media_dirs):
        self._media_dirs = media_dirs
        self.mode = "idle"
        self.torch_state = False
        self.calls = []

    def photo(self):
        self.calls.append("photo")
        return {"file": {"dir": "photos", "name": "IMG_1.png", "size": 4, "modified": 1}}

    def video_start(self):
        if self.mode != "idle":
            raise CommandError(409, "occupato", f"registrazione {self.mode} in corso")
        self.mode = "video"
        return {"mode": "video", "file": {"dir": "videos", "name": "VID_1.mp4", "size": 0, "modified": 1}}

    def video_stop(self):
        if self.mode != "video":
            raise CommandError(409, "non_attivo", "nessuna registrazione video in corso")
        self.mode = "idle"
        return {"mode": "idle", "saved": True, "seconds": 3.2, "file": {"dir": "videos", "name": "VID_1.mp4"}}

    def audio_start(self):
        self.mode = "audio"
        return {"mode": "audio", "file": {"dir": "audio", "name": "AUD_1.m4a", "size": 0, "modified": 1}}

    def audio_stop(self):
        self.mode = "idle"
        return {"mode": "idle", "saved": False, "seconds": 0.2, "file": None}

    def torch(self, on):
        self.torch_state = on
        return {"torch": on}

    def status(self):
        return {
            "platform": "android",
            "mode": self.mode,
            "recording_seconds": 65.4 if self.mode != "idle" else 0.0,
            "battery": {"percent": 81, "charging": True},
            "storage": {"free_bytes": 5 * 1024**3, "total_bytes": 64 * 1024**3},
            "camera": {
                "open": True,
                "has_frame": True,
                "preview_mode": "surface",
                "preview_size": [1920, 1080],
                "rotation": 90,
                "torch": self.torch_state,
            },
        }

    def media_dirs(self):
        return self._media_dirs


@pytest.fixture
def phone(tmp_path):
    dirs = {}
    for name in ("photos", "videos", "audio"):
        (tmp_path / name).mkdir()
        dirs[name] = str(tmp_path / name)
    (tmp_path / "photos" / "IMG_1.png").write_bytes(b"\x89PNG")
    (tmp_path / "videos" / "VID_1.mp4").write_bytes(bytes(range(256)) * 20_000)
    controller = Controller(dirs)
    broker = FrameBroker()
    api = CommandApi(controller, MainThreadRunner(schedule=lambda fn: fn(), timeout=2))
    server = MjpegServer(
        broker, lambda: {"rotation": 90, "width": 640, "height": 480}, ports=(0,), host="127.0.0.1", token=TOKEN, api=api
    )
    server.start()
    yield PhoneClient("127.0.0.1", server.port, TOKEN), controller, broker
    server.stop()


def test_iter_mjpeg_extracts_frames():
    payload = (
        b"--gioco-frame\r\nContent-Type: image/jpeg\r\nContent-Length: 3\r\n\r\nABC\r\n"
        b"--gioco-frame\r\nContent-Length: 2\r\nContent-Type: image/jpeg\r\n\r\nDE\r\n"
    )
    assert list(iter_mjpeg(io.BytesIO(payload))) == [b"ABC", b"DE"]


def test_iter_mjpeg_stops_on_truncated_frame():
    payload = b"--gioco-frame\r\nContent-Length: 10\r\n\r\nABC"
    assert list(iter_mjpeg(io.BytesIO(payload))) == []


def test_iter_mjpeg_rejects_missing_length():
    with pytest.raises(ValueError):
        list(iter_mjpeg(io.BytesIO(b"--gioco-frame\r\nContent-Type: image/jpeg\r\n\r\nABC\r\n")))


def test_iter_mjpeg_honours_stop():
    stop = threading.Event()
    stop.set()
    assert list(iter_mjpeg(io.BytesIO(b"--x\r\nContent-Length: 1\r\n\r\nA\r\n"), stop)) == []


def test_client_urls_carry_token():
    client = PhoneClient("192.168.1.23", 8080, "Ab3_x9Qz")
    assert client.page_url() == "http://192.168.1.23:8080/?t=Ab3_x9Qz"
    assert client.url("/files/get", path="videos/VID 1.mp4") == (
        "http://192.168.1.23:8080/files/get?t=Ab3_x9Qz&path=videos%2FVID+1.mp4"
    )


def test_client_commands_round_trip(phone):
    client, controller, _ = phone
    assert client.info()["rotation"] == 90
    assert client.photo()["file"]["name"] == "IMG_1.png"
    assert client.video(True)["mode"] == "video"
    assert client.status()["mode"] == "video"
    assert client.video(False)["saved"] is True
    assert client.audio(True)["mode"] == "audio"
    assert client.audio(False)["saved"] is False
    assert client.torch(True) == {"ok": True, "torch": True}
    assert client.torch(False) == {"ok": True, "torch": False}
    assert controller.calls == ["photo"]


def test_client_raises_api_error_with_server_code(phone):
    client, _, _ = phone
    with pytest.raises(ApiError) as info:
        client.video(False)
    assert (info.value.status, info.value.code) == (409, "non_attivo")
    assert str(info.value) == "nessuna registrazione video in corso (non_attivo, HTTP 409)"


def test_client_wrong_token_is_403(phone):
    client, _, _ = phone
    wrong = PhoneClient("127.0.0.1", int(client.base.rsplit(":", 1)[1]), "sbagliato")
    with pytest.raises(ApiError) as info:
        wrong.status()
    assert (info.value.status, info.value.code) == (403, "token")


def test_client_network_error_is_api_error():
    with pytest.raises(ApiError) as info:
        PhoneClient("127.0.0.1", 9, TOKEN).status()
    assert info.value.code == "rete"


def test_client_lists_and_downloads_files(phone, tmp_path):
    client, _, _ = phone
    listing = client.files("videos")
    assert [entry["name"] for entry in listing["files"]] == ["VID_1.mp4"]
    dest = tmp_path / "scaricato.mp4"
    seen = []
    size = client.download("videos", "VID_1.mp4", str(dest), progress=lambda done, total: seen.append((done, total)))
    assert size == 256 * 20_000
    assert dest.read_bytes() == bytes(range(256)) * 20_000
    assert seen and seen[-1][1] == 256 * 20_000
    assert not (tmp_path / "scaricato.mp4.part").exists()


def test_client_download_missing_file_leaves_nothing(phone, tmp_path):
    client, _, _ = phone
    dest = tmp_path / "manca.png"
    with pytest.raises(ApiError) as info:
        client.download("photos", "IMG_mai.png", str(dest))
    assert info.value.code == "file_non_trovato"
    assert not dest.exists()


def test_client_reads_stream_frames(phone):
    client, _, broker = phone
    publisher = threading.Timer(0.2, lambda: [broker.publish(b"jpeg-%d" % i) for i in range(1)])
    broker.publish(b"jpeg-0")
    response = client.open_stream()
    with response:
        frames = iter_mjpeg(response)
        assert next(frames) == b"jpeg-0"
        publisher.start()
        broker.publish(b"jpeg-1")
        assert next(frames) == b"jpeg-1"
    publisher.cancel()


def test_describe_status_texts(phone):
    client, controller, _ = phone
    controller.mode = "video"
    controller.torch_state = True
    texts = describe_status(client.status())
    assert texts == {
        "mode": "registra video",
        "recording": "video da 01:05",
        "battery": "81% in carica",
        "storage": "5.0 GB liberi su 64.0 GB",
        "camera": "aperta 1920x1080, surface, torcia accesa",
    }


def test_describe_status_without_android_data():
    texts = describe_status({"mode": "idle", "recording_seconds": 0, "battery": None, "storage": None, "camera": {}})
    assert texts["battery"] == "non disponibile"
    assert texts["storage"] == "non disponibile"
    assert texts["camera"] == "chiusa"
    assert texts["recording"] == "nessuna"


@pytest.mark.parametrize(("size", "text"), [(0, "0 B"), (900, "900 B"), (2048, "2.0 KB"), (5 * 1024**3, "5.0 GB")])
def test_human_size(size, text):
    assert human_size(size) == text


def test_module_imports_without_tk_requirements():
    assert pc_controllo.PhoneClient is PhoneClient
    assert pc_controllo.DEFAULT_PORT == 8080


def test_describe_status_tolerates_malformed_fields():
    texts = describe_status(
        {"mode": "audio", "recording_seconds": "x", "battery": {"charging": True}, "storage": {"free_bytes": 1},
         "camera": {"open": True, "preview_size": "1920x1080", "torch": False}}
    )
    assert texts["battery"] == "non disponibile"
    assert texts["storage"] == "non disponibile"
    assert texts["recording"] == "audio da 00:00"
    assert texts["camera"].startswith("aperta, ")


def test_describe_status_accepts_non_dict():
    assert describe_status(None)["mode"] == "?"


@pytest.mark.parametrize(("value", "expected"), [(5, 5), ("7", 7), (None, 0), ("x", 0), (True, 0), (3.9, 3)])
def test_as_int(value, expected):
    assert as_int(value) == expected


@pytest.mark.parametrize("value", [None, "ieri", 0, -5, True, 10**20])
def test_format_timestamp_invalid(value):
    assert format_timestamp(value) == "?"


def test_format_timestamp_valid():
    assert len(format_timestamp(1_700_000_000)) == len("2023-11-14 22:13")


# --- stream: geometria, decodifica e thread -------------------------------------------------------

from pc_controllo import FrameSink, StreamWorker, decode_frame, fit_size  # noqa: E402


def jpeg_bytes(size=(640, 480), color=(200, 30, 30)):
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, "JPEG", quality=80)
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("source", "box", "rotation", "expected"),
    [
        ((640, 480), (640, 480), 0, (640, 480)),
        ((1920, 1080), (960, 540), 0, (960, 540)),
        ((1920, 1080), (540, 960), 90, (960, 540)),
        ((640, 480), (1280, 960), 0, (1280, 960)),
        ((640, 480), (300, 1000), 270, (400, 300)),
        ((640, 480), (0, 100), 0, (640, 480)),
    ],
)
def test_fit_size(source, box, rotation, expected):
    assert fit_size(source, box, rotation) == expected


@pytest.mark.parametrize(("rotation", "expected"), [(0, (400, 300)), (90, (225, 300)), (180, (400, 300)), (270, (225, 300))])
def test_decode_frame_fits_box_after_rotation(rotation, expected):
    image = decode_frame(jpeg_bytes((1600, 1200)), rotation, (400, 300))
    assert image.size == expected
    assert image.mode == "RGB"


def test_decode_frame_rotates_clockwise():
    from PIL import Image

    source = Image.new("RGB", (64, 32), (0, 0, 0))
    source.paste((255, 255, 255), (0, 0, 32, 32))
    buffer = io.BytesIO()
    source.save(buffer, "JPEG", quality=95)
    rotated = decode_frame(buffer.getvalue(), 90, (32, 64))
    assert rotated.size == (32, 64)
    assert rotated.getpixel((16, 8))[0] > 200
    assert rotated.getpixel((16, 56))[0] < 50


def test_frame_sink_keeps_latest_and_counts():
    sink = FrameSink()
    sink.box = (320, 240)
    assert sink.push(jpeg_bytes(color=(10, 10, 10))) is None
    assert sink.push(jpeg_bytes(color=(250, 250, 250))) is None
    image = sink.take()
    assert image.getpixel((5, 5))[0] > 200
    assert sink.take() is None
    assert sink.take_count() == 2
    assert sink.take_count() == 0


def test_frame_sink_discards_corrupt_jpeg():
    sink = FrameSink()
    problem = sink.push(b"\xff\xd8 non e' un jpeg")
    assert problem is not None
    assert sink.bad_frames == 1
    assert sink.take() is None


class ClosableStream(io.BytesIO):
    pass


class FakeStreamClient:
    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.opened = 0

    def open_stream(self):
        self.opened += 1
        if not self.scripts:
            raise ApiError(0, "rete", "telefono non raggiungibile: spento")
        item = self.scripts.pop(0)
        if isinstance(item, Exception):
            raise item
        return ClosableStream(item)


def mjpeg(*frames):
    return b"".join(b"--gioco-frame\r\nContent-Length: %d\r\n\r\n%s\r\n" % (len(f), f) for f in frames)


def test_stream_worker_delivers_frames_and_logs_failures_once():
    client = FakeStreamClient([mjpeg(b"A", b"B"), ApiError(0, "rete", "giu"), mjpeg(b"C")])
    frames, events, states = [], [], []
    worker = StreamWorker(client, frames.append, events.append, states.append, retry_seconds=0.01, max_retry_seconds=0.02)
    worker.start()
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and client.opened < 6:
        time.sleep(0.01)
    worker.stop(wait=2)
    assert frames == [b"A", b"B", b"C"]
    assert events[0] == "Stream collegato"
    assert events[1] == "Stream chiuso dal telefono, riprovo"
    assert events[2].startswith("Stream interrotto: giu")
    assert events[3] == "Stream ripristinato"
    assert sum(1 for event in events if event.startswith("Stream interrotto")) == 2
    assert states[0] is True and states[-1] is False


def test_stream_worker_stop_is_prompt_while_waiting():
    client = FakeStreamClient([])
    worker = StreamWorker(client, lambda f: None, lambda e: None, retry_seconds=30)
    worker.start()
    time.sleep(0.1)
    started = time.monotonic()
    worker.stop(wait=2)
    assert time.monotonic() - started < 1
    assert worker.stopped


# --- indirizzi, letture ripetute e risposte non valide ---------------------------------------------

from pc_controllo import format_host, parse_phone_address, status_retry_delay_ms  # noqa: E402


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("192.168.1.23", ("192.168.1.23", None, None)),
        (" 192.168.1.23:8081 ", ("192.168.1.23", 8081, None)),
        ("http://192.168.1.23:8080/?t=Ab3_x9Qz", ("192.168.1.23", 8080, "Ab3_x9Qz")),
        ("http://10.0.0.5:8080/", ("10.0.0.5", 8080, None)),
        ("[fe80::1]:8080", ("fe80::1", 8080, None)),
        ("fe80::1", ("fe80::1", None, None)),
        ("http://[fe80::1]:8082/?t=xyz", ("fe80::1", 8082, "xyz")),
    ],
)
def test_parse_phone_address(text, expected):
    assert parse_phone_address(text) == expected


@pytest.mark.parametrize("text", ["", "   ", "192.168.1.23:porta", "http:///?t=x"])
def test_parse_phone_address_rejects(text):
    with pytest.raises(ValueError):
        parse_phone_address(text)


def test_format_host_and_ipv6_client_url():
    assert format_host("192.168.1.23") == "192.168.1.23"
    assert format_host("fe80::1") == "[fe80::1]"
    assert PhoneClient("fe80::1", 8080, "t").page_url() == "http://[fe80::1]:8080/?t=t"


@pytest.mark.parametrize(("failures", "delay"), [(0, 2000), (1, 2000), (2, 4000), (3, 8000), (4, 15000), (10, 15000)])
def test_status_retry_delay(failures, delay):
    assert status_retry_delay_ms(failures) == delay


class FakeResponse(io.BytesIO):
    status = 200


def test_reads_retry_network_errors_but_commands_do_not(monkeypatch):
    sleeps = []
    client = PhoneClient("127.0.0.1", 9, TOKEN, sleep=sleeps.append)
    attempts = {"count": 0}

    def flaky_open(request, timeout):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise ApiError(0, "rete", "telefono non raggiungibile: timeout")
        return FakeResponse(b'{"ok": true, "dir": "photos", "files": []}')

    monkeypatch.setattr(client, "_open", flaky_open)
    assert client.files("photos")["dir"] == "photos"
    assert attempts["count"] == 2 and sleeps == [0.5]

    attempts["count"] = 0
    with pytest.raises(ApiError):
        client.photo()
    assert attempts["count"] == 1


def test_non_json_answer_is_clear_error(monkeypatch):
    client = PhoneClient("127.0.0.1", 9, TOKEN)
    monkeypatch.setattr(client, "_open", lambda request, timeout: FakeResponse(b"<html>captive portal</html>"))
    with pytest.raises(ApiError) as info:
        client.status()
    assert info.value.code == "risposta"
    monkeypatch.setattr(client, "_open", lambda request, timeout: FakeResponse(b"[1, 2]"))
    with pytest.raises(ApiError, match="JSON inatteso"):
        client.status()


# --- download: file parziali, più file insieme, avanzamento, istantanea ----------------------------

from pc_controllo import (  # noqa: E402
    DownloadBatch,
    DownloadItem,
    ProgressThrottle,
    unique_path,
    write_bytes_atomic,
)


def test_unique_path_never_overwrites(tmp_path):
    (tmp_path / "VID.mp4").write_bytes(b"x")
    (tmp_path / "VID (2).mp4").write_bytes(b"x")
    taken = {str(tmp_path / "VID (3).mp4")}
    assert unique_path(str(tmp_path), "VID.mp4", taken) == str(tmp_path / "VID (4).mp4")
    assert unique_path(str(tmp_path), "nuovo.png") == str(tmp_path / "nuovo.png")
    assert unique_path(str(tmp_path), "../fuori.png") == str(tmp_path / "fuori.png")


def test_write_bytes_atomic(tmp_path):
    target = tmp_path / "istantanea.jpg"
    write_bytes_atomic(str(target), b"jpeg")
    assert target.read_bytes() == b"jpeg"
    assert not (tmp_path / "istantanea.jpg.part").exists()


def test_progress_throttle_limits_rate_but_keeps_final():
    now = {"t": 0.0}
    seen = []
    report = ProgressThrottle(lambda done, total: seen.append(done), clock=lambda: now["t"])
    for step in range(10):
        now["t"] = step * 0.03
        report(step, 10)
    report(10, 10, final=True)
    assert seen == [0, 4, 8, 10]


def test_download_cancelled_leaves_no_partial_file(phone, tmp_path):
    client, _, _ = phone
    cancel = threading.Event()
    cancel.set()
    dest = tmp_path / "video.mp4"
    with pytest.raises(ApiError) as info:
        client.download("videos", "VID_1.mp4", str(dest), cancel=cancel)
    assert info.value.code == "annullato"
    assert not dest.exists() and not (tmp_path / "video.mp4.part").exists()


def test_download_reports_final_progress(phone, tmp_path):
    client, _, _ = phone
    seen = []
    client.download("photos", "IMG_1.png", str(tmp_path / "foto.png"), progress=lambda d, t: seen.append((d, t)))
    assert seen[-1] == (4, 4)


def test_download_batch_continues_after_a_failure(phone, tmp_path):
    client, _, _ = phone
    items = [
        DownloadItem("photos", "IMG_1.png", str(tmp_path / "a.png"), 4),
        DownloadItem("photos", "IMG_mai.png", str(tmp_path / "b.png"), 10),
        DownloadItem("videos", "VID_1.mp4", str(tmp_path / "c.mp4"), 256 * 20_000),
    ]
    progress, logs = [], []
    report = DownloadBatch(client, items, lambda *args: progress.append(args), logs.append).run()
    assert [item.name for item in report.completed] == ["IMG_1.png", "VID_1.mp4"]
    assert [item.name for item, _ in report.failed] == ["IMG_mai.png"]
    assert not report.cancelled
    assert (tmp_path / "c.mp4").stat().st_size == 256 * 20_000
    dones = [entry[0] for entry in progress]
    assert dones == sorted(dones)
    assert progress[-1][2:] == ("VID_1.mp4", 2, 3)
    assert any("IMG_mai.png" in line for line in logs)


def test_download_batch_cancel_stops_before_next_file(phone, tmp_path):
    client, _, _ = phone
    items = [DownloadItem("photos", "IMG_1.png", str(tmp_path / f"{i}.png"), 4) for i in range(3)]
    batch = DownloadBatch(client, items, lambda *args: batch.cancel(), lambda line: None)
    report = batch.run()
    assert report.cancelled
    assert len(report.completed) <= 1


def test_snapshot(phone):
    client, _, broker = phone
    with pytest.raises(ApiError) as info:
        client.snapshot()
    assert info.value.status == 503
    broker.publish(b"\xff\xd8jpeg\xff\xd9")
    assert client.snapshot() == b"\xff\xd8jpeg\xff\xd9"
