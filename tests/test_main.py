from datetime import datetime

import pytest

from main import (
    BlinkDot,
    RecordingBadge,
    RoundButton,
    choose_preview_size,
    choose_size,
    cover_tex_coords,
    format_duration,
    media_filename,
    orientation_hint,
    rotated_size,
    surface_rotation_to_degrees,
)


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
