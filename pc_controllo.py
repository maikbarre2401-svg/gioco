#!/usr/bin/env python3
"""Pannello di controllo dal PC per l'app Gioco sul telefono: stream, comandi e file.

Avvio con doppio clic, oppure: python pc_controllo.py
Pillow serve solo a mostrare lo stream nella finestra (pip install pillow); senza Pillow
il pulsante "Apri nel browser" mostra lo stream nella pagina servita dal telefono.

La sezione "Telefono e APK" compila l'APK con buildozer dentro WSL2 (buildozer non gira su
Windows), lo installa con adb, concede i permessi, avvia l'app, legge token e porta dal log
del telefono, apre adb forward e si connette da sola.
"""

import io
import json
import os
import platform
import queue
import re
import shlex
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import zipfile
from dataclasses import dataclass
from datetime import datetime

try:
    import tkinter as tk
    from tkinter import filedialog, ttk
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
STREAM_TIMEOUT = 10.0
STREAM_RETRY_SECONDS = 2.0
STATUS_INTERVAL_MS = 2000
PUMP_INTERVAL_MS = 30
FPS_INTERVAL_SECONDS = 1.0
DOWNLOAD_CHUNK_BYTES = 256 * 1024
PROGRESS_STEP_BYTES = 2 * 1024 * 1024
MAX_PART_BYTES = 20 * 1024 * 1024
MEDIA_DIRS = (("photos", "Foto"), ("videos", "Video"), ("audio", "Audio"))
VIDEO_MIN_SIZE = (640, 480)
LOG_MAX_LINES = 4000

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


