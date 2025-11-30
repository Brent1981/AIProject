#!/bin/bash

# Exit on error
set -e

# --- Configuration ---
# Directory where backups will be stored
BACKUP_DIR="/home/brent/aiproject/backups"
# Project directory name (used as a prefix for volume names)
PROJECT_NAME="aiproject"
# List of Docker volume names to back up (without project prefix)
VOLUMES_TO_BACKUP="chromadb_data ollama_models n8n_data file_intake"
# Number of old backups to keep
RETENTION_DAYS=7
# --- End Configuration ---

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Timestamp for the backup file
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_FILENAME="ai_server_backup_${TIMESTAMP}.tar.gz"
BACKUP_PATH="$BACKUP_DIR/$BACKUP_FILENAME"

echo "Starting backup of Docker volumes..."
echo "Backup file will be saved to: $BACKUP_PATH"

# --- Get Volume Paths & Create Backup ---
TEMP_BACKUP_DIR=$(mktemp -d)
echo "Using temporary directory: $TEMP_BACKUP_DIR"

for volume_suffix in $VOLUMES_TO_BACKUP; do
    volume_name="${PROJECT_NAME}_${volume_suffix}"
    volume_path=$(docker volume inspect -f '{{.Mountpoint}}' "$volume_name")
    if [ -z "$volume_path" ]; then
        echo "Warning: Could not find path for volume '$volume_name'. Skipping."
        continue
    fi
    echo "Backing up volume '$volume_name' from '$volume_path'"
    # Create a subdirectory in the temp dir that matches the volume name suffix
    mkdir -p "$TEMP_BACKUP_DIR/$volume_suffix"
    # Use tar to pipe the volume contents directly into the subdirectory
    tar -C "$volume_path" -c . | tar -C "$TEMP_BACKUP_DIR/$volume_suffix" -x
done

echo "Creating compressed archive..."
tar -czf "$BACKUP_PATH" -C "$TEMP_BACKUP_DIR" .

# Clean up the temporary directory
rm -rf "$TEMP_BACKUP_DIR"

echo "Backup created successfully!"

# --- Cleanup Old Backups ---
echo "Cleaning up old backups (older than $RETENTION_DAYS days)..."
find "$BACKUP_DIR" -name "ai_server_backup_*.tar.gz" -mtime +"$RETENTION_DAYS" -exec rm -v {} \;

echo "Backup process complete."
