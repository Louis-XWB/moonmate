"""
Decision Flow Matrix - 决策流矩阵配置管理

用户可以通过可视化界面自定义交易决策流程，
选择启用/禁用不同的数据源、分析模块和策略组件。
支持二级子节点，提供更细粒度的控制。
"""

import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel


class SubNodeConfig(BaseModel):
    """子节点配置"""
    id: str
    name: str
    enabled: bool = True
    status: str = "idle"  # idle, running, success, error


class NodeConfig(BaseModel):
    """节点配置"""
    enabled: bool = True
    status: str = "idle"  # idle, running, success, error
    last_updated: Optional[str] = None
    sub_nodes: Optional[List[SubNodeConfig]] = None  # 子节点列表


class DecisionFlowConfig(BaseModel):
    """决策流配置"""
    master_switch: bool = False  # 总开关，默认关闭
    nodes: Dict[str, NodeConfig] = {}
    updated_at: Optional[str] = None


class DecisionFlowManager:
    """决策流管理器"""
    
    def __init__(self, config_file: str = "data/decision_flow_config.json"):
        self.config_file = config_file
        self._ensure_config_file()
        self.config = self._load_config()
    
    def _ensure_config_file(self):
        """确保配置文件存在"""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        if not os.path.exists(self.config_file):
            # 创建默认配置
            default_config = self._get_default_config()
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
    
    def _get_default_config(self) -> dict:
        """获取默认配置"""
        return {
            "master_switch": False,
            "nodes": {
                # 数据层
                "marketData": {
                    "enabled": True, 
                    "status": "idle",
                    "sub_nodes": [
                        {"id": "binance", "name": "Binance", "enabled": True, "status": "idle"},
                        {"id": "okx", "name": "OKX", "enabled": True, "status": "idle"},
                        {"id": "coinbase", "name": "Coinbase", "enabled": True, "status": "idle"}
                    ]
                },
                "newsData": {
                    "enabled": True, 
                    "status": "idle",
                    "sub_nodes": [
                        {"id": "coindesk", "name": "CoinDesk", "enabled": True, "status": "idle"},
                        {"id": "cointelegraph", "name": "Cointelegraph", "enabled": True, "status": "idle"},
                        {"id": "theblock", "name": "The Block", "enabled": True, "status": "idle"}
                    ]
                },
                "socialMedia": {
                    "enabled": True, 
                    "status": "idle",
                    "sub_nodes": [
                        {"id": "twitter", "name": "Twitter(X)", "enabled": True, "status": "idle"},
                        {"id": "reddit", "name": "Reddit", "enabled": True, "status": "idle"},
                        {"id": "telegram", "name": "Telegram", "enabled": True, "status": "idle"}
                    ]
                },
                "onchainData": {
                    "enabled": True, 
                    "status": "idle",
                    "sub_nodes": [
                        {"id": "etherscan", "name": "Etherscan", "enabled": True, "status": "idle"},
                        {"id": "bscscan", "name": "BSCScan", "enabled": True, "status": "idle"},
                        {"id": "whale_alert", "name": "Whale Alert", "enabled": True, "status": "idle"}
                    ]
                },
                "technicalIndicators": {
                    "enabled": True, 
                    "status": "idle",
                    "sub_nodes": [
                        {"id": "rsi", "name": "RSI", "enabled": True, "status": "idle"},
                        {"id": "macd", "name": "MACD", "enabled": True, "status": "idle"},
                        {"id": "bollinger", "name": "布林带", "enabled": True, "status": "idle"},
                        {"id": "ema", "name": "EMA", "enabled": True, "status": "idle"},
                        {"id": "volume", "name": "成交量", "enabled": True, "status": "idle"}
                    ]
                },
                
                # AI分析层
                "sentimentAnalysis": {
                    "enabled": True, 
                    "status": "idle"
                },
                "multiAgent": {
                    "enabled": True, 
                    "status": "idle",
                    "sub_nodes": [
                        {"id": "conservative", "name": "保守派", "enabled": True, "status": "idle"},
                        {"id": "aggressive", "name": "激进派", "enabled": True, "status": "idle"},
                        {"id": "technical", "name": "技术派", "enabled": True, "status": "idle"},
                        {"id": "fundamental", "name": "基本面派", "enabled": True, "status": "idle"},
                        {"id": "risk_manager", "name": "风险管理", "enabled": True, "status": "idle"}
                    ]
                },
                "newsAnalysis": {
                    "enabled": True, 
                    "status": "idle"
                },
                "whaleTracking": {
                    "enabled": True, 
                    "status": "idle"
                },
                
                # 规则层
                "vibeRules": {
                    "enabled": True, 
                    "status": "idle",
                    "sub_nodes": []  # 动态加载用户的Vibe规则
                },
                
                # 风控层
                "riskControl": {
                    "enabled": True, 
                    "status": "idle",
                    "sub_nodes": [
                        {"id": "position_limit", "name": "仓位限制", "enabled": True, "status": "idle"},
                        {"id": "stop_loss", "name": "止损", "enabled": True, "status": "idle"},
                        {"id": "take_profit", "name": "止盈", "enabled": True, "status": "idle"},
                        {"id": "circuit_breaker", "name": "熔断", "enabled": True, "status": "idle"}
                    ]
                },
                
                # 执行层
                "executeTrade": {
                    "enabled": True, 
                    "status": "idle"
                }
            },
            "updated_at": datetime.now().isoformat()
        }
    
    def _load_config(self) -> DecisionFlowConfig:
        """加载配置"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return DecisionFlowConfig(**data)
        except Exception as e:
            print(f"加载配置失败: {e}")
            return DecisionFlowConfig(**self._get_default_config())
    
    def _save_config(self):
        """保存配置"""
        try:
            self.config.updated_at = datetime.now().isoformat()
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config.dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置失败: {e}")
    
    def get_config(self) -> dict:
        """获取当前配置"""
        return self.config.dict()
    
    def update_config(self, master_switch: Optional[bool] = None, 
                     nodes: Optional[Dict[str, dict]] = None) -> dict:
        """更新配置"""
        if master_switch is not None:
            self.config.master_switch = master_switch
        
        if nodes is not None:
            for node_id, node_data in nodes.items():
                if node_id in self.config.nodes:
                    # 更新现有节点
                    if 'enabled' in node_data:
                        self.config.nodes[node_id].enabled = node_data['enabled']
                    if 'status' in node_data:
                        self.config.nodes[node_id].status = node_data['status']
                    self.config.nodes[node_id].last_updated = datetime.now().isoformat()
                else:
                    # 添加新节点
                    self.config.nodes[node_id] = NodeConfig(**node_data)
        
        self._save_config()
        return self.config.dict()
    
    def toggle_node(self, node_id: str) -> dict:
        """切换节点启用状态"""
        if node_id in self.config.nodes:
            self.config.nodes[node_id].enabled = not self.config.nodes[node_id].enabled
            self.config.nodes[node_id].last_updated = datetime.now().isoformat()
            self._save_config()
            return {
                "success": True,
                "node_id": node_id,
                "enabled": self.config.nodes[node_id].enabled
            }
        else:
            return {
                "success": False,
                "message": f"节点 {node_id} 不存在"
            }
    
    def toggle_sub_node(self, node_id: str, sub_node_id: str) -> dict:
        """切换子节点启用状态"""
        if node_id not in self.config.nodes:
            return {
                "success": False,
                "message": f"节点 {node_id} 不存在"
            }
        
        node = self.config.nodes[node_id]
        if not node.sub_nodes:
            return {
                "success": False,
                "message": f"节点 {node_id} 没有子节点"
            }
        
        for sub_node in node.sub_nodes:
            if sub_node.id == sub_node_id:
                sub_node.enabled = not sub_node.enabled
                node.last_updated = datetime.now().isoformat()
                self._save_config()
                return {
                    "success": True,
                    "node_id": node_id,
                    "sub_node_id": sub_node_id,
                    "enabled": sub_node.enabled
                }
        
        return {
            "success": False,
            "message": f"子节点 {sub_node_id} 不存在"
        }
    
    def load_vibe_rules(self, vibe_rules: List[dict]):
        """加载Vibe规则作为子节点"""
        if "vibeRules" in self.config.nodes:
            sub_nodes = []
            for rule in vibe_rules:
                sub_nodes.append(SubNodeConfig(
                    id=f"vibe_{rule['id']}",
                    name=rule['content'][:30] + "..." if len(rule['content']) > 30 else rule['content'],
                    enabled=rule.get('enabled', True),
                    status="idle"
                ))
            self.config.nodes["vibeRules"].sub_nodes = sub_nodes
            self._save_config()
    
    def reset_to_default(self) -> dict:
        """重置为默认配置"""
        default_config = self._get_default_config()
        self.config = DecisionFlowConfig(**default_config)
        self._save_config()
        return self.config.dict()
    
    def is_node_enabled(self, node_id: str) -> bool:
        """检查节点是否启用"""
        if not self.config.master_switch:
            # 总开关关闭时，所有节点都视为启用（使用默认流程）
            return True
        
        if node_id in self.config.nodes:
            return self.config.nodes[node_id].enabled
        return True  # 未配置的节点默认启用
    
    def is_sub_node_enabled(self, node_id: str, sub_node_id: str) -> bool:
        """检查子节点是否启用"""
        if not self.config.master_switch:
            return True
        
        if node_id not in self.config.nodes:
            return True
        
        node = self.config.nodes[node_id]
        if not node.enabled:
            # 父节点禁用时，所有子节点都视为禁用
            return False
        
        if not node.sub_nodes:
            return True
        
        for sub_node in node.sub_nodes:
            if sub_node.id == sub_node_id:
                return sub_node.enabled
        
        return True
    
    def get_enabled_nodes(self) -> list:
        """获取所有启用的节点"""
        if not self.config.master_switch:
            # 总开关关闭时，返回所有节点
            return list(self.config.nodes.keys())
        
        return [
            node_id for node_id, node_config in self.config.nodes.items()
            if node_config.enabled
        ]
    
    def update_node_status(self, node_id: str, status: str):
        """更新节点状态（用于实时反馈）"""
        if node_id in self.config.nodes:
            self.config.nodes[node_id].status = status
            self.config.nodes[node_id].last_updated = datetime.now().isoformat()
            # 注意：这里不保存到文件，只更新内存状态


# 全局单例
_decision_flow_manager = None

def get_decision_flow_manager() -> DecisionFlowManager:
    """获取决策流管理器单例"""
    global _decision_flow_manager
    if _decision_flow_manager is None:
        _decision_flow_manager = DecisionFlowManager()
    return _decision_flow_manager
