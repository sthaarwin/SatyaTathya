import os
import sys
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.chroma_service import add_claim_to_db, search_similar_claims, collection

def test_chroma_operations():
    print("[*] Testing ChromaDB operations...")

    test_id = "test_claim_001"
    test_claim = "Government announces new infrastructure development plan for Kathmandu valley"
    test_metadata = {
        "url": "https://example.com/news/123",
        "spoken_claim": "Government building new roads",
        "written_claim": "Infrastructure Development Plan 2024"
    }

    print("\n[1] Adding claim to ChromaDB...")
    add_claim_to_db(test_id, test_claim, test_metadata)
    print("[+] Claim added successfully")

    print("\n[2] Checking collection count...")
    count = collection.count()
    print(f"[+] Total items in ChromaDB: {count}")

    print("\n[3] Searching for similar claim...")
    results = search_similar_claims("infrastructure development plan Kathmandu", threshold=2.0)
    print(f"[+] Found {len(results)} similar claims")
    if results:
        print(f"    - Top match: {results[0]['document'][:80]}...")
        print(f"    - Distance: {results[0]['distance']:.4f}")

    print("\n[4] Testing search with unrelated query...")
    results = search_similar_claims("celebrity gossip movie star", threshold=1.5)
    print(f"[+] Found {len(results)} similar claims (should be 0)")

    print("\n[5] Peeking at all stored data...")
    all_data = collection.peek()
    print(f"[+] Keys available: {list(all_data.keys())}")
    if all_data.get('ids'):
        print(f"[+] Sample ID: {all_data['ids'][0]}")

    print("\n[6] Cleaning up test data...")
    collection.delete(ids=[test_id])
    print("[+] Test data removed")

    print("\n========================================")
    print("[+] ChromaDB tests completed!")
    print("========================================\n")

if __name__ == "__main__":
    test_chroma_operations()