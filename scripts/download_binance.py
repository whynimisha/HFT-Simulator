import argparse, os, time
import pandas as pd
import ccxt

def fetch_ohlcv_all(exchange, symbol, timeframe='1m', since=None, limit=1000, max_batches=1000, sleep_s=0.2):
    all_rows = []
    now = exchange.milliseconds()
    if since is None:
        # ~ last 24h default if no since; but we’ll iterate forward
        since = now - 24 * 60 * 60 * 1000

    for _ in range(max_batches):
        batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit)
        if not batch:
            break
        all_rows += batch
        # advance 'since'
        since = batch[-1][0] + 1
        time.sleep(sleep_s)
        # safety stop (about 30 days for 1m * 1000 * batches)
        if len(all_rows) >= limit * max_batches:
            break
    return all_rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTC/USDT")  # Binance symbol
    ap.add_argument("--timeframe", default="1m")
    ap.add_argument("--out", default="data/BTC-USD_1m.csv")  # we’ll write in your required schema
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    ex = ccxt.binance()
    ms_per_day = 24*60*60*1000
    since = ex.milliseconds() - args.days * ms_per_day

    rows = fetch_ohlcv_all(ex, args.symbol, timeframe=args.timeframe, since=since, limit=1000)
    if not rows:
        raise SystemExit("No OHLCV returned. Try fewer days or different symbol.")

    df = pd.DataFrame(rows, columns=["time","open","high","low","close","volume"])
    df["time"] = pd.to_datetime(df["time"], unit="ms")
    # ensure numeric
    for c in ["open","high","low","close","volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna().sort_values("time")

    df.to_csv(args.out, index=False)
    print(f"Wrote {len(df)} rows to {args.out} with columns {list(df.columns)}")

if __name__ == "__main__":
    main()
