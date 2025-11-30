#!/bin/bash
set -e

# Get the directory of the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."

echo "Stopping the AI Powerhouse stack..."
cd "$PROJECT_ROOT"
docker-compose down

echo "AI Powerhouse stack stopped."
