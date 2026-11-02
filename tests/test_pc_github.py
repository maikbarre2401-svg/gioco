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
)

REPO = "maik/gioco"
BRANCH = "claude/festive-brahmagupta-vdj2r9"
TOKEN = "ghp_finto"
APK_BYTES = b"PK\x03\x04 finto apk " * 1000


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
                    if query.get("branch") != [BRANCH]:
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


def builds(fake, token=TOKEN, repo=REPO):
    return GitHubBuilds(repo, BRANCH, token, api=fake.api_base)


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
