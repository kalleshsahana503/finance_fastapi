"""
app.py — the Streamlit UI. This file does NOT do any analysis itself.
It only asks api.py for already-computed results and draws them.

EDA --> Dataset       : finance_transactions.csv (read by api.py)
Python --> EDA        : pandas code lives in api.py, not here
FastAPI --> endpoints : api.py, started below as its own process
Streamlit --> UI      : this file — every chart is call_api() + a plot

Run with: streamlit run app.py
(You do NOT need to separately run api.py — this file starts it for
you automatically, as a real independent process, the first time the
dashboard loads.)
"""

import os
import subprocess
import sys
import time
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
import plotly.express as px

API_HOST = "127.0.0.1"
API_PORT = 8000
API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
_HERE = os.path.dirname(os.path.abspath(__file__))
API_SCRIPT = os.path.join(_HERE, "api.py")

st.set_page_config(page_title="Finance Analytics Dashboard", layout="wide", page_icon="💰")


@st.cache_resource
def start_api_process():
    """Starts api.py as its own separate process (not a thread inside
    this one) using the same Python interpreter Streamlit is running
    under. @st.cache_resource means this only happens once for the
    whole life of the app, no matter how many times the script reruns
    when you touch a filter."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api:app", "--host", API_HOST, "--port", str(API_PORT)],
        cwd=_HERE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Wait for the API to actually be ready, instead of guessing with a
    # fixed sleep — try for up to 10 seconds.
    for _ in range(50):
        try:
            requests.get(f"{API_BASE_URL}/", timeout=0.5)
            break
        except requests.exceptions.ConnectionError:
            time.sleep(0.2)
    return proc


start_api_process()


def call_api(endpoint: str, params: dict = None):
    try:
        r = requests.get(f"{API_BASE_URL}{endpoint}", params=params or {}, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Could not reach the API at {endpoint}: {e}")
        return None


# ==================================================================
# SIDEBAR STYLING — a blue "Filters" badge + red rounded filter pills,
# on top of Streamlit's normal widgets (no functionality changes,
# just CSS applied to the same multiselect/date/slider widgets below).
# ==================================================================
st.markdown("""
<style>
/* The blue "Filters" header badge */
.filters-badge {
    background-color: #3B5BDB;
    color: white;
    padding: 10px 18px;
    border-radius: 10px;
    font-size: 22px;
    font-weight: 700;
    margin-bottom: 18px;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* Selected chips inside every sidebar multiselect */
section[data-testid="stSidebar"] span[data-baseweb="tag"] {
    background-color: #FF5C5C !important;
    border-radius: 20px !important;
}
section[data-testid="stSidebar"] span[data-baseweb="tag"] span {
    color: white !important;
    font-weight: 600 !important;
}

/* White rounded card behind each multiselect's chip area */
section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
    background-color: white !important;
    border-radius: 14px !important;
    border: 1px solid #e3e3e3 !important;
    padding: 4px !important;
}

