import json
import os
from datetime import UTC, datetime, timedelta

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from schemas.donations import MAX_EXPIRY_HOURS
from services.ml_features import CATEGORIES, normalize_category

load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MOCK_MODE = os.getenv("LLM_MOCK", "false").lower() == "true"

_client = None


class NotFoodDescription(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        _client = genai.Client(api_key=api_key)
    return _client


class _Extraction(BaseModel):
    is_food: bool
    category: str
    description: str
    quantity_portions: float
    quantity_estimated: bool
    hours_until_unsafe: float
    expiry_estimated: bool
    warnings: list[str] = Field(default_factory=list)


SYSTEM_PROMPT = f"""You convert a food donor's free-text message into structured data for a food redistribution platform.
 
is_food: set to true only if the message describes an actual food donation. Set to false if the message is empty,
unrelated to food, or has no usable donation details, and explain why in warnings. When is_food is false, the other
fields are ignored, so fill them with any placeholder values.
 
Allowed categories (choose exactly one): {", ".join(CATEGORIES)}.
 
quantity_portions: estimate how many single-person meal portions the donation provides.
If the donor gives a portion, meal, tray, or person count directly, use it and set quantity_estimated=false.
If the donor gives weight or volume instead, convert to portions using a reasonable estimate and set quantity_estimated=true.
 
hours_until_unsafe: estimate how many hours from now the food remains safe to eat, using standard food-safety practice.
Hot cooked food left at room temperature is typically only safe a few hours; refrigerated, packaged, or shelf-stable
food is safe much longer. If the donor states an explicit expiry or best-before time or date, use that instead and
set expiry_estimated=false. Otherwise estimate conservatively and set expiry_estimated=true. Never exceed {MAX_EXPIRY_HOURS} hours.
 
description: a short, clean restatement of what is being donated, at most 255 characters.
 
warnings: short notes for the donor to double check, e.g. "quantity estimated from weight" or
"expiry estimated from food-safety guidance, please confirm". Empty list if nothing to flag."""


def _to_result(extraction: _Extraction) -> dict:
    category = normalize_category(extraction.category)

    quantity = max(0.0, float(extraction.quantity_portions))
    warnings = list(extraction.warnings)
    if quantity <= 0:
        warnings.append("Could not determine a quantity; please enter it manually.")
        quantity = 1.0

    hours = extraction.hours_until_unsafe
    if hours is None or hours <= 0:
        hours = 2.0
        warnings.append("Could not determine an expiry; defaulted to 2 hours, please confirm.")
        expiry_estimated = True
    else:
        hours = min(float(hours), MAX_EXPIRY_HOURS)
        expiry_estimated = extraction.expiry_estimated

    expiry_time = datetime.now(UTC) + timedelta(hours=hours)

    return {
        "category": category,
        "description": (extraction.description or "").strip()[:255] or "Food donation",
        "quantity_portions": quantity,
        "quantity_estimated": bool(extraction.quantity_estimated),
        "expiry_time": expiry_time.isoformat(),
        "expiry_estimated": bool(expiry_estimated),
        "warnings": warnings,
    }


def _mock_extraction(text: str) -> _Extraction:
    return _Extraction(
        is_food=True,
        category="other",
        description=text[:255],
        quantity_portions=1,
        quantity_estimated=True,
        hours_until_unsafe=4,
        expiry_estimated=True,
        warnings=["LLM_MOCK is enabled; this is a placeholder result, not a real Gemini call."],
    )


def parse_donation_text(text: str) -> dict:
    if MOCK_MODE:
        extraction = _mock_extraction(text)
    else:
        client = _get_client()
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=_Extraction,
                temperature=0.1,
            ),
        )
        extraction = _Extraction.model_validate(json.loads(response.text))

    if not extraction.is_food:
        reason = (
            extraction.warnings[0]
            if extraction.warnings
            else "This does not look like a food donation."
        )
        raise NotFoodDescription(reason)

    return _to_result(extraction)
