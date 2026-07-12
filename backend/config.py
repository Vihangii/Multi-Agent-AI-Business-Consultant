import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-4o-mini"

# Backend API Configuration
BACKEND_HOST = "0.0.0.0"
BACKEND_PORT = 8000

# Validate API key on import
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found. Please set it in the .env file.")
