from abc import ABC, abstractmethod
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class BaseStrategy(ABC):
    """Base class for all trading strategies"""
    
    def __init__(self, symbol: str, timeframe: str = '1h'):
        self.symbol = symbol
        self.timeframe = timeframe
        self.signals = {}
    
    @abstractmethod
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate trading signals
        
        Args:
            df: OHLCV DataFrame
        
        Returns:
            DataFrame with signal columns
        """
        pass
    
    def validate_data(self, df: pd.DataFrame) -> bool:
        """
        Validate data quality
        """
        if df is None or len(df) == 0:
            logger.warning(f"Empty or None data for {self.symbol}")
            return False
        
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
            logger.warning(f"Missing required columns for {self.symbol}")
            return False
        
        if df.isnull().any().any():
            logger.warning(f"NaN values found in data for {self.symbol}")
            return False
        
        return True
