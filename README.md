# Aim Assist

Vision-based mouse aim assist for first-person shooters on Windows. Uses YOLO
detection and pose estimation with humanised aim math and a transparent overlay.

## Requirements

- Windows 10/11
- Python 3.11
- NVIDIA GPU with CUDA support (recommended)
- Game running in **borderless windowed 1920x1080**

## Installation

```bash
install.bat
```

Or manually:

```bash
pip install -r requirements.txt
```

## Usage

```bash
run.bat
```

Or:

```bash
python aimbot_gui.py
```

The application will request UAC elevation on startup (required for SendInput).

## Calibration

Calculate your `counts_per_deg` value:

```bash
python tools/calibrate.py <distance_cm> <dpi> --save
```

Measure the distance in cm your mouse travels for a full 360-degree turn
in-game, then pass that along with your mouse DPI.

## Hotkeys

| Key | Action |
|-----|--------|
| Mouse X2 (default) | Hold to aim (or toggle in toggle mode) |
| F8 | Toggle aim enable |
| F9 | Toggle triggerbot |
| F10 | Quit application |

The aim button can be changed via `hold_button` in cfg.json (`x1`, `x2`, `middle`).

## File Map

```
cfg.json              Main configuration (auto-created on first run)
core/
  config.py           Config dataclass with JSON persistence
  utils.py            Windows system utilities (DPI, foreground process)
  capture.py          Screen capture (dxcam + mss fallback)
  vision.py           YOLO detection and pose estimation
  skeleton.py         COCO-17 skeleton bones, named points, drawing
  kalman.py           Constant-velocity Kalman filter for tracking
  human.py            Humanised aim: reaction, spring, tremor, fatigue
  metrics.py          Rolling metrics with CSV logging
  profile.py          Aim profiles (builtin + user)
  aim.py              Target picking, Kalman tracking, aim step
  output.py           Win32 SendInput mouse + optional Arduino serial
  overlay.py          Transparent click-through overlay window
  engine.py           Main engine thread (capture -> detect -> aim loop)
aimbot_gui.py         Tkinter dark control panel with live preview
tools/
  calibrate.py        counts_per_deg calculator
  bench.py            Detection latency benchmark
  label.py            Auto-annotate frames to YOLO format
  train.py            Fine-tune YOLOv8n on custom data
profiles/             User-saved aim profiles
logs/                 Metrics CSV output
```

## Tuning Table

| Parameter | Default | Description |
|-----------|---------|-------------|
| `conf` | 0.35 | Detection confidence threshold |
| `fov_px` | 300 | Max pixel radius from crosshair to consider targets |
| `max_step` | 140 | Maximum mouse counts per tick |
| `tick_hz` | 250 | Engine loop frequency |
| `deadzone` | 0.9 | Pixel radius where aim stops adjusting |
| `counts_per_deg` | 1200 | Mouse counts per degree (calibrate!) |
| `hfov_deg` | 80 | Game horizontal field of view |
| `omega` | 26.0 | Spring natural frequency (higher = faster snap) |
| `zeta` | 0.62 | Spring damping ratio (< 1 = overshoot) |
| `reaction_ms` | 190 | Mean reaction delay on new targets |
| `tremor` | 0.55 | Aim tremor amplitude |
| `miss_rate` | 0.12 | Probability of a deliberate near-miss |
| `sticky_radius` | 55 | Pixel radius for aim slowdown near target |
| `sticky_gain` | 0.45 | Aim speed multiplier inside sticky radius |
| `lead_ms` | 55 | Kalman prediction lead time |
| `trigger_radius` | 12 | Pixel radius for auto-fire |
| `trigger_delay_ms` | 40 | Mean trigger delay |

## Built-in Profiles

- **naturale** - Balanced human-like aim
- **soft** - Slow, high tremor, more misses
- **aggressivo** - Fast snap, low tremor
- **rage** - No humanisation (not recommended)

## Benchmark

```bash
python tools/bench.py
```

Measures detection latency over 50 frames and reports mean, median, p95, and
effective FPS.

## Training Custom Models

1. Collect game frames
2. Auto-label with: `python tools/label.py frames/ -o labels/`
3. Create a YOLO dataset YAML
4. Train: `python tools/train.py dataset.yaml --epochs 50`
5. Update `det_model` in cfg.json to the new weights path
