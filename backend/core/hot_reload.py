"""
配置热更新模块
支持运行时动态更新配置，无需重启服务
"""

import os
import yaml
import json
import asyncio
import hashlib
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from backend.core.logger import get_logger
from backend.core.events import EventBus, Event, EventType, get_event_bus

logger = get_logger("hot_reload")


@dataclass
class ConfigChange:
    """配置变更记录"""
    timestamp: datetime
    path: str
    old_value: Any
    new_value: Any
    source: str  # "file" or "api"


class ConfigValidator:
    """配置验证器"""
    
    @staticmethod
    def validate_risk_config(config: Dict[str, Any]) -> tuple[bool, str]:
        """验证风控配置"""
        errors = []
        
        # 验证止损比例
        max_loss_per_trade = config.get("max_loss_per_trade", 0)
        if not 0 < max_loss_per_trade <= 10:
            errors.append(f"max_loss_per_trade must be between 0 and 10, got {max_loss_per_trade}")
        
        # 验证日亏损限制
        max_daily_loss = config.get("max_daily_loss", 0)
        if not 0 < max_daily_loss <= 20:
            errors.append(f"max_daily_loss must be between 0 and 20, got {max_daily_loss}")
        
        # 验证仓位限制
        max_position_size = config.get("max_position_size", 0)
        if not 0 < max_position_size <= 100:
            errors.append(f"max_position_size must be between 0 and 100, got {max_position_size}")
        
        # 验证杠杆
        max_leverage = config.get("max_leverage", 1)
        if not 1 <= max_leverage <= 20:
            errors.append(f"max_leverage must be between 1 and 20, got {max_leverage}")
        
        if errors:
            return False, "; ".join(errors)
        return True, ""
    
    @staticmethod
    def validate_strategy_config(config: Dict[str, Any]) -> tuple[bool, str]:
        """验证策略配置"""
        errors = []
        
        # 验证信号阈值
        signal_threshold = config.get("signal_threshold", 0)
        if not 0 <= signal_threshold <= 1:
            errors.append(f"signal_threshold must be between 0 and 1, got {signal_threshold}")
        
        # 验证回看周期
        lookback_period = config.get("lookback_period", 0)
        if not 5 <= lookback_period <= 500:
            errors.append(f"lookback_period must be between 5 and 500, got {lookback_period}")
        
        if errors:
            return False, "; ".join(errors)
        return True, ""
    
    @staticmethod
    def validate_trading_config(config: Dict[str, Any]) -> tuple[bool, str]:
        """验证交易配置"""
        errors = []
        
        # 验证交易模式
        mode = config.get("mode", "")
        if mode not in ["paper", "live"]:
            errors.append(f"mode must be 'paper' or 'live', got {mode}")
        
        if errors:
            return False, "; ".join(errors)
        return True, ""


class ConfigFileWatcher(FileSystemEventHandler):
    """配置文件监视器"""
    
    def __init__(self, callback: Callable[[str], None]):
        self.callback = callback
        self._last_modified: Dict[str, float] = {}
        self._debounce_seconds = 1.0  # 防抖动
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        if not event.src_path.endswith(('.yaml', '.yml', '.json')):
            return
        
        # 防抖动
        now = datetime.now().timestamp()
        last = self._last_modified.get(event.src_path, 0)
        if now - last < self._debounce_seconds:
            return
        
        self._last_modified[event.src_path] = now
        
        logger.info(f"Config file modified: {event.src_path}")
        self.callback(event.src_path)


