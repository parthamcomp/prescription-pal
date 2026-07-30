# Prescription Assistant

A private prescription knowledge base with OCR and AI chat. Parents store their child's prescription records and ask natural-language questions over them.

> **Disclaimer:** This application summarizes your saved records only. It does not provide medical advice, dosing recommendations, or diagnoses. Always consult a qualified healthcare provider.

This project exists in two forms, built in two stages:

- **Part 1 — local, single-user.** Everything (LLM, embeddings, storage) runs on your machine with no cloud accounts. Preserved at the git tag [`v1.0`](../../releases/tag/v1.0) — the current `master` branch has since migrated to Part 2, so Part 1 is no longer what `docker compose up` on `master` gives you.
- **Part 2 — multi-user, production-shaped.** Real accounts (JWT auth), a real database (Postgres + pgvector), a background job queue (Redis + Arq), S3-compatible object storage, and OpenAI for chat/embeddings/extraction. This is what lives on `master` today.

Jump to: [Part 1 setup](#part-1--local-single-user-ollama) · [Part 2 setup](#part-2--multi-user-production-stack)

## Which one do I want?

| | Part 1 | Part 2 |
|---|---|---|
| Users | Single user, no login | Real accounts, email+password, JWT cookies |
| Storage | Flat JSON file (`data/prescriptions.json`) | Postgres |
| Search | ChromaDB + `sentence-transformers` (semantic only) | Postgres full-text + pgvector (hybrid, reciprocal rank fusion) |
| LLM / embeddings | Ollama, local (`llama3.2`) | OpenAI (`gpt-4o-mini` + `text-embedding-3-small`) |
| OCR pipeline | Synchronous, in the request | Async — upload returns a `job_id`, a worker processes it, frontend polls |
| Image storage | Not persisted (read once, discarded) | S3-compatible object storage (MinIO locally, R2/S3 in production) |
| Cost to run | Free (all local) | OpenAI usage-based billing |
| Good for | Trying the idea, fully offline use | Actually deploying this somewhere for more than one person |

Part 2 was built by hand-implementing the "Part 2 · Multi-User Production" design from `Prescription_Assistant_Implementation_Guide.html` (kept locally, not published to the remote).

---

## Part 1 — Local, Single-User (Ollama)

### Features

- **Upload & extract** — snap a photo of a prescription; Tesseract OCR pulls the text and a local LLM structures it into fields (doctor, date, diagnosis, medications, dosage, duration) for you to review and correct before saving.
- **Manual entry** — add records by hand without a photo.
- **Ask** — chat interface backed by semantic search (ChromaDB + sentence-transformers) over your saved records; the LLM answers from your data only.
- **Records** — browse everything you've saved.
- 100% offline — OCR, embeddings, and the LLM (Ollama) all run locally. Nothing leaves your machine.

### Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19 + Vite + TypeScript, served by nginx |
| Backend | FastAPI + uvicorn |
| OCR | Tesseract (inside the backend container) |
| LLM | Ollama, running `llama3.2` on the host machine |
| Vector search | ChromaDB + `sentence-transformers` (`all-MiniLM-L6-v2`) |
| Storage | Flat JSON file (`data/prescriptions.json`), mounted as a volume |
| Orchestration | Docker Compose |

### Architecture

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

Ollama is **not** containerized — it runs directly on your host machine, and the backend container reaches it via `host.docker.internal:11434`.

### Prerequisites

| Tool | Where to get it | Verify |
|---|---|---|
| Docker Desktop | [docker.com/products/docker-desktop](https://docker.com/products/docker-desktop) | `docker --version` |
| Ollama | [ollama.com/download](https://ollama.com/download) | `ollama list` |
| `llama3.2` model | `ollama pull llama3.2` | shows up in `ollama list` (~2 GB) |

### Install, configure, and run

```powershell
# 1. Clone the repo and check out the Part 1 snapshot
git clone <your-repo-url> prescription-assistant
cd prescription-assistant
git checkout v1.0

# 2. Make sure Ollama is running and has the model
ollama pull llama3.2
ollama list

# 3. Build and start everything
docker compose up --build
```

**First build note:** downloads base images plus the `sentence-transformers` embedding model (~90 MB) on first run — allow 10–20 minutes on a slow connection, and a few extra minutes on any rebuild unless you've added the Hugging Face cache volume described below.

Once it's up:

| URL | What you'll see |
|---|---|
| `http://localhost:3000` | The app — Ask / Records / Upload tabs |
| `http://localhost:8000/docs` | Swagger UI listing all backend routes |

To stop: `docker compose down` (your data in `./data` persists across restarts). When you're done and want the Part 2 code back: `git checkout master`.

### Configuration

Environment values are currently set directly in `docker-compose.yml` under the `backend` service. `.env.example` (at this tag) documents what each one means if you want to break them out into a real `.env` file:

| Variable | Default | Purpose |
|---|---|---|
| `DATA_DIR` | `/app/data` | Where prescription data lives inside the container |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Where the backend reaches Ollama on your host |
| `OLLAMA_MODEL` | `llama3.2` | Model used for both extraction and chat |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers model for semantic search |
| `CHROMA_COLLECTION` | `prescriptions` | ChromaDB collection name |

### Project Structure

```
prescription-assistant/
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── __init__.py
│       ├── config.py         # settings (paths, model names)
│       ├── models.py         # Pydantic schemas
│       ├── storage.py        # read/write prescriptions.json
│       ├── ocr.py            # image bytes -> text (Tesseract)
│       ├── extraction.py     # OCR text -> structured JSON (Ollama)
│       ├── rag.py            # vector search + chat answer (Ollama)
│       └── main.py           # FastAPI routes
├── frontend/
│   ├── Dockerfile             # multi-stage: npm build + nginx serve
│   ├── nginx.conf             # proxies /api to backend, SPA fallback
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx           # chat / records / upload UI
│       ├── api.ts            # fetch wrappers
│       ├── index.css
│       └── vite-env.d.ts
├── data/
│   └── prescriptions.json     # your records (persisted volume, gitignored)
├── docker-compose.yml
├── .env.example
└── .gitignore
```

### Customizations from the base build

- **`frontend/nginx.conf`** — the `/api/` location block sets `proxy_read_timeout`, `proxy_send_timeout`, and `proxy_connect_timeout` to `180s`. OCR + LLM extraction on a photo can take well past nginx's 60s default, which otherwise surfaces as a `504 Bad Gateway` in the browser even though the backend is still working.
- **`backend/app/rag.py`** — chat calls use Ollama's `/api/chat` endpoint with separate `system`/`user` messages, instead of one flat prompt to `/api/generate`. The system prompt explicitly frames answers as *reporting already-recorded history* rather than *giving medical advice*, which noticeably reduces the model refusing to state a dosage/duration that's already written in a saved record.
- **`docker-compose.yml`** — the backend service mounts an extra volume, `./data/hf-cache:/root/.cache/huggingface`, so the `sentence-transformers` embedding model persists across rebuilds instead of re-downloading (and delaying startup by several minutes) every time the backend image is rebuilt.

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Error loading ASGI app. Could not import module "app.main"` | `main.py` doesn't exist yet, or you ran `up`/`run` without overriding the default `uvicorn` command | Expected before `main.py` is created; otherwise use `docker compose run --rm backend python -c "..."` to bypass the default CMD |
| `ModuleNotFoundError` for a file you just added | Source is baked into the image at build time, not live-mounted | `docker compose build backend` (or `--no-cache` for a clean rebuild), then rerun |
| `invalid mount config ... mount path must be absolute` | Missing colon in a `volumes:` entry in `docker-compose.yml` | Should read `./data:/app/data`, not `./data/app/data` |
| `504 Bad Gateway` / Gateway Timeout on OCR | nginx's default 60s proxy timeout is shorter than OCR + LLM extraction can take | Increase `proxy_read_timeout` etc. in `nginx.conf` (see Customizations above), then `docker compose build frontend` |
| `connect() failed (111: Connection refused)` in nginx logs, backend unreachable | Backend container crashed on startup (often a syntax error after editing `rag.py`/`extraction.py`) | `docker compose logs backend` for the traceback; fix and `docker compose up --build backend` |
| Backend takes ~5 minutes to come up after a rebuild | Embedding model re-downloading because its cache isn't persisted | Add the `hf-cache` volume mount described above |
| Chat says "Ollama is unavailable" | Ollama isn't running, or wrong model name | `ollama list` to confirm `llama3.2` is present; make sure Ollama is running before `docker compose up` |
| `Invoke-RestMethod` shows nothing for `/api/prescriptions` | PowerShell prints nothing for an empty array — this is expected, not an error | Confirm with `(Invoke-WebRequest ...).Content` or `| ConvertTo-Json` |

---

## Part 2 — Multi-User Production Stack

### Features

Everything from Part 1, plus:

- **Accounts** — register/login with email+password, JWT access+refresh tokens in `HttpOnly` cookies, per-user data isolation.
- **Hybrid search** — pgvector cosine-distance vector search *and* Postgres full-text search (`tsvector`/GIN index), merged via reciprocal rank fusion, so exact drug/doctor-name matches aren't missed by pure embedding search.
- **Async OCR pipeline** — upload returns a `job_id` immediately; a separate worker process does OCR + extraction; the frontend polls `/api/jobs/{id}` instead of blocking the request.
- **Real object storage** — uploaded images persist to an S3-compatible bucket (MinIO locally, swap for Cloudflare R2/S3 in production) instead of being read once and discarded.
- **Graceful degradation without an API key** — chat falls back to full-text-only retrieval, extraction falls back to a regex-based parser, so the app stays usable (in a reduced way) if `OPENAI_API_KEY` is missing or the account has no credit.

### Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19 + Vite + TypeScript + React Router, served by nginx |
| Backend | FastAPI + uvicorn, async SQLAlchemy + Alembic |
| Worker | Arq (Redis-backed job queue) |
| Database | Postgres 16 + `pgvector` (`pgvector/pgvector:pg16` image) |
| OCR | Tesseract (inside the worker container) |
| LLM / embeddings | OpenAI (`gpt-4o-mini` for chat/extraction, `text-embedding-3-small` for embeddings) |
| Object storage | S3-compatible (MinIO locally; Cloudflare R2/S3 in production) |
| Auth | JWT access + refresh tokens, `HttpOnly` cookies, bcrypt password hashing |
| Orchestration | Docker Compose locally; `render.yaml` blueprint for Render in production |
| Local DB browser | Adminer (dev-only, **never expose publicly**) |

### Architecture

```
Browser (React SPA: Login / Register / Ask / Records / Upload / Profile)
   |  HTTP requests, credentials: include
   v
nginx (frontend container -- port 3000)
   |  /api/* proxied to backend, re-resolved via Docker DNS on every request
   v
FastAPI backend (port 8000)
   |
   +--[POST /api/auth/*]---------> bcrypt + JWT (HttpOnly access/refresh cookies)
   |
   +--[POST /api/ocr]------------> enqueue job (Redis) ---> Arq worker
   |                                                            |
   |                                            +---[Tesseract OCR]
   |                                            +---[OpenAI extraction, JSON mode]
   |                                            +---[object storage: image bytes]
   |                                                            |
   +--[GET /api/jobs/{id}]--------> Postgres (job status, polled by frontend)
   |
   +--[POST /api/prescriptions]---> Postgres (row) + OpenAI embedding -> pgvector
   |
   +--[POST /api/chat]------------> hybrid search (pgvector + full-text, RRF)
                                     -> OpenAI chat completion, context-grounded
```

### Prerequisites

| Tool | Where to get it | Verify |
|---|---|---|
| Docker Desktop | [docker.com/products/docker-desktop](https://docker.com/products/docker-desktop) | `docker --version` |
| An OpenAI API key with billing/credit enabled | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | starts with `sk-` |

No Node.js, Python, or Ollama needed locally — everything builds and runs inside Docker.

### Install, configure, and run

```powershell
# 1. Clone the repo (make sure you're on master, not the v1.0 tag)
git clone <your-repo-url> prescription-assistant
cd prescription-assistant
git checkout master

# 2. Configure environment
cp .env.example .env
# edit .env and paste your real key:
#   OPENAI_API_KEY=sk-...

# 3. Build and start everything
docker compose up --build
```

Alembic migrations (including `CREATE EXTENSION IF NOT EXISTS vector`) run automatically on backend startup — no manual migration step needed.

Once it's up:

| URL | What you'll see |
|---|---|
| `http://localhost:3000` | The app — register an account, then Ask / Records / Upload / Profile |
| `http://localhost:8000/docs` | Swagger UI listing all backend routes |
| `http://localhost:8080` | Adminer — browse the Postgres tables directly (see below) |
| `http://localhost:9001` | MinIO console — browse uploaded prescription images |

**Viewing the database:** `localhost:5432` is a raw Postgres port, not a webpage — opening it in a browser will error. Use Adminer at `localhost:8080` instead (System: `PostgreSQL`, Server: `db`, Username: `app`, Password: `app`, Database: `app`), or `docker compose exec db psql -U app -d app` for a terminal session. `users` and `prescriptions` (which includes the `embedding vector(1536)` column) are both plain tables there — pgvector is a Postgres extension, not a separate database.

To stop: `docker compose down` (Postgres/MinIO data persists in named volumes across restarts; `docker compose down -v` wipes them).

### Configuration

Everything is read from environment variables (`backend/app/config.py`), with local Docker Compose defaults baked into `docker-compose.yml` and only the OpenAI key expected in `.env`:

| Variable | Local default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | *(required, no default)* | Chat, extraction, and embeddings |
| `OPENAI_CHAT_MODEL` | `gpt-4o-mini` | Chat + structured extraction |
| `OPENAI_EMBED_MODEL` | `text-embedding-3-small` | Embeddings for hybrid search |
| `DATABASE_URL` | `postgresql+asyncpg://app:app@db:5432/app` | Postgres connection |
| `REDIS_URL` | `redis://redis:6379` | Arq job queue |
| `STORAGE_ENDPOINT` / `STORAGE_BUCKET` / `STORAGE_ACCESS_KEY` / `STORAGE_SECRET_KEY` | MinIO (`minioadmin`/`minioadmin`) | Object storage for uploaded images |
| `JWT_SECRET` | `dev-insecure-change-me` | **Must** be overridden in any real deployment |
| `ACCESS_TTL_MIN` / `REFRESH_TTL_DAYS` | 30 min / 14 days | Token lifetimes |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` | Allowed frontend origins |
| `ENFORCE_HTTPS` | `false` | Set `true` in production (redirects + HSTS) |
| `COOKIE_SECURE` | `false` | Set `true` in production (cookies only over HTTPS) |
| `COOKIE_SAMESITE` | `lax` | Use `none` if frontend and API are on different origins in production |
| `TRUSTED_HOSTS` | `*` | Comma-separated allow-list in production; `*` disables the check |

The local Postgres/MinIO/Adminer credentials above are dev-only defaults baked into `docker-compose.yml` — they are not meant to be reused anywhere reachable from the internet.

### Project Structure

```
prescription-assistant/
├── backend/
│   ├── Dockerfile              # API image: alembic upgrade head && uvicorn
│   ├── Dockerfile.worker       # worker image: Tesseract + arq
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/versions/       # 0001_init, 0002_hybrid_search, 0003_children
│   └── app/
│       ├── config.py           # env-driven settings
│       ├── db.py               # async SQLAlchemy session factory
│       ├── models_db.py        # ORM models (users, prescriptions, children, jobs)
│       ├── schemas.py          # Pydantic request/response models
│       ├── main.py             # FastAPI app, middleware, router wiring
│       ├── worker.py           # Arq task: OCR -> extraction
│       ├── queue.py            # Redis connection for enqueueing jobs
│       ├── auth/                # JWT issuing/verification, password hashing
│       ├── routers/             # auth, prescriptions, chat, ocr, jobs, children
│       ├── repositories/        # DB queries per entity (incl. hybrid search)
│       └── services/            # openai_client, embeddings, llm, rag, extraction,
│                                 # ocr (Tesseract), objects (S3/R2/MinIO), budget
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf               # proxies /api, re-resolves backend DNS
│   └── src/
│       ├── main.tsx             # routing + auth-gated Shell (keeps App mounted)
│       ├── App.tsx              # Ask / Records / Upload UI
│       ├── auth/AuthContext.tsx # login/register/refresh/logout state
│       ├── pages/                # Login, Register, Profile
│       └── api.ts               # fetch wrappers (VITE_API_URL for split-origin deploys)
├── docker-compose.yml           # db, redis, minio, backend, worker, frontend, adminer
├── render.yaml                  # Render blueprint for production deployment
├── .env.example
└── .gitignore
```

### Customizations and tuning notes

A handful of issues only showed up under real use and were fixed post-scaffold — worth knowing if you're extending this:

- **`frontend/nginx.conf`** — `proxy_pass` re-resolves the `backend` hostname on a 10s TTL against Docker's embedded DNS (`resolver 127.0.0.11`) instead of caching it once at nginx startup. Without this, restarting/recreating just the backend container (new internal IP) leaves nginx proxying to a dead address until the frontend container is also restarted — surfaces as a `502 Bad Gateway` on every API call. (A variable in `proxy_pass` also disables nginx's normal location-prefix rewriting, so the config explicitly appends `$request_uri` — otherwise every request collapses to a bare `/api/`.)
- **`backend/app/services/rag.py`** — the chat system prompt tells the model to judge each question by *whether the records contain relevant information*, not by how the question is phrased. Originally, "What medication for a cough?" would answer correctly but "What should I do if my child has a cough?" would refuse ("I don't have that information") even though the same record answered it — the model was treating advice-shaped phrasing as a request for medical advice. The prompt now explicitly treats those as equivalent, while still declining questions that ask for a genuinely new medical judgment the records never made (safety/interactions, whether something is an emergency, what to do if a documented treatment doesn't work).
- **`backend/app/services/rag.py` / `repositories/prescriptions.py`** — both the embedding call in chat and the extraction call are wrapped in try/except with fallbacks (full-text-only search; regex-based field extraction) instead of raising, so a missing/invalid/rate-limited `OPENAI_API_KEY` degrades the app rather than 500ing it.
- **`backend/app/models_db.py`** — `search_vector` is mapped with SQLAlchemy's `Computed(...)`, matching the Postgres `GENERATED ALWAYS ... STORED` column from the `0002_hybrid_search` migration. Without it, SQLAlchemy tries to INSERT an explicit `NULL` into a generated column and Postgres rejects the whole request.
- **`frontend/src/main.tsx`** — `/profile` used to be a fully separate top-level route, which unmounted the main `App` component (and its local chat/records/upload state) whenever you visited it. A `Shell` wrapper now keeps `App` mounted (hidden via CSS, not unmounted) while `/profile` is shown, so chat history and any in-progress work survive the round trip.
- **`docker-compose.yml`** — adds an `adminer` service (port `8080`) purely so the Postgres/pgvector tables can be browsed without a separate DB client. Local-dev convenience only; it ships with no auth of its own beyond the DB credentials, so it must never be part of a production deployment.

### Deploying to production

The stack is already env-driven and cloud-ready (CORS, cookie `SameSite`/`Secure`, HTTPS redirect, S3-compatible storage client are all wired up, not hardcoded to Docker Compose). `render.yaml` is a ready-to-use blueprint for the API + worker on [Render](https://render.com), backed by managed Postgres/Redis (or swap in Neon/Upstash by pointing the same env vars at external URLs). Pair it with:

- An S3-compatible bucket (Cloudflare R2 recommended — free egress) for `STORAGE_*`
- A static host (Cloudflare Pages, Vercel, Netlify) for the frontend, built with `VITE_API_URL` pointing at the deployed API
- `COOKIE_SAMESITE=none` once frontend and API are on different origins (same-origin nginx proxying, as used locally, can stay `lax`)

**Do not** deploy `docker-compose.yml` as-is to a public host — it includes Adminer and MinIO with default, publicly-known credentials, meant only for local development.

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `502 Bad Gateway` from nginx after restarting/rebuilding just the backend | Stale DNS resolution in nginx (see Customizations above) | Already fixed in current `nginx.conf`; if it recurs anyway, `docker compose restart frontend` |
| `Internal Server Error` on `POST /api/prescriptions` | Postgres rejecting an explicit `NULL` into the generated `search_vector` column | Already fixed (`Computed(...)` mapping in `models_db.py`); make sure you're on a current build |
| Chat says "No prescription records found" for a question that should match | Full-text search (`plainto_tsquery`) is AND-only across stemmed terms — one missing word can fail the match; only matters when the OpenAI key is absent/unusable, since vector search normally fills this gap | Expected limitation of full-text-only fallback, not a bug; add/verify `OPENAI_API_KEY` and confirm `has_embedding` is true on the record |
| Chat/extraction/embeddings feel "dumber" than expected (crude regex fields, raw-context dumps) | Missing or invalid `OPENAI_API_KEY`, or embedding calls failing | Both degrade gracefully by design — check `docker compose logs backend` for the underlying OpenAI error |
| `RateLimitError: insufficient_quota` in backend logs | Key is valid but the OpenAI account has no usable billing credit | Add credit / a payment method in the OpenAI billing dashboard, not a code issue |
| `401 Unauthorized` on a `curl` request that worked minutes ago | Access token TTL is 30 minutes; the browser frontend auto-refreshes via `api.ts`, but `curl` does not | Re-run `POST /api/auth/login` to get a fresh cookie jar |
| `localhost:5432` gives "there is a problem with this site" in a browser | Postgres speaks the wire protocol, not HTTP — a browser can't render it | Use Adminer (`localhost:8080`) or `psql` instead (see Configuration above) |
| `openai==1.59.0` (or similar) fails to install | That exact patch version was pulled from PyPI | Bump to the next available patch in `backend/requirements.txt` |
| Backend container won't start after a fresh `.env` change | Env vars are read at container start, not live | `docker compose up -d --force-recreate backend` (and `worker` if it also uses that var) |

### Known gaps

- The backend has a `children` API (`/api/children`) for grouping prescriptions per child, but the frontend never calls it — the Profile page only shows account details, not children. Left as-is for now; would need dedicated UI work.
- No rate limiting on `/api/auth/login` or `/api/auth/register` — fine for personal/family use behind a login wall, worth adding before wider public exposure.
- Adminer has no authentication of its own — never expose it (or MinIO's console) outside your local machine.

## License

Personal project — add a license here if you plan to open-source it.
