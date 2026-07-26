# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Multiple caregivers sharing one household's local instance — parents, and potentially grandparents or other regular caregivers — who together manage prescription records for their children. The app has no accounts or login; whoever is at the machine or phone is "the user," so the UI must read as shared family infrastructure, not a personalized single-owner tool.

Primary job: after a doctor's visit or pharmacy trip, quickly get a prescription (paper or photographed) into a searchable record, and later recall what was prescribed, when, by whom, and for what — often mid-conversation with a doctor, pharmacist, or the other caregiver.

## Product Purpose

A fully local, private knowledge base for a family's prescription history. Parents/caregivers upload a photo of a prescription (or enter one manually); OCR plus a local LLM extract it into structured fields for review; the app then answers natural-language questions over the saved records (dosages, diagnoses, doctors, dates) via retrieval-augmented chat. Success is a caregiver trusting the record enough to ask "what was my kid prescribed for the ear infection in the spring?" and get a fast, accurate answer sourced from their own saved data.

It explicitly does not give medical advice, dosing guidance, or diagnoses — it only reports back what was already recorded.

## Positioning

Runs entirely on the caregiver's own machine — OCR, embeddings, and the LLM (Ollama) all execute locally, with no cloud account, API key, or data leaving the device. Where mainstream health-record apps require signing up with a cloud health platform, this is the private, offline alternative built for a single household's own devices.

## Operating Context

- Used in bursts around real medical events: right after a pharmacy visit (photographing a paper prescription), during a doctor's appointment (checking history on a phone while talking to the doctor), or at home reviewing/organizing records.
- Even split between desktop (calmer review/management sessions) and phone (in-the-moment capture and lookup) — both must feel fully native, not adapted-from-desktop.
- Runs via Docker Compose on the household's own hardware; Ollama runs on the host, not in a container. No internet dependency once set up.
- Photographed prescriptions are frequently imperfect (glare, handwriting, angle) — OCR output and extracted fields are a first draft the caregiver reviews and corrects before saving, not a final answer.

## Capabilities and Constraints

- Upload & OCR extraction (photo → structured draft: doctor, date, diagnosis, medications with dosage/frequency/duration) with a manual-entry fallback.
- Ask: RAG chat strictly over the household's own saved records — never general medical knowledge.
- Records: browse, view, and delete saved prescriptions.
- No authentication, no per-user accounts, no per-user data isolation — this is a single shared local data store by design.
- No cloud services, no telemetry, no external API keys.
- Must never read as giving medical advice, dosing recommendations, or diagnoses — only as recalling what a doctor already recorded.
- Single-user/household scale (not built for many simultaneous users or large record volumes).

## Brand Commitments

None fixed. The current name ("Prescription Assistant") and mark (a text "Rx" glyph) are placeholders, not binding — naming and mark are open to reconsideration as part of establishing a stronger visual identity.

## Evidence on Hand

No real prescriptions, testimonials, screenshots of real patient data, or case studies exist or may be fabricated — all example/demo content must be clearly fictional placeholder data (e.g. `data/prescriptions.example.json`). No existing logo file or brand asset beyond the in-app "Rx" text mark.

## Product Principles

1. Trust through transparency: every answer should be traceable to a saved record; never blur into medical advice.
2. Calm under real stress: caregivers use this while tired, at a pharmacy counter, or mid-appointment — clarity and speed beat cleverness.
3. Shared, not personal: the interface belongs to the household, not one named user — avoid single-owner framing.
4. Private by construction: local-only operation is a promise the UI should visibly reinforce, not just a backend fact.
5. First draft, human-verified: OCR/LLM extraction is always presented as editable and provisional, never as authoritative until the caregiver confirms it.

## Accessibility & Inclusion

No accessibility requirement was specified by the user beyond general good practice; treat as standard WCAG AA expectations given the caregiver demographic (adults of varying ages, sometimes reading a phone screen in a pharmacy or doctor's office under poor lighting or while distracted).
