import os
import requests
from fastapi import APIRouter, Request, Form, Response, BackgroundTasks
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client as TwilioClient
import app_state
from utils.image_utils import save_base64_image

router = APIRouter()

async def process_twilio_background(body: str, from_number: str, media_url: str, media_type: str, host_url: str):
    app_state.diag_logger.info(f"Starting Twilio background task for {from_number}")
    try:
        user_text = body or ""
        if media_url and "audio" in media_type:
            audio_response = requests.get(media_url)
            if audio_response.status_code == 200:
                user_text = app_state.chatbot.transcribe_audio(audio_response.content)
        if not user_text and not media_url:
            return
        if user_text.lower().startswith("/image"):
            prompt = user_text[7:].strip()
            if prompt:
                image_result = app_state.chatbot.generate_image(prompt)
                image_url = save_base64_image(image_result, host_url)
                # Media-only message for cleaner UX
                send_twilio_reply(from_number, "", image_url)
                return
        ai_response = await app_state.chatbot.chat(f"{user_text}\n\n[Instruction: Keep your response under 1500 characters.]")
        send_twilio_reply(from_number, ai_response)
    except Exception as e:
        app_state.diag_logger.error(f"Error in Twilio background task: {e}")
        send_twilio_reply(from_number, "Sorry, I encountered an error processing your query.")

def send_twilio_reply(to_number: str, message_text: str, image_url: str = None):
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")
    if not all([account_sid, auth_token, from_number]):
        app_state.diag_logger.error("CRITICAL: Twilio credentials missing!")
        return
    try:
        client = TwilioClient(account_sid, auth_token)
        params = {"from_": from_number, "to": to_number}
        if message_text:
            params["body"] = message_text
        if image_url:
            app_state.diag_logger.info(f"Adding media_url to Twilio params: {image_url}")
            params["media_url"] = [image_url]
            
        host_url = os.getenv("BASE_URL", "").rstrip("/")
        if host_url:
            if "azurewebsites.net" in host_url and not host_url.startswith("https"):
                host_url = host_url.replace("http://", "https://")
            params["status_callback"] = f"{host_url}/twilio/status"
            
        msg_instance = client.messages.create(**params)
        app_state.diag_logger.info(f"Twilio background reply sent. SID: {msg_instance.sid}, Status: {msg_instance.status}")
    except Exception as e:
        app_state.diag_logger.error(f"Failed to send Twilio outbound: {str(e)}")

@router.post("/whatsapp")
async def whatsapp_webhook(background_tasks: BackgroundTasks, request: Request, Body: str = Form(None), From: str = Form(...), MediaUrl0: str = Form(None), MediaContentType0: str = Form(None)):
    app_state.diag_logger.info(f"Received Twilio message from {From}")
    host_url = f"{request.url.scheme}://{request.url.netloc}"
    if "azurewebsites.net" in host_url: host_url = host_url.replace("http://", "https://")
    background_tasks.add_task(process_twilio_background, Body, From, MediaUrl0, MediaContentType0, host_url)
    return Response(content=str(MessagingResponse()), media_type="application/xml")

@router.post("/twilio/status")
async def twilio_status_callback(request: Request):
    form_data = await request.form()
    sid = form_data.get("MessageSid")
    status = form_data.get("SmsStatus") or form_data.get("MessageStatus")
    error_code = form_data.get("ErrorCode")
    msg = f"Twilio Status Callback: SID={sid}, Status={status}"
    if error_code: msg += f", ERROR_CODE={error_code}"
    if status in ["failed", "undelivered"]: app_state.diag_logger.error(msg)
    else: app_state.diag_logger.info(msg)
    return {"status": "ok"}
