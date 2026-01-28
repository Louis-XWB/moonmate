"""
DEX Swap 执行模块
支持 Uniswap、PancakeSwap 等 DEX 的代币交换
"""

import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from web3 import Web3

from backend.core.logger import get_logger
from .chain import EthereumProvider, get_chain_provider, TransactionReceipt
from .wallet import Wallet
from .signer import TransactionSigner
from .dex import DEXAggregator, SwapQuote, TOKENS, DEX_ROUTERS

logger = get_logger("swap")


class SwapStatus(str, Enum):
    """交换状态"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    FAILED = "failed"


@dataclass
class SwapResult:
    """交换结果"""
    status: SwapStatus
    tx_hash: Optional[str]
    token_in: str
    token_out: str
    amount_in: int
    amount_out: int
    gas_used: int
    gas_price: int
    error: Optional[str] = None
    receipt: Optional[TransactionReceipt] = None


class SwapExecutor:
    """Swap 执行器"""
    
    # Uniswap V2 Router ABI（交换相关）
    ROUTER_ABI = [
        {
            "inputs": [
                {"name": "amountIn", "type": "uint256"},
                {"name": "amountOutMin", "type": "uint256"},
                {"name": "path", "type": "address[]"},
                {"name": "to", "type": "address"},
                {"name": "deadline", "type": "uint256"}
            ],
            "name": "swapExactTokensForTokens",
            "outputs": [{"name": "amounts", "type": "uint256[]"}],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [
                {"name": "amountOutMin", "type": "uint256"},
                {"name": "path", "type": "address[]"},
                {"name": "to", "type": "address"},
                {"name": "deadline", "type": "uint256"}
            ],
            "name": "swapExactETHForTokens",
            "outputs": [{"name": "amounts", "type": "uint256[]"}],
            "stateMutability": "payable",
            "type": "function"
        },
        {
            "inputs": [
                {"name": "amountIn", "type": "uint256"},
                {"name": "amountOutMin", "type": "uint256"},
                {"name": "path", "type": "address[]"},
                {"name": "to", "type": "address"},
                {"name": "deadline", "type": "uint256"}
            ],
            "name": "swapExactTokensForETH",
            "outputs": [{"name": "amounts", "type": "uint256[]"}],
            "stateMutability": "nonpayable",
            "type": "function"
        },
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
    
    # ERC20 Approve ABI
    ERC20_APPROVE_ABI = [
        {
            "inputs": [
                {"name": "spender", "type": "address"},
                {"name": "amount", "type": "uint256"}
            ],
            "name": "approve",
            "outputs": [{"name": "", "type": "bool"}],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [
                {"name": "owner", "type": "address"},
                {"name": "spender", "type": "address"}
            ],
            "name": "allowance",
            "outputs": [{"name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        }
    ]
    
    def __init__(
        self,
        wallet: Wallet,
        chain_id: int = 1,
        router_address: Optional[str] = None,
        slippage_tolerance: float = 0.5,  # 0.5%
        deadline_minutes: int = 20
    ):
        self.wallet = wallet
        self.chain_id = chain_id
        self.chain = get_chain_provider(chain_id)
        self.aggregator = DEXAggregator(chain_id)
        self.slippage_tolerance = slippage_tolerance
        self.deadline_minutes = deadline_minutes
        
        # 设置路由器地址
        if router_address:
            self.router_address = router_address
        elif chain_id == 1:
            self.router_address = DEX_ROUTERS[1]["uniswap_v2"]
        elif chain_id == 56:
            self.router_address = DEX_ROUTERS[56]["pancakeswap_v2"]
        else:
            raise ValueError(f"No default router for chain {chain_id}")
        
        # 获取 WETH 地址
        tokens = TOKENS.get(chain_id, {})
        self.weth_address = tokens.get("WETH") or tokens.get("WBNB") or tokens.get("WMATIC")
        
        logger.info(f"SwapExecutor initialized: chain={chain_id}, router={self.router_address[:10]}...")
    
    async def check_allowance(self, token_address: str, amount: int) -> bool:
        """检查授权额度"""
        allowance = await self.chain.call_contract(
            token_address,
            self.ERC20_APPROVE_ABI,
            "allowance",
            Web3.to_checksum_address(self.wallet.address),
            Web3.to_checksum_address(self.router_address)
        )
        return allowance >= amount
    
    async def approve_token(
        self,
        token_address: str,
        amount: int = 2**256 - 1  # 最大授权
    ) -> str:
        """授权代币"""
        logger.info(f"Approving token: {token_address[:10]}...")
        
        # 构建授权交易数据
        contract = self.chain.w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=self.ERC20_APPROVE_ABI
        )
        
        data = contract.functions.approve(
            Web3.to_checksum_address(self.router_address),
            amount
        ).build_transaction({
            "from": self.wallet.address
        })["data"]
        
        # 获取 nonce 和 gas
        nonce = await self.chain.get_nonce(self.wallet.address)
        gas_price = await self.chain.get_gas_price()
        
        # 签名交易
        signer = TransactionSigner(self.wallet.private_key, self.chain_id)
        signed = signer.sign_transaction(
            to=token_address,
            data=data,
            nonce=nonce,
            gas=100000,
            gas_price=gas_price
        )
        
        # 发送交易
        tx_hash = await self.chain.send_transaction(signed["raw_transaction"])
        
        # 等待确认
        receipt = await self.chain.wait_for_transaction(tx_hash)
        
        if receipt.status:
            logger.info(f"Token approved: {tx_hash}")
        else:
            logger.error(f"Approval failed: {tx_hash}")
        
        return tx_hash
    
    async def get_quote(
        self,
        token_in: str,
        token_out: str,
        amount_in: int
    ) -> SwapQuote:
        """获取交换报价"""
        return await self.aggregator.get_best_quote(token_in, token_out, amount_in)
    
    async def swap(
        self,
        token_in: str,
        token_out: str,
        amount_in: int,
        min_amount_out: Optional[int] = None,
        auto_approve: bool = True
    ) -> SwapResult:
        """执行代币交换"""
        logger.info(f"Executing swap: {amount_in} {token_in[:10]}... -> {token_out[:10]}...")
        
        try:
            # 检查钱包是否解锁
            if self.wallet.is_locked:
                return SwapResult(
                    status=SwapStatus.FAILED,
                    tx_hash=None,
                    token_in=token_in,
                    token_out=token_out,
                    amount_in=amount_in,
                    amount_out=0,
                    gas_used=0,
                    gas_price=0,
                    error="Wallet is locked"
                )
            
            # 获取报价
            quote = await self.get_quote(token_in, token_out, amount_in)
            if not quote:
                return SwapResult(
                    status=SwapStatus.FAILED,
                    tx_hash=None,
                    token_in=token_in,
                    token_out=token_out,
                    amount_in=amount_in,
                    amount_out=0,
                    gas_used=0,
                    gas_price=0,
                    error="Failed to get quote"
                )
            
            # 计算最小输出（考虑滑点）
            if min_amount_out is None:
                min_amount_out = int(quote.amount_out * (1 - self.slippage_tolerance / 100))
            
            # 检查并授权
            is_eth_in = token_in.lower() == self.weth_address.lower() if self.weth_address else False
            
            if not is_eth_in and auto_approve:
                has_allowance = await self.check_allowance(token_in, amount_in)
                if not has_allowance:
                    logger.info("Insufficient allowance, approving...")
                    await self.approve_token(token_in)
            
            # 构建交换交易
            path = [
                Web3.to_checksum_address(token_in),
                Web3.to_checksum_address(token_out)
            ]
            deadline = int(datetime.now().timestamp()) + self.deadline_minutes * 60
            
            contract = self.chain.w3.eth.contract(
                address=Web3.to_checksum_address(self.router_address),
                abi=self.ROUTER_ABI
            )
            
            # 根据代币类型选择方法
            is_eth_out = token_out.lower() == self.weth_address.lower() if self.weth_address else False
            
            if is_eth_in:
                # ETH -> Token
                tx_data = contract.functions.swapExactETHForTokens(
                    min_amount_out,
                    path,
                    Web3.to_checksum_address(self.wallet.address),
                    deadline
                ).build_transaction({
                    "from": self.wallet.address,
                    "value": amount_in
                })
            elif is_eth_out:
                # Token -> ETH
                tx_data = contract.functions.swapExactTokensForETH(
                    amount_in,
                    min_amount_out,
                    path,
                    Web3.to_checksum_address(self.wallet.address),
                    deadline
                ).build_transaction({
                    "from": self.wallet.address
                })
            else:
                # Token -> Token
                tx_data = contract.functions.swapExactTokensForTokens(
                    amount_in,
                    min_amount_out,
                    path,
                    Web3.to_checksum_address(self.wallet.address),
                    deadline
                ).build_transaction({
                    "from": self.wallet.address
                })
            
            # 获取 nonce 和 gas
            nonce = await self.chain.get_nonce(self.wallet.address)
            gas_price = await self.chain.get_gas_price()
            gas_limit = quote.gas_estimate + 50000  # 添加缓冲
            
            # 签名交易
            signer = TransactionSigner(self.wallet.private_key, self.chain_id)
            signed = signer.sign_transaction(
                to=self.router_address,
                value=amount_in if is_eth_in else 0,
                data=tx_data["data"],
                nonce=nonce,
                gas=gas_limit,
                gas_price=gas_price
            )
            
            # 发送交易
            tx_hash = await self.chain.send_transaction(signed["raw_transaction"])
            logger.info(f"Swap transaction sent: {tx_hash}")
            
            # 等待确认
            receipt = await self.chain.wait_for_transaction(tx_hash)
            
            if receipt.status:
                logger.info(f"Swap successful: {tx_hash}")
                return SwapResult(
                    status=SwapStatus.CONFIRMED,
                    tx_hash=tx_hash,
                    token_in=token_in,
                    token_out=token_out,
                    amount_in=amount_in,
                    amount_out=quote.amount_out,  # 实际输出需要从日志解析
                    gas_used=receipt.gas_used,
                    gas_price=receipt.effective_gas_price,
                    receipt=receipt
                )
            else:
                logger.error(f"Swap failed: {tx_hash}")
                return SwapResult(
                    status=SwapStatus.FAILED,
                    tx_hash=tx_hash,
                    token_in=token_in,
                    token_out=token_out,
                    amount_in=amount_in,
                    amount_out=0,
                    gas_used=receipt.gas_used,
                    gas_price=receipt.effective_gas_price,
                    error="Transaction reverted",
                    receipt=receipt
                )
                
        except Exception as e:
            logger.error(f"Swap error: {e}")
            return SwapResult(
                status=SwapStatus.FAILED,
                tx_hash=None,
                token_in=token_in,
                token_out=token_out,
                amount_in=amount_in,
                amount_out=0,
                gas_used=0,
                gas_price=0,
                error=str(e)
            )
    
    async def estimate_gas(
        self,
        token_in: str,
        token_out: str,
        amount_in: int
    ) -> Dict[str, Any]:
        """估算 Gas 费用"""
        quote = await self.get_quote(token_in, token_out, amount_in)
        gas_price = await self.chain.get_gas_price()
        
        gas_limit = quote.gas_estimate if quote else 200000
        gas_cost_wei = gas_limit * gas_price
        gas_cost_eth = Web3.from_wei(gas_cost_wei, "ether")
        
        return {
            "gas_limit": gas_limit,
            "gas_price_gwei": float(Web3.from_wei(gas_price, "gwei")),
            "gas_cost_eth": float(gas_cost_eth),
            "gas_cost_wei": gas_cost_wei
        }


class MEVProtection:
    """MEV 保护"""
    
    # Flashbots RPC
    FLASHBOTS_RPC = "https://rpc.flashbots.net"
    
    def __init__(self, chain_id: int = 1):
        self.chain_id = chain_id
        self.enabled = chain_id == 1  # 目前只支持以太坊主网
    
    async def send_private_transaction(
        self,
        signed_tx: str,
        max_block_number: Optional[int] = None
    ) -> Dict[str, Any]:
        """通过 Flashbots 发送私有交易"""
        if not self.enabled:
            raise ValueError("MEV protection only available on Ethereum mainnet")
        
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_sendPrivateTransaction",
                "params": [{
                    "tx": signed_tx,
                    "maxBlockNumber": max_block_number
                }],
                "id": 1
            }
            
            async with session.post(self.FLASHBOTS_RPC, json=payload) as resp:
                result = await resp.json()
                return result
    
    @staticmethod
    def calculate_mev_risk(
        amount_usd: float,
        price_impact: float,
        is_large_trade: bool = False
    ) -> Dict[str, Any]:
        """评估 MEV 风险"""
        risk_score = 0
        risk_factors = []
        
        # 大额交易风险
        if amount_usd > 10000:
            risk_score += 30
            risk_factors.append("Large trade amount")
        
        if amount_usd > 100000:
            risk_score += 30
            risk_factors.append("Very large trade amount")
        
        # 价格影响风险
        if price_impact > 1:
            risk_score += 20
            risk_factors.append("High price impact")
        
        if price_impact > 3:
            risk_score += 20
            risk_factors.append("Very high price impact")
        
        # 确定风险等级
        if risk_score >= 60:
            risk_level = "high"
            recommendation = "Use MEV protection (Flashbots)"
        elif risk_score >= 30:
            risk_level = "medium"
            recommendation = "Consider using MEV protection"
        else:
            risk_level = "low"
            recommendation = "Standard transaction is acceptable"
        
        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "recommendation": recommendation
        }
