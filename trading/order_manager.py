"""
Order state machine.

States: pending -> submitted -> partial -> filled
                    |-> cancelled / rejected / timeout
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class OrderStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


VALID_TRANSITIONS = {
    OrderStatus.PENDING: {OrderStatus.SUBMITTED, OrderStatus.REJECTED, OrderStatus.CANCELLED},
    OrderStatus.SUBMITTED: {OrderStatus.PARTIAL, OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.TIMEOUT, OrderStatus.REJECTED},
    OrderStatus.PARTIAL: {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.TIMEOUT},
    OrderStatus.FILLED: set(),
    OrderStatus.CANCELLED: set(),
    OrderStatus.REJECTED: set(),
    OrderStatus.TIMEOUT: set(),
}


class OrderManager:
    """Track order lifecycle with state machine + timeout."""

    def __init__(self, default_timeout_sec: int = 60):
        self.orders: Dict[str, Dict] = {}
        self.default_timeout_sec = default_timeout_sec

    def create_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        order_type: str = "market",
        price: float = None,
        meta: dict = None,
    ) -> str:
        order_id = str(uuid.uuid4())[:12]
        self.orders[order_id] = {
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "amount": amount,
            "price": price,
            "status": OrderStatus.PENDING.value,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "filled_amount": 0.0,
            "avg_fill_price": None,
            "fee": 0.0,
            "slippage": 0.0,
            "meta": meta or {},
        }
        logger.info(f"Order created {order_id} {side} {symbol} amt={amount}")
        return order_id

    def transition(self, order_id: str, new_status: OrderStatus, **kwargs) -> bool:
        order = self.orders.get(order_id)
        if not order:
            logger.warning(f"Unknown order {order_id}")
            return False
        current = OrderStatus(order["status"])
        if new_status not in VALID_TRANSITIONS.get(current, set()):
            logger.error(f"Invalid transition {current} -> {new_status} for {order_id}")
            return False
        order["status"] = new_status.value
        order["updated_at"] = datetime.utcnow()
        for k, v in kwargs.items():
            order[k] = v
        logger.info(f"Order {order_id}: {current.value} -> {new_status.value}")
        return True

    def mark_submitted(self, order_id: str):
        return self.transition(order_id, OrderStatus.SUBMITTED)

    def mark_filled(self, order_id: str, fill_price: float, fee: float = 0.0, slippage: float = 0.0):
        order = self.orders.get(order_id)
        if not order:
            return False
        return self.transition(
            order_id, OrderStatus.FILLED,
            filled_amount=order["amount"],
            avg_fill_price=fill_price,
            fee=fee,
            slippage=slippage,
        )

    def mark_partial(self, order_id: str, filled_amount: float, avg_price: float):
        return self.transition(order_id, OrderStatus.PARTIAL, filled_amount=filled_amount, avg_fill_price=avg_price)

    def mark_cancelled(self, order_id: str):
        return self.transition(order_id, OrderStatus.CANCELLED)

    def mark_rejected(self, order_id: str, reason: str = ""):
        return self.transition(order_id, OrderStatus.REJECTED, meta={**(self.orders.get(order_id, {}).get("meta") or {}), "reject_reason": reason})

    def check_timeouts(self) -> List[str]:
        """Mark timed-out submitted/partial orders."""
        timed_out = []
        now = datetime.utcnow()
        for oid, o in list(self.orders.items()):
            if o["status"] in (OrderStatus.SUBMITTED.value, OrderStatus.PARTIAL.value):
                age = (now - o["created_at"]).total_seconds()
                if age > self.default_timeout_sec:
                    self.transition(oid, OrderStatus.TIMEOUT)
                    timed_out.append(oid)
        return timed_out

    def get_order(self, order_id: str) -> Optional[Dict]:
        return self.orders.get(order_id)

    def get_pending(self) -> List[Dict]:
        return [o for o in self.orders.values() if o["status"] in (
            OrderStatus.PENDING.value, OrderStatus.SUBMITTED.value, OrderStatus.PARTIAL.value
        )]

    def get_filled(self) -> List[Dict]:
        return [o for o in self.orders.values() if o["status"] == OrderStatus.FILLED.value]
