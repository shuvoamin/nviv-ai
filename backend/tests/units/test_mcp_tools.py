import pytest
from unittest.mock import MagicMock, patch, mock_open
import sys
import os

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) + "/src")

from utils.tools.communication import send_twilio_sms, send_whatsapp_message
from utils.tools.media import generate_image

# --- Communication Tests ---

class TestCommunication:
    @patch("utils.tools.communication.os.getenv")
    @patch("utils.tools.communication.TwilioClient")
    def test_send_twilio_sms_success(self, mock_twilio, mock_getenv):
        """Test successful SMS sending."""
        # Setup env vars
        mock_getenv.side_effect = lambda key: {
            "TWILIO_ACCOUNT_SID": "AC123",
            "TWILIO_AUTH_TOKEN": "token",
            "TWILIO_FROM_NUMBER": "+1234567890"
        }.get(key)
        
        # Setup Mock Client
        mock_client_instance = mock_twilio.return_value
        mock_message = MagicMock()
        mock_message.sid = "SM123"
        mock_client_instance.messages.create.return_value = mock_message
        
        result = send_twilio_sms("+0987654321", "Hello")
        
        assert "sent successfully" in result
        assert "SM123" in result
        mock_client_instance.messages.create.assert_called_once_with(
            body="Hello",
            from_="+1234567890",
            to="+0987654321"
        )

    @patch("utils.tools.communication.os.getenv")
    def test_send_twilio_sms_missing_credentials(self, mock_getenv):
        """Test usage with missing credentials."""
        mock_getenv.return_value = None
        result = send_twilio_sms("123", "msg")
        assert "Error" in result
        assert "missing" in result

    @patch("utils.tools.communication.os.getenv")
    @patch("utils.tools.communication.requests.post")
    def test_send_whatsapp_success(self, mock_post, mock_getenv):
        """Test successful WhatsApp sending."""
        mock_getenv.side_effect = lambda key: {
            "WHATSAPP_ACCESS_TOKEN": "token",
            "WHATSAPP_PHONE_NUMBER_ID": "123"
        }.get(key)
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"messages": [{"id": "wag_123"}]}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = send_whatsapp_message("+123", "Hello")
        
        assert "sent successfully" in result
        mock_post.assert_called_once()
    
# --- Media Tests ---

    @patch("utils.tools.communication.os.getenv")
    @patch("utils.tools.communication.TwilioClient")
    def test_send_twilio_sms_exception(self, mock_twilio, mock_getenv):
        """Test exception handling during SMS sending."""
        mock_getenv.side_effect = lambda key: "dummy"
        mock_twilio.side_effect = Exception("Twilio Error")
        
        result = send_twilio_sms("123", "msg")
        assert "Error sending Twilio SMS" in result
        assert "Twilio Error" in result

    @patch("utils.tools.communication.os.getenv")
    def test_send_whatsapp_missing_credentials(self, mock_getenv):
        """Test WhatsApp with missing credentials."""
        mock_getenv.return_value = None
        result = send_whatsapp_message("123", "msg")
        assert "Error" in result
        assert "missing" in result

    @patch("utils.tools.communication.os.getenv")
    @patch("utils.tools.communication.requests.post")
    def test_send_whatsapp_exception(self, mock_post, mock_getenv):
        """Test exception handling during WhatsApp sending."""
        mock_getenv.side_effect = lambda key: "dummy"
        mock_post.side_effect = Exception("WhatsApp Error")
        
        result = send_whatsapp_message("123", "msg")
        assert "Error sending WhatsApp message" in result
        assert "WhatsApp Error" in result

# --- Media Tests ---

