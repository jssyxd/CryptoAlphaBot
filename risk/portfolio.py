import pandas as pd
import logging
from typing import Dict, List
from config.config import config

logger = logging.getLogger(__name__)

class PortfolioManager:
    """Manage overall portfolio and allocation"""
    
    def __init__(self, initial_balance: float = None):
        self.initial_balance = initial_balance or config.INITIAL_BALANCE
        self.current_balance = self.initial_balance
        self.positions = {}  # symbol -> position data
        self.trades = []
    
    def update_balance(self, amount: float):
        """Update account balance"""
        self.current_balance += amount
        logger.info(f"Balance updated: ${self.current_balance:.2f}")
    
    def get_portfolio_value(self) -> float:
        """Get total portfolio value (balance + open positions)"""
        position_value = sum(
            pos['entry_price'] * pos['position_size']
            for pos in self.positions.values()
        )
        return self.current_balance + position_value
    
    def get_allocation(self) -> Dict[str, float]:
        """Get portfolio allocation by symbol"""
        total_value = self.get_portfolio_value()
        if total_value == 0:
            return {}
        
        allocation = {}
        for symbol, pos in self.positions.items():
            pos_value = pos['entry_price'] * pos['position_size']
            allocation[symbol] = (pos_value / total_value) * 100
        
        # Add cash allocation
        allocation['CASH'] = (self.current_balance / total_value) * 100
        
        return allocation
    
    def get_stats(self) -> Dict:
        """Get portfolio statistics"""
        total_value = self.get_portfolio_value()
        total_pnl = total_value - self.initial_balance
        total_pnl_percent = (total_pnl / self.initial_balance) * 100
        
        return {
            'initial_balance': self.initial_balance,
            'current_cash': self.current_balance,
            'total_portfolio_value': total_value,
            'total_pnl': total_pnl,
            'total_pnl_percent': total_pnl_percent,
            'open_positions': len(self.positions),
            'num_trades': len(self.trades)
        }
