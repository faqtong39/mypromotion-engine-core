"""
促销规则互斥检查器（去 Django 化版本）

提供清晰、灵活的互斥检查机制，纯内存计算。
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class MutexCheckResult(Enum):
    """互斥检查结果"""
    ALLOWED = "allowed"
    MUTEX_BY_GROUP = "mutex_group"
    MUTEX_BY_SPECIAL = "mutex_special"
    STACKABLE = "stackable"
    REPLACE = "replace"


@dataclass
class MutexCheckInfo:
    """互斥检查详细信息"""
    result: MutexCheckResult
    message: str = ""
    mutex_group: Optional[str] = None
    mutex_rule_id: Optional[str] = None
    skipped_by: Optional[str] = None
    replace_target: Optional[Any] = None


class MutexConfigLoader:
    """互斥配置加载器（纯内存版本）"""

    def __init__(self, mutex_groups: Optional[Dict[str, Dict]] = None):
        self.mutex_groups = mutex_groups or {}

    def load_mutex_groups(self) -> Dict[str, Dict]:
        return self.mutex_groups

    def load_stackable_strategies(self) -> List[str]:
        return []


class MutexChecker:
    """互斥检查器（纯内存版本，无数据库依赖）"""

    def __init__(
        self,
        mutex_groups: Optional[Dict[str, Dict]] = None,
        special_mutex_rules: Optional[List] = None,
    ):
        self.config_loader = MutexConfigLoader(mutex_groups)
        self.mutex_groups = self.config_loader.load_mutex_groups()
        self.stackable_strategies = self.config_loader.load_stackable_strategies()
        self.used_groups: Set[str] = set()
        self.applied_rule_ids: List[str] = []
        self.special_mutex_rules = special_mutex_rules or []

    def reset(self) -> None:
        """重置检查器状态（用于重新计算）"""
        self.used_groups.clear()
        self.applied_rule_ids.clear()

    def check_mutex(self, rule, applied_rules: Optional[List] = None) -> MutexCheckInfo:
        """
        检查规则是否互斥

        检查优先级：
        1. 特殊互斥规则（最高优先级）
        2. 规则的叠加配置 (stack_config)
        3. 策略类型互斥组
        4. 可叠加策略默认
        """
        applied_rules = applied_rules or []
        strategy_type = getattr(rule, "strategy_type", None)
        rule_id = getattr(rule, "promotion_code", None)
        rule_code = rule_id or "Unknown"
        stack_config = getattr(rule, "stack_config", {}) or {}

        # 1. 检查特殊互斥规则
        special_check = self._check_special_mutex(rule_id, applied_rules)
        if special_check:
            if special_check.get("should_replace") and applied_rules:
                target_rule = special_check.get("target_rule")
                if target_rule:
                    return MutexCheckInfo(
                        result=MutexCheckResult.REPLACE,
                        message=f"规则 {rule_code} 优先级高于 {special_check['other_code']}，将替换该规则",
                        mutex_rule_id=special_check.get("rule_id"),
                        replace_target=target_rule,
                    )
            return MutexCheckInfo(
                result=MutexCheckResult.MUTEX_BY_SPECIAL,
                message=f"规则 {rule_code} 与规则 {special_check['other_code']} 存在特殊互斥关系",
                mutex_rule_id=special_check.get("rule_id"),
                skipped_by=f"规则:{special_check['other_code']}",
            )

        # 2. 检查强制叠加
        if stack_config.get("force_stackable", False):
            return MutexCheckInfo(
                result=MutexCheckResult.STACKABLE,
                message=f"规则 {rule_code} 设置了强制叠加(force_stackable)",
            )

        # 3. 检查 stack_config 白名单/黑名单
        if applied_rules:
            stack_check = self._check_stack_config(rule, stack_config, applied_rules)
            if stack_check:
                return stack_check

        # 4. 检查策略类型互斥组
        if not stack_config.get("ignore_mutex_groups", False):
            group_check = self._check_group_mutex(strategy_type, rule_id)
            if group_check:
                group_name = self.mutex_groups.get(group_check, {}).get("name", group_check)
                return MutexCheckInfo(
                    result=MutexCheckResult.MUTEX_BY_GROUP,
                    message=f"规则 {rule_code} 与互斥组 {group_name} 中的已应用规则互斥",
                    mutex_group=group_check,
                    skipped_by=f"组:{group_check}",
                )

        # 5. 检查可叠加策略默认
        if strategy_type in self.stackable_strategies:
            return MutexCheckInfo(
                result=MutexCheckResult.STACKABLE,
                message=f"策略 {strategy_type} 是可叠加策略，不参与互斥检查",
            )

        return MutexCheckInfo(
            result=MutexCheckResult.ALLOWED,
            message=f"规则 {rule_code} 允许应用",
        )

    def _check_group_mutex(self, strategy_type: Optional[str] = None, rule_id: Optional[str] = None) -> Optional[str]:
        """检查策略类型或规则名称是否在已使用的互斥组中"""
        if not strategy_type and not rule_id:
            return None
        for group_code, group_config in self.mutex_groups.items():
            strategies = group_config.get("strategies", [])
            rule_ids = group_config.get("rule_ids", [])
            matched = False
            if strategy_type and strategy_type in strategies:
                matched = True
            if rule_id and rule_id in rule_ids:
                matched = True
            if matched and group_code in self.used_groups:
                return group_code
        return None

    def _check_stack_config(
        self, rule, stack_config: Dict, applied_rules: List
    ) -> Optional[MutexCheckInfo]:
        """检查规则的叠加配置（stack_config）"""
        rule_code = getattr(rule, "promotion_code", "Unknown")

        if stack_config.get("force_stackable", False):
            return MutexCheckInfo(
                result=MutexCheckResult.STACKABLE,
                message=f"规则 {rule_code} 设置了强制叠加",
            )

        applied_codes = set()
        applied_mutex_targets = set()
        for r in applied_rules:
            code = getattr(r, "promotion_code", None)
            if code:
                applied_codes.add(code)
                r_stack = getattr(r, "stack_config", {}) or {}
                r_mutex_with = r_stack.get("mutex_with", [])
                if r_mutex_with:
                    applied_mutex_targets.update(r_mutex_with)

        # 白名单检查
        stackable_with = stack_config.get("stackable_with", [])
        if stackable_with and applied_codes:
            intersect = set(stackable_with) & applied_codes
            if intersect:
                return MutexCheckInfo(
                    result=MutexCheckResult.STACKABLE,
                    message=f"规则 {rule_code} 与规则 {', '.join(intersect)} 在白名单中，允许叠加",
                )

        # 黑名单正向检查
        mutex_with = stack_config.get("mutex_with", [])
        if mutex_with and applied_codes:
            intersect = set(mutex_with) & applied_codes
            if intersect:
                return MutexCheckInfo(
                    result=MutexCheckResult.MUTEX_BY_GROUP,
                    message=f"规则 {rule_code} 与规则 {', '.join(intersect)} 互斥（互斥黑名单）",
                    skipped_by=f"互斥黑名单:{', '.join(intersect)}",
                )

        # 黑名单反向检查
        if rule_code in applied_mutex_targets:
            for r in applied_rules:
                r_stack = getattr(r, "stack_config", {}) or {}
                r_mutex_with = r_stack.get("mutex_with", [])
                if rule_code in r_mutex_with:
                    applied_code = getattr(r, "promotion_code", "Unknown")
                    return MutexCheckInfo(
                        result=MutexCheckResult.MUTEX_BY_GROUP,
                        message=f"规则 {rule_code} 被规则 {applied_code} 的互斥配置阻止",
                        skipped_by=f"互斥黑名单:{applied_code}",
                    )

        return None

    def _check_special_mutex(self, rule_id: Optional[str], applied_rules: Optional[List]) -> Optional[Dict]:
        """检查特殊互斥规则"""
        if not rule_id or not applied_rules:
            return None

        applied_ids = set(self.applied_rule_ids)
        applied_rule_map = {}
        for r in applied_rules:
            rid = getattr(r, "promotion_code", None)
            if rid:
                applied_rule_map[rid] = r

        now = datetime.now()

        for mutex_rule in self.special_mutex_rules:
            if not getattr(mutex_rule, "is_active", True):
                continue
            valid_from = getattr(mutex_rule, "valid_from", None)
            valid_to = getattr(mutex_rule, "valid_to", None)
            if valid_from and now < valid_from:
                continue
            if valid_to and now > valid_to:
                continue

            rule_a_id = getattr(mutex_rule, "rule_a_id", "")
            rule_b_id = getattr(mutex_rule, "rule_b_id", "")

            is_current_a = (rule_a_id == rule_id)
            is_current_b = (rule_b_id == rule_id)

            if not is_current_a and not is_current_b:
                continue

            other_id = rule_b_id if is_current_a else rule_a_id
            other_code = other_id

            if other_id not in applied_ids:
                continue

            if getattr(mutex_rule, "is_bidirectional", True):
                return {"rule_id": id(mutex_rule), "other_code": other_code, "should_replace": False}

            priority_direction = getattr(mutex_rule, "priority_direction", "a")
            if priority_direction == "a":
                if is_current_a:
                    return {
                        "rule_id": id(mutex_rule),
                        "other_code": other_code,
                        "should_replace": True,
                        "target_rule": applied_rule_map.get(other_id),
                    }
                else:
                    return {"rule_id": id(mutex_rule), "other_code": other_code, "should_replace": False}
            else:
                if is_current_b:
                    return {
                        "rule_id": id(mutex_rule),
                        "other_code": other_code,
                        "should_replace": True,
                        "target_rule": applied_rule_map.get(other_id),
                    }
                else:
                    return {"rule_id": id(mutex_rule), "other_code": other_code, "should_replace": False}

        return None

    def mark_applied(self, rule) -> None:
        """标记规则为已应用"""
        rule_id = getattr(rule, "promotion_code", None)
        strategy_type = getattr(rule, "strategy_type", None)

        if rule_id:
            self.applied_rule_ids.append(rule_id)

        for group_code, group_config in self.mutex_groups.items():
            strategies = group_config.get("strategies", [])
            rule_ids = group_config.get("rule_ids", [])
            matched = False
            if strategy_type and strategy_type in strategies:
                matched = True
            if rule_id and rule_id in rule_ids:
                matched = True
            if matched:
                self.used_groups.add(group_code)

    def get_applied_summary(self) -> Dict[str, Any]:
        """获取已应用规则的汇总信息"""
        return {
            "applied_rule_ids": self.applied_rule_ids,
            "used_mutex_groups": list(self.used_groups),
            "mutex_groups_detail": {
                code: self.mutex_groups.get(code, {}) for code in self.used_groups
            },
        }
