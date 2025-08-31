import os, argparse, itertools, numpy as np, pandas as pd
from hft_mm_sim.data import load_csv, synthetic_minute
from hft_mm_sim.config import MMConfig
from hft_mm_sim.backtester import Backtester

def final_equity(logs: pd.DataFrame):
    if logs is None or logs.empty or 'equity' not in logs:
        return np.nan
    return float(logs['equity'].iloc[-1])

def run_with(cfg, df_slice):
    bt = Backtester(cfg)
    res = bt.run(df_slice)
    return final_equity(res['logs']), res

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', type=str, default='')
    ap.add_argument('--train_len', type=int, default=2000)
    ap.add_argument('--test_len', type=int, default=1000)
    ap.add_argument('--outcsv', type=str, default='artifacts/walk_forward.csv')
    args = ap.parse_args()

    if args.csv and os.path.exists(args.csv):
        df = load_csv(args.csv)
    else:
        df = synthetic_minute(minutes=args.train_len + args.test_len + 1000)

    rows = []
    grid = {
        'k_vol': [0.3, 0.5, 0.8],
        'k_inv': [0.01, 0.02, 0.05],
        'latency_sec': [0, 30, 60],
    }

    total = len(df)
    step = args.test_len
    for start in range(0, total - (args.train_len + args.test_len), step):
        train = df.iloc[start : start + args.train_len]
        test  = df.iloc[start + args.train_len : start + args.train_len + args.test_len]

        # Tune on train
        best = None
        best_score = -np.inf
        for k_vol, k_inv, latency in itertools.product(grid['k_vol'], grid['k_inv'], grid['latency_sec']):
            cfg = MMConfig(k_vol=k_vol, k_inv=k_inv, latency_sec=latency)
            score, _ = run_with(cfg, train)
            if np.isnan(score):
                continue
            if score > best_score:
                best_score = score
                best = (k_vol, k_inv, latency)

        # Evaluate on test
        if best is None:
            continue
        k_vol, k_inv, latency = best
        cfg = MMConfig(k_vol=k_vol, k_inv=k_inv, latency_sec=latency)
        oos_score, res = run_with(cfg, test)

        rows.append({
            'train_start': train.index[0],
            'train_end': train.index[-1],
            'test_start': test.index[0],
            'test_end': test.index[-1],
            'k_vol': k_vol,
            'k_inv': k_inv,
            'latency_sec': latency,
            'train_final_equity': float(best_score),
            'test_final_equity': float(oos_score),
            'test_trades': len(res['trades'])
        })

    os.makedirs(os.path.dirname(args.outcsv), exist_ok=True)
    pd.DataFrame(rows).to_csv(args.outcsv, index=False)
    print(f"Wrote walk-forward results to {args.outcsv}")

if __name__ == '__main__':
    main()
