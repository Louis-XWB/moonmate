"""
Wallet Management Module
Supports private key/mnemonic import, address generation, and balance queries
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
    """Wallet type"""
    PRIVATE_KEY = "private_key"
    MNEMONIC = "mnemonic"
    KEYSTORE = "keystore"
    HARDWARE = "hardware"  # Hardware wallet (reserved)


@dataclass
class WalletInfo:
    """Wallet information"""
    address: str
    wallet_type: WalletType
    name: str
    created_at: datetime
    is_locked: bool = True
    balance: float = 0
    chain_id: int = 1  # Default: Ethereum mainnet


class Wallet:
    """Wallet class"""

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
        """Initialize from private key"""
        try:
            # Ensure private key format is correct
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
        """Initialize from mnemonic"""
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
        """Get wallet address"""
        if self._account:
            return self._account.address
        return ""

    @property
    def is_locked(self) -> bool:
        """Whether the wallet is locked"""
        return self._is_locked

    @property
    def private_key(self) -> Optional[str]:
        """Get private key (only when unlocked)"""
        if self._is_locked:
            return None
        return self._private_key

    def lock(self):
        """Lock the wallet"""
        self._is_locked = True
        logger.info(f"Wallet locked: {self.address[:10]}...")

    def unlock(self, password: str) -> bool:
        """Unlock the wallet (simplified; production should use encrypted storage)"""
        # Simplified handling; production should verify the password
        self._is_locked = False
        logger.info(f"Wallet unlocked: {self.address[:10]}...")
        return True

    def sign_message(self, message: str) -> Dict[str, Any]:
        """Sign a message"""
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
        """Sign a transaction"""
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
        """Get wallet information"""
        return WalletInfo(
            address=self.address,
            wallet_type=WalletType.PRIVATE_KEY,
            name=self.name,
            created_at=self.created_at,
            is_locked=self._is_locked
        )

    @staticmethod
    def generate_mnemonic(strength: int = 128) -> str:
        """Generate a mnemonic phrase"""
        Account.enable_unaudited_hdwallet_features()
        return generate_mnemonic(strength, "english")

    @staticmethod
    def create_random(name: str = "random") -> "Wallet":
        """Create a random wallet"""
        account = Account.create()
        wallet = Wallet(private_key=account.key.hex(), name=name)
        return wallet


class WalletManager:
    """Wallet manager"""

    def __init__(self):
        self._wallets: Dict[str, Wallet] = {}
        self._active_wallet: Optional[str] = None

    def add_wallet(self, wallet: Wallet) -> str:
        """Add a wallet"""
        address = wallet.address.lower()
        self._wallets[address] = wallet

        if self._active_wallet is None:
            self._active_wallet = address

        logger.info(f"Wallet added: {address[:10]}...")
        return address

    def remove_wallet(self, address: str) -> bool:
        """Remove a wallet"""
        address = address.lower()
        if address in self._wallets:
            del self._wallets[address]
            if self._active_wallet == address:
                self._active_wallet = next(iter(self._wallets), None)
            logger.info(f"Wallet removed: {address[:10]}...")
            return True
        return False

    def get_wallet(self, address: str) -> Optional[Wallet]:
        """Get a wallet"""
        return self._wallets.get(address.lower())

    def get_active_wallet(self) -> Optional[Wallet]:
        """Get the currently active wallet"""
        if self._active_wallet:
            return self._wallets.get(self._active_wallet)
        return None

    def set_active_wallet(self, address: str) -> bool:
        """Set the active wallet"""
        address = address.lower()
        if address in self._wallets:
            self._active_wallet = address
            logger.info(f"Active wallet set: {address[:10]}...")
            return True
        return False

    def list_wallets(self) -> List[WalletInfo]:
        """List all wallets"""
        return [w.get_info() for w in self._wallets.values()]

    def import_from_private_key(self, private_key: str, name: str = "imported") -> str:
        """Import a wallet from a private key"""
        wallet = Wallet(private_key=private_key, name=name)
        return self.add_wallet(wallet)

    def import_from_mnemonic(self, mnemonic: str, name: str = "imported") -> str:
        """Import a wallet from a mnemonic phrase"""
        wallet = Wallet(mnemonic=mnemonic, name=name)
        return self.add_wallet(wallet)

    def create_wallet(self, name: str = "new") -> Wallet:
        """Create a new wallet"""
        wallet = Wallet.create_random(name=name)
        self.add_wallet(wallet)
        return wallet


# Global wallet manager instance
_wallet_manager: Optional[WalletManager] = None


def get_wallet_manager() -> WalletManager:
    """Get the global wallet manager"""
    global _wallet_manager
    if _wallet_manager is None:
        _wallet_manager = WalletManager()
    return _wallet_manager
