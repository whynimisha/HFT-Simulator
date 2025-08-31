import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)

def save_equity_plot(logs: pd.DataFrame, out_dir: str):
    ensure_dir(out_dir)
    if logs is None or logs.empty or 'equity' not in logs:
        return
    plt.figure()
    logs['equity'].plot()
    plt.title('Equity Curve')
    plt.xlabel('Time')
    plt.ylabel('Equity')
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'equity_curve.png'))
    plt.close()

def save_inventory_plot(logs: pd.DataFrame, out_dir: str):
    ensure_dir(out_dir)
    if logs is None or logs.empty or 'inventory' not in logs:
        return
    plt.figure()
    logs['inventory'].plot()
    plt.title('Inventory Over Time')
    plt.xlabel('Time')
    plt.ylabel('Inventory')
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'inventory.png'))
    plt.close()

# NEW: quotes vs mid
def save_quotes_plot(logs: pd.DataFrame, out_dir: str):
    ensure_dir(out_dir)
    if logs is None or logs.empty:
        return
    cols = [c for c in ['mid', 'bid', 'ask'] if c in logs.columns]
    if not cols:
        return
    plt.figure()
    logs[cols].plot()
    plt.title('Quoted Prices vs. Mid')
    plt.xlabel('Time')
    plt.ylabel('Price')
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'quotes_vs_mid.png'))
    plt.close()

# NEW: per-trade mark-outs and attribution CSVs
def save_markouts_and_attribution(logs: pd.DataFrame,
                                  trades: pd.DataFrame,
                                  out_dir: str,
                                  horizons=(1, 5, 10)):
    ensure_dir(out_dir)
    if logs is None or trades is None or logs.empty or trades.empty:
        return

    df = trades.copy()
    if 'liquidity' not in df.columns:
        df['liquidity'] = 'maker'

    mids = logs[['mid']].copy()
    mids.index.name = 'time'
    df = df.merge(mids.rename(columns={'mid': 'mid_t'}),
                  left_on='time', right_index=True, how='left')

    # Spread edge at fill
    df['spread_edge'] = np.where(
        df['side'].eq('buy'),
        df['mid_t'] - df['price'],
        df['price'] - df['mid_t']
    )

    # Mark-outs
    for h in horizons:
        col = f'mid_t_plus_{h}'
        mids_lead = mids['mid'].shift(-h).rename(col)
        df = df.merge(mids_lead, left_on='time', right_index=True, how='left')
        df[f'markout_{h}'] = np.where(
            df['side'].eq('buy'),
            df[col] - df['mid_t'],
            df['mid_t'] - df[col]
        )
        df.drop(columns=[col], inplace=True)

    # Save detailed
    df.to_csv(os.path.join(out_dir, 'trades_with_markouts.csv'), index=False)

    # Summaries
    def _sum_safe(s): return float(s.dropna().sum()) if len(s) else 0.0

    total = {
        'trades': int(len(df)),
        'fees_sum': _sum_safe(df['fee']),
        'spread_edge_sum': _sum_safe(df['spread_edge']),
    }
    for h in horizons:
        total[f'markout_{h}_sum'] = _sum_safe(df[f'markout_{h}'])

    # Maker/taker split
    mk = df[df['liquidity'] == 'maker']
    tk = df[df['liquidity'] == 'taker']
    maker = {
        'maker_trades': int(len(mk)),
        'maker_fees_sum': _sum_safe(mk['fee']),
        'maker_spread_edge_sum': _sum_safe(mk['spread_edge']),
    }
    for h in horizons:
        maker[f'maker_markout_{h}_sum'] = _sum_safe(mk[f'markout_{h}'])
    taker = {
        'taker_trades': int(len(tk)),
        'taker_fees_sum': _sum_safe(tk['fee']),
        'taker_spread_edge_sum': _sum_safe(tk['spread_edge']),
    }
    for h in horizons:
        taker[f'taker_markout_{h}_sum'] = _sum_safe(tk[f'markout_{h}'])

    pd.DataFrame([total | maker | taker]).to_csv(
        os.path.join(out_dir, 'attribution_summary.csv'),
        index=False
    )
