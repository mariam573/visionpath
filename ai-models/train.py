"""
VisionPath — YOLOv8 Training Script

Usage:
    python train.py --dataset data/visionpath.yaml --model yolov8n --epochs 100

This script fine-tunes YOLOv8 on the VisionPath custom dataset which includes
COCO base objects + custom indoor navigation objects (doors, handles, signs, etc.)
"""
import argparse
from pathlib import Path
from loguru import logger
from ultralytics import YOLO


def parse_args():
    parser = argparse.ArgumentParser(description="Train YOLOv8 for VisionPath")
    parser.add_argument("--dataset", type=str, default="data/visionpath.yaml",
                        help="Path to dataset YAML file")
    parser.add_argument("--model", type=str, default="yolov8n",
                        choices=["yolov8n", "yolov8s", "yolov8m"],
                        help="YOLOv8 model size")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", type=str, default="0",
                        help="CUDA device id or 'cpu'")
    parser.add_argument("--project", type=str, default="runs/train")
    parser.add_argument("--name", type=str, default="visionpath_v1")
    return parser.parse_args()


def train(args):
    logger.info(f"Starting VisionPath YOLOv8 training with model: {args.model}")

    # Load pretrained weights from COCO
    model = YOLO(f"{args.model}.pt")

    results = model.train(
        data=args.dataset,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=args.project,
        name=args.name,
        # Augmentation settings
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        degrees=0.0,
        translate=0.1,
        scale=0.5,
        flipud=0.0,
        fliplr=0.5,
        mosaic=1.0,
        mixup=0.0,
        # Pretrained COCO weights — transfer learning
        pretrained=True,
        # Performance
        workers=8,
        cache=True,
        amp=True,  # Automatic Mixed Precision
        verbose=True,
    )
    logger.info(f"Training complete. Results: {results}")
    return results


if __name__ == "__main__":
    args = parse_args()
    train(args)
