import os
import json
import logging
import time
import argparse
from typing import Dict, Optional, Tuple, List
from urllib import request
from urllib.parse import urlparse
import numpy as np
from bs4 import BeautifulSoup
from tqdm import tqdm
import re
import subprocess
from yt_dlp import YoutubeDL
from dotenv import load_dotenv

# Load environment variables from .env file (optional)
# This allows configuring COOKIE_FILE path via a .env file if desired.
load_dotenv()

# --- Constants from the reference YouTube download script ---
THROTTLE_TIME = 20
COOLDOWN_TIME = 10  # Base cooldown time for YouTube downloads in seconds (used in np.random.normal)
SAMPLE_RATE = 44100  # Sample rate for audio conversion
CHANNELS = 2  # Number of audio channels for conversion

# Try to get COOKIE_FILE path from environment variable "COOKIE_FILE" or use a default.
# The .env file can set this environment variable.
# Default is "cookies.txt" in the current working directory.
DEFAULT_COOKIE_FILE_NAME = "cookies.txt"
COOKIE_FILE_PATH_FROM_ENV = os.getenv("COOKIE_FILE")
if COOKIE_FILE_PATH_FROM_ENV:
    COOKIE_FILE = os.path.abspath(COOKIE_FILE_PATH_FROM_ENV)
    # print(f"Using COOKIE_FILE from environment variable: {COOKIE_FILE}")
else:
    COOKIE_FILE = os.path.abspath(DEFAULT_COOKIE_FILE_NAME)
    # print(f"Using default COOKIE_FILE path: {COOKIE_FILE} (can be set with COOKIE_FILE env var)")


# --- Global logger setup (adapted from reference script) ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Prevent multiple handlers if script/module is reloaded (e.g., in interactive sessions)
if not logger.handlers:
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Error File Handler: logs errors to "yt_download.error" in the CWD.
    # Consider making this path configurable or relative to output_base_dir for production use.
    error_log_filename = "yt_download.error"
    file_handler = logging.FileHandler(error_log_filename, mode="w", encoding="utf-8")
    file_handler.setLevel(logging.ERROR)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    # print(f"Error logs will be written to: {os.path.abspath(error_log_filename)}")

logger.info(f"Using COOKIE_FILE: {COOKIE_FILE}")
if not os.path.exists(COOKIE_FILE):
    logger.warning(
        f"Cookie file not found at {COOKIE_FILE}. "
        "Downloads may fail for age-restricted, private, or member-only videos."
    )

# --- Global variables for YouTube request cooldown management (from reference script) ---
yt_time = 0  # Timestamp of the last YouTube download attempt

# --- yt-dlp options setup (from reference script, enhanced) ---
# This is a template; 'outtmpl' will be set per download.
ydl_opts_template = {
    "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "format_sort": ["ext:mp4:m4a"], # Try to get mp4 directly
    "merge_output_format": "mp4", # Merge to mp4 if separate streams are downloaded
    "quiet": True, # Suppress yt-dlp console output
    "no_warnings": True, # Suppress yt-dlp warnings
    "recode_video": "mp4", # Recode to mp4 if necessary after download
    "cookiefile": COOKIE_FILE,
    "socket_timeout": 60, # Timeout for network operations
    "noprogress": True, # Do not print progress bar
    "retries": 5, # Number of retries for downloads (yt-dlp internal)
    "fragment_retries": 5, # Number of retries for downloading fragments (yt-dlp internal)
    # 'verbose': True, # Uncomment for detailed yt-dlp debugging output
    # 'ignoreerrors': True, # If True, yt-dlp will try to continue on download errors for playlists (not typically used for single videos)
}


