# Deployment Guide - Nviv AI Chatbot

This guide covers multiple deployment options for your Azure OpenAI chatbot application.

## Prerequisites

- Azure account with an active subscription
- Azure OpenAI resource with deployed model
- Git repository (for some deployment methods)

## Option 1: Azure App Service (Recommended)

Azure App Service is ideal for hosting both the Python backend and React frontend.

### Backend Deployment

1. **Build the frontend:**
   ```bash
   cd frontend
   npm run build
   ```

2. **Serve frontend from backend:**
   Update `src/api.py` to serve the built frontend files:
   ```python
   from fastapi.staticfiles import StaticFiles
   
   # Add after CORS middleware
   app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")
   ```

3. **Create `startup.sh`:**
   ```bash
   #!/bin/bash
   export PYTHONPATH=$PYTHONPATH:$(pwd)/backend/src
   uvicorn backend.src.api:app --host 0.0.0.0 --port 8000
   ```

4. **Deploy to Azure App Service:**
   ```bash
   az webapp up --runtime PYTHON:3.9 --sku B1 --name <your-app-name>
   ```
   *Note: `az webapp up` and the VS Code Azure extension normally ignore files in `.gitignore` (which includes `frontend/dist`). We have added an `.azureignore` and `.vscode/settings.json` to ensure the compiled frontend is included when you deploy.*

5. **Configure environment variables** in Azure Portal under Configuration → Application settings.

### Using Azure CLI

```bash
# Login
az login

# Create resource group
az group create --name chatbot-rg --location eastus

# Create App Service plan
az appservice plan create --name chatbot-plan --resource-group chatbot-rg --sku B1 --is-linux

# Create web app
az webapp create --resource-group chatbot-rg --plan chatbot-plan --name <your-app-name> --runtime "PYTHON:3.9"

# Configure startup command
az webapp config set --resource-group chatbot-rg --name <your-app-name> --startup-file "startup.sh"

# Deploy code
az webapp up --name <your-app-name> --resource-group chatbot-rg
```

## Option 2: Docker Deployment

### Build and Run Locally

```bash
# Build the image
docker build -t azure-chatbot .

# Run the container
docker run -d -p 8000:8000 --env-file .env --name chatbot azure-chatbot
```

### Deploy to Azure Container Instances

```bash
# Create container registry
az acr create --resource-group chatbot-rg --name <registry-name> --sku Basic

# Build and push image
az acr build --registry <registry-name> --image azure-chatbot:latest .

# Deploy to ACI
az container create \
  --resource-group chatbot-rg \
  --name chatbot-container \
  --image <registry-name>.azurecr.io/azure-chatbot:latest \
  --dns-name-label <unique-dns-name> \
  --ports 8000 \
  --environment-variables \
    AZURE_OPENAI_ENDPOINT=$AZURE_OPENAI_ENDPOINT \
    AZURE_OPENAI_API_KEY=$AZURE_OPENAI_API_KEY \
    AZURE_OPENAI_DEPLOYMENT_NAME=$AZURE_OPENAI_DEPLOYMENT_NAME
```

## Option 3: Other Cloud Platforms

### Render

1. Create a new Web Service
2. Connect your GitHub repository
3. Set build command: `cd frontend && npm install && npm run build && cd .. && pip install -r requirements.txt`
4. Set start command: `uvicorn src.api:app --host 0.0.0.0 --port $PORT`
5. Add environment variables

### Railway

1. Create new project from GitHub
2. Add environment variables
3. Railway auto-detects Python and deploys

### Heroku

```bash
# Create Procfile
echo "web: uvicorn src.api:app --host 0.0.0.0 --port \$PORT" > Procfile

# Deploy
heroku create <app-name>
heroku config:set AZURE_OPENAI_ENDPOINT=<value>
heroku config:set AZURE_OPENAI_API_KEY=<value>
heroku config:set AZURE_OPENAI_DEPLOYMENT_NAME=<value>
git push heroku main
```

## Option 4: GitHub Actions Deployment (CI/CD)

Automate your deployments whenever you push to the `main` branch.

### 1. Configure GitHub Secrets

