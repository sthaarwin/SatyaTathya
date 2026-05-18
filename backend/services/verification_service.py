import os
import json
from urllib.parse import urlparse
from ddgs import DDGS
from bs4 import BeautifulSoup
import requests
from firecrawl import FirecrawlApp
from google import genai
from google.genai import types
from dotenv import load_dotenv
from services.chroma_service import search_similar_claims, compute_similarity

load_dotenv()
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

SOURCES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "trusted_sources.json")
try:
    with open(SOURCES_PATH, "r") as f:
        SOURCE_WEIGHTS = json.load(f)
except Exception:
    SOURCE_WEIGHTS = {}

def calculate_weighted_score(findings):
    """
    Truth Score = (sum(S_i * W_i) - sum(C_j * W_j)) / Total Sources Found
    
    Where:
    - S_i: Similarity score of Supporting article
    - C_j: Similarity score of Contradicting article
    - W_i, W_j: Weight of source (e.g., Nepal Gazette = 1.0, Random Blog = 0.3)
    """
    if not findings:
        return 0.0
    
    support_sum = 0.0
    contradict_sum = 0.0
    
    for result in findings:
        domain = result.get('domain', '')
        weight = 0.4
        for trusted_domain, w in SOURCE_WEIGHTS.items():
            if trusted_domain in domain:
                weight = w
                break
        if weight == 0.0:
            print(f"[!] Warning: Data source is blacklisted: {domain}")
            
        stance = result.get('stance', 'NEUTRAL')
        similarity = result.get('similarity', 0.5)
        
        if stance == "SUPPORT":
            support_sum += (similarity * weight)
        elif stance == "CONTRADICT":
            contradict_sum += (similarity * weight)
    
    total_sources = len([f for f in findings if f.get('stance') in ['SUPPORT', 'CONTRADICT']])
    truth_score = (support_sum - contradict_sum) / total_sources if total_sources > 0 else 0.0
    
    return truth_score

def extract_search_query(claim: str) -> str:
    """Uses Gemini to distill a long conversational claim into a concise 3-5 word search query."""
    if not GEMINI_API_KEY or len(claim.split()) <= 6:
        return claim
    
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
    Uses sentence-transformers embeddings to compute similarity.
    Uses keyword matching for stance (SUPPORT/CONTRADICT/NEUTRAL).
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
        'misleading', 'hoax', 'rumor', 'untrue', 'incorrect', 'illegal',
        'not authorized', 'no permission', 'violated', 'scam', 'fraud'
    ]
    
    claim_keywords = set(claim_lower.split())
    claim_entities = claim_keywords & nepali_claim_entities
    evidence_entities = set(evidence_lower.split()) & nepali_claim_entities
    entity_overlap = len(claim_entities & evidence_entities)
    
    support_count = sum(1 for w in support_words if w in evidence_lower)
    contradict_count = sum(1 for w in contradict_words if w in evidence_lower)
    
    # Stance determination with priority
    if entity_overlap >= 2:
        if support_count > contradict_count:
            stance = "SUPPORT"
        elif contradict_count > support_count:
            stance = "CONTRADICT"
        else:
            stance = "SUPPORT"  # Same entities = likely related
    elif support_count > 0 and contradict_count == 0:
        stance = "SUPPORT"
    elif contradict_count > 0 and support_count == 0:
        stance = "CONTRADICT"
    elif support_count > contradict_count:
        stance = "SUPPORT"
    elif contradict_count > support_count:
        stance = "CONTRADICT"
    else:
        stance = "NEUTRAL"
    
    # Compute embedding similarity with claim + extracted key terms
    key_terms = " ".join(claim_entities) if claim_entities else claim[:200]
    similarity = compute_similarity(key_terms, evidence_text[:500])
    
    # Boost similarity if high entity overlap
    if entity_overlap >= 3:
        similarity = min(1.0, similarity + 0.2)
    
    return {
        "stance": stance,
        "similarity": round(similarity, 3),
        "reasoning": f"Similarity: {similarity:.3f}, Entities: {entity_overlap}, Support: {support_count}, Contradict: {contradict_count}"
    }

def verify_claim(core_claim: str, url: str = None, use_firecrawl: bool = False) -> dict:
    print(f"[*] Verifying claim: {core_claim[:100]}...")
    
    result = {
        "core_claim": core_claim,
        "neutrosophic": {"T": 0.5, "I": 0.3, "F": 0.2},
        "truth_score": 0.0,
        "past_similar_claims": [],
        "evidence": [],
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
        print("[*] Computing embedding similarity for evidence...")
        findings = []
        for ev in evidence:
            eval_result = evaluate_evidence_embedding(core_claim, ev)
            finding = {
                "domain": ev.get("domain", ""),
                "stance": eval_result.get("stance", "NEUTRAL"),
                "similarity": eval_result.get("similarity", 0.5),
                "reasoning": eval_result.get("reasoning", ""),
                "title": ev.get("title", ""),
                "url": ev.get("url", "")
            }
            findings.append(finding)
        
        truth_score = calculate_weighted_score(findings)
        result["truth_score"] = truth_score
        
        total = len(findings)
        support_count = sum(1 for f in findings if f["stance"] == "SUPPORT")
        contradict_count = sum(1 for f in findings if f["stance"] == "CONTRADICT")
        
        result["neutrosophic"]["T"] = support_count / total if total > 0 else 0.0
        result["neutrosophic"]["F"] = contradict_count / total if total > 0 else 0.0
        result["neutrosophic"]["I"] = 1.0 - (result["neutrosophic"]["T"] + result["neutrosophic"]["F"])
        
        result["findings"] = findings
        result["summary"] = f"Truth Score: {truth_score:.3f} ({support_count} support, {contradict_count} contradict, {total-support_count-contradict_count} neutral)"
    
    return result
