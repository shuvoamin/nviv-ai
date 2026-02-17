import os
import requests
import logging
from openai import AzureOpenAI
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChatBot:
    def __init__(self):
        load_dotenv()
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        self.whisper_deployment = os.getenv("AZURE_OPENAI_WHISPER_DEPLOYMENT")
        self.flux_deployment = os.getenv("AZURE_OPENAI_FLUX_DEPLOYMENT")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

        self._validate_env()

        self.client = AzureOpenAI(
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            api_version=self.api_version
        )
        
        
        # Load knowledge base
        self.system_message = self._load_knowledge_base()
        self.history = [{"role": "system", "content": self.system_message}]

    def _load_knowledge_base(self):
        """Load knowledge base from file or use default"""
        knowledge_file = os.path.join(os.path.dirname(__file__), "..", "knowledge_base.md")
        
        if os.path.exists(knowledge_file):
            with open(knowledge_file, 'r') as f:
                knowledge = f.read()
                return f"You are Nviv, a helpful AI assistant.\n\n{knowledge}\n\nUse this knowledge to answer questions accurately."
        
        # Default if no knowledge base file
        return "You are Nviv, a helpful AI assistant."

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
        """Generate image using FLUX.2-pro (Azure AI Inference)"""
        if not self.flux_deployment:
            raise ValueError("FLUX deployment name not configured (AZURE_OPENAI_FLUX_DEPLOYMENT)")

        # Construct the URL for Azure AI Inference Image Generation
        # Usually: {endpoint}/openai/deployments/{deployment}/images/generations?api-version={version}
        # Or if it's a model catalog endpoint: {endpoint}/v1/images/generations
        
        url = f"{self.endpoint}/openai/deployments/{self.flux_deployment}/images/generations?api-version=2024-02-15-preview"
        
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "prompt": prompt,
            "n": 1,
            "size": "1024x1024"
        }

        try:
            logger.info(f"Requesting image generation from URL: {url}")
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code != 200:
                logger.error(f"Image generation failed. Status: {response.status_code}, Body: {response.text}")
                return f"Error: Image generation failed with status {response.status_code}. Details: {response.text}"
            
            data = response.json()
            logger.info(f"Image generation response received: {data}")
            
            # Format check: Some APIs return 'url' directly, others in a list
            if 'data' in data and len(data['data']) > 0:
                return data['data'][0].get('url', 'URL not found in data[0]')
            elif 'url' in data:
                return data['url']
            else:
                logger.error(f"Unexpected response format: {data}")
                return "Error: Unexpected response format from image API."
        except Exception as e:
            logger.error(f"Exception during image generation: {str(e)}")
            return f"Error: Image generation failed: {str(e)}"


    def _validate_env(self):
        if not all([self.endpoint, self.api_key, self.deployment_name]):
            raise ValueError("Missing required environment variables: AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT_NAME")

    def chat(self, user_input: str) -> str:
        # Reload knowledge base to pick up any changes
        self.system_message = self._load_knowledge_base()
        self.history[0] = {"role": "system", "content": self.system_message}
        
        self.history.append({"role": "user", "content": user_input})
        
        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=self.history
            )
            assistant_response = response.choices[0].message.content
            self.history.append({"role": "assistant", "content": assistant_response})
            return assistant_response
        except Exception as e:
            return f"Error: {str(e)}"

    def reset_history(self):
        self.history = [{"role": "system", "content": self.system_message}]
