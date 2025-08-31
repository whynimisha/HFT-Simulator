from dataclasses import dataclass
import math

@dataclass
class Quotes:
    bid: float
    ask: float
    size_bid: float
    size_ask: float
    reason: str

def round_to_tick(x: float, tick: float) -> float:
    return math.floor(x / tick) * tick

class MarketMakerStrategy:
    def __init__(self, cfg):
        self.cfg = cfg

    def compute_quotes(self, row, inventory: float) -> Quotes:
        price = float(row['close'])
        mid = float(row.get('mid', price))
        vol = float(row.get('vol', 0.0))  # unitless std of returns
        mom_sign = float(row.get('mom_sign', 0.0))

        # Baseline half-spread scales with price * vol
        half_spread = max(self.cfg.tick_size, self.cfg.k_vol * price * vol)

        # Momentum tilt (guard adverse selection): widen bid if up-trend, widen ask if down-trend
        tilt = self.cfg.k_mom * mom_sign * half_spread
        half_spread_adj = half_spread + abs(tilt)

        # Inventory skew: push quotes away from current inventory
        skew = self.cfg.k_inv * inventory * self.cfg.tick_size * 10  # scale skew in ticks
        bid = mid - (half_spread_adj + max(0.0, skew))
        ask = mid + (half_spread_adj - min(0.0, skew))

        bid = round_to_tick(bid, self.cfg.tick_size)
        ask = round_to_tick(ask, self.cfg.tick_size)

        # Order sizing shrinks as |inventory| approaches cap
        inv_util = min(1.0, abs(inventory) / max(1e-9, self.cfg.inv_cap))
        size_factor = max(0.1, 1.0 - inv_util)
        size = self.cfg.base_size * size_factor

        reason = f"half={half_spread_adj:.6f}, skew={skew:.6f}, mom={mom_sign:.0f}"
        return Quotes(bid=bid, ask=ask, size_bid=size, size_ask=size, reason=reason)
