class RiskManager:
    def __init__(self, cfg):
        self.cfg = cfg
        self.equity_peak = 100.0
    def update_equity(self, equity: float):
            if equity is None:
                return
            if self.equity_peak is None or equity > self.equity_peak:
                self.equity_peak = equity

    def allow_new_orders(self, inventory: float, rolling_vol: float, equity: float, bar_i: int | None = None) -> bool:
        # Update peak
        if equity is not None:
            self.equity_peak = max(self.equity_peak, float(equity))

        # Volatility brake
        if rolling_vol is not None and rolling_vol > self.cfg.vol_brake_mult * 1e-3:
            return False

        # Inventory cap
        if abs(inventory) >= self.cfg.inv_cap:
            return False

        # Drawdown stop (after warmup only)
        if bar_i is None or bar_i >= self.warmup_bars:
            if equity < self.equity_peak * (1.0 - self.cfg.dd_stop):
                return False

        return True
