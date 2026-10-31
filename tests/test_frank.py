"""Test del cuore di Frank. Ogni test usa una dir temporanea come base."""
import json

import frank_core as core


def _seed(base):
    (base / "frank_state.seed.json").write_text(json.dumps(core.default_state()))


def test_default_state_shape():
    s = core.default_state()
    assert s["name"] == "Frank"
    assert s["current_task"] is None
    assert s["known_bugs"] == []


def test_wake_materializes_state_from_seed(tmp_path):
    _seed(tmp_path)
    msg = core.wake(base=tmp_path)
    assert "Sono Frank" in msg
    assert (tmp_path / "frank_state.json").exists()


def test_wake_without_seed_uses_default(tmp_path):
    msg = core.wake(base=tmp_path)
    assert "Sono Frank" in msg
    assert (tmp_path / "frank_state.json").exists()


def test_remember_appends_history_and_log(tmp_path):
    _seed(tmp_path)
    core.wake(base=tmp_path)
    s = core.remember(base=tmp_path)
    assert s["history"][-1]["note"] == "sessione chiusa"
    assert s["last_run"] is not None
    assert (tmp_path / "frank_history.log").exists()


def test_task_open_then_close(tmp_path):
    _seed(tmp_path)
    core.open_task("scrivere il parser", base=tmp_path)
    assert core.load(base=tmp_path)["current_task"] == "scrivere il parser"
    core.close_task(base=tmp_path)
    assert core.load(base=tmp_path)["current_task"] is None


def test_bug_add_then_resolve(tmp_path):
    _seed(tmp_path)
    core.add_bug("crash su input vuoto", base=tmp_path)
    assert len(core.load(base=tmp_path)["known_bugs"]) == 1
    core.resolve_bug(0, base=tmp_path)
    assert core.load(base=tmp_path)["known_bugs"] == []


def test_resolve_bug_out_of_range_is_noop(tmp_path):
    _seed(tmp_path)
    core.add_bug("bug", base=tmp_path)
    core.resolve_bug(99, base=tmp_path)
    assert len(core.load(base=tmp_path)["known_bugs"]) == 1


def test_load_falls_back_on_corrupt_json(tmp_path):
    (tmp_path / "frank_state.json").write_text("{ json non valido")
    _seed(tmp_path)
    s = core.load(base=tmp_path)
    assert s["name"] == "Frank"


def test_status_lists_bugs(tmp_path):
    _seed(tmp_path)
    core.add_bug("bug X", base=tmp_path)
    out = core.status(base=tmp_path)
    assert "bug X" in out
    assert "Task corrente" in out
