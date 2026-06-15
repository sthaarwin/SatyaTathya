"""
Train a lightweight classifier on top of frozen NLI model embeddings.
This fine-tunes only the classification head (not the full transformer),
making it fast enough to run on CPU.

Usage:
    source ../venv/bin/activate && python train_nli_linear.py --save-models
"""
import argparse
import json
import os
import sys
import time

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from scripts.train_climate_fever_classical import load_climate_fever


def extract_embeddings(rows):
    """Extract [CLS] embeddings from the NLI model for each (claim, evidence) pair."""
    from transformers import AutoModel, AutoTokenizer
    import torch

    model_name = os.getenv("NLI_MODEL_NAME", "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli")
    print(f"[*] Loading NLI model for embedding extraction: {model_name}")

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    model.eval()

    embeddings = []
    total = len(rows)
    start = time.time()

    for i, row in enumerate(rows):
        claim = row.get("claim", "")
        evidence = row.get("evidence", "")
        inputs = tokenizer(evidence, claim, return_tensors="pt", truncation=True, max_length=256)

        with torch.no_grad():
            outputs = model(**inputs)
            # Use [CLS] token embedding (first token)
            cls_emb = outputs.last_hidden_state[0, 0, :].numpy()
            embeddings.append(cls_emb)

        if (i + 1) % 100 == 0:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed
            remaining = (total - i - 1) / rate
            print(f"  [{i + 1}/{total}] embeddings extracted [{elapsed:.0f}s elapsed, ~{remaining:.0f}s remaining]")

    return np.array(embeddings)


def main():
    parser = argparse.ArgumentParser(description="Train linear classifier on frozen NLI embeddings.")
    parser.add_argument("--dataset", default="rexarski/climate_fever_fixed")
    parser.add_argument("--split", default="train")
    parser.add_argument("--data-dir", default=os.path.join(BACKEND_DIR, "data", "climate_fever"))
    parser.add_argument("--max-rows", type=int, default=2000, help="Rows to use for embedding extraction")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--output-dir", default=os.path.join(BACKEND_DIR, "models"))
    parser.add_argument("--save-models", action="store_true")
    args = parser.parse_args()

    print(f"[*] Loading {args.max_rows} rows from {args.dataset}:{args.split}...")
    examples = load_climate_fever(args.dataset, args.split, args.max_rows, args.data_dir)
    labels = [e["label"] for e in examples]

    train_rows, test_rows, y_train, y_test = train_test_split(
        examples, labels, test_size=args.test_size, stratify=labels, random_state=42
    )

    print(f"[*] Extracting NLI embeddings for {len(train_rows)} train + {len(test_rows)} test rows...")
    X_train = extract_embeddings(train_rows)
    X_test = extract_embeddings(test_rows)

    print(f"[*] Training Logistic Regression on {X_train.shape[1]}-dim embeddings...")
    clf = LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42)
    clf.fit(X_train, y_train)

    preds = clf.predict(X_test)
    accuracy = accuracy_score(y_test, preds)
    macro_f1 = f1_score(y_test, preds, average="macro")

    print(f"\n=== nli_embedding_logreg ===")
    print(f"Accuracy: {accuracy:.4f}")
    print(f"Macro F1: {macro_f1:.4f}")
    print(classification_report(y_test, preds, digits=3))

    if args.save_models:
        path = os.path.join(args.output_dir, "nli_embedding_logreg.joblib")
        joblib.dump(clf, path)
        print(f"Saved model to {path}")

    results = [{
        "model": "nli_embedding_logreg",
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(f1_score(y_test, preds, average="weighted"), 4),
    }]
    results_path = os.path.join(args.output_dir, "nli_embedding_results.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved results to {results_path}")


if __name__ == "__main__":
    main()
