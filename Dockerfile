# Use a slim Python base image
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies, including ffmpeg for yt-dlp
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install/update yt-dlp and gallery-dl using pip
RUN pip install --no-cache-dir --upgrade yt-dlp gallery-dl

# Copy the rest of your application code into the container
COPY . .

# The default command to run the Flask app with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]