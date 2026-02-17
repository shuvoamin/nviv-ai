import pytest

def test_web_chat_endpoint(client, mock_chatbot):
    """Verify the /chat endpoint returns a valid AI response"""
    payload = {"message": "Hello bot", "reset": False}
    response = client.post("/chat", json=payload)
    
    assert response.status_code == 200
    assert "Mock AI Response" in response.json()["message"]

def test_web_image_generation_endpoint(client, mock_chatbot):
    """Verify the /generate-image endpoint returns a valid URL"""
    payload = {"prompt": "a beautiful sunset"}
    response = client.post("/generate-image", json=payload)
    
    assert response.status_code == 200
    assert "/static/generated_images/" in response.json()["url"]

def test_get_image_not_found(client):
    """Verify that requesting a non-existent image returns a 404"""
    response = client.get("/static/generated_images/non-existent.jpg")
    assert response.status_code == 404
