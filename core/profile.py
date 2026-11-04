"""Aim profiles: built-in presets and user profiles in profiles/ directory."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

_PROFILES_DIR = Path("profiles")

BUILTINS: Dict[str, Dict] = {
    "naturale": {
        "human": True,
        "reaction_ms": 190,
        "reaction_var": 55,
        "omega": 26.0,
        "zeta": 0.62,
        "overshoot": 0.18,
        "tremor": 0.55,
        "tremor_hz": 7.5,
        "fatigue": True,
        "fatigue_rate": 0.006,
        "miss_rate": 0.12,
        "miss_deg": 0.9,
        "sticky_gain": 0.45,
        "sticky_radius": 55,
    },
    "soft": {
        "human": True,
        "reaction_ms": 230,
        "reaction_var": 70,
        "omega": 18.0,
        "zeta": 0.75,
        "overshoot": 0.08,
        "tremor": 0.7,
        "tremor_hz": 6.0,
        "fatigue": True,
        "fatigue_rate": 0.008,
        "miss_rate": 0.18,
        "miss_deg": 1.2,
        "sticky_gain": 0.55,
        "sticky_radius": 65,
    },
    "aggressivo": {
        "human": True,
        "reaction_ms": 130,
        "reaction_var": 35,
        "omega": 38.0,
        "zeta": 0.48,
        "overshoot": 0.30,
        "tremor": 0.3,
        "tremor_hz": 9.0,
        "fatigue": True,
        "fatigue_rate": 0.004,
        "miss_rate": 0.06,
        "miss_deg": 0.5,
        "sticky_gain": 0.30,
        "sticky_radius": 40,
    },
    "rage": {
        "human": False,
        "reaction_ms": 10,
        "reaction_var": 5,
        "omega": 60.0,
        "zeta": 0.35,
        "overshoot": 0.05,
        "tremor": 0.0,
        "tremor_hz": 0.0,
        "fatigue": False,
        "fatigue_rate": 0.0,
        "miss_rate": 0.0,
        "miss_deg": 0.0,
        "sticky_gain": 0.0,
        "sticky_radius": 0,
    },
}


def ensure() -> None:
    """Create the profiles directory if it does not exist."""
    _PROFILES_DIR.mkdir(exist_ok=True)


def names() -> List[str]:
    """Return sorted list of all profile names (builtins + user files)."""
    ensure()
    user_profiles = [
        p.stem for p in _PROFILES_DIR.glob("*.json") if p.stem not in BUILTINS
    ]
    return sorted(set(list(BUILTINS.keys()) + user_profiles))


def load(name: str) -> Dict:
    """Load a profile by name. Builtins take priority, then files."""
    if name in BUILTINS:
        return dict(BUILTINS[name])
    ensure()
    path = _PROFILES_DIR / f"{name}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.exception("Failed to load profile %s", name)
    return {}


def save(name: str, data: Dict) -> None:
    """Save a user profile to disk. Cannot overwrite builtins."""
    if name in BUILTINS:
        logger.warning("Cannot overwrite builtin profile %s", name)
        return
    ensure()
    path = _PROFILES_DIR / f"{name}.json"
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        logger.exception("Failed to save profile %s", name)