def throttle_youtube_download(url: str, ydl_opts: dict) -> Optional[dict]:
    """
    Downloads a video using yt-dlp, incorporating a cooldown mechanism.
    Based on the reference script's throttling logic.
    Args:
        url: The YouTube URL to download.
        ydl_opts: The yt-dlp options dictionary for this specific download.
    Returns:
        Info dictionary from yt-dlp on success, None on failure.
    """
    global yt_time
    current_time = time.time()

    # Cooldown logic: if the last attempt was less than 5 seconds ago, sleep.
    # The sleep duration is randomized around COOLDOWN_TIME.
    if current_time - yt_time < THROTTLE_TIME:  # Minimum 5s interval enforced before starting this longer sleep
        sleep_duration = np.random.normal(COOLDOWN_TIME, COOLDOWN_TIME / 2)
        # Cap sleep duration (e.g., between 0.5*COOLDOWN_TIME and 1.5*COOLDOWN_TIME)
        min_sleep = max(1.0, COOLDOWN_TIME / 2) # Ensure at least 1s, and at least half of cooldown
        max_sleep = COOLDOWN_TIME * 1.5
        sleep_duration = np.clip(sleep_duration, min_sleep, max_sleep)
        
        logger.info(f"Throttling YouTube download for {url}. Sleeping for {sleep_duration:.2f}s.")
        time.sleep(sleep_duration)

    try:
        # Create a new YoutubeDL instance for each download to ensure options are fresh.
        with YoutubeDL(ydl_opts) as ydl:
            logger.info(f"Attempting to download: {url} (Output template: {ydl_opts.get('outtmpl')})")
            # extract_info with download=True will perform the download.
            info = ydl.extract_info(url, download=True)
        yt_time = time.time()  # Update timestamp after a successful download attempt cycle
        return info
    except Exception as e:
        # Log specific yt-dlp known errors for clarity
        error_str = str(e).lower()
        if "video unavailable" in error_str or "private video" in error_str or "age restricted" in error_str:
            logger.error(f"Download failed for {url}. Reason: Video unavailable/private/age-restricted. Details: {e}")
        elif "http error 429" in error_str or "too many requests" in error_str:
            logger.error(f"Download failed for {url} due to rate limiting (429 Too Many Requests). Details: {e}")
        elif "urlopen error [errno 110] connection timed out" in error_str or "socket timeout" in error_str:
             logger.error(f"Download failed for {url} due to connection/socket timeout. Details: {e}")
        else:
            logger.error(f"Generic error during YouTube download for {url}. Details: {e}")
        yt_time = time.time()  # Update timestamp even on failure to respect cooldown for the next URL
        return None


def convert_to_wav(video_path: str, audio_path: str) -> bool:
    """
    Extracts audio from a video file and saves it as a WAV file using FFmpeg.
    Args:
        video_path: Path to the input video file.
        audio_path: Path where the output WAV file will be saved.
    Returns:
        True if conversion was successful, False otherwise.
    """
    if not os.path.exists(video_path):
        logger.error(f"Cannot convert to WAV: Video file not found at {video_path}")
        return False

    # FFmpeg command arguments
    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output file if it exists
        "-i", video_path,
        "-vn",  # Disable video recording (audio only)
        "-acodec", "pcm_s16le",  # Audio codec for WAV (signed 16-bit PCM, little-endian)
        "-ar", str(SAMPLE_RATE),  # Audio sample rate
        "-ac", str(CHANNELS),  # Number of audio channels
        "-hide_banner",       # Suppress FFmpeg's informational banner
        "-loglevel", "error",  # Log only errors from FFmpeg to stderr
        audio_path,
    ]
    try:
        logger.info(f"Converting '{video_path}' to '{audio_path}' using FFmpeg.")
        # subprocess.run with check=True will raise CalledProcessError on non-zero exit code
        process = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding='utf-8')
        logger.info(f"FFmpeg conversion successful for '{video_path}'. Output at '{audio_path}'.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg audio extraction failed for '{video_path}'.")
        logger.error(f"Command: {' '.join(cmd)}")
        logger.error(f"FFmpeg Return Code: {e.returncode}")
        logger.error(f"FFmpeg stderr: {e.stderr.strip() if e.stderr else 'N/A'}")
        logger.error(f"FFmpeg stdout: {e.stdout.strip() if e.stdout else 'N/A'}")
        return False
    except FileNotFoundError:
        logger.error(
            "ffmpeg command not found. Please ensure FFmpeg is installed and in your system's PATH."
        )
        return False


