"""Screen capture via dxcam with mss fallback."""

from __future__ import annotations

import logging
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class Capturer:
    """Captures a centered screen region as BGR ndarray."""

    def __init__(self, region: int) -> None:
        self._region = region
        self._dxcam_cam = None
        self._use_mss = False
        self._mss_inst = None
        self._bbox: Optional[Tuple[int, int, int, int]] = None
        self._init_bbox()
        self._init_dxcam()

    def _init_bbox(self) -> None:
        """Compute centered capture bounding box."""
        import ctypes
        user32 = ctypes.windll.user32
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        half = self._region // 2
        cx, cy = sw // 2, sh // 2
        self._bbox = (cx - half, cy - half, cx + half, cy + half)

    def _init_dxcam(self) -> None:
        """Try to initialise dxcam; fall back to mss on failure."""
        try:
            import dxcam
            cam = dxcam.create(output_color="BGR")
            if cam is None:
                raise RuntimeError("dxcam.create returned None")
            cam.start(target_fps=300, region=self._bbox)
            self._dxcam_cam = cam
            logger.info("dxcam capture initialised")
        except Exception:
            logger.warning("dxcam unavailable, falling back to mss", exc_info=True)
            self._use_mss = True
            self._init_mss()

    def _init_mss(self) -> None:
        """Initialise mss fallback."""
        try:
            import mss
            self._mss_inst = mss.mss()
        except Exception:
            logger.exception("mss initialisation failed")
            self._mss_inst = None

    def grab(self) -> Optional[np.ndarray]:
        """Return a BGR ndarray of the capture region, or None on failure."""
        if not self._use_mss and self._dxcam_cam is not None:
            try:
                frame = self._dxcam_cam.get_latest_frame()
                if frame is not None:
                    return np.ascontiguousarray(frame)
            except Exception:
                logger.warning("dxcam grab failed, switching to mss", exc_info=True)
                self._release_dxcam()
                self._use_mss = True
                self._init_mss()

        if self._use_mss and self._mss_inst is not None:
            try:
                left, top, right, bottom = self._bbox
                monitor = {
                    "left": left,
                    "top": top,
                    "width": right - left,
                    "height": bottom - top,
                }
                shot = self._mss_inst.grab(monitor)
                frame = np.frombuffer(shot.rgb, dtype=np.uint8).reshape(
                    (shot.height, shot.width, 3)
                )
                import cv2
                return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            except Exception:
                logger.warning("mss grab failed", exc_info=True)

        return None

    def _release_dxcam(self) -> None:
        """Stop and release dxcam camera."""
        if self._dxcam_cam is not None:
            try:
                self._dxcam_cam.stop()
            except Exception:
                pass
            self._dxcam_cam = None

    def release(self) -> None:
        """Release all capture resources."""
        self._release_dxcam()
        if self._mss_inst is not None:
            try:
                self._mss_inst.close()
            except Exception:
                pass
            self._mss_inst = None
