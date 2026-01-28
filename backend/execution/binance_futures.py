"""
币安永续合约交易执行器
支持USDT本位永续合约交易
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
from decimal import Decimal
from enum import Enum

from binance.client import Client
from binance.exceptions import BinanceAPIException
import ccxt.async_support as ccxt

from backend.core.logger import get_logger
from backend.data.models import Order, OrderStatus, OrderType, OrderSide, Position

logger = get_logger("binance_futures")


class PositionSide(str, Enum):
    """持仓方向"""
    LONG = "LONG"
    SHORT = "SHORT"
    BOTH = "BOTH"


class MarginType(str, Enum):
    """保证金类型"""
    ISOLATED = "ISOLATED"  # 逐仓
    CROSSED = "CROSSED"    # 全仓


class BinanceFuturesExecutor:
    """
    币安永续合约执行器
    
    功能：
    - 下单/撤单/查询订单
    - 仓位管理
    - 杠杆设置
    - 保证金模式切换
    - 风险管理
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = True,
        default_leverage: int = 1,
        margin_type: MarginType = MarginType.ISOLATED
    ):
        """
        初始化币安永续合约执行器
        
        Args:
            api_key: API密钥
            api_secret: API密钥
            testnet: 是否使用测试网
            default_leverage: 默认杠杆倍数
            margin_type: 保证金模式
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.default_leverage = default_leverage
        self.margin_type = margin_type
        
        # 初始化客户端
        if testnet:
            # 测试网
            self.client = Client(api_key, api_secret, testnet=True)
            self.base_url = "https://testnet.binancefuture.com"
        else:
            # 主网
            self.client = Client(api_key, api_secret)
            self.base_url = "https://fapi.binance.com"
        
        # 使用CCXT作为备用客户端
        self.ccxt_client = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'testnet': testnet
            }
        })
        
        # 缓存
        self._positions: Dict[str, Position] = {}
        self._orders: Dict[str, Order] = {}
        
        logger.info(f"Binance Futures Executor initialized (testnet={testnet})")
    
    async def initialize(self):
        """初始化：设置杠杆和保证金模式"""
        try:
            # 获取所有交易对
            exchange_info = self.client.futures_exchange_info()
            symbols = [s['symbol'] for s in exchange_info['symbols']]
            
            logger.info(f"Found {len(symbols)} futures symbols")
            
            # 为常用交易对设置杠杆和保证金模式
            common_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT']
            
            for symbol in common_symbols:
                if symbol in symbols:
                    try:
                        # 设置杠杆
                        await self.set_leverage(symbol, self.default_leverage)
                        
                        # 设置保证金模式
                        await self.set_margin_type(symbol, self.margin_type)
                        
                        logger.info(f"Initialized {symbol}: leverage={self.default_leverage}, margin={self.margin_type.value}")
                    except Exception as e:
                        logger.warning(f"Failed to initialize {symbol}: {e}")
            
            logger.info("Binance Futures Executor initialization complete")
            
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            raise
    
    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """
        设置杠杆倍数
        
        Args:
            symbol: 交易对（如BTCUSDT）
            leverage: 杠杆倍数（1-125）
        
        Returns:
            是否成功
        """
        try:
            result = self.client.futures_change_leverage(
                symbol=symbol,
                leverage=leverage
            )
            logger.info(f"Set leverage for {symbol}: {leverage}x")
            return True
        except BinanceAPIException as e:
            if e.code == -4028:  # 杠杆已经设置
                logger.debug(f"Leverage already set for {symbol}")
                return True
            logger.error(f"Failed to set leverage for {symbol}: {e}")
            return False
    
    async def set_margin_type(self, symbol: str, margin_type: MarginType) -> bool:
        """
        设置保证金模式
        
        Args:
            symbol: 交易对
            margin_type: 保证金类型（逐仓/全仓）
        
        Returns:
            是否成功
        """
        try:
            result = self.client.futures_change_margin_type(
                symbol=symbol,
                marginType=margin_type.value
            )
            logger.info(f"Set margin type for {symbol}: {margin_type.value}")
            return True
        except BinanceAPIException as e:
            if e.code == -4046:  # 保证金模式已经设置
                logger.debug(f"Margin type already set for {symbol}")
                return True
            logger.error(f"Failed to set margin type for {symbol}: {e}")
            return False
    
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        reduce_only: bool = False,
        time_in_force: str = "GTC"
    ) -> Optional[Order]:
        """
        下单
        
        Args:
            symbol: 交易对
            side: 买卖方向
            order_type: 订单类型
            quantity: 数量
            price: 价格（限价单需要）
            reduce_only: 是否只减仓
            time_in_force: 有效期类型
        
        Returns:
            订单对象
        """
        try:
            # 构造订单参数
            params = {
                'symbol': symbol.replace('/', ''),  # BTCUSDT
                'side': side.value.upper(),
                'type': self._convert_order_type(order_type),
                'quantity': quantity,
                'reduceOnly': reduce_only,
            }
            
            # 限价单需要价格
            if order_type == OrderType.LIMIT:
                if price is None:
                    raise ValueError("Limit order requires price")
                params['price'] = price
                params['timeInForce'] = time_in_force
            
            # 下单
            result = self.client.futures_create_order(**params)
            
            # 转换为Order对象
            order = self._convert_to_order(result)
            self._orders[order.order_id] = order
            
            logger.info(f"Order placed: {order.order_id} {side.value} {quantity} {symbol} @ {price or 'MARKET'}")
            
            return order
            
        except BinanceAPIException as e:
            logger.error(f"Failed to place order: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error placing order: {e}")
            return None
    
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """
        撤单
        
        Args:
            symbol: 交易对
            order_id: 订单ID
        
        Returns:
            是否成功
        """
        try:
            result = self.client.futures_cancel_order(
                symbol=symbol.replace('/', ''),
                orderId=order_id
            )
            
            logger.info(f"Order cancelled: {order_id}")
            
            # 更新订单状态
            if order_id in self._orders:
                self._orders[order_id].status = OrderStatus.CANCELLED
            
            return True
            
        except BinanceAPIException as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    async def get_order(self, symbol: str, order_id: str) -> Optional[Order]:
        """
        查询订单
        
        Args:
            symbol: 交易对
            order_id: 订单ID
        
        Returns:
            订单对象
        """
        try:
            result = self.client.futures_get_order(
                symbol=symbol.replace('/', ''),
                orderId=order_id
            )
            
            order = self._convert_to_order(result)
            self._orders[order.order_id] = order
            
            return order
            
        except BinanceAPIException as e:
            logger.error(f"Failed to get order {order_id}: {e}")
            return None
    
    async def get_position(self, symbol: str) -> Optional[Position]:
        """
        获取持仓
        
        Args:
            symbol: 交易对
        
        Returns:
            持仓对象
        """
        try:
            positions = self.client.futures_position_information(
                symbol=symbol.replace('/', '')
            )
            
            for pos_data in positions:
                if float(pos_data['positionAmt']) != 0:
                    position = self._convert_to_position(pos_data)
                    self._positions[symbol] = position
                    return position
            
            # 没有持仓
            return None
            
        except BinanceAPIException as e:
            logger.error(f"Failed to get position for {symbol}: {e}")
            return None
    
    async def get_all_positions(self) -> List[Position]:
        """
        获取所有持仓
        
        Returns:
            持仓列表
        """
        try:
            positions_data = self.client.futures_position_information()
            
            positions = []
            for pos_data in positions_data:
                if float(pos_data['positionAmt']) != 0:
                    position = self._convert_to_position(pos_data)
                    positions.append(position)
                    self._positions[position.symbol] = position
            
            return positions
            
        except BinanceAPIException as e:
            logger.error(f"Failed to get all positions: {e}")
            return []
    
    async def close_position(
        self,
        symbol: str,
        position_side: Optional[PositionSide] = None
    ) -> bool:
        """
        平仓
        
        Args:
            symbol: 交易对
            position_side: 持仓方向（单向持仓模式不需要）
        
        Returns:
            是否成功
        """
        try:
            # 获取当前持仓
            position = await self.get_position(symbol)
            
            if not position or position.quantity == 0:
                logger.warning(f"No position to close for {symbol}")
                return False
            
            # 确定平仓方向和数量
            quantity = abs(position.quantity)
            side = OrderSide.SELL if position.quantity > 0 else OrderSide.BUY
            
            # 市价平仓
            order = await self.place_order(
                symbol=symbol,
                side=side,
                order_type=OrderType.MARKET,
                quantity=quantity,
                reduce_only=True
            )
            
            if order:
                logger.info(f"Position closed: {symbol} {quantity}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Failed to close position for {symbol}: {e}")
            return False
    
    async def get_account_balance(self) -> Dict[str, Any]:
        """
        获取账户余额
        
        Returns:
            余额信息
        """
        try:
            account = self.client.futures_account()
            
            balance_info = {
                'total_balance': float(account['totalWalletBalance']),
                'available_balance': float(account['availableBalance']),
                'total_unrealized_pnl': float(account['totalUnrealizedProfit']),
                'total_margin_balance': float(account['totalMarginBalance']),
                'assets': []
            }
            
            for asset in account['assets']:
                if float(asset['walletBalance']) > 0:
                    balance_info['assets'].append({
                        'asset': asset['asset'],
                        'wallet_balance': float(asset['walletBalance']),
                        'unrealized_profit': float(asset['unrealizedProfit']),
                        'margin_balance': float(asset['marginBalance']),
                        'available_balance': float(asset['availableBalance'])
                    })
            
            return balance_info
            
        except BinanceAPIException as e:
            logger.error(f"Failed to get account balance: {e}")
            return {}
    
    def _convert_order_type(self, order_type: OrderType) -> str:
        """转换订单类型"""
        mapping = {
            OrderType.MARKET: 'MARKET',
            OrderType.LIMIT: 'LIMIT',
        }
        return mapping.get(order_type, 'MARKET')
    
    def _convert_to_order(self, data: Dict) -> Order:
        """转换币安订单数据为Order对象"""
        return Order(
            order_id=str(data['orderId']),
            symbol=data['symbol'],
            side=OrderSide.BUY if data['side'] == 'BUY' else OrderSide.SELL,
            order_type=OrderType.LIMIT if data['type'] == 'LIMIT' else OrderType.MARKET,
            quantity=float(data['origQty']),
            price=float(data.get('price', 0)),
            status=self._convert_order_status(data['status']),
            filled_quantity=float(data.get('executedQty', 0)),
            average_price=float(data.get('avgPrice', 0)),
            timestamp=data['time'] / 1000,
            metadata={'raw': data}
        )
    
    def _convert_order_status(self, status: str) -> OrderStatus:
        """转换订单状态"""
        mapping = {
            'NEW': OrderStatus.PENDING,
            'PARTIALLY_FILLED': OrderStatus.PARTIAL,
            'FILLED': OrderStatus.FILLED,
            'CANCELED': OrderStatus.CANCELLED,
            'REJECTED': OrderStatus.REJECTED,
            'EXPIRED': OrderStatus.CANCELLED,
        }
        return mapping.get(status, OrderStatus.PENDING)
    
    def _convert_to_position(self, data: Dict) -> Position:
        """转换币安持仓数据为Position对象"""
        quantity = float(data['positionAmt'])
        entry_price = float(data['entryPrice'])
        
        return Position(
            symbol=data['symbol'],
            quantity=quantity,
            entry_price=entry_price,
            current_price=float(data['markPrice']),
            unrealized_pnl=float(data['unRealizedProfit']),
            leverage=int(data['leverage']),
            margin_type=data['marginType'],
            liquidation_price=float(data.get('liquidationPrice', 0)),
            metadata={'raw': data}
        )
    
    async def close(self):
        """关闭客户端"""
        await self.ccxt_client.close()
        logger.info("Binance Futures Executor closed")


# ==================== 辅助函数 ====================

async def test_binance_futures():
    """测试币安永续合约功能"""
    import os
    
    api_key = os.getenv('BINANCE_API_KEY', '')
    api_secret = os.getenv('BINANCE_API_SECRET', '')
    
    if not api_key or not api_secret:
        logger.warning("No Binance API credentials, using testnet defaults")
        # 测试网默认值（需要用户自己申请）
        api_key = "your_testnet_api_key"
        api_secret = "your_testnet_api_secret"
    
    executor = BinanceFuturesExecutor(
        api_key=api_key,
        api_secret=api_secret,
        testnet=True,
        default_leverage=2
    )
    
    try:
        # 初始化
        await executor.initialize()
        
        # 获取账户余额
        balance = await executor.get_account_balance()
        logger.info(f"Account balance: {balance}")
        
        # 获取所有持仓
        positions = await executor.get_all_positions()
        logger.info(f"Current positions: {len(positions)}")
        
        for pos in positions:
            logger.info(f"Position: {pos.symbol} {pos.quantity} @ {pos.entry_price}")
        
    finally:
        await executor.close()


if __name__ == '__main__':
    asyncio.run(test_binance_futures())
