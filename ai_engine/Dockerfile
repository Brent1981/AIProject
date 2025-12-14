# Use an official Python runtime as a parent image
FROM python:3.12-slim-bookworm

# Set the working directory in the container
WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code into the container at /app
COPY app.py .
COPY lib/ ./lib/

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Run gunicorn to serve the Flask application
# The command assumes your Flask app object is named 'app' inside app.py
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]