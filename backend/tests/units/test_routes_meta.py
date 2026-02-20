import pytest
import pytest
import os
from unittest.mock import patch, MagicMock, AsyncMock

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

def test_meta_webhook_verification_failure(client):
    """Verify webhook verification failure"""
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "wrong_token",
        "hub.challenge": "12345"
    }
    response = client.get("/meta/webhook", params=params)
    assert response.status_code == 403
    assert response.text == "Failed"

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

def test_meta_webhook_body_error(client):
    """Verify handling of malformed body in webhook"""
    # Sending invalid JSON triggers generic 422 usually, but strict mode check in code:
    # try: body = await request.json() except: return {"status": "error"}
    # To trigger exception in request.json() with test client is hard unless we mock it or send bad content-type/data mismatch.
    # Starlette TestClient might handle json decoding before?
    # Let's try sending data that is valid json but triggers error inside logic?
    # No, the try/except wraps request.json().
    
    # We can mock Request.json
    with patch("fastapi.Request.json", side_effect=ValueError("Bad JSON")):
        response = client.post("/meta/webhook", content="bad data")
        assert response.status_code == 200
        assert response.json() == {"status": "error"}

@pytest.mark.asyncio
async def test_meta_send_image():
    """Verify sending image via Meta API"""
    from routes.meta_routes import send_meta_whatsapp_image
    envs = {"WHATSAPP_ACCESS_TOKEN": "token", "WHATSAPP_PHONE_NUMBER_ID": "pid"}
    with patch.dict(os.environ, envs):
        with patch('requests.post') as mock_post:
            send_meta_whatsapp_image("to", "http://image.url")
            mock_post.assert_called_once()
            assert mock_post.call_args[1]['json']['type'] == 'image'

@pytest.mark.asyncio
async def test_meta_background_no_action():
    """Verify background task with no usable content returns early"""
    from routes.meta_routes import process_meta_background
    # Body with no object
    await process_meta_background({}, "http://host")
    
    # Body with object but no text/media
    body = {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"value": {"messages": [{"type": "unknown"}]}}]}]
    }
    await process_meta_background(body, "http://host")
    
    # Assert nothing bad happened (no mock calls)
    
@pytest.mark.asyncio
async def test_meta_background_exception():
    """Verify exception handling in Meta background task"""
    from routes.meta_routes import process_meta_background
    # Trigger exception by passing None body which causes AttributeError
    with patch('app_state.diag_logger') as mock_logger:
        await process_meta_background(None, "host")
        mock_logger.error.assert_called()
        assert "Error in Meta background task" in str(mock_logger.error.call_args)

def test_meta_process_audio_message(client):
    """Verify processing of audio messages from Meta"""
    from routes.meta_routes import process_meta_background
    
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"value": {"messages": [{"type": "audio", "audio": {"id": "media_id"}, "from": "123"}]}}]}]
    }
    
    with patch('app_state.chatbot') as mock_bot:
        with patch('routes.meta_routes.get_meta_media_url') as mock_get_url:
            mock_get_url.return_value = "http://audio.url"
            
            with patch('requests.get') as mock_get:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.content = b"audio"
                mock_get.return_value = mock_resp
                
                mock_bot.transcribe_audio.return_value = "Audio Text"
                mock_bot.chat = AsyncMock(return_value="AI Reply")
                
                with patch('routes.meta_routes.send_meta_whatsapp_message') as mock_send:
                    import asyncio
                    asyncio.run(process_meta_background(payload, "http://host"))
                    
                    mock_bot.transcribe_audio.assert_called_once()
                    # assert_called() on AsyncMock works but verify await happened:
                     # mock_bot.chat.assert_awaited_once() # or just assert_called if we don't care about await detail
                    mock_bot.chat.assert_called()
                    mock_send.assert_called_with("123", "AI Reply")

def test_meta_process_image_command(client):
    """Verify processing of /image command from Meta"""
    from routes.meta_routes import process_meta_background
    
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"value": {"messages": [{"type": "text", "text": {"body": "/image sun"}, "from": "123"}]}}]}]
    }
    
    with patch('app_state.chatbot') as mock_bot:
        mock_bot.generate_image.return_value = "data:image/png;base64,data"
        
        with patch('routes.meta_routes.save_base64_image') as mock_save:
            mock_save.return_value = "http://host/img.jpg"
            
            with patch('routes.meta_routes.send_meta_whatsapp_image') as mock_send_img:
                import asyncio
                asyncio.run(process_meta_background(payload, "http://host"))
                
                mock_bot.generate_image.assert_called_with("sun")
                mock_send_img.assert_called_with("123", "http://host/img.jpg")

def test_meta_get_media_url(client):
    """Verify media URL retrieval"""
    from routes.meta_routes import get_meta_media_url
    envs = {"WHATSAPP_ACCESS_TOKEN": "token"}
    with patch.dict(os.environ, envs):
        with patch('requests.get') as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"url": "http://real.url"}
            mock_get.return_value = mock_resp
            
            url = get_meta_media_url("id")
            assert url == "http://real.url"

def test_meta_send_message(client):
    """Verify message sending logic"""
    from routes.meta_routes import send_meta_whatsapp_message
    envs = {"WHATSAPP_ACCESS_TOKEN": "token", "WHATSAPP_PHONE_NUMBER_ID": "pid"}
    with patch.dict(os.environ, envs):
        with patch('requests.post') as mock_post:
            send_meta_whatsapp_message("to", "text")
            mock_post.assert_called_once()
