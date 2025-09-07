from yt_dlp import YoutubeDL
import os
import re
import sys
from typing import Optional, List, Dict, Tuple
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache


@lru_cache(maxsize=128)
def get_url_info(url: str) -> Tuple[bool, Dict]:
    """
    Get URL information with caching to avoid duplicate yt-dlp calls.
    Returns (is_playlist, info_dict) for efficient reuse.

    Args:
        url (str): YouTube URL to analyze

    Returns:
        Tuple[bool, Dict]: (is_playlist, info_dict)
    """
    try:
        # Use yt-dlp to extract info without downloading
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,  # Only extract basic info, faster
            'no_warnings': True,
            'skip_download': True,
            'playlist_items': '1',  # Only check first item for speed
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            # Check if info extraction was successful
            if info is None:
                # Fallback to URL parsing if yt-dlp fails
                parsed_url = urlparse(url)
                query_params = parse_qs(parsed_url.query)
                is_playlist = 'list' in query_params
                return is_playlist, {}

            is_playlist = info.get('_type') == 'playlist'
            return is_playlist, info

    except Exception:
        # Simple fallback: check for 'list' parameter
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        is_playlist = 'list' in query_params
        return is_playlist, {}


def is_playlist_url(url: str) -> bool:
    """
    Check if the provided URL is a playlist or a single video using cached detection.
    Uses yt-dlp's native detection with simple URL parsing fallback.

    Args:
        url (str): YouTube URL to check

    Returns:
        bool: True if URL is a playlist, False if single video
    """
    is_playlist, _ = get_url_info(url)
    return is_playlist


def parse_multiple_urls(input_string: str) -> List[str]:
    """
    Parse multiple URLs from input string separated by commas, spaces, newlines, or mixed formats.
    Handles complex mixed separators like "url1, url2 url3\nurl4".

    Args:
        input_string (str): String containing one or more URLs

    Returns:
        List[str]: List of cleaned URLs
    """
    # Use regex to split by multiple separators: comma, space, newline, tab
    urls = re.split(r'[,\s\n\t]+', input_string.strip())
    urls = [url.strip() for url in urls if url.strip()]

    # Validate URLs (basic YouTube URL check)
    valid_urls = []
    invalid_count = 0
    for url in urls:
        if 'youtube.com' in url or 'youtu.be' in url:
            valid_urls.append(url)
        elif url:  # Only show warning for non-empty strings
            print(f"⚠️  Skipping invalid URL: {url}")
            invalid_count += 1

    if invalid_count > 0:
        print(
            f"💡 Found {len(valid_urls)} valid YouTube URLs, skipped {invalid_count} invalid entries")

    return valid_urls


def get_available_formats(url: str) -> None:
    """
    List available formats for debugging purposes.

    Args:
        url (str): YouTube URL to check formats for
    """
    ydl_opts = {
        'listformats': True,
        'quiet': False
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=False)
    except Exception as e:
        print(f"Error listing formats: {str(e)}")


