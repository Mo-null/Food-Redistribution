import logging
import os

import joblib
import numpy as np

from services.ml_features import vectorize

logger = logging.getLogger(__name__)

MATCH_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "match_model.joblib"
)
ML_WEIGHT = 0.5

_cache = {"loaded": False, "bundle": None}


def _load():
    if _cache["loaded"]:
        return _cache["bundle"]
    _cache["loaded"] = True
    if not os.path.exists(MATCH_MODEL_PATH):
        _cache["bundle"] = None
        return None
    try:
        _cache["bundle"] = joblib.load(MATCH_MODEL_PATH)
    except Exception:
        logger.exception("Could not load the match model; using the rule score only")
        _cache["bundle"] = None
    return _cache["bundle"]


def predict_success_batch(features_list: list[dict]) -> list[float] | None:
    bundle = _load()
    if bundle is None:
        return None

    X = np.array([vectorize(f) for f in features_list], dtype=float)
    if bundle["kind"] == "lr":
        X = bundle["scaler"].transform(X)
    probs = bundle["model"].predict_proba(X)[:, 1]
    return [float(p) for p in probs]


def blend(rule_score: float, p: float | None) -> float:
    if p is None:
        return rule_score
    return (1 - ML_WEIGHT) * rule_score + ML_WEIGHT * p
