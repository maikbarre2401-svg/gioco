import ctypes
import hmac
import ipaddress
import json
import logging
import os
import secrets
import shutil
import socket
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlsplit

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.graphics import BindTexture, Callback, Color, Ellipse, Fbo, Line, Rectangle, RoundedRectangle
from kivy.graphics.opengl import (
    glActiveTexture,
    glBindTexture,
    glCompileShader,
    glCreateShader,
    glDeleteShader,
    glDeleteTextures,
    glGenTextures,
    glGetShaderInfoLog,
    glGetShaderiv,
    glGetString,
    glShaderSource,
)
from kivy.graphics.texture import Texture
from kivy.graphics.transformation import Matrix
from kivy.logger import Logger
from kivy.metrics import dp
from kivy.properties import BooleanProperty
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.utils import platform


# Diagnostica della pipeline: una riga su logcat con tag GIOCO per ogni stadio, solo con DEBUG = True.

DEBUG = True

TAG = "GIOCO"
# logcat tronca le righe oltre ~4 KB; meglio tagliare noi e lasciare spazio a tag e intestazione.
MAX_MESSAGE_BYTES = 3500

ANDROID_LOG_INFO = 4
ANDROID_LOG_ERROR = 6

STAGE_DEBUG = "debug"
STAGE_CAMERA_OPEN = "fotocamera"
STAGE_PREVIEW_SIZE = "dimensioni"
STAGE_ROTATION = "rotazione"
STAGE_TEXTURE = "texture"
STAGE_SHADER = "shader"
STAGE_FIRST_FRAME = "primo_fotogramma"
STAGE_CALLBACK = "callback"
STAGE_FRAMES = "fotogrammi"
STAGE_ENCODER = "encoder"
STAGE_CLIENTS = "client"

STAGES = (
    STAGE_DEBUG,
    STAGE_CAMERA_OPEN,
    STAGE_PREVIEW_SIZE,
    STAGE_ROTATION,
    STAGE_TEXTURE,
    STAGE_SHADER,
    STAGE_FIRST_FRAME,
    STAGE_CALLBACK,
    STAGE_FRAMES,
    STAGE_ENCODER,
    STAGE_CLIENTS,
)

_STARTED_AT = time.monotonic()
_lock = threading.Lock()
_last_state: dict[str, tuple[bool, str]] = {}
_write = None
_output = "non ancora scelto"


def _android_writer():
    # ctypes su liblog invece di android.util.Log via pyjnius: un thread che tocca la JVM deve fare detach
    # prima di uscire, e i thread del server HTTP non lo fanno.
    try:
        liblog = ctypes.CDLL("liblog.so")
    except OSError:
        return None
    log_write = liblog["__android_log_write"]
    log_write.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p)
    log_write.restype = ctypes.c_int
    tag = TAG.encode("ascii")

    def write(priority: int, message: str) -> None:
        log_write(priority, tag, encode_message(message))

    return write


def _stderr_writer(priority: int, message: str) -> None:
    level = "E" if priority >= ANDROID_LOG_ERROR else "I"
    print(f"{TAG}/{level}: {message}", file=sys.stderr, flush=True)


def _get_writer():
    global _write, _output
    if _write is None:
        android = _android_writer()
        if android is not None:
            _write, _output = android, "logcat (liblog)"
        else:
            _write, _output = _stderr_writer, "stderr"
    return _write


def output_name() -> str:
    _get_writer()
    return _output


def encode_message(message: str) -> bytes:
    data = message.replace("\x00", "\\0").encode("utf-8", "replace")
    if len(data) <= MAX_MESSAGE_BYTES:
        return data
    return data[: MAX_MESSAGE_BYTES - 3].decode("utf-8", "ignore").encode("utf-8") + b"..."


def format_line(stage: str, ok: bool, detail: str, elapsed: float) -> str:
    verdict = "OK" if ok else "FAIL"
    line = f"t={elapsed:8.3f}s {stage:<16} {verdict}"
    return f"{line} {detail}" if detail else line


def report(stage: str, ok: bool, detail: str = "") -> None:
    if not DEBUG:
        return
    line = format_line(stage, ok, detail, time.monotonic() - _STARTED_AT)
    try:
        _get_writer()(ANDROID_LOG_INFO if ok else ANDROID_LOG_ERROR, line)
    except Exception as exc:
        # La diagnostica non deve mai far cadere l'app: ripiega su stderr, che p4a manda in logcat col tag python.
        _stderr_writer(ANDROID_LOG_ERROR, f"scrittura log fallita ({type(exc).__name__}: {exc}): {line}")


def ok(stage: str, detail: str = "") -> None:
    report(stage, True, detail)


def fail(stage: str, reason: str) -> None:
    report(stage, False, reason)


def state(stage: str, ok: bool, detail: str = "") -> None:
    """Come report, ma scrive solo quando esito o dettaglio cambiano: per gli stadi controllati ogni secondo."""
    if not DEBUG:
        return
    key = (ok, detail)
    with _lock:
        if _last_state.get(stage) == key:
            return
        _last_state[stage] = key
    report(stage, ok, detail)


def forget(stage: str) -> None:
    with _lock:
        _last_state.pop(stage, None)


class StageProbe:
    def __init__(self):
        self.detail = ""


@contextmanager
def stage(name: str):
    """OK con probe.detail se il blocco termina, FAIL con il tipo e il messaggio dell'eccezione se solleva (che poi risale)."""
    probe = StageProbe()
    try:
        yield probe
    except BaseException as exc:
        fail(name, f"{type(exc).__name__}: {exc}")
        raise
    ok(name, probe.detail)


# Server MJPEG: pagina web, stream multipart, istantanea, info.json e token nell'URL.

log = logging.getLogger("mjpeg")

BOUNDARY = b"gioco-frame"
TOKEN_PARAM = "t"
# 6 byte casuali = 8 caratteri url-safe, 48 bit: abbastanza per una rete locale, corto da leggere sulla scheda.
TOKEN_BYTES = 6
DEFAULT_PORTS = tuple(range(8080, 8090))
CLIENT_WAIT_TIMEOUT = 5.0
CLIENT_SOCKET_TIMEOUT = 10.0
PROBE_ADDRESSES = ("10.255.255.255", "192.0.2.1", "8.8.8.8")
# Wi-Fi prima, poi hotspot, poi tethering USB/Ethernet. Le interfacce dati mobili e VPN non sono raggiungibili dal PC.
INTERFACE_PRIORITY = (("wlan", 0), ("swlan", 1), ("softap", 1), ("ap", 1), ("eth", 2), ("usb", 2), ("rndis", 2), ("ncm", 2))
EXCLUDED_INTERFACE_PREFIXES = ("rmnet", "ccmni", "tun", "ppp", "dummy", "lo", "ipsec", "clat", "v4-")
OTHER_INTERFACE_PRIORITY = 3


class BrokerClosed(Exception):
    pass


class FrameBroker:
    """Ultimo JPEG disponibile più un numero di sequenza: ogni client salta i fotogrammi che non riesce a seguire."""

    def __init__(self):
        self._cond = threading.Condition()
        self._frame = None
        self._seq = 0
        self._closed = False
        self._clients = 0
        self._published_at = None

    @property
    def clients(self) -> int:
        with self._cond:
            return self._clients

    def publish(self, jpeg: bytes) -> None:
        with self._cond:
            self._frame = bytes(jpeg)
            self._seq += 1
            self._published_at = time.monotonic()
            self._cond.notify_all()

    def frame_age(self) -> float | None:
        with self._cond:
            if self._published_at is None:
                return None
            return time.monotonic() - self._published_at

    def latest(self) -> bytes | None:
        with self._cond:
            return self._frame

    def wait_next(self, last_seq: int, timeout: float) -> tuple[int, bytes] | None:
        deadline = time.monotonic() + timeout
        with self._cond:
            while not self._closed and self._seq == last_seq:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._cond.wait(remaining)
            if self._closed:
                raise BrokerClosed()
            return self._seq, self._frame

    @contextmanager
    def client(self):
        with self._cond:
            self._clients += 1
        try:
            yield
        finally:
            with self._cond:
                self._clients -= 1

    def close(self) -> None:
        with self._cond:
            self._closed = True
            self._cond.notify_all()


class LatestFrameEncoder:
    """Tiene in coda un solo fotogramma: se la codifica è lenta, quelli intermedi vengono scartati invece di accumularsi."""

    def __init__(self, broker: FrameBroker, encode, max_fps: float, on_thread_exit=None):
        if max_fps <= 0:
            raise ValueError(f"max_fps deve essere positivo: {max_fps}")
        self._broker = broker
        self._encode = encode
        self._min_interval = 1.0 / max_fps
        self._on_thread_exit = on_thread_exit
        self._cond = threading.Condition()
        self._pending = None
        self._running = False
        self._thread = None
        self.encoded = 0
        self.dropped = 0
        self.errors = 0
        self.last_error = None
        self.last_error_at = None
        self.last_encoded_at = None

    @property
    def is_alive(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def start(self) -> None:
        with self._cond:
            if self._running:
                return
            self._running = True
        self._thread = threading.Thread(target=self._run, name="mjpeg-encoder", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        with self._cond:
            self._running = False
            self._pending = None
            self._cond.notify_all()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def submit(self, item) -> None:
        with self._cond:
            if not self._running:
                return
            if self._pending is not None:
                self.dropped += 1
            self._pending = item
            self._cond.notify()

    def _take(self):
        with self._cond:
            if not self._running:
                return None, False
            item, self._pending = self._pending, None
            return item, True

    def _run(self) -> None:
        last = 0.0
        try:
            while True:
                with self._cond:
                    while self._running and self._pending is None:
                        self._cond.wait()
                    if not self._running:
                        return
                delay = self._min_interval - (time.monotonic() - last)
                if delay > 0:
                    time.sleep(delay)
                item, running = self._take()
                if not running:
                    return
                if item is None:
                    continue
                last = time.monotonic()
                try:
                    jpeg = self._encode(item)
                except Exception as exc:
                    # L'encoder Android solleva JavaException, che qui non è importabile.
                    log.exception("codifica JPEG fallita")
                    self.errors += 1
                    self.last_error = f"{type(exc).__name__}: {exc}"
                    self.last_error_at = time.monotonic()
                    continue
                self._broker.publish(jpeg)
                self.encoded += 1
                self.last_encoded_at = time.monotonic()
        finally:
            if self._on_thread_exit is not None:
                self._on_thread_exit()


class _Handler(BaseHTTPRequestHandler):
    server_version = "GiocoMJPEG/1.0"
    # Un client che smette di leggere bloccherebbe il thread per sempre sulla write.
    timeout = CLIENT_SOCKET_TIMEOUT

    def _authorized(self, query: str) -> bool:
        expected = self.server.token
        if expected is None:
            return True
        supplied = parse_qs(query).get(TOKEN_PARAM, [""])[0]
        # Confronto a tempo costante: non rivela quanti caratteri iniziali sono giusti.
        return hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))

    def do_GET(self):
        parts = urlsplit(self.path)
        path = parts.path
        if not self._authorized(parts.query):
            self._send(HTTPStatus.FORBIDDEN, "text/plain; charset=utf-8", b"token mancante o errato\n")
            return
        if is_api_path(path):
            self._send_json(HTTPStatus.METHOD_NOT_ALLOWED, error_payload("metodo", "usa POST"), allow="POST")
            return
        if path in ("/", "/index.html"):
            self._send(HTTPStatus.OK, "text/html; charset=utf-8", PAGE_HTML.encode("utf-8"))
        elif path == "/stream.mjpg":
            self._stream()
        elif path == "/snapshot.jpg":
            frame = self.server.broker.latest()
            if frame is None:
                self._send(HTTPStatus.SERVICE_UNAVAILABLE, "text/plain; charset=utf-8", b"nessun fotogramma\n")
            else:
                self._send(HTTPStatus.OK, "image/jpeg", frame)
        elif path == "/info.json":
            info = dict(self.server.info_provider())
            broker = self.server.broker
            info["clients"] = broker.clients
            age = broker.frame_age()
            # Senza questo campo la pagina non distingue uno stream fermo da uno vivo: la connessione resta aperta.
            info["frame_age"] = None if age is None else round(age, 1)
            self._send(HTTPStatus.OK, "application/json", json.dumps(info).encode("utf-8"))
        else:
            self._send(HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", b"non trovato\n")

    def do_POST(self):
        parts = urlsplit(self.path)
        if not self._authorized(parts.query):
            self._send_json(HTTPStatus.FORBIDDEN, error_payload("token", "token mancante o errato"))
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._send_json(HTTPStatus.BAD_REQUEST, error_payload("richiesta", "Content-Length non valido"))
            return
        if length < 0:
            self._send_json(HTTPStatus.BAD_REQUEST, error_payload("richiesta", "Content-Length non valido"))
            return
        if length > MAX_BODY_BYTES:
            self._send_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE, error_payload("troppo_grande", f"corpo oltre {MAX_BODY_BYTES} byte")
            )
            return
        body = self.rfile.read(length) if length else b""
        api = self.server.api
        if api is None:
            self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, error_payload("non_disponibile", "API di comando non attiva"))
            return
        result = api.dispatch(parts.path, parse_qs(parts.query), body)
        if result.file_path is not None:
            self._send_file(result)
        else:
            self._send_json(result.status, result.payload)

    def _send_json(self, status, payload: dict, allow: str | None = None):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if allow is not None:
            self.send_header("Allow", allow)
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, result: "ApiResult"):
        try:
            handle = open(result.file_path, "rb")
        except OSError as exc:
            self._send_json(HTTPStatus.NOT_FOUND, error_payload("file_non_trovato", str(exc)))
            return
        with handle:
            size = os.fstat(handle.fileno()).st_size
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", result.content_type)
            self.send_header("Content-Length", str(size))
            self.send_header("Content-Disposition", f'attachment; filename="{result.filename}"')
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                shutil.copyfileobj(handle, self.wfile, FILE_CHUNK_BYTES)
            except OSError:
                # Il client ha chiuso a metà download: non c'è nessuno a cui rispondere.
                return

    def _send(self, status, content_type, body: bytes):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _stream(self):
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={BOUNDARY.decode()}")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        broker = self.server.broker
        seq = 0
        with broker.client():
            try:
                while True:
                    item = broker.wait_next(seq, CLIENT_WAIT_TIMEOUT)
                    if item is None:
                        continue
                    seq, frame = item
                    header = b"--%s\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % (BOUNDARY, len(frame))
                    self.wfile.write(header + frame + b"\r\n")
                    self.wfile.flush()
            except (OSError, BrokerClosed):
                return

    def log_message(self, fmt, *args):
        log.debug("%s %s", self.address_string(), fmt % args)


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class MjpegServer:
    def __init__(
        self,
        broker: FrameBroker,
        info_provider,
        ports=DEFAULT_PORTS,
        host: str = "0.0.0.0",
        token: str | None = None,
        api: "CommandApi | None" = None,
    ):
        self._broker = broker
        self._info_provider = info_provider
        self._token = token
        self._api = api
        self._ports = tuple(ports)
        self._host = host
        self._httpd = None
        self._thread = None
        self.port = None

    def start(self) -> int:
        if self._httpd is not None:
            return self.port
        if not self._ports:
            raise ValueError("nessuna porta indicata")
        last_error = None
        for port in self._ports:
            try:
                httpd = _Server((self._host, port), _Handler)
                break
            except OSError as exc:
                last_error = exc
        else:
            raise OSError(f"nessuna porta libera in {self._ports}: {last_error}")
        httpd.broker = self._broker
        httpd.info_provider = self._info_provider
        httpd.token = self._token
        httpd.api = self._api
        self._httpd = httpd
        self.port = httpd.server_address[1]
        self._thread = threading.Thread(
            target=httpd.serve_forever, kwargs={"poll_interval": 0.5}, name="mjpeg-server", daemon=True
        )
        self._thread.start()
        log.info("server MJPEG in ascolto su %s:%d", self._host, self.port)
        return self.port

    def stop(self) -> None:
        if self._httpd is None:
            return
        self._broker.close()
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=2.0)
        self._httpd = None
        self._thread = None


