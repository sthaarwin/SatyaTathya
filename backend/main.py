from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from services.video_service import download_video
from services.analysis_service import analyze_video_with_gemini
from services.fingerprint_service import generate_video_fingerprint
from services.db_service import init_db, get_cached_analysis_by_url, get_cached_analysis_by_hash, save_analysis, get_cached_verification, save_verification
from services.chroma_service import add_claim_to_db
from services.verification_service import verify_claim

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
        core_claim = cached_result.get("core_news_claim", "")
        if core_claim:
            cached_verification = get_cached_verification(core_claim)
            if cached_verification:
                cached_result["verification"] = cached_verification
            else:
                verification = verify_claim(core_claim, url)
                save_verification(core_claim, verification)
                cached_result["verification"] = verification
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
            if os.path.exists(file_path):
                os.remove(file_path)
            save_analysis(url, vid_hash, visual_cached_result)
            core_claim = visual_cached_result.get("core_news_claim", "")
            if core_claim:
                cached_verification = get_cached_verification(core_claim)
                if cached_verification:
                    visual_cached_result["verification"] = cached_verification
                else:
                    verification = verify_claim(core_claim, url)
                    save_verification(core_claim, verification)
                    visual_cached_result["verification"] = verification
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
    
    # 5. Clean up video
    if os.path.exists(file_path):
        os.remove(file_path)
        
    if "error" not in analysis_result:
        save_analysis(url, vid_hash, analysis_result)
        
        # Store in ChromaDB for semantic search
        core_claim = analysis_result.get("core_news_claim", "")
        if core_claim:
            claim_id = f"claim_{vid_hash[:16]}"
            metadata = {
                "url": url,
                "spoken_claim": analysis_result.get("spoken_claim", ""),
                "written_claim": analysis_result.get("written_claim", ""),
                "truth_score": 0.5
            }
            add_claim_to_db(claim_id, core_claim, metadata)
            
            # Run full verification pipeline (evidence search + neutrosophic scoring)
            verification = verify_claim(core_claim, url)
            save_verification(core_claim, verification)
            analysis_result["verification"] = verification
            
            # Update metadata with final scores
            metadata["truth_score"] = verification.get("neutrosophic", {}).get("T", 0.5)
        
    return {"status": "success", "match_type": "ai_analysis", "data": analysis_result}
