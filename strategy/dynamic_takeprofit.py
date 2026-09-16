import pandas as pd
import numpy as np
from typing import Optional
import logging
from config.config import config

logger = logging.getLogger(__name__)

class DynamicTakeProfitEngine:
    """
    ⭐ Dynamic Take Profit Engine
    
    Calculates adaptive take profit levels based on:
    1. SMA10/SMA30 crossover angle (穿越夹角)
    2. Historical price curvature (历史曲率)
    
    Formula:
    takeprofit = base + angle_contribution + curvature_contribution
    
    Range: 4% - 15%
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def calculate_takeprofit(
        self,
        df: pd.DataFrame,
        entry_index: int,
        fast_sma_period: int = 10,
        slow_sma_period: int = 30,
        tp_params: dict = None,
        lookback_window: int = 20
    ) -> float:
        """
        Calculate dynamic take profit level for an entry point
        
        Args:
            df: OHLCV DataFrame with SMA columns already calculated
            entry_index: Index of the entry point (where signal == 1)
            fast_sma_period: Period for fast SMA (default 10)
            slow_sma_period: Period for slow SMA (default 30)
            tp_params: Take profit parameters dict
            lookback_window: Number of bars to analyze for curvature (default 20)
        
        Returns:
            Dynamic take profit percentage (4.0 to 15.0)
        """
        if tp_params is None:
            tp_params = config.load_strategy_params()['takeprofit_params']
        
        # Calculate components
        angle = self._calculate_crossover_angle(df, entry_index, fast_sma_period, slow_sma_period)
        curvature = self._calculate_price_curvature(df, entry_index, lookback_window)
        
        # Normalize components to [0, 1] range
        angle_normalized = self._normalize_angle(angle, tp_params['angle_scale'])
        curvature_normalized = self._normalize_curvature(curvature)
        
        # Weighted combination
        base = tp_params['base']
        angle_weight = tp_params['angle_weight']
        curvature_weight = tp_params['curvature_weight']
        
        # Calculate contribution (in percentage points)
        angle_contrib = angle_normalized * angle_weight * (tp_params['max_takeprofit'] - base)
        curvature_contrib = curvature_normalized * curvature_weight * (tp_params['max_takeprofit'] - base)
        
        # Final take profit
        takeprofit = base + angle_contrib + curvature_contrib
        
        # Clamp to min/max range
        takeprofit = np.clip(
            takeprofit,
            tp_params['min_takeprofit'],
            tp_params['max_takeprofit']
        )
        
        self.logger.info(
            f"Dynamic TP calculated at index {entry_index}: "
            f"angle={angle:.2f}°, curvature={curvature:.4f}, "
            f"TP={takeprofit:.2f}%"
        )
        
        return takeprofit
    
    def _calculate_crossover_angle(self, df: pd.DataFrame, entry_index: int, fast_period: int, slow_period: int) -> float:
        """
        Calculate the angle (speed) of SMA crossover
        
        Algorithm:
        1. Calculate SMA difference: diff = SMA_fast - SMA_slow
        2. Look at recent bars to estimate the rate of change
        3. Convert rate of change to angle (0-90 degrees)
        
        Returns:
            Angle in degrees (0-90, where 90 = steepest crossover)
        """
        if entry_index < max(fast_period, slow_period) + 2:
            return 45.0  # Default middle value for insufficient history
        
        # Ensure SMA columns exist
        if 'sma_fast' not in df.columns or 'sma_slow' not in df.columns:
            return 45.0
        
        # Look back 3 bars before entry to calculate angle
        lookback = 3
        if entry_index < lookback:
            lookback = max(1, entry_index - 1)
        
        start_idx = entry_index - lookback
        end_idx = entry_index
        
        # SMA differences
        sma_diffs = df['sma_fast'].iloc[start_idx:end_idx+1] - df['sma_slow'].iloc[start_idx:end_idx+1]
        
        # Calculate rate of change
        price_change = df['close'].iloc[end_idx] - df['close'].iloc[start_idx]
        sma_change = sma_diffs.iloc[-1] - sma_diffs.iloc[0]
        
        if price_change == 0:
            return 45.0
        
        # Calculate slope
        slope = abs(sma_change / price_change) if price_change != 0 else 0
        
        # Convert slope to angle (arctan)
        angle_rad = np.arctan(slope)
        angle_deg = np.degrees(angle_rad) * 1.5  # Scale to 0-90 range
        
        # Clamp to reasonable range
        angle_deg = np.clip(angle_deg, 15.0, 85.0)
        
        return angle_deg
    
    def _calculate_price_curvature(self, df: pd.DataFrame, entry_index: int, window: int = 20) -> float:
        """
        Calculate historical price curvature
        
        Curvature measures the "strength" and "persistence" of the trend:
        - Returns normalized log-returns to measure momentum
        - High curvature = strong uptrend consistency
        - Low curvature = weak or choppy trend
        
        Args:
            df: OHLCV DataFrame
            entry_index: Entry point index
            window: Lookback window (default 20 bars)
        
        Returns:
            Curvature score (0-1 range)
        """
        if entry_index < window:
            # Not enough history, use partial window
            window = max(5, entry_index - 2)
        
        # Get price series for lookback period
        start_idx = max(0, entry_index - window)
        prices = df['close'].iloc[start_idx:entry_index+1].values
        
        if len(prices) < 3:
            return 0.5  # Default middle value
        
        # Calculate log returns
        log_returns = np.diff(np.log(prices))
        
        # Calculate second derivative (curvature)
        # Represents acceleration/deceleration of price movement
        if len(log_returns) < 2:
            return 0.5
        
        second_derivative = np.diff(log_returns)
        
        # Curvature score: mean absolute change in momentum
        curvature_score = np.mean(np.abs(second_derivative))
        
        # Normalize to [0, 1] range
        # Typical range for log returns second derivative is 0-0.01
        curvature_normalized = np.clip(curvature_score / 0.01, 0, 1)
        
        return curvature_normalized
    
    def _normalize_angle(self, angle: float, scale: float = 100) -> float:
        """
        Normalize angle from 0-90 degrees to 0-1 range
        
        Args:
            angle: Angle in degrees (0-90)
            scale: Scaling factor (default 100)
        
        Returns:
            Normalized value (0-1)
        """
        # Map 15-85 degrees to roughly 0-1
        # With scale factor for fine-tuning
        normalized = (angle - 15.0) / 70.0  # 15-85 range
        return np.clip(normalized, 0, 1)
    
    def _normalize_curvature(self, curvature: float) -> float:
        """
        Normalize curvature score to 0-1 range
        
        Args:
            curvature: Curvature value (typically 0-1)
        
        Returns:
            Normalized value (0-1)
        """
        return np.clip(curvature, 0, 1)
