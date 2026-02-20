import pytest
import os
import sys
from unittest.mock import MagicMock, patch, AsyncMock, mock_open

# Add the src directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) + "/src")

import chatbot
from chatbot import ChatBot

@pytest.fixture
def mock_agent():
    with patch("chatbot.ChatbotAgent") as MockAgent:
        agent_instance = MockAgent.return_value
        agent_instance.initialize = AsyncMock()
        agent_instance.chat = AsyncMock(return_value="Mocked AI Response")
        agent_instance.reset_history = MagicMock()
        yield agent_instance

def test_chatbot_initialization(mock_agent):
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
            assert bot.agent is not None

def test_chatbot_reset_history(mock_agent):
    """Verify that resetting history calls agent's reset"""
    envs = {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "test-model"
    }
    with patch.dict(os.environ, envs):
        with patch('chatbot.AzureOpenAI'):
            bot = ChatBot()
            bot.reset_history()
            mock_agent.reset_history.assert_called_once()

@pytest.mark.asyncio
async def test_chatbot_chat_flow(mock_agent):
    """Test the chat flow delegates to agent"""
    envs = {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "test-model"
    }
    with patch.dict(os.environ, envs):
        with patch('chatbot.AzureOpenAI'):
            bot = ChatBot()
            response = await bot.chat("hello world")
            
            mock_agent.chat.assert_awaited_once_with("hello world")
            assert response == "Mocked AI Response"

@pytest.mark.asyncio
async def test_chatbot_chat_exception(mock_agent):
    """Verify exception handling via agent propogation"""
    envs = {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "test-model"
    }
    with patch.dict(os.environ, envs):
        with patch('chatbot.AzureOpenAI'):
            bot = ChatBot()
            mock_agent.chat.side_effect = Exception("Agent Error")
            
            with pytest.raises(Exception, match="Agent Error"):
                await bot.chat("hello")

def test_chatbot_init_missing_env():
    """Verify error when required env vars are missing"""
    with patch.dict(os.environ, {}, clear=True):
        with patch('chatbot.load_dotenv'):
            # Should raise ValueError because endpoint/key/deployment are missing
            with pytest.raises(ValueError, match="Missing required environment variables"):
                ChatBot()

# --- Legacy Image/Audio tests that use AzureOpenAI client directly ---
# These methods in ChatBot still use self.client, so we test them similarly 
# but ignoring the agent part.

def test_chatbot_transcribe_audio_success(mock_agent):
    """Verify successful audio transcription"""
    envs = {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "test-model",
        "AZURE_OPENAI_WHISPER_DEPLOYMENT": "whisper-model"
    }
    with patch.dict(os.environ, envs):
        with patch('chatbot.AzureOpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            
            mock_response = MagicMock(text="Transcribed text")
            mock_client.audio.transcriptions.create.return_value = mock_response
            
            bot = ChatBot()
            result = bot.transcribe_audio(b"audio_bytes")
            assert result == "Transcribed text"

def test_chatbot_generate_image_success_b64(mock_agent):
    """Verify successful image generation returning base64"""
    envs = {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "test-model",
        "AZURE_OPENAI_FLUX_DEPLOYMENT": "flux-model"
    }
    with patch.dict(os.environ, envs):
        with patch('chatbot.AzureOpenAI'), patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": [{"b64_json": "base64data"}]}
            mock_post.return_value = mock_response
            
            
            bot = ChatBot()
            result = bot.generate_image("a prompt")
            assert result == "data:image/png;base64,base64data"

def test_chatbot_transcribe_audio_missing_deployment(mock_agent):
    """Verify error when whisper deployment is missing"""
    envs = {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "test-model"
    }
    with patch.dict(os.environ, envs, clear=True):
        with patch('chatbot.AzureOpenAI'):
            bot = ChatBot()
            with pytest.raises(ValueError, match="Whisper deployment name not configured"):
                bot.transcribe_audio(b"audio")

def test_chatbot_transcribe_audio_exception(mock_agent):
    """Verify exception handling in transcription"""
    envs = {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "test-model",
        "AZURE_OPENAI_WHISPER_DEPLOYMENT": "whisper-model"
    }
    with patch.dict(os.environ, envs):
        with patch('chatbot.AzureOpenAI') as mock_openai:
            client = mock_openai.return_value
            client.audio.transcriptions.create.side_effect = Exception("Whisper Fail")
            
            bot = ChatBot()
            with pytest.raises(RuntimeError, match="Transcription failed: Whisper Fail"):
                bot.transcribe_audio(b"audio")

def test_chatbot_generate_image_missing_deployment(mock_agent):
    """Verify error when flux deployment is missing"""
    # clear=True removes all env vars, so we only have what we define.
    # We purposefully exclude AZURE_OPENAI_FLUX_DEPLOYMENT
    envs = {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "test-model"
    }
    with patch.dict(os.environ, envs, clear=True):
        with patch('chatbot.AzureOpenAI'), \
             patch('chatbot.load_dotenv'):
            bot = ChatBot()
            # Explicitly ensure it is None in case of leakage or defaults
            bot.flux_deployment = None 
            
            # Need to call generate_image to trigger the check
            with pytest.raises(ValueError, match="FLUX deployment name not configured"):
                bot.generate_image("prompt")

def test_chatbot_generate_image_api_error(mock_agent):
    """Verify handling of non-200 API response"""
    envs = {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "test-model",
        "AZURE_OPENAI_FLUX_DEPLOYMENT": "flux"
    }
    with patch.dict(os.environ, envs), \
         patch('chatbot.AzureOpenAI'), \
         patch('requests.post') as mock_post:
         
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response
        
        bot = ChatBot()
        with pytest.raises(RuntimeError, match="Image API returned 400"):
            bot.generate_image("prompt")

def test_chatbot_generate_image_no_data(mock_agent):
    """Verify handling of response with missing data"""
    envs = {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "test-model",
        "AZURE_OPENAI_FLUX_DEPLOYMENT": "flux"
    }
    with patch.dict(os.environ, envs), \
         patch('chatbot.AzureOpenAI'), \
         patch('requests.post') as mock_post:
         
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_post.return_value = mock_response
        
        bot = ChatBot()
        with pytest.raises(RuntimeError, match="Image content .* not found"):
            bot.generate_image("prompt")

def test_chatbot_generate_image_url_response(mock_agent):
    """Verify handling of URL in response"""
    envs = {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "test-model",
        "AZURE_OPENAI_FLUX_DEPLOYMENT": "flux"
    }
    with patch.dict(os.environ, envs), \
         patch('chatbot.AzureOpenAI'), \
         patch('requests.post') as mock_post:
         
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"url": "http://image.com"}]}
        mock_post.return_value = mock_response
        
        bot = ChatBot()
        # The method returns the URL directly if 'url' is present and 'b64_json' is not
        result = bot.generate_image("prompt")
        assert result == "http://image.com"

