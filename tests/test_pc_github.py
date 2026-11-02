import io
import json
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest

from pc_controllo import (
    ARTIFACT_PREFIX,
    DeployError,
    Deployer,
    DeploySettings,
    GitHubBuilds,
    GitHubPipeline,
    apk_from_file,
    extract_apk,
    resolve_sources,
)

REPO = "maik/gioco"
BRANCH = "claude/festive-brahmagupta-vdj2r9"
TOKEN = "ghp_finto"


def _fake_apk() -> bytes:
    # Un APK è uno zip: il pannello lo verifica prima di riusare una copia già scaricata.
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as apk:
        apk.writestr("AndroidManifest.xml", b"finto manifest " * 500)
    return buffer.getvalue()


APK_BYTES = _fake_apk()


def apk_zip(name="gioco-0.3.0-arm64-v8a-debug.apk", content=APK_BYTES):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        bundle.writestr(name, content)
    return buffer.getvalue()


class FakeGitHub:
    """API GitHub minima più un secondo server che fa da archivio firmato, come il blob storage reale."""

    def __init__(self):
        self.requests = []
        self.blob_requests = []
        self.runs = []
        self.artifacts = {}
        self.latest_any = None
        self.zip_bytes = apk_zip()
        self.require_token = True
        # Quante richieste all'elenco delle compilazioni falliscono con 502 prima di rispondere.
        self.flaky_runs = 0
        self.garbage_runs = False
        self.sources = {}
        outer = self

        class Api(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _json(self, status, payload):
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                parts = urlsplit(self.path)
                query = parse_qs(parts.query)
                outer.requests.append((parts.path, query, self.headers.get("Authorization")))
                if parts.path == f"/repos/{REPO}/actions/workflows/camera-apk.yml/runs":
                    if outer.flaky_runs > 0:
                        outer.flaky_runs -= 1
                        self._json(502, {"message": "Bad Gateway"})
                    elif outer.garbage_runs:
                        body = b"<html>manutenzione</html>"
                        self.send_response(200)
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                    elif query.get("branch") != [BRANCH]:
                        self._json(200, {"workflow_runs": []})
                    elif query.get("status") == ["success"]:
                        self._json(200, {"workflow_runs": outer.runs})
                    else:
                        self._json(200, {"workflow_runs": [outer.latest_any] if outer.latest_any else []})
                elif parts.path.startswith(f"/repos/{REPO}/actions/runs/") and parts.path.endswith("/artifacts"):
                    run_id = int(parts.path.split("/")[-2])
                    self._json(200, {"artifacts": outer.artifacts.get(run_id, [])})
                elif parts.path.startswith(f"/repos/{REPO}/actions/artifacts/") and parts.path.endswith("/zip"):
                    if outer.require_token and self.headers.get("Authorization") != f"Bearer {TOKEN}":
                        self._json(401, {"message": "Requires authentication"})
                        return
                    self.send_response(302)
                    self.send_header("Location", f"{outer.blob_base}/firmato.zip?sig=abc")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                elif parts.path.startswith(f"/repos/{REPO}/contents/"):
                    name = parts.path.rsplit("/", 1)[-1]
                    if name not in outer.sources or self.headers.get("Accept") != "application/vnd.github.raw":
                        self._json(404, {"message": "Not Found"})
                        return
                    body = outer.sources[name]
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                elif parts.path == "/repos/nessuno/nulla/actions/workflows/camera-apk.yml/runs":
                    self._json(404, {"message": "Not Found"})
                elif parts.path == "/limite/x/actions/workflows/camera-apk.yml/runs":
                    self._json(403, {"message": "API rate limit exceeded"})
                else:
                    self._json(404, {"message": "Not Found"})

        class Blob(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                outer.blob_requests.append(self.headers.get("Authorization"))
                if self.headers.get("Authorization"):
                    # Come Azure Blob: una firma nell'URL più un header Authorization è una richiesta rifiutata.
                    self.send_response(400)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(outer.zip_bytes)))
                self.end_headers()
                self.wfile.write(outer.zip_bytes)

        self.api_server = ThreadingHTTPServer(("127.0.0.1", 0), Api)
        self.blob_server = ThreadingHTTPServer(("127.0.0.1", 0), Blob)
        self.api_base = f"http://127.0.0.1:{self.api_server.server_address[1]}"
        # Porta diversa = host diverso per il redirect: è lì che il token va tolto.
        self.blob_base = f"http://127.0.0.1:{self.blob_server.server_address[1]}"
        for server in (self.api_server, self.blob_server):
            threading.Thread(target=server.serve_forever, daemon=True).start()

    def add_run(self, run_id, artifacts):
        self.runs.append(
            {
                "id": run_id,
                "head_sha": f"{run_id:040d}",
                "created_at": "2026-11-02T02:00:00Z",
                "html_url": f"https://github.com/{REPO}/actions/runs/{run_id}",
            }
        )
        self.artifacts[run_id] = [
            {
                "id": artifact_id,
                "name": name,
                "expired": expired,
                "size_in_bytes": 4321,
                "archive_download_url": f"{self.api_base}/repos/{REPO}/actions/artifacts/{artifact_id}/zip",
            }
            for artifact_id, name, expired in artifacts
        ]

    def close(self):
        for server in (self.api_server, self.blob_server):
            server.shutdown()
            server.server_close()


