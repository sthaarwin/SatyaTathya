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
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler
from sklearn.svm import LinearSVC


LABEL_MAP = {
    0: "SUPPORT",
    1: "CONTRADICT",
    2: "INDETERMINATE",
    "SUPPORT": "SUPPORT",
    "SUPPORTS": "SUPPORT",
    "SUPPORTED": "SUPPORT",
    "REFUTE": "CONTRADICT",
    "REFUTES": "CONTRADICT",
    "REFUTED": "CONTRADICT",
    "CONTRADICT": "CONTRADICT",
    "CONTRADICTS": "CONTRADICT",
    "NOT_ENOUGH_INFO": "INDETERMINATE",
    "NOT ENOUGH INFO": "INDETERMINATE",
    "NEI": "INDETERMINATE",
}

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SUPPORT_WORDS = {
    "confirmed",
    "true",
    "announced",
    "approved",
    "launched",
    "begins",
    "initiated",
    "inaugurated",
    "completed",
    "opened",
    "supports",
    "shows",
    "found",
}

CONTRADICT_WORDS = {
    "denied",
    "false",
    "fake",
    "cancelled",
    "canceled",
    "stopped",
    "rejected",
    "debunked",
    "misleading",
    "hoax",
    "rumor",
    "untrue",
    "incorrect",
    "not",
    "no",
}


@dataclass
class ExperimentResult:
    model: str
    dataset: str
    train_size: int
    test_size: int
    accuracy: float
    macro_f1: float
    weighted_f1: float


def normalize_label(label) -> str:
    if isinstance(label, int):
        return LABEL_MAP.get(label, str(label))
    label_text = str(label).strip().upper().replace("-", "_").replace(" ", "_")
    return LABEL_MAP.get(label_text, label_text)


def row_to_example(row: dict) -> dict | None:
    claim = str(row.get("claim", "")).strip()
    evidence = str(row.get("evidence", "")).strip()
    label = normalize_label(row.get("label", ""))
    if not claim or not evidence or label not in {"SUPPORT", "CONTRADICT", "INDETERMINATE"}:
        return None
    return {
        "text": f"Claim: {claim}\nEvidence: {evidence}",
        "claim": claim,
        "evidence": evidence,
        "interaction": f"{claim} [SEP] {evidence}",
        "label": label,
    }


def load_local_climate_fever(data_dir: str, split: str, max_rows: int | None) -> list[dict]:
    path = os.path.join(data_dir, f"{split}.jsonl")
    examples = []
    with open(path, "r") as data_file:
        for line in data_file:
            row = json.loads(line)
            example = row_to_example(row)
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
        raise ValueError(f"No usable claim/evidence rows found in {dataset_name}:{split}")
    return examples


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[\w]+", text.lower()))


def count_keywords(text: str, keywords: set[str]) -> int:
    lowered = text.lower()
    return sum(1 for keyword in keywords if keyword in lowered)


def engineered_features(rows: list[dict]) -> np.ndarray:
    features = []
    for row in rows:
        claim_tokens = tokenize(row["claim"])
        evidence_tokens = tokenize(row["evidence"])
        overlap = len(claim_tokens & evidence_tokens)
        union = len(claim_tokens | evidence_tokens) or 1
        features.append(
            [
                len(row["claim"]),
                len(row["evidence"]),
                len(claim_tokens),
                len(evidence_tokens),
                overlap,
                overlap / union,
                count_keywords(row["evidence"], SUPPORT_WORDS),
                count_keywords(row["evidence"], CONTRADICT_WORDS),
            ]
        )
    return np.array(features, dtype=float)


def text_values(rows: list[dict]) -> list[str]:
    return [row["text"] for row in rows]


def claim_values(rows: list[dict]) -> list[str]:
    return [row["claim"] for row in rows]


def evidence_values(rows: list[dict]) -> list[str]:
    return [row["evidence"] for row in rows]


def interaction_values(rows: list[dict]) -> list[str]:
    return [row["interaction"] for row in rows]


def make_tfidf(selector, max_features: int, ngram_range: tuple[int, int], analyzer: str = "word") -> Pipeline:
    min_df = 2 if analyzer == "word" else 1
    return Pipeline(
        steps=[
            ("select", FunctionTransformer(selector, validate=False)),
            (
                "tfidf",
                TfidfVectorizer(
                    max_features=max_features,
                    ngram_range=ngram_range,
                    min_df=min_df,
                    analyzer=analyzer,
                    sublinear_tf=True,
                    strip_accents="unicode",
                ),
            ),
        ]
    )


