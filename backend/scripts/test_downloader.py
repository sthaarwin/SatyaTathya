import argparse
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.video_service import download_video

def main():
    parser = argparse.ArgumentParser(description="Test video downloader functionality")
    parser.add_argument("url", help="URL of the video to download (e.g., TikTok)")
    args = parser.parse_args()

    print(f"[*] Attempting to download video from: {args.url}")
    try:
        result = download_video(args.url)
        print("\n[+] Success! Video downloaded.")
        print(f"    - ID: {result['video_id']}")
        print(f"    - Title: {result['title']}")
        print(f"    - Saved path: {result['file_path']}")
    except Exception as e:
        print(f"\n[-] Error downloading video: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
