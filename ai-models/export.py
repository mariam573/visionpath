"""Export a trained candidate for evaluation in the proposed native runtime.

Export success does not prove runtime compatibility, accelerator use, or a
quantization speed/size gain. Validate output parity on a held-out set and on
the target Android development build before packaging a release artifact.
"""
import argparse
from pathlib import Path
import yaml
from ultralytics import YOLO


VISIONPATH_CLASSES = [
    "person", "chair", "table", "door", "cell_phone", "keys_keyring", "backpack"
]


def parse_args():
    parser = argparse.ArgumentParser(description="Export a VisionPath model candidate")
    parser.add_argument("--weights", type=Path, required=True, help="Trained checkpoint")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument(
        "--formats", nargs="+", default=["litert"],
        choices=["onnx", "litert", "coreml", "torchscript"],
    )
    parser.add_argument(
        "--quantize",
        choices=["8", "w8a16", "w8a32"],
        help="LiteRT quantization candidate; benchmark against FP32 before selection.",
    )
    parser.add_argument(
        "--data", type=Path,
        help="Calibration-only YAML containing development splits and no test key (required for 8/w8a16).",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.weights.is_file():
        raise FileNotFoundError(f"Weights not found: {args.weights}")
    if args.quantize in {"8", "w8a16"} and args.data is None:
        raise ValueError("Static quantization requires --data from a development split; never calibrate on the locked test set")
    if args.quantize in {"8", "w8a16"}:
        calibration = yaml.safe_load(args.data.read_text(encoding="utf-8"))
        if not isinstance(calibration, dict) or "train" not in calibration or "test" in calibration:
            raise ValueError("Calibration YAML must contain a development train split and omit the locked test key")
    if args.quantize and "litert" not in args.formats:
        raise ValueError("--quantize is supported here only for the LiteRT comparison export")

    model = YOLO(str(args.weights))
    names = model.names
    class_names = [names[index] for index in range(len(names))] if isinstance(names, dict) else list(names)
    if "litert" in args.formats and class_names != VISIONPATH_CLASSES:
        raise ValueError(
            "Mobile LiteRT export requires the exact VisionPath class order: "
            + ", ".join(VISIONPATH_CLASSES)
            + f". Checkpoint has: {class_names}"
        )

    for fmt in args.formats:
        options = {"format": fmt, "imgsz": args.imgsz, "dynamic": False}
        if fmt == "litert":
            if args.imgsz != 640:
                raise ValueError("The mobile runtime contract is pinned to 640x640 input")
        if fmt == "litert" and args.quantize:
            options["quantize"] = int(args.quantize) if args.quantize == "8" else args.quantize
        if fmt == "litert" and args.quantize in {"8", "w8a16"}:
            options["data"] = str(args.data)
        artifact = model.export(**options)
        print(f"Exported {fmt}: {artifact}")


if __name__ == "__main__":
    main()
