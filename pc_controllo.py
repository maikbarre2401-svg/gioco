#!/usr/bin/env python3
"""Pannello di controllo dal PC per l'app Gioco sul telefono: stream, comandi e file.

Avvio con doppio clic, oppure: python pc_controllo.py
Pillow serve solo a mostrare lo stream nella finestra (pip install pillow); senza Pillow
il pulsante "Apri nel browser" mostra lo stream nella pagina servita dal telefono.

La sezione "Telefono e APK" compila l'APK con buildozer dentro WSL2 (buildozer non gira su
Windows), lo installa con adb, concede i permessi, avvia l'app, legge token e porta dal log
del telefono, apre adb forward e si connette da sola.
"""

from __future__ import annotations

__version__ = "2.0.0"

import io
import json
import os
import platform
import queue
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:
    # La parte di rete resta importabile (e testabile) anche dove Tk non è installato.
    tk = None

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    from PIL import ImageTk
except ImportError:
    ImageTk = None

DEFAULT_PORT = 8080
TOKEN_PARAM = "t"
HTTP_TIMEOUT = 15.0
# Più corto dei comandi: serve ad accorgersi presto che il telefono non risponde più.
STATUS_TIMEOUT = 5.0
READ_RETRIES = 1
READ_RETRY_DELAY = 0.5
STATUS_MAX_INTERVAL_MS = 15000
STREAM_TIMEOUT = 10.0
STREAM_RETRY_SECONDS = 2.0
STREAM_RETRY_MAX_SECONDS = 10.0
STATUS_INTERVAL_MS = 2000
PUMP_INTERVAL_MS = 30
# Massimo lavoro per giro della coda: con buildozer -v arrivano migliaia di righe e Tk deve restare reattivo.
PUMP_BUDGET_SECONDS = 0.02
FPS_INTERVAL_SECONDS = 1.0
DOWNLOAD_CHUNK_BYTES = 256 * 1024
PROGRESS_STEP_BYTES = 2 * 1024 * 1024
# L'avanzamento si aggiorna al massimo 10 volte al secondo: abbastanza fluido, senza intasare la coda di Tk.
PROGRESS_INTERVAL_SECONDS = 0.1
MAX_PART_BYTES = 20 * 1024 * 1024
MEDIA_DIRS = (("photos", "Foto"), ("videos", "Video"), ("audio", "Audio"))
VIDEO_MIN_SIZE = (640, 480)
# Dimensione richiesta dal riquadro video: piccola, così su schermi bassi lo spazio va prima ai pannelli laterali.
VIDEO_REQUEST_SIZE = (480, 270)
LOG_MAX_LINES = 4000
HISTORY_LIMIT = 10
SETTINGS_VERSION = 1
GEOMETRY_PATTERN = re.compile(r"^(\d+)x(\d+)([+-]-?\d+)([+-]-?\d+)$")

APP_PACKAGE = "org.maikbarre.gioco"
APP_ACTIVITY = "org.kivy.android.PythonActivity"
APP_PERMISSIONS = ("android.permission.CAMERA", "android.permission.RECORD_AUDIO")
DEFAULT_PROJECT_DIR = "~/gioco"
DEFAULT_BUILDOZER = "~/.venvs/buildozer/bin/buildozer"
TOKEN_WAIT_SECONDS = 30.0
TOKEN_POLL_SECONDS = 1.0
OUTPUT_TAIL_LINES = 400
ERROR_TAIL_LINES = 15
GITHUB_API = "https://api.github.com"
DEFAULT_REPO = "maikbarre2401-svg/gioco"
DEFAULT_BRANCH = "claude/festive-brahmagupta-vdj2r9"
WORKFLOW_FILE = "camera-apk.yml"
ARTIFACT_PREFIX = "gioco-apk"
RUNS_TO_SCAN = 10
GITHUB_TIMEOUT = 30.0
GITHUB_RETRIES = 2
GITHUB_RETRY_DELAY = 1.0
# Dopo terminate() un processo che non esce entro questo tempo viene chiuso con kill().
PROCESS_KILL_SECONDS = 5.0
# Riga che main.py scrive all'avvio del server; Kivy la riformatta come "[INFO   ] [Stream      ] token=… porta=…".
SERVER_LINE = re.compile(r"\] token=([A-Za-z0-9_-]+) porta=(\d+)")

# Il telefono è sulla rete locale: un proxy di sistema sul PC intercetterebbe le richieste senza poterle servire.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def __str__(self) -> str:
        if self.status:
            return f"{self.message} ({self.code}, HTTP {self.status})"
        return f"{self.message} ({self.code})"


def _api_error_from_http(exc: urllib.error.HTTPError) -> ApiError:
    raw = exc.read()
    try:
        payload = json.loads(raw.decode("utf-8"))
        return ApiError(exc.code, payload.get("error", "errore"), payload.get("message", ""))
    except (ValueError, AttributeError):
        return ApiError(exc.code, "http", raw.decode("utf-8", "replace").strip() or exc.reason)


def write_bytes_atomic(path: str, data: bytes) -> None:
    """Scrive in un file temporaneo e poi lo rinomina: un errore a metà non lascia un file troncato."""
    partial = path + ".part"
    try:
        with open(partial, "wb") as handle:
            handle.write(data)
        os.replace(partial, path)
    except BaseException:
        _remove_quietly(partial)
        raise


