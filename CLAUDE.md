# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A fully local, private prescription knowledge base with OCR and AI chat. Parents store their child's prescription records and ask natural-language questions over them. Everything runs locally/in Docker — no cloud accounts, no API keys. It summarizes saved records only; it does not give medical advice.

[Prescription_Assistant_Implementation_Guide.html](Prescription_Assistant_Implementation_Guide.html) is the from-scratch tutorial this codebase was built from. Its "Part 1" appendices are the origin of every file under `backend/` and `frontend/` today (the code has since diverged slightly — see "Known tuning" below). Its "Part 2 · Multi-User Production" is a fully designed but **unimplemented** migration path to a multi-user cloud deployment — see "Documented production migration path" below. Treat the guide as reference material, not as something to keep in sync with the code.

## Commands

Everything runs through Docker Compose; there is no requirement to have Node or Python installed on the host.

```powershell
# Start everything (requires Ollama running on the host with `llama3.2` pulled)
docker compose up --build

# Rebuild a single service after changing its source
docker compose build backend
docker compose build frontend

# Tail logs / diagnose a crashed container
docker compose logs backend

# Bypass the default uvicorn CMD to run a one-off command in the backend image
docker compose run --rm backend python -c "..."

# Stop (data in ./data persists)
docker compose down
```

Frontend-only commands (if working inside `frontend/` with Node installed locally):
```bash
npm run dev       # vite dev server
npm run build      # tsc -b && vite build
npm run preview
```

There is no test suite and no lint config in this repo currently — don't assume `npm test`/`pytest`/`ruff` exist.

Once running: app UI at `http://localhost:3000`, Swagger UI for backend routes at `http://localhost:8000/docs`.

## Architecture

```
Browser (React SPA)
   |  HTTP requests
   v
nginx (frontend container -- port 3000)
   |  /api/* proxied internally
   v
FastAPI backend (port 8000 -- internal only)
   |
   +--[POST /api/ocr]-----------> Tesseract OCR   (inside backend image)
   |                                 v  raw text
   +--[extraction.py]-----------> Ollama on host  (:11434)
   |                                 v  structured JSON
   +--[storage.py]---------------> prescriptions.json  (volume: ./data)
   |
   +--[rag.py]--------------------> ChromaDB  (persisted in ./data/chroma/)
   |                                 v  embeddings (sentence-transformers)
   +--[POST /api/chat]-----------> Ollama on host  (:11434, chat API)
```

**Ollama runs on the host, not in a container** — the backend reaches it via `host.docker.internal:11434` (see `OLLAMA_BASE_URL` in `docker-compose.yml`). This is the one piece of infra you can't `docker compose up` your way into; it must be started and have `llama3.2` pulled separately.

### Backend (`backend/app/`)

Single FastAPI app (`main.py`) wired to four modules, each owning one concern:

- `storage.py` — `PrescriptionStore`, a flat-file CRUD layer over `data/prescriptions.json` (module-level singleton `store`). Every record is a `Prescription` (see `models.py`). No database.
- `ocr.py` — `extract_text_from_image()`, a thin `pytesseract` wrapper. Image bytes in, raw text out.
- `extraction.py` — turns raw OCR text into a structured `Prescription` by prompting Ollama's `/api/generate` with `format: json`. If Ollama is unreachable or returns unparseable JSON, falls back to `_fallback_extract()`, a regex-based best-effort parser (looks for `Rx:`/`Tab:`/`Syrup:` patterns and date-like substrings). Both paths always return a `Prescription`, never raise to the caller.
- `rag.py` — `PrescriptionRAG` (singleton `rag`). Embeds every prescription as a flattened text document via `sentence-transformers` and indexes it in a persistent ChromaDB collection at `data/chroma/`. `rebuild_index()` fully replaces the collection contents (delete-all then re-add) rather than diffing — cheap enough at this scale, but means every write triggers a full re-embed of all records. `answer()` retrieves top-k matches and asks Ollama's `/api/chat` (system+user messages, not `/api/generate`) to answer strictly from that context.

**Index consistency**: `main.py` calls `rag.rebuild_index(store.list_all())` (aliased `_reindex()`) on app startup and after every create/update/delete. The vector index is treated as a derived cache of the JSON store, not a source of truth — if the two ever diverge, `POST /api/reindex` rebuilds it from `prescriptions.json`.

**Both Ollama-calling modules degrade gracefully**: `extraction.py` falls back to regex extraction; `rag.answer()` falls back to dumping raw retrieved context if the chat call fails. Neither raises an unhandled exception when Ollama is down — preserve this pattern if you touch either.

