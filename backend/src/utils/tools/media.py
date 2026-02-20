import os
import requests
import base64
import uuid
import io
from PIL import Image

def generate_image(prompt: str) -> str:
    """
    Generates an image using Azure OpenAI (Flux) based on the user's prompt.
    Returns a markdown image link to display to the user.
    
    Args:
        prompt: A descriptive text prompt for the image generation.
    """
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = (os.getenv("AZURE_OPENAI_ENDPOINT") or "").rstrip("/")
    flux_deployment = os.getenv("AZURE_OPENAI_FLUX_DEPLOYMENT")
    flux_url = os.getenv("AZURE_OPENAI_FLUX_URL")

    if not all([api_key, endpoint, flux_deployment]):
         return "Error: Azure OpenAI credentials (API_KEY, ENDPOINT, FLUX_DEPLOYMENT) are missing."

    # If no custom URL, build it using the services AI domain pattern
    if not flux_url:
        base_url = endpoint.replace("cognitiveservices.azure.com", "services.ai.azure.com").rstrip("/")
        flux_url = f"{base_url}/providers/blackforestlabs/v1/{flux_deployment}?api-version=preview"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "prompt": prompt,
        "width": 1024,
        "height": 1024,
        "n": 1,
        "model": "FLUX.2-pro" 
    }

    try:
        response = requests.post(flux_url, headers=headers, json=payload)
        if response.status_code != 200:
            return f"Error: Image API returned {response.status_code}: {response.text}"
        
        data = response.json()
        image_data = None
        
        if 'data' in data and len(data['data']) > 0:
            item = data['data'][0]
            if 'b64_json' in item:
                image_data = item['b64_json']
            elif 'url' in item:
                # If URL, we might want to download it or just return it? 
                # The prompt implies we want to host it locally to be consistent.
                # For now let's assume b64_json is what we get or handle URL -> saving.
                return f"![Generated Image]({item['url']})"
        
        if not image_data:
             return "Error: Image content not found in response."

        # Save Image locally
        filename = f"{uuid.uuid4()}.jpg"
        
        # Determine path relative to THIS file
        # this file is in backend/src/utils/tools/media.py
        # root is ../../../../
        # static is backend/static/generated_images
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, "..", "..", "..", ".."))
        images_dir = os.path.join(project_root, "backend", "static", "generated_images")
        
        # Fallback if path resolution fails (e.g. running from root)
        if not os.path.exists(os.path.join(project_root, "backend")):
             # Try absolute path based on CWD if running from root
             images_dir = os.path.abspath("backend/static/generated_images")

        os.makedirs(images_dir, exist_ok=True)
        
        filepath = os.path.join(images_dir, filename)
        
        # Decode and save
        image_bytes = base64.b64decode(image_data)
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(filepath, "JPEG", quality=85)
        
        # Construct public URL
        # Use relative path for web app compatibility (proxied via Vite)
        # If BASE_URL is set (e.g. for prod/ngrok), use it. Otherwise relative.
        base_app_url = os.getenv("BASE_URL")
        if base_app_url:
            public_url = f"{base_app_url.rstrip('/')}/static/generated_images/{filename}"
        else:
             public_url = f"/static/generated_images/{filename}"
        
        return f"![Generated Image]({public_url})"

    except Exception as e:
        return f"Error generating image: {str(e)}"