class HotReloadManager:
    """热更新管理器"""
    
    def __init__(
        self,
        config_dir: str = "config",
        auto_watch: bool = True
    ):
        self.config_dir = Path(config_dir)
        self.auto_watch = auto_watch
        self.event_bus = get_event_bus()
        
        # 当前配置
        self._config: Dict[str, Any] = {}
        self._config_hash: Dict[str, str] = {}
        
        # 变更历史
        self._change_history: List[ConfigChange] = []
        
        # 回调函数
        self._callbacks: Dict[str, List[Callable]] = {}
        
        # 验证器
        self._validators: Dict[str, Callable] = {
            "risk": ConfigValidator.validate_risk_config,
            "strategy": ConfigValidator.validate_strategy_config,
            "trading": ConfigValidator.validate_trading_config
        }
        
        # 文件监视器
        self._observer: Optional[Observer] = None
        
        if auto_watch:
            self._start_file_watcher()
    
    def _start_file_watcher(self):
        """启动文件监视器"""
        if not self.config_dir.exists():
            logger.warning(f"Config directory not found: {self.config_dir}")
            return
        
        self._observer = Observer()
        handler = ConfigFileWatcher(self._on_file_changed)
        self._observer.schedule(handler, str(self.config_dir), recursive=False)
        self._observer.start()
        logger.info(f"Started watching config directory: {self.config_dir}")
    
    def _stop_file_watcher(self):
        """停止文件监视器"""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
    
    def _calculate_hash(self, data: Any) -> str:
        """计算配置哈希"""
        content = json.dumps(data, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()
    
    def _on_file_changed(self, file_path: str):
        """文件变更回调"""
        asyncio.create_task(self.reload_from_file(file_path))
    
    async def load_config(self, file_path: str) -> Dict[str, Any]:
        """加载配置文件"""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {file_path}")
        
        with open(path, 'r') as f:
            if path.suffix in ['.yaml', '.yml']:
                config = yaml.safe_load(f)
            elif path.suffix == '.json':
                config = json.load(f)
            else:
                raise ValueError(f"Unsupported config format: {path.suffix}")
        
        return config or {}
    
    async def reload_from_file(self, file_path: str):
        """从文件重新加载配置"""
        try:
            new_config = await self.load_config(file_path)
            
            # 检测变更
            file_name = Path(file_path).stem
            old_config = self._config.get(file_name, {})
            
            # 计算哈希检查是否真的有变化
            new_hash = self._calculate_hash(new_config)
            old_hash = self._config_hash.get(file_name, "")
            
            if new_hash == old_hash:
                logger.debug(f"Config unchanged: {file_name}")
                return
            
            # 验证配置
            validator = self._validators.get(file_name)
            if validator:
                is_valid, error = validator(new_config)
                if not is_valid:
                    logger.error(f"Invalid config {file_name}: {error}")
                    await self.event_bus.publish(Event(
                        type=EventType.CONFIG_ERROR,
                        data={"file": file_name, "error": error}
                    ))
                    return
            
            # 记录变更
            changes = self._detect_changes(file_name, old_config, new_config)
            for change in changes:
                self._change_history.append(change)
                logger.info(f"Config changed: {change.path} = {change.new_value}")
            
            # 更新配置
            self._config[file_name] = new_config
            self._config_hash[file_name] = new_hash
            
            # 触发回调
            await self._trigger_callbacks(file_name, new_config, changes)
            
            # 发布事件
            await self.event_bus.publish(Event(
                type=EventType.CONFIG_UPDATED,
                data={
                    "file": file_name,
                    "changes": [
                        {"path": c.path, "old": c.old_value, "new": c.new_value}
                        for c in changes
                    ]
                }
            ))
            
            logger.info(f"Config reloaded: {file_name} ({len(changes)} changes)")
            
        except Exception as e:
            logger.error(f"Failed to reload config: {e}")
    
    def _detect_changes(
        self,
        section: str,
        old: Dict[str, Any],
        new: Dict[str, Any],
        prefix: str = ""
    ) -> List[ConfigChange]:
        """检测配置变更"""
        changes = []
        
        all_keys = set(old.keys()) | set(new.keys())
        
        for key in all_keys:
            path = f"{prefix}.{key}" if prefix else key
            old_value = old.get(key)
            new_value = new.get(key)
            
            if old_value != new_value:
                if isinstance(old_value, dict) and isinstance(new_value, dict):
                    # 递归检测嵌套变更
                    changes.extend(self._detect_changes(section, old_value, new_value, path))
                else:
                    changes.append(ConfigChange(
                        timestamp=datetime.now(),
                        path=f"{section}.{path}",
                        old_value=old_value,
                        new_value=new_value,
                        source="file"
                    ))
        
        return changes
    
    def register_callback(self, section: str, callback: Callable):
        """注册配置变更回调"""
        if section not in self._callbacks:
            self._callbacks[section] = []
        self._callbacks[section].append(callback)
        logger.info(f"Registered callback for config section: {section}")
    
    async def _trigger_callbacks(
        self,
        section: str,
        config: Dict[str, Any],
        changes: List[ConfigChange]
    ):
        """触发配置变更回调"""
        callbacks = self._callbacks.get(section, [])
        
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(config, changes)
                else:
                    callback(config, changes)
            except Exception as e:
                logger.error(f"Error in config callback: {e}")
    
    def get_config(self, section: str, key: str = None, default: Any = None) -> Any:
        """获取配置值"""
        config = self._config.get(section, {})
        
        if key is None:
            return config
        
        # 支持点号分隔的嵌套键
        keys = key.split('.')
        value = config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        
        return value if value is not None else default
    
    async def update_config(
        self,
        section: str,
        key: str,
        value: Any,
        persist: bool = True
    ) -> bool:
        """通过 API 更新配置"""
        try:
            # 获取当前配置
            config = self._config.get(section, {}).copy()
            
            # 更新值
            keys = key.split('.')
            target = config
            
            for k in keys[:-1]:
                if k not in target:
                    target[k] = {}
                target = target[k]
            
            old_value = target.get(keys[-1])
            target[keys[-1]] = value
            
            # 验证
            validator = self._validators.get(section)
            if validator:
                is_valid, error = validator(config)
                if not is_valid:
                    logger.error(f"Invalid config update: {error}")
                    return False
            
            # 记录变更
            change = ConfigChange(
                timestamp=datetime.now(),
                path=f"{section}.{key}",
                old_value=old_value,
                new_value=value,
                source="api"
            )
            self._change_history.append(change)
            
            # 更新内存配置
            self._config[section] = config
            self._config_hash[section] = self._calculate_hash(config)
            
            # 持久化到文件
            if persist:
                await self._persist_config(section, config)
            
            # 触发回调
            await self._trigger_callbacks(section, config, [change])
            
            logger.info(f"Config updated via API: {section}.{key} = {value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update config: {e}")
            return False
    
    async def _persist_config(self, section: str, config: Dict[str, Any]):
        """持久化配置到文件"""
        file_path = self.config_dir / f"{section}.yaml"
        
        with open(file_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        
        logger.info(f"Config persisted to: {file_path}")
    
    def get_change_history(
        self,
        section: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取变更历史"""
        history = self._change_history
        
        if section:
            history = [c for c in history if c.path.startswith(section)]
        
        # 按时间倒序
        history = sorted(history, key=lambda x: x.timestamp, reverse=True)
        
        return [
            {
                "timestamp": c.timestamp.isoformat(),
                "path": c.path,
                "old_value": c.old_value,
                "new_value": c.new_value,
                "source": c.source
            }
            for c in history[:limit]
        ]
    
    def rollback(self, change_index: int) -> bool:
        """回滚配置变更"""
        if change_index >= len(self._change_history):
            return False
        
        change = self._change_history[change_index]
        
        # 解析路径
        parts = change.path.split('.', 1)
        section = parts[0]
        key = parts[1] if len(parts) > 1 else None
        
        # 回滚
        asyncio.create_task(
            self.update_config(section, key, change.old_value, persist=True)
        )
        
        logger.info(f"Config rolled back: {change.path}")
        return True
    
    def __del__(self):
        """清理资源"""
        self._stop_file_watcher()


# 全局热更新管理器
_hot_reload_manager: Optional[HotReloadManager] = None


def get_hot_reload_manager() -> HotReloadManager:
    """获取全局热更新管理器"""
    global _hot_reload_manager
    if _hot_reload_manager is None:
        _hot_reload_manager = HotReloadManager()
    return _hot_reload_manager