def _remove_quietly(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def unique_path(directory: str, name: str, taken: set[str] | None = None) -> str:
    """Percorso libero in directory: 'VID.mp4', poi 'VID (2).mp4', 'VID (3).mp4'... Non sovrascrive mai."""
    taken = taken if taken is not None else set()
    stem, ext = os.path.splitext(os.path.basename(name))
    candidate = os.path.join(directory, f"{stem}{ext}")
    counter = 2
    while os.path.exists(candidate) or candidate in taken:
        candidate = os.path.join(directory, f"{stem} ({counter}){ext}")
        counter += 1
    return candidate


class ProgressThrottle:
    """Lascia passare un aggiornamento di avanzamento al massimo ogni PROGRESS_INTERVAL_SECONDS, più l'ultimo."""

    def __init__(self, callback: Callable[[int, int], None] | None, clock: Callable[[], float] = time.monotonic):
        self._callback = callback
        self._clock = clock
        self._last = float("-inf")

    def __call__(self, done: int, total: int, final: bool = False) -> None:
        if self._callback is None:
            return
        now = self._clock()
        if final or now - self._last >= PROGRESS_INTERVAL_SECONDS:
            self._last = now
            self._callback(done, total)


def format_host(host: str) -> str:
    """Host per un URL: gli IPv6 vanno tra parentesi quadre."""
    if ":" in host and not host.startswith("["):
        return f"[{host}]"
    return host


def parse_phone_address(text: str) -> tuple[str, int | None, str | None]:
    """Host, porta e token da quello che l'utente scrive o incolla nel campo IP.

    Accetta '192.168.1.23', '192.168.1.23:8080', '[fe80::1]:8080', 'fe80::1' e l'URL completo
    mostrato dalla scheda sul telefono ('http://192.168.1.23:8080/?t=Ab3_x9Qz').
    """
    text = text.strip()
    if not text:
        raise ValueError("indirizzo vuoto")
    if "://" in text:
        parts = urllib.parse.urlsplit(text)
        if not parts.hostname:
            raise ValueError(f"URL senza host: {text}")
        token = urllib.parse.parse_qs(parts.query).get(TOKEN_PARAM, [None])[0]
        return parts.hostname, parts.port, token
    if text.startswith("["):
        host, _, rest = text[1:].partition("]")
        port_text = rest[1:] if rest.startswith(":") else ""
        return host, int(port_text) if port_text else None, None
    if text.count(":") == 1:
        host, _, port_text = text.partition(":")
        return host, int(port_text), None
    return text, None, None


class PhoneClient:
    """Client HTTP del telefono. Ogni metodo blocca: va chiamato da un thread di rete, mai da Tk."""

    def __init__(self, host: str, port: int, token: str, sleep: Callable[[float], None] = time.sleep):
        self.base = f"http://{format_host(host)}:{port}"
        self.token = token
        self._sleep = sleep

    def url(self, endpoint: str, **params) -> str:
        # "endpoint" e non "path": /files/get ha un parametro di query che si chiama proprio path.
        query = urllib.parse.urlencode({TOKEN_PARAM: self.token, **params})
        return f"{self.base}{endpoint}?{query}"

    def page_url(self) -> str:
        return self.url("/")

    def _open(self, request: urllib.request.Request, timeout: float):
        try:
            return _OPENER.open(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            raise _api_error_from_http(exc) from None
        except (urllib.error.URLError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise ApiError(0, "rete", f"telefono non raggiungibile: {reason}") from None

    def _json(self, request: urllib.request.Request, timeout: float = HTTP_TIMEOUT, retries: int = 0) -> dict:
        """Risposta JSON. retries ripete solo gli errori di rete: da usare solo per le letture, mai per i comandi."""
        attempt = 0
        while True:
            try:
                with self._open(request, timeout) as response:
                    raw = response.read()
                    status = response.status
                break
            except ApiError as exc:
                if exc.code != "rete" or attempt >= retries:
                    raise
                attempt += 1
                self._sleep(READ_RETRY_DELAY * attempt)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise ApiError(status, "risposta", "risposta non valida dal telefono: non è JSON") from None
        if not isinstance(payload, dict):
            raise ApiError(status, "risposta", "risposta non valida dal telefono: JSON inatteso")
        return payload

    def post(self, endpoint: str, body: bytes = b"", timeout: float = HTTP_TIMEOUT, retries: int = 0, **params) -> dict:
        request = urllib.request.Request(self.url(endpoint, **params), data=body, method="POST")
        return self._json(request, timeout, retries)

    def info(self) -> dict:
        return self._json(urllib.request.Request(self.url("/info.json"), method="GET"), retries=READ_RETRIES)

    def status(self) -> dict:
        return self.post("/status", timeout=STATUS_TIMEOUT)

    def photo(self) -> dict:
        return self.post("/cmd/photo")

    def video(self, start: bool) -> dict:
        return self.post("/cmd/video/start" if start else "/cmd/video/stop")

    def audio(self, start: bool) -> dict:
        return self.post("/cmd/audio/start" if start else "/cmd/audio/stop")

    def torch(self, on: bool) -> dict:
        return self.post("/cmd/torch", b"on" if on else b"off")

    def files(self, dirname: str) -> dict:
        return self.post("/files", retries=READ_RETRIES, dir=dirname)

    def download(
        self,
        dirname: str,
        name: str,
        dest: str,
        progress: Callable[[int, int], None] | None = None,
        cancel: threading.Event | None = None,
    ) -> int:
        """Scarica un file del telefono in dest passando da dest.part: errori e annullamenti non lasciano resti."""
        request = urllib.request.Request(self.url("/files/get", path=f"{dirname}/{name}"), data=b"", method="POST")
        partial = dest + ".part"
        report = ProgressThrottle(progress)
        received = 0
        try:
            with self._open(request, HTTP_TIMEOUT) as response, open(partial, "wb") as handle:
                total = as_int(response.headers.get("Content-Length"))
                while True:
                    if cancel is not None and cancel.is_set():
                        raise ApiError(0, "annullato", "download annullato")
                    try:
                        chunk = response.read(DOWNLOAD_CHUNK_BYTES)
                    except OSError as exc:
                        raise ApiError(0, "rete", f"download interrotto: {exc}") from None
                    if not chunk:
                        break
                    handle.write(chunk)
                    received += len(chunk)
                    report(received, total)
            if total and received != total:
                raise ApiError(0, "incompleto", f"ricevuti {received} byte su {total}")
            os.replace(partial, dest)
        except BaseException:
            _remove_quietly(partial)
            raise
        report(received, total or received, final=True)
        return received

    def snapshot(self) -> bytes:
        """Ultimo fotogramma dello stream in JPEG, così come lo serve il telefono."""
        with self._open(urllib.request.Request(self.url("/snapshot.jpg"), method="GET"), HTTP_TIMEOUT) as response:
            return response.read()

    def open_stream(self):
        return self._open(urllib.request.Request(self.url("/stream.mjpg"), method="GET"), STREAM_TIMEOUT)


def _read_exact(stream, length: int) -> bytes | None:
    chunks = []
    remaining = length
    while remaining > 0:
        chunk = stream.read(remaining)
        if not chunk:
            return None
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def iter_mjpeg(stream, stop=None):
    """Restituisce i JPEG di uno stream multipart/x-mixed-replace finché la connessione resta aperta."""
    while stop is None or not stop.is_set():
        line = stream.readline()
        if not line:
            return
        if not line.startswith(b"--"):
            continue
        length = None
        while True:
            header = stream.readline()
            if not header:
                return
            header = header.strip()
            if not header:
                break
            name, _, value = header.partition(b":")
            if name.strip().lower() == b"content-length":
                length = int(value.strip())
        if length is None or length < 0 or length > MAX_PART_BYTES:
            raise ValueError(f"parte MJPEG senza Content-Length valido: {length}")
        data = _read_exact(stream, length)
        if data is None:
            return
        yield data


def fit_size(source: tuple[int, int], box: tuple[int, int], rotation: int) -> tuple[int, int]:
    """Dimensione, prima della rotazione, che fa stare il fotogramma ruotato nel riquadro senza deformarlo."""
    source_w, source_h = source
    box_w, box_h = box
    if min(source_w, source_h, box_w, box_h) <= 0:
        return max(source_w, 1), max(source_h, 1)
    turned = rotation % 180 == 90
    rotated_w, rotated_h = (source_h, source_w) if turned else (source_w, source_h)
    scale = min(box_w / rotated_w, box_h / rotated_h)
    return max(1, round(source_w * scale)), max(1, round(source_h * scale))


def decode_frame(jpeg: bytes, rotation: int, box: tuple[int, int]):
    """JPEG dello stream -> immagine Pillow ruotata e adattata al riquadro. Richiede Pillow."""
    image = Image.open(io.BytesIO(jpeg))
    target = fit_size(image.size, box, rotation)
    if target[0] < image.size[0]:
        # draft fa decodificare a libjpeg direttamente a 1/2, 1/4 o 1/8: molta meno CPU sui fotogrammi grandi.
        image.draft("RGB", target)
    image = image.convert("RGB")
    if image.size != target:
        image = image.resize(target, _RESAMPLE_BILINEAR)
    turn = rotation % 360
    if turn in _TRANSPOSE_CLOCKWISE:
        image = image.transpose(_TRANSPOSE_CLOCKWISE[turn])
    elif turn:
        # Lo stream esce con l'orientamento del sensore: Pillow ruota in senso antiorario, quindi il segno è negativo.
        image = image.rotate(-turn, expand=True)
    return image


if Image is not None:
    _RESAMPLE_BILINEAR = getattr(getattr(Image, "Resampling", Image), "BILINEAR")
    _TRANSPOSE = getattr(Image, "Transpose", Image)
    # Rotazioni orarie esatte: transpose non interpola ed è molto più veloce di rotate.
    _TRANSPOSE_CLOCKWISE = {90: _TRANSPOSE.ROTATE_270, 180: _TRANSPOSE.ROTATE_180, 270: _TRANSPOSE.ROTATE_90}
else:
    _RESAMPLE_BILINEAR = None
    _TRANSPOSE_CLOCKWISE = {}


class FrameSink:
    """Ponte tra il thread dello stream e Tk: decodifica e conserva solo l'ultimo fotogramma."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest = None
        self._decoded = 0
        self.bad_frames = 0
        # Scritti dal thread Tk, letti dal thread dello stream: valori semplici, non widget.
        self.box: tuple[int, int] = VIDEO_MIN_SIZE
        self.rotation = 0

    def push(self, jpeg: bytes) -> str | None:
        """Decodifica un JPEG. Restituisce il motivo se il fotogramma è illeggibile e va scartato."""
        try:
            image = decode_frame(jpeg, self.rotation, self.box)
        except Exception as exc:
            # Pillow solleva tipi diversi (OSError, ValueError, SyntaxError...) per i JPEG troncati o corrotti.
            with self._lock:
                self.bad_frames += 1
            return f"{type(exc).__name__}: {exc}"
        with self._lock:
            self._latest = image
            self._decoded += 1
        return None

    def take(self):
        with self._lock:
            image, self._latest = self._latest, None
        return image

    def take_count(self) -> int:
        with self._lock:
            count, self._decoded = self._decoded, 0
        return count

    def reset(self) -> None:
        with self._lock:
            self._latest = None
            self._decoded = 0
            self.bad_frames = 0


class StreamWorker:
    """Legge /stream.mjpg in un thread suo e si ricollega da solo. Parla con l'esterno solo via callback."""

    def __init__(
        self,
        client: PhoneClient,
        on_frame: Callable[[bytes], None],
        on_event: Callable[[str], None],
        on_state: Callable[[bool], None] | None = None,
        retry_seconds: float = STREAM_RETRY_SECONDS,
        max_retry_seconds: float = STREAM_RETRY_MAX_SECONDS,
    ) -> None:
        self._client = client
        self._on_frame = on_frame
        self._on_event = on_event
        self._on_state = on_state or (lambda alive: None)
        self._retry = retry_seconds
        self._max_retry = max_retry_seconds
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._response = None
        self._thread: threading.Thread | None = None

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="rete-stream", daemon=True)
        self._thread.start()

    def stop(self, wait: float = 0.0) -> None:
        self._stop.set()
        with self._lock:
            response, self._response = self._response, None
        if response is not None:
            # Chiudere la risposta sblocca la readline del thread dello stream.
            try:
                response.close()
            except Exception:
                pass
        if wait and self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(wait)

    def _run(self) -> None:
        delay = self._retry
        failing = False
        ever_connected = False
        while not self._stop.is_set():
            response = None
            try:
                response = self._client.open_stream()
                with self._lock:
                    if self._stop.is_set():
                        response.close()
                        break
                    self._response = response
                self._on_event("Stream ripristinato" if failing else "Stream collegato")
                self._on_state(True)
                failing = False
                ever_connected = True
                delay = self._retry
                with response:
                    for jpeg in iter_mjpeg(response, self._stop):
                        self._on_frame(jpeg)
                if not self._stop.is_set():
                    self._on_event("Stream chiuso dal telefono, riprovo")
                    self._on_state(False)
            except Exception as exc:
                if self._stop.is_set():
                    break
                if not failing:
                    # Solo il primo errore va nel log: con il telefono spento si riproverebbe all'infinito.
                    self._on_event(f"Stream interrotto: {exc}. Riprovo in automatico")
                    self._on_state(False)
                failing = True
            finally:
                with self._lock:
                    if self._response is response:
                        self._response = None
            if self._stop.wait(delay):
                break
            if failing:
                delay = min(delay * 2, self._max_retry)
        if ever_connected:
            self._on_state(False)


# Stato della connessione mostrato accanto ai campi: (testo, colore).
CONNECTION_STATES = {
    "disconnected": ("Disconnesso", "#808080"),
    "connecting": ("Connessione...", "#d08000"),
    "connected": ("Connesso", "#1a9a3a"),
    "unreachable": ("Telefono irraggiungibile, riprovo", "#c03030"),
    "rejected": ("Token rifiutato: inserisci quello nuovo", "#c03030"),
}


def status_retry_delay_ms(failures: int) -> int:
    """Intervallo fino al prossimo /status: normale se va tutto bene, raddoppia a ogni errore fino a 15 s."""
    if failures <= 0:
        return STATUS_INTERVAL_MS
    return min(STATUS_INTERVAL_MS * 2 ** (failures - 1), STATUS_MAX_INTERVAL_MS)


def format_timestamp(value: Any) -> str:
    """Data leggibile da un timestamp Unix del telefono; '?' se manca o non è valido."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return "?"
    try:
        return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M")
    except (OverflowError, OSError, ValueError):
        return "?"


def human_size(size: int | None) -> str:
    if size is None:
        return "?"
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def as_int(value: Any, default: int = 0) -> int:
    """Intero da un campo JSON del telefono, senza eccezioni se manca o ha un tipo inatteso."""
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def describe_status(status: dict) -> dict:
    """Testi del pannello di stato a partire dalla risposta di /status. Campi mancanti o strani non sollevano."""
    status = _as_dict(status)
    mode = status.get("mode", "?")
    seconds = as_int(status.get("recording_seconds"))
    battery = _as_dict(status.get("battery"))
    storage = _as_dict(status.get("storage"))
    camera = _as_dict(status.get("camera"))
    if "percent" in battery:
        battery_text = f"{as_int(battery['percent'])}%{' in carica' if battery.get('charging') else ''}"
    else:
        battery_text = "non disponibile"
    if "free_bytes" in storage and "total_bytes" in storage:
        storage_text = (
            f"{human_size(as_int(storage['free_bytes']))} liberi su {human_size(as_int(storage['total_bytes']))}"
        )
    else:
        storage_text = "non disponibile"
    if camera.get("open"):
        size = camera.get("preview_size")
        size_text = f" {size[0]}x{size[1]}" if isinstance(size, (list, tuple)) and len(size) == 2 else ""
        camera_text = f"aperta{size_text}, {camera.get('preview_mode')}, torcia {'accesa' if camera.get('torch') else 'spenta'}"
        if not camera.get("has_frame"):
            camera_text += ", nessun fotogramma"
    else:
        camera_text = "chiusa"
    recording = {"video": "video", "audio": "audio"}.get(mode)
    return {
        "mode": {"idle": "in attesa", "video": "registra video", "audio": "registra audio"}.get(mode, mode),
        "recording": f"{recording} da {int(seconds) // 60:02d}:{int(seconds) % 60:02d}" if recording else "nessuna",
        "battery": battery_text,
        "storage": storage_text,
        "camera": camera_text,
    }


@dataclass
class DownloadItem:
    dirname: str
    name: str
    dest: str
    size: int | None = None


@dataclass
class DownloadReport:
    completed: list[DownloadItem]
    failed: list[tuple[DownloadItem, str]]
    cancelled: bool


class DownloadBatch:
    """Scarica uno o più file del telefono in sequenza. Nessun widget: avanzamento e righe di log via callback."""

    def __init__(
        self,
        client: PhoneClient,
        items: list[DownloadItem],
        on_progress: Callable[[int, int, str, int, int], None],
        on_log: Callable[[str], None],
    ) -> None:
        self.client = client
        self.items = items
        self._on_progress = on_progress
        self._on_log = on_log
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def run(self) -> DownloadReport:
        total = sum(item.size or 0 for item in self.items)
        done_bytes = 0
        completed: list[DownloadItem] = []
        failed: list[tuple[DownloadItem, str]] = []
        count = len(self.items)
        for index, item in enumerate(self.items):
            if self._cancel.is_set():
                break
            base = done_bytes

            def progress(received: int, size: int, item=item, index=index, base=base) -> None:
                self._on_progress(base + received, max(total, base + size), item.name, index, count)

            try:
                size = self.client.download(item.dirname, item.name, item.dest, progress=progress, cancel=self._cancel)
            except ApiError as exc:
                if exc.code == "annullato":
                    break
                failed.append((item, str(exc)))
                self._on_log(f"  {item.name}: {exc}")
            except OSError as exc:
                # Disco pieno, cartella senza permessi: si annota e si passa al file successivo.
                failed.append((item, f"{type(exc).__name__}: {exc}"))
                self._on_log(f"  {item.name}: impossibile scrivere {item.dest}: {exc}")
            else:
                completed.append(item)
                done_bytes += size
                self._on_log(f"  Scaricato {item.name} ({human_size(size)}) in {item.dest}")
        return DownloadReport(completed, failed, self._cancel.is_set())


def default_settings_path() -> str:
    """File delle impostazioni: %APPDATA%\\gioco su Windows, ~/.config/gioco altrove. GIOCO_PC_CONFIG lo sostituisce."""
    override = os.environ.get("GIOCO_PC_CONFIG")
    if override:
        return override
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "gioco", "pc_controllo.json")


class SettingsStore:
    """Impostazioni in JSON. Un file illeggibile non blocca l'avvio: viene messo da parte e si riparte da zero."""

    def __init__(self, path: str | None = None) -> None:
        self.path = path or default_settings_path()
        self.load_problem: str | None = None

    def load(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as exc:
            broken = self.path + ".rotto"
            try:
                os.replace(self.path, broken)
                self.load_problem = f"impostazioni illeggibili ({exc}): salvate in {broken}, riparto da zero"
            except OSError:
                self.load_problem = f"impostazioni illeggibili ({exc}): riparto da zero"
            return {}
        if not isinstance(data, dict):
            self.load_problem = "impostazioni in un formato inatteso: riparto da zero"
            return {}
        return data

    def save(self, data: dict) -> None:
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        payload = {"version": SETTINGS_VERSION, **data}
        write_bytes_atomic(self.path, json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"))


def remember_connection(history: Any, host: str, port: int, token: str, now: datetime | None = None) -> list[dict]:
    """Mette la connessione in cima alla cronologia, senza doppioni di host:porta, al massimo HISTORY_LIMIT voci."""
    entry = {"host": host, "port": port, "token": token, "used": (now or datetime.now()).isoformat(timespec="seconds")}
    previous = [
        item for item in (history if isinstance(history, list) else [])
        if isinstance(item, dict) and isinstance(item.get("host"), str)
        and not (item.get("host") == host and as_int(item.get("port")) == port)
    ]
    return [entry, *previous][:HISTORY_LIMIT]


def history_label(entry: dict) -> str:
    return f"{entry.get('host')}:{as_int(entry.get('port'), DEFAULT_PORT)}"


def valid_geometry(geometry: Any, screen_width: int, screen_height: int) -> str | None:
    """Geometria salvata, se ha senso su questo schermo; la posizione si scarta se finirebbe fuori (monitor staccato)."""
    if not isinstance(geometry, str):
        return None
    match = GEOMETRY_PATTERN.match(geometry)
    if not match:
        return None
    width, height = min(int(match.group(1)), screen_width), min(int(match.group(2)), screen_height)
    # "+N" è la distanza dal bordo sinistro/alto; "-N" dal bordo destro/basso e "+-N" è fuori a sinistra: scartate.
    offsets = [match.group(3), match.group(4)]
    if all(part.startswith("+") and not part.startswith("+-") for part in offsets):
        x, y = int(offsets[0][1:]), int(offsets[1][1:])
        if x < screen_width - 100 and y < screen_height - 100:
            return f"{width}x{height}+{x}+{y}"
    return f"{width}x{height}"


class DeployError(Exception):
    """Errore di compilazione, installazione o GitHub. retryable indica un problema temporaneo (rete, 5xx)."""

    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


# Testo del pulsante e descrizione dell'attività in corso, per modalità.
ACTION_LABELS = {
    "github": {
        "check": ("Verifica", "verifica di GitHub e del telefono"),
        "build": ("Scarica APK da GitHub", "download dell'APK"),
        "install": ("Installa sul telefono", "download e installazione"),
        "launch": ("Avvia e connetti", "avvio"),
        "everything": ("Tutto: scarica, installa, avvia", "download, installazione e avvio"),
    },
    "wsl": {
        "check": ("Verifica", "verifica di WSL e del telefono"),
        "build": ("Genera APK", "compilazione"),
        "install": ("Installa sul telefono", "installazione"),
        "launch": ("Avvia e connetti", "avvio"),
        "everything": ("Tutto: genera, installa, avvia", "compilazione, installazione e avvio"),
    },
}


def detect_host() -> str:
    if os.name == "nt":
        return "windows"
    if "microsoft" in platform.release().lower():
        return "wsl"
    return "linux"


def default_adb(host: str) -> str:
    # Dentro WSL2 l'USB non si vede: serve l'adb.exe di Windows, raggiungibile via interop.
    return "adb.exe" if host == "wsl" else "adb"


@dataclass
class DeploySettings:
    host: str
    project_dir: str = DEFAULT_PROJECT_DIR
    buildozer: str = DEFAULT_BUILDOZER
    wsl_distro: str = ""
    adb: str = "adb"


def bash_path(path: str) -> str:
    """Percorso per bash -lc: ~/ diventa $HOME/ tra virgolette doppie, ogni altro percorso è quotato per intero."""
    if path == "~":
        return '"$HOME"'
    if path.startswith("~/"):
        rest = path[2:]
        for char in ("\\", '"', "$", "`"):
            rest = rest.replace(char, "\\" + char)
        return f'"$HOME/{rest}"'
    return shlex.quote(path)


def linux_command(settings: DeploySettings, script: str) -> list[str]:
    if settings.host == "windows":
        args = ["wsl.exe"]
        if settings.wsl_distro:
            args += ["-d", settings.wsl_distro]
        return args + ["--", "bash", "-lc", script]
    return ["bash", "-lc", script]


def check_script(settings: DeploySettings) -> str:
    return (
        f"if ! cd {bash_path(settings.project_dir)} 2>/dev/null; then echo 'MANCA cartella del progetto'; exit 0; fi; "
        "for f in main.py buildozer.spec; do test -f \"$f\" || echo \"MANCA $f\"; done; "
        f"test -x {bash_path(settings.buildozer)} || echo 'MANCA buildozer'; "
        "echo FINE"
    )


def build_script(settings: DeploySettings) -> str:
    return f"cd {bash_path(settings.project_dir)} && {bash_path(settings.buildozer)} -v android debug"


def needs_windows_path(settings: DeploySettings) -> bool:
    return settings.host == "windows" or settings.adb.lower().endswith(".exe")


def apk_path_script(settings: DeploySettings) -> str:
    show = 'wslpath -w "$PWD/$f"' if needs_windows_path(settings) else 'printf "%s\\n" "$PWD/$f"'
    return (
        f"cd {bash_path(settings.project_dir)} && f=$(ls -t bin/*.apk 2>/dev/null | head -n 1) && "
        f'test -n "$f" && {show}'
    )


def parse_server_line(text: str) -> tuple[str, int] | None:
    match = None
    for match in SERVER_LINE.finditer(text):
        pass
    if match is None:
        return None
    return match.group(1), int(match.group(2))


def parse_devices(lines: list[str]) -> tuple[list[str], list[str]]:
    """Da 'adb devices': (seriali pronti, righe con problemi come unauthorized o offline)."""
    ready, problems = [], []
    for line in lines:
        parts = line.split()
        if len(parts) < 2 or line.startswith("List of devices") or line.startswith("*"):
            continue
        if parts[1] == "device":
            ready.append(parts[0])
        else:
            problems.append(f"{parts[0]} {parts[1]}")
    return ready, problems


class ProcessRunner:
    """Esegue un comando e ne passa le righe a on_line. Blocca: si usa solo da un thread di lavoro."""

    def __init__(self):
        self._lock = threading.Lock()
        self._process = None
        self.cancelled = False

    def __call__(self, args: list[str], on_line=None) -> tuple[int, list[str]]:
        if self.cancelled:
            raise DeployError("interrotto")
        try:
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                # Su Windows evita che ogni comando apra una finestra di console.
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except FileNotFoundError:
            raise DeployError(f"comando non trovato: {args[0]}") from None
        except OSError as exc:
            raise DeployError(f"impossibile avviare {args[0]}: {exc}") from None
        with self._lock:
            self._process = process
        tail = []
        for raw in process.stdout:
            # wsl.exe scrive i propri messaggi in UTF-16: i byte nulli resterebbero nel testo.
            line = raw.decode("utf-8", "replace").replace("\x00", "").rstrip("\r\n")
            tail.append(line)
            if len(tail) > OUTPUT_TAIL_LINES:
                del tail[0]
            if on_line is not None:
                on_line(line)
        code = process.wait()
        with self._lock:
            self._process = None
        if self.cancelled:
            raise DeployError("interrotto")
        return code, tail

    def cancel(self):
        self.cancelled = True
        with self._lock:
            process = self._process
        if process is None or process.poll() is not None:
            return
        try:
            process.terminate()
        except OSError:
            return

        def kill_if_stuck() -> None:
            try:
                process.wait(PROCESS_KILL_SECONDS)
            except subprocess.TimeoutExpired:
                try:
                    process.kill()
                except OSError:
                    pass

        threading.Thread(target=kill_if_stuck, name="kill-processo", daemon=True).start()


class Deployer:
    """Compila, installa, avvia e trova token e porta. Riceve run e log dall'esterno: nessun widget qui."""

    def __init__(self, settings: DeploySettings, run, log, sleep=time.sleep, clock=time.monotonic):
        self.settings = settings
        self._run = run
        self._log = log
        self._sleep = sleep
        self._clock = clock

    def _call(self, args: list[str], label: str, stream: bool = False) -> list[str]:
        self._log("$ " + " ".join(shlex.quote(arg) for arg in args))
        code, lines = self._run(args, self._log if stream else None)
        if code != 0:
            tail = "\n".join(lines[-ERROR_TAIL_LINES:])
            raise DeployError(f"{label} fallito (uscita {code})" + (f":\n{tail}" if tail else ""))
        return lines

    def adb(self, *args: str, label: str | None = None) -> list[str]:
        return self._call([self.settings.adb, *args], label or f"adb {args[0]}")

    def phone_problems(self) -> list[str]:
        problems = []
        try:
            ready, bad = parse_devices(self.adb("devices"))
        except DeployError as exc:
            return [f"adb non utilizzabile: {exc}"]
        if bad:
            problems.append("telefono non pronto: " + ", ".join(bad) + " (accetta l'impronta RSA sul telefono)")
        if not ready:
            problems.append("nessun telefono collegato con il debug USB attivo")
        elif len(ready) > 1:
            problems.append(f"più telefoni collegati ({', '.join(ready)}): lasciane collegato uno")
        return problems

    def report(self, problems: list[str], ready_text: str) -> list[str]:
        for problem in problems:
            self._log(f"PROBLEMA: {problem}")
        if not problems:
            self._log(ready_text)
        return problems

    def check(self) -> list[str]:
        problems = []
        lines = self._call(linux_command(self.settings, check_script(self.settings)), "controllo di WSL")
        for line in lines:
            if line.startswith("MANCA "):
                problems.append(f"in WSL manca: {line[6:]} ({self.settings.project_dir}, {self.settings.buildozer})")
        if "FINE" not in lines and not problems:
            problems.append("WSL non ha risposto come previsto: " + " | ".join(lines[-3:]))
        problems += self.phone_problems()
        return self.report(problems, "Pronto: progetto e buildozer in WSL, un telefono collegato.")

    def build(self) -> None:
        self._log("Compilazione dell'APK in WSL: la prima volta dura 20-40 minuti.")
        self._call(linux_command(self.settings, build_script(self.settings)), "buildozer", stream=True)

    def apk_path(self) -> str:
        lines = self._call(linux_command(self.settings, apk_path_script(self.settings)), "ricerca dell'APK")
        paths = [line.strip() for line in lines if line.strip()]
        if not paths:
            raise DeployError("nessun APK in bin/: compila prima")
        return paths[-1]

    def install(self) -> None:
        self.install_apk(self.apk_path())

    def install_apk(self, path: str) -> None:
        lines = self.adb("install", "-r", path, label="installazione")
        if not any("Success" in line for line in lines):
            raise DeployError("installazione non confermata da adb:\n" + "\n".join(lines[-ERROR_TAIL_LINES:]))
        for permission in APP_PERMISSIONS:
            self.adb("shell", "pm", "grant", APP_PACKAGE, permission, label=f"permesso {permission}")
        self._log("APK installato, permessi fotocamera e microfono concessi.")

    def launch(self) -> tuple[str, int]:
        self.adb("logcat", "-c", label="pulizia del log")
        self.adb("shell", "am", "force-stop", APP_PACKAGE, label="chiusura dell'app")
        lines = self.adb("shell", "am", "start", "-W", "-n", f"{APP_PACKAGE}/{APP_ACTIVITY}", label="avvio dell'app")
        if any(line.startswith("Error") for line in lines):
            raise DeployError("avvio rifiutato:\n" + "\n".join(lines))
        deadline = self._clock() + TOKEN_WAIT_SECONDS
        found = None
        reported_error = False
        while found is None:
            try:
                lines = self.adb("logcat", "-d", "-s", "python:I", label="lettura del log")
            except DeployError as exc:
                # adb a volte risponde 'device offline' per un attimo mentre l'app parte: si riprova fino alla scadenza.
                if not reported_error:
                    self._log(f"lettura del log non riuscita, riprovo: {exc}")
                    reported_error = True
                lines = []
            found = parse_server_line("\n".join(lines))
            if found is None:
                if self._clock() >= deadline:
                    raise DeployError(
                        f"token non trovato nel log entro {TOKEN_WAIT_SECONDS:.0f} s: "
                        "guarda il telefono, l'app potrebbe essere in errore"
                    )
                self._sleep(TOKEN_POLL_SECONDS)
        token, port = found
        self.adb("forward", f"tcp:{port}", f"tcp:{port}", label="adb forward")
        self._log(f"App avviata: token {token}, porta {port} inoltrata su localhost via USB.")
        return token, port

    def everything(self) -> tuple[str, int]:
        problems = self.check()
        if problems:
            raise DeployError("controllo iniziale fallito: " + "; ".join(problems))
        self.build()
        self.install()
        return self.launch()


class _DropAuthOnRedirect(urllib.request.HTTPRedirectHandler):
    """GitHub rimanda il download a un archivio esterno firmato: lì il token GitHub va tolto, altrimenti rifiuta."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and urllib.parse.urlsplit(newurl).netloc != urllib.parse.urlsplit(req.full_url).netloc:
            new.remove_header("Authorization")
        return new


_GITHUB_OPENER = urllib.request.build_opener(_DropAuthOnRedirect)


def default_apk_dir() -> str:
    downloads = os.path.join(os.path.expanduser("~"), "Downloads")
    base = downloads if os.path.isdir(downloads) else os.path.expanduser("~")
    return os.path.join(base, "gioco-apk")


def extract_apk(archive: str, target_dir: str) -> str:
    """Estrae il primo .apk di uno zip (come quelli scaricati da GitHub) e ne restituisce il percorso."""
    try:
        bundle = zipfile.ZipFile(archive)
    except zipfile.BadZipFile:
        raise DeployError(f"{archive} non è uno zip valido") from None
    with bundle:
        members = [name for name in bundle.namelist() if name.lower().endswith(".apk")]
        if not members:
            raise DeployError(f"l'archivio non contiene un APK: {bundle.namelist()}")
        os.makedirs(target_dir, exist_ok=True)
        # Solo il nome del file: un percorso dentro lo zip non deve poter uscire dalla cartella.
        path = os.path.join(target_dir, os.path.basename(members[0]))
        partial = path + ".part"
        try:
            with bundle.open(members[0]) as source, open(partial, "wb") as target:
                shutil.copyfileobj(source, target)
            os.replace(partial, path)
        except BaseException:
            _remove_quietly(partial)
            raise
    return path


def apk_from_file(path: str, work_dir: str) -> str:
    """Un .apk si installa così com'è; lo zip scaricato dalla pagina di GitHub va prima aperto."""
    if path.lower().endswith(".zip"):
        return extract_apk(path, work_dir)
    return path


class GitHubBuilds:
    """APK compilati da GitHub Actions (workflow camera-apk.yml). Blocca: solo da un thread di lavoro."""

    def __init__(
        self,
        repo: str,
        branch: str,
        token: str,
        workflow: str = WORKFLOW_FILE,
        api: str = GITHUB_API,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._sleep = sleep
        if repo.count("/") != 1 or not all(repo.split("/")):
            raise DeployError(f"repository nella forma proprietario/nome, ricevuto: {repo!r}")
        self.repo = repo
        self.branch = branch
        self.token = token
        self.workflow = workflow
        self.api = api.rstrip("/")

    def page_url(self) -> str:
        query = urllib.parse.quote(f"branch:{self.branch}")
        return f"https://github.com/{self.repo}/actions/workflows/{self.workflow}?query={query}"

    def _request(self, url: str) -> urllib.request.Request:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "gioco-pc-controllo",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return urllib.request.Request(url, headers=headers)

    def _open(self, url: str):
        try:
            return _GITHUB_OPENER.open(self._request(url), timeout=GITHUB_TIMEOUT)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            if exc.code == 401:
                raise DeployError("token GitHub non valido o scaduto") from None
            if exc.code == 403 and "rate limit" in body.lower():
                raise DeployError("limite di richieste a GitHub raggiunto: inserisci un token GitHub") from None
            if exc.code == 403:
                raise DeployError("GitHub nega l'accesso: il token deve avere il permesso Actions: Read") from None
            if exc.code == 404:
                raise DeployError(f"non trovato su GitHub: {self.repo}, branch {self.branch}, {self.workflow}") from None
            raise DeployError(f"GitHub ha risposto {exc.code}: {body[:200]}", retryable=exc.code >= 500) from None
        except (urllib.error.URLError, OSError) as exc:
            raise DeployError(f"GitHub non raggiungibile: {getattr(exc, 'reason', exc)}", retryable=True) from None

    def _json(self, url: str) -> dict:
        """Lettura dall'API di GitHub, ripetuta sugli errori temporanei (rete, 5xx) con attesa crescente."""
        attempt = 0
        while True:
            try:
                with self._open(url) as response:
                    raw = response.read()
                break
            except DeployError as exc:
                error = exc
            except OSError as exc:
                # La connessione può cadere anche a metà della risposta, dopo che _open è riuscita.
                error = DeployError(f"GitHub non raggiungibile: {exc}", retryable=True)
            if not error.retryable or attempt >= GITHUB_RETRIES:
                raise error
            attempt += 1
            self._sleep(GITHUB_RETRY_DELAY * attempt)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise DeployError("risposta di GitHub non valida: non è JSON") from None
        if not isinstance(payload, dict):
            raise DeployError("risposta di GitHub non valida: JSON inatteso")
        return payload

    def _runs(self, **params) -> list[dict]:
        query = urllib.parse.urlencode({"branch": self.branch, **params})
        url = f"{self.api}/repos/{self.repo}/actions/workflows/{self.workflow}/runs?{query}"
        return self._json(url).get("workflow_runs", [])

    def latest_build(self) -> dict:
        for run in self._runs(status="success", per_page=RUNS_TO_SCAN):
            artifacts = self._json(f"{self.api}/repos/{self.repo}/actions/runs/{run['id']}/artifacts")
            for artifact in artifacts.get("artifacts", []):
                if artifact["name"].startswith(ARTIFACT_PREFIX) and not artifact.get("expired"):
                    return {
                        "run_id": run["id"],
                        "sha": run.get("head_sha", ""),
                        "created_at": run.get("created_at", ""),
                        "run_url": run.get("html_url", ""),
                        "artifact_id": artifact["id"],
                        "artifact_name": artifact["name"],
                        "size": artifact.get("size_in_bytes"),
                        "download_url": artifact["archive_download_url"],
                    }
        raise DeployError(f"nessun APK pronto su GitHub per il branch {self.branch}{self._latest_run_note()}")

    def _latest_run_note(self) -> str:
        runs = self._runs(per_page=1)
        if not runs:
            return ": il workflow non è mai partito su questo branch"
        run = runs[0]
        if run.get("status") != "completed":
            return f": compilazione in corso dal {run.get('created_at')}, riprova tra qualche minuto ({run.get('html_url')})"
        return f": l'ultima compilazione è finita con '{run.get('conclusion')}' ({run.get('html_url')})"

    def download_apk(
        self,
        build: dict,
        dest_dir: str,
        log: Callable[[str], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
        progress: Callable[[int, int], None] | None = None,
    ) -> str:
        target_dir = os.path.join(dest_dir, str(build["artifact_id"]))
        if os.path.isdir(target_dir):
            for name in os.listdir(target_dir):
                if not name.lower().endswith(".apk"):
                    continue
                path = os.path.join(target_dir, name)
                # Un APK è uno zip: se non si apre è un resto di un'estrazione fallita e va riscaricato.
                if zipfile.is_zipfile(path):
                    if log is not None:
                        log(f"APK già scaricato: {path}")
                    return path
                _remove_quietly(path)
        if not self.token:
            raise DeployError(
                "per scaricare l'APK da GitHub serve un token con Actions: Read; in alternativa scaricalo "
                "dalla pagina delle compilazioni e usa 'Installa APK da file...'"
            )
        os.makedirs(target_dir, exist_ok=True)
        archive = target_dir + ".zip.part"
        received = 0
        reported = 0
        report = ProgressThrottle(progress)
        try:
            with self._open(build["download_url"]) as response, open(archive, "wb") as handle:
                total = as_int(response.headers.get("Content-Length")) or as_int(build.get("size"))
                while True:
                    if should_stop is not None and should_stop():
                        raise DeployError("interrotto")
                    try:
                        chunk = response.read(DOWNLOAD_CHUNK_BYTES)
                    except OSError as exc:
                        raise DeployError(f"download da GitHub interrotto: {exc}") from None
                    if not chunk:
                        break
                    handle.write(chunk)
                    received += len(chunk)
                    report(received, total)
                    if log is not None and received - reported >= PROGRESS_STEP_BYTES:
                        reported = received
                        log(f"  scaricati {human_size(received)}")
            report(received, total or received, final=True)
            path = extract_apk(archive, target_dir)
        finally:
            _remove_quietly(archive)
        if log is not None:
            log(f"APK salvato in {path}")
        return path


class GitHubPipeline:
    """Le stesse azioni di Deployer, ma l'APK arriva già compilato da GitHub Actions: sul PC basta adb."""

    def __init__(
        self,
        deployer: Deployer,
        builds: GitHubBuilds,
        dest_dir: str,
        log: Callable[[str], None],
        should_stop: Callable[[], bool] | None = None,
        progress: Callable[[int, int], None] | None = None,
    ):
        self.deployer = deployer
        self.builds = builds
        self.dest_dir = dest_dir
        self._log = log
        self._should_stop = should_stop
        self._progress = progress

    def check(self) -> list[str]:
        problems = []
        try:
            build = self.builds.latest_build()
        except DeployError as exc:
            problems.append(str(exc))
        else:
            self._log(
                f"Ultimo APK su GitHub: {build['artifact_name']} ({human_size(build['size'])}), "
                f"commit {build['sha'][:7]} del {build['created_at']}"
            )
            if not self.builds.token:
                problems.append("manca il token GitHub: senza, l'APK non si può scaricare da qui")
        problems += self.deployer.phone_problems()
        return self.deployer.report(problems, "Pronto: APK disponibile su GitHub, un telefono collegato.")

    def build(self) -> str:
        build = self.builds.latest_build()
        self._log(f"Scarico {build['artifact_name']} (commit {build['sha'][:7]}, {build['created_at']})")
        return self.builds.download_apk(build, self.dest_dir, self._log, self._should_stop, self._progress)

    def install(self) -> None:
        self.deployer.install_apk(self.build())

    def launch(self) -> tuple[str, int]:
        return self.deployer.launch()

    def everything(self) -> tuple[str, int]:
        problems = self.check()
        if problems:
            raise DeployError("controllo iniziale fallito: " + "; ".join(problems))
        self.install()
        return self.launch()


@dataclass(frozen=True)
class Shortcut:
    key: str
    accelerator: str
    # Tk usa molti Ctrl+lettera per modificare il testo (Ctrl+F avanti di un carattere, Ctrl+T scambia...):
    # mentre si scrive in un campo scattano solo le scorciatoie marcate come sicure.
    text_safe: bool = False


SHORTCUTS: dict[str, Shortcut] = {
    "save_settings": Shortcut("Control-s", "Ctrl+S", True),
    "export_log": Shortcut("Control-e", "Ctrl+E"),
    "quit": Shortcut("Control-q", "Ctrl+Q", True),
    "connect": Shortcut("Control-Return", "Ctrl+Invio", True),
    "photo": Shortcut("Control-f", "Ctrl+F"),
    "video": Shortcut("Control-r", "Ctrl+R"),
    "audio": Shortcut("Control-m", "Ctrl+M"),
    "torch": Shortcut("Control-t", "Ctrl+T"),
    "snapshot": Shortcut("Control-i", "Ctrl+I"),
    "browser": Shortcut("Control-b", "Ctrl+B"),
    "refresh_files": Shortcut("F5", "F5", True),
    "download": Shortcut("Control-d", "Ctrl+D"),
    "clear_log": Shortcut("Control-l", "Ctrl+L"),
    "cancel": Shortcut("Escape", "Esc", True),
    "help": Shortcut("F1", "F1", True),
}

SHORTCUT_HELP = (
    ("connect", "Connetti o disconnetti"),
    ("photo", "Foto"),
    ("video", "Avvia o ferma il video"),
    ("audio", "Avvia o ferma l'audio"),
    ("torch", "Torcia"),
    ("snapshot", "Istantanea sul PC"),
    ("browser", "Apri lo stream nel browser"),
    ("refresh_files", "Aggiorna i file sul telefono"),
    ("download", "Scarica i file selezionati"),
    ("cancel", "Annulla il download in corso, o la compilazione dopo conferma"),
    ("save_settings", "Salva le impostazioni"),
    ("export_log", "Esporta il log"),
    ("clear_log", "Pulisci il log"),
    ("quit", "Esci"),
    ("help", "Questo elenco"),
)


def shortcut_sequences(shortcut: Shortcut) -> list[str]:
    """Con il Bloc Maiusc attivo Tk riceve la lettera maiuscola: si legano entrambe."""
    sequences = [f"<{shortcut.key}>"]
    modifier, _, letter = shortcut.key.rpartition("-")
    if modifier and len(letter) == 1 and letter.isalpha():
        sequences.append(f"<{modifier}-{letter.upper()}>")
    return sequences


def is_text_input(widget: Any) -> bool:
    """True se il widget è un campo in cui si sta scrivendo (non disabilitato né in sola lettura)."""
    if tk is None or not isinstance(widget, tk.Misc):
        return False
    try:
        if isinstance(widget, ttk.Entry):
            return bool(widget.instate(["!disabled", "!readonly"]))
        if isinstance(widget, (tk.Entry, tk.Text, tk.Spinbox)):
            return str(widget.cget("state")) == "normal"
    except tk.TclError:
        return False
    return False


class ControlPanel:
    """Finestra Tk. Regola: i thread di rete mettono messaggi in coda, solo _pump (thread Tk) tocca i widget."""

    def __init__(self, root):
        self.root = root
        # Coda di (funzione, argomenti) da eseguire sul thread Tk: è l'unico ponte tra thread di rete e widget.
        self.events: queue.Queue[tuple[Callable[..., Any], tuple[Any, ...]]] = queue.Queue()
        self.client: PhoneClient | None = None
        # Cambia a ogni connessione e disconnessione: le risposte di una sessione vecchia vengono scartate.
        self._session = 0
        self.status = {}
        self._sink = FrameSink()
        self._stream: StreamWorker | None = None
        self._fps_since = time.monotonic()
        self._photo_image = None
        self._photo_size: tuple[int, int] | None = None
        self._bad_frames_logged = 0
        self._status_job = None
        self._status_busy = False
        self._status_failures = 0
        self._busy_commands: set[str] = set()
        self._download_batch: DownloadBatch | None = None
        self._file_sizes: dict[str, int | None] = {}
        self.download_dir = os.path.expanduser("~")
        self._host = detect_host()
        self._runner = None
        self._closing = False
        self.settings_store = SettingsStore()
        self.history: list[dict] = []
        self._build()
        self._load_settings()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.report_callback_exception = self._report_tk_exception
        self._pump_job: str | None = self.root.after(PUMP_INTERVAL_MS, self._pump)

    def _build(self):
        root = self.root
        root.title("Gioco - controllo telefono")
        root.minsize(1000, 760)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        deploy = ttk.LabelFrame(root, text="Telefono e APK (adb via USB)", padding=8)
        deploy.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        # Su Windows buildozer non gira: lì la strada predefinita è l'APK già compilato da GitHub.
        self.mode_var = tk.StringVar(value="github" if self._host == "windows" else "wsl")
        self.adb_var = tk.StringVar(value=default_adb(self._host))
        mode_row = ttk.Frame(deploy)
        mode_row.grid(row=0, column=0, sticky="w")
        ttk.Label(mode_row, text="APK da:").grid(row=0, column=0, padx=(0, 6))
        ttk.Radiobutton(
            mode_row, text="GitHub (compilato online, niente WSL)", variable=self.mode_var, value="github",
            command=self._on_mode_change,
        ).grid(row=0, column=1, padx=(0, 12))
        ttk.Radiobutton(
            mode_row, text="WSL2 (buildozer su questo PC)", variable=self.mode_var, value="wsl",
            command=self._on_mode_change,
        ).grid(row=0, column=2, padx=(0, 24))
        ttk.Label(mode_row, text="adb").grid(row=0, column=3, padx=(0, 4))
        ttk.Entry(mode_row, textvariable=self.adb_var, width=12).grid(row=0, column=4)

        self.repo_var = tk.StringVar(value=DEFAULT_REPO)
        self.branch_var = tk.StringVar(value=DEFAULT_BRANCH)
        self.github_token_var = tk.StringVar(value=os.environ.get("GITHUB_TOKEN", ""))
        self.apk_dir_var = tk.StringVar(value=default_apk_dir())
        self.remember_github_token_var = tk.BooleanVar(value=False)
        self.github_fields = ttk.Frame(deploy)
        self.github_fields.grid(row=1, column=0, sticky="w", pady=(6, 0))
        for column, (label, variable, width, secret) in enumerate(
            (
                ("Repository", self.repo_var, 24, False),
                ("Branch", self.branch_var, 30, False),
                ("Token GitHub", self.github_token_var, 18, True),
                ("Cartella APK", self.apk_dir_var, 26, False),
            )
        ):
            ttk.Label(self.github_fields, text=label).grid(row=0, column=column * 2, padx=(0, 4), sticky="w")
            ttk.Entry(self.github_fields, textvariable=variable, width=width, show="•" if secret else "").grid(
                row=0, column=column * 2 + 1, padx=(0, 12)
            )
        ttk.Checkbutton(
            self.github_fields, text="Ricorda token", variable=self.remember_github_token_var
        ).grid(row=0, column=8, padx=(0, 4))

        self.project_var = tk.StringVar(value=DEFAULT_PROJECT_DIR)
        self.buildozer_var = tk.StringVar(value=DEFAULT_BUILDOZER)
        self.distro_var = tk.StringVar(value="")
        self.wsl_fields = ttk.Frame(deploy)
        self.wsl_fields.grid(row=1, column=0, sticky="w", pady=(6, 0))
        fields = [("Progetto in WSL", self.project_var, 18), ("buildozer", self.buildozer_var, 30)]
        if self._host == "windows":
            fields.append(("Distribuzione WSL (vuoto = predefinita)", self.distro_var, 14))
        for column, (label, variable, width) in enumerate(fields):
            ttk.Label(self.wsl_fields, text=label).grid(row=0, column=column * 2, padx=(0, 4), sticky="w")
            ttk.Entry(self.wsl_fields, textvariable=variable, width=width).grid(row=0, column=column * 2 + 1, padx=(0, 12))

        actions = ttk.Frame(deploy)
        actions.grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.action_buttons = {}
        for column, action in enumerate(("check", "build", "install", "launch", "everything")):
            button = ttk.Button(actions, command=lambda name=action: self.deploy(name))
            button.grid(row=0, column=column, padx=(0, 6))
            self.action_buttons[action] = button
        self.install_file_button = ttk.Button(actions, text="Installa APK da file...", command=self.install_from_file)
        self.install_file_button.grid(row=0, column=5, padx=(0, 6))
        self.builds_page_button = ttk.Button(actions, text="Pagina compilazioni", command=self.open_builds_page)
        self.builds_page_button.grid(row=0, column=6, padx=(0, 6))
        self.deploy_buttons = list(self.action_buttons.values()) + [self.install_file_button]
        self.cancel_button = ttk.Button(actions, text="Interrompi", command=self.cancel_deploy)
        self.cancel_button.grid(row=0, column=7, padx=(12, 0))
        self.cancel_button.state(["disabled"])
        self.deploy_progress = ttk.Progressbar(actions, mode="indeterminate", length=140, maximum=1000)
        self.deploy_progress.grid(row=0, column=8, padx=(12, 0))
        self.deploy_progress.grid_remove()
        self.deploy_var = tk.StringVar(value="")
        ttk.Label(actions, textvariable=self.deploy_var).grid(row=0, column=9, padx=(12, 0))
        self._on_mode_change()

        connection = ttk.LabelFrame(root, text="Connessione", padding=8)
        connection.grid(row=1, column=0, sticky="ew", padx=8, pady=4)
        self.host_var = tk.StringVar()
        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))
        self.token_var = tk.StringVar()
        ttk.Label(connection, text="IP").grid(row=0, column=0, padx=(0, 4))
        # Combobox modificabile: si scrive l'IP (o si incolla l'URL della scheda) oppure si sceglie dalla cronologia.
        self.host_box = ttk.Combobox(connection, textvariable=self.host_var, width=22)
        self.host_box.grid(row=0, column=1, padx=(0, 12))
        self.host_box.bind("<<ComboboxSelected>>", self._on_history_selected)
        for column, (label, variable, width) in enumerate(
            (("Porta", self.port_var, 6), ("Token", self.token_var, 12)), start=1
        ):
            ttk.Label(connection, text=label).grid(row=0, column=column * 2, padx=(0, 4))
            entry = ttk.Entry(connection, textvariable=variable, width=width)
            entry.grid(row=0, column=column * 2 + 1, padx=(0, 12))
            entry.bind("<Return>", self._on_field_return)
        self.host_box.bind("<Return>", self._on_field_return)
        self.connect_button = ttk.Button(connection, text="Connetti", command=self.toggle_connection)
        self.connect_button.grid(row=0, column=6, padx=(0, 8))
        ttk.Button(connection, text="Apri nel browser", command=self.open_browser).grid(row=0, column=7)
        self.state_label = tk.Label(connection, text="", anchor="w")
        self.state_label.grid(row=0, column=8, padx=(16, 0), sticky="w")
        connection.columnconfigure(8, weight=1)

        body = ttk.Frame(root)
        body.grid(row=2, column=0, sticky="nsew", padx=8, pady=4)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        video_frame = ttk.LabelFrame(body, text="Stream", padding=4)
        video_frame.grid(row=0, column=0, sticky="nsew")
        video_frame.columnconfigure(0, weight=1)
        video_frame.rowconfigure(0, weight=1)
        # Contenitore a dimensione fissa e etichetta piazzata dentro: l'immagine non può più far crescere la finestra.
        self.video_area = tk.Frame(video_frame, background="black", width=VIDEO_REQUEST_SIZE[0], height=VIDEO_REQUEST_SIZE[1])
        self.video_area.grid(row=0, column=0, sticky="nsew")
        self.video_area.grid_propagate(False)
        self.video_label = tk.Label(
            self.video_area, background="black", foreground="#cccccc", text="Non connesso", borderwidth=0,
            highlightthickness=0,
        )
        self.video_label.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.video_area.bind("<Configure>", self._on_video_resize)
        self.fps_var = tk.StringVar(value="")
        ttk.Label(video_frame, textvariable=self.fps_var).grid(row=1, column=0, sticky="w")

        side = ttk.Frame(body)
        side.grid(row=0, column=1, sticky="ns", padx=(8, 0))

        commands = ttk.LabelFrame(side, text="Comandi", padding=8)
        commands.grid(row=0, column=0, sticky="ew")
        self.photo_button = ttk.Button(commands, text="Foto", command=self.take_photo)
        self.video_button = ttk.Button(commands, text="Avvia video", command=self.toggle_video)
        self.audio_button = ttk.Button(commands, text="Avvia audio", command=self.toggle_audio)
        self.torch_button = ttk.Button(commands, text="Accendi torcia", command=self.toggle_torch)
        self.snapshot_button = ttk.Button(commands, text="Istantanea sul PC", command=self.save_snapshot)
        self.command_buttons = (
            self.photo_button, self.video_button, self.audio_button, self.torch_button, self.snapshot_button
        )
        self.command_button_map = {
            "foto": self.photo_button,
            "video": self.video_button,
            "audio": self.audio_button,
            "torcia": self.torch_button,
            "istantanea": self.snapshot_button,
        }
        for row, button in enumerate(self.command_buttons):
            button.grid(row=row, column=0, sticky="ew", pady=2)

        status_frame = ttk.LabelFrame(side, text="Stato", padding=8)
        status_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.status_vars = {}
        for row, (key, label) in enumerate(
            (
                ("mode", "Modo"),
                ("recording", "Registrazione"),
                ("battery", "Batteria"),
                ("storage", "Spazio"),
                ("camera", "Fotocamera"),
            )
        ):
            ttk.Label(status_frame, text=f"{label}:").grid(row=row, column=0, sticky="nw", padx=(0, 6))
            variable = tk.StringVar(value="-")
            ttk.Label(status_frame, textvariable=variable, wraplength=230).grid(row=row, column=1, sticky="w")
            self.status_vars[key] = variable

        files = ttk.LabelFrame(side, text="File sul telefono", padding=8)
        files.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
        side.rowconfigure(2, weight=1)
        self.dir_var = tk.StringVar(value=MEDIA_DIRS[0][1])
        self.dir_box = ttk.Combobox(
            files, textvariable=self.dir_var, values=[label for _, label in MEDIA_DIRS], state="readonly", width=10
        )
        self.dir_box.grid(row=0, column=0, sticky="w")
        self.dir_box.bind("<<ComboboxSelected>>", lambda event: self.refresh_files())
        self.refresh_button = ttk.Button(files, text="Aggiorna", command=self.refresh_files)
        self.refresh_button.grid(row=0, column=1, sticky="e")
        self.files_tree = ttk.Treeview(files, columns=("size", "date"), height=8, selectmode="extended")
        self.files_tree.heading("#0", text="Nome")
        self.files_tree.heading("size", text="Dimensione")
        self.files_tree.heading("date", text="Data")
        self.files_tree.column("#0", width=200)
        self.files_tree.column("size", width=80, anchor="e")
        self.files_tree.column("date", width=120)
        self.files_tree.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=4)
        files.rowconfigure(1, weight=1)
        self.files_tree.bind("<Double-1>", self._on_file_double_click)
        self.download_button = ttk.Button(files, text="Scarica selezionati", command=self.download_selected)
        self.download_button.grid(row=2, column=0, columnspan=2, sticky="ew")
        transfer = ttk.Frame(files)
        transfer.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        transfer.columnconfigure(0, weight=1)
        self.transfer_bar = ttk.Progressbar(transfer, mode="determinate", maximum=1000)
        self.transfer_bar.grid(row=0, column=0, sticky="ew")
        self.transfer_cancel = ttk.Button(transfer, text="Annulla", width=8, command=self.cancel_downloads)
        self.transfer_cancel.grid(row=0, column=1, padx=(4, 0))
        self.transfer_cancel.state(["disabled"])
        self.transfer_var = tk.StringVar(value="")
        ttk.Label(transfer, textvariable=self.transfer_var, wraplength=330).grid(row=1, column=0, columnspan=2, sticky="w")

        log_frame = ttk.LabelFrame(root, text="Log", padding=4)
        log_frame.grid(row=3, column=0, sticky="ew", padx=8, pady=(4, 8))
        log_frame.columnconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=8, state="disabled", wrap="word")
        self.log_text.grid(row=0, column=0, sticky="ew")
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self.connection_state = "disconnected"
        self._set_connected(False)
        self._build_menu()
        self._bind_shortcuts()
        if Image is None or ImageTk is None:
            self.log("Pillow non installato: lo stream non si vede qui. pip install pillow, oppure 'Apri nel browser'.")

    def _shortcut_actions(self) -> dict[str, Callable[[], Any]]:
        return {
            "save_settings": self.save_settings,
            "export_log": self.export_log,
            "quit": self.close,
            "connect": lambda: self._invoke(self.connect_button),
            "photo": lambda: self._invoke(self.photo_button),
            "video": lambda: self._invoke(self.video_button),
            "audio": lambda: self._invoke(self.audio_button),
            "torch": lambda: self._invoke(self.torch_button),
            "snapshot": lambda: self._invoke(self.snapshot_button),
            "browser": self.open_browser,
            "refresh_files": lambda: self._invoke(self.refresh_button),
            "download": lambda: self._invoke(self.download_button),
            "clear_log": self.clear_log,
            "cancel": self.cancel_current,
            "help": self.show_shortcuts,
        }

    def _build_menu(self) -> None:
        actions = self._shortcut_actions()
        menubar = tk.Menu(self.root)
        # Voci di menu legate a un pulsante: prima di aprire il menu ne copiano testo e stato.
        self._menu_mirrors: list[tuple[tk.Menu, int, ttk.Button]] = []

        def add(menu: tk.Menu, label: str, name: str, button: ttk.Button | None = None) -> None:
            menu.add_command(label=label, command=actions[name], accelerator=SHORTCUTS[name].accelerator)
            if button is not None:
                self._menu_mirrors.append((menu, menu.index("end"), button))

        def mirror() -> None:
            for menu, index, button in self._menu_mirrors:
                menu.entryconfigure(
                    index, label=str(button.cget("text")), state="normal" if button.instate(["!disabled"]) else "disabled"
                )

        file_menu = tk.Menu(menubar, tearoff=False)
        add(file_menu, "Salva impostazioni", "save_settings")
        add(file_menu, "Esporta log...", "export_log")
        file_menu.add_separator()
        add(file_menu, "Esci", "quit")
        menubar.add_cascade(label="File", menu=file_menu)

        phone = tk.Menu(menubar, tearoff=False, postcommand=mirror)
        add(phone, "Connetti", "connect", self.connect_button)
        phone.add_separator()
        add(phone, "Foto", "photo", self.photo_button)
        add(phone, "Avvia video", "video", self.video_button)
        add(phone, "Avvia audio", "audio", self.audio_button)
        add(phone, "Accendi torcia", "torch", self.torch_button)
        add(phone, "Istantanea sul PC", "snapshot", self.snapshot_button)
        phone.add_separator()
        add(phone, "Apri nel browser", "browser")
        add(phone, "Aggiorna i file", "refresh_files", self.refresh_button)
        add(phone, "Scarica selezionati", "download", self.download_button)
        menubar.add_cascade(label="Telefono", menu=phone)

        apk = tk.Menu(menubar, tearoff=False, postcommand=mirror)
        for action, button in self.action_buttons.items():
            apk.add_command(label=str(button.cget("text")), command=button.invoke)
            self._menu_mirrors.append((apk, apk.index("end"), button))
        apk.add_command(label="Installa APK da file...", command=self.install_from_file)
        self._menu_mirrors.append((apk, apk.index("end"), self.install_file_button))
        apk.add_command(label="Pagina compilazioni", command=self.open_builds_page)
        apk.add_separator()
        apk.add_command(label="Interrompi", command=self.cancel_deploy)
        self._menu_mirrors.append((apk, apk.index("end"), self.cancel_button))
        menubar.add_cascade(label="APK", menu=apk)

        view = tk.Menu(menubar, tearoff=False)
        add(view, "Pulisci log", "clear_log")
        menubar.add_cascade(label="Visualizza", menu=view)

        help_menu = tk.Menu(menubar, tearoff=False)
        add(help_menu, "Scorciatoie da tastiera", "help")
        help_menu.add_command(label="Informazioni", command=self.show_about)
        menubar.add_cascade(label="Aiuto", menu=help_menu)

        self.root.configure(menu=menubar)
        self.menubar = menubar

    def _bind_shortcuts(self) -> None:
        for name, action in self._shortcut_actions().items():
            handler = self._shortcut_handler(SHORTCUTS[name], action)
            for sequence in shortcut_sequences(SHORTCUTS[name]):
                self.root.bind(sequence, handler)

    def _shortcut_handler(self, shortcut: Shortcut, action: Callable[[], Any]) -> Callable[[Any], str | None]:
        def handler(event: Any) -> str | None:
            if not shortcut.text_safe and is_text_input(getattr(event, "widget", None)):
                return None
            action()
            return "break"

        return handler

    def _on_field_return(self, event: Any) -> None:
        # Tk passa anche Ctrl+Invio a un legame su <Return>: quello lo gestisce la scorciatoia, o si connetterebbe due volte.
        if getattr(event, "state", 0) & 0x4:
            return
        if self.client is None:
            self.toggle_connection()

    @staticmethod
    def _invoke(button: ttk.Button) -> None:
        """Come un clic: un pulsante disabilitato (comando in corso, non connesso) non fa nulla."""
        if button.instate(["!disabled"]):
            button.invoke()

    # --- thread Tk ---------------------------------------------------------------------------------

    def log(self, text: str) -> None:
        if self._closing:
            return
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{datetime.now():%H:%M:%S}  {text}\n")
        # buildozer -v scrive migliaia di righe: oltre il limite si tolgono le più vecchie.
        lines = int(self.log_text.index("end-1c").split(".")[0])
        if lines > LOG_MAX_LINES:
            self.log_text.delete("1.0", f"{lines - LOG_MAX_LINES}.0")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def export_log(self) -> None:
        dest = filedialog.asksaveasfilename(
            initialfile=f"gioco_log_{datetime.now():%Y%m%d_%H%M%S}.txt", initialdir=self.download_dir,
            defaultextension=".txt", filetypes=[("Testo", "*.txt")], title="Esporta il log",
        )
        if not dest:
            return
        try:
            write_bytes_atomic(dest, self.log_text.get("1.0", "end-1c").encode("utf-8"))
        except OSError as exc:
            self.log(f"Log non esportato: {exc}")
            return
        self.log(f"Log esportato in {dest}")

    def cancel_current(self) -> None:
        """Esc: il download si annulla subito, la compilazione (che può durare minuti) solo dopo conferma."""
        if self._download_batch is not None:
            self.cancel_downloads()
            return
        if self._runner is not None and messagebox.askyesno(
            "Interrompere?", "Interrompere l'operazione sull'APK in corso?", parent=self.root
        ):
            self.cancel_deploy()

    def show_shortcuts(self) -> None:
        lines = [f"{SHORTCUTS[name].accelerator}:  {text}" for name, text in SHORTCUT_HELP]
        lines.append("")
        lines.append("Mentre scrivi in un campo valgono solo Ctrl+S, Ctrl+Q, Ctrl+Invio, F1, F5 ed Esc.")
        messagebox.showinfo("Scorciatoie da tastiera", "\n".join(lines), parent=self.root)

    def about_text(self) -> str:
        pillow = "non installato"
        if Image is not None:
            import PIL

            pillow = getattr(PIL, "__version__", "?")
        return "\n".join(
            (
                f"Gioco - controllo telefono {__version__}",
                f"Python {platform.python_version()} ({sys.platform})",
                f"Tk {self.root.tk.call('info', 'patchlevel')}",
                f"Pillow {pillow}",
                f"Impostazioni: {self.settings_store.path}",
            )
        )

    def show_about(self) -> None:
        messagebox.showinfo("Informazioni", self.about_text(), parent=self.root)

    def _set_connected(self, connected: bool):
        self.connect_button.configure(text="Disconnetti" if connected else "Connetti")
        for widget in (self.refresh_button, self.download_button):
            widget.state(["!disabled"] if connected else ["disabled"])
        self._refresh_command_buttons()
        if not connected:
            self._set_state("disconnected")

    # --- impostazioni e cronologia ------------------------------------------------------------------

    def _settings_fields(self) -> dict[str, Any]:
        return {
            "host": self.host_var,
            "port": self.port_var,
            "token": self.token_var,
            "mode": self.mode_var,
            "adb": self.adb_var,
            "repo": self.repo_var,
            "branch": self.branch_var,
            "apk_dir": self.apk_dir_var,
            "project_dir": self.project_var,
            "buildozer": self.buildozer_var,
            "wsl_distro": self.distro_var,
            "media_dir": self.dir_var,
        }

    def _load_settings(self) -> None:
        data = self.settings_store.load()
        if self.settings_store.load_problem:
            self.log(self.settings_store.load_problem)
        for key, variable in self._settings_fields().items():
            value = data.get(key)
            if isinstance(value, str) and value:
                variable.set(value)
        if self.mode_var.get() not in ACTION_LABELS:
            self.mode_var.set("github" if self._host == "windows" else "wsl")
        if self.dir_var.get() not in [label for _, label in MEDIA_DIRS]:
            self.dir_var.set(MEDIA_DIRS[0][1])
        self.remember_github_token_var.set(bool(data.get("remember_github_token")))
        saved_token = data.get("github_token")
        if self.remember_github_token_var.get() and isinstance(saved_token, str) and saved_token:
            if not self.github_token_var.get():
                self.github_token_var.set(saved_token)
        download_dir = data.get("download_dir")
        if isinstance(download_dir, str) and os.path.isdir(download_dir):
            self.download_dir = download_dir
        self.history = []
        history = data.get("history")
        if isinstance(history, list):
            self.history = [entry for entry in history if isinstance(entry, dict) and isinstance(entry.get("host"), str)][
                :HISTORY_LIMIT
            ]
        self._refresh_history_box()
        geometry = valid_geometry(data.get("geometry"), self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        if geometry:
            self.root.geometry(geometry)
        self._on_mode_change()

    def save_settings(self, quiet: bool = False) -> bool:
        data: dict[str, Any] = {key: variable.get() for key, variable in self._settings_fields().items()}
        data["history"] = self.history
        data["download_dir"] = self.download_dir
        data["remember_github_token"] = bool(self.remember_github_token_var.get())
        if data["remember_github_token"]:
            data["github_token"] = self.github_token_var.get().strip()
        data["geometry"] = self.root.geometry()
        try:
            self.settings_store.save(data)
        except OSError as exc:
            self.log(f"Impostazioni non salvate in {self.settings_store.path}: {exc}")
            return False
        if not quiet:
            self.log(f"Impostazioni salvate in {self.settings_store.path}")
        return True

    def _remember_current_connection(self) -> None:
        try:
            host, _, _ = parse_phone_address(self.host_var.get())
        except ValueError:
            return
        port = as_int(self.port_var.get(), DEFAULT_PORT)
        self.history = remember_connection(self.history, host, port, self.token_var.get().strip())
        self._refresh_history_box()
        self.save_settings(quiet=True)

    def _refresh_history_box(self) -> None:
        self.host_box.configure(values=[history_label(entry) for entry in self.history])

    def _on_history_selected(self, event=None) -> None:
        index = self.host_box.current()
        if not 0 <= index < len(self.history):
            return
        entry = self.history[index]
        self.host_var.set(entry.get("host", ""))
        self.port_var.set(str(as_int(entry.get("port"), DEFAULT_PORT)))
        self.token_var.set(entry.get("token") or "")

    def _set_state(self, state: str, detail: str = "") -> None:
        text, color = CONNECTION_STATES[state]
        self.connection_state = state
        self.state_label.configure(text=f"● {text}{f' - {detail}' if detail else ''}", foreground=color)

    def _refresh_command_buttons(self) -> None:
        """Abilita i comandi solo da connessi, non mentre sono già in corso e non se lo stato li renderebbe inutili."""
        connected = self.client is not None
        mode = self.status.get("mode") if connected else None
        blocked = {
            "foto": False,
            "video": mode == "audio",
            "audio": mode == "video",
            "torcia": False,
            "istantanea": False,
        }
        for label, button in self.command_button_map.items():
            enabled = connected and label not in self._busy_commands and not blocked[label]
            button.state(["!disabled"] if enabled else ["disabled"])

    @property
    def rotation(self) -> int:
        return self._sink.rotation

    @rotation.setter
    def rotation(self, value: int) -> None:
        self._sink.rotation = value

    def _on_video_resize(self, event):
        self._sink.box = (max(event.width, 1), max(event.height, 1))

    def _read_fields(self):
        try:
            host, parsed_port, parsed_token = parse_phone_address(self.host_var.get())
        except ValueError as exc:
            self.log(f"Indirizzo non valido: {exc}")
            return None
        # Se nel campo IP è stato incollato l'URL della scheda, porta e token vengono presi da lì.
        if parsed_port is not None:
            self.port_var.set(str(parsed_port))
        if parsed_token:
            self.token_var.set(parsed_token)
        if parsed_port is not None or parsed_token:
            self.host_var.set(host)
        token = self.token_var.get().strip()
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            port = 0
        if not host or not token or not 0 < port < 65536:
            self.log("Servono IP, porta (1-65535) e token: li mostra la scheda sul telefono.")
            return None
        return PhoneClient(host, port, token)

    def ui_call(self, function: Callable[..., Any], *args: Any) -> None:
        """Chiede al thread Tk di eseguire function(*args). Sicura da qualunque thread."""
        self.events.put((function, args))

    def log_from_thread(self, text: str) -> None:
        self.ui_call(self.log, text)

    def run_in_thread(
        self,
        label: str,
        work: Callable[[], Any],
        on_success: Callable[[Any], Any] | None = None,
        on_error: Callable[[Exception], Any] | None = None,
        session: int | None = None,
    ) -> None:
        """Esegue work() in un thread; esito ed errore tornano sul thread Tk tramite la coda.

        Con session, l'esito viene scartato se nel frattempo la connessione è cambiata.
        """

        def deliver(callback: Callable[..., Any] | None, value: Any) -> None:
            if session is not None and session != self._session:
                return
            if callback is not None:
                callback(value)

        def runner() -> None:
            try:
                value = work()
            except Exception as exc:
                if on_error is None:
                    self.ui_call(deliver, lambda error: self.log(f"{label}: {error}"), exc)
                else:
                    self.ui_call(deliver, on_error, exc)
            else:
                self.ui_call(deliver, on_success, value)

        threading.Thread(target=runner, name=f"rete-{label}", daemon=True).start()

    def _pump(self) -> None:
        deadline = time.monotonic() + PUMP_BUDGET_SECONDS
        try:
            while time.monotonic() < deadline:
                try:
                    function, args = self.events.get_nowait()
                except queue.Empty:
                    break
                try:
                    function(*args)
                except Exception:
                    # Un esito malformato non deve fermare la coda: senza questo il pannello resterebbe congelato.
                    self._log_exception("errore interno")
            self._show_latest_frame()
        finally:
            if not self._closing:
                self._pump_job = self.root.after(PUMP_INTERVAL_MS, self._pump)

    def _log_exception(self, context: str) -> None:
        details = traceback.format_exc().strip().splitlines()
        self.log(f"{context}: {details[-1] if details else 'sconosciuto'}")

    def _report_tk_exception(self, exc_type, exc_value, exc_traceback) -> None:
        last = traceback.format_exception_only(exc_type, exc_value)[-1].strip()
        self.log(f"errore nell'interfaccia: {last}")

    def _show_latest_frame(self):
        frame = self._sink.take()
        if frame is not None and ImageTk is not None:
            if self._photo_image is not None and self._photo_size == frame.size:
                # Stessa dimensione: si riscrivono i pixel invece di creare una nuova immagine Tk a ogni fotogramma.
                self._photo_image.paste(frame)
            else:
                self._photo_image = ImageTk.PhotoImage(frame)
                self._photo_size = frame.size
                self.video_label.configure(image=self._photo_image, text="")
        now = time.monotonic()
        if now - self._fps_since >= FPS_INTERVAL_SECONDS:
            fps = self._sink.take_count() / (now - self._fps_since)
            self._fps_since = now
            if self._stream is not None and not self._stream.stopped:
                bad = self._sink.bad_frames
                bad_text = f", {bad} illeggibili scartati" if bad else ""
                self.fps_var.set(f"{fps:.1f} fotogrammi/s, rotazione {self.rotation}°{bad_text}")

    def toggle_connection(self):
        if self.client is not None:
            self.disconnect()
            return
        client = self._read_fields()
        if client is None:
            return
        self.log(f"Connessione a {client.base} ...")
        self.connect_button.state(["disabled"])
        self._set_state("connecting")
        self._session += 1

        def work():
            return client.info(), client.status()

        def failed(exc: Exception) -> None:
            self.connect_button.state(["!disabled"])
            self.log(f"connessione: {exc}")
            if isinstance(exc, ApiError) and exc.code == "token":
                self._set_state("rejected")
            else:
                self._set_state("disconnected", "connessione non riuscita")

        def connected(result):
            info, status = result
            self.client = client
            self.rotation = as_int(_as_dict(info).get("rotation"))
            self.connect_button.state(["!disabled"])
            self._status_failures = 0
            self._busy_commands.clear()
            self._set_connected(True)
            self._set_state("connected", client.base.removeprefix("http://"))
            self.log(f"Connesso: {info.get('width')}x{info.get('height')}, rotazione {self.rotation}°")
            self._remember_current_connection()
            self._apply_status(status)
            self._start_stream()
            self._schedule_status()
            self.refresh_files()

        self.run_in_thread("connessione", work, connected, failed, session=self._session)

    def disconnect(self):
        self._session += 1
        self._status_busy = False
        self._status_failures = 0
        self._busy_commands.clear()
        self._stop_stream()
        self.cancel_downloads()
        if self._status_job is not None:
            self.root.after_cancel(self._status_job)
            self._status_job = None
        self.client = None
        self._set_connected(False)
        self.video_label.configure(image="", text="Non connesso")
        self._photo_image = None
        self._photo_size = None
        self.fps_var.set("")
        self.log("Disconnesso")

    def _deploy_settings(self) -> DeploySettings:
        return DeploySettings(
            host=self._host,
            project_dir=self.project_var.get().strip() or DEFAULT_PROJECT_DIR,
            buildozer=self.buildozer_var.get().strip() or DEFAULT_BUILDOZER,
            wsl_distro=self.distro_var.get().strip(),
            adb=self.adb_var.get().strip() or default_adb(self._host),
        )

    def _on_mode_change(self):
        github = self.mode_var.get() == "github"
        if github:
            self.wsl_fields.grid_remove()
            self.github_fields.grid()
            self.builds_page_button.grid()
        else:
            self.github_fields.grid_remove()
            self.wsl_fields.grid()
            self.builds_page_button.grid_remove()
        for action, button in self.action_buttons.items():
            button.configure(text=ACTION_LABELS[self.mode_var.get()][action][0])

    def _github_builds(self) -> GitHubBuilds:
        return GitHubBuilds(
            self.repo_var.get().strip() or DEFAULT_REPO,
            self.branch_var.get().strip() or DEFAULT_BRANCH,
            self.github_token_var.get().strip(),
        )

    def open_builds_page(self):
        try:
            url = self._github_builds().page_url()
        except DeployError as exc:
            self.log(str(exc))
            return
        webbrowser.open(url)
        self.log(f"Aperta la pagina delle compilazioni: {url}")

    def install_from_file(self):
        path = filedialog.askopenfilename(
            title="APK da installare (o zip scaricato da GitHub)",
            filetypes=[("APK o zip di GitHub", "*.apk *.zip"), ("Tutti i file", "*.*")],
        )
        if path:
            self.deploy("install_file", apk_path=path)

    def deploy(self, action: str, apk_path: str | None = None):
        if self._runner is not None:
            return
        settings = self._deploy_settings()
        mode = self.mode_var.get()
        try:
            builds = self._github_builds() if mode == "github" else None
        except DeployError as exc:
            self.log(str(exc))
            return
        dest_dir = self.apk_dir_var.get().strip() or default_apk_dir()
        runner = ProcessRunner()
        self._runner = runner
        for button in self.deploy_buttons:
            button.state(["disabled"])
        self.cancel_button.state(["!disabled"])
        self.deploy_progress.configure(mode="indeterminate", value=0)
        self.deploy_progress.grid()
        self.deploy_progress.start(15)
        if action == "install_file":
            self.deploy_var.set("In corso: installazione da file...")
        else:
            self.deploy_var.set(f"In corso: {ACTION_LABELS[mode][action][1]}...")

        emit = self.log_from_thread

        def work():
            deployer = Deployer(settings, runner, emit)
            if action == "install_file":
                deployer.install_apk(apk_from_file(apk_path, os.path.join(dest_dir, "da-file")))
                return action, None
            if builds is not None:
                pipeline = GitHubPipeline(
                    deployer, builds, dest_dir, emit, lambda: runner.cancelled,
                    lambda done, total: self.ui_call(self._deploy_download_progress, done, total),
                )
                return action, getattr(pipeline, action)()
            return action, getattr(deployer, action)()

        def failed(exc: Exception) -> None:
            self.log(f"apk: {exc}")
            self._deploy_finished("errore: vedi il log")

        self.run_in_thread("apk", work, self._deploy_done, failed)

    def _deploy_done(self, result):
        action, value = result
        if action == "check":
            self._deploy_finished("pronto" if not value else f"{len(value)} problemi: vedi il log")
            return
        if action == "build" and value:
            self._deploy_finished("APK pronto")
            self.log(f"APK: {value}")
            return
        if action in ("launch", "everything"):
            token, port = value
            self._deploy_finished(f"app avviata, porta {port}")
            if self.client is not None:
                self.disconnect()
            self.host_var.set("127.0.0.1")
            self.port_var.set(str(port))
            self.token_var.set(token)
            self.toggle_connection()
            return
        self._deploy_finished("fatto")

    def _deploy_download_progress(self, done: int, total: int) -> None:
        if self._runner is None:
            return
        if total > 0:
            if str(self.deploy_progress.cget("mode")) != "determinate":
                self.deploy_progress.stop()
                self.deploy_progress.configure(mode="determinate")
            self.deploy_progress.configure(value=min(1000, int(done * 1000 / total)))
        self.deploy_var.set(f"Download dell'APK: {human_size(done)} di {human_size(total) if total else '?'}")

    def _deploy_finished(self, text: str):
        self.deploy_progress.stop()
        self.deploy_progress.grid_remove()
        self._runner = None
        for button in self.deploy_buttons:
            button.state(["!disabled"])
        self.cancel_button.state(["disabled"])
        self.deploy_var.set(text)

    def cancel_deploy(self):
        if self._runner is not None:
            self._runner.cancel()
            self.log("Interruzione richiesta.")

    def open_browser(self):
        client = self.client or self._read_fields()
        if client is not None:
            webbrowser.open(client.page_url())
            self.log(f"Aperto nel browser: {client.page_url()}")

    def _schedule_status(self, delay_ms: int = STATUS_INTERVAL_MS):
        if self._status_job is not None:
            self.root.after_cancel(self._status_job)
        self._status_job = self.root.after(delay_ms, self._poll_status)

    def _poll_status(self):
        self._status_job = None
        if self.client is None:
            return
        if self._status_busy:
            self._schedule_status()
            return
        self.refresh_status(reschedule=True)

    def refresh_status(self, reschedule: bool = False):
        """Chiede /status. Con reschedule il prossimo controllo parte quando arriva questo, con l'attesa giusta."""
        if self.client is None or self._status_busy:
            return
        self._status_busy = True
        client = self.client

        def done(status: dict) -> None:
            self._apply_status(status)
            if reschedule:
                self._schedule_status(status_retry_delay_ms(0))

        def failed(exc: Exception) -> None:
            self._status_busy = False
            self._status_failed(exc)
            if reschedule:
                self._schedule_status(status_retry_delay_ms(self._status_failures))

        self.run_in_thread("stato", client.status, done, failed, session=self._session)

    def _status_failed(self, exc: Exception) -> None:
        self._status_failures += 1
        if isinstance(exc, ApiError) and exc.code == "token":
            if self.connection_state != "rejected":
                self.log("Token rifiutato: l'app sul telefono è stata riavviata? Inserisci il nuovo token e riconnetti.")
            self._set_state("rejected")
            return
        if self._status_failures == 1:
            self.log(f"stato: {exc}")
        else:
            if self.connection_state != "unreachable":
                self.log("Il telefono non risponde: continuo a riprovare con attese più lunghe.")
            self._set_state("unreachable", str(exc))

    def _apply_status(self, status: dict):
        self._status_busy = False
        if self._status_failures and self.client is not None:
            self.log("Telefono di nuovo raggiungibile.")
        self._status_failures = 0
        if self.client is not None and self.connection_state != "connected":
            self._set_state("connected", self.client.base.removeprefix("http://"))
        status = _as_dict(status)
        self.status = status
        camera = _as_dict(status.get("camera"))
        rotation = camera.get("rotation")
        if isinstance(rotation, int) and not isinstance(rotation, bool):
            self.rotation = rotation
        for key, text in describe_status(status).items():
            self.status_vars[key].set(text)
        mode = status.get("mode")
        torch = camera.get("torch")
        self.video_button.configure(text="Ferma video" if mode == "video" else "Avvia video")
        self.audio_button.configure(text="Ferma audio" if mode == "audio" else "Avvia audio")
        self.torch_button.configure(text="Spegni torcia" if torch else "Accendi torcia")
        self._refresh_command_buttons()

    def _command(self, label: str, work, describe):
        """Manda un comando al telefono; il suo pulsante resta disattivato finché non arriva la risposta."""
        client = self.client
        if client is None or label in self._busy_commands:
            return
        self._busy_commands.add(label)
        self._refresh_command_buttons()

        def finished() -> None:
            self._busy_commands.discard(label)
            self._refresh_command_buttons()
            self.refresh_status()

        def done(result):
            finished()
            self.log(describe(_as_dict(result)))
            self.refresh_files()

        def failed(exc: Exception) -> None:
            finished()
            self.log(f"{label}: {exc}")

        self.run_in_thread(label, lambda: work(client), done, failed, session=self._session)

    def take_photo(self):
        self._command("foto", lambda c: c.photo(), lambda r: f"Foto salvata: {self._file_text(r.get('file'))}")

    def toggle_video(self):
        start = self.status.get("mode") != "video"
        self._command(
            "video", lambda c: c.video(start), lambda r: self._recording_text("Video", start, r)
        )

    def toggle_audio(self):
        start = self.status.get("mode") != "audio"
        self._command(
            "audio", lambda c: c.audio(start), lambda r: self._recording_text("Audio", start, r)
        )

    def toggle_torch(self):
        on = not (self.status.get("camera") or {}).get("torch")
        self._command("torcia", lambda c: c.torch(on), lambda r: f"Torcia {'accesa' if r.get('torch') else 'spenta'}")

    def _file_text(self, entry) -> str:
        if not entry:
            return "-"
        return f"{entry.get('dir')}/{entry.get('name')} ({human_size(entry.get('size'))})"

    def _recording_text(self, label: str, start: bool, result: dict) -> str:
        if start:
            return f"{label} avviato: {self._file_text(result.get('file'))}"
        if result.get("saved"):
            return f"{label} salvato dopo {result.get('seconds')} s: {self._file_text(result.get('file'))}"
        return f"{label} troppo breve: file scartato"

    def _selected_dir(self) -> str:
        label = self.dir_var.get()
        for dirname, text in MEDIA_DIRS:
            if text == label:
                return dirname
        return MEDIA_DIRS[0][0]

    def refresh_files(self):
        if self.client is None:
            return
        dirname = self._selected_dir()
        client = self.client
        self.run_in_thread("file", lambda: client.files(dirname), self._show_files, session=self._session)

    def _show_files(self, result: dict):
        result = _as_dict(result)
        if result.get("dir") != self._selected_dir():
            return
        self.files_tree.delete(*self.files_tree.get_children())
        self._file_sizes = {}
        files = result.get("files")
        for entry in files if isinstance(files, list) else []:
            entry = _as_dict(entry)
            name = entry.get("name")
            if not isinstance(name, str) or not name:
                continue
            self._file_sizes[name] = as_int(entry.get("size")) or None
            self.files_tree.insert(
                "", "end", text=name, values=(human_size(entry.get("size")), format_timestamp(entry.get("modified")))
            )

    def _on_file_double_click(self, event) -> None:
        item = self.files_tree.identify_row(event.y)
        if item:
            self.files_tree.selection_set(item)
            self.download_selected()

    def download_selected(self):
        """Un file: si sceglie dove salvarlo. Più file: si sceglie la cartella e i nomi restano unici."""
        if self.client is None:
            return
        if self._download_batch is not None:
            self.log("C'è già un download in corso: aspetta che finisca o premi Annulla.")
            return
        names = [self.files_tree.item(item, "text") for item in self.files_tree.selection()]
        if not names:
            self.log("Seleziona uno o più file nell'elenco (Ctrl o Maiusc per selezionarne più di uno).")
            return
        dirname = self._selected_dir()
        if len(names) == 1:
            dest = filedialog.asksaveasfilename(
                initialfile=names[0], initialdir=self.download_dir, title="Salva il file del telefono"
            )
            if not dest:
                return
            self.download_dir = os.path.dirname(dest)
            items = [DownloadItem(dirname, names[0], dest, self._file_sizes.get(names[0]))]
        else:
            directory = filedialog.askdirectory(initialdir=self.download_dir, title=f"Cartella per {len(names)} file")
            if not directory:
                return
            self.download_dir = directory
            taken: set[str] = set()
            items = []
            for name in names:
                dest = unique_path(directory, name, taken)
                taken.add(dest)
                items.append(DownloadItem(dirname, name, dest, self._file_sizes.get(name)))
        self._start_downloads(items)

    def _start_downloads(self, items: list[DownloadItem]) -> None:
        session = self._session

        def on_progress(done: int, total: int, name: str, index: int, count: int) -> None:
            self.ui_call(self._show_transfer, session, done, total, name, index, count)

        batch = DownloadBatch(self.client, items, on_progress, self.log_from_thread)
        self._download_batch = batch
        self.download_button.state(["disabled"])
        self.transfer_cancel.state(["!disabled"])
        self.transfer_bar.configure(value=0)
        self.transfer_var.set(f"Download di {len(items)} file...")
        self.log(f"Download di {len(items)} file da {items[0].dirname} ...")

        def finished(report: DownloadReport) -> None:
            self._download_batch = None
            self.transfer_cancel.state(["disabled"])
            if self.client is not None:
                self.download_button.state(["!disabled"])
            parts = [f"{len(report.completed)} scaricati"]
            if report.failed:
                parts.append(f"{len(report.failed)} non riusciti")
            if report.cancelled:
                parts.append("annullato")
            summary = ", ".join(parts)
            self.transfer_var.set(summary)
            if not report.cancelled and not report.failed:
                self.transfer_bar.configure(value=1000)
            self.log(f"Download finito: {summary}.")

        def failed(exc: Exception) -> None:
            finished(DownloadReport([], [(item, str(exc)) for item in items], batch.cancelled))

        self.run_in_thread("download", batch.run, finished, failed)

    def _show_transfer(self, session: int, done: int, total: int, name: str, index: int, count: int) -> None:
        if self._download_batch is None:
            return
        if total > 0:
            self.transfer_bar.configure(value=min(1000, int(done * 1000 / total)))
        total_text = human_size(total) if total else "?"
        position = f" ({index + 1}/{count})" if count > 1 else ""
        self.transfer_var.set(f"{name}{position}: {human_size(done)} di {total_text}")

    def cancel_downloads(self) -> None:
        if self._download_batch is not None:
            self._download_batch.cancel()
            self.transfer_var.set("Annullamento...")

    def save_snapshot(self) -> None:
        if self.client is None:
            return
        name = f"istantanea_{datetime.now():%Y%m%d_%H%M%S}.jpg"
        dest = filedialog.asksaveasfilename(
            initialfile=name, initialdir=self.download_dir, defaultextension=".jpg",
            filetypes=[("JPEG", "*.jpg")], title="Salva l'istantanea dello stream",
        )
        if not dest:
            return
        self.download_dir = os.path.dirname(dest)

        def work(client: PhoneClient) -> dict:
            data = client.snapshot()
            write_bytes_atomic(dest, data)
            return {"size": len(data)}

        self._command("istantanea", work, lambda r: f"Istantanea salvata in {dest} ({human_size(r.get('size'))})")

    def _start_stream(self):
        if Image is None or ImageTk is None:
            self.video_label.configure(text="Pillow non installato: usa 'Apri nel browser'")
            return
        self._stop_stream()
        self._sink.reset()
        self._bad_frames_logged = 0
        self.video_label.configure(text="Stream in arrivo...")
        session = self._session

        def on_event(text: str) -> None:
            self.ui_call(self._stream_event, session, text)

        self._stream = StreamWorker(self.client, self._on_stream_frame, on_event)
        self._stream.start()

    def _stop_stream(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream = None

    def _stream_event(self, session: int, text: str) -> None:
        if session == self._session:
            self.log(text)

    def _on_stream_frame(self, jpeg: bytes) -> None:
        """Thread dello stream: decodifica e basta. Un fotogramma illeggibile si scarta senza chiudere lo stream."""
        problem = self._sink.push(jpeg)
        if problem is not None and self._sink.bad_frames in (1, 10, 100, 1000):
            self.log_from_thread(f"Fotogramma illeggibile scartato ({self._sink.bad_frames} in tutto): {problem}")

    def close(self):
        if self._closing:
            return
        if self._runner is not None:
            self._runner.cancel()
        if self.client is not None:
            self.disconnect()
        self.save_settings(quiet=True)
        self._closing = True
        # Un after rimasto in coda scatterebbe su un comando Tcl già cancellato da destroy().
        for job in (self._pump_job, self._status_job):
            if job is not None:
                try:
                    self.root.after_cancel(job)
                except tk.TclError:
                    pass
        self.root.destroy()


def main():
    if tk is None:
        raise SystemExit("Tkinter non è installato in questo Python: su Linux sudo apt install python3-tk")
    root = tk.Tk()
    ControlPanel(root)
    root.mainloop()


if __name__ == "__main__":
    main()
