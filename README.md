# SatyaTathya
Tiktok news autheticity checker.

## Classical ML Baseline

The backend includes a standalone Climate-FEVER experiment for comparing classical claim/evidence stance classifiers against the heuristic and LLM-based verification methods.

Install backend dependencies:

```bash
cd backend
pip install -r requirements.txt
```

Run Logistic Regression, Linear SVM, Random Forest, and richer tuned variants:

```bash
cd ..
python backend/scripts/download_climate_fever.py
python backend/scripts/train_climate_fever_classical.py --save-models
```

The stronger `_rich` variants combine:

- pair-level word TF-IDF
- pair-level character TF-IDF
- separate claim TF-IDF
- separate evidence TF-IDF
- engineered overlap and keyword features

The script uses `rexarski/climate_fever_fixed` by default and maps labels to:

- `SUPPORT`
- `CONTRADICT`
- `INDETERMINATE`

Downloaded data is written to `backend/data/climate_fever/`. Training outputs are written to `backend/models/`, including `climate_fever_classical_results.json` and optional `.joblib` model files.
