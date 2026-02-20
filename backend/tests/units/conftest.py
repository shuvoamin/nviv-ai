import pytest
import os
import sys
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock

# Add the src directory to sys.path to allow importing local modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) + "/src")

@pytest.fixture(scope="session", autouse=True)
def mock_chatbot_session():
    """Mock ChatBot globally for the entire test session to avoid real init"""
    with patch("chatbot.ChatBot") as MockChatBot:
        # Create a mock instance with necessary async methods
        mock_instance = MockChatBot.return_value
        
        # Mock the internal agent 
        mock_agent = AsyncMock()
        mock_agent.initialize = AsyncMock()
        mock_agent.chat = AsyncMock(return_value="Global Mock AI Response")
        mock_agent.reset_history = MagicMock()
        mock_instance.agent = mock_agent
        
        # Mock high-level methods
        mock_instance.initialize = AsyncMock()
        mock_instance.chat = AsyncMock(return_value="Global Mock AI Response")
        mock_instance.generate_image.return_value = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        mock_instance.reset_history = MagicMock()
        
        # Ensure we patch where it is used/imported
        with patch("app_state.ChatBot", MockChatBot):
             yield mock_instance

@pytest.fixture
def client(mock_chatbot_session):
    """Fixture for creating a FastAPI TestClient"""
    # Import app here internally so the session mock is already active
    from api import app
    return TestClient(app)

@pytest.fixture
def mock_chatbot(monkeypatch, mock_chatbot_session):
    """Fixture to customize the mock ChatBot per test if needed"""
    import app_state
    
    # Reset side effects or return values if needed, otherwise use the session one
    # If we want a fresh mock per test we can replace it here
    
    # For now, let's just ensure app_state.chatbot uses our session mock
    monkeypatch.setattr(app_state, "chatbot", mock_chatbot_session)
    return mock_chatbot_session