def local_ipv4(probe_addresses=PROBE_ADDRESSES) -> str | None:
    # connect() su UDP non spedisce pacchetti: chiede solo al kernel quale interfaccia userebbe.
    for address in probe_addresses:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect((address, 1))
                ip = sock.getsockname()[0]
        except OSError:
            continue
        if ip and ip != "0.0.0.0" and not ip.startswith("127."):
            return ip
    return None


def _interface_priority(name: str) -> int | None:
    lowered = name.lower()
    if lowered.startswith(EXCLUDED_INTERFACE_PREFIXES):
        return None
    for prefix, priority in INTERFACE_PRIORITY:
        if lowered.startswith(prefix):
            return priority
    return OTHER_INTERFACE_PRIORITY


def rank_lan_addresses(candidates: list[tuple[str, str]]) -> list[str]:
    """Ordina gli IPv4 privati per probabilità che il PC li raggiunga; scarta dati mobili, VPN, loopback e link-local."""
    ranked = []
    for order, (name, ip) in enumerate(candidates):
        priority = _interface_priority(name)
        if priority is None:
            continue
        try:
            address = ipaddress.IPv4Address(ip)
        except ValueError:
            continue
        if not address.is_private or address.is_loopback or address.is_link_local:
            continue
        ranked.append((priority, order, ip))
    result = []
    for _, _, ip in sorted(ranked):
        if ip not in result:
            result.append(ip)
    return result


API_PATHS = ("/status", "/files", "/files/get")
API_PREFIX = "/cmd/"
CMD_TIMEOUT = 10.0
MAX_BODY_BYTES = 1024
FILE_CHUNK_BYTES = 256 * 1024
MEDIA_DIRS = ("photos", "videos", "audio")
MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".mp4": "video/mp4", ".m4a": "audio/mp4"}


def is_api_path(path: str) -> bool:
    return path.startswith(API_PREFIX) or path in API_PATHS


def error_payload(code: str, message: str) -> dict:
    return {"ok": False, "error": code, "message": message}


class CommandError(Exception):
    """Errore di un comando remoto: diventa una risposta JSON con il suo codice HTTP."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


@dataclass
class ApiResult:
    status: int
    payload: dict | None = None
    file_path: str | None = None
    content_type: str | None = None
    filename: str | None = None


class MainThreadRunner:
    """Esegue una funzione sul thread di Kivy e ne attende il risultato da un altro thread."""

    def __init__(self, schedule=None, timeout: float = CMD_TIMEOUT):
        self._schedule = schedule if schedule is not None else _schedule_on_kivy
        self.timeout = timeout

    def call(self, fn):
        lock = threading.Lock()
        done = threading.Event()
        state_ = {"started": False, "cancelled": False}
        box = {}

        def run():
            with lock:
                if state_["cancelled"]:
                    return
                state_["started"] = True
            try:
                box["value"] = fn()
            except BaseException as exc:
                box["error"] = exc
            finally:
                done.set()

        self._schedule(run)
        if not done.wait(self.timeout):
            with lock:
                started = state_["started"]
                if not started:
                    state_["cancelled"] = True
            if not started:
                raise CommandError(
                    504, "timeout", f"il thread di Kivy non ha preso il comando entro {self.timeout:.0f} s: annullato"
                )
            # Il comando è partito sul thread di Kivy: aspettarlo ancora non bloccherebbe niente di nuovo.
            if not done.wait(self.timeout):
                raise CommandError(
                    504, "timeout", f"comando avviato ma non concluso entro {2 * self.timeout:.0f} s: esito sconosciuto"
                )
        if "error" in box:
            raise box["error"]
        return box["value"]


def _schedule_on_kivy(fn) -> None:
    # Clock.schedule_once è l'unico ingresso al thread di Kivy sicuro da un altro thread.
    Clock.schedule_once(lambda dt: fn(), 0)


def parse_torch_body(body: bytes) -> bool:
    text = body.decode("utf-8", "replace").strip().lower()
    if text == "on":
        return True
    if text == "off":
        return False
    raise CommandError(400, "richiesta", "corpo atteso: on oppure off")


def media_entry(dirname: str, path: str) -> dict:
    try:
        stat = os.stat(path)
    except OSError:
        return {"dir": dirname, "name": os.path.basename(path), "size": 0, "modified": None}
    return {"dir": dirname, "name": os.path.basename(path), "size": stat.st_size, "modified": int(stat.st_mtime)}


def list_media(dirs: dict, query: dict) -> dict:
    if not dirs:
        raise CommandError(503, "non_disponibile", "cartelle dei file disponibili solo su Android")
    dirname = query.get("dir", [""])[0]
    if dirname not in MEDIA_DIRS:
        raise CommandError(400, "richiesta", f"dir deve essere uno di {', '.join(MEDIA_DIRS)}")
    folder = dirs[dirname]
    files = []
    try:
        entries = list(os.scandir(folder))
    except FileNotFoundError:
        entries = []
    for entry in entries:
        if entry.name.startswith(".") or not entry.is_file():
            continue
        stat = entry.stat()
        files.append({"name": entry.name, "size": stat.st_size, "modified": int(stat.st_mtime)})
    files.sort(key=lambda item: (item["modified"], item["name"]), reverse=True)
    return {"dir": dirname, "files": files}


def resolve_media_file(dirs: dict, query: dict) -> ApiResult:
    if not dirs:
        raise CommandError(503, "non_disponibile", "cartelle dei file disponibili solo su Android")
    raw = query.get("path", [""])[0]
    dirname, separator, name = raw.partition("/")
    valid_name = name and name not in (".", "..") and not name.startswith(".") and "/" not in name and "\\" not in name
    if not separator or dirname not in MEDIA_DIRS or not valid_name:
        raise CommandError(400, "richiesta", "path atteso nella forma <photos|videos|audio>/<nome file>")
    folder = os.path.realpath(dirs[dirname])
    full = os.path.realpath(os.path.join(folder, name))
    # realpath risolve anche i link simbolici: il file deve stare davvero dentro la cartella dichiarata.
    if os.path.dirname(full) != folder:
        raise CommandError(400, "richiesta", "path fuori dalla cartella dei file")
    if not os.path.isfile(full):
        raise CommandError(404, "file_non_trovato", f"{dirname}/{name} non esiste")
    content_type = MEDIA_TYPES.get(os.path.splitext(name)[1].lower(), "application/octet-stream")
    return ApiResult(200, file_path=full, content_type=content_type, filename=name)


class CommandApi:
    """Instrada le richieste POST. I comandi che toccano fotocamera o stato dell'app passano dal runner."""

    def __init__(self, controller, runner: MainThreadRunner):
        self._controller = controller
        self._runner = runner

    def dispatch(self, path: str, query: dict, body: bytes) -> ApiResult:
        try:
            return self._route(path, query, body)
        except CommandError as exc:
            return ApiResult(exc.status, error_payload(exc.code, exc.message))
        except Exception as exc:
            log.exception("comando %s fallito", path)
            return ApiResult(500, error_payload("errore", f"{type(exc).__name__}: {exc}"))

    def _route(self, path: str, query: dict, body: bytes) -> ApiResult:
        controller = self._controller
        if path == "/cmd/photo":
            return self._on_main(controller.photo)
        if path == "/cmd/video/start":
            return self._on_main(controller.video_start)
        if path == "/cmd/video/stop":
            return self._on_main(controller.video_stop)
        if path == "/cmd/audio/start":
            return self._on_main(controller.audio_start)
        if path == "/cmd/audio/stop":
            return self._on_main(controller.audio_stop)
        if path == "/cmd/torch":
            on = parse_torch_body(body)
            return self._on_main(lambda: controller.torch(on))
        if path == "/status":
            return self._on_main(controller.status)
        if path == "/files":
            return ApiResult(200, {"ok": True, **list_media(controller.media_dirs(), query)})
        if path == "/files/get":
            return resolve_media_file(controller.media_dirs(), query)
        raise CommandError(404, "sconosciuto", f"endpoint sconosciuto: {path}")

    def _on_main(self, fn) -> ApiResult:
        return ApiResult(200, {"ok": True, **self._runner.call(fn)})


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def stream_url(ip: str, port: int, token: str | None = None) -> str:
    if token is None:
        return f"http://{ip}:{port}/"
    return f"http://{ip}:{port}/?{TOKEN_PARAM}={quote(token)}"


