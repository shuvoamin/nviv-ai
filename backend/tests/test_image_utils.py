import pytest
import os
import sys
from pathlib import Path

# Add the src directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/src")

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
