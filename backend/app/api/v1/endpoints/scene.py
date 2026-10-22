"""
Scene Understanding Endpoint
Accepts structured object detection results from the mobile app
and returns a natural language description of the scene via Gemini.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List
from loguru import logger

from app.services.gemini_service import GeminiService
from app.core.database import list_scene_descriptions, save_scene_description

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


class SceneHistoryItem(BaseModel):
    id: int
    created_at: str
    scene_context: str
    narrative: str
    priority_alert: str
    objects: List[DetectedObject]


class SceneHistoryResponse(BaseModel):
    items: List[SceneHistoryItem]
    count: int


@router.get("/history", response_model=SceneHistoryResponse)
async def get_scene_history(limit: int = Query(default=20, ge=1, le=100)):
    """Return recent scene descriptions saved by this backend instance."""
    try:
        items = list_scene_descriptions(limit=limit)
        return SceneHistoryResponse(items=items, count=len(items))
    except Exception as e:
        logger.error(f"Scene history lookup failed: {e}")
        raise HTTPException(status_code=500, detail="Could not load scene history")


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
        try:
            save_scene_description(
                scene_context=request.scene_context,
                narrative=narrative,
                priority_alert=alert,
                objects=request.objects,
            )
        except Exception as e:
            # Persistence should not prevent the live navigation response.
            logger.error(f"Could not save scene description: {e}")
        return SceneResponse(
            narrative=narrative,
            priority_alert=alert,
            objects_count=len(request.objects),
        )
    except Exception as e:
        logger.error(f"Scene description failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
