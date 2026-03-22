"""
Hyperliquid on-chain perpetual futures trading executor
Supports Hyperliquid L1 on-chain order book trading
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
    """Hyperliquid order type"""
    LIMIT = "limit"
    MARKET = "market"
    STOP_MARKET = "stop_market"
    STOP_LIMIT = "stop_limit"
    TAKE_PROFIT_MARKET = "take_profit_market"
    TAKE_PROFIT_LIMIT = "take_profit_limit"


class HyperliquidExecutor:
    """
    Hyperliquid on-chain perpetual futures executor
    
    Features:
    - On-chain order book trading (real decentralized perpetual contracts)
    - Supports limit orders, market orders, stop-loss/take-profit
    - Leveraged trading (up to 50x)
    - Real-time position management
    - Zero gas fee trading (Hyperliquid L1 feature)
    """
    
    def __init__(
        self,
        private_key: str,
        testnet: bool = True,
        default_leverage: int = 1,
        vault_address: Optional[str] = None
    ):
        """
        Initialize the Hyperliquid executor
        
        Args:
            private_key: Private key (starting with 0x)
            testnet: Whether to use testnet
            default_leverage: Default leverage multiplier (1-50)
            vault_address: Vault address (if trading through a Vault)
        """
        self.private_key = private_key
        self.testnet = testnet
        self.default_leverage = default_leverage
        self.vault_address = vault_address
        
        # Create account
        self.account: LocalAccount = Account.from_key(private_key)
        self.address = self.account.address
        
        # Initialize Info and Exchange clients
        base_url = constants.TESTNET_API_URL if testnet else constants.MAINNET_API_URL
        
        self.info = Info(base_url=base_url, skip_ws=True)
        self.exchange = Exchange(
            account=self.account,
            base_url=base_url,
            vault_address=vault_address
        )
        
        # Cache
        self._positions: Dict[str, Position] = {}
        self._orders: Dict[str, Order] = {}
        self._asset_contexts: Dict[str, Dict] = {}  # Asset context (precision, etc.)
        
        logger.info(f"Hyperliquid Executor initialized (testnet={testnet}, address={self.address})")
    
    async def initialize(self):
        """Initialize: fetch asset info and set leverage"""
        try:
            # Get all asset info
            meta = self.info.meta()
            self.universe = meta['universe']
            
            logger.info(f"Found {len(self.universe)} assets on Hyperliquid")
            
            # Build asset context
            for asset_info in self.universe:
                symbol = asset_info['name']
                self._asset_contexts[symbol] = {
                    'name': symbol,
                    'sz_decimals': asset_info['szDecimals'],
                    'max_leverage': asset_info.get('maxLeverage', 50),
                    'only_isolated': asset_info.get('onlyIsolated', False)
                }
            
            # Set leverage for common assets
            common_assets = ['BTC', 'ETH', 'SOL', 'HYPE']
            
            for asset in common_assets:
                if asset in self._asset_contexts:
                    try:
                        await self.set_leverage(asset, self.default_leverage)
                        logger.info(f"Set leverage for {asset}: {self.default_leverage}x")
                    except Exception as e:
                        logger.warning(f"Failed to set leverage for {asset}: {e}")
            
            # Get current account state
            user_state = self.info.user_state(self.address)
            if user_state:
                logger.info(f"Account value: ${user_state.get('marginSummary', {}).get('accountValue', 0)}")
            
            logger.info("Hyperliquid Executor initialization complete")
            
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            raise
    
    async def set_leverage(self, asset: str, leverage: int, is_cross: bool = True) -> bool:
        """
        Set leverage
        
        Args:
            asset: Asset name (e.g. BTC)
            leverage: Leverage multiplier (1-50)
            is_cross: Whether cross margin (True=cross, False=isolated)
        
        Returns:
            Whether successful
        """
        try:
            # Check if asset exists
            if asset not in self._asset_contexts:
                logger.error(f"Asset {asset} not found")
                return False
            
            # Check leverage range
            max_leverage = self._asset_contexts[asset]['max_leverage']
            if leverage > max_leverage:
                logger.warning(f"Leverage {leverage} exceeds max {max_leverage}, using {max_leverage}")
                leverage = max_leverage
            
            # Set leverage
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
        Place an order
        
        Args:
            asset: Asset name (e.g. BTC)
            side: Buy/sell direction
            order_type: Order type
            quantity: Quantity
            price: Price (required for limit orders)
            reduce_only: Whether reduce-only
            time_in_force: Time-in-force (Gtc/Ioc/Alo)
            slippage: Slippage tolerance (for market orders)
        
        Returns:
            Order object
        """
        try:
            # Check asset
            if asset not in self._asset_contexts:
                logger.error(f"Asset {asset} not found")
                return None
            
            # Get asset precision
            sz_decimals = self._asset_contexts[asset]['sz_decimals']
            
            # Format quantity
            quantity = round(quantity, sz_decimals)
            
            # Determine buy or sell
            is_buy = (side == OrderSide.BUY)
            
            # Build order parameters
            if order_type == OrderType.LIMIT:
                # Limit order
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
                # Market order (simulated with limit order using large slippage)
                # Get current market price
                mid_price = await self._get_mid_price(asset)
                if mid_price is None:
                    logger.error(f"Failed to get mid price for {asset}")
                    return None
                
                # Calculate slippage price
                if is_buy:
                    limit_price = mid_price * (1 + slippage)
                else:
                    limit_price = mid_price * (1 - slippage)
                
                order_result = self.exchange.order(
                    asset=asset,
                    is_buy=is_buy,
                    sz=quantity,
                    limit_px=limit_price,
                    order_type={'limit': {'tif': 'Ioc'}},  # Immediate-or-cancel
                    reduce_only=reduce_only
                )
            
            else:
                logger.error(f"Unsupported order type: {order_type}")
                return None
            
            # Check result
            if order_result.get('status') == 'ok':
                response = order_result.get('response', {})
                data = response.get('data', {})
                
                # Extract order info
                statuses = data.get('statuses', [])
                if statuses:
                    status_info = statuses[0]
                    
                    # Create Order object
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
        Cancel an order
        
        Args:
            asset: Asset name
            order_id: Order ID (integer)
        
        Returns:
            Whether successful
        """
        try:
            result = self.exchange.cancel(
                asset=asset,
                oid=order_id
            )
            
            if result.get('status') == 'ok':
                logger.info(f"Order cancelled: {order_id}")
                
                # Update order status
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
        Cancel all orders
        
        Args:
            asset: Asset name (None for all assets)
        
        Returns:
            Whether successful
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
        Get open orders
        
        Args:
            asset: Asset name (None for all assets)
        
        Returns:
            List of orders
        """
        try:
            user_state = self.info.user_state(self.address)
            
            if not user_state:
                return []
            
            open_orders = []
            
            for order_data in user_state.get('assetPositions', []):
                position_data = order_data.get('position', {})
                asset_name = position_data.get('coin', '')
                
                # Filter by asset
                if asset and asset_name != asset:
                    continue
                
                # Get orders for this asset
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
        Get position
        
        Args:
            asset: Asset name
        
        Returns:
            Position object
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
        Get all positions
        
        Returns:
            List of positions
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
        Close a position
        
        Args:
            asset: Asset name
        
        Returns:
            Whether successful
        """
        try:
            # Get current position
            position = await self.get_position(asset)
            
            if not position or position.quantity == 0:
                logger.warning(f"No position to close for {asset}")
                return False
            
            # Determine close direction and quantity
            quantity = abs(position.quantity)
            side = OrderSide.SELL if position.quantity > 0 else OrderSide.BUY
            
            # Market close
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
        Get account balance
        
        Returns:
            Balance information
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
        """Get mid price for asset"""
        try:
            all_mids = self.info.all_mids()
            return float(all_mids.get(asset, 0))
        except Exception as e:
            logger.error(f"Error getting mid price for {asset}: {e}")
            return None
    
    def _convert_order_status(self, status: str) -> OrderStatus:
        """Convert order status"""
        mapping = {
            'open': OrderStatus.PENDING,
            'filled': OrderStatus.FILLED,
            'canceled': OrderStatus.CANCELLED,
            'rejected': OrderStatus.REJECTED,
            'triggered': OrderStatus.PENDING,
        }
        return mapping.get(status.lower(), OrderStatus.PENDING)
    
    def _convert_to_order(self, data: Dict, asset: str) -> Order:
        """Convert Hyperliquid order data to Order object"""
        side = OrderSide.BUY if data.get('side') == 'B' else OrderSide.SELL
        
        return Order(
            order_id=str(data.get('oid', '')),
            symbol=asset,
            side=side,
            order_type=OrderType.LIMIT,  # Hyperliquid primarily uses limit orders
            quantity=abs(float(data.get('sz', 0))),
            price=float(data.get('limitPx', 0)),
            status=OrderStatus.PENDING,
            filled_quantity=0,
            average_price=0,
            timestamp=data.get('timestamp', time.time()),
            metadata={'raw': data}
        )
    
    def _convert_to_position(self, data: Dict) -> Position:
        """Convert Hyperliquid position data to Position object"""
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


# ==================== Helper functions ====================

async def test_hyperliquid():
    """Test Hyperliquid functionality"""
    import os
    
    private_key = os.getenv('HYPERLIQUID_PRIVATE_KEY', '')
    
    if not private_key:
        logger.warning("No Hyperliquid private key provided")
        # Generate test private key (for demo only)
        test_account = Account.create()
        private_key = test_account.key.hex()
        logger.info(f"Generated test account: {test_account.address}")
    
    executor = HyperliquidExecutor(
        private_key=private_key,
        testnet=True,
        default_leverage=2
    )
    
    try:
        # Initialize
        await executor.initialize()
        
        # Get account balance
        balance = await executor.get_account_balance()
        logger.info(f"Account balance: {balance}")
        
        # Get all positions
        positions = await executor.get_all_positions()
        logger.info(f"Current positions: {len(positions)}")
        
        for pos in positions:
            logger.info(f"Position: {pos.symbol} {pos.quantity} @ {pos.entry_price}")
        
        # Get open orders
        open_orders = await executor.get_open_orders()
        logger.info(f"Open orders: {len(open_orders)}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")


if __name__ == '__main__':
    asyncio.run(test_hyperliquid())
