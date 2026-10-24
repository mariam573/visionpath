/**
 * Replaced by the mobile packaging step after a model has passed the plan's
 * dataset, export-parity, license, and reference-device checks. Keeping this
 * null makes an unvalidated model impossible to ship accidentally.
 */
export const visionPathModelAsset: number | null = null;

export const VISIONPATH_MODEL = {
  version: 'not-installed',
  inputWidth: 640,
  inputHeight: 640,
  classNames: [
    'person',
    'chair',
    'table',
    'door',
    'cell_phone',
    'keys_keyring',
    'backpack',
  ] as const,
  // Provisional decoder contract, not a model selection: YOLO26-style
  // end-to-end TFLite output [1, N, 6], rows [x1, y1, x2, y2, score, classId].
  maxDetections: 300,
} as const;
