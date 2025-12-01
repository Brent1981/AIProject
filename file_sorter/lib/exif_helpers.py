# file_sorter/lib/exif_helpers.py
import exifread
import logging

logger = logging.getLogger(__name__)

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
