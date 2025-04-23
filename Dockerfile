# Use an official Python runtime as a parent image
FROM python:3.9-slim

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

# Install Flask, gallery-dl, and yt-dlp
RUN pip install --no-cache-dir Flask gallery-dl yt-dlp

# Copy the current directory contents into the container at /app
COPY . /app

# Create the directory for downloads
RUN mkdir downloads

# Expose the port the app runs on
EXPOSE 5000

# Run the application
# Using a production-ready WSGI server like Gunicorn is recommended for production
# For this example, we'll use Flask's built-in server
CMD ["flask", "run", "--host", "0.0.0.0"]
