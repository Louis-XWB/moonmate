# Auto Trading Agent - Core Module
# Core module: configuration management, event bus, logging system

from .config import Config, TradingConfig, RiskConfig
from .events import EventBus, Event, EventType
from .logger import setup_logger, get_logger

__all__ = [
    'Config', 'TradingConfig', 'RiskConfig',
    'EventBus', 'Event', 'EventType',
    'setup_logger', 'get_logger'
]
