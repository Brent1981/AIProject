# /addons/central_ai_addon/Dockerfile
FROM python:3.9-slim-buster

# Set up the working directory
WORKDIR /app

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY run.py .

# Command to run the application
CMD [ "python3", "-u", "run.py" ]