@pytest.fixture
def github():
    fake = FakeGitHub()
    yield fake
    fake.close()


def builds(fake, token=TOKEN, repo=REPO, sleeps=None):
    sleep = sleeps.append if sleeps is not None else (lambda seconds: None)
    return GitHubBuilds(repo, BRANCH, token, api=fake.api_base, sleep=sleep)


def test_latest_build_picks_newest_run_with_apk(github):
    github.add_run(30, [(300, "altro-artifact", False)])
    github.add_run(20, [(200, f"{ARTIFACT_PREFIX}-surface-abc", True), (201, f"{ARTIFACT_PREFIX}-fbo-abc", False)])
    github.add_run(10, [(100, f"{ARTIFACT_PREFIX}-surface-old", False)])
    build = builds(github).latest_build()
    assert (build["run_id"], build["artifact_id"], build["artifact_name"]) == (20, 201, f"{ARTIFACT_PREFIX}-fbo-abc")
    path, query, auth = github.requests[0]
    assert query["status"] == ["success"] and query["branch"] == [BRANCH]
    assert auth == f"Bearer {TOKEN}"


def test_latest_build_explains_build_in_progress(github):
    github.latest_any = {"status": "in_progress", "created_at": "2026-11-02T02:10:00Z", "html_url": "https://x/run/9"}
    with pytest.raises(DeployError, match="compilazione in corso dal 2026-11-02T02:10:00Z"):
        builds(github).latest_build()


def test_latest_build_explains_failed_build(github):
    github.latest_any = {"status": "completed", "conclusion": "failure", "html_url": "https://x/run/9"}
    with pytest.raises(DeployError, match="finita con 'failure'"):
        builds(github).latest_build()


def test_latest_build_without_any_run(github):
    with pytest.raises(DeployError, match="non è mai partito"):
        builds(github).latest_build()


def test_download_extracts_apk_and_drops_token_on_redirect(github, tmp_path):
    github.add_run(20, [(201, f"{ARTIFACT_PREFIX}-surface-abc", False)])
    client = builds(github)
    logs = []
    path = client.download_apk(client.latest_build(), str(tmp_path), logs.append)
    assert path == str(tmp_path / "201" / "gioco-0.3.0-arm64-v8a-debug.apk")
    assert open(path, "rb").read() == APK_BYTES
    assert github.blob_requests == [None]
    assert not (tmp_path / "201.zip.part").exists()
    assert logs[-1] == f"APK salvato in {path}"


def test_download_reuses_existing_apk(github, tmp_path):
    github.add_run(20, [(201, f"{ARTIFACT_PREFIX}-surface-abc", False)])
    client = builds(github)
    first = client.download_apk(client.latest_build(), str(tmp_path))
    logs = []
    second = client.download_apk(client.latest_build(), str(tmp_path), logs.append)
    assert first == second
    assert github.blob_requests == [None]
    assert logs == [f"APK già scaricato: {second}"]


def test_download_without_token_explains_alternative(github, tmp_path):
    github.add_run(20, [(201, f"{ARTIFACT_PREFIX}-surface-abc", False)])
    client = builds(github, token="")
    with pytest.raises(DeployError, match="Installa APK da file"):
        client.download_apk(client.latest_build(), str(tmp_path))


def test_download_with_bad_token_is_clear(github, tmp_path):
    github.add_run(20, [(201, f"{ARTIFACT_PREFIX}-surface-abc", False)])
    client = builds(github, token="sbagliato")
    with pytest.raises(DeployError, match="token GitHub non valido"):
        client.download_apk(client.latest_build(), str(tmp_path))


def test_download_rejects_zip_without_apk(github, tmp_path):
    github.zip_bytes = apk_zip(name="leggimi.txt")
    github.add_run(20, [(201, f"{ARTIFACT_PREFIX}-surface-abc", False)])
    client = builds(github)
    with pytest.raises(DeployError, match="non contiene un APK"):
        client.download_apk(client.latest_build(), str(tmp_path))


