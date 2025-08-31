import argparse, os, itertools
import pandas as pd
from hft_mm_sim.config import MMConfig
from hft_mm_sim.data import load_csv
from hft_mm_sim.backtester import Backtester
from hft_mm_sim.analytics import save_heatmap

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--use_lob", action="store_true")
    ap.add_argument("--outdir", default="artifacts")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    plots_dir = os.path.join(args.outdir, "plots")
    os.makedirs(plots_dir, exist_ok=True)

    df = load_csv(args.csv)

    fees = [0, 3, 5, 7, 10]          # bps
    lats = [0, 5, 15, 30, 60]        # seconds
    slips = [0, 1, 2, 3]             # bps

    rows = []
    for fee, lat in itertools.product(fees, lats):
        cfg = MMConfig(fee_bps=fee, latency_sec=lat, use_lob=args.use_lob)
        bt = Backtester(cfg)
        res = bt.run(df)
        logs = res["logs"]
        final_equity = logs["equity"].iloc[-1] if len(logs) else 0.0
        rows.append({"fee_bps": fee, "latency_sec": lat, "final_equity": final_equity})

    stress = pd.DataFrame(rows)
    stress.to_csv(os.path.join(args.outdir, "stress_results.csv"), index=False)

    # heatmap (fee vs latency)
    piv = stress.pivot(index="latency_sec", columns="fee_bps", values="final_equity")
    save_heatmap(piv, "Final Equity vs Fee/Latency", os.path.join(plots_dir, "heatmap_equity_fee_latency.png"),
                 xlabel="fee_bps", ylabel="latency_sec")

    # Optional: slippage sweep vs latency
    rows2 = []
    for slip, lat in itertools.product(slips, lats):
        cfg = MMConfig(slippage_bps=slip, latency_sec=lat, use_lob=args.use_lob)
        bt = Backtester(cfg)
        res = bt.run(df)
        logs = res["logs"]
        final_equity = logs["equity"].iloc[-1] if len(logs) else 0.0
        rows2.append({"slippage_bps": slip, "latency_sec": lat, "final_equity": final_equity})
    stress2 = pd.DataFrame(rows2)
    stress2.to_csv(os.path.join(args.outdir, "stress_results_slip.csv"), index=False)

    piv2 = stress2.pivot(index="latency_sec", columns="slippage_bps", values="final_equity")
    save_heatmap(piv2, "Final Equity vs Slippage/Latency", os.path.join(plots_dir, "heatmap_equity_slip_latency.png"),
                 xlabel="slippage_bps", ylabel="latency_sec")

if __name__ == "__main__":
    main()
