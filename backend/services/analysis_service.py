import os
import json
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

def analyze_video_with_gemini(file_path: str):
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        raise ValueError("Please set a valid GEMINI_API_KEY in the .env file")
        
    client = genai.Client(api_key=GEMINI_API_KEY)

    print(f"[*] Uploading file to Gemini API: {file_path}")
    video_file = client.files.upload(file=file_path)

    print("[*] Waiting for video processing...", end="", flush=True)
    while video_file.state.name == "PROCESSING":
        print(".", end="", flush=True)
        time.sleep(3)
        video_file = client.files.get(name=video_file.name)
    
    if video_file.state.name == "FAILED":
        raise Exception("Video processing in Gemini API failed.")
    print("\n[+] Video processed successfully.")

    prompt = """
    Please analyze this video critically. Perform Video-OCR to read any banners, overlays, or text shown in the video. 
    Perform Speech-to-Text to transcribe and understand the spoken language (including Nepali). 
    
    Provide the output strictly as a JSON object matching this schema:
    {
      "spoken_claim": "What is the main claim being spoken in the audio?",
      "written_claim": "What is the main claim written as text on the screen?",
      "core_news_claim": "A unified, synthesized factual claim combining both spoken and written elements."
    }
    """
    
    print("[*] Prompting Gemini 2.5 Flash for Multimodal Analysis...")
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[video_file, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    
    try:
        return json.loads(response.text)
    except json.JSONDecodeError:
        return {"error": "Invalid response format", "raw_response": response.text}
