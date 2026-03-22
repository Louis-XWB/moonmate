"""
Configuration management module
Supports multi-environment configuration, hot-reload, and config validation
"""

import os
import yaml
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


class Environment(str, Enum):
    """Runtime environment"""
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class ExchangeConfig(BaseModel):
    """Exchange configuration"""
    name: str = Field(..., description="Exchange name")
    api_key: str = Field(default="", description="API Key")
    api_secret: str = Field(default="", description="API Secret")
    passphrase: str = Field(default="", description="API Passphrase (required by some exchanges)")
    testnet: bool = Field(default=True, description="Whether to use testnet")
    rate_limit: int = Field(default=10, description="Rate limit per second")


class TradingConfig(BaseModel):
    """Trading configuration"""
    mode: str = Field(default="paper", description="Trading mode: paper/live_cex/live_dex")
    symbols: List[str] = Field(default=["BTC/USDT"], description="Trading pair list")
    base_currency: str = Field(default="USDT", description="Base currency")
    max_position_size: float = Field(default=1000.0, description="Maximum position amount")
    max_single_order: float = Field(default=100.0, description="Maximum single order amount")
    leverage: int = Field(default=1, description="Leverage multiplier")
    order_types: List[str] = Field(default=["limit", "market"], description="Supported order types")
    min_order_interval: int = Field(default=60, description="Minimum order interval (seconds)")


class RiskConfig(BaseModel):
    """Risk control configuration"""
    max_daily_loss: float = Field(default=100.0, description="Maximum daily loss amount")
    max_daily_loss_pct: float = Field(default=5.0, description="Maximum daily loss percentage")
    max_drawdown: float = Field(default=10.0, description="Maximum drawdown percentage")
    stop_loss_pct: float = Field(default=2.0, description="Stop-loss percentage")
    take_profit_pct: float = Field(default=5.0, description="Take-profit percentage")
    trailing_stop_pct: float = Field(default=1.0, description="Trailing stop percentage")
    max_consecutive_losses: int = Field(default=5, description="Maximum consecutive losses")
    cooldown_period: int = Field(default=3600, description="Circuit breaker cooldown period (seconds)")
    position_limit: int = Field(default=3, description="Maximum concurrent positions")


class AIConfig(BaseModel):
    """AI configuration"""
    enabled: bool = Field(default=True, description="Whether to enable AI signals")
    model: str = Field(default="gpt-4.1-mini", description="Model to use")
    temperature: float = Field(default=0.3, description="Model temperature")
    max_tokens: int = Field(default=1000, description="Maximum token count")
    confidence_threshold: float = Field(default=0.6, description="Signal confidence threshold")
    signal_ttl: int = Field(default=300, description="Signal TTL (seconds)")


class StrategyConfig(BaseModel):
    """Strategy configuration"""
    name: str = Field(default="momentum", description="Strategy name")
    enabled: bool = Field(default=True, description="Whether to enable")
    params: Dict[str, Any] = Field(default_factory=dict, description="Strategy parameters")
    weight: float = Field(default=1.0, description="Strategy weight")


class Config(BaseModel):
    """Main configuration class"""
    env: Environment = Field(default=Environment.DEV, description="Runtime environment")
    debug: bool = Field(default=True, description="Debug mode")
    
    # Exchange configuration
    exchange: ExchangeConfig = Field(default_factory=lambda: ExchangeConfig(name="binance"))
    
    # Trading configuration
    trading: TradingConfig = Field(default_factory=TradingConfig)
    
    # Risk control configuration
    risk: RiskConfig = Field(default_factory=RiskConfig)
    
    # AI configuration
    ai: AIConfig = Field(default_factory=AIConfig)
    
    # Strategy configuration list
    strategies: List[StrategyConfig] = Field(default_factory=list)
    
    # API service configuration
    api_host: str = Field(default="0.0.0.0", description="API service address")
    api_port: int = Field(default=8000, description="API service port")
    
    # WebSocket configuration
    ws_enabled: bool = Field(default=True, description="Whether to enable WebSocket")
    
    @classmethod
    def load_from_file(cls, config_path: str) -> "Config":
        """Load configuration from file"""
        if not os.path.exists(config_path):
            return cls()
        
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        return cls(**data) if data else cls()
    
    @classmethod
    def load_from_env(cls) -> "Config":
        """Load configuration from environment variables"""
        env = os.getenv("TRADING_ENV", "dev")
        config_path = f"config/{env}.yaml"
        return cls.load_from_file(config_path)
    
    def save_to_file(self, config_path: str):
        """Save configuration to file"""
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False, allow_unicode=True)


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get global configuration"""
    global _config
    if _config is None:
        _config = Config.load_from_env()
    return _config


def set_config(config: Config):
    """Set global configuration"""
    global _config
    _config = config
