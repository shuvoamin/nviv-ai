from fastapi import APIRouter, Response
from app_state import LOG_BUFFER, APP_NAME

router = APIRouter()

@router.get("/health")
async def health_check():
    """Basic health check endpoint"""
    return {"status": "ok"}


