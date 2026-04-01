"""
Vibe strategy management module
Allows users to customize strategy preferences; AI incorporates these into trading decisions
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class VibeRule:
    """Single Vibe strategy rule"""
    id: str
    content: str  # Strategy content, e.g. "I prefer going long, avoid shorting"
    created_at: str
    updated_at: str
    enabled: bool = True  # Whether enabled

    def to_dict(self) -> Dict:
        return asdict(self)


class VibeStrategyManager:
    """Vibe strategy manager"""

    def __init__(self, storage_path: str = None):
        """
        Initialize the Vibe strategy manager

        Args:
            storage_path: Strategy rule storage path (defaults to data/vibe_rules.json in project root)
        """
        if storage_path is None:
            # Default to data/vibe_rules.json in the project root
            base_dir = Path(__file__).parent.parent.parent
            storage_path = base_dir / "data" / "vibe_rules.json"
        """
        Initialize the Vibe strategy manager

        Args:
            storage_path: Strategy rule storage path
        """
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.rules: List[VibeRule] = []
        self._load_rules()

    def _load_rules(self):
        """Load rules from file"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.rules = [VibeRule(**rule) for rule in data]
            except Exception as e:
                print(f"Failed to load Vibe rules: {e}")
                self.rules = []
        else:
            self.rules = []

    def _save_rules(self):
        """Save rules to file"""
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump([rule.to_dict() for rule in self.rules], f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save Vibe rules: {e}")

    def add_rule(self, content: str) -> VibeRule:
        """
        Add a new rule

        Args:
            content: Rule content

        Returns:
            Newly created rule
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
        Update a rule

        Args:
            rule_id: Rule ID
            content: New rule content (optional)
            enabled: Whether enabled (optional)

        Returns:
            Updated rule, or None if the rule was not found
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
        Delete a rule

        Args:
            rule_id: Rule ID

        Returns:
            Whether deletion was successful
        """
        for i, rule in enumerate(self.rules):
            if rule.id == rule_id:
                self.rules.pop(i)
                self._save_rules()
                return True
        return False

    def get_rule(self, rule_id: str) -> Optional[VibeRule]:
        """
        Get a single rule

        Args:
            rule_id: Rule ID

        Returns:
            Rule object, or None if not found
        """
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        return None

    def get_all_rules(self, enabled_only: bool = False) -> List[VibeRule]:
        """
        Get all rules

        Args:
            enabled_only: Whether to return only enabled rules

        Returns:
            List of rules
        """
        if enabled_only:
            return [rule for rule in self.rules if rule.enabled]
        return self.rules

    def get_rules_as_prompt(self) -> str:
        """
        Convert enabled rules to prompt format for passing to AI

        Returns:
            Formatted rule text
        """
        enabled_rules = self.get_all_rules(enabled_only=True)

        if not enabled_rules:
            return ""

        prompt = "User's strategy preferences (Vibe):\n"
        for i, rule in enumerate(enabled_rules, 1):
            prompt += f"{i}. {rule.content}\n"

        prompt += "\nPlease consider these user preferences when generating trading signals."
        return prompt

    def clear_all_rules(self):
        """Clear all rules"""
        self.rules = []
        self._save_rules()


# Global singleton
_vibe_manager: Optional[VibeStrategyManager] = None


def get_vibe_manager() -> VibeStrategyManager:
    """Get global Vibe strategy manager"""
    global _vibe_manager
    if _vibe_manager is None:
        _vibe_manager = VibeStrategyManager()
    return _vibe_manager
