import argparse
import json
import os
import sys

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, f1_score
from sklearn.metrics.pairwise import cosine_similarity


BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = os.path.dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from scripts.train_climate_fever_classical import (
    claim_values,
    engineered_features,
    evidence_values,
    interaction_values,
    load_climate_fever,
    text_values,
)  # noqa: E402
from services import verification_service  # noqa: E402
from models.ensemble_model import get_ensemble_verifier  # noqa: E402


MODEL_FILES = {
    "logreg": "climate_fever_logreg.joblib",
    "svm": "climate_fever_svm.joblib",
    "random_forest": "climate_fever_random_forest.joblib",
    "logreg_rich": "climate_fever_logreg_rich.joblib",
    "svm_rich": "climate_fever_svm_rich.joblib",
    "random_forest_tuned_rich": "climate_fever_random_forest_tuned_rich.joblib",
    "logreg_smote": "climate_fever_logreg_smote.joblib",
    "svm_smote": "climate_fever_svm_smote.joblib",
    "random_forest_smote": "climate_fever_random_forest_smote.joblib",
}

ENSEMBLE_MODELS = ["logreg", "svm", "random_forest"]


def score_predictions(name: str, y_true: list[str], y_pred: list[str]) -> dict:
    return {
        "model": name,
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
        "macro_f1": round(f1_score(y_true, y_pred, average="macro"), 4),
        "weighted_f1": round(f1_score(y_true, y_pred, average="weighted"), 4),
    }


