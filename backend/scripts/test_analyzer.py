import argparse
import sys
import os
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.analysis_service import analyze_video_with_gemini

def main():
    parser = argparse.ArgumentParser(description="Test Gemini Multimodal Analysis")
    parser.add_argument("file_path", help="Path to the MP4 file to analyze")
    args = parser.parse_args()

    if not os.path.exists(args.file_path):
        print(f"[-] File not found: {args.file_path}")
        return

    try:
        result = analyze_video_with_gemini(args.file_path)
        print("\n[+] Multimodal Analysis Results:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"\n[-] Error analyzing video: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
