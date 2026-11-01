"""
Avviamento dell'ambiente: venv, dipendenze, diagnostica, installazione di sistema.

Questo modulo usa SOLO la libreria standard: gira prima che numpy o fastapi esistano.
Non importare qui nient'altro del pacchetto che tiri dentro dipendenze esterne.
"""
import os
import shutil
import socket
import subprocess
import sys

IS_WIN = os.name == "nt"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV = os.path.join(ROOT, ".venv")
VPY = os.path.join(VENV, "Scripts", "python.exe") if IS_WIN else os.path.join(VENV, "bin", "python")

REQ_CORE = ["numpy", "fastapi", "uvicorn[standard]", "websockets", "requests"]
REQ_RADIO = ["pyrtlsdr"]
REQ_STT = ["faster-whisper"]
REQ = REQ_CORE + REQ_RADIO + REQ_STT


def have(b):
    return shutil.which(b) is not None


def sh(cmd):
    return subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True)


def run_live(cmd):
    """Come sh() ma con l'output a schermo: obbligatorio per pip, che e' lento."""
    print("  $ " + (cmd if isinstance(cmd, str) else " ".join(cmd)), flush=True)
    return subprocess.run(cmd, shell=isinstance(cmd, str)).returncode


def win_dll_path():
    """
    Su Windows pyrtlsdr cerca librtlsdr.dll nelle cartelle di sistema e nel PATH, non
    accanto al programma: con questo basta copiare i DLL qui (o in ./dll) e funziona.
    """
    if not (IS_WIN and hasattr(os, "add_dll_directory")):
        return
    for d in (ROOT, os.path.join(ROOT, "dll")):
        if os.path.isdir(d):
            try:
                os.add_dll_directory(d)
            except OSError:
                pass


def dongle_hint(err):
    """Libreria assente e driver assente sono problemi diversi, con rimedi diversi."""
    msg = str(err)
    if "No module named" in msg:
        print("!! manca il pacchetto python pyrtlsdr:")
        print("   %s -m pip install pyrtlsdr" % sys.executable)
    elif "librtlsdr" in msg or "DLL" in msg.upper() or "cannot open shared object" in msg:
        print("!! manca la libreria librtlsdr (il driver del dongle e' un'altra cosa):")
        if IS_WIN:
            print("   scarica i binari Windows da github.com/rtlsdrblog/rtl-sdr-blog/releases")
            print("   e copia librtlsdr.dll e libusb-1.0.dll accanto a guardia.py")
        else:
            print("   sudo apt install rtl-sdr librtlsdr0    (oppure python guardia.py --install)")
    elif IS_WIN:
        print("!! su Windows serve Zadig/WinUSB sul dongle (vedi la docstring o --check)")
    else:
        print("!! controlla che il dongle sia collegato e non in uso da un altro programma")


def port_free(host, port):
    """Prova a occupare la porta prima di avviare uvicorn, per un errore comprensibile."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if not IS_WIN:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)   # come fa uvicorn
        s.bind(("" if host in ("0.0.0.0", "") else host, int(port)))
        return True
    except OSError:
        return False
    finally:
        s.close()


def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def missing(pkgs):
    out = []
    for pkg in pkgs:
        mod = pkg.split("[")[0].replace("-", "_")
        try:
            __import__(mod)
        except Exception:
            out.append(pkg)
    return out


def pip_install(pkgs, etichetta=""):
    if not pkgs:
        return True
    print("\n" + "=" * 62)
    print("  INSTALLAZIONE DIPENDENZE %s— puo' durare qualche minuto." % (etichetta and etichetta + " "))
    print("  Vedrai l'avanzamento: NON e' bloccato, lascia finire.")
    print("  Pacchetti: " + " ".join(pkgs))
    print("=" * 62 + "\n", flush=True)
    run_live([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "wheel"])
    rc = run_live([sys.executable, "-m", "pip", "install", "--prefer-binary"] + pkgs)
    if rc != 0:
        print("\n!! Installazione fallita. Lancia a mano per leggere l'errore reale:\n")
        print('   "%s" -m pip install --prefer-binary %s\n' % (sys.executable, " ".join(pkgs)))
        return False
    print("\n· dipendenze pronte.\n", flush=True)
    return True


def ensure_env(pkgs=None, hard=True, argv=None):
    """Crea la venv al primo avvio, poi installa cio' che manca. Idempotente."""
    if sys.prefix == sys.base_prefix and not os.environ.get("GUARDIA_NO_VENV"):
        if not os.path.exists(VPY):
            print("· creo l'ambiente virtuale...", flush=True)
            run_live([sys.executable, "-m", "venv", VENV])
        if not os.path.exists(VPY):
            print("!! venv non creata. Reinstalla Python spuntando 'pip' e 'Add python.exe to PATH',")
            print("   oppure riavvia con GUARDIA_NO_VENV=1 per usare il Python di sistema.")
            sys.exit(1)
        os.execv(VPY, [VPY] + (argv or sys.argv))

    serve = missing(pkgs or REQ_CORE)
    if serve and not pip_install(serve) and hard:
        sys.exit(1)
    return not serve