def download_video_and_audio(youtube_url: str, output_dir: str, base_ydl_opts: dict) -> bool:
    """
    Downloads a YouTube video to the specified directory, ensuring it's 'video.mp4',
    and then converts it to 'audio.wav'.
    Args:
        youtube_url: The URL of the YouTube video.
        output_dir: The directory where 'video.mp4' and 'audio.wav' will be saved.
        base_ydl_opts: The base yt-dlp options template.
    Returns:
        True if both download and conversion are successful, False otherwise.
    """
    os.makedirs(output_dir, exist_ok=True)  # Ensure the output directory exists

    video_filename_base = "video" # The base name for the video file
    final_video_path = os.path.join(output_dir, f"{video_filename_base}.mp4")
    audio_path = os.path.join(output_dir, "audio.wav")

    # Create a copy of the ydl_opts template and set the output path specifically for this download
    current_ydl_opts = base_ydl_opts.copy()
    # yt-dlp will use this template to name the output file.
    # With merge_output_format="mp4" and recode_video="mp4", it should result in "video.mp4".
    current_ydl_opts["outtmpl"] = os.path.join(output_dir, f"{video_filename_base}.%(ext)s")
    
    logger.info(f"Starting download process for {youtube_url} into directory {output_dir}")
    download_info = throttle_youtube_download(youtube_url, current_ydl_opts)

    if not download_info:
        logger.error(f"Video download failed for {youtube_url} (throttle_youtube_download returned None).")
        return False

    # After throttle_youtube_download, check if 'video.mp4' was successfully created.
    # yt-dlp (with recode_video="mp4") should handle the naming to video.mp4 if outtmpl is set as above.
    # Add a robust check for the final video file.
    video_check_timeout = 45  # seconds to wait for video.mp4 to appear and be non-empty
    time_waited = 0
    check_interval = 1 # second
    
    while not (os.path.exists(final_video_path) and os.path.getsize(final_video_path) > 0):
        if time_waited >= video_check_timeout:
            logger.error(f"Video file '{final_video_path}' not found or is empty after download attempt for {youtube_url}. Timeout ({video_check_timeout}s) reached.")
            try:
                dir_contents = os.listdir(output_dir)
                logger.error(f"Contents of '{output_dir}': {dir_contents}")
                # Look for partial files or files with different extensions
                for item in dir_contents:
                    if item.startswith(video_filename_base) and not item.endswith(".mp4"):
                        logger.warning(f"Found related file: '{item}'. Download might be incomplete, or recoding failed.")
            except Exception as e_ls:
                logger.error(f"Could not list directory '{output_dir}': {e_ls}")
            return False
        time.sleep(check_interval)
        time_waited += check_interval
    
    logger.info(f"Video '{final_video_path}' confirmed for {youtube_url} (size: {os.path.getsize(final_video_path)} bytes).")

    # Convert the downloaded video to WAV
    if not convert_to_wav(final_video_path, audio_path):
        logger.error(f"Audio conversion to WAV failed for '{final_video_path}'.")
        # Depending on requirements, one might still consider this a partial success if video is present.
        # For this script, we aim for both, so it's a failure if WAV isn't produced.
        return False

    logger.info(f"Successfully downloaded video and converted to audio for {youtube_url}. Files in '{output_dir}'.")
    return True


