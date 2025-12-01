import os
import json
import logging
from flask import Flask, request, jsonify
from datetime import datetime
from lib.exif_helpers import get_exif_data
from lib.ollama_helpers import get_ollama_vision_response
from lib.path_helpers import generate_new_path_and_name, move_file

# --- Configuration ---
OLLAMA_API_BASE_URL = os.getenv("OLLAMA_API_BASE_URL", "http://ollama:11434")
LLAVA_MODEL_NAME = os.getenv("LLAVA_MODEL_NAME", "llava")
OCR_MODEL_NAME = os.getenv("OCR_MODEL_NAME", "llava")
TARGET_BASE_DIR = os.getenv("TARGET_BASE_DIR", "/organized_files")
LOG_FILE = os.getenv("LOG_FILE", "/var/log/file_sorter.log")

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)



# --- Flask Routes ---
@app.route('/process_file', methods=['POST'])
def process_file_endpoint():
    """
    API endpoint to receive a file path from n8n and process it.
    Expected JSON payload: {"file_path": "/path/to/new/file.jpg"}
    """
    data = request.get_json()
    file_path = data.get('file_path')

    if not file_path or not os.path.exists(file_path):
        logger.error(f"Invalid or non-existent file_path received: {file_path}")
        return jsonify({"status": "error", "message": "Invalid or non-existent file_path"}), 400

    logger.info(f"Received request to process file: {file_path}")

    # 1. Extract EXIF Data
    exif_data = get_exif_data(file_path)

    # 2. Get LLM Description
    description_prompt = "Describe this image in detail, focusing on objects, people, locations, and any text present."
    description = get_ollama_vision_response(file_path, LLAVA_MODEL_NAME, description_prompt)
    if not description:
        logger.warning(f"Could not get LLM description for {file_path}. Proceeding without it.")

    # 3. Perform OCR
    ocr_prompt = "Extract all text from this image."
    ocr_text = get_ollama_vision_response(file_path, OCR_MODEL_NAME, ocr_prompt)
    if not ocr_text:
        logger.warning(f"Could not perform OCR for {file_path}. Proceeding without it.")

    # 4. Generate New Path and Name
    new_file_path, target_folder = generate_new_path_and_name(file_path, description, ocr_text, exif_data)

    # 5. Move File
    if move_file(file_path, new_file_path, target_folder):
        return jsonify({
            "status": "success",
            "message": "File processed and organized successfully",
            "original_path": file_path,
            "new_path": new_file_path
        }), 200
    else:
        return jsonify({"status": "error", "message": "Failed to move file"}), 500

@app.route('/healthz', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    # Ensure the target base directory exists for the application
    os.makedirs(TARGET_BASE_DIR, exist_ok=True)
    app.run(host='0.0.0.0', port=5001)