from datetime import datetime

import pytest

from main import (
    BlinkDot,
    RecordingBadge,
    RoundButton,
    choose_preview_size,
    choose_size,
    cover_tex_coords,
    encoder_health,
    format_duration,
    gl_extensions,
    java_bytes,
    lan_addresses,
    mat4_multiply,
    media_filename,
    orientation_hint,
    rotated_size,
    shader_compile_log,
    stream_texts,
    surface_rotation_to_degrees,
    surface_texture_fallback_matrix,
)
from main import MAT4_FLIP_V, MAT4_IDENTITY


def test_choose_size_returns_exact_match():
    assert choose_size((1920, 1080), [(1280, 720), (1920, 1080)]) == (1920, 1080)


def test_choose_size_prefers_largest_same_aspect_not_larger():
    candidates = [(640, 480), (1280, 720), (960, 540), (3840, 2160)]
    assert choose_size((1920, 1080), candidates) == (1280, 720)


def test_choose_size_takes_smallest_when_all_larger():
    assert choose_size((640, 360), [(3840, 2160), (1920, 1080)]) == (1920, 1080)


def test_choose_size_falls_back_to_any_aspect():
    assert choose_size((1920, 1080), [(640, 480), (1600, 1200)]) == (1600, 1200)


def test_choose_size_rejects_empty_list():
    with pytest.raises(ValueError):
        choose_size((1920, 1080), [])


def test_choose_preview_size_uses_video_size_when_supported():
    assert choose_preview_size((1280, 720), [(1280, 720), (1920, 1080)], (1920, 1080)) == (1280, 720)


def test_choose_preview_size_uses_preferred_when_video_size_missing():
    assert choose_preview_size((3840, 2160), [(1280, 720), (1920, 1080)], (1920, 1080)) == (1920, 1080)


def test_choose_preview_size_ignores_unsupported_preferred():
    assert choose_preview_size((3840, 2160), [(1280, 720), (1920, 1080)], (800, 600)) == (1920, 1080)


@pytest.mark.parametrize(
    ("sensor", "display", "expected"),
    [(90, 0, 90), (270, 0, 270), (90, 90, 0), (90, 270, 180), (0, 90, 270)],
)
def test_orientation_hint(sensor, display, expected):
    assert orientation_hint(sensor, display) == expected


@pytest.mark.parametrize(("sensor", "display"), [(45, 0), (90, 30)])
def test_orientation_hint_rejects_invalid(sensor, display):
    with pytest.raises(ValueError):
        orientation_hint(sensor, display)


@pytest.mark.parametrize(("rotation", "degrees"), [(0, 0), (1, 90), (2, 180), (3, 270)])
def test_surface_rotation_to_degrees(rotation, degrees):
    assert surface_rotation_to_degrees(rotation) == degrees


def test_surface_rotation_to_degrees_rejects_unknown():
    with pytest.raises(ValueError):
        surface_rotation_to_degrees(4)


@pytest.mark.parametrize(
    ("rotation", "expected"),
    [(0, (1920, 1080)), (90, (1080, 1920)), (180, (1920, 1080)), (270, (1080, 1920))],
)
def test_rotated_size(rotation, expected):
    assert rotated_size((1920, 1080), rotation) == expected


def test_cover_tex_coords_same_aspect_uses_whole_texture():
    assert cover_tex_coords((1080, 1920), (540, 960)) == pytest.approx((0.0, 0.0, 1.0, 1.0))


def test_cover_tex_coords_crops_sides_on_taller_box():
    assert cover_tex_coords((1080, 1920), (1080, 2400)) == pytest.approx((0.1, 0.0, 0.9, 1.0))


def test_cover_tex_coords_crops_top_and_bottom_on_wider_box():
    assert cover_tex_coords((1080, 1920), (1440, 1920)) == pytest.approx((0.0, 0.125, 1.0, 0.875))


def test_cover_tex_coords_rejects_zero():
    with pytest.raises(ValueError):
        cover_tex_coords((1080, 1920), (0, 100))


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0, "00:00"), (-3, "00:00"), (9.9, "00:09"), (65, "01:05"), (3600, "1:00:00"), (3725, "1:02:05")],
)
def test_format_duration(seconds, expected):
    assert format_duration(seconds) == expected


def test_media_filename_includes_milliseconds():
    moment = datetime(2026, 11, 1, 9, 5, 7, 42_500)
    assert media_filename("IMG", "png", moment) == "IMG_20261101_090507_042.png"


def test_round_button_rejects_unknown_glyph():
    with pytest.raises(ValueError):
        RoundButton("flash")


@pytest.mark.parametrize("glyph", ["photo", "video", "audio"])
def test_round_button_dims_when_disabled(glyph):
    button = RoundButton(glyph, size_hint=(None, None), size=(64, 64))
    button.disabled = True
    assert button.opacity == pytest.approx(0.35)
    button.disabled = False
    button.active = True
    assert button.opacity == 1.0


