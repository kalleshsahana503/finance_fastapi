"""
api.py — the FastAPI backend.

EDA --> Dataset : finance_transactions.csv
Python --> EDA  : the pandas code inside each endpoint below
FastAPI --> endpoints : this file turns each EDA result into a URL

This file is a normal, standalone FastAPI app. It knows nothing about
Streamlit. You can even test it completely on its own:

    uvicorn api:app --port 8000

...then open http://127.0.0.1:8000/docs in a browser to try every
endpoint by hand. Keeping this file independent of Streamlit is what
avoids the port/threading problems from the combined-file version —
this always runs as its own separate process, the same way it would
in a real company's setup.
"""

import os
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ------------------------------------------------------------------
# DATASET — find the CSV next to this file
# ------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(_HERE, "finance_transactions.csv")


def load_data() -> pd.DataFrame:
    """Reads the CSV fresh each call. Simple and correct; the dataset
    is small (a few thousand rows) so re-reading it costs almost
    nothing, and it means every endpoint always reflects the current
    file on disk with no caching to think about."""
    df = pd.read_csv(DATA_PATH, parse_dates=["date"])
    df["month"] = df["date"].dt.to_period("M").astype(str)
    df["weekday"] = df["date"].dt.day_name()
    return df


def apply_filters(
    df: pd.DataFrame,
    category: Optional[str] = None,
    city: Optional[str] = None,
    payment_method: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """Every filterable endpoint calls this the same way. Each filter
    arrives as a comma-separated string (e.g. "Rent,Travel") because
    that's easy to pass in a URL — None/empty means "no filter on
    this field, keep everything." """
    if category:
        df = df[df["category"].isin(category.split(","))]
    if city:
        df = df[df["city"].isin(city.split(","))]
    if payment_method:
        df = df[df["payment_method"].isin(payment_method.split(","))]
    if start_date:
        df = df[df["date"] >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df["date"] <= pd.to_datetime(end_date)]
    return df


# Shared query parameters every filterable endpoint accepts. FastAPI
# lets us define these once and reuse them with `Depends(...)` so we
# don't repeat the same 5 parameters on every single function.
def filter_params(
    category: Optional[str] = None,
    city: Optional[str] = None,
    payment_method: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    return dict(category=category, city=city, payment_method=payment_method,
                start_date=start_date, end_date=end_date)


app = FastAPI(title="Finance Analytics API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/")
def root():
    return {"status": "ok", "message": "Finance Analytics API is running"}


@app.get("/filter-options")
def filter_options():
    """Gives Streamlit the distinct values to populate the sidebar
    multiselects with, and the overall date range for the date picker."""
    df = load_data()
    return {
        "categories": sorted(df["category"].unique().tolist()),
        "cities": sorted(df["city"].unique().tolist()),
        "payment_methods": sorted(df["payment_method"].unique().tolist()),
        "min_date": df["date"].min().strftime("%Y-%m-%d"),
        "max_date": df["date"].max().strftime("%Y-%m-%d"),
    }


@app.get("/summary")
def summary(filters: dict = Depends(filter_params)):
    df = apply_filters(load_data(), **filters)
    income = df.loc[df.type == "Income", "amount"].sum()
    expense = df.loc[df.type == "Expense", "amount"].sum()
    net = income - expense
    return {
        "total_income": round(float(income), 2),
        "total_expense": round(float(expense), 2),
        "net_savings": round(float(net), 2),
        "savings_rate_pct": round(float(net / income * 100), 2) if income else 0,
        "avg_transaction": round(float(df["amount"].mean()), 2) if len(df) else 0,
        "transaction_count": int(len(df)),
    }


@app.get("/monthly-trend")
def monthly_trend(filters: dict = Depends(filter_params)):
    df = apply_filters(load_data(), **filters)
    trend = (df.groupby(["month", "type"])["amount"].sum()
             .reset_index().pivot(index="month", columns="type", values="amount")
             .fillna(0).reset_index().sort_values("month"))
    for col in ("Income", "Expense"):
        if col not in trend.columns:
            trend[col] = 0
    trend["Net"] = trend["Income"] - trend["Expense"]
    trend["Cumulative Savings"] = trend["Net"].cumsum()
    return trend.to_dict(orient="records")


@app.get("/category-breakdown")
def category_breakdown(filters: dict = Depends(filter_params)):
    df = apply_filters(load_data(), **filters)
    exp = df[df.type == "Expense"]
    return (exp.groupby("category")["amount"].sum()
            .sort_values(ascending=False).reset_index()).to_dict(orient="records")


@app.get("/category-month-heatmap")
def category_month_heatmap(filters: dict = Depends(filter_params)):
    df = apply_filters(load_data(), **filters)
    exp = df[df.type == "Expense"]
    pivot = exp.groupby(["month", "category"])["amount"].sum().reset_index()
    return pivot.to_dict(orient="records")


@app.get("/payment-method-split")
def payment_method_split(filters: dict = Depends(filter_params)):
    df = apply_filters(load_data(), **filters)
    exp = df[df.type == "Expense"]
    return exp.groupby("payment_method")["amount"].sum().reset_index().to_dict(orient="records")


@app.get("/essential-vs-lifestyle")
def essential_vs_lifestyle(filters: dict = Depends(filter_params)):
    df = apply_filters(load_data(), **filters)
    exp = df[df.type == "Expense"]
    return exp.groupby("subcategory")["amount"].sum().reset_index().to_dict(orient="records")


@app.get("/weekday-pattern")
def weekday_pattern(filters: dict = Depends(filter_params)):
    df = apply_filters(load_data(), **filters)
    exp = df[df.type == "Expense"]
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    out = exp.groupby("weekday")["amount"].sum().reindex(order).fillna(0).reset_index()
    return out.to_dict(orient="records")


@app.get("/top-merchants")
def top_merchants(limit: int = 10, filters: dict = Depends(filter_params)):
    df = apply_filters(load_data(), **filters)
    exp = df[df.type == "Expense"]
    return (exp.groupby("merchant")["amount"].sum().sort_values(ascending=False)
            .head(limit).reset_index()).to_dict(orient="records")


@app.get("/city-breakdown")
def city_breakdown(filters: dict = Depends(filter_params)):
    df = apply_filters(load_data(), **filters)
    exp = df[df.type == "Expense"]
    return exp.groupby("city")["amount"].sum().sort_values(ascending=False).reset_index().to_dict(orient="records")


@app.get("/anomalies")
def anomalies(z_thresh: float = 2.5, filters: dict = Depends(filter_params)):
    df = apply_filters(load_data(), **filters)
    exp = df[df.type == "Expense"].copy()
    stats = exp.groupby("category")["amount"].agg(["mean", "std"]).rename(
        columns={"mean": "cat_mean", "std": "cat_std"})
    exp = exp.join(stats, on="category")
    exp["cat_std"] = exp["cat_std"].replace(0, np.nan)
    exp["z_score"] = (exp["amount"] - exp["cat_mean"]) / exp["cat_std"]
    flagged = exp[exp["z_score"] >= z_thresh].sort_values("z_score", ascending=False)
    cols = ["transaction_id", "date", "category", "amount", "merchant", "city", "z_score"]
    flagged = flagged[cols].copy()
    flagged["date"] = flagged["date"].dt.strftime("%Y-%m-%d")
    flagged["z_score"] = flagged["z_score"].round(2)
    return flagged.to_dict(orient="records")


@app.get("/transactions")
def transactions(limit: int = 500, filters: dict = Depends(filter_params)):
    df = apply_filters(load_data(), **filters).sort_values("date", ascending=False).head(limit)
    return df.drop(columns=["month", "weekday"]).to_dict(orient="records")


if __name__ == "__main__":
    # Lets you run just the API by itself: python api.py
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
