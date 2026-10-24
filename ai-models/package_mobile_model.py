"""Bundle a model only after its Android selection evidence is approved."""
import argparse
import hashlib
import json
import math
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL_DESTINATION = ROOT / "mobile" / "assets" / "models" / "visionpath.tflite"
MODEL_MODULE = ROOT / "mobile" / "src" / "vision" / "modelAsset.ts"
CLASSES = ["person", "chair", "table", "door", "cell_phone", "keys_keyring", "backpack"]
EXPECTED_CANDIDATES = {"yolov8n", "yolo26n", "yolo26s", "yoloe26n"}
MEASURED_CANDIDATES_REQUIRED = {"yolov8n", "yolo26n"}
INPUT_CONTRACT = "float32-nhwc-rgb-640"
OUTPUT_CONTRACT = "yolo26-e2e-xyxy-score-classid"
REQUIRED_EVIDENCE = {
    "dataset_manifest", "dataset_source_register", "training_configuration", "license_review", "model_comparison", "device_performance",
    "runtime_compatibility", "export_parity", "precision_comparison", "dependency_locks", "rollback",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value.lower()):
        raise ValueError(f"{label} must be a 64-character SHA-256 checksum")
    return value.lower()


def require_number(value: object, label: str, *, minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    number = float(value)
    if minimum is not None and number < minimum:
        raise ValueError(f"{label} must be at least {minimum}")
    if maximum is not None and number > maximum:
        raise ValueError(f"{label} must be at most {maximum}")
    return number


def verify_evidence(entry: object, label: str) -> None:
    if not isinstance(entry, dict):
        raise ValueError(f"{label} must include an evidence object with path and sha256")
    relative = entry.get("path")
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError(f"{label} evidence path is required")
    evidence_path = (ROOT / relative).resolve()
    if not evidence_path.is_relative_to(ROOT.resolve()) or not evidence_path.is_file():
        raise ValueError(f"{label} evidence must be an existing file inside the repository: {relative}")
    expected = require_sha256(entry.get("sha256"), f"{label} evidence sha256")
    if sha256_file(evidence_path) != expected:
        raise ValueError(f"{label} evidence checksum does not match: {relative}")


def validate_report(report: object, model_path: Path) -> dict:
    if not isinstance(report, dict) or report.get("schema_version") != 2:
        raise ValueError("Validation report must use schema_version 2")
    if report.get("report_status") != "approved":
        raise ValueError("Report is not approved; benchmark evidence is incomplete or pending")

    classes = report.get("dataset", {}).get("class_names") if isinstance(report.get("dataset"), dict) else None
    if classes != CLASSES:
        raise ValueError(f"dataset.class_names must match the mobile class order: {CLASSES}")
    dataset = report["dataset"]
    if not isinstance(dataset.get("version"), str) or not dataset["version"].strip():
        raise ValueError("dataset.version is required")
    manifest_sha = require_sha256(dataset.get("manifest_sha256"), "dataset.manifest_sha256")
    if dataset.get("grouped_splits_verified") is not True or dataset.get("final_test_split_locked") is not True:
        raise ValueError("Grouped dataset splits and a locked final test split must be verified")
    verify_evidence({"path": dataset.get("manifest_path"), "sha256": manifest_sha}, "dataset manifest")
    source_sha = require_sha256(dataset.get("source_register_sha256"), "dataset.source_register_sha256")
    verify_evidence({"path": dataset.get("source_register_path"), "sha256": source_sha}, "dataset source/license register")
    data_license = dataset.get("license_review")
    if not isinstance(data_license, dict) or data_license.get("status") != "approved" or data_license.get("training_use_allowed") is not True or data_license.get("model_distribution_allowed") is not True:
        raise ValueError("Dataset and source licenses must approve both training use and distribution of the trained model")
    for field in ("reviewer", "reviewed_at"):
        if not isinstance(data_license.get(field), str) or not data_license[field].strip():
            raise ValueError(f"dataset.license_review.{field} is required")
    verify_evidence(data_license.get("evidence"), "dataset license review")

    primary_device_id = report.get("primary_device_id")
    if not isinstance(primary_device_id, str) or not primary_device_id.strip():
        raise ValueError("primary_device_id must identify the measured Android reference device")

    candidates = report.get("candidate_results")
    if not isinstance(candidates, list):
        raise ValueError("candidate_results must list the complete model shortlist")
    by_id = {item.get("candidate_id"): item for item in candidates if isinstance(item, dict)}
    if len(by_id) != len(candidates) or set(by_id) != EXPECTED_CANDIDATES:
        raise ValueError(f"candidate_results must contain exactly: {sorted(EXPECTED_CANDIDATES)}")
    measured_ids = set()
    for candidate_id, candidate in by_id.items():
        status = candidate.get("status")
        if status not in {"measured", "excluded"}:
            raise ValueError(f"{candidate_id} must be measured or have a documented exclusion")
        license_review = candidate.get("license_review")
        if not isinstance(license_review, dict) or license_review.get("status") not in {"approved", "rejected", "restricted"}:
            raise ValueError(f"{candidate_id} needs a completed license review")
        for field in ("name", "source_url", "reviewer", "reviewed_at"):
            if not isinstance(license_review.get(field), str) or not license_review[field].strip():
                raise ValueError(f"{candidate_id} license_review.{field} is required")
        if not isinstance(license_review.get("redistribution_allowed"), bool):
            raise ValueError(f"{candidate_id} license redistribution decision must be explicit")
        verify_evidence(license_review.get("evidence"), f"{candidate_id} license review")
        if status == "excluded":
            if not isinstance(candidate.get("exclusion_reason"), str) or not candidate["exclusion_reason"].strip():
                raise ValueError(f"{candidate_id} needs a documented exclusion reason")
            continue
        measured_ids.add(candidate_id)
        if license_review.get("status") != "approved":
            raise ValueError(f"{candidate_id} cannot be benchmarked for this selection unless its use is approved")
        require_sha256(candidate.get("checkpoint_sha256"), f"{candidate_id} checkpoint_sha256")
        compatibility = candidate.get("runtime_compatibility")
        if not isinstance(compatibility, dict) or compatibility.get("status") != "passed":
            raise ValueError(f"{candidate_id} has not passed native runtime compatibility")
        for field in ("runtime", "requested_delegate", "observed_delegate"):
            if not isinstance(compatibility.get(field), str) or not compatibility[field].strip():
                raise ValueError(f"{candidate_id} runtime_compatibility.{field} is required")
        if compatibility.get("cpu_fallback_verified") is not True:
            raise ValueError(f"{candidate_id} must verify the on-device CPU fallback")
        metrics = candidate.get("per_class_metrics")
        if not isinstance(metrics, dict) or set(metrics) != set(CLASSES):
            raise ValueError(f"{candidate_id} needs per-class metrics for every VisionPath class")
        for class_name, values in metrics.items():
            if not isinstance(values, dict):
                raise ValueError(f"{candidate_id}.{class_name} metrics must include precision and recall")
            require_number(values.get("precision"), f"{candidate_id}.{class_name}.precision", minimum=0, maximum=1)
            require_number(values.get("recall"), f"{candidate_id}.{class_name}.recall", minimum=0, maximum=1)
        key_finding = candidate.get("key_finding")
        if not isinstance(key_finding, dict):
            raise ValueError(f"{candidate_id} key_finding success/time and false announcements are required")
        require_number(key_finding.get("success_rate"), f"{candidate_id}.key_finding.success_rate", minimum=0, maximum=1)
        require_number(key_finding.get("median_time_seconds"), f"{candidate_id}.key_finding.median_time_seconds", minimum=0)
        require_number(key_finding.get("absent_target_false_announcement_rate"), f"{candidate_id}.key_finding.absent_target_false_announcement_rate", minimum=0, maximum=1)
        runs = candidate.get("device_runs")
        matching_runs = [run for run in runs if isinstance(run, dict) and run.get("device_id") == primary_device_id] if isinstance(runs, list) else []
        if not matching_runs:
            raise ValueError(f"{candidate_id} has no measurement on primary_device_id {primary_device_id}")
        for run in matching_runs:
            if run.get("sample_count", 0) < 100 or run.get("repetitions", 0) < 3 or run.get("sustained_minutes", 0) < 30:
                raise ValueError(f"{candidate_id} primary-device run requires >=100 samples, >=3 runs, and >=30 sustained minutes")
            for field in ("device_model", "soc", "android_version", "build_fingerprint", "runtime_version", "delegate_observed"):
                if not isinstance(run.get(field), str) or not run[field].strip():
                    raise ValueError(f"{candidate_id} device run is missing {field}")
            for field in ("capture_to_feedback_p50_ms", "capture_to_feedback_p95_ms", "inference_p95_ms", "peak_memory_mb", "battery_delta_percent", "temperature_start_c", "temperature_peak_c", "temperature_end_c", "throttling_events"):
                require_number(run.get(field), f"{candidate_id}.device_run.{field}", minimum=0)
            if run["capture_to_feedback_p95_ms"] < run["capture_to_feedback_p50_ms"]:
                raise ValueError(f"{candidate_id} capture-to-feedback p95 cannot be below p50")
    if not MEASURED_CANDIDATES_REQUIRED.issubset(measured_ids):
        raise ValueError("At least YOLOv8n baseline and YOLO26n must be measured on the same primary device")

    decision = report.get("decision")
    config = report.get("selected_configuration")
    if not isinstance(decision, dict) or decision.get("status") != "approved":
        raise ValueError("A reviewer-approved model-selection decision is required")
    if not isinstance(config, dict) or config.get("candidate_id") != decision.get("selected_candidate"):
        raise ValueError("selected_configuration must match the approved selected_candidate")
    selected = by_id.get(decision.get("selected_candidate"))
    if not isinstance(selected, dict) or selected.get("status") != "measured":
        raise ValueError("Selected candidate must have a completed measurement")
    if selected["license_review"].get("status") != "approved" or selected["license_review"].get("redistribution_allowed") is not True:
        raise ValueError("Selected model license must explicitly permit redistribution")
    for field in ("reviewer", "reviewed_at", "rationale"):
        if not isinstance(decision.get(field), str) or not decision[field].strip():
            raise ValueError(f"decision.{field} is required")
    version = config.get("model_version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("selected_configuration.model_version is required")
    if config.get("input_contract") != INPUT_CONTRACT or config.get("output_contract") != OUTPUT_CONTRACT:
        raise ValueError("Chosen model tensor contracts do not match the app decoder; update and revalidate the app first")
    if config.get("class_names") != CLASSES:
        raise ValueError("selected_configuration.class_names must match the app's class order")
    input_tensor = config.get("input_tensor")
    if not isinstance(input_tensor, dict) or input_tensor.get("dtype") != "float32" or input_tensor.get("shape") != [1, 640, 640, 3] or not isinstance(input_tensor.get("name"), str) or not input_tensor["name"].strip():
        raise ValueError("selected_configuration.input_tensor must record the exact float32 [1,640,640,3] tensor")
    preprocessing = config.get("preprocessing")
    if not isinstance(preprocessing, dict) or preprocessing.get("pixel_order") != "RGB" or preprocessing.get("tensor_layout") != "NHWC" or preprocessing.get("resize_mode") != "cover":
        raise ValueError("selected preprocessing must match RGB/NHWC/cover app behavior")
    if not isinstance(preprocessing.get("normalization"), str) or not preprocessing["normalization"].strip():
        raise ValueError("Record the measured tensor normalization in selected_configuration.preprocessing")
    require_number(preprocessing.get("input_min"), "selected_configuration.preprocessing.input_min")
    require_number(preprocessing.get("input_max"), "selected_configuration.preprocessing.input_max")
    if preprocessing["input_max"] <= preprocessing["input_min"]:
        raise ValueError("preprocessing.input_max must exceed input_min")
    output_tensor = config.get("output_tensor")
    if not isinstance(output_tensor, dict) or output_tensor.get("dtype") != "float32" or not isinstance(output_tensor.get("name"), str) or not output_tensor["name"].strip():
        raise ValueError("selected_configuration.output_tensor must record the exact float32 output tensor")
    output_shape = output_tensor.get("shape")
    if not isinstance(output_shape, list) or len(output_shape) != 3 or output_shape[0] != 1 or not isinstance(output_shape[1], int) or output_shape[1] <= 0 or output_shape[2] != 6:
        raise ValueError("selected output tensor must match [1,N,6]")
    if config.get("precision") not in {"float32", "w8a32"}:
        raise ValueError("The app input path currently supports float32 and float-input w8a32 configurations only")
    confidence = require_number(config.get("confidence_threshold"), "selected_configuration.confidence_threshold", minimum=0, maximum=1)
    iou = require_number(config.get("iou_threshold"), "selected_configuration.iou_threshold", minimum=0, maximum=1)
    decoder = (ROOT / "mobile" / "src" / "vision" / "yolo26.ts").read_text(encoding="utf-8")
    if not re.search(rf"const CONFIDENCE_THRESHOLD = {re.escape(str(confidence))};", decoder):
        raise ValueError("selected confidence threshold differs from the decoder; update and revalidate the app first")
    if not re.search(rf"const IOU_THRESHOLD = {re.escape(str(iou))};", decoder):
        raise ValueError("selected IoU threshold differs from the decoder; update and revalidate the app first")
    artifact_sha = require_sha256(config.get("artifact_sha256"), "selected_configuration.artifact_sha256")
    if sha256_file(model_path) != artifact_sha:
        raise ValueError("Exported .tflite checksum does not match selected_configuration.artifact_sha256")
    if selected["license_review"].get("status") != "approved":
        raise ValueError("Selected model did not pass the license review")

    parity = report.get("export_parity")
    if not isinstance(parity, dict) or parity.get("status") != "passed" or parity.get("sample_count", 0) < 100:
        raise ValueError("Export parity must pass on at least 100 validation samples")
    if parity.get("validation_manifest_sha256") != manifest_sha:
        raise ValueError("Export parity must cite the versioned development/validation data manifest")
    for field in ("preprocessing_verified", "rotation_crop_verified", "tensor_layout_verified", "postprocessing_verified", "coordinate_mapping_verified"):
        if parity.get(field) is not True:
            raise ValueError(f"export_parity.{field} must pass")
    if require_number(parity.get("mean_box_iou"), "export_parity.mean_box_iou", minimum=0, maximum=1) < require_number(parity.get("minimum_mean_box_iou"), "export_parity.minimum_mean_box_iou", minimum=0, maximum=1):
        raise ValueError("Export mean box IoU is below its predeclared threshold")
    if require_number(parity.get("class_match_rate"), "export_parity.class_match_rate", minimum=0, maximum=1) < require_number(parity.get("minimum_class_match_rate"), "export_parity.minimum_class_match_rate", minimum=0, maximum=1):
        raise ValueError("Export class match rate is below its predeclared threshold")
    if require_number(parity.get("maximum_confidence_error"), "export_parity.maximum_confidence_error", minimum=0) > require_number(parity.get("maximum_allowed_confidence_error"), "export_parity.maximum_allowed_confidence_error", minimum=0):
        raise ValueError("Export confidence error exceeds its predeclared threshold")
    verify_evidence(parity.get("evidence"), "export parity")

    precision = report.get("precision_comparison")
    if not isinstance(precision, dict) or precision.get("status") != "completed":
        raise ValueError("Float32 versus quantized comparison must be completed, including a documented unsupported result")
    require_sha256(precision.get("float32_artifact_sha256"), "precision_comparison.float32_artifact_sha256")
    if precision.get("same_device_and_workload") is not True or precision.get("quality_delta_reported") is not True or precision.get("latency_memory_thermal_battery_delta_reported") is not True:
        raise ValueError("Precision comparison must report quality and device resource deltas under the same workload")
    if not isinstance(precision.get("decision_rationale"), str) or not precision["decision_rationale"].strip():
        raise ValueError("precision_comparison.decision_rationale is required")
    quantized_sha = precision.get("quantized_artifact_sha256")
    if quantized_sha is not None:
        require_sha256(quantized_sha, "precision_comparison.quantized_artifact_sha256")
        if not isinstance(precision.get("quantized_variant"), str) or not precision["quantized_variant"].strip():
            raise ValueError("precision_comparison.quantized_variant is required")
        deltas = precision.get("measured_deltas")
        if not isinstance(deltas, dict):
            raise ValueError("Quantization comparison must report numeric quality, latency, memory, battery and thermal deltas")
        for field in ("map50_95_delta", "key_success_rate_delta", "capture_to_feedback_p95_ms_delta", "peak_memory_mb_delta", "battery_delta_percent", "temperature_peak_c_delta"):
            require_number(deltas.get(field), f"precision_comparison.measured_deltas.{field}")
        if not isinstance(deltas.get("observed_delegate"), str) or not deltas["observed_delegate"].strip():
            raise ValueError("precision_comparison.measured_deltas.observed_delegate is required")
    elif not isinstance(precision.get("unsupported_reason"), str) or not precision["unsupported_reason"].strip():
        raise ValueError("If no quantized artifact was produced, document why quantization is unsupported")
    if config.get("precision") == "float32" and artifact_sha != precision["float32_artifact_sha256"].lower():
        raise ValueError("Selected float32 artifact checksum differs from precision_comparison.float32_artifact_sha256")
    if config.get("precision") == "w8a32":
        if quantized_sha is None or artifact_sha != quantized_sha.lower() or precision.get("quantized_input_contract_compatible") is not True:
            raise ValueError("Selected w8a32 artifact needs matching checksum and verified float-input compatibility")
    verify_evidence(precision.get("evidence"), "precision comparison")

    locks = report.get("dependency_locks")
    if not isinstance(locks, dict):
        raise ValueError("Exact dependency lock metadata is required")
    for lock_name in ("training_lock", "mobile_lock"):
        lock = locks.get(lock_name)
        if not isinstance(lock, dict) or not isinstance(lock.get("path"), str):
            raise ValueError(f"dependency_locks.{lock_name} path is required")
        expected_path = "ai-models/requirements.txt" if lock_name == "training_lock" else "mobile/pnpm-lock.yaml"
        if lock["path"] != expected_path:
            raise ValueError(f"dependency_locks.{lock_name}.path must be {expected_path}")
        lock_path = (ROOT / lock["path"]).resolve()
        if not lock_path.is_relative_to(ROOT.resolve()) or not lock_path.is_file():
            raise ValueError(f"{lock_name} must point to a checked-in lock file")
        if sha256_file(lock_path) != require_sha256(lock.get("sha256"), f"{lock_name}.sha256"):
            raise ValueError(f"{lock_name} checksum does not match the checked-in lock")
    mobile_manifest = ROOT / "mobile" / "package.json"
    if sha256_file(mobile_manifest) != require_sha256(locks.get("mobile_manifest_sha256"), "dependency_locks.mobile_manifest_sha256"):
        raise ValueError("mobile/package.json checksum does not match the report")
    mobile_dependencies = json.loads(mobile_manifest.read_text(encoding="utf-8"))["dependencies"]
    training_lock_text = (ROOT / locks["training_lock"]["path"]).read_text(encoding="utf-8")
    expected_exporter = f"ultralytics=={locks.get('exporter_version')}"
    if expected_exporter not in training_lock_text.splitlines():
        raise ValueError("The reported exporter version is not pinned in ai-models/requirements.txt")
    if locks.get("runtime_package") != "react-native-fast-tflite" or locks.get("runtime_version") != config.get("runtime_version"):
        raise ValueError("Exact selected native runtime package/version must match the chosen configuration")
    if mobile_dependencies.get("react-native-fast-tflite") != locks.get("runtime_version"):
        raise ValueError("Selected runtime version differs from the pinned mobile manifest")
    for field in ("exporter_version", "native_interpreter_version"):
        if not isinstance(locks.get(field), str) or not locks[field].strip():
            raise ValueError(f"dependency_locks.{field} is required")
    if locks["native_interpreter_version"] != config.get("native_interpreter_version"):
        raise ValueError("Native interpreter version differs from selected_configuration")

    evidence = report.get("evidence")
    if not isinstance(evidence, list):
        raise ValueError("evidence must list checked raw records for every release gate")
    categories = set()
    for item in evidence:
        if not isinstance(item, dict) or not isinstance(item.get("category"), str):
            raise ValueError("Every evidence item needs a category, path, and sha256")
        categories.add(item["category"])
        verify_evidence(item, f"{item['category']} evidence")
    if REQUIRED_EVIDENCE - categories:
        raise ValueError("Missing evidence categories: " + ", ".join(sorted(REQUIRED_EVIDENCE - categories)))

    rollback = report.get("rollback")
    if not isinstance(rollback, dict) or rollback.get("tested") is not True or not isinstance(rollback.get("predecessor"), str) or not rollback["predecessor"].strip() or not isinstance(rollback.get("procedure"), str) or not rollback["procedure"].strip():
        raise ValueError("A tested rollback predecessor and procedure are required")
    verify_evidence(rollback.get("evidence"), "rollback")
    return {"version": version, "artifact_sha256": artifact_sha}


def main():
    parser = argparse.ArgumentParser(description="Package a plan-validated mobile model")
    parser.add_argument("--model", type=Path, required=True, help="Exported .tflite candidate")
    parser.add_argument("--validation-report", type=Path, required=True, help="Completed JSON validation report")
    args = parser.parse_args()

    if not args.model.is_file() or args.model.suffix.lower() != ".tflite":
        raise FileNotFoundError("--model must point to an exported .tflite file")
    report = json.loads(args.validation_report.read_text(encoding="utf-8"))
    validated = validate_report(report, args.model.resolve())
    version = validated["version"]
    if MODEL_DESTINATION.exists():
        raise FileExistsError(f"Refusing to replace an existing bundled model: {MODEL_DESTINATION}")

    source = MODEL_MODULE.read_text(encoding="utf-8")
    marker = "export const visionPathModelAsset: number | null = null;"
    if marker not in source or "version: 'not-installed'" not in source:
        raise ValueError("Mobile model module is not in its expected unbundled state; inspect it before packaging")
    source = source.replace(
        marker,
        "// Bundled only by package_mobile_model.py after validation approval.\n"
        "export const visionPathModelAsset: number | null = require('../../assets/models/visionpath.tflite');",
    )
    source = source.replace("version: 'not-installed'", f"version: {json.dumps(version)}")
    temp_model = MODEL_DESTINATION.with_name(MODEL_DESTINATION.name + ".tmp")
    temp_module = MODEL_MODULE.with_name(MODEL_MODULE.name + ".tmp")
    try:
        shutil.copy2(args.model, temp_model)
        temp_module.write_text(source, encoding="utf-8")
        temp_model.replace(MODEL_DESTINATION)
        temp_module.replace(MODEL_MODULE)
    finally:
        temp_model.unlink(missing_ok=True)
        temp_module.unlink(missing_ok=True)
    print(f"Packaged validated model {version} at {MODEL_DESTINATION}")


if __name__ == "__main__":
    main()