1.  In your GitHub repository, go to **Settings** > **Secrets and variables** > **Actions**.
2.  Click **New repository secret**.
3.  Name: `AZURE_WEBAPP_PUBLISH_PROFILE`.
4.  Value: Paste the content of the Publish Profile downloaded from the Azure Portal (App Service > Get publish profile).

### 2. Update Workflow File

1.  Open [.github/workflows/deploy.yml](file:///.github/workflows/deploy.yml).
2.  Replace `'YOUR_APP_NAME'` with your actual Azure App Service name.

### 3. Deploy

Push your changes to the `main` branch:
```bash
git add .
git commit -m "Add GitHub Actions workflow"
git push origin main
```
The workflow will automatically trigger and deploy your app.


## Setting Environment Variables in Azure

Since this app uses Azure OpenAI, you must set your API keys as **Environment Variables** (Application Settings) in the Azure Portal so the backend can access them.

1.  In the **Azure Portal**, go to your **App Service** (nviv).
2.  On the left menu, select **Settings** > **Environment variables** (or **Configuration** in some versions).
3.  Under the **App settings** tab, click **+ Add**.
4.  Add the following variables:
    *   **Azure OpenAI (Chat)**: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT_NAME`, `AZURE_OPENAI_API_VERSION`.
    *   **Azure AI Foundry (Images)**: `AZURE_OPENAI_FLUX_URL`, `AZURE_OPENAI_FLUX_DEPLOYMENT`.
    *   **Twilio (WhatsApp)**: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`.
    *   **Meta (Native WhatsApp)**: `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN`.
5.  Click **Apply** at the bottom, then click **Confirm** to restart your app with the new settings.

---

## Production Checklist

- [ ] Build frontend for production (`npm run build`)
- [ ] Set all environment variables
- [ ] Configure CORS for production domain
- [ ] Enable HTTPS
- [ ] Set up monitoring and logging
- [ ] Configure auto-scaling (if needed)
- [ ] Set up CI/CD pipeline
- [ ] Test all endpoints in production

---

## WhatsApp Integration (via Twilio)

You can now connect your chatbot to WhatsApp using Twilio.

### 1. Twilio Sandbox Setup
1.  Go to the **Twilio Console** > **Messaging** > **Try it Out** > **Send a WhatsApp message**.
2.  Follow the instructions to join the Sandbox (e.g., text `join <your-sandbox-word>` to your Sandbox number).

### 2. Configure Webhook
1.  In the Twilio Console, go to **Messaging** > **Settings** > **WhatsApp Sandbox Settings**.
2.  Under **Sandbox Configuration**, find the field **"WHEN A MESSAGE COMES IN"**.
3.  Set the URL to: `https://<your-app-name>.azurewebsites.net/whatsapp`
4.  Ensure the method is set to `POST`.
5.  Click **Save**.

### 3. Test on WhatsApp
1.  Send a message to your Twilio Sandbox number.
2.  The AI should respond back directly in your WhatsApp chat!

> [!NOTE]
> The `/whatsapp` endpoint returns TwiML, which Twilio uses to format the response message. Azure OpenAI environment variables must be correctly configured for the response to be generated.

---

## Native Meta WhatsApp Integration

Alternatively, you can connect directly to Meta's Business Platform without Twilio.

### 1. Meta App Setup
1.  Create an app on the **Meta App Dashboard**.
2.  Add the **WhatsApp** product to your app.
3.  In the **WhatsApp** > **Configuration** tab:
    - **Callback URL**: `https://<your-app-name>.azurewebsites.net/meta/webhook`
    - **Verify Token**: Set a custom string (e.g., `nviv_verify_token`).
4.  Copy your **Phone Number ID** and **Permanent Access Token**.

### 2. Configure Environment Variables
Add these to your Azure App Service:
- `WHATSAPP_ACCESS_TOKEN`: Your Meta Access Token.
- `WHATSAPP_PHONE_NUMBER_ID`: Your Phone Number ID.
- `WHATSAPP_VERIFY_TOKEN`: The same token you set in the Meta Console.

### 3. Test
1.  Whitelist your phone number in the Meta Dashboard (for test numbers).
2.  Send a message or a voice note! The bot will respond via the Meta Graph API.
