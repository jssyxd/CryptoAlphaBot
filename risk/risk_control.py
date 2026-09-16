import logging
from datetime import datetime, timedelta
from typing import Dict, List
from config.config import config

logger = logging.getLogger(__name__)

class RiskControl:
    """
    🛡️ Risk Control System
    
    Implements three risk management rules:
    1. Daily loss limit: Stop trading if daily loss >= 10%
    2. Consecutive loss cooldown: Stop trading 24h after 3 consecutive losses
    3. Position sizing: Max 10% per trade, max 15% drawdown
    """
    
    def __init__(self, initial_balance: float = None):
        self.initial_balance = initial_balance or config.INITIAL_BALANCE
        self.current_balance = self.initial_balance
        self.daily_loss = 0.0
        self.daily_loss_limit = config.DAILY_LOSS_LIMIT / 100  # Convert to ratio
        self.consecutive_losses = 0
        self.consecutive_loss_limit = config.CONSECUTIVE_LOSS_LIMIT
        self.cooldown_until = None
        self.trade_history = []
    
    def can_trade(self) -> tuple[bool, str]:
        """
        Check if trading is allowed based on risk rules
        
        Returns:
            (can_trade: bool, reason: str)
        """
        # Rule 1: Check daily loss limit
        daily_loss_ratio = abs(self.daily_loss) / self.initial_balance
        if daily_loss_ratio >= self.daily_loss_limit:
            return False, f"Daily loss limit reached ({daily_loss_ratio:.2%} >= {self.daily_loss_limit:.2%})"
        
        # Rule 2: Check cooldown period (consecutive losses)
        if self.cooldown_until is not None:
            if datetime.now() < self.cooldown_until:
                remaining = (self.cooldown_until - datetime.now()).total_seconds() / 3600
                return False, f"In cooldown period after 3 consecutive losses. Remaining: {remaining:.1f}h"
            else:
                # Cooldown period expired
                self.cooldown_until = None
                self.consecutive_losses = 0
                logger.info("Cooldown period expired. Trading resumed.")
        
        return True, "OK"
    
    def record_trade(self, symbol: str, pnl: float, pnl_percent: float):
        """
        Record a completed trade
        
        Args:
            symbol: Trading pair
            pnl: Profit/loss in USD
            pnl_percent: Profit/loss in percentage
        """
        trade = {
            'timestamp': datetime.now(),
            'symbol': symbol,
            'pnl': pnl,
            'pnl_percent': pnl_percent,
            'is_loss': pnl < 0
        }
        
        self.trade_history.append(trade)
        self.current_balance += pnl
        self.daily_loss += pnl
        
        # Update consecutive loss counter
        if pnl < 0:
            self.consecutive_losses += 1
            
            # Trigger cooldown if 3 consecutive losses
            if self.consecutive_losses >= self.consecutive_loss_limit:
                self.cooldown_until = datetime.now() + timedelta(hours=config.COOLDOWN_HOURS)
                logger.warning(
                    f"⚠️ {self.consecutive_losses} consecutive losses detected! "
                    f"Trading paused for {config.COOLDOWN_HOURS}h until {self.cooldown_until.strftime('%Y-%m-%d %H:%M:%S')}"
                )
        else:
            # Reset consecutive loss counter on profit
            self.consecutive_losses = 0
        
        logger.info(
            f"Trade recorded: {symbol} | P&L: ${pnl:+.2f} ({pnl_percent:+.2f}%) | "
            f"Balance: ${self.current_balance:.2f} | "
            f"Consecutive losses: {self.consecutive_losses}/{self.consecutive_loss_limit}"
        )
    
    def reset_daily_loss(self):
        """
        Reset daily loss counter (call at end of trading day / midnight)
        """
        logger.info(f"Daily loss reset. Previous: ${self.daily_loss:.2f}")
        self.daily_loss = 0.0
    
    def get_max_position_size(self, entry_price: float) -> float:
        """
        Get maximum position size based on current balance
        
        Args:
            entry_price: Entry price
        
        Returns:
            Maximum position size (amount of base asset)
        """
        max_value = self.current_balance * (config.POSITION_SIZE_PERCENT / 100)
        max_size = max_value / entry_price
        return max_size
    
    def check_max_drawdown(self) -> tuple[bool, float]:
        """
        Check if current drawdown exceeds maximum allowed
        
        Returns:
            (within_limit: bool, current_drawdown_percent: float)
        """
        drawdown = (self.current_balance - self.initial_balance) / self.initial_balance
        drawdown_percent = drawdown * 100
        
        within_limit = drawdown_percent >= -config.MAX_DRAWDOWN_PERCENT
        
        return within_limit, drawdown_percent
    
    def get_stats(self) -> Dict:
        """
        Get current risk control statistics
        
        Returns:
            Dictionary with risk metrics
        """
        drawdown_ok, drawdown = self.check_max_drawdown()
        can_trade_ok, trade_reason = self.can_trade()
        daily_loss_ratio = abs(self.daily_loss) / self.initial_balance
        
        return {
            'initial_balance': self.initial_balance,
            'current_balance': self.current_balance,
            'total_pnl': self.current_balance - self.initial_balance,
            'total_pnl_percent': ((self.current_balance - self.initial_balance) / self.initial_balance) * 100,
            'daily_loss': self.daily_loss,
            'daily_loss_ratio': daily_loss_ratio,
            'daily_loss_limit_ratio': self.daily_loss_limit,
            'consecutive_losses': self.consecutive_losses,
            'consecutive_loss_limit': self.consecutive_loss_limit,
            'cooldown_until': self.cooldown_until,
            'current_drawdown_percent': drawdown,
            'max_drawdown_limit': -config.MAX_DRAWDOWN_PERCENT,
            'drawdown_within_limit': drawdown_ok,
            'can_trade': can_trade_ok,
            'trade_restriction_reason': trade_reason,
            'total_trades': len(self.trade_history),
            'winning_trades': sum(1 for t in self.trade_history if t['pnl'] > 0),
            'losing_trades': sum(1 for t in self.trade_history if t['pnl'] < 0),
            'win_rate': (sum(1 for t in self.trade_history if t['pnl'] > 0) / len(self.trade_history) * 100) if self.trade_history else 0
        }
