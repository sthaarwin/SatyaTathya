"""
Tune heuristic thresholds against the validation set to maximize macro F1.

Optimizes: MIN_RELEVANCE_FOR_SCORING, similarity_weight, term_overlap_weight,
entity_weight, support/contradict confidence values.

Usage:
    source ../venv/bin/activate && python tune_heuristic.py
"""
import argparse
import itertools
import json
import os
import re
import sys
from copy import deepcopy

import numpy as np
from sklearn.metrics import accuracy_score, f1_score

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from services import verification_service
from services.chroma_service import compute_similarity
from scripts.train_climate_fever_classical import load_climate_fever


# Grid search ranges
RELEVANCE_THRESHOLDS = [0.15, 0.20, 0.25, 0.30, 0.35]
SIM_WEIGHTS = [0.55, 0.60, 0.65, 0.70, 0.75]
TERM_WEIGHTS = [0.15, 0.20, 0.25, 0.30, 0.35]
ENTITY_WEIGHTS = [0.05, 0.10, 0.15, 0.20]
CONFIDENCE_MAP = {
    "low": [0.30, 0.35, 0.40],
    "medium": [0.40, 0.45, 0.50],
    "high": [0.50, 0.55, 0.60],
}


def heuristic_predict(claim: str, evidence: str, params: dict) -> str:
    """Replicate evaluate_evidence_embedding with custom parameters."""
    evidence_text = evidence[:1500]
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

    def count_indicators(text, indicators):
        return sum(1 for ind in indicators if ind in text)

    claim_keywords = set(re.findall(r"[\w\u0900-\u097F]+", claim_lower))
    claim_entities = claim_keywords & nepali_claim_entities
    evidence_tokens = set(re.findall(r"[\w\u0900-\u097F]+", evidence_lower))
    evidence_entities = evidence_tokens & nepali_claim_entities
    entity_overlap = len(claim_entities & evidence_entities)

    support_count = count_indicators(evidence_lower, support_words)
    contradict_count = count_indicators(evidence_lower, contradict_words)
    uncertainty_count = count_indicators(evidence_lower, uncertainty_words)

    claim_terms = [t for t in claim_keywords if len(t) > 2 and t not in verification_service.STOP_WORDS]
    term_overlap = len(set(claim_terms) & evidence_tokens)
    similarity = compute_similarity(claim[:300], evidence_text[:700]) if evidence_text.strip() else 0.0

    sim_w = params["similarity_weight"]
    term_w = params["term_weight"]
    ent_w = params["entity_weight"]
    relevance = max(0.0, min(1.0, (similarity * sim_w) + (min(term_overlap, 6) / 6 * term_w) + (min(entity_overlap, 3) / 3 * ent_w)))

    min_rel = params["min_relevance"]
    conf_low = params["conf_low"]
    conf_med = params["conf_med"]
    conf_high = params["conf_high"]

    if relevance < min_rel:
        return "INDETERMINATE"
    if uncertainty_count > max(support_count, contradict_count) and support_count == 0 and contradict_count == 0:
        return "INDETERMINATE"
    if entity_overlap >= 2:
        if support_count > contradict_count:
            return "SUPPORT"
        elif contradict_count > support_count:
            return "CONTRADICT"
        else:
            return "INDETERMINATE"
    if support_count > 0 and contradict_count == 0:
        return "SUPPORT"
    if contradict_count > 0 and support_count == 0:
        return "CONTRADICT"
    if support_count > contradict_count:
        return "SUPPORT"
    if contradict_count > support_count:
        return "CONTRADICT"
    return "INDETERMINATE"


def tune(args):
    print("[*] Loading validation data...")
    examples = load_climate_fever(args.dataset, "valid", args.max_rows, args.data_dir)
    print(f"[*] Loaded {len(examples)} validation examples")

    param_grid = {
        "min_relevance": RELEVANCE_THRESHOLDS,
        "similarity_weight": SIM_WEIGHTS,
        "term_weight": TERM_WEIGHTS,
        "entity_weight": ENTITY_WEIGHTS,
        "conf_low": CONFIDENCE_MAP["low"],
        "conf_med": CONFIDENCE_MAP["medium"],
        "conf_high": CONFIDENCE_MAP["high"],
    }

    keys = list(param_grid.keys())
    best_f1 = -1.0
    best_params = None
    total = 1
    for v in param_grid.values():
        total *= len(v)

    print(f"[*] Searching {total} combinations...")
    count = 0
    for values in itertools.product(*param_grid.values()):
        params = dict(zip(keys, values))
        count += 1
        if count % 50 == 0:
            print(f"[*] {count}/{total}...")

        y_true = []
        y_pred = []
        for ex in examples:
            pred = heuristic_predict(ex["claim"], ex["evidence"], params)
            y_true.append(ex["label"])
            y_pred.append(pred)

        macro_f1 = f1_score(y_true, y_pred, average="macro")
        weighted_f1 = f1_score(y_true, y_pred, average="weighted")
        acc = accuracy_score(y_true, y_pred)

        if macro_f1 > best_f1:
            best_f1 = macro_f1
            best_params = {
                "params": params,
                "accuracy": round(acc, 4),
                "macro_f1": round(macro_f1, 4),
                "weighted_f1": round(weighted_f1, 4),
            }
            print(f"\n[+] New best! Macro F1: {best_f1:.4f}")
            print(f"    Params: {params}")

    print(f"\n{'='*60}")
    print("BEST PARAMETERS:")
    print(json.dumps(best_params, indent=2))
    print(f"{'='*60}")

    with open(os.path.join(args.output_dir, "heuristic_tuned_params.json"), "w") as f:
        json.dump(best_params, f, indent=2)
    print(f"Saved to heuristic_tuned_params.json")


def parse_args():
    p = argparse.ArgumentParser(description="Tune heuristic thresholds on validation set.")
    p.add_argument("--dataset", default="rexarski/climate_fever_fixed")
    p.add_argument("--data-dir", default=os.path.join(BACKEND_DIR, "data", "climate_fever"))
    p.add_argument("--max-rows", type=int)
    p.add_argument("--output-dir", default=os.path.join(BACKEND_DIR, "models"))
    return p.parse_args()


if __name__ == "__main__":
    tune(parse_args())