def benchmark_heuristic(rows: list[dict], model_dir: str | None = None) -> list[str]:
    predictions = []
    tuned_path = os.path.join(model_dir, "heuristic_tuned_params.json") if model_dir else None
    tuned = None
    if tuned_path and os.path.exists(tuned_path):
        with open(tuned_path) as f:
            data = json.load(f)
            tuned = data.get("params", {})
            print(f"[*] Using tuned heuristic params: min_relevance={tuned.get('min_relevance')}, sim_weight={tuned.get('similarity_weight')}")

    for row in rows:
        if tuned:
            import types
            orig_eval = verification_service.evaluate_evidence_embedding
            def patched_eval(claim, evidence_item, _tuned=tuned, _orig=orig_eval):
                MIN_RELEVANCE_FOR_SCORING = _tuned.get("min_relevance", 0.25)
                evidence_text = evidence_item.get("content", "")[:1500]
                evidence_lower = evidence_text.lower()
                claim_lower = claim.lower()

                nepali_claim_entities = {
                    'government', 'nepal', 'prime', 'minister', 'kathmandu', 'municipality',
                    'river', 'bank', 'demolition', 'illegal', 'building', 'road', 'highway',
                    'construction', 'project', 'development', 'budget', 'hospital', 'school',
                    'parliament', 'president', 'mayor', 'ward', 'province', 'district',
                    'police', 'army', 'court', 'commission', 'ministry', 'ministerial',
                    'election', 'vote', 'candidate', 'party', 'tax', 'price', 'fuel',
                    'electricity', 'airport', 'bridge', 'tunnel', 'landslide', 'flood',
                    'earthquake', 'border', 'citizenship', 'passport', 'visa', 'climate',
                    'warming', 'temperature', 'carbon', 'emissions', 'environment', 'science',
                    'nasa', 'ipcc', 'noaa', 'united', 'nations', 'supreme', 'central',
                    'नपल', 'नेपाल', 'सरकार', 'प्रधानमन्त्री', 'मन्त्री', 'काठमाडौं', 'पालिका',
                    'नगरपालिका', 'अदालत', 'प्रहरी', 'सेना', 'निर्वाचन', 'चुनाव',
                    'बजेट', 'सडक', 'अस्पताल', 'विद्यालय', 'विकास', 'वातावरण', 'जलवायु',
                    'परिवर्तन', 'तापक्रम'
                }

                support_words = [
                    'confirmed', 'true', 'announced', 'approved', 'launched', 'begins',
                    'construction started', 'fund approved', 'will implement', 'initiated',
                    'clearance granted', 'permission granted', 'tender awarded', 'contract signed',
                    'development', 'inaugurated', 'completed', 'opened', 'verified',
                    'officially confirmed', 'has confirmed', 'have confirmed', 'according to',
                    'reported that', 'stated that', 'said that', 'revealed that', 'found that',
                    'evidence shows', 'data shows', 'records show', 'documents show',
                    'signed', 'passed', 'implemented', 'enforced', 'published', 'released',
                    'issued', 'declared', 'decided', 'endorsed', 'ratified', 'allocated',
                    'budget allocated', 'notice issued', 'gazette published', 'started',
                    'resumed', 'operational', 'in operation', 'took effect', 'came into effect',
                    'scientific consensus', 'study found', 'research indicates', 'evidence suggests',
                    'consistent with', 'peer-reviewed', 'data supports', 'corroborates',
                    'substantiates', 'validated', 'authentic', 'legitimate', 'unanimous',
                    'पुष्टि', 'सत्य', 'स्वीकृत', 'अनुमोदन', 'घोषणा', 'सुरु', 'शुरु',
                    'कार्यान्वयन', 'निर्णय', 'जारी', 'प्रकाशित', 'सम्पन्न', 'खुला',
                    'पारित', 'बजेट विनियोजन', 'ठेक्का', 'सम्झौता', 'प्रमाणित',
                    'pushti', 'satya', 'swikrit', 'anumodan', 'ghoshana', 'suru',
                    'karyanwayan', 'nirnaya', 'jari', 'prakashit', 'parit'
                ]
                contradict_words = [
                    'denied', 'false', 'fake', 'cancelled', 'stopped', 'rejected', 'debunked',
                    'misleading', 'hoax', 'rumor', 'untrue', 'incorrect',
                    'not authorized', 'no permission', 'violated', 'scam', 'fraud',
                    'no evidence', 'not true', 'is not true', 'was not true', 'not correct',
                    'fact check', 'fact-check', 'fact checked', 'fabricated', 'baseless',
                    'unverified', 'unsubstantiated', 'doctored', 'manipulated', 'edited',
                    'old video', 'old photo', 'taken out of context', 'out of context',
                    'wrong context', 'miscaptioned', 'unrelated video', 'unrelated photo',
                    'denies', 'denied that', 'refuted', 'contradicted', 'clarified that no',
                    'there is no', 'there are no', 'has not', 'have not', 'did not',
                    'will not', 'never', 'without permission', 'unauthorized', 'invalid',
                    'illegal', 'arrested for spreading', 'police denied', 'officials denied',
                    'misinformation', 'scientific myth', 'lack of empirical evidence',
                    'discredited', 'inconsistent with', 'unfounded', 'refuted by',
                    'खण्डन', 'गलत', 'झुटो', 'झूठो', 'नक्कली', 'भ्रामक', 'अफवाह',
                    'असत्य', 'होइन', 'छैन', 'गरेको छैन', 'भएको छैन', 'स्वीकार गरेन',
                    'अस्वीकार', 'रद्द', 'फर्जी', 'ठगी', 'प्रमाण छैन', 'गलत सूचना',
                    'khandan', 'galat', 'jhuto', 'nakkali', 'bhramak', 'afwah',
                    'asatya', 'hoina', 'chaina', 'gareko chaina', 'bhayeko chaina',
                    'aswikar', 'radda', 'farji', 'thagi'
                ]
                uncertainty_words = [
                    'alleged', 'allegedly', 'claim', 'claims', 'claimed', 'reportedly',
                    'unconfirmed', 'unclear', 'unknown', 'may', 'might', 'could',
                    'possibly', 'likely', 'rumoured', 'rumored', 'sources say',
                    'not independently verified', 'investigation ongoing', 'under investigation',
                    'awaiting confirmation', 'unproven', 'specious', 'fallacious',
                    'अस्पष्ट', 'अनिश्चित', 'दाबी', 'भनिएको', 'सम्भावना', 'हुन सक्छ',
                    'पुष्टि हुन बाँकी', 'अनुसन्धान जारी',
                    'aspashta', 'anischit', 'dabi', 'bhanieko', 'huna sakcha'
                ]

                claim_keywords = set(re.findall(r"[\w\u0900-\u097F]+", claim_lower))
                claim_entities = claim_keywords & nepali_claim_entities
                evidence_tokens = set(re.findall(r"[\w\u0900-\u097F]+", evidence_lower))
                evidence_entities = evidence_tokens & nepali_claim_entities
                entity_overlap = len(claim_entities & evidence_entities)

                support_count = sum(1 for w in support_words if w in evidence_lower)
                contradict_count = sum(1 for w in contradict_words if w in evidence_lower)
                uncertainty_count = sum(1 for w in uncertainty_words if w in evidence_lower)

                claim_terms = [t for t in claim_keywords if len(t) > 2 and t not in verification_service.STOP_WORDS]
                term_overlap = len(set(claim_terms) & evidence_tokens)
                similarity = verification_service.compute_similarity(claim[:300], evidence_text[:700]) if evidence_text.strip() else 0.0

                sim_w = _tuned.get("similarity_weight", 0.65)
                term_w = _tuned.get("term_weight", 0.25)
                ent_w = _tuned.get("entity_weight", 0.10)
                relevance = max(0.0, min(1.0, (similarity * sim_w) + (min(term_overlap, 6) / 6 * term_w) + (min(entity_overlap, 3) / 3 * ent_w)))

                if relevance < MIN_RELEVANCE_FOR_SCORING:
                    stance = "INDETERMINATE"
                elif uncertainty_count > max(support_count, contradict_count) and support_count == 0 and contradict_count == 0:
                    stance = "INDETERMINATE"
                elif entity_overlap >= 2:
                    if support_count > contradict_count:
                        stance = "SUPPORT"
                    elif contradict_count > support_count:
                        stance = "CONTRADICT"
                    else:
                        stance = "INDETERMINATE"
                elif support_count > 0 and contradict_count == 0:
                    stance = "SUPPORT"
                elif contradict_count > 0 and support_count == 0:
                    stance = "CONTRADICT"
                elif support_count > contradict_count:
                    stance = "SUPPORT"
                elif contradict_count > support_count:
                    stance = "CONTRADICT"
                else:
                    stance = "INDETERMINATE"

                return {"stance": stance, "relevance": round(relevance, 3)}

            result = patched_eval(row["claim"], {"content": row["evidence"]})
        else:
            result = verification_service.evaluate_evidence_embedding(row["claim"], {"content": row["evidence"]})
        predictions.append(verification_service.normalize_stance(result.get("stance")))
    return predictions