**System prompt framing** (`rag.py`): the chat system prompt deliberately frames answers as *reporting already-recorded history* rather than *giving medical advice* — this was tuned to stop the model from refusing to state a dosage/duration that's already written in a saved record. Keep this framing if you edit the prompt; a more clinical-sounding prompt tends to reintroduce refusals.

Settings (`config.py`) are a `pydantic_settings.BaseSettings` reading from env vars / `.env` — `data_dir`, `ollama_base_url`, `ollama_model`, `embedding_model`, `chroma_collection`. In Docker these are currently set directly in `docker-compose.yml` under the `backend` service rather than via `.env`.

### Frontend (`frontend/src/`)

Small React 19 + TypeScript app, no router or state library — `App.tsx` holds all view state (Ask / Records / Upload tabs) and `api.ts` is a thin fetch wrapper (`prescriptionsApi`) mirroring the backend routes 1:1. Types in `api.ts` (`Prescription`, `Medication`, `OCRResult`, `ChatMessage`) should be kept in sync with `backend/app/models.py` by hand — there's no shared schema/codegen between the two.

Built by nginx multi-stage Docker build; `nginx.conf` proxies `/api/*` to the backend container and serves the SPA for everything else.

### Known tuning that isn't obvious from the code alone

- `frontend/nginx.conf` sets `proxy_read_timeout`/`proxy_send_timeout`/`proxy_connect_timeout` to `180s` — OCR + LLM extraction on a photo can exceed nginx's 60s default, which otherwise surfaces as a `504` in the browser even though the backend is still working.
- `docker-compose.yml` mounts `./data/hf-cache:/root/.cache/huggingface` so the `sentence-transformers` embedding model persists across backend rebuilds instead of re-downloading on every `docker compose build backend` (adds several minutes otherwise).

### Current scope / known gaps

This is a single-user, local-only app by design. No auth, no per-user data isolation, storage is a flat JSON file (not a real DB), OCR+extraction run synchronously in-request, no HTTPS/secrets management. Don't add multi-user or cloud-deployment scaffolding unless explicitly asked — it's out of scope for the current design.

### Documented production migration path (not implemented in this repo)

The implementation guide's "Part 2 · Multi-User Production" spells out — in full source form, appendices included — how this app would be turned into a public multi-user product. None of it exists in `backend/app/` today (no `models_db.py`, `schemas.py`, `auth/`, `worker.py`, etc.); it's a reference design, not in-progress work. If a task calls for moving toward multi-user/cloud, consult the guide's Part 2 rather than re-deriving the approach:

- **Storage**: `prescriptions.json` → Postgres via async SQLAlchemy + Alembic, every table scoped by `user_id`.
- **Vectors**: ChromaDB full-rebuild-on-write → pgvector, incremental upsert per record, `cosine_distance` query filtered by user, combined with Postgres full-text search (generated `tsvector` + GIN index) via reciprocal rank fusion — because pure embedding search misses exact drug/doctor-name/dosage strings.
- **LLM/embeddings**: Ollama (local) → OpenAI (`gpt-4o-mini` for chat, `text-embedding-3-small` for embeddings), gated by a per-request token budget so a large OCR dump can't silently run up cost.
- **OCR pipeline**: inline/blocking in the request → async, via an Arq worker over Redis; upload returns a `job_id` immediately, frontend polls `/api/jobs/{id}`.
- **Uploads**: read-then-discarded → persisted to object storage (S3/R2/MinIO).
- **Auth**: none → JWT access+refresh tokens in `HttpOnly` cookies, bcrypt password hashing, a `get_current_user` FastAPI dependency injected into every data route.
- **Infra**: Postgres on Neon, Redis on Upstash, storage on Cloudflare R2, API+worker on Render (`render.yaml` blueprint), frontend on the existing nginx container or a static host — all wired through env vars documented in the guide's Setup chapters.
- **Security specifics worth knowing if this path is ever taken**: cookies use `SameSite=lax` only when frontend and API share an origin (the nginx proxy setup); a split-origin deployment (SPA on Vercel, API on Render) requires `SameSite=none` + `Secure=true` or auth silently breaks. Prescription fields are deliberately *not* encrypted at the column level — RAG needs plaintext to embed and to send as LLM context, so encrypting them would break search; the design relies on provider-level encryption at rest (Neon/Upstash/R2) plus TLS everywhere instead.
