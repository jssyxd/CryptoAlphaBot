import pandas as pd
import numpy as np
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class DataProcessor:
    """Process and clean market data"""
    
    @staticmethod
    def clean_data(df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean OHLCV data
        
        Args:
            df: Raw OHLCV DataFrame
        
        Returns:
            Cleaned DataFrame
        """
        df = df.copy()
        
        # Remove NaN values
        df = df.dropna()
        
        # Remove duplicates
        df = df[~df.index.duplicated(keep='last')]
        
        # Sort by timestamp
        df = df.sort_index()
        
        # Ensure numeric columns
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Remove rows with NaN after conversion
        df = df.dropna()
        
        logger.info(f"Cleaned data: {len(df)} rows")
        return df
    
    @staticmethod
    def add_returns(df: pd.DataFrame) -> pd.DataFrame:
        """
        Add return columns to DataFrame
        """
        df = df.copy()
        df['returns'] = df['close'].pct_change()
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        return df
    
    @staticmethod
    def resample(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """
        Resample data to different timeframe
        
        Args:
            df: DataFrame with DatetimeIndex
            timeframe: Target timeframe (e.g., '1h', '4h', '1d')
        
        Returns:
            Resampled DataFrame
        """
        resampler = df.resample(timeframe)
        result = pd.DataFrame({
            'open': resampler['open'].first(),
            'high': resampler['high'].max(),
            'low': resampler['low'].min(),
            'close': resampler['close'].last(),
            'volume': resampler['volume'].sum()
        })
        return result.dropna()
