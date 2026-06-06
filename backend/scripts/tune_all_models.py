"""
Hyperparameter tuning for all classical ML models (LogReg, SVM, RandomForest).

Usage:
    source ../venv/bin/activate && python tune_all_models.py --save-models
"""
import argparse
import json
import os
import sys
import logging
from datetime import datetime

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, classification_report, precision_score, recall_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler
from sklearn.svm import LinearSVC, SVC

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from scripts.train_climate_fever_classical import (
    load_climate_fever, engineered_features, text_values, LABEL_MAP, row_to_example,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def build_feature_pipeline():
    """Build feature extraction pipeline (text + engineered features)."""
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
    return features


def tune_logistic_regression(train_data, y_train, test_data, y_test, output_dir, cv):
    """Tune LogisticRegression hyperparameters."""
    logger.info("=" * 60)
    logger.info("TUNING LOGISTIC REGRESSION")
    logger.info("=" * 60)
    
    features = build_feature_pipeline()
    clf = LogisticRegression(class_weight="balanced", random_state=42, max_iter=1000, solver="lbfgs")
    pipe = Pipeline([("features", features), ("classifier", clf)])
    
    param_grid = {
        "classifier__C": [0.001, 0.01, 0.1, 0.5, 1.0, 5.0, 10.0],
    }
    
    gs = GridSearchCV(pipe, param_grid, cv=cv, scoring="f1_macro", n_jobs=-1, verbose=1, refit=True)
    gs.fit(train_data, y_train)
    
    preds = gs.predict(test_data)
    results = evaluate_model("LogisticRegression", preds, y_test, gs.best_params_, gs.best_score_)
    
    return gs.best_estimator_, results


def tune_svm_linear(train_data, y_train, test_data, y_test, output_dir, cv):
    """Tune Linear SVM hyperparameters."""
    logger.info("=" * 60)
    logger.info("TUNING LINEAR SVM")
    logger.info("=" * 60)
    
    features = build_feature_pipeline()
    clf = LinearSVC(class_weight="balanced", random_state=42, max_iter=10000)
    pipe = Pipeline([("features", features), ("classifier", clf)])
    
    param_grid = {
        "classifier__C": [0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
        "classifier__loss": ["squared_hinge", "hinge"],
    }
    
    gs = GridSearchCV(pipe, param_grid, cv=cv, scoring="f1_macro", n_jobs=-1, verbose=2, refit=True)
    gs.fit(train_data, y_train)
    
    preds = gs.predict(test_data)
    results = evaluate_model("SVM (Linear)", preds, y_test, gs.best_params_, gs.best_score_)
    
    return gs.best_estimator_, results


def tune_svm_rbf(train_data, y_train, test_data, y_test, output_dir, cv):
    """Tune RBF SVM hyperparameters."""
    logger.info("=" * 60)
    logger.info("TUNING RBF SVM")
    logger.info("=" * 60)
    
    features = build_feature_pipeline()
    clf = SVC(class_weight="balanced", random_state=42, kernel="rbf", probability=True)
    pipe = Pipeline([("features", features), ("classifier", clf)])
    
    param_grid = {
        "classifier__C": [0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
        "classifier__gamma": ["scale", "auto", 0.001, 0.01, 0.1],
    }
    
    gs = GridSearchCV(pipe, param_grid, cv=cv, scoring="f1_macro", n_jobs=-1, verbose=2, refit=True)
    gs.fit(train_data, y_train)
    
    preds = gs.predict(test_data)
    results = evaluate_model("SVM (RBF)", preds, y_test, gs.best_params_, gs.best_score_)
    
    return gs.best_estimator_, results


def tune_random_forest(train_data, y_train, test_data, y_test, output_dir, cv):
    """Tune RandomForest hyperparameters."""
    logger.info("=" * 60)
    logger.info("TUNING RANDOM FOREST")
    logger.info("=" * 60)
    
    features = build_feature_pipeline()
    clf = RandomForestClassifier(class_weight="balanced", random_state=42, n_jobs=-1)
    pipe = Pipeline([("features", features), ("classifier", clf)])
    
    param_grid = {
        "classifier__n_estimators": [50, 100, 200, 300],
        "classifier__max_depth": [10, 20, 30, None],
        "classifier__min_samples_split": [2, 5, 10],
        "classifier__min_samples_leaf": [1, 2, 4],
    }
    
    gs = GridSearchCV(pipe, param_grid, cv=cv, scoring="f1_macro", n_jobs=-1, verbose=2, refit=True)
    gs.fit(train_data, y_train)
    
    preds = gs.predict(test_data)
    results = evaluate_model("RandomForest", preds, y_test, gs.best_params_, gs.best_score_)
    
    return gs.best_estimator_, results


def evaluate_model(model_name, preds, y_test, best_params, best_cv_score):
    """Evaluate model and return results dictionary."""
    accuracy = accuracy_score(y_test, preds)
    macro_f1 = f1_score(y_test, preds, average='macro')
    weighted_f1 = f1_score(y_test, preds, average='weighted')
    precision = precision_score(y_test, preds, average='macro')
    recall = recall_score(y_test, preds, average='macro')
    
    logger.info(f"\n{model_name} Results:")
    logger.info(f"  Accuracy:       {accuracy:.4f}")
    logger.info(f"  Macro F1:       {macro_f1:.4f}")
    logger.info(f"  Weighted F1:    {weighted_f1:.4f}")
    logger.info(f"  Precision:      {precision:.4f}")
    logger.info(f"  Recall:         {recall:.4f}")
    logger.info(f"  Best CV Macro F1: {best_cv_score:.4f}")
    logger.info(f"  Best Params:    {best_params}")
    
    return {
        "model": model_name,
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "precision": precision,
        "recall": recall,
        "best_cv_macro_f1": best_cv_score,
        "best_params": best_params,
    }


def load_local_data(data_dir: str, split: str, max_rows: int | None) -> list[dict]:
    """Load from local JSONL files."""
    import json
    path = os.path.join(data_dir, split, f"{split}.jsonl")
    
    # Try different path patterns
    if not os.path.exists(path):
        path = os.path.join(data_dir, f"{split}.jsonl")
    
    if not os.path.exists(path):
        raise FileNotFoundError(f"Cannot find {split}.jsonl in {data_dir}")
    
    examples = []
    with open(path, "r") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            examples.append(row)
            if max_rows and len(examples) >= max_rows:
                break
    return examples


def main(args):
    # Load data from local files
    logger.info("Loading Climate FEVER dataset from local files...")
    import json
    
    # Try multiple paths
    local_path = os.path.join(args.data_dir, f"{args.split}.jsonl")
    if not os.path.exists(local_path):
        local_path = os.path.join(args.data_dir, args.dataset, f"{args.split}.jsonl")
    
    if not os.path.exists(local_path):
        logger.error(f"Cannot find {args.split}.jsonl in {args.data_dir}")
        raise FileNotFoundError(f"Dataset file not found at {local_path}")
    
    logger.info(f"Loading from {local_path}")
    raw_examples = []
    with open(local_path, "r") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            raw_examples.append(row)
            if args.max_rows and len(raw_examples) >= args.max_rows:
                break
    
    # Convert raw examples to processed format
    examples = []
    for raw_ex in raw_examples:
        ex = row_to_example(raw_ex)
        if ex:
            examples.append(ex)
    
    logger.info(f"Loaded {len(examples)} examples")
    labels = [e["label"] for e in examples]
    
    train_data, test_data, y_train, y_test = train_test_split(
        examples, labels, test_size=args.test_size, stratify=labels, random_state=42
    )
    
    logger.info(f"Dataset loaded: {len(train_data)} train, {len(test_data)} test")
    logger.info(f"Label distribution: {set(labels)}")
    
    # Setup cross-validation
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    
    # Tune all models
    all_results = {
        "timestamp": datetime.now().isoformat(),
        "dataset": args.dataset,
        "train_size": len(train_data),
        "test_size": len(test_data),
        "models": {}
    }
    
    # LogisticRegression
    lr_model, lr_results = tune_logistic_regression(train_data, y_train, test_data, y_test, args.output_dir, cv)
    all_results["models"]["LogisticRegression"] = lr_results
    if args.save_models:
        lr_path = os.path.join(args.output_dir, "climate_fever_logreg_tuned.joblib")
        joblib.dump(lr_model, lr_path)
        logger.info(f"Saved LogisticRegression to {lr_path}")
    
    # Linear SVM
    svm_linear_model, svm_linear_results = tune_svm_linear(train_data, y_train, test_data, y_test, args.output_dir, cv)
    all_results["models"]["SVM_Linear"] = svm_linear_results
    if args.save_models:
        svm_linear_path = os.path.join(args.output_dir, "climate_fever_svm_linear_tuned.joblib")
        joblib.dump(svm_linear_model, svm_linear_path)
        logger.info(f"Saved Linear SVM to {svm_linear_path}")
    
    # RBF SVM
    svm_rbf_model, svm_rbf_results = tune_svm_rbf(train_data, y_train, test_data, y_test, args.output_dir, cv)
    all_results["models"]["SVM_RBF"] = svm_rbf_results
    if args.save_models:
        svm_rbf_path = os.path.join(args.output_dir, "climate_fever_svm_rbf_tuned.joblib")
        joblib.dump(svm_rbf_model, svm_rbf_path)
        logger.info(f"Saved RBF SVM to {svm_rbf_path}")
    
    # RandomForest
    rf_model, rf_results = tune_random_forest(train_data, y_train, test_data, y_test, args.output_dir, cv)
    all_results["models"]["RandomForest"] = rf_results
    if args.save_models:
        rf_path = os.path.join(args.output_dir, "climate_fever_random_forest_tuned.joblib")
        joblib.dump(rf_model, rf_path)
        logger.info(f"Saved RandomForest to {rf_path}")
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TUNING SUMMARY")
    logger.info("=" * 60)
    
    for model_name, results in all_results["models"].items():
        logger.info(f"\n{model_name}:")
        logger.info(f"  Accuracy: {results['accuracy']:.4f}")
        logger.info(f"  Macro F1: {results['macro_f1']:.4f}")
        logger.info(f"  Weighted F1: {results['weighted_f1']:.4f}")
    
    # Find best model
    best_model = max(all_results["models"].items(), key=lambda x: x[1]["accuracy"])
    logger.info(f"\n🏆 BEST MODEL: {best_model[0]} with {best_model[1]['accuracy']:.4f} accuracy")
    
    # Save results
    results_path = os.path.join(args.output_dir, "tuning_all_models_results.json")
    with open(results_path, "w") as f:
        json.dump(all_results, f, indent=2)
    logger.info(f"\nResults saved to {results_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tune all classical ML models")
    parser.add_argument("--dataset", default="climate_fever", help="Dataset name")
    parser.add_argument("--split", default="test", help="Data split (train/valid/test)")
    parser.add_argument("--data-dir", default="data", help="Data directory")
    parser.add_argument("--max-rows", type=int, default=None, help="Max rows to load")
    parser.add_argument("--test-size", type=float, default=0.2, help="Test split size")
    parser.add_argument("--output-dir", default="models", help="Output directory for models")
    parser.add_argument("--save-models", action="store_true", help="Save tuned models")
    
    args = parser.parse_args()
    
    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)
    
    main(args)
