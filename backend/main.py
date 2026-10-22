"""
VisionPath Backend — Main FastAPI Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core.config import settings
from app.api.v1.router import api_router

app = FastAPI(
    title="VisionPath API",
    description="AI-powered navigation assistant backend for the visually impaired",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "visionpath-backend", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting VisionPath API on {settings.HOST}:{settings.PORT}")
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
