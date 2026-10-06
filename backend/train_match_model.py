import sys
from datetime import UTC, datetime

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

from services.match_model import MATCH_MODEL_PATH
from services.ml_features import vectorize
from services.synthetic_match_data import generate_synthetic_dataset

MIN_REAL_MATCHES = 200
SYNTHETIC_N = 4000


def load_real_data():
    from db.database import SessionLocal
    from models.donation import Donation  # noqa: F401
    from models.match import Match
    from models.user import User  # noqa: F401

    db = SessionLocal()
    try:
        rows = (
            db.query(Match)
            .filter(Match.outcome.isnot(None), Match.features.isnot(None))
            .order_by(Match.created_at.asc())
            .all()
        )
        features_list = [r.features for r in rows]
        labels = [1 if r.outcome == "fulfilled" else 0 for r in rows]
        timestamps = [r.created_at for r in rows]
        return features_list, labels, timestamps
    finally:
        db.close()


def precision_at_k(y_true, scores, k):
    if k <= 0:
        return None
    order = np.argsort(scores)[::-1][:k]
    return float(np.mean(np.array(y_true)[order]))


def main():
    features_list, labels, timestamps = load_real_data()
    using_real = len(features_list) >= MIN_REAL_MATCHES

    if not using_real:
        print(
            f"Only {len(features_list)} real resolved matches found (< {MIN_REAL_MATCHES}). "
            "Training on SYNTHETIC data instead."
        )
        features_list, labels, timestamps = generate_synthetic_dataset(SYNTHETIC_N)
    else:
        print(f"Training on {len(features_list)} real resolved matches.")

    order = np.argsort(
        [t.timestamp() if hasattr(t, "timestamp") else i for i, t in enumerate(timestamps)]
    )
    features_list = [features_list[i] for i in order]
    labels = [labels[i] for i in order]

    X = np.array([vectorize(f) for f in features_list], dtype=float)
    y = np.array(labels, dtype=int)
    rule_scores = np.array([f["rule_score"] for f in features_list], dtype=float)

    split = int(len(X) * 0.8)
    if split < 20 or len(X) - split < 20:
        print(
            "Not enough data for a meaningful time-based split. Aborting; "
            "keeping the rule-based score in production."
        )
        sys.exit(1)

    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    rule_test = rule_scores[split:]

    if len(set(y_train.tolist())) < 2 or len(set(y_test.tolist())) < 2:
        print("Training or test split has only one class present. Aborting.")
        sys.exit(1)

    baseline_auc = roc_auc_score(y_test, rule_test)
    k = max(1, int(y_test.sum()))
    baseline_p_at_k = precision_at_k(y_test, rule_test, k)
    print(
        f"Baseline (current rule score)  AUC={baseline_auc:.3f}  precision@{k}={baseline_p_at_k:.3f}"
    )

    scaler = StandardScaler().fit(X_train)
    lr = LogisticRegression(max_iter=1000).fit(scaler.transform(X_train), y_train)
    lr_probs = lr.predict_proba(scaler.transform(X_test))[:, 1]
    lr_auc = roc_auc_score(y_test, lr_probs)
    lr_p_at_k = precision_at_k(y_test, lr_probs, k)
    print(f"Logistic Regression             AUC={lr_auc:.3f}  precision@{k}={lr_p_at_k:.3f}")

    hgb = HistGradientBoostingClassifier(max_depth=4, random_state=0).fit(X_train, y_train)
    hgb_probs = hgb.predict_proba(X_test)[:, 1]
    hgb_auc = roc_auc_score(y_test, hgb_probs)
    hgb_p_at_k = precision_at_k(y_test, hgb_probs, k)
    print(f"Gradient Boosting               AUC={hgb_auc:.3f}  precision@{k}={hgb_p_at_k:.3f}")

    candidates = [
        ("lr", lr_auc, {"kind": "lr", "model": lr, "scaler": scaler}),
        ("hgb", hgb_auc, {"kind": "hgb", "model": hgb, "scaler": None}),
    ]
    name, auc, bundle = max(candidates, key=lambda c: c[1])

    if auc <= baseline_auc:
        print(
            f"\nBest model ({name}, AUC={auc:.3f}) did not beat the baseline "
            f"(AUC={baseline_auc:.3f}). Not saving a model; matching keeps using "
            "the rule-based score."
        )
        sys.exit(0)

    bundle["trained_at"] = datetime.now(UTC).isoformat()
    bundle["using_real_data"] = using_real
    bundle["n_train"] = int(split)
    bundle["n_test"] = int(len(X) - split)
    bundle["test_auc"] = float(auc)
    bundle["baseline_auc"] = float(baseline_auc)

    joblib.dump(bundle, MATCH_MODEL_PATH)
    print(f"\nSaved {name} model to {MATCH_MODEL_PATH}")
    print(f"Improvement over baseline: {auc - baseline_auc:+.3f} AUC")
    if not using_real:
        print(
            "NOTE: this model was trained on synthetic data and should be "
            "retrained once enough real match outcomes are logged."
        )


if __name__ == "__main__":
    main()
