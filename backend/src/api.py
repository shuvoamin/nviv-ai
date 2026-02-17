import os
import sys
import uvicorn
from fastapi import FastAPI, HTTPException, Form, Response, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client as TwilioClient
import requests
import base64
import uuid
from fastapi.staticfiles import StaticFiles

# Add the current directory to sys.path to allow importing local modules
# This helps when the script is run from different working directories
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from chatbot import ChatBot
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- In-Memory Diagnostic Logging ---
from collections import deque
from datetime import datetime
LOG_BUFFER = deque(maxlen=100)

class DiagnosticLogger:
    def info(self, msg):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        LOG_BUFFER.append(f"[{timestamp}] INFO: {msg}")
        logger.info(msg)
    
    def error(self, msg):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        LOG_BUFFER.append(f"[{timestamp}] ERROR: {msg}")
        logger.error(msg)
    
    def warning(self, msg):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        LOG_BUFFER.append(f"[{timestamp}] WARNING: {msg}")
        logger.warning(msg)

diag_logger = DiagnosticLogger()

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

# --- Image Hosting Setup ---
# Create static/images directory
STATIC_DIR = Path(__file__).parent.parent / "static"
IMAGES_DIR = STATIC_DIR / "generated_images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# Mount static folder
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="images")

def save_base64_image(image_data: str, base_url: str) -> str:
    """
    Saves a base64 Data URI to a file and returns the public URL.
    Input: "data:image/png;base64,iVBOR..."
    Output: "https://.../static/generated_images/uuid.png"
    """
    if not image_data.startswith("data:image"):
        return image_data # Already a URL?

    try:
        # Extract base64 part
        header, encoded = image_data.split(",", 1)
        # Determine extension
        ext = "png"
        if "jpeg" in header: ext = "jpg"
        elif "webp" in header: ext = "webp"
        
        filename = f"{uuid.uuid4()}.{ext}"
        filepath = IMAGES_DIR / filename
        
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(encoded))
            
        # Construct public URL
        # Robustly handle schemes (especially for Azure)
        url_str = str(base_url).rstrip('/')
        if "azurewebsites.net" in url_str and not url_str.startswith("https"):
            url_str = url_str.replace("http://", "https://")
            
        public_url = f"{url_str}/static/generated_images/{filename}"
        logger.info(f"Image saved locally: {public_url}")
        return public_url
    except Exception as e:
        logger.error(f"Failed to save base64 image: {e}")
        return image_data # Fallback to original

class ChatRequest(BaseModel):
    message: str
    reset: bool = False

class ChatResponse(BaseModel):
    message: str

class ImageRequest(BaseModel):
    prompt: str

class ImageResponse(BaseModel):
    url: str

# Initialize chatbot
try:
    chatbot = ChatBot()
    logger.info("ChatBot initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize ChatBot: {e}")
    chatbot = None

# --- Background Task Helpers ---

async def process_twilio_background(body: str, from_number: str, media_url: str, media_type: str, host_url: str):
    """Processes Twilio message in background and sends reply via REST API"""
    diag_logger.info(f"Starting Twilio background task for {from_number}")
    try:
        user_text = body or ""
        
        # Handle Audio
        if media_url and "audio" in media_type:
            audio_response = requests.get(media_url)
            if audio_response.status_code == 200:
                user_text = chatbot.transcribe_audio(audio_response.content)
        
        if not user_text and not media_url:
            return

        # Handle Image Request
        if user_text.lower().startswith("/image"):
            prompt = user_text[7:].strip()
            if prompt:
                image_result = chatbot.generate_image(prompt)
                image_url = save_base64_image(image_result, host_url)
                send_twilio_reply(from_number, "Here is your generated image!", image_url)
                return

        # Standard Chat
        ai_response = chatbot.chat(f"{user_text}\n\n[Instruction: Keep your response under 1500 characters.]")
        send_twilio_reply(from_number, ai_response)
        
    except Exception as e:
        logger.error(f"Error in Twilio background task: {e}")
        send_twilio_reply(from_number, "Sorry, I encountered an error processing your query.")

def send_twilio_reply(to_number: str, message_text: str, image_url: str = None):
    """Sends an outbound message using Twilio Client"""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER") # e.g. whatsapp:+14155238886

    if not all([account_sid, auth_token, from_number]):
        msg = "CRITICAL: Twilio credentials (SID, Token, or FromNumber) are missing in environment variables! Messaging will not work."
        diag_logger.error(msg)
        return

    try:
        client = TwilioClient(account_sid, auth_token)
        params = {
            "from_": from_number,
            "to": to_number,
            "body": message_text
        }
        if image_url:
            diag_logger.info(f"Adding media_url to Twilio params: {image_url}")
            params["media_url"] = [image_url]
            
        client.messages.create(**params)
        diag_logger.info(f"Twilio background reply sent to {to_number}")
    except Exception as e:
        diag_logger.error(f"Failed to send Twilio outbound: {e}")