/* Date input box, same rounded white card look */
section[data-testid="stSidebar"] div[data-baseweb="input"] {
    border-radius: 10px !important;
}
</style>
""", unsafe_allow_html=True)


# ==================================================================
# SIDEBAR FILTERS
# ==================================================================
st.sidebar.markdown('<div class="filters-badge">🔎 Filters</div>', unsafe_allow_html=True)

opts = call_api("/filter-options") or {
    "categories": [], "cities": [], "payment_methods": [],
    "min_date": None, "max_date": None,
}

st.sidebar.subheader("Date range")
if opts["min_date"] and opts["max_date"]:
    date_range = st.sidebar.date_input(
        "Date range", label_visibility="collapsed",
        value=(pd.to_datetime(opts["min_date"]).date(), pd.to_datetime(opts["max_date"]).date()),
        min_value=pd.to_datetime(opts["min_date"]).date(),
        max_value=pd.to_datetime(opts["max_date"]).date(),
    )
else:
    date_range = None

st.sidebar.subheader("Category")
sel_categories = st.sidebar.multiselect(
    "Category", label_visibility="collapsed",
    options=opts["categories"], default=opts["categories"],
)

st.sidebar.subheader("City")
sel_cities = st.sidebar.multiselect(
    "City", label_visibility="collapsed",
    options=opts["cities"], default=opts["cities"],
)

st.sidebar.subheader("Payment method")
sel_methods = st.sidebar.multiselect(
    "Payment method", label_visibility="collapsed",
    options=opts["payment_methods"], default=opts["payment_methods"],
)

st.sidebar.caption(f"Backend API: {API_BASE_URL}  \n(try {API_BASE_URL}/docs in a new tab)")
z_thresh = st.sidebar.slider("Anomaly sensitivity (z-score)", 1.5, 4.0, 2.5, 0.1)

# Every call_api(...) below passes these same filters, so every chart
# reflects whatever is currently selected in the sidebar.
active_filters = {
    "category": ",".join(sel_categories) if sel_categories else None,
    "city": ",".join(sel_cities) if sel_cities else None,
    "payment_method": ",".join(sel_methods) if sel_methods else None,
}
if date_range and isinstance(date_range, tuple) and len(date_range) == 2:
    active_filters["start_date"] = str(date_range[0])
    active_filters["end_date"] = str(date_range[1])


def call_api_filtered(endpoint: str, extra_params: dict = None):
    params = {**active_filters, **(extra_params or {})}
    params = {k: v for k, v in params.items() if v is not None}
    return call_api(endpoint, params=params)


# ==================================================================
# STREAMLIT DASHBOARD — everything below is display only
# ==================================================================
st.title("💰 Finance Analytics Dashboard")
st.caption("CSV → FastAPI (analysis, as its own process) → Streamlit (UI only)")

summ = call_api_filtered("/summary")
if summ:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Income", f"₹{summ['total_income']:,.0f}")
    c2.metric("Total Expense", f"₹{summ['total_expense']:,.0f}")
    c3.metric("Net Savings", f"₹{summ['net_savings']:,.0f}")
    c4.metric("Savings Rate", f"{summ['savings_rate_pct']}%")
    c5.metric("Avg Transaction", f"₹{summ['avg_transaction']:,.0f}")

st.divider()

tab_overview, tab_trends, tab_category, tab_merchants, tab_anomaly, tab_data = st.tabs(
    ["📊 Overview", "📈 Trends", "🧾 Category Deep-Dive", "🏪 Merchants & Cities",
     "🚨 Anomaly Detection", "📋 Raw Data"]
)

with tab_overview:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Spend by Category")
        cat = call_api_filtered("/category-breakdown")
        if cat:
            fig = px.pie(pd.DataFrame(cat), names="category", values="amount", hole=0.35)
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.subheader("Essential vs Lifestyle")
        el = call_api_filtered("/essential-vs-lifestyle")
        if el:
            fig = px.pie(pd.DataFrame(el), names="subcategory", values="amount", hole=0.35,
                         color="subcategory",
                         color_discrete_map={"Essential": "#4C78A8", "Lifestyle": "#F58518"})
            st.plotly_chart(fig, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        st.subheader("Payment Method Split")
        pm = call_api_filtered("/payment-method-split")
        if pm:
            fig = px.bar(pd.DataFrame(pm), x="payment_method", y="amount")
            st.plotly_chart(fig, use_container_width=True)
    with col4:
        st.subheader("Spending by Weekday")
        wd = call_api_filtered("/weekday-pattern")
        if wd:
            fig = px.bar(pd.DataFrame(wd), x="weekday", y="amount")
            st.plotly_chart(fig, use_container_width=True)

with tab_trends:
    trend_data = call_api_filtered("/monthly-trend")
    if trend_data:
        tdf = pd.DataFrame(trend_data)
        st.subheader("Monthly Income vs Expense")
        fig = px.line(tdf, x="month", y=["Income", "Expense"], markers=True)
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Cumulative Savings Over Time")
        fig2 = px.area(tdf, x="month", y="Cumulative Savings")
        st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Monthly Net (Income − Expense)")
        fig3 = px.bar(tdf, x="month", y="Net", color=tdf["Net"] > 0,
                      color_discrete_map={True: "#54A24B", False: "#E45756"})
        fig3.update_layout(showlegend=False)
        st.plotly_chart(fig3, use_container_width=True)

with tab_category:
    st.subheader("Category Spend Over Time (Heatmap)")
    hm = call_api_filtered("/category-month-heatmap")
    if hm:
        hdf = pd.DataFrame(hm)
        pivot = hdf.pivot(index="category", columns="month", values="amount").fillna(0)
        fig = px.imshow(pivot, aspect="auto", color_continuous_scale="Blues",
                         labels=dict(x="Month", y="Category", color="Amount (₹)"))
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Category Treemap")
    cat = call_api_filtered("/category-breakdown")
    if cat:
        fig = px.treemap(pd.DataFrame(cat), path=["category"], values="amount")
        st.plotly_chart(fig, use_container_width=True)

with tab_merchants:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Top 10 Merchants")
        m = call_api_filtered("/top-merchants", extra_params={"limit": 10})
        if m:
            fig = px.bar(pd.DataFrame(m), x="amount", y="merchant", orientation="h")
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.subheader("Spend by City")
        c = call_api_filtered("/city-breakdown")
        if c:
            fig = px.bar(pd.DataFrame(c), x="city", y="amount")
            st.plotly_chart(fig, use_container_width=True)

with tab_anomaly:
    st.subheader("Unusually Large Transactions")
    st.caption("A transaction is flagged if it's far above the typical amount for its own "
               "category (z-score ≥ your sidebar threshold).")
    anom = call_api_filtered("/anomalies", extra_params={"z_thresh": z_thresh})
    if anom:
        if len(anom) == 0:
            st.success("No anomalies at this sensitivity — try lowering the z-score slider.")
        else:
            adf = pd.DataFrame(anom)
            st.dataframe(adf, use_container_width=True, height=350)
            fig = px.scatter(adf, x="date", y="amount", color="category", size="z_score",
                              hover_data=["merchant", "city"])
            st.plotly_chart(fig, use_container_width=True)

with tab_data:
    st.subheader("All Transactions")
    txns = call_api_filtered("/transactions", extra_params={"limit": 2000})
    if txns:
        tdf = pd.DataFrame(txns)
        st.dataframe(tdf, use_container_width=True, height=420)
        st.download_button(
            "⬇️ Download data as CSV",
            data=tdf.to_csv(index=False),
            file_name=f"finance_data_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

st.divider()
st.caption(f"FastAPI does the analysis, running separately at {API_BASE_URL} — Streamlit only displays it.")
