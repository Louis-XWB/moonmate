"""
Binance perpetual futures trading executor
Supports USDT-margined perpetual futures trading
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
    """Position side"""
    LONG = "LONG"
    SHORT = "SHORT"
    BOTH = "BOTH"


class MarginType(str, Enum):
    """Margin type"""
    ISOLATED = "ISOLATED"  # Isolated margin
    CROSSED = "CROSSED"    # Cross margin


class BinanceFuturesExecutor:
    """
    Binance perpetual futures executor
    
    Features:
    - Place/cancel/query orders
    - Position management
    - Leverage configuration
    - Margin mode switching
    - Risk management
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
        Initialize the Binance perpetual futures executor
        
        Args:
            api_key: API key
            api_secret: API secret
            testnet: Whether to use testnet
            default_leverage: Default leverage multiplier
            margin_type: Margin mode
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.default_leverage = default_leverage
        self.margin_type = margin_type
        
        # Initialize client
        if testnet:
            # Testnet
            self.client = Client(api_key, api_secret, testnet=True)
            self.base_url = "https://testnet.binancefuture.com"
        else:
            # Mainnet
            self.client = Client(api_key, api_secret)
            self.base_url = "https://fapi.binance.com"
        
        # Use CCXT as fallback client
        self.ccxt_client = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'testnet': testnet
            }
        })
        
        # Cache
        self._positions: Dict[str, Position] = {}
        self._orders: Dict[str, Order] = {}
        
        logger.info(f"Binance Futures Executor initialized (testnet={testnet})")
    
    async def initialize(self):
        """Initialize: set leverage and margin mode"""
        try:
            # Get all trading pairs
            exchange_info = self.client.futures_exchange_info()
            symbols = [s['symbol'] for s in exchange_info['symbols']]
            
            logger.info(f"Found {len(symbols)} futures symbols")
            
            # Set leverage and margin mode for common trading pairs
            common_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT']
            
            for symbol in common_symbols:
                if symbol in symbols:
                    try:
                        # Set leverage
                        await self.set_leverage(symbol, self.default_leverage)
                        
                        # Set margin mode
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
        Set leverage multiplier
        
        Args:
            symbol: Trading pair (e.g. BTCUSDT)
            leverage: Leverage multiplier (1-125)
        
        Returns:
            Whether successful
        """
        try:
            result = self.client.futures_change_leverage(
                symbol=symbol,
                leverage=leverage
            )
            logger.info(f"Set leverage for {symbol}: {leverage}x")
            return True
        except BinanceAPIException as e:
            if e.code == -4028:  # Leverage already set
                logger.debug(f"Leverage already set for {symbol}")
                return True
            logger.error(f"Failed to set leverage for {symbol}: {e}")
            return False
    
    async def set_margin_type(self, symbol: str, margin_type: MarginType) -> bool:
        """
        Set margin mode
        
        Args:
            symbol: Trading pair
            margin_type: Margin type (isolated/cross)
        
        Returns:
            Whether successful
        """
        try:
            result = self.client.futures_change_margin_type(
                symbol=symbol,
                marginType=margin_type.value
            )
            logger.info(f"Set margin type for {symbol}: {margin_type.value}")
            return True
        except BinanceAPIException as e:
            if e.code == -4046:  # Margin mode already set
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
        Place an order
        
        Args:
            symbol: Trading pair
            side: Buy/sell direction
            order_type: Order type
            quantity: Quantity
            price: Price (required for limit orders)
            reduce_only: Whether reduce-only
            time_in_force: Time-in-force type
        
        Returns:
            Order object
        """
        try:
            # Build order parameters
            params = {
                'symbol': symbol.replace('/', ''),  # BTCUSDT
                'side': side.value.upper(),
                'type': self._convert_order_type(order_type),
                'quantity': quantity,
                'reduceOnly': reduce_only,
            }
            
            # Limit orders require a price
            if order_type == OrderType.LIMIT:
                if price is None:
                    raise ValueError("Limit order requires price")
                params['price'] = price
                params['timeInForce'] = time_in_force
            
            # Place order
            result = self.client.futures_create_order(**params)
            
            # Convert to Order object
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
        Cancel an order
        
        Args:
            symbol: Trading pair
            order_id: Order ID
        
        Returns:
            Whether successful
        """
        try:
            result = self.client.futures_cancel_order(
                symbol=symbol.replace('/', ''),
                orderId=order_id
            )
            
            logger.info(f"Order cancelled: {order_id}")
            
            # Update order status
            if order_id in self._orders:
                self._orders[order_id].status = OrderStatus.CANCELLED
            
            return True
            
        except BinanceAPIException as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    async def get_order(self, symbol: str, order_id: str) -> Optional[Order]:
        """
        Query an order
        
        Args:
            symbol: Trading pair
            order_id: Order ID
        
        Returns:
            Order object
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
        Get position
        
        Args:
            symbol: Trading pair
        
        Returns:
            Position object
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
            
            # No position
            return None
            
        except BinanceAPIException as e:
            logger.error(f"Failed to get position for {symbol}: {e}")
            return None
    
    async def get_all_positions(self) -> List[Position]:
        """
        Get all positions
        
        Returns:
            List of positions
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
        Close a position
        
        Args:
            symbol: Trading pair
            position_side: Position side (not needed in one-way position mode)
        
        Returns:
            Whether successful
        """
        try:
            # Get current position
            position = await self.get_position(symbol)
            
            if not position or position.quantity == 0:
                logger.warning(f"No position to close for {symbol}")
                return False
            
            # Determine close direction and quantity
            quantity = abs(position.quantity)
            side = OrderSide.SELL if position.quantity > 0 else OrderSide.BUY
            
            # Market close
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
        Get account balance
        
        Returns:
            Balance information
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
        """Convert order type"""
        mapping = {
            OrderType.MARKET: 'MARKET',
            OrderType.LIMIT: 'LIMIT',
        }
        return mapping.get(order_type, 'MARKET')
    
    def _convert_to_order(self, data: Dict) -> Order:
        """Convert Binance order data to Order object"""
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
        """Convert order status"""
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
        """Convert Binance position data to Position object"""
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
        """Close the client"""
        await self.ccxt_client.close()
        logger.info("Binance Futures Executor closed")


# ==================== Helper functions ====================

async def test_binance_futures():
    """Test Binance perpetual futures functionality"""
    import os
    
    api_key = os.getenv('BINANCE_API_KEY', '')
    api_secret = os.getenv('BINANCE_API_SECRET', '')
    
    if not api_key or not api_secret:
        logger.warning("No Binance API credentials, using testnet defaults")
        # Testnet defaults (users need to apply for their own keys)
        api_key = "your_testnet_api_key"
        api_secret = "your_testnet_api_secret"
    
    executor = BinanceFuturesExecutor(
        api_key=api_key,
        api_secret=api_secret,
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
        
    finally:
        await executor.close()


if __name__ == '__main__':
    asyncio.run(test_binance_futures())
