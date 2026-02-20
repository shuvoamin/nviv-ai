import pytest
import os
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add the src directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) + "/src")

from utils.image_utils import save_base64_image
from app_state import IMAGES_DIR

def test_save_base64_image_success():
    """Verify that a valid base64 image is saved and transcoded to JPEG"""
    # A tiny 1x1 black png
    base64_data = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    base_url = "http://localhost:8000"
    
    url = save_base64_image(base64_data, base_url)
    
    assert "/static/generated_images/" in url
    assert url.endswith(".jpg")
    
    # Check if file exists
    filename = url.split("/")[-1]
    filepath = IMAGES_DIR / filename
    assert filepath.exists()
    
    # Simple cleanup
    if filepath.exists():
        filepath.unlink()

def test_save_base64_image_invalid_format():
    """Verify that invalid strings are returned as-is"""
    url = save_base64_image("not-an-image", "http://localhost:8000")
    assert url == "not-an-image"

def test_save_base64_image_file_error():
    """Verify error handling during file save"""
    # Mock open to raise exception
    with patch("builtins.open", side_effect=IOError("Disk full")):
        with patch('app_state.diag_logger') as mock_logger:
            url = save_base64_image("data:image/png;base64,data", "http://host")
            # Should fall back to returning original data
            assert url.startswith("data:image/png;base64")

def test_save_base64_image_general_exception():
    """Verify general exception handling"""
    # Trigger exception in decoding or other part
    # We can pass invalid base64 that causes b64decode to fail?
    # No, earlier test handles "not-an-image" by returning it.
    # We need to raise Exception inside the try block but AFTER the initial checks.
    # The function:
    # try:
    #    header, encoded = base64_data.split(",", 1) ...
    
    with patch("builtins.open", side_effect=Exception("General Fail")):
        with patch('app_state.diag_logger') as mock_logger:
             url = save_base64_image("data:image/png;base64,data", "host")
             assert url.startswith("data:image/png;base64")

def test_save_base64_azure_url():
    """Verify that Azure URLs are upgraded to HTTPS"""
    with patch('app_state.diag_logger'):
        with patch('base64.b64decode') as mock_b64:
            mock_b64.return_value = b'imagedata' # Return bytes!
            with patch('PIL.Image.open') as mock_open:
                mock_img = MagicMock()
                mock_img.mode = "RGB"
                mock_open.return_value = mock_img
                
                with patch('pathlib.Path.stat') as mock_stat:
                     mock_stat.return_value.st_size = 1024
                     with patch('pathlib.Path.open'):
                         # Execute logic
                         url = save_base64_image("data:image/png;base64,data", "http://myapp.azurewebsites.net")
                         # Use equality check with substring to debug value if it fails
                         assert "https://myapp.azurewebsites.net" in url
