import pytest

import debug


@pytest.fixture
def captured(monkeypatch):
    lines = []
    monkeypatch.setattr(debug, "DEBUG", True)
    monkeypatch.setattr(debug, "_write", lambda priority, message: lines.append((priority, message)))
    monkeypatch.setattr(debug, "_last_state", {})
    return lines


def test_stages_are_unique_and_cover_the_pipeline():
    assert len(set(debug.STAGES)) == len(debug.STAGES) == 10


def test_format_line_ok_and_fail():
    assert debug.format_line("shader", True, "compilato", 1.5) == "t=   1.500s shader           OK compilato"
    assert debug.format_line("texture", False, "", 12.25) == "t=  12.250s texture          FAIL"


def test_ok_uses_info_and_fail_uses_error_priority(captured):
    debug.ok(debug.STAGE_CAMERA_OPEN, "id=0")
    debug.fail(debug.STAGE_SHADER, "log=errore")
    assert captured[0][0] == debug.ANDROID_LOG_INFO
    assert captured[0][1].endswith("fotocamera       OK id=0")
    assert captured[1][0] == debug.ANDROID_LOG_ERROR
    assert captured[1][1].endswith("shader           FAIL log=errore")


def test_nothing_is_written_when_disabled(captured, monkeypatch):
    monkeypatch.setattr(debug, "DEBUG", False)
    debug.ok(debug.STAGE_CAMERA_OPEN, "id=0")
    debug.state(debug.STAGE_CLIENTS, True, "0 collegati")
    with debug.stage(debug.STAGE_TEXTURE):
        pass
    assert captured == []


def test_stage_reports_ok_with_detail(captured):
    with debug.stage(debug.STAGE_ROTATION) as probe:
        probe.detail = "sensore=90°"
    assert captured[-1][1].endswith("rotazione        OK sensore=90°")


def test_stage_reports_fail_and_reraises(captured):
    with pytest.raises(ValueError):
        with debug.stage(debug.STAGE_PREVIEW_SIZE):
            raise ValueError("nessuna dimensione supportata dalla fotocamera")
    assert captured[-1][0] == debug.ANDROID_LOG_ERROR
    assert captured[-1][1].endswith("FAIL ValueError: nessuna dimensione supportata dalla fotocamera")


def test_state_writes_only_on_change(captured):
    debug.state(debug.STAGE_CLIENTS, True, "0 collegati")
    debug.state(debug.STAGE_CLIENTS, True, "0 collegati")
    debug.state(debug.STAGE_CLIENTS, True, "1 collegati")
    debug.state(debug.STAGE_CLIENTS, False, "1 collegati")
    debug.forget(debug.STAGE_CLIENTS)
    debug.state(debug.STAGE_CLIENTS, False, "1 collegati")
    assert len(captured) == 4


def test_encode_message_strips_nul_and_truncates():
    assert debug.encode_message("a\x00b") == b"a\\0b"
    long = debug.encode_message("è" * 5000)
    assert len(long) <= debug.MAX_MESSAGE_BYTES
    assert long.endswith(b"...")
    long.decode("utf-8")


def test_writer_failure_falls_back_to_stderr(captured, monkeypatch, capsys):
    def broken(priority, message):
        raise OSError("liblog assente")

    monkeypatch.setattr(debug, "_write", broken)
    debug.fail(debug.STAGE_ENCODER, "thread terminato")
    err = capsys.readouterr().err
    assert "GIOCO/E: scrittura log fallita (OSError: liblog assente)" in err
    assert "encoder" in err


def test_desktop_output_is_stderr(monkeypatch, capsys):
    monkeypatch.setattr(debug, "DEBUG", True)
    monkeypatch.setattr(debug, "_write", None)
    assert debug.output_name() == "stderr"
    debug.ok(debug.STAGE_DEBUG, "prova")
    assert "GIOCO/I: t=" in capsys.readouterr().err
