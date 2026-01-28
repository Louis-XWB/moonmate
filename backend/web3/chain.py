"""
链上交互模块
提供 RPC 连接、余额查询、交易发送等功能
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from web3 import Web3
from web3.middleware import geth_poa_middleware

from backend.core.logger import get_logger

logger = get_logger("chain")


@dataclass
class ChainConfig:
    """链配置"""
    chain_id: int
    name: str
    rpc_url: str
    explorer_url: str
    native_symbol: str
    native_decimals: int = 18


# 预定义链配置
CHAIN_CONFIGS = {
    1: ChainConfig(
        chain_id=1,
        name="Ethereum Mainnet",
        rpc_url="https://eth.llamarpc.com",
        explorer_url="https://etherscan.io",
        native_symbol="ETH",
        native_decimals=18
    ),
    56: ChainConfig(
        chain_id=56,
        name="BNB Smart Chain",
        rpc_url="https://bsc-dataseed.binance.org",
        explorer_url="https://bscscan.com",
        native_symbol="BNB",
        native_decimals=18
    ),
    137: ChainConfig(
        chain_id=137,
        name="Polygon",
        rpc_url="https://polygon-rpc.com",
        explorer_url="https://polygonscan.com",
        native_symbol="MATIC",
        native_decimals=18
    ),
    42161: ChainConfig(
        chain_id=42161,
        name="Arbitrum One",
        rpc_url="https://arb1.arbitrum.io/rpc",
        explorer_url="https://arbiscan.io",
        native_symbol="ETH",
        native_decimals=18
    ),
    10: ChainConfig(
        chain_id=10,
        name="Optimism",
        rpc_url="https://mainnet.optimism.io",
        explorer_url="https://optimistic.etherscan.io",
        native_symbol="ETH",
        native_decimals=18
    ),
    8453: ChainConfig(
        chain_id=8453,
        name="Base",
        rpc_url="https://mainnet.base.org",
        explorer_url="https://basescan.org",
        native_symbol="ETH",
        native_decimals=18
    )
}


@dataclass
class TransactionReceipt:
    """交易回执"""
    tx_hash: str
    block_number: int
    status: bool
    gas_used: int
    effective_gas_price: int
    from_address: str
    to_address: str
    logs: List[Dict]


class ChainProvider(ABC):
    """链提供者基类"""
    
    @abstractmethod
    async def get_balance(self, address: str) -> int:
        """获取原生代币余额"""
        pass
    
    @abstractmethod
    async def get_token_balance(self, address: str, token_address: str) -> int:
        """获取 ERC20 代币余额"""
        pass
    
    @abstractmethod
    async def get_nonce(self, address: str) -> int:
        """获取 nonce"""
        pass
    
    @abstractmethod
    async def get_gas_price(self) -> int:
        """获取 gas 价格"""
        pass
    
    @abstractmethod
    async def send_transaction(self, signed_tx: str) -> str:
        """发送已签名交易"""
        pass
    
    @abstractmethod
    async def wait_for_transaction(self, tx_hash: str, timeout: int = 120) -> TransactionReceipt:
        """等待交易确认"""
        pass


class EthereumProvider(ChainProvider):
    """以太坊兼容链提供者"""
    
    # ERC20 ABI（简化版）
    ERC20_ABI = [
        {
            "constant": True,
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "balance", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "decimals",
            "outputs": [{"name": "", "type": "uint8"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "symbol",
            "outputs": [{"name": "", "type": "string"}],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [
                {"name": "_spender", "type": "address"},
                {"name": "_value", "type": "uint256"}
            ],
            "name": "approve",
            "outputs": [{"name": "", "type": "bool"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [
                {"name": "_owner", "type": "address"},
                {"name": "_spender", "type": "address"}
            ],
            "name": "allowance",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function"
        }
    ]
    
    def __init__(self, chain_id: int = 1, rpc_url: Optional[str] = None):
        self.chain_id = chain_id
        
        # 获取链配置
        if chain_id in CHAIN_CONFIGS:
            self.config = CHAIN_CONFIGS[chain_id]
            rpc_url = rpc_url or self.config.rpc_url
        else:
            self.config = None
            if not rpc_url:
                raise ValueError(f"Unknown chain_id {chain_id}, please provide rpc_url")
        
        # 初始化 Web3
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        
        # 对于 PoA 链添加中间件
        if chain_id in [56, 137]:
            self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        logger.info(f"Chain provider initialized: {chain_id} ({rpc_url[:30]}...)")
    
    @property
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self.w3.is_connected()
    
    async def get_balance(self, address: str) -> int:
        """获取原生代币余额（Wei）"""
        address = Web3.to_checksum_address(address)
        balance = await asyncio.to_thread(self.w3.eth.get_balance, address)
        return balance
    
    async def get_balance_ether(self, address: str) -> float:
        """获取原生代币余额（Ether）"""
        balance_wei = await self.get_balance(address)
        return float(Web3.from_wei(balance_wei, "ether"))
    
    async def get_token_balance(self, address: str, token_address: str) -> int:
        """获取 ERC20 代币余额"""
        address = Web3.to_checksum_address(address)
        token_address = Web3.to_checksum_address(token_address)
        
        contract = self.w3.eth.contract(address=token_address, abi=self.ERC20_ABI)
        balance = await asyncio.to_thread(contract.functions.balanceOf(address).call)
        return balance
    
    async def get_token_info(self, token_address: str) -> Dict[str, Any]:
        """获取代币信息"""
        token_address = Web3.to_checksum_address(token_address)
        contract = self.w3.eth.contract(address=token_address, abi=self.ERC20_ABI)
        
        symbol = await asyncio.to_thread(contract.functions.symbol().call)
        decimals = await asyncio.to_thread(contract.functions.decimals().call)
        
        return {
            "address": token_address,
            "symbol": symbol,
            "decimals": decimals
        }
    
    async def get_nonce(self, address: str) -> int:
        """获取 nonce"""
        address = Web3.to_checksum_address(address)
        nonce = await asyncio.to_thread(self.w3.eth.get_transaction_count, address)
        return nonce
    
    async def get_gas_price(self) -> int:
        """获取 gas 价格（Wei）"""
        gas_price = await asyncio.to_thread(self.w3.eth.gas_price)
        return gas_price
    
    async def get_gas_price_gwei(self) -> float:
        """获取 gas 价格（Gwei）"""
        gas_price = await self.get_gas_price()
        return float(Web3.from_wei(gas_price, "gwei"))
    
    async def estimate_gas(self, tx: Dict[str, Any]) -> int:
        """估算 gas"""
        gas = await asyncio.to_thread(self.w3.eth.estimate_gas, tx)
        return gas
    
    async def send_transaction(self, signed_tx: str) -> str:
        """发送已签名交易"""
        if not signed_tx.startswith("0x"):
            signed_tx = "0x" + signed_tx
        
        tx_hash = await asyncio.to_thread(
            self.w3.eth.send_raw_transaction,
            bytes.fromhex(signed_tx[2:])
        )
        
        logger.info(f"Transaction sent: {tx_hash.hex()}")
        return tx_hash.hex()
    
    async def wait_for_transaction(
        self,
        tx_hash: str,
        timeout: int = 120,
        poll_interval: float = 2.0
    ) -> TransactionReceipt:
        """等待交易确认"""
        if not tx_hash.startswith("0x"):
            tx_hash = "0x" + tx_hash
        
        receipt = await asyncio.to_thread(
            self.w3.eth.wait_for_transaction_receipt,
            tx_hash,
            timeout=timeout,
            poll_latency=poll_interval
        )
        
        return TransactionReceipt(
            tx_hash=receipt.transactionHash.hex(),
            block_number=receipt.blockNumber,
            status=receipt.status == 1,
            gas_used=receipt.gasUsed,
            effective_gas_price=receipt.effectiveGasPrice,
            from_address=receipt["from"],
            to_address=receipt.to,
            logs=[dict(log) for log in receipt.logs]
        )
    
    async def get_block_number(self) -> int:
        """获取当前区块号"""
        return await asyncio.to_thread(self.w3.eth.block_number)
    
    async def get_block(self, block_number: int) -> Dict[str, Any]:
        """获取区块信息"""
        block = await asyncio.to_thread(self.w3.eth.get_block, block_number)
        return dict(block)
    
    async def call_contract(
        self,
        contract_address: str,
        abi: List[Dict],
        function_name: str,
        *args
    ) -> Any:
        """调用合约只读方法"""
        contract_address = Web3.to_checksum_address(contract_address)
        contract = self.w3.eth.contract(address=contract_address, abi=abi)
        
        func = getattr(contract.functions, function_name)
        result = await asyncio.to_thread(func(*args).call)
        return result
    
    def encode_function_call(
        self,
        contract_address: str,
        abi: List[Dict],
        function_name: str,
        *args
    ) -> str:
        """编码合约调用数据"""
        contract_address = Web3.to_checksum_address(contract_address)
        contract = self.w3.eth.contract(address=contract_address, abi=abi)
        
        func = getattr(contract.functions, function_name)
        return func(*args).build_transaction({"from": "0x" + "0" * 40})["data"]


# 全局链提供者缓存
_chain_providers: Dict[int, EthereumProvider] = {}


def get_chain_provider(chain_id: int = 1, rpc_url: Optional[str] = None) -> EthereumProvider:
    """获取链提供者（带缓存）"""
    if chain_id not in _chain_providers:
        _chain_providers[chain_id] = EthereumProvider(chain_id, rpc_url)
    return _chain_providers[chain_id]
