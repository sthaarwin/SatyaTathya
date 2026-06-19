from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime

from validators.content_validator import ContentValidator


class Verdict(str, Enum):
    TRUE = "true"
    FALSE = "false"
    UNCERTAIN = "uncertain"


class AnalyzeRequest(BaseModel):
    url: str = Field(..., description="Video URL to analyze")

    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        """Validate URL format and domain"""
        is_valid, _ = ContentValidator.validate_url(v)
        if not is_valid:
            raise ValueError(f'Invalid or unsupported URL: {v}')
        return v


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500, description="Search query")

    @field_validator('query')
    @classmethod
    def validate_query(cls, v):
        """Sanitize and validate search query"""
        if not v or len(v.strip()) < 2:
            raise ValueError('Query must be at least 2 characters')
        return v.strip()


class ClaimQuality(BaseModel):
    is_extractable: bool
    confidence: float = Field(ge=0.0, le=1.0)
    language_detected: str
    length: int
    quality_score: float = Field(ge=0.0, le=1.0)


class NeutrosophicScore(BaseModel):
    truth: float = Field(ge=0.0, le=1.0, description="Truth degree (T)")
    indeterminacy: float = Field(ge=0.0, le=1.0, description="Indeterminacy degree (I)")
    falsity: float = Field(ge=0.0, le=1.0, description="Falsity degree (F)")


class EvidenceFinding(BaseModel):
    domain: str
    title: str
    snippet: str
    stance: str  # SUPPORT, CONTRADICT, INDETERMINATE
    relevance: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    source_credibility: float = Field(ge=0.0, le=1.0)
    evidence_weight: float = Field(ge=0.0, le=1.0)


class VerificationResult(BaseModel):
    claim: str
    verdict: str  # SUPPORT, CONTRADICT, INDETERMINATE
    truth_score: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_count: int
    evidence_findings: List[EvidenceFinding] = []
    neutrosophic_score: NeutrosophicScore
    reasoning: str
    used_llm: bool = False


class AnalysisData(BaseModel):
    spoken_claim: str
    written_claim: str
    core_news_claim: str
    verification: Optional[VerificationResult] = None


class AnalysisResponse(BaseModel):
    status: str
    match_type: str  # url_cache, visual_hash_cache, ai_analysis
    data: AnalysisData
    claim_quality: Optional[ClaimQuality] = None
    eda_results: Optional[Dict[str, Any]] = None
    timestamp: float
    processing_time_ms: Optional[float] = None


class SearchResponse(BaseModel):
    status: str
    query: str
    results: List[Dict[str, Any]]
    count: int
    timestamp: float


class StatsResponse(BaseModel):
    total_analyses: int
    chroma_vectors: int
    verdicts: Dict[str, int]  # true, false, uncertain counts
    timestamp: float


class ComparisonMetric(BaseModel):
    model: str
    accuracy: float
    precision: float
    recall: float
    f1_score: float


class ComparisonResponse(BaseModel):
    dataset: str
    split: str
    test_size: int
    metrics: List[ComparisonMetric]
    timestamp: float


class ErrorResponse(BaseModel):
    status: str = "error"
    detail: str
    error_code: str
    timestamp: float


class APIResponse(BaseModel):
    """Generic API response wrapper"""
    status: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())
