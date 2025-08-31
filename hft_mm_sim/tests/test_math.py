import pandas as pd
from hft_mm_sim.config import MMConfig
from hft_mm_sim.data import synthetic_minute
from hft_mm_sim.backtester import Backtester

def test_equity_consistency():
    df = synthetic_minute(minutes=120, seed=1)
    cfg = MMConfig(fee_bps=0, slippage_bps=0, latency_sec=0)
    bt = Backtester(cfg)
    res = bt.run(df)
    logs = res['logs']
    assert not logs.empty
    # equity must equal cash + inv*price_ref (already in code), just smoke check monotonicity with zero fees/slip
    assert abs(logs['equity'].iloc[-1] - (logs['cash'].iloc[-1] + logs['inventory'].iloc[-1]*logs['price_ref'].iloc[-1])) < 1e-6

def test_trades_log_exists():
    df = synthetic_minute(minutes=120, seed=2)
    cfg = MMConfig()
    bt = Backtester(cfg)
    res = bt.run(df)
    assert 'trades' in res and isinstance(res['trades'], pd.DataFrame)
