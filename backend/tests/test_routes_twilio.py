import pytest
from unittest.mock import patch, MagicMock

def test_twilio_whatsapp_webhook_ack(client):
    """Verify that the Twilio webhook acknowledges messages immediately"""
    # Simulate a Form-encoded Twilio request
    payload = {
        "From": "whatsapp:+1234567890",
        "Body": "Hello"
    }
    # We mock the diagnostic logger to avoid unnecessary output in tests
    with patch('app_state.diag_logger'):
        response = client.post("/whatsapp", data=payload)
        
    assert response.status_code == 200
    assert "application/xml" in response.headers["content-type"]
    assert "<Response" in response.text

def test_twilio_status_callback(client):
    """Verify that the status callback endpoint accepts and logs data"""
    payload = {
        "MessageSid": "SM123",
        "MessageStatus": "delivered"
    }
    response = client.post("/twilio/status", data=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
