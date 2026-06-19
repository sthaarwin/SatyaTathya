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
```

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
| 3. NLI (optional) | `DeBERTa-v3-base-mnli-fever-anli` | Free (local) | ~3s |
| 4. Gemini | Gemini 2.0/2.5 Flash | API cost | ~2s |

Toggle NLI with `USE_NLI_STANCE=true` in `.env`.

### Classical ML Models

Trained on `rexarski/climate_fever_fixed` (claim/evidence stance). Run:

```bash
source .venv/bin/activate
python scripts/download_climate_fever.py
python scripts/train_climate_fever_classical.py --save-models
```

Available model names: `logreg`, `svm`, `random_forest`, `xgb` (append `_rich` for richer TF-IDF features).

The `EnsembleVerifier` loads all available `.joblib` models and performs majority voting.

### Benchmark Results (200-row Climate-FEVER test set)

| Model | Accuracy | Macro F1 |
|-------|----------|----------|
| **EnsembleVerifier** (LogReg+SVM+RF) | **68.0%** | **0.619** |
| Heuristic | 63.0% | 0.290 |
| NLI DeBERTa-v3 (zero-shot) | 61.5% | 0.453 |

## Environment Variables

Key vars in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEYS` | — | Comma-separated Gemini keys (round-robin) |
| `USE_LLM_STANCE` | `true` | Enable Gemini stance classification |
| `USE_NLI_STANCE` | `true` | Enable local NLI model (DeBERTa-v3) |
| `NLI_MODEL_NAME` | `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` | HuggingFace NLI model |
| `RATE_LIMIT_ANALYZE` | `5/minute` | Rate limit for `/api/analyze` |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/analyze` | POST | Analyze a video URL |
| `/api/search` | POST | Search cached claims |
| `/api/stats` | GET | Cache statistics |
| `/api/health` | GET | Health check + model status |
| `/api/cache/clear` | POST | Clear all caches |
