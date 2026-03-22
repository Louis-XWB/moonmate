"""
Decision Flow Matrix - Decision flow matrix configuration management

Users can customize the trading decision flow through a visual interface,
selecting which data sources, analysis modules, and strategy components to enable/disable.
Supports second-level sub-nodes for more granular control.
"""

import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel


class SubNodeConfig(BaseModel):
    """Sub-node configuration"""
    id: str
    name: str
    enabled: bool = True
    status: str = "idle"  # idle, running, success, error


class NodeConfig(BaseModel):
    """Node configuration"""
    enabled: bool = True
    status: str = "idle"  # idle, running, success, error
    last_updated: Optional[str] = None
    sub_nodes: Optional[List[SubNodeConfig]] = None  # Sub-node list


class DecisionFlowConfig(BaseModel):
    """Decision flow configuration"""
    master_switch: bool = False  # Master switch, disabled by default
    nodes: Dict[str, NodeConfig] = {}
    updated_at: Optional[str] = None


class DecisionFlowManager:
    """Decision flow manager"""

    def __init__(self, config_file: str = "data/decision_flow_config.json"):
        self.config_file = config_file
        self._ensure_config_file()
        self.config = self._load_config()

    def _ensure_config_file(self):
        """Ensure config file exists"""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        if not os.path.exists(self.config_file):
            # Create default configuration
            default_config = self._get_default_config()
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)

    def _get_default_config(self) -> dict:
        """Get default configuration"""
        return {
            "master_switch": False,
            "nodes": {
                # Data layer
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
                        {"id": "bollinger", "name": "Bollinger Bands", "enabled": True, "status": "idle"},
                        {"id": "ema", "name": "EMA", "enabled": True, "status": "idle"},
                        {"id": "volume", "name": "Volume", "enabled": True, "status": "idle"}
                    ]
                },

                # AI analysis layer
                "sentimentAnalysis": {
                    "enabled": True,
                    "status": "idle"
                },
                "multiAgent": {
                    "enabled": True,
                    "status": "idle",
                    "sub_nodes": [
                        {"id": "conservative", "name": "Conservative", "enabled": True, "status": "idle"},
                        {"id": "aggressive", "name": "Aggressive", "enabled": True, "status": "idle"},
                        {"id": "technical", "name": "Technical", "enabled": True, "status": "idle"},
                        {"id": "fundamental", "name": "Fundamental", "enabled": True, "status": "idle"},
                        {"id": "risk_manager", "name": "Risk Management", "enabled": True, "status": "idle"}
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

                # Rules layer
                "vibeRules": {
                    "enabled": True,
                    "status": "idle",
                    "sub_nodes": []  # Dynamically loaded user Vibe rules
                },

                # Risk control layer
                "riskControl": {
                    "enabled": True,
                    "status": "idle",
                    "sub_nodes": [
                        {"id": "position_limit", "name": "Position Limit", "enabled": True, "status": "idle"},
                        {"id": "stop_loss", "name": "Stop Loss", "enabled": True, "status": "idle"},
                        {"id": "take_profit", "name": "Take Profit", "enabled": True, "status": "idle"},
                        {"id": "circuit_breaker", "name": "Circuit Breaker", "enabled": True, "status": "idle"}
                    ]
                },

                # Execution layer
                "executeTrade": {
                    "enabled": True,
                    "status": "idle"
                }
            },
            "updated_at": datetime.now().isoformat()
        }

    def _load_config(self) -> DecisionFlowConfig:
        """Load configuration"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return DecisionFlowConfig(**data)
        except Exception as e:
            print(f"Failed to load configuration: {e}")
            return DecisionFlowConfig(**self._get_default_config())

    def _save_config(self):
        """Save configuration"""
        try:
            self.config.updated_at = datetime.now().isoformat()
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config.dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save configuration: {e}")

    def get_config(self) -> dict:
        """Get current configuration"""
        return self.config.dict()

    def update_config(self, master_switch: Optional[bool] = None,
                     nodes: Optional[Dict[str, dict]] = None) -> dict:
        """Update configuration"""
        if master_switch is not None:
            self.config.master_switch = master_switch

        if nodes is not None:
            for node_id, node_data in nodes.items():
                if node_id in self.config.nodes:
                    # Update existing node
                    if 'enabled' in node_data:
                        self.config.nodes[node_id].enabled = node_data['enabled']
                    if 'status' in node_data:
                        self.config.nodes[node_id].status = node_data['status']
                    self.config.nodes[node_id].last_updated = datetime.now().isoformat()
                else:
                    # Add new node
                    self.config.nodes[node_id] = NodeConfig(**node_data)

        self._save_config()
        return self.config.dict()

    def toggle_node(self, node_id: str) -> dict:
        """Toggle node enabled state"""
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
                "message": f"Node {node_id} does not exist"
            }

    def toggle_sub_node(self, node_id: str, sub_node_id: str) -> dict:
        """Toggle sub-node enabled state"""
        if node_id not in self.config.nodes:
            return {
                "success": False,
                "message": f"Node {node_id} does not exist"
            }

        node = self.config.nodes[node_id]
        if not node.sub_nodes:
            return {
                "success": False,
                "message": f"Node {node_id} has no sub-nodes"
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
            "message": f"Sub-node {sub_node_id} does not exist"
        }

    def load_vibe_rules(self, vibe_rules: List[dict]):
        """Load Vibe rules as sub-nodes"""
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
        """Reset to default configuration"""
        default_config = self._get_default_config()
        self.config = DecisionFlowConfig(**default_config)
        self._save_config()
        return self.config.dict()

    def is_node_enabled(self, node_id: str) -> bool:
        """Check if node is enabled"""
        if not self.config.master_switch:
            # When master switch is off, all nodes are considered enabled (use default flow)
            return True

        if node_id in self.config.nodes:
            return self.config.nodes[node_id].enabled
        return True  # Unconfigured nodes are enabled by default

    def is_sub_node_enabled(self, node_id: str, sub_node_id: str) -> bool:
        """Check if sub-node is enabled"""
        if not self.config.master_switch:
            return True

        if node_id not in self.config.nodes:
            return True

        node = self.config.nodes[node_id]
        if not node.enabled:
            # When parent node is disabled, all sub-nodes are considered disabled
            return False

        if not node.sub_nodes:
            return True

        for sub_node in node.sub_nodes:
            if sub_node.id == sub_node_id:
                return sub_node.enabled

        return True

    def get_enabled_nodes(self) -> list:
        """Get all enabled nodes"""
        if not self.config.master_switch:
            # When master switch is off, return all nodes
            return list(self.config.nodes.keys())

        return [
            node_id for node_id, node_config in self.config.nodes.items()
            if node_config.enabled
        ]

    def update_node_status(self, node_id: str, status: str):
        """Update node status (for real-time feedback)"""
        if node_id in self.config.nodes:
            self.config.nodes[node_id].status = status
            self.config.nodes[node_id].last_updated = datetime.now().isoformat()
            # Note: this does not save to file, only updates in-memory state


# Global singleton
_decision_flow_manager = None

def get_decision_flow_manager() -> DecisionFlowManager:
    """Get decision flow manager singleton"""
    global _decision_flow_manager
    if _decision_flow_manager is None:
        _decision_flow_manager = DecisionFlowManager()
    return _decision_flow_manager
