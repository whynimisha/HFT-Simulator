from dataclasses import dataclass
from typing import List, Optional
import math, random

@dataclass
class Order:
    side: str     # 'buy' or 'sell'
    price: float
    qty: float
    activate_at_idx: int  # bar index when order becomes active

@dataclass
class Fill:
    time: any
    side: str
    price: float
    qty: float
    fee: float

class ExecutionSimulator:
    def __init__(self, cfg):
        self.cfg = cfg
        self.active_orders: List[Order] = []
        self.rng = random.Random(cfg.seed)

    def submit_quotes(self, idx: int, bid: float, ask: float, size_bid: float, size_ask: float):
        latency_bars = max(0, math.ceil(self.cfg.latency_sec / 60.0))
        self.active_orders.append(Order(side='buy',  price=bid, qty=size_bid,  activate_at_idx=idx+latency_bars))
        self.active_orders.append(Order(side='sell', price=ask, qty=size_ask, activate_at_idx=idx+latency_bars))

    def process_bar(self, idx: int, time, row, next_row) -> List[Fill]:
        fills: List[Fill] = []
        low  = float(next_row['low'])
        high = float(next_row['high'])
        vol  = float(next_row.get('volume', 0.0))
        vol_cap = max(0.0, min(1.0, self.cfg.vol_cap_frac))
        max_fill = max(0.0, vol * vol_cap)

        # Momentum direction (bar-to-bar)
        mom = float(next_row['close']) - float(row['close'])
        momentum_up = mom > 0

        # Activate now
        active_now = [o for o in self.active_orders if o.activate_at_idx == idx]
        self.active_orders = [o for o in self.active_orders if o.activate_at_idx > idx]

        # Which could fill?
        could_fill = []
        for o in active_now:
            cond = (o.side == 'buy' and o.price >= low) or (o.side == 'sell' and o.price <= high)
            if cond:
                could_fill.append(o)

        # Bias toward momentum-aligned side (adverse selection)
        if len(could_fill) >= 2:
            buys  = [o for o in could_fill if o.side == 'buy']
            sells = [o for o in could_fill if o.side == 'sell']
            if buys and sells:
                prefer_side = 'sell' if momentum_up else 'buy'
                if self.rng.random() < max(0.0, min(1.0, self.cfg.adverse_bias)):
                    could_fill = sells if prefer_side == 'sell' else buys

        # Apply volume cap and slippage
        remaining_cap = max_fill if max_fill > 0 else None
        slip = self.cfg.slippage_bps / 1e4  # bps → fraction
        for o in could_fill:
            if remaining_cap is not None and remaining_cap <= 0:
                break
            qty = o.qty if remaining_cap is None else min(o.qty, remaining_cap)
            if qty <= 0:
                continue

            # Slippage against us
            exec_price = o.price * (1 + slip) if o.side == 'buy' else o.price * (1 - slip)
            fee = abs(exec_price * qty) * (self.cfg.fee_bps / 1e4)
            fills.append(Fill(time=time, side=o.side, price=exec_price, qty=qty, fee=fee))

            if remaining_cap is not None:
                remaining_cap -= qty

        return fills
