"""
Benchmark the NLI model against the Climate-FEVER test set.
Compares with existing heuristic and ensemble results.

Usage:
    source ../venv/bin/activate && python benchmark_nli.py --max-rows 200
"""
import argparse
import json
import os
import sys
import time

import numpy as np
from sklearn.metrics import accuracy_score, f1_score, classification_report

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from scripts.train_climate_fever_classical import load_climate_fever
from models.ensemble_model import get_ensemble_verifier


def benchmark_nli(rows: list[dict]) -> list[str]:
    from services.nli_service import evaluate_with_nli, nli_available
    if not nli_available():
        print("[!] NLI model not available. Aborting.")
        return []

    predictions = []
    total = len(rows)
    print(f"[*] Running NLI benchmark on {total} rows...")

    start = time.time()
    for i, row in enumerate(rows):
        result = evaluate_with_nli(row["claim"], {"content": row["evidence"]})
        predictions.append(result["stance"])
        if (i + 1) % 20 == 0:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed
            remaining = (total - i - 1) / rate
            print(f"  [{i + 1}/{total}] {result['stance']} (conf={result['confidence']:.3f}) "
                  f"[{elapsed:.0f}s elapsed, ~{remaining:.0f}s remaining]")

    return predictions


def benchmark_ensemble_verifier(rows: list[dict]) -> list[str]:
    ensemble = get_ensemble_verifier()
    if not ensemble.is_available():
        print("[!] EnsembleVerifier not available")
        return []
    predictions = []
    for row in rows:
        stance, _, _ = ensemble.predict_stance(row["claim"], row["evidence"])
        predictions.append(stance)
    return predictions


def main():
    parser = argparse.ArgumentParser(description="Benchmark NLI model on Climate-FEVER.")
    parser.add_argument("--dataset", default="rexarski/climate_fever_fixed")
    parser.add_argument("--split", default="test")
    parser.add_argument("--data-dir", default=os.path.join(BACKEND_DIR, "data", "climate_fever"))
    parser.add_argument("--max-rows", type=int, default=200)
    args = parser.parse_args()

    rows = load_climate_fever(args.dataset, args.split, args.max_rows, args.data_dir)
    y_true = [row["label"] for row in rows]
    print(f"Loaded {len(rows)} rows from {args.dataset}:{args.split}")

    results = []

    # Heuristic baseline
    from services import verification_service
    # Use lexical similarity for speed (no embedding download needed)
    from scripts.benchmark_method_comparison import lexical_similarity
    orig_sim = verification_service.compute_similarity
    verification_service.compute_similarity = lexical_similarity

    print("[*] Running heuristic baseline...")
    heuristic_preds = []
    for row in rows:
        r = verification_service.evaluate_evidence_embedding(row["claim"], {"content": row["evidence"]})
        heuristic_preds.append(verification_service.normalize_stance(r.get("stance")))
    verification_service.compute_similarity = orig_sim

    results.append({
        "model": "heuristic",
        "accuracy": round(accuracy_score(y_true, heuristic_preds), 4),
        "macro_f1": round(f1_score(y_true, heuristic_preds, average="macro"), 4),
        "weighted_f1": round(f1_score(y_true, heuristic_preds, average="weighted"), 4),
    })
    print(f"  Heuristic: accuracy={results[-1]['accuracy']:.4f}, macro_f1={results[-1]['macro_f1']:.4f}")

    # EnsembleVerifier
    print("[*] Running EnsembleVerifier...")
    ensemble_preds = benchmark_ensemble_verifier(rows)
    if ensemble_preds:
        results.append({
            "model": "ensemble_verifier",
            "accuracy": round(accuracy_score(y_true, ensemble_preds), 4),
            "macro_f1": round(f1_score(y_true, ensemble_preds, average="macro"), 4),
            "weighted_f1": round(f1_score(y_true, ensemble_preds, average="weighted"), 4),
        })
        print(f"  EnsembleVerifier: accuracy={results[-1]['accuracy']:.4f}, macro_f1={results[-1]['macro_f1']:.4f}")

    # NLI
    print("[*] Running NLI...")
    nli_preds = benchmark_nli(rows)
    if nli_preds:
        results.append({
            "model": "nli_deberta_v3",
            "accuracy": round(accuracy_score(y_true, nli_preds), 4),
            "macro_f1": round(f1_score(y_true, nli_preds, average="macro"), 4),
            "weighted_f1": round(f1_score(y_true, nli_preds, average="weighted"), 4),
        })
        print(f"\nNLI Results:")
        print(classification_report(y_true, nli_preds, digits=3))

    results.sort(key=lambda r: r["macro_f1"], reverse=True)

    output = {"dataset": args.dataset, "split": args.split, "test_size": len(rows), "metrics": results}
    print("\n" + "=" * 60)
    print(json.dumps(output, indent=2))

    output_path = os.path.join(BACKEND_DIR, "models", "nli_benchmark_results.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {output_path}")


if __name__ == "__main__":
    main()
