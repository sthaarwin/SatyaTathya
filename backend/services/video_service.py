import yt_dlp
import os
import uuid

import ffmpeg

DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def download_video(url: str):
    """
    Downloads a video from the given URL using yt-dlp.
    Ensures the format is H.264 MP4 and compresses it using FFmpeg.
    Returns the path where the compressed video was saved and metadata.
    """
    video_id = str(uuid.uuid4())
    raw_path = os.path.join(DOWNLOAD_DIR, f"{video_id}_raw.mp4")
    final_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp4")
    
    ydl_opts = {
        'format': 'best',
        'outtmpl': raw_path,
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            video_title = info_dict.get('title', 'Unknown Title')
            
            # Use FFmpeg to enforce H.264 codec (no HEVC) and compress via CRF
            # Adding pix_fmt='yuv420p' provides the widest compatibility across media players
            try:
                (
                    ffmpeg
                    .input(raw_path)
                    .output(final_path, vcodec='libx264', crf=28, preset='fast', acodec='aac', pix_fmt='yuv420p')
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
            except ffmpeg.Error as e:
                raise Exception(f"FFmpeg compression error: {e.stderr.decode('utf8', 'ignore')}")

            # Clean up the uncompressed/raw file
            if os.path.exists(raw_path):
                os.remove(raw_path)
            
            return {
                "video_id": video_id,
                "title": video_title,
                "file_path": final_path
            }
    except Exception as e:
        raise Exception(f"Failed to download or process video: {str(e)}")
