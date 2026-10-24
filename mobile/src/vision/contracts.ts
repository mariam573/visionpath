export type VisionPathClass =
  | 'person'
  | 'chair'
  | 'table'
  | 'door'
  | 'cell_phone'
  | 'keys_keyring'
  | 'backpack';

export type CameraRelativeDirection = 'left' | 'ahead' | 'right' | 'unknown';

export interface BoundingBox {
  /** Normalized image coordinates in the range [0, 1]. */
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Detection {
  className: VisionPathClass;
  confidence: number;
  box: BoundingBox;
  direction: CameraRelativeDirection;
  /** Null unless provided by a separately validated measurement. */
  measuredDistanceMeters: number | null;
}

export interface SceneObservation {
  capturedAtEpochMs: number;
  modelVersion: string;
  detections: Detection[];
}

export type DetectorState =
  | { status: 'unavailable'; reason: 'model_missing' | 'model_invalid' | 'native_runtime_unavailable' }
  | { status: 'loading' }
  | { status: 'ready'; modelVersion: string }
  | { status: 'failed'; reason: string };

export interface LocalDetector {
  load(): Promise<void>;
  detect(frame: ArrayBuffer, capturedAtEpochMs: number): Promise<SceneObservation>;
  dispose(): Promise<void>;
}

export interface SpeechOutput {
  speak(text: string): void;
  stop(): void;
}
