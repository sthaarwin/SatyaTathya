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
    keys = [k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()]
    if not keys:
        raise ValueError("Please set a valid GEMINI_API_KEY in the .env file")

    if not os.path.exists(file_path):
        return {"error": f"Local file not found: {file_path}"}

    max_retries = 5
    last_error = None

    for attempt in range(max_retries):
        key_index = attempt % len(keys)
        api_key = keys[key_index]
        client = genai.Client(api_key=api_key)

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
                    temperature=0.2
                )
            )

            try:
                client.files.delete(name=video_file.name)
                print("[*] Temporary cloud file cleaned up successfully.")
            except Exception as e:
                print(f"[!] Warning: Failed to delete temporary file: {e}")

            return json.loads(response.text)

        except Exception as e:
            last_error = e
            err_str = str(e)
            is_retryable = "503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str or "RESOURCE_EXHAUSTED" in err_str

            if "RATE_LIMIT" in err_str.upper():
                limit_type = "per-minute rate limit"
            elif "exceeded your current quota" in err_str.lower():
                limit_type = "daily free-tier quota"
            elif "daily" in err_str.lower() or "day" in err_str.lower():
                limit_type = "daily quota"
            elif "per month" in err_str.lower() or "monthly" in err_str.lower():
                limit_type = "monthly quota"
            elif "token" in err_str.lower():
                limit_type = "token limit"
            elif "503" in err_str or "UNAVAILABLE" in err_str:
                limit_type = "model overloaded"
            else:
                limit_type = "quota"

            if is_retryable and attempt < max_retries - 1:
                wait = min(2 ** attempt * 5, 60)
                print(f"\n[!] {limit_type} (key {key_index + 1}) — retrying in {wait}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait)
                continue

            print(f"\n[!] Critical Pipeline Error: {last_error}")
            return {"error": str(last_error)}