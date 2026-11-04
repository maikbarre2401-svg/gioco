"""Auto-annotate a frames folder into YOLO format using a COCO person model."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
from ultralytics import YOLO


def annotate_folder(
    frames_dir: str,
    output_dir: str,
    model_path: str = "yolov8n.pt",
    conf: float = 0.35,
    imgsz: int = 640,
) -> None:
    """Run detection on all images in frames_dir, write YOLO txt labels to output_dir."""
    frames = Path(frames_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    model = YOLO(model_path)
    extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    images = sorted(p for p in frames.iterdir() if p.suffix.lower() in extensions)

    if not images:
        print(f"No images found in {frames_dir}")
        return

    print(f"Processing {len(images)} images...")
    total_dets = 0

    for img_path in images:
        frame = cv2.imread(str(img_path))
        if frame is None:
            print(f"  Skipping {img_path.name}: unreadable")
            continue

        h, w = frame.shape[:2]
        results = model.predict(
            frame, imgsz=imgsz, conf=conf, verbose=False, classes=[0]
        )

        label_path = out / (img_path.stem + ".txt")
        lines: list[str] = []

        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                cls_id = int(box.cls[0])
                if cls_id != 0:
                    continue
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().tolist()
                cx = ((x1 + x2) / 2.0) / w
                cy = ((y1 + y2) / 2.0) / h
                bw = (x2 - x1) / w
                bh = (y2 - y1) / h
                lines.append(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
                total_dets += 1

        label_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"Done: {total_dets} detections across {len(images)} images")
    print(f"Labels saved to {out}")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Auto-annotate frames to YOLO format")
    parser.add_argument("frames_dir", help="Directory containing frame images")
    parser.add_argument("--output", "-o", default="labels", help="Output label directory")
    parser.add_argument("--model", default="yolov8n.pt", help="YOLO model for detection")
    parser.add_argument("--conf", type=float, default=0.35, help="Confidence threshold")
    parser.add_argument("--imgsz", type=int, default=640, help="Inference image size")
    args = parser.parse_args()

    annotate_folder(args.frames_dir, args.output, args.model, args.conf, args.imgsz)


if __name__ == "__main__":
    main()
