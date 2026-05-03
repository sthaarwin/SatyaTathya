from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from services.video_service import download_video
from services.analysis_service import analyze_video_with_gemini
from services.fingerprint_service import generate_video_fingerprint
from services.db_service import init_db, get_cached_analysis_by_url, get_cached_analysis_by_hash, save_analysis

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="SatyaTathya API", 
    description="Backend for Multimodal Fact-Checking",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    url: str

@app.get("/")
def read_root():
    return {"message": "Welcome to SatyaTathya API"}

@app.post("/api/analyze")
def analyze_url(request: AnalyzeRequest):
    url = request.url
    
    # 1. Check basic URL cache first (Fastest string match)
    cached_result = get_cached_analysis_by_url(url)
    if cached_result:
        return {"status": "success", "match_type": "url_cache", "data": cached_result}
    
    # 2. Not cached: Download video
    try:
        video_info = download_video(url)
        file_path = video_info["file_path"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download video: {str(e)}")
        
    # 3. Generate Visual Fingerprint (PHash) and check DB
    try:
        vid_hash = generate_video_fingerprint(file_path)
        visual_cached_result = get_cached_analysis_by_hash(vid_hash)
        
        # If we have seen this EXACT video footage before under a different URL
        if visual_cached_result:
            # Clean up the duplicate video immediately
            if os.path.exists(file_path):
                os.remove(file_path)
            # Save the new URL mapping to the old hash so we skip downloading next time
            save_analysis(url, vid_hash, visual_cached_result)
            return {"status": "success", "match_type": "visual_hash_cache", "data": visual_cached_result}
            
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Failed during fingerprinting: {str(e)}")

    # 4. Completely unseen video: Run full Gemini AI Analysis
    try:
        analysis_result = analyze_video_with_gemini(file_path)
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Failed to analyze video: {str(e)}")
        
    # 5. Clean up video and Save to Cache
    if os.path.exists(file_path):
        os.remove(file_path)
        
    if "error" not in analysis_result:
        save_analysis(url, vid_hash, analysis_result)
        
    return {"status": "success", "match_type": "ai_analysis", "data": analysis_result}
