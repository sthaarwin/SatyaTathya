import joblib
import os
import re
from typing import Tuple, Optional
import logging
import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.preprocessing import LabelEncoder

try:
    from xgboost import XGBClassifier
    HAS_XGB = True
except ImportError:
    XGBClassifier = None
    HAS_XGB = False

logger = logging.getLogger(__name__)

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")

# These functions/classes are referenced by the trained sklearn Pipelines via joblib.
# They must be at module level so joblib can find them when unpickling.


class _XGBWrapper(BaseEstimator, ClassifierMixin):
    """Wraps XGBoost to handle string labels via LabelEncoder."""
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self._xgb = None
        self._le = LabelEncoder()

    def fit(self, X, y):
        y_encoded = self._le.fit_transform(y)
        self._xgb = XGBClassifier(**self.kwargs)
        self._xgb.fit(X, y_encoded)
        self.classes_ = self._le.classes_
        return self

    def predict(self, X):
        return self._le.inverse_transform(self._xgb.predict(X))

    def predict_proba(self, X):
        return self._xgb.predict_proba(X)

SUPPORT_WORDS = {
    "confirmed", "true", "announced", "approved", "launched", "begins",
    "initiated", "inaugurated", "completed", "opened",
    "supports", "shows", "found",
}

CONTRADICT_WORDS = {
    "denied", "false", "fake", "cancelled", "canceled", "stopped",
    "rejected", "debunked", "misleading", "hoax", "rumor",
    "untrue", "incorrect", "not", "no",
}


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[\w]+", text.lower()))


def count_keywords(text: str, keywords: set[str]) -> int:
    lowered = text.lower()
    return sum(1 for keyword in keywords if keyword in lowered)


def engineered_features(rows: list[dict]) -> np.ndarray:
    features = []
    for row in rows:
        ct = tokenize(row["claim"])
        et = tokenize(row["evidence"])
        overlap = len(ct & et)
        union = len(ct | et) or 1
        features.append([
            len(row["claim"]),
            len(row["evidence"]),
            len(ct),
            len(et),
            overlap,
            overlap / union,
            count_keywords(row["evidence"], SUPPORT_WORDS),
            count_keywords(row["evidence"], CONTRADICT_WORDS),
        ])
    return np.array(features, dtype=float)


def text_values(rows: list[dict]) -> list[str]:
    return [row["text"] for row in rows]


def claim_values(rows: list[dict]) -> list[str]:
    return [row["claim"] for row in rows]


def evidence_values(rows: list[dict]) -> list[str]:
    return [row["evidence"] for row in rows]


def interaction_values(rows: list[dict]) -> list[str]:
    return [row["interaction"] for row in rows]


