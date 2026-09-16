import os
from dotenv import load_dotenv
from pathlib import Path
import json

load_dotenv()

class Config:
    """Global configuration management"""

    PROJECT_ROOT = Path(__file__).parent.parent
    DATA_DIR = PROJECT_ROOT / "data"
    LOG_DIR = PROJECT_ROOT / "logs"

    DATA_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)

    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
    BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

    TRADING_MODE = os.getenv("TRADING_MODE", "sandbox")
    INITIAL_BALANCE = float(os.getenv("INITIAL_BALANCE", 10000))
    TIMEFRAME = os.getenv("TIMEFRAME", "1h")
    EXCHANGE_ID = os.getenv("EXCHANGE_ID", "binanceus")

    FAST_SMA_PERIOD = int(os.getenv("FAST_SMA_PERIOD", 10))
    SLOW_SMA_PERIOD = int(os.getenv("SLOW_SMA_PERIOD", 30))
    RSI_PERIOD = int(os.getenv("RSI_PERIOD", 14))
    RSI_OVERBOUGHT = float(os.getenv("RSI_OVERBOUGHT", 70))
    RSI_OVERSOLD = float(os.getenv("RSI_OVERSOLD", 30))

    STOP_LOSS_PERCENT = float(os.getenv("STOP_LOSS_PERCENT", 2.0))
    BASE_TAKE_PROFIT = float(os.getenv("BASE_TAKE_PROFIT", 5.0))
    POSITION_SIZE_PERCENT = float(os.getenv("POSITION_SIZE_PERCENT", 10.0))
    MAX_DRAWDOWN_PERCENT = float(os.getenv("MAX_DRAWDOWN_PERCENT", 15.0))
    DAILY_LOSS_LIMIT = float(os.getenv("DAILY_LOSS_LIMIT", 10.0))
    CONSECUTIVE_LOSS_LIMIT = int(os.getenv("CONSECUTIVE_LOSS_LIMIT", 3))
    COOLDOWN_HOURS = int(os.getenv("COOLDOWN_HOURS", 24))
    CIRCUIT_BREAKER_PCT = float(os.getenv("CIRCUIT_BREAKER_PCT", 5.0))  # 1h equity drop %

    KLINES_HISTORY_LENGTH = int(os.getenv("KLINES_HISTORY_LENGTH", 500))
    CURVATURE_WINDOW = int(os.getenv("CURVATURE_WINDOW", 20))

    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/trading.db")

    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
    ENABLE_TELEGRAM = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)

    # Realistic execution defaults
    COMMISSION = float(os.getenv("COMMISSION", 0.001))
    SLIPPAGE = float(os.getenv("SLIPPAGE", 0.0005))

    @classmethod
    def load_symbols(cls):
        symbols_file = cls.PROJECT_ROOT / "config" / "symbols.json"
        if symbols_file.exists():
            with open(symbols_file, "r") as f:
                return json.load(f)
        return ["BTC/USDT", "ETH/USDT"]

    @classmethod
    def load_strategy_params(cls):
        params_file = cls.PROJECT_ROOT / "config" / "strategy_params.json"
        if params_file.exists():
            with open(params_file, "r") as f:
                return json.load(f)
        return {
            "takeprofit_params": {
                "base": cls.BASE_TAKE_PROFIT,
                "angle_weight": 0.4,
                "curvature_weight": 0.3,
                "angle_scale": 100,
                "max_takeprofit": 15.0,
                "min_takeprofit": 4.0,
            }
        }

config = Config()
