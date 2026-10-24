import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AppState, Linking, Platform } from 'react-native';
import { Camera, useCameraDevice, useCameraPermission, useFrameOutput, type Constraint, type Frame } from 'react-native-vision-camera';
import { useResizer } from 'react-native-vision-camera-resizer';
import { loadTensorflowModel, type TfliteModel } from 'react-native-fast-tflite';
import { scheduleOnRN } from 'react-native-worklets';
import * as Speech from 'expo-speech';
import {
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import type { Detection, VisionPathClass } from '../src/vision/contracts';
import { visionPathModelAsset, VISIONPATH_MODEL } from '../src/vision/modelAsset';
import { decodeYolo26Output } from '../src/vision/yolo26';

const MAX_FRAME_AGE_MS = 250;
const WATCHDOG_MS = 1_800;
const TRACK_TTL_MS = 1_200;
const MIN_STABLE_HITS = 2;
const SPEECH_COOLDOWN_MS = 3_500;
const PRIORITY: VisionPathClass[] = [
  'person', 'door', 'chair', 'table', 'backpack', 'cell_phone', 'keys_keyring',
];

type ModelState = 'loading' | 'ready' | 'missing' | 'failed';
type AssistState = 'paused' | 'starting' | 'observing' | 'stalled' | 'error';
type Track = Detection & { id: number; hits: number; firstSeenAt: number; lastSeenAt: number };

export default function AssistScreen() {
  const { hasPermission, requestPermission } = useCameraPermission();
  const device = useCameraDevice('back');
  const [cameraActive, setCameraActive] = useState(false);
  const [permissionDenied, setPermissionDenied] = useState(false);
  const [modelState, setModelState] = useState<ModelState>('loading');
  const [modelError, setModelError] = useState('');
  const [assistState, setAssistState] = useState<AssistState>('paused');
  const [cameraError, setCameraError] = useState('');
  const [speechError, setSpeechError] = useState('');
  const [recoveryNotice, setRecoveryNotice] = useState('');
  const [visibleTracks, setVisibleTracks] = useState<Track[]>([]);
  const [lastResultAt, setLastResultAt] = useState(0);
  const [language, setLanguage] = useState<'en-US' | 'ar'>('en-US');
  const cameraActiveRef = useRef(false);
  const [model, setModel] = useState<TfliteModel | null>(null);
  const tracksRef = useRef<Track[]>([]);
  const nextTrackIdRef = useRef(1);
  const lastSpokenRef = useRef(new Map<number, number>());
  const lastObservationRef = useRef(0);
  const startedAtRef = useRef(0);
  const noObjectSpokenAtRef = useRef(0);

  const resizerState = useResizer({
    width: VISIONPATH_MODEL.inputWidth,
    height: VISIONPATH_MODEL.inputHeight,
    channelOrder: 'rgb',
    dataType: 'float32',
    scaleMode: 'cover',
    pixelLayout: 'interleaved',
  });
  const resizer = resizerState.state === 'ready' ? resizerState.resizer : null;

  useEffect(() => () => { resizer?.dispose(); }, [resizer]);

  useEffect(() => {
    let canceled = false;
    async function loadModel() {
      if (visionPathModelAsset == null) {
        setModelState('missing');
        return;
      }
      setModelState('loading');
      setModelError('');
      try {
        let loaded: TfliteModel;
        try {
          // Android GPU is a benchmark candidate; CPU remains the compatibility fallback.
          loaded = await loadTensorflowModel(visionPathModelAsset, Platform.OS === 'android' ? ['android-gpu'] : []);
        } catch {
          loaded = await loadTensorflowModel(visionPathModelAsset, []);
        }
        validateModel(loaded);
        console.info(
          `[VisionPath] Model loaded; requested delegate result: ${loaded.delegates.length ? loaded.delegates.join(',') : 'cpu'}`,
        );
        if (canceled) return;
        setModel(loaded);
        setModelState('ready');
      } catch (error) {
        if (canceled) return;
        setModel(null);
        setModelState('failed');
        setModelError(error instanceof Error ? error.message : 'The local model could not be loaded.');
      }
    }
    void loadModel();
    return () => {
      canceled = true;
    };
  }, []);

  const speak = useCallback((message: string) => {
    setSpeechError('');
    Speech.stop();
    Speech.speak(message, {
      language,
      rate: language === 'ar' ? 0.88 : 0.92,
      pitch: 1,
      onError: () => setSpeechError(language === 'ar' ? 'تعذر تشغيل الصوت. تحقق من إعدادات الصوت.' : 'Speech playback failed. Check the phone audio output and try again.'),
    });
  }, [language]);

  const handleResult = useCallback((capturedAt: number, detections: Detection[]) => {
    const now = Date.now();
    if (!cameraActiveRef.current || capturedAt < startedAtRef.current || now - capturedAt > MAX_FRAME_AGE_MS || capturedAt <= lastObservationRef.current) return;
    lastObservationRef.current = capturedAt;
    setLastResultAt(capturedAt);
    setAssistState('observing');

    const previous = tracksRef.current.filter((track) => now - track.lastSeenAt <= TRACK_TTL_MS);
    const usedIds = new Set<number>();
    const next = detections.map((detection) => {
      let best: Track | undefined;
      let bestIou = 0.25;
      for (const track of previous) {
        if (usedIds.has(track.id) || track.className !== detection.className) continue;
        const overlap = iou(track.box, detection.box);
        if (overlap > bestIou) { best = track; bestIou = overlap; }
      }
      if (best) {
        usedIds.add(best.id);
        return { ...detection, id: best.id, hits: best.hits + 1, firstSeenAt: best.firstSeenAt, lastSeenAt: now };
      }
      const id = nextTrackIdRef.current++;
      return { ...detection, id, hits: 1, firstSeenAt: now, lastSeenAt: now };
    });
    tracksRef.current = [...next, ...previous.filter((track) => !usedIds.has(track.id))];
    setVisibleTracks(next);

    const stable = next
      .filter((track) => track.hits >= MIN_STABLE_HITS)
      .sort((a, b) => PRIORITY.indexOf(a.className) - PRIORITY.indexOf(b.className));
    const candidate = stable.find((track) => now - (lastSpokenRef.current.get(track.id) ?? 0) >= SPEECH_COOLDOWN_MS);
    if (candidate) {
      lastSpokenRef.current.set(candidate.id, now);
      speak(describeDetection(candidate, language));
    } else if (next.length === 0 && now - noObjectSpokenAtRef.current > 7_000) {
      noObjectSpokenAtRef.current = now;
      speak(language === 'ar' ? 'لم يتم رصد أجسام مدعومة. حرّك الهاتف ببطء.' : 'No supported objects detected. Move the phone slowly.');
    }
  }, [language, speak]);

  const processFrame = useCallback((frame: Frame) => {
    'worklet';
    const activeModel = model;
    const activeResizer = resizer;
    if (!activeModel || !activeResizer) { frame.dispose(); return; }

    const capturedAt = Date.now();
    let resized: ReturnType<typeof activeResizer.resize> | null = null;
    try {
      resized = activeResizer.resize(frame);
      const input = resized.getPixelBuffer();
      const output = activeModel.runSync([input])[0];
      if (output == null) return;
      const shape = activeModel.outputs[0]?.shape ?? [];
      const detections = decodeYolo26Output(
        output,
        shape,
        VISIONPATH_MODEL.classNames,
        VISIONPATH_MODEL.inputWidth,
        VISIONPATH_MODEL.inputHeight,
      );
      scheduleOnRN(handleResult, capturedAt, detections);
    } catch {
      // Native inference errors are reported through the watchdog and retry UI.
    } finally {
      resized?.dispose();
      frame.dispose();
    }
  }, [handleResult, model, resizer]);

  const frameResolution = useMemo(() => ({ width: 640, height: 480 }), []);
  const cameraConstraints = useMemo<Constraint[]>(() => [
    { fps: 15 },
    { pixelFormat: Platform.OS === 'ios' ? 'yuv-420-8-bit-full' : 'private' },
  ], []);
  const frameOutput = useFrameOutput({
    targetResolution: frameResolution,
    pixelFormat: Platform.OS === 'android' ? 'native' : 'yuv',
    dropFramesWhileBusy: true,
    onFrame: processFrame,
  });

  useEffect(() => {
    let previousState = AppState.currentState;
    const subscription = AppState.addEventListener('change', (state) => {
      if (state !== 'active') {
        const wasRunning = cameraActiveRef.current;
        cameraActiveRef.current = false;
        startedAtRef.current = Date.now();
        setCameraActive(false);
        setAssistState('paused');
        Speech.stop();
        if (wasRunning) setRecoveryNotice('Assistance paused when VisionPath left the foreground. Restart it when you are ready.');
      } else if (previousState !== 'active') {
        // Do not silently reopen the camera after a call, lock screen, or app switch.
        setRecoveryNotice((current) => current || 'VisionPath is active again. Camera access stays paused until you restart assistance.');
      }
      previousState = state;
    });
    return () => { subscription.remove(); Speech.stop(); };
  }, []);

  useEffect(() => {
    if (!cameraActive || modelState !== 'ready') return;
    const timer = setInterval(() => {
      const reference = lastObservationRef.current || startedAtRef.current;
      if (reference > 0 && Date.now() - reference > WATCHDOG_MS) setAssistState('stalled');
    }, 500);
    return () => clearInterval(timer);
  }, [cameraActive, modelState]);

  useEffect(() => {
    if (resizerState.state === 'error') {
      setModelState('failed');
      setModelError(`Frame preparation unavailable: ${resizerState.error.message}`);
    }
  }, [resizerState]);

  const startCamera = async () => {
    setCameraError('');
    setRecoveryNotice('');
    setSpeechError('');
    if (!hasPermission) {
      const granted = await requestPermission();
      if (!granted) { setPermissionDenied(true); return; }
    }
    if (!device) { setCameraError('No rear camera is available on this device.'); setAssistState('error'); return; }
    setPermissionDenied(false);
    cameraActiveRef.current = true;
    lastObservationRef.current = 0;
    startedAtRef.current = Date.now();
    setAssistState(modelState === 'ready' ? 'starting' : 'paused');
    setCameraActive(true);
  };

  const pause = () => {
    cameraActiveRef.current = false;
    startedAtRef.current = Date.now();
    setCameraActive(false);
    setAssistState('paused');
    setVisibleTracks([]);
    tracksRef.current = [];
    Speech.stop();
  };

  const modelReady = modelState === 'ready' && resizerState.state === 'ready';
  const scanning = cameraActive && modelReady && assistState === 'observing';
  const statusLabel = !cameraActive ? 'PAUSED' : scanning ? 'ASSISTING' : modelReady ? 'STARTING' : 'PREVIEW ONLY';
  const modelMessage = modelState === 'loading'
    ? 'Preparing the on-device recognition model…'
    : modelState === 'missing'
      ? 'The validated VisionPath model is not bundled yet. Camera preview and local speech work; object recognition stays off until a model passes the plan’s checks.'
      : modelState === 'failed'
        ? `Local recognition could not start. ${modelError}`
        : assistState === 'stalled'
          ? 'No fresh inference result arrived. Pause and restart assistance to recover.'
          : cameraActive && !scanning
            ? 'Camera preview is running while the on-device detector starts.'
            : cameraActive
              ? 'Objects are detected on this device. No frames are sent to a server.'
              : 'Start assistance when you are ready. You can pause the camera at any time.';

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.page}>
        <View style={styles.header}>
          <View accessible>
            <Text style={styles.eyebrow}>VISIONPATH · LOCAL ASSISTANCE</Text>
            <Text accessibilityRole="header" style={styles.title}>Visual assistant</Text>
          </View>
          <View accessible accessibilityLabel={`Assistance status: ${statusLabel}`} style={styles.statusPill}>
            <View style={[styles.statusDot, cameraActive && styles.statusDotOn, assistState === 'stalled' && styles.statusDotWarn]} />
            <Text style={styles.statusText}>{statusLabel}</Text>
          </View>
        </View>

        <Text style={styles.intro}>
          {modelReady
            ? 'Camera frames are analyzed on device. Speech guidance uses the phone’s local text-to-speech service.'
            : 'Camera preview and status speech stay on device. Object recognition is unavailable because the validated model is not bundled.'}
        </Text>

        <View
          accessible
          accessibilityRole="image"
          accessibilityLabel="Camera preview area. The live rear camera preview is processed on this device."
          style={styles.previewFrame}
        >
          {cameraActive && hasPermission && device ? (
            <Camera
              device={device}
              isActive={cameraActive}
              outputs={[frameOutput]}
              constraints={cameraConstraints}
              onPreviewStarted={() => {
                startedAtRef.current = Date.now();
                lastObservationRef.current = 0;
                if (modelReady) setAssistState('starting');
              }}
              onError={(error) => {
                cameraActiveRef.current = false;
                startedAtRef.current = Date.now();
                setCameraError(error.message);
                setAssistState('error');
                setCameraActive(false);
                Speech.stop();
              }}
              style={StyleSheet.absoluteFill}
            />
          ) : (
            <View style={styles.previewPlaceholder}>
              <Text style={styles.cameraIcon}>◎</Text>
              <Text style={styles.previewTitle}>Camera is paused</Text>
              <Text style={styles.previewCopy}>Your camera stays off until you start assistance.</Text>
            </View>
          )}
          <View style={styles.previewBadge}>
            <Text style={styles.previewBadgeText}>{scanning ? 'ON-DEVICE DETECTION' : 'CAMERA · ON DEVICE'}</Text>
          </View>
        </View>

        {permissionDenied ? <Text accessibilityRole="alert" style={styles.notice}>Camera permission was denied. Enable it in system settings to use assistance.</Text> : null}
        {permissionDenied ? (
          <Pressable accessibilityRole="button" accessibilityLabel="Open system settings to allow camera access" onPress={() => { void Linking.openSettings().catch(() => setCameraError('Could not open system settings. Open the app permissions from your phone settings.')); }} style={styles.secondaryButton}>
            <Text style={styles.secondaryButtonText}>Open camera settings</Text>
          </Pressable>
        ) : null}
        {cameraError ? <Text accessibilityRole="alert" style={styles.notice}>Camera needs attention: {cameraError}</Text> : null}
        {speechError ? <Text accessibilityRole="alert" style={styles.notice}>{speechError}</Text> : null}
        {recoveryNotice ? <Text accessibilityRole="alert" style={styles.notice}>{recoveryNotice}</Text> : null}
        {modelState === 'failed' || modelState === 'missing' ? <Text accessibilityRole="alert" style={styles.modelNotice}>{modelMessage}</Text> : null}

        <View style={styles.card}>
          <Text style={styles.cardEyebrow}>LOCAL PATH STATUS</Text>
          <Text accessibilityLiveRegion="polite" style={styles.cardTitle}>
            {!cameraActive ? 'Ready when you are' : scanning ? 'Observing nearby objects' : assistState === 'stalled' ? 'Detection paused · recovery needed' : modelState === 'missing' ? 'Preview active · model not installed' : assistState === 'error' ? 'Camera unavailable' : 'Starting local assistance'}
          </Text>
          <Text style={styles.cardCopy}>{modelMessage}</Text>
          {lastResultAt > 0 && scanning ? <Text style={styles.freshness}>Latest result {Math.max(0, Date.now() - lastResultAt)} ms ago · stale results are discarded</Text> : null}
        </View>

        {modelReady && cameraActive ? (
          <View style={styles.card}>
            <Text style={styles.cardEyebrow}>SUPPORTED OBJECTS IN VIEW</Text>
            {visibleTracks.filter((track) => track.hits >= MIN_STABLE_HITS).length === 0 ? (
              <Text style={styles.cardCopy}>No stable supported objects in the latest frame.</Text>
            ) : visibleTracks.filter((track) => track.hits >= MIN_STABLE_HITS).map((track) => (
              <View key={track.id} style={styles.objectRow}>
                <Text style={styles.objectName}>{displayName(track.className, language)}</Text>
                <Text style={styles.objectDirection}>{directionLabel(track.direction, language)} · {Math.round(track.confidence * 100)}%</Text>
              </View>
            ))}
          </View>
        ) : null}

        <View style={styles.actions}>
          <Pressable
            accessibilityRole="button"
            accessibilityState={{ disabled: false }}
            accessibilityLabel={cameraActive ? 'Pause assistance' : 'Start local assistance'}
            onPress={cameraActive ? pause : startCamera}
            style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed]}
          >
            <Text style={styles.primaryButtonText}>{cameraActive ? 'Pause assistance' : 'Start assistance'}</Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={language === 'en-US' ? 'Speech language English. Switch to Arabic.' : 'لغة النطق العربية. التبديل إلى الإنجليزية.'}
            accessibilityState={{ selected: language === 'ar' }}
            onPress={() => setLanguage((current) => current === 'en-US' ? 'ar' : 'en-US')}
            style={({ pressed }) => [styles.secondaryButton, pressed && styles.pressed]}
          >
            <Text style={styles.secondaryButtonText}>{language === 'en-US' ? 'Speech: English · tap for Arabic' : 'Speech: العربية · tap for English'}</Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={language === 'ar' ? 'إعادة الحالة صوتيًا' : 'Repeat current assistance status aloud'}
            onPress={() => speak(cameraActive ? modelReady ? (language === 'ar' ? 'المساعدة المحلية نشطة.' : 'Local assistance is active.') : (language === 'ar' ? 'معاينة الكاميرا نشطة. نموذج التعرف غير مثبت.' : 'Camera preview is active. The recognition model is not installed.') : (language === 'ar' ? 'فيجن باث متوقف مؤقتا.' : 'VisionPath is paused. Start assistance when you are ready.'))}
            style={({ pressed }) => [styles.secondaryButton, pressed && styles.pressed]}
          >
            <Text style={styles.secondaryButtonText}>Repeat status aloud</Text>
          </Pressable>
        </View>

        <Text style={styles.privacyNote}>
          {modelReady
            ? 'Camera frames, model inference, and device speech stay local. This path does not require an account, network API, or LLM.'
            : 'Camera preview and device speech stay local. This path does not require an account, network API, or LLM; object recognition is currently unavailable.'}
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

