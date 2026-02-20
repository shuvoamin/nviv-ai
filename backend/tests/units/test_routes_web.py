import pytest
from unittest.mock import patch, MagicMock

def test_web_chat_endpoint(client, mock_chatbot):
    """Verify the /chat endpoint returns a valid AI response"""
    payload = {"message": "Hello bot", "reset": False}
    response = client.post("/chat", json=payload)
    
    assert response.status_code == 200
    assert "Mock AI Response" in response.json()["message"]



def test_get_image_not_found(client):
    """Verify that requesting a non-existent image returns a 404"""
    response = client.get("/static/generated_images/non-existent.jpg")
    assert response.status_code == 404

    response = client.get("/static/generated_images/non-existent.jpg")
    assert response.status_code == 404


def test_api_image_content_types(client):
    """Verify content type logic in api.py"""
    # We will patch 'api.FileResponse' and 'app_state.IMAGES_DIR'
    from api import get_image
    
    with patch('app_state.IMAGES_DIR') as mock_dir:
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_dir.__truediv__.return_value = mock_file
        
        with patch('api.FileResponse') as mock_file_resp:
            mock_file_resp.return_value = "Response"
            
            # Test png (default)
            request = MagicMock()
            import asyncio
            asyncio.run(get_image("test.png", request))
            assert mock_file_resp.call_args[1]['media_type'] == 'image/png'
            
            # Test jpg
            asyncio.run(get_image("test.jpg", request))
            assert mock_file_resp.call_args[1]['media_type'] == 'image/jpeg'
            
            # Test webp
            asyncio.run(get_image("test.webp", request))
            assert mock_file_resp.call_args[1]['media_type'] == 'image/webp'

def test_web_chat_unavailable(client):
    """Verify 503 when chatbot is not initialized"""
    with patch('app_state.chatbot', None):
        response = client.post("/chat", json={"message": "hello"})
        assert response.status_code == 503



def test_chat_endpoint_success(mock_chatbot, client):
    """Verify successful chat response."""
    response = client.post("/chat", json={"message": "hello", "session_id": "test_123"})
    assert response.status_code == 200
    assert response.json() == {"message": "Global Mock AI Response"}
    mock_chatbot.chat.assert_any_call("hello", thread_id="test_123")
    mock_chatbot.reset_history.assert_not_called()

def test_chat_endpoint_with_reset(mock_chatbot, client):
    """Verify chat endpoint with reset flag."""
    response = client.post("/chat", json={"message": "hello", "reset": True, "session_id": "test_123"})
    assert response.status_code == 200
    mock_chatbot.reset_history.assert_awaited_once_with("test_123")
    mock_chatbot.chat.assert_any_call("hello", thread_id="test_123")


