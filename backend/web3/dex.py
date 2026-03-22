"""
DEX Data Module
Fetches price and liquidity data from DEXes such as Uniswap, PancakeSwap, etc.
"""

import asyncio
import aiohttp
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from web3 import Web3

from backend.core.logger import get_logger
from .chain import EthereumProvider, get_chain_provider

logger = get_logger("dex")


@dataclass
class PoolInfo:
    """Liquidity pool information"""
    address: str
    token0: str
    token1: str
    token0_symbol: str
    token1_symbol: str
    reserve0: int
    reserve1: int
    fee: int  # Basis points, e.g. 30 = 0.3%
    liquidity: int
    price: float  # token0/token1 price
    tvl_usd: float


@dataclass
class SwapQuote:
    """Swap quote"""
    token_in: str
    token_out: str
    amount_in: int
    amount_out: int
    price_impact: float  # Percentage
    path: List[str]
    gas_estimate: int
    protocol: str

# Common token addresses
TOKENS = {
    1: {  # Ethereum
        "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "DAI": "0x6B175474E89094C44Da98b954EescdeCB5BE3830",
        "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
    },
    56: {  # BSC
        "WBNB": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
        "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
        "USDT": "0x55d398326f99059fF775485246999027B3197955",
        "BUSD": "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
    },
    137: {  # Polygon
        "WMATIC": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
        "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        "USDT": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
        "WETH": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
    }
}

# DEX router addresses
DEX_ROUTERS = {
    1: {
        "uniswap_v2": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        "uniswap_v3": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "sushiswap": "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F",
    },
    56: {
        "pancakeswap_v2": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
        "pancakeswap_v3": "0x13f4EA83D0bd40E75C8222255bc855a974568Dd4",
    },
    137: {
        "quickswap": "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
        "sushiswap": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
    }
}


class DEXProvider(ABC):
    """DEX data provider base class"""

    @abstractmethod
    async def get_price(self, token_in: str, token_out: str) -> float:
        """Get token price"""
        pass

    @abstractmethod
    async def get_quote(
        self,
        token_in: str,
        token_out: str,
        amount_in: int
    ) -> SwapQuote:
        """Get swap quote"""
        pass

    @abstractmethod
    async def get_pool_info(self, pool_address: str) -> PoolInfo:
        """Get pool information"""
        pass


