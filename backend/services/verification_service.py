import os
import json
import re
from urllib.parse import urlparse, parse_qs
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
GEMINI_KEYS = [k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()]
CURRENT_KEY_INDEX = 0
ALL_KEYS_EXHAUSTED_AT = 0.0
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
    stance: str = Field(description="One of SUPPORT, CONTRADICT, or INDETERMINATE.")
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
            
        stance = result.get('stance', 'INDETERMINATE')
        if stance == "NEUTRAL":
            stance = "INDETERMINATE"

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
    stance = (stance or "INDETERMINATE").upper()
    if stance in {"SUPPORT", "SUPPORTED", "TRUE", "SUPPORTS"}:
        return "SUPPORT"
    if stance in {"CONTRADICT", "CONTRADICTS", "FALSE", "REFUTED", "REFUTES"}:
        return "CONTRADICT"
    return "INDETERMINATE"


def clamp_score(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def count_indicators(text: str, indicators: list[str]) -> int:
    return sum(1 for indicator in indicators if indicator in text)


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
    if not USE_LLM_QUERY_OPTIMIZER or not GEMINI_KEYS:
        return local_search_query(claim)
    
    for attempt in range(len(GEMINI_KEYS)):
        try:
            global CURRENT_KEY_INDEX
            client = genai.Client(api_key=GEMINI_KEYS[CURRENT_KEY_INDEX])
            prompt = f"Distill the following claim into 3-5 keyword search terms. Return only the keywords, no explanations.\n\nClaim: {claim}"
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.1)
            )
            keywords = response.text.strip().replace('"', '')
            if keywords:
                return keywords
        except Exception as e:
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                CURRENT_KEY_INDEX = (CURRENT_KEY_INDEX + 1) % len(GEMINI_KEYS)
                continue
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

    searchable_domains = [domain for domain, weight in SOURCE_WEIGHTS.items() if weight > 0]
    site_str = " OR ".join([f"site:{domain}" for domain in searchable_domains])
    search_query = f"{optimized_query} {site_str}" if site_str else optimized_query
    
    print(f"[*] Using DuckDuckGo + BeautifulSoup to search and scrape.")
    results = []
    for attempt in range(3):
        try:
            results = DDGS().text(search_query, max_results=3)
            if results:
                break
        except Exception as e:
            print(f"[-] DuckDuckGo search attempt {attempt + 1}/3 failed: {e}")
            if attempt < 2:
                time.sleep(3)
    
    evidence = []
    if not results:
        print("[-] DuckDuckGo returned no results. Trying direct HTTP fallback...")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            resp = requests.get(
                f"https://html.duckduckgo.com/html/?q={requests.utils.quote(search_query)}",
                headers=headers, timeout=15
            )
            soup = BeautifulSoup(resp.text, 'html.parser')
            for link in soup.select('.result__a'):
                href = link.get('href')
                if href:
                    parsed = urlparse(href)
                    qs = parse_qs(parsed.query)
                    actual_url = qs.get('uddg', [None])[0] or href
                    snippet_el = link.find_next('.result__snippet')
                    results.append({
                        'href': actual_url,
                        'title': link.get_text(strip=True),
                        'body': snippet_el.get_text(strip=True) if snippet_el else '',
                    })
            results = results[:3]
        except Exception as e2:
            print(f"[-] Direct DuckDuckGo fallback also failed: {e2}")
    
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
    
    # Nepal-specific and general fact-checking entities
    nepali_claim_entities = {
        'government', 'nepal', 'prime', 'minister', 'kathmandu', 'municipality',
        'river', 'bank', 'demolition', 'illegal', 'building', 'road', 'highway',
        'construction', 'project', 'development', 'budget', 'hospital', 'school',
        'parliament', 'president', 'mayor', 'ward', 'province', 'district',
        'police', 'army', 'court', 'commission', 'ministry', 'ministerial',
        'election', 'vote', 'candidate', 'party', 'tax', 'price', 'fuel',
        'electricity', 'airport', 'bridge', 'tunnel', 'landslide', 'flood',
        'earthquake', 'border', 'citizenship', 'passport', 'visa', 'climate',
        'warming', 'temperature', 'carbon', 'emissions', 'environment', 'science',
        'nasa', 'ipcc', 'noaa', 'united', 'nations', 'supreme', 'central',
        'नपल', 'नेपाल', 'सरकार', 'प्रधानमन्त्री', 'मन्त्री', 'काठमाडौं', 'पालिका',
        'नगरपालिका', 'अदालत', 'प्रहरी', 'सेना', 'निर्वाचन', 'चुनाव',
        'बजेट', 'सडक', 'अस्पताल', 'विद्यालय', 'विकास', 'वातावरण', 'जलवायु',
        'परिवर्तन', 'तापक्रम'
    }
    
    # Strong support indicators
    support_words = [
        'confirmed', 'true', 'announced', 'approved', 'launched', 'begins',
        'construction started', 'fund approved', 'will implement', 'initiated',
        'clearance granted', 'permission granted', 'tender awarded', 'contract signed',
        'development', 'inaugurated', 'completed', 'opened', 'verified',
        'officially confirmed', 'has confirmed', 'have confirmed', 'according to',
        'reported that', 'stated that', 'said that', 'revealed that', 'found that',
        'evidence shows', 'data shows', 'records show', 'documents show',
        'signed', 'passed', 'implemented', 'enforced', 'published', 'released',
        'issued', 'declared', 'decided', 'endorsed', 'ratified', 'allocated',
        'budget allocated', 'notice issued', 'gazette published', 'started',
        'resumed', 'operational', 'in operation', 'took effect', 'came into effect',
        'scientific consensus', 'study found', 'research indicates', 'evidence suggests',
        'consistent with', 'peer-reviewed', 'data supports', 'corroborates',
        'substantiates', 'validated', 'authentic', 'legitimate', 'unanimous',
        'पुष्टि', 'सत्य', 'स्वीकृत', 'अनुमोदन', 'घोषणा', 'सुरु', 'शुरु',
        'कार्यान्वयन', 'निर्णय', 'जारी', 'प्रकाशित', 'सम्पन्न', 'खुला',
        'पारित', 'बजेट विनियोजन', 'ठेक्का', 'सम्झौता', 'प्रमाणित',
        'pushti', 'satya', 'swikrit', 'anumodan', 'ghoshana', 'suru',
        'karyanwayan', 'nirnaya', 'jari', 'prakashit', 'parit'
    ]
    
    # Strong contradiction indicators
    contradict_words = [
        'denied', 'false', 'fake', 'cancelled', 'stopped', 'rejected', 'debunked',
        'misleading', 'hoax', 'rumor', 'untrue', 'incorrect',
        'not authorized', 'no permission', 'violated', 'scam', 'fraud',
        'no evidence', 'not true', 'is not true', 'was not true', 'not correct',
        'fact check', 'fact-check', 'fact checked', 'fabricated', 'baseless',
        'unverified', 'unsubstantiated', 'doctored', 'manipulated', 'edited',
        'old video', 'old photo', 'taken out of context', 'out of context',
        'wrong context', 'miscaptioned', 'unrelated video', 'unrelated photo',
        'denies', 'denied that', 'refuted', 'contradicted', 'clarified that no',
        'there is no', 'there are no', 'has not', 'have not', 'did not',
        'will not', 'never', 'without permission', 'unauthorized', 'invalid',
        'illegal', 'arrested for spreading', 'police denied', 'officials denied',
        'misinformation', 'scientific myth', 'lack of empirical evidence',
        'discredited', 'inconsistent with', 'unfounded', 'refuted by',
        'खण्डन', 'गलत', 'झुटो', 'झूठो', 'नक्कली', 'भ्रामक', 'अफवाह',
        'असत्य', 'होइन', 'छैन', 'गरेको छैन', 'भएको छैन', 'स्वीकार गरेन',
        'अस्वीकार', 'रद्द', 'फर्जी', 'ठगी', 'प्रमाण छैन', 'गलत सूचना',
        'khandan', 'galat', 'jhuto', 'nakkali', 'bhramak', 'afwah',
        'asatya', 'hoina', 'chaina', 'gareko chaina', 'bhayeko chaina',
        'aswikar', 'radda', 'farji', 'thagi'
    ]

    uncertainty_words = [
        'alleged', 'allegedly', 'claim', 'claims', 'claimed', 'reportedly',
        'unconfirmed', 'unclear', 'unknown', 'may', 'might', 'could',
        'possibly', 'likely', 'rumoured', 'rumored', 'sources say',
        'not independently verified', 'investigation ongoing', 'under investigation',
        'awaiting confirmation', 'unproven', 'specious', 'fallacious',
        'अस्पष्ट', 'अनिश्चित', 'दाबी', 'भनिएको', 'सम्भावना', 'हुन सक्छ',
        'पुष्टि हुन बाँकी', 'अनुसन्धान जारी',
        'aspashta', 'anischit', 'dabi', 'bhanieko', 'huna sakcha'
    ]
    
    claim_keywords = set(re.findall(r"[\w\u0900-\u097F]+", claim_lower))
    claim_entities = claim_keywords & nepali_claim_entities
    evidence_tokens = set(re.findall(r"[\w\u0900-\u097F]+", evidence_lower))
    evidence_entities = evidence_tokens & nepali_claim_entities
    entity_overlap = len(claim_entities & evidence_entities)
    
    support_count = count_indicators(evidence_lower, support_words)
    contradict_count = count_indicators(evidence_lower, contradict_words)
    uncertainty_count = count_indicators(evidence_lower, uncertainty_words)

    claim_terms = [t for t in claim_keywords if len(t) > 2 and t not in STOP_WORDS]
    term_overlap = len(set(claim_terms) & evidence_tokens)
    similarity = compute_similarity(claim[:300], evidence_text[:700]) if evidence_text.strip() else 0.0
    relevance = clamp_score((similarity * 0.65) + (min(term_overlap, 6) / 6 * 0.25) + (min(entity_overlap, 3) / 3 * 0.10))
    
    # Stance determination with priority
    if relevance < MIN_RELEVANCE_FOR_SCORING:
        stance = "INDETERMINATE"
        confidence = 0.35
    elif uncertainty_count > max(support_count, contradict_count) and support_count == 0 and contradict_count == 0:
        stance = "INDETERMINATE"
        confidence = 0.45
    elif entity_overlap >= 2:
        if support_count > contradict_count:
            stance = "SUPPORT"
            confidence = 0.55
        elif contradict_count > support_count:
            stance = "CONTRADICT"
            confidence = 0.55
        else:
            stance = "INDETERMINATE"
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
        stance = "INDETERMINATE"
        confidence = 0.35
    
    return {
        "stance": stance,
        "relevance": round(relevance, 3),
        "similarity": round(similarity, 3),
        "confidence": round(confidence, 3),
        "reasoning": f"Relevance: {relevance:.3f}, Similarity: {similarity:.3f}, Terms: {term_overlap}, Entities: {entity_overlap}, Support: {support_count}, Contradict: {contradict_count}, Uncertainty: {uncertainty_count}",
        "method": "local_embedding"
    }


