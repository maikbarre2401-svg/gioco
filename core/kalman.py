"""Constant-acceleration 1D Kalman filter for target tracking."""

from __future__ import annotations

import numpy as np


class Axis:
    """1D constant-acceleration Kalman filter with 3x3 state [position, velocity, acceleration]."""

    def __init__(self, process_noise: float = 80.0, measurement_noise: float = 2.5) -> None:
        self._x = np.zeros(3, dtype=np.float64)
        self._P = np.eye(3, dtype=np.float64) * 500.0
        self._Q_base = process_noise
        self._R = measurement_noise
        self._initialised = False

    def reset(self, value: float) -> None:
        self._x[0] = value
        self._x[1] = 0.0
        self._x[2] = 0.0
        self._P = np.eye(3, dtype=np.float64) * 500.0
        self._initialised = True

    def predict(self, dt: float) -> float:
        if not self._initialised:
            return float(self._x[0])
        dt2 = dt * dt
        F = np.array([
            [1.0, dt, 0.5 * dt2],
            [0.0, 1.0, dt],
            [0.0, 0.0, 1.0],
        ], dtype=np.float64)
        self._x = F @ self._x
        Q = np.array([
            [dt2 * dt2 / 4, dt2 * dt / 2, dt2 / 2],
            [dt2 * dt / 2, dt2, dt],
            [dt2 / 2, dt, 1.0],
        ], dtype=np.float64) * self._Q_base
        self._P = F @ self._P @ F.T + Q
        return float(self._x[0])

    def update(self, measurement: float) -> float:
        if not self._initialised:
            self.reset(measurement)
            return measurement
        S = float(self._P[0, 0] + self._R)
        if abs(S) < 1e-12:
            S = 1e-12
        y = measurement - self._x[0]
        gate = y * y / S
        if gate > 16.0:
            self._R = min(self._R * 2.0, 50.0)
        else:
            self._R = max(self._R * 0.98, 1.0)
        K = self._P[:, 0] / S
        self._x += K * y
        self._P = self._P - np.outer(K, self._P[0, :])
        return float(self._x[0])

    def lead(self, seconds: float) -> float:
        s2 = seconds * seconds
        return float(self._x[0] + self._x[1] * seconds + 0.5 * self._x[2] * s2)

    @property
    def initialised(self) -> bool:
        return self._initialised

    @property
    def position(self) -> float:
        return float(self._x[0])

    @property
    def velocity(self) -> float:
        return float(self._x[1])

    @property
    def acceleration(self) -> float:
        return float(self._x[2])


class Tracker:
    """2D target tracker wrapping X and Y acceleration-model Kalman axes."""

    def __init__(self) -> None:
        self.kx = Axis()
        self.ky = Axis()

    def reset(self, x: float, y: float) -> None:
        self.kx.reset(x)
        self.ky.reset(y)

    def feed(self, x: float, y: float, dt: float) -> tuple[float, float]:
        self.kx.predict(dt)
        self.ky.predict(dt)
        fx = self.kx.update(x)
        fy = self.ky.update(y)
        return (fx, fy)

    def predict(self, lead_seconds: float) -> tuple[float, float]:
        return (self.kx.lead(lead_seconds), self.ky.lead(lead_seconds))

    def velocity(self) -> tuple[float, float]:
        return (self.kx.velocity, self.ky.velocity)

    def acceleration(self) -> tuple[float, float]:
        return (self.kx.acceleration, self.ky.acceleration)
