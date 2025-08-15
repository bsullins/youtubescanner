import streamlit as st
import os
import json
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import WebshareProxyConfig
import time
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import re

# Create cache directory
CACHE_DIR = "transcript_cache"
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# Set up Streamlit app
st.title("YouTube Transcript Searcher")

# Initialize YouTube API
@st.cache_resource
def get_youtube_service():
    api_key = st.secrets["youtube"]["api_key"]
    return build('youtube', 'v3', developerKey=api_key)

# Initialize YouTube Transcript API with WebShare proxy
@st.cache_resource
def get_transcript_api():
    proxy_config = WebshareProxyConfig(
        proxy_username=st.secrets["webshare"]["username"],
        proxy_password=st.secrets["webshare"]["password"]
    )
    return YouTubeTranscriptApi(proxy_config=proxy_config)

# Function to extract channel ID from handle
def get_channel_id_from_handle(channel_handle):
    try:
        youtube = get_youtube_service()
        
        # Remove @ if present
        handle = channel_handle.lstrip('@')
        
        # Search for channel
        search_response = youtube.search().list(
            q=handle,
            type='channel',
            part='id,snippet',
            maxResults=1
        ).execute()
        
        if search_response['items']:
            return search_response['items'][0]['id']['channelId']
        else:
            # Try with custom URL format
            channels_response = youtube.channels().list(
                part='id',
                forUsername=handle
            ).execute()
            
            if channels_response['items']:
                return channels_response['items'][0]['id']
                
        return None
    except HttpError as e:
        st.error(f"YouTube API error: {e}")
        return None

# Function to get channel videos
def get_channel_videos(channel_handle, max_videos=10):
    try:
        youtube = get_youtube_service()
        
        # Get channel ID
        channel_id = get_channel_id_from_handle(channel_handle)
        if not channel_id:
            st.error(f"Could not find channel: {channel_handle}")
            return []
        
        # Get uploads playlist
        channels_response = youtube.channels().list(
            id=channel_id,
            part='contentDetails'
        ).execute()
        
        uploads_playlist_id = channels_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        
        # Get videos from uploads playlist
        playlist_response = youtube.playlistItems().list(
            playlistId=uploads_playlist_id,
            part='snippet',
            maxResults=min(max_videos, 50)
        ).execute()
        
        videos = []
        for item in playlist_response['items']:
            videos.append({
                'video_id': item['snippet']['resourceId']['videoId'],
                'title': item['snippet']['title'],
                'published_at': item['snippet']['publishedAt']
            })
        
        return videos
        
    except HttpError as e:
        st.error(f"YouTube API error: {e}")
        return []

# Function to get video metadata
def get_video_metadata(video_id):
    try:
        youtube = get_youtube_service()
        
        # Get video details
        video_response = youtube.videos().list(
            part='snippet',
            id=video_id
        ).execute()
        
        if video_response['items']:
            video_info = video_response['items'][0]['snippet']
            return {
                'title': video_info['title'],
                'published_at': video_info['publishedAt'],
                'channel_title': video_info['channelTitle'],
                'description': video_info.get('description', '')
            }
    except Exception as e:
        st.error(f"Error fetching metadata for {video_id}: {e}")
    
    return {
        'title': f'Video {video_id}',
        'published_at': 'Unknown',
        'channel_title': 'Unknown',
        'description': ''
    }
def download_and_cache_transcript(video_id, use_proxy=True):
    cache_file = os.path.join(CACHE_DIR, f"{video_id}.json")
    
    # Check if cached
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            return json.load(f)
    
    try:
        if use_proxy:
            # Use WebShare proxy configuration
            ytt_api = get_transcript_api()
        else:
            # Use without proxy
            ytt_api = YouTubeTranscriptApi()
        
        # Fetch transcript using the new API
        fetched_transcript = ytt_api.fetch(video_id)
        
        # Convert to raw data format for caching
        transcript_data = fetched_transcript.to_raw_data()
        
        # Cache the transcript
        with open(cache_file, 'w') as f:
            json.dump(transcript_data, f)
            
        return transcript_data
    except Exception as e:
        st.error(f"Error downloading transcript for {video_id}: {e}")
        return None