async def process_meta_background(body: dict, host_url: str):
    """Processes Meta event in background"""
    diag_logger.info("Meta background task starting...")
    try:
        diag_logger.info(f"Meta event object: {body.get('object')}")
        
        if body.get("object") != "whatsapp_business_account":
            diag_logger.warning(f"Meta event object is not 'whatsapp_business_account'. Skipping. (Found: {body.get('object')})")
            return

        for entry_idx, entry in enumerate(body.get("entry", [])):
            diag_logger.info(f"Processing entry {entry_idx}")
            for change_idx, change in enumerate(entry.get("changes", [])):
                value = change.get("value", {})
                messages = value.get("messages", [])
                diag_logger.info(f"Entry {entry_idx}, Change {change_idx} has {len(messages)} messages")
                
                if messages:
                    message = messages[0]
                    from_number = message.get("from")
                    diag_logger.info(f"New message from {from_number} (Type: {message.get('type')})")
                    from_number = message.get("from")
                    user_text = ""
                    
                    if message.get("type") == "text":
                        user_text = message.get("text", {}).get("body", "")
                        diag_logger.info(f"Extracted user text: '{user_text}'")
                    elif message.get("type") == "audio":
                        audio = message.get("audio", {})
                        media_id = audio.get("id")
                        audio_url = get_meta_media_url(media_id)
                        if audio_url:
                            token = os.getenv('WHATSAPP_ACCESS_TOKEN')
                            audio_resp = requests.get(audio_url, headers={"Authorization": f"Bearer {token}"})
                            if audio_resp.status_code == 200:
                                user_text = chatbot.transcribe_audio(audio_resp.content)

                    if user_text:
                        if chatbot is None:
                            diag_logger.error("Chatbot is not initialized. Cannot process message.")
                            send_meta_whatsapp_message(from_number, "Service temporarily unavailable.")
                            return

                        if user_text.lower().startswith("/image"):
                            prompt = user_text[7:].strip()
                            if prompt:
                                image_result = chatbot.generate_image(prompt)
                                image_url = save_base64_image(image_result, host_url)
                                send_meta_whatsapp_image(from_number, image_url)
                        else:
                            diag_logger.info("Calling chatbot.chat...")
                            ai_response = chatbot.chat(f"{user_text}\n\n[Instruction: Keep your response under 1500 characters.]")
                            diag_logger.info(f"AI Response generated: {ai_response[:50]}...")
                            send_meta_whatsapp_message(from_number, ai_response)
    except Exception as e:
        diag_logger.error(f"Error in Meta background task: {e}")

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    if chatbot is None:
        raise HTTPException(status_code=503, detail="Chatbot service not available (check configuration)")

    if request.reset:
        chatbot.reset_history()
    
    response = chatbot.chat(request.message)
    return ChatResponse(message=response)

@app.post("/generate-image", response_model=ImageResponse)
async def generate_image_endpoint(request: ImageRequest, api_request: Request):
    if chatbot is None:
        raise HTTPException(status_code=503, detail="Chatbot service not available")
    
    try:
        image_result = chatbot.generate_image(request.prompt)
        # Convert base64 to public URL for WhatsApp/Web consistency
        image_url = save_base64_image(image_result, api_request.base_url)
        return ImageResponse(url=image_url)
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/debug-logs")
async def debug_logs():
    """Returns the last 100 log entries as a simple HTML list"""
    logs_html = "<html><head><title>Nviv Debug Logs</title><style>body{font-family:monospace;background:#1e1e1e;color:#d4d4d4;padding:20px;} li{margin-bottom:5px;border-bottom:1px solid #333;padding-bottom:5px;}</style></head><body>"
    logs_html += "<h1>System Diagnostic Logs (Last 100)</h1><ul>"
    
    reversed_logs = list(LOG_BUFFER)
    reversed_logs.reverse()
    
    for entry in reversed_logs:
        color = "#ff4444" if "ERROR" in entry else "#ffbb33" if "WARNING" in entry else "#d4d4d4"
        logs_html += f"<li style='color:{color}'>{entry}</li>"
    
    logs_html += "</ul></body></html>"
    return Response(content=logs_html, media_type="text/html")