def lexical_similarity(text1: str, text2: str) -> float:
    """
    Compute a simple lexical similarity score using TF-IDF (1-2 ngrams).
    This serves as a fast, offline fallback that doesn't require downloading
    or loading heavy embedding models.
    """
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
    matrix = vectorizer.fit_transform([text1, text2])
    return float(cosine_similarity(matrix[0], matrix[1])[0][0])


def benchmark_hybrid(rows: list[dict], svm_model) -> list[str]:
    """
    Hybrid model: Uses SVM as the primary engine but falls back to Gemini 2.0 
    only when the heuristic indicates high uncertainty or there is a mismatch.
    This saves API costs while pushing accuracy towards LLM levels.
    """
    predictions = []
    svm_preds = svm_model.predict(rows)
    
    for i, row in enumerate(rows):
        # 1. Start with the cheap local heuristic
        h_result = verification_service.evaluate_evidence_embedding(row["claim"], {"content": row["evidence"]})
        h_stance = verification_service.normalize_stance(h_result.get("stance"))
        svm_stance = svm_preds[i]
        
        # 2. Decision Logic for Gemini Escalation:
        # If Heuristic and SVM disagree on ANY stance, escalate to Gemini.
        should_escalate = (h_stance != svm_stance)
        
        if should_escalate:
            print(f"[*] Escalating row {i} to Gemini (H: {h_stance}, SVM: {svm_stance})")
            # Escalating to Gemini 2.0 Flash
            g_result = verification_service.classify_evidence_with_gemini(
                row["claim"], 
                {"content": row["evidence"]}, 
                h_result
            )
            predictions.append(verification_service.normalize_stance(g_result.get("stance")))
        else:
            # Trust the consensus
            predictions.append(svm_stance)
            
    return predictions


