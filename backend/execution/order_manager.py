"""
订单管理器
管理订单生命周期、状态转换、持仓跟踪
"""

from datetime import datetime
from typing import Dict, List, Optional
from backend.data.models import Order, OrderStatus, OrderSide, OrderType, Position, Signal, SignalDirection
from backend.core.logger import get_logger
from backend.core.events import Event, EventType, get_event_bus

logger = get_logger("order_manager")


class OrderManager:
    """订单管理器"""
    
    def __init__(self):
        self.orders: Dict[str, Order] = {}
        self.positions: Dict[str, Position] = {}
        self.event_bus = get_event_bus()
        
        # 统计数据
        self.total_orders = 0
        self.filled_orders = 0
        self.cancelled_orders = 0
        self.total_pnl = 0
    
    def create_order_from_signal(
        self,
        signal: Signal,
        size: float,
        order_type: OrderType = OrderType.LIMIT
    ) -> Order:
        """从信号创建订单"""
        
        # 确定订单方向
        if signal.direction == SignalDirection.LONG:
            side = OrderSide.BUY
        elif signal.direction == SignalDirection.SHORT:
            side = OrderSide.SELL
        elif signal.direction == SignalDirection.CLOSE:
            # 平仓需要根据当前持仓方向确定
            position = self.positions.get(signal.symbol)
            if position and position.size > 0:
                side = OrderSide.SELL if position.side == OrderSide.BUY else OrderSide.BUY
                size = position.size  # 平仓使用持仓数量
            else:
                logger.warning(f"No position to close for {signal.symbol}")
                return None
        else:
            logger.warning(f"Cannot create order for neutral signal")
            return None
        
        order = Order(
            symbol=signal.symbol,
            side=side,
            type=order_type,
            price=signal.entry_price or 0,
            size=size,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            signal_id=signal.id,
            strategy_id=signal.strategy_id,
            reason=signal.reason
        )
        
        self.orders[order.id] = order
        self.total_orders += 1
        
        logger.info(f"Created order: {order.id} {order.side} {order.size} {order.symbol} @ {order.price}")
        
        return order
    
    def update_order_status(
        self,
        order_id: str,
        status: OrderStatus,
        filled_size: float = 0,
        avg_price: float = 0,
        fee: float = 0,
        error_msg: str = ""
    ):
        """更新订单状态"""
        if order_id not in self.orders:
            logger.error(f"Order not found: {order_id}")
            return
        
        order = self.orders[order_id]
        old_status = order.status
        
        order.status = status
        order.updated_at = datetime.now()
        
        if filled_size > 0:
            order.filled_size = filled_size
        if avg_price > 0:
            order.avg_price = avg_price
        if fee > 0:
            order.fee = fee
        if error_msg:
            order.error_msg = error_msg
        
        # 处理成交
        if status == OrderStatus.FILLED:
            order.filled_at = datetime.now()
            self.filled_orders += 1
            self._update_position(order)
            
            self.event_bus.publish_sync(Event(
                type=EventType.ORDER_FILLED,
                source="order_manager",
                data={"order_id": order_id, "order": order.model_dump()}
            ))
        
        elif status == OrderStatus.CANCELLED:
            self.cancelled_orders += 1
            self.event_bus.publish_sync(Event(
                type=EventType.ORDER_CANCELLED,
                source="order_manager",
                data={"order_id": order_id}
            ))
        
        elif status == OrderStatus.REJECTED:
            self.event_bus.publish_sync(Event(
                type=EventType.ORDER_REJECTED,
                source="order_manager",
                data={"order_id": order_id, "reason": error_msg}
            ))
        
        logger.info(f"Order {order_id} status: {old_status} -> {status}")
    
    def _update_position(self, order: Order):
        """根据成交更新持仓"""
        symbol = order.symbol
        
        if symbol not in self.positions:
            # 新建持仓
            if order.side == OrderSide.BUY:
                self.positions[symbol] = Position(
                    symbol=symbol,
                    side=OrderSide.BUY,
                    size=order.filled_size,
                    entry_price=order.avg_price,
                    current_price=order.avg_price
                )
                logger.info(f"Opened long position: {symbol} size={order.filled_size}")
            else:
                self.positions[symbol] = Position(
                    symbol=symbol,
                    side=OrderSide.SELL,
                    size=order.filled_size,
                    entry_price=order.avg_price,
                    current_price=order.avg_price
                )
                logger.info(f"Opened short position: {symbol} size={order.filled_size}")
        else:
            position = self.positions[symbol]
            
            # 同向加仓
            if (order.side == OrderSide.BUY and position.side == OrderSide.BUY) or \
               (order.side == OrderSide.SELL and position.side == OrderSide.SELL):
                # 计算新的平均价格
                total_value = position.entry_price * position.size + order.avg_price * order.filled_size
                new_size = position.size + order.filled_size
                position.entry_price = total_value / new_size
                position.size = new_size
                position.updated_at = datetime.now()
                logger.info(f"Added to position: {symbol} new_size={new_size}")
            
            # 反向减仓/平仓
            else:
                if order.filled_size >= position.size:
                    # 完全平仓
                    pnl = self._calculate_pnl(position, order.avg_price)
                    self.total_pnl += pnl
                    position.realized_pnl += pnl
                    
                    logger.info(f"Closed position: {symbol} PnL={pnl:.2f}")
                    
                    # 如果有剩余，开反向仓位
                    remaining = order.filled_size - position.size
                    if remaining > 0:
                        position.side = order.side
                        position.size = remaining
                        position.entry_price = order.avg_price
                        position.unrealized_pnl = 0
                    else:
                        del self.positions[symbol]
                else:
                    # 部分平仓
                    pnl = self._calculate_pnl(position, order.avg_price, order.filled_size)
                    self.total_pnl += pnl
                    position.realized_pnl += pnl
                    position.size -= order.filled_size
                    position.updated_at = datetime.now()
                    logger.info(f"Reduced position: {symbol} remaining={position.size} PnL={pnl:.2f}")
    
    def _calculate_pnl(self, position: Position, exit_price: float, size: Optional[float] = None) -> float:
        """计算盈亏"""
        size = size or position.size
        if position.side == OrderSide.BUY:
            return (exit_price - position.entry_price) * size
        else:
            return (position.entry_price - exit_price) * size
    
    def update_position_price(self, symbol: str, current_price: float):
        """更新持仓当前价格"""
        if symbol in self.positions:
            self.positions[symbol].update_pnl(current_price)
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """获取订单"""
        return self.orders.get(order_id)
    
    def get_active_orders(self) -> List[Order]:
        """获取活跃订单"""
        return [o for o in self.orders.values() if o.is_active]
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """获取持仓"""
        return self.positions.get(symbol)
    
    def get_all_positions(self) -> List[Position]:
        """获取所有持仓"""
        return list(self.positions.values())
    
    def get_statistics(self) -> Dict:
        """获取统计数据"""
        return {
            "total_orders": self.total_orders,
            "filled_orders": self.filled_orders,
            "cancelled_orders": self.cancelled_orders,
            "fill_rate": self.filled_orders / self.total_orders if self.total_orders > 0 else 0,
            "total_pnl": self.total_pnl,
            "active_positions": len(self.positions),
            "unrealized_pnl": sum(p.unrealized_pnl for p in self.positions.values())
        }