class EnsembleVerifier:
    """
    Ensemble model that combines classical ML models for fast stance detection.
    Used as a fallback/optimization before LLM-based verification.
    """

    def __init__(self):
        self.logreg = None
        self.svm = None
        self.random_forest = None
        self.xgb = None
        self._load_models()

    def _load_models(self):
        """Load pre-trained classical models"""
        try:
            import sys
            this_module = sys.modules[__name__]
            for expected_name in ('__main__', 'scripts.train_climate_fever_classical', 'train_climate_fever_classical'):
                sys.modules[expected_name] = this_module

            logreg_path = os.path.join(MODELS_DIR, "climate_fever_logreg_rich.joblib")
            svm_path = os.path.join(MODELS_DIR, "climate_fever_svm_rich.joblib")
            rf_path = os.path.join(MODELS_DIR, "climate_fever_random_forest_tuned_rich.joblib")

            if os.path.exists(logreg_path):
                self.logreg = joblib.load(logreg_path)
                logger.info("Loaded Logistic Regression model")

            if os.path.exists(svm_path):
                self.svm = joblib.load(svm_path)
                logger.info("Loaded SVM model")

            if os.path.exists(rf_path):
                self.random_forest = joblib.load(rf_path)
                logger.info("Loaded Random Forest model")

            xgb_path = os.path.join(MODELS_DIR, "climate_fever_xgb_rich.joblib")
            if os.path.exists(xgb_path):
                self.xgb = joblib.load(xgb_path)
                logger.info("Loaded XGBoost model")

        except Exception as e:
            logger.warning(f"Failed to load ensemble models: {e}")

    def is_available(self) -> bool:
        """Check if ensemble models are loaded"""
        return self.logreg is not None or self.svm is not None or self.random_forest is not None or self.xgb is not None

    @staticmethod
    def _format_input(claim: str, evidence: str) -> list[dict]:
        """
        Format claim and evidence as the dict structure the trained Pipelines expect.
        The models were trained on Climate-FEVER rows with 'claim', 'evidence', 'text', 'interaction' keys.
        """
        return [{
            "claim": claim,
            "evidence": evidence,
            "text": f"Claim: {claim}\nEvidence: {evidence}",
            "interaction": f"{claim} [SEP] {evidence}",
        }]

    def predict_stance(
        self, claim: str, evidence: str
    ) -> Tuple[str, float, Optional[str]]:
        """
        Use ensemble models to predict stance: SUPPORT, CONTRADICT, or INDETERMINATE.
        The loaded .joblib files are full sklearn Pipelines containing TF-IDF + engineered features.
        Returns (stance, confidence, model_used)
        """
        if not self.is_available():
            return "INDETERMINATE", 0.0, None

        try:
            input_data = self._format_input(claim, evidence)

            predictions = []
            confidences = []
            models_used = []

            # Logistic Regression
            if self.logreg is not None:
                try:
                    pred = self.logreg.predict(input_data)[0]
                    proba = max(self.logreg.predict_proba(input_data)[0])
                    predictions.append(pred)
                    confidences.append(proba)
                    models_used.append("LogisticRegression")
                except Exception as e:
                    logger.warning(f"LogReg prediction failed: {e}")

            # SVM
            if self.svm is not None:
                try:
                    pred = self.svm.predict(input_data)[0]
                    decision = self.svm.decision_function(input_data)[0]
                    proba = min(1.0, max(abs(decision)) / 5.0)
                    predictions.append(pred)
                    confidences.append(proba)
                    models_used.append("SVM")
                except Exception as e:
                    logger.warning(f"SVM prediction failed: {e}")

            # Random Forest
            if self.random_forest is not None:
                try:
                    pred = self.random_forest.predict(input_data)[0]
                    proba = max(self.random_forest.predict_proba(input_data)[0])
                    predictions.append(pred)
                    confidences.append(proba)
                    models_used.append("RandomForest")
                except Exception as e:
                    logger.warning(f"RF prediction failed: {e}")

            # XGBoost
            if self.xgb is not None:
                try:
                    pred = self.xgb.predict(input_data)[0]
                    proba = max(self.xgb.predict_proba(input_data)[0])
                    predictions.append(pred)
                    confidences.append(proba)
                    models_used.append("XGBoost")
                except Exception as e:
                    logger.warning(f"XGBoost prediction failed: {e}")

            # Ensemble voting
            if predictions:
                from collections import Counter
                stance = Counter(predictions).most_common(1)[0][0]
                avg_confidence = float(np.mean(confidences))
                model_str = ",".join(models_used)

                return stance, avg_confidence, model_str

        except Exception as e:
            logger.error(f"Ensemble prediction error: {e}")

        return "INDETERMINATE", 0.0, None

    def get_model_info(self) -> dict:
        """Get information about loaded models"""
        return {
            "logreg_available": self.logreg is not None,
            "svm_available": self.svm is not None,
            "random_forest_available": self.random_forest is not None,
            "xgb_available": self.xgb is not None,
            "ensemble_ready": self.is_available(),
        }


# Global ensemble instance
_ensemble_instance: Optional[EnsembleVerifier] = None


def get_ensemble_verifier() -> EnsembleVerifier:
    """Get or create the global ensemble verifier instance"""
    global _ensemble_instance
    if _ensemble_instance is None:
        _ensemble_instance = EnsembleVerifier()
    return _ensemble_instance
