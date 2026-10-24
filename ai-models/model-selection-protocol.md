# Model comparison and Android release gate

## Current decision

The repository has no versioned dataset, trained checkpoint, exported `.tflite`, reference-device benchmark, or reviewed weight/data license record. There is therefore no selected detector or validated Android runtime configuration. `YOLO26n` is a candidate, not a release decision. The application must remain in camera-preview mode until an approved report passes `package_mobile_model.py`.

The current experiment pins in `requirements.txt` make a candidate-training environment repeatable. They are not evidence that the model, exporter, native runtime, delegate, or exact Android device combination was benchmarked. Keep the selected configuration unassigned until the shared-task comparison is complete.

## Candidates and fair comparison

Evaluate the currently usable shortlist from the implementation plan:

- YOLOv8n as the compatibility baseline.
- YOLO26n as the first continuous-mobile candidate.
- YOLO26s as the accuracy candidate.
- YOLOE-26n as a broader-category experiment.

Record a measured result or a reasoned exclusion for every candidate. Review checkpoint, code, dataset, and redistribution terms before training or packaging. Do not use an excluded/research-only asset in a distributable build.

Use the same versioned, group-split dataset, seven-class label map, thresholds protocol, image sizes, reference Android phone, native build, and workload for compared candidates. Freeze the development/validation protocol before model comparison and keep the final test split locked for the final report. Include per-class precision/recall, small-object results, key-finding success/time, absent-target false announcements, and examples of unseen-building failures. Published COCO scores and desktop/GPU timings are context only, not VisionPath selection evidence.

For each candidate, record the exact checkpoint checksum, exporter/tool versions, export format and flags, output tensor metadata, artifact checksum, license review, and any conversion warnings. Compare FP32 with available quantized formats using the same data and device. Static calibration may use development data only, never the locked test split. Record actual delegate use and CPU fallback; requesting an accelerator is not proof it ran.

## Reference Android measurement protocol

Name the phone model, SoC, RAM, Android/API/build fingerprint, app build, ambient conditions, brightness, battery state, network/radio state, camera settings, runtime package/native interpreter, delegate requested and delegate actually used. The comparison requires at least three repeated runs, a documented warm-up, at least 100 measured observations, and a 30-minute sustained development run per candidate on the primary device. Capture raw timing logs and thermal/battery observations.

Report p50 and p95 from camera-frame capture through spoken feedback, inference-only latency, peak memory, battery change, temperature trend, throttling or delegate fallback, dropped/stale frames, and speech delivery state. Do not convert short-run measurements into a longer-session claim. The release acceptance plan still requires its separate two-hour battery/thermal soak.

## Export parity and runtime compatibility

Use a fixed, versioned parity fixture from the development/validation split, not the locked final test split. Compare the reference framework and exported `.tflite` through the same RGB/rotation/crop/resize-or-letterbox path, tensor layout, normalization, confidence threshold and postprocessing. Record input/output names, shapes, data types, per-sample detections, coordinate transforms, class agreement, box IoU and confidence deltas, along with predeclared acceptance thresholds and raw evidence.

Load and run the exported model in the actual Expo development build on the named Android phone. The app currently tries the Android GPU delegate and falls back to CPU; record whether it actually loads, which operations fall back, and whether the CPU path remains correct. The app currently accepts only float32 NHWC RGB 640x640 input and one float32 `[1,N,6]` output. A candidate with a different tensor contract requires a separately reviewed app decoder/configuration change before it can pass packaging.

## Decision, dependencies and package

The report must name the selected model and justify the tradeoff using the same-task evidence. It must include exact checksummed training and mobile dependency locks, the native runtime/library versions, exported artifact checksum, label map, thresholds, preprocessing/output contract, version, reviewer approval, and rollback predecessor. Update and verify the exact locks only after selecting and testing the complete model/export/runtime/device configuration.

`mobile-validation.example.json` is intentionally blocked and contains no fabricated result. Create a completed copy for the experiment, attach raw evidence files under this repository or provide a controlled evidence bundle, and run the package script. The script validates report structure, required candidate coverage, measurements, evidence paths/checksums, selected artifact checksum, current app tensor contract, and dependency-lock checksums before copying or activating a model. It cannot determine whether human license/reviewer statements are truthful; reviewers must inspect the cited evidence.

## Current references

- The implementation plan's model selection and training section (page 14), training/release sequence (page 15), and D01-D08 evidence tracker (page 38).
- [Ultralytics LiteRT export documentation](https://docs.ultralytics.com/integrations/litert/) for current exporter arguments and supported artifact formats.
- [react-native-fast-tflite v3 migration notes](https://github.com/margelo/react-native-fast-tflite/blob/main/MIGRATION_V2_TO_V3.md) for the runtime API/delegate behavior that still needs testing on the target device.
