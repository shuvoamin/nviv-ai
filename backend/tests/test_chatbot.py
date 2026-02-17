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

            assert isinstance(bot.history, list)

def test_chatbot_init_no_knowledge_base():
    """Verify default system message if knowledge base file is missing"""
    envs = {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "test-model"
    }
    with patch.dict(os.environ, envs):
        with patch('chatbot.AzureOpenAI'), patch('chatbot.load_dotenv'):
            with patch('os.path.exists', return_value=False):
                bot = ChatBot()
                assert "You are Nviv" in bot.system_message
                assert "Use this knowledge" not in bot.system_message

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


def test_chatbot_chat_exception():
    """Verify exception handling in chat method"""
    envs = {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "test-model"
    }
    with patch.dict(os.environ, envs):
        with patch('chatbot.AzureOpenAI'), patch('chatbot.load_dotenv'):
            bot = ChatBot()
            # Mock client to raise exception
            # We need to set the mock on the instance
            bot.client = MagicMock()
            bot.client.chat.completions.create.side_effect = Exception("API Fail")
            
            response = bot.chat("hello")
            assert "Error: API Fail" in response

def test_chatbot_image_missing_content():
    """Verify error when image response lacks data"""
    envs = {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "test-model",
        "AZURE_OPENAI_FLUX_DEPLOYMENT": "flux-model"
    }
    with patch.dict(os.environ, envs):
        with patch('chatbot.AzureOpenAI'), patch('chatbot.load_dotenv'):
            # Patch requests.post globally for this block
            with patch('requests.post') as mock_post:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = {"data": []} # Empty data
                mock_post.return_value = mock_resp
                
                bot = ChatBot()
                with pytest.raises(RuntimeError, match="Image content .url/b64_json. not found"):
                    bot.generate_image("prompt")

def test_chatbot_generate_image_auto_url():
    """Verify that Flux URL is constructed correctly if not provided in env"""
    envs = {
        "AZURE_OPENAI_ENDPOINT": "https://resource.cognitiveservices.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "test-model",
        "AZURE_OPENAI_FLUX_DEPLOYMENT": "flux-model"
        # AZURE_OPENAI_FLUX_URL is missing
    }
    with patch.dict(os.environ, envs, clear=True):
         with patch('chatbot.AzureOpenAI'), patch('chatbot.load_dotenv'):
             with patch('requests.post') as mock_post:
                 mock_resp = MagicMock()
                 mock_resp.status_code = 200
                 mock_resp.json.return_value = {"data": [{"url": "http://image"}]}
                 mock_post.return_value = mock_resp
                 
                 bot = ChatBot()
                 bot.generate_image("prompt")
                 
                 # Verify URL construction
                 expected_url = "https://resource.services.ai.azure.com/providers/blackforestlabs/v1/flux-model?api-version=preview"
                 assert mock_post.call_args[0][0] == expected_url

def test_chatbot_transcribe_audio_success():
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

def test_chatbot_transcribe_audio_missing_deployment():
    """Verify error when whisper deployment is missing"""
    envs = {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "test-model"
        # Missing AZURE_OPENAI_WHISPER_DEPLOYMENT
    }
    with patch.dict(os.environ, envs):
        with patch('chatbot.AzureOpenAI'):
            bot = ChatBot()
            with pytest.raises(ValueError, match="Whisper deployment name not configured"):
                bot.transcribe_audio(b"audio_bytes")

def test_chatbot_transcribe_audio_failure():
    """Verify runtime error on transcription failure"""
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
            mock_client.audio.transcriptions.create.side_effect = Exception("API Error")
            
            bot = ChatBot()
            with pytest.raises(RuntimeError, match="Transcription failed: API Error"):
                bot.transcribe_audio(b"audio_bytes")

            with pytest.raises(RuntimeError, match="Transcription failed: API Error"):
                bot.transcribe_audio(b"audio_bytes")

def test_chatbot_init_missing_env():
    """Verify error when required env vars are missing"""
    with patch.dict(os.environ, {}, clear=True):
        with patch('chatbot.load_dotenv'):
            # Should raise ValueError because endpoint/key/deployment are missing
            with pytest.raises(ValueError, match="Missing required environment variables"):
                ChatBot()

def test_chatbot_generate_image_success_b64():
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

def test_chatbot_generate_image_success_url():
    """Verify successful image generation returning URL"""
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
            mock_response.json.return_value = {"data": [{"url": "http://image.url"}]}
            mock_post.return_value = mock_response
            
            bot = ChatBot()
            result = bot.generate_image("a prompt")
            assert result == "http://image.url"

def test_chatbot_generate_image_missing_deployment():
    """Verify error when flux deployment is missing"""
    envs = {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "test-model"
        # Missing AZURE_OPENAI_FLUX_DEPLOYMENT
    }
    with patch.dict(os.environ, envs, clear=True):
        # Patch requests.post globally for this block to ensure it's caught
        with patch('requests.post') as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 401
            mock_post.return_value = mock_resp
            
            with patch('chatbot.AzureOpenAI'), patch('chatbot.load_dotenv'):
                bot = ChatBot()
                with pytest.raises(ValueError, match="FLUX deployment name not configured"):
                     bot.generate_image("prompt")

def test_chatbot_generate_image_api_failure():
    """Verify error on non-200 API response"""
    envs = {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "test-model",
        "AZURE_OPENAI_FLUX_DEPLOYMENT": "flux-model"
    }
    with patch.dict(os.environ, envs):
        with patch('chatbot.AzureOpenAI'), patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = "Bad Request"
            mock_post.return_value = mock_response
            
            bot = ChatBot()
            with pytest.raises(RuntimeError, match="Image API returned 400: Bad Request"):
                bot.generate_image("prompt")
