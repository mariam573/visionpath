# Accessibility and device acceptance

This checklist is a release evidence gate, not a claim that hardware testing has passed. Do not mark a row passed without a named handset, OS/build, reproducible steps, outcome, and attached evidence. The project does not currently identify a reference handset and the validated on-device model is not bundled, so model-dependent rows remain blocked.

## Required device record

Create one record per handset and OS version. Include manufacturer/model, Android version and security patch, VisionPath build/git revision, display/font scaling, TalkBack version/settings, date, tester, and evidence file paths. Test the primary supported Android handset and at least one lower-end supported handset before release. Add iOS only if it remains a supported target.

| Handset / OS / build | Accessibility setup | Camera/audio setup | Tester/date | Evidence location | Overall |
|---|---|---|---|---|---|
| _Not yet named or tested_ | — | — | — | — | pending |

## Core accessibility and failure gates

Run each gate on every named target handset; record pass/fail/blocked independently. Capture TalkBack traversal and announcements, screenshots/video where appropriate, and app logs for failure cases. Never use a cloud response or movement instruction as a fallback.

| Gate | Procedure and acceptance criteria | Status |
|---|---|---|
| TalkBack navigation | Enable TalkBack. Navigate the screen without sight. Every action has a clear role, unique spoken label, and useful state; status and permission/camera/speech errors are announced once and are not drowned by per-frame updates. Camera preview is identified as a live local preview. | pending |
| Large text and display scaling | Set Android font/display size to default, 1.3x, and largest practical size. Scroll to every action; text remains readable, wraps without clipping/overlap, and buttons remain reachable and operable. | pending |
| Camera permission: first request | Fresh install, deny once, then retry. No preview/inference starts until granted; denial explains how to recover. | pending |
| Camera permission: blocked/revoked | Deny permanently or revoke permission in system settings. App offers settings recovery, reports the unavailable camera, and does not crash or claim assistance is running. | pending |
| Camera lifecycle | Start, lock/unlock, background/foreground, rotate if supported, and receive a phone call. Camera is stopped when leaving foreground, is not silently restarted, and explicit restart restores preview/inference. | pending |
| Audio interruption and failure | Speak an observation; interrupt with a call, alarm, audio route change, or system TTS failure. Speech must stop or recover without crashing or repeating stale guidance. Check repeat-status recovery. | pending |
| Low light and obstructed lens | Test daylight, dim indoor light, and fully covered lens. Do not announce an object or infer safe/clear space from unreliable frames. A low-light/obstruction detector is not implemented: until separately validated, treat this as an unresolved limitation and do not claim detection of these conditions. | blocked: capability/evidence absent |
| Stale results and inference stall | With model enabled, induce a slow/stalled inference and verify results older than the freshness limit or captured before restart are discarded; watchdog shows recovery state and no stale speech is delivered. | blocked: model absent |
| Offline behavior | Disable Wi-Fi and mobile data before launch; verify local preview, inference, and device TTS work without account/API/LLM, and that loss of network does not alter the local path. | pending; model-dependent portion blocked |
| Arabic and English | Test all visible controls/status/errors with each supported UI locale, RTL layout, TalkBack pronunciation, and device TTS voice. Verify switching language during active assistance and speech recovery. Current screen provides bilingual object speech but does not yet localize all UI text; full bilingual UI/RTL remains blocked. | blocked: localization incomplete |

## Separate evidence gates for future capabilities

These are independent capabilities. Passing one does not approve another. Keep them unavailable in production until their own evidence is reviewed.

| Capability | Minimum separate evidence before enabling | Status |
|---|---|---|
| OCR / text reading | Named-device tests across supported scripts/languages, blur/glare/low light, accessibility delivery, false-read and omission rates, privacy review, and offline/runtime evidence. | not implemented / blocked |
| Depth or distance | Sensor/model provenance, calibrated distance error by range and surface, uncertainty behavior, failure cases, named-device measurements, and safety review. | not implemented / blocked |
| Routing / navigation | Versioned mapped environment, localization and route-completion evaluation, obstacle/change handling, stale-map behavior, named-device user study, and explicit safety review. Cloud answers must never produce movement guidance. | not implemented / blocked |

## Current implementation notes

- The local path stops when the app leaves the foreground and requires the user to restart it on return.
- Camera denial has a system-settings recovery action; camera, speech, and inference failures must remain visible and non-fatal.
- Frame freshness filtering and an inference watchdog are present, but their device behavior is unverified.
- The active screen currently exposes English UI and English/Arabic object speech. It does not yet provide a fully translated Arabic UI/RTL experience.
- No named phones, completed device logs, low-light/obstruction classifier, or bundled validated model are present in this checkout. Hardware and model-dependent gates therefore remain pending or blocked as indicated above.
