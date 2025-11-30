#!/bin/bash
set -e

# Get the directory of the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/../.." # Go up two levels to the project root

echo "Updating the project from git..."
cd "$PROJECT_ROOT"
git pull

echo "Restarting the AI Powerhouse stack to apply updates..."
# Call the start.sh script to handle the restart
"$SCRIPT_DIR/start.sh"

echo "Update and restart complete."
