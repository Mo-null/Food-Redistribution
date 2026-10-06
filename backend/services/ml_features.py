import math
import re

from models.donation import DonationCategory

W_URGENCY = 0.4
W_PROXIMITY = 0.25
W_CAPACITY_FIT = 0.15
W_RELIABILITY = 0.2

MAX_EXPIRY_WINDOW_HOURS = 48
MAX_MATCH_DISTANCE_KM = 10

HISTORY_CONFIDENT_AFTER_N = 10
HISTORY_PRIOR = {"fulfilled": 0.56, "declined": 0.18, "ignored": 0.13, "no_show": 0.13}

CATEGORIES = [c.value for c in DonationCategory]

NUMERIC_FEATURES = [
    "hours_to_expiry",
    "distance_km",
    "urgency",
    "proximity",
    "capacity_fit",
    "reliability",
    "rule_score",
    "quantity",
    "capacity",
    "qty_ratio",
    "is_organization",
    "hour_of_day",
    "weekday",
    "r_n_prior",
    "r_fulfill_rate",
    "r_decline_rate",
    "r_ignore_rate",
    "r_noshow_rate",
]


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def normalize_category(raw: str | None) -> str:
    if not raw:
        return "other"
    key = re.sub(r"[^a-z]+", "_", raw.strip().lower()).strip("_")
    return key if key in CATEGORIES else "other"


def urgency_score(hours_to_expiry: float) -> float:
    h = max(0.0, min(hours_to_expiry, MAX_EXPIRY_WINDOW_HOURS))
    return 1 - (h / MAX_EXPIRY_WINDOW_HOURS)


def proximity_score(distance_km: float) -> float:
    return max(0.0, 1 - (distance_km / MAX_MATCH_DISTANCE_KM))


def capacity_fit_score(quantity: float, capacity: float) -> float:
    ratio = quantity / capacity
    return max(0.0, 1 - abs(1 - ratio))


def rule_score(urgency: float, proximity: float, capacity_fit: float, reliability: float) -> float:
    return (
        W_URGENCY * urgency
        + W_PROXIMITY * proximity
        + W_CAPACITY_FIT * capacity_fit
        + W_RELIABILITY * reliability
    )


def history_features(counts: dict[str, int] | None) -> dict[str, float]:
    c = counts or {}
    f = c.get("fulfilled", 0)
    d = c.get("declined", 0)
    i = c.get("ignored", 0)
    ns = c.get("no_show", 0)
    n = f + d + i + ns
    confidence = min(n / HISTORY_CONFIDENT_AFTER_N, 1.0)

    def shrunk(count: int, outcome: str) -> float:
        raw = count / n if n else 0.0
        return confidence * raw + (1 - confidence) * HISTORY_PRIOR[outcome]

    return {
        "r_n_prior": float(n),
        "r_fulfill_rate": shrunk(f, "fulfilled"),
        "r_decline_rate": shrunk(d, "declined"),
        "r_ignore_rate": shrunk(i, "ignored"),
        "r_noshow_rate": shrunk(ns, "no_show"),
    }


def build_features(
    *,
    hours_to_expiry: float,
    distance_km: float,
    quantity: float,
    capacity: float,
    category: str | None,
    reliability: float,
    is_organization: bool,
    hour_of_day: int,
    weekday: int,
    history_counts: dict[str, int] | None,
) -> dict:
    h = max(0.0, float(hours_to_expiry))
    urgency = urgency_score(h)
    proximity = proximity_score(float(distance_km))
    fit = capacity_fit_score(float(quantity), float(capacity))
    feats = {
        "hours_to_expiry": h,
        "distance_km": float(distance_km),
        "urgency": float(urgency),
        "proximity": float(proximity),
        "capacity_fit": float(fit),
        "reliability": float(reliability),
        "rule_score": float(rule_score(urgency, proximity, fit, reliability)),
        "quantity": float(quantity),
        "capacity": float(capacity),
        "qty_ratio": float(quantity) / float(capacity),
        "category": normalize_category(category),
        "is_organization": 1 if is_organization else 0,
        "hour_of_day": int(hour_of_day),
        "weekday": int(weekday),
    }
    feats.update(history_features(history_counts))
    return feats


def vectorize(feats: dict) -> list[float]:
    row = [float(feats[k]) for k in NUMERIC_FEATURES]
    cat = normalize_category(feats.get("category"))
    row += [1.0 if cat == c else 0.0 for c in CATEGORIES]
    return row
