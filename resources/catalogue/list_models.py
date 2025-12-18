
import google.generativeai as genai
import os
from dotenv import load_dotenv
import sys

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    api_key = os.getenv("GOOGLE_API_KEY_1")

with open("models.txt", "w") as f:
    if not api_key:
        f.write("❌ No GOOGLE_API_KEY found.\n")
    else:
        try:
            f.write(f"Python: {sys.version}\n")
            f.write(f"GenAI SDK: {genai.__version__}\n")
            genai.configure(api_key=api_key)
            f.write("Available Models:\n")
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    f.write(f"- {m.name}\n")
        except Exception as e:
            f.write(f"❌ Error: {e}\n")
