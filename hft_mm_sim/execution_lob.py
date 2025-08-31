from dataclasses import dataclass
from typing import List
import math, random
import pandas as pd
from .lob import LimitOrderBook, MakerFill  # MakerFill may be used by your LOB

@dataclass
class FillEx:
    time: any
    side: str           # 'buy' or 'sell'
    price: float
    qty: float
    fee: float
    liquidity: str      # 'maker' or 'taker'

class ExecutionLOB:
    """Persistent LOB across bars; multi-level quoting; queue modeling; maker/taker econ."""
    def __init__(self, cfg):
        self.cfg = cfg
        self.rng = random.Random(cfg.seed)
        self.book: LimitOrderBook | None = None
        self.ours: List[int] = []  # our resting order IDs

    def _ensure_book(self, mid: float, tick: float):
        if self.book is None:
            self.book = LimitOrderBook(
                mid,
                tick,
                self.cfg.lob_levels,
                self.cfg.lob_base_depth,
                self.cfg.lob_depth_decay
            )

    def _cancel_all(self, ref_time) -> float:
        """
        Cancel our orders; return penalty cost (bps of notional at mid * base_size * n_orders).
        Uses the ACTUAL number of our resting orders, not a fixed guess.
        """
        if not self.ours or self.book is None:
            return 0.0

        # capture how many we really cancel right now
        n_orders = len(self.ours)

        # cancel them on the book
        for oid in list(self.ours):
            self.book.cancel(oid)
        self.ours.clear()

        # compute a flat per-cancel penalty from best bid/ask mid
        bb, _ = self.book.best_bid()
        ba, _ = self.book.best_ask()
        mid = (bb + ba) / 2.0
        cost = n_orders * (mid * self.cfg.base_size) * (self.cfg.cancel_penalty_bps / 1e4)
        return float(cost)

    def _place_quotes(self, mid: float, tick: float) -> None:
        """Place up to quote_levels per side; larger at top, decayed sizes deeper."""
        assert self.book is not None
        # replenish background depth each bar
        self.book.replenish(self.cfg.lob_base_depth, self.cfg.lob_depth_decay)

        for lvl in range(self.cfg.quote_levels):
            bid_p = self.book.bids[lvl][0]
            ask_p = self.book.asks[lvl][0]
            size = self.cfg.base_size * (self.cfg.level_size_decay ** lvl)
            rb = self.book.place_limit('buy',  bid_p, size)
            ra = self.book.place_limit('sell', ask_p, size)
            if rb: self.ours.append(rb.order_id)
            if ra: self.ours.append(ra.order_id)

    def _taker_rebalance(self, inventory: float, ref_time) -> List[FillEx]:
        if not (self.cfg.taker_rebalance and self.book):
            return []
        thr = self.cfg.taker_rebalance_threshold * self.cfg.inv_cap
        if abs(inventory) < thr:
            return []
        side = 'sell' if inventory > 0 else 'buy'
        best_price, best_size = (self.book.best_bid() if side == 'sell' else self.book.best_ask())
        qty = min(max(0.0, abs(inventory) * self.cfg.taker_rebalance_pct), best_size)
        if qty <= 0:
            return []
        slip = self.cfg.slippage_bps / 1e4
        px = best_price * (1 - slip) if side == 'sell' else best_price * (1 + slip)
        fee = abs(px * qty) * (self.cfg.taker_fee_bps / 1e4)
        # consume book at best level
        if side == 'sell':
            p, s = self.book.bids[0]
            self.book.bids[0] = (p, max(0.0, s - qty))
        else:
            p, s = self.book.asks[0]
            self.book.asks[0] = (p, max(0.0, s - qty))
        return [FillEx(time=ref_time, side=side, price=px, qty=qty, fee=fee, liquidity='taker')]

def run_bar(self, idx: int, t_start: any, row: pd.Series, next_row: pd.Series, inventory: float) -> List[FillEx]:
    fills: List[FillEx] = []
    mid = float(row.get('mid', row['close']))
    tick = self.cfg.tick_size
    self._ensure_book(mid, tick)
    # Only cancel if not carrying orders
    if not self.cfg.carry_orders or (self.ours and not self.cfg.carry_orders):
        cancel_cost = self._cancel_all(t_start)
        if cancel_cost > 0.0:
            fills.append(FillEx(time=t_start, side='buy', price=mid, qty=0.0, fee=cancel_cost, liquidity='maker'))
    # ... rest of the function ...
    # Remove end-of-bar cancel or conditionalize similarly
    if not self.cfg.carry_orders:
        cancel_cost = self._cancel_all(t_start)
        if cancel_cost > 0.0:
            fills.append(FillEx(time=t_start, side='buy', price=mid, qty=0.0, fee=cancel_cost, liquidity='maker'))

        # Place quotes for this bar
        self._place_quotes(mid, tick)

        # Convert latency seconds to micro-ticks
        latency_ticks = max(0, math.ceil(self.cfg.latency_sec / (60.0 / max(1, self.cfg.lob_ticks_per_bar))))

        # MO flow per micro-tick with momentum bias
        total_vol = float(row.get('volume', 0.0))
        mo_total = max(0.0, total_vol * self.cfg.mo_frac)
        mean_per_tick = mo_total / max(1, self.cfg.lob_ticks_per_bar)
        mom_sign = float(row.get('mom_sign', 0.0))

        for k in range(self.cfg.lob_ticks_per_bar):
            # latency gate: our newly placed orders start interacting only after latency elapses
            if k >= latency_ticks:
                prob_buy = 0.5 + 0.2 * mom_sign
                prob_buy = max(0.0, min(1.0, prob_buy))
                side = 'buy' if self.rng.random() < prob_buy else 'sell'
                # exponential MO size
                lam = 1.0 / max(1e-6, mean_per_tick)
                mo_qty = max(0.0, self.rng.expovariate(lam))
                maker_fills = self.book.process_market_order(side, mo_qty, t=t_start)
                for mf in maker_fills:
                    # maker economics: rebate is negative bps → negative fee means +PnL
                    fee = abs(mf.price * mf.qty) * (self.cfg.maker_rebate_bps / 1e4)
                    fills.append(FillEx(time=mf.time, side=mf.side, price=mf.price,
                                        qty=mf.qty, fee=fee, liquidity='maker'))

        # Optional taker rebalance near bar end
        fills.extend(self._taker_rebalance(inventory, ref_time=t_start))

        # 🚫 FIX: only end-of-bar cancel if carry_orders is False
        if not self.cfg.carry_orders:
            cancel_cost = self._cancel_all(t_start)
            if cancel_cost > 0.0:
                fills.append(FillEx(time=t_start, side='buy', price=mid, qty=0.0,
                                    fee=cancel_cost, liquidity='maker'))

        return fills
