import ccxt
import logging
from typing import Dict, List, Optional
from config.config import config

logger = logging.getLogger(__name__)

class BinanceBroker:
    """Interface with Binance exchange"""
    
    def __init__(self, api_key: str = None, api_secret: str = None, sandbox: bool = False):
        self.api_key = api_key or config.BINANCE_API_KEY
        self.api_secret = api_secret or config.BINANCE_API_SECRET
        self.sandbox = sandbox
        
        exchange_config = {
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
        }
        
        if sandbox:
            exchange_config['urls'] = {
                'api': 'https://testnet.binance.vision/api',
            }
        
        self.exchange = ccxt.binance(exchange_config)
        logger.info(f"Binance broker initialized (sandbox={sandbox})")
    
    def get_balance(self) -> Dict:
        """Get account balance"""
        try:
            balance = self.exchange.fetch_balance()
            return balance
        except Exception as e:
            logger.error(f"Error fetching balance: {str(e)}")
            raise
    
    def get_ticker(self, symbol: str) -> Dict:
        """Get current ticker for a symbol"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker
        except Exception as e:
            logger.error(f"Error fetching ticker for {symbol}: {str(e)}")
            raise
    
    def create_market_buy_order(self, symbol: str, amount: float) -> Dict:
        """Create market buy order"""
        try:
            order = self.exchange.create_market_buy_order(symbol, amount)
            logger.info(f"Market buy order created: {symbol} {amount}")
            return order
        except Exception as e:
            logger.error(f"Error creating buy order: {str(e)}")
            raise
    
    def create_market_sell_order(self, symbol: str, amount: float) -> Dict:
        """Create market sell order"""
        try:
            order = self.exchange.create_market_sell_order(symbol, amount)
            logger.info(f"Market sell order created: {symbol} {amount}")
            return order
        except Exception as e:
            logger.error(f"Error creating sell order: {str(e)}")
            raise
    
    def create_limit_buy_order(self, symbol: str, amount: float, price: float) -> Dict:
        """Create limit buy order"""
        try:
            order = self.exchange.create_limit_buy_order(symbol, amount, price)
            logger.info(f"Limit buy order created: {symbol} {amount} @ {price}")
            return order
        except Exception as e:
            logger.error(f"Error creating limit buy order: {str(e)}")
            raise
    
    def create_limit_sell_order(self, symbol: str, amount: float, price: float) -> Dict:
        """Create limit sell order"""
        try:
            order = self.exchange.create_limit_sell_order(symbol, amount, price)
            logger.info(f"Limit sell order created: {symbol} {amount} @ {price}")
            return order
        except Exception as e:
            logger.error(f"Error creating limit sell order: {str(e)}")
            raise
    
    def fetch_order(self, order_id: str, symbol: str) -> Dict:
        """Fetch order status"""
        try:
            order = self.exchange.fetch_order(order_id, symbol)
            return order
        except Exception as e:
            logger.error(f"Error fetching order {order_id}: {str(e)}")
            raise
    
    def cancel_order(self, order_id: str, symbol: str) -> Dict:
        """Cancel an order"""
        try:
            order = self.exchange.cancel_order(order_id, symbol)
            logger.info(f"Order {order_id} cancelled")
            return order
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {str(e)}")
            raise
