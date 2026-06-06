"""
GridSearchCV hyperparameter tuning for SVM (best performer so far).

Usage:
    source ../venv/bin/activate && python tune_hyperparameters.py
"""
import argparse
import json
import os
import re
import sys

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, f1_score, classification_report
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler
from sklearn.svm import LinearSVC, SVC

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from scripts.train_climate_fever_classical import (
    load_climate_fever, engineered_features, text_values, LABEL_MAP,
    SUPPORT_WORDS, CONTRADICT_WORDS,
)


def build_tuning_pipeline(kernel: str = "linear"):
    numeric = Pipeline([
        ("engineered", FunctionTransformer(engineered_features, validate=False)),
        ("scale", StandardScaler()),
    ])
    text_pipeline = Pipeline([
        ("extract", FunctionTransformer(text_values, validate=False)),
        ("tfidf", TfidfVectorizer(max_features=30000, ngram_range=(1, 2), min_df=2, sublinear_tf=True, strip_accents="unicode")),
    ])
    features = FeatureUnion([
        ("text", text_pipeline),
        ("numeric", numeric),
    ])

    if kernel == "linear":
        clf = LinearSVC(class_weight="balanced", random_state=42, max_iter=10000)
    else:
        clf = SVC(class_weight="balanced", random_state=42, kernel=kernel, probability=True)

    return Pipeline([("features", features), ("classifier", clf)])


def tune_svm(args):
    examples = load_climate_fever(args.dataset, args.split, args.max_rows, args.data_dir)
    labels = [e["label"] for e in examples]
    train_rows, test_rows, y_train, y_test = train_test_split(examples, labels, test_size=args.test_size, stratify=labels, random_state=42)

    pipe = build_tuning_pipeline(args.kernel)

    if args.kernel == "linear":
        param_grid = {
            "classifier__C": [0.01, 0.05, 0.1, 0.3, 0.5, 0.7, 1.0, 2.0, 5.0],
            "classifier__loss": ["squared_hinge", "hinge"],
        }
    else:
        param_grid = {
            "classifier__C": [0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
            "classifier__gamma": ["scale", "auto", 0.01, 0.1],
        }

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    gs = GridSearchCV(pipe, param_grid, cv=cv, scoring="f1_macro", n_jobs=-1, verbose=2, refit=True)
    gs.fit(train_rows, y_train)

    print(f"\n=== Best Params ({args.kernel}) ===")
    print(json.dumps(gs.best_params_, indent=2))
    print(f"Best CV Macro F1: {gs.best_score_:.4f}")

    preds = gs.predict(test_rows)
    print(f"\nTest Accuracy: {accuracy_score(y_test, preds):.4f}")
    print(f"Test Macro F1: {f1_score(y_test, preds, average='macro'):.4f}")
    print(f"Test Weighted F1: {f1_score(y_test, preds, average='weighted'):.4f}")
    print(classification_report(y_test, preds, digits=3))

    if args.save_model:
        model_path = os.path.join(args.output_dir, f"climate_fever_svm_tuned_{args.kernel}.joblib")
        joblib.dump(gs.best_estimator_, model_path)
        print(f"Saved best model to {model_path}")

    result = {
        "model": f"svm_tuned_{args.kernel}",
        "dataset": args.dataset,
        "train_size": len(train_rows),
        "test_size": len(test_rows),
        "accuracy": accuracy_score(y_test, preds),
        "macro_f1": f1_score(y_test, preds, average="macro"),
        "weighted_f1": f1_score(y_test, preds, average="weighted"),
        "best_params": gs.best_params_,
        "best_cv_macro_f1": gs.best_score_,
    }

    with open(os.path.join(args.output_dir, f"svm_tuning_{args.kernel}_results.json"), "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nResults saved.")


def parse_args():
    p = argparse.ArgumentParser(description="GridSearchCV hyperparameter tuning for SVM on Climate-FEVER.")
    p.add_argument("--dataset", default="rexarski/climate_fever_fixed")
    p.add_argument("--split", default="train")
    p.add_argument("--data-dir", default=os.path.join(BACKEND_DIR, "data", "climate_fever"))
    p.add_argument("--max-rows", type=int)
    p.add_argument("--test-size", type=float, default=0.2)
    p.add_argument("--kernel", choices=["linear", "rbf"], default="linear")
    p.add_argument("--output-dir", default=os.path.join(BACKEND_DIR, "models"))
    p.add_argument("--save-model", action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.kernel == "rbf":
        print("[!] RBF kernel + probability=True is slow. Consider --max-rows to limit.")
        if not args.max_rows:
            print("[!] No --max-rows set. This will take a while.")
    tune_svm(args)
