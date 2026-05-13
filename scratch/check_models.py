import os
from google import genai
from dotenv import load_dotenv
from pathlib import Path

# Load .env from backend folder
env_path = Path("backend") / ".env"
load_dotenv(dotenv_path=env_path)

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("ERROR: GEMINI_API_KEY not found in backend/.env")
    exit(1)

client = genai.Client(api_key=api_key)

print("--- AVAILABLE MODELS ---")
try:
    for model in client.models.list():
        print(f"Name: {model.name} | Display Name: {model.display_name}")
except Exception as e:
    print(f"Error listing models: {e}")
