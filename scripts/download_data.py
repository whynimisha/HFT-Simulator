import argparse
import pandas as pd
from datetime import datetime, timedelta

def try_yfinance(symbol, start, end, interval):
    import yfinance as yf
    df = yf.download(tickers=symbol, start=start, end=end, interval=interval, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0].lower() for c in df.columns]
    else:
        df.columns = [c.lower() for c in df.columns]
    df = df.rename(columns={'adj close':'close'})
    df = df[['open','high','low','close','volume']].dropna()
    df.index.name = 'time'
    df = df.reset_index()
    return df

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--symbol', required=True)
    ap.add_argument('--start', required=True)
    ap.add_argument('--end', required=True)
    ap.add_argument('--interval', default='1m')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    try:
        df = try_yfinance(args.symbol, args.start, args.end, args.interval)
    except Exception as e:
        raise SystemExit(f"yfinance download failed: {e}")

    df.to_csv(args.out, index=False)
    print(f"Wrote {len(df)} rows to {args.out}")

if __name__ == '__main__':
    main()
