"""Tier 1 unit tests for services/extraction.py - both the LLM-backed path
and _fallback_extract, the rule-based extractor used when the LLM call
fails or returns unparseable JSON (services/extraction.py's own docstring:
"Rule-based fallback when the LLM is unavailable").
"""
import json

from app.services.extraction import _fallback_extract, _normalise_date, extract_prescription_from_text


class TestNormaliseDate:
    def test_valid_iso_date_passes_through(self):
        assert _normalise_date("2026-06-15") == "2026-06-15"

    def test_a_full_timestamp_is_truncated_to_the_date(self):
        assert _normalise_date("2026-06-15T10:30:00") == "2026-06-15"

    def test_none_returns_none(self):
        assert _normalise_date(None) is None

    def test_the_literal_string_null_returns_none(self):
        # the model is asked for "YYYY-MM-DD or null" but returns JSON as
        # text, so this can arrive as the actual string "null" rather than
        # a JSON null - both have to resolve to None.
        assert _normalise_date("null") is None

    def test_empty_string_returns_none(self):
        assert _normalise_date("") is None

    def test_unparseable_date_returns_none_not_a_crash(self):
        assert _normalise_date("not a date at all") is None


class TestFallbackExtract:
    def test_extracts_medications_from_rx_prefixed_lines(self):
        raw = "Rx: Amoxicillin 250mg\nTab: Paracetamol"
        result = _fallback_extract(raw)

        names = [m["name"] for m in result["medications"]]
        assert "Amoxicillin 250mg" in names
        assert "Paracetamol" in names

    def test_recognizes_syrup_cap_and_drops_prefixes_case_insensitively(self):
        raw = "SYRUP: Cough Syrup\ncap Vitamin D\nDROPS: Ear Drops"
        result = _fallback_extract(raw)
        names = [m["name"] for m in result["medications"]]
        assert len(names) == 3

    def test_caps_at_five_medications(self):
        raw = "\n".join(f"Rx: Med{i}" for i in range(10))
        result = _fallback_extract(raw)
        assert len(result["medications"]) == 5

    def test_no_recognizable_medication_lines_returns_an_empty_list(self):
        result = _fallback_extract("just some plain unstructured text")
        assert result["medications"] == []

    def test_additional_notes_carries_the_raw_text_truncated_to_500_chars(self):
        raw = "x" * 1000
        result = _fallback_extract(raw)
        assert result["additional_notes"] == "x" * 500

    def test_empty_raw_text_produces_empty_notes_not_a_crash(self):
        result = _fallback_extract("")
        assert result["additional_notes"] == ""
        assert result["medications"] == []

    def test_every_expected_key_is_present_with_a_safe_default(self):
        result = _fallback_extract("some text")
        assert result["doctor_name"] == ""
        assert result["date_of_visit"] is None
        assert result["complaint"] == ""
        assert result["diagnosis"] == ""
        assert result["child_age"] == ""
        assert result["child_weight"] == ""


class TestExtractPrescriptionFromText:
    async def test_a_well_formed_llm_response_is_used_directly(self, stub_openai):
        stub_openai.chat.completions.create = _chat_json(
            {
                "doctor_name": "Dr. Patel",
                "date_of_visit": "2026-06-01",
                "complaint": "cough",
                "diagnosis": "common cold",
                "medications": [
                    {"name": "Amoxicillin", "form": "Syrup", "dosage": "250mg", "frequency": "twice daily", "duration": "7 days"}
                ],
                "child_age": "4 years",
                "child_weight": "16kg",
                "additional_notes": "",
                "low_confidence": ["date_of_visit"],
            }
        )

        result = await extract_prescription_from_text("some ocr text")

        assert result["doctor_name"] == "Dr. Patel"
        assert result["date_of_visit"] == "2026-06-01"
        assert result["medications"][0]["name"] == "Amoxicillin"
        assert result["low_confidence"] == ["date_of_visit"]
        assert result["source_text"] == "some ocr text"

    async def test_malformed_json_falls_back_to_rule_based_extraction(self, stub_openai):
        async def _garbage(*args, **kwargs):
            from unittest.mock import AsyncMock

            resp = AsyncMock()
            resp.choices = [AsyncMock()]
            resp.choices[0].message.content = "this is not json"
            resp.usage = AsyncMock(prompt_tokens=10, completion_tokens=5)
            return resp

        stub_openai.chat.completions.create = _garbage

        result = await extract_prescription_from_text("Rx: Amoxicillin 250mg")

        assert result["medications"][0]["name"] == "Amoxicillin 250mg"
        assert result["doctor_name"] == ""

    async def test_the_chat_call_itself_failing_falls_back_too(self, stub_openai):
        async def _blow_up(*args, **kwargs):
            raise ConnectionError("openai unreachable")

        stub_openai.chat.completions.create = _blow_up

        result = await extract_prescription_from_text("Tab: Paracetamol")

        assert result["medications"][0]["name"] == "Paracetamol"

    async def test_non_string_low_confidence_entries_are_filtered_out(self, stub_openai):
        # A model that returns e.g. a number or object in this array
        # shouldn't be able to break the response shape the frontend expects.
        stub_openai.chat.completions.create = _chat_json(
            {
                "doctor_name": "",
                "date_of_visit": None,
                "complaint": "",
                "diagnosis": "",
                "medications": [],
                "child_age": "",
                "child_weight": "",
                "additional_notes": "",
                "low_confidence": ["doctor_name", 42, {"nested": "object"}, None],
            }
        )

        result = await extract_prescription_from_text("text")
        assert result["low_confidence"] == ["doctor_name"]

    async def test_missing_medication_fields_default_to_empty_strings(self, stub_openai):
        stub_openai.chat.completions.create = _chat_json(
            {
                "doctor_name": "",
                "date_of_visit": None,
                "complaint": "",
                "diagnosis": "",
                "medications": [{"name": "Amoxicillin"}],  # no form/dosage/frequency/duration
                "child_age": "",
                "child_weight": "",
                "additional_notes": "",
                "low_confidence": [],
            }
        )

        result = await extract_prescription_from_text("text")
        med = result["medications"][0]
        assert med == {
            "name": "Amoxicillin",
            "form": "",
            "dosage": "",
            "frequency": "",
            "duration": "",
        }


def _chat_json(data: dict):
    async def _create(*args, **kwargs):
        from unittest.mock import AsyncMock

        resp = AsyncMock()
        resp.choices = [AsyncMock()]
        resp.choices[0].message.content = json.dumps(data)
        resp.usage = AsyncMock(prompt_tokens=10, completion_tokens=5)
        return resp

    return _create