function validateModel(model: TfliteModel) {
  const input = model.inputs[0];
  const output = model.outputs[0];
  const inputShape = input?.shape;
  const outputShape = output?.shape;
  if (model.inputs.length !== 1 || input?.dataType !== 'float32' ||
      inputShape?.length !== 4 || inputShape[0] !== 1 ||
      inputShape[1] !== VISIONPATH_MODEL.inputHeight ||
      inputShape[2] !== VISIONPATH_MODEL.inputWidth || inputShape[3] !== 3) {
    throw new Error('Model input must be float32 RGB [1, 640, 640, 3].');
  }
  if (model.outputs.length !== 1 || output?.dataType !== 'float32' || outputShape?.length !== 3 || outputShape[0] !== 1 || outputShape[2] !== 6 || !outputShape[1]) {
    throw new Error('Model output must be YOLO26 end-to-end detections [1, N, 6].');
  }
}

function iou(a: Detection['box'], b: Detection['box']): number {
  const left = Math.max(a.x, b.x);
  const top = Math.max(a.y, b.y);
  const right = Math.min(a.x + a.width, b.x + b.width);
  const bottom = Math.min(a.y + a.height, b.y + b.height);
  const intersection = Math.max(0, right - left) * Math.max(0, bottom - top);
  const union = a.width * a.height + b.width * b.height - intersection;
  return union > 0 ? intersection / union : 0;
}

