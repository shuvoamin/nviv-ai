import base64
import uuid
import io
from PIL import Image
from app_state import IMAGES_DIR, diag_logger

def save_base64_image(image_data: str, base_url: str) -> str:
    """Saves base64 image and transcodes to JPEG for WhatsApp compatibility"""
    if not image_data.startswith("data:image"):
        return image_data
    try:
        header, encoded = image_data.split(",", 1)
        # Force JPEG for maximum WhatsApp/Twilio compatibility (fixes 63019)
        filename = f"{uuid.uuid4()}.jpg"
        filepath = IMAGES_DIR / filename
        
        # Decode and transcode to RGB JPEG
        image_bytes = base64.b64decode(encoded)
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(filepath, "JPEG", quality=85)
        
        filesize_kb = filepath.stat().st_size / 1024
        diag_logger.info(f"Image saved: {filename} ({filesize_kb:.2f} KB)")
        
        url_str = str(base_url).rstrip('/')
        if "azurewebsites.net" in url_str and not url_str.startswith("https"):
            url_str = url_str.replace("http://", "https://")
            
        public_url = f"{url_str}/static/generated_images/{filename}"
        diag_logger.info(f"Image available at: {public_url}")
        return public_url
    except Exception as e:
        diag_logger.error(f"Failed to transcode base64 image: {e}")
        return image_data
