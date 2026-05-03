import os
import json
from urllib.parse import urlparse
from ddgs import DDGS
from bs4 import BeautifulSoup
import requests
from firecrawl import FirecrawlApp
from dotenv import load_dotenv

load_dotenv()
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")

# Load the trusted sources weights
SOURCES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "trusted_sources.json")
try:
    with open(SOURCES_PATH, "r") as f:
        SOURCE_WEIGHTS = json.load(f)
except Exception:
    SOURCE_WEIGHTS = {}

def calculate_weighted_score(findings):
    """
    Calculates the truth score based on authority weights.
    findings: list of dicts with 'domain', 'stance' ("SUPPORT"|"CONTRADICT"|"NEUTRAL"), and 'similarity' (float)
    """
    total_score = 0
    for result in findings:
        domain = result.get('domain', '')
        
        # Check if the domain ends with any trusted domain (e.g., english.onlinekhabar.com -> onlinekhabar.com)
        weight = 0.4 # Default weight
        for trusted_domain, w in SOURCE_WEIGHTS.items():
            if trusted_domain in domain:
                weight = w
                break
                
        # If it's a blacklist site, flag it
        if weight == 0.0:
            print(f"[!] Warning: Data source is blacklisted: {domain}")
            
        stance = result.get('stance', 'NEUTRAL')
        similarity = result.get('similarity', 0.5)
        
        if stance == "SUPPORT":
            total_score += (similarity * weight)
        elif stance == "CONTRADICT":
            total_score -= (similarity * weight)
            
    return total_score

def search_and_scrape_evidence(query: str, use_firecrawl: bool = False):
    """
    Search and scrape evidence. Can toggle between Firecrawl and BeautifulSoup (local).
    """
    print(f"[*] Searching the web for: {query}")
    
    search_query = f"{query} site:onlinekhabar.com OR site:setopati.com OR site:ekantipur.com"
    
    # Option 1: Firecrawl
    if use_firecrawl:
        if not FIRECRAWL_API_KEY:
            print("[!] Warning: FIRECRAWL_API_KEY not set. Falling back to simple bs4 scraper.")
        else:
            print(f"[*] Using Firecrawl API to search and scrape.")
            try:
                app = FirecrawlApp(api_key=FIRECRAWL_API_KEY)
                # The latest Firecrawl API uses scrape_options
                response = app.search(query=search_query, limit=3, scrape_options={"formats": ["markdown"]})
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
                return evidence
            except Exception as e:
                print(f"[-] Firecrawl Failed: {e}. Falling back to simple scraper.")

    # Option 2: DuckDuckGo + BeautifulSoup (Fallback / Default)
    print(f"[*] Using DuckDuckGo + BeautifulSoup to search and scrape.")
    results = DDGS().text(search_query, max_results=3)
    
    evidence = []
    if not results:
        return evidence
        
    for res in results:
        url = res.get('href')
        title = res.get('title')
        domain = urlparse(url).netloc
        
        print(f"[*] Scraping evidence from: {domain}...")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Basic text extraction
            paragraphs = soup.find_all('p')
            text_content = "\n".join([p.get_text() for p in paragraphs])
            
            evidence.append({
                "title": title,
                "url": url,
                "domain": domain,
                "content": text_content[:1500]
            })
        except Exception as e:
            print(f"[-] Failed to scrape {url}: {e}")
            
    return evidence