PAGE_HTML = """<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gioco - fotocamera</title>
<style>
  :root { color-scheme: dark; --bg: #0b0d10; --panel: #161a20; --text: #e8ebef; --muted: #8b95a1; --live: #e5484d; --ok: #3dd68c; }
  * { box-sizing: border-box; }
  html, body { margin: 0; height: 100%; background: var(--bg); color: var(--text); font: 15px/1.4 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  body { display: flex; flex-direction: column; }
  header { display: flex; align-items: center; gap: 12px; padding: 10px 16px; background: var(--panel); flex-wrap: wrap; }
  h1 { font-size: 16px; margin: 0; font-weight: 600; }
  .status { display: flex; align-items: center; gap: 8px; color: var(--muted); font-size: 14px; }
  .dot { width: 10px; height: 10px; border-radius: 50%; background: var(--muted); }
  .live .dot { background: var(--live); animation: blink 1s steps(1) infinite; }
  .live, .paused { color: var(--text); }
  .paused .dot { background: #f5a524; }
  @keyframes blink { 50% { opacity: 0.2; } }
  .spacer { flex: 1; }
  button, a.button { background: #252b33; color: var(--text); border: 1px solid #333b45; border-radius: 8px; padding: 7px 12px; font: inherit; cursor: pointer; text-decoration: none; }
  button:hover, a.button:hover { background: #2f3640; }
  #stage { position: relative; flex: 1; overflow: hidden; }
  #video { position: absolute; left: 50%; top: 50%; transform-origin: center center; background: #000; }
  #message { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: var(--text); background: rgba(11, 13, 16, 0.6); text-align: center; padding: 16px; pointer-events: none; }
  footer { padding: 6px 16px; color: var(--muted); font-size: 13px; background: var(--panel); }
</style>
</head>
<body>
<header>
  <h1>Gioco &middot; fotocamera posteriore</h1>
  <div id="status" class="status"><span class="dot"></span><span id="status-text">connessione...</span></div>
  <div class="spacer"></div>
  <button id="rotate" type="button">Ruota 90&deg;</button>
  <a id="snapshot" class="button" href="/snapshot.jpg" target="_blank" rel="noopener">Istantanea</a>
  <button id="fullscreen" type="button">Schermo intero</button>
</header>
<div id="stage">
  <img id="video" alt="Stream della fotocamera">
  <div id="message">In attesa del primo fotogramma...</div>
</div>
<footer id="footer">&nbsp;</footer>
<script>
(() => {
  const img = document.getElementById("video");
  const stage = document.getElementById("stage");
  const message = document.getElementById("message");
  const status = document.getElementById("status");
  const statusText = document.getElementById("status-text");
  const footer = document.getElementById("footer");
  const STALE_SECONDS = 2.5;
  // Il token arriva nell'URL della pagina e va ripetuto su ogni richiesta al telefono.
  const auth = "t=" + encodeURIComponent(new URLSearchParams(location.search).get("t") || "");
  document.getElementById("snapshot").href = "/snapshot.jpg?" + auth;
  let frameW = 1280, frameH = 720, rotation = 0, userRotated = false, online = false;

  function layout() {
    const box = stage.getBoundingClientRect();
    const turned = rotation % 180 !== 0;
    const rw = turned ? frameH : frameW;
    const rh = turned ? frameW : frameH;
    const scale = Math.min(box.width / rw, box.height / rh);
    img.style.width = (frameW * scale) + "px";
    img.style.height = (frameH * scale) + "px";
    img.style.transform = "translate(-50%, -50%) rotate(" + rotation + "deg)";
  }

  function connect() {
    img.src = "/stream.mjpg?" + auth + "&n=" + Date.now();
  }

  function setState(state, text) {
    online = state !== "offline";
    status.classList.toggle("live", state === "live");
    status.classList.toggle("paused", state === "paused");
    statusText.textContent = text;
  }

  function showMessage(text) {
    message.style.display = text ? "flex" : "none";
    message.textContent = text;
  }

  img.addEventListener("error", () => {
    setState("offline", "riconnessione...");
    message.style.display = "flex";
    message.textContent = "Stream interrotto. Riprovo...";
    setTimeout(connect, 1500);
  });

  async function poll() {
    try {
      const response = await fetch("/info.json?" + auth, { cache: "no-store" });
      if (response.status === 403) {
        setState("offline", "token mancante o errato");
        showMessage("Apri l'indirizzo completo mostrato sul telefono, con ?t=...");
        return;
      }
      const info = await response.json();
      if (!online) { connect(); }
      if (info.frame_age === null) {
        setState("paused", "in attesa");
        showMessage("In attesa del primo fotogramma...");
      } else if (info.frame_age > STALE_SECONDS) {
        setState("paused", "in pausa");
        showMessage("Nessun fotogramma da " + Math.round(info.frame_age) + " s: sul telefono l'app \u00e8 in background o sta registrando un video.");
      } else {
        setState("live", "in diretta");
        showMessage("");
      }
      if (info.width && info.height) { frameW = info.width; frameH = info.height; }
      if (!userRotated && typeof info.rotation === "number") { rotation = info.rotation; }
      footer.textContent = frameW + "\\u00d7" + frameH + " \\u00b7 rotazione " + rotation + "\\u00b0 \\u00b7 spettatori: " + info.clients;
      layout();
    } catch (err) {
      setState("offline", "telefono non raggiungibile");
    }
  }

  document.getElementById("rotate").addEventListener("click", () => {
    rotation = (rotation + 90) % 360;
    userRotated = true;
    layout();
  });
  document.getElementById("fullscreen").addEventListener("click", () => {
    if (document.fullscreenElement) { document.exitFullscreen(); } else { stage.requestFullscreen(); }
  });
  window.addEventListener("resize", layout);
  document.addEventListener("fullscreenchange", layout);

  layout();
  poll();
  setInterval(poll, 3000);
})();
</script>
</body>
</html>
"""


IS_ANDROID = platform == "android"

if IS_ANDROID:
    from android.permissions import Permission, check_permission, request_permissions
    from android.runnable import run_on_ui_thread
    from jnius import JavaException, PythonJavaClass, autoclass, cast, detach, java_method

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    ImageFormat = autoclass("android.graphics.ImageFormat")
    YuvImage = autoclass("android.graphics.YuvImage")
    AndroidRect = autoclass("android.graphics.Rect")
    ByteArrayOutputStream = autoclass("java.io.ByteArrayOutputStream")
    WindowLayoutParams = autoclass("android.view.WindowManager$LayoutParams")
    Camera = autoclass("android.hardware.Camera")
    CameraInfo = autoclass("android.hardware.Camera$CameraInfo")
    CameraSize = autoclass("android.hardware.Camera$Size")
    CamcorderProfile = autoclass("android.media.CamcorderProfile")
    MediaRecorder = autoclass("android.media.MediaRecorder")
    AudioSource = autoclass("android.media.MediaRecorder$AudioSource")
    VideoSource = autoclass("android.media.MediaRecorder$VideoSource")
    OutputFormat = autoclass("android.media.MediaRecorder$OutputFormat")
    VideoEncoder = autoclass("android.media.MediaRecorder$VideoEncoder")
    AudioEncoder = autoclass("android.media.MediaRecorder$AudioEncoder")
    Environment = autoclass("android.os.Environment")
    SurfaceTexture = autoclass("android.graphics.SurfaceTexture")
    BatteryManager = autoclass("android.os.BatteryManager")
    Context = autoclass("android.content.Context")
    SurfaceView = autoclass("android.view.SurfaceView")
    Gravity = autoclass("android.view.Gravity")
    ViewGroup = autoclass("android.view.ViewGroup")
    FrameLayoutParams = autoclass("android.widget.FrameLayout$LayoutParams")
    NetworkInterface = autoclass("java.net.NetworkInterface")
    InetAddress = autoclass("java.net.InetAddress")
    JAVA_ERRORS = (JavaException,)

    class _PreviewCallback(PythonJavaClass):
        __javainterfaces__ = ["android/hardware/Camera$PreviewCallback"]
        __javacontext__ = "app"

        def __init__(self, on_frame):
            super().__init__()
            self._on_frame = on_frame

        @java_method("([BLandroid/hardware/Camera;)V")
        def onPreviewFrame(self, data, camera):
            # Un'eccezione Python che risale in un callback Java abbatte il processo.
            try:
                self._on_frame(data)
            except Exception:
                Logger.exception("Stream: callback anteprima fallito")

    @run_on_ui_thread
    def keep_screen_on():
        PythonActivity.mActivity.getWindow().addFlags(WindowLayoutParams.FLAG_KEEP_SCREEN_ON)

    class _SurfaceHolderCallback(PythonJavaClass):
        __javainterfaces__ = ["android/view/SurfaceHolder$Callback"]
        __javacontext__ = "app"

        def __init__(self, on_created, on_destroyed):
            super().__init__()
            self._on_created = on_created
            self._on_destroyed = on_destroyed

        @java_method("(Landroid/view/SurfaceHolder;)V")
        def surfaceCreated(self, holder):
            try:
                self._on_created(holder)
            except Exception:
                Logger.exception("Camera: surfaceCreated fallito")

        @java_method("(Landroid/view/SurfaceHolder;III)V")
        def surfaceChanged(self, holder, pixel_format, width, height):
            Logger.info(f"Camera: SurfaceView {width}x{height} formato {pixel_format}")

        @java_method("(Landroid/view/SurfaceHolder;)V")
        def surfaceDestroyed(self, holder):
            try:
                self._on_destroyed(holder)
            except Exception:
                Logger.exception("Camera: surfaceDestroyed fallito")

    class NativePreviewSurface:
        """SurfaceView nativa sopra la superficie SDL; ogni metodo gira sul thread UI di Android."""

        def __init__(self, on_created, on_destroyed):
            # pyjnius non trattiene il proxy: senza questo riferimento il GC lo libera mentre Java lo chiama.
            self._callback = _SurfaceHolderCallback(on_created, on_destroyed)
            self._view = None

        @run_on_ui_thread
        def attach(self, left, top, width, height, hidden):
            if self._view is not None:
                return
            activity = PythonActivity.mActivity
            view = SurfaceView(activity)
            # Sopra la SurfaceView di SDL: Kivy non può disegnarci sopra, per questo il riquadro evita barra e fascia alta.
            view.setZOrderMediaOverlay(True)
            view.getHolder().addCallback(self._callback)
            params = FrameLayoutParams(width, height, Gravity.TOP | Gravity.LEFT)
            params.setMargins(left, top, 0, 0)
            view.setTranslationX(SURFACE_HIDDEN_OFFSET if hidden else 0.0)
            activity.addContentView(view, params)
            self._view = view

        @run_on_ui_thread
        def set_hidden(self, hidden):
            if self._view is not None:
                # Fuori schermo invece di INVISIBLE: con INVISIBLE Android distrugge la superficie e l'anteprima si ferma.
                self._view.setTranslationX(SURFACE_HIDDEN_OFFSET if hidden else 0.0)

        @run_on_ui_thread
        def detach(self):
            view, self._view = self._view, None
            if view is None:
                return
            view.getHolder().removeCallback(self._callback)
            parent = view.getParent()
            if parent is not None:
                cast(ViewGroup, parent).removeView(view)
else:
    JAVA_ERRORS = ()

GL_TEXTURE0 = 0x84C0
GL_TEXTURE_EXTERNAL_OES = 0x8D65
GL_FRAGMENT_SHADER = 0x8B30
GL_COMPILE_STATUS = 0x8B81
GL_EXTENSIONS = 0x1F03
OES_EXTENSION = "GL_OES_EGL_image_external"
CAMERA_TEXTURE_UNIT = 1

FIRST_FRAME_TIMEOUT = 3.0
FRAME_STALL_SECONDS = 3.0
FRAME_REPORT_SECONDS = 1.0

# Codici di android.graphics.ImageFormat: i formati di anteprima che Camera può restituire.
IMAGE_FORMAT_NAMES = {
    0: "UNKNOWN",
    4: "RGB_565",
    16: "NV16",
    17: "NV21",
    20: "YUY2",
    32: "RAW_SENSOR",
    34: "PRIVATE",
    35: "YUV_420_888",
    256: "JPEG",
    842094169: "YV12",
}
IMAGE_FORMAT_BITS = {4: 16, 16: 16, 17: 12, 20: 16, 35: 12}
IMAGE_FORMAT_YV12 = 842094169

FOCUS_CONTINUOUS_VIDEO = "continuous-video"
FLASH_MODE_TORCH = "torch"
FLASH_MODE_OFF = "off"
AUDIO_BIT_RATE = 128_000
AUDIO_SAMPLE_RATE = 44_100

STREAM_JPEG_QUALITY = 70
STREAM_MAX_FPS = 15
STREAM_REFRESH_SECONDS = 1.0

PREVIEW_FBO = "fbo"
PREVIEW_SURFACE = "surface"
PREVIEW_MODES = (PREVIEW_FBO, PREVIEW_SURFACE)


def check_preview_mode(mode: str) -> str:
    if mode not in PREVIEW_MODES:
        raise ValueError(f"PREVIEW_MODE non valido: {mode!r}, ammessi {PREVIEW_MODES}")
    return mode


# "fbo": SurfaceTexture -> shader OES -> FBO mostrato da Kivy.
# "surface": SurfaceView nativa per lo schermo; il FBO per le foto è alimentato da onPreviewFrame (NV21).
PREVIEW_MODE = check_preview_mode("fbo")
SURFACE_FBO_INTERVAL = 0.1
SURFACE_HIDDEN_OFFSET = -100000.0
TOP_BAND_DP = 112

MODE_IDLE = "idle"
MODE_VIDEO = "video"
MODE_AUDIO = "audio"

KEY_BACK = 27
BAR_HEIGHT_DP = 150
RECORD_RED = (0.92, 0.16, 0.16, 1)
GLYPHS = ("photo", "video", "audio")

# Matrici 4x4 column-major come quelle di GLConsumer (frameworks/native/libs/gui/GLConsumer.cpp).
MAT4_IDENTITY = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)
MAT4_FLIP_H = (-1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 1.0, 0.0, 0.0, 1.0)
MAT4_FLIP_V = (1.0, 0.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 1.0)
MAT4_ROT_90 = (0.0, 1.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 1.0, 0.0, 0.0, 1.0)
# Rotazione di setDisplayOrientation -> flag NATIVE_WINDOW_TRANSFORM (flip_h, flip_v, rot_90).
DISPLAY_ORIENTATION_TRANSFORM = {0: (False, False, False), 90: (False, False, True), 180: (True, True, False), 270: (True, True, True)}

VALID_ROTATIONS = (0, 90, 180, 270)
SURFACE_ROTATION_DEGREES = {0: 0, 1: 90, 2: 180, 3: 270}
ASPECT_TOLERANCE = 0.01

# La texture della fotocamera è GL_TEXTURE_EXTERNAL_OES: un sampler2D non la legge.
PREVIEW_FRAGMENT_SHADER = """
#extension GL_OES_EGL_image_external : require
#ifdef GL_ES
    precision highp float;
#endif

varying vec4 frag_color;
varying vec2 tex_coord0;

uniform samplerExternalOES camera_texture;
uniform mat4 st_matrix;

void main()
{
    vec2 coord = (st_matrix * vec4(tex_coord0, 0.0, 1.0)).xy;
    gl_FragColor = texture2D(camera_texture, coord);
}
"""

# NV21: piano Y (luminance) e piano VU interleaved a metà risoluzione (luminance_alpha: L=V, A=U). BT.601 full range.
YUV_FRAGMENT_SHADER = """
#ifdef GL_ES
    precision highp float;
#endif

varying vec4 frag_color;
varying vec2 tex_coord0;

uniform sampler2D texture0;
uniform sampler2D uv_texture;
uniform mat4 st_matrix;

void main()
{
    vec2 coord = (st_matrix * vec4(tex_coord0, 0.0, 1.0)).xy;
    float y = texture2D(texture0, coord).r;
    vec4 vu = texture2D(uv_texture, coord);
    float v = vu.r - 0.5;
    float u = vu.a - 0.5;
    gl_FragColor = vec4(y + 1.402 * v, y - 0.344136 * u - 0.714136 * v, y + 1.772 * u, 1.0);
}
"""
UV_TEXTURE_UNIT = 1