def test_chatbot_generate_image_construct_url(mock_agent):
    """Verify URL construction when FLUX_URL is missing"""
    envs = {
        "AZURE_OPENAI_ENDPOINT": "https://service.cognitiveservices.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "test-model",
        "AZURE_OPENAI_FLUX_DEPLOYMENT": "flux-deployment",
        "AZURE_OPENAI_FLUX_URL": "" # Explicitly empty
    }
    with patch.dict(os.environ, envs, clear=True), \
         patch('chatbot.AzureOpenAI'), \
         patch('chatbot.load_dotenv'), \
         patch('requests.post') as mock_post:
         
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"url": "http://image.com"}]}
        mock_post.return_value = mock_response
        
        bot = ChatBot()
        bot.generate_image("prompt")
        
        # Verify the URL was constructed correctly
        # endpoint: https://service.cognitiveservices.azure.com/
        # base: https://service.services.ai.azure.com -> services.ai.azure.com
        # constructed: https://service.services.ai.azure.com/providers/blackforestlabs/v1/flux-deployment?api-version=preview
        
        expected_url = "https://service.services.ai.azure.com/providers/blackforestlabs/v1/flux-deployment?api-version=preview"
        
        # Check that post was called with constructed URL
        args, _ = mock_post.call_args
        assert args[0] == expected_url

def test_load_knowledge_base(mock_agent):
    """Test loading knowledge base from file and fallback."""
    envs = {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "test-model"
    }
    
    # Case 1: File exists
    with patch.dict(os.environ, envs), \
         patch('chatbot.AzureOpenAI'), \
         patch('chatbot.load_dotenv'), \
         patch('os.path.exists') as mock_exists, \
         patch('builtins.open', mock_open(read_data="Knowledge Content")):
         
        # We need os.path.exists to return True for the knowledge file
        # But maybe we should use side_effect to be safe if other things check paths
        mock_exists.return_value = True
         
        bot = ChatBot()
        kb = bot._load_knowledge_base()
        assert "Knowledge Content" in kb

    # Case 2: File missing
    with patch.dict(os.environ, envs), \
         patch('chatbot.AzureOpenAI'), \
         patch('chatbot.load_dotenv'), \
         patch('os.path.exists', return_value=False):
         
        bot = ChatBot()
        kb = bot._load_knowledge_base()
        assert "helpful AI assistant" in kb
        assert "Knowledge Content" not in kb

@pytest.mark.asyncio
async def test_chatbot_initialize(mock_agent):
    """Test async initialization delegates to agent."""
    envs = {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "test-model"
    }
    with patch.dict(os.environ, envs), \
         patch('chatbot.AzureOpenAI'):
            
        bot = ChatBot()
        await bot.initialize()
        mock_agent.initialize.assert_awaited_once()