def download_single_video(url: str, output_path: str, thread_id: int = 0, audio_only: bool = False) -> dict:
    """
    Download a single YouTube video or playlist.

    Args:
        url (str): YouTube URL to download
        output_path (str): Directory to save the download
        thread_id (int): Thread identifier for logging
        audio_only (bool): If True, download audio only in MP3 format

    Returns:
        dict: Result status with success/failure info
    """
    if audio_only:
        # Configure for audio-only MP3 downloads
        format_selector = 'bestaudio/best'
        file_extension = 'mp3'
        postprocessors = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
        print(f"🎵 [Thread {thread_id}] Audio-only mode: Downloading MP3...")
    else:
        # Configure for video downloads
        format_selector = (
            # Try best video+audio combination first
            'bestvideo[height<=1080]+bestaudio/best[height<=1080]/'
            # Fallback to best available quality
            'best'
        )
        file_extension = 'mp4'
        postprocessors = [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }]

    # Configure yt-dlp options
    ydl_opts = {
        'format': format_selector,
        'ignoreerrors': True,
        'no_warnings': False,
        'extract_flat': False,
        # Disable additional downloads for clean output
        'writesubtitles': False,
        'writethumbnail': False,
        'writeautomaticsub': False,
        'postprocessors': postprocessors,
        # Clean up options
        'keepvideo': False,
        'clean_infojson': True,
        'retries': 3,
        'fragment_retries': 3,
        # Ensure playlists are fully downloaded
        'noplaylist': False,  # Allow playlist downloads
    }

    # Add merge format for video downloads only
    if not audio_only:
        ydl_opts['merge_output_format'] = 'mp4'

    # Set different output templates for playlists and single videos
    is_playlist, cached_info = get_url_info(url)

    # Debug: Print detection result
    if thread_id == 1:  # Only print for first thread to avoid spam
        print(
            f"🔍 [Debug] URL analysis: {'Playlist' if is_playlist else 'Single video'}")

    if is_playlist:
        ydl_opts['outtmpl'] = os.path.join(
            output_path, '%(playlist_title)s', f'%(playlist_index)s-%(title)s.{file_extension}')
        content_type = "playlist"
        print(
            f"🎵 [Thread {thread_id}] Detected playlist URL. Downloading entire playlist...")
    else:
        ydl_opts['outtmpl'] = os.path.join(
            output_path, f'%(title)s.{file_extension}')
        content_type = "video"
        print(
            f"🎥 [Thread {thread_id}] Detected single video URL. Downloading {'audio' if audio_only else 'video'}...")

    try:
        with YoutubeDL(ydl_opts) as ydl:
            # Extract fresh info for download (cached info is only for detection)
            info = ydl.extract_info(url, download=False)

            # Check if info extraction was successful
            if info is None:
                return {
                    'url': url,
                    'success': False,
                    'message': f"❌ [Thread {thread_id}] Failed to extract video information. Video may be private or unavailable."
                }

            if info.get('_type') == 'playlist':
                playlist_title = info.get('title', 'Unknown Playlist')
                video_count = len(info.get('entries', []))
                print(
                    f"📋 [Thread {thread_id}] Playlist: '{playlist_title}' ({video_count} videos)")

                # Ensure we have entries to download
                if video_count == 0:
                    return {
                        'url': url,
                        'success': False,
                        'message': f"❌ [Thread {thread_id}] Playlist appears to be empty or private"
                    }

            # Download content
            ydl.download([url])

            if info.get('_type') == 'playlist':
                return {
                    'url': url,
                    'success': True,
                    'message': f"✅ [Thread {thread_id}] Playlist '{playlist_title}' download completed! ({video_count} {'MP3s' if audio_only else 'videos'})"
                }
            else:
                return {
                    'url': url,
                    'success': True,
                    'message': f"✅ [Thread {thread_id}] {'Audio' if audio_only else 'Video'} download completed successfully!"
                }

    except Exception as e:
        return {
            'url': url,
            'success': False,
            'message': f"❌ [Thread {thread_id}] Error: {str(e)}"
        }


def download_youtube_content(urls: List[str], output_path: Optional[str] = None,
                             list_formats: bool = False, max_workers: int = 3, audio_only: bool = False) -> None:
    """
    Download YouTube content (single videos or playlists) in MP4 format or MP3 audio only.
    Supports multiple URLs for simultaneous downloading.

    Args:
        urls (List[str]): List of YouTube URLs to download
        output_path (str, optional): Directory to save the downloads. Defaults to './downloads'
        list_formats (bool): If True, only list available formats without downloading
        max_workers (int): Maximum number of concurrent downloads
        audio_only (bool): If True, download audio only in MP3 format
    """
    # Set default output path if none provided
    if output_path is None:
        output_path = os.path.join(os.getcwd(), 'downloads')

    # If user wants to list formats, do that for the first URL and return
    if list_formats:
        print("Available formats for the first provided URL:")
        get_available_formats(urls[0])
        return

    # Create output directory if it doesn't exist
    os.makedirs(output_path, exist_ok=True)

    print(
        f"\n🚀 Starting download of {len(urls)} URL(s) with {max_workers} concurrent workers...")
    print(f"📁 Output directory: {output_path}")
    print(f"🎧 Format: {'MP3 Audio Only' if audio_only else 'MP4 Video'}")

    # Show what types of content we're downloading
    playlist_count = sum(1 for url in urls if is_playlist_url(url))
    video_count = len(urls) - playlist_count
    if playlist_count > 0 and video_count > 0:
        print(
            f"📋 Content: {playlist_count} playlist(s) + {video_count} video(s)")
    elif playlist_count > 0:
        print(f"📋 Content: {playlist_count} playlist(s)")
    else:
        print(f"🎥 Content: {video_count} video(s)")

    print("-" * 60)

    # Concurrent downloads
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(download_single_video, url, output_path, i+1, audio_only): url
            for i, url in enumerate(urls)
        }

        # Collect results
        for future in as_completed(future_to_url):
            result = future.result()
            results.append(result)
            print(result['message'])

    print("\n" + "=" * 60)
    print("📊 DOWNLOAD SUMMARY")
    print("=" * 60)

    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]

    print(f"✅ Successful downloads: {len(successful)}")
    print(f"❌ Failed downloads: {len(failed)}")

    if failed:
        print("\n❌ Failed URLs:")
        for result in failed:
            print(f"   • {result['url']}")
            print(f"     Reason: {result['message']}")

    if successful:
        print(f"\n🎉 All files saved to: {output_path}")