Size = tuple[int, int]


class CameraError(ValueError):
    pass


CAMERA_ERRORS = JAVA_ERRORS + (ValueError,)


def _area(size: Size) -> int:
    return size[0] * size[1]


def _aspect(size: Size) -> float:
    return size[0] / size[1]


def _check_rotation(value: int) -> None:
    if value not in VALID_ROTATIONS:
        raise ValueError(f"rotazione non valida: {value}")


def choose_size(target: Size, candidates: list[Size]) -> Size:
    if not candidates:
        raise ValueError("nessuna dimensione supportata dalla fotocamera")
    if target in candidates:
        return target
    same_aspect = [s for s in candidates if abs(_aspect(s) - _aspect(target)) <= ASPECT_TOLERANCE]
    pool = same_aspect or candidates
    not_larger = [s for s in pool if _area(s) <= _area(target)]
    if not_larger:
        return max(not_larger, key=_area)
    return min(pool, key=_area)


def choose_preview_size(video_size: Size, preview_sizes: list[Size], preferred: Size | None) -> Size:
    if video_size in preview_sizes:
        return video_size
    if preferred is not None and preferred in preview_sizes:
        return preferred
    return choose_size(video_size, preview_sizes)


def orientation_hint(sensor_degrees: int, display_degrees: int) -> int:
    _check_rotation(sensor_degrees)
    _check_rotation(display_degrees)
    return (sensor_degrees - display_degrees) % 360


def surface_rotation_to_degrees(rotation: int) -> int:
    if rotation not in SURFACE_ROTATION_DEGREES:
        raise ValueError(f"costante Surface.ROTATION sconosciuta: {rotation}")
    return SURFACE_ROTATION_DEGREES[rotation]


def rotated_size(size: Size, rotation: int) -> Size:
    _check_rotation(rotation)
    if rotation in (90, 270):
        return size[1], size[0]
    return size


def cover_tex_coords(content: Size, box: Size) -> tuple[float, float, float, float]:
    if min(*content, *box) <= 0:
        raise ValueError(f"dimensioni non positive: contenuto={content} area={box}")
    content_aspect = _aspect(content)
    box_aspect = box[0] / box[1]
    if content_aspect > box_aspect:
        visible = box_aspect / content_aspect
        start = (1.0 - visible) / 2.0
        return start, 0.0, start + visible, 1.0
    visible = content_aspect / box_aspect
    start = (1.0 - visible) / 2.0
    return 0.0, start, 1.0, start + visible


def mat4_multiply(a, b) -> tuple[float, ...]:
    return tuple(sum(a[k * 4 + row] * b[col * 4 + k] for k in range(4)) for col in range(4) for row in range(4))


def surface_texture_fallback_matrix(rotation: int) -> tuple[float, ...]:
    """Ricostruisce la matrice di getTransformMatrix senza crop, per quando pyjnius non la restituisce."""
    _check_rotation(rotation)
    flip_h, flip_v, rot_90 = DISPLAY_ORIENTATION_TRANSFORM[rotation]
    xform = MAT4_IDENTITY
    if flip_h:
        xform = mat4_multiply(xform, MAT4_FLIP_H)
    if flip_v:
        xform = mat4_multiply(xform, MAT4_FLIP_V)
    if rot_90:
        xform = mat4_multiply(xform, MAT4_ROT_90)
    return mat4_multiply(MAT4_FLIP_V, xform)


