"""YOLO detection and pose estimation with multi-scale and IoU tracking."""

from __future__ import annotations

import logging
from typing import Callable, List, Optional, Tuple

import numpy as np
import torch
from ultralytics import YOLO

from core.config import Config

logger = logging.getLogger(__name__)

Detection = Tuple[float, float, float, float, float]


def _iou(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    """Compute IoU between two (x1, y1, x2, y2) boxes."""
    ix1 = max(a[0], b[0])
    iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2])
    iy2 = min(a[3], b[3])
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    aa = max(0.0, (a[2] - a[0]) * (a[3] - a[1]))
    ab = max(0.0, (b[2] - b[0]) * (b[3] - b[1]))
    union = aa + ab - inter
    if union < 1e-6:
        return 0.0
    return inter / union


def _nms(dets: List[Detection], iou_thr: float = 0.5) -> List[Detection]:
    """Simple greedy NMS on a list of (x1, y1, x2, y2, conf)."""
    if not dets:
        return []
    dets = sorted(dets, key=lambda d: d[4], reverse=True)
    keep: List[Detection] = []
    for d in dets:
        suppress = False
        for k in keep:
            if _iou(d[:4], k[:4]) > iou_thr:
                suppress = True
                break
        if not suppress:
            keep.append(d)
    return keep


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
        if self._cfg.device == "auto":
            if torch.cuda.is_available():
                return "0"
            return "cpu"
        return self._cfg.device

    def _parse_results(self, results) -> List[Detection]:
        """Extract person detections from YOLO results."""
        dets: List[Detection] = []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                if int(box.cls[0]) != 0:
                    continue
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().tolist()
                conf = float(box.conf[0])
                dets.append((x1, y1, x2, y2, conf))
        return dets

    def detect(
        self, frame: np.ndarray, tracked_box: tuple[float, float, float, float] | None = None
    ) -> List[Detection]:
        """Run detection with optional multi-scale for distant targets."""
        results = self._det_model.predict(
            frame,
            imgsz=self._cfg.imgsz,
            conf=self._cfg.conf,
            device=self._device,
            verbose=False,
            classes=[0],
        )
        detections = self._parse_results(results)

        if self._cfg.multiscale and self._cfg.imgsz_far > self._cfg.imgsz:
            results_far = self._det_model.predict(
                frame,
                imgsz=self._cfg.imgsz_far,
                conf=max(0.20, self._cfg.conf - 0.10),
                device=self._device,
                verbose=False,
                classes=[0],
            )
            dets_far = self._parse_results(results_far)
            detections = _nms(detections + dets_far, iou_thr=0.50)

        if tracked_box is not None:
            boosted = []
            for x1, y1, x2, y2, conf in detections:
                overlap = _iou((x1, y1, x2, y2), tracked_box)
                if overlap > 0.3:
                    conf = min(1.0, conf + overlap * 0.08)
                boosted.append((x1, y1, x2, y2, conf))
            detections = boosted

        return detections

    def keypoints(
        self, frame: np.ndarray, box: Tuple[float, float, float, float]
    ) -> Optional[np.ndarray]:
        """Run pose on adaptive crop with enhanced person selection."""
        x1, y1, x2, y2 = box
        bw = x2 - x1
        bh = y2 - y1
        min_dim = min(bw, bh)

        if min_dim < 30:
            expand_x, expand_y = bw * 0.70, bh * 0.55
        elif min_dim < 60:
            expand_x, expand_y = bw * 0.50, bh * 0.35
        elif min_dim < 100:
            expand_x, expand_y = bw * 0.30, bh * 0.20
        else:
            expand_x, expand_y = bw * 0.15, bh * 0.10

        fh, fw = frame.shape[:2]
        cx1 = max(0, int(x1 - expand_x))
        cy1 = max(0, int(y1 - expand_y))
        cx2 = min(fw, int(x2 + expand_x))
        cy2 = min(fh, int(y2 + expand_y))

        crop = frame[cy1:cy2, cx1:cx2]
        if crop.size == 0:
            return None

        pose_sz = self._cfg.pose_imgsz
        if min_dim < 35:
            pose_sz = max(pose_sz, 544)
        elif min_dim < 60:
            pose_sz = max(pose_sz, 480)
        elif min_dim < 100:
            pose_sz = max(pose_sz, 384)

        results = self._pose_model.predict(
            crop,
            imgsz=pose_sz,
            conf=max(0.15, self._cfg.kp_conf - 0.10),
            device=self._device,
            verbose=False,
        )

        target_in_crop = (x1 - cx1, y1 - cy1, x2 - cx1, y2 - cy1)
        tcx = (target_in_crop[0] + target_in_crop[2]) / 2
        tcy = (target_in_crop[1] + target_in_crop[3]) / 2

        best_kps: Optional[np.ndarray] = None
        best_score = -1.0

        for r in results:
            if r.keypoints is None:
                continue
            kp_data = r.keypoints.data.cpu().numpy()
            for i in range(kp_data.shape[0]):
                person_kps = kp_data[i]
                if person_kps.shape[0] < 17:
                    continue

                valid_x, valid_y, valid_c = [], [], []
                for k in range(17):
                    if float(person_kps[k, 2]) > 0.08:
                        valid_x.append(float(person_kps[k, 0]))
                        valid_y.append(float(person_kps[k, 1]))
                        valid_c.append(float(person_kps[k, 2]))

                if len(valid_x) < 3:
                    continue

                mean_conf = sum(valid_c) / len(valid_c)
                n_valid = len(valid_x) / 17.0

                kp_box = (min(valid_x), min(valid_y), max(valid_x), max(valid_y))
                iou = _iou(kp_box, target_in_crop)

                kp_cx = sum(valid_x) / len(valid_x)
                kp_cy = sum(valid_y) / len(valid_y)
                crop_diag = max(1.0, (cx2 - cx1 + cy2 - cy1) / 2.0)
                center_dist = ((kp_cx - tcx) ** 2 + (kp_cy - tcy) ** 2) ** 0.5
                proximity = max(0.0, 1.0 - center_dist / crop_diag)

                score = iou * 0.40 + mean_conf * 0.25 + n_valid * 0.15 + proximity * 0.20

                if score > best_score:
                    best_score = score
                    best_kps = person_kps.copy()

        if best_kps is None:
            return None

        best_kps[:, 0] += cx1
        best_kps[:, 1] += cy1
        return best_kps
