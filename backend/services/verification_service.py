import os
import json
import re
from urllib.parse import urlparse
from ddgs import DDGS
from bs4 import BeautifulSoup
import requests
from firecrawl import FirecrawlApp
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from services.chroma_service import search_similar_claims, compute_similarity

load_dotenv()
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
USE_LLM_STANCE = os.getenv("USE_LLM_STANCE", "true").lower() == "true"
USE_LLM_QUERY_OPTIMIZER = os.getenv("USE_LLM_QUERY_OPTIMIZER", "false").lower() == "true"
MAX_LLM_EVIDENCE_ITEMS = int(os.getenv("MAX_LLM_EVIDENCE_ITEMS", "2"))
MIN_RELEVANCE_FOR_LLM = float(os.getenv("MIN_RELEVANCE_FOR_LLM", "0.32"))
MIN_RELEVANCE_FOR_SCORING = float(os.getenv("MIN_RELEVANCE_FOR_SCORING", "0.25"))
EVIDENCE_SNIPPET_CHARS = int(os.getenv("EVIDENCE_SNIPPET_CHARS", "900"))

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "that", "this", "these",
    "those", "is", "are", "was", "were", "be", "been", "being", "to", "of", "in",
    "on", "for", "from", "by", "with", "as", "at", "it", "its", "has", "have",
    "had", "will", "would", "can", "could", "should", "about", "into", "over",
    "after", "before", "news", "claim", "video", "says", "said",
}


class EvidenceStanceSchema(BaseModel):
    relevance: float = Field(ge=0.0, le=1.0, description="Whether the evidence is about the same specific factual claim.")
    stance: str = Field(description="One of SUPPORT, CONTRADICT, or INSUFFICIENT.")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the stance decision.")
    reason: str = Field(description="Brief explanation grounded in the evidence.")
    evidence_quote: str = Field(description="Short exact supporting phrase from the evidence, if available.")

SOURCES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "trusted_sources.json")
try:
    with open(SOURCES_PATH, "r") as f:
        SOURCE_WEIGHTS = json.load(f)
except Exception:
    SOURCE_WEIGHTS = {}

def calculate_weighted_score(findings):
    """
    Truth Score = weighted support minus weighted contradiction.

    Each finding is weighted by source trust, relevance, and stance confidence.
    Weak or unrelated evidence should contribute little or nothing.
    """
    if not findings:
        return 0.0
    
    support_sum = 0.0
    contradict_sum = 0.0
    total_weight = 0.0
    
    for result in findings:
        domain = result.get('domain', '')
        source_weight = 0.4
        for trusted_domain, w in SOURCE_WEIGHTS.items():
            if trusted_domain in domain:
                source_weight = w
                break
        if source_weight == 0.0:
            print(f"[!] Warning: Data source is blacklisted: {domain}")
            
        stance = result.get('stance', 'INSUFFICIENT')
        if stance == "NEUTRAL":
            stance = "INSUFFICIENT"

        relevance = result.get('relevance', result.get('similarity', 0.0))
        confidence = result.get('confidence', 0.5)
        evidence_weight = source_weight * relevance * confidence
        
        if stance == "SUPPORT":
            support_sum += evidence_weight
            total_weight += evidence_weight
        elif stance == "CONTRADICT":
            contradict_sum += evidence_weight
            total_weight += evidence_weight
    
    truth_score = (support_sum - contradict_sum) / total_weight if total_weight > 0 else 0.0
    
    return truth_score


def get_source_weight(domain: str) -> float:
    for trusted_domain, weight in SOURCE_WEIGHTS.items():
        if trusted_domain in domain:
            return weight
    return 0.4


def normalize_stance(stance: str) -> str:
    stance = (stance or "INSUFFICIENT").upper()
    if stance in {"SUPPORT", "SUPPORTED", "TRUE"}:
        return "SUPPORT"
    if stance in {"CONTRADICT", "CONTRADICTS", "FALSE"}:
        return "CONTRADICT"
    return "INSUFFICIENT"


