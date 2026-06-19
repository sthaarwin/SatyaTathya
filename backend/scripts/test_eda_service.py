#!/usr/bin/env python
"""
Test script for EDA (Exploratory Data Analysis) results generation.
This tests the integration of the eda_service with the claim analysis pipeline.
"""

import sys
import os
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.eda_service import (
    create_and_save_eda_results,
    ensure_results_directory,
    generate_eda_results
)

# Sample test data
TEST_CLAIM_ID = "claim_test123456789abcd"

TEST_ANALYSIS_DATA = {
    "spoken_claim": "The government announced a new climate policy",
    "written_claim": "Climate Policy 2024",
    "core_news_claim": "The government has announced a new comprehensive climate policy for 2024",
    "past_similar_claims": [
        {
            "claim": "Similar claim about climate",
            "score": 0.87
        }
    ]
}

TEST_VERIFICATION_DATA = {
    "core_claim": "The government has announced a new comprehensive climate policy for 2024",
    "neutrosophic_score": {
        "truth": 0.72,
        "indeterminacy": 0.15,
        "falsity": 0.13
    },
    "truth_score": 0.72,
    "confidence": 0.85,
    "verdict": "verified",
    "findings": [
        {
            "domain": "gov.example.com",
            "title": "Government Climate Policy 2024",
            "url": "https://gov.example.com/climate-2024",
            "stance": "SUPPORT",
            "relevance": 0.95,
            "confidence": 0.92,
            "source_weight": 1.0,
            "reasoning": "Official government announcement confirming the policy",
            "evidence_quote": "We announce the comprehensive climate policy for 2024"
        },
        {
            "domain": "news.example.com",
            "title": "New Climate Policy Announced",
            "url": "https://news.example.com/climate",
            "stance": "SUPPORT",
            "relevance": 0.88,
            "confidence": 0.85,
            "source_weight": 0.8,
            "reasoning": "News coverage confirming the announcement",
            "evidence_quote": "The policy was announced today"
        },
        {
            "domain": "opposition.example.com",
            "title": "Climate Policy Criticism",
            "url": "https://opposition.example.com/critique",
            "stance": "CONTRADICT",
            "relevance": 0.65,
            "confidence": 0.72,
            "source_weight": 0.5,
            "reasoning": "Opposing viewpoint on the policy effectiveness",
            "evidence_quote": "The policy does not address core issues"
        }
    ],
    "summary": "Evidence suggests the claim is supported with high confidence"
}

TEST_METADATA = {
    "url": "https://example.com/video123",
    "spoken_claim": "The government announced a new climate policy",
    "written_claim": "Climate Policy 2024",
    "truth_score": 0.72
}

def test_eda_generation():
    """Test the EDA generation and saving functionality"""
    print("[*] Testing EDA Service...")
    print(f"[*] Claim ID: {TEST_CLAIM_ID}\n")
    
    try:
        # Test 1: Generate EDA results
        print("[1] Generating EDA results...")
        eda_summary, results_dir = generate_eda_results(
            TEST_CLAIM_ID,
            TEST_ANALYSIS_DATA,
            TEST_VERIFICATION_DATA,
            TEST_METADATA
        )
        
        print(f"[+] EDA summary generated")
        print(f"[+] Results directory: {results_dir}")
        print(f"\n[*] EDA Summary Structure:")
        print(f"    - Claim ID: {eda_summary.get('claim_id')}")
        print(f"    - Verdict: {eda_summary.get('verification_summary', {}).get('verdict')}")
        print(f"    - Truth Score: {eda_summary.get('verification_summary', {}).get('truth_score')}")
        print(f"    - Confidence: {eda_summary.get('verification_summary', {}).get('confidence')}")
        
        # Test 2: Save EDA results
        print("\n[2] Saving EDA results to files...")
        save_result = create_and_save_eda_results(
            TEST_CLAIM_ID,
            TEST_ANALYSIS_DATA,
            TEST_VERIFICATION_DATA,
            TEST_METADATA,
            save_full_data=True
        )
        
        if save_result.get("status") == "success":
            print(f"[+] EDA results saved successfully")
            print(f"\n[*] Saved files:")
            for file_type, path in save_result.get("saved_files", {}).items():
                if os.path.exists(path):
                    size = os.path.getsize(path)
                    print(f"    - {file_type}: {path} ({size} bytes)")
                else:
                    print(f"    - {file_type}: NOT FOUND")
        else:
            print(f"[-] Failed to save EDA results: {save_result.get('error')}")
            return False
        
        # Test 3: Verify saved files
        print("\n[3] Verifying saved files...")
        results_dir = save_result.get("results_directory")
        if os.path.exists(results_dir):
            files = os.listdir(results_dir)
            print(f"[+] Directory contents: {files}")
            
            # Check eda_summary.json
            summary_path = os.path.join(results_dir, "eda_summary.json")
            if os.path.exists(summary_path):
                with open(summary_path, "r") as f:
                    summary = json.load(f)
                print(f"\n[*] EDA Summary Keys: {list(summary.keys())}")
                
                # Print evidence analysis
                evidence = summary.get("evidence_analysis", {})
                print(f"\n[*] Evidence Analysis:")
                print(f"    - Total items: {evidence.get('total_evidence_items')}")
                print(f"    - Supporting: {evidence.get('count_by_stance', {}).get('supporting')}")
                print(f"    - Contradicting: {evidence.get('count_by_stance', {}).get('contradicting')}")
                print(f"    - Indeterminate: {evidence.get('count_by_stance', {}).get('indeterminate')}")
            
            print(f"\n[+] All tests passed!")
            return True
        else:
            print(f"[-] Results directory does not exist: {results_dir}")
            return False
    
    except Exception as e:
        print(f"\n[-] Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_eda_generation()
    sys.exit(0 if success else 1)