@app.post("/whatsapp")
async def whatsapp_webhook(
    background_tasks: BackgroundTasks,
    request: Request,
    Body: str = Form(None), 
    From: str = Form(...),
    MediaUrl0: str = Form(None),
    MediaContentType0: str = Form(None)
):
    diag_logger.info(f"Received Twilio WhatsApp message from {From}. (Acknowledging immediately)")
    
    if chatbot is None:
        resp = MessagingResponse()
        resp.message("Service temporarily unavailable.")
        return Response(content=str(resp), media_type="application/xml")

    # Add processing to background tasks
    # Ensure we use https if we are on Azure
    host_url = f"{request.url.scheme}://{request.url.netloc}"
    if "azurewebsites.net" in host_url:
        host_url = host_url.replace("http://", "https://")
        
    background_tasks.add_task(process_twilio_background, Body, From, MediaUrl0, MediaContentType0, host_url)

    return Response(content=str(MessagingResponse()), media_type="application/xml")

# --- Native Meta WhatsApp Webhook ---

@app.get("/meta/webhook")
async def verify_meta_webhook(request: Request):
    """
    Handle Meta's webhook verification (GET request).
    Meta sends a challenge to verify this server.
    """
    params = request.query_params
    diag_logger.info(f"Meta Verification Attempt: {params}")
    
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    # Use the token provided by the user
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "nviv_verify_token_jan_2026")

    if mode == "subscribe" and token == verify_token:
        diag_logger.info("Meta Webhook verified successfully!")
        # IMPORTANT: Response must be raw plain text (no JSON quotes)
        return Response(content=str(challenge), media_type="text/plain")
    
    diag_logger.warning(f"Meta Webhook verification failed. Expected: {verify_token}, Received: {token}")
    return Response(content="Verification failed", status_code=403)

@app.post("/meta/webhook")
async def meta_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Handle incoming WhatsApp messages from Meta (POST request).
    """
    try:
        body = await request.json()
        diag_logger.info(f"Received Meta Webhook event. (Acknowledging immediately)")
    except Exception as e:
        diag_logger.error(f"Failed to parse Meta JSON: {e}")
        return {"status": "error"}

    # Add to background tasks
    if chatbot is None:
        diag_logger.warning("Chatbot not initialized in Meta webhook, but proceeding to background task for diagnostic logging.")
        
    host_url = f"{request.url.scheme}://{request.url.netloc}"
    if "azurewebsites.net" in host_url:
        host_url = host_url.replace("http://", "https://")
        
    background_tasks.add_task(process_meta_background, body, host_url)
                        
    return {"status": "ok"}

def get_meta_media_url(media_id):
    """Helper to get the actual download URL for a media ID from Meta."""
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    if not access_token:
        diag_logger.error("WHATSAPP_ACCESS_TOKEN missing while trying to get media URL")
        return None
        
    url = f"https://graph.facebook.com/v18.0/{media_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return resp.json().get("url")
    diag_logger.error(f"Failed to get media URL from Meta: {resp.text}")
    return None

def send_meta_whatsapp_message(to_number, message_text):
    """Helper to send a message via Meta's Graph API."""
    diag_logger.info(f"Attempting to send Meta message to {to_number}...")
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    
    if not access_token or not phone_number_id:
        diag_logger.error(f"Meta credentials missing. Token present: {bool(access_token)}, ID present: {bool(phone_number_id)}")
        return

    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message_text}
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload)
        if resp.status_code == 200:
            diag_logger.info(f"Message sent to {to_number} successfully.")
        else:
            diag_logger.error(f"Failed to send Meta message back to {to_number}. Status: {resp.status_code}, Error: {resp.text}")
    except Exception as e:
        diag_logger.error(f"Exception during Meta send: {e}")

def send_meta_whatsapp_image(to_number, image_url):
    """Helper to send an image via Meta's Graph API."""
    diag_logger.info(f"Attempting to send Meta image to {to_number}...")
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    
    if not access_token or not phone_number_id:
        diag_logger.error("Meta credentials missing for image sending.")
        return

    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "image",
        "image": {"link": image_url}
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload)
        if resp.status_code == 200:
            diag_logger.info(f"Image sent to {to_number} successfully.")
        else:
            diag_logger.error(f"Failed to send Meta image back to {to_number}. Status: {resp.status_code}, Error: {resp.text}")
    except Exception as e:
        diag_logger.error(f"Exception during Meta image send: {e}")

# Serve static files (frontend) - MUST be last to not interfere with API routes
from pathlib import Path
frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"

diag_logger.info(f"Checking for frontend at: {frontend_dist.absolute()}")

if frontend_dist.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")
    diag_logger.info("Frontend dist found and mounted.")
else:
    diag_logger.warning(f"Frontend dist NOT found at {frontend_dist.absolute()}. Only API will be available.")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
