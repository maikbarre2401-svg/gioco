"""Humanised aim: reaction gate, spring dynamics, tremor, fatigue, sticky aim, micro-corrections."""

from __future__ import annotations

import math
import random
import time
from typing import Tuple

from core.config import Config
from core.utils import clamp


class Humanizer:
    """Produces human-like aim adjustments: spring physics, tremor, fatigue, wind-up, micro-corrections."""

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
        self._windup_t: float = 0.0
        self._prev_err_x: float = 0.0
        self._prev_err_y: float = 0.0
        self._flick_boost: float = 0.0
        self._momentum_x: float = 0.0
        self._momentum_y: float = 0.0
        self._breath_t: float = random.uniform(0, 2 * math.pi)
        self._prev_step_x: float = 0.0
        self._prev_step_y: float = 0.0
        self._accel_limit: float = 800.0

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
        self._windup_t = 0.0
        self._flick_boost = 0.0
        self._momentum_x = 0.0
        self._momentum_y = 0.0
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

    def skip_reaction(self) -> None:
        """Clear the reaction deadline immediately (used during snap phase)."""
        self._reaction_deadline = 0

    def fatigue(self) -> float:
        """Return fatigue multiplier 1.0..2.2 based on engagement and session duration."""
        if not self._cfg.fatigue:
            return 1.0
        now = time.monotonic()
        engage_s = now - self._engage_start if self._engage_start > 0 else 0.0
        session_s = now - self._session_start
        f = 1.0 + engage_s * self._cfg.fatigue_rate + session_s * 0.0009
        return clamp(f, 1.0, 2.2)

    def _windup_factor(self, dt: float) -> float:
        """Smooth acceleration curve: starts slow, ramps to full speed over ~80ms."""
        self._windup_t += dt
        t = min(1.0, self._windup_t / 0.08)
        return 0.3 + 0.7 * (3 * t * t - 2 * t * t * t)

    def detect_flick(self, err_x: float, err_y: float, dt: float) -> None:
        """Detect sudden direction changes and boost response temporarily."""
        if dt < 0.0001:
            return
        derr_x = (err_x - self._prev_err_x) / dt
        derr_y = (err_y - self._prev_err_y) / dt
        change_rate = math.hypot(derr_x, derr_y)
        if change_rate > 800.0:
            self._flick_boost = min(1.0, change_rate / 2000.0)
        else:
            self._flick_boost *= max(0.0, 1.0 - dt * 8.0)
        self._prev_err_x = err_x
        self._prev_err_y = err_y

    def spring(self, err_x_deg: float, err_y_deg: float, dt: float, distance_px: float = 0.0) -> Tuple[float, float]:
        """Second-order spring with distance-adaptive params, flick boost, and acceleration limiting."""
        fat = self.fatigue()
        omega = self._cfg.omega / fat
        zeta = self._cfg.zeta / fat

        if distance_px > 0:
            fov = self._cfg.fov_px
            norm_dist = min(1.0, distance_px / max(1.0, fov))
            omega *= 0.7 + 0.6 * norm_dist
            zeta_adj = 0.15 * (1.0 - norm_dist)
            zeta = min(0.98, zeta + zeta_adj)

        self.detect_flick(err_x_deg, err_y_deg, dt)

        flick_omega_mult = 1.0 + self._flick_boost * 0.6
        omega *= flick_omega_mult

        windup = self._windup_factor(dt)
        omega *= windup

        omega_sq = omega * omega

        ax = -(omega_sq) * (err_x_deg + self._residual_x) - 2.0 * zeta * omega * self._spring_vel_x
        ay = -(omega_sq) * (err_y_deg + self._residual_y) - 2.0 * zeta * omega * self._spring_vel_y

        self._spring_vel_x += ax * dt
        self._spring_vel_y += ay * dt

        step_x = self._spring_vel_x * dt
        step_y = self._spring_vel_y * dt

        if dt > 0.0001:
            accel_x = (step_x - self._prev_step_x) / dt
            accel_y = (step_y - self._prev_step_y) / dt
            accel_mag = math.hypot(accel_x, accel_y)
            if accel_mag > self._accel_limit:
                scale = self._accel_limit / accel_mag
                step_x = self._prev_step_x + (step_x - self._prev_step_x) * scale
                step_y = self._prev_step_y + (step_y - self._prev_step_y) * scale
        self._prev_step_x = step_x
        self._prev_step_y = step_y

        self._momentum_x = self._momentum_x * 0.92 + step_x * 0.08
        self._momentum_y = self._momentum_y * 0.92 + step_y * 0.08
        step_x += self._momentum_x * 0.15
        step_y += self._momentum_y * 0.15

        if self._cfg.overshoot > 0 and zeta < 1.0:
            self._residual_x *= (1.0 - dt * 2.0)
            self._residual_y *= (1.0 - dt * 2.0)

        return (step_x, step_y)

    def micro_correction(self, err_x_deg: float, err_y_deg: float, dt: float) -> Tuple[float, float]:
        """Fine-grained sub-deadzone corrections with smooth cubic gain curve."""
        dist_deg = math.hypot(err_x_deg, err_y_deg)
        if dist_deg < 0.0005:
            return (0.0, 0.0)
        t = min(1.0, dist_deg / 0.6)
        gain = 0.45 * (t * t * (3.0 - 2.0 * t))
        jitter_scale = 0.012 * (1.0 - t * 0.7)
        jx = random.gauss(0, jitter_scale) * dt * 60
        jy = random.gauss(0, jitter_scale) * dt * 60
        return (err_x_deg * gain + jx, err_y_deg * gain + jy)

    def tremor(self, dt: float, distance_px: float = 0.0) -> Tuple[float, float]:
        """Return smooth 2-axis tremor + breathing, reduced when close to target."""
        if self._cfg.tremor <= 0:
            return (0.0, 0.0)
        self._tremor_t += dt
        self._breath_t += dt
        tx = 0.0
        ty = 0.0
        for i, (freq, phase) in enumerate(self._tremor_phases):
            angle = 2.0 * math.pi * freq * self._tremor_t + phase
            if i % 2 == 0:
                tx += math.sin(angle)
            else:
                ty += math.sin(angle)
        scale = self._cfg.tremor / len(self._tremor_phases) * 2.0
        fat = self.fatigue()
        scale *= (0.8 + 0.2 * fat)

        if distance_px > 0:
            proximity_damp = min(1.0, distance_px / max(1.0, self._cfg.fov_px * 0.3))
            scale *= 0.3 + 0.7 * proximity_damp

        breath_freq = 0.22
        breath_amp = self._cfg.tremor * 0.18
        breath_y = math.sin(2.0 * math.pi * breath_freq * self._breath_t) * breath_amp
        breath_x = math.sin(2.0 * math.pi * breath_freq * 0.5 * self._breath_t + 0.7) * breath_amp * 0.3

        return (tx * scale + breath_x, ty * scale + breath_y)

    def miss_offset(self) -> Tuple[float, float]:
        """Return the miss offset in degrees if this engagement was flagged as a miss."""
        if self._missed:
            dx, dy = self._miss_dx, self._miss_dy
            self._miss_dx *= 0.85
            self._miss_dy *= 0.85
            return (dx, dy)
        return (0.0, 0.0)

    def sticky(self, distance_px: float) -> float:
        """Smooth cubic sticky aim curve: strong slow-down near target, smooth ramp-out."""
        cfg = self._cfg
        sr = cfg.sticky_radius
        if distance_px >= sr * 1.5:
            return 1.0
        if distance_px < sr * 0.3:
            return cfg.sticky_gain * 0.8
        t = clamp(distance_px / (sr * 1.5), 0.0, 1.0)
        cubic = t * t * (3.0 - 2.0 * t)
        return cfg.sticky_gain + cubic * (1.0 - cfg.sticky_gain)

    def recoil_offset(self, recoil_amount: float, dt: float) -> Tuple[float, float]:
        """Compute humanized recoil compensation pull-down."""
        if recoil_amount <= 0:
            return (0.0, 0.0)
        jitter_x = random.gauss(0, recoil_amount * 0.08)
        pull_y = -recoil_amount * (0.85 + random.gauss(0, 0.05))
        return (jitter_x * dt * 60, pull_y * dt * 60)
