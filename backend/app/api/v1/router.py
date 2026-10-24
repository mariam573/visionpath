from fastapi import APIRouter

from app.api.v1.endpoints.consents import router as consents_router
from app.api.v1.endpoints.users import router as users_router

# Only identity-protected self-profile and consent controls are mounted.
# Scene questions, navigation questions, registration, audio upload,
# synchronization, and sharing implementations are absent until their gates exist.
api_router = APIRouter()
api_router.include_router(users_router)
api_router.include_router(consents_router)
