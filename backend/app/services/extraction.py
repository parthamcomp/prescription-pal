import json
import re
from datetime import date

from app.services.llm import chat_completion

EXTRACTION_SYSTEM = "You are a medical prescription data extractor."

EXTRACTION_PROMPT = """Given OCR text from a doctor's prescription, extract structured information.

Return ONLY valid JSON with this exact schema (no markdown, no explanation):
{
  "doctor_name": "string",
  "date_of_visit": "YYYY-MM-DD or null",
  "complaint": "string",
  "diagnosis": "string",
  "medications": [
    {"name": "string", "form": "string (e.g. Tablet, Syrup, Drops - empty if unclear)", "dosage": "string", "frequency": "string", "duration": "string"}
  ],
  "child_age": "string",
  "child_weight": "string",
  "additional_notes": "string",
  "low_confidence": ["field paths you are genuinely unsure about, e.g. \\"doctor_name\\", \\"date_of_visit\\", \\"medications.0.dosage\\" - empty array if you're confident in everything you extracted"]
}

Use empty strings for unknown fields. If date is unclear, use null. Only list a field in
low_confidence if the OCR text was genuinely ambiguous, smudged, or ran characters together for
that specific field - do not hedge on fields you actually read clearly.
OCR text:
"""


def _normalise_date(value) -> str | None:
    if not value or value == "null":
        return None
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError:
        return None


def _fallback_extract(raw_text: str) -> dict:
    """Rule-based fallback when the LLM is unavailable."""
    medications = []
    for name in re.findall(
        r"(?i)(?:rx|tab|syrup|cap|drops?)[:\s]*([^\n,;]+)", raw_text
    )[:5]:
        medications.append(
            {"name": name.strip(), "form": "", "dosage": "", "frequency": "", "duration": ""}
        )
    return {
        "doctor_name": "",
        "date_of_visit": None,
        "complaint": "",
        "diagnosis": "",
        "medications": medications,
        "child_age": "",
        "child_weight": "",
        "additional_notes": raw_text[:500] if raw_text else "",
    }


async def extract_prescription_from_text(raw_text: str) -> dict:
    """Return a dict matching PrescriptionCreate fields (plus source_text)."""
    try:
        content = await chat_completion(
            EXTRACTION_SYSTEM,
            EXTRACTION_PROMPT + raw_text,
            temperature=0.0,
            json_mode=True,
        )
        data = json.loads(content)
    except (json.JSONDecodeError, KeyError, Exception):  # noqa: BLE001
        data = _fallback_extract(raw_text)

    medications = [
        {
            "name": m.get("name", ""),
            "form": m.get("form", ""),
            "dosage": m.get("dosage", ""),
            "frequency": m.get("frequency", ""),
            "duration": m.get("duration", ""),
        }
        for m in data.get("medications", [])
    ]

    low_confidence = [
        f for f in data.get("low_confidence", []) if isinstance(f, str)
    ]

    return {
        "doctor_name": data.get("doctor_name", ""),
        "date_of_visit": _normalise_date(data.get("date_of_visit")),
        "complaint": data.get("complaint", ""),
        "diagnosis": data.get("diagnosis", ""),
        "medications": medications,
        "child_age": data.get("child_age", ""),
        "child_weight": data.get("child_weight", ""),
        "additional_notes": data.get("additional_notes", ""),
        "source_text": raw_text,
        # Not persisted on the Prescription row itself (PrescriptionCreate has
        # no such field) - only carried on the job payload so the review UI
        # can flag fields the model itself said it wasn't sure about.
        "low_confidence": low_confidence,
    }
