import json
import os
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

# ---- settings ----
START_DATE = "2024-01-01"   # touches before this retire lines silently, no buy counted
LEFT, RIGHT = 2, 2          # weekly pivot bars
MAX_LINES = 50
QTY = 100
DATA = Path("data")
UNIVERSE_FILE = DATA / "nifty500.csv"
DOWNLOAD_BATCH_SIZE = 50
TIMEFRAMES = {
    "1 week": "W-FRI",
    "2 weeks": "2W-FRI",
    "1 month": "ME",
}

NIFTY500 = (
    pd.read_csv(UNIVERSE_FILE, usecols=["Symbol"])["Symbol"]
    .dropna()
    .str.strip()
    .drop_duplicates()
    .tolist()
)
if not NIFTY500:
    raise ValueError(f"No constituents found in {UNIVERSE_FILE}")


def weekly_pivots(df, left=LEFT, right=RIGHT, timeframe="1 week"):
    """Return [(activation_date, price)]. A line goes live the day after the
    pivot is confirmed (right timeframe bars later), matching the non-repainting logic."""
    w = df["Low"].resample(TIMEFRAMES[timeframe]).min().dropna()
    L, idx = w.values, w.index
    out = []
    for i in range(left, len(L) - right):
        if L[i] < L[i - left:i].min() and L[i] <= L[i + 1:i + 1 + right].min():
            out.append((idx[i + right], float(L[i])))
    return sorted(out)


def simulate(
    df,
    start_date=START_DATE,
    end_date=None,
    left=LEFT,
    right=RIGHT,
    quantity=QTY,
    max_lines=MAX_LINES,
    timeframe="1 week",
):
    pivots = weekly_pivots(df, left=left, right=right, timeframe=timeframe)
    start = pd.Timestamp(start_date) if start_date is not None else None
    end = pd.Timestamp(end_date) if end_date is not None else None
    lows, dates = df["Low"].values, df.index
    lines, buys, ignored, pi = [], [], 0, 0

    for t in range(len(df)):
        d = dates[t]
        while pi < len(pivots) and d > pivots[pi][0]:
            lines.append(pivots[pi][1])
            pi += 1
        lines = lines[-max_lines:]
        if t == 0:
            continue
        # Match the Pine crossover rule: today's low reaches the line after
        # yesterday's low was still above it.
        touched = [p for p in lines if lows[t] <= p < lows[t - 1]]
        if not touched:
            continue
        in_range = (start is None or d >= start) and (end is None or d <= end)
        if in_range:
            best = max(touched)
            buys.append({
                "date": d.strftime("%Y-%m-%d"),
                "price": float(best),
                "qty": quantity,
            })
            ignored += len(touched) - 1
        for p in touched:          # every touched line is used up
            lines.remove(p)
    return lines, buys, ignored


def notify(text):
    token, chat = os.getenv("TELEGRAM_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if token and chat:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      data={"chat_id": chat, "text": text}, timeout=15)


def main():
    DATA.mkdir(exist_ok=True)
    stocks, all_buys, all_prices = [], [], []
    batches = [
        NIFTY500[i:i + DOWNLOAD_BATCH_SIZE]
        for i in range(0, len(NIFTY500), DOWNLOAD_BATCH_SIZE)
    ]
    if len(batches) > 1 and len(batches[-1]) == 1:
        batches[-2].extend(batches.pop())

    for batch_number, symbols in enumerate(batches, start=1):
        tickers = [symbol + ".NS" for symbol in symbols]
        try:
            raw = yf.download(
                tickers,
                period="5y",
                interval="1d",
                group_by="ticker",
                auto_adjust=False,
                progress=False,
                threads=True,
            )
        except Exception as e:
            print(f"skip download batch {batch_number}/{len(batches)}: {e}")
            continue

        for sym in symbols:
            try:
                ticker = sym + ".NS"
                ticker_data = raw[ticker] if isinstance(raw.columns, pd.MultiIndex) else raw
                df = ticker_data[["Low", "High", "Close"]].dropna()
                df.index = pd.to_datetime(df.index).tz_localize(None)
                if len(df) < 100:
                    print(f"skip {sym}: only {len(df)} daily rows")
                    continue
                all_prices.append(pd.DataFrame({
                    "symbol": sym,
                    "date": df.index.strftime("%Y-%m-%d"),
                    "low": df["Low"].values,
                    "high": df["High"].values,
                    "close": df["Close"].values,
                }))
                lines, buys, ignored = simulate(df)
            except Exception as e:
                print(f"skip {sym}: {e}")
                continue

            close = float(df["Close"].iloc[-1])
            last = df.index[-1].strftime("%Y-%m-%d")
            below = sorted([p for p in lines if p < close], reverse=True)
            above = sorted([p for p in lines if p >= close])
            nxt = below[0] if below else None
            stocks.append({
                "symbol": sym, "close": round(close, 2), "last_date": last,
                "next_level": round(nxt, 2) if nxt else None,
                "dist_pct": round((close - nxt) / close * 100, 2)
                if nxt is not None else None,
                "levels_below": [round(p, 2) for p in below[:5]],
                "levels_above": [round(p, 2) for p in above[:3]],
                "buys": len(buys), "invalid": ignored,
                "signal_today": bool(buys) and buys[-1]["date"] == last,
            })
            all_buys += [{"symbol": sym, **b} for b in buys]

    if not stocks:
        raise SystemExit("No data downloaded; aborting without overwriting results.")

    latest = max(s["last_date"] for s in stocks)
    signals = [s for s in stocks if s["signal_today"] and s["last_date"] == latest]

    cols = ["symbol", "date", "price", "qty"]
    hist = pd.DataFrame(all_buys, columns=cols)
    hist.sort_values("date", ascending=False).to_csv(DATA / "signals.csv", index=False)
    pd.concat(all_prices, ignore_index=True).to_csv(DATA / "prices.csv", index=False)
    (DATA / "results.json").write_text(json.dumps(
        {"as_of": latest, "signals": [s["symbol"] for s in signals], "stocks": stocks}, indent=1))

    if signals:
        msg = [f"{s['symbol']}  close {s['close']}" for s in signals]
        notify(f"BUY signals {latest}\n" + "\n".join(msg))
    print(f"{latest}: {len(signals)} buy signal(s)")


if __name__ == "__main__":
    main()
