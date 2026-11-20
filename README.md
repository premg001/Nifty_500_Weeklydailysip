# Nifty 500 Weekly Green Line Levels

Daily EOD scanner + Streamlit UI. Weekly pivot lows (2 left / 2 right) become green lines.
The Pine-compatible touch rule is a daily low at or below a line after the prior daily low
was above it. The first crossing uses up the line; at most one buy per stock per day, with
the highest crossed line selected.

## Run locally
    pip install -r requirements.txt
    python scanner.py
    streamlit run app.py

The scanner reads constituents from `data/nifty500.csv`, downloads daily data in batches,
and saves it to `data/prices.csv`. The UI contains the all-stocks CMP, signal,
upcoming-level, and market-cap category table, with search by symbol or company name.
Large/Mid/Small categories come from the corresponding official Nifty 100, Midcap 150,
and Smallcap 250 constituent lists. Run `python scanner.py` to refresh prices and EOD results.

## Deploy
1. Push this folder to a GitHub repo.
2. share.streamlit.io -> new app -> main file `app.py`.
3. GitHub Actions (`.github/workflows/eod.yml`) runs weekdays at 5:00 PM IST and commits `data/`.
4. Optional Telegram alerts: add repo secrets `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID`.
5. First run: Actions tab -> "EOD scan" -> Run workflow.

## Notes
- Edit `START_DATE`, `QTY`, `MAX_LINES` at the top of `scanner.py`.
- Refresh `data/nifty500.csv` from the official Nifty Indices site after index rebalances.