# Function to get all unique channels from cached transcripts
def get_cached_channels():
    channels = set()
    
    if not os.path.exists(CACHE_DIR):
        return []
    
    for filename in os.listdir(CACHE_DIR):
        if filename.endswith('.json'):
            video_id = filename[:-5]
            try:
                metadata = get_video_metadata(video_id)
                if metadata['channel_title'] != 'Unknown':
                    channels.add(metadata['channel_title'])
            except:
                continue
    
    return sorted(list(channels))

# Function to create smart search pattern for plurals
def create_smart_search_pattern(search_term):
    """
    Creates a regex pattern that matches the search term and its common plural forms
    while maintaining whole word boundaries.
    """
    escaped_term = re.escape(search_term.lower())
    
    # Handle common plural patterns
    patterns = [escaped_term]  # Original term
    
    # Add plural variations
    if search_term.endswith('y'):
        # city -> cities, berry -> berries
        stem = escaped_term[:-1]
        patterns.append(stem + 'ies')
    elif search_term.endswith(('s', 'sh', 'ch', 'x', 'z')):
        # bus -> buses, dish -> dishes, box -> boxes
        patterns.append(escaped_term + 'es')
    elif search_term.endswith('f'):
        # leaf -> leaves, wolf -> wolves
        stem = escaped_term[:-1]
        patterns.append(stem + 'ves')
    elif search_term.endswith('fe'):
        # knife -> knives, wife -> wives
        stem = escaped_term[:-2]
        patterns.append(stem + 'ves')
    else:
        # Regular plurals: cat -> cats, dog -> dogs
        patterns.append(escaped_term + 's')
    
    # Also handle reverse - if someone searches for plural, find singular
    if search_term.endswith('ies'):
        # cities -> city, berries -> berry
        stem = escaped_term[:-3]
        patterns.append(stem + 'y')
    elif search_term.endswith('ves'):
        # leaves -> leaf, knives -> knife
        stem = escaped_term[:-3]
        patterns.append(stem + 'f')
        patterns.append(stem + 'fe')
    elif search_term.endswith('es') and len(search_term) > 3:
        # dishes -> dish, boxes -> box (but not "es" -> "e")
        stem = escaped_term[:-2]
        patterns.append(stem)
    elif search_term.endswith('s') and len(search_term) > 2:
        # cats -> cat, dogs -> dog (but not "is" -> "i")
        stem = escaped_term[:-1]
        patterns.append(stem)
    
    # Create pattern with word boundaries
    pattern_string = r'\b(?:' + '|'.join(patterns) + r')\b'
    return re.compile(pattern_string, re.IGNORECASE)

# Function to search all cached transcripts
def search_all_transcripts(search_term, channel_filter=None):
    results = []
    
    if not os.path.exists(CACHE_DIR):
        return results
    
    # Create smart search pattern that handles plurals
    pattern = create_smart_search_pattern(search_term)
    
    for filename in os.listdir(CACHE_DIR):
        if filename.endswith('.json'):
            video_id = filename[:-5]  # Remove .json extension
            
            with open(os.path.join(CACHE_DIR, filename), 'r') as f:
                transcript = json.load(f)
            
            video_results = []
            for entry in transcript:
                # Use smart pattern for whole word matching with plurals
                if pattern.search(entry['text']):
                    video_results.append({
                        'timestamp': entry['start'],
                        'text': entry['text']
                    })
            
            if video_results:
                # Get video metadata
                metadata = get_video_metadata(video_id)
                
                # Apply channel filter if specified
                if channel_filter and channel_filter != "All Channels" and metadata['channel_title'] != channel_filter:
                    continue
                
                results.append({
                    'video_id': video_id,
                    'metadata': metadata,
                    'matches': video_results
                })
    
    # Sort results by publish date (newest first)
    results.sort(key=lambda x: x['metadata']['published_at'], reverse=True)
    
    return results

# Sidebar for adding channels and manual videos
st.sidebar.header("Add Content")

# Channel section
st.sidebar.subheader("Add Channel")
channel_handle = st.sidebar.text_input("Enter YouTube Channel Handle (e.g., @joerogan):")
max_videos = st.sidebar.number_input("Number of videos to download:", min_value=1, max_value=50, value=10)

