# file_sorter/lib/path_helpers.py
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

TARGET_BASE_DIR = os.getenv("TARGET_BASE_DIR", "/organized_files")

def generate_new_path_and_name(original_file_path, description, ocr_text, exif_data):
    """
    Generates a new, descriptive file path and name based on extracted data.
    This is the core logic for organization.
    """
    logger.info(f"Generating new path and name for {original_file_path}")
    
    file_extension = os.path.splitext(original_file_path)[1].lower()
    original_filename = os.path.basename(original_file_path)
    now = datetime.now()

    # 1. Determine the date
    file_date = None
    if exif_data.get('DateTimeOriginal'):
        try:
            # EXIF format is 'YYYY:MM:DD HH:MM:SS'
            file_date = datetime.strptime(exif_data['DateTimeOriginal'], '%Y:%m:%d %H:%M:%S')
        except ValueError:
            logger.warning(f"Could not parse EXIF date: {exif_data['DateTimeOriginal']}")
    
    if not file_date:
        try:
            # Fallback to file modification time
            mtime = os.path.getmtime(original_file_path)
            file_date = datetime.fromtimestamp(mtime)
        except Exception as e:
            logger.error(f"Could not get file modification time: {e}")
            file_date = now # Final fallback

    date_str = file_date.strftime("%Y-%m-%d")
    time_str = file_date.strftime("%H%M%S")
    year = file_date.strftime("%Y")
    month_num = file_date.strftime("%m")
    month_name = file_date.strftime("%B")

    # 2. Determine file type and base folder
    photo_extensions = ['.jpg', '.jpeg', '.png', '.heic', '.dng', '.raw']
    doc_extensions = ['.pdf', '.doc', '.docx', '.txt']
    
    if file_extension in photo_extensions:
        base_folder = "Photos"
        target_folder = os.path.join(TARGET_BASE_DIR, base_folder, year, f"{month_num}-{month_name}")
    elif file_extension in doc_extensions:
        base_folder = "Documents"
        target_folder = os.path.join(TARGET_BASE_DIR, base_folder, year)
    else:
        base_folder = "Unsorted"
        target_folder = os.path.join(TARGET_BASE_DIR, base_folder, year)

    # 3. Generate a descriptive name
    descriptive_part = ""
    if description:
        # A simple approach to get a few descriptive words
        # This can be replaced with a more advanced NLP keyword extraction
        words = [word.lower() for word in description.split() if len(word) > 4 and word.isalpha()]
        descriptive_part = "_".join(words[:3]) # Use up to 3 keywords

    if not descriptive_part:
        # Fallback to original filename without extension
        descriptive_part = os.path.splitext(original_filename)[0].replace(" ", "_")

    new_filename = f"{date_str}_{time_str}_{descriptive_part}{file_extension}"

    # 4. Combine for the full new path
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
