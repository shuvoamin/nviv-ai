# Azure Chatbot Demo

This is a simple demo project for building a chatbot using Azure OpenAI and Python.

## Prerequisites

- Python 3.8 or higher
- An Azure OpenAI resource with a deployed model (e.g., GPT-3.5 or GPT-4)

## Setup

1.  **Clone the repository or navigate to the project directory:**

    ```bash
    cd azure-chatbot-demo
    ```

2.  **Create a virtual environment (optional but recommended):**

    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables:**

    - Copy the `.env.example` file to a new file named `.env`:

      ```bash
      cp .env.example .env
      ```

    - Open `.env` in a text editor and fill in your credentials:
        
        **Azure OpenAI (Chat)**
        - `AZURE_OPENAI_ENDPOINT`: Your Azure OpenAI endpoint URL.
        - `AZURE_OPENAI_API_KEY`: Your Azure OpenAI API key.
        - `AZURE_OPENAI_DEPLOYMENT_NAME`: The name of your deployed model (e.g., `gpt-35-turbo`).
        - `AZURE_OPENAI_API_VERSION`: API version (default is `2024-02-15-preview`).

        **Azure AI Foundry (Image Generation)**
        - `AZURE_OPENAI_FLUX_URL`: The REST endpoint for the FLUX model in Azure AI Foundry.
        - `AZURE_OPENAI_FLUX_DEPLOYMENT`: The deployment name for FLUX (e.g., `flux-2-pro`).

        **Twilio (WhatsApp)**
        - `TWILIO_ACCOUNT_SID`: Your Twilio Account SID.
        - `TWILIO_AUTH_TOKEN`: Your Twilio Auth Token.
        - `TWILIO_FROM_NUMBER`: Your Twilio WhatsApp number (e.g., `whatsapp:+14155238886`).

        **Meta (Native WhatsApp)**
        - `WHATSAPP_ACCESS_TOKEN`: Your Meta Permanent Access Token.
        - `WHATSAPP_PHONE_NUMBER_ID`: Your WhatsApp Phone Number ID.
        - `WHATSAPP_VERIFY_TOKEN`: A custom string for webhook verification.

## Usage

### CLI Chatbot

Run the chatbot in the terminal:

```bash
python src/main.py
```

Type your message and press Enter. To exit, type `quit` or `exit`.

### API

Run the API server:

```bash
uvicorn api:app --app-dir src --reload
```

The API will be available at `http://localhost:8000`.

## Frontend Web App

1.  **Navigate to the frontend directory:**

    ```bash
    cd frontend
    ```

2.  **Install dependencies:**

    ```bash
    npm install
    ```

3.  **Run the full stack (Frontend + Backend):**

    ```bash
    npm run dev:all
    ```

    This command starts both the FastAPI backend (on port 8000) and the React frontend (usually on port 5173). Open the URL shown in the terminal (likely `http://localhost:5173`).


**Endpoints:**

- `POST /chat`: Send a message to the chatbot.
  - Body: `{"message": "Hello"}`
  - Response: `{"message": "..."}`
  - Optional: `{"message": "Start over", "reset": true}` to reset conversation history.

- `GET /health`: Health check.

## Debugging

This project includes VS Code launch configurations for debugging.

### VS Code Debugging

1.  Open the project in VS Code.
2.  Go to the **Run and Debug** view or press `Cmd+Shift+D` (macOS).
3.  Select a configuration:
    - **Python: Current File**: suitable for running `src/main.py`.
    - **Python: API (FastAPI)**: suitable for running the API server with reloading disabled (debugging with auto-reload can be tricky, but this config attempts to work with it).
4.  Set breakpoints in your code (e.g., in `src/chatbot.py` or `src/api.py`).
5.  Press `F5` to start debugging.

### Manual Debugging

You can also use `pdb` in your code:

```python
import pdb; pdb.set_trace()
```

## Deployment

For detailed deployment instructions, see [deployment_guide.md](deployment_guide.md).

### Quick Deploy to Azure

1. **Build the frontend:**
   ```bash
   cd frontend && npm run build && cd ..
   ```

2. **Deploy using Azure CLI:**
   ```bash
   az webapp up --runtime PYTHON:3.9 --sku B1 --name <your-app-name>
   ```

3. **Set environment variables** in Azure Portal under Configuration.

### Docker Deployment

```bash
docker build -t azure-chatbot .
docker run -d -p 8000:8000 --env-file .env azure-chatbot
```

For more deployment options (Azure Container Instances, Render, Railway, Heroku), see the full [deployment guide](deployment_guide.md).
