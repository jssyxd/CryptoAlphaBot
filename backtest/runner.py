"""
Backtest runner + Walk-Forward analysis.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List

import pandas as pd

from backtest.engine import BacktestEngine
from config.config import config
from data.fetcher import DataFetcher
from data.processor import DataProcessor
from strategy.multi_factor import MultiFactorStrategy

logger = logging.getLogger(__name__)


class BacktestRunner:
    def __init__(self, exchange_id: str = "binanceus"):
        self.fetcher = DataFetcher(exchange_id=exchange_id)
        self.processor = DataProcessor()

    def run_backtest(
        self,
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        limit: int = 2000,
        initial_balance: float = 10000,
        commission: float = 0.001,
        slippage: float = 0.0005,
    ) -> Dict:
        logger.info(f"Full backtest {symbol} limit={limit}")
        df = self.fetcher.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = self.processor.clean_data(df)
        strategy = MultiFactorStrategy(symbol, timeframe)
        engine = BacktestEngine(
            initial_balance=initial_balance,
            commission=commission,
            slippage=slippage,
            persist=True,
        )
        return engine.run_backtest(df, symbol, strategy)

    def run_walk_forward(
        self,
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        total_bars: int = 3000,
        train_bars: int = 720,   # ~30 days of 1h
        test_bars: int = 168,    # ~7 days
        step_bars: int = 168,
        initial_balance: float = 10000,
    ) -> Dict:
        """
        Rolling Walk-Forward:
        train on [i : i+train], test on [i+train : i+train+test], step forward.
        """
        logger.info(
            f"Walk-Forward {symbol} total={total_bars} train={train_bars} "
            f"test={test_bars} step={step_bars}"
        )
        df = self.fetcher.fetch_ohlcv(symbol, timeframe, limit=total_bars)
        df = self.processor.clean_data(df)
        if len(df) < train_bars + test_bars:
            raise ValueError(f"Not enough data: {len(df)} < {train_bars + test_bars}")

        folds = []
        i = 0
        while i + train_bars + test_bars <= len(df):
            train_df = df.iloc[i : i + train_bars].copy()
            test_df = df.iloc[i + train_bars : i + train_bars + test_bars].copy()

            # In-sample (optional diagnostics)
            strat_is = MultiFactorStrategy(symbol, timeframe)
            eng_is = BacktestEngine(initial_balance, persist=False)
            is_stats = eng_is.run_backtest(train_df, symbol, strat_is)

            # Out-of-sample
            strat_oos = MultiFactorStrategy(symbol, timeframe)
            eng_oos = BacktestEngine(initial_balance, persist=False)
            oos_stats = eng_oos.run_backtest(test_df, symbol, strat_oos)

            fold = {
                "fold": len(folds) + 1,
                "train_start": str(train_df.index[0]),
                "train_end": str(train_df.index[-1]),
                "test_start": str(test_df.index[0]),
                "test_end": str(test_df.index[-1]),
                "is_return": is_stats.get("total_return", 0),
                "is_sharpe": is_stats.get("sharpe_ratio", 0),
                "is_trades": is_stats.get("total_trades", 0),
                "oos_return": oos_stats.get("total_return", 0),
                "oos_sharpe": oos_stats.get("sharpe_ratio", 0),
                "oos_max_dd": oos_stats.get("max_drawdown", 0),
                "oos_trades": oos_stats.get("total_trades", 0),
                "oos_win_rate": oos_stats.get("win_rate", 0),
            }
            folds.append(fold)
            logger.info(
                f"Fold {fold['fold']}: OOS return={fold['oos_return']:.2f}% "
                f"Sharpe={fold['oos_sharpe']:.2f} DD={fold['oos_max_dd']:.2f}% trades={fold['oos_trades']}"
            )
            i += step_bars

        if not folds:
            return {"folds": [], "summary": {}}

        oos_returns = [f["oos_return"] for f in folds]
        oos_sharpes = [f["oos_sharpe"] for f in folds]
        summary = {
            "n_folds": len(folds),
            "avg_oos_return": sum(oos_returns) / len(oos_returns),
            "avg_oos_sharpe": sum(oos_sharpes) / len(oos_sharpes),
            "pct_positive_folds": sum(1 for r in oos_returns if r > 0) / len(oos_returns) * 100,
            "worst_oos_return": min(oos_returns),
            "best_oos_return": max(oos_returns),
        }
        logger.info(f"Walk-Forward summary: {summary}")
        return {"folds": folds, "summary": summary}


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )
    runner = BacktestRunner(exchange_id="binanceus")

    print("\n========== FULL BACKTEST (BTC/USDT 1h, ~2000 bars) ==========\n")
    stats = runner.run_backtest(symbol="BTC/USDT", timeframe="1h", limit=2000)
    for k in ["initial_balance", "final_balance", "total_return", "total_trades",
              "win_rate", "profit_factor", "max_drawdown", "sharpe_ratio", "total_fees"]:
        print(f"  {k}: {stats.get(k)}")

    print("\n========== WALK-FORWARD ==========\n")
    wf = runner.run_walk_forward(
        symbol="BTC/USDT",
        timeframe="1h",
        total_bars=2500,
        train_bars=720,
        test_bars=168,
        step_bars=168,
    )
    print("Summary:", wf["summary"])
    for f in wf["folds"]:
        print(
            f"  Fold {f['fold']}: OOS ret={f['oos_return']:.2f}% "
            f"Sharpe={f['oos_sharpe']:.2f} DD={f['oos_max_dd']:.2f}% trades={f['oos_trades']}"
        )


if __name__ == "__main__":
    main()
