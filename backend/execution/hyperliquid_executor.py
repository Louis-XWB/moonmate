"""
Hyperliquid 链上永续合约交易执行器
支持 Hyperliquid L1 链上订单簿交易
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from enum import Enum
import json

from eth_account import Account
from eth_account.signers.local import LocalAccount
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants

from backend.core.logger import get_logger
from backend.data.models import Order, OrderStatus, OrderType, OrderSide, Position

logger = get_logger("hyperliquid")


class HyperliquidOrderType(str, Enum):
    """Hyperliquid订单类型"""
    LIMIT = "limit"
    MARKET = "market"
    STOP_MARKET = "stop_market"
    STOP_LIMIT = "stop_limit"
    TAKE_PROFIT_MARKET = "take_profit_market"
    TAKE_PROFIT_LIMIT = "take_profit_limit"


class HyperliquidExecutor:
    """
    Hyperliquid 链上永续合约执行器
    
    功能：
    - 链上订单簿交易（真实的去中心化永续合约）
    - 支持限价单、市价单、止损止盈
    - 杠杆交易（最高50x）
    - 实时持仓管理
    - 零Gas费交易（Hyperliquid L1特性）
    """
    
    def __init__(
        self,
        private_key: str,
        testnet: bool = True,
        default_leverage: int = 1,
        vault_address: Optional[str] = None
    ):
        """
        初始化Hyperliquid执行器
        
        Args:
            private_key: 私钥（0x开头）
            testnet: 是否使用测试网
            default_leverage: 默认杠杆倍数（1-50）
            vault_address: Vault地址（如果通过Vault交易）
        """
        self.private_key = private_key
        self.testnet = testnet
        self.default_leverage = default_leverage
        self.vault_address = vault_address
        
        # 创建账户
        self.account: LocalAccount = Account.from_key(private_key)
        self.address = self.account.address
        
        # 初始化Info和Exchange客户端
        base_url = constants.TESTNET_API_URL if testnet else constants.MAINNET_API_URL
        
        self.info = Info(base_url=base_url, skip_ws=True)
        self.exchange = Exchange(
            account=self.account,
            base_url=base_url,
            vault_address=vault_address
        )
        
        # 缓存
        self._positions: Dict[str, Position] = {}
        self._orders: Dict[str, Order] = {}
        self._asset_contexts: Dict[str, Dict] = {}  # 资产上下文（精度等）
        
        logger.info(f"Hyperliquid Executor initialized (testnet={testnet}, address={self.address})")
    
    async def initialize(self):
        """初始化：获取资产信息和设置杠杆"""
        try:
            # 获取所有资产信息
            meta = self.info.meta()
            self.universe = meta['universe']
            
            logger.info(f"Found {len(self.universe)} assets on Hyperliquid")
            
            # 构建资产上下文
            for asset_info in self.universe:
                symbol = asset_info['name']
                self._asset_contexts[symbol] = {
                    'name': symbol,
                    'sz_decimals': asset_info['szDecimals'],
                    'max_leverage': asset_info.get('maxLeverage', 50),
                    'only_isolated': asset_info.get('onlyIsolated', False)
                }
            
            # 为常用资产设置杠杆
            common_assets = ['BTC', 'ETH', 'SOL', 'HYPE']
            
            for asset in common_assets:
                if asset in self._asset_contexts:
                    try:
                        await self.set_leverage(asset, self.default_leverage)
                        logger.info(f"Set leverage for {asset}: {self.default_leverage}x")
                    except Exception as e:
                        logger.warning(f"Failed to set leverage for {asset}: {e}")
            
            # 获取当前账户状态
            user_state = self.info.user_state(self.address)
            if user_state:
                logger.info(f"Account value: ${user_state.get('marginSummary', {}).get('accountValue', 0)}")
            
            logger.info("Hyperliquid Executor initialization complete")
            
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            raise
    
    async def set_leverage(self, asset: str, leverage: int, is_cross: bool = True) -> bool:
        """
        设置杠杆
        
        Args:
            asset: 资产名称（如BTC）
            leverage: 杠杆倍数（1-50）
            is_cross: 是否全仓（True=全仓，False=逐仓）
        
        Returns:
            是否成功
        """
        try:
            # 检查资产是否存在
            if asset not in self._asset_contexts:
                logger.error(f"Asset {asset} not found")
                return False
            
            # 检查杠杆范围
            max_leverage = self._asset_contexts[asset]['max_leverage']
            if leverage > max_leverage:
                logger.warning(f"Leverage {leverage} exceeds max {max_leverage}, using {max_leverage}")
                leverage = max_leverage
            
            # 设置杠杆
            result = self.exchange.update_leverage(
                leverage=leverage,
                asset=asset,
                is_cross=is_cross
            )
            
            if result.get('status') == 'ok':
                logger.info(f"Set leverage for {asset}: {leverage}x ({'cross' if is_cross else 'isolated'})")
                return True
            else:
                logger.error(f"Failed to set leverage: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Error setting leverage for {asset}: {e}")
            return False
    
    async def place_order(
        self,
        asset: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        reduce_only: bool = False,
        time_in_force: str = "Gtc",
        slippage: float = 0.05
    ) -> Optional[Order]:
        """
        下单
        
        Args:
            asset: 资产名称（如BTC）
            side: 买卖方向
            order_type: 订单类型
            quantity: 数量
            price: 价格（限价单需要）
            reduce_only: 是否只减仓
            time_in_force: 有效期（Gtc/Ioc/Alo）
            slippage: 滑点容忍度（市价单）
        
        Returns:
            订单对象
        """
        try:
            # 检查资产
            if asset not in self._asset_contexts:
                logger.error(f"Asset {asset} not found")
                return None
            
            # 获取资产精度
            sz_decimals = self._asset_contexts[asset]['sz_decimals']
            
            # 格式化数量
            quantity = round(quantity, sz_decimals)
            
            # 确定是买还是卖
            is_buy = (side == OrderSide.BUY)
            
            # 构造订单参数
            if order_type == OrderType.LIMIT:
                # 限价单
                if price is None:
                    raise ValueError("Limit order requires price")
                
                order_result = self.exchange.order(
                    asset=asset,
                    is_buy=is_buy,
                    sz=quantity,
                    limit_px=price,
                    order_type={'limit': {'tif': time_in_force}},
                    reduce_only=reduce_only
                )
                
            elif order_type == OrderType.MARKET:
                # 市价单（使用限价单模拟，设置较大的滑点）
                # 获取当前市场价格
                mid_price = await self._get_mid_price(asset)
                if mid_price is None:
                    logger.error(f"Failed to get mid price for {asset}")
                    return None
                
                # 计算滑点价格
                if is_buy:
                    limit_price = mid_price * (1 + slippage)
                else:
                    limit_price = mid_price * (1 - slippage)
                
                order_result = self.exchange.order(
                    asset=asset,
                    is_buy=is_buy,
                    sz=quantity,
                    limit_px=limit_price,
                    order_type={'limit': {'tif': 'Ioc'}},  # 立即成交或取消
                    reduce_only=reduce_only
                )
            
            else:
                logger.error(f"Unsupported order type: {order_type}")
                return None
            
            # 检查结果
            if order_result.get('status') == 'ok':
                response = order_result.get('response', {})
                data = response.get('data', {})
                
                # 提取订单信息
                statuses = data.get('statuses', [])
                if statuses:
                    status_info = statuses[0]
                    
                    # 创建Order对象
                    order = Order(
                        order_id=str(status_info.get('oid', '')),
                        symbol=asset,
                        side=side,
                        order_type=order_type,
                        quantity=quantity,
                        price=price or limit_price,
                        status=self._convert_order_status(status_info.get('status', '')),
                        filled_quantity=0,
                        average_price=0,
                        timestamp=time.time(),
                        metadata={'raw': order_result}
                    )
                    
                    self._orders[order.order_id] = order
                    
                    logger.info(f"Order placed: {order.order_id} {side.value} {quantity} {asset} @ {price or limit_price}")
                    
                    return order
            
            logger.error(f"Failed to place order: {order_result}")
            return None
            
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None
    
    async def cancel_order(self, asset: str, order_id: int) -> bool:
        """
        撤单
        
        Args:
            asset: 资产名称
            order_id: 订单ID（整数）
        
        Returns:
            是否成功
        """
        try:
            result = self.exchange.cancel(
                asset=asset,
                oid=order_id
            )
            
            if result.get('status') == 'ok':
                logger.info(f"Order cancelled: {order_id}")
                
                # 更新订单状态
                order_id_str = str(order_id)
                if order_id_str in self._orders:
                    self._orders[order_id_str].status = OrderStatus.CANCELLED
                
                return True
            else:
                logger.error(f"Failed to cancel order: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False
    
    async def cancel_all_orders(self, asset: Optional[str] = None) -> bool:
        """
        撤销所有订单
        
        Args:
            asset: 资产名称（None表示所有资产）
        
        Returns:
            是否成功
        """
        try:
            result = self.exchange.cancel_all(asset=asset)
            
            if result.get('status') == 'ok':
                logger.info(f"All orders cancelled for {asset or 'all assets'}")
                return True
            else:
                logger.error(f"Failed to cancel all orders: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Error cancelling all orders: {e}")
            return False
    
    async def get_open_orders(self, asset: Optional[str] = None) -> List[Order]:
        """
        获取未成交订单
        
        Args:
            asset: 资产名称（None表示所有资产）
        
        Returns:
            订单列表
        """
        try:
            user_state = self.info.user_state(self.address)
            
            if not user_state:
                return []
            
            open_orders = []
            
            for order_data in user_state.get('assetPositions', []):
                position_data = order_data.get('position', {})
                asset_name = position_data.get('coin', '')
                
                # 过滤资产
                if asset and asset_name != asset:
                    continue
                
                # 获取该资产的订单
                for order_info in position_data.get('openOrders', []):
                    order = self._convert_to_order(order_info, asset_name)
                    open_orders.append(order)
                    self._orders[order.order_id] = order
            
            return open_orders
            
        except Exception as e:
            logger.error(f"Error getting open orders: {e}")
            return []
    
    async def get_position(self, asset: str) -> Optional[Position]:
        """
        获取持仓
        
        Args:
            asset: 资产名称
        
        Returns:
            持仓对象
        """
        try:
            user_state = self.info.user_state(self.address)
            
            if not user_state:
                return None
            
            for asset_position in user_state.get('assetPositions', []):
                position_data = asset_position.get('position', {})
                
                if position_data.get('coin') == asset:
                    szi = float(position_data.get('szi', 0))
                    
                    if szi != 0:
                        position = self._convert_to_position(position_data)
                        self._positions[asset] = position
                        return position
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting position for {asset}: {e}")
            return None
    
    async def get_all_positions(self) -> List[Position]:
        """
        获取所有持仓
        
        Returns:
            持仓列表
        """
        try:
            user_state = self.info.user_state(self.address)
            
            if not user_state:
                return []
            
            positions = []
            
            for asset_position in user_state.get('assetPositions', []):
                position_data = asset_position.get('position', {})
                szi = float(position_data.get('szi', 0))
                
                if szi != 0:
                    position = self._convert_to_position(position_data)
                    positions.append(position)
                    self._positions[position.symbol] = position
            
            return positions
            
        except Exception as e:
            logger.error(f"Error getting all positions: {e}")
            return []
    
    async def close_position(self, asset: str) -> bool:
        """
        平仓
        
        Args:
            asset: 资产名称
        
        Returns:
            是否成功
        """
        try:
            # 获取当前持仓
            position = await self.get_position(asset)
            
            if not position or position.quantity == 0:
                logger.warning(f"No position to close for {asset}")
                return False
            
            # 确定平仓方向和数量
            quantity = abs(position.quantity)
            side = OrderSide.SELL if position.quantity > 0 else OrderSide.BUY
            
            # 市价平仓
            order = await self.place_order(
                asset=asset,
                side=side,
                order_type=OrderType.MARKET,
                quantity=quantity,
                reduce_only=True
            )
            
            if order:
                logger.info(f"Position closed: {asset} {quantity}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Error closing position for {asset}: {e}")
            return False
    
    async def get_account_balance(self) -> Dict[str, Any]:
        """
        获取账户余额
        
        Returns:
            余额信息
        """
        try:
            user_state = self.info.user_state(self.address)
            
            if not user_state:
                return {}
            
            margin_summary = user_state.get('marginSummary', {})
            
            balance_info = {
                'account_value': float(margin_summary.get('accountValue', 0)),
                'total_margin_used': float(margin_summary.get('totalMarginUsed', 0)),
                'total_ntl_pos': float(margin_summary.get('totalNtlPos', 0)),
                'total_raw_usd': float(margin_summary.get('totalRawUsd', 0)),
                'withdrawable': float(user_state.get('withdrawable', 0)),
                'cross_margin_summary': user_state.get('crossMarginSummary', {}),
            }
            
            return balance_info
            
        except Exception as e:
            logger.error(f"Error getting account balance: {e}")
            return {}
    
    async def _get_mid_price(self, asset: str) -> Optional[float]:
        """获取资产的中间价"""
        try:
            all_mids = self.info.all_mids()
            return float(all_mids.get(asset, 0))
        except Exception as e:
            logger.error(f"Error getting mid price for {asset}: {e}")
            return None
    
    def _convert_order_status(self, status: str) -> OrderStatus:
        """转换订单状态"""
        mapping = {
            'open': OrderStatus.PENDING,
            'filled': OrderStatus.FILLED,
            'canceled': OrderStatus.CANCELLED,
            'rejected': OrderStatus.REJECTED,
            'triggered': OrderStatus.PENDING,
        }
        return mapping.get(status.lower(), OrderStatus.PENDING)
    
    def _convert_to_order(self, data: Dict, asset: str) -> Order:
        """转换Hyperliquid订单数据为Order对象"""
        side = OrderSide.BUY if data.get('side') == 'B' else OrderSide.SELL
        
        return Order(
            order_id=str(data.get('oid', '')),
            symbol=asset,
            side=side,
            order_type=OrderType.LIMIT,  # Hyperliquid主要是限价单
            quantity=abs(float(data.get('sz', 0))),
            price=float(data.get('limitPx', 0)),
            status=OrderStatus.PENDING,
            filled_quantity=0,
            average_price=0,
            timestamp=data.get('timestamp', time.time()),
            metadata={'raw': data}
        )
    
    def _convert_to_position(self, data: Dict) -> Position:
        """转换Hyperliquid持仓数据为Position对象"""
        szi = float(data.get('szi', 0))
        entry_price = float(data.get('entryPx', 0))
        
        return Position(
            symbol=data.get('coin', ''),
            quantity=szi,
            entry_price=entry_price,
            current_price=float(data.get('markPx', 0)),
            unrealized_pnl=float(data.get('unrealizedPnl', 0)),
            leverage=int(data.get('leverage', {}).get('value', 1)),
            margin_type='cross' if data.get('leverage', {}).get('type') == 'cross' else 'isolated',
            liquidation_price=float(data.get('liquidationPx', 0)),
            metadata={'raw': data}
        )


# ==================== 辅助函数 ====================

async def test_hyperliquid():
    """测试Hyperliquid功能"""
    import os
    
    private_key = os.getenv('HYPERLIQUID_PRIVATE_KEY', '')
    
    if not private_key:
        logger.warning("No Hyperliquid private key provided")
        # 生成测试私钥（仅用于演示）
        test_account = Account.create()
        private_key = test_account.key.hex()
        logger.info(f"Generated test account: {test_account.address}")
    
    executor = HyperliquidExecutor(
        private_key=private_key,
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
        
        # 获取未成交订单
        open_orders = await executor.get_open_orders()
        logger.info(f"Open orders: {len(open_orders)}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")


if __name__ == '__main__':
    asyncio.run(test_hyperliquid())
