import os
import ffmpeg
import imagehash
from PIL import Image

def generate_video_fingerprint(file_path: str) -> str:
    """
    Generates a unique visual fingerprint for a video.
    It extracts 3 frames (at 20%, 50%, and 80% mark) and calculates a perceptual hash (phash).
    This ensures even if the video is re-downloaded or slightly compressed differently, 
    the core visual hash remains identical.
    """
    try:
        # Get exact duration of the video to find proper timestamps
        probe = ffmpeg.probe(file_path)
        duration = float(probe['format']['duration'])
    except Exception:
        # Fallback duration if probe fails
        duration = 10.0
    
    # We will sample 3 frames across the video
    timestamps = [duration * 0.2, duration * 0.5, duration * 0.8]
    hashes = []
    
    # Temporary frame image path
    temp_img = os.path.join(os.path.dirname(file_path), "temp_frame.jpg")
    
    for t in timestamps:
        try:
            # Extract exactly 1 frame at the given timestamp
            (
                ffmpeg
                .input(file_path, ss=t)
                .output(temp_img, vframes=1, loglevel="quiet")
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            # Calculate perceptual hash of the image
            img = Image.open(temp_img)
            h = str(imagehash.phash(img))
            hashes.append(h)
            img.close()
        except Exception as e:
            hashes.append("ERROR")
            
    if os.path.exists(temp_img):
        os.remove(temp_img)
        
    return "-".join(hashes)
