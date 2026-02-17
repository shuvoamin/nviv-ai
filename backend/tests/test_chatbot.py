import pytest
import os
import sys
from unittest.mock import MagicMock, patch

# Add the src directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/src")

import chatbot
from chatbot import ChatBot

def test_chatbot_initialization():
    """Verify that the chatbot initializes correctly (given valid env vars)"""
    envs = {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "test-model"
    }
    with patch.dict(os.environ, envs):
        with patch('chatbot.AzureOpenAI'):
            bot = ChatBot()
            assert bot is not None
            assert isinstance(bot.history, list)

def test_chatbot_reset_history():
    """Verify that resetting history clears the list except for the system prompt"""
    envs = {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "test-model"
    }
    with patch.dict(os.environ, envs):
        with patch('chatbot.AzureOpenAI'):
            bot = ChatBot()
            bot.history.append({"role": "user", "content": "hello"})
            bot.reset_history()
            assert len(bot.history) == 1
            assert bot.history[0]["role"] == "system"

def test_chatbot_chat_flow():
    """Test the chat flow with a mocked response"""
    envs = {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "test-model"
    }
    with patch.dict(os.environ, envs):
        with patch('chatbot.AzureOpenAI') as mock_openai:
            # Setup mock response
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content="Mocked response from AI"))]
            mock_client.chat.completions.create.return_value = mock_response
            
            bot = ChatBot()
            response = bot.chat("hello world")
            
            assert response == "Mocked response from AI"
            assert len(bot.history) >= 2
