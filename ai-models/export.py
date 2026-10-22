"""
VisionPath — YOLOv8 Export Script
Exports a trained model to ONNX and TFLite (INT8) for mobile deployment.

Usage:
    python export.py --weights runs/train/visionpath_v1/weights/best.pt
"""
import argparse
from pathlib import Path
from loguru import logger
from ultralytics import YOLO


def parse_args():
    parser = argparse.ArgumentParser(description="Export YOLOv8 to mobile formats")
    parser.add_argument("--weights", type=str, required=True,
                        help="Path to trained .pt weights file")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--formats", nargs="+",
                        default=["onnx", "tflite"],
                        choices=["onnx", "tflite", "coreml", "torchscript"],
                        help="Export formats")
    parser.add_argument("--int8", action="store_true", default=True,
                        help="INT8 quantization for mobile (reduces size ~4x)")
    parser.add_argument("--half", action="store_true", default=False,
                        help="FP16 half precision")
    return parser.parse_args()


def export(args):
    model = YOLO(args.weights)
    weights_path = Path(args.weights)
    export_dir = weights_path.parent.parent / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    for fmt in args.formats:
        logger.info(f"Exporting to {fmt.upper()} (int8={args.int8})...")
        try:
            exported = model.export(
                format=fmt,
                imgsz=args.imgsz,
                int8=args.int8 if fmt == "tflite" else False,
                half=args.half,
                dynamic=False,
                simplify=True,  # ONNX simplification
            )
            logger.success(f"Exported {fmt.upper()} → {exported}")
        except Exception as e:
            logger.error(f"Export to {fmt} failed: {e}")


if __name__ == "__main__":
    args = parse_args()
    export(args)
