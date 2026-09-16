#!/usr/bin/env python3
"""
Smoke test for CryptoAlphaBot

- Fetches public BTC/USDT 1h data (no API key needed)
- Runs MultiFactorStrategy + DynamicTakeProfit
- Prints a few signals and dynamic TP values
- Optionally runs a short paper loop (default ~90s)
"""

import sys
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("smoke_test")


def test_data_and_strategy():
    from data.fetcher import DataFetcher
    from data.processor import DataProcessor
    from strategy.multi_factor import MultiFactorStrategy

    logger.info("=== 1. Fetch public OHLCV (BTC/USDT 1h) ===")
    fetcher = DataFetcher()
    df = fetcher.fetch_ohlcv("BTC/USDT", "1h", limit=200)
    logger.info(f"Fetched {len(df)} candles. Last close: {df['close'].iloc[-1]:.2f}")

    logger.info("=== 2. Clean + Strategy signals ===")
    processor = DataProcessor()
    df = processor.clean_data(df)

    strategy = MultiFactorStrategy(symbol="BTC/USDT", timeframe="1h")
    df = strategy.calculate_signals(df)

    # Show last 5 rows of interest
    cols = ["close", "sma_fast", "sma_slow", "rsi", "signal", "dynamic_takeprofit"]
    available = [c for c in cols if c in df.columns]
    print("\nLast 5 signal rows:")
    print(df[available].tail(5).to_string())

    # Count signals
    buy_signals = (df["signal"] == 1).sum()
    sell_signals = (df["signal"] == -1).sum()
    logger.info(f"Buy signals: {buy_signals} | Sell signals: {sell_signals}")

    # Dynamic TP samples
    tp_samples = df.loc[df["signal"] == 1, "dynamic_takeprofit"].dropna()
    if len(tp_samples) > 0:
        logger.info(
            f"Dynamic TP on buy signals: min={tp_samples.min():.2f}% "
            f"mean={tp_samples.mean():.2f}% max={tp_samples.max():.2f}%"
        )
    else:
        logger.info("No buy signals in this window for TP stats.")

    return True


def test_risk_control():
    from risk.risk_control import RiskControl

    logger.info("=== 3. RiskControl basic checks ===")
    risk = RiskControl(initial_balance=10000)
    can, reason = risk.can_trade()
    assert can, reason
    logger.info(f"can_trade={can} ({reason})")

    # Simulate 3 consecutive losses
    for i in range(3):
        risk.record_trade("BTC/USDT", pnl=-100, pnl_percent=-1.0)
    can, reason = risk.can_trade()
    logger.info(f"After 3 losses: can_trade={can} | {reason}")
    assert not can
    return True


def main():
    logger.info(f"Smoke test started at {datetime.now().isoformat()}")
    try:
        test_data_and_strategy()
        test_risk_control()
        logger.info("=== Core unit smoke tests PASSED ===")
    except Exception as e:
        logger.exception(f"Smoke test FAILED: {e}")
        sys.exit(1)

    # Short paper loop (~90s)
    logger.info("=== 4. Running short paper loop (~90s) ===")
    from main import run_paper_loop
    run_paper_loop(duration_seconds=90, poll_interval=20)
    logger.info("Smoke test finished successfully.")


if __name__ == "__main__":
    main()
