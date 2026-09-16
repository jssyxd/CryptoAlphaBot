import pandas as pd
import logging
from datetime import datetime, timedelta
from data.fetcher import DataFetcher
from data.processor import DataProcessor
from strategy.multi_factor import MultiFactorStrategy
from backtest.engine import BacktestEngine
from config.config import config

logger = logging.getLogger(__name__)

class BacktestRunner:
    """Run backtests with different configurations"""
    
    def __init__(self):
        self.fetcher = DataFetcher()
        self.processor = DataProcessor()
    
    def run_backtest(
        self,
        symbol: str,
        timeframe: str = '1h',
        days: int = 90,
        initial_balance: float = 10000
    ) -> dict:
        """
        Run a backtest for a specific symbol
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Candlestick period
            days: Number of days to backtest
            initial_balance: Starting balance
        
        Returns:
            Backtest results
        """
        logger.info(f"Running backtest for {symbol} ({days} days)")
        
        # Calculate required number of candles
        if timeframe == '1h':
            limit = days * 24
        elif timeframe == '4h':
            limit = days * 6
        elif timeframe == '1d':
            limit = days
        else:
            limit = days * 24
        
        # Fetch data
        df = self.fetcher.fetch_ohlcv(symbol, timeframe, limit=limit)
        
        # Clean data
        df = self.processor.clean_data(df)
        
        # Initialize strategy and engine
        strategy = MultiFactorStrategy(symbol, timeframe)
        engine = BacktestEngine(initial_balance=initial_balance)
        
        # Run backtest
        results = engine.run_backtest(df, symbol, strategy)
        
        return results
    
    def run_rolling_window_backtest(
        self,
        symbol: str,
        timeframe: str = '1h',
        total_days: int = 365,
        window_size: int = 90,
        step_size: int = 30
    ) -> list:
        """
        Run rolling window backtest (in-sample vs out-of-sample)
        
        Args:
            symbol: Trading pair
            timeframe: Candlestick period
            total_days: Total historical period
            window_size: Training window size in days
            step_size: Step forward in days
        
        Returns:
            List of backtest results for each window
        """
        logger.info(
            f"Running rolling window backtest for {symbol} "
            f"(total={total_days}d, window={window_size}d, step={step_size}d)"
        )
        
        results = []
        
        # Calculate required total candles
        if timeframe == '1h':
            total_limit = total_days * 24
        elif timeframe == '4h':
            total_limit = total_days * 6
        else:
            total_limit = total_days
        
        # Fetch all data
        df_all = self.fetcher.fetch_ohlcv(symbol, timeframe, limit=total_limit)
        df_all = self.processor.clean_data(df_all)
        
        # Calculate window parameters
        if timeframe == '1h':
            window_candles = window_size * 24
            step_candles = step_size * 24
        elif timeframe == '4h':
            window_candles = window_size * 6
            step_candles = step_size * 6
        else:
            window_candles = window_size
            step_candles = step_size
        
        # Rolling windows
        for start_idx in range(0, len(df_all) - window_candles, step_candles):
            end_idx = start_idx + window_candles
            
            if end_idx > len(df_all):
                break
            
            df_window = df_all.iloc[start_idx:end_idx]
            
            # Run backtest for this window
            strategy = MultiFactorStrategy(symbol, timeframe)
            engine = BacktestEngine(initial_balance=10000)
            
            window_results = engine.run_backtest(df_window, symbol, strategy)
            window_results['start_date'] = df_window.index[0]
            window_results['end_date'] = df_window.index[-1]
            
            results.append(window_results)
            
            logger.info(
                f"Window {len(results)}: {df_window.index[0]} to {df_window.index[-1]} | "
                f"Return: {window_results.get('total_return', 0):.2f}%"
            )
        
        return results
