#!/usr/bin/env python3
"""
CryptoAlphaBot - Main entry point (Paper / Dry-run mode)

Usage:
    python main.py

Runs a continuous paper-trading loop:
- Fetches public OHLCV from Binance
- Calculates multi-factor signals + dynamic take-profit
- Applies risk rules
- Logs decisions (no real orders unless TRADING_MODE=live and keys are set)
"""

import time
import logging
from datetime import datetime
from config.config import config
from data.fetcher import DataFetcher
from data.processor import DataProcessor
from strategy.multi_factor import MultiFactorStrategy
from risk.risk_control import RiskControl
from risk.position_manager import PositionManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


def run_paper_loop(duration_seconds: int = 120, poll_interval: int = 30):
    """
    Run paper trading loop for a limited time (default 2 minutes for smoke test).
    """
    symbols = config.load_symbols()
    logger.info(f"Starting CryptoAlphaBot paper loop | symbols={symbols} | mode={config.TRADING_MODE}")
    logger.info(f"Will run for ~{duration_seconds}s (poll every {poll_interval}s)")

    fetcher = DataFetcher()
    processor = DataProcessor()
    risk = RiskControl(config.INITIAL_BALANCE)
    positions = PositionManager(config.INITIAL_BALANCE)

    strategies = {
        sym: MultiFactorStrategy(symbol=sym, timeframe=config.TIMEFRAME)
        for sym in symbols
    }

    start = time.time()
    cycle = 0

    while time.time() - start < duration_seconds:
        cycle += 1
        logger.info(f"===== Cycle {cycle} | {datetime.now().isoformat()} =====")

        can_trade, reason = risk.can_trade()
        if not can_trade:
            logger.warning(f"Trading paused by risk control: {reason}")
            time.sleep(poll_interval)
            continue

        for symbol in symbols:
            try:
                # Public data — no API key required
                df = fetcher.fetch_ohlcv(symbol, config.TIMEFRAME, limit=config.KLINES_HISTORY_LENGTH)
                df = processor.clean_data(df)

                strategy = strategies[symbol]
                df = strategy.calculate_signals(df)

                last = df.iloc[-1]
                signal = int(last["signal"])
                price = float(last["close"])
                dyn_tp = float(last.get("dynamic_takeprofit", 0) or 0)

                logger.info(
                    f"{symbol} | price={price:.2f} | signal={signal} | "
                    f"RSI={last.get('rsi', 0):.1f} | dyn_tp={dyn_tp:.2f}%"
                )

                # Paper position management (no real orders)
                if signal == 1 and not positions.has_position(symbol):
                    sl = price * (1 - config.STOP_LOSS_PERCENT / 100)
                    tp = price * (1 + (dyn_tp or config.BASE_TAKE_PROFIT) / 100)
                    size = positions.calculate_position_size(symbol, price, sl)
                    positions.open_position(symbol, "buy", price, sl, tp, size)
                    logger.info(f"[PAPER] OPEN long {symbol} size={size:.6f} SL={sl:.2f} TP={tp:.2f}")

                elif positions.has_position(symbol):
                    pos = positions.get_position(symbol)
                    # Check SL / TP / sell signal
                    exit_reason = None
                    if price <= pos["stop_loss"]:
                        exit_reason = "stop_loss"
                    elif price >= pos["take_profit"]:
                        exit_reason = "take_profit"
                    elif signal == -1:
                        exit_reason = "signal"

                    if exit_reason:
                        closed = positions.close_position(symbol, price)
                        if closed:
                            risk.record_trade(symbol, closed["pnl"], closed["pnl_percent"])
                            logger.info(
                                f"[PAPER] CLOSE {symbol} reason={exit_reason} "
                                f"PnL={closed['pnl']:.2f} ({closed['pnl_percent']:.2f}%)"
                            )

            except Exception as e:
                logger.exception(f"Error processing {symbol}: {e}")

        # Stats
        stats = risk.get_stats()
        logger.info(
            f"Balance={stats['current_balance']:.2f} | "
            f"PnL={stats['total_pnl']:.2f} ({stats['total_pnl_percent']:.2f}%) | "
            f"Trades={stats['total_trades']} | WinRate={stats['win_rate']:.1f}%"
        )

        remaining = duration_seconds - (time.time() - start)
        if remaining <= 0:
            break
        time.sleep(min(poll_interval, remaining))

    logger.info("Paper loop finished.")
    final = risk.get_stats()
    logger.info(f"Final stats: {final}")
    return final


if __name__ == "__main__":
    # Default: 2-minute smoke run
    run_paper_loop(duration_seconds=120, poll_interval=25)
