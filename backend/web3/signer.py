"""
签名模块
支持消息签名、EIP-712 结构化签名、交易签名
"""

import json
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from eth_account import Account
from eth_account.messages import encode_defunct, encode_structured_data
from web3 import Web3

from backend.core.logger import get_logger

logger = get_logger("signer")


@dataclass
class SignatureResult:
    """签名结果"""
    message_hash: str
    signature: str
    r: str
    s: str
    v: int
    signer: str
    timestamp: datetime


class MessageSigner:
    """消息签名器"""
    
    def __init__(self, private_key: str):
        if not private_key.startswith("0x"):
            private_key = "0x" + private_key
        self._account = Account.from_key(private_key)
    
    @property
    def address(self) -> str:
        return self._account.address
    
    def sign_message(self, message: str) -> SignatureResult:
        """签名普通消息"""
        message_hash = encode_defunct(text=message)
        signed = self._account.sign_message(message_hash)
        
        return SignatureResult(
            message_hash=message_hash.body.hex() if hasattr(message_hash, 'body') else "",
            signature=signed.signature.hex(),
            r=hex(signed.r),
            s=hex(signed.s),
            v=signed.v,
            signer=self.address,
            timestamp=datetime.now()
        )
    
    def sign_typed_data(self, domain: Dict, types: Dict, message: Dict) -> SignatureResult:
        """签名 EIP-712 结构化数据"""
        structured_data = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                **types
            },
            "primaryType": list(types.keys())[0],
            "domain": domain,
            "message": message
        }
        
        encoded = encode_structured_data(structured_data)
        signed = self._account.sign_message(encoded)
        
        return SignatureResult(
            message_hash=encoded.body.hex() if hasattr(encoded, 'body') else "",
            signature=signed.signature.hex(),
            r=hex(signed.r),
            s=hex(signed.s),
            v=signed.v,
            signer=self.address,
            timestamp=datetime.now()
        )
    
    @staticmethod
    def recover_signer(message: str, signature: str) -> str:
        """从签名恢复签名者地址"""
        message_hash = encode_defunct(text=message)
        return Account.recover_message(message_hash, signature=signature)
    
    @staticmethod
    def verify_signature(message: str, signature: str, expected_signer: str) -> bool:
        """验证签名"""
        try:
            recovered = MessageSigner.recover_signer(message, signature)
            return recovered.lower() == expected_signer.lower()
        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False


class TransactionSigner:
    """交易签名器"""
    
    def __init__(self, private_key: str, chain_id: int = 1):
        if not private_key.startswith("0x"):
            private_key = "0x" + private_key
        self._account = Account.from_key(private_key)
        self.chain_id = chain_id
    
    @property
    def address(self) -> str:
        return self._account.address
    
    def sign_transaction(
        self,
        to: str,
        value: int = 0,
        data: str = "0x",
        nonce: int = 0,
        gas: int = 21000,
        gas_price: Optional[int] = None,
        max_fee_per_gas: Optional[int] = None,
        max_priority_fee_per_gas: Optional[int] = None
    ) -> Dict[str, Any]:
        """签名交易"""
        
        tx = {
            "to": Web3.to_checksum_address(to),
            "value": value,
            "data": data,
            "nonce": nonce,
            "gas": gas,
            "chainId": self.chain_id
        }
        
        # EIP-1559 交易
        if max_fee_per_gas and max_priority_fee_per_gas:
            tx["maxFeePerGas"] = max_fee_per_gas
            tx["maxPriorityFeePerGas"] = max_priority_fee_per_gas
            tx["type"] = 2
        elif gas_price:
            tx["gasPrice"] = gas_price
        else:
            # 默认 gas price
            tx["gasPrice"] = Web3.to_wei(50, "gwei")
        
        signed_tx = self._account.sign_transaction(tx)
        
        return {
            "raw_transaction": signed_tx.rawTransaction.hex(),
            "hash": signed_tx.hash.hex(),
            "r": hex(signed_tx.r),
            "s": hex(signed_tx.s),
            "v": signed_tx.v,
            "from": self.address,
            "to": to,
            "value": value,
            "nonce": nonce,
            "gas": gas,
            "chain_id": self.chain_id
        }
    
    def sign_contract_call(
        self,
        contract_address: str,
        function_data: str,
        value: int = 0,
        nonce: int = 0,
        gas: int = 100000,
        gas_price: Optional[int] = None
    ) -> Dict[str, Any]:
        """签名合约调用"""
        return self.sign_transaction(
            to=contract_address,
            value=value,
            data=function_data,
            nonce=nonce,
            gas=gas,
            gas_price=gas_price
        )


class EIP712Signer:
    """EIP-712 签名器（用于 DEX 订单签名等）"""
    
    # Uniswap Permit2 域
    PERMIT2_DOMAIN = {
        "name": "Permit2",
        "chainId": 1,
        "verifyingContract": "0x000000000022D473030F116dDEE9F6B43aC78BA3"
    }
    
    # Permit 类型
    PERMIT_TYPES = {
        "PermitSingle": [
            {"name": "details", "type": "PermitDetails"},
            {"name": "spender", "type": "address"},
            {"name": "sigDeadline", "type": "uint256"}
        ],
        "PermitDetails": [
            {"name": "token", "type": "address"},
            {"name": "amount", "type": "uint160"},
            {"name": "expiration", "type": "uint48"},
            {"name": "nonce", "type": "uint48"}
        ]
    }
    
    def __init__(self, private_key: str, chain_id: int = 1):
        self.signer = MessageSigner(private_key)
        self.chain_id = chain_id
    
    def sign_permit(
        self,
        token: str,
        spender: str,
        amount: int,
        expiration: int,
        nonce: int,
        deadline: int
    ) -> SignatureResult:
        """签名 Permit2 授权"""
        domain = {**self.PERMIT2_DOMAIN, "chainId": self.chain_id}
        
        message = {
            "details": {
                "token": token,
                "amount": amount,
                "expiration": expiration,
                "nonce": nonce
            },
            "spender": spender,
            "sigDeadline": deadline
        }
        
        return self.signer.sign_typed_data(domain, self.PERMIT_TYPES, message)
    
    def sign_order(
        self,
        order_type: str,
        order_data: Dict[str, Any],
        domain: Dict[str, Any],
        types: Dict[str, Any]
    ) -> SignatureResult:
        """签名通用订单（如 0x、1inch 等）"""
        return self.signer.sign_typed_data(domain, types, order_data)
