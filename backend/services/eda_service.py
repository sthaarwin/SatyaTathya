import os
import json
import re
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

def ensure_results_directory(claim_id: str) -> str:
    """Create results directory for a claim and return the path."""
    results_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data",
        "results",
        claim_id
    )
    os.makedirs(results_dir, exist_ok=True)
    return results_dir

# Keyword indicators for truth/falsity and claiming/contradicting
TRUTH_INDICATORS = {
    "confirmed", "verified", "proven", "authentic", "legitimate", "official",
    "authorized", "approved", "validated", "substantiated", "documented",
    "confirmed by", "verified by", "according to", "reported by", "announced",
    "true", "accurate", "correct", "valid", "genuine", "established",
    "published", "released", "issued", "declared", "implemented",
    "सत्य", "सच", "सही", "प्रमाणित", "सत्यापित", "आधिकारिक"  # Nepali equivalents
}

FALSEHOOD_INDICATORS = {
    "false", "fake", "hoax", "denied", "refuted", "debunked", "untrue",
    "misinformation", "disinformation", "fabricated", "misleading", "incorrect",
    "unverified", "unsubstantiated", "baseless", "untruthful", "fraudulent",
    "cancelled", "retracted", "withdrawn", "disputed", "contradicted",
    "झुटो", "गलत", "नक्कली", "भ्रामक", "असत्य"  # Nepali equivalents
}

CONTRADICTION_INDICATORS = {
    "denied", "contradicted", "refuted", "disagreed", "disputed", "objected",
    "rejected", "challenged", "opposed", "negated", "contrary to",
    "contradicts", "opposite", "conflicting", "counter",
    "विरोध", "खण्डन", "असहमत", "विरुद्ध"  # Nepali equivalents
}

CLAIMING_INDICATORS = {
    "claims", "stated", "said", "asserted", "alleged", "reportedly",
    "claimed", "argued", "suggests", "proposes", "maintains", "holds",
    "contends", "declares", "affirms", "announces", "according to",
    "दावी", "भन्छ", "भनिएको", "कहा जाता है", "मानिन्छ"  # Nepali equivalents
}

def extract_indicator_keywords(text: str, indicators: set) -> List[Tuple[str, int]]:
    """
    Extract indicator keywords from text.
    
    Args:
        text: Text to extract keywords from
        indicators: Set of indicator words/phrases to look for
    
    Returns:
        List of (keyword, count) tuples sorted by frequency
    """
    if not text:
        return []
    
    text_lower = text.lower()
    found_indicators = {}
    
    for indicator in indicators:
        # Use word boundaries for single words, flexible matching for phrases
        if " " in indicator:
            # Phrase matching
            count = len(re.findall(r'\b' + re.escape(indicator) + r'\b', text_lower, re.IGNORECASE))
        else:
            # Single word matching with word boundaries
            count = len(re.findall(r'\b' + re.escape(indicator) + r'\b', text_lower, re.IGNORECASE))
        
        if count > 0:
            found_indicators[indicator] = count
    
    # Sort by frequency (descending)
    return sorted(found_indicators.items(), key=lambda x: x[1], reverse=True)

def analyze_keyword_indicators(findings: list) -> Dict[str, Any]:
    """
    Analyze keywords in evidence to identify indicators of truth/falsity and stance.
    
    Args:
        findings: List of evidence findings
    
    Returns:
        Dictionary with keyword analysis results
    """
    
    if not findings:
        return {
            "total_indicators_found": 0,
            "truth_indicators": [],
            "falsehood_indicators": [],
            "contradiction_indicators": [],
            "claiming_indicators": [],
            "stance_based_keywords": {}
        }
    
    # Organize findings by stance
    support_findings = [f for f in findings if f.get("stance") == "SUPPORT"]
    contradict_findings = [f for f in findings if f.get("stance") == "CONTRADICT"]
    
    # Combine text from findings
    def combine_text(findings_list):
        texts = []
        for f in findings_list:
            texts.append(f.get("title", ""))
            texts.append(f.get("snippet", ""))
            texts.append(f.get("reasoning", ""))
            texts.append(f.get("evidence_quote", ""))
        return " ".join(filter(None, texts))
    
    support_text = combine_text(support_findings)
    contradict_text = combine_text(contradict_findings)
    all_text = combine_text(findings)
    
    # Extract indicators
    truth_ind = extract_indicator_keywords(all_text, TRUTH_INDICATORS)
    false_ind = extract_indicator_keywords(all_text, FALSEHOOD_INDICATORS)
    contradict_ind = extract_indicator_keywords(contradict_text, CONTRADICTION_INDICATORS)
    claiming_ind = extract_indicator_keywords(all_text, CLAIMING_INDICATORS)
    
    # Analyze by stance
    support_keywords = extract_indicator_keywords(support_text, TRUTH_INDICATORS | CLAIMING_INDICATORS)
    contradict_keywords = extract_indicator_keywords(contradict_text, CONTRADICTION_INDICATORS | FALSEHOOD_INDICATORS)
    
    total_indicators = len(truth_ind) + len(false_ind) + len(contradict_ind) + len(claiming_ind)
    
    analysis = {
        "total_indicators_found": total_indicators,
        "truth_indicators": [{"keyword": k, "count": c} for k, c in truth_ind],
        "falsehood_indicators": [{"keyword": k, "count": c} for k, c in false_ind],
        "contradiction_indicators": [{"keyword": k, "count": c} for k, c in contradict_ind],
        "claiming_indicators": [{"keyword": k, "count": c} for k, c in claiming_ind],
        "stance_based_keywords": {
            "support_keywords": [{"keyword": k, "count": c} for k, c in support_keywords],
            "contradict_keywords": [{"keyword": k, "count": c} for k, c in contradict_keywords]
        }
    }
    
    return analysis

