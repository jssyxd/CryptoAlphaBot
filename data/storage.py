import pandas as pd
from pathlib import Path
import json
import logging
from config.config import config

logger = logging.getLogger(__name__)

class DataStorage:
    """Handle local data storage and retrieval"""
    
    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir) if data_dir else config.DATA_DIR
        self.data_dir.mkdir(exist_ok=True)
    
    def save_ohlcv(self, df: pd.DataFrame, symbol: str, timeframe: str):
        """
        Save OHLCV data to CSV
        """
        filename = self.data_dir / f"{symbol.replace('/', '_')}_{timeframe}.csv"
        df.to_csv(filename)
        logger.info(f"Saved data to {filename}")
    
    def load_ohlcv(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """
        Load OHLCV data from CSV
        """
        filename = self.data_dir / f"{symbol.replace('/', '_')}_{timeframe}.csv"
        if filename.exists():
            df = pd.read_csv(filename, index_col='timestamp', parse_dates=True)
            logger.info(f"Loaded data from {filename}")
            return df
        return None
    
    def save_config(self, config_dict: dict, filename: str):
        """
        Save configuration to JSON
        """
        filepath = self.data_dir / filename
        with open(filepath, 'w') as f:
            json.dump(config_dict, f, indent=2)
        logger.info(f"Saved config to {filepath}")
    
    def load_config(self, filename: str) -> dict:
        """
        Load configuration from JSON
        """
        filepath = self.data_dir / filename
        if filepath.exists():
            with open(filepath, 'r') as f:
                return json.load(f)
        return {}
