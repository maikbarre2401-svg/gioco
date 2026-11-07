"""XInput gamepad polling via ctypes — no external dependencies."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

ERROR_SUCCESS = 0
ERROR_DEVICE_NOT_CONNECTED = 1167
XINPUT_GAMEPAD_LEFT_TRIGGER = 0
XINPUT_GAMEPAD_RIGHT_TRIGGER = 1


class _XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ("wButtons", ctypes.wintypes.WORD),
        ("bLeftTrigger", ctypes.c_ubyte),
        ("bRightTrigger", ctypes.c_ubyte),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]


class _XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ("dwPacketNumber", ctypes.wintypes.DWORD),
        ("Gamepad", _XINPUT_GAMEPAD),
    ]


BUTTON_NAMES = {
    0x0001: "dpad_up",
    0x0002: "dpad_down",
    0x0004: "dpad_left",
    0x0008: "dpad_right",
    0x0010: "start",
    0x0020: "back",
    0x0040: "left_stick",
    0x0080: "right_stick",
    0x0100: "lb",
    0x0200: "rb",
    0x1000: "a",
    0x2000: "b",
    0x4000: "x",
    0x8000: "y",
}

AIM_TRIGGER_MAP = {
    "lt": "left_trigger",
    "rt": "right_trigger",
    "lb": "lb",
    "rb": "rb",
}


def _load_xinput():
    for dll in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
        try:
            lib = ctypes.WinDLL(dll)
            fn = lib.XInputGetState
            fn.argtypes = [ctypes.wintypes.DWORD, ctypes.POINTER(_XINPUT_STATE)]
            fn.restype = ctypes.wintypes.DWORD
            return fn
        except (OSError, AttributeError):
            continue
    return None


class Gamepad:
    """Polls an XInput controller and fires callbacks on aim trigger edges."""

    def __init__(
        self,
        aim_trigger: str = "lt",
        trigger_threshold: int = 80,
        poll_hz: int = 120,
    ) -> None:
        self._get_state = _load_xinput()
        self._available = self._get_state is not None
        self._aim_trigger = AIM_TRIGGER_MAP.get(aim_trigger, "left_trigger")
        self._threshold = trigger_threshold
        self._poll_interval = 1.0 / poll_hz
        self._user_index = 0

        self._on_aim_press: Optional[Callable[[], None]] = None
        self._on_aim_release: Optional[Callable[[], None]] = None
        self._aim_down = False
        self._connected = False

        self._stop = False
        self._thread: Optional[threading.Thread] = None

    @property
    def available(self) -> bool:
        return self._available

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def aim_down(self) -> bool:
        return self._aim_down

    def set_callbacks(
        self,
        on_press: Optional[Callable[[], None]] = None,
        on_release: Optional[Callable[[], None]] = None,
    ) -> None:
        self._on_aim_press = on_press
        self._on_aim_release = on_release

    def start(self) -> None:
        if not self._available:
            logger.info("XInput not available — gamepad disabled")
            return
        if self.running:
            return
        self._stop = False
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop = True
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def configure(self, aim_trigger: str, threshold: int) -> None:
        self._aim_trigger = AIM_TRIGGER_MAP.get(aim_trigger, "left_trigger")
        self._threshold = threshold

    def _find_controller(self, state: _XINPUT_STATE) -> Optional[int]:
        """Scan all four XInput slots for a connected pad, return its index."""
        for idx in range(4):
            if self._get_state(idx, ctypes.byref(state)) == ERROR_SUCCESS:
                return idx
        return None

    def _poll_loop(self) -> None:
        state = _XINPUT_STATE()
        misses = 0
        while not self._stop:
            result = self._get_state(self._user_index, ctypes.byref(state))

            if result == ERROR_DEVICE_NOT_CONNECTED:
                if self._connected:
                    self._connected = False
                    self._aim_down = False
                    logger.info("Gamepad disconnected")
                found = self._find_controller(state)
                if found is None:
                    misses += 1
                    time.sleep(self._poll_interval if misses < 30 else 1.0)
                    continue
                self._user_index = found
                result = ERROR_SUCCESS

            if result != ERROR_SUCCESS:
                time.sleep(self._poll_interval)
                continue

            if not self._connected:
                self._connected = True
                misses = 0
                logger.info("Gamepad connected (index %d)", self._user_index)

            gp = state.Gamepad
            pressed = self._check_aim(gp)

            if pressed and not self._aim_down:
                self._aim_down = True
                if self._on_aim_press:
                    self._on_aim_press()
            elif not pressed and self._aim_down:
                self._aim_down = False
                if self._on_aim_release:
                    self._on_aim_release()

            time.sleep(self._poll_interval)

    def _check_aim(self, gp: _XINPUT_GAMEPAD) -> bool:
        if self._aim_trigger == "left_trigger":
            return gp.bLeftTrigger >= self._threshold
        elif self._aim_trigger == "right_trigger":
            return gp.bRightTrigger >= self._threshold
        elif self._aim_trigger == "lb":
            return bool(gp.wButtons & 0x0100)
        elif self._aim_trigger == "rb":
            return bool(gp.wButtons & 0x0200)
        return False
