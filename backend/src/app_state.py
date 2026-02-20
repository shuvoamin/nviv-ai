import logging
from collections import deque
from datetime import datetime
from pathlib import Path
import os
import sys

# Add the current directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from chatbot import ChatBot

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from config import APP_NAME

# --- Configuration ---
# APP_NAME imported from config

# --- In-Memory Diagnostic Logging ---
LOG_BUFFER = deque(maxlen=100)

class DiagnosticLogger:
    def info(self, msg):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        LOG_BUFFER.append(f"[{timestamp}] INFO: {msg}")
        logger.info(msg)
    
    def error(self, msg):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        LOG_BUFFER.append(f"[{timestamp}] ERROR: {msg}")
        logger.error(msg)
    
    def warning(self, msg):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        LOG_BUFFER.append(f"[{timestamp}] WARNING: {msg}")
        logger.warning(msg)

diag_logger = DiagnosticLogger()

# Initialize ChatBot
try:
    chatbot = ChatBot()
    diag_logger.info("ChatBot initialized successfully via AppState.")
except Exception as e:
    diag_logger.error(f"Failed to initialize ChatBot: {e}")
    chatbot = None

# Shared Directories
STATIC_DIR = Path(__file__).parent.parent / "static"
IMAGES_DIR = STATIC_DIR / "generated_images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
