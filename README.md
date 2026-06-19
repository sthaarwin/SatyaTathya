# SatyaTathya

TikTok/news video fact-checking system targeting Nepali-language and Nepal-related misinformation.

## Architecture

```
Video URL → Download → Visual fingerprint → Gemini analysis → Claim extraction
                                                                    ↓
                                              Claim verification pipeline:
                                                heuristic (fast, local)
                                                    ↓ if uncertain
                                                NLI model (accurate, local)
                                                    ↓ if uncertain  
                                                Gemini (most accurate, API)

                                              Results cached in:
                                                Local SQLite (primary)
                                                Supabase (shared, survives redeploy)

                                              Frontend (Next.js):
                                                Auth with Supabase
                                                User analysis history
```

## Tech Stack

- **Backend**: FastAPI (Python), SQLite + Supabase (Postgres), HuggingFace NLI, Gemini API
- **Frontend**: Next.js 16 (App Router), Supabase Auth, Tailwind CSS
- **Caching**: Dual-write (local SQLite + shared Supabase tables)

## Backend

### Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # add your API keys
```

### Run

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Verification Pipeline

The pipeline has four tiers, each falling through to the next when confidence is low:

| Tier | Model | Cost | Speed |
|------|-------|------|-------|
| 1. Heuristic | Keyword + embedding similarity | Free | ~10ms |
| 2. Classical Ensemble | LogReg + SVM + RF (or XGBoost) majority vote | Free | ~50ms |
| 3. NLI (zero-shot) | `facebook/bart-large-mnli` | Free (local) | ~3s |
| 4. Gemini | Gemini 2.0/2.5 Flash | API cost | ~2s |

Toggle NLI with `USE_NLI_STANCE=true` in `.env`. Zero-shot labels: `supports this claim`, `contradicts this claim`, `unrelated`.

### Classical ML Models

Trained on `rexarski/climate_fever_fixed` (claim/evidence stance). Run:

```bash
source .venv/bin/activate
python scripts/download_climate_fever.py
python scripts/train_climate_fever_classical.py --save-models
```

Available model names: `logreg`, `svm`, `random_forest`, `xgb` (append `_rich` for richer TF-IDF features).

The `EnsembleVerifier` loads all available `.joblib` models and performs majority voting.

### Evidence Scraping

Sources are scraped from a curated list of trusted domains (`backend/data/trusted_sources.json`). The search uses short 4-keyword queries with DuckDuckGo, with automatic broadening fallback when fewer than 4 results are returned.

## Frontend

### Setup

```bash
cd frontend
cp .env.local.example .env.local  # add Supabase credentials
npm install
```

### Run

```bash
npm run dev
```

### Auth

Authentication is handled by Supabase with a cookie-based server-side session:

- `middleware.ts` checks `sb-access-token` cookie on protected routes
- `page.tsx` (server component) reads cookie before rendering Dashboard
- Auth pages at `/auth`, `/auth/callback`
- Logout clears cookies and redirects to `/auth`

## Supabase Setup

1. Create a Supabase project
2. Run `backend/supabase_migration.sql` in the Supabase SQL editor to create tables:
   - `analysis_cache` (public read/write — shared cache)
   - `verification_cache` (public read/write — shared cache)
   - `user_analyses` (per-user RLS — personal history)
3. Copy Supabase URL and keys to both `backend/.env` and `frontend/.env.local`

## Environment Variables

### Backend (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEYS` | — | Comma-separated Gemini keys (round-robin) |
| `USE_LLM_STANCE` | `true` | Enable Gemini stance classification |
| `USE_NLI_STANCE` | `true` | Enable local NLI model |
| `NLI_MODEL_NAME` | `facebook/bart-large-mnli` | HuggingFace zero-shot NLI model |
| `RATE_LIMIT_ANALYZE` | `5/minute` | Rate limit for `/api/analyze` |
| `SUPABASE_URL` | — | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | — | Supabase service role key |

### Frontend (`.env.local`)

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anonymous key |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key |
| `NEXT_PUBLIC_SITE_URL` | Frontend URL (e.g. `http://localhost:3000`) |
| `NEXT_PUBLIC_API_URL` | Backend API URL (e.g. `http://127.0.0.1:8000`) |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/analyze` | POST | Analyze a video URL |
| `/api/search` | POST | Search cached claims |
| `/api/stats` | GET | Cache statistics |
| `/api/sources` | GET | List trusted sources with credibility weights |
| `/api/health` | GET | Health check + model status |
| `/api/cache/clear` | POST | Clear all caches |
| `/api/auth/signup` | POST | Create a new account |
| `/api/auth/login` | POST | Sign in |
| `/api/auth/logout` | POST | Sign out (clears cookies) |
| `/api/auth/user` | GET | Current user info |
| `/api/auth/google` | GET | Google OAuth redirect |
| `/api/analyses/save` | POST | Save analysis to user history |
| `/api/analyses/list` | GET | List user's analyses |
| `/api/analyses/clear` | POST | Clear user's analysis history |
