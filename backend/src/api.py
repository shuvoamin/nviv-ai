import os
import sys
import uvicorn
from fastapi import FastAPI, HTTPException, Form, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from twilio.twiml.messaging_response import MessagingResponse

# Add the current directory to sys.path to allow importing local modules
# This helps when the script is run from different working directories
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from chatbot import ChatBot
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Nviv", description="API for communicating with Azure OpenAI Chatbot")

import os
logger.info(f"Current Working Directory: {os.getcwd()}")
logger.info(f"Files in root: {os.listdir('.')}")
if os.path.exists('backend'):
    logger.info(f"Files in backend: {os.listdir('backend')}")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

class ChatRequest(BaseModel):
    message: str
    reset: bool = False

class ChatResponse(BaseModel):
    message: str

# Initialize chatbot
try:
    chatbot = ChatBot()
    logger.info("ChatBot initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize ChatBot: {e}")
    # In a real app we might want to fail start-up, but for now we'll handle calls gracefully if possible or let them fail
    chatbot = None

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    if chatbot is None:
        raise HTTPException(status_code=503, detail="Chatbot service not available (check configuration)")

    if request.reset:
        chatbot.reset_history()
    
    response = chatbot.chat(request.message)
    return ChatResponse(message=response)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/whatsapp")
async def whatsapp_webhook(
    Body: str = Form(None), 
    From: str = Form(...),
    MediaUrl0: str = Form(None),
    MediaContentType0: str = Form(None)
):
    logger.info(f"Received WhatsApp message from {From}. Body: {Body}, Media: {MediaContentType0}")
    
    if chatbot is None:
        logger.error("Chatbot not initialized")
        resp = MessagingResponse()
        resp.message("Service temporarily unavailable.")
        return Response(content=str(resp), media_type="application/xml")

    try:
        user_text = Body or ""
        
        # Handle Audio Media
        if MediaUrl0 and "audio" in MediaContentType0:
            import requests
            logger.info(f"Downloading audio from {MediaUrl0}")
            audio_response = requests.get(MediaUrl0)
            if audio_response.status_code == 200:
                logger.info("Transcribing audio...")
                transcribed_text = chatbot.transcribe_audio(audio_response.content)
                logger.info(f"Transcribed Text: {transcribed_text}")
                user_text = transcribed_text
            else:
                logger.error(f"Failed to download audio: {audio_response.status_code}")
                user_text = "[Error: Could not process audio message]"

        if not user_text and not MediaUrl0:
            resp = MessagingResponse()
            resp.message("I received an empty message. How can I help you?")
            return Response(content=str(resp), media_type="application/xml")

        # Get AI response with WhatsApp-specific constraint
        ai_response = chatbot.chat(f"{user_text}\n\n[Instruction: Keep your response under 1500 characters.]")
        
        # Create TwiML response
        resp = MessagingResponse()
        resp.message(ai_response)
        
        return Response(content=str(resp), media_type="application/xml")
    except Exception as e:
        logger.error(f"Error in whatsapp_webhook: {e}")
        resp = MessagingResponse()
        resp.message("Sorry, I encountered an error processing your message.")
        return Response(content=str(resp), media_type="application/xml")

# Serve static files (frontend) - MUST be last to not interfere with API routes
from pathlib import Path
frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"

logger.info(f"Checking for frontend at: {frontend_dist.absolute()}")

if frontend_dist.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")
    logger.info("Frontend dist found and mounted.")
else:
    logger.warning(f"Frontend dist NOT found at {frontend_dist.absolute()}. Only API will be available.")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
