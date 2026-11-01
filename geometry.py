import math
from datetime import datetime

Size = tuple[int, int]

VALID_ROTATIONS = (0, 90, 180, 270)
SURFACE_ROTATION_DEGREES = {0: 0, 1: 90, 2: 180, 3: 270}
ASPECT_TOLERANCE = 0.01


def _area(size: Size) -> int:
    return size[0] * size[1]


def _aspect(size: Size) -> float:
    return size[0] / size[1]


def _check_rotation(value: int) -> None:
    if value not in VALID_ROTATIONS:
        raise ValueError(f"rotazione non valida: {value}")


def choose_size(target: Size, candidates: list[Size]) -> Size:
    if not candidates:
        raise ValueError("nessuna dimensione supportata dalla fotocamera")
    if target in candidates:
        return target
    same_aspect = [s for s in candidates if abs(_aspect(s) - _aspect(target)) <= ASPECT_TOLERANCE]
    pool = same_aspect or candidates
    not_larger = [s for s in pool if _area(s) <= _area(target)]
    if not_larger:
        return max(not_larger, key=_area)
    return min(pool, key=_area)


def choose_preview_size(video_size: Size, preview_sizes: list[Size], preferred: Size | None) -> Size:
    if video_size in preview_sizes:
        return video_size
    if preferred is not None and preferred in preview_sizes:
        return preferred
    return choose_size(video_size, preview_sizes)


def orientation_hint(sensor_degrees: int, display_degrees: int) -> int:
    _check_rotation(sensor_degrees)
    _check_rotation(display_degrees)
    return (sensor_degrees - display_degrees) % 360


def surface_rotation_to_degrees(rotation: int) -> int:
    if rotation not in SURFACE_ROTATION_DEGREES:
        raise ValueError(f"costante Surface.ROTATION sconosciuta: {rotation}")
    return SURFACE_ROTATION_DEGREES[rotation]


def rotated_size(size: Size, rotation: int) -> Size:
    _check_rotation(rotation)
    if rotation in (90, 270):
        return size[1], size[0]
    return size


def cover_size(content: Size, box: Size) -> Size:
    if min(*content, *box) <= 0:
        raise ValueError(f"dimensioni non positive: contenuto={content} area={box}")
    scale = max(box[0] / content[0], box[1] / content[1])
    return math.ceil(content[0] * scale), math.ceil(content[1] * scale)


def video_filename(moment: datetime) -> str:
    return moment.strftime("VID_%Y%m%d_%H%M%S.mp4")
