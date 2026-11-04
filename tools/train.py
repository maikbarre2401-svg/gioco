"""Fine-tune YOLOv8n on a custom dataset."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ultralytics import YOLO


def train(
    data_yaml: str,
    model: str = "yolov8n.pt",
    epochs: int = 50,
    imgsz: int = 640,
    batch: int = 16,
    project: str = "runs/train",
    name: str = "custom",
    device: str = "0",
) -> str:
    """Fine-tune a YOLOv8 model and return the path to best weights."""
    yolo = YOLO(model)
    results = yolo.train(
        data=data_yaml,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        project=project,
        name=name,
        device=device,
        patience=10,
        save=True,
        plots=True,
        verbose=True,
    )
    best_path = Path(project) / name / "weights" / "best.pt"
    if best_path.exists():
        print(f"\nBest weights: {best_path}")
        return str(best_path)
    print("\nTraining complete (best.pt not found at expected path)")
    return ""


def main() -> None:
    """CLI entry point for fine-tuning."""
    parser = argparse.ArgumentParser(description="Fine-tune YOLOv8n on custom data")
    parser.add_argument("data_yaml", help="Path to dataset YAML (YOLO format)")
    parser.add_argument("--model", default="yolov8n.pt", help="Base model")
    parser.add_argument("--epochs", type=int, default=50, help="Training epochs")
    parser.add_argument("--imgsz", type=int, default=640, help="Training image size")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    parser.add_argument("--device", default="0", help="CUDA device")
    parser.add_argument("--project", default="runs/train", help="Project directory")
    parser.add_argument("--name", default="custom", help="Run name")
    args = parser.parse_args()

    best = train(
        args.data_yaml,
        model=args.model,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        project=args.project,
        name=args.name,
        device=args.device,
    )
    if best:
        print(f"\nTo use in aim assist, set det_model in cfg.json to: {best}")


if __name__ == "__main__":
    main()