class PhoneClient:
    """Client HTTP del telefono. Ogni metodo blocca: va chiamato da un thread di rete, mai da Tk."""

    def __init__(self, host: str, port: int, token: str):
        self.base = f"http://{host}:{port}"
        self.token = token

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

    def _json(self, request: urllib.request.Request) -> dict:
        with self._open(request, HTTP_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))

    def post(self, endpoint: str, body: bytes = b"", **params) -> dict:
        return self._json(urllib.request.Request(self.url(endpoint, **params), data=body, method="POST"))

    def info(self) -> dict:
        return self._json(urllib.request.Request(self.url("/info.json"), method="GET"))

    def status(self) -> dict:
        return self.post("/status")

    def photo(self) -> dict:
        return self.post("/cmd/photo")

    def video(self, start: bool) -> dict:
        return self.post("/cmd/video/start" if start else "/cmd/video/stop")

    def audio(self, start: bool) -> dict:
        return self.post("/cmd/audio/start" if start else "/cmd/audio/stop")

    def torch(self, on: bool) -> dict:
        return self.post("/cmd/torch", b"on" if on else b"off")

    def files(self, dirname: str) -> dict:
        return self.post("/files", dir=dirname)

    def download(self, dirname: str, name: str, dest: str, progress=None, cancel=None) -> int:
        request = urllib.request.Request(self.url("/files/get", path=f"{dirname}/{name}"), data=b"", method="POST")
        partial = dest + ".part"
        received = 0
        reported = 0
        with self._open(request, HTTP_TIMEOUT) as response, open(partial, "wb") as handle:
            total = int(response.headers.get("Content-Length") or 0)
            while True:
                if cancel is not None and cancel.is_set():
                    raise ApiError(0, "annullato", "download annullato")
                chunk = response.read(DOWNLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                handle.write(chunk)
                received += len(chunk)
                if progress is not None and received - reported >= PROGRESS_STEP_BYTES:
                    reported = received
                    progress(received, total)
        if total and received != total:
            os.remove(partial)
            raise ApiError(0, "incompleto", f"ricevuti {received} byte su {total}")
        os.replace(partial, dest)
        return received

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


def human_size(size: int | None) -> str:
    if size is None:
        return "?"
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def describe_status(status: dict) -> dict:
    """Testi del pannello di stato a partire dalla risposta di /status."""
    mode = status.get("mode", "?")
    seconds = status.get("recording_seconds") or 0
    battery = status.get("battery")
    storage = status.get("storage")
    camera = status.get("camera") or {}
    if battery:
        battery_text = f"{battery['percent']}%{' in carica' if battery.get('charging') else ''}"
    else:
        battery_text = "non disponibile"
    if storage:
        storage_text = f"{human_size(storage['free_bytes'])} liberi su {human_size(storage['total_bytes'])}"
    else:
        storage_text = "non disponibile"
    if camera.get("open"):
        size = camera.get("preview_size")
        size_text = f" {size[0]}x{size[1]}" if size else ""
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


class DeployError(Exception):
    pass


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
        if process is not None and process.poll() is None:
            process.terminate()


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
        while found is None:
            found = parse_server_line("\n".join(self.adb("logcat", "-d", "-s", "python:I", label="lettura del log")))
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
        with bundle.open(members[0]) as source, open(path, "wb") as target:
            shutil.copyfileobj(source, target)
    return path


def apk_from_file(path: str, work_dir: str) -> str:
    """Un .apk si installa così com'è; lo zip scaricato dalla pagina di GitHub va prima aperto."""
    if path.lower().endswith(".zip"):
        return extract_apk(path, work_dir)
    return path


class GitHubBuilds:
    """APK compilati da GitHub Actions (workflow camera-apk.yml). Blocca: solo da un thread di lavoro."""

    def __init__(self, repo: str, branch: str, token: str, workflow: str = WORKFLOW_FILE, api: str = GITHUB_API):
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
            raise DeployError(f"GitHub ha risposto {exc.code}: {body[:200]}") from None
        except (urllib.error.URLError, OSError) as exc:
            raise DeployError(f"GitHub non raggiungibile: {getattr(exc, 'reason', exc)}") from None

    def _json(self, url: str) -> dict:
        with self._open(url) as response:
            return json.loads(response.read().decode("utf-8"))

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

    def download_apk(self, build: dict, dest_dir: str, log=None, should_stop=None) -> str:
        target_dir = os.path.join(dest_dir, str(build["artifact_id"]))
        if os.path.isdir(target_dir):
            for name in os.listdir(target_dir):
                if name.lower().endswith(".apk"):
                    path = os.path.join(target_dir, name)
                    if log is not None:
                        log(f"APK già scaricato: {path}")
                    return path
        if not self.token:
            raise DeployError(
                "per scaricare l'APK da GitHub serve un token con Actions: Read; in alternativa scaricalo "
                "dalla pagina delle compilazioni e usa 'Installa APK da file...'"
            )
        os.makedirs(target_dir, exist_ok=True)
        archive = target_dir + ".zip.part"
        received = 0
        reported = 0
        with self._open(build["download_url"]) as response, open(archive, "wb") as handle:
            while True:
                if should_stop is not None and should_stop():
                    raise DeployError("interrotto")
                chunk = response.read(DOWNLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                handle.write(chunk)
                received += len(chunk)
                if log is not None and received - reported >= PROGRESS_STEP_BYTES:
                    reported = received
                    log(f"  scaricati {human_size(received)}")
        try:
            path = extract_apk(archive, target_dir)
        finally:
            os.remove(archive)
        if log is not None:
            log(f"APK salvato in {path}")
        return path


class GitHubPipeline:
    """Le stesse azioni di Deployer, ma l'APK arriva già compilato da GitHub Actions: sul PC basta adb."""

    def __init__(self, deployer: Deployer, builds: GitHubBuilds, dest_dir: str, log, should_stop=None):
        self.deployer = deployer
        self.builds = builds
        self.dest_dir = dest_dir
        self._log = log
        self._should_stop = should_stop

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
        return self.builds.download_apk(build, self.dest_dir, self._log, self._should_stop)

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


class ControlPanel:
    """Finestra Tk. Regola: i thread di rete mettono messaggi in coda, solo _pump (thread Tk) tocca i widget."""

    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.client = None
        self.status = {}
        self.rotation = 0
        self._stream_stop = None
        self._stream_response = None
        self._frame_lock = threading.Lock()
        self._latest_frame = None
        self._frames = 0
        self._fps_since = time.monotonic()
        self._photo_image = None
        self._video_box = VIDEO_MIN_SIZE
        self._status_job = None
        self._status_busy = False
        self._host = detect_host()
        self._runner = None
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(PUMP_INTERVAL_MS, self._pump)

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
        self.deploy_var = tk.StringVar(value="")
        ttk.Label(actions, textvariable=self.deploy_var).grid(row=0, column=8, padx=(12, 0))
        self._on_mode_change()

        connection = ttk.LabelFrame(root, text="Connessione", padding=8)
        connection.grid(row=1, column=0, sticky="ew", padx=8, pady=4)
        self.host_var = tk.StringVar()
        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))
        self.token_var = tk.StringVar()
        for column, (label, variable, width) in enumerate(
            (("IP", self.host_var, 16), ("Porta", self.port_var, 6), ("Token", self.token_var, 12))
        ):
            ttk.Label(connection, text=label).grid(row=0, column=column * 2, padx=(0, 4))
            ttk.Entry(connection, textvariable=variable, width=width).grid(row=0, column=column * 2 + 1, padx=(0, 12))
        self.connect_button = ttk.Button(connection, text="Connetti", command=self.toggle_connection)
        self.connect_button.grid(row=0, column=6, padx=(0, 8))
        ttk.Button(connection, text="Apri nel browser", command=self.open_browser).grid(row=0, column=7)

        body = ttk.Frame(root)
        body.grid(row=2, column=0, sticky="nsew", padx=8, pady=4)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        video_frame = ttk.LabelFrame(body, text="Stream", padding=4)
        video_frame.grid(row=0, column=0, sticky="nsew")
        video_frame.columnconfigure(0, weight=1)
        video_frame.rowconfigure(0, weight=1)
        self.video_label = tk.Label(video_frame, background="black", foreground="#cccccc", text="Non connesso")
        self.video_label.grid(row=0, column=0, sticky="nsew")
        self.video_label.bind("<Configure>", self._on_video_resize)
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
        self.command_buttons = (self.photo_button, self.video_button, self.audio_button, self.torch_button)
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
        self.files_tree = ttk.Treeview(files, columns=("size", "date"), height=8, selectmode="browse")
        self.files_tree.heading("#0", text="Nome")
        self.files_tree.heading("size", text="Dimensione")
        self.files_tree.heading("date", text="Data")
        self.files_tree.column("#0", width=200)
        self.files_tree.column("size", width=80, anchor="e")
        self.files_tree.column("date", width=120)
        self.files_tree.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=4)
        files.rowconfigure(1, weight=1)
        self.download_button = ttk.Button(files, text="Scarica", command=self.download_selected)
        self.download_button.grid(row=2, column=0, columnspan=2, sticky="ew")

        log_frame = ttk.LabelFrame(root, text="Log", padding=4)
        log_frame.grid(row=3, column=0, sticky="ew", padx=8, pady=(4, 8))
        log_frame.columnconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=8, state="disabled", wrap="word")
        self.log_text.grid(row=0, column=0, sticky="ew")
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self._set_connected(False)
        if Image is None or ImageTk is None:
            self.log("Pillow non installato: lo stream non si vede qui. pip install pillow, oppure 'Apri nel browser'.")

    # --- thread Tk ---------------------------------------------------------------------------------

    def log(self, text: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{datetime.now():%H:%M:%S}  {text}\n")
        # buildozer -v scrive migliaia di righe: oltre il limite si tolgono le più vecchie.
        lines = int(self.log_text.index("end-1c").split(".")[0])
        if lines > LOG_MAX_LINES:
            self.log_text.delete("1.0", f"{lines - LOG_MAX_LINES}.0")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_connected(self, connected: bool):
        self.connect_button.configure(text="Disconnetti" if connected else "Connetti")
        for widget in self.command_buttons + (self.refresh_button, self.download_button):
            widget.state(["!disabled"] if connected else ["disabled"])

    def _on_video_resize(self, event):
        # Dimensione letta dal thread dello stream: è una tupla Python, non un widget.
        self._video_box = (max(event.width, 1), max(event.height, 1))

    def _read_fields(self):
        host = self.host_var.get().strip()
        token = self.token_var.get().strip()
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            port = 0
        if not host or not token or not 0 < port < 65536:
            self.log("Servono IP, porta (1-65535) e token: li mostra la scheda sul telefono.")
            return None
        return PhoneClient(host, port, token)

    def run_in_thread(self, label: str, work, on_success=None):
        """Esegue work() in un thread; il risultato torna sul thread Tk tramite la coda."""

        def runner():
            try:
                value = work()
            except Exception as exc:
                self.events.put(("error", label, exc))
            else:
                self.events.put(("done", on_success, value))

        threading.Thread(target=runner, name=f"rete-{label}", daemon=True).start()

    def _pump(self):
        try:
            while True:
                kind, first, second = self.events.get_nowait()
                if kind == "done":
                    if first is not None:
                        first(second)
                elif kind == "error":
                    self.log(f"{first}: {second}")
                    if first == "stato":
                        self._status_busy = False
                    elif first == "connessione":
                        self.connect_button.state(["!disabled"])
                    elif first == "apk":
                        self._deploy_finished("errore: vedi il log")
                elif kind == "log":
                    self.log(first)
        except queue.Empty:
            pass
        self._show_latest_frame()
        self.root.after(PUMP_INTERVAL_MS, self._pump)

    def _show_latest_frame(self):
        with self._frame_lock:
            frame, self._latest_frame = self._latest_frame, None
        if frame is not None and ImageTk is not None:
            self._photo_image = ImageTk.PhotoImage(frame)
            self.video_label.configure(image=self._photo_image, text="")
        now = time.monotonic()
        if now - self._fps_since >= FPS_INTERVAL_SECONDS:
            fps = self._frames / (now - self._fps_since)
            self._frames = 0
            self._fps_since = now
            if self._stream_stop is not None and not self._stream_stop.is_set():
                self.fps_var.set(f"{fps:.1f} fotogrammi/s, rotazione {self.rotation}°")

    def toggle_connection(self):
        if self.client is not None:
            self.disconnect()
            return
        client = self._read_fields()
        if client is None:
            return
        self.log(f"Connessione a {client.base} ...")
        self.connect_button.state(["disabled"])

        def work():
            return client.info(), client.status()

        def connected(result):
            info, status = result
            self.client = client
            self.rotation = int(info.get("rotation") or 0)
            self.connect_button.state(["!disabled"])
            self._set_connected(True)
            self.log(f"Connesso: {info.get('width')}x{info.get('height')}, rotazione {self.rotation}°")
            self._apply_status(status)
            self._start_stream()
            self._schedule_status()
            self.refresh_files()

        self.run_in_thread("connessione", work, connected)

    def disconnect(self):
        if self._stream_stop is not None:
            self._stream_stop.set()
        response = self._stream_response
        if response is not None:
            # Chiudere la risposta sblocca la readline del thread dello stream.
            try:
                response.close()
            except Exception:
                pass
        if self._status_job is not None:
            self.root.after_cancel(self._status_job)
            self._status_job = None
        self.client = None
        self._set_connected(False)
        self.video_label.configure(image="", text="Non connesso")
        self._photo_image = None
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
        if action == "install_file":
            self.deploy_var.set("In corso: installazione da file...")
        else:
            self.deploy_var.set(f"In corso: {ACTION_LABELS[mode][action][1]}...")

        def emit(line):
            self.events.put(("log", line, None))

        def work():
            deployer = Deployer(settings, runner, emit)
            if action == "install_file":
                deployer.install_apk(apk_from_file(apk_path, os.path.join(dest_dir, "da-file")))
                return action, None
            if builds is not None:
                pipeline = GitHubPipeline(deployer, builds, dest_dir, emit, lambda: runner.cancelled)
                return action, getattr(pipeline, action)()
            return action, getattr(deployer, action)()

        self.run_in_thread("apk", work, self._deploy_done)

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

    def _deploy_finished(self, text: str):
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

    def _schedule_status(self):
        self._status_job = self.root.after(STATUS_INTERVAL_MS, self._poll_status)

    def _poll_status(self):
        self._status_job = None
        if self.client is None:
            return
        if not self._status_busy:
            self.refresh_status()
        self._schedule_status()

    def refresh_status(self):
        if self.client is None:
            return
        self._status_busy = True
        client = self.client
        self.run_in_thread("stato", client.status, self._apply_status)

    def _apply_status(self, status: dict):
        self._status_busy = False
        self.status = status
        rotation = (status.get("camera") or {}).get("rotation")
        if isinstance(rotation, int):
            self.rotation = rotation
        for key, text in describe_status(status).items():
            self.status_vars[key].set(text)
        mode = status.get("mode")
        torch = (status.get("camera") or {}).get("torch")
        self.video_button.configure(text="Ferma video" if mode == "video" else "Avvia video")
        self.audio_button.configure(text="Ferma audio" if mode == "audio" else "Avvia audio")
        self.torch_button.configure(text="Spegni torcia" if torch else "Accendi torcia")

    def _command(self, label: str, work, describe):
        client = self.client
        if client is None:
            return

        def done(result):
            self.log(describe(result))
            self.refresh_status()
            self.refresh_files()

        self.run_in_thread(label, lambda: work(client), done)

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
        self.run_in_thread("file", lambda: client.files(dirname), self._show_files)

    def _show_files(self, result: dict):
        if result.get("dir") != self._selected_dir():
            return
        self.files_tree.delete(*self.files_tree.get_children())
        for entry in result.get("files", []):
            modified = entry.get("modified")
            date = datetime.fromtimestamp(modified).strftime("%Y-%m-%d %H:%M") if modified else "?"
            self.files_tree.insert("", "end", text=entry["name"], values=(human_size(entry.get("size")), date))

    def download_selected(self):
        if self.client is None:
            return
        selection = self.files_tree.selection()
        if not selection:
            self.log("Seleziona un file nell'elenco.")
            return
        name = self.files_tree.item(selection[0], "text")
        dirname = self._selected_dir()
        dest = filedialog.asksaveasfilename(initialfile=name, title="Salva il file del telefono")
        if not dest:
            return
        client = self.client
        self.log(f"Download di {dirname}/{name} ...")

        def progress(received, total):
            total_text = human_size(total) if total else "?"
            self.events.put(("log", f"  {name}: {human_size(received)} di {total_text}", None))

        self.run_in_thread(
            "download",
            lambda: client.download(dirname, name, dest, progress=progress),
            lambda size: self.log(f"Scaricato {name} ({human_size(size)}) in {dest}"),
        )

    def _start_stream(self):
        if Image is None or ImageTk is None:
            self.video_label.configure(text="Pillow non installato: usa 'Apri nel browser'")
            return
        stop = threading.Event()
        self._stream_stop = stop
        client = self.client
        threading.Thread(target=self._stream_loop, args=(client, stop), name="rete-stream", daemon=True).start()

    def close(self):
        if self._runner is not None:
            self._runner.cancel()
        if self.client is not None:
            self.disconnect()
        self.root.destroy()

    # --- thread di rete: niente widget, solo coda e frame condiviso -------------------------------

    def _stream_loop(self, client: PhoneClient, stop: threading.Event):
        while not stop.is_set():
            try:
                response = client.open_stream()
                self._stream_response = response
                self.events.put(("log", "Stream collegato", None))
                with response:
                    for jpeg in iter_mjpeg(response, stop):
                        self._decode(jpeg)
                if not stop.is_set():
                    self.events.put(("log", "Stream chiuso dal telefono, riprovo", None))
            except Exception as exc:
                if stop.is_set():
                    return
                self.events.put(("log", f"Stream interrotto: {exc}. Riprovo tra {STREAM_RETRY_SECONDS:.0f} s", None))
            finally:
                self._stream_response = None
            stop.wait(STREAM_RETRY_SECONDS)

    def _decode(self, jpeg: bytes):
        image = Image.open(io.BytesIO(jpeg))
        image.load()
        if self.rotation:
            # Lo stream esce con l'orientamento del sensore: Pillow ruota in senso antiorario, quindi il segno è negativo.
            image = image.rotate(-self.rotation, expand=True)
        width, height = self._video_box
        image.thumbnail((width, height))
        with self._frame_lock:
            self._latest_frame = image
        self._frames += 1


def main():
    if tk is None:
        raise SystemExit("Tkinter non è installato in questo Python: su Linux sudo apt install python3-tk")
    root = tk.Tk()
    ControlPanel(root)
    root.mainloop()


if __name__ == "__main__":
    main()
