import base64
import uuid
import io
import time
from PIL import Image
from app_state import IMAGES_DIR, diag_logger
from config import IMAGE_RETENTION_HOURS

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

def cleanup_old_images():
    """Deletes images older than the configured retention period."""
    try:
        current_time = time.time()
        retention_seconds = IMAGE_RETENTION_HOURS * 3600
        deleted_count = 0
        
        for filepath in IMAGES_DIR.glob('*'):
            if filepath.is_file():
                # Get the file modification time
                file_age = current_time - filepath.stat().st_mtime
                if file_age > retention_seconds:
                    try:
                        filepath.unlink()
                        deleted_count += 1
                    except Exception as e:
                        diag_logger.error(f"Failed to delete old image {filepath.name}: {e}")
                        
        if deleted_count > 0:
            diag_logger.info(f"Cleaned up {deleted_count} old generated images")
    except Exception as e:
        diag_logger.error(f"Error during image cleanup: {e}")