def generate_eda_results(
    claim_id: str,
    analysis_data: dict,
    verification_data: dict,
    metadata: dict
) -> Dict[str, Any]:
    """
    Generate comprehensive EDA (Exploratory Data Analysis) results for a claim.
    
    Args:
        claim_id: Unique identifier for the claim
        analysis_data: Video analysis results (spoken, written, core claims)
        verification_data: Verification results (truth score, findings, etc.)
        metadata: Additional metadata (url, timestamp, etc.)
    
    Returns:
        Dictionary containing the generated EDA results
    """
    
    results_dir = ensure_results_directory(claim_id)
    
    # Extract key information
    core_claim = analysis_data.get("core_news_claim", "")
    spoken_claim = analysis_data.get("spoken_claim", "")
    written_claim = analysis_data.get("written_claim", "")
    
    # Extract verification details
    neutrosophic = verification_data.get("neutrosophic_score", {})
    findings = verification_data.get("evidence_findings", [])
    verdict = verification_data.get("verdict", "uncertain")
    truth_score = verification_data.get("truth_score", 0.0)
    confidence = verification_data.get("confidence", 0.0)
    
    # Generate EDA summary
    eda_summary = {
        "claim_id": claim_id,
        "timestamp": datetime.now().isoformat(),
        "url": metadata.get("url", ""),
        
        # Claim Information
        "claim_extraction": {
            "spoken_claim": spoken_claim,
            "written_claim": written_claim,
            "core_claim": core_claim,
            "claim_length": len(core_claim),
        },
        
        # Verification Results
        "verification_summary": {
            "verdict": verdict,
            "truth_score": round(truth_score, 3),
            "confidence": round(confidence, 3),
            "neutrosophic_scores": {
                "truth": round(neutrosophic.get("truth", 0.5), 3),
                "indeterminacy": round(neutrosophic.get("indeterminacy", 0.3), 3),
                "falsity": round(neutrosophic.get("falsity", 0.2), 3),
            }
        },
        
        # Evidence Analysis
        "evidence_analysis": generate_evidence_analysis(findings),
        
        # Keyword Analysis (indicators of truth/falsity and stance)
        "keyword_analysis": analyze_keyword_indicators(findings),
        
        # Statistics
        "statistics": generate_statistics(findings, truth_score, confidence),
        
        # Past Similar Claims
        "past_similar_claims": analysis_data.get("past_similar_claims", []),
    }
    
    return eda_summary, results_dir

def generate_evidence_analysis(findings: list) -> dict:
    """Analyze and summarize evidence findings."""
    
    if not findings:
        return {
            "total_evidence_items": 0,
            "supporting": [],
            "contradicting": [],
            "indeterminate": [],
            "summary": "No evidence found"
        }
    
    supporting = [f for f in findings if f.get("stance") == "SUPPORT"]
    contradicting = [f for f in findings if f.get("stance") == "CONTRADICT"]
    indeterminate = [f for f in findings if f.get("stance") == "INDETERMINATE"]
    
    analysis = {
        "total_evidence_items": len(findings),
        "count_by_stance": {
            "supporting": len(supporting),
            "contradicting": len(contradicting),
            "indeterminate": len(indeterminate),
        },
        "supporting": format_evidence_items(supporting),
        "contradicting": format_evidence_items(contradicting),
        "indeterminate": format_evidence_items(indeterminate),
        "top_domains": extract_top_domains(findings),
    }
    
    return analysis

def format_evidence_items(items: list) -> list:
    """Format evidence items for readability."""
    formatted = []
    for item in items:
        formatted.append({
            "domain": item.get("domain", ""),
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("snippet", "")[:200],
            "relevance": round(item.get("relevance", 0.0), 3),
            "confidence": round(item.get("confidence", 0.5), 3),
            "source_weight": round(item.get("source_weight", item.get("source_credibility", 0.4)), 3),
        })
    return formatted