if st.sidebar.button("Download Channel Transcripts"):
    if channel_handle:
        with st.sidebar:
            with st.spinner(f"Fetching videos from {channel_handle}..."):
                videos = get_channel_videos(channel_handle, max_videos)
                
            if videos:
                st.success(f"Found {len(videos)} videos")
                
                # Create progress bar
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                downloaded_count = 0
                for i, video in enumerate(videos):
                    status_text.text(f"Downloading transcript {i+1}/{len(videos)}: {video['title'][:50]}...")
                    
                    transcript = download_and_cache_transcript(video['video_id'], use_proxy=True)
                    if transcript:
                        downloaded_count += 1
                    
                    progress_bar.progress((i + 1) / len(videos))
                    time.sleep(0.5)  # Rate limiting
                
                status_text.text(f"Completed! Downloaded {downloaded_count}/{len(videos)} transcripts")
                st.balloons()
            else:
                st.error("No videos found or error accessing channel")
    else:
        st.sidebar.error("Please enter a channel handle")

# Manual video section
st.sidebar.subheader("Add Single Video")
video_id_input = st.sidebar.text_input("Enter YouTube Video ID:")
if st.sidebar.button("Download Video Transcript"):
    if video_id_input:
        with st.sidebar:
            with st.spinner("Downloading transcript..."):
                transcript = download_and_cache_transcript(video_id_input, use_proxy=False)
                if transcript:
                    st.success(f"Successfully cached transcript for video {video_id_input}")
                else:
                    st.error("Failed to download transcript")

# Main search interface
st.header("Search Transcripts")

# Search input and channel filter
col1, col2 = st.columns([3, 1])

with col1:
    search_term = st.text_input("Enter search term:")

with col2:
    # Get available channels for filter
    available_channels = get_cached_channels()
    channel_options = ["All Channels"] + available_channels
    channel_filter = st.selectbox("Filter by channel:", channel_options)

if search_term:
    results = search_all_transcripts(search_term, channel_filter)
    
    if results:
        st.success(f"Found {sum(len(r['matches']) for r in results)} results across {len(results)} videos")
        
        for video_result in results:
            video_id = video_result['video_id']
            metadata = video_result['metadata']
            matches = video_result['matches']
            
            # Format publish date
            try:
                from datetime import datetime
                publish_date = datetime.fromisoformat(metadata['published_at'].replace('Z', '+00:00'))
                formatted_date = publish_date.strftime("%B %d, %Y")
            except:
                formatted_date = metadata['published_at']
            
            # Separator line above each video result
            st.markdown("---")
            
            # Video header with title and metadata
            st.markdown(f"## {metadata['title']}")
            st.markdown(f"**Channel:** {metadata['channel_title']} | **Published:** {formatted_date}")
            
            # Create a container for the video player that can be updated
            video_container = st.empty()
            
            # Default video URL starts at the first match timestamp
            first_match_timestamp = int(matches[0]['timestamp'])
            current_video_url = f"https://www.youtube.com/embed/{video_id}?start={first_match_timestamp}"
            
            # Show matches with clickable timestamps
            st.markdown(f"**{len(matches)} matches found:**")
            
            # Check if any timestamp button was clicked
            clicked_timestamp = None
            for i, match in enumerate(matches):
                timestamp_seconds = int(match['timestamp'])
                
                # Create clickable timestamp
                col1, col2 = st.columns([1, 4])
                with col1:
                    if st.button(f"{timestamp_seconds//60}:{timestamp_seconds%60:02d}", key=f"{video_id}_{i}"):
                        clicked_timestamp = timestamp_seconds
                with col2:
                    st.write(f"*{match['text']}*")
            
            # Update video URL if a timestamp was clicked (with autoplay)
            if clicked_timestamp is not None:
                current_video_url = f"https://www.youtube.com/embed/{video_id}?start={clicked_timestamp}&autoplay=1"
            
            # Display the video (either default or with timestamp)
            with video_container:
                st.components.v1.iframe(current_video_url, width=560, height=315)
    else:
        st.warning("No results found in cached transcripts")