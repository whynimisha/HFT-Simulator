# HFT Market Making Simulation (Minute-Bar Backtest)

Educational backtester for a market-making strategy on minute OHLCV bars (yfinance/ccxt). 
Quotes around the mid-price, with volatility-based spread, inventory skew, momentum tilt, latency, 
next-bar high/low fills with volume caps, and fee modeling.

> This is an **educational** approximation — not production HFT.

## Quick Start
```bash
# 1) Create/activate a virtual environment (recommended)
python -m venv .venv && source .venv/bin/activate  # (Windows: .venv\Scripts\activate)

# 2) Install requirements
pip install -r requirements.txt

# 3) (Optional) Download data with yfinance (internet required)
python scripts/download_data.py --symbol BTC-USD --start 2024-01-01 --end 2024-01-05 --interval 1m --out data/BTC-USD_1m.csv

# 4) Run a backtest (uses sample synthetic data if no CSV provided)
python run_backtest.py --csv data/sample_minute.csv --fee_bps 5 --latency_sec 30

# 5) Outputs
# - artifacts/trades.csv
# - artifacts/equity_curve.csv
# - artifacts/plots/*.png
```

## Project Structure
```
hft_mm_sim/
  hft_mm_sim/
    __init__.py
    config.py
    data.py
    features.py
    strategy.py
    execution.py
    risk.py
    backtester.py
    analytics.py
  scripts/
    download_data.py
  data/
    sample_minute.csv
  run_backtest.py
  requirements.txt
  README.md
```

## Key Ideas
- **Quoting**: mid ± half_spread; spread scales with volatility, skewed by inventory, tilted by momentum.
- **Latency**: orders activate after a delay (in bars).
- **Fills**: next-bar high/low; partial fills constrained by a volume cap fraction.
- **PnL**: realized + mark-to-market; explicit fees.
- **Risk**: inventory caps, drawdown stop, volatility brakes.

## Disclaimers
This is **not** investment advice. Use for learning only.