def benchmark_gemini(rows: list[dict]) -> list[str]:
    """Pure Gemini 2.0 Flash model for comparison."""
    predictions = []
    print(f"[*] Running pure Gemini benchmark on {len(rows)} rows...")
    for i, row in enumerate(rows):
        # We still need the local relevance for the context
        h_result = verification_service.evaluate_evidence_embedding(row["claim"], {"content": row["evidence"]})
        g_result = verification_service.classify_evidence_with_gemini(
            row["claim"], 
            {"content": row["evidence"]}, 
            h_result
        )
        predictions.append(verification_service.normalize_stance(g_result.get("stance")))
    return predictions


def benchmark_voting_ensemble(rows: list[dict], model_dir: str) -> list[str] | None:
    """Hard-voting ensemble of pre-trained logreg, svm, and random_forest.
    
    Uses majority vote without refitting on test data.
    """
    estimators = []
    for name in ENSEMBLE_MODELS:
        path = os.path.join(model_dir, MODEL_FILES[name])
        if not os.path.exists(path):
            return None
        model = joblib.load(path)
        estimators.append((name, model))

    all_preds = []
    for _, model in estimators:
        preds = model.predict(rows)
        all_preds.append(preds)

    ensemble_preds = []
    for i in range(len(rows)):
        votes = [preds[i] for preds in all_preds]
        from collections import Counter
        majority = Counter(votes).most_common(1)[0][0]
        ensemble_preds.append(majority)
    return ensemble_preds


def benchmark_ensemble_verifier(rows: list[dict]) -> list[str] | None:
    """Benchmark the new EnsembleVerifier class with feature extraction.
    
    Uses Logistic Regression, SVM, and Random Forest with ensemble voting
    on extracted text features.
    """
    ensemble = get_ensemble_verifier()
    
    if not ensemble.is_available():
        print("[!] Warning: EnsembleVerifier models not available")
        return None
    
    predictions = []
    print(f"[*] Running EnsembleVerifier benchmark on {len(rows)} rows...")
    
    for i, row in enumerate(rows):
        claim = row.get("claim", "")
        evidence = row.get("evidence", "")
        
        try:
            stance, confidence, model_used = ensemble.predict_stance(claim, evidence)
            predictions.append(stance)
            
            if (i + 1) % 50 == 0:
                print(f"  [{i + 1}/{len(rows)}] Processed using: {model_used} (conf: {confidence:.3f})")
        except Exception as e:
            print(f"[!] Error on row {i}: {e}")
            predictions.append("INDETERMINATE")
    
    return predictions


def benchmark_models(rows: list[dict], model_dir: str, use_gemini: bool = False) -> list[dict]:
    y_true = [row["label"] for row in rows]
    results = [score_predictions("heuristic", y_true, benchmark_heuristic(rows, model_dir))]
    svm_model = None

    for model_name, filename in MODEL_FILES.items():
        model_path = os.path.join(model_dir, filename)
        if not os.path.exists(model_path):
            continue
        model = joblib.load(model_path)
        if model_name == "svm":
            svm_model = model
            
        predictions = model.predict(rows)
        results.append(score_predictions(model_name, y_true, predictions))

    ensemble_preds = benchmark_voting_ensemble(rows, model_dir)
    if ensemble_preds is not None:
        results.append(score_predictions("voting_ensemble", y_true, ensemble_preds))

    # Benchmark the new EnsembleVerifier class
    ensemble_verifier_preds = benchmark_ensemble_verifier(rows)
    if ensemble_verifier_preds is not None:
        results.append(score_predictions("ensemble_verifier", y_true, ensemble_verifier_preds))

    if use_gemini:
        # 1. Hybrid Model
        if svm_model:
            print("[*] Running Hybrid Heuristic + SVM + Gemini benchmark...")
            hybrid_preds = benchmark_hybrid(rows, svm_model)
            results.append(score_predictions("hybrid_svm_gemini", y_true, hybrid_preds))
        
        # 2. Pure Gemini Model
        gemini_preds = benchmark_gemini(rows)
        results.append(score_predictions("gemini_pure", y_true, gemini_preds))

    return sorted(results, key=lambda result: result["macro_f1"], reverse=True)


