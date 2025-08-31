import argparse, os
import pandas as pd
import yfinance as yf

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTC-USD")
    ap.add_argument("--period", default="5d")       # 1m supports ~5-7 days
    ap.add_argument("--interval", default="1m")     # try 1h if 1m is empty
    ap.add_argument("--out", default="data/BTC-USD_1m.csv")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    df = yf.download(args.symbol, period=args.period, interval=args.interval, progress=False)
    if df is None or df.empty:
        raise SystemExit("Downloaded DataFrame is empty. Try different --period/--interval.")

    df = df.reset_index()  # expose Datetime/Date as a column

    # Normalize columns to required schema
    rename_map = {
        "Datetime": "time",
        "Date": "time",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "close",   # fallback if Close missing
        "Volume": "volume",
    }
    df = df.rename(columns=rename_map)

    keep = ["time", "open", "high", "low", "close", "volume"]
    present = [c for c in keep if c in df.columns]
    if "time" not in present:
        # last fallback: create 'time' from index we just reset
        df.insert(0, "time", pd.to_datetime(df.iloc[:,0], errors="coerce"))
        present = [c for c in keep if c in df.columns or c == "time"]

    df = df[present]
    df["time"] = pd.to_datetime(df["time"], errors="coerce")

    # coerce numerics only if present
    for col in ["open","high","low","close","volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            print(f"[WARN] Column {col} not found after rename.")

    df = df.dropna().sort_values("time")
    if df.empty:
        raise SystemExit("All rows dropped after cleaning. Try --period 3d or --interval 1h.")

    df.to_csv(args.out, index=False)
    print(f"Wrote {len(df)} rows to {args.out} with columns {list(df.columns)}")

if __name__ == "__main__":
    main()
