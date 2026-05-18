import os
import json
import time
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

class ClaimExtractionSchema(BaseModel):
    spoken_claim: str = Field(description="What is the main claim being spoken in the audio?")
    written_claim: str = Field(description="What is the main claim written as text on the screen/banners?")
    core_news_claim: str = Field(description="A unified, synthesized factual news claim combining both spoken and written elements.")

def analyze_video_with_gemini(file_path: str) -> dict:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        raise ValueError("Please set a valid GEMINI_API_KEY in the .env file")
        
    client = genai.Client(api_key=GEMINI_API_KEY)

    if not os.path.exists(file_path):
        return {"error": f"Local file not found: {file_path}"}

    try:
        print(f"[*] Uploading file to Gemini API: {file_path}")
        video_file = client.files.upload(file=file_path)

        print("[*] Waiting for video processing...", end="", flush=True)
        while video_file.state.name == "PROCESSING":
            print(".", end="", flush=True)
            time.sleep(5) 
            video_file = client.files.get(name=video_file.name)
        
        if video_file.state.name == "FAILED":
            return {"error": "Video processing failed within the Gemini API infrastructure."}
        print("\n[+] Video processed successfully.")

        prompt = """
        Analyze this video critically. Perform Video-OCR to read any banners, overlays, or breaking news text shown in the video. 
        Perform Speech-to-Text to transcribe and understand the spoken language (handling native Nepali, English, and Romanized code-switching).
        Extract and synthesize the core news claim. If the transcript or OCR contains minor transcription inaccuracies due to audio quality, 
        use the overall context to infer and correct the proper names of locations or figures in Nepal.
        """
        
        print("[*] Prompting Gemini 2.5 Flash for Structured Multimodal Analysis...")
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[video_file, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ClaimExtractionSchema,
                temperature=0.2 # Lower temperature = more focused factual extraction
            )
        )

        try:
            client.files.delete(name=video_file.name)
            print("[*] Temporary cloud file cleaned up successfully.")
        except Exception as e:
            print(f"[!] Warning: Failed to delete temporary file: {e}")

        return json.loads(response.text)
        
    except Exception as general_error:
        print(f"\n[!] Critical Pipeline Error: {general_error}")
        return {"error": str(general_error)}