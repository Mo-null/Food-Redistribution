"""
Run from backend:  python eval_llm_parse.py
Needs GEMINI_API_KEY in .env. Calls the real Gemini API 20 times.
"""

import time

from services.llm_parse import parse_donation_text

SECONDS_BETWEEN_CALLS = 13
MAX_RETRIES = 3

CASES = [
    (
        "Cooked 40 portions of dal and rice at 1pm today, will spoil if not eaten by evening",
        "cooked_meals",
        False,
    ),
    ("20 kg of rice, unopened bags", "packaged", True),
    ("15 trays of biryani, about 8 servings each, made this morning", "cooked_meals", False),
    ("50 loaves of bread from the bakery, best before tomorrow night", "bakery", False),
    ("3 crates of tomatoes and onions, still fresh", "raw_produce", True),
    ("2 dozen eggs and a crate of milk cartons, refrigerated", "dairy_eggs", True),
    ("100 cans of chickpeas and lentils, long shelf life", "packaged", False),
    ("30 bottles of orange juice, unopened, needs to be used within a week", "beverages", False),
    ("Fresh fish, about 10kg, caught this morning, needs to go out today", "meat_fish", True),
    (
        "Leftover wedding catering, chicken and rice, feeds about 100 people, from tonight's event",
        "cooked_meals",
        False,
    ),
    ("Extra sandwiches from the cafe, 25 of them, made this afternoon", "cooked_meals", False),
    ("A box of assorted vegetables, roughly enough for 15 people", "raw_produce", True),
    ("10 packets of biscuits and chips, unopened", "packaged", False),
    ("5 liters of yogurt, needs to be picked up within 2 days", "dairy_eggs", False),
    ("hi", "other", True),
    ("Chicken curry, 20 portions, cooked 3 hours ago, keep refrigerated", "cooked_meals", False),
    ("40 muffins and pastries from this morning's batch", "bakery", False),
    ("Bulk rice, 25kg sacks, 4 of them", "packaged", True),
    ("Raw mutton, 8kg, needs same-day pickup", "meat_fish", True),
    ("Soft drinks, 3 crates, 24 bottles each", "beverages", True),
]


def main():
    correct_category = 0
    correct_quantity_flag = 0
    errors = 0

    for i, (text, expected_category, expected_estimated) in enumerate(CASES):
        if i > 0:
            time.sleep(SECONDS_BETWEEN_CALLS)

        result = None
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                result = parse_donation_text(text)
                break
            except Exception as e:
                last_error = e
                if "429" in str(e) or "503" in str(e):
                    if attempt < MAX_RETRIES - 1:
                        print(f"  retrying in 20s ({attempt + 1}/{MAX_RETRIES})...")
                        time.sleep(20)
                        continue
                break

        if result is None:
            print(f"ERROR  {text!r}  -> {last_error}")
            errors += 1
            continue

        cat_ok = result["category"] == expected_category
        qty_ok = result["quantity_estimated"] == expected_estimated
        correct_category += cat_ok
        correct_quantity_flag += qty_ok

        mark = "OK  " if cat_ok else "MISS"
        print(
            f"{mark}  cat={result['category']:<14} expected={expected_category:<14} "
            f"qty={result['quantity_portions']:<6} est={result['quantity_estimated']}  {text[:60]}"
        )

    n = len(CASES)
    print()
    print(f"Category accuracy: {correct_category}/{n} ({100 * correct_category / n:.0f}%)")
    print(
        f"Quantity-estimated flag matched: {correct_quantity_flag}/{n} ({100 * correct_quantity_flag / n:.0f}%)"
    )
    print(f"Errors (API/parse failures): {errors}/{n}")


if __name__ == "__main__":
    main()
