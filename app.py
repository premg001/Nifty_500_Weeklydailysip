from pathlib import Path

import pandas as pd
import streamlit as st

from scanner import LEFT, MAX_LINES, NIFTY500, QTY, RIGHT, START_DATE, simulate

st.set_page_config(page_title="Nifty 500 Levels", layout="wide")
price_path = Path("data/prices.csv")
if not price_path.exists():
    st.error("Cached price data not found. Run `python scanner.py` to download data first.")
    st.stop()

price_columns = set(pd.read_csv(price_path, nrows=0).columns)
if not {"symbol", "date", "low", "high", "close"}.issubset(price_columns):
    st.error("Cached prices need daily high/low data. Run `python scanner.py` to refresh them.")
    st.stop()

constituents = pd.read_csv(
    "data/nifty500.csv",
    usecols=["Symbol", "Company Name", "Market Cap"],
)
company_by_symbol = dict(zip(constituents["Symbol"], constituents["Company Name"]))
market_cap_by_symbol = dict(zip(constituents["Symbol"], constituents["Market Cap"]))


@st.cache_data(show_spinner=False)
def calculate_stocks(cache_version):
    cached_prices = pd.read_csv(price_path, parse_dates=["date"])
    rows = []

    for symbol, symbol_prices in cached_prices.groupby("symbol", sort=False):
        df = (
            symbol_prices.set_index("date")[["low", "high", "close"]]
            .rename(columns={"low": "Low", "high": "High", "close": "Close"})
            .sort_index()
        )
        lines, buys, ignored = simulate(
            df,
            start_date=START_DATE,
            end_date="2026-12-31",
            left=LEFT,
            right=RIGHT,
            quantity=QTY,
            max_lines=MAX_LINES,
        )
        close = float(df["Close"].iloc[-1])
        below = sorted((level for level in lines if level < close), reverse=True)
        next_level = below[0] if below else None
        last_date = df.index[-1].strftime("%Y-%m-%d")
        rows.append({
            "symbol": symbol,
            "close": close,
            "signal": bool(buys) and buys[-1]["date"] == last_date,
            "next_level": next_level,
            "change_pct": (next_level - close) / close * 100
            if next_level is not None else None,
        })

    return pd.DataFrame(rows)


stocks = calculate_stocks(price_path.stat().st_mtime_ns)
if stocks.empty:
    st.error("No price data is available.")
    st.stop()

stocks = (
    stocks.set_index("symbol")
    .reindex(NIFTY500)
    .rename_axis("symbol")
    .reset_index()
)
stocks["signal"] = stocks["signal"].fillna(False)
stocks["market_cap"] = stocks["symbol"].map(market_cap_by_symbol)

st.subheader("All stocks: CMP, signal, and levels below")
search_term = st.text_input("Search stock", placeholder="Symbol or company name")
if search_term:
    symbol_matches = stocks["symbol"].str.contains(
        search_term, case=False, regex=False, na=False
    )
    company_matches = stocks["symbol"].map(company_by_symbol).str.contains(
        search_term, case=False, regex=False, na=False
    )
    stocks = stocks[symbol_matches | company_matches]

stocks["signal"] = stocks["signal"].map({True: "BUY", False: "—"})
stocks = stocks.rename(
    columns={
        "symbol": "Stock",
        "close": "CMP",
        "signal": "Signal",
        "next_level": "Next level below",
        "change_pct": "% Change to next level",
        "market_cap": "Market cap",
    }
)
stocks["CMP"] = stocks["CMP"].map(
    lambda price: f"{price:,.2f}" if pd.notna(price) else "—"
)
stocks["Next level below"] = stocks["Next level below"].map(
    lambda price: f"{price:,.2f}" if pd.notna(price) else "—"
)
stocks["% Change to next level"] = stocks["% Change to next level"].map(
    lambda change: f"{change:.2f}%" if pd.notna(change) else "—"
)
stocks = stocks[
    [
        "Stock",
        "CMP",
        "Signal",
        "Next level below",
        "% Change to next level",
        "Market cap",
    ]
].sort_values("Stock")
st.dataframe(stocks, hide_index=True, width="stretch")
