import os
import stat
import subprocess
import sys
import textwrap
import threading
import time

import pytest

from pc_controllo import (
    APP_ACTIVITY,
    DEFAULT_BUILDOZER,
    APP_PACKAGE,
    DeployError,
    Deployer,
    DeploySettings,
    ProcessRunner,
    apk_path_script,
    bash_path,
    toolchain_script,
    build_script,
    check_script,
    default_adb,
    linux_command,
    needs_windows_path,
    parse_devices,
    parse_server_line,
)

KIVY_LINE = "11-02 10:00:01.123  4321  4350 I python  : [INFO   ] [Stream      ] token=Ab3_x9Qz porta=8080"


class FakeRun:
    """Risponde ai comandi in base a parole chiave e registra tutto."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, args, on_line=None):
        self.calls.append(args)
        joined = " ".join(args)
        for key, value in self.responses:
            if key in joined:
                code, lines = value() if callable(value) else value
                if on_line is not None:
                    for line in lines:
                        on_line(line)
                return code, list(lines)
        return 0, []


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def ok_responses(token_after_polls=0):
    polls = {"count": 0}

    def logcat_dump():
        polls["count"] += 1
        if polls["count"] > token_after_polls:
            return 0, ["--------- beginning of main", KIVY_LINE]
        return 0, ["--------- beginning of main"]

    return [
        ("echo FINE", (0, ["FINE"])),
        ("android debug", (0, ["# Check configuration tokens", "# APK gioco-0.3.0-arm64-v8a-debug.apk available"])),
        ("bin/*.apk", (0, ["/home/u/gioco/bin/gioco-0.3.0-arm64-v8a-debug.apk"])),
        ("devices", (0, ["List of devices attached", "R58M123ABC\tdevice", ""])),
        ("install -r", (0, ["Performing Streamed Install", "Success"])),
        ("logcat -d", logcat_dump),
        ("am start", (0, ["Starting: Intent { cmp=org.maikbarre.gioco/org.kivy.android.PythonActivity }", "Status: ok"])),
        ("echo WSL_OK", (0, ["WSL_OK"])),
    ]


def make(settings=None, responses=None, clock=None):
    logs = []
    run = FakeRun(responses if responses is not None else ok_responses())
    clock = clock or FakeClock()
    deployer = Deployer(settings or DeploySettings(host="linux", adb="adb"), run, logs.append, clock.sleep, clock)
    return deployer, run, logs, clock


def adb_calls(run):
    return [call[1:] for call in run.calls if call[0] == "adb"]


def test_everything_runs_steps_in_order_and_returns_token():
    deployer, run, logs, clock = make(responses=ok_responses(token_after_polls=2))
    assert deployer.everything() == ("Ab3_x9Qz", 8080)
    assert adb_calls(run) == [
        ["devices"],
        ["install", "-r", "/home/u/gioco/bin/gioco-0.3.0-arm64-v8a-debug.apk"],
        ["shell", "pm", "grant", APP_PACKAGE, "android.permission.CAMERA"],
        ["shell", "pm", "grant", APP_PACKAGE, "android.permission.RECORD_AUDIO"],
        ["logcat", "-c"],
        ["shell", "am", "force-stop", APP_PACKAGE],
        ["shell", "am", "start", "-W", "-n", f"{APP_PACKAGE}/{APP_ACTIVITY}"],
        ["logcat", "-d", "-s", "python:I"],
        ["logcat", "-d", "-s", "python:I"],
        ["logcat", "-d", "-s", "python:I"],
        ["forward", "tcp:8080", "tcp:8080"],
    ]
    assert clock.sleeps == [1.0, 1.0]
    assert "# APK gioco-0.3.0-arm64-v8a-debug.apk available" in logs
    build_call = next(call for call in run.calls if "android debug" in " ".join(call))
    assert build_call == ["bash", "-lc", build_script(DeploySettings(host="linux"))]
    assert 'b="$HOME/.venvs/buildozer/bin/buildozer"' in build_call[-1]


def test_everything_stops_before_build_when_check_fails():
    responses = ok_responses()
    responses[0] = ("echo FINE", (0, ["MANCA buildozer.spec", "FINE"]))
    deployer, run, logs, _ = make(responses=responses)
    with pytest.raises(DeployError, match="buildozer.spec"):
        deployer.everything()
    assert not any("android debug" in " ".join(call) for call in run.calls)


def test_check_reports_missing_phone_and_unauthorized():
    responses = ok_responses()
    responses[3] = ("devices", (0, ["List of devices attached", "R58M123ABC\tunauthorized", ""]))
    deployer, _, logs, _ = make(responses=responses)
    problems = deployer.check()
    assert any("unauthorized" in problem for problem in problems)
    assert any("nessun telefono" in problem for problem in problems)
    assert any(line.startswith("PROBLEMA:") for line in logs)


def test_check_reports_missing_project_folder():
    responses = ok_responses()
    responses[0] = ("echo FINE", (0, ["MANCA cartella del progetto"]))
    deployer, _, _, _ = make(responses=responses)
    assert deployer.check() == ["in WSL manca: cartella del progetto (~/gioco, ~/.venvs/buildozer/bin/buildozer)"]


def test_check_reports_adb_missing():
    responses = ok_responses()
    responses[3] = ("devices", lambda: (_ for _ in ()).throw(DeployError("comando non trovato: adb")))
    deployer, _, _, _ = make(responses=responses)
    assert deployer.check() == ["adb non utilizzabile: comando non trovato: adb"]


def test_build_failure_shows_tail_of_output():
    responses = ok_responses()
    responses[1] = ("android debug", (1, [f"riga {i}" for i in range(40)] + ["BUILD FAILURE: ndk mancante"]))
    deployer, _, _, _ = make(responses=responses)
    with pytest.raises(DeployError) as info:
        deployer.build()
    assert "buildozer fallito (uscita 1)" in str(info.value)
    assert "BUILD FAILURE: ndk mancante" in str(info.value)
    assert "riga 0\n" not in str(info.value)


def test_install_requires_success_line():
    responses = ok_responses()
    responses[4] = ("install -r", (0, ["adb: failed to install x.apk: INSTALL_FAILED_OLDER_SDK"]))
    deployer, _, _, _ = make(responses=responses)
    with pytest.raises(DeployError, match="INSTALL_FAILED_OLDER_SDK"):
        deployer.install()


def test_install_without_apk_is_clear_error():
    responses = ok_responses()
    responses[2] = ("bin/*.apk", (1, []))
    deployer, _, _, _ = make(responses=responses)
    with pytest.raises(DeployError, match="ricerca dell'APK fallito"):
        deployer.install()


def test_launch_times_out_without_token():
    responses = ok_responses(token_after_polls=10_000)
    deployer, run, _, clock = make(responses=responses)
    with pytest.raises(DeployError, match="token non trovato"):
        deployer.launch()
    assert clock.now >= 30
    assert not any(call[1:2] == ["forward"] for call in run.calls)


def test_launch_rejects_activity_error():
    responses = ok_responses()
    responses[6] = ("am start", (0, ["Error type 3", "Error: Activity class does not exist."]))
    deployer, _, _, _ = make(responses=responses)
    with pytest.raises(DeployError, match="avvio rifiutato"):
        deployer.launch()


def test_windows_host_runs_through_wsl_and_asks_windows_path():
    settings = DeploySettings(host="windows", wsl_distro="Ubuntu-24.04", adb="adb")
    deployer, run, _, _ = make(settings=settings)
    deployer.install()
    apk_call = next(call for call in run.calls if "bin/*.apk" in " ".join(call))
    assert apk_call[:5] == ["wsl.exe", "-d", "Ubuntu-24.04", "--", "bash"]
    assert 'wslpath -w "$PWD/$f"' in apk_call[-1]


@pytest.mark.parametrize(
    ("host", "adb", "windows"),
    [("windows", "adb", True), ("wsl", "adb.exe", True), ("wsl", "adb", False), ("linux", "adb", False)],
)
def test_needs_windows_path(host, adb, windows):
    assert needs_windows_path(DeploySettings(host=host, adb=adb)) is windows


def test_default_adb_per_host():
    assert default_adb("wsl") == "adb.exe"
    assert default_adb("windows") == "adb"
    assert default_adb("linux") == "adb"


def test_linux_command_without_distro():
    assert linux_command(DeploySettings(host="windows"), "true") == ["wsl.exe", "--", "bash", "-lc", "true"]
    assert linux_command(DeploySettings(host="wsl"), "true") == ["bash", "-lc", "true"]


@pytest.mark.parametrize(
    "text",
    [
        KIVY_LINE,
        "I/python  ( 4321): [INFO   ] [Stream      ] token=Ab3_x9Qz porta=8080",
        "[INFO   ] [Stream      ] token=vecchio1 porta=8081\n" + KIVY_LINE,
    ],
)
def test_parse_server_line_takes_last_match(text):
    assert parse_server_line(text) == ("Ab3_x9Qz", 8080)


def test_parse_server_line_ignores_debug_url_and_missing():
    assert parse_server_line("GIOCO client OK 0 collegati, http://10.0.0.2:8080/?t=Ab3_x9Qz") is None
    assert parse_server_line("") is None


def test_parse_devices():
    ready, problems = parse_devices(
        [
            "* daemon started successfully",
            "List of devices attached",
            "R58M123ABC\tdevice",
            "emulator-5554\toffline",
            "ZY22\tunauthorized",
            "",
        ]
    )
    assert ready == ["R58M123ABC"]
    assert problems == ["emulator-5554 offline", "ZY22 unauthorized"]


def test_bash_path_survives_real_bash(tmp_path):
    weird = 'cartella con spazi $HOME "virgolette" `x`'
    (tmp_path / weird).mkdir()
    script = f"cd {bash_path('~/' + weird)} && pwd"
    output = subprocess.run(
        ["bash", "-c", script], env={**os.environ, "HOME": str(tmp_path)}, capture_output=True, text=True, check=True
    )
    assert output.stdout.strip() == str(tmp_path / weird)


def test_bash_path_quotes_absolute_paths():
    assert bash_path("/opt/my tools/buildozer") == "'/opt/my tools/buildozer'"
    assert bash_path("~") == '"$HOME"'


def test_scripts_mention_project_and_buildozer():
    settings = DeploySettings(host="linux", project_dir="/srv/gioco", buildozer="/srv/venv/bin/buildozer")
    assert build_script(settings).startswith("cd /srv/gioco && b=/srv/venv/bin/buildozer && ")
    assert build_script(settings).endswith('yes | "$b" -v android debug; exit "${PIPESTATUS[1]}"')
    assert "cd /srv/gioco" in check_script(settings)
    assert apk_path_script(settings).endswith('printf "%s\\n" "$PWD/$f"')


def test_process_runner_streams_lines_and_exit_code():
    lines = []
    code, tail = ProcessRunner()(
        [sys.executable, "-c", "import sys; print('uno'); print('due'); sys.exit(3)"], lines.append
    )
    assert code == 3
    assert lines == ["uno", "due"]
    assert tail == ["uno", "due"]


def test_process_runner_missing_command():
    with pytest.raises(DeployError, match="comando non trovato"):
        ProcessRunner()(["comando-che-non-esiste-gioco"])


def test_process_runner_cancel_terminates():
    runner = ProcessRunner()
    threading.Timer(0.3, runner.cancel).start()
    started = time.monotonic()
    with pytest.raises(DeployError, match="interrotto"):
        runner([sys.executable, "-c", "import time; print('via', flush=True); time.sleep(30)"])
    assert time.monotonic() - started < 10


def write_script(path, body):
    path.write_text("#!/bin/bash\n" + textwrap.dedent(body))
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def test_real_processes_with_fake_buildozer_and_adb(tmp_path, monkeypatch):
    # Un pacchetto sicuramente installato: il test non deve chiamare apt-get.
    monkeypatch.setattr("pc_controllo.SYSTEM_PACKAGES", ("bash",))
    project = tmp_path / "gioco con spazi"
    sources = tmp_path / "sorgenti"
    sources.mkdir()
    (sources / "main.py").write_text('x = 1\nPREVIEW_MODE = check_preview_mode("fbo")\n')
    (sources / "buildozer.spec").write_text("[app]\n")
    out = tmp_path / "apk sul pc"
    buildozer = write_script(
        tmp_path / "buildozer",
        """
        echo "# buildozer $*"
        mkdir -p bin
        echo apk > bin/gioco-0.3.0-arm64-v8a-debug.apk
        echo "# APK pronto"
        """,
    )
    log_file = tmp_path / "adb.log"
    adb = write_script(
        tmp_path / "adb",
        f"""
        echo "$*" >> {log_file}
        case "$1" in
          devices) printf 'List of devices attached\\nR58M123ABC\\tdevice\\n\\n' ;;
          install) echo Success ;;
          logcat) [ "$2" = "-d" ] && echo '{KIVY_LINE}' ;;
          shell) [ "$2" = "am" ] && [ "$3" = "start" ] && echo 'Status: ok' ;;
        esac
        exit 0
        """,
    )
    settings = DeploySettings(
        host="linux", project_dir=str(project), buildozer=buildozer, adb=adb, source_dir=str(sources), apk_dir=str(out)
    )
    logs = []
    deployer = Deployer(settings, ProcessRunner(), logs.append)
    assert deployer.everything() == ("Ab3_x9Qz", 8080)
    assert "# buildozer -v android debug" in logs
    assert (project / "main.py").read_text() == 'x = 1\nPREVIEW_MODE = check_preview_mode("surface")\n'
    assert (project / "buildozer.spec").read_text() == "[app]\n"
    assert (sources / "main.py").read_text().endswith('check_preview_mode("fbo")\n')
    exported = out / "gioco-0.3.0-arm64-v8a-debug.apk"
    assert exported.read_text() == "apk\n"
    adb_log = log_file.read_text().splitlines()
    assert adb_log[1] == f"install -r {exported}"
    assert adb_log[-1] == "forward tcp:8080 tcp:8080"


def test_launch_tolerates_logcat_hiccups():
    responses = ok_responses()
    attempts = {"count": 0}

    def flaky_logcat():
        attempts["count"] += 1
        if attempts["count"] <= 3:
            return 1, ["error: device offline"]
        return 0, [KIVY_LINE]

    responses[5] = ("logcat -d", flaky_logcat)
    deployer, run, logs, _ = make(responses=responses)
    assert deployer.launch() == ("Ab3_x9Qz", 8080)
    assert sum("lettura del log non riuscita" in line for line in logs) == 1
    assert any(call[1:2] == ["forward"] for call in run.calls)


def test_launch_gives_up_when_logcat_never_answers():
    responses = ok_responses()
    responses[5] = ("logcat -d", (1, ["error: no devices/emulators found"]))
    deployer, _, _, clock = make(responses=responses)
    with pytest.raises(DeployError, match="token non trovato"):
        deployer.launch()
    assert clock.now >= 30


def test_process_runner_kills_process_that_ignores_terminate(monkeypatch):
    monkeypatch.setattr("pc_controllo.PROCESS_KILL_SECONDS", 0.5)
    runner = ProcessRunner()

    def on_line(line):
        if line == "via":
            threading.Timer(0.1, runner.cancel).start()

    script = (
        "import signal, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "print('via', flush=True)\n"
        "time.sleep(30)\n"
    )
    started = time.monotonic()
    with pytest.raises(DeployError, match="interrotto"):
        runner([sys.executable, "-c", script], on_line)
    assert time.monotonic() - started < 10


def test_process_runner_cancel_before_start():
    runner = ProcessRunner()
    runner.cancel()
    with pytest.raises(DeployError, match="interrotto"):
        runner([sys.executable, "-c", "print('mai')"])


def test_main_refuses_old_python(monkeypatch):
    import pc_controllo

    monkeypatch.setattr(pc_controllo.sys, "version_info", (3, 9, 18))
    with pytest.raises(SystemExit, match="Serve Python 3.10"):
        pc_controllo.main()


def test_check_explains_missing_wsl_on_windows():
    responses = ok_responses()
    responses[-1] = ("echo WSL_OK", (1, ["Windows Subsystem for Linux has no installed distributions."]))
    deployer, _, _, _ = make(settings=DeploySettings(host="windows", adb="adb"), responses=responses)
    problems = deployer.check()
    assert "wsl --install -d Ubuntu-24.04" in problems[0]
    assert "no installed distributions" in problems[0]


def test_missing_wsl_command_is_explained():
    def run(args, on_line=None):
        raise DeployError(f"comando non trovato: {args[0]}")

    deployer = Deployer(DeploySettings(host="windows"), run, lambda text: None)
    with pytest.raises(DeployError, match="wsl --install"):
        deployer.ensure_linux()


def test_build_prepares_wsl_syncs_sources_and_exports_apk():
    responses = ok_responses()
    responses.insert(0, ("MANCA_PACCHETTO", (0, ["MANCA_PACCHETTO openjdk-17-jdk-headless", "MANCA_PACCHETTO cmake",
                                                 "PACCHETTI_CONTROLLATI"])))
    responses.insert(0, ("cp \"$f\" \"$out/\"", (0, ["gioco-0.3.0-arm64-v8a-debug.apk"])))
    settings = DeploySettings(host="windows", adb="adb", source_dir=r"C:\Users\Maik\gioco", apk_dir=r"C:\Users\Maik\apk")
    deployer, run, logs, _ = make(settings=settings, responses=responses)
    path = deployer.build()
    assert path.endswith("gioco-0.3.0-arm64-v8a-debug.apk") and path.startswith(r"C:\Users\Maik\apk")
    scripts = [call[-1] for call in run.calls]
    root_call = next(call for call in run.calls if "apt-get install" in call[-1])
    assert root_call[:4] == ["wsl.exe", "-u", "root", "--"]
    assert "openjdk-17-jdk-headless cmake" in root_call[-1]
    order = [
        next(i for i, script in enumerate(scripts) if marker in script)
        for marker in ("echo WSL_OK", "MANCA_PACCHETTO", "apt-get install", "BUILDOZER_PRONTO", "wslpath -u", "android debug", 'cp "$f"')
    ]
    assert order == sorted(order)
    sync = next(script for script in scripts if "check_preview_mode" in script)
    assert "wslpath -u 'C:\\Users\\Maik\\gioco'" in sync


def test_build_without_apt_is_clear():
    responses = ok_responses()
    responses.insert(0, ("MANCA_PACCHETTO", (0, ["SENZA_APT"])))
    deployer, _, _, _ = make(responses=responses)
    with pytest.raises(DeployError, match="non ha apt-get"):
        deployer.build()


def test_package_install_without_sudo_explains_command(monkeypatch):
    monkeypatch.setattr("pc_controllo.os.geteuid", lambda: 1000, raising=False)
    responses = ok_responses()
    responses.insert(0, ("apt-get install", (1, ["sudo: a password is required"])))
    responses.insert(0, ("MANCA_PACCHETTO", (0, ["MANCA_PACCHETTO cmake"])))
    deployer, run, _, _ = make(responses=responses)
    with pytest.raises(DeployError, match="sudo apt-get install -y cmake"):
        deployer.build()
    assert next(call for call in run.calls if "apt-get install" in call[-1])[:2] == ["sudo", "-n"]


def test_toolchain_script_never_deletes_and_pins_versions():
    script = toolchain_script(DeploySettings(host="linux"))
    assert "rm " not in script and "--clear" not in script
    assert "buildozer==1.6.0" in script and "cython==0.29.37" in script and "--python 3.11" in script
    custom = toolchain_script(DeploySettings(host="linux", buildozer="/opt/buildozer"))
    assert custom.startswith("test -x /opt/buildozer ||")
    assert DEFAULT_BUILDOZER in custom


def test_real_toolchain_script_refuses_foreign_folder(tmp_path):
    foreign = tmp_path / "non-venv"
    foreign.mkdir()
    (foreign / "dati.txt").write_text("importante")
    script = toolchain_script(DeploySettings(host="linux", buildozer=str(foreign / "bin" / "buildozer")))
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert result.returncode == 3
    assert "non lo tocco" in result.stderr
    assert (foreign / "dati.txt").read_text() == "importante"


def test_wsl_host_converts_apk_path_for_adb_exe():
    responses = ok_responses()
    responses.insert(0, ("wslpath -w", (0, [r"C:\Users\Maik\apk\gioco.apk"])))
    settings = DeploySettings(host="wsl", adb="adb.exe")
    deployer, run, _, _ = make(settings=settings, responses=responses)
    deployer.install_apk("/home/maik/apk/gioco.apk")
    install = next(call for call in run.calls if call[:2] == ["adb.exe", "install"])
    assert install[-1] == r"C:\Users\Maik\apk\gioco.apk"


@pytest.mark.parametrize(("code", "expected"), [(0, 0), (7, 7)])
def test_build_script_keeps_buildozer_exit_code(tmp_path, code, expected):
    project = tmp_path / "progetto"
    project.mkdir()
    buildozer = write_script(
        tmp_path / "venv" / "bin" / "buildozer" if (tmp_path / "venv" / "bin").mkdir(parents=True) is None else None,
        f"""
        read -r risposta
        echo "risposta=$risposta"
        exit {code}
        """,
    )
    script = build_script(DeploySettings(host="linux", project_dir=str(project), buildozer=buildozer))
    result = subprocess.run(["bash", "-lc", script], capture_output=True, text=True)
    assert result.returncode == expected
    assert "risposta=y" in result.stdout


def test_windows_defaults_to_github_build():
    from pc_controllo import default_mode

    assert default_mode("windows") == "github"
    assert default_mode("wsl") == "wsl"
    assert default_mode("linux") == "wsl"
