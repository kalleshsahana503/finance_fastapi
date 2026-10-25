# 💰 Finance Analytics Dashboard

A finance data analytics project built with **Python + FastAPI + Streamlit**.
This README explains the project simply enough to walk your colleagues
through it in a few minutes.

## What this project does

It takes 3 years of finance transactions (income + expenses) and turns
them into an interactive dashboard: trends, category breakdowns, top
merchants, spending patterns, and automatic anomaly detection.

## Files

| File | Purpose |
|---|---|
| `finance_transactions.csv` | The dataset — 1,220 transactions (2023–2025) |
| `api.py` | The FastAPI backend — reads the CSV, does all the pandas analysis, exposes it as endpoints |
| `app.py` | The Streamlit dashboard — calls `api.py` and draws the charts |
| `README.md` | This file |

## The code flow, in plain words

```
  CSV FILE  →  api.py (FastAPI)     →  app.py (Streamlit)
  (data)       pandas does the EDA,     calls each endpoint,
               each result becomes      draws the result as
               one endpoint             a chart
```

This maps directly onto the four-part structure you may have seen
described elsewhere:

- **Dataset** → `finance_transactions.csv`
- **Python → EDA** → the pandas code inside every function in `api.py`
  (`.groupby()`, `.sum()`, the z-score anomaly calculation, etc.)
- **FastAPI → endpoints** → every `@app.get(...)` in `api.py` — each
  one is a URL that returns the result of one piece of analysis as JSON
- **Streamlit → UI** → `app.py` — it never touches the CSV or does any
  analysis itself; it only calls the endpoints and draws what comes back

## Why two files instead of one

`api.py` and `app.py` are genuinely separate programs. When you run
`streamlit run app.py`, it automatically starts `api.py` for you as
its own independent process (not a background thread inside the same
process) — this is the same setup real teams use, and it's what makes
the two parts reliable: the dashboard and the backend can't interfere
with each other's ports, because they're two full, separate programs
talking over a normal HTTP connection, exactly like a browser talking
to any website.

You can also run `api.py` completely on its own to test it in
isolation:
```bash
uvicorn api:app --port 8000
```
Then open `http://127.0.0.1:8000/docs` — FastAPI automatically builds
an interactive page there where you can try every endpoint by hand and
see the raw JSON each one returns, with no dashboard involved at all.

## What's in the dashboard

- **Overview** — category split, essential vs lifestyle, payment
  methods, weekday spending pattern
- **Trends** — income vs expense over time, cumulative savings, monthly
  net (surplus/deficit)
- **Category Deep-Dive** — a heatmap of category spend by month, and a
  treemap
- **Merchants & Cities** — top merchants, spend by city
- **Anomaly Detection** — automatically flags transactions that are
  unusually large for their category (adjustable sensitivity slider)
- **Raw Data** — the full dataset, with a CSV download button

## How to run it

```bash
pip install streamlit fastapi uvicorn pandas plotly numpy requests
streamlit run app.py
```

Open the URL it prints (usually `http://localhost:8501`). You do NOT
need to separately start `api.py` — `app.py` starts it for you
automatically the first time it loads.

All three files (`api.py`, `app.py`, `finance_transactions.csv`) need
to be in the same folder.

## Talking points for your presentation

- "The dataset is 3 years of realistic transactions — income, rent,
  EMIs, everyday spending — with a few deliberately unusual
  transactions mixed in."
- "The backend (`api.py`) and the frontend (`app.py`) are two
  completely separate programs that talk over HTTP — the same pattern
  a real company would use if multiple apps needed to share one
  backend."
- "The anomaly detector uses a z-score: how many standard deviations a
  transaction is above the normal amount for its category — a
  standard first-pass technique for spotting outliers."
- "You can open `api.py`'s `/docs` page on its own to show the backend
  working independently of the dashboard."
