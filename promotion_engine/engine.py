"""
促销规则计算引擎（去 Django 化版本）

核心计算流程：
1. 按优先级排序所有规则
2. 对每个规则进行互斥检查
3. 检查规则条件是否满足
4. 计算优惠金额
5. 汇总结果
"""
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from itertools import groupby
from typing import Any, Dict, List, Optional, Tuple, Union

from .coupon_calculation import CouponUsageCalculator
from .mutex import MutexCheckResult, MutexChecker
from .plugins.base import PluginManager
from .types import (
    CalculationContext,
    CalculationResult,
    CartItem,
    PromotionResult,
    Rule,
)


class RuleConditionChecker:
    """规则条件检查器（插件化版本）"""

    def __init__(self, plugin_manager: Optional[PluginManager] = None):
        if plugin_manager is None:
            plugin_manager = PluginManager()
        self.plugin_manager = plugin_manager

    def check_all(self, conditions, context: CalculationContext, items: List[CartItem]) -> Tuple[bool, list]:
        if not conditions:
            return True, []

        logic_operator = getattr(conditions[0], "logic_operator", "AND")
        failed_conditions = []
        passed_count = 0

        for condition in conditions:
            result = self.check_single_with_detail(condition, context, items)
            if result.success:
                passed_count += 1
            else:
                failed_conditions.append({
                    "type": condition.condition_type,
                    "message": result.message or f"{condition.condition_type} 条件不满足",
                })

        if logic_operator == "OR":
            all_passed = passed_count > 0
            return all_passed, failed_conditions if not all_passed else []

        return len(failed_conditions) == 0, failed_conditions

    def check_single_with_detail(self, condition, context: CalculationContext, items: List[CartItem]):
        condition_type = condition.condition_type
        config = condition.config

        if not self.plugin_manager.has_condition_plugin(condition_type):
            from .plugins.base import PluginResult
            return PluginResult(
                success=False,
                message=f"未找到条件插件: {condition_type}",
            )

        return self.plugin_manager.check_condition_with_result(condition_type, config, context, items)


class ScopeFilter:
    """范围过滤器（插件化版本）"""

    def __init__(self, plugin_manager: Optional[PluginManager] = None):
        if plugin_manager is None:
            plugin_manager = PluginManager()
        self.plugin_manager = plugin_manager

    def filter_items(self, scope, items: List[CartItem]) -> List[CartItem]:
        scope_type = scope.scope_type
        config = scope.config

        if not self.plugin_manager.has_scope_plugin(scope_type):
            return items

        return self.plugin_manager.filter_scope(scope_type, config, items)


class DiscountCalculator:
    """优惠计算器（插件化版本）"""

    def __init__(self, plugin_manager: Optional[PluginManager] = None):
        if plugin_manager is None:
            plugin_manager = PluginManager()
        self.plugin_manager = plugin_manager

    def calculate(
        self, action, items: List[CartItem], context: CalculationContext
    ) -> Tuple[Decimal, List[Dict], str]:
        action_type = action.action_type
        config = action.config
        max_discount = getattr(action, "max_discount", None)

        if not self.plugin_manager.has_action_plugin(action_type):
            return Decimal("0"), [], f"未找到动作插件: {action_type}"

        discount, gifts, message = self.plugin_manager.calculate_action(
            action_type, config, items, context
        )

        total_amount = sum(item.total_amount for item in items)
        if max_discount and discount > max_discount:
            discount = max_discount
        if discount > total_amount:
            discount = total_amount
        if discount < 0:
            discount = Decimal("0")

        return discount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), gifts, message


