import ccxt
import pandas as pd
from datetime import datetime
from config.config import config
import logging
import os

logger = logging.getLogger(__name__)

# Preferred public exchanges when Binance main is geo-blocked
FALLBACK_EXCHANGES = ["binanceus", "okx", "kucoin", "gate", "kraken", "bitget"]


class DataFetcher:
    """Fetch market data via CCXT with multi-exchange fallback."""

    def __init__(self, exchange_id: str = None):
        self.exchange_id = exchange_id or os.getenv("EXCHANGE_ID", "binanceus")
        self.exchange = self._create_exchange(self.exchange_id)
        logger.info(f"DataFetcher using exchange={self.exchange_id}")

    def _create_exchange(self, eid: str):
        cls = getattr(ccxt, eid, None)
        if cls is None:
            raise ValueError(f"Unknown exchange: {eid}")
        return cls({
            "apiKey": config.BINANCE_API_KEY or None,
            "secret": config.BINANCE_API_SECRET or None,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })

    def _try_exchanges(self, fn):
        """Try primary then fallbacks."""
        tried = [self.exchange_id] + [e for e in FALLBACK_EXCHANGES if e != self.exchange_id]
        last_err = None
        for eid in tried:
            try:
                if eid != self.exchange_id:
                    self.exchange = self._create_exchange(eid)
                    self.exchange_id = eid
                    logger.warning(f"Switched to fallback exchange: {eid}")
                return fn()
            except Exception as e:
                last_err = e
                logger.warning(f"{eid} failed: {type(e).__name__}: {str(e)[:80]}")
        raise RuntimeError(f"All exchanges failed. Last error: {last_err}")

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
        def _do():
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            df = df.set_index("timestamp")
            logger.info(f"Fetched {len(df)} candles for {symbol} ({timeframe}) via {self.exchange_id}")
            return df

        return self._try_exchanges(_do)

    def fetch_ticker(self, symbol: str):
        return self._try_exchanges(lambda: self.exchange.fetch_ticker(symbol))

    def get_balance(self):
        return self.exchange.fetch_balance()
