import pandas as pd
import numpy as np

REQUIRED_COLS = ['open', 'high', 'low', 'close', 'volume']

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip().lower() for c in df.columns]
    # consolidate duplicate 'close' columns if present
    close_like = [c for c in df.columns if c == 'close' or c.startswith('close')]
    if len(close_like) > 1:
        df['close'] = df[close_like].bfill(axis=1).iloc[:, 0]
        for c in close_like:
            if c != 'close':
                df.drop(columns=c, inplace=True)
    return df

def _coerce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    # Strip spaces, remove thousands separators, convert common null strings to NaN
    df = df.replace(r'^\s*$', np.nan, regex=True)
    for c in REQUIRED_COLS:
        if c in df.columns:
            if df[c].dtype == object:
                s = df[c].astype(str).str.replace(',', '', regex=False).str.strip()
                s = s.replace({'null': np.nan, 'None': np.nan, 'nan': np.nan})
                df[c] = pd.to_numeric(s, errors='coerce')
            else:
                df[c] = pd.to_numeric(df[c], errors='coerce')
    return df

def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)

    # Ensure time column exists (fallback if first column is time-like)
    df.columns = [str(c).strip().lower() for c in df.columns]
    if 'time' not in df.columns:
        df.rename(columns={df.columns[0]: 'time'}, inplace=True)

    # Parse time and set index
    df['time'] = pd.to_datetime(df['time'], errors='coerce', utc=False)
    df = df.dropna(subset=['time']).set_index('time').sort_index()

    # Normalize headers & dedupe close
    df = _normalize_columns(df)

    # Check required columns present
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"CSV {path} missing required columns: {missing}")

    # Coerce to numeric robustly
    df = _coerce_numeric(df)

    # Drop rows missing any required field
    before = len(df)
    df = df.dropna(subset=REQUIRED_COLS)
    after = len(df)

    if after == 0:
        print(f"[WARN] After cleaning, 0 rows remain in {path}. First 5 raw rows (pre-clean):")
        try:
            print(pd.read_csv(path, nrows=5, low_memory=False).to_string(index=False))
        except Exception:
            pass

    # Non-negative volume
    if (df['volume'] < 0).any():
        df.loc[df['volume'] < 0, 'volume'] = 0.0

    return df

def synthetic_minute(start='2024-01-01', minutes=600, seed=42, start_price=100.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start=start, periods=minutes, freq='1min')
    drift = 0.0
    vol = 0.0008  # ~8 bps per min
    reversion = 0.02
    prices = [start_price]
    for _ in range(1, len(idx)):
        ret = drift + vol * rng.normal() - reversion * (prices[-1] - start_price)/start_price * 0.01
        prices.append(prices[-1] * (1 + ret))
    close = pd.Series(prices, index=idx)
    high = close * (1 + np.maximum(0, vol*3*rng.normal(size=len(idx))).astype(float))
    low  = close * (1 - np.maximum(0, vol*3*rng.normal(size=len(idx))).astype(float))
    open_ = close.shift(1).fillna(close.iloc[0])
    volu = np.maximum(1, (rng.normal(loc=1000, scale=200, size=len(idx)))).astype(float)
    df = pd.DataFrame({'open': open_, 'high': high, 'low': low, 'close': close, 'volume': volu}, index=idx)
    df.index.name = 'time'
    return df
