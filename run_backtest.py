import os
import argparse
import pandas as pd

from hft_mm_sim.config import MMConfig
from hft_mm_sim.data import load_csv, synthetic_minute  # synthetic is used only if --csv missing
from hft_mm_sim.backtester import Backtester
from hft_mm_sim.analytics import (
    save_equity_plot,
    save_inventory_plot,
    save_quotes_plot,
    save_markouts_and_attribution,
    plot_attribution_stacked,
)

def _print_df_info(df: pd.DataFrame, label: str):
    print(f"[INFO] {label}: rows={len(df)}, cols={list(df.columns)}")
    if len(df) > 0:
        try:
            print(f"[INFO] {label}: time range: {df.index.min()} -> {df.index.max()}")
        except Exception:
            pass

def parse_args():
    ap = argparse.ArgumentParser(description="HFT MM backtest runner")
    ap.add_argument(
        "--csv",
        type=str,
        default="",
        help="Path to 1m CSV with columns: time,open,high,low,close,volume",
    )
    ap.add_argument("--fee_bps", type=float, default=5.0)
    ap.add_argument("--latency_sec", type=int, default=30)
    ap.add_argument("--inv_cap", type=float, default=10.0)
    ap.add_argument("--base_size", type=float, default=1.0)
    ap.add_argument("--k_vol", type=float, default=0.5)
    ap.add_argument("--k_inv", type=float, default=0.02)
    ap.add_argument("--k_mom", type=float, default=0.05)
    ap.add_argument("--high_activity", action="store_true", help="Apply high-activity trading preset")
    ap.add_argument(
        "--outdir",
        type=str,
        default="artifacts",
        help="Directory to write outputs (CSVs/plots). Defaults to 'artifacts/'",
    )
    return ap.parse_args()

def main():
    args = parse_args()

    # Build config from CLI (any other fields are taken from config.py defaults)
    cfg = MMConfig(
        fee_bps=args.fee_bps,
        latency_sec=args.latency_sec,
        inv_cap=args.inv_cap,
        base_size=args.base_size,
        k_vol=args.k_vol,
        k_inv=args.k_inv,
        k_mom=args.k_mom,
    )
    # after cfg = MMConfig(...):
    from hft_mm_sim.config import apply_high_activity_preset
    if args.high_activity:
        cfg = apply_high_activity_preset(cfg)

    # Load data
    if args.csv and os.path.exists(args.csv):
        df = load_csv(args.csv)
        _print_df_info(df, f"loaded: {args.csv}")
    else:
        print("[WARN] --csv not provided or file missing; using synthetic minute data.")
        df = synthetic_minute(minutes=600, seed=cfg.seed)
        _print_df_info(df, "synthetic_minute")

    # Backtest
    bt = Backtester(cfg)
    res = bt.run(df)
    logs: pd.DataFrame = res["logs"]
    trades: pd.DataFrame = res["trades"]

    # Ensure outdir exists
    os.makedirs(args.outdir, exist_ok=True)
    plots_dir = os.path.join(args.outdir, "plots")
    os.makedirs(plots_dir, exist_ok=True)

    # Save CSVs
    logs.to_csv(os.path.join(args.outdir, "equity_curve.csv"))
    trades.to_csv(os.path.join(args.outdir, "trades.csv"), index=False)
    logs.to_csv(os.path.join(args.outdir, "logs.csv"), index=False)

    # Plots + attribution
    save_equity_plot(logs, plots_dir)
    save_inventory_plot(logs, plots_dir)
    save_quotes_plot(logs, plots_dir)
    save_markouts_and_attribution(
        logs, trades, plots_dir, horizons=MMConfig().markout_horizons
    )
    # Stacked PnL attribution (spread vs. markout vs. fees)
    plot_attribution_stacked(
        logs, os.path.join(plots_dir, "trades_with_markouts.csv"), plots_dir
    )

    # Summary
    n_logs = 0 if logs is None else len(logs)
    n_trades = 0 if trades is None else len(trades)
    print(f"Finished. Wrote {n_trades} trades and {n_logs} log rows to {args.outdir}")

if __name__ == "__main__":
    main()
