# Media Downloader

A simple, robust Flask web application for downloading media from various platforms like YouTube, Instagram, TikTok, Twitter, and more.

## Features

- ✅ **Simple & Clean UI**: Modern, responsive design with Tailwind CSS
- ✅ **Multi-platform Support**: YouTube, Instagram, TikTok, Twitter, and 1000+ sites via yt-dlp and gallery-dl
- ✅ **Background Processing**: Downloads run in background threads
- ✅ **Real-time Updates**: Auto-refresh shows download progress
- ✅ **Error Handling**: Robust error handling with user-friendly messages
- ✅ **No External Dependencies**: No Redis or database required
- ✅ **Docker Ready**: Easy deployment with Docker and docker-compose

## Quick Start

### Using Docker (Recommended)

```bash
# Clone and start
git clone <repository>
cd wapp
docker-compose up --build

# Access at http://localhost:12000
```

### Manual Installation

```bash
# Install dependencies
pip install -r requirements.txt
pip install yt-dlp gallery-dl

# Run the app
python app.py

# Access at http://localhost:12000
```

## Usage

1. Open the web interface
2. Paste a URL from any supported platform
3. Click "Download"
4. Wait for the download to complete
5. Click the green "Download" button to get your file

## Supported Platforms

- **YouTube** - Videos, playlists, channels
- **Instagram** - Posts, stories, reels
- **TikTok** - Videos
- **Twitter** - Videos, images
- **Facebook** - Videos
- **And 1000+ more sites** supported by yt-dlp

## Architecture

This is a complete rewrite of the original broken application with:

- **Simplified Architecture**: No Redis/RQ dependency
- **In-memory Job Management**: Uses Python threading for background downloads
- **Better Error Handling**: Comprehensive error catching and user feedback
- **Cleaner Code**: Modern Python with type hints and dataclasses
- **Responsive UI**: Mobile-friendly design
- **Auto-refresh**: Page updates automatically during downloads

## API Endpoints

- `GET /` - Main interface
- `POST /download` - Start a new download
- `GET /status/<job_id>` - Get job status (JSON)
- `GET /download/<job_id>` - Download completed file
- `GET /health` - Health check

## Configuration

Environment variables:
- `PORT` - Server port (default: 12000)
- `FLASK_ENV` - Environment (development/production)
- `SECRET_KEY` - Flask secret key (auto-generated if not set)

## File Storage

- Downloads are stored in `./downloads/` directory
- Temporary files use `./temp/` directory (auto-cleaned)
- Files are named with job ID prefix for security

## Security Features

- URL validation
- File access control via job IDs
- Temporary file cleanup
- Input sanitization
- CORS protection

## Improvements Over Original

The original app was broken due to:
- Redis connection issues
- Complex RQ worker setup
- Syntax errors in code
- Overly complex JavaScript
- Configuration mismatches
- Poor error handling

This rewrite fixes all these issues with a simpler, more maintainable architecture.