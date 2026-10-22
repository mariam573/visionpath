"""
Navigation Query Endpoint
Accepts a free-form user query + current scene objects and returns
navigation guidance via Gemini.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List
from loguru import logger

from app.services.gemini_service import GeminiService

router = APIRouter()
gemini = GeminiService()


class NavObject(BaseModel):
    label: str
    distance_meters: float
    clock_direction: int


class NavigationRequest(BaseModel):
    query: str = Field(..., description="User voice query e.g. 'Where is the elevator?'")
    objects: List[NavObject] = Field(default=[], description="Currently detected objects")
    scene_context: str = Field(default="indoor")


class NavigationResponse(BaseModel):
    response: str = Field(..., description="Spoken navigation guidance")
    requires_action: bool = Field(default=False)


@router.post("/query", response_model=NavigationResponse)
async def navigation_query(request: NavigationRequest):
    """
    Conversational navigation — user asks a question about their surroundings
    and Gemini responds with concise, actionable spatial guidance.
    """
    try:
        answer = await gemini.answer_navigation_query(
            query=request.query,
            objects=request.objects,
            scene_context=request.scene_context,
        )
        return NavigationResponse(response=answer)
    except Exception as e:
        logger.error(f"Navigation query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