function displayName(name: VisionPathClass, language: 'en-US' | 'ar') {
  if (language === 'ar') {
    const names: Record<VisionPathClass, string> = {
      person: 'شخص', chair: 'كرسي', table: 'طاولة', door: 'باب',
      cell_phone: 'هاتف', keys_keyring: 'مفاتيح', backpack: 'حقيبة ظهر',
    };
    return names[name];
  }
  return name === 'cell_phone' ? 'phone' : name === 'keys_keyring' ? 'keys' : name.replace('_', ' ');
}

function directionLabel(direction: Detection['direction'], language: 'en-US' | 'ar') {
  if (language === 'ar') return direction === 'left' ? 'على اليسار' : direction === 'right' ? 'على اليمين' : 'أمامك';
  return direction === 'left' ? 'left' : direction === 'right' ? 'right' : 'ahead';
}

function describeDetection(detection: Detection, language: 'en-US' | 'ar') {
  const object = displayName(detection.className, language);
  const direction = directionLabel(detection.direction, language);
  return language === 'ar' ? `${object} ${direction}` : `${object} ${direction}`;
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#101820' },
  page: { flexGrow: 1, paddingHorizontal: 22, paddingTop: 18, paddingBottom: 34, gap: 18 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  eyebrow: { color: '#91B7B2', fontSize: 11, fontWeight: '700', letterSpacing: 1.8 },
  title: { color: '#F5F7F6', fontSize: 28, fontWeight: '700', marginTop: 5 },
  statusPill: { flexDirection: 'row', alignItems: 'center', gap: 7, borderRadius: 20, backgroundColor: '#202E36', paddingHorizontal: 11, paddingVertical: 8 },
  statusDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: '#839097' },
  statusDotOn: { backgroundColor: '#56D6A0' },
  statusDotWarn: { backgroundColor: '#FFB45D' },
  statusText: { color: '#D7E2E0', fontSize: 10, fontWeight: '700', letterSpacing: 0.8 },
  intro: { color: '#B9C5C8', fontSize: 15, lineHeight: 22 },
  previewFrame: { minHeight: 240, height: 310, overflow: 'hidden', borderRadius: 22, backgroundColor: '#1A2931', position: 'relative' },
  previewPlaceholder: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  cameraIcon: { color: '#79B8AC', fontSize: 48, marginBottom: 8 },
  previewTitle: { color: '#F5F7F6', fontSize: 19, fontWeight: '700' },
  previewCopy: { color: '#AAB9BC', fontSize: 14, marginTop: 7, textAlign: 'center', lineHeight: 20 },
  previewBadge: { position: 'absolute', left: 12, top: 12, borderRadius: 12, backgroundColor: '#101820D9', paddingHorizontal: 10, paddingVertical: 7 },
  previewBadgeText: { color: '#D8E5E2', fontSize: 9, fontWeight: '700', letterSpacing: 1 },
  notice: { color: '#FFD6A0', fontSize: 13, lineHeight: 19 },
  modelNotice: { color: '#FFD6A0', fontSize: 13, lineHeight: 19, borderRadius: 12, backgroundColor: '#342A1E', padding: 12 },
  card: { borderColor: '#293941', borderWidth: 1, borderRadius: 18, padding: 17, backgroundColor: '#17242C', gap: 7 },
  cardEyebrow: { color: '#91B7B2', fontSize: 10, fontWeight: '700', letterSpacing: 1.4 },
  cardTitle: { color: '#F5F7F6', fontSize: 19, fontWeight: '700', marginTop: 3 },
  cardCopy: { color: '#B9C5C8', fontSize: 14, lineHeight: 21 },
  freshness: { color: '#83BCA9', fontSize: 12, marginTop: 4 },
  objectRow: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', gap: 6, paddingVertical: 7, borderBottomColor: '#293941', borderBottomWidth: StyleSheet.hairlineWidth },
  objectName: { color: '#F5F7F6', fontSize: 15, fontWeight: '600' },
  objectDirection: { color: '#B9C5C8', fontSize: 13 },
  actions: { gap: 10 },
  primaryButton: { minHeight: 54, borderRadius: 15, backgroundColor: '#66D4B1', alignItems: 'center', justifyContent: 'center', paddingHorizontal: 18 },
  primaryButtonText: { color: '#10211F', fontSize: 16, fontWeight: '800' },
  secondaryButton: { minHeight: 52, borderRadius: 15, borderWidth: 1, borderColor: '#4B686D', alignItems: 'center', justifyContent: 'center', paddingHorizontal: 18 },
  secondaryButtonText: { color: '#E3EEEB', fontSize: 15, fontWeight: '700', textAlign: 'center' },
  pressed: { opacity: 0.76 },
  privacyNote: { color: '#87989C', fontSize: 12, lineHeight: 18, textAlign: 'center' },
});
