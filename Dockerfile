# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required by gallery-dl and yt-dlp
# yt-dlp requires ffmpeg for some formats
# gallery-dl might require other dependencies depending on the site
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy the current directory contents into the container at /app
COPY . /app

# Install Flask, gallery-dl, yt-dlp, and Gunicorn
# This step was moved AFTER COPY . /app to ensure requirements.txt is available
RUN pip install Flask gunicorn yt-dlp gallery-dl

# Create the directory for downloads
RUN mkdir downloads
# Add to your existing Dockerfile
RUN groupadd -r appuser && \
    useradd -r -g appuser appuser && \
    chown -R appuser:appuser /app

USER appuser
VOLUME /app/downloads


# Expose the port the app runs on
EXPOSE 5000

# Run the application using Gunicorn
# 'app:app' means run the 'app' object (your Flask app instance)
# from the 'app.py' file (the first 'app')
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
