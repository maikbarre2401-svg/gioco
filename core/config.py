"""Configuration dataclass persisted to cfg.json."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, fields, asdict
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

_CFG_PATH = Path("cfg.json")


@dataclass
class Config:
    """All tunables for the aim-assist system."""

    schema: int = 2
    det_model: str = "yolov8n.pt"
    pose_model: str = "yolov8n-pose.pt"
    imgsz: int = 640
    pose_imgsz: int = 320
    capture: int = 640
    conf: float = 0.35
    kp_conf: float = 0.30
    multiscale: bool = True
    imgsz_far: int = 960
    device: str = "auto"
    half: bool = False
    use_pose: bool = True
    bone: str = "head"
    bone_by_distance: bool = True
    fov_px: int = 300
    hfov_deg: float = 80.0
    counts_per_deg: float = 1200.0
    max_step: int = 140
    tick_hz: int = 250
    deadzone: float = 0.9
    jitter: float = 0.0
    human: bool = True
    reaction_ms: int = 190
    reaction_var: int = 55
    omega: float = 26.0
    zeta: float = 0.62
    overshoot: float = 0.18
    fitts: bool = True
    tremor: float = 0.55
    tremor_hz: float = 7.5
    fatigue: bool = True
    fatigue_rate: float = 0.006
    miss_rate: float = 0.12
    miss_deg: float = 0.9
    sticky_radius: int = 55
    sticky_gain: float = 0.45
    switch_margin: float = 0.35
    switch_cooldown_ms: int = 160
    settle_ms: int = 90
    ads_delay_ms: int = 120
    lead_ms: int = 55
    trigger: bool = True
    trigger_radius: int = 12
    trigger_delay_ms: int = 40
    trigger_var_ms: int = 25
    recoil: float = 0.0
    hold_button: str = "x2"
    toggle_mode: bool = False
    always_active: bool = True
    crosshair_offset_x: int = 0
    crosshair_offset_y: int = 0
    overlay: bool = True
    overlay_skeleton: bool = True
    overlay_boxes: bool = True
    overlay_color: str = "#ff2fd0"
    overlay_skeleton_color: str = "#7a5cff"
    overlay_aim_circle: bool = True
    snap_duration_ms: int = 250
    snap_omega: float = 55.0
    snap_zeta: float = 0.85
    third_person: bool = True
    self_zone_w: int = 120
    self_zone_h: int = 300
    self_zone_offset_y: int = 30
    process: str = "fortniteclient-win64-shipping.exe"
    log_metrics: bool = True
    ads_mult: Dict[str, float] = field(
        default_factory=lambda: {"1.0": 1.0, "2.0": 0.55, "3.0": 0.38, "4.0": 0.28}
    )

    def ads(self, optic: float) -> float:
        """Return the ADS multiplier for a given optic zoom level."""
        key = str(optic)
        if key in self.ads_mult:
            return self.ads_mult[key]
        zooms = sorted(float(k) for k in self.ads_mult)
        if optic <= zooms[0]:
            return self.ads_mult[str(zooms[0])]
        if optic >= zooms[-1]:
            return self.ads_mult[str(zooms[-1])]
        for i in range(len(zooms) - 1):
            lo, hi = zooms[i], zooms[i + 1]
            if lo <= optic <= hi:
                t = (optic - lo) / (hi - lo)
                v_lo = self.ads_mult[str(lo)]
                v_hi = self.ads_mult[str(hi)]
                return v_lo + t * (v_hi - v_lo)
        return 1.0

    def save(self, path: Path | None = None) -> None:
        """Persist config to JSON."""
        p = path or _CFG_PATH
        try:
            p.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        except OSError:
            logger.exception("Failed to save config to %s", p)

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        """Load config from JSON, ignoring unknown keys."""
        p = path or _CFG_PATH
        if not p.exists():
            cfg = cls()
            cfg.save(p)
            return cfg
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.exception("Failed to load config from %s, using defaults", p)
            return cls()
        known = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in raw.items() if k in known}
        return cls(**filtered)
