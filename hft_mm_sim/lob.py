from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

@dataclass
class RestingOrder:
    order_id: int
    side: str         # 'buy' or 'sell'
    price: float
    qty: float
    level_idx: int    # 0 = best
    queue_ahead: float  # size ahead of us at that level (not including our qty)

@dataclass
class MakerFill:
    time: any
    side: str         # 'buy' (our bid hit) or 'sell' (our ask lifted)
    price: float
    qty: float

class LimitOrderBook:
    """
    Symmetric ladder with FIFO queues per level.
    Tracks OUR resting orders' queue_ahead and fills them after visible size is consumed.
    """
    def __init__(self, mid: float, tick: float, levels: int, base_depth: float, depth_decay: float):
        self.tick = tick
        self.levels = levels
        self._next_id = 1
        self._ours: Dict[int, RestingOrder] = {}
        self._build_symmetric(mid, base_depth, depth_decay)

    def _build_symmetric(self, mid: float, base_depth: float, decay: float):
        self.bids: List[Tuple[float, float]] = []
        self.asks: List[Tuple[float, float]] = []
        for i in range(self.levels):
            p_bid = mid - (i + 1) * self.tick
            p_ask = mid + (i + 1) * self.tick
            size = base_depth * (decay ** i)
            self.bids.append((p_bid, size))
            self.asks.append((p_ask, size))

    def best_bid(self) -> Tuple[float, float]: return self.bids[0]
    def best_ask(self) -> Tuple[float, float]: return self.asks[0]

    def replenish(self, base_depth: float, decay: float):
        """Top up each level back toward target depth (simulates new liquidity arriving)."""
        for side in (self.bids, self.asks):
            for i, (p, s) in enumerate(side):
                target = base_depth * (decay ** i)
                if s < target:
                    side[i] = (p, target)

    def place_limit(self, side: str, price: float, qty: float) -> Optional[RestingOrder]:
        book = self.bids if side == 'buy' else self.asks
        level_idx = None
        for i, (p, _) in enumerate(book):
            if abs(p - price) < 1e-12:
                level_idx = i
                break
        if level_idx is None:
            return None
        queue_ahead = book[level_idx][1]
        oid = self._next_id; self._next_id += 1
        ro = RestingOrder(oid, side, price, qty, level_idx, queue_ahead=queue_ahead)
        self._ours[oid] = ro
        # increase visible size (we join at the tail)
        p, s = book[level_idx]
        book[level_idx] = (p, s + qty)
        return ro

    def cancel(self, order_id: int):
        ro = self._ours.pop(order_id, None)
        if not ro: return
        book = self.bids if ro.side == 'buy' else self.asks
        p, s = book[ro.level_idx]
        book[ro.level_idx] = (p, max(0.0, s - ro.qty))

    def process_market_order(self, side: str, qty: float, t) -> List[MakerFill]:
        """
        side='buy' consumes ASKs; side='sell' consumes BIDs.
        We consume visible-ahead first, then OUR queue_ahead, then OUR qty.
        """
        fills: List[MakerFill] = []
        book = self.asks if side == 'buy' else self.bids
        remaining = qty
        level = 0
        while remaining > 0 and level < self.levels:
            price, level_size = book[level]

            # Our total resting size on this level
            ours_here = sum(ro.qty for ro in self._ours.values()
                            if ro.level_idx == level and ro.side == ('sell' if side == 'buy' else 'buy'))

            visible_ahead = max(0.0, level_size - ours_here)
            take_ahead = min(remaining, visible_ahead)
            remaining -= take_ahead
            level_size -= take_ahead

            if remaining > 0:
                for ro in list(self._ours.values()):
                    if ro.level_idx == level and ro.side == ('sell' if side == 'buy' else 'buy') and ro.qty > 0:
                        use_ahead = min(remaining, ro.queue_ahead)
                        ro.queue_ahead -= use_ahead
                        remaining -= use_ahead
                        if ro.queue_ahead <= 1e-12 and remaining > 0:
                            fill_qty = min(remaining, ro.qty)
                            if fill_qty > 0:
                                ro.qty -= fill_qty
                                remaining -= fill_qty
                                level_size -= fill_qty
                                fills.append(MakerFill(time=t, side=ro.side, price=ro.price, qty=fill_qty))
                # drop empty
                for ro in list(self._ours.values()):
                    if ro.qty <= 1e-12:
                        self._ours.pop(ro.order_id, None)

            book[level] = (price, max(0.0, level_size))
            if book[level][1] <= 1e-12:
                level += 1
            elif remaining <= 1e-12:
                break
        return fills

    def our_order_ids(self) -> List[int]:
        return list(self._ours.keys())
