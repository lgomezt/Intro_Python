"""Gemini API client configuration for notebook generation."""

import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

MODEL_NAME = "gemini-3-pro-preview"

# Generation defaults
DEFAULT_THINKING_BUDGET = -1  # Unlimited for generation tasks
DEFAULT_TEMPERATURE = 0.4     # Slightly creative but consistent
