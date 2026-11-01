import pytest

from main import (
    PREVIEW_FBO,
    PREVIEW_MODE,
    PREVIEW_MODES,
    PREVIEW_SURFACE,
    CameraError,
    YuvPreviewRenderer,
    check_preview_mode,
    contain_rect,
    kivy_rect_to_android,
    save_texture_png,
)

WIDTH, HEIGHT = 16, 8


@pytest.fixture
def gl_context():
    from kivy.core.window import Window

    return Window


def nv21(y_value, width=WIDTH, height=HEIGHT, v=128, u=128):
    luma = bytes(y_value(x, row) for row in range(height) for x in range(width))
    return luma + bytes([v, u]) * ((width // 2) * (height // 2))


def left_half_white(x, row):
    return 255 if x < WIDTH // 2 else 0


def top_rows_white(x, row):
    return 255 if row < HEIGHT // 2 else 0


def pixel(renderer, x, y):
    """RGBA del FBO con origine in basso a sinistra, come Kivy."""
    width = renderer.content_size[0]
    data = renderer.fbo.pixels
    offset = (y * width + x) * 4
    return tuple(data[offset:offset + 4])


def is_white(rgba):
    return all(channel > 230 for channel in rgba[:3])


def is_black(rgba):
    return all(channel < 25 for channel in rgba[:3])


def render(rotation, y_value):
    renderer = YuvPreviewRenderer((WIDTH, HEIGHT), rotation)
    renderer.compile()
    renderer.upload(nv21(y_value))
    return renderer


def test_default_mode_is_fbo():
    assert PREVIEW_MODE == PREVIEW_FBO
    assert PREVIEW_MODES == (PREVIEW_FBO, PREVIEW_SURFACE)


@pytest.mark.parametrize("mode", ["fbo", "surface"])
def test_check_preview_mode_accepts_known_modes(mode):
    assert check_preview_mode(mode) == mode


def test_check_preview_mode_rejects_unknown():
    with pytest.raises(ValueError, match="PREVIEW_MODE non valido"):
        check_preview_mode("texture_view")


def test_contain_rect_letterboxes_wide_area():
    assert contain_rect((1080, 1920), (0, 150, 1080, 1500)) == (118, 150, 843, 1500)


def test_contain_rect_pillarboxes_tall_area():
    assert contain_rect((1080, 1920), (0, 0, 1080, 2400)) == (0, 240, 1080, 1920)


def test_contain_rect_rejects_empty_area():
    with pytest.raises(ValueError):
        contain_rect((1080, 1920), (0, 0, 0, 100))


def test_kivy_rect_to_android_flips_y_axis():
    assert kivy_rect_to_android((118, 150, 843, 1500), window_height=1920) == (118, 270, 843, 1500)


def test_renderer_rejects_odd_sizes(gl_context):
    with pytest.raises(ValueError):
        YuvPreviewRenderer((15, 8), 90)


def test_renderer_requires_compile(gl_context):
    renderer = YuvPreviewRenderer((WIDTH, HEIGHT), 0)
    with pytest.raises(CameraError):
        renderer.upload(nv21(left_half_white))


def test_renderer_rejects_short_frame(gl_context):
    renderer = YuvPreviewRenderer((WIDTH, HEIGHT), 0)
    renderer.compile()
    with pytest.raises(ValueError, match="attesi 192"):
        renderer.upload(b"\x00" * 100)


@pytest.mark.parametrize(
    ("rotation", "content_size", "white_at", "black_at"),
    [
        (0, (16, 8), (2, 4), (13, 4)),
        (90, (8, 16), (4, 13), (4, 2)),
        (180, (16, 8), (13, 4), (2, 4)),
        (270, (8, 16), (4, 2), (4, 13)),
    ],
)
def test_left_side_of_sensor_follows_rotation(gl_context, rotation, content_size, white_at, black_at):
    renderer = render(rotation, left_half_white)
    assert renderer.content_size == content_size
    assert is_white(pixel(renderer, *white_at))
    assert is_black(pixel(renderer, *black_at))


@pytest.mark.parametrize(
    ("rotation", "white_at", "black_at"),
    [
        (0, (8, 6), (8, 1)),
        (90, (6, 8), (1, 8)),
        (180, (8, 1), (8, 6)),
        (270, (1, 8), (6, 8)),
    ],
)
def test_top_rows_of_buffer_follow_rotation(gl_context, rotation, white_at, black_at):
    renderer = render(rotation, top_rows_white)
    assert is_white(pixel(renderer, *white_at))
    assert is_black(pixel(renderer, *black_at))


def test_nv21_red_becomes_red(gl_context):
    renderer = YuvPreviewRenderer((WIDTH, HEIGHT), 90)
    renderer.compile()
    renderer.upload(nv21(lambda x, row: 76, v=255, u=85))
    r, g, b, _ = pixel(renderer, 4, 8)
    assert r > 220 and g < 40 and b < 40


def test_photo_from_surface_fbo_is_upright(gl_context, tmp_path):
    from PIL import Image

    renderer = render(90, left_half_white)
    path = tmp_path / "foto.png"
    save_texture_png(renderer.texture, str(path))
    with Image.open(path) as image:
        assert image.size == (8, 16)
        rgb = image.convert("RGB")
        assert is_white(rgb.getpixel((4, 2)))
        assert is_black(rgb.getpixel((4, 13)))


def test_upload_counts_frames(gl_context):
    renderer = render(0, left_half_white)
    renderer.upload(nv21(top_rows_white))
    assert renderer.frames == 2
