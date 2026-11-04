"""Mouse output via Win32 SendInput, with optional Arduino serial backend."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import struct
import time
from typing import Optional

logger = logging.getLogger(__name__)

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000

INPUT_MOUSE = 0


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.wintypes.DWORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT(ctypes.Structure):
    class _INPUT_UNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]

    _anonymous_ = ("_union",)
    _fields_ = [
        ("type", ctypes.wintypes.DWORD),
        ("_union", _INPUT_UNION),
    ]


def _send_input(inp: INPUT) -> None:
    """Call SendInput with a single INPUT structure."""
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


class MouseOutput:
    """Win32 SendInput mouse mover with sub-pixel accumulation."""

    def __init__(self) -> None:
        self._button_down = False
        self._accum_x: float = 0.0
        self._accum_y: float = 0.0

    def move_precise(self, dx: float, dy: float) -> None:
        """Accumulate fractional mouse movement and send integer part."""
        self._accum_x += dx
        self._accum_y += dy
        ix = int(self._accum_x)
        iy = int(self._accum_y)
        if ix == 0 and iy == 0:
            return
        self._accum_x -= ix
        self._accum_y -= iy
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.mi.dx = ix
        inp.mi.dy = iy
        inp.mi.dwFlags = MOUSEEVENTF_MOVE
        inp.mi.mouseData = 0
        inp.mi.time = 0
        inp.mi.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
        _send_input(inp)

    def move(self, dx: int, dy: int) -> None:
        """Send a relative mouse move."""
        if dx == 0 and dy == 0:
            return
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.mi.dx = dx
        inp.mi.dy = dy
        inp.mi.dwFlags = MOUSEEVENTF_MOVE
        inp.mi.mouseData = 0
        inp.mi.time = 0
        inp.mi.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
        _send_input(inp)

    def click(self, down: bool, delay_ms: float = 0.0) -> None:
        """Press or release left mouse button (idempotent)."""
        if down and self._button_down:
            return
        if not down and not self._button_down:
            return
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.mi.dx = 0
        inp.mi.dy = 0
        inp.mi.dwFlags = MOUSEEVENTF_LEFTDOWN if down else MOUSEEVENTF_LEFTUP
        inp.mi.mouseData = 0
        inp.mi.time = 0
        inp.mi.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
        _send_input(inp)
        self._button_down = down

    def release(self) -> None:
        """Ensure button is released."""
        if self._button_down:
            self.click(down=False)


class SerialOutput:
    """Arduino HID backend speaking 'M dx dy', 'D', 'U' at 115200."""

    def __init__(self, port: str = "COM3", baudrate: int = 115200) -> None:
        self._ser: Optional[object] = None
        self._button_down = False
        try:
            import serial
            self._ser = serial.Serial(port, baudrate, timeout=0.05)
            logger.info("Serial output on %s @ %d", port, baudrate)
        except Exception:
            logger.warning("Serial port %s unavailable", port, exc_info=True)

    def move(self, dx: int, dy: int) -> None:
        """Send relative move command over serial."""
        if self._ser is None or (dx == 0 and dy == 0):
            return
        try:
            self._ser.write(f"M {dx} {dy}\n".encode())
        except Exception:
            logger.warning("Serial move failed", exc_info=True)

    def click(self, down: bool, delay_ms: float = 0.0) -> None:
        """Send click down/up over serial (idempotent)."""
        if self._ser is None:
            return
        if down and self._button_down:
            return
        if not down and not self._button_down:
            return
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)
        try:
            cmd = b"D\n" if down else b"U\n"
            self._ser.write(cmd)
            self._button_down = down
        except Exception:
            logger.warning("Serial click failed", exc_info=True)

    def release(self) -> None:
        """Ensure button is released."""
        if self._button_down:
            self.click(down=False)

    def close(self) -> None:
        """Close serial port."""
        self.release()
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None
