import os
import sys
import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Add the current directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import app_state
from config import APP_NAME
from utils.image_utils import save_base64_image
from routes import twilio_routes, meta_routes, system_routes

from contextlib import asynccontextmanager

cleanup_task_ref = None

async def background_cleanup_task():
    while True:
        try:
            from utils.image_utils import cleanup_old_images
            await asyncio.to_thread(cleanup_old_images)
        except asyncio.CancelledError:
            break
        except Exception as e:
            app_state.diag_logger.error(f"Image cleanup task error: {e}")
        # Run cleanup every hour (3600 seconds = 1 hour)
        await asyncio.sleep(3600)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global cleanup_task_ref
    # Startup: Initialize Chatbot Agent
    if app_state.chatbot:
        await app_state.chatbot.initialize()
        
    cleanup_task_ref = asyncio.create_task(background_cleanup_task())
    yield
    # Shutdown: Cleanup
    if cleanup_task_ref:
        cleanup_task_ref.cancel()
    if app_state.chatbot and hasattr(app_state.chatbot, 'agent'):
        await app_state.chatbot.agent.cleanup()

app = FastAPI(title=APP_NAME, description=f"Enterprise API for {APP_NAME} Chatbot", lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(system_routes.router, tags=["System"])
app.include_router(twilio_routes.router, tags=["Twilio"])
app.include_router(meta_routes.router, tags=["Meta"])

# --- Web App Endpoints ---

class ChatRequest(BaseModel):
    message: str
    session_id: str = "web_default"
    reset: bool = False

class ChatResponse(BaseModel):
    message: str


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    if app_state.chatbot is None: raise HTTPException(status_code=503, detail="Service unavailable")
    if request.reset: await app_state.chatbot.reset_history(request.session_id)
    response = await app_state.chatbot.chat(request.message, thread_id=request.session_id)
    return ChatResponse(message=response)


@app.get("/static/generated_images/{filename}")
async def get_image(filename: str, request: Request):
    """Serve images with explicit headers and diagnostic logging"""
    filepath = app_state.IMAGES_DIR / filename
    ua = request.headers.get("user-agent", "Unknown")
    
    if not filepath.exists():
        app_state.diag_logger.error(f"Image 404: {filename} requested by {ua}")
        raise HTTPException(status_code=404, detail="Image not found")
    
    media_type = "image/png"
    if filename.endswith(".jpg") or filename.endswith(".jpeg"):
        media_type = "image/jpeg"
    elif filename.endswith(".webp"):
        media_type = "image/webp"
        
    app_state.diag_logger.info(f"Image fetched: {filename} by {ua}. Content-Type: {media_type}")
    return FileResponse(filepath, media_type=media_type)

# Frontend implementation
frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")


if __name__ == "__main__": # pragma: no cover
    uvicorn.run(app, host="0.0.0.0", port=8000)
