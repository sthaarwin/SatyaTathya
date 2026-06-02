"""
Train classical ML models with SMOTE oversampling to handle class imbalance.

Usage:
    source ../venv/bin/activate && python train_with_smote.py --save-models
"""
import argparse
import json
import os
import re
from dataclasses import asdict, dataclass

import joblib
import numpy as np
from datasets import load_dataset
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler
from sklearn.svm import LinearSVC

try:
    from imblearn.over_sampling import SMOTE
    from imblearn.pipeline import Pipeline as ImbPipeline
    HAS_SMOTE = True
except ImportError:
    HAS_SMOTE = False
    ImbPipeline = Pipeline


LABEL_MAP = {
    0: "SUPPORT", 1: "CONTRADICT", 2: "INDETERMINATE",
    "SUPPORT": "SUPPORT", "SUPPORTS": "SUPPORT", "SUPPORTED": "SUPPORT",
    "REFUTE": "CONTRADICT", "REFUTES": "CONTRADICT", "REFUTED": "CONTRADICT",
    "CONTRADICT": "CONTRADICT", "CONTRADICTS": "CONTRADICT",
    "NOT_ENOUGH_INFO": "INDETERMINATE", "NOT ENOUGH INFO": "INDETERMINATE", "NEI": "INDETERMINATE",
}

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SUPPORT_WORDS = {"confirmed", "true", "announced", "approved", "launched", "begins", "initiated", "inaugurated", "completed", "opened", "supports", "shows", "found"}
CONTRADICT_WORDS = {"denied", "false", "fake", "cancelled", "canceled", "stopped", "rejected", "debunked", "misleading", "hoax", "rumor", "untrue", "incorrect", "not", "no"}


@dataclass
class ExperimentResult:
    model: str; dataset: str; train_size: int; test_size: int; accuracy: float; macro_f1: float; weighted_f1: float


def normalize_label(label) -> str:
    if isinstance(label, int):
        return LABEL_MAP.get(label, str(label))
    return LABEL_MAP.get(str(label).strip().upper().replace("-", "_").replace(" ", "_"), str(label))


def row_to_example(row: dict) -> dict | None:
    claim, evidence, label = str(row.get("claim", "")).strip(), str(row.get("evidence", "")).strip(), normalize_label(row.get("label", ""))
    if not claim or not evidence or label not in {"SUPPORT", "CONTRADICT", "INDETERMINATE"}:
        return None
    return {"text": f"Claim: {claim}\nEvidence: {evidence}", "claim": claim, "evidence": evidence, "interaction": f"{claim} [SEP] {evidence}", "label": label}


def load_local_climate_fever(data_dir: str, split: str, max_rows: int | None) -> list[dict]:
    path = os.path.join(data_dir, f"{split}.jsonl")
    examples = []
    with open(path) as f:
        for line in f:
            example = row_to_example(json.loads(line))
            if example:
                examples.append(example)
            if max_rows and len(examples) >= max_rows:
                break
    return examples


def load_climate_fever(dataset_name: str, split: str, max_rows: int | None, data_dir: str | None) -> list[dict]:
    if data_dir:
        local_path = os.path.join(data_dir, f"{split}.jsonl")
        if os.path.exists(local_path):
            examples = load_local_climate_fever(data_dir, split, max_rows)
            if examples:
                return examples
    dataset = load_dataset(dataset_name, split=split)
    examples = []
    for row in dataset:
        example = row_to_example(row)
        if example:
            examples.append(example)
        if max_rows and len(examples) >= max_rows:
            break
    if not examples:
        raise ValueError(f"No usable rows found in {dataset_name}:{split}")
    return examples


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[\w]+", text.lower()))


def count_keywords(text: str, keywords: set[str]) -> int:
    lowered = text.lower()
    return sum(1 for k in keywords if k in lowered)


def engineered_features(rows: list[dict]) -> np.ndarray:
    features = []
    for row in rows:
        ct, et = tokenize(row["claim"]), tokenize(row["evidence"])
        overlap = len(ct & et)
        features.append([len(row["claim"]), len(row["evidence"]), len(ct), len(et), overlap, overlap / (len(ct | et) or 1), count_keywords(row["evidence"], SUPPORT_WORDS), count_keywords(row["evidence"], CONTRADICT_WORDS)])
    return np.array(features, dtype=float)


def text_values(rows): return [r["text"] for r in rows]
def claim_values(rows): return [r["claim"] for r in rows]
def evidence_values(rows): return [r["evidence"] for r in rows]
def interaction_values(rows): return [r["interaction"] for r in rows]


