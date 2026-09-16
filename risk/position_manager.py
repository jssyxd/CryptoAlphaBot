import pandas as pd
import logging
from typing import Optional, Dict
from datetime import datetime
from config.config import config

logger = logging.getLogger(__name__)

class PositionManager:
    """Manage trading positions and orders"""
    
    def __init__(self, account_balance: float = None):
        self.account_balance = account_balance or config.INITIAL_BALANCE
        self.positions = {}  # symbol -> position data
        self.orders = {}  # order_id -> order data
    
    def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss_price: float
    ) -> float:
        """
        Calculate position size based on risk management rules
        
        Args:
            symbol: Trading pair
            entry_price: Entry price
            stop_loss_price: Stop loss price
        
        Returns:
            Position size (amount of base asset)
        """
        # Maximum position size is 10% of account
        max_position_value = self.account_balance * (config.POSITION_SIZE_PERCENT / 100)
        
        # Risk per trade is the difference between entry and SL
        risk_amount = abs(entry_price - stop_loss_price)
        
        if risk_amount == 0:
            return 0
        
        # Position size that would risk 1% of account at SL
        position_size = (self.account_balance * 0.01) / risk_amount
        
        # Cap at max position size
        position_value = position_size * entry_price
        if position_value > max_position_value:
            position_size = max_position_value / entry_price
        
        logger.info(
            f"Calculated position size for {symbol}: {position_size:.8f} "
            f"(value: ${position_value:.2f})"
        )
        
        return position_size
    
    def open_position(
        self,
        symbol: str,
        side: str,  # 'buy' or 'sell'
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        position_size: float
    ) -> Dict:
        """
        Open a new position
        
        Args:
            symbol: Trading pair
            side: 'buy' or 'sell'
            entry_price: Entry price
            stop_loss: Stop loss price/percentage
            take_profit: Take profit price/percentage
            position_size: Position size
        
        Returns:
            Position dictionary
        """
        position = {
            'symbol': symbol,
            'side': side,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'position_size': position_size,
            'entry_time': datetime.now(),
            'entry_value': entry_price * position_size,
            'status': 'open'
        }
        
        self.positions[symbol] = position
        logger.info(f"Opened {side} position for {symbol} at ${entry_price}")
        
        return position
    
    def close_position(self, symbol: str, exit_price: float) -> Optional[Dict]:
        """
        Close an existing position
        
        Args:
            symbol: Trading pair
            exit_price: Exit price
        
        Returns:
            Closed position with P&L info
        """
        if symbol not in self.positions:
            logger.warning(f"No open position for {symbol}")
            return None
        
        position = self.positions[symbol]
        exit_value = exit_price * position['position_size']
        
        if position['side'] == 'buy':
            pnl = exit_value - position['entry_value']
            pnl_percent = (exit_price - position['entry_price']) / position['entry_price'] * 100
        else:  # sell
            pnl = position['entry_value'] - exit_value
            pnl_percent = (position['entry_price'] - exit_price) / position['entry_price'] * 100
        
        position['exit_price'] = exit_price
        position['exit_time'] = datetime.now()
        position['pnl'] = pnl
        position['pnl_percent'] = pnl_percent
        position['status'] = 'closed'
        position['hold_time'] = (position['exit_time'] - position['entry_time']).total_seconds() / 3600  # hours
        
        # Update account balance
        self.account_balance += pnl
        
        del self.positions[symbol]
        
        logger.info(
            f"Closed {position['side']} position for {symbol} at ${exit_price} "
            f"| P&L: ${pnl:.2f} ({pnl_percent:.2f}%)"
        )
        
        return position
    
    def get_position(self, symbol: str) -> Optional[Dict]:
        """Get current position for a symbol"""
        return self.positions.get(symbol)
    
    def get_open_positions(self) -> Dict:
        """Get all open positions"""
        return self.positions.copy()
    
    def has_position(self, symbol: str) -> bool:
        """Check if there's an open position for a symbol"""
        return symbol in self.positions
