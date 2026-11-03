"""Humanised aim: reaction gate, spring dynamics, tremor, fatigue, sticky aim."""

from __future__ import annotations

import math
import random
import time
from typing import Tuple

from core.config import Config
from core.utils import clamp


class Humanizer:
    """Produces human-like aim adjustments: spring physics, tremor, fatigue."""

    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self._session_start = time.monotonic()
        self._engage_start: float = 0.0
        self._reaction_deadline: float = 0.0
        self._missed: bool = False
        self._miss_dx: float = 0.0
        self._miss_dy: float = 0.0
        self._spring_vel_x: float = 0.0
        self._spring_vel_y: float = 0.0
        self._residual_x: float = 0.0
        self._residual_y: float = 0.0
        self._tremor_phases = [
            (random.uniform(0.8, 1.2) * cfg.tremor_hz, random.uniform(0, 2 * math.pi))
            for _ in range(4)
        ]
        self._tremor_t: float = 0.0

    def start_engagement(self, distance_px: float) -> None:
        """Begin a new aim engagement: set reaction deadline and miss flag."""
        cfg = self._cfg
        raw = random.gauss(cfg.reaction_ms, cfg.reaction_var)
        delay_ms = max(20.0, raw)
        if cfg.fitts and distance_px > 1.0:
            fitts_extra = 50.0 * math.log2(1.0 + distance_px / 50.0)
            delay_ms += fitts_extra
        self._reaction_deadline = time.monotonic() + delay_ms / 1000.0
        self._engage_start = time.monotonic()
        self._spring_vel_x = 0.0
        self._spring_vel_y = 0.0
        self._residual_x = 0.0
        self._residual_y = 0.0
        self._tremor_t = 0.0
        self._missed = random.random() < cfg.miss_rate
        if self._missed:
            angle = random.uniform(0, 2 * math.pi)
            r = abs(random.gauss(0, cfg.miss_deg))
            self._miss_dx = r * math.cos(angle)
            self._miss_dy = r * math.sin(angle) * 0.3
        else:
            self._miss_dx = 0.0
            self._miss_dy = 0.0

    def reacting(self) -> bool:
        """Return True if still within the reaction delay period."""
        return time.monotonic() < self._reaction_deadline

    def fatigue(self) -> float:
        """Return fatigue multiplier 1.0..2.2 based on engagement and session duration."""
        if not self._cfg.fatigue:
            return 1.0
        now = time.monotonic()
        engage_s = now - self._engage_start if self._engage_start > 0 else 0.0
        session_s = now - self._session_start
        f = 1.0 + engage_s * self._cfg.fatigue_rate + session_s * 0.0009
        return clamp(f, 1.0, 2.2)

    def spring(self, err_x_deg: float, err_y_deg: float, dt: float) -> Tuple[float, float]:
        """Second-order spring dynamics returning (step_x_deg, step_y_deg)."""
        fat = self.fatigue()
        omega = self._cfg.omega / fat
        zeta = self._cfg.zeta / fat

        omega_sq = omega * omega

        ax = -(omega_sq) * (err_x_deg + self._residual_x) - 2.0 * zeta * omega * self._spring_vel_x
        ay = -(omega_sq) * (err_y_deg + self._residual_y) - 2.0 * zeta * omega * self._spring_vel_y

        self._spring_vel_x += ax * dt
        self._spring_vel_y += ay * dt

        step_x = self._spring_vel_x * dt
        step_y = self._spring_vel_y * dt

        if self._cfg.overshoot > 0 and zeta < 1.0:
            self._residual_x *= (1.0 - dt * 2.0)
            self._residual_y *= (1.0 - dt * 2.0)

        return (step_x, step_y)

    def tremor(self, dt: float) -> Tuple[float, float]:
        """Return smooth 2-axis tremor offset built from summed sines."""
        if self._cfg.tremor <= 0:
            return (0.0, 0.0)
        self._tremor_t += dt
        tx = 0.0
        ty = 0.0
        for i, (freq, phase) in enumerate(self._tremor_phases):
            angle = 2.0 * math.pi * freq * self._tremor_t + phase
            if i % 2 == 0:
                tx += math.sin(angle)
            else:
                ty += math.sin(angle)
        scale = self._cfg.tremor / len(self._tremor_phases) * 2.0
        return (tx * scale, ty * scale)

    def miss_offset(self) -> Tuple[float, float]:
        """Return the miss offset in degrees if this engagement was flagged as a miss."""
        if self._missed:
            dx, dy = self._miss_dx, self._miss_dy
            self._miss_dx *= 0.85
            self._miss_dy *= 0.85
            return (dx, dy)
        return (0.0, 0.0)

    def sticky(self, distance_px: float) -> float:
        """Return aim slowdown gain: sticky_gain below sticky_radius, ramping to 1.0."""
        cfg = self._cfg
        if distance_px < cfg.sticky_radius:
            return cfg.sticky_gain
        ramp_zone = cfg.sticky_radius * 0.5
        if distance_px < cfg.sticky_radius + ramp_zone:
            t = (distance_px - cfg.sticky_radius) / ramp_zone
            return cfg.sticky_gain + t * (1.0 - cfg.sticky_gain)
        return 1.0
