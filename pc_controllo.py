#!/usr/bin/env python3
"""Pannello di controllo dal PC per l'app Gioco sul telefono: stream, comandi e file.

Avvio con doppio clic, oppure: python pc_controllo.py
Pillow serve solo a mostrare lo stream nella finestra (pip install pillow); senza Pillow
il pulsante "Apri nel browser" mostra lo stream nella pagina servita dal telefono.
"""

import io
import json
import os
import queue
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
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
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(PUMP_INTERVAL_MS, self._pump)

    def _build(self):
        root = self.root
        root.title("Gioco - controllo telefono")
        root.minsize(1000, 700)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        connection = ttk.LabelFrame(root, text="Connessione", padding=8)
        connection.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
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
        body.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
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
        log_frame.grid(row=2, column=0, sticky="ew", padx=8, pady=(4, 8))
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