def download_videos_for_songs(input_file: str, output_base_dir: str):
    """
    Loads song data from a JSON file. For each song and language,
    downloads the corresponding YouTube video and converts it to WAV audio.
    """
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            songs_data = json.load(f)
    except FileNotFoundError:
        logger.error(f"Input JSON file not found: {input_file}")
        return
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON from file '{input_file}': {e}")
        return

    # Handle both old dict format and new array format
    if isinstance(songs_data, list):
        # New array format - convert to dict for processing
        songs_dict = {}
        for song_item in songs_data:
            if "song_title" in song_item:
                song_key = song_item["song_title"]
                # Create song_info dict with all fields except song_title
                song_info = {k: v for k, v in song_item.items() if k != "song_title"}
                songs_dict[song_key] = song_info
        songs_data = songs_dict
    elif not isinstance(songs_data, dict):
        logger.error(f"Unexpected data format in {input_file}. Expected list or dict.")
        return

    os.makedirs(output_base_dir, exist_ok=True)
    failed_log_path = os.path.join(output_base_dir, "failed_video_downloads.jsonl")
    logger.info(f"Failed downloads will be logged to: {failed_log_path}")

    global ydl_opts_template # Use the globally defined template

    for song_key, song_info in tqdm(songs_data.items(), desc="Downloading Videos"):
        logger.info(f"Processing song: '{song_key}'")
        
        youtube_urls_by_lang = song_info.get("youtube_url")
        if not isinstance(youtube_urls_by_lang, dict):
            logger.warning(f"Skipping '{song_key}': 'youtube_url' field is missing or not a dictionary.")
            with open(failed_log_path, "a", encoding="utf-8") as f_jsonl:
                failure_data = {"song_key": song_key, "reason": "'youtube_url' field missing or not a dictionary in input."}
                f_jsonl.write(json.dumps(failure_data, ensure_ascii=False) + "\n")
            continue

        for lang_code, yt_url in youtube_urls_by_lang.items():
            if not yt_url or not isinstance(yt_url, str) or not (yt_url.startswith("http://") or yt_url.startswith("https://")):
                logger.debug(f"Skipping language '{lang_code}' for song '{song_key}': Invalid or no YouTube URL provided ('{yt_url}').")
                continue

            lang_output_dir = os.path.join(output_base_dir, song_key, lang_code)
            final_video_path = os.path.join(lang_output_dir, "video.mp4")
            audio_path = os.path.join(lang_output_dir, "audio.wav")

            # Check if both video and audio files already exist and are non-empty
            video_exists = os.path.exists(final_video_path) and os.path.getsize(final_video_path) > 0
            audio_exists = os.path.exists(audio_path) and os.path.getsize(audio_path) > 0

            if video_exists and audio_exists:
                logger.info(f"Video and audio for '{song_key}' ({lang_code}) already exist in '{lang_output_dir}'. Skipping.")
                continue
            
            if video_exists and not audio_exists:
                logger.info(f"Video for '{song_key}' ({lang_code}) exists at '{final_video_path}', but audio.wav is missing or empty. Attempting conversion.")
                if convert_to_wav(final_video_path, audio_path):
                    logger.info(f"Successfully converted existing video to WAV for '{song_key}' ({lang_code}).")
                    continue # Successfully processed this language version
                else:
                    logger.warning(f"Failed to convert existing video to WAV for '{song_key}' ({lang_code}). This might indicate an issue with the video file or ffmpeg.")
                    # Log this specific conversion failure. We won't re-download if video is present.
                    with open(failed_log_path, "a", encoding="utf-8") as f_jsonl:
                        failure_data = {
                            "song_key": song_key, "language": lang_code, "youtube_url": yt_url,
                            "reason": "Existing video.mp4, but audio.wav conversion failed."}
                        f_jsonl.write(json.dumps(failure_data, ensure_ascii=False) + "\n")
                    continue # Move to next item, as re-attempting download_video_and_audio might not help if video is corrupt


            # If files don't exist or video exists but audio conversion failed above (and we decided to retry)
            logger.info(f"Attempting to download video for '{song_key}' ({lang_code}) from: {yt_url}")
            
            os.makedirs(lang_output_dir, exist_ok=True) # Ensure directory is there before calling download helper

            success = download_video_and_audio(yt_url, lang_output_dir, ydl_opts_template)

            if success:
                logger.info(f"Successfully downloaded and processed '{song_key}' ({lang_code}) from {yt_url}")
            else:
                logger.warning(f"Failed to download or process video for '{song_key}' ({lang_code}) from {yt_url}.")
                # Log this failure to the JSONL file
                failure_data = {
                    "song_key": song_key, "language": lang_code, "youtube_url": yt_url,
                    "reason": "download_video_and_audio helper function reported failure. Check logs for details."}
                try:
                    with open(failed_log_path, "a", encoding="utf-8") as f_jsonl:
                        f_jsonl.write(json.dumps(failure_data, ensure_ascii=False) + "\n")
                except IOError as e_io:
                    logger.error(f"Could not write to failed items log '{failed_log_path}': {e_io}")
        
    logger.info("YouTube video download and processing script finished.")


def main():
    parser = argparse.ArgumentParser(
        description="Download YouTube videos based on URLs from a JSON file and convert them to WAV audio."
    )
    parser.add_argument(
        "--input",
        type=str,
        default="mavl_dataset.json",
        help="Path to the input JSON file (e.g., mavl_dataset.json). "
             "Each entry should have a 'youtube_url' field, which is a dictionary mapping lang_code to video URL.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="mavl_datasets",
        help="Base directory to save downloaded video ('video.mp4') and audio ('audio.wav') files.",
    )
    args = parser.parse_args()

    logger.info(f"Starting YouTube download process. Input JSON: '{args.input}', Output Base Directory: '{args.output}'")
    download_videos_for_songs(args.input, args.output)
    logger.info("Main script execution completed.")


if __name__ == "__main__":
    # Example usage:
    # python download_yt.py --input path/to/your/song_database.json --output path/to/your/video_audio_output_directory
    main()