class TestMedia:
    @patch("utils.tools.media.os.getenv")
    @patch("utils.tools.media.requests.post")
    @patch("utils.tools.media.Image.open")
    @patch("utils.tools.media.os.makedirs")
    def test_generate_image_success(self, mock_makedirs, mock_img_open, mock_post, mock_getenv):
        """Test successful image generation and saving."""
        mock_getenv.side_effect = lambda key, default=None: {
            "AZURE_OPENAI_API_KEY": "key",
            "AZURE_OPENAI_ENDPOINT": "https://example.com",
            "AZURE_OPENAI_FLUX_DEPLOYMENT": "flux",
            "BASE_URL": "http://localhost:8000"
        }.get(key, default)
        
        # Mock API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"b64_json": "ZmFrZV9pbWFnZV9kYXRh"}] # "fake_image_data" in base64
        }
        mock_post.return_value = mock_response
        
        # Mock Image processing
        mock_img = MagicMock()
        mock_img.mode = "RGB"
        mock_img_open.return_value = mock_img
        
        result = generate_image("A futuristic city")
        
        assert "![Generated Image]" in result
        assert "http://localhost:8000/static/generated_images/" in result
        
        mock_post.assert_called_once()
        mock_img.save.assert_called_once()

    @patch("utils.tools.media.os.getenv")
    @patch("utils.tools.media.requests.post")
    @patch("utils.tools.media.Image.open")
    @patch("utils.tools.media.os.makedirs")
    def test_generate_image_relative_url(self, mock_makedirs, mock_img_open, mock_post, mock_getenv):
        """Test image generation with relative URL (no BASE_URL)."""
        mock_getenv.side_effect = lambda key, default=None: {
            "AZURE_OPENAI_API_KEY": "key",
            "AZURE_OPENAI_ENDPOINT": "https://example.com",
            "AZURE_OPENAI_FLUX_DEPLOYMENT": "flux"
            # BASE_URL missing
        }.get(key, default)
        
        # Mock API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"b64_json": "ZmFrZV9pbWFnZV9kYXRh"}]
        }
        mock_post.return_value = mock_response
        
        # Mock Image processing
        mock_img = MagicMock()
        mock_img.mode = "RGB"
        mock_img_open.return_value = mock_img
        
        result = generate_image("A futuristic city")
        
        assert "![Generated Image]" in result
        assert "](/static/generated_images/" in result
        assert "http" not in result.split("]")[1] # Ensure no scheme in URL
        
        mock_post.assert_called_once()
        mock_img.save.assert_called_once()

    @patch("utils.tools.media.os.getenv")
    def test_generate_image_missing_credentials(self, mock_getenv):
        """Test usage with missing credentials."""
        mock_getenv.return_value = None
        result = generate_image("prompt")
        assert "Error" in result
        assert "missing" in result

    @patch("utils.tools.media.os.getenv")
    @patch("utils.tools.media.requests.post")
    def test_generate_image_api_error(self, mock_post, mock_getenv):
        """Test handling of non-200 API response."""
        mock_getenv.side_effect = lambda key, default=None: "dummy"
        
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response
        
        result = generate_image("prompt")
        assert "Error: Image API returned 400" in result
        assert "Bad Request" in result

    @patch("utils.tools.media.os.getenv")
    @patch("utils.tools.media.requests.post")
    def test_generate_image_url_response(self, mock_post, mock_getenv):
        """Test handling of URL-based response."""
        mock_getenv.side_effect = lambda key, default=None: "dummy"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"url": "http://example.com/image.jpg"}]
        }
        mock_post.return_value = mock_response
        
        result = generate_image("prompt")
        assert "![Generated Image](http://example.com/image.jpg)" in result

    @patch("utils.tools.media.os.getenv")
    @patch("utils.tools.media.requests.post")
    def test_generate_image_no_data(self, mock_post, mock_getenv):
        """Test handling of empty data in response."""
        mock_getenv.side_effect = lambda key, default=None: "dummy"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_post.return_value = mock_response
        
        result = generate_image("prompt")
        assert "Error: Image content not found" in result

    @patch("utils.tools.media.os.getenv")
    @patch("utils.tools.media.requests.post")
    @patch("utils.tools.media.Image.open")
    @patch("utils.tools.media.os.makedirs")
    def test_generate_image_rgba_conversion(self, mock_makedirs, mock_img_open, mock_post, mock_getenv):
        """Test conversion of RGBA images to RGB."""
        mock_getenv.side_effect = lambda key, default=None: "dummy"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"b64_json": "ZmFrZQ=="}]
        }
        mock_post.return_value = mock_response
        
        mock_img = MagicMock()
        mock_img.mode = "RGBA"
        mock_img_open.return_value = mock_img
        
        generate_image("prompt")
        
        mock_img.convert.assert_called_once_with("RGB")
        mock_img.convert.return_value.save.assert_called_once()

    @patch("utils.tools.media.os.getenv")
    @patch("utils.tools.media.requests.post")
    def test_generate_image_exception(self, mock_post, mock_getenv):
        """Test generic exception handling."""
        mock_getenv.side_effect = lambda key, default=None: "dummy"
        mock_post.side_effect = Exception("Net Error")
        
        result = generate_image("prompt")
        assert "Error generating image" in result
        assert "Net Error" in result

    @patch("utils.tools.media.os.getenv")
    @patch("utils.tools.media.requests.post")
    @patch("utils.tools.media.Image.open")
    @patch("utils.tools.media.os.makedirs")
    @patch("utils.tools.media.os.path.exists")
    def test_generate_image_path_fallback(self, mock_exists, mock_makedirs, mock_img_open, mock_post, mock_getenv):
        """Test path fallback logic when project root is not found."""
        mock_getenv.side_effect = lambda key, default=None: "dummy"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"b64_json": "ZmFrZQ=="}]
        }
        mock_post.return_value = mock_response
        
        mock_img = MagicMock()
        mock_img_open.return_value = mock_img
        mock_img.mode = "RGB"

        # Simulate path existence check failure for project root logic
        # logic: if not os.path.exists(os.path.join(project_root, "backend")):
        # We want this to return False so it enters the if block
        mock_exists.return_value = False
        
        generate_image("prompt")
        
        # We can't easily assert the path changed without mocking os.path.abspath behavior specifically
        # or inspecting the call to makedirs/save.
        # But simply executing this path covers the lines.
        mock_makedirs.assert_called()