def clamp_score(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def local_search_query(claim: str, max_terms: int = 8) -> str:
    """Cheap query extraction that avoids an API call for every verification."""
    tokens = re.findall(r"[\w\u0900-\u097F]+", claim.lower())
    useful_tokens = [t for t in tokens if len(t) > 2 and t not in STOP_WORDS]
    seen = set()
    keywords = []
    for token in useful_tokens:
        if token not in seen:
            seen.add(token)
            keywords.append(token)
        if len(keywords) >= max_terms:
            break
    return " ".join(keywords) if keywords else " ".join(claim.split()[:max_terms])

def extract_search_query(claim: str) -> str:
    """Uses Gemini to distill a long conversational claim into a concise 3-5 word search query."""
    if len(claim.split()) <= 6:
        return claim
    if not USE_LLM_QUERY_OPTIMIZER or not GEMINI_API_KEY:
        return local_search_query(claim)
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"Extract the most important 3 to 5 search keywords from this claim. Do not include stop words. Output ONLY the keywords separated by spaces, nothing else. Claim: {claim}"
    
    # We use a fast, low-retry loop since it's just for optimization
    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.1)
            )
            keywords = response.text.strip().replace('"', '')
            if keywords:
                return keywords
        except Exception as e:
            if "RESOURCE_EXHAUSTED" in str(e):
                import time
                time.sleep(5)
            pass
            
    # If it fails, fallback to the first 8 words natively
    return " ".join(claim.split()[:8])

