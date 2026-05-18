import os
import sys
import json
import argparse

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.verification_service import verify_claim, search_and_scrape_evidence

def test_verify_claim(test_claim, use_firecrawl=False):
    print("[*] Testing verify_claim function...")

    print(f"\n[1] Verifying claim: {test_claim[:60]}...")
    result = verify_claim(test_claim, use_firecrawl=use_firecrawl)

    print("\n[2] Neutrosophic Scores:")
    neuro = result.get("neutrosophic", {})
    print(f"    - Truth (T): {neuro.get('T', 0):.2f}")
    print(f"    - Indeterminacy (I): {neuro.get('I', 0):.2f}")
    print(f"    - Falsity (F): {neuro.get('F', 0):.2f}")

    print("\n[3] AI Evidence Findings (Stances):")
    findings = result.get('findings', [])
    if not findings:
        print("    - No stances found.")
    for f in findings:
        print(f"    -> Domain: {f.get('domain')}")
        print(f"       Stance: {f.get('stance')}")
        print(f"       Reasoning: {f.get('reasoning')}")

    print("\n[4] Past similar claims:")
    past = result.get("past_similar_claims", [])
    print(f"    - {len(past)} similar past claims found")

    print(f"\n[5] Final Weighted Truth Score: {result.get('truth_score', 0.0):.3f}")
    print(f"    - Summary: {result.get('summary', 'No summary')}")

    verdict = "TRUE" if neuro.get('T', 0) > 0.6 else ("FALSE" if neuro.get('F', 0) > 0.6 else "UNCERTAIN")
    print(f"\n========================================")
    print(f"[+] VERDICT: {verdict}")
    print("========================================\n")

def test_evidence_search(test_claim, use_firecrawl=False):
    print("\n[*] Testing evidence search alone...")

    print(f"\n[1] Searching for: {test_claim}")
    evidence = search_and_scrape_evidence(test_claim, use_firecrawl=use_firecrawl)
    print(f"[+] Found {len(evidence)} evidence items")

    if evidence:
        print("\n[2] Evidence search works!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Verification Service")
    parser.add_argument("--claim", type=str, default="The government has initiated the demolition of illegally", help="Claim to verify")
    parser.add_argument("--firecrawl", action="store_true", help="Use Firecrawl")
    parser.add_argument("--search-only", action="store_true", help="Only test the evidence search scraper")
    args = parser.parse_args()

    if args.search_only:
        test_evidence_search(args.claim, args.firecrawl)
    else:
        test_verify_claim(args.claim, args.firecrawl)