def contain_rect(content: Size, rect: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Riquadro più grande con le proporzioni di content, centrato dentro rect (x, y, larghezza, altezza)."""
    x, y, width, height = rect
    if min(*content, width, height) <= 0:
        raise ValueError(f"dimensioni non positive: contenuto={content} riquadro={rect}")
    scale = min(width / content[0], height / content[1])
    fit_w = int(content[0] * scale)
    fit_h = int(content[1] * scale)
    return x + (width - fit_w) // 2, y + (height - fit_h) // 2, fit_w, fit_h


def kivy_rect_to_android(rect: tuple[int, int, int, int], window_height: int) -> tuple[int, int, int, int]:
    """Kivy misura y dal basso, le View Android dall'alto."""
    x, y, width, height = rect
    return x, window_height - (y + height), width, height


def format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def media_filename(prefix: str, extension: str, moment: datetime) -> str:
    # I millisecondi evitano che due foto nello stesso secondo si sovrascrivano.
    return f"{prefix}_{moment:%Y%m%d_%H%M%S}_{moment.microsecond // 1000:03d}.{extension}"


def _remove_file(path: str | None) -> None:
    if path is None:
        return
    try:
        os.remove(path)
    except FileNotFoundError:
        return
    except OSError:
        Logger.exception(f"Camera: impossibile eliminare {path}")


def _size_tuple(size) -> Size:
    return int(size.width), int(size.height)


def _java_sizes(java_list) -> list[Size]:
    if java_list is None:
        return []
    return [_size_tuple(cast(CameraSize, java_list.get(i))) for i in range(java_list.size())]


def _java_strings(java_list) -> list[str]:
    if java_list is None:
        return []
    items = []
    for i in range(java_list.size()):
        item = java_list.get(i)
        items.append(item if isinstance(item, str) else item.toString())
    return items


def _app_dir(activity, kind) -> str:
    directory = activity.getExternalFilesDir(kind)
    if directory is None:
        directory = activity.getFilesDir()
    path = directory.getAbsolutePath()
    os.makedirs(path, exist_ok=True)
    return path


def _android_ipv4_candidates() -> list[tuple[str, str]]:
    candidates = []
    interfaces = NetworkInterface.getNetworkInterfaces()
    if interfaces is None:
        return candidates
    while interfaces.hasMoreElements():
        iface = cast(NetworkInterface, interfaces.nextElement())
        try:
            if not iface.isUp() or iface.isLoopback():
                continue
        except JAVA_ERRORS:
            continue
        name = iface.getName()
        addresses = iface.getInetAddresses()
        while addresses.hasMoreElements():
            host = cast(InetAddress, addresses.nextElement()).getHostAddress()
            if host and ":" not in host:
                candidates.append((name, host))
    return candidates


def lan_addresses() -> list[str]:
    candidates = []
    if IS_ANDROID:
        try:
            candidates = _android_ipv4_candidates()
        except JAVA_ERRORS:
            Logger.exception("Stream: elenco interfacce di rete fallito")
    ranked = rank_lan_addresses(candidates)
    if ranked:
        return ranked
    fallback = local_ipv4()
    return rank_lan_addresses([("default", fallback)]) if fallback else []


def gl_extensions() -> str:
    try:
        value = glGetString(GL_EXTENSIONS)
    except Exception as exc:
        # I binding GL di Kivy sollevano tipi diversi a seconda della piattaforma.
        return f"<glGetString fallita: {exc}>"
    if isinstance(value, bytes):
        return value.decode("ascii", "replace")
    return str(value or "")


def shader_compile_log(source: str) -> str:
    """Ricompila lo shader a mano solo per leggerne il log: Kivy lo stampa ma non lo espone."""
    try:
        shader = glCreateShader(GL_FRAGMENT_SHADER)
        try:
            glShaderSource(shader, source.encode("utf-8"))
            glCompileShader(shader)
            status = glGetShaderiv(shader, GL_COMPILE_STATUS)
            log = glGetShaderInfoLog(shader, 4096)
        finally:
            glDeleteShader(shader)
    except Exception as exc:
        return f"log GL non disponibile ({type(exc).__name__}: {exc}); cerca 'Shader' nel log di Kivy"
    text = log.decode("utf-8", "replace") if isinstance(log, bytes) else str(log)
    text = " ".join(text.split())
    return f"compile_status={status} log={text or '<vuoto>'}"


def image_format_name(code: int | None) -> str:
    if code is None:
        return "sconosciuto"
    return f"{IMAGE_FORMAT_NAMES.get(code, 'NON_DOCUMENTATO')}({code})"


def expected_frame_bytes(width: int, height: int, image_format: int | None) -> int | None:
    if image_format == IMAGE_FORMAT_YV12:
        # YV12 allinea le righe a 16 byte (documentazione di Camera.Parameters.setPreviewFormat).
        y_stride = -(-width // 16) * 16
        uv_stride = -(-(y_stride // 2) // 16) * 16
        return y_stride * height + uv_stride * (height // 2) * 2
    bits = IMAGE_FORMAT_BITS.get(image_format)
    if bits is None:
        return None
    return width * height * bits // 8


class PreviewFrameMonitor:
    """Conta i fotogrammi di onPreviewFrame e decide, a ogni controllo, se lo stallo è iniziato."""

    def __init__(self, stall_seconds: float = FRAME_STALL_SECONDS):
        self.stall_seconds = stall_seconds
        self.total = 0
        self.last_bytes = None
        self.zero_seconds = 0.0
        self._last_total = 0
        self._stall_reported = False

    def frame(self, nbytes: int | None) -> None:
        # Unico scrittore: il thread UI di Android. Il thread di Kivy legge soltanto.
        self.total += 1
        self.last_bytes = nbytes

    def tick(self, dt: float, suspended: bool) -> tuple[str, int]:
        """Restituisce (esito, fotogrammi dall'ultimo tick). Esiti: ok, sospeso, zero, stallo (una volta), fermo."""
        total = self.total
        count = total - self._last_total
        self._last_total = total
        if suspended or count > 0:
            self.zero_seconds = 0.0
            self._stall_reported = False
            return ("sospeso" if suspended else "ok"), count
        self.zero_seconds += dt
        if self.zero_seconds < self.stall_seconds:
            return "zero", 0
        if not self._stall_reported:
            self._stall_reported = True
            return "stallo", 0
        return "fermo", 0


def _java_ints(java_list) -> list[int]:
    if java_list is None:
        return []
    values = []
    for i in range(java_list.size()):
        item = java_list.get(i)
        values.append(int(item) if isinstance(item, int) else int(item.intValue()))
    return values


def java_bytes(value) -> bytes:
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    tostring = getattr(value, "tostring", None)
    if tostring is not None:
        return bytes(tostring())
    # I byte Java sono con segno: -128..127.
    return bytes(b & 0xFF for b in value)


def nv21_to_jpeg(item) -> bytes:
    data, width, height = item
    image = YuvImage(data, ImageFormat.NV21, width, height, None)
    stream = ByteArrayOutputStream()
    if not image.compressToJpeg(AndroidRect(0, 0, width, height), STREAM_JPEG_QUALITY, stream):
        raise CameraError("YuvImage.compressToJpeg ha restituito false")
    return java_bytes(stream.toByteArray())


def _stop_recorder(recorder) -> bool:
    saved = True
    try:
        recorder.stop()
    except JAVA_ERRORS:
        # MediaRecorder.stop lancia RuntimeException se non ha ricevuto dati validi.
        Logger.exception("Camera: stop registrazione fallito")
        saved = False
    try:
        recorder.reset()
        recorder.release()
    except JAVA_ERRORS:
        Logger.exception("Camera: rilascio MediaRecorder fallito")
    return saved


def save_texture_png(texture, path: str) -> None:
    # Le texture degli FBO hanno la riga 0 in basso: senza flipped=True il PNG esce capovolto (verificato in test).
    texture.save(path, flipped=True)


class YuvPreviewRenderer:
    """Converte fotogrammi NV21 in RGB dentro un FBO, ruotati come lo schermo. Gira sul thread di Kivy."""

    def __init__(self, frame_size: Size, rotation: int):
        width, height = frame_size
        if width <= 0 or height <= 0 or width % 2 or height % 2:
            raise ValueError(f"NV21 richiede dimensioni pari e positive, ricevuto {width}x{height}")
        self.frame_size = frame_size
        self.rotation = rotation
        self.content_size = rotated_size(frame_size, rotation)
        self.frame_bytes = width * height * 3 // 2
        self.frames = 0
        self.y_texture = Texture.create(size=(width, height), colorfmt="luminance")
        self.uv_texture = Texture.create(size=(width // 2, height // 2), colorfmt="luminance_alpha")
        self.fbo = None

    def compile(self) -> None:
        fbo = Fbo(size=self.content_size)
        fbo.shader.fs = YUV_FRAGMENT_SHADER
        if not fbo.shader.success:
            raise CameraError(f"shader YUV non compilato: {shader_compile_log(YUV_FRAGMENT_SHADER)}")
        with fbo:
            BindTexture(texture=self.uv_texture, index=UV_TEXTURE_UNIT)
            Rectangle(size=self.content_size, texture=self.y_texture)
        fbo["uv_texture"] = UV_TEXTURE_UNIT
        # Il buffer NV21 ha la riga 0 in alto e l'orientamento del sensore: è la stessa trasformazione
        # che GLConsumer applica a una SurfaceTexture ruotata con setDisplayOrientation.
        matrix = Matrix()
        matrix.set(flat=list(surface_texture_fallback_matrix(self.rotation)))
        fbo["st_matrix"] = matrix
        self.fbo = fbo

    @property
    def texture(self):
        return self.fbo.texture if self.fbo is not None else None

    def upload(self, nv21) -> None:
        if self.fbo is None:
            raise CameraError("YuvPreviewRenderer.compile() non ancora chiamato")
        width, height = self.frame_size
        # bytes e non memoryview: Texture.blit_buffer di Kivy rifiuta i memoryview in sola lettura.
        data = nv21 if isinstance(nv21, bytes) else bytes(nv21)
        if len(data) < self.frame_bytes:
            raise ValueError(f"fotogramma NV21 di {len(data)} byte, attesi {self.frame_bytes} per {width}x{height}")
        luma = width * height
        self.y_texture.blit_buffer(data[:luma], colorfmt="luminance", bufferfmt="ubyte")
        self.uv_texture.blit_buffer(data[luma:self.frame_bytes], colorfmt="luminance_alpha", bufferfmt="ubyte")
        self.fbo.ask_update()
        self.fbo.draw()
        self.frames += 1


class TorchUnavailable(CameraError):
    pass


class CameraBackend:
    """Fotocamera, MediaRecorder e texture GL vivono sul thread di Kivy, che possiede il contesto GL.

    Fa eccezione la SurfaceView della modalità "surface": i suoi callback arrivano sul thread UI di Android,
    e l'unico accesso alla fotocamera da lì (stopPreview in surfaceDestroyed) passa per _camera_lock.
    """

    def __init__(self, on_frame, mode: str = PREVIEW_MODE, surface_rect=None):
        self._on_frame = on_frame
        self.mode = check_preview_mode(mode)
        if self.mode == PREVIEW_SURFACE and surface_rect is None:
            raise ValueError("la modalità surface richiede surface_rect")
        self._surface_rect = surface_rect
        self._camera_lock = threading.RLock()
        self._encoder = None
        self._yuv = None
        self._latest_nv21 = None
        self._uploaded_nv21 = None
        self._yuv_error_reported = False
        self._native_surface = None
        self._surface_hidden = False
        self._surface_preview_running = False
        self._has_frame = False
        activity = PythonActivity.mActivity
        self.photo_dir = _app_dir(activity, Environment.DIRECTORY_PICTURES)
        self.video_dir = _app_dir(activity, Environment.DIRECTORY_MOVIES)
        self.audio_dir = _app_dir(activity, Environment.DIRECTORY_MUSIC)
        self._camera = None
        self._profile = None
        self._video_size = None
        self._rotation = 0
        self.content_size = None
        self._tex_id = None
        self._surface_texture = None
        self._fbo = None
        # Lista Python: pyjnius ci ricopia dentro il float[] scritto da getTransformMatrix.
        self._st_values = [0.0] * 16
        self._last_st_values = None
        self._matrix_fallback_logged = False
        self._opened_at = 0.0
        self._first_frame_failed = False
        self._stream_wanted = False
        self._callback_error = None
        self._requested_format = None
        self._actual_format = None
        self._supported_formats = []
        self._frame_monitor = PreviewFrameMonitor()
        self._video_recorder = None
        self._video_path = None
        self._audio_recorder = None
        self._audio_path = None
        self.preview_size = None
        self._callback_active = False
        # pyjnius non trattiene il proxy: senza questo riferimento il GC lo libera mentre Java lo chiama.
        self._preview_callback = None

    @property
    def is_open(self) -> bool:
        return self._camera is not None

    def stream_info(self) -> dict:
        if self.preview_size is None:
            return {"rotation": 0}
        return {"rotation": self._rotation, "width": self.preview_size[0], "height": self.preview_size[1]}

    def attach_encoder(self, encoder: LatestFrameEncoder) -> None:
        self._encoder = encoder

    def set_streaming(self, enabled: bool):
        self._stream_wanted = enabled
        self._sync_preview_callback()

    def _sync_preview_callback(self):
        # Il callback copia ~3 MB a fotogramma da Java a Python: lo si registra solo se serve a qualcuno.
        surface_needs_frames = self.mode == PREVIEW_SURFACE
        want_callback = self._stream_wanted or DEBUG or surface_needs_frames
        if self._camera is None or self._video_recorder is not None:
            return
        if want_callback != self._callback_active:
            try:
                if want_callback:
                    width, height = self.preview_size
                    self._preview_callback = _PreviewCallback(lambda data: self._on_preview_frame(data, width, height))
                    self._camera.setPreviewCallback(self._preview_callback)
                else:
                    self._camera.setPreviewCallback(None)
            except JAVA_ERRORS as exc:
                Logger.exception("Stream: cambio stato del callback anteprima fallito")
                self._callback_error = f"setPreviewCallback({'proxy' if want_callback else 'null'}): {exc}"
                state(STAGE_CALLBACK, False, self._callback_error)
                return
            self._callback_active = want_callback
            self._callback_error = None
            Logger.info(f"Stream: callback anteprima {'attivo' if want_callback else 'spento'}")
        if not self._callback_active:
            detail = "spento: nessuno spettatore"
        elif self._stream_wanted:
            detail = "attivo, fotogrammi inoltrati all'encoder"
        elif surface_needs_frames:
            detail = "attivo per il FBO delle foto (modalità surface), nessuno spettatore"
        else:
            detail = "attivo solo per il contatore (DEBUG), nessuno spettatore"
        state(STAGE_CALLBACK, True, detail)

    def _on_preview_frame(self, data, width, height):
        # Gira sul thread UI di Android: solo contatore e consegna, niente lavoro.
        try:
            nbytes = len(data)
        except TypeError:
            nbytes = None
        self._frame_monitor.frame(nbytes)
        if self.mode == PREVIEW_SURFACE:
            self._latest_nv21 = data
        encoder = self._encoder
        if self._stream_wanted and encoder is not None:
            encoder.submit((data, width, height))

    def _report_preview_frames(self, dt):
        monitor = self._frame_monitor
        outcome, count = monitor.tick(dt, suspended=self._video_recorder is not None)
        width, height = self.preview_size
        expected = expected_frame_bytes(width, height, self._actual_format)
        summary = f"{count} in {dt:.1f} s, totale {monitor.total}"
        if outcome == "ok":
            ok(STAGE_FRAMES, f"{summary}, ultimo={monitor.last_bytes} byte (attesi {expected})")
        elif outcome == "sospeso":
            ok(STAGE_FRAMES, f"{summary}, callback sospeso: registrazione video")
        elif outcome == "zero":
            ok(STAGE_FRAMES, f"{summary}, a zero da {monitor.zero_seconds:.0f} s")
        elif outcome == "stallo":
            fail(STAGE_FRAMES, self._frame_stall_reason(expected))
        else:
            fail(STAGE_FRAMES, f"{summary}, a zero da {monitor.zero_seconds:.0f} s")

    def _frame_stall_reason(self, expected) -> str:
        width, height = self.preview_size
        supported = ", ".join(image_format_name(code) for code in self._supported_formats) or "nessuno"
        if self._callback_error is not None:
            callback = f"non registrato ({self._callback_error})"
        else:
            callback = "registrato" if self._callback_active else "non registrato"
        return (
            f"0 fotogrammi da onPreviewFrame da {self._frame_monitor.zero_seconds:.0f} s con fotocamera aperta; "
            f"formato richiesto={image_format_name(self._requested_format)} "
            f"effettivo={image_format_name(self._actual_format)} supportati=[{supported}]; "
            f"anteprima={width}x{height} attesi={expected} byte/fotogramma; callback {callback}"
        )

    @property
    def texture(self):
        if self._yuv is not None:
            return self._yuv.texture
        return self._fbo.texture if self._fbo is not None else None

    @property
    def has_frame(self) -> bool:
        return self._has_frame

    def open(self):
        if self._camera is not None:
            return
        self._opened_at = time.monotonic()
        self._first_frame_failed = False
        self._has_frame = False
        self._frame_monitor = PreviewFrameMonitor()
        try:
            self._open_camera()
            if self.mode == PREVIEW_FBO:
                self._create_gl_pipeline()
                try:
                    self._camera.setPreviewTexture(self._surface_texture)
                    self._camera.startPreview()
                except CAMERA_ERRORS as exc:
                    fail(STAGE_FIRST_FRAME, f"startPreview fallito: {exc}")
                    raise
            else:
                self._create_yuv_pipeline()
        except CAMERA_ERRORS:
            self.close()
            raise
        self._sync_preview_callback()
        if self.mode == PREVIEW_FBO:
            Clock.schedule_interval(self._tick, 0)
        else:
            Clock.schedule_interval(self._tick_yuv, SURFACE_FBO_INTERVAL)
            self._attach_native_surface()
        if DEBUG:
            Clock.schedule_interval(self._report_preview_frames, FRAME_REPORT_SECONDS)

    def close(self):
        Clock.unschedule(self._tick)
        Clock.unschedule(self._tick_yuv)
        Clock.unschedule(self._report_preview_frames)
        if self._video_recorder is not None:
            self.stop_video()
        with self._camera_lock:
            camera, self._camera = self._camera, None
            self._surface_preview_running = False
        if camera is not None:
            if self._callback_active:
                Logger.info("Stream: callback anteprima spento (fotocamera chiusa)")
                state(STAGE_CALLBACK, True, "spento: fotocamera chiusa")
            self._callback_active = False
            try:
                camera.setPreviewCallback(None)
                camera.stopPreview()
                camera.release()
            except JAVA_ERRORS:
                Logger.exception("Camera: rilascio fotocamera fallito")
        if self._native_surface is not None:
            self._native_surface.detach()
            self._native_surface = None
        self._yuv = None
        self._latest_nv21 = None
        self._uploaded_nv21 = None
        self._has_frame = False
        if self._surface_texture is not None:
            self._surface_texture.release()
            self._surface_texture = None
        if self._tex_id is not None:
            glDeleteTextures([self._tex_id])
            self._tex_id = None
        self._fbo = None
        self._last_st_values = None

    def _find_back_camera(self) -> tuple[int, int]:
        info = CameraInfo()
        for camera_id in range(Camera.getNumberOfCameras()):
            Camera.getCameraInfo(camera_id, info)
            if info.facing == CameraInfo.CAMERA_FACING_BACK:
                return camera_id, int(info.orientation)
        raise CameraError("nessuna fotocamera posteriore trovata")

    def _open_camera(self):
        with stage(STAGE_CAMERA_OPEN) as probe:
            camera_id, sensor_degrees = self._find_back_camera()
            self._camera = Camera.open(camera_id)
            probe.detail = f"id={camera_id} sensore={sensor_degrees}° fotocamere={Camera.getNumberOfCameras()}"
        params = self._camera.getParameters()

        with stage(STAGE_PREVIEW_SIZE) as probe:
            profile = CamcorderProfile.get(camera_id, CamcorderProfile.QUALITY_HIGH)
            profile_size = (int(profile.videoFrameWidth), int(profile.videoFrameHeight))
            preview_sizes = _java_sizes(params.getSupportedPreviewSizes())
            video_sizes = _java_sizes(params.getSupportedVideoSizes()) or preview_sizes
            video_size = choose_size(profile_size, video_sizes)
            preferred = params.getPreferredPreviewSizeForVideo()
            preferred_size = _size_tuple(preferred) if preferred is not None else None
            preview_size = choose_preview_size(video_size, preview_sizes, preferred_size)

            params.setPreviewSize(preview_size[0], preview_size[1])
            params.setPreviewFormat(ImageFormat.NV21)
            params.setRecordingHint(True)
            focus_modes = _java_strings(params.getSupportedFocusModes())
            if FOCUS_CONTINUOUS_VIDEO in focus_modes:
                params.setFocusMode(FOCUS_CONTINUOUS_VIDEO)
            self._camera.setParameters(params)
            # Riletti dopo setParameters: alcuni driver accettano NV21 e poi consegnano altro.
            applied = self._camera.getParameters()
            self._requested_format = int(ImageFormat.NV21)
            self._actual_format = int(applied.getPreviewFormat())
            self._supported_formats = _java_ints(applied.getSupportedPreviewFormats())
            probe.detail = (
                f"anteprima={preview_size[0]}x{preview_size[1]} video={video_size[0]}x{video_size[1]} "
                f"formato richiesto={image_format_name(self._requested_format)} "
                f"effettivo={image_format_name(self._actual_format)} "
                f"profilo={profile_size[0]}x{profile_size[1]} preferita={preferred_size} "
                f"supportate={len(preview_sizes)} anteprime/{len(video_sizes)} video "
                f"fuoco={'continuous-video' if FOCUS_CONTINUOUS_VIDEO in focus_modes else 'predefinito'}"
            )

        with stage(STAGE_ROTATION) as probe:
            display = PythonActivity.mActivity.getWindowManager().getDefaultDisplay()
            display_degrees = surface_rotation_to_degrees(display.getRotation())
            rotation = orientation_hint(sensor_degrees, display_degrees)
            # Su SurfaceTexture la rotazione arriva nella matrice di getTransformMatrix, applicata dallo shader.
            self._camera.setDisplayOrientation(rotation)
            probe.detail = f"sensore={sensor_degrees}° display={display_degrees}° -> setDisplayOrientation({rotation})"

        self._profile = profile
        self._video_size = video_size
        self._rotation = rotation
        self.preview_size = preview_size
        self.content_size = rotated_size(preview_size, rotation)
        Logger.info(f"Camera: id={camera_id} video={video_size} anteprima={preview_size} rotazione={rotation}")

    def _create_gl_pipeline(self):
        width, height = self.content_size
        with stage(STAGE_TEXTURE) as probe:
            self._tex_id = int(glGenTextures(1)[0])
            if self._tex_id == 0:
                raise CameraError("glGenTextures ha restituito 0: nessun contesto GL attivo su questo thread")
            self._surface_texture = SurfaceTexture(self._tex_id)
            fbo = Fbo(size=(width, height))
            probe.detail = f"gl_id={self._tex_id} SurfaceTexture creata, fbo={width}x{height}"
        with stage(STAGE_SHADER) as probe:
            has_oes = OES_EXTENSION in gl_extensions()
            fbo.shader.fs = PREVIEW_FRAGMENT_SHADER
            if not fbo.shader.success:
                raise CameraError(
                    f"shader dell'anteprima non compilato ({OES_EXTENSION} "
                    f"{'presente' if has_oes else 'assente'}): {shader_compile_log(PREVIEW_FRAGMENT_SHADER)}"
                )
            probe.detail = f"compilato, {OES_EXTENSION} {'presente' if has_oes else 'assente'}"
        with fbo:
            Callback(self._bind_camera_texture)
            Rectangle(size=(width, height))
        fbo["camera_texture"] = CAMERA_TEXTURE_UNIT
        fbo["st_matrix"] = Matrix()
        self._fbo = fbo

    def _bind_camera_texture(self, instruction):
        glActiveTexture(GL_TEXTURE0 + CAMERA_TEXTURE_UNIT)
        glBindTexture(GL_TEXTURE_EXTERNAL_OES, self._tex_id)
        glActiveTexture(GL_TEXTURE0)

    def _create_yuv_pipeline(self):
        with stage(STAGE_TEXTURE) as probe:
            renderer = YuvPreviewRenderer(self.preview_size, self._rotation)
            width, height = self.preview_size
            probe.detail = (
                f"modalità surface: Y {width}x{height} luminance, VU {width // 2}x{height // 2} luminance_alpha, "
                f"fbo={renderer.content_size[0]}x{renderer.content_size[1]}"
            )
        with stage(STAGE_SHADER) as probe:
            renderer.compile()
            probe.detail = "shader YUV->RGB compilato (modalità surface)"
        self._yuv = renderer
        self._yuv_error_reported = False

    def _attach_native_surface(self):
        x, y, width, height, window_height = self._surface_rect()
        fit = contain_rect(self.content_size, (x, y, width, height))
        left, top, view_w, view_h = kivy_rect_to_android(fit, window_height)
        self._native_surface = NativePreviewSurface(self._on_surface_created, self._on_surface_destroyed)
        self._native_surface.attach(left, top, view_w, view_h, self._surface_hidden)
        Logger.info(f"Camera: SurfaceView richiesta in left={left} top={top} {view_w}x{view_h}")

    def set_surface_hidden(self, hidden: bool) -> None:
        self._surface_hidden = hidden
        if self._native_surface is not None:
            self._native_surface.set_hidden(hidden)

    def _on_surface_created(self, holder):
        # Thread UI: la fotocamera si tocca solo dal thread di Kivy, quindi si rimanda lì.
        Clock.schedule_once(lambda dt: self._start_surface_preview(holder), 0)

    def _start_surface_preview(self, holder):
        with self._camera_lock:
            if self._camera is None or self._surface_preview_running:
                return
            try:
                self._camera.setPreviewDisplay(holder)
                self._camera.startPreview()
            except JAVA_ERRORS as exc:
                Logger.exception("Camera: startPreview su SurfaceView fallito")
                fail(STAGE_FIRST_FRAME, f"startPreview su SurfaceView fallito: {exc}")
                return
            self._surface_preview_running = True
        Logger.info("Camera: anteprima avviata su SurfaceView")

    def _on_surface_destroyed(self, holder):
        # Thread UI: Android invalida la superficie appena questo metodo ritorna, quindi l'anteprima va fermata qui.
        with self._camera_lock:
            if self._camera is None or not self._surface_preview_running:
                return
            try:
                self._camera.stopPreview()
                self._camera.setPreviewDisplay(None)
            except JAVA_ERRORS:
                Logger.exception("Camera: stop anteprima su SurfaceView fallito")
            self._surface_preview_running = False

    def _tick_yuv(self, dt):
        renderer = self._yuv
        if renderer is None:
            return False
        data = self._latest_nv21
        if data is None or data is self._uploaded_nv21:
            if not self._has_frame:
                self._check_first_frame_timeout("onPreviewFrame non ha ancora consegnato fotogrammi al FBO")
            return None
        self._uploaded_nv21 = data
        try:
            renderer.upload(java_bytes(data))
        except ValueError as exc:
            if not self._yuv_error_reported:
                self._yuv_error_reported = True
                Logger.error(f"Camera: fotogramma NV21 scartato: {exc}")
                fail(STAGE_FIRST_FRAME, f"{exc}; formato effettivo={image_format_name(self._actual_format)}")
            return None
        if not self._has_frame:
            self._has_frame = True
            elapsed = time.monotonic() - self._opened_at
            ok(STAGE_FIRST_FRAME, f"dopo {elapsed * 1000:.0f} ms, onPreviewFrame -> FBO YUV")
        self._on_frame()
        return None

    def _check_first_frame_timeout(self, reason: str) -> None:
        elapsed = time.monotonic() - self._opened_at
        if elapsed > FIRST_FRAME_TIMEOUT and not self._first_frame_failed:
            self._first_frame_failed = True
            fail(STAGE_FIRST_FRAME, f"nessun fotogramma dopo {FIRST_FRAME_TIMEOUT:.0f} s: {reason}")

    def _tick(self, dt):
        if self._surface_texture is None or self._fbo is None:
            return False
        try:
            self._surface_texture.updateTexImage()
            self._surface_texture.getTransformMatrix(self._st_values)
        except JAVA_ERRORS:
            Logger.exception("Camera: aggiornamento texture fallito")
            return None
        values = list(self._st_values)
        if not self._has_frame:
            self._check_first_frame(real_matrix=any(values))
        if not any(values):
            # pyjnius non ha ricopiato il float[] nella lista: senza matrice l'anteprima esce ruotata e capovolta.
            values = list(surface_texture_fallback_matrix(self._rotation))
            if not self._matrix_fallback_logged:
                Logger.warning(f"Camera: getTransformMatrix vuota, uso la matrice calcolata per rotazione={self._rotation}")
                self._matrix_fallback_logged = True
        if values != self._last_st_values:
            self._last_st_values = values
            # Kivy carica una uniform solo se l'oggetto cambia: serve una Matrix nuova.
            matrix = Matrix()
            matrix.set(flat=values)
            self._fbo["st_matrix"] = matrix
        self._fbo.ask_update()
        self._fbo.draw()
        self._on_frame()
        return None

    def _check_first_frame(self, real_matrix: bool):
        if self._surface_texture.getTimestamp() != 0:
            self._has_frame = True
            elapsed = time.monotonic() - self._opened_at
            ok(
                STAGE_FIRST_FRAME,
                f"dopo {elapsed * 1000:.0f} ms, matrice {'da getTransformMatrix' if real_matrix else 'ricostruita'}",
            )
        else:
            self._check_first_frame_timeout("SurfaceTexture.getTimestamp() è ancora 0")

    def take_photo(self, path: str):
        texture = self.texture
        if texture is None:
            raise CameraError("fotocamera non aperta")
        if not self._has_frame:
            # Prima del primo fotogramma il FBO contiene memoria non inizializzata: la foto sarebbe nera o sporca.
            raise CameraError("nessun fotogramma ancora disponibile")
        save_texture_png(texture, path)

    # Fotocamera su cui è stata accesa la torcia: dopo una chiusura e riapertura è un altro oggetto e la torcia è spenta.
    _torch_camera = None

    @property
    def torch_on(self) -> bool:
        return self._camera is not None and self._torch_camera is self._camera

    def set_torch(self, on: bool) -> None:
        if self._camera is None:
            raise CameraError("fotocamera non aperta")
        params = self._camera.getParameters()
        modes = _java_strings(params.getSupportedFlashModes())
        wanted = FLASH_MODE_TORCH if on else FLASH_MODE_OFF
        if wanted not in modes:
            raise TorchUnavailable(f"modalità flash '{wanted}' non supportata, disponibili: {modes or 'nessuna'}")
        params.setFlashMode(wanted)
        self._camera.setParameters(params)
        self._torch_camera = self._camera if on else None

    def _relock_camera(self):
        if self._camera is None:
            return
        try:
            self._camera.lock()
            self._camera.startPreview()
        except JAVA_ERRORS:
            Logger.exception("Camera: ripresa del controllo della fotocamera fallita")

    def start_video(self, path: str):
        if self._camera is None:
            raise CameraError("fotocamera non aperta")
        profile = self._profile
        if self._callback_active:
            # Con la fotocamera ceduta a MediaRecorder i callback dell'anteprima non sono garantiti.
            self._camera.setPreviewCallback(None)
            self._callback_active = False
            Logger.info("Stream: callback anteprima spento (registrazione video)")
            state(STAGE_CALLBACK, True, "spento: registrazione video in corso")
        recorder = MediaRecorder()
        try:
            self._camera.unlock()
            recorder.setCamera(self._camera)
            recorder.setAudioSource(AudioSource.CAMCORDER)
            recorder.setVideoSource(VideoSource.CAMERA)
            recorder.setOutputFormat(OutputFormat.MPEG_4)
            recorder.setVideoEncoder(VideoEncoder.H264)
            recorder.setAudioEncoder(AudioEncoder.AAC)
            recorder.setVideoSize(self._video_size[0], self._video_size[1])
            recorder.setVideoFrameRate(profile.videoFrameRate)
            recorder.setVideoEncodingBitRate(profile.videoBitRate)
            recorder.setAudioEncodingBitRate(profile.audioBitRate)
            recorder.setAudioChannels(profile.audioChannels)
            recorder.setAudioSamplingRate(profile.audioSampleRate)
            recorder.setOrientationHint(self._rotation)
            recorder.setOutputFile(path)
            recorder.prepare()
            recorder.start()
        except JAVA_ERRORS:
            recorder.reset()
            recorder.release()
            self._relock_camera()
            _remove_file(path)
            raise
        self._video_recorder = recorder
        self._video_path = path

    def stop_video(self) -> tuple[bool, str]:
        recorder, path = self._video_recorder, self._video_path
        self._video_recorder = None
        self._video_path = None
        saved = _stop_recorder(recorder)
        self._relock_camera()
        if not saved:
            _remove_file(path)
        return saved, path

    def start_audio(self, path: str):
        recorder = MediaRecorder()
        try:
            recorder.setAudioSource(AudioSource.MIC)
            recorder.setOutputFormat(OutputFormat.MPEG_4)
            recorder.setAudioEncoder(AudioEncoder.AAC)
            recorder.setAudioEncodingBitRate(AUDIO_BIT_RATE)
            recorder.setAudioSamplingRate(AUDIO_SAMPLE_RATE)
            recorder.setAudioChannels(1)
            recorder.setOutputFile(path)
            recorder.prepare()
            recorder.start()
        except JAVA_ERRORS:
            recorder.reset()
            recorder.release()
            _remove_file(path)
            raise
        self._audio_recorder = recorder
        self._audio_path = path

    def stop_audio(self) -> tuple[bool, str]:
        recorder, path = self._audio_recorder, self._audio_path
        self._audio_recorder = None
        self._audio_path = None
        saved = _stop_recorder(recorder)
        if not saved:
            _remove_file(path)
        return saved, path


class CameraPreview(Widget):
    def __init__(self, on_tap, **kwargs):
        super().__init__(**kwargs)
        self._on_tap = on_tap
        self._content_size = None
        with self.canvas:
            Color(0, 0, 0, 1)
            self._background = Rectangle()
            self._frame_color = Color(1, 1, 1, 0)
            self._frame = Rectangle()
            self._flash_color = Color(1, 1, 1, 0)
            self._flash = Rectangle()
        self._message = Label(halign="center", valign="middle", font_size="16sp")
        self.add_widget(self._message)
        self.bind(pos=self._relayout, size=self._relayout)

    def set_source(self, texture, content_size):
        self._content_size = content_size
        self._frame.texture = texture
        self._frame_color.a = 1
        self._message.text = ""
        self._relayout()

    def clear_source(self):
        self._content_size = None
        self._frame.texture = None
        self._frame_color.a = 0

    def show_message(self, text):
        self.clear_source()
        self._message.text = text

    def refresh(self):
        self.canvas.ask_update()

    def flash(self):
        self._flash_color.a = 0.75
        Clock.schedule_once(lambda dt: setattr(self._flash_color, "a", 0), 0.12)

    def _relayout(self, *_):
        for rect in (self._background, self._frame, self._flash):
            rect.pos = self.pos
            rect.size = self.size
        self._message.pos = self.pos
        self._message.size = self.size
        self._message.text_size = (self.width * 0.85, None)
        if self._content_size is not None and self.width > 0 and self.height > 0:
            u0, v0, u1, v1 = cover_tex_coords(self._content_size, (self.width, self.height))
            self._frame.tex_coords = (u0, v0, u1, v0, u1, v1, u0, v1)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._on_tap()
            return True
        return super().on_touch_down(touch)


class RoundButton(ButtonBehavior, Widget):
    active = BooleanProperty(False)

    def __init__(self, glyph, **kwargs):
        if glyph not in GLYPHS:
            raise ValueError(f"glifo sconosciuto: {glyph}")
        super().__init__(**kwargs)
        self.glyph = glyph
        self.bind(pos=self._redraw, size=self._redraw, state=self._redraw, active=self._redraw, disabled=self._redraw)
        self._redraw()

    def _redraw(self, *_):
        self.opacity = 0.35 if self.disabled else 1.0
        cx, cy = self.center
        radius = min(self.size) / 2.0
        self.canvas.clear()
        with self.canvas:
            Color(1, 1, 1, 0.3 if self.state == "down" else 0.12)
            Ellipse(pos=(cx - radius, cy - radius), size=(radius * 2, radius * 2))
            Color(1, 1, 1, 1)
            Line(circle=(cx, cy, radius - dp(2)), width=dp(2))
            if self.active:
                self._draw_stop(cx, cy, radius)
            elif self.glyph == "photo":
                self._draw_disc(cx, cy, radius * 0.62, (1, 1, 1, 1))
            elif self.glyph == "video":
                self._draw_disc(cx, cy, radius * 0.6, RECORD_RED)
            else:
                self._draw_microphone(cx, cy, radius)

    def _draw_disc(self, cx, cy, r, rgba):
        Color(*rgba)
        Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))

    def _draw_stop(self, cx, cy, radius):
        side = radius * 0.72
        Color(*RECORD_RED)
        RoundedRectangle(pos=(cx - side / 2, cy - side / 2), size=(side, side), radius=[dp(6)])

    def _draw_microphone(self, cx, cy, radius):
        Color(1, 1, 1, 1)
        mic_w = radius * 0.36
        mic_h = radius * 0.62
        mic_bottom = cy - radius * 0.18
        RoundedRectangle(pos=(cx - mic_w / 2, mic_bottom), size=(mic_w, mic_h), radius=[mic_w / 2])
        arc_cy = mic_bottom + mic_w / 2
        arc_r = mic_w / 2 + radius * 0.12
        Line(circle=(cx, arc_cy, arc_r, 90, 270), width=dp(1.6))
        stem_top = arc_cy - arc_r
        stem_bottom = stem_top - radius * 0.14
        Line(points=[cx, stem_top, cx, stem_bottom], width=dp(1.6))
        Line(points=[cx - radius * 0.15, stem_bottom, cx + radius * 0.15, stem_bottom], width=dp(1.6))


class BlinkDot(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._event = None
        with self.canvas:
            self._color = Color(*RECORD_RED)
            self._dot = Ellipse()
        self.bind(pos=self._relayout, size=self._relayout)

    def _relayout(self, *_):
        diameter = min(self.size)
        self._dot.size = (diameter, diameter)
        self._dot.pos = (self.center_x - diameter / 2, self.center_y - diameter / 2)

    def start(self):
        self.stop()
        self._event = Clock.schedule_interval(self._toggle, 0.5)

    def stop(self):
        if self._event is not None:
            self._event.cancel()
            self._event = None
        self._color.a = 1

    def _toggle(self, dt):
        self._color.a = 0.0 if self._color.a > 0.5 else 1.0


class RecordingBadge(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(
            orientation="horizontal",
            size_hint=(None, None),
            size=(dp(132), dp(40)),
            padding=(dp(14), dp(8)),
            spacing=dp(10),
            **kwargs,
        )
        with self.canvas.before:
            Color(0, 0, 0, 0.55)
            self._background = RoundedRectangle(radius=[dp(20)])
        self.bind(pos=self._relayout, size=self._relayout)
        self.dot = BlinkDot(size_hint=(None, 1), width=dp(14))
        self.time_label = Label(text=format_duration(0), font_size="18sp", bold=True)
        self.add_widget(self.dot)
        self.add_widget(self.time_label)
        self.opacity = 0

    def _relayout(self, *_):
        self._background.pos = self.pos
        self._background.size = self.size

    def show(self):
        self.set_elapsed(0)
        self.opacity = 1
        self.dot.start()

    def hide(self):
        self.dot.stop()
        self.opacity = 0

    def set_elapsed(self, seconds):
        self.time_label.text = format_duration(seconds)


class Toast(Label):
    def __init__(self, **kwargs):
        super().__init__(
            size_hint=(None, None),
            halign="center",
            valign="middle",
            font_size="14sp",
            padding=(dp(14), dp(10)),
            **kwargs,
        )
        self._hide_event = None
        with self.canvas.before:
            Color(0, 0, 0, 0.65)
            self._background = RoundedRectangle(radius=[dp(12)])
        self.bind(pos=self._relayout, size=self._relayout, texture_size=self._fit)
        self.opacity = 0

    def _relayout(self, *_):
        self._background.pos = self.pos
        self._background.size = self.size

    def _fit(self, *_):
        self.size = self.texture_size
        if self.parent is not None:
            self.center_x = self.parent.center_x

    def show(self, text, max_width, duration=3.5):
        self.text_size = (max_width, None)
        self.text = text
        self.opacity = 1
        self._fit()
        if self._hide_event is not None:
            self._hide_event.cancel()
        self._hide_event = Clock.schedule_once(self._hide, duration)

    def _hide(self, dt):
        self.opacity = 0
        self._hide_event = None


class StreamCard(ButtonBehavior, BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(
            orientation="vertical",
            size_hint=(0.9, None),
            height=dp(200),
            padding=(dp(16), dp(18)),
            spacing=dp(4),
            **kwargs,
        )
        with self.canvas.before:
            Color(0.07, 0.08, 0.1, 0.9)
            self._background = RoundedRectangle(radius=[dp(20)])
        self.bind(pos=self._relayout, size=self._relayout)
        self.title_label = Label(text="Apri dal PC", font_size="15sp", color=(1, 1, 1, 0.75), size_hint_y=None, height=dp(24))
        self.ip_label = Label(font_size="40sp", bold=True)
        # Due righe: l'URL con il token non sta in una sola accanto al numero di spettatori.
        self.detail_label = Label(
            font_size="15sp", color=(1, 1, 1, 0.85), size_hint_y=None, height=dp(44), halign="center", valign="middle"
        )
        self.detail_label.bind(width=lambda label, width: setattr(label, "text_size", (width, None)))
        self.hint_label = Label(text="Tocca per ridurre", font_size="12sp", color=(1, 1, 1, 0.5), size_hint_y=None, height=dp(20))
        for label in (self.title_label, self.ip_label, self.detail_label, self.hint_label):
            self.add_widget(label)

    def _relayout(self, *_):
        self._background.pos = self.pos
        self._background.size = self.size

    def set_texts(self, title, big, detail):
        self.title_label.text = title
        self.ip_label.text = big
        self.detail_label.text = detail


class StreamChip(ButtonBehavior, Label):
    def __init__(self, **kwargs):
        super().__init__(size_hint=(None, None), font_size="14sp", padding=(dp(14), dp(8)), **kwargs)
        with self.canvas.before:
            Color(0, 0, 0, 0.6)
            self._background = RoundedRectangle(radius=[dp(16)])
        self.bind(pos=self._relayout, size=self._relayout, texture_size=self._fit)

    def _relayout(self, *_):
        self._background.pos = self.pos
        self._background.size = self.size

    def _fit(self, *_):
        self.size = self.texture_size


def battery_status() -> dict | None:
    if not IS_ANDROID:
        return None
    try:
        manager = cast(BatteryManager, PythonActivity.mActivity.getSystemService(Context.BATTERY_SERVICE))
        return {
            "percent": int(manager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)),
            "charging": bool(manager.isCharging()),
        }
    except JAVA_ERRORS:
        Logger.exception("Comandi: lettura batteria fallita")
        return None


def storage_status(path: str) -> dict | None:
    try:
        stats = os.statvfs(path)
    except OSError:
        return None
    return {"free_bytes": stats.f_bavail * stats.f_frsize, "total_bytes": stats.f_blocks * stats.f_frsize}


class AppController:
    """Comandi remoti tradotti in chiamate all'app. Tutti tranne media_dirs girano sul thread di Kivy."""

    def __init__(self, app):
        self._app = app

    def photo(self) -> dict:
        return {"file": media_entry("photos", self._app._photo())}

    def video_start(self) -> dict:
        return {"mode": MODE_VIDEO, "file": media_entry("videos", self._app._start_video())}

    def video_stop(self) -> dict:
        return self._app._stop_mode(MODE_VIDEO, "videos")

    def audio_start(self) -> dict:
        return {"mode": MODE_AUDIO, "file": media_entry("audio", self._app._start_audio())}

    def audio_stop(self) -> dict:
        return self._app._stop_mode(MODE_AUDIO, "audio")

    def torch(self, on: bool) -> dict:
        return {"torch": self._app._set_torch(on)}

    def status(self) -> dict:
        return self._app._remote_status()

    def media_dirs(self) -> dict:
        # Cartelle fissate alla creazione del backend: leggerle dal thread del server non tocca la fotocamera.
        backend = self._app._backend
        if backend is None:
            return {}
        return {"photos": backend.photo_dir, "videos": backend.video_dir, "audio": backend.audio_dir}


def encoder_health(encoder: LatestFrameEncoder) -> tuple[bool, str]:
    if not encoder.is_alive:
        return False, "thread mjpeg-encoder terminato"
    if encoder.last_error_at is not None and (
        encoder.last_encoded_at is None or encoder.last_error_at > encoder.last_encoded_at
    ):
        return False, f"thread vivo ma la codifica fallisce: {encoder.last_error}"
    if encoder.last_encoded_at is None:
        return True, "thread vivo, nessun fotogramma da codificare"
    return True, "thread vivo, codifica JPEG riuscita"


def stream_texts(
    ip: str | None, port: int | None, clients: int, error: str | None, token: str | None = None
) -> tuple[str, str, str, str]:
    """Restituisce (titolo, testo grande, dettaglio, testo compatto) per la scheda dello stream."""
    if error is not None:
        return "Server non avviato", "Errore", error, "Server non avviato"
    if ip is None:
        return "Nessuna rete", "Wi-Fi assente", "Collega il telefono alla stessa rete del PC", "Wi-Fi assente"
    viewers = "nessuno spettatore" if clients == 0 else f"spettatori: {clients}"
    url = stream_url(ip, port, token)
    return "Apri dal PC", ip, f"{url}\n{viewers}", f"{ip}:{port}  ·  {viewers}"


class GiocoCameraApp(App):
    title = "Gioco"

    def build(self):
        from kivy.core.window import Window

        self._window = Window
        Window.clearcolor = (0, 0, 0, 1)
        self._backend = None
        self._mode = MODE_IDLE
        self._record_started = 0.0
        self._timer_event = None
        self._camera_allowed = False
        self._mic_allowed = False

        root = FloatLayout()
        self._preview = CameraPreview(on_tap=self._on_preview_tap)
        root.add_widget(self._preview)

        top = AnchorLayout(anchor_x="center", anchor_y="top", padding=dp(20))
        self._badge = RecordingBadge()
        top.add_widget(self._badge)
        root.add_widget(top)

        self._toast = Toast()
        self._toast.y = dp(BAR_HEIGHT_DP) + dp(16)
        if PREVIEW_MODE == PREVIEW_SURFACE:
            # La SurfaceView copre l'area sopra la barra: gli avvisi vanno nella fascia alta, che resta di Kivy.
            self._toast.bind(size=lambda toast, size: setattr(toast, "top", Window.height - dp(8)))
        root.add_widget(self._toast)

        root.add_widget(self._build_bottom_bar())
        Window.bind(on_keyboard=self._on_keyboard)

        if IS_ANDROID:
            self._backend = CameraBackend(
                on_frame=self._preview.refresh, mode=PREVIEW_MODE, surface_rect=self._surface_preview_rect
            )
        else:
            self._preview.show_message("Anteprima disponibile solo su Android")
        self._refresh_controls()

        self._root = root
        self._stream_card = StreamCard(pos_hint={"center_x": 0.5, "center_y": 0.55})
        self._stream_card.bind(on_release=lambda *_: self._show_stream_card(False))
        self._stream_chip = StreamChip()
        self._stream_chip.bind(on_release=lambda *_: self._show_stream_card(True))
        self._stream_chip.bind(size=self._place_stream_chip)
        root.bind(size=self._place_stream_chip)
        self._start_stream_server()
        self._show_stream_card(True)
        self._refresh_stream(0)
        self._stream_event = Clock.schedule_interval(self._refresh_stream, STREAM_REFRESH_SECONDS)
        return root

    def _start_stream_server(self):
        ok(STAGE_DEBUG, f"diagnostica attiva, uscita={output_name()}, android={IS_ANDROID}")
        self._broker = FrameBroker()
        self._encoder = None
        self._stream_error = None
        self._lan_addresses = None
        if IS_ANDROID:
            # detach: un thread Python che ha chiamato Java e termina senza staccarsi dalla JVM fa crashare il processo.
            self._encoder = LatestFrameEncoder(self._broker, nv21_to_jpeg, STREAM_MAX_FPS, on_thread_exit=detach)
            self._encoder.start()
            self._backend.attach_encoder(self._encoder)
        self._stream_token = new_token()
        api = CommandApi(AppController(self), MainThreadRunner())
        self._server = MjpegServer(self._broker, self._stream_info, token=self._stream_token, api=api)
        try:
            self._server.start()
            # Per adb forward dal PC, che non vede la scheda sul telefono. Logcat è leggibile solo via adb.
            Logger.info(f"Stream: token={self._stream_token} porta={self._server.port}")
        except OSError as exc:
            Logger.exception("Stream: avvio server fallito")
            self._stream_error = str(exc)

    def _stream_info(self) -> dict:
        if self._backend is None:
            return {"rotation": 0}
        return self._backend.stream_info()

    def _show_stream_card(self, expanded):
        for widget in (self._stream_card, self._stream_chip):
            if widget.parent is not None:
                widget.parent.remove_widget(widget)
        self._root.add_widget(self._stream_card if expanded else self._stream_chip)
        self._place_stream_chip()
        if self._backend is not None and self._backend.mode == PREVIEW_SURFACE:
            # La scheda IP sta sotto la SurfaceView: mentre è aperta, la SurfaceView si sposta fuori schermo.
            self._backend.set_surface_hidden(expanded)

    def _surface_preview_rect(self) -> tuple[int, int, int, int, int]:
        """Riquadro Kivy (x, y, larghezza, altezza) libero per la SurfaceView, più l'altezza della finestra."""
        window_w, window_h = (int(v) for v in self._window.size)
        bottom = int(dp(BAR_HEIGHT_DP))
        height = window_h - bottom - int(dp(TOP_BAND_DP))
        return 0, bottom, window_w, height, window_h

    def _place_stream_chip(self, *_):
        chip = self._stream_chip
        chip.center_x = self._root.center_x
        chip.top = self._root.top - dp(20) - dp(40) - dp(10)

    def _refresh_stream(self, dt):
        clients = self._broker.clients
        addresses = lan_addresses()
        if addresses != self._lan_addresses:
            Logger.info(f"Stream: indirizzi locali {addresses}")
            self._lan_addresses = addresses
        ip = addresses[0] if addresses else None
        title, big, detail, compact = stream_texts(
            ip, self._server.port, clients, self._stream_error, self._stream_token
        )
        self._stream_card.set_texts(title, big, detail)
        self._stream_chip.text = compact
        if self._backend is not None:
            self._backend.set_streaming(clients > 0 and self._mode != MODE_VIDEO)
        if DEBUG:
            self._report_pipeline(ip, clients)

    def _report_pipeline(self, ip, clients):
        if self._stream_error is not None:
            state(STAGE_CLIENTS, False, f"server non avviato: {self._stream_error}")
        else:
            address = stream_url(ip, self._server.port, self._stream_token) if ip else "nessun IP locale raggiungibile"
            state(STAGE_CLIENTS, True, f"{clients} collegati, {address}")
        if self._encoder is not None:
            state(STAGE_ENCODER, *encoder_health(self._encoder))

    def _build_bottom_bar(self):
        bar = BoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(BAR_HEIGHT_DP),
            pos_hint={"x": 0, "y": 0},
            padding=(dp(24), dp(12), dp(24), dp(18)),
        )
        with bar.canvas.before:
            Color(0, 0, 0, 0.5)
            background = Rectangle()
        bar.bind(pos=lambda w, value: setattr(background, "pos", value))
        bar.bind(size=lambda w, value: setattr(background, "size", value))

        self._photo_button = RoundButton("photo", size_hint=(None, None), size=(dp(64), dp(64)))
        self._video_button = RoundButton("video", size_hint=(None, None), size=(dp(80), dp(80)))
        self._audio_button = RoundButton("audio", size_hint=(None, None), size=(dp(64), dp(64)))
        self._photo_button.bind(on_release=lambda *_: self._take_photo())
        self._video_button.bind(on_release=lambda *_: self._toggle_video())
        self._audio_button.bind(on_release=lambda *_: self._toggle_audio())

        for button, caption in (
            (self._photo_button, "Foto"),
            (self._video_button, "Video"),
            (self._audio_button, "Audio"),
        ):
            slot = BoxLayout(orientation="vertical", spacing=dp(6))
            holder = AnchorLayout(anchor_x="center", anchor_y="center")
            holder.add_widget(button)
            slot.add_widget(holder)
            slot.add_widget(Label(text=caption, font_size="13sp", size_hint_y=None, height=dp(18)))
            bar.add_widget(slot)
        return bar

    def notify(self, text):
        self._toast.show(text, max_width=self._window.width * 0.85)

    def _refresh_controls(self):
        camera_ready = self._backend is not None and self._backend.is_open
        self._photo_button.disabled = not camera_ready
        self._video_button.disabled = not (
            camera_ready and self._mic_allowed and self._mode in (MODE_IDLE, MODE_VIDEO)
        )
        self._audio_button.disabled = not (
            self._backend is not None and self._mic_allowed and self._mode in (MODE_IDLE, MODE_AUDIO)
        )
        self._video_button.active = self._mode == MODE_VIDEO
        self._audio_button.active = self._mode == MODE_AUDIO

    def on_start(self):
        if IS_ANDROID:
            # Con lo schermo spento l'Activity va in pausa e la fotocamera viene rilasciata: lo stream si fermerebbe.
            keep_screen_on()
            self._request_permissions()

    def _request_permissions(self):
        request_permissions([Permission.CAMERA, Permission.RECORD_AUDIO], self._on_permissions_result)

    @mainthread
    def _on_permissions_result(self, permissions, grant_results):
        self._apply_permissions()

    def _apply_permissions(self):
        # Rilette ogni volta: l'utente può revocarle dalle impostazioni mentre l'app è in pausa.
        self._camera_allowed = check_permission(Permission.CAMERA)
        self._mic_allowed = check_permission(Permission.RECORD_AUDIO)
        if self._camera_allowed:
            self._open_camera()
        else:
            self._preview.show_message("Permesso fotocamera negato.\nTocca qui per chiederlo di nuovo.")
        if not self._mic_allowed:
            self.notify("Microfono negato: video e audio disattivati")
        self._refresh_controls()

    def _open_camera(self):
        if self._backend.is_open:
            return
        try:
            self._backend.open()
        except CAMERA_ERRORS as exc:
            Logger.exception("Camera: apertura fallita")
            self._preview.show_message(f"Errore apertura fotocamera:\n{exc}")
            return
        if self._backend.mode == PREVIEW_FBO:
            self._preview.set_source(self._backend.texture, self._backend.content_size)
        else:
            self._preview.clear_source()
            self._backend.set_surface_hidden(self._stream_card.parent is not None)

    def _on_preview_tap(self):
        if IS_ANDROID and not self._camera_allowed:
            self._request_permissions()

    def _take_photo(self):
        try:
            self._photo()
        except CommandError:
            return

    def _toggle_video(self):
        if self._mode == MODE_VIDEO:
            self._stop_recording()
            return
        try:
            self._start_video()
        except CommandError:
            return

    def _toggle_audio(self):
        if self._mode == MODE_AUDIO:
            self._stop_recording()
            return
        try:
            self._start_audio()
        except CommandError:
            return

    def _require_backend(self):
        if self._backend is None:
            raise CommandError(503, "non_disponibile", "fotocamera e microfono disponibili solo su Android")

    def _require_camera(self):
        self._require_backend()
        if not self._backend.is_open:
            raise CommandError(409, "fotocamera_chiusa", "fotocamera non aperta: app in pausa o permesso negato")

    def _require_idle(self, wanted: str):
        if self._mode == wanted:
            raise CommandError(409, "gia_attivo", f"registrazione {wanted} già in corso")
        if self._mode != MODE_IDLE:
            raise CommandError(409, "occupato", f"registrazione {self._mode} in corso")

    def _require_microphone(self):
        if not self._mic_allowed:
            raise CommandError(409, "microfono_negato", "permesso microfono negato")

    def _photo(self) -> str:
        """Thread di Kivy. Restituisce il percorso della foto o solleva CommandError."""
        self._require_camera()
        path = os.path.join(self._backend.photo_dir, media_filename("IMG", "png", datetime.now()))
        try:
            self._backend.take_photo(path)
        except Exception as exc:
            # I provider immagine di Kivy sollevano eccezioni di tipo diverso a seconda del backend.
            Logger.exception("Camera: salvataggio foto fallito")
            self.notify(f"Errore foto: {exc}")
            if not self._backend.has_frame:
                raise CommandError(409, "nessun_fotogramma", str(exc)) from exc
            raise CommandError(500, "errore", f"salvataggio foto fallito: {exc}") from exc
        self._preview.flash()
        self.notify(f"Foto salvata:\n{path}")
        return path

    def _start_video(self) -> str:
        """Thread di Kivy. Restituisce il percorso del video o solleva CommandError."""
        self._require_idle(MODE_VIDEO)
        self._require_camera()
        self._require_microphone()
        path = os.path.join(self._backend.video_dir, media_filename("VID", "mp4", datetime.now()))
        try:
            self._backend.start_video(path)
        except CAMERA_ERRORS as exc:
            Logger.exception("Camera: avvio video fallito")
            self.notify(f"Errore avvio video: {exc}")
            raise CommandError(500, "errore", f"avvio video fallito: {exc}") from exc
        self._enter_recording(MODE_VIDEO)
        return path

    def _start_audio(self) -> str:
        """Thread di Kivy. Restituisce il percorso dell'audio o solleva CommandError."""
        self._require_idle(MODE_AUDIO)
        self._require_backend()
        self._require_microphone()
        path = os.path.join(self._backend.audio_dir, media_filename("AUD", "m4a", datetime.now()))
        try:
            self._backend.start_audio(path)
        except CAMERA_ERRORS as exc:
            Logger.exception("Camera: avvio audio fallito")
            self.notify(f"Errore avvio audio: {exc}")
            raise CommandError(500, "errore", f"avvio audio fallito: {exc}") from exc
        self._enter_recording(MODE_AUDIO)
        return path

    def _stop_mode(self, mode: str, dirname: str) -> dict:
        """Thread di Kivy. Ferma la registrazione di quel tipo o solleva CommandError."""
        if self._mode != mode:
            raise CommandError(409, "non_attivo", f"nessuna registrazione {mode} in corso")
        result = self._stop_recording()
        return {
            "mode": MODE_IDLE,
            "saved": result["saved"],
            "seconds": round(result["seconds"], 1),
            "file": media_entry(dirname, result["path"]) if result["saved"] else None,
        }

    def _set_torch(self, on: bool) -> bool:
        """Thread di Kivy. Restituisce lo stato della torcia dopo il comando."""
        self._require_camera()
        try:
            self._backend.set_torch(on)
        except TorchUnavailable as exc:
            raise CommandError(409, "torcia_non_disponibile", str(exc)) from exc
        except CAMERA_ERRORS as exc:
            Logger.exception("Camera: torcia fallita")
            raise CommandError(500, "errore", f"torcia: {exc}") from exc
        self.notify("Torcia accesa" if on else "Torcia spenta")
        return self._backend.torch_on

    def _remote_status(self) -> dict:
        """Thread di Kivy: legge lo stato dell'app e della fotocamera senza modificarlo."""
        backend = self._backend
        camera = {
            "open": False,
            "has_frame": False,
            "preview_mode": PREVIEW_MODE,
            "preview_size": None,
            "rotation": None,
            "torch": False,
        }
        if backend is not None:
            camera.update(
                open=backend.is_open,
                has_frame=backend.has_frame,
                preview_mode=backend.mode,
                preview_size=list(backend.preview_size) if backend.preview_size else None,
                rotation=backend.stream_info().get("rotation"),
                torch=backend.torch_on,
            )
        recording = time.monotonic() - self._record_started if self._mode != MODE_IDLE else 0.0
        return {
            "platform": "android" if IS_ANDROID else "desktop",
            "mode": self._mode,
            "recording_seconds": round(recording, 1),
            "battery": battery_status(),
            "storage": storage_status(backend.photo_dir if backend is not None else os.getcwd()),
            "camera": camera,
            "permissions": {"camera": self._camera_allowed, "microphone": self._mic_allowed},
            "stream": {"clients": self._broker.clients, "port": self._server.port},
        }

    def _enter_recording(self, mode):
        self._mode = mode
        self._record_started = time.monotonic()
        self._badge.show()
        self._timer_event = Clock.schedule_interval(self._update_timer, 0.25)
        self._refresh_controls()

    def _update_timer(self, dt):
        self._badge.set_elapsed(time.monotonic() - self._record_started)

    def _stop_recording(self):
        mode = self._mode
        if mode == MODE_VIDEO:
            saved, path = self._backend.stop_video()
            label = "Video"
        elif mode == MODE_AUDIO:
            saved, path = self._backend.stop_audio()
            label = "Audio"
        else:
            return None
        seconds = time.monotonic() - self._record_started
        self._mode = MODE_IDLE
        if self._timer_event is not None:
            self._timer_event.cancel()
            self._timer_event = None
        self._badge.hide()
        self._refresh_controls()
        if saved:
            self.notify(f"{label} salvato:\n{path}")
        else:
            self.notify("Registrazione troppo breve: file scartato")
        return {"mode": mode, "saved": saved, "path": path, "seconds": seconds}

    def _release_everything(self):
        if self._mode != MODE_IDLE:
            self._stop_recording()
        if self._backend is not None:
            self._backend.close()
            self._preview.clear_source()
        self._refresh_controls()

    def _on_keyboard(self, window, key, *args):
        if key != KEY_BACK:
            return False
        if self._mode != MODE_IDLE:
            self._stop_recording()
            return True
        if IS_ANDROID:
            PythonActivity.mActivity.moveTaskToBack(True)
            return True
        return False

    def on_pause(self):
        self._release_everything()
        return True

    def on_resume(self):
        if IS_ANDROID:
            self._apply_permissions()

    def on_stop(self):
        self._release_everything()
        self._stream_event.cancel()
        self._server.stop()
        if self._encoder is not None:
            self._encoder.stop()


if __name__ == "__main__":
    GiocoCameraApp().run()
