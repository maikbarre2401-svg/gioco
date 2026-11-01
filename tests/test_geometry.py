from datetime import datetime

import pytest

from geometry import (
    choose_preview_size,
    choose_size,
    cover_size,
    orientation_hint,
    rotated_size,
    surface_rotation_to_degrees,
    video_filename,
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


def test_choose_preview_size_without_preferred():
    assert choose_preview_size((3840, 2160), [(1280, 720), (1920, 1080)], None) == (1920, 1080)


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


def test_rotated_size_rejects_invalid():
    with pytest.raises(ValueError):
        rotated_size((1920, 1080), 45)


def test_cover_size_exact_fit():
    assert cover_size((720, 1280), (1080, 1920)) == (1080, 1920)


def test_cover_size_crops_horizontally_on_taller_screen():
    width, height = cover_size((1080, 1920), (1080, 2400))
    assert height == 2400
    assert width >= 1080


def test_cover_size_crops_vertically_on_wider_box():
    width, height = cover_size((1080, 1920), (1440, 1920))
    assert width == 1440
    assert height >= 1920


def test_cover_size_rejects_zero():
    with pytest.raises(ValueError):
        cover_size((0, 1920), (1080, 1920))


def test_video_filename():
    assert video_filename(datetime(2026, 11, 1, 9, 5, 7)) == "VID_20261101_090507.mp4"
