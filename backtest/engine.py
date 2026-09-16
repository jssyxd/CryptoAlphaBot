import pandas as pd
import numpy as np
from datetime import datetime
import logging
from typing import Dict, Tuple
from data.fetcher import DataFetcher
from data.processor import DataProcessor
from strategy.multi_factor import MultiFactorStrategy
from risk.position_manager import PositionManager
from risk.risk_control import RiskControl
from config.config import config

logger = logging.getLogger(__name__)

class BacktestEngine:
    """Core backtesting engine for strategy validation"""
    
    def __init__(
        self,
        initial_balance: float = None,
        commission: float = 0.001,
        slippage: float = 0.0005
    ):
        self.initial_balance = initial_balance or config.INITIAL_BALANCE
        self.commission = commission
        self.slippage = slippage
        
        self.position_manager = PositionManager(self.initial_balance)
        self.risk_control = RiskControl(self.initial_balance)
        self.data_processor = DataProcessor()
        
        self.trades = []
        self.equity_curve = []
        self.signals = []
    
    def run_backtest(
        self,
        df: pd.DataFrame,
        symbol: str,
        strategy: MultiFactorStrategy
    ) -> Dict:
        """
        Run backtest on historical data
        
        Args:
            df: OHLCV DataFrame
            symbol: Trading pair
            strategy: Strategy instance
        
        Returns:
            Backtest results dictionary
        """
        logger.info(f"Starting backtest for {symbol}")
        
        # Calculate signals
        df = strategy.calculate_signals(df)
        
        # Iterate through data
        for i in range(len(df)):
            current_price = df['close'].iloc[i]
            current_time = df.index[i]
            current_signal = df['signal'].iloc[i]
            dynamic_tp = df['dynamic_takeprofit'].iloc[i]
            
            # Check if we can trade
            can_trade, trade_reason = self.risk_control.can_trade()
            
            # Process exit signals for open positions
            if self.position_manager.has_position(symbol):
                position = self.position_manager.get_position(symbol)
                pnl = self._calculate_pnl(position, current_price)
                pnl_percent = pnl / position['entry_value'] * 100
                
                # Check exit conditions
                exit_reason = None
                
                # Stop loss
                if current_price <= position['stop_loss']:
                    exit_reason = 'stop_loss'
                
                # Take profit
                elif current_price >= position['take_profit']:
                    exit_reason = 'take_profit'
                
                # Sell signal
                elif current_signal == -1:
                    exit_reason = 'signal'
                
                if exit_reason:
                    closed_pos = self.position_manager.close_position(symbol, current_price)
                    self.risk_control.record_trade(symbol, closed_pos['pnl'], closed_pos['pnl_percent'])
                    
                    self.trades.append({
                        'entry_time': closed_pos['entry_time'],
                        'exit_time': closed_pos['exit_time'],
                        'entry_price': closed_pos['entry_price'],
                        'exit_price': closed_pos['exit_price'],
                        'pnl': closed_pos['pnl'],
                        'pnl_percent': closed_pos['pnl_percent'],
                        'exit_reason': exit_reason
                    })
            
            # Process entry signals
            if current_signal == 1 and not self.position_manager.has_position(symbol) and can_trade:
                # Calculate position size
                stop_loss_price = current_price * (1 - config.STOP_LOSS_PERCENT / 100)
                position_size = self.position_manager.calculate_position_size(
                    symbol,
                    current_price,
                    stop_loss_price
                )
                
                # Calculate take profit (use dynamic TP)
                take_profit_price = current_price * (1 + dynamic_tp / 100)
                
                # Open position
                self.position_manager.open_position(
                    symbol,
                    'buy',
                    current_price,
                    stop_loss_price,
                    take_profit_price,
                    position_size
                )
            
            # Record equity
            portfolio_value = self.position_manager.account_balance
            if self.position_manager.has_position(symbol):
                position = self.position_manager.get_position(symbol)
                portfolio_value += position['entry_price'] * position['position_size']
            
            self.equity_curve.append({
                'time': current_time,
                'equity': portfolio_value,
                'balance': self.position_manager.account_balance
            })
        
        # Calculate statistics
        stats = self._calculate_statistics()
        
        logger.info(f"Backtest completed for {symbol}")
        logger.info(f"Total trades: {len(self.trades)}")
        logger.info(f"Final equity: ${self.risk_control.current_balance:.2f}")
        
        return stats
    
    def _calculate_pnl(self, position: Dict, current_price: float) -> float:
        """Calculate P&L for a position"""
        if position['side'] == 'buy':
            return (current_price - position['entry_price']) * position['position_size']
        else:
            return (position['entry_price'] - current_price) * position['position_size']
    
    def _calculate_statistics(self) -> Dict:
        """Calculate backtest statistics"""
        if not self.trades:
            return {'error': 'No trades executed'}
        
        trades_df = pd.DataFrame(self.trades)
        equity_df = pd.DataFrame(self.equity_curve)
        
        total_return = (self.risk_control.current_balance - self.initial_balance) / self.initial_balance
        annual_return = total_return * 252  # Assuming 252 trading days per year
        
        # Win rate
        winning_trades = len(trades_df[trades_df['pnl'] > 0])
        total_trades = len(trades_df)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        # Profit factor
        total_profit = trades_df[trades_df['pnl'] > 0]['pnl'].sum()
        total_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum())
        profit_factor = total_profit / total_loss if total_loss > 0 else 0
        
        # Max drawdown
        equity_df['running_max'] = equity_df['equity'].expanding().max()
        equity_df['drawdown'] = (equity_df['equity'] - equity_df['running_max']) / equity_df['running_max']
        max_drawdown = equity_df['drawdown'].min()
        
        # Sharpe ratio
        returns = equity_df['equity'].pct_change().dropna()
        if len(returns) > 0 and returns.std() > 0:
            sharpe = (returns.mean() / returns.std()) * np.sqrt(252)
        else:
            sharpe = 0
        
        return {
            'initial_balance': self.initial_balance,
            'final_balance': self.risk_control.current_balance,
            'total_return': total_return * 100,
            'annual_return': annual_return * 100,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': total_trades - winning_trades,
            'win_rate': win_rate * 100,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown * 100,
            'sharpe_ratio': sharpe,
            'avg_trade_profit': trades_df['pnl'].mean(),
            'total_profit': total_profit,
            'total_loss': -total_loss,
            'trades': self.trades
        }