# ───────────────────────────── comandi di manutenzione

def do_install():
    print("== INSTALLAZIONE ==")
    if not IS_WIN and have("apt"):
        run_live(["sudo", "apt", "update"])
        run_live(["sudo", "apt", "install", "-y", "rtl-sdr", "sqlite3", "ffmpeg", "curl",
                  "cmake", "build-essential", "libpulse-dev", "pulseaudio", "python3-venv"])
    if have("pactl"):
        if "dsd_out" not in sh("pactl list short sinks").stdout:
            sh("pactl load-module module-null-sink sink_name=dsd_out rate=48000 channels=1")
        print("· sink PulseAudio 'dsd_out' pronto")
    d = os.path.join(ROOT, "dsd-fme")
    if not IS_WIN and not have("dsd-fme") and not os.path.isdir(d):
        run_live(["git", "clone", "https://github.com/lwvmobile/dsd-fme", d])
    if os.path.isdir(d) and not have("dsd-fme"):
        sh(["git", "-C", d, "checkout", "pulseaudio"])
        os.makedirs(os.path.join(d, "build"), exist_ok=True)
        run_live("cd '%s/build' && cmake .. && make -j$(nproc) && sudo make install" % d)
    if IS_WIN:
        print("· Windows: ffmpeg opzionale → winget install Gyan.FFmpeg")
        print("· Per l'SDR reale servono Zadig/WinUSB e librtlsdr.dll (vedi la docstring).")
    ensure_env(REQ, hard=False)
    print("\nfatto. Avvia con: python guardia.py")


def do_check():
    win_dll_path()
    print("== DIAGNOSTICA ==")
    print("  python   " + sys.executable)
    print("  venv     " + ("si" if sys.prefix != sys.base_prefix else "NO"))
    for pkg in REQ:
        mod = pkg.split("[")[0].replace("-", "_")
        try:
            __import__(mod)
            print("  ok       " + pkg)
        except Exception:
            print("  MANCA    " + pkg)
    for b in ["rtl_test", "ffmpeg", "parec", "pactl", "dsd-fme"]:
        print(("  ok       " if have(b) else "  assente  ") + b)
    if have("pactl"):
        print(("  ok       " if "dsd_out" in sh("pactl list short sinks").stdout
               else "  assente  ") + "sink dsd_out")
    try:
        from rtlsdr import RtlSdr
        sdr = RtlSdr()
        try:
            print("  ok       dongle RTL-SDR (tuner %s)" % getattr(sdr, "tuner_type", "?"))
        finally:
            sdr.close()
    except Exception as e:
        print("  MANCA    dongle (" + str(e)[:70] + ")")
        dongle_hint(e)
    from . import config
    print("  dati     " + config.PATHS.root)
    print("  database " + ("presente" if os.path.exists(config.PATHS.db) else "da creare"))


def do_service():
    if IS_WIN:
        print("Windows: usa il Task Scheduler, oppure avvia con: pythonw guardia.py")
        return
    py = VPY if os.path.exists(VPY) else sys.executable
    unit = """[Unit]
Description=Guardia
After=network.target sound.target

[Service]
User=%s
WorkingDirectory=%s
ExecStart=%s %s/guardia.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
""" % (os.environ.get("USER", "pi"), ROOT, py, ROOT)
    with open("/tmp/guardia.service", "w") as f:
        f.write(unit)
    sh(["sudo", "cp", "/tmp/guardia.service", "/etc/systemd/system/guardia.service"])
    sh(["sudo", "systemctl", "daemon-reload"])
    print("fatto: sudo systemctl enable --now guardia")
