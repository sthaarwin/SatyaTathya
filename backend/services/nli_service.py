import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Config
NLI_MODEL_NAME = os.getenv("NLI_MODEL_NAME", "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli")
USE_NLI_STANCE = os.getenv("USE_NLI_STANCE", "true").lower() == "true"

_nli_pipeline = None


def _load_nli_model():
    """Lazy-load the NLI model once (downloaded on first use, ~1GB)."""
    global _nli_pipeline
    if _nli_pipeline is not None:
        return True
    try:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        import torch
        logger.info(f"Loading NLI model: {NLI_MODEL_NAME}...")
        tokenizer = AutoTokenizer.from_pretrained(NLI_MODEL_NAME)
        model = AutoModelForSequenceClassification.from_pretrained(NLI_MODEL_NAME)
        _nli_pipeline = {
            "model": model,
            "tokenizer": tokenizer,
            "id2label": model.config.id2label,
        }
        logger.info("NLI model loaded successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to load NLI model: {e}")
        return False


def nli_available() -> bool:
    return _nli_pipeline is not None or _load_nli_model()


def evaluate_with_nli(claim: str, evidence_item: dict) -> dict:
    """
    Evaluate claim-evidence pair using an NLI model.
    Returns same dict format as evaluate_evidence_embedding().
    """
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

    if not _load_nli_model():
        return {
            "stance": "INDETERMINATE",
            "relevance": 0.0,
            "similarity": 0.0,
            "confidence": 0.0,
            "reasoning": "NLI model not available",
            "method": "nli_fallback",
        }

    try:
        import torch
        # NLI format: (premise=evidence, hypothesis=claim)
        inputs = _nli_pipeline["tokenizer"](
            evidence_text, claim,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=512,
        )
        with torch.no_grad():
            outputs = _nli_pipeline["model"](**inputs)
            probs = torch.nn.functional.softmax(outputs.logits[0], dim=-1)

        # Standard NLI label order: 0=ENTAILMENT, 1=NEUTRAL, 2=CONTRADICTION
        id2label = _nli_pipeline["id2label"]
        label_map = {v.upper(): k for k, v in id2label.items()}
        entailment = float(probs[label_map.get("ENTAILMENT", 0)])
        neutral = float(probs[label_map.get("NEUTRAL", 1)])
        contradiction = float(probs[label_map.get("CONTRADICTION", 2)])

        if entailment > contradiction and entailment > neutral:
            stance = "SUPPORT"
            confidence = entailment
            relevance = entailment + neutral
        elif contradiction > entailment and contradiction > neutral:
            stance = "CONTRADICT"
            confidence = contradiction
            relevance = contradiction + neutral
        else:
            stance = "INDETERMINATE"
            confidence = neutral
            relevance = neutral

        return {
            "stance": stance,
            "relevance": round(min(1.0, relevance), 3),
            "similarity": round(entailment + neutral, 3),
            "confidence": round(confidence, 3),
            "reasoning": f"NLI: E={entailment:.3f}, C={contradiction:.3f}, N={neutral:.3f}",
            "method": "nli",
        }
    except Exception as e:
        logger.warning(f"NLI evaluation failed: {e}")

    return {
        "stance": "INDETERMINATE",
        "relevance": 0.0,
        "similarity": 0.0,
        "confidence": 0.0,
        "reasoning": "NLI evaluation error",
        "method": "nli_fallback",
    }
