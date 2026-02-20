
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

@pytest.mark.asyncio
async def test_background_cleanup_task_cancelled():
    """Verify that background cleanup task handles CancelledError properly"""
    import asyncio
    
    with patch("api.asyncio.to_thread", side_effect=asyncio.CancelledError()):
        # Call the task directly - it should break out of the while loop immediately
        await api.background_cleanup_task()
        
@pytest.mark.asyncio
async def test_background_cleanup_task_exception():
    """Verify that background cleanup task catches other exceptions and continues"""
    import asyncio
    
    # We want it to raise an exception on first loop, then CancelledError on second loop
    # so we can break out of the infinite while True
    side_effects = [Exception("Test error"), asyncio.CancelledError()]
    
    with patch("api.asyncio.to_thread", side_effect=side_effects):
        with patch("api.app_state.diag_logger") as mock_logger:
            with patch("api.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                await api.background_cleanup_task()
                mock_logger.error.assert_called_with("Image cleanup task error: Test error")
                mock_sleep.assert_awaited_once_with(3600)
