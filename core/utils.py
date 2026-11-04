"""System utility helpers for Windows."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


def set_dpi_aware() -> None:
    """Set process DPI awareness to per-monitor v2."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            logger.warning("Could not set DPI awareness")


def screen_size() -> Tuple[int, int]:
    """Return (width, height) of the primary monitor."""
    user32 = ctypes.windll.user32
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def foreground_exe() -> str:
    """Return the lowercase executable name of the foreground window."""
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""

    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value == 0:
        return ""

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ""

    try:
        buf = ctypes.create_unicode_buffer(512)
        size = ctypes.wintypes.DWORD(512)
        ok = kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
        if ok:
            path = buf.value
            return path.rsplit("\\", 1)[-1].lower()
        return ""
    finally:
        kernel32.CloseHandle(handle)


def is_admin() -> bool:
    """Return True if the process is running elevated."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def clamp(value: float, lo: float, hi: float) -> float:
    """Clamp value to [lo, hi]."""
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def iou_box(
    a: Tuple[float, float, float, float],
    b: Tuple[float, float, float, float],
) -> float:
    """Intersection-over-Union for two (x1, y1, x2, y2) boxes."""
    ix1 = max(a[0], b[0])
    iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2])
    iy2 = min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, (a[2] - a[0]) * (a[3] - a[1]))
    area_b = max(0.0, (b[2] - b[0]) * (b[3] - b[1]))
    union = area_a + area_b - inter
    return inter / union if union > 1e-6 else 0.0


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation from a to b by factor t."""
    return a + (b - a) * t