def plot_results(metrics: list[dict], output_path: str) -> None:
    """Visualize benchmark results using a bar chart."""
    import matplotlib.pyplot as plt
    import pandas as pd

    plt.switch_backend("Agg")

    df = pd.DataFrame(metrics)
    models = [m.replace("_", " ").title() for m in df["model"].tolist()]
    accuracies = df["accuracy"].tolist()
    macro_f1s = df["macro_f1"].tolist()
    weighted_f1s = df["weighted_f1"].tolist()

    fig_width = max(10, len(models) * 1.5)
    plt.figure(figsize=(fig_width, 6))

    x = range(len(models))
    width = 0.25

    plt.bar(x, accuracies, width, label="Accuracy", color="#3498db", alpha=0.8)
    plt.bar([p + width for p in x], macro_f1s, width, label="Macro F1", color="#2ecc71", alpha=0.8)
    plt.bar([p + width * 2 for p in x], weighted_f1s, width, label="Weighted F1", color="#e67e22", alpha=0.8)

    plt.xlabel("Model")
    plt.ylabel("Score")
    plt.title("Model Comparison: Accuracy vs F1 Scores")
    plt.xticks([p + width for p in x], models, rotation=15, ha="right", fontsize=9)
    plt.ylim(0, 1.1)
    plt.legend(loc="lower right", fontsize=9)
    plt.grid(axis="y", linestyle="--", alpha=0.7)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    print(f"Comparison plot saved to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark heuristic and trained models on Climate-FEVER test rows.")
    parser.add_argument("--dataset", default="rexarski/climate_fever_fixed")
    parser.add_argument("--split", default="test")
    parser.add_argument("--data-dir", default=os.path.join(BACKEND_DIR, "data", "climate_fever"))
    parser.add_argument("--model-dir", default=os.path.join(BACKEND_DIR, "models"))
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--similarity", choices=["lexical", "embedding"], default="lexical")
    parser.add_argument("--use-gemini", action="store_true", help="Enable hybrid LLM verification for uncertain cases (slower, cost involved)")
    parser.add_argument("--output", default=os.path.join(BACKEND_DIR, "models", "method_comparison_results.json"))
    parser.add_argument("--plot", default=os.path.join(BACKEND_DIR, "models", "method_comparison_plot.png"))
    args = parser.parse_args()

    if args.use_gemini and args.max_rows and args.max_rows > 50:
        print("[!] Warning: Running Gemini benchmarks on many rows may hit API quotas. Consider reducing --max-rows.")

    # If lexical similarity is selected, we override the default embedding-based 
    # similarity in verification_service to allow fully offline benchmarking.
    if args.similarity == "lexical":
        verification_service.compute_similarity = lexical_similarity

    rows = load_climate_fever(args.dataset, args.split, args.max_rows, args.data_dir)
    results = {
        "dataset": args.dataset,
        "split": args.split,
        "test_size": len(rows),
        "metrics": benchmark_models(rows, args.model_dir, use_gemini=args.use_gemini),
    }

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as output_file:
        json.dump(results, output_file, indent=2)

    print(json.dumps(results, indent=2))
    print(f"Saved comparison results to {args.output}")

    if args.plot:
        plot_results(results["metrics"], args.plot)


if __name__ == "__main__":
    main()
