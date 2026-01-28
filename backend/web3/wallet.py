"""
钱包管理模块
支持私钥/助记词导入、地址生成、余额查询
"""

import os
import json
import hashlib
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from eth_account import Account
from eth_account.hdaccount import generate_mnemonic, seed_from_mnemonic, key_from_seed
from web3 import Web3

from backend.core.logger import get_logger

logger = get_logger("wallet")


class WalletType(str, Enum):
    """钱包类型"""
    PRIVATE_KEY = "private_key"
    MNEMONIC = "mnemonic"
    KEYSTORE = "keystore"
    HARDWARE = "hardware"  # 硬件钱包（预留）


@dataclass
class WalletInfo:
    """钱包信息"""
    address: str
    wallet_type: WalletType
    name: str
    created_at: datetime
    is_locked: bool = True
    balance: float = 0
    chain_id: int = 1  # 默认以太坊主网


class Wallet:
    """钱包类"""
    
    def __init__(
        self,
        private_key: Optional[str] = None,
        mnemonic: Optional[str] = None,
        name: str = "default"
    ):
        self.name = name
        self.created_at = datetime.now()
        self._private_key: Optional[str] = None
        self._account: Optional[Account] = None
        self._is_locked = True
        
        if private_key:
            self._init_from_private_key(private_key)
        elif mnemonic:
            self._init_from_mnemonic(mnemonic)
    
    def _init_from_private_key(self, private_key: str):
        """从私钥初始化"""
        try:
            # 确保私钥格式正确
            if not private_key.startswith("0x"):
                private_key = "0x" + private_key
            
            self._account = Account.from_key(private_key)
            self._private_key = private_key
            self._is_locked = False
            
            logger.info(f"Wallet initialized from private key: {self.address[:10]}...")
        except Exception as e:
            logger.error(f"Failed to init wallet from private key: {e}")
            raise ValueError(f"Invalid private key: {e}")
    
    def _init_from_mnemonic(self, mnemonic: str, path: str = "m/44'/60'/0'/0/0"):
        """从助记词初始化"""
        try:
            Account.enable_unaudited_hdwallet_features()
            self._account = Account.from_mnemonic(mnemonic, account_path=path)
            self._private_key = self._account.key.hex()
            self._is_locked = False
            
            logger.info(f"Wallet initialized from mnemonic: {self.address[:10]}...")
        except Exception as e:
            logger.error(f"Failed to init wallet from mnemonic: {e}")
            raise ValueError(f"Invalid mnemonic: {e}")
    
    @property
    def address(self) -> str:
        """获取钱包地址"""
        if self._account:
            return self._account.address
        return ""
    
    @property
    def is_locked(self) -> bool:
        """钱包是否锁定"""
        return self._is_locked
    
    @property
    def private_key(self) -> Optional[str]:
        """获取私钥（仅在解锁状态）"""
        if self._is_locked:
            return None
        return self._private_key
    
    def lock(self):
        """锁定钱包"""
        self._is_locked = True
        logger.info(f"Wallet locked: {self.address[:10]}...")
    
    def unlock(self, password: str) -> bool:
        """解锁钱包（简化版，实际应使用加密存储）"""
        # 这里简化处理，实际应该验证密码
        self._is_locked = False
        logger.info(f"Wallet unlocked: {self.address[:10]}...")
        return True
    
    def sign_message(self, message: str) -> Dict[str, Any]:
        """签名消息"""
        if self._is_locked:
            raise ValueError("Wallet is locked")
        
        from eth_account.messages import encode_defunct
        
        message_hash = encode_defunct(text=message)
        signed = self._account.sign_message(message_hash)
        
        return {
            "message": message,
            "signature": signed.signature.hex(),
            "r": hex(signed.r),
            "s": hex(signed.s),
            "v": signed.v,
            "signer": self.address
        }
    
    def sign_transaction(self, tx: Dict[str, Any]) -> Dict[str, Any]:
        """签名交易"""
        if self._is_locked:
            raise ValueError("Wallet is locked")
        
        signed_tx = self._account.sign_transaction(tx)
        
        return {
            "raw_transaction": signed_tx.rawTransaction.hex(),
            "hash": signed_tx.hash.hex(),
            "r": hex(signed_tx.r),
            "s": hex(signed_tx.s),
            "v": signed_tx.v
        }
    
    def get_info(self) -> WalletInfo:
        """获取钱包信息"""
        return WalletInfo(
            address=self.address,
            wallet_type=WalletType.PRIVATE_KEY,
            name=self.name,
            created_at=self.created_at,
            is_locked=self._is_locked
        )
    
    @staticmethod
    def generate_mnemonic(strength: int = 128) -> str:
        """生成助记词"""
        Account.enable_unaudited_hdwallet_features()
        return generate_mnemonic(strength, "english")
    
    @staticmethod
    def create_random(name: str = "random") -> "Wallet":
        """创建随机钱包"""
        account = Account.create()
        wallet = Wallet(private_key=account.key.hex(), name=name)
        return wallet


class WalletManager:
    """钱包管理器"""
    
    def __init__(self):
        self._wallets: Dict[str, Wallet] = {}
        self._active_wallet: Optional[str] = None
    
    def add_wallet(self, wallet: Wallet) -> str:
        """添加钱包"""
        address = wallet.address.lower()
        self._wallets[address] = wallet
        
        if self._active_wallet is None:
            self._active_wallet = address
        
        logger.info(f"Wallet added: {address[:10]}...")
        return address
    
    def remove_wallet(self, address: str) -> bool:
        """移除钱包"""
        address = address.lower()
        if address in self._wallets:
            del self._wallets[address]
            if self._active_wallet == address:
                self._active_wallet = next(iter(self._wallets), None)
            logger.info(f"Wallet removed: {address[:10]}...")
            return True
        return False
    
    def get_wallet(self, address: str) -> Optional[Wallet]:
        """获取钱包"""
        return self._wallets.get(address.lower())
    
    def get_active_wallet(self) -> Optional[Wallet]:
        """获取当前活跃钱包"""
        if self._active_wallet:
            return self._wallets.get(self._active_wallet)
        return None
    
    def set_active_wallet(self, address: str) -> bool:
        """设置活跃钱包"""
        address = address.lower()
        if address in self._wallets:
            self._active_wallet = address
            logger.info(f"Active wallet set: {address[:10]}...")
            return True
        return False
    
    def list_wallets(self) -> List[WalletInfo]:
        """列出所有钱包"""
        return [w.get_info() for w in self._wallets.values()]
    
    def import_from_private_key(self, private_key: str, name: str = "imported") -> str:
        """从私钥导入钱包"""
        wallet = Wallet(private_key=private_key, name=name)
        return self.add_wallet(wallet)
    
    def import_from_mnemonic(self, mnemonic: str, name: str = "imported") -> str:
        """从助记词导入钱包"""
        wallet = Wallet(mnemonic=mnemonic, name=name)
        return self.add_wallet(wallet)
    
    def create_wallet(self, name: str = "new") -> Wallet:
        """创建新钱包"""
        wallet = Wallet.create_random(name=name)
        self.add_wallet(wallet)
        return wallet


# 全局钱包管理器实例
_wallet_manager: Optional[WalletManager] = None


def get_wallet_manager() -> WalletManager:
    """获取全局钱包管理器"""
    global _wallet_manager
    if _wallet_manager is None:
        _wallet_manager = WalletManager()
    return _wallet_manager
