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
from fastapi.responses import FileResponse

# Add the current directory to sys.path to allow importing local modules
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

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Image Hosting Setup ---
STATIC_DIR = Path(__file__).parent.parent / "static"
IMAGES_DIR = STATIC_DIR / "generated_images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

@app.get("/static/generated_images/{filename}")
async def get_image(filename: str, request: Request):
    """Serve images with explicit headers and diagnostic logging"""
    filepath = IMAGES_DIR / filename
    ua = request.headers.get("user-agent", "Unknown")
    
    if not filepath.exists():
        diag_logger.error(f"Image 404: {filename} requested by {ua}")
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Force explicit media type based on extension
    media_type = "image/png"
    if filename.endswith((".jpg", ".jpeg")):
        media_type = "image/jpeg"
    elif filename.endswith(".webp"):
        media_type = "image/webp"
        
    diag_logger.info(f"Image fetched: {filename} by {ua}. Content-Type: {media_type}")
    return FileResponse(filepath, media_type=media_type)

def save_base64_image(image_data: str, base_url: str) -> str:
    if not image_data.startswith("data:image"):
        return image_data
    try:
        header, encoded = image_data.split(",", 1)
        ext = "png"
        if "jpeg" in header: ext = "jpg"
        elif "webp" in header: ext = "webp"
        filename = f"{uuid.uuid4()}.{ext}"
        filepath = IMAGES_DIR / filename
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(encoded))
        filesize_kb = filepath.stat().st_size / 1024
        diag_logger.info(f"Image saved: {filename} ({filesize_kb:.2f} KB)")
        url_str = str(base_url).rstrip('/')
        if "azurewebsites.net" in url_str and not url_str.startswith("https"):
            url_str = url_str.replace("http://", "https://")
        public_url = f"{url_str}/static/generated_images/{filename}"
        diag_logger.info(f"Image saved locally: {public_url}")
        return public_url
    except Exception as e:
        diag_logger.error(f"Failed to save base64 image: {e}")
        return image_data

class ChatRequest(BaseModel):
    message: str
    reset: bool = False

class ChatResponse(BaseModel):
    message: str

class ImageRequest(BaseModel):
    prompt: str

class ImageResponse(BaseModel):
    url: str

try:
    chatbot = ChatBot()
    diag_logger.info("ChatBot initialized successfully.")
except Exception as e:
    diag_logger.error(f"Failed to initialize ChatBot: {e}")
    chatbot = None

# --- Background Task Helpers ---

async def process_twilio_background(body: str, from_number: str, media_url: str, media_type: str, host_url: str):
    diag_logger.info(f"Starting Twilio background task for {from_number}")
    try:
        user_text = body or ""
        if media_url and "audio" in media_type:
            audio_response = requests.get(media_url)
            if audio_response.status_code == 200:
                user_text = chatbot.transcribe_audio(audio_response.content)
        if not user_text and not media_url:
            return
        if user_text.lower().startswith("/image"):
            prompt = user_text[7:].strip()
            if prompt:
                image_result = chatbot.generate_image(prompt)
                image_url = save_base64_image(image_result, host_url)
                # TEST: Split text and image into two messages to avoid 63019 caption conflict
                send_twilio_reply(from_number, "Here is your generated image!")
                send_twilio_reply(from_number, "", image_url)
                return
        ai_response = chatbot.chat(f"{user_text}\n\n[Instruction: Keep your response under 1500 characters.]")
        send_twilio_reply(from_number, ai_response)
    except Exception as e:
        diag_logger.error(f"Error in Twilio background task: {e}")
        send_twilio_reply(from_number, "Sorry, I encountered an error processing your query.")

def send_twilio_reply(to_number: str, message_text: str, image_url: str = None):
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")
    if not all([account_sid, auth_token, from_number]):
        diag_logger.error("CRITICAL: Twilio credentials missing!")
        return
    try:
        client = TwilioClient(account_sid, auth_token)
        # Build params
        params = {"from_": from_number, "to": to_number}
        if message_text:
            params["body"] = message_text
        if image_url:
            diag_logger.info(f"Adding media_url to Twilio params: {image_url}")
            params["media_url"] = [image_url]
        # Add status callback to track delivery failures
        host_url = os.getenv("BASE_URL", "").rstrip("/")
        if host_url:
            if "azurewebsites.net" in host_url and not host_url.startswith("https"):
                host_url = host_url.replace("http://", "https://")
            params["status_callback"] = f"{host_url}/twilio/status"
        msg_instance = client.messages.create(**params)
        diag_logger.info(f"Twilio background reply sent. SID: {msg_instance.sid}, Status: {msg_instance.status}")
    except Exception as e:
        diag_logger.error(f"Failed to send Twilio outbound: {str(e)}")

