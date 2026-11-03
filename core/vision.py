"""YOLO detection and pose estimation."""

from __future__ import annotations

import logging
from typing import Callable, List, Optional, Tuple

import numpy as np
import torch
from ultralytics import YOLO

from core.config import Config

logger = logging.getLogger(__name__)

Detection = Tuple[float, float, float, float, float]


class Vision:
    """Loads YOLO detection and pose models, runs inference."""

    def __init__(self, cfg: Config, log: Callable[[str], None]) -> None:
        self._cfg = cfg
        self._log = log
        self._device = self._resolve_device()
        log(f"Vision device: {self._device}")

        self._det_model = YOLO(cfg.det_model)
        self._det_model.to(self._device)

        self._pose_model = YOLO(cfg.pose_model)
        self._pose_model.to(self._device)

        log("Models loaded")

    def _resolve_device(self) -> str:
        """Resolve 'auto' device to cuda:0 if available."""
        if self._cfg.device == "auto":
            if torch.cuda.is_available():
                return "0"
            return "cpu"
        return self._cfg.device

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """Run detection, return list of (x1, y1, x2, y2, conf) for class 0 (person)."""
        results = self._det_model.predict(
            frame,
            imgsz=self._cfg.imgsz,
            conf=self._cfg.conf,
            device=self._device,
            verbose=False,
            classes=[0],
        )
        detections: List[Detection] = []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                cls_id = int(box.cls[0])
                if cls_id != 0:
                    continue
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().tolist()
                conf = float(box.conf[0])
                detections.append((x1, y1, x2, y2, conf))
        return detections

    def keypoints(
        self, frame: np.ndarray, box: Tuple[float, float, float, float]
    ) -> Optional[np.ndarray]:
        """Run pose on an expanded crop, return (17, 3) keypoints in frame coords or None."""
        x1, y1, x2, y2 = box
        bw = x2 - x1
        bh = y2 - y1
        expand_x = bw * 0.15
        expand_y = bh * 0.10
        fh, fw = frame.shape[:2]
        cx1 = max(0, int(x1 - expand_x))
        cy1 = max(0, int(y1 - expand_y))
        cx2 = min(fw, int(x2 + expand_x))
        cy2 = min(fh, int(y2 + expand_y))

        crop = frame[cy1:cy2, cx1:cx2]
        if crop.size == 0:
            return None

        results = self._pose_model.predict(
            crop,
            imgsz=self._cfg.pose_imgsz,
            conf=self._cfg.kp_conf,
            device=self._device,
            verbose=False,
        )

        best_kps: Optional[np.ndarray] = None
        best_conf = -1.0

        for r in results:
            if r.keypoints is None:
                continue
            kp_data = r.keypoints.data.cpu().numpy()
            for i in range(kp_data.shape[0]):
                person_kps = kp_data[i]
                if person_kps.shape[0] < 17:
                    continue
                mean_conf = float(person_kps[:, 2].mean())
                if mean_conf > best_conf:
                    best_conf = mean_conf
                    best_kps = person_kps.copy()

        if best_kps is None:
            return None

        best_kps[:, 0] += cx1
        best_kps[:, 1] += cy1
        return best_kps