class PromotionEngine:
    """促销规则执行引擎"""

    def __init__(
        self,
        calculation_order: Union[List[str], str] = None,
        mutex_groups: Optional[Dict[str, Dict]] = None,
        special_mutex_rules: Optional[List] = None,
        debug: bool = False,
    ):
        self.debug = debug
        self.calculation_order = calculation_order or ["promotions", "coupons"]

        self.plugin_manager = PluginManager()
        self.condition_checker = RuleConditionChecker(self.plugin_manager)
        self.scope_filter = ScopeFilter(self.plugin_manager)
        self.discount_calculator = DiscountCalculator(self.plugin_manager)
        self.mutex_checker = MutexChecker(mutex_groups, special_mutex_rules)

    def calculate(self, context: CalculationContext, rules: List[Rule]) -> CalculationResult:
        """
        执行促销计算（支持顺序参数化与并行取最优）

        三种 calculation_order 模式：
        - ['promotions', 'coupons']: 促销先、券后（默认）
        - ['coupons', 'promotions']: 券先、促销后
        - 'optimal': 并行计算两种顺序，自动取最省钱结果
        """
        calculation_order = getattr(context, "calculation_order", self.calculation_order) or ["promotions", "coupons"]

        if calculation_order == "optimal":
            original_payable = context._current_payable_amount

            context.calculation_order = ["promotions", "coupons"]
            self.mutex_checker.reset()
            result_a = self._calculate_once(context, rules)

            context._current_payable_amount = original_payable
            self.mutex_checker.reset()
            context.calculation_order = ["coupons", "promotions"]
            result_b = self._calculate_once(context, rules)

            if result_a.payable_amount <= result_b.payable_amount:
                context.calculation_order = ["promotions", "coupons"]
                return result_a
            else:
                context.calculation_order = ["coupons", "promotions"]
                return result_b

        return self._calculate_once(context, rules)

    def _calculate_once(self, context: CalculationContext, rules: List[Rule]) -> CalculationResult:
        """执行单次促销计算"""
        original_amount = context.total_amount
        applied_results = []
        remaining_items = list(context.cart_items)
        skipped_rules = []

        calculation_order = getattr(context, "calculation_order", ["promotions", "coupons"]) or ["promotions", "coupons"]
        coupons_first = calculation_order == ["coupons", "promotions"]

        # 如果券先计算
        coupon_discount = Decimal("0")
        used_coupon_details = []
        if coupons_first and context.used_coupons:
            coupon_discount, used_coupon_details = self._calculate_coupons(context)
            if coupon_discount > 0:
                context.update_payable_amount(original_amount - coupon_discount)

        self.mutex_checker.reset()

        # 按优先级排序（含单向互斥拓扑排序）
        sorted_rules = self._apply_mutex_priority_order(rules)

        # 范围预筛
        sorted_rules = self._pre_filter_by_scope(sorted_rules, remaining_items)

        # 按优先级分组
        priority_groups = []
        for priority, group in groupby(sorted_rules, key=lambda r: r.priority):
            priority_groups.append((priority, list(group)))

        applied_rules = []

        for priority, group_rules in priority_groups:
            group_applied = []
            group_payable = context.current_payable_amount

            for rule in group_rules:
                # Step 1: 互斥检查
                mutex_info = self.mutex_checker.check_mutex(rule, applied_rules)

                if mutex_info.result in (MutexCheckResult.MUTEX_BY_GROUP, MutexCheckResult.MUTEX_BY_SPECIAL):
                    skipped_rules.append({
                        "code": rule.promotion_code,
                        "reason": "mutex",
                        "message": mutex_info.message,
                    })
                    continue

                # Step 2: 处理替换逻辑
                if mutex_info.result == MutexCheckResult.REPLACE:
                    target_rule = mutex_info.replace_target
                    if target_rule:
                        applied_rules = [r for r in applied_rules if r.promotion_code != target_rule.promotion_code]
                        target_in_group = any(r.promotion_code == target_rule.promotion_code for r in group_applied)
                        if target_in_group:
                            group_applied = [r for r in group_applied if r.promotion_code != target_rule.promotion_code]

                        target_result_idx = None
                        target_discount = Decimal("0")
                        for idx, result in enumerate(applied_results):
                            if result.promotion_code == target_rule.promotion_code:
                                target_result_idx = idx
                                target_discount = result.discount
                                break

                        if target_result_idx is not None:
                            removed_result = applied_results.pop(target_result_idx)
                            target_discount = removed_result.discount
                            current_payable = context.current_payable_amount
                            new_payable = current_payable + target_discount
                            context.update_payable_amount(new_payable)
                            group_payable = new_payable

                        self.mutex_checker.reset()
                        for r in applied_rules:
                            self.mutex_checker.mark_applied(r)

                        skipped_rules.append({
                            "code": target_rule.promotion_code,
                            "reason": "replaced",
                            "message": f"被高优先级规则 {rule.promotion_code} 替换",
                        })

                # Step 3: 范围匹配检查
                scopes = list(rule.scopes)
                if scopes:
                    applicable_items = []
                    seen_skus = set()
                    for scope in scopes:
                        filtered = self.scope_filter.filter_items(scope, remaining_items)
                        for item in filtered:
                            if item.sku not in seen_skus:
                                applicable_items.append(item)
                                seen_skus.add(item.sku)

                    if not applicable_items:
                        skipped_rules.append({
                            "code": rule.promotion_code,
                            "reason": "scope_mismatch",
                            "message": "没有商品满足范围条件",
                        })
                        continue
                else:
                    applicable_items = remaining_items

                # Step 4: 条件检查
                conditions = list(rule.conditions)
                all_passed, failed_conditions = self.condition_checker.check_all(conditions, context, applicable_items)
                if not all_passed:
                    if failed_conditions:
                        failure_reasons = [f"[{fc['type']}] {fc['message']}" for fc in failed_conditions]
                        skipped_rules.append({
                            "code": rule.promotion_code,
                            "reason": "conditions_not_met",
                            "message": "；".join(failure_reasons),
                        })
                    else:
                        skipped_rules.append({
                            "code": rule.promotion_code,
                            "reason": "conditions_not_met",
                            "message": "条件不满足",
                        })
                    continue

                # Step 5: 应用规则
                original_payable = context._current_payable_amount
                context._current_payable_amount = group_payable
                try:
                    apply_result = self._apply_rule(rule, context, applicable_items)
                finally:
                    context._current_payable_amount = original_payable

                if not apply_result:
                    skipped_rules.append({
                        "code": rule.promotion_code,
                        "reason": "not_applicable",
                        "message": "规则未应用",
                    })
                    continue

                if apply_result.discount > 0 or apply_result.rewards or apply_result.free_shipping or apply_result.tier_details:
                    group_applied.append(apply_result)
                    applied_rules.append(rule)
                    self.mutex_checker.mark_applied(rule)
                else:
                    no_discount_msg = apply_result.message or "规则条件满足但未产生优惠"
                    skipped_rules.append({
                        "code": rule.promotion_code,
                        "reason": "no_discount",
                        "message": no_discount_msg,
                    })

            if group_applied:
                applied_results.extend(group_applied)
                group_discount = sum(r.discount for r in group_applied)
                new_payable = context.current_payable_amount - group_discount
                context.update_payable_amount(new_payable)

        total_discount = sum((r.discount for r in applied_results), Decimal("0"))

        if coupons_first:
            promotion_payable = original_amount - coupon_discount
            payable_amount = promotion_payable - total_discount
        else:
            promotion_payable = original_amount - total_discount
            if context.used_coupons:
                coupon_discount, used_coupon_details = self._calculate_coupons(context)
            payable_amount = promotion_payable - coupon_discount

        shipping_fee = getattr(context, "shipping_fee", Decimal("0"))
        has_free_shipping = any(p.free_shipping for p in applied_results)
        effective_shipping_fee = Decimal("0") if has_free_shipping else shipping_fee
        payable_amount = max(payable_amount, Decimal("0")) + effective_shipping_fee

        return CalculationResult(
            applied_promotions=applied_results,
            total_discount=total_discount,
            payable_amount=payable_amount,
            original_amount=original_amount,
            skipped_rules=skipped_rules,
            coupon_discount=coupon_discount,
            used_coupons=used_coupon_details,
            shipping_fee=effective_shipping_fee,
        )

    def _apply_rule(self, rule: Rule, context: CalculationContext, items: List[CartItem]) -> Optional[PromotionResult]:
        """应用单个规则"""
        actions = list(rule.actions)
        if not actions:
            return None

        total_discount = Decimal("0")
        all_rewards = []
        tier_details = []
        has_free_shipping = False
        action_messages = []
        total_amount = sum(item.total_amount for item in items)

        for action in actions:
            discount, rewards, message = self.discount_calculator.calculate(action, items, context)
            total_discount += discount
            # 多个 action 的累计折扣不得超过商品总金额
            if total_discount > total_amount:
                total_discount = total_amount

            if message:
                action_messages.append({"action_type": action.action_type, "message": message, "config": action.config})

            for reward in rewards:
                if reward.get("type") == "free_shipping":
                    has_free_shipping = True
                all_rewards.append(reward)

            if action.action_type in ["tiered_price", "tiered_amount"]:
                tier_details.append({"action_type": action.action_type, "config": action.config, "discount": str(discount)})

        action_info = "; ".join(f"[{m['action_type']}] {m['message']}" for m in action_messages if m["message"])

        return PromotionResult(
            promotion_code=rule.promotion_code,
            strategy_type=rule.strategy_type,
            discount=total_discount,
            applied_items=[item.sku for item in items],
            message=action_info,
            rewards=all_rewards,
            tier_details=tier_details,
            free_shipping=has_free_shipping,
            refund_config=rule.refund_config,
        )

    def _apply_mutex_priority_order(self, rules: List[Rule]) -> List[Rule]:
        """
        应用互斥优先级顺序（单向互斥拓扑排序）

        双向互斥：按优先级排序（默认行为）
        单向互斥：强制按指定顺序排序（A优先则A在前，忽略优先级）
        """
        if not rules or not self.mutex_checker.special_mutex_rules:
            return sorted(rules, key=lambda r: (-r.priority, r.promotion_code))

        now = datetime.now()
        rule_codes = {getattr(r, "promotion_code", None) for r in rules if getattr(r, "promotion_code", None)}

        # 筛选与当前规则相关的单向互斥规则
        priority_order = {}
        for mr in self.mutex_checker.special_mutex_rules:
            if getattr(mr, "is_bidirectional", True):
                continue
            if not getattr(mr, "is_active", True):
                continue
            valid_from = getattr(mr, "valid_from", None)
            valid_to = getattr(mr, "valid_to", None)
            if valid_from and now < valid_from:
                continue
            if valid_to and now > valid_to:
                continue

            rule_a_id = getattr(mr, "rule_a_id", "")
            rule_b_id = getattr(mr, "rule_b_id", "")

            if rule_a_id not in rule_codes and rule_b_id not in rule_codes:
                continue

            priority_direction = getattr(mr, "priority_direction", "a")
            if priority_direction == "a":
                # A优先：A应该先检查，B后检查
                priority_order[rule_b_id] = rule_a_id
            else:
                # B优先：B应该先检查，A后检查
                priority_order[rule_a_id] = rule_b_id

        if not priority_order:
            return sorted(rules, key=lambda r: (-r.priority, r.promotion_code))

        def get_sort_key(rule):
            code = getattr(rule, "promotion_code", "")
            if code not in priority_order:
                # 没有单向互斥关系的，按优先级排序（权重0）
                return (0, -rule.priority, code)

            # 有单向互斥关系的
            is_priority_rule = code in priority_order.values()
            if is_priority_rule:
                # 优先规则（应该先检查的）：排在最前面（权重-1）
                return (-1, -rule.priority, code)
            else:
                # 非优先规则（应该后检查的）：排在后面（权重1）
                return (1, -rule.priority, code)

        return sorted(rules, key=get_sort_key)

    def _pre_filter_by_scope(self, rules: List[Rule], items: List[CartItem]) -> List[Rule]:
        """基于范围配置快速排除明显不匹配的规则"""
        if not items:
            return rules

        item_skus = {getattr(item, "sku", None) for item in items if getattr(item, "sku", None)}
        candidates = []

        for rule in rules:
            scopes = list(rule.scopes)
            if not scopes:
                candidates.append(rule)
                continue

            might_match = False
            for scope in scopes:
                scope_type = scope.scope_type
                config = scope.config or {}

                if scope_type in ("all_items", "all"):
                    might_match = True
                    break
                elif scope_type in ("specific_items", "sku_list", "sku"):
                    rule_skus = set(config.get("skus", []))
                    if item_skus & rule_skus:
                        might_match = True
                        break
                else:
                    might_match = True
                    break

            if might_match:
                candidates.append(rule)

        return candidates

    def _calculate_coupons(self, context: CalculationContext) -> Tuple[Decimal, List[Dict]]:
        """完整版券抵扣计算（支持5种券类型 + 组合规则过滤）"""
        calc = CouponUsageCalculator()
        total_discount, details = calc.calculate(
            promotion_payable=context.current_payable_amount,
            used_coupons=context.used_coupons,
        )
        # 转换为引擎内部统一格式
        used_details = []
        for d in details:
            used_details.append({
                "code": d.get("code", ""),
                "coupon_type": d.get("coupon_type", ""),
                "discount": d.get("deducted_amount", "0"),
                "status": d.get("status", ""),
                "message": d.get("message", ""),
            })
        return total_discount, used_details

    def get_calculation_details(self) -> dict:
        """获取计算详情（用于调试和分析）"""
        return {
            "mutex_config": self.mutex_checker.mutex_groups,
            "plugins": {
                "conditions": self.plugin_manager.get_available_conditions(),
                "actions": self.plugin_manager.get_available_actions(),
                "scopes": self.plugin_manager.get_available_scopes(),
            },
        }

    def get_available_plugins(self) -> Dict:
        """获取所有可用的插件列表"""
        return {
            "conditions": self.plugin_manager.get_available_conditions(),
            "actions": self.plugin_manager.get_available_actions(),
            "scopes": self.plugin_manager.get_available_scopes(),
        }

    def has_plugin_for(self, plugin_type: str, code: str) -> bool:
        """检查是否有指定类型的插件"""
        if plugin_type == "condition":
            return self.plugin_manager.has_condition_plugin(code)
        elif plugin_type == "action":
            return self.plugin_manager.has_action_plugin(code)
        elif plugin_type == "scope":
            return self.plugin_manager.has_scope_plugin(code)
        return False

    def force_refresh_config(self) -> None:
        """强制刷新所有配置（重置互斥检查器状态）"""
        self.mutex_checker.reset()
