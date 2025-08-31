from dataclasses import dataclass
from typing import Tuple

@dataclass
class MMConfig:
    # --- strategy & features ---
    k_vol: float = 0.05
    vol_lookback: int = 30
    k_inv: float = 0.002
    k_mom: float = 0.05
    mom_lookback: int = 5

    # --- risk knobs ---
    vol_brake_mult: float = 3.0
    inv_cap: float = 50.0
    dd_stop: float = 0.8

    # --- execution/frictions ---
    tick_size: float = 0.01
    base_size: float = 5.0
    fee_bps: float = 5.0
    latency_sec: int = 1
    slippage_bps: float = 1.0
    adverse_bias: float = 0.5
    vol_cap_frac: float = 0.1
    ref_price: str = "close"
    seed: int = 42

    # --- analytics ---
    markout_horizons: Tuple[int, ...] = (1, 5, 10)

    # --- LOB / queue sim ---
    use_lob: bool = True          # turn it on (only once)
    lob_levels: int = 10
    lob_ticks_per_bar: int = 100
    lob_base_depth: float = 8.0
    lob_depth_decay: float = 0.75
    mo_frac: float = 1.0

    # maker/taker econ
    maker_rebate_bps: float = -2.0
    taker_fee_bps: float = 7.0

    # quoting
    quote_levels: int = 3
    level_size_decay: float = 0.6
    carry_orders: bool = True
    cancel_penalty_bps: float = 0.1

    # taker rebalance
    taker_rebalance: bool = True
    taker_rebalance_threshold: float = 0.3
    taker_rebalance_pct: float = 0.5
def apply_high_activity_preset(cfg: "MMConfig") -> "MMConfig":
    cfg.k_vol = 0.1              # tighter quotes
    cfg.base_size = 2.0          # bigger size
    cfg.inv_cap = 50.0           # allow more inventory
    cfg.latency_sec = 5          # faster reaction
    cfg.vol_cap_frac = 0.2       # more volume can fill us (OHLC path)
    cfg.mo_frac = 0.8            # more market-order flow (LOB path)
    cfg.lob_base_depth = 12.0    # deeper synthetic book
    return cfg
