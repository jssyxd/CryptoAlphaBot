import pandas as pd
import numpy as np
from .base import BaseStrategy
from .indicators import TechnicalIndicators
from .dynamic_takeprofit import DynamicTakeProfitEngine
from config.config import config
import logging

logger = logging.getLogger(__name__)

class MultiFactorStrategy(BaseStrategy):
    """
    Multi-factor quantitative trading strategy
    Combines SMA, RSI, MACD, and Bollinger Bands
    """
    
    def __init__(self, symbol: str, timeframe: str = '1h', params: dict = None):
        super().__init__(symbol, timeframe)
        self.params = params or self._get_default_params()
        self.indicators = TechnicalIndicators()
        self.tp_engine = DynamicTakeProfitEngine()
        
        # Trading state
        self.in_position = False
        self.entry_price = None
        self.entry_index = None
        self.stop_loss = None
        self.take_profit = None
    
    def _get_default_params(self) -> dict:
        """Load default parameters from config"""
        return config.load_strategy_params()
    
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate multi-factor signals
        
        Args:
            df: OHLCV DataFrame
        
        Returns:
            DataFrame with additional signal columns
        """
        if not self.validate_data(df):
            return df
        
        df = df.copy()
        
        # Calculate technical indicators
        fast_sma = self.params['sma_params']['fast_period']
        slow_sma = self.params['sma_params']['slow_period']
        
        df['sma_fast'] = self.indicators.sma(df['close'], fast_sma)
        df['sma_slow'] = self.indicators.sma(df['close'], slow_sma)
        
        # RSI
        rsi_period = self.params['rsi_params']['period']
        df['rsi'] = self.indicators.rsi(df['close'], rsi_period)
        
        # MACD
        macd_params = self.params['macd_params']
        df['macd'], df['macd_signal'], df['macd_histogram'] = self.indicators.macd(
            df['close'],
            macd_params['fast_period'],
            macd_params['slow_period'],
            macd_params['signal_period']
        )
        
        # Bollinger Bands
        bb_params = self.params['bollinger_params']
        df['bb_upper'], df['bb_middle'], df['bb_lower'] = self.indicators.bollinger_bands(
            df['close'],
            bb_params['period'],
            bb_params['std_dev']
        )
        
        # Detect SMA crossover
        df['sma_crossover'] = self.indicators.calculate_crossover(df['sma_fast'], df['sma_slow'])
        
        # Generate signals based on multiple factors
        df['signal'] = self._generate_composite_signal(df)
        
        # Dynamic take profit calculation
        df['dynamic_takeprofit'] = self._calculate_dynamic_takeprofit(df)
        
        return df
    
    def _generate_composite_signal(self, df: pd.DataFrame) -> pd.Series:
        """
        Generate buy/sell signals based on multiple factors
        
        Signal values:
        1: Strong buy signal
        0: Hold/No signal
        -1: Strong sell signal
        """
        signal = pd.Series(0, index=df.index)
        
        rsi_overbought = self.params['rsi_params']['overbought']
        rsi_oversold = self.params['rsi_params']['oversold']
        
        for i in range(len(df)):
            if i < self.params['sma_params']['slow_period']:
                continue
            
            # Buy conditions
            if (df['sma_crossover'].iloc[i] == 1 and  # Golden cross
                df['rsi'].iloc[i] < rsi_overbought and  # RSI not overbought
                df['macd_histogram'].iloc[i] > 0 and  # MACD positive
                df['close'].iloc[i] > df['bb_lower'].iloc[i]):  # Price above lower BB
                signal.iloc[i] = 1
            
            # Sell conditions
            elif (df['sma_crossover'].iloc[i] == -1 or  # Death cross
                  (df['rsi'].iloc[i] > rsi_overbought and df['macd_histogram'].iloc[i] < 0)):  # RSI overbought and MACD negative
                signal.iloc[i] = -1
        
        return signal
    
    def _calculate_dynamic_takeprofit(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate dynamic take profit for each entry point
        """
        takeprofit = pd.Series(0.0, index=df.index)
        
        for i in range(len(df)):
            if df['signal'].iloc[i] == 1:  # Buy signal detected
                # Use dynamic TP engine to calculate TP based on angle and curvature
                tp = self.tp_engine.calculate_takeprofit(
                    df,
                    entry_index=i,
                    fast_sma_period=self.params['sma_params']['fast_period'],
                    slow_sma_period=self.params['sma_params']['slow_period'],
                    tp_params=self.params['takeprofit_params']
                )
                takeprofit.iloc[i] = tp
        
        return takeprofit
