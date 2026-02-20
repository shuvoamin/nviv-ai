
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.testclient import TestClient
import sys
import os

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) + "/src")

import api
import app_state

@pytest.mark.asyncio
async def test_api_lifespan():
    """Test startup and shutdown events."""
    
    # Mock ChatBot
    mock_chatbot = MagicMock()
    mock_chatbot.initialize = AsyncMock()
    mock_chatbot.agent = MagicMock()
    mock_chatbot.agent.cleanup = AsyncMock()
    
    # Patch app_state.chatbot
    with patch.object(app_state, "chatbot", mock_chatbot):
        # Use TestClient with the app context to trigger lifespan
        with TestClient(api.app) as client:
            # Startup should have run
            mock_chatbot.initialize.assert_awaited_once()
            
            # Make a dummy request to ensure app is up (optional)
            # client.get("/") 
            
        # Context exit triggers shutdown
        mock_chatbot.agent.cleanup.assert_awaited_once()

@pytest.mark.asyncio
async def test_api_lifespan_no_chatbot():
    """Test lifespan when chatbot is None (safe handling)."""
    with patch.object(app_state, "chatbot", None):
        with TestClient(api.app) as client:
            pass
        # Should complete without error
