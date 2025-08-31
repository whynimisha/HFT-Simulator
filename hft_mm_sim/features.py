import pandas as pd
import numpy as np

def add_features(df: pd.DataFrame, vol_lookback: int, mom_lookback: int) -> pd.DataFrame:
    out = df.copy()
    out['mid'] = (out['high'] + out['low']) / 2.0

    ret = out['close'].pct_change()
    vol = ret.rolling(vol_lookback, min_periods=max(2, vol_lookback//2)).std()
    out['vol'] = vol.fillna(0.0)

    out['mom'] = out['close'].diff(mom_lookback)
    out['mom_sign'] = np.sign(out['mom']).fillna(0.0)

    return out
