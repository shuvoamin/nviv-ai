import pytest
import os
import sys
from fastapi.testclient import TestClient

# Add the src directory to sys.path to allow importing local modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/src")

from api import app

@pytest.fixture
def client():
    """Fixture for creating a FastAPI TestClient"""
    return TestClient(app)

@pytest.fixture
def mock_chatbot(monkeypatch):
    """Fixture to mock the ChatBot instance in app_state"""
    from app_state import chatbot
    
    class MockChatBot:
        def chat(self, message):
            return f"Mock AI Response: {message}"
        
        def generate_image(self, prompt):
            # Mock base64 image data
            return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        
        def reset_history(self):
            pass
            
    mock_instance = MockChatBot()
    # Use monkeypatch to replace the chatbot instance in app_state
    import app_state
    monkeypatch.setattr(app_state, "chatbot", mock_instance)
    return mock_instance