def make_tfidf(selector, max_features, ngram_range, analyzer="word"):
    return ("tfidf", TfidfVectorizer(max_features=max_features, ngram_range=ngram_range, min_df=2 if analyzer == "word" else 1, analyzer=analyzer, sublinear_tf=True, strip_accents="unicode"))


def build_feature_union(variant: str):
    numeric = Pipeline([("engineered", FunctionTransformer(engineered_features, validate=False)), ("scale", StandardScaler())])
    if variant == "basic":
        return FeatureUnion([("text", TfidfVectorizer(max_features=30000, ngram_range=(1, 2), min_df=2, sublinear_tf=True, strip_accents="unicode")), ("numeric", numeric)])
    return FeatureUnion([
        ("pair_word", TfidfVectorizer(max_features=50000, ngram_range=(1, 3), min_df=2, sublinear_tf=True, strip_accents="unicode")),
        ("pair_char", TfidfVectorizer(max_features=30000, ngram_range=(3, 5), min_df=1, analyzer="char_wb", sublinear_tf=True, strip_accents="unicode")),
        ("claim_word", TfidfVectorizer(max_features=15000, ngram_range=(1, 2), min_df=2, sublinear_tf=True, strip_accents="unicode")),
        ("evidence_word", TfidfVectorizer(max_features=30000, ngram_range=(1, 2), min_df=2, sublinear_tf=True, strip_accents="unicode")),
        ("numeric", numeric),
    ])


def build_model(model_name: str, use_smote: bool):
    is_rich = model_name.endswith("_rich")
    base = model_name.replace("_smote", "").replace("_rich", "")
    features = build_feature_union("rich" if is_rich else "basic")

    if base == "logreg":
        clf = LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42)
    elif base == "svm":
        clf = LinearSVC(class_weight="balanced", random_state=42, max_iter=10000, C=0.5)
    elif base == "random_forest":
        clf = RandomForestClassifier(n_estimators=300, max_depth=None, min_samples_leaf=2, class_weight="balanced", n_jobs=-1, random_state=42)
    elif base == "random_forest_tuned":
        clf = RandomForestClassifier(n_estimators=700, max_depth=40, min_samples_leaf=1, max_features="sqrt", class_weight="balanced_subsample", n_jobs=-1, random_state=42)
    else:
        raise ValueError(f"Unsupported model: {model_name}")

    steps = [("features", features)]
    if use_smote and HAS_SMOTE:
        steps.append(("smote", SMOTE(random_state=42, k_neighbors=3)))
    steps.append(("classifier", clf))
    return ImbPipeline(steps) if (use_smote and HAS_SMOTE) else Pipeline(steps)


def run_experiment(args):
    examples = load_climate_fever(args.dataset, args.split, args.max_rows, args.data_dir)
    labels = [e["label"] for e in examples]
    train_rows, test_rows, y_train, y_test = train_test_split(examples, labels, test_size=args.test_size, stratify=labels, random_state=42)
    os.makedirs(args.output_dir, exist_ok=True)
    results = []

    for model_name in args.models:
        pipe = build_model(model_name, args.use_smote)
        pipe.fit(train_rows, y_train)
        preds = pipe.predict(test_rows)

        result = ExperimentResult(model=model_name, dataset=args.dataset, train_size=len(train_rows), test_size=len(test_rows), accuracy=accuracy_score(y_test, preds), macro_f1=f1_score(y_test, preds, average="macro"), weighted_f1=f1_score(y_test, preds, average="weighted"))
        results.append(asdict(result))

        print(f"\n=== {model_name} ===")
        print(json.dumps(asdict(result), indent=2))
        print(classification_report(y_test, preds, digits=3))

        if args.save_models:
            path = os.path.join(args.output_dir, f"climate_fever_{model_name}.joblib")
            joblib.dump(pipe, path)
            print(f"Saved model to {path}")

    with open(os.path.join(args.output_dir, "climate_fever_smote_results.json"), "w") as f:
        json.dump(results, f, indent=2)


def parse_args():
    p = argparse.ArgumentParser(description="Train models with SMOTE on Climate-FEVER.")
    p.add_argument("--dataset", default="rexarski/climate_fever_fixed")
    p.add_argument("--split", default="train")
    p.add_argument("--data-dir", default=os.path.join(BACKEND_DIR, "data", "climate_fever"))
    p.add_argument("--max-rows", type=int)
    p.add_argument("--test-size", type=float, default=0.2)
    p.add_argument("--use-smote", action="store_true", default=True)
    p.add_argument("--no-smote", action="store_false", dest="use_smote")
    p.add_argument("--models", nargs="+", default=["logreg_smote", "svm_smote", "random_forest_smote"])
    p.add_argument("--output-dir", default=os.path.join(BACKEND_DIR, "models"))
    p.add_argument("--save-models", action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    run_experiment(parse_args())