def test_blink_dot_toggles_and_resets():
    dot = BlinkDot()
    dot._toggle(0.5)
    assert dot._color.a == 0.0
    dot._toggle(0.5)
    assert dot._color.a == 1.0
    dot._toggle(0.5)
    dot.stop()
    assert dot._color.a == 1


def test_recording_badge_shows_elapsed_time():
    badge = RecordingBadge()
    assert badge.opacity == 0
    badge.show()
    badge.set_elapsed(75)
    assert badge.opacity == 1
    assert badge.time_label.text == "01:15"
    badge.hide()
    assert badge.opacity == 0


def test_java_bytes_accepts_bytes_and_signed_lists():
    assert java_bytes(b"\xff\x00") == b"\xff\x00"
    assert java_bytes(bytearray(b"ab")) == b"ab"
    assert java_bytes([-1, 0, 127, -128]) == b"\xff\x00\x7f\x80"


def test_java_bytes_uses_tostring():
    class FakeByteArray:
        def tostring(self):
            return b"jpeg"

    assert java_bytes(FakeByteArray()) == b"jpeg"


def test_stream_texts_with_ip():
    title, big, detail, compact = stream_texts("192.168.1.23", 8080, 0, None)
    assert title == "Apri dal PC"
    assert big == "192.168.1.23"
    assert detail == "http://192.168.1.23:8080/  ·  nessuno spettatore"
    assert compact == "192.168.1.23:8080  ·  nessuno spettatore"


def test_stream_texts_counts_viewers():
    assert stream_texts("10.0.0.5", 8081, 2, None)[3] == "10.0.0.5:8081  ·  spettatori: 2"


def test_stream_texts_without_network():
    assert stream_texts(None, 8080, 0, None)[1] == "Wi-Fi assente"


def test_stream_texts_with_server_error():
    title, big, detail, _ = stream_texts("10.0.0.5", None, 0, "porte occupate")
    assert (title, big, detail) == ("Server non avviato", "Errore", "porte occupate")


def apply_mat4(matrix, x, y):
    return (matrix[0] * x + matrix[4] * y + matrix[12], matrix[1] * x + matrix[5] * y + matrix[13])


def test_mat4_multiply_identity():
    assert mat4_multiply(MAT4_IDENTITY, MAT4_FLIP_V) == pytest.approx(MAT4_FLIP_V)


@pytest.mark.parametrize(
    ("rotation", "mapping"),
    [
        (0, lambda x, y: (x, 1 - y)),
        (90, lambda x, y: (1 - y, 1 - x)),
        (180, lambda x, y: (1 - x, y)),
        (270, lambda x, y: (y, x)),
    ],
)
def test_surface_texture_fallback_matrix_maps_corners(rotation, mapping):
    matrix = surface_texture_fallback_matrix(rotation)
    for x, y in ((0, 0), (1, 0), (1, 1), (0, 1), (0.25, 0.75)):
        assert apply_mat4(matrix, x, y) == pytest.approx(mapping(x, y))


def test_surface_texture_fallback_matrix_rejects_invalid_rotation():
    with pytest.raises(ValueError):
        surface_texture_fallback_matrix(45)


def test_lan_addresses_on_desktop_are_private():
    import ipaddress

    for ip in lan_addresses():
        assert ipaddress.IPv4Address(ip).is_private


def fake_encoder(alive=True, last_error=None, last_error_at=None, last_encoded_at=None):
    from types import SimpleNamespace

    return SimpleNamespace(
        is_alive=alive, last_error=last_error, last_error_at=last_error_at, last_encoded_at=last_encoded_at
    )


def test_encoder_health_dead_thread():
    assert encoder_health(fake_encoder(alive=False)) == (False, "thread mjpeg-encoder terminato")


def test_encoder_health_idle():
    assert encoder_health(fake_encoder()) == (True, "thread vivo, nessun fotogramma da codificare")


def test_encoder_health_failing_since_last_success():
    health = encoder_health(fake_encoder(last_error="JavaException: x", last_error_at=5.0, last_encoded_at=4.0))
    assert health == (False, "thread vivo ma la codifica fallisce: JavaException: x")


def test_encoder_health_recovered():
    health = encoder_health(fake_encoder(last_error="JavaException: x", last_error_at=4.0, last_encoded_at=5.0))
    assert health == (True, "thread vivo, codifica JPEG riuscita")


@pytest.fixture
def gl_context():
    from kivy.core.window import Window

    return Window


def test_gl_extensions_lists_something(gl_context):
    assert gl_extensions().strip()


def test_shader_compile_log_valid_shader(gl_context):
    assert shader_compile_log("void main() { gl_FragColor = vec4(1.0); }").startswith("compile_status=1")


def test_shader_compile_log_reports_errors(gl_context):
    result = shader_compile_log("void main() { questo non compila }")
    assert result.startswith("compile_status=0 log=")
    assert "<vuoto>" not in result
