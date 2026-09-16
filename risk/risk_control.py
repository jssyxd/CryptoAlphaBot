"""
Risk control with daily loss, consecutive loss cooldown,
max drawdown, and stricter circuit breakers.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, Tuple

from config.config import config

logger = logging.getLogger(__name__)


class RiskControl:
    """
    Rules:
    1. Daily loss limit (default 10%) -> stop for the day
    2. Consecutive losses (default 3) -> 24h cooldown
    3. Max drawdown (default 15%) -> hard stop
    4. Circuit breaker: if equity drops > CIRCUIT_BREAKER_PCT in one hour -> pause
    5. Max open positions / max position size
    """

    def __init__(self, initial_balance: float = None):
        self.initial_balance = initial_balance or config.INITIAL_BALANCE
        self.current_balance = self.initial_balance
        self.peak_balance = self.initial_balance
        self.daily_loss = 0.0
        self.daily_loss_limit = config.DAILY_LOSS_LIMIT / 100.0
        self.consecutive_losses = 0
        self.consecutive_loss_limit = config.CONSECUTIVE_LOSS_LIMIT
        self.cooldown_until = None
        self.trade_history = []
        self.circuit_breaker_until = None
        self.hourly_equity = []  # (ts, equity)
        self.circuit_breaker_pct = float(getattr(config, "CIRCUIT_BREAKER_PCT", 5.0)) / 100.0
        self.hard_stopped = False

    def can_trade(self) -> Tuple[bool, str]:
        if self.hard_stopped:
            return False, "Hard stop: max drawdown breached"

        if self.circuit_breaker_until and datetime.utcnow() < self.circuit_breaker_until:
            remaining = (self.circuit_breaker_until - datetime.utcnow()).total_seconds() / 60
            return False, f"Circuit breaker active, remaining {remaining:.0f} min"

        daily_loss_ratio = abs(min(self.daily_loss, 0)) / self.initial_balance
        if daily_loss_ratio >= self.daily_loss_limit:
            return False, f"Daily loss limit reached ({daily_loss_ratio:.2%} >= {self.daily_loss_limit:.2%})"

        if self.cooldown_until is not None:
            if datetime.utcnow() < self.cooldown_until:
                remaining = (self.cooldown_until - datetime.utcnow()).total_seconds() / 3600
                return False, f"Cooldown cooldown after consecutive losses. Remaining: {remaining:.1f}h"
            else:
                self.cooldown_until = None
                self.consecutive_losses = 0
                logger.info("Cooldown cooldown expired. Trading resumed.")

        dd_ok, dd = self.check_max_drawdown()
        if not dd_ok:
            self.hard_stopped = True
            return False, f"Max drawdown breached ({dd:.2f}%)"

        return True, "OK"

    def record_trade(self, symbol: str, pnl: float, pnl_percent: float):
        trade = {
            "timestamp": datetime.utcnow(),
            "symbol": symbol,
            "pnl": pnl,
            "pnl_percent": pnl_percent,
            "is_loss": pnl < 0,
        }
        self.trade_history.append(trade)
        self.current_balance += pnl
        self.daily_loss += pnl
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance

        if pnl < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= self.consecutive_loss_limit:
                self.cooldown_until = datetime.utcnow() + timedelta(hours=config.COOLDOWN_HOURS)
                logger.warning(
                    f"⚠️ {self.consecutive_losses} consecutive losses! "
                    f"Paused until {self.cooldown_until}"
                )
        else:
            self.consecutive_losses = 0

        logger.info(
            f"Trade recorded: {symbol} | P&L: ${pnl:+.2f} ({pnl_percent:+.2f}%) | "
            f"Balance: ${self.current_balance:.2f} | "
            f"Consecutive losses: {self.consecutive_losses}/{self.consecutive_loss_limit}"
        )

    def update_equity(self, equity: float):
        """Call periodically to detect rapid drawdown (circuit breaker)."""
        now = datetime.utcnow()
        self.hourly_equity.append((now, equity))
        # Keep last 2 hours
        cutoff = now - timedelta(hours=2)
        self.hourly_equity = [(t, e) for t, e in self.hourly_equity if t >= cutoff]

        # Check 1-hour drop
        one_hour_ago = now - timedelta(hours=1)
        past = [e for t, e in self.hourly_equity if t <= one_hour_ago]
        if past:
            peak_1h = max(past)
            drop = (peak_1h - equity) / peak_1h if peak_1h > 0 else 0
            if drop >= self.circuit_breaker_pct:
                self.circuit_breaker_until = now + timedelta(hours=1)
                logger.warning(
                    f"🚨 Circuit breaker: equity dropped {drop:.2%} in ~1h. "
                    f"Paused until {self.circuit_breaker_until}"
                )

    def reset_daily_loss(self):
        logger.info(f"Daily loss reset. Previous: ${self.daily_loss:.2f}")
        self.daily_loss = 0.0

    def get_max_position_size(self, entry_price: float) -> float:
        max_value = self.current_balance * (config.POSITION_SIZE_PERCENT / 100)
        return max_value / entry_price if entry_price > 0 else 0

    def check_max_drawdown(self) -> Tuple[bool, float]:
        if self.peak_balance <= 0:
            return True, 0.0
        drawdown = (self.current_balance - self.peak_balance) / self.peak_balance
        drawdown_percent = drawdown * 100
        within_limit = drawdown_percent >= -config.MAX_DRAWDOWN_PERCENT
        return within_limit, drawdown_percent

    def get_stats(self) -> Dict:
        dd_ok, dd = self.check_max_drawdown()
        can, reason = self.can_trade()
        daily_loss_ratio = abs(min(self.daily_loss, 0)) / self.initial_balance
        wins = sum(1 for t in self.trade_history if t["pnl"] > 0)
        losses = sum(1 for t in self.trade_history if t["pnl"] < 0)
        n = len(self.trade_history)
        return {
            "initial_balance": self.initial_balance,
            "current_balance": self.current_balance,
            "peak_balance": self.peak_balance,
            "total_pnl": self.current_balance - self.initial_balance,
            "total_pnl_percent": ((self.current_balance - self.initial_balance) / self.initial_balance) * 100,
            "daily_loss": self.daily_loss,
            "daily_loss_ratio": daily_loss_ratio,
            "consecutive_losses": self.consecutive_losses,
            "cooldown_until": self.cooldown_until,
            "circuit_breaker_until": self.circuit_breaker_until,
            "current_drawdown_percent": dd,
            "max_drawdown_limit": -config.MAX_DRAWDOWN_PERCENT,
            "drawdown_within_limit": dd_ok,
            "hard_stopped": self.hard_stopped,
            "can_trade": can,
            "trade_restriction_reason": reason,
            "total_trades": n,
            "winning_trades": wins,
            "losing_trades": losses,
            "win_rate": (wins / n * 100) if n else 0,
        }
