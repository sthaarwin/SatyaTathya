from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import os
import json
import time
import logging
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import hashlib
from dotenv import load_dotenv

from services.video_service import download_video
from services.analysis_service import analyze_video_with_gemini
from services.fingerprint_service import generate_video_fingerprint
from services.db_service import init_db, get_cached_analysis_by_url, get_cached_analysis_by_hash, save_analysis, get_cached_verification, save_verification, get_all_cached_analyses, clear_cache
from services.chroma_service import add_claim_to_db, search_similar_claims, collection, clear_chroma
from services.verification_service import verify_claim
from services.eda_service import create_and_save_eda_results, load_existing_eda_results
from models.schemas import (
    AnalyzeRequest, SearchRequest, AnalysisResponse, SearchResponse, StatsResponse, 
    ComparisonResponse, ErrorResponse, APIResponse, AnalysisData, ClaimQuality, NeutrosophicScore
)
from validators.content_validator import ContentValidator
from models.ensemble_model import get_ensemble_verifier

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rate limits from env vars (with defaults)
RATE_LIMIT_ANALYZE = os.getenv("RATE_LIMIT_ANALYZE", "5/minute")
RATE_LIMIT_SEARCH = os.getenv("RATE_LIMIT_SEARCH", "10/minute")
RATE_LIMIT_STATS = os.getenv("RATE_LIMIT_STATS", "20/minute")
RATE_LIMIT_CACHE_CLEAR = os.getenv("RATE_LIMIT_CACHE_CLEAR", "2/minute")
RATE_LIMIT_HEALTH = os.getenv("RATE_LIMIT_HEALTH", "30/minute")

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Initialize ensemble verifier
ensemble_verifier = get_ensemble_verifier()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Ensemble Model Status:", ensemble_verifier.get_model_info())
    yield

app = FastAPI(
    title="SatyaTathya API", 
    description="Backend for Multimodal Fact-Checking",
    lifespan=lifespan
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda request, exc: JSONResponse(
    status_code=429,
    content={
        "status": "error",
        "detail": "Too many requests. Please try again later.",
        "error_code": "RATE_LIMIT_EXCEEDED"
    }
))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to SatyaTathya API"}


