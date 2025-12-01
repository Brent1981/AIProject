# ai_engine/lib/ollama_helpers.py
import os
import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL")

def call_ollama(prompt, model):
    """Sends a prompt to the Ollama API and returns the response."""
    print(f"Querying Ollama with model '{model}'...")
    print(f"-- OLLAMA PROMPT --\n{prompt}\n-- END OLLAMA PROMPT --")
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=60,
        )
        response.raise_for_status()
        print("Successfully received response from Ollama.")
        return response.json().get("response", "No response field found in Ollama reply.")
    except requests.exceptions.RequestException as e:
        print(f"Error calling Ollama API: {e}")
        return f"Error: Could not connect to Ollama at {OLLAMA_URL}."
