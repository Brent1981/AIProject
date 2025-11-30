#!/bin/bash

# Exit on error
set -e

# --- Configuration ---
# Directory where backups are stored
BACKUP_DIR="/home/brent/aiproject/backups"
# Project directory where docker-compose.yml is located
PROJECT_DIR="/home/brent/aiproject"
# Project name (used as a prefix for Docker volume names)
PROJECT_NAME="aiproject"
# List of Docker volume names to restore (without project prefix)
VOLUMES_TO_RESTORE="chromadb_data ollama_models n8n_data file_intake"
# List of services to stop/start during restore
SERVICES_TO_MANAGE="ai_engine chromadb ollama n8n"
# --- End Configuration ---

# Check if a backup file was provided as an argument
if [ -z "$1" ]; then
    echo "Usage: $0 <path_to_backup_file.tar.gz>"
    echo "Example: $0 $BACKUP_DIR/ai_server_backup_2025-11-24_10-00-00.tar.gz"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file '$BACKUP_FILE' not found."
    exit 1
fi

echo "Starting restore process from: $BACKUP_FILE"

# --- Stop Services ---
echo "Stopping services to ensure data consistency: $SERVICES_TO_MANAGE"
cd "$PROJECT_DIR" && docker-compose stop $SERVICES_TO_MANAGE

# --- Extract Backup to Temporary Location ---
TEMP_RESTORE_DIR=$(mktemp -d)
echo "Extracting backup to temporary directory: $TEMP_RESTORE_DIR"
tar -xzf "$BACKUP_FILE" -C "$TEMP_RESTORE_DIR"

# --- Restore Volumes ---
for volume_suffix in $VOLUMES_TO_RESTORE; do
    volume_name="${PROJECT_NAME}_${volume_suffix}"
    volume_path=$(docker volume inspect -f '{{.Mountpoint}}' "$volume_name" 2>/dev/null || true)

    if [ -z "$volume_path" ]; then
        echo "Warning: Docker volume '$volume_name' does not exist. Creating it."
        docker volume create "$volume_name"
        volume_path=$(docker volume inspect -f '{{.Mountpoint}}' "$volume_name")
    fi

    if [ -z "$volume_path" ]; then
        echo "Error: Could not determine mountpoint for volume '$volume_name'. Skipping restore for this volume."
        continue
    fi

    SOURCE_DATA_PATH="$TEMP_RESTORE_DIR/$volume_suffix"

    if [ ! -d "$SOURCE_DATA_PATH" ]; then
        echo "Warning: No data found in backup for volume '$volume_name' at '$SOURCE_DATA_PATH'. Skipping restore for this volume."
        continue
    fi

    echo "Restoring volume '$volume_name' to '$volume_path'"
    # Clear existing data in the volume
    sudo rm -rf "$volume_path"/* "$volume_path"/.[!.]* || true # Remove all files and hidden files/dirs
    # Copy extracted data to the volume
    sudo cp -a "$SOURCE_DATA_PATH"/. "$volume_path"/
done

# Clean up the temporary directory
rm -rf "$TEMP_RESTORE_DIR"

# --- Start Services ---
echo "Starting services..."
cd "$PROJECT_DIR" && docker-compose start $SERVICES_TO_MANAGE

echo "Restore process complete."
