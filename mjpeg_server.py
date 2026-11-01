import ipaddress
import json
import logging
import socket
import threading
import time
from contextlib import contextmanager
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger("mjpeg")

BOUNDARY = b"gioco-frame"
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
                except Exception:
                    # L'encoder Android solleva JavaException, che qui non è importabile.
                    log.exception("codifica JPEG fallita")
                    continue
                self._broker.publish(jpeg)
                self.encoded += 1
        finally:
            if self._on_thread_exit is not None:
                self._on_thread_exit()


class _Handler(BaseHTTPRequestHandler):
    server_version = "GiocoMJPEG/1.0"
    # Un client che smette di leggere bloccherebbe il thread per sempre sulla write.
    timeout = CLIENT_SOCKET_TIMEOUT

    def do_GET(self):
        path = self.path.split("?", 1)[0]
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
    def __init__(self, broker: FrameBroker, info_provider, ports=DEFAULT_PORTS, host: str = "0.0.0.0"):
        self._broker = broker
        self._info_provider = info_provider
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


def stream_url(ip: str, port: int) -> str:
    return f"http://{ip}:{port}/"


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
  <a class="button" href="/snapshot.jpg" target="_blank" rel="noopener">Istantanea</a>
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
    img.src = "/stream.mjpg?t=" + Date.now();
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
      const response = await fetch("/info.json", { cache: "no-store" });
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
