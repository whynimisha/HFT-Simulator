import pandas as pd
from .config import MMConfig
from .features import add_features
from .strategy import MarketMakerStrategy
from .execution import ExecutionSimulator
from .risk import RiskManager
from .execution_lob import ExecutionLOB

class Backtester:
    def __init__(self, cfg: MMConfig):
        self.exec_lob = ExecutionLOB(cfg)
        self.cfg = cfg
        self.strategy = MarketMakerStrategy(cfg)
        self.exec = ExecutionSimulator(cfg)
        self.risk = RiskManager(cfg)
        self.reset()

    def reset(self):
        self.inventory = 0.0
        self.cash = 0.0
        self.logs = []   # per-bar logs
        self.trades = [] # per-trade logs

    def _finalize(self):
        # Build outputs robustly even if no logs/trades
        logs_df = pd.DataFrame(self.logs)
        if not logs_df.empty and ('time' in logs_df.columns):
            logs_df = logs_df.set_index('time')
        else:
            logs_df = pd.DataFrame(
                columns=['price_ref','inventory','cash','equity','reason']
            )
        trades_df = pd.DataFrame(self.trades) if self.trades else pd.DataFrame(
        columns=['time','side','price','qty','fee','liquidity']  # <-- add liquidity   
       )

        return {'logs': logs_df, 'trades': trades_df}

    def run(self, df: pd.DataFrame) -> dict:
        # Keep only the core market columns for NA filtering
        required = ['open','high','low','close','volume']
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Input DataFrame missing required columns: {missing}")

        # Only drop rows that have NA in the required columns
        df = df.dropna(subset=required).copy()
        if len(df) < 3:
            # Not enough bars to simulate next-bar fills
            return self._finalize()

        df = add_features(df, vol_lookback=self.cfg.vol_lookback, mom_lookback=self.cfg.mom_lookback)
        # Do NOT dropna() blindly here; features already handle NaNs

        ref = self.cfg.ref_price if self.cfg.ref_price in df.columns else 'close'

        for i in range(len(df)-1):  # use next bar for fills
            t = df.index[i]
            row = df.iloc[i]
            next_row = df.iloc[i+1]

           # pre-trade equity
            p_ref_now = float(row[ref])
            equity_now = self.cash + self.inventory * p_ref_now

            if self.cfg.use_lob:
    # LOB path
                bid = ask = None
                if self.risk.allow_new_orders(self.inventory, row.get('vol', 0.0), equity_now):
                    mid = float(row.get('mid', p_ref_now))
                    fills = self.exec_lob.run_bar(t, row, mid=mid, tick=self.cfg.tick_size, inventory=self.inventory)
                    # 👇 ADD THIS: record top-of-book so bid/ask columns aren’t NaN
                    if self.exec_lob.book is not None:
                        bb = self.exec_lob.book.best_bid()[0]
                        ba = self.exec_lob.book.best_ask()[0]
                        bid, ask = float(bb), float(ba)
                    reason = "lob_quote"
                else:
                    fills = []
                    reason = "risk_block"

            else:
                # Original OHLC next-bar path
                bid = ask = None
                if self.risk.allow_new_orders(self.inventory, row.get('vol', 0.0), equity_now):
                    q = self.strategy.compute_quotes(row, self.inventory)
                    bid, ask = q.bid, q.ask
                    self.exec.submit_quotes(i, q.bid, q.ask, q.size_bid, q.size_ask)
                    reason = q.reason
                else:
                    reason = "risk_block"
                fills = self.exec.process_bar(i+1, df.index[i+1], row, next_row)
            
            for f in fills:
                if f.side == 'buy':
                    self.cash -= f.price * f.qty
                    self.inventory += f.qty
                else:
                    self.cash += f.price * f.qty
                    self.inventory -= f.qty
                self.cash -= f.fee
                # ensure trades log has liquidity if from LOB, else mark as 'maker' by default
                liq = getattr(f, 'liquidity', 'maker')
                trade_time = getattr(f, 'time', t)
                self.trades.append({
                            'time': trade_time,
                            'side': f.side,
                            'price': f.price,
                            'qty': f.qty,
                            'fee': f.fee,
                            'liquidity': liq
})


            # 3) Mark-to-market
            p_ref = float(df.iloc[i][ref])
            equity = self.cash + self.inventory * p_ref

            self.logs.append({
                'time': t,
                'price_ref': p_ref,
                'mid': float(row.get('mid', p_ref)),
                'bid': float(bid) if bid is not None else float('nan'),
                'ask': float(ask) if ask is not None else float('nan'),
                'inventory': self.inventory,
                'cash': self.cash,
                'equity': equity,
                'reason': reason
            })


        return self._finalize()
