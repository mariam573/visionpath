"""
Scene Understanding Endpoint
Accepts structured object detection results from the mobile app
and returns a natural language description of the scene via Gemini.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List
from loguru import logger

from app.services.gemini_service import GeminiService

router = APIRouter()
gemini = GeminiService()


class DetectedObject(BaseModel):
    label: str = Field(..., description="Object class label e.g. 'door', 'chair'")
    confidence: float = Field(..., ge=0.0, le=1.0)
    distance_meters: float = Field(..., description="Estimated distance in meters")
    clock_direction: int = Field(..., ge=1, le=12, description="Clock-face direction (1-12)")
    bbox: List[float] = Field(..., description="[x1, y1, x2, y2] normalized 0-1")


class SceneRequest(BaseModel):
    objects: List[DetectedObject]
    user_query: str = Field(default="", description="Optional voice query from user")
    scene_context: str = Field(default="indoor", description="Context: indoor/outdoor/corridor")


class SceneResponse(BaseModel):
    narrative: str = Field(..., description="Natural language scene description")
    priority_alert: str = Field(default="", description="Urgent hazard alert if any")
    objects_count: int


@router.post("/describe", response_model=SceneResponse)
async def describe_scene(request: SceneRequest):
    """
    Accepts detected objects from on-device YOLOv8 and returns
    a spatial audio-ready scene description via Gemini.
    """
    if not request.objects:
        return SceneResponse(narrative="No objects detected in the scene.", objects_count=0)

    try:
        narrative, alert = await gemini.describe_scene(
            objects=request.objects,
            user_query=request.user_query,
            scene_context=request.scene_context,
        )
        return SceneResponse(
            narrative=narrative,
            priority_alert=alert,
            objects_count=len(request.objects),
        )
    except Exception as e:
        logger.error(f"Scene description failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
