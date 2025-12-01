# file_sorter/lib/ollama_helpers.py
import os
import base64
import requests
import logging

logger = logging.getLogger(__name__)

OLLAMA_API_BASE_URL = os.getenv("OLLAMA_API_BASE_URL", "http://ollama:11434")

def get_ollama_vision_response(file_path, model_name, prompt):
    """
    Sends an image to a multimodal LLM (e.g., LLaVA) and gets a response.
    """
    logger.info(f"Sending {file_path} to LLM for description using model {model_name}")
    try:
        with open(file_path, "rb") as f:
            image_data = f.read()

        encoded_image = base64.b64encode(image_data).decode('utf-8')

        headers = {"Content-Type": "application/json"}
        payload = {
            "model": model_name,
            "prompt": prompt,
            "images": [encoded_image],
            "stream": False
        }
        response = requests.post(f"{OLLAMA_API_BASE_URL}/api/generate", headers=headers, json=payload)
        response.raise_for_status()
        response_text = response.json().get("response", "").strip()
        logger.info(f"LLM response for {file_path}: {response_text[:100]}...")
        return response_text
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling Ollama API: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during LLM request: {e}")
        return None
