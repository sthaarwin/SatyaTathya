import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

NLI_MODEL_NAME = os.getenv("NLI_MODEL_NAME", "facebook/bart-large-mnli")
USE_NLI_STANCE = os.getenv("USE_NLI_STANCE", "true").lower() == "true"

_classifier = None


def _load_classifier():
    global _classifier
    if _classifier is not None:
        return True
    try:
        from transformers import pipeline
        logger.info(f"Loading zero-shot classifier: {NLI_MODEL_NAME}...")
        _classifier = pipeline(
            "zero-shot-classification",
            model=NLI_MODEL_NAME,
            device=-1,
        )
        logger.info("Zero-shot classifier loaded successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to load classifier: {e}")
        return False


def nli_available() -> bool:
    return _classifier is not None or _load_classifier()


def evaluate_with_nli(claim: str, evidence_item: dict) -> dict:
    evidence_text = evidence_item.get("content", "")[:1500]
    if not evidence_text or not claim:
        return {
            "stance": "INDETERMINATE",
            "relevance": 0.0,
            "similarity": 0.0,
            "confidence": 0.0,
            "reasoning": "Empty claim or evidence",
            "method": "nli",
        }

    if not _load_classifier():
        return {
            "stance": "INDETERMINATE",
            "relevance": 0.0,
            "similarity": 0.0,
            "confidence": 0.0,
            "reasoning": "Classifier not available",
            "method": "nli_fallback",
        }

    try:
        labels = ["supports this claim", "contradicts this claim", "unrelated"]
        result = _classifier(evidence_text, labels)

        scores = dict(zip(result["labels"], result["scores"]))
        support = scores.get("supports this claim", 0.0)
        contradict = scores.get("contradicts this claim", 0.0)
        unrelated = scores.get("unrelated", 0.0)

        MARGIN = 0.05
        if support > contradict and support > unrelated and (support - max(contradict, unrelated)) > MARGIN:
            stance = "SUPPORT"
            confidence = support
            relevance = support
        elif contradict > support and contradict > unrelated and (contradict - max(support, unrelated)) > MARGIN:
            stance = "CONTRADICT"
            confidence = contradict
            relevance = contradict
        else:
            stance = "INDETERMINATE"
            confidence = max(support, contradict, unrelated)
            relevance = max(support, contradict, unrelated)

        return {
            "stance": stance,
            "relevance": round(min(1.0, relevance), 3),
            "similarity": round(max(support, contradict) + unrelated, 3),
            "confidence": round(confidence, 3),
            "reasoning": f"Zero-shot: S={support:.3f} C={contradict:.3f} U={unrelated:.3f}",
            "method": "nli",
        }
    except Exception as e:
        logger.warning(f"Zero-shot classification failed: {e}")

    return {
        "stance": "INDETERMINATE",
        "relevance": 0.0,
        "similarity": 0.0,
        "confidence": 0.0,
        "reasoning": "Classification error",
        "method": "nli_fallback",
    }
