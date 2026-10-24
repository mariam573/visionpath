# VisionPath

VisionPath is an early visual-assistance prototype for blind and low-vision users. The repository is not yet the application described by the approved implementation plan, and the current code must not be presented as a reliable navigation aid.

## Implementation status

- `mobile/` is the active Expo SDK 58 / React Native / TypeScript app with locally defined EAS Android development, preview and production profiles.
- VisionCamera frame output, native frame resizing and `react-native-fast-tflite` integration points, 15 FPS camera constraints, stale-result rejection, IoU tracking/filtering, a language switch that requests English or Arabic device TTS, pause/background handling and an inference watchdog are present in the mobile screen. The validated model asset is absent, so the current screen is preview/status speech only and does not claim object recognition. Installed TTS voices, Arabic quality and the native inference path have not been device-verified.
- The native camera/inference setup requires a custom development build; this app is not an Expo Go target. The repository has no linked EAS project ID, so the team's existing EAS project still needs to be identified and linked before remote builds.
- The FastAPI backend now has a PostgreSQL-only SQLAlchemy schema managed by Alembic, OIDC access-token verification, identity-subject-bound self profiles, and append-only purpose-specific consent grant/revocation events. Only protected `/users/me` profile and consent endpoints are mounted. There is no public account-registration handler; the managed identity provider owns credential signup. Scene questions, navigation questions, audio upload/transcription, synchronization, and sharing implementations are absent from the active backend until their consent, ownership, quota, evidence, and safety gates are built.
- Speech recognition, scene narration, account sharing and navigation are not integrated end-to-end.
- The current app has no local SQLite/SQLCipher persistence, preferences/history store, ASR/push-to-talk commands, guided find/read/ask modes, fully localized Arabic RTL UI, obstruction/low-light detector, thermal degradation profile, or audio-route recovery. These remain plan work; see the [implementation alignment register](docs/implementation-alignment.md) for task IDs and evidence status.
- Detection boxes alone cannot establish metric distance, door state, seat occupancy, a clear floor, or a safe route. Current supported spatial language is limited to camera-relative left/ahead/right when the implementation can justify it. Otherwise direction and distance are unknown.

The implementation plan is the target architecture and scope reference. Its tracker is initially unchecked; a plan item is complete only when implementation and its acceptance evidence exist.

## Target architecture

- Android-first React Native/TypeScript/Expo app with the team's existing EAS workflow to be validated and extended. Use an Expo development build for native camera and inference modules; the active native app cannot run in Expo Go.
- Keep camera frames, inference, tracking, evidence rules and common commands in a local foreground path. Local assistance must work without an account, backend, network or LLM.
- Treat cloud questions and sharing as optional, consent-based services. Never turn generated text into movement or safety instructions; reject stale or unsupported answers.
- Evaluate the scoped starter classes: person, chair, table, door, cell phone, keys/keyring and backpack. Source and license every dataset item, group related scenes before splitting, and keep an independently verified local holdout.
- PostgreSQL/Alembic currently back the identity-bound profile and consent foundation. Extend the schema with reviewed migrations as approved services are implemented. Do not store routine camera frames, raw audio or default question transcripts.
- Add distance, attributes, OCR and mapped-building routing only behind separate data, device and evaluation gates.

## Current repository layout

```text
mobile/       Expo / React Native / TypeScript app
              native frame-to-TFLite integration; validated model asset pending
backend/      FastAPI PostgreSQL/Alembic and OIDC profile/consent foundation
ai-models/    Ultralytics training/export experiments; artifacts and evaluations pending
```

## Running the current prototype

### Backend

```powershell
cd backend
Copy-Item .env.example .env
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

Configure `DATABASE_URL`, the managed identity provider's exact `OIDC_ISSUER`, `OIDC_JWKS_URL`, and API `OIDC_AUDIENCE`, and a reviewed `CONSENT_POLICY_VERSION` in `backend/.env`. The application does not create tables at startup: apply migrations first. The currently mounted profile and consent routes require a valid bearer access token and derive ownership from its verified issuer/subject. Unsupported scene/navigation questions and audio upload/transcription code is absent from the active backend. See [backend/README.md](<C:/Users/hp/OneDrive/Desktop/Grad Project/visionpath/backend/README.md>) before using a non-local deployment.

### Expo app

```powershell
cd mobile
pnpm install --frozen-lockfile
pnpm start
```

Install an EAS development build before starting the JS bundler. Expo Go does not contain VisionCamera or the TFLite native runtime. First log in with the team's Expo account, confirm which existing EAS project owns the application ID, and link that project with:

```powershell
pnpm eas:link
```

Then create the Android development build:

```powershell
pnpm build:android:development
```

The app IDs currently configured in `app.json` are `com.visionpath.visionpath_app` for Android and `com.visionpath.visionpathApp` for iOS. Confirm they match existing registrations before building or publishing. Remote EAS builds require the project to be linked to an Expo account. Without the validated model artifact, the current build only provides camera preview and status speech; it cannot identify objects.

### Model experiments

The training scripts are experiments, not evidence of model accuracy, mobile speed, or supported classes. Compare YOLOv8n, YOLO26n/s and YOLOE-26n on shared held-out campus tasks and the same named Android device; record license/export support, per-class and key-finding quality, p95 end-to-end latency, memory, thermal behavior, battery and actual delegate/fallback behavior. Follow [the model-selection protocol](ai-models/model-selection-protocol.md), then export and complete `ai-models/mobile-validation.example.json`. The fail-closed packager checks raw evidence and exact dependency-lock hashes before it can copy a candidate into the app. The current experiment pins are reproducibility inputs, not a selected model/runtime configuration. No benchmark, license decision or model selection is claimed yet.

## Immediate architecture work

1. Link and audit the existing EAS project, then validate development, preview and production Android profiles.
2. Inventory exact reference Android devices and measure VisionCamera/TFLite/TTS compatibility, including frame age, thermal behavior, and CPU fallback.
3. Compare the plan's candidate detectors on shared tasks and devices, source and version the licensed dataset, validate export parity/runtime compatibility and measure latency/thermal/battery before selecting and packaging a model.
4. After a model passes the packaging gate, exercise the bundled camera-to-detection-to-spoken-observation path on reference devices; record accuracy, latency, stale-frame, pause/recovery, and offline acceptance evidence.
5. Select/configure the managed identity provider, review the consent text/version, and deploy PostgreSQL with secret management, backups, monitoring, and retention controls before enabling cloud questions, synchronization, or sharing.
6. Add accessibility, privacy, failure and device evaluation evidence before widening scope.

No capability should be marked complete based only on a mock screen, separate model experiment, or this documentation.
