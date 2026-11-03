"""Compute counts_per_deg from a measured 360-degree mouse distance and DPI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def counts_per_deg(distance_cm: float, dpi: int) -> float:
    """Calculate counts per degree from a 360-degree turn distance in cm and mouse DPI.

    Formula: (distance_cm / 2.54 * dpi) / 360
    """
    inches = distance_cm / 2.54
    total_counts = inches * dpi
    return total_counts / 360.0


def main() -> None:
    """CLI entry point for calibration."""
    parser = argparse.ArgumentParser(description="Calculate counts_per_deg for aim config")
    parser.add_argument("distance_cm", type=float, help="Distance in cm for a full 360-degree turn")
    parser.add_argument("dpi", type=int, help="Mouse DPI setting")
    parser.add_argument("--save", action="store_true", help="Write result to cfg.json")
    args = parser.parse_args()

    result = counts_per_deg(args.distance_cm, args.dpi)
    print(f"Distance: {args.distance_cm} cm")
    print(f"DPI: {args.dpi}")
    print(f"Counts per degree: {result:.2f}")

    if args.save:
        cfg_path = Path("cfg.json")
        if cfg_path.exists():
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
        else:
            data = {}
        data["counts_per_deg"] = round(result, 2)
        cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"Saved to {cfg_path}")


if __name__ == "__main__":
    main()
