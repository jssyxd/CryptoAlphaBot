"""
SQLite persistence for signals, orders, trades and equity curve.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import (
    Column, DateTime, Float, Integer, MetaData, String, Text, create_engine, text
)
from sqlalchemy.orm import declarative_base, sessionmaker

from config.config import config

logger = logging.getLogger(__name__)
Base = declarative_base()


class SignalRecord(Base):
    __tablename__ = "signals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, index=True)
    symbol = Column(String(32), index=True)
    signal = Column(Integer)  # 1 buy, -1 sell, 0 hold
    price = Column(Float)
    rsi = Column(Float, nullable=True)
    dynamic_tp = Column(Float, nullable=True)
    meta = Column(Text, nullable=True)  # JSON extra


class OrderRecord(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(64), unique=True, index=True)
    symbol = Column(String(32), index=True)
    side = Column(String(8))  # buy / sell
    order_type = Column(String(16))  # market / limit
    amount = Column(Float)
    price = Column(Float, nullable=True)
    status = Column(String(24), index=True)  # pending / submitted / partial / filled / cancelled / rejected / timeout
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    filled_amount = Column(Float, default=0.0)
    avg_fill_price = Column(Float, nullable=True)
    fee = Column(Float, default=0.0)
    slippage = Column(Float, default=0.0)
    meta = Column(Text, nullable=True)


class TradeRecord(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), index=True)
    side = Column(String(8))
    entry_time = Column(DateTime)
    exit_time = Column(DateTime, nullable=True)
    entry_price = Column(Float)
    exit_price = Column(Float, nullable=True)
    amount = Column(Float)
    pnl = Column(Float, nullable=True)
    pnl_percent = Column(Float, nullable=True)
    fee_total = Column(Float, default=0.0)
    exit_reason = Column(String(32), nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    meta = Column(Text, nullable=True)


class EquityRecord(Base):
    __tablename__ = "equity"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, index=True)
    equity = Column(Float)
    balance = Column(Float)
    drawdown_pct = Column(Float, nullable=True)


class DataStorage:
    """Local CSV + SQLite storage."""

    def __init__(self, db_url: str = None, data_dir=None):
        self.data_dir = Path(data_dir) if data_dir else config.DATA_DIR
        self.data_dir.mkdir(exist_ok=True)
        self.db_url = db_url or config.DATABASE_URL
        # Ensure sqlite path is absolute under data/
        if self.db_url.startswith("sqlite:///") and not self.db_url.startswith("sqlite:////"):
            rel = self.db_url.replace("sqlite:///", "")
            abs_path = self.data_dir / Path(rel).name
            self.db_url = f"sqlite:///{abs_path}"
        self.engine = create_engine(self.db_url, echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        logger.info(f"SQLite ready: {self.db_url}")

    # ---- CSV helpers (unchanged) ----
    def save_ohlcv(self, df: pd.DataFrame, symbol: str, timeframe: str):
        filename = self.data_dir / f"{symbol.replace('/', '_')}_{timeframe}.csv"
        df.to_csv(filename)
        logger.info(f"Saved OHLCV -> {filename}")

    def load_ohlcv(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        filename = self.data_dir / f"{symbol.replace('/', '_')}_{timeframe}.csv"
        if filename.exists():
            return pd.read_csv(filename, index_col="timestamp", parse_dates=True)
        return None

    # ---- SQLite writers ----
    def save_signal(self, timestamp, symbol: str, signal: int, price: float,
                    rsi: float = None, dynamic_tp: float = None, meta: dict = None):
        with self.Session() as s:
            s.add(SignalRecord(
                timestamp=timestamp, symbol=symbol, signal=signal, price=price,
                rsi=rsi, dynamic_tp=dynamic_tp,
                meta=json.dumps(meta) if meta else None,
            ))
            s.commit()

    def save_order(self, order: Dict):
        with self.Session() as s:
            rec = OrderRecord(
                order_id=order["order_id"],
                symbol=order["symbol"],
                side=order["side"],
                order_type=order.get("order_type", "market"),
                amount=order["amount"],
                price=order.get("price"),
                status=order.get("status", "pending"),
                filled_amount=order.get("filled_amount", 0.0),
                avg_fill_price=order.get("avg_fill_price"),
                fee=order.get("fee", 0.0),
                slippage=order.get("slippage", 0.0),
                meta=json.dumps(order.get("meta")) if order.get("meta") else None,
            )
            s.merge(rec)
            s.commit()

    def update_order_status(self, order_id: str, status: str, **kwargs):
        with self.Session() as s:
            rec = s.query(OrderRecord).filter_by(order_id=order_id).first()
            if rec:
                rec.status = status
                rec.updated_at = datetime.utcnow()
                for k, v in kwargs.items():
                    if hasattr(rec, k):
                        setattr(rec, k, v)
                s.commit()

    def save_trade(self, trade: Dict):
        with self.Session() as s:
            s.add(TradeRecord(
                symbol=trade["symbol"],
                side=trade.get("side", "buy"),
                entry_time=trade["entry_time"],
                exit_time=trade.get("exit_time"),
                entry_price=trade["entry_price"],
                exit_price=trade.get("exit_price"),
                amount=trade["amount"],
                pnl=trade.get("pnl"),
                pnl_percent=trade.get("pnl_percent"),
                fee_total=trade.get("fee_total", 0.0),
                exit_reason=trade.get("exit_reason"),
                stop_loss=trade.get("stop_loss"),
                take_profit=trade.get("take_profit"),
                meta=json.dumps(trade.get("meta")) if trade.get("meta") else None,
            ))
            s.commit()

    def save_equity(self, timestamp, equity: float, balance: float, drawdown_pct: float = None):
        with self.Session() as s:
            s.add(EquityRecord(
                timestamp=timestamp, equity=equity, balance=balance, drawdown_pct=drawdown_pct
            ))
            s.commit()

    def get_trades_df(self) -> pd.DataFrame:
        return pd.read_sql("SELECT * FROM trades", self.engine)

    def get_signals_df(self, symbol: str = None) -> pd.DataFrame:
        q = "SELECT * FROM signals"
        if symbol:
            q += f" WHERE symbol = '{symbol}'"
        return pd.read_sql(q, self.engine)

    def get_equity_df(self) -> pd.DataFrame:
        return pd.read_sql("SELECT * FROM equity ORDER BY timestamp", self.engine)