def test_download_ignores_paths_inside_zip(github, tmp_path):
    github.zip_bytes = apk_zip(name="../../fuori/gioco.apk")
    github.add_run(20, [(201, f"{ARTIFACT_PREFIX}-surface-abc", False)])
    client = builds(github)
    path = client.download_apk(client.latest_build(), str(tmp_path / "apk"))
    assert path == str(tmp_path / "apk" / "201" / "gioco.apk")
    assert not (tmp_path / "fuori").exists()


def test_download_can_be_stopped(github, tmp_path):
    github.add_run(20, [(201, f"{ARTIFACT_PREFIX}-surface-abc", False)])
    client = builds(github)
    with pytest.raises(DeployError, match="interrotto"):
        client.download_apk(client.latest_build(), str(tmp_path), should_stop=lambda: True)


def test_unknown_repo_is_404_message(github):
    with pytest.raises(DeployError, match="non trovato su GitHub"):
        builds(github, repo="nessuno/nulla").latest_build()


@pytest.mark.parametrize("repo", ["gioco", "a/b/c", "/gioco", "maik/"])
def test_repo_format_is_checked(repo):
    with pytest.raises(DeployError, match="proprietario/nome"):
        GitHubBuilds(repo, BRANCH, TOKEN)


def test_page_url_filters_branch():
    url = GitHubBuilds(REPO, BRANCH, "").page_url()
    assert url == f"https://github.com/{REPO}/actions/workflows/camera-apk.yml?query=branch%3A{BRANCH}"


class FakeRun:
    def __init__(self):
        self.calls = []

    def __call__(self, args, on_line=None):
        self.calls.append(args)
        joined = " ".join(args)
        if "devices" in joined:
            return 0, ["List of devices attached", "R58M123ABC\tdevice"]
        if "install -r" in joined:
            return 0, ["Success"]
        if "am start" in joined:
            return 0, ["Status: ok"]
        if "logcat -d" in joined:
            return 0, ["I python  : [INFO   ] [Stream      ] token=Ab3_x9Qz porta=8080"]
        return 0, []


def test_pipeline_everything_downloads_installs_and_launches_without_wsl(github, tmp_path):
    github.add_run(20, [(201, f"{ARTIFACT_PREFIX}-surface-abc", False)])
    run = FakeRun()
    logs = []
    deployer = Deployer(DeploySettings(host="windows", adb="adb.exe"), run, logs.append)
    pipeline = GitHubPipeline(deployer, builds(github), str(tmp_path), logs.append)
    assert pipeline.everything() == ("Ab3_x9Qz", 8080)
    assert all(call[0] == "adb.exe" for call in run.calls), "in modalità GitHub non si usa wsl.exe"
    install = next(call for call in run.calls if call[1:3] == ["install", "-r"])
    assert install[3] == str(tmp_path / "201" / "gioco-0.3.0-arm64-v8a-debug.apk")
    assert "Pronto: APK disponibile su GitHub, un telefono collegato." in logs


def test_pipeline_check_reports_missing_token_and_phone(github, tmp_path):
    github.add_run(20, [(201, f"{ARTIFACT_PREFIX}-surface-abc", False)])

    def no_phone(args, on_line=None):
        return 0, ["List of devices attached", ""]

    deployer = Deployer(DeploySettings(host="windows", adb="adb.exe"), no_phone, lambda line: None)
    pipeline = GitHubPipeline(deployer, builds(github, token=""), str(tmp_path), lambda line: None)
    problems = pipeline.check()
    assert any("token GitHub" in problem for problem in problems)
    assert any("nessun telefono" in problem for problem in problems)


def test_apk_from_file_passes_apk_through(tmp_path):
    apk = tmp_path / "gioco.apk"
    apk.write_bytes(APK_BYTES)
    assert apk_from_file(str(apk), str(tmp_path / "estratti")) == str(apk)


def test_apk_from_file_opens_github_zip(tmp_path):
    archive = tmp_path / "gioco-apk-surface-abc.zip"
    archive.write_bytes(apk_zip())
    path = apk_from_file(str(archive), str(tmp_path / "estratti"))
    assert path == str(tmp_path / "estratti" / "gioco-0.3.0-arm64-v8a-debug.apk")
    assert open(path, "rb").read() == APK_BYTES


def test_extract_apk_rejects_non_zip(tmp_path):
    bogus = tmp_path / "rotto.zip"
    bogus.write_bytes(b"non sono uno zip")
    with pytest.raises(DeployError, match="non è uno zip valido"):
        extract_apk(str(bogus), str(tmp_path / "x"))


