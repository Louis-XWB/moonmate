"""
Vibe策略管理模块
允许用户自定义策略偏好，AI会将这些偏好纳入交易决策考量
"""

import json
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class VibeRule:
    """单条Vibe策略规则"""
    id: str
    content: str  # 策略内容，如"我偏好做多，不喜欢做空"
    created_at: str
    updated_at: str
    enabled: bool = True  # 是否启用
    
    def to_dict(self) -> Dict:
        return asdict(self)


class VibeStrategyManager:
    """Vibe策略管理器"""
    
    def __init__(self, storage_path: str = "/home/ubuntu/auto-trading-agent/data/vibe_rules.json"):
        """
        初始化Vibe策略管理器
        
        Args:
            storage_path: 策略规则存储路径
        """
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.rules: List[VibeRule] = []
        self._load_rules()
    
    def _load_rules(self):
        """从文件加载规则"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.rules = [VibeRule(**rule) for rule in data]
            except Exception as e:
                print(f"加载Vibe规则失败: {e}")
                self.rules = []
        else:
            self.rules = []
    
    def _save_rules(self):
        """保存规则到文件"""
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump([rule.to_dict() for rule in self.rules], f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存Vibe规则失败: {e}")
    
    def add_rule(self, content: str) -> VibeRule:
        """
        添加新规则
        
        Args:
            content: 规则内容
            
        Returns:
            新创建的规则
        """
        now = datetime.now().isoformat()
        rule_id = f"vibe_{len(self.rules) + 1}_{int(datetime.now().timestamp())}"
        
        rule = VibeRule(
            id=rule_id,
            content=content,
            created_at=now,
            updated_at=now,
            enabled=True
        )
        
        self.rules.append(rule)
        self._save_rules()
        return rule
    
    def update_rule(self, rule_id: str, content: Optional[str] = None, enabled: Optional[bool] = None) -> Optional[VibeRule]:
        """
        更新规则
        
        Args:
            rule_id: 规则ID
            content: 新的规则内容（可选）
            enabled: 是否启用（可选）
            
        Returns:
            更新后的规则，如果规则不存在则返回None
        """
        for rule in self.rules:
            if rule.id == rule_id:
                if content is not None:
                    rule.content = content
                if enabled is not None:
                    rule.enabled = enabled
                rule.updated_at = datetime.now().isoformat()
                self._save_rules()
                return rule
        return None
    
    def delete_rule(self, rule_id: str) -> bool:
        """
        删除规则
        
        Args:
            rule_id: 规则ID
            
        Returns:
            是否删除成功
        """
        for i, rule in enumerate(self.rules):
            if rule.id == rule_id:
                self.rules.pop(i)
                self._save_rules()
                return True
        return False
    
    def get_rule(self, rule_id: str) -> Optional[VibeRule]:
        """
        获取单条规则
        
        Args:
            rule_id: 规则ID
            
        Returns:
            规则对象，如果不存在则返回None
        """
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        return None
    
    def get_all_rules(self, enabled_only: bool = False) -> List[VibeRule]:
        """
        获取所有规则
        
        Args:
            enabled_only: 是否只返回启用的规则
            
        Returns:
            规则列表
        """
        if enabled_only:
            return [rule for rule in self.rules if rule.enabled]
        return self.rules
    
    def get_rules_as_prompt(self) -> str:
        """
        将启用的规则转换为Prompt格式，用于传递给AI
        
        Returns:
            格式化的规则文本
        """
        enabled_rules = self.get_all_rules(enabled_only=True)
        
        if not enabled_rules:
            return ""
        
        prompt = "用户的策略偏好（Vibe）：\n"
        for i, rule in enumerate(enabled_rules, 1):
            prompt += f"{i}. {rule.content}\n"
        
        prompt += "\n请在生成交易信号时考虑这些用户偏好。"
        return prompt
    
    def clear_all_rules(self):
        """清空所有规则"""
        self.rules = []
        self._save_rules()


# 全局单例
_vibe_manager: Optional[VibeStrategyManager] = None


def get_vibe_manager() -> VibeStrategyManager:
    """获取全局Vibe策略管理器"""
    global _vibe_manager
    if _vibe_manager is None:
        _vibe_manager = VibeStrategyManager()
    return _vibe_manager
