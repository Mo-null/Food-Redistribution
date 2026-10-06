import math
import random
from datetime import UTC, datetime, timedelta

from services.ml_features import CATEGORIES, HISTORY_PRIOR, build_features

TARGET_SUCCESS_RATE = HISTORY_PRIOR["fulfilled"]

CATEGORY_RISK = {
    "cooked_meals": -0.6,
    "raw_produce": -0.1,
    "bakery": 0.0,
    "packaged": 0.3,
    "dairy_eggs": 0.0,
    "meat_fish": -0.3,
    "beverages": 0.3,
    "other": -0.1,
}


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1 / (1 + math.exp(-x))
    z = math.exp(x)
    return z / (1 + z)


def _calibrate_intercept(base_logits: list[float], target_rate: float) -> float:
    """Find the intercept so the average success probability equals target_rate (bisection)."""
    low, high = -30.0, 30.0
    for _ in range(50):
        mid = (low + high) / 2
        mean_p = sum(_sigmoid(z + mid) for z in base_logits) / len(base_logits)
        if mean_p < target_rate:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def _sample_history(rng: random.Random, base_reliability: float) -> dict[str, int]:
    n_prior = rng.choices(
        [0, rng.randint(1, 3), rng.randint(4, 15), rng.randint(16, 40)],
        weights=[0.35, 0.30, 0.25, 0.10],
    )[0]
    if n_prior == 0:
        return {"fulfilled": 0, "declined": 0, "ignored": 0, "no_show": 0}
    fulfilled = 0
    declined = ignored = no_show = 0
    for _ in range(n_prior):
        r = rng.random()
        if r < base_reliability:
            fulfilled += 1
        elif r < base_reliability + (1 - base_reliability) * 0.4:
            declined += 1
        elif r < base_reliability + (1 - base_reliability) * 0.7:
            ignored += 1
        else:
            no_show += 1
    return {"fulfilled": fulfilled, "declined": declined, "ignored": ignored, "no_show": no_show}


def generate_synthetic_dataset(
    n: int, seed: int = 42
) -> tuple[list[dict], list[int], list[datetime]]:
    rng = random.Random(seed)
    features_list, base_logits, timestamps = [], [], []
    start = datetime.now(UTC) - timedelta(days=180)

    for k in range(n):
        base_reliability = rng.betavariate(2.5, 2.0)
        hours_to_expiry = rng.uniform(0.1, 48)
        distance_km = rng.uniform(0.1, 10)
        capacity = rng.uniform(2, 20)
        qty_ratio_center = rng.choice([0.6, 1.0, 1.0, 1.4, 2.2])
        quantity = max(0.5, capacity * rng.gauss(qty_ratio_center, 0.25))
        category = rng.choice(CATEGORIES)
        is_organization = rng.random() < 0.3
        hour_of_day = rng.randint(0, 23)
        weekday = rng.randint(0, 6)
        history_counts = _sample_history(rng, base_reliability)

        feats = build_features(
            hours_to_expiry=hours_to_expiry,
            distance_km=distance_km,
            quantity=quantity,
            capacity=capacity,
            category=category,
            reliability=base_reliability,
            is_organization=is_organization,
            hour_of_day=hour_of_day,
            weekday=weekday,
            history_counts=history_counts,
        )

        # The intercept is solved for afterwards (_calibrate_intercept) so the overall rate hits the target.
        base_logit = (
            2.2 * feats["proximity"]
            + 3.0 * feats["r_fulfill_rate"]
            + 1.8 * feats["reliability"]
            + 1.5 * feats["capacity_fit"]
            + CATEGORY_RISK[feats["category"]]
            + (0.5 if is_organization else 0.0)
            + (-2.5 if hours_to_expiry < 1 else 0.0)
            + (-0.8 if hour_of_day >= 22 or hour_of_day <= 5 else 0.0)
            + (-1.0 if feats["qty_ratio"] > 1.8 or feats["qty_ratio"] < 0.3 else 0.0)
            + rng.gauss(0, 0.6)
        )

        features_list.append(feats)
        base_logits.append(base_logit)
        timestamps.append(start + timedelta(minutes=k * 15))

    intercept = _calibrate_intercept(base_logits, TARGET_SUCCESS_RATE)
    labels = [1 if rng.random() < _sigmoid(z + intercept) else 0 for z in base_logits]

    return features_list, labels, timestamps
