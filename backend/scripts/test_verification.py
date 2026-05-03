import os
import sys
import json
import argparse
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Ensure the parent directory is in the path to import from services correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.verification_service import search_and_scrape_evidence, calculate_weighted_score
from services.db_service import get_cached_verification, save_verification, init_db

load_dotenv()

def evaluate_evidence_with_gemini(claim: str, evidence_text: str):
    """
    Uses Gemini to read the scraped article and determine if it supports or 
    contradicts our target claim, and provides a semantic similarity score.
    """
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    prompt = f"""
    You are a professional fact-checker. 
    Compare the following CLAIM with the EVIDENCE text.
    
    CLAIM: {claim}
    
    EVIDENCE: {evidence_text}
    
    Analyze if the EVIDENCE supports or contradicts the CLAIM.
    Provide the output strictly as a JSON object matching this schema:
    {{
      "stance": "SUPPORT" | "CONTRADICT" | "NEUTRAL",
      "similarity": <float between 0.0 and 1.0 representing how strongly it addresses the claim>,
      "reasoning": "A 1-sentence explanation of why."
    }}
    """
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    
    return json.loads(response.text)

def main():
    parser = argparse.ArgumentParser(description="Test Verification and Consensus Engine")
    parser.add_argument(
        "--claim", 
        type=str, 
        default="The government is demolishing illegally constructed buildings along river banks as part of a campaign to clear squatter settlements.", 
        help="The specific text claim to verify"
    )
    parser.add_argument("--firecrawl", action="store_true", help="Use Firecrawl instead of DuckDuckGo/Crawl4AI")
    args = parser.parse_args()
    
    # Initialize the DB for verification table support
    init_db()

    print(f"\n[*] Target Claim: '{args.claim}'")
    
    # 0. Check SQLite Cache First
    cached_verification = get_cached_verification(args.claim)
    if cached_verification:
        print("[!] This claim has already been evaluated! Bypassing scrape and LLM.")
        print("\n[*] Cached Consensus Findings:")
        print(json.dumps(cached_verification["findings"], indent=2))
        
        final_score = cached_verification["final_score"]
        print(f"\n==========================================")
        print(f"[+] Final Weighted Truth Score (CACHED): {final_score:.2f}")
        if final_score > 0.5:
            print("[+] VERDICT: LIKELY TRUE (Supported by high-authority sources)")
        elif final_score < -0.5:
            print("[-] VERDICT: LIKELY FALSE (Contradicted by high-authority sources)")
        else:
            print("[?] VERDICT: INCONCLUSIVE / MIXED")
        print(f"==========================================\n")
        return
    
    # 1. Search the web and scrape Markdown
    evidences = search_and_scrape_evidence(args.claim, use_firecrawl=args.firecrawl)
    
    if not evidences:
        print("[-] No evidence was scraped. Cannot verify.")
        return

    findings = []
    print("\n[*] Evaluating Evidence against Claim using Gemini Consensus Check...")
    
    for ev in evidences:
        print(f"    -> Analyzing article from: {ev['domain']}")
        try:
            eval_result = evaluate_evidence_with_gemini(args.claim, ev['content'])
            
            # Combine the domain info from the scraper with the AI evaluation
            finding = {
                "domain": ev['domain'],
                "stance": eval_result.get("stance", "NEUTRAL"),
                "similarity": eval_result.get("similarity", 0.0),
                "reasoning": eval_result.get("reasoning", ""),
                "title": ev['title'],
                "url": ev['url']
            }
            findings.append(finding)
        except Exception as e:
             print(f"       [-] Evaluation failed for {ev['domain']}: {e}")

    print("\n[*] Consensus Findings:")
    print(json.dumps(findings, indent=2))
    
    # 2. Run the findings through our Authority Weighting formula
    final_score = calculate_weighted_score(findings)
    
    # 3. Cache the final result
    save_verification(args.claim, findings, final_score)
    
    print(f"\n==========================================")
    print(f"[+] Final Weighted Truth Score: {final_score:.2f}")
    if final_score > 0.5:
        print("[+] VERDICT: LIKELY TRUE (Supported by high-authority sources)")
    elif final_score < -0.5:
        print("[-] VERDICT: LIKELY FALSE (Contradicted by high-authority sources)")
    else:
        print("[?] VERDICT: INCONCLUSIVE / MIXED")
    print(f"==========================================\n")

if __name__ == "__main__":
    main()
