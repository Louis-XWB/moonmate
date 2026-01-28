"""
配置管理模块
支持多环境配置、热加载、配置验证
"""

import os
import yaml
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


class Environment(str, Enum):
    """运行环境"""
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class ExchangeConfig(BaseModel):
    """交易所配置"""
    name: str = Field(..., description="交易所名称")
    api_key: str = Field(default="", description="API Key")
    api_secret: str = Field(default="", description="API Secret")
    passphrase: str = Field(default="", description="API Passphrase (部分交易所需要)")
    testnet: bool = Field(default=True, description="是否使用测试网")
    rate_limit: int = Field(default=10, description="每秒请求限制")


class TradingConfig(BaseModel):
    """交易配置"""
    mode: str = Field(default="paper", description="交易模式: paper/live_cex/live_dex")
    symbols: List[str] = Field(default=["BTC/USDT"], description="交易对列表")
    base_currency: str = Field(default="USDT", description="基础货币")
    max_position_size: float = Field(default=1000.0, description="最大持仓金额")
    max_single_order: float = Field(default=100.0, description="单笔最大下单金额")
    leverage: int = Field(default=1, description="杠杆倍数")
    order_types: List[str] = Field(default=["limit", "market"], description="支持的订单类型")
    min_order_interval: int = Field(default=60, description="最小下单间隔(秒)")


class RiskConfig(BaseModel):
    """风控配置"""
    max_daily_loss: float = Field(default=100.0, description="日最大亏损金额")
    max_daily_loss_pct: float = Field(default=5.0, description="日最大亏损百分比")
    max_drawdown: float = Field(default=10.0, description="最大回撤百分比")
    stop_loss_pct: float = Field(default=2.0, description="止损百分比")
    take_profit_pct: float = Field(default=5.0, description="止盈百分比")
    trailing_stop_pct: float = Field(default=1.0, description="跟踪止损百分比")
    max_consecutive_losses: int = Field(default=5, description="最大连续亏损次数")
    cooldown_period: int = Field(default=3600, description="熔断冷却期(秒)")
    position_limit: int = Field(default=3, description="最大同时持仓数量")


class AIConfig(BaseModel):
    """AI配置"""
    enabled: bool = Field(default=True, description="是否启用AI信号")
    model: str = Field(default="gpt-4.1-mini", description="使用的模型")
    temperature: float = Field(default=0.3, description="模型温度")
    max_tokens: int = Field(default=1000, description="最大token数")
    confidence_threshold: float = Field(default=0.6, description="信号置信度阈值")
    signal_ttl: int = Field(default=300, description="信号有效期(秒)")


class StrategyConfig(BaseModel):
    """策略配置"""
    name: str = Field(default="momentum", description="策略名称")
    enabled: bool = Field(default=True, description="是否启用")
    params: Dict[str, Any] = Field(default_factory=dict, description="策略参数")
    weight: float = Field(default=1.0, description="策略权重")


class Config(BaseModel):
    """主配置类"""
    env: Environment = Field(default=Environment.DEV, description="运行环境")
    debug: bool = Field(default=True, description="调试模式")
    
    # 交易所配置
    exchange: ExchangeConfig = Field(default_factory=lambda: ExchangeConfig(name="binance"))
    
    # 交易配置
    trading: TradingConfig = Field(default_factory=TradingConfig)
    
    # 风控配置
    risk: RiskConfig = Field(default_factory=RiskConfig)
    
    # AI配置
    ai: AIConfig = Field(default_factory=AIConfig)
    
    # 策略配置列表
    strategies: List[StrategyConfig] = Field(default_factory=list)
    
    # API服务配置
    api_host: str = Field(default="0.0.0.0", description="API服务地址")
    api_port: int = Field(default=8000, description="API服务端口")
    
    # WebSocket配置
    ws_enabled: bool = Field(default=True, description="是否启用WebSocket")
    
    @classmethod
    def load_from_file(cls, config_path: str) -> "Config":
        """从文件加载配置"""
        if not os.path.exists(config_path):
            return cls()
        
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        return cls(**data) if data else cls()
    
    @classmethod
    def load_from_env(cls) -> "Config":
        """从环境变量加载配置"""
        env = os.getenv("TRADING_ENV", "dev")
        config_path = f"config/{env}.yaml"
        return cls.load_from_file(config_path)
    
    def save_to_file(self, config_path: str):
        """保存配置到文件"""
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False, allow_unicode=True)


# 全局配置实例
_config: Optional[Config] = None


def get_config() -> Config:
    """获取全局配置"""
    global _config
    if _config is None:
        _config = Config.load_from_env()
    return _config


def set_config(config: Config):
    """设置全局配置"""
    global _config
    _config = config
