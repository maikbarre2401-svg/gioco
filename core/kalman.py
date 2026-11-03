"""Constant-velocity 1D Kalman filter for target tracking."""

from __future__ import annotations

import numpy as np


class Axis:
    """1D constant-velocity Kalman filter with 2x2 state [position, velocity]."""

    def __init__(self, process_noise: float = 100.0, measurement_noise: float = 4.0) -> None:
        self._x = np.zeros(2, dtype=np.float64)
        self._P = np.eye(2, dtype=np.float64) * 500.0
        self._Q_base = process_noise
        self._R = measurement_noise
        self._initialised = False

    def reset(self, value: float) -> None:
        """Hard-reset the state to a measured position with zero velocity."""
        self._x[0] = value
        self._x[1] = 0.0
        self._P = np.eye(2, dtype=np.float64) * 500.0
        self._initialised = True

    def predict(self, dt: float) -> float:
        """Predict forward by dt seconds, return predicted position."""
        if not self._initialised:
            return float(self._x[0])
        F = np.array([[1.0, dt], [0.0, 1.0]], dtype=np.float64)
        self._x = F @ self._x
        Q = np.array(
            [[dt**4 / 4, dt**3 / 2], [dt**3 / 2, dt**2]], dtype=np.float64
        ) * self._Q_base
        self._P = F @ self._P @ F.T + Q
        return float(self._x[0])

    def update(self, measurement: float) -> float:
        """Incorporate a measurement, return updated position."""
        if not self._initialised:
            self.reset(measurement)
            return measurement
        S = self._P[0, 0] + self._R
        if abs(S) < 1e-12:
            S = 1e-12
        K0 = self._P[0, 0] / S
        K1 = self._P[1, 0] / S
        y = measurement - self._x[0]
        self._x[0] += K0 * y
        self._x[1] += K1 * y
        p00 = self._P[0, 0]
        p01 = self._P[0, 1]
        p10 = self._P[1, 0]
        p11 = self._P[1, 1]
        self._P[0, 0] = p00 - K0 * p00
        self._P[0, 1] = p01 - K0 * p01
        self._P[1, 0] = p10 - K1 * p00
        self._P[1, 1] = p11 - K1 * p01
        return float(self._x[0])

    def lead(self, seconds: float) -> float:
        """Return predicted position after the given seconds without advancing state."""
        return float(self._x[0] + self._x[1] * seconds)


class Tracker:
    """2D target tracker wrapping X and Y Kalman axes."""

    def __init__(self) -> None:
        self.kx = Axis()
        self.ky = Axis()

    def reset(self, x: float, y: float) -> None:
        """Hard-reset both axes."""
        self.kx.reset(x)
        self.ky.reset(y)

    def feed(self, x: float, y: float, dt: float) -> tuple[float, float]:
        """Predict + update cycle, return filtered (x, y)."""
        self.kx.predict(dt)
        self.ky.predict(dt)
        fx = self.kx.update(x)
        fy = self.ky.update(y)
        return (fx, fy)

    def predict(self, lead_seconds: float) -> tuple[float, float]:
        """Return predicted position at lead_seconds into the future."""
        return (self.kx.lead(lead_seconds), self.ky.lead(lead_seconds))
