"""Benchmark detection latency over 50 frames."""

from __future__ import annotations

import statistics
import sys
import time

import numpy as np


def main() -> None:
    """Run detection benchmark and print latency statistics."""
    from core.config import Config
    from core.capture import Capturer
    from core.vision import Vision

    cfg = Config.load()
    print(f"Model: {cfg.det_model}, imgsz: {cfg.imgsz}, device: {cfg.device}")

    print("Initialising capture...")
    cap = Capturer(cfg.capture)

    print("Initialising vision...")
    vis = Vision(cfg, print)

    print("Warming up (5 frames)...")
    for _ in range(5):
        frame = cap.grab()
        if frame is not None:
            vis.detect(frame)

    n_frames = 50
    latencies: list[float] = []
    det_counts: list[int] = []

    print(f"Benchmarking {n_frames} frames...")
    for i in range(n_frames):
        frame = cap.grab()
        if frame is None:
            print(f"  Frame {i}: capture failed")
            continue

        t0 = time.perf_counter()
        dets = vis.detect(frame)
        t1 = time.perf_counter()

        ms = (t1 - t0) * 1000.0
        latencies.append(ms)
        det_counts.append(len(dets))

        if (i + 1) % 10 == 0:
            print(f"  {i + 1}/{n_frames} done ({ms:.1f} ms, {len(dets)} detections)")

    cap.release()

    if not latencies:
        print("No frames captured!")
        return

    print("\n--- Results ---")
    print(f"Frames: {len(latencies)}")
    print(f"Mean latency: {statistics.mean(latencies):.2f} ms")
    print(f"Median latency: {statistics.median(latencies):.2f} ms")
    print(f"Stdev: {statistics.stdev(latencies):.2f} ms" if len(latencies) > 1 else "")
    print(f"Min: {min(latencies):.2f} ms")
    print(f"Max: {max(latencies):.2f} ms")
    print(f"P95: {sorted(latencies)[int(0.95 * len(latencies))]:.2f} ms")
    print(f"Avg detections: {statistics.mean(det_counts):.1f}")
    fps = 1000.0 / statistics.mean(latencies)
    print(f"Effective FPS: {fps:.1f}")


if __name__ == "__main__":
    main()
