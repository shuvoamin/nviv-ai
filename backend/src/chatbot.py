import os
import requests
import logging
from openai import AzureOpenAI
from dotenv import load_dotenv
from config import APP_NAME

from agent import ChatbotAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChatBot:
    def __init__(self):
        load_dotenv()
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        self.whisper_deployment = os.getenv("AZURE_OPENAI_WHISPER_DEPLOYMENT")
        self.flux_deployment = os.getenv("AZURE_OPENAI_FLUX_DEPLOYMENT")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

        self._validate_env()
        
        # Initialize Agent
        self.agent = ChatbotAgent()

        self.client = AzureOpenAI(
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            api_version=self.api_version
        )
        
    async def initialize(self):
        await self.agent.initialize()



    def _load_knowledge_base(self):
        """Load knowledge base from file or use default"""
        knowledge_file = os.path.join(os.path.dirname(__file__), "..", "..", "training", "knowledge_base.md")
        
        if os.path.exists(knowledge_file):
            with open(knowledge_file, 'r') as f:
                knowledge = f.read()
                return f"You are {APP_NAME}, a helpful AI assistant.\n\n{knowledge}\n\nUse this knowledge to answer questions accurately."
        
        # Default if no knowledge base file
        return f"You are {APP_NAME}, a helpful AI assistant."

    def transcribe_audio(self, audio_content) -> str:
        """Transcribe audio using Azure OpenAI Whisper"""
        if not self.whisper_deployment:
            raise ValueError("Whisper deployment name not configured (AZURE_OPENAI_WHISPER_DEPLOYMENT)")

        try:
            # We use the open() compatible interface if it were a file, 
            # but since we have content in memory from requests, we use a Tuple
            # (filename, file_content, content_type)
            response = self.client.audio.transcriptions.create(
                model=self.whisper_deployment,
                file=("audio.ogg", audio_content, "audio/ogg")
            )
            return response.text
        except Exception as e:
            raise RuntimeError(f"Transcription failed: {str(e)}")

    def generate_image(self, prompt: str) -> str:
        """Generate image using FLUX.2-pro following the exact Microsoft REST example (MaaS)"""
        if not self.flux_deployment:
            raise ValueError("FLUX deployment name not configured (AZURE_OPENAI_FLUX_DEPLOYMENT)")

        flux_url = os.getenv("AZURE_OPENAI_FLUX_URL")
        
        # If no custom URL, build it using the services AI domain pattern
        if not flux_url:
            base_url = self.endpoint.replace("cognitiveservices.azure.com", "services.ai.azure.com").rstrip("/")
            flux_url = f"{base_url}/providers/blackforestlabs/v1/{self.flux_deployment}?api-version=preview"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Payload must match the MaaS REST example exactly
        payload = {
            "prompt": prompt,
            "width": 1024,
            "height": 1024,
            "n": 1,
            # Note: The curl example uses "FLUX.2-pro" (exact case)
            "model": "FLUX.2-pro" 
        }

        try:
            logger.info(f"Targeting Image API: {flux_url}")
            response = requests.post(flux_url, headers=headers, json=payload)
            
            if response.status_code != 200:
                logger.error(f"Image generation failed. Status: {response.status_code}, Body: {response.text}")
                # Raising here allows api.py to catch and return the detail to the frontend
                raise RuntimeError(f"Image API returned {response.status_code}: {response.text}")
            
            data = response.json()
            
            # The REST example returns base64 in data[0].b64_json
            if 'data' in data and len(data['data']) > 0:
                item = data['data'][0]
                if 'b64_json' in item:
                    return f"data:image/png;base64,{item['b64_json']}"
                elif 'url' in item:
                    return item['url']
            
            raise RuntimeError("Image content (url/b64_json) not found in response.")
        except Exception as e:
            logger.error(f"Exception during image generation: {str(e)}")
            raise RuntimeError(f"Image generation failed: {str(e)}")


    def _validate_env(self):
        if not all([self.endpoint, self.api_key, self.deployment_name]):
            raise ValueError("Missing required environment variables: AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT_NAME")

    async def chat(self, user_input: str) -> str:
        return await self.agent.chat(user_input)

    def reset_history(self):
        self.agent.reset_history()
