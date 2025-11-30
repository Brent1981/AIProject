import os
import json
import logging
from flask import Flask, request, jsonify
import requests
import exifread
from datetime import datetime

# --- Configuration ---
# This should ideally come from environment variables or a config file
OLLAMA_API_BASE_URL = os.getenv("OLLAMA_API_BASE_URL", "http://ollama:11434")
LLAVA_MODEL_NAME = os.getenv("LLAVA_MODEL_NAME", "llava")
OCR_MODEL_NAME = os.getenv("OCR_MODEL_NAME", "llava") # Assuming LLaVA can do basic OCR or another model will be used
TARGET_BASE_DIR = os.getenv("TARGET_BASE_DIR", "/organized_files") # Base directory for organized files
LOG_FILE = os.getenv("LOG_FILE", "/var/log/file_sorter.log")

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- Helper Functions ---
def get_exif_data(file_path):
    """
    Extracts EXIF data from an image file using the exifread library.
    """
    logger.info(f"Attempting to extract EXIF data from {file_path}")
    exif_data = {}
    try:
        with open(file_path, 'rb') as f:
            tags = exifread.process_file(f, details=False) # details=False is faster

        if not tags:
            logger.warning(f"No EXIF information found in {file_path}")
            return exif_data

        # Extract specific tags and convert them to strings
        if 'EXIF DateTimeOriginal' in tags:
            exif_data['DateTimeOriginal'] = str(tags['EXIF DateTimeOriginal'])
        if 'Image Make' in tags:
            exif_data['Make'] = str(tags['Image Make'])
        if 'Image Model' in tags:
            exif_data['Model'] = str(tags['Image Model'])
        
        logger.info(f"Extracted EXIF: {exif_data}")

    except Exception as e:
        logger.error(f"Error extracting EXIF from {file_path}: {e}")
    
    return exif_data

def get_llm_description(file_path, model_name):
    """
    Sends an image to a multimodal LLM (e.g., LLaVA) for description.
    """
    logger.info(f"Sending {file_path} to LLM for description using model {model_name}")
    try:
        with open(file_path, "rb") as f:
            image_data = f.read() # Read image as bytes

        # Ollama expects base64 encoded images
        import base64
        encoded_image = base64.b64encode(image_data).decode('utf-8')

        headers = {"Content-Type": "application/json"}
        payload = {
            "model": model_name,
            "prompt": "Describe this image in detail, focusing on objects, people, locations, and any text present.",
            "images": [encoded_image],
            "stream": False
        }
        response = requests.post(f"{OLLAMA_API_BASE_URL}/api/generate", headers=headers, json=payload)
        response.raise_for_status()
        description = response.json().get("response", "").strip()
        logger.info(f"LLM description for {file_path}: {description[:100]}...")
        return description
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling Ollama API for description: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during LLM description: {e}")
        return None

def perform_ocr(file_path, model_name):
    """
    Performs OCR on an image or document using an LLM or dedicated OCR service.
    For now, it reuses the LLaVA model with a specific prompt.
    """
    logger.info(f"Performing OCR on {file_path} using model {model_name}")
    try:
        with open(file_path, "rb") as f:
            image_data = f.read()

        import base64
        encoded_image = base64.b64encode(image_data).decode('utf-8')

        headers = {"Content-Type": "application/json"}
        payload = {
            "model": model_name,
            "prompt": "Extract all text from this image.",
            "images": [encoded_image],
            "stream": False
        }
        response = requests.post(f"{OLLAMA_API_BASE_URL}/api/generate", headers=headers, json=payload)
        response.raise_for_status()
        ocr_text = response.json().get("response", "").strip()
        logger.info(f"OCR text for {file_path}: {ocr_text[:100]}...")
        return ocr_text
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling Ollama API for OCR: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during OCR: {e}")
        return None

def generate_new_path_and_name(original_file_path, description, ocr_text, exif_data):
    """
    Generates a new, descriptive file path and name based on extracted data.
    This is the core logic for organization.
    """
    logger.info(f"Generating new path and name for {original_file_path}")
    # Placeholder logic - this will be highly customized
    file_extension = os.path.splitext(original_file_path)[1].lower()
    base_name = os.path.basename(original_file_path)

    # Example: Use date from EXIF or current date
    date_str = exif_data.get('DateTimeOriginal', datetime.now().strftime("%Y:%m:%d %H:%M:%S")).split(' ')[0].replace(':', '-')
    year = date_str.split('-')[0]
    month_num = date_str.split('-')[1]
    month_name = datetime.strptime(month_num, "%m").strftime("%B")

    # Simple keyword extraction from description/OCR for folder/filename
    keywords = []
    if description:
        keywords.extend([word.lower() for word in description.split() if len(word) > 3 and word.isalpha()])
    if ocr_text:
        keywords.extend([word.lower() for word in ocr_text.split() if len(word) > 3 and word.isalpha()])

    # Deduplicate and prioritize keywords
    unique_keywords = sorted(list(set(keywords)), key=keywords.count, reverse=True)[:3] # Top 3 keywords

    # Construct a more descriptive name
    descriptive_name = "_".join(unique_keywords) if unique_keywords else "untitled"
    new_filename = f"{date_str}_{descriptive_name}{file_extension}"

    # Construct folder structure: TARGET_BASE_DIR/Year/MonthName/Keywords/
    target_folder = os.path.join(TARGET_BASE_DIR, year, f"{month_num}-{month_name}", descriptive_name)
    new_file_path = os.path.join(target_folder, new_filename)

    logger.info(f"Generated new path: {new_file_path}")
    return new_file_path, target_folder

def move_file(source_path, destination_path, target_folder):
    """
    Moves the file to its new organized location, creating directories if necessary.
    """
    logger.info(f"Moving file from {source_path} to {destination_path}")
    try:
        os.makedirs(target_folder, exist_ok=True)
        os.rename(source_path, destination_path)
        logger.info(f"Successfully moved {source_path} to {destination_path}")
        return True
    except Exception as e:
        logger.error(f"Error moving file {source_path} to {destination_path}: {e}")
        return False

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
    description = get_llm_description(file_path, LLAVA_MODEL_NAME)
    if not description:
        logger.warning(f"Could not get LLM description for {file_path}. Proceeding without it.")

    # 3. Perform OCR
    ocr_text = perform_ocr(file_path, OCR_MODEL_NAME)
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
    app.run(host='0.0.0.0', port=5001) # Using a different port than ai_engine