def search_and_scrape_evidence(query: str, use_firecrawl: bool = False):
    optimized_query = extract_search_query(query)
    print(f"[*] Optimizing search query to: '{optimized_query}'")
    
    if use_firecrawl:
        if not FIRECRAWL_API_KEY:
            print("[!] Warning: FIRECRAWL_API_KEY not set. Falling back to simple bs4 scraper.")
        else:
            print(f"[*] Using Firecrawl API to search and scrape.")
            try:
                app = FirecrawlApp(api_key=FIRECRAWL_API_KEY)
                response = app.search(query=optimized_query, limit=3, scrape_options={"formats": ["markdown"]})
                evidence = []
                if response and 'data' in response:
                    for item in response['data']:
                        url = item.get('url', '')
                        domain = urlparse(url).netloc
                        evidence.append({
                            "title": item.get('title', 'Unknown'),
                            "url": url,
                            "domain": domain,
                            "content": item.get('markdown', '')[:1500]
                        })
                if evidence:
                    return evidence
                else:
                    print("[-] Firecrawl found 0 results. Falling back to simple scraper.")
            except Exception as e:
                print(f"[-] Firecrawl Failed: {e}. Falling back to simple scraper.")

    nepali_domains = ["ekantipur.com", "kathmandupost.com", "onlinekhabar.com", "setopati.com", 
                    "ratopati.com", "nepalfactcheck.org", "southasiacheck.org"]
    site_str = " OR ".join([f"site:{d}" for d in nepali_domains])
    search_query = f"{optimized_query} {site_str}"
    
    print(f"[*] Using DuckDuckGo + BeautifulSoup to search and scrape.")
    try:
        results = DDGS().text(search_query, max_results=3)
    except Exception as e:
        print(f"[-] DuckDuckGo search failed: {e}")
        results = []
    
    evidence = []
    if not results:
        return evidence
        
    for res in results:
        url = res.get('href')
        
        # Prevent scraping root homepages (e.g. onlinekhabar.com/) which contain generic spam
        parsed = urlparse(url)
        if len(parsed.path) < 5 or parsed.path == "/":
            continue
            
        title = res.get('title')
        domain = urlparse(url).netloc
        
        print(f"[*] Scraping evidence from: {domain}...")
        try:
            from newspaper import Article
            article = Article(url, fetch_images=False, request_timeout=10)
            article.download()
            article.parse()
            text_content = article.text
            
            if not text_content.strip():
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                response = requests.get(url, headers=headers, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                paragraphs = soup.find_all('p')
                text_content = "\n".join([p.get_text() for p in paragraphs])
            
            evidence.append({
                "title": article.title if article.title else title,
                "url": url,
                "domain": domain,
                "content": text_content[:1500]
            })
        except Exception as e:
            print(f"[-] Failed to scrape {url}: {e}")
            
    return evidence

import time

def evaluate_evidence_embedding(claim: str, evidence_item: dict) -> dict:
    """
    Cheap first-pass evidence evaluation.

    It estimates relevance locally and only makes a weak stance guess. This is used
    both as an API-token gate and as the fallback when LLM stance classification is
    disabled or unavailable.
    No API calls needed - fully deterministic.
    """
    evidence_text = evidence_item.get('content', '')[:1500]
    evidence_lower = evidence_text.lower()
    claim_lower = claim.lower()
    
    # Nepal-specific claim keywords
    nepali_claim_entities = {
        'government', 'nepal', 'prime', 'minister', 'kathmandu', 'municipality',
        'river', 'bank', 'demolition', 'illegal', 'building', 'road', 'highway',
        'construction', 'project', 'development', 'budget', 'hospital', 'school'
    }
    
    # Strong support indicators
    support_words = [
        'confirmed', 'true', 'announced', 'approved', 'launched', 'begins', 
        'construction started', 'fund approved', 'will implement', 'initiated',
        'clearance granted', 'permission granted', 'tender awarded', 'contract signed',
        'development', 'inaugurated', 'completed', 'opened'
    ]
    
    # Strong contradiction indicators  
    contradict_words = [
        'denied', 'false', 'fake', 'cancelled', 'stopped', 'rejected', 'debunked',
        'misleading', 'hoax', 'rumor', 'untrue', 'incorrect',
        'not authorized', 'no permission', 'violated', 'scam', 'fraud'
    ]
    
    claim_keywords = set(re.findall(r"[\w\u0900-\u097F]+", claim_lower))
    claim_entities = claim_keywords & nepali_claim_entities
    evidence_tokens = set(re.findall(r"[\w\u0900-\u097F]+", evidence_lower))
    evidence_entities = evidence_tokens & nepali_claim_entities
    entity_overlap = len(claim_entities & evidence_entities)
    
    support_count = sum(1 for w in support_words if w in evidence_lower)
    contradict_count = sum(1 for w in contradict_words if w in evidence_lower)

    claim_terms = [t for t in claim_keywords if len(t) > 2 and t not in STOP_WORDS]
    term_overlap = len(set(claim_terms) & evidence_tokens)
    similarity = compute_similarity(claim[:300], evidence_text[:700]) if evidence_text.strip() else 0.0
    relevance = clamp_score((similarity * 0.65) + (min(term_overlap, 6) / 6 * 0.25) + (min(entity_overlap, 3) / 3 * 0.10))
    
    # Stance determination with priority
    if relevance < MIN_RELEVANCE_FOR_SCORING:
        stance = "INSUFFICIENT"
        confidence = 0.35
    elif entity_overlap >= 2:
        if support_count > contradict_count:
            stance = "SUPPORT"
            confidence = 0.55
        elif contradict_count > support_count:
            stance = "CONTRADICT"
            confidence = 0.55
        else:
            stance = "INSUFFICIENT"
            confidence = 0.40
    elif support_count > 0 and contradict_count == 0:
        stance = "SUPPORT"
        confidence = 0.45
    elif contradict_count > 0 and support_count == 0:
        stance = "CONTRADICT"
        confidence = 0.45
    elif support_count > contradict_count:
        stance = "SUPPORT"
        confidence = 0.45
    elif contradict_count > support_count:
        stance = "CONTRADICT"
        confidence = 0.45
    else:
        stance = "INSUFFICIENT"
        confidence = 0.35
    
    return {
        "stance": stance,
        "relevance": round(relevance, 3),
        "similarity": round(similarity, 3),
        "confidence": round(confidence, 3),
        "reasoning": f"Relevance: {relevance:.3f}, Similarity: {similarity:.3f}, Terms: {term_overlap}, Entities: {entity_overlap}, Support: {support_count}, Contradict: {contradict_count}",
        "method": "local_embedding"
    }


def classify_evidence_with_gemini(claim: str, evidence_item: dict, local_eval: dict) -> dict:
    """
    Token-bounded stance classification for only the best local evidence candidates.
    Returns the local evaluation if Gemini is disabled, missing, or fails.
    """
    if not USE_LLM_STANCE or not GEMINI_API_KEY:
        return local_eval

    evidence_text = " ".join(evidence_item.get("content", "").split())[:EVIDENCE_SNIPPET_CHARS]
    if not evidence_text:
        return local_eval

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""
You are checking whether one evidence excerpt verifies one factual claim.
Classify only from the excerpt. If the excerpt is about a related topic but does not directly prove or disprove the claim, use INSUFFICIENT.

Claim:
{claim[:500]}

Evidence title:
{evidence_item.get('title', '')[:180]}

Evidence excerpt:
{evidence_text}
"""
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=EvidenceStanceSchema,
                temperature=0.0,
            ),
        )
        llm_result = json.loads(response.text)
        stance = normalize_stance(llm_result.get("stance"))
        relevance = clamp_score(float(llm_result.get("relevance", local_eval.get("relevance", 0.0))))
        confidence = clamp_score(float(llm_result.get("confidence", local_eval.get("confidence", 0.5))))
        if relevance < MIN_RELEVANCE_FOR_SCORING:
            stance = "INSUFFICIENT"
        return {
            **local_eval,
            "stance": stance,
            "relevance": round(relevance, 3),
            "confidence": round(confidence, 3),
            "reasoning": llm_result.get("reason", local_eval.get("reasoning", ""))[:500],
            "evidence_quote": llm_result.get("evidence_quote", "")[:300],
            "method": "gemini_stance",
        }
    except Exception as e:
        print(f"[!] Gemini stance classification failed, using local fallback: {e}")
        return local_eval


def select_verdict(truth_score: float, confidence: float) -> str:
    if confidence < 0.35:
        return "uncertain"
    if truth_score >= 0.35:
        return "likely_true"
    if truth_score <= -0.35:
        return "likely_false"
    return "uncertain"

def verify_claim(core_claim: str, url: str = None, use_firecrawl: bool = False) -> dict:
    print(f"[*] Verifying claim: {core_claim[:100]}...")
    
    result = {
        "core_claim": core_claim,
        "neutrosophic": {"T": 0.5, "I": 0.3, "F": 0.2},
        "truth_score": 0.0,
        "confidence": 0.0,
        "verdict": "uncertain",
        "past_similar_claims": [],
        "evidence": [],
        "findings": [],
        "summary": ""
    }
    
    try:
        similar = search_similar_claims(core_claim, threshold=1.5)
        if similar:
            print(f"[+] Found {len(similar)} similar past claims")
            result["past_similar_claims"] = similar
    except Exception as e:
        print(f"[!] ChromaDB search failed: {e}")
    
    evidence = search_and_scrape_evidence(core_claim, use_firecrawl=use_firecrawl)
    result["evidence"] = [
        {"title": e.get("title", ""), "domain": e.get("domain", ""), "url": e.get("url", "")}
        for e in evidence
    ]
    
    if evidence:
        print("[*] Evaluating evidence relevance locally...")
        local_candidates = []
        for index, ev in enumerate(evidence):
            local_eval = evaluate_evidence_embedding(core_claim, ev)
            local_candidates.append((index, ev, local_eval))

        local_candidates.sort(key=lambda item: item[2].get("relevance", 0.0), reverse=True)
        llm_budget = max(0, MAX_LLM_EVIDENCE_ITEMS)
        llm_used = 0
        findings = []

        for index, ev, local_eval in local_candidates:
            if local_eval.get("relevance", 0.0) < MIN_RELEVANCE_FOR_SCORING:
                eval_result = local_eval
            elif llm_used < llm_budget and local_eval.get("relevance", 0.0) >= MIN_RELEVANCE_FOR_LLM:
                eval_result = classify_evidence_with_gemini(core_claim, ev, local_eval)
                if eval_result.get("method") == "gemini_stance":
                    llm_used += 1
            else:
                eval_result = local_eval

            finding = {
                "domain": ev.get("domain", ""),
                "stance": normalize_stance(eval_result.get("stance", "INSUFFICIENT")),
                "relevance": eval_result.get("relevance", 0.0),
                "similarity": eval_result.get("similarity", 0.5),
                "confidence": eval_result.get("confidence", 0.5),
                "source_weight": get_source_weight(ev.get("domain", "")),
                "method": eval_result.get("method", "local_embedding"),
                "reasoning": eval_result.get("reasoning", ""),
                "evidence_quote": eval_result.get("evidence_quote", ""),
                "title": ev.get("title", ""),
                "url": ev.get("url", "")
            }
            findings.append(finding)
        
        findings.sort(key=lambda f: (f.get("stance") != "INSUFFICIENT", f.get("relevance", 0.0)), reverse=True)
        truth_score = calculate_weighted_score(findings)
        result["truth_score"] = truth_score

        support_weight = 0.0
        contradict_weight = 0.0
        insufficient_weight = 0.0
        for f in findings:
            weight = f.get("source_weight", 0.4) * f.get("relevance", 0.0) * f.get("confidence", 0.5)
            if f["stance"] == "SUPPORT":
                support_weight += weight
            elif f["stance"] == "CONTRADICT":
                contradict_weight += weight
            else:
                insufficient_weight += max(weight, 0.05)

        total_weight = support_weight + contradict_weight + insufficient_weight
        if total_weight > 0:
            result["neutrosophic"]["T"] = round(support_weight / total_weight, 3)
            result["neutrosophic"]["F"] = round(contradict_weight / total_weight, 3)
            result["neutrosophic"]["I"] = round(insufficient_weight / total_weight, 3)

        decisive_weight = support_weight + contradict_weight
        result["confidence"] = round(clamp_score(decisive_weight / (total_weight or 1.0)), 3)
        result["verdict"] = select_verdict(truth_score, result["confidence"])
        
        result["findings"] = findings
        support_count = sum(1 for f in findings if f["stance"] == "SUPPORT")
        contradict_count = sum(1 for f in findings if f["stance"] == "CONTRADICT")
        insufficient_count = len(findings) - support_count - contradict_count
        result["summary"] = (
            f"Verdict: {result['verdict']} | Truth Score: {truth_score:.3f} | "
            f"Confidence: {result['confidence']:.3f} | "
            f"{support_count} support, {contradict_count} contradict, {insufficient_count} insufficient | "
            f"Gemini stance calls: {llm_used}"
        )
    else:
        result["summary"] = "No external evidence found; verdict remains uncertain."
    
    return result