def test_download_replaces_corrupt_cached_apk_and_reports_progress(github, tmp_path):
    github.add_run(20, [(201, f"{ARTIFACT_PREFIX}-surface-abc", False)])
    cache = tmp_path / "201"
    cache.mkdir()
    (cache / "gioco-0.3.0-arm64-v8a-debug.apk").write_bytes(b"troncato")
    client = builds(github)
    seen = []
    path = client.download_apk(client.latest_build(), str(tmp_path), progress=lambda d, t: seen.append((d, t)))
    assert open(path, "rb").read() == APK_BYTES
    assert seen and seen[-1][0] == seen[-1][1] == len(github.zip_bytes)
    assert github.blob_requests == [None]


def test_failed_download_leaves_no_archive(github, tmp_path):
    github.add_run(20, [(201, f"{ARTIFACT_PREFIX}-surface-abc", False)])
    github.zip_bytes = b"non zip"
    client = builds(github)
    with pytest.raises(DeployError):
        client.download_apk(client.latest_build(), str(tmp_path))
    assert not (tmp_path / "201.zip.part").exists()
    assert [p.name for p in (tmp_path / "201").iterdir()] == []


def test_temporary_github_errors_are_retried(github):
    github.add_run(40, [(400, f"{ARTIFACT_PREFIX}-surface-abc", False)])
    github.flaky_runs = 2
    sleeps = []
    assert builds(github, sleeps=sleeps).latest_build()["run_id"] == 40
    assert sleeps == [1.0, 2.0]


def test_github_gives_up_after_retries(github):
    github.flaky_runs = 10
    sleeps = []
    with pytest.raises(DeployError, match="GitHub ha risposto 502") as error:
        builds(github, sleeps=sleeps).latest_build()
    assert error.value.retryable
    assert len(sleeps) == 2


def test_client_errors_are_not_retried(github):
    sleeps = []
    with pytest.raises(DeployError, match="non trovato su GitHub"):
        builds(github, repo="nessuno/nulla", sleeps=sleeps).latest_build()
    assert sleeps == []


def test_unreachable_github_is_retryable(tmp_path):
    sleeps = []
    unreachable = GitHubBuilds(REPO, BRANCH, TOKEN, api="http://127.0.0.1:9", sleep=sleeps.append)
    with pytest.raises(DeployError, match="GitHub non raggiungibile"):
        unreachable.latest_build()
    assert len(sleeps) == 2


def test_non_json_github_answer_is_clear(github):
    github.garbage_runs = True
    with pytest.raises(DeployError, match="non è JSON"):
        builds(github).latest_build()


def test_malformed_runs_and_artifacts_are_skipped(github):
    github.add_run(50, [(500, f"{ARTIFACT_PREFIX}-surface-abc", False)])
    github.runs.insert(0, {"senza": "id"})
    github.artifacts[50].insert(0, {"name": f"{ARTIFACT_PREFIX}-rotto"})
    assert builds(github).latest_build()["artifact_id"] == 500


def test_download_sources_from_branch(github, tmp_path):
    github.sources = {"main.py": b"print('telefono')\n", "buildozer.spec": b"[app]\n"}
    target = builds(github).download_sources(str(tmp_path / "sorgenti"))
    assert (tmp_path / "sorgenti" / "main.py").read_bytes() == b"print('telefono')\n"
    assert (tmp_path / "sorgenti" / "buildozer.spec").read_bytes() == b"[app]\n"
    assert target == str(tmp_path / "sorgenti")
    paths = [(path, query.get("ref")) for path, query, _ in github.requests if "/contents/" in path]
    assert paths == [(f"/repos/{REPO}/contents/main.py", [BRANCH]), (f"/repos/{REPO}/contents/buildozer.spec", [BRANCH])]


def test_download_sources_missing_file_suggests_local_folder(github, tmp_path):
    github.sources = {"main.py": b"x"}
    with pytest.raises(DeployError, match="buildozer.spec non scaricato da GitHub.*cartella Sorgenti"):
        builds(github).download_sources(str(tmp_path / "sorgenti"))


def test_resolve_sources_prefers_local_folder(tmp_path):
    local = tmp_path / "locale"
    local.mkdir()
    for name in ("main.py", "buildozer.spec"):
        (local / name).write_text("x")
    logs = []

    def no_github():
        raise AssertionError("GitHub non serve")

    assert resolve_sources(str(local), no_github, str(tmp_path / "apk"), logs.append) == str(local)


def test_resolve_sources_falls_back_to_github(github, tmp_path):
    github.sources = {"main.py": b"x", "buildozer.spec": b"y"}
    logs = []
    folder = resolve_sources(str(tmp_path / "vuota"), lambda: builds(github), str(tmp_path / "apk"), logs.append)
    assert folder == str(tmp_path / "apk" / "sorgenti")
    assert any("li scarico da GitHub" in line for line in logs)
