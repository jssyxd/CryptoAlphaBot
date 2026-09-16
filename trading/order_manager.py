import logging
from typing import Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)

class OrderManager:
    """Manage order lifecycle"""
    
    def __init__(self):
        self.orders = {}  # order_id -> order info
        self.pending_orders = []  # Orders awaiting confirmation
        self.completed_orders = []
    
    def add_order(self, order_id: str, order_data: Dict):
        """Add order to tracking"""
        self.orders[order_id] = order_data
        self.pending_orders.append(order_id)
        logger.info(f"Order added: {order_id}")
    
    def update_order_status(self, order_id: str, status: str):
        """Update order status"""
        if order_id in self.orders:
            self.orders[order_id]['status'] = status
            self.orders[order_id]['updated_at'] = datetime.now()
            logger.info(f"Order {order_id} status updated to {status}")
    
    def order_filled(self, order_id: str):
        """Mark order as filled"""
        if order_id in self.orders:
            self.orders[order_id]['status'] = 'filled'
            if order_id in self.pending_orders:
                self.pending_orders.remove(order_id)
            self.completed_orders.append(order_id)
            logger.info(f"Order {order_id} filled")
    
    def get_order(self, order_id: str) -> Dict:
        """Get order details"""
        return self.orders.get(order_id)
    
    def get_pending_orders(self) -> List[str]:
        """Get all pending orders"""
        return self.pending_orders.copy()