async def process_meta_background(body: dict, host_url: str):
    diag_logger.info("Meta background task starting...")
    try:
        if body.get("object") != "whatsapp_business_account": return
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for message in value.get("messages", []):
                    from_number = message.get("from")
                    user_text = ""
                    if message.get("type") == "text": user_text = message.get("text", {}).get("body", "")
                    elif message.get("type") == "audio":
                        audio_url = get_meta_media_url(message.get("audio", {}).get("id"))
                        if audio_url:
                            token = os.getenv('WHATSAPP_ACCESS_TOKEN')
                            audio_resp = requests.get(audio_url, headers={"Authorization": f"Bearer {token}"})
                            if audio_resp.status_code == 200: user_text = chatbot.transcribe_audio(audio_resp.content)
                    if user_text:
                        if user_text.lower().startswith("/image"):
                            prompt = user_text[7:].strip()
                            image_result = chatbot.generate_image(prompt)
                            image_url = save_base64_image(image_result, host_url)
                            send_meta_whatsapp_image(from_number, image_url)
                        else:
                            ai_response = chatbot.chat(f"{user_text}\n\n[Instruction: Keep your response under 1500 characters.]")
                            send_meta_whatsapp_message(from_number, ai_response)
    except Exception as e: diag_logger.error(f"Error in Meta background task: {e}")

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    if chatbot is None: raise HTTPException(status_code=503, detail="Service unavailable")
    if request.reset: chatbot.reset_history()
    return ChatResponse(message=chatbot.chat(request.message))

@app.post("/generate-image", response_model=ImageResponse)
async def generate_image_endpoint(request: ImageRequest, api_request: Request):
    if chatbot is None: raise HTTPException(status_code=503, detail="Service unavailable")
    try:
        image_result = chatbot.generate_image(request.prompt)
        image_url = save_base64_image(image_result, api_request.base_url)
        return ImageResponse(url=image_url)
    except Exception as e:
        diag_logger.error(f"Image generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check(): return {"status": "ok"}

@app.get("/debug-logs")
async def debug_logs():
    logs_html = "<html><head><title>Nviv Debug Logs</title><style>body{font-family:monospace;background:#1e1e1e;color:#d4d4d4;padding:20px;} li{margin-bottom:5px;border-bottom:1px solid #333;padding-bottom:5px;}</style></head><body>"
    logs_html += "<h1>System Diagnostic Logs (Last 100)</h1><ul>"
    for entry in reversed(list(LOG_BUFFER)):
        color = "#ff4444" if "ERROR" in entry else "#ffbb33" if "WARNING" in entry else "#d4d4d4"
        logs_html += f"<li style='color:{color}'>{entry}</li>"
    return Response(content=logs_html + "</ul></body></html>", media_type="text/html")

@app.post("/whatsapp")
async def whatsapp_webhook(background_tasks: BackgroundTasks, request: Request, Body: str = Form(None), From: str = Form(...), MediaUrl0: str = Form(None), MediaContentType0: str = Form(None)):
    diag_logger.info(f"Received Twilio message from {From}")
    host_url = f"{request.url.scheme}://{request.url.netloc}"
    if "azurewebsites.net" in host_url: host_url = host_url.replace("http://", "https://")
    background_tasks.add_task(process_twilio_background, Body, From, MediaUrl0, MediaContentType0, host_url)
    return Response(content=str(MessagingResponse()), media_type="application/xml")

@app.post("/twilio/status")
async def twilio_status_callback(request: Request):
    form_data = await request.form()
    sid = form_data.get("MessageSid")
    status = form_data.get("SmsStatus") or form_data.get("MessageStatus")
    error_code = form_data.get("ErrorCode")
    msg = f"Twilio Status Callback: SID={sid}, Status={status}"
    if error_code: msg += f", ERROR_CODE={error_code}"
    if status in ["failed", "undelivered"]: diag_logger.error(msg)
    else: diag_logger.info(msg)
    return {"status": "ok"}

@app.get("/meta/webhook")
async def verify_meta_webhook(request: Request):
    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == os.getenv("WHATSAPP_VERIFY_TOKEN", "nviv_verify_token_jan_2026"):
        return Response(content=str(params.get("hub.challenge")), media_type="text/plain")
    return Response(content="Failed", status_code=403)

@app.post("/meta/webhook")
async def meta_webhook(request: Request, background_tasks: BackgroundTasks):
    try: body = await request.json()
    except: return {"status": "error"}
    host_url = f"{request.url.scheme}://{request.url.netloc}"
    if "azurewebsites.net" in host_url: host_url = host_url.replace("http://", "https://")
    background_tasks.add_task(process_meta_background, body, host_url)
    return {"status": "ok"}

def get_meta_media_url(media_id):
    token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    if not token: return None
    resp = requests.get(f"https://graph.facebook.com/v18.0/{media_id}", headers={"Authorization": f"Bearer {token}"})
    return resp.json().get("url") if resp.status_code == 200 else None

def send_meta_whatsapp_message(to_number, text):
    token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    pid = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    if token and pid: requests.post(f"https://graph.facebook.com/v18.0/{pid}/messages", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json={"messaging_product": "whatsapp", "to": to_number, "type": "text", "text": {"body": text}})

def send_meta_whatsapp_image(to_number, url):
    token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    pid = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    if token and pid: requests.post(f"https://graph.facebook.com/v18.0/{pid}/messages", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json={"messaging_product": "whatsapp", "to": to_number, "type": "image", "image": {"link": url}})

frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
