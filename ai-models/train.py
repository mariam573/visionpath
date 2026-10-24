"""Train a VisionPath detector candidate on a versioned dataset.

Usage from ai-models/: python train.py --dataset data/visionpath.yaml --model yolo26n.pt
This experiment does not establish mobile performance or application support.
"""
import argparse
from loguru import logger
from ultralytics import YOLO


def parse_args():
    parser = argparse.ArgumentParser(description="Train a VisionPath detector candidate")
    parser.add_argument("--dataset", default="data/visionpath.yaml")
    parser.add_argument(
        "--model", default="yolo26n.pt",
        help="Pretrained detector checkpoint, such as yolo26n.pt or yolo26s.pt",
    )
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default="0", help="CUDA device id or 'cpu'")
    parser.add_argument("--project", default="runs/train")
    parser.add_argument("--name", default="visionpath_candidate")
    return parser.parse_args()


def train(args):
    logger.info(f"Training candidate {args.model} on {args.dataset}")
    model = YOLO(args.model)
    return model.train(
        data=args.dataset,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=args.project,
        name=args.name,
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
        pretrained=True,
        workers=8,
        cache=False,
        amp=True,
        verbose=True,
    )


if __name__ == "__main__":
    train(parse_args())