def classify_evidence_with_gemini(claim: str, evidence_item: dict, local_eval: dict) -> dict:
    """
    Token-bounded stance classification for only the best local evidence candidates.
    Returns the local evaluation if Gemini is disabled, missing, or fails.
    """
    global CURRENT_KEY_INDEX, ALL_KEYS_EXHAUSTED_AT

    if not USE_LLM_STANCE or not GEMINI_KEYS:
        return local_eval

    # If all keys were recently exhausted, wait before retrying
    cooldown_remaining = ALL_KEYS_EXHAUSTED_AT + 30 - time.time()
    if cooldown_remaining > 0:
        print(f"[!] All keys exhausted, cooling down for {cooldown_remaining:.0f}s...")
        time.sleep(cooldown_remaining)
        ALL_KEYS_EXHAUSTED_AT = 0.0

    evidence_text = " ".join(evidence_item.get("content", "").split())[:EVIDENCE_SNIPPET_CHARS]
    if not evidence_text:
        return local_eval

    prompt = f"""
You are a professional fact-checker. Determine if the evidence excerpt supports or contradicts the claim.

Guidelines:
- SUPPORT: If the evidence provides direct or strong logical confirmation. Note: Scientific terms like "suggests", "consistent with", or "indicates" should be treated as SUPPORT in a scientific context.
- CONTRADICT: If the evidence directly refutes or provides a factual counter-point.
- INDETERMINATE: Use ONLY if the evidence is completely irrelevant or the information is insufficient to make even a logical inference.

Claim: {claim[:500]}
Evidence Title: {evidence_item.get('title', '')[:110]}
Evidence Content: {evidence_text}
"""
    
    initial_index = CURRENT_KEY_INDEX
    
    for _ in range(len(GEMINI_KEYS)):
        current_key = GEMINI_KEYS[CURRENT_KEY_INDEX]
        client = genai.Client(api_key=current_key)
        
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
            
            print(f"[DEBUG] Gemini Result (Key {CURRENT_KEY_INDEX}): Stance={stance}, Relevance={relevance}, Conf={confidence}")
            
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
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                err_msg = str(e)[:200]
                if "RATE_LIMIT" in err_msg.upper():
                    limit = "per-minute rate limit"
                elif "exceeded your current quota" in err_msg.lower():
                    limit = "daily free-tier quota"
                elif "daily" in err_msg.lower() or "day" in err_msg.lower():
                    limit = "daily quota"
                elif "per month" in err_msg.lower() or "monthly" in err_msg.lower():
                    limit = "monthly quota"
                elif "token" in err_msg.lower():
                    limit = "token limit"
                else:
                    limit = "generic quota"
                print(f"[!] Key {CURRENT_KEY_INDEX} hit {limit}: {err_msg[:120]}")
                CURRENT_KEY_INDEX = (CURRENT_KEY_INDEX + 1) % len(GEMINI_KEYS)
                time.sleep(1)
                if CURRENT_KEY_INDEX == initial_index:
                    print("[!] All Gemini API keys exhausted.")
                    ALL_KEYS_EXHAUSTED_AT = time.time()
                    break
                continue
            else:
                print(f"[!] Gemini stance classification failed: {e}")
                return local_eval
                
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
    
    # Internal working dict
    working_result = {
        "core_claim": core_claim,
        "neutrosophic": {"T": 0.5, "I": 0.3, "F": 0.2},
        "truth_score": 0.0,
        "confidence": 0.0,
        "verdict": "uncertain",
        "past_similar_claims": [],
        "evidence": [],
        "findings": [],
        "summary": "",
        "llm_used": 0
    }
    
    try:
        similar = search_similar_claims(core_claim, threshold=1.5)
        if similar:
            print(f"[+] Found {len(similar)} similar past claims")
            working_result["past_similar_claims"] = similar
    except Exception as e:
        print(f"[!] ChromaDB search failed: {e}")
    
    evidence = search_and_scrape_evidence(core_claim, use_firecrawl=use_firecrawl)
    working_result["evidence"] = [
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
                local_stance = local_eval.get("stance", "INDETERMINATE")
                local_confidence = local_eval.get("confidence", 0.0)
                if local_stance != "INDETERMINATE" and local_confidence >= 0.5:
                    eval_result = local_eval
                else:
                    eval_result = classify_evidence_with_gemini(core_claim, ev, local_eval)
                    if eval_result.get("method") == "gemini_stance":
                        llm_used += 1
            else:
                eval_result = local_eval

            finding = {
                "domain": ev.get("domain", ""),
                "title": ev.get("title", ""),
                "snippet": ev.get("content", "")[:300],
                "stance": normalize_stance(eval_result.get("stance", "INDETERMINATE")),
                "relevance": eval_result.get("relevance", 0.0),
                "confidence": eval_result.get("confidence", 0.5),
                "source_credibility": get_source_weight(ev.get("domain", "")),
                "evidence_weight": eval_result.get("relevance", 0.0) * eval_result.get("confidence", 0.5) * get_source_weight(ev.get("domain", ""))
            }
            findings.append(finding)
        
        findings.sort(key=lambda f: (f.get("stance") != "INDETERMINATE", f.get("relevance", 0.0)), reverse=True)
        truth_score = calculate_weighted_score(findings)
        working_result["truth_score"] = truth_score

        support_weight = 0.0
        contradict_weight = 0.0
        insufficient_weight = 0.0
        for f in findings:
            weight = f.get("source_credibility", 0.4) * f.get("relevance", 0.0) * f.get("confidence", 0.5)
            if f["stance"] == "SUPPORT":
                support_weight += weight
            elif f["stance"] == "CONTRADICT":
                contradict_weight += weight
            else:
                insufficient_weight += max(weight, 0.05)

        total_weight = support_weight + contradict_weight + insufficient_weight
        if total_weight > 0:
            working_result["neutrosophic"]["T"] = round(support_weight / total_weight, 3)
            working_result["neutrosophic"]["F"] = round(contradict_weight / total_weight, 3)
            working_result["neutrosophic"]["I"] = round(insufficient_weight / total_weight, 3)

        decisive_weight = support_weight + contradict_weight
        working_result["confidence"] = round(clamp_score(decisive_weight / (total_weight or 1.0)), 3)
        working_result["verdict"] = select_verdict(truth_score, working_result["confidence"])
        
        working_result["findings"] = findings
        support_count = sum(1 for f in findings if f["stance"] == "SUPPORT")
        contradict_count = sum(1 for f in findings if f["stance"] == "CONTRADICT")
        insufficient_count = len(findings) - support_count - contradict_count
        working_result["summary"] = (
            f"Verdict: {working_result['verdict']} | Truth Score: {truth_score:.3f} | "
            f"Confidence: {working_result['confidence']:.3f} | "
            f"{support_count} support, {contradict_count} contradict, {insufficient_count} insufficient | "
            f"Gemini stance calls: {llm_used}"
        )
        working_result["llm_used"] = llm_used
    else:
        working_result["summary"] = "No external evidence found; verdict remains uncertain."
    
    # Transform to VerificationResult schema
    result = {
        "claim": working_result["core_claim"],
        "verdict": working_result["verdict"],
        "truth_score": working_result["truth_score"],
        "confidence": working_result["confidence"],
        "evidence_count": len(working_result["findings"]),
        "evidence_findings": working_result["findings"],
        "neutrosophic_score": {
            "truth": working_result["neutrosophic"]["T"],
            "indeterminacy": working_result["neutrosophic"]["I"],
            "falsity": working_result["neutrosophic"]["F"]
        },
        "reasoning": working_result["summary"],
        "used_llm": working_result["llm_used"] > 0
    }
    
    return result
