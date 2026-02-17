import pytest
from unittest.mock import patch, MagicMock

def test_meta_webhook_verification(client):
    """Verify that the Meta webhook challenge logic works"""
    # Using the default verify token if not set in env
    verify_token = "nviv_verify_token_jan_2026"
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": verify_token,
        "hub.challenge": "123456789"
    }
    response = client.get("/meta/webhook", params=params)
    
    assert response.status_code == 200
    assert response.text == "123456789"

def test_meta_webhook_invalid_verification(client):
    """Verify that invalid verification tokens are rejected"""
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "wrong_token",
        "hub.challenge": "123456789"
    }
    response = client.get("/meta/webhook", params=params)
    assert response.status_code == 403

def test_meta_webhook_post_ack(client):
    """Verify that the Meta POST webhook acknowledges messages"""
    payload = {
        "object": "whatsapp_business_account",
        "entry": []
    }
    response = client.post("/meta/webhook", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
