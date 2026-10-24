import type { BoundingBox, CameraRelativeDirection, Detection, VisionPathClass } from './contracts';

// Provisional baseline values only. Re-evaluate on the versioned validation
// split and update this decoder with the reviewed model-selection report.
const CONFIDENCE_THRESHOLD = 0.4;
const IOU_THRESHOLD = 0.5;

/** Decode the current provisional YOLO26 end-to-end candidate contract. */
export function decodeYolo26Output(
  output: ArrayBuffer,
  shape: number[],
  classNames: readonly VisionPathClass[],
  inputWidth: number,
  inputHeight: number,
): Detection[] {
  'worklet';
  if (shape.length !== 3 || shape[0] !== 1 || shape[2] !== 6) return [];
  const rowCount = shape[1];
  const values = new Float32Array(output);
  if (values.length < rowCount * 6) return [];

  const candidates: Detection[] = [];
  for (let row = 0; row < rowCount; row += 1) {
    const offset = row * 6;
    const score = values[offset + 4];
    const classId = Math.round(values[offset + 5]);
    if (!Number.isFinite(score) || score < CONFIDENCE_THRESHOLD) continue;
    if (classId < 0 || classId >= classNames.length) continue;

    const x1 = clamp(values[offset] / inputWidth, 0, 1);
    const y1 = clamp(values[offset + 1] / inputHeight, 0, 1);
    const x2 = clamp(values[offset + 2] / inputWidth, 0, 1);
    const y2 = clamp(values[offset + 3] / inputHeight, 0, 1);
    if (x2 <= x1 || y2 <= y1) continue;

    const box: BoundingBox = { x: x1, y: y1, width: x2 - x1, height: y2 - y1 };
    candidates.push({
      className: classNames[classId],
      confidence: score,
      box,
      direction: directionFor(box),
      measuredDistanceMeters: null,
    });
  }

  // Keep only the strongest overlapping detection for each class.
  candidates.sort((a, b) => b.confidence - a.confidence);
  const selected: Detection[] = [];
  for (const candidate of candidates) {
    const overlaps = selected.some(
      (item) => item.className === candidate.className && intersectionOverUnion(item.box, candidate.box) > IOU_THRESHOLD,
    );
    if (!overlaps) selected.push(candidate);
    if (selected.length >= 20) break;
  }
  return selected;
}

function directionFor(box: BoundingBox): CameraRelativeDirection {
  'worklet';
  const center = box.x + box.width / 2;
  if (center < 0.38) return 'left';
  if (center > 0.62) return 'right';
  return 'ahead';
}

function intersectionOverUnion(a: BoundingBox, b: BoundingBox): number {
  'worklet';
  const left = Math.max(a.x, b.x);
  const top = Math.max(a.y, b.y);
  const right = Math.min(a.x + a.width, b.x + b.width);
  const bottom = Math.min(a.y + a.height, b.y + b.height);
  const intersection = Math.max(0, right - left) * Math.max(0, bottom - top);
  const union = a.width * a.height + b.width * b.height - intersection;
  return union <= 0 ? 0 : intersection / union;
}

function clamp(value: number, min: number, max: number): number {
  'worklet';
  return Math.max(min, Math.min(max, value));
}