if __name__ == "__main__":
    # Check for command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == '--list-formats':
        url = input("Enter the YouTube URL to list formats: ")
        download_youtube_content([url], list_formats=True)
    else:
        # Normal download flow
        print("📥 YouTube Multi-Video Downloader")
        print("=" * 50)
        print("💡 SUPPORTED INPUT FORMATS:")
        print("   🔸 Single URL: Just paste one YouTube URL")
        print("   🔸 Comma-separated: url1, url2, url3")
        print("   🔸 Space-separated: url1 url2 url3")
        print("   🔸 Mixed format: url1, url2 url3, url4")
        print("   🔸 Multi-line: Press Enter without typing, then one URL per line")
        print("-" * 50)

        urls_input = input("Enter YouTube URL(s): ")

        # Handle multi-line input
        if not urls_input.strip():
            print("📝 Multi-line mode activated!")
            print("💡 Enter one URL per line, press Enter twice when finished:")
            urls_list = []
            line_count = 1
            while True:
                line = input(f"   URL {line_count}: ")
                if line.strip() == "":
                    break
                urls_list.append(line)
                line_count += 1
            urls_input = '\n'.join(urls_list)

        if not urls_input.strip():
            print("❌ No URLs entered. Exiting...")
            exit(1)

        urls = parse_multiple_urls(urls_input)

        if not urls:
            print("❌ No valid YouTube URLs found. Please try again.")
            exit(1)

        print(f"\n✅ Found {len(urls)} valid URL(s)")
        for i, url in enumerate(urls, 1):
            print(f"   {i}. {url}")

        output_dir = input(
            "\nEnter output directory (press Enter for default): "
        ).strip()

        # Ask for format preference
        format_choice = input(
            "\nChoose format:\n"
            "  1. MP4 Video (default)\n"
            "  2. MP3 Audio only\n"
            "Enter choice (1-2, default=1): ").strip()

        audio_only = False
        if format_choice == '2':
            audio_only = True
            print("🎵 Selected: MP3 Audio only")
        else:
            print("🎥 Selected: MP4 Video")

        # Only ask for concurrent workers if there are multiple URLs
        max_workers = 1  # Default for single URL
        if len(urls) > 1:
            workers_input = input(
                "Number of concurrent downloads (1-5, default=3): ").strip()
            try:
                max_workers = int(workers_input) if workers_input else 3
                max_workers = max(1, min(5, max_workers))  # Clamp between 1-5
            except ValueError:
                max_workers = 3

        print(f"\n🎬 Starting downloads...")
        print(f"📊 URLs to download: {len(urls)}")
        print(f"🎧 Format: {'MP3 Audio' if audio_only else 'MP4 Video'}")
        if len(urls) > 1:
            print(f"⚡ Concurrent workers: {max_workers}")
        print(
            f"📁 Output: {output_dir if output_dir else 'default (./downloads)'}")

        if output_dir:
            download_youtube_content(
                urls, output_dir, max_workers=max_workers, audio_only=audio_only)
        else:
            download_youtube_content(
                urls, max_workers=max_workers, audio_only=audio_only)
