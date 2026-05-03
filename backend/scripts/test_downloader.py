import argparse
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.video_service import download_video
from services.fingerprint_service import generate_video_fingerprint
from services.db_service import get_cached_analysis_by_url, get_cached_analysis_by_hash

def main():
    parser = argparse.ArgumentParser(description="Test video downloader functionality")
    parser.add_argument("url", help="URL of the video to download (e.g., TikTok)")
    args = parser.parse_args()

    print(f"[*] Attempting to download video from: {args.url}")
    
    # Check cache first
    cached = get_cached_analysis_by_url(args.url)
    if cached:
        print("[!] Video URL is already cached! Bypassing download.")
        print(f"    - Spoken Claim: {cached.get('spoken_claim', '')[:50]}...")
        return
        
    try:
        result = download_video(args.url)
        print("\n[+] Success! Video downloaded.")
        print(f"    - ID: {result['video_id']}")
        print(f"    - Title: {result['title']}")
        print(f"    - Saved path: {result['file_path']}")
        
    # Test fingerprinting as well
        print("\n[*] Generating visual fingerprint...")
        vid_hash = generate_video_fingerprint(result['file_path'])
        print(f"    - Hash: {vid_hash}")
        
        hash_cached = get_cached_analysis_by_hash(vid_hash)
        if hash_cached:
            print(f"[!] This precise video footage (Hash: {vid_hash}) has been processed before!")
            print(f"    - Spoken Claim: {hash_cached.get('spoken_claim', '')[:50]}...")
            
            # Since it's already in the system, we can safely delete the newly downloaded file
            print("    - Deleting duplicate video file...")
            import os
            if os.path.exists(result['file_path']):
                os.remove(result['file_path'])
        else:
            print("[*] Video footage is completely new to the system.")
             
    except Exception as e:
        print(f"\n[-] Error processing video: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
