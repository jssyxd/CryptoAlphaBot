import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class OrderExecutor:
    """Execute trades based on signals"""
    
    def __init__(self, broker):
        self.broker = broker
        self.executed_orders = []
    
    def execute_buy(self, symbol: str, amount: float, order_type: str = 'market') -> Optional[Dict]:
        """
        Execute a buy order
        
        Args:
            symbol: Trading pair
            amount: Amount to buy
            order_type: 'market' or 'limit'
        
        Returns:
            Order result
        """
        try:
            if order_type == 'market':
                order = self.broker.create_market_buy_order(symbol, amount)
            else:
                # For limit orders, use current price
                ticker = self.broker.get_ticker(symbol)
                price = ticker['last']
                order = self.broker.create_limit_buy_order(symbol, amount, price)
            
            self.executed_orders.append(order)
            logger.info(f"Buy order executed: {symbol} {amount}")
            return order
        
        except Exception as e:
            logger.error(f"Error executing buy order: {str(e)}")
            return None
    
    def execute_sell(self, symbol: str, amount: float, order_type: str = 'market') -> Optional[Dict]:
        """
        Execute a sell order
        
        Args:
            symbol: Trading pair
            amount: Amount to sell
            order_type: 'market' or 'limit'
        
        Returns:
            Order result
        """
        try:
            if order_type == 'market':
                order = self.broker.create_market_sell_order(symbol, amount)
            else:
                # For limit orders, use current price
                ticker = self.broker.get_ticker(symbol)
                price = ticker['last']
                order = self.broker.create_limit_sell_order(symbol, amount, price)
            
            self.executed_orders.append(order)
            logger.info(f"Sell order executed: {symbol} {amount}")
            return order
        
        except Exception as e:
            logger.error(f"Error executing sell order: {str(e)}")
            return None
    
    def get_order_status(self, order_id: str, symbol: str) -> Optional[Dict]:
        """Get order status"""
        try:
            return self.broker.fetch_order(order_id, symbol)
        except Exception as e:
            logger.error(f"Error getting order status: {str(e)}")
            return None
    
    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an order"""
        try:
            self.broker.cancel_order(order_id, symbol)
            logger.info(f"Order {order_id} cancelled")
            return True
        except Exception as e:
            logger.error(f"Error cancelling order: {str(e)}")
            return False