def build_feature_union(variant: str) -> FeatureUnion:
    numeric_features = Pipeline(
        steps=[
            ("engineered", FunctionTransformer(engineered_features, validate=False)),
            ("scale", StandardScaler()),
        ]
    )

    if variant == "basic":
        return FeatureUnion(
            [
                ("text", make_tfidf(text_values, max_features=30000, ngram_range=(1, 2))),
                ("numeric", numeric_features),
            ]
        )

    if variant == "rich":
        return FeatureUnion(
            [
                ("pair_word", make_tfidf(interaction_values, max_features=50000, ngram_range=(1, 3))),
                ("pair_char", make_tfidf(interaction_values, max_features=30000, ngram_range=(3, 5), analyzer="char_wb")),
                ("claim_word", make_tfidf(claim_values, max_features=15000, ngram_range=(1, 2))),
                ("evidence_word", make_tfidf(evidence_values, max_features=30000, ngram_range=(1, 2))),
                ("numeric", numeric_features),
            ]
        )

    raise ValueError(f"Unsupported feature variant: {variant}")


def build_model(model_name: str) -> Pipeline:
    features = build_feature_union("rich" if model_name.endswith("_rich") else "basic")
    base_model_name = model_name.replace("_rich", "")

    if base_model_name == "logreg":
        classifier = LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42)
    elif base_model_name == "svm":
        classifier = LinearSVC(class_weight="balanced", random_state=42, max_iter=10000, C=0.5)
    elif base_model_name == "random_forest":
        classifier = RandomForestClassifier(
            n_estimators=300,
            max_depth=None,
            min_samples_leaf=2,
            class_weight="balanced",
            n_jobs=-1,
            random_state=42,
        )
    elif base_model_name == "random_forest_tuned":
        classifier = RandomForestClassifier(
            n_estimators=700,
            max_depth=40,
            min_samples_leaf=1,
            max_features="sqrt",
            class_weight="balanced_subsample",
            n_jobs=-1,
            random_state=42,
        )
    else:
        raise ValueError(f"Unsupported model: {model_name}")

    return Pipeline([("features", features), ("classifier", classifier)])


def run_experiment(args: argparse.Namespace) -> None:
    examples = load_climate_fever(args.dataset, args.split, args.max_rows, args.data_dir)
    labels = [example["label"] for example in examples]
    train_rows, test_rows, y_train, y_test = train_test_split(
        examples,
        labels,
        test_size=args.test_size,
        stratify=labels,
        random_state=42,
    )

    os.makedirs(args.output_dir, exist_ok=True)
    results = []
    for model_name in args.models:
        model = build_model(model_name)
        model.fit(train_rows, y_train)
        predictions = model.predict(test_rows)

        result = ExperimentResult(
            model=model_name,
            dataset=args.dataset,
            train_size=len(train_rows),
            test_size=len(test_rows),
            accuracy=accuracy_score(y_test, predictions),
            macro_f1=f1_score(y_test, predictions, average="macro"),
            weighted_f1=f1_score(y_test, predictions, average="weighted"),
        )
        results.append(asdict(result))

        print(f"\n=== {model_name} ===")
        print(json.dumps(asdict(result), indent=2))
        print(classification_report(y_test, predictions, digits=3))
        print(confusion_matrix(y_test, predictions, labels=["SUPPORT", "CONTRADICT", "INDETERMINATE"]))

        if args.save_models:
            model_path = os.path.join(args.output_dir, f"climate_fever_{model_name}.joblib")
            joblib.dump(model, model_path)
            print(f"Saved model to {model_path}")

    results_path = os.path.join(args.output_dir, "climate_fever_classical_results.json")
    with open(results_path, "w") as result_file:
        json.dump(results, result_file, indent=2)
    print(f"\nSaved results to {results_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train classical ML baselines on Climate-FEVER claim/evidence stance data.")
    parser.add_argument("--dataset", default="rexarski/climate_fever_fixed")
    parser.add_argument("--split", default="train")
    parser.add_argument("--data-dir", default=os.path.join(BACKEND_DIR, "data", "climate_fever"))
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument(
        "--models",
        nargs="+",
        default=["logreg", "svm", "random_forest", "logreg_rich", "svm_rich", "random_forest_tuned_rich"],
    )
    parser.add_argument("--output-dir", default=os.path.join(BACKEND_DIR, "models"))
    parser.add_argument("--save-models", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    run_experiment(parse_args())
