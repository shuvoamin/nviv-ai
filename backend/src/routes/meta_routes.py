import os
import requests
from fastapi import APIRouter, Request, BackgroundTasks, Response
import app_state
from utils.image_utils import save_base64_image

router = APIRouter()

async def process_meta_background(body: dict, host_url: str):
    app_state.diag_logger.info("Meta background task starting...")
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
                            if audio_resp.status_code == 200: 
                                user_text = app_state.chatbot.transcribe_audio(audio_resp.content)
                    if user_text:
                        if user_text.lower().startswith("/image"):
                            prompt = user_text[7:].strip()
                            image_result = app_state.chatbot.generate_image(prompt)
                            image_url = save_base64_image(image_result, host_url)
                            send_meta_whatsapp_image(from_number, image_url)
                        else:
                            ai_response = await app_state.chatbot.chat(f"{user_text}\n\n[Instruction: Keep your response under 1500 characters.]")
                            send_meta_whatsapp_message(from_number, ai_response)
    except Exception as e: app_state.diag_logger.error(f"Error in Meta background task: {e}")

@router.get("/meta/webhook")
async def verify_meta_webhook(request: Request):
    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == os.getenv("WHATSAPP_VERIFY_TOKEN", "nviv_verify_token_jan_2026"):
        return Response(content=str(params.get("hub.challenge")), media_type="text/plain")
    return Response(content="Failed", status_code=403)

@router.post("/meta/webhook")
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
