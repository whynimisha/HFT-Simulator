import argparse, os, json
import pandas as pd

TEMPLATE = """# HFT Market-Making Simulation — Report

## Summary Metrics
{metrics_table}

## Key Plots
- Equity Curve: `plots/equity_curve.png`
- Equity & Inventory Overlay: `plots/equity_inventory_overlay.png`
- Quotes vs Mid: `plots/quotes_vs_mid.png`
- PnL Attribution (lines): `plots/pnl_attribution_stacked.png`
- Attribution Bars: `plots/attribution_bars.png`
- Stress Heatmaps:
  - `plots/heatmap_equity_fee_latency.png`
  - `plots/heatmap_equity_slip_latency.png`

## Files
- Logs: `equity_curve.csv`
- Trades: `trades.csv`
- Walk-Forward: `walk_forward.csv` (if run)
- Stress: `stress_results.csv` (if run)
- Attribution Summary: `plots/attribution_summary.csv`
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", default="artifacts")
    ap.add_argument("--out", default="artifacts/report.md")
    args = ap.parse_args()

    plots_dir = os.path.join(args.artifacts, "plots")
    metrics_path = os.path.join(plots_dir, "metrics.csv")

    if os.path.exists(metrics_path):
        m = pd.read_csv(metrics_path)
        metrics_table = m.to_markdown(index=False)
    else:
        metrics_table = "_No metrics.csv found_"

    report = TEMPLATE.format(metrics_table=metrics_table)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Wrote {args.out}")

if __name__ == "__main__":
    main()
