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
    APP_PACKAGE,
    DeployError,
    Deployer,
    DeploySettings,
    ProcessRunner,
    apk_path_script,
    bash_path,
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
    assert build_call == ["bash", "-lc", 'cd "$HOME/gioco" && "$HOME/.venvs/buildozer/bin/buildozer" -v android debug']


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
    assert build_script(settings) == "cd /srv/gioco && /srv/venv/bin/buildozer -v android debug"
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


def test_real_processes_with_fake_buildozer_and_adb(tmp_path):
    project = tmp_path / "gioco"
    project.mkdir()
    (project / "main.py").write_text("")
    (project / "buildozer.spec").write_text("")
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
    settings = DeploySettings(host="linux", project_dir=str(project), buildozer=buildozer, adb=adb)
    logs = []
    deployer = Deployer(settings, ProcessRunner(), logs.append)
    assert deployer.everything() == ("Ab3_x9Qz", 8080)
    assert "# buildozer -v android debug" in logs
    assert (project / "bin" / "gioco-0.3.0-arm64-v8a-debug.apk").exists()
    adb_log = log_file.read_text().splitlines()
    assert adb_log[1] == f"install -r {project}/bin/gioco-0.3.0-arm64-v8a-debug.apk"
    assert adb_log[-1] == "forward tcp:8080 tcp:8080"
