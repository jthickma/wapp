# Start with a Python base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies in a single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies including yt-dlp and gallery-dl
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir yt-dlp gallery-dl

# Copy the rest of the application code
COPY . .

# Expose the port the app runs on
EXPOSE 5000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py

# Default command (can be overridden by Coolify)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