def plot_attribution_stacked(logs: pd.DataFrame, trades_with_markouts_csv: str, out_dir: str):
    """Stacked PnL contributions over time: spread_edge, markout_1 (or pick), fees."""
    ensure_dir(out_dir)
    import pandas as pd, matplotlib.pyplot as plt, numpy as np, os
    if not os.path.exists(trades_with_markouts_csv):
        return
    df = pd.read_csv(trades_with_markouts_csv, parse_dates=['time'])
    if df.empty: return
    df = df.set_index('time').sort_index()
    # choose markout horizon
    mo = 'markout_5' if 'markout_5' in df.columns else [c for c in df.columns if c.startswith('markout_')][0]
    # resample to per-bar contributions (align with logs)
    contrib = pd.DataFrame({
        'spread': df['spread_edge'],
        'markout': df[mo],
        'fees': -df['fee']
    }).resample('1min').sum().fillna(0.0)
    plt.figure()
    contrib[['spread', 'markout', 'fees']].cumsum().plot(stacked=False)
    plt.title('Cumulative PnL Attribution (Spread vs Markout vs Fees)')
    plt.xlabel('Time'); plt.ylabel('PnL')
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'pnl_attribution_stacked.png'))
    plt.close()

def save_heatmap(csv_path: str, x: str, y: str, z: str, out_png: str, agg='mean'):
    if not os.path.exists(csv_path): return
    df = pd.read_csv(csv_path)
    if df.empty or x not in df or y not in df or z not in df: return
    pivot = df.pivot_table(index=y, columns=x, values=z, aggfunc=agg)
    plt.figure()
    im = plt.imshow(pivot.values, aspect='auto', origin='lower')
    plt.colorbar(im, label=z)
    plt.xticks(ticks=range(len(pivot.columns)), labels=pivot.columns, rotation=45)
    plt.yticks(ticks=range(len(pivot.index)), labels=pivot.index)
    plt.title(f'{z} heatmap by {x} x {y}')
    plt.tight_layout()
    plt.savefig(out_png)
    plt.close()
def compute_metrics(equity: pd.Series, freq_per_day=1440):
    if equity is None or len(equity) < 3:
        return {"final_equity": float(equity.iloc[-1]) if len(equity) else 0.0}
    ret = equity.diff().fillna(0.0)
    mu = ret.mean()
    sigma = ret.std(ddof=1)
    sharpe = (mu / (sigma + 1e-12)) * (freq_per_day ** 0.5)
    downside = ret[ret < 0]
    sortino = (mu / (downside.std(ddof=1) + 1e-12)) * (freq_per_day ** 0.5)
    # max drawdown
    cum_max = equity.cummax()
    drawdown = equity - cum_max
    max_dd = drawdown.min()
    return {"final_equity": float(equity.iloc[-1]),
            "sharpe": float(sharpe),
            "sortino": float(sortino),
            "max_drawdown": float(max_dd)}

def save_metrics_csv(logs: pd.DataFrame, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    if logs is None or logs.empty: return
    m = compute_metrics(logs["equity"])
    pd.DataFrame([m]).to_csv(os.path.join(out_dir, "metrics.csv"), index=False)

def save_equity_inventory_overlay(logs: pd.DataFrame, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    if logs is None or logs.empty: return
    fig, ax1 = plt.subplots()
    ax1.plot(logs.index, logs["equity"])
    ax1.set_xlabel("Time"); ax1.set_ylabel("Equity")
    ax2 = ax1.twinx()
    ax2.plot(logs.index, logs["inventory"])
    ax2.set_ylabel("Inventory")
    plt.title("Equity (left) & Inventory (right)")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "equity_inventory_overlay.png"))
    plt.close()