@app.post("/api/analyze", response_model=AnalysisResponse)
@limiter.limit(RATE_LIMIT_ANALYZE)
def analyze_url(request: Request, analyze_request: AnalyzeRequest):
    """Analyze a video URL for misinformation"""
    start_time = time.time()
    url = analyze_request.url
    
    try:
        _, domain = ContentValidator.validate_url(url)
        logger.info(f"Processing URL: {url} (domain: {domain})")
        
        # 1. Check basic URL cache first (Fastest string match)
        cached_result = get_cached_analysis_by_url(url)
        if cached_result:
            logger.info(f"URL cache hit: {url}")
            core_claim = cached_result.get("core_news_claim", "")
            claim_quality = None
            eda_results = None
            if core_claim:
                cached_verification = get_cached_verification(core_claim)
                if cached_verification:
                    cached_result["verification"] = cached_verification
                else:
                    verification = verify_claim(core_claim, url)
                    save_verification(core_claim, verification)
                    cached_result["verification"] = verification
                
                is_extractable, quality_conf = ContentValidator.validate_claim_extractability(core_claim)
                language = ContentValidator.detect_language(core_claim)
                quality_score = ContentValidator.calculate_claim_quality_score(
                    core_claim, is_extractable, language, quality_conf
                )
                claim_quality = ClaimQuality(
                    is_extractable=is_extractable,
                    confidence=quality_conf,
                    language_detected=language,
                    length=len(core_claim),
                    quality_score=quality_score
                )

                claim_id = f"claim_{hashlib.md5(url.encode()).hexdigest()[:16]}"
                existing_eda = load_existing_eda_results(claim_id)
                if existing_eda:
                    eda_results = existing_eda
                else:
                    metadata = {
                        "url": url,
                        "spoken_claim": cached_result.get("spoken_claim", ""),
                        "written_claim": cached_result.get("written_claim", ""),
                        "truth_score": 0.5
                    }
                    try:
                        eda_result = create_and_save_eda_results(
                            claim_id=claim_id,
                            analysis_data=cached_result,
                            verification_data=cached_result.get("verification", {}),
                            metadata=metadata,
                            save_full_data=True
                        )
                        if eda_result.get("status") == "success":
                            logger.info(f"EDA results saved to {eda_result.get('results_directory')}")
                            eda_results = eda_result
                    except Exception as e:
                        logger.error(f"Error generating EDA results: {str(e)}")
            
            processing_time = (time.time() - start_time) * 1000
            return AnalysisResponse(
                status="success",
                match_type="url_cache",
                data=AnalysisData(**cached_result),
                claim_quality=claim_quality,
                eda_results=eda_results,
                timestamp=time.time(),
                processing_time_ms=processing_time
            )
        
        # 2. Not cached: Download video
        try:
            logger.info(f"Downloading video from {url}")
            video_info = download_video(url)
            file_path = video_info["file_path"]
        except Exception as e:
            logger.error(f"Download failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to download video: {str(e)}")
            
        # 3. Generate Visual Fingerprint (PHash) and check DB
        try:
            vid_hash = generate_video_fingerprint(file_path)
            visual_cached_result = get_cached_analysis_by_hash(vid_hash)
            
            # If we have seen this EXACT video footage before under a different URL
            if visual_cached_result:
                logger.info(f"Visual hash cache hit: {vid_hash}")
                if os.path.exists(file_path):
                    os.remove(file_path)
                save_analysis(url, vid_hash, visual_cached_result)
                core_claim = visual_cached_result.get("core_news_claim", "")
                claim_quality = None
                eda_results = None
                if core_claim:
                    cached_verification = get_cached_verification(core_claim)
                    if cached_verification:
                        visual_cached_result["verification"] = cached_verification
                    else:
                        verification = verify_claim(core_claim, url)
                        save_verification(core_claim, verification)
                        visual_cached_result["verification"] = verification

                    is_extractable, quality_conf = ContentValidator.validate_claim_extractability(core_claim)
                    language = ContentValidator.detect_language(core_claim)
                    quality_score = ContentValidator.calculate_claim_quality_score(
                        core_claim, is_extractable, language, quality_conf
                    )
                    claim_quality = ClaimQuality(
                        is_extractable=is_extractable,
                        confidence=quality_conf,
                        language_detected=language,
                        length=len(core_claim),
                        quality_score=quality_score
                    )

                    claim_id = f"claim_{vid_hash[:16]}"
                    existing_eda = load_existing_eda_results(claim_id)
                    if existing_eda:
                        eda_results = existing_eda
                    else:
                        metadata = {
                            "url": url,
                            "spoken_claim": visual_cached_result.get("spoken_claim", ""),
                            "written_claim": visual_cached_result.get("written_claim", ""),
                            "truth_score": 0.5
                        }
                        try:
                            eda_result = create_and_save_eda_results(
                                claim_id=claim_id,
                                analysis_data=visual_cached_result,
                                verification_data=visual_cached_result.get("verification", {}),
                                metadata=metadata,
                                save_full_data=True
                            )
                            if eda_result.get("status") == "success":
                                logger.info(f"EDA results saved to {eda_result.get('results_directory')}")
                                eda_results = eda_result
                        except Exception as e:
                            logger.error(f"Error generating EDA results: {str(e)}")
                
                processing_time = (time.time() - start_time) * 1000
                return AnalysisResponse(
                    status="success",
                    match_type="visual_hash_cache",
                    data=AnalysisData(**visual_cached_result),
                    claim_quality=claim_quality,
                    eda_results=eda_results,
                    timestamp=time.time(),
                    processing_time_ms=processing_time
                )
                
        except Exception as e:
            if os.path.exists(file_path):
                os.remove(file_path)
            logger.error(f"Fingerprinting failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed during fingerprinting: {str(e)}")

        # 4. Completely unseen video: Run full Gemini AI Analysis
        try:
            logger.info(f"Running Gemini analysis on video")
            analysis_result = analyze_video_with_gemini(file_path)
        except Exception as e:
            if os.path.exists(file_path):
                os.remove(file_path)
            logger.error(f"Analysis failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to analyze video: {str(e)}")
        
        # 5. Clean up video
        if os.path.exists(file_path):
            os.remove(file_path)
            
        if "error" not in analysis_result:
            save_analysis(url, vid_hash, analysis_result)
            
            # Validate and enhance claim quality
            core_claim = analysis_result.get("core_news_claim", "")
            if core_claim:
                # Fix transcription errors
                core_claim = ContentValidator.fix_transcription_errors(core_claim)
                analysis_result["core_news_claim"] = core_claim
                
                # Assess claim quality
                is_extractable, quality_conf = ContentValidator.validate_claim_extractability(core_claim)
                language = ContentValidator.detect_language(core_claim)
                quality_score = ContentValidator.calculate_claim_quality_score(
                    core_claim, is_extractable, language, quality_conf
                )
                claim_quality = ClaimQuality(
                    is_extractable=is_extractable,
                    confidence=quality_conf,
                    language_detected=language,
                    length=len(core_claim),
                    quality_score=quality_score
                )
                
                claim_id = f"claim_{vid_hash[:16]}"
                metadata = {
                    "url": url,
                    "spoken_claim": analysis_result.get("spoken_claim", ""),
                    "written_claim": analysis_result.get("written_claim", ""),
                    "truth_score": 0.5
                }
                add_claim_to_db(claim_id, core_claim, metadata)
                
                # Run full verification pipeline
                verification = verify_claim(core_claim, url)
                save_verification(core_claim, verification)
                analysis_result["verification"] = verification
                
                # Update metadata with final scores
                metadata["truth_score"] = verification.get("neutrosophic_score", {}).get("truth", 0.5)
                
                # Generate and save EDA results
                eda_results = None
                try:
                    eda_result = create_and_save_eda_results(
                        claim_id=claim_id,
                        analysis_data=analysis_result,
                        verification_data=verification,
                        metadata=metadata,
                        save_full_data=True
                    )
                    if eda_result.get("status") == "success":
                        logger.info(f"EDA results saved to {eda_result.get('results_directory')}")
                        eda_results = eda_result
                    else:
                        logger.warning(f"Failed to save EDA results: {eda_result.get('error')}")
                except Exception as e:
                    logger.error(f"Error generating EDA results: {str(e)}")
            
            processing_time = (time.time() - start_time) * 1000
            return AnalysisResponse(
                status="success",
                match_type="ai_analysis",
                data=AnalysisData(**analysis_result),
                claim_quality=claim_quality if core_claim else None,
                eda_results=eda_results,
                timestamp=time.time(),
                processing_time_ms=processing_time
            )
        else:
            raise HTTPException(status_code=500, detail=analysis_result.get("error", "Unknown analysis error"))
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/api/search", response_model=SearchResponse)
@limiter.limit(RATE_LIMIT_SEARCH)
def search_claims(request: Request, search_request: SearchRequest):
    """Search for similar claims in the database"""
    query = search_request.query
    
    try:
        # Sanitize query
        sanitized_query = ContentValidator.sanitize_query(query)
        if not sanitized_query:
            raise HTTPException(status_code=400, detail="Query must contain valid characters")
        
        logger.info(f"Searching for claims: {sanitized_query}")
        results = search_similar_claims(sanitized_query, threshold=2.0)
        
        return SearchResponse(
            status="success",
            query=sanitized_query,
            results=results,
            count=len(results),
            timestamp=time.time()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/api/stats", response_model=StatsResponse)
@limiter.limit(RATE_LIMIT_STATS)
def get_stats(request: Request):
    """Get statistics about cached analyses"""
    try:
        cached_analyses = get_all_cached_analyses()
        chroma_count = collection.count()
        
        true_count = sum(1 for c in cached_analyses if c.get("truth_score", 0) > 0.6)
        false_count = sum(1 for c in cached_analyses if c.get("truth_score", 0) < 0.4)
        uncertain_count = len(cached_analyses) - true_count - false_count
        
        return StatsResponse(
            total_analyses=len(cached_analyses),
            chroma_vectors=chroma_count,
            verdicts={
                "true": true_count,
                "false": false_count,
                "uncertain": uncertain_count
            },
            timestamp=time.time()
        )
    except Exception as e:
        logger.error(f"Stats error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

@app.get("/api/comparison", response_model=ComparisonResponse)
@limiter.limit("10/minute")
def get_method_comparison(request: Request):
    """Get method comparison results"""
    try:
        comparison_path = os.path.join(MODELS_DIR, "method_comparison_results.json")
        classical_path = os.path.join(MODELS_DIR, "climate_fever_classical_results.json")

        for path in [comparison_path, classical_path]:
            if os.path.exists(path):
                with open(path, "r") as file:
                    data = json.load(file)
                if isinstance(data, list):
                    return ComparisonResponse(
                        dataset="rexarski/climate_fever_fixed",
                        split="train",
                        test_size=data[0].get("test_size", 0) if data else 0,
                        metrics=data,
                        timestamp=time.time()
                    )
                return ComparisonResponse(
                    dataset="rexarski/climate_fever_fixed",
                    split="train",
                    test_size=0,
                    metrics=data if isinstance(data, list) else [data],
                    timestamp=time.time()
                )

        return ComparisonResponse(
            dataset="rexarski/climate_fever_fixed",
            split="train",
            test_size=0,
            metrics=[],
            timestamp=time.time()
        )
    except Exception as e:
        logger.error(f"Comparison error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get comparison: {str(e)}")

@app.post("/api/cache/clear")
@limiter.limit(RATE_LIMIT_CACHE_CLEAR)
def clear_cache_endpoint(request: Request):
    """Clear cache and ChromaDB"""
    try:
        logger.info("Clearing cache...")
        db_cleared = clear_cache()
        chroma_cleared = clear_chroma()
        return {
            "status": "success",
            "message": f"Cleared {db_cleared} cache entries and {chroma_cleared} ChromaDB vectors",
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Cache clear error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


@app.get("/api/sources")
def get_sources(request: Request):
    """Return trusted sources with credibility weights"""
    import json as j
    with open(os.path.join(os.path.dirname(__file__), "data", "trusted_sources.json")) as f:
        sources = j.load(f)
    return {
        "sources": [{"domain": d, "weight": w} for d, w in sorted(sources.items(), key=lambda x: -x[1])],
        "timestamp": time.time()
    }

@app.get("/api/health")
@limiter.limit(RATE_LIMIT_HEALTH)
def health_check(request: Request):
    """Health check endpoint"""
    return {
        "status": "healthy",
        "ensemble_available": ensemble_verifier.is_available(),
        "ensemble_models": ensemble_verifier.get_model_info(),
        "timestamp": time.time()
    }
