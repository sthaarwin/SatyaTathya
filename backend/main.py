from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from contextlib import asynccontextmanager

from services.video_service import download_video
from services.analysis_service import analyze_video_with_gemini
from services.db_service import init_db, get_cached_analysis, save_analysis

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="SatyaTathya API", 
    description="Backend for Multimodal Fact-Checking",
    lifespan=lifespan
)

class AnalyzeRequest(BaseModel):
    url: str

@app.get("/")
def read_root():
    return {"message": "Welcome to SatyaTathya API"}

@app.post("/api/analyze")
def analyze_url(request: AnalyzeRequest):
    url = request.url
    
    # 1. Check SQLite Cache
    cached_result = get_cached_analysis(url)
    if cached_result:
        return {"status": "success", "cached": True, "data": cached_result}
    
    # 2. Not cached: Download video
    try:
        video_info = download_video(url)
        file_path = video_info["file_path"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download video: {str(e)}")
        
    # 3. Analyze video
    try:
        analysis_result = analyze_video_with_gemini(file_path)
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Failed to analyze video: {str(e)}")
        
    # 4. Clean up video to save disk space
    if os.path.exists(file_path):
        os.remove(file_path)
        
    # 5. Save to SQLite cache and return
    if "error" not in analysis_result:
        save_analysis(url, analysis_result)
        
    return {"status": "success", "cached": False, "data": analysis_result}
