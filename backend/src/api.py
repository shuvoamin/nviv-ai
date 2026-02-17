import os
import sys
import uvicorn
from fastapi import FastAPI, HTTPException, Form, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from twilio.twiml.messaging_response import MessagingResponse
import requests
import base64
import uuid
from pathlib import Path
from fastapi.staticfiles import StaticFiles

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

# --- Image Hosting Setup ---
# Create static/images directory
STATIC_DIR = Path(__file__).parent.parent / "static"
IMAGES_DIR = STATIC_DIR / "generated_images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# Mount static folder
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

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
        # Ensure base_url doesn't have double slashes
        public_url = f"{str(base_url).rstrip('/')}/static/generated_images/{filename}"
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

@app.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
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

        if user_text.lower().startswith("/image"):
            prompt = user_text[7:].strip()
            if prompt:
                logger.info(f"Generating image for Twilio: {prompt}")
                # We need the base URL for the public link
                # Twilio doesn't provide a direct way to get our own URL, but we can infer it or use an env var
                # For now, we'll try to use the request host
                host_url = f"{request.url.scheme}://{request.url.netloc}"
                image_result = chatbot.generate_image(prompt)
                image_url = save_base64_image(image_result, host_url)
                
                resp = MessagingResponse()
                msg = resp.message("Here is your generated image!")
                msg.media(image_url)
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

# --- Native Meta WhatsApp Webhook ---

@app.get("/meta/webhook")
async def verify_meta_webhook(request: Request):
    """
    Handle Meta's webhook verification (GET request).
    Meta sends a challenge to verify this server.
    """
    params = request.query_params
    logger.info(f"Meta Verification Attempt: {params}")
    
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    # Use the token provided by the user
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "nviv_verify_token_jan_2026")

    if mode == "subscribe" and token == verify_token:
        logger.info("Meta Webhook verified successfully!")
        # IMPORTANT: Response must be raw plain text (no JSON quotes)
        return Response(content=str(challenge), media_type="text/plain")
    
    logger.warning(f"Meta Webhook verification failed. Expected: {verify_token}, Received: {token}")
    return Response(content="Verification failed", status_code=403)

@app.post("/meta/webhook")
async def meta_webhook(request: Request):
    """
    Handle incoming WhatsApp messages from Meta (POST request).
    """
    try:
        body = await request.json()
        logger.info(f"Received Meta Webhook event: {body}")
    except Exception as e:
        logger.error(f"Failed to parse Meta JSON: {e}")
        return {"status": "error"}

    # Check if this is a WhatsApp message
    if body.get("object") == "whatsapp_business_account":
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                
                if messages:
                    message = messages[0]
                    from_number = message.get("from")
                    
                    # Handle Text Messages
                    user_text = ""
                    if message.get("type") == "text":
                        user_text = message.get("text", {}).get("body", "")
                        logger.info(f"Processing text message from {from_number}: {user_text}")
                    
                    # Handle Audio Messages (Whisper)
                    elif message.get("type") == "audio":
                        audio = message.get("audio", {})
                        media_id = audio.get("id")
                        logger.info(f"Processing audio message from {from_number}, ID: {media_id}")
                        
                        audio_url = get_meta_media_url(media_id)
                        if audio_url:
                            audio_resp = requests.get(audio_url, headers={"Authorization": f"Bearer {os.getenv('WHATSAPP_ACCESS_TOKEN')}"})
                            if audio_resp.status_code == 200:
                                transcribed_text = chatbot.transcribe_audio(audio_resp.content)
                                logger.info(f"Transcribed Text: {transcribed_text}")
                                user_text = transcribed_text
                            else:
                                logger.error(f"Failed to download audio: {audio_resp.status_code}")
                    
                    if user_text:
                        # Detect image request
                        if user_text.lower().startswith("/image"):
                            prompt = user_text[7:].strip()
                            if prompt:
                                logger.info(f"Generating image for Meta: {prompt}")
                                try:
                                    # Use host from request
                                    host_url = f"{request.url.scheme}://{request.url.netloc}"
                                    image_result = chatbot.generate_image(prompt)
                                    image_url = save_base64_image(image_result, host_url)
                                    send_meta_whatsapp_image(from_number, image_url)
                                except Exception as e:
                                    logger.error(f"Meta image gen failed: {e}")
                                    send_meta_whatsapp_message(from_number, "Sorry, I couldn't generate that image.")
                        else:
                            # Get AI response
                            ai_response = chatbot.chat(f"{user_text}\n\n[Instruction: Keep your response under 1500 characters.]")
                            logger.info(f"AI Response generated. Sending to {from_number}...")
                            
                            # Send back via Meta Graph API
                            send_meta_whatsapp_message(from_number, ai_response)
                    else:
                        logger.warning(f"No processable text or audio found in message from {from_number}")
                        
    return {"status": "ok"}

def get_meta_media_url(media_id):
    """Helper to get the actual download URL for a media ID from Meta."""
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    if not access_token:
        logger.error("WHATSAPP_ACCESS_TOKEN missing while trying to get media URL")
        return None
        
    url = f"https://graph.facebook.com/v18.0/{media_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return resp.json().get("url")
    logger.error(f"Failed to get media URL from Meta: {resp.text}")
    return None

def send_meta_whatsapp_message(to_number, message_text):
    """Helper to send a message via Meta's Graph API."""
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    
    if not access_token or not phone_number_id:
        logger.error(f"Meta credentials missing. Token present: {bool(access_token)}, ID present: {bool(phone_number_id)}")
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
    
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code == 200:
        logger.info(f"Message sent to {to_number} successfully.")
    else:
        logger.error(f"Failed to send Meta message back to {to_number}. Status: {resp.status_code}, Error: {resp.text}")

def send_meta_whatsapp_image(to_number, image_url):
    """Helper to send an image via Meta's Graph API."""
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    
    if not access_token or not phone_number_id:
        logger.error("Meta credentials missing for image sending.")
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
    
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code == 200:
        logger.info(f"Image sent to {to_number} successfully.")
    else:
        logger.error(f"Failed to send Meta image: {resp.text}")

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
