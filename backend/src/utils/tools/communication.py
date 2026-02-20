import os
import requests
from twilio.rest import Client as TwilioClient

def send_twilio_sms(to_number: str, message_body: str) -> str:
    """
    Sends an SMS message using Twilio.
    
    Args:
        to_number: The phone number to send the SMS to (E.164 format).
        message_body: The content of the SMS message.
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")
    
    if not all([account_sid, auth_token, from_number]):
        return "Error: specific Twilio credentials (ACCOUNT_SID, AUTH_TOKEN, FROM_NUMBER) are missing."

    try:
        client = TwilioClient(account_sid, auth_token)
        message = client.messages.create(
            body=message_body,
            from_=from_number,
            to=to_number
        )
        return f"Twilio SMS sent successfully. SID: {message.sid}"
    except Exception as e:
        return f"Error sending Twilio SMS: {str(e)}"

def send_whatsapp_message(to_number: str, message_body: str) -> str:
    """
    Sends a WhatsApp message using Meta's WhatsApp API.
    
    Args:
        to_number: The phone number to send the message to.
        message_body: The content of the message.
    """
    token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    pid = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    
    if not token or not pid:
        return "Error: Meta WhatsApp credentials (WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID) are missing."

    url = f"https://graph.facebook.com/v18.0/{pid}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message_body}
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return f"WhatsApp message sent successfully. Response: {response.json()}"
    except Exception as e:
        return f"Error sending WhatsApp message: {str(e)}"