def extract_top_domains(findings: list, limit: int = 10) -> list:
    """Extract the most frequently appearing domains in evidence."""
    domain_counts = {}
    for f in findings:
        domain = f.get("domain", "unknown")
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
    
    top_domains = sorted(
        domain_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )[:limit]
    
    return [{"domain": d, "count": c} for d, c in top_domains]

def generate_statistics(findings: list, truth_score: float, confidence: float) -> dict:
    """Generate statistical summary of the analysis."""
    
    relevance_scores = [f.get("relevance", 0.0) for f in findings if f]
    confidence_scores = [f.get("confidence", 0.5) for f in findings if f]
    similarity_scores = [f.get("similarity", 0.5) for f in findings if f]
    
    return {
        "overall_truth_score": round(truth_score, 3),
        "overall_confidence": round(confidence, 3),
        "relevance_distribution": {
            "mean": round(sum(relevance_scores) / len(relevance_scores), 3) if relevance_scores else 0,
            "min": round(min(relevance_scores), 3) if relevance_scores else 0,
            "max": round(max(relevance_scores), 3) if relevance_scores else 0,
        },
        "confidence_distribution": {
            "mean": round(sum(confidence_scores) / len(confidence_scores), 3) if confidence_scores else 0,
            "min": round(min(confidence_scores), 3) if confidence_scores else 0,
            "max": round(max(confidence_scores), 3) if confidence_scores else 0,
        },
        "similarity_distribution": {
            "mean": round(sum(similarity_scores) / len(similarity_scores), 3) if similarity_scores else 0,
            "min": round(min(similarity_scores), 3) if similarity_scores else 0,
            "max": round(max(similarity_scores), 3) if similarity_scores else 0,
        }
    }

def save_eda_results(
    claim_id: str,
    eda_summary: dict,
    results_dir: str,
    full_analysis: Optional[dict] = None,
    full_verification: Optional[dict] = None
) -> dict:
    """
    Save EDA results to files.
    
    Args:
        claim_id: Unique identifier for the claim
        eda_summary: Summary of EDA results
        results_dir: Directory to save results to
        full_analysis: Full analysis data (optional)
        full_verification: Full verification data (optional)
    
    Returns:
        Dictionary with file paths of saved results
    """
    
    saved_files = {}
    
    try:
        # Save EDA summary
        summary_path = os.path.join(results_dir, "eda_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(eda_summary, f, ensure_ascii=False, indent=2)
        saved_files["eda_summary"] = summary_path
        
        # Save full analysis data
        if full_analysis:
            analysis_path = os.path.join(results_dir, "analysis_full.json")
            with open(analysis_path, "w", encoding="utf-8") as f:
                json.dump(full_analysis, f, ensure_ascii=False, indent=2)
            saved_files["analysis_full"] = analysis_path
        
        # Save full verification data
        if full_verification:
            verification_path = os.path.join(results_dir, "verification_full.json")
            with open(verification_path, "w", encoding="utf-8") as f:
                json.dump(full_verification, f, ensure_ascii=False, indent=2)
            saved_files["verification_full"] = verification_path
        
        # Save metadata
        metadata_path = os.path.join(results_dir, "metadata.json")
        metadata = {
            "claim_id": claim_id,
            "created_at": datetime.now().isoformat(),
            "files": saved_files,
        }
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        saved_files["metadata"] = metadata_path
        
        return {
            "status": "success",
            "claim_id": claim_id,
            "results_directory": results_dir,
            "saved_files": saved_files
        }
    
    except Exception as e:
        return {
            "status": "error",
            "claim_id": claim_id,
            "error": str(e)
        }

def load_existing_eda_results(claim_id: str) -> Optional[dict]:
    """Load previously saved EDA results from disk if they exist."""
    results_dir = ensure_results_directory(claim_id)
    summary_path = os.path.join(results_dir, "eda_summary.json")
    if not os.path.exists(summary_path):
        return None
    try:
        return {
            "status": "success",
            "claim_id": claim_id,
            "results_directory": results_dir,
            "saved_files": {
                "eda_summary": summary_path,
            }
        }
    except Exception:
        return None

def create_and_save_eda_results(
    claim_id: str,
    analysis_data: dict,
    verification_data: dict,
    metadata: dict,
    save_full_data: bool = True
) -> dict:
    """
    Wrapper function to generate and save EDA results in one call.
    
    Args:
        claim_id: Unique identifier for the claim
        analysis_data: Video analysis results
        verification_data: Verification results
        metadata: Additional metadata
        save_full_data: Whether to save full analysis and verification data
    
    Returns:
        Dictionary with save status and paths
    """
    
    eda_summary, results_dir = generate_eda_results(
        claim_id,
        analysis_data,
        verification_data,
        metadata
    )
    
    save_result = save_eda_results(
        claim_id,
        eda_summary,
        results_dir,
        full_analysis=analysis_data if save_full_data else None,
        full_verification=verification_data if save_full_data else None
    )
    
    return save_result
