import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import itertools, os, argparse, numpy as np, pandas as pd
from hft_mm_sim.config import MMConfig
from hft_mm_sim.data import load_csv, synthetic_minute
from hft_mm_sim.backtester import Backtester

def summarize(logs: pd.DataFrame):
    if logs.empty or 'equity' not in logs:
        return {'final_equity': np.nan, 'sharpe': np.nan, 'max_drawdown': np.nan}
    eq = logs['equity'].astype(float)
    rets = eq.diff().fillna(0.0)
    vol = rets.std()
    sharpe = (rets.mean() / vol) * np.sqrt(1440) if vol > 0 else np.nan  # approx per-day scaling
    max_dd = (eq.cummax() - eq).max()
    return {'final_equity': float(eq.iloc[-1]), 'sharpe': float(sharpe), 'max_drawdown': float(max_dd)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', type=str, default='')
    ap.add_argument('--outcsv', type=str, default='artifacts/grid_search.csv')
    args = ap.parse_args()

    if args.csv and os.path.exists(args.csv):
        df = load_csv(args.csv)
    else:
        df = synthetic_minute(minutes=600, seed=42)

    grid = {
        'k_vol': [0.3, 0.5, 0.8],
        'k_inv': [0.01, 0.02, 0.05],
        'latency_sec': [0, 30, 60]
    }

    rows = []
    for k_vol, k_inv, latency in itertools.product(grid['k_vol'], grid['k_inv'], grid['latency_sec']):
        cfg = MMConfig(k_vol=k_vol, k_inv=k_inv, latency_sec=latency)
        bt = Backtester(cfg)
        res = bt.run(df)
        summ = summarize(res['logs'])
        summ.update({'k_vol': k_vol, 'k_inv': k_inv, 'latency_sec': latency, 'trades': len(res['trades'])})
        rows.append(summ)

    os.makedirs(os.path.dirname(args.outcsv), exist_ok=True)
    pd.DataFrame(rows).to_csv(args.outcsv, index=False)
    print(f"Wrote grid search results to {args.outcsv}")

if __name__ == '__main__':
    main()
