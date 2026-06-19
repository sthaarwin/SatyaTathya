import os
import sys
import json
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.db_service import init_db
from services.chroma_service import collection

API_BASE = "http://localhost:8000"

def test_api_health():
    print("[*] Testing API health endpoint...")

    try:
        response = requests.get(f"{API_BASE}/", timeout=5)
        print(f"[+] Status: {response.status_code}")
        print(f"    Response: {response.json()}")
    except Exception as e:
        print(f"[-] API not running: {e}")
        return False
    return True

def test_full_pipeline():
    print("\n[*] Testing full analyze pipeline...")

    test_url = "https://www.tiktok.com/@routineofnepalbanda/video/7641156318614654216"

    payload = {"url": test_url}

    print(f"\n[1] Sending request to /api/analyze")
    print(f"    URL: {test_url}")

    try:
        response = requests.post(f"{API_BASE}/api/analyze", json=payload, timeout=120)
        print(f"[+] Status: {response.status_code}")

        result = response.json()
        print(f"\n[2] Response structure:")
        print(f"    - status: {result.get('status')}")
        print(f"    - match_type: {result.get('match_type')}")

        data = result.get("data", {})

        print(f"\n[3] Analysis Results:")
        print(f"    - spoken_claim: {data.get('spoken_claim', 'N/A')[:60]}...")
        print(f"    - written_claim: {data.get('written_claim', 'N/A')[:60]}...")
        print(f"    - core_news_claim: {data.get('core_news_claim', 'N/A')[:80]}...")

        verification = data.get("verification", {})
        if verification:
            print(f"\n[4] Verification Results:")
            neuro = verification.get("neutrosophic_score", {})
            print(f"    - Truth (T): {neuro.get('truth', 0):.2f}")
            print(f"    - Indeterminacy (I): {neuro.get('indeterminacy', 0):.2f}")
            print(f"    - Falsity (F): {neuro.get('falsity', 0):.2f}")
            print(f"    - Evidence sources: {len(verification.get('evidence', []))}")
            print(f"    - Summary: {verification.get('summary', 'N/A')[:100]}")

            past = verification.get("past_similar_claims", [])
            print(f"    - Past similar claims: {len(past)}")
        else:
            print(f"\n[4] No verification data (cached or error)")

        return result
    except Exception as e:
        print(f"[-] API request failed: {e}")
        return None

def test_chroma_after_analysis():
    print("\n[*] Checking ChromaDB after analysis...")

    try:
        count = collection.count()
        print(f"[+] ChromaDB contains {count} claims")

        if count > 0:
            sample = collection.peek(limit=1)
            print(f"    - Sample claim: {sample['documents'][0][:80]}...")
    except Exception as e:
        print(f"[-] ChromaDB check failed: {e}")

def test_cache():
    print("\n[*] Checking SQLite cache...")

    try:
        from services.db_service import get_all_cached_analyses
        cached = get_all_cached_analyses()
        print(f"[+] SQLite cache has {len(cached)} entries")
    except Exception as e:
        print(f"[-] Cache check failed: {e}")

if __name__ == "__main__":
    print("========================================")
    print("  SatyaTathya API Integration Tests")
    print("========================================\n")

    init_db()

    if test_api_health():
        test_full_pipeline()
        test_chroma_after_analysis()
        test_cache()

    print("\n========================================")
    print("  Tests completed!")
    print("========================================\n")