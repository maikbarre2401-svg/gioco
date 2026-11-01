"""Diagnostica della pipeline: una riga su logcat con tag GIOCO per ogni stadio, solo con DEBUG = True."""

import ctypes
import sys
import threading
import time
from contextlib import contextmanager

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