class UniswapV2Provider(DEXProvider):
    """Uniswap V2 data provider"""

    # Uniswap V2 Factory ABI
    FACTORY_ABI = [
        {
            "constant": True,
            "inputs": [
                {"name": "tokenA", "type": "address"},
                {"name": "tokenB", "type": "address"}
            ],
            "name": "getPair",
            "outputs": [{"name": "pair", "type": "address"}],
            "type": "function"
        }
    ]

    # Uniswap V2 Pair ABI
    PAIR_ABI = [
        {
            "constant": True,
            "inputs": [],
            "name": "getReserves",
            "outputs": [
                {"name": "reserve0", "type": "uint112"},
                {"name": "reserve1", "type": "uint112"},
                {"name": "blockTimestampLast", "type": "uint32"}
            ],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "token0",
            "outputs": [{"name": "", "type": "address"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "token1",
            "outputs": [{"name": "", "type": "address"}],
            "type": "function"
        }
    ]

    # Router ABI
    ROUTER_ABI = [
        {
            "inputs": [
                {"name": "amountIn", "type": "uint256"},
                {"name": "path", "type": "address[]"}
            ],
            "name": "getAmountsOut",
            "outputs": [{"name": "amounts", "type": "uint256[]"}],
            "stateMutability": "view",
            "type": "function"
        }
    ]

    def __init__(
        self,
        chain_id: int = 1,
        factory_address: Optional[str] = None,
        router_address: Optional[str] = None
    ):
        self.chain_id = chain_id
        self.provider = get_chain_provider(chain_id)

        # Default addresses
        if chain_id == 1:
            self.factory_address = factory_address or "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"
            self.router_address = router_address or DEX_ROUTERS[1]["uniswap_v2"]
        elif chain_id == 56:
            self.factory_address = factory_address or "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73"
            self.router_address = router_address or DEX_ROUTERS[56]["pancakeswap_v2"]
        else:
            self.factory_address = factory_address
            self.router_address = router_address

    async def get_pair_address(self, token_a: str, token_b: str) -> str:
        """Get trading pair address"""
        pair = await self.provider.call_contract(
            self.factory_address,
            self.FACTORY_ABI,
            "getPair",
            Web3.to_checksum_address(token_a),
            Web3.to_checksum_address(token_b)
        )
        return pair

    async def get_reserves(self, pair_address: str) -> Tuple[int, int]:
        """Get reserves"""
        reserves = await self.provider.call_contract(
            pair_address,
            self.PAIR_ABI,
            "getReserves"
        )
        return reserves[0], reserves[1]

    async def get_price(self, token_in: str, token_out: str) -> float:
        """Get token price"""
        try:
            pair_address = await self.get_pair_address(token_in, token_out)

            if pair_address == "0x" + "0" * 40:
                logger.warning(f"Pair not found: {token_in} / {token_out}")
                return 0

            reserve0, reserve1 = await self.get_reserves(pair_address)

            # Get token0 address to determine ordering
            token0 = await self.provider.call_contract(
                pair_address,
                self.PAIR_ABI,
                "token0"
            )

            if token_in.lower() == token0.lower():
                price = reserve1 / reserve0 if reserve0 > 0 else 0
            else:
                price = reserve0 / reserve1 if reserve1 > 0 else 0

            return price

        except Exception as e:
            logger.error(f"Failed to get price: {e}")
            return 0

    async def get_quote(
        self,
        token_in: str,
        token_out: str,
        amount_in: int
    ) -> SwapQuote:
        """Get swap quote"""
        try:
            path = [
                Web3.to_checksum_address(token_in),
                Web3.to_checksum_address(token_out)
            ]

            amounts = await self.provider.call_contract(
                self.router_address,
                self.ROUTER_ABI,
                "getAmountsOut",
                amount_in,
                path
            )

            amount_out = amounts[-1]

            # Calculate price impact
            spot_price = await self.get_price(token_in, token_out)
            if spot_price > 0 and amount_in > 0:
                effective_price = amount_out / amount_in
                price_impact = abs(effective_price - spot_price) / spot_price * 100
            else:
                price_impact = 0

            return SwapQuote(
                token_in=token_in,
                token_out=token_out,
                amount_in=amount_in,
                amount_out=amount_out,
                price_impact=price_impact,
                path=[str(p) for p in path],
                gas_estimate=150000,
                protocol="uniswap_v2"
            )

        except Exception as e:
            logger.error(f"Failed to get quote: {e}")
            raise

    async def get_pool_info(self, pool_address: str) -> PoolInfo:
        """Get pool information"""
        pool_address = Web3.to_checksum_address(pool_address)

        # Get token addresses
        token0 = await self.provider.call_contract(
            pool_address, self.PAIR_ABI, "token0"
        )
        token1 = await self.provider.call_contract(
            pool_address, self.PAIR_ABI, "token1"
        )

        # Get reserves
        reserve0, reserve1 = await self.get_reserves(pool_address)

        # Get token information
        token0_info = await self.provider.get_token_info(token0)
        token1_info = await self.provider.get_token_info(token1)

        # Calculate price
        price = reserve1 / reserve0 if reserve0 > 0 else 0

        return PoolInfo(
            address=pool_address,
            token0=token0,
            token1=token1,
            token0_symbol=token0_info["symbol"],
            token1_symbol=token1_info["symbol"],
            reserve0=reserve0,
            reserve1=reserve1,
            fee=30,  # Uniswap V2 fixed 0.3%
            liquidity=0,  # V2 does not have concentrated liquidity
            price=price,
            tvl_usd=0  # Requires additional calculation
        )


class DEXAggregator:
    """DEX Aggregator - fetches the best price from multiple DEXes"""

    def __init__(self, chain_id: int = 1):
        self.chain_id = chain_id
        self.providers: Dict[str, DEXProvider] = {}

        # Initialize providers
        if chain_id == 1:
            self.providers["uniswap_v2"] = UniswapV2Provider(chain_id)
        elif chain_id == 56:
            self.providers["pancakeswap_v2"] = UniswapV2Provider(
                chain_id,
                factory_address="0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73",
                router_address=DEX_ROUTERS[56]["pancakeswap_v2"]
            )

    async def get_best_price(self, token_in: str, token_out: str) -> Dict[str, Any]:
        """Get the best price"""
        results = {}

        for name, provider in self.providers.items():
            try:
                price = await provider.get_price(token_in, token_out)
                if price > 0:
                    results[name] = price
            except Exception as e:
                logger.error(f"Failed to get price from {name}: {e}")

        if not results:
            return {"best_price": 0, "best_dex": None, "all_prices": {}}

        best_dex = max(results, key=results.get)

        return {
            "best_price": results[best_dex],
            "best_dex": best_dex,
            "all_prices": results
        }

    async def get_best_quote(
        self,
        token_in: str,
        token_out: str,
        amount_in: int
    ) -> Optional[SwapQuote]:
        """Get the best quote"""
        best_quote = None
        best_amount_out = 0

        for name, provider in self.providers.items():
            try:
                quote = await provider.get_quote(token_in, token_out, amount_in)
                if quote.amount_out > best_amount_out:
                    best_amount_out = quote.amount_out
                    best_quote = quote
            except Exception as e:
                logger.error(f"Failed to get quote from {name}: {e}")

        return best_quote


class OnChainDataProvider:
    """On-chain data provider - integrates DEX prices and on-chain events"""

    def __init__(self, chain_id: int = 1):
        self.chain_id = chain_id
        self.chain = get_chain_provider(chain_id)
        self.dex = DEXAggregator(chain_id)
        self._price_cache: Dict[str, Tuple[float, datetime]] = {}
        self._cache_ttl = 10  # 10-second cache

    async def get_token_price_usd(self, token_address: str) -> float:
        """Get token USD price"""
        # Check cache
        cache_key = f"{token_address}_usd"
        if cache_key in self._price_cache:
            price, cached_at = self._price_cache[cache_key]
            if (datetime.now() - cached_at).seconds < self._cache_ttl:
                return price

        # Get stablecoin addresses
        stables = TOKENS.get(self.chain_id, {})
        usdc = stables.get("USDC")
        usdt = stables.get("USDT")

        if not usdc and not usdt:
            return 0

        # Try to get price
        price = 0
        if usdc:
            result = await self.dex.get_best_price(token_address, usdc)
            price = result.get("best_price", 0)

        if price == 0 and usdt:
            result = await self.dex.get_best_price(token_address, usdt)
            price = result.get("best_price", 0)

        # Cache result
        self._price_cache[cache_key] = (price, datetime.now())

        return price

    async def get_eth_price_usd(self) -> float:
        """Get native token (ETH/BNB/etc.) USD price"""
        weth = TOKENS.get(self.chain_id, {}).get("WETH") or TOKENS.get(self.chain_id, {}).get("WBNB") or TOKENS.get(self.chain_id, {}).get("WMATIC")

        if weth:
            return await self.get_token_price_usd(weth)
        return 0

    async def get_wallet_portfolio(self, address: str) -> Dict[str, Any]:
        """Get wallet portfolio"""
        # Get native token balance
        native_balance = await self.chain.get_balance_ether(address)
        native_price = await self.get_eth_price_usd()

        portfolio = {
            "address": address,
            "chain_id": self.chain_id,
            "native_balance": native_balance,
            "native_value_usd": native_balance * native_price,
            "tokens": [],
            "total_value_usd": native_balance * native_price
        }

        # Get common token balances
        tokens = TOKENS.get(self.chain_id, {})
        for symbol, token_address in tokens.items():
            if symbol.startswith("W"):  # Skip wrapped native tokens
                continue

            try:
                balance = await self.chain.get_token_balance(address, token_address)
                if balance > 0:
                    token_info = await self.chain.get_token_info(token_address)
                    decimals = token_info["decimals"]
                    balance_formatted = balance / (10 ** decimals)

                    price = await self.get_token_price_usd(token_address)
                    value_usd = balance_formatted * price

                    portfolio["tokens"].append({
                        "symbol": symbol,
                        "address": token_address,
                        "balance": balance_formatted,
                        "price_usd": price,
                        "value_usd": value_usd
                    })
                    portfolio["total_value_usd"] += value_usd
            except Exception as e:
                logger.error(f"Failed to get balance for {symbol}: {e}")

        return portfolio
