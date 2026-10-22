# VisionPath 🦯

> AI-powered indoor navigation assistant for visually impaired users  
> Alamein International University — Computer Science & Engineering — Grad Project 2026

## What It Does

VisionPath turns a smartphone into a real-time indoor navigation assistant. Using on-device computer vision (YOLOv8), voice recognition (Whisper), and an LLM conversational brain (Gemini), it tells visually impaired users exactly where objects are — "Chair at your 10 o'clock, 1.2 meters away."

## Architecture

```
Mobile (Flutter)
├── Camera → YOLOv8 TFLite (on-device, <150ms)
├── Mic    → Whisper ASR (via backend)
└── TTS    → Spatial binaural audio

Backend (FastAPI)
├── /scene/describe   → Gemini scene narration
├── /scene/history    → Recent saved scene descriptions (SQLite)
├── /users/register   → Save a user profile and role (SQLite)
├── /asr/transcribe   → Whisper speech-to-text
└── /navigate/query   → Gemini conversational Q&A
```

## Repository Structure

```
visionpath/
├── mobile/         Flutter app (camera, TFLite, spatial audio)
├── backend/        FastAPI server (Gemini, Whisper)
├── ai-models/      YOLOv8 training + ONNX/TFLite export scripts
└── docs/           Documentation
```

## Quick Start

### Backend

```bash
cd backend
cp .env.example .env           # Add your GEMINI_API_KEY
pip install -r requirements.txt
uvicorn main:app --reload
# API docs at http://localhost:8000/docs
# Scene history is stored in backend/data/visionpath.sqlite3 by default.
# User profiles are stored in the same SQLite database.
# Set USER_PROVISIONING_KEY in backend/.env before creating supervisor/admin profiles.
```

### Mobile App

```bash
cd mobile
flutter pub get
flutter run
```

### AI Model Training

```bash
cd ai-models
pip install -r requirements.txt
python train.py --dataset data/visionpath.yaml --model yolov8n --epochs 100
python export.py --weights runs/train/visionpath_v1/weights/best.pt
```

## Team

| Name | Role |
|------|------|
| TBD  | ML Engineer |
| TBD  | Mobile Developer |
| TBD  | Backend Developer |

**Supervisor:** Dr. Abdallah Hassan
