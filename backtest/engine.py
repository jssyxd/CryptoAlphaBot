"""
Backtest engine with realistic slippage, fees, and SQLite persistence.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List

import numpy as np
import pandas as pd

from config.config import config
from data.processor import DataProcessor
from data.storage import DataStorage
from risk.position_manager import PositionManager
from risk.risk_control import RiskControl
from strategy.multi_factor import MultiFactorStrategy

logger = logging.getLogger(__name__)


class BacktestEngine:
    def __init__(
        self,
        initial_balance: float = None,
        commission: float = 0.001,      # 0.1% per side (Binance-like)
        slippage: float = 0.0005,       # 0.05% slippage
        persist: bool = True,
    ):
        self.initial_balance = initial_balance or config.INITIAL_BALANCE
        self.commission = commission
        self.slippage = slippage
        self.position_manager = PositionManager(self.initial_balance)
        self.risk_control = RiskControl(self.initial_balance)
        self.data_processor = DataProcessor()
        self.storage = DataStorage() if persist else None
        self.trades: List[Dict] = []
        self.equity_curve: List[Dict] = []

    def _apply_slippage(self, price: float, side: str) -> float:
        """Buy pays higher, sell receives lower."""
        if side == "buy":
            return price * (1 + self.slippage)
        return price * (1 - self.slippage)

    def _fee(self, notional: float) -> float:
        return notional * self.commission

    def run_backtest(
        self,
        df: pd.DataFrame,
        symbol: str,
        strategy: MultiFactorStrategy,
    ) -> Dict:
        logger.info(f"Backtest start {symbol} | bars={len(df)} | fee={self.commission} slip={self.slippage}")
        df = strategy.calculate_signals(df)

        for i in range(len(df)):
            row = df.iloc[i]
            current_price = float(row["close"])
            current_time = df.index[i]
            current_signal = int(row["signal"])
            dynamic_tp = float(row.get("dynamic_takeprofit", 0) or 0)

            # Persist signal
            if self.storage and current_signal != 0:
                self.storage.save_signal(
                    current_time, symbol, current_signal, current_price,
                    rsi=float(row.get("rsi") or 0),
                    dynamic_tp=dynamic_tp if dynamic_tp else None,
                )

            can_trade, reason = self.risk_control.can_trade()

            # ---- Exit logic ----
            if self.position_manager.has_position(symbol):
                pos = self.position_manager.get_position(symbol)
                exit_reason = None
                if current_price <= pos["stop_loss"]:
                    exit_reason = "stop_loss"
                elif current_price >= pos["take_profit"]:
                    exit_reason = "take_profit"
                elif current_signal == -1:
                    exit_reason = "signal"

                if exit_reason:
                    fill = self._apply_slippage(current_price, "sell")
                    closed = self.position_manager.close_position(symbol, fill)
                    if closed:
                        notional = closed["entry_price"] * closed["position_size"]
                        fee = self._fee(notional) + self._fee(fill * closed["position_size"])
                        closed["pnl"] -= fee
                        closed["pnl_percent"] = closed["pnl"] / closed["entry_value"] * 100
                        closed["fee_total"] = fee
                        closed["exit_reason"] = exit_reason
                        self.risk_control.record_trade(symbol, closed["pnl"], closed["pnl_percent"])
                        self.trades.append(closed)
                        if self.storage:
                            self.storage.save_trade({
                                "symbol": symbol,
                                "side": closed["side"],
                                "entry_time": closed["entry_time"],
                                "exit_time": closed["exit_time"],
                                "entry_price": closed["entry_price"],
                                "exit_price": closed["exit_price"],
                                "amount": closed["position_size"],
                                "pnl": closed["pnl"],
                                "pnl_percent": closed["pnl_percent"],
                                "fee_total": fee,
                                "exit_reason": exit_reason,
                                "stop_loss": closed.get("stop_loss"),
                                "take_profit": closed.get("take_profit"),
                            })

            # ---- Entry logic ----
            if current_signal == 1 and not self.position_manager.has_position(symbol) and can_trade:
                fill = self._apply_slippage(current_price, "buy")
                stop_loss = fill * (1 - config.STOP_LOSS_PERCENT / 100)
                tp_pct = dynamic_tp if dynamic_tp > 0 else config.BASE_TAKE_PROFIT
                take_profit = fill * (1 + tp_pct / 100)
                size = self.position_manager.calculate_position_size(symbol, fill, stop_loss)
                if size > 0:
                    fee = self._fee(fill * size)
                    # Reduce balance by fee immediately (simpler accounting)
                    self.position_manager.account_balance -= fee
                    self.position_manager.open_position(
                        symbol, "buy", fill, stop_loss, take_profit, size
                    )

            # Equity mark-to-market
            equity = self.position_manager.account_balance
            if self.position_manager.has_position(symbol):
                pos = self.position_manager.get_position(symbol)
                equity += current_price * pos["position_size"]
            self.risk_control.update_equity(equity)
            self.equity_curve.append({
                "time": current_time,
                "equity": equity,
                "balance": self.position_manager.account_balance,
            })
            if self.storage and i % 24 == 0:  # hourly snapshot approx
                peak = max(e["equity"] for e in self.equity_curve) if self.equity_curve else equity
                dd = (equity - peak) / peak * 100 if peak else 0
                self.storage.save_equity(current_time, equity, self.position_manager.account_balance, dd)

        stats = self._calculate_statistics()
        logger.info(
            f"Backtest done {symbol} | trades={len(self.trades)} | "
            f"return={stats.get('total_return', 0):.2f}% | maxDD={stats.get('max_drawdown', 0):.2f}%"
        )
        return stats

    def _calculate_statistics(self) -> Dict:
        if not self.trades:
            return {
                "initial_balance": self.initial_balance,
                "final_balance": self.risk_control.current_balance,
                "total_return": 0.0,
                "total_trades": 0,
                "win_rate": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
                "profit_factor": 0.0,
                "trades": [],
            }

        trades_df = pd.DataFrame(self.trades)
        equity_df = pd.DataFrame(self.equity_curve)

        total_return = (self.risk_control.current_balance - self.initial_balance) / self.initial_balance * 100
        winning = trades_df[trades_df["pnl"] > 0]
        losing = trades_df[trades_df["pnl"] <= 0]
        win_rate = len(winning) / len(trades_df) * 100 if len(trades_df) else 0
        profit_factor = (
            winning["pnl"].sum() / abs(losing["pnl"].sum())
            if len(losing) and losing["pnl"].sum() != 0 else 0
        )

        equity_df["running_max"] = equity_df["equity"].expanding().max()
        equity_df["drawdown"] = (equity_df["equity"] - equity_df["running_max"]) / equity_df["running_max"]
        max_dd = equity_df["drawdown"].min() * 100

        returns = equity_df["equity"].pct_change().dropna()
        sharpe = (returns.mean() / returns.std() * np.sqrt(252 * 24)) if len(returns) and returns.std() > 0 else 0

        return {
            "initial_balance": self.initial_balance,
            "final_balance": self.risk_control.current_balance,
            "total_return": total_return,
            "total_trades": len(trades_df),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "max_drawdown": max_dd,
            "sharpe_ratio": sharpe,
            "avg_trade_pnl": trades_df["pnl"].mean(),
            "total_fees": trades_df["fee_total"].sum() if "fee_total" in trades_df.columns else 0,
            "trades": self.trades,
        }
