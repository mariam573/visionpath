from fastapi import APIRouter
from app.api.v1.endpoints import scene, asr, navigate, users

api_router = APIRouter()

api_router.include_router(scene.router, prefix="/scene", tags=["Scene Understanding"])
api_router.include_router(asr.router, prefix="/asr", tags=["Speech Recognition"])
api_router.include_router(navigate.router, prefix="/navigate", tags=["Navigation"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
