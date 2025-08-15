# YouTube Transcript Scanner

A Python Streamlit application for downloading, caching, and searching YouTube video transcripts with embedded video playback at specific timestamps.

## Features

- **Channel Transcript Downloads**: Enter YouTube channel handles (e.g., @joerogan) to download transcripts from recent videos
- **Smart Caching**: Permanent transcript storage for fast retrieval
- **Advanced Search**: Search across all cached transcripts with highlighted results
- **Embedded Video Playback**: Click timestamps to watch videos at exact moments where search terms appear
- **YouTube Data API Integration**: Fetch channel videos and metadata
- **WebShare Proxy Support**: Uses rotating residential proxies for reliable API access

## Setup

1. **Install Dependencies**:
   ```bash
   pip install streamlit youtube-transcript-api google-api-python-client requests
   ```

2. **Configure API Keys**:
   Create `.streamlit/secrets.toml` with your credentials:
   ```toml
   [youtube]
   api_key = "your_youtube_api_key_here"

   [webshare]
   username = "your_webshare_username"
   password = "your_webshare_password"

   [app]
   max_videos_per_channel = 50
   ```

3. **Run the Application**:
   ```bash
   streamlit run app.py
   ```

## Usage

### Add Channel Transcripts
1. Enter a YouTube channel handle in the sidebar (e.g., `@BenSullinsOfficial`)
2. Set the number of recent videos to download
3. Click "Download Channel Transcripts"

### Search Transcripts
1. Enter search terms in the main search box
2. View results with embedded videos
3. Click timestamps to jump to specific moments

### Manual Video Addition
- Enter individual YouTube video IDs for testing or specific videos

## File Structure

- `app.py` - Main Streamlit application
- `transcript_cache/` - Cached transcript JSON files
- `.streamlit/secrets.toml` - API configuration (not committed)
- `.github/copilot-instructions.md` - Development workflow

## API Requirements

- **YouTube Data API v3**: For fetching channel videos and metadata
- **WebShare Rotating Residential Proxies**: For reliable API access and rate limiting

## Technical Notes

- Uses YouTube Transcript API v1.2.2 with the updated `fetch()` method
- Transcripts are cached permanently for fast retrieval
- WebShare proxy integration prevents IP blocking
- Supports embedded video playback with timestamp navigation

## Development Status

✅ Core functionality implemented and tested
✅ API integrations working
✅ Caching system operational
✅ Search and playback features functional
