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

# Function to download and cache transcripts
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

# Function to search all cached transcripts
def search_all_transcripts(search_term):
    results = []
    
    if not os.path.exists(CACHE_DIR):
        return results
    
    for filename in os.listdir(CACHE_DIR):
        if filename.endswith('.json'):
            video_id = filename[:-5]  # Remove .json extension
            
            with open(os.path.join(CACHE_DIR, filename), 'r') as f:
                transcript = json.load(f)
            
            for entry in transcript:
                if search_term.lower() in entry['text'].lower():
                    results.append({
                        'video_id': video_id,
                        'timestamp': entry['start'],
                        'text': entry['text']
                    })
    
    return results

# Sidebar for adding channels
st.sidebar.header("Add Channel")
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

# Main search interface
st.header("Search Transcripts")

# Show cached transcript count
cached_count = len([f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]) if os.path.exists(CACHE_DIR) else 0
st.info(f"Currently have {cached_count} cached transcripts")

search_term = st.text_input("Enter search term:")

if st.button("Search All Transcripts"):
    if search_term:
        results = search_all_transcripts(search_term)
        
        if results:
            st.success(f"Found {len(results)} results")
            
            for result in results:
                with st.expander(f"Video: {result['video_id']} - Timestamp: {result['timestamp']:.1f}s"):
                    st.write(result['text'])
                    
                    # YouTube embed with timestamp
                    video_url = f"https://www.youtube.com/embed/{result['video_id']}?start={int(result['timestamp'])}"
                    st.components.v1.iframe(video_url, width=560, height=315)
        else:
            st.warning("No results found in cached transcripts")
    else:
        st.error("Please enter a search term")

# Manual video ID input for testing
st.header("Manual Video Addition")
video_id_input = st.text_input("Enter YouTube Video ID to download transcript:")
if st.button("Download Single Video"):
    if video_id_input:
        with st.spinner("Downloading transcript..."):
            transcript = download_and_cache_transcript(video_id_input, use_proxy=False)
            if transcript:
                st.success(f"Successfully cached transcript for video {video_id_input}")
            else:
                st.error("Failed to download transcript")
