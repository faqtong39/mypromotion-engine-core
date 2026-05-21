"""
使用券抵扣计算（去 Django 化版本）

处理用户已持有的优惠券在正向计算中的抵扣金额计算。
支持五种券类型：满减券、折扣券、无门槛券、阶梯券、兑换/特价券。

去 Django 化改动：
- 删除 CouponInstance / CouponTemplate ORM 查询
- 删除 CouponCombinationRule ORM 查询，改为可选的内存配置传入
- 所有外部数据通过 UsedCoupon dataclass 显式传入
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Any, Tuple, Optional

from .types import UsedCoupon


class CouponCombinationChecker:
    """
    消费券组合规则检查器（内存版本）

    根据配置的组合规则，检查传入的使用券列表，
    过滤掉互斥的券，保留叠加的券。

    【设计原则】
    - 默认所有券可叠加（无规则不限制）
    - 互斥规则：组内只保留券模板优先级最高的那张
    - 叠加规则：不做限制，但计算时按券模板优先级从高到低排序
    """

    def __init__(self, combination_rules: Optional[List[Dict]] = None):
        """
        Args:
            combination_rules: 内存中的组合规则列表，每项格式：
                {
                    "name": str,
                    "coupon_types": List[str],
                    "combination_mode": "stackable" | "mutex",
                }
        """
        self.rules = combination_rules or []

    def filter_coupons(
        self,
        used_coupons: List[UsedCoupon]
    ) -> Tuple[List[UsedCoupon], List[Dict[str, Any]]]:
        """
        根据组合规则过滤使用券

        Returns:
            (retained_coupons, excluded_coupons_info)
        """
        if not self.rules or not used_coupons:
            sorted_coupons = sorted(used_coupons, key=lambda c: c.priority, reverse=True)
            return sorted_coupons, []

        retained = list(used_coupons)
        excluded = []

        for rule in self.rules:
            types_in_rule = set(rule.get("coupon_types") or [])
            if len(types_in_rule) < 2:
                continue

            matched = [c for c in retained if c.coupon_type in types_in_rule]
            if len(matched) <= 1:
                continue

            if rule.get("combination_mode") == "stackable":
                pass
            else:
                matched_sorted = sorted(matched, key=lambda c: c.priority, reverse=True)
                keep = matched_sorted[0]
                for c in matched_sorted[1:]:
                    excluded.append({
                        "code": c.code,
                        "coupon_type": c.coupon_type,
                        "reason": f"与 {keep.code} 互斥（规则:{rule.get('name', '')}，保留优先级更高的券）",
                        "rule_name": rule.get("name", ""),
                    })
                    if c in retained:
                        retained.remove(c)

        retained = sorted(retained, key=lambda c: c.priority, reverse=True)
        return retained, excluded


class CouponUsageCalculator:
    """
    使用券抵扣计算器（纯内存，无外部依赖）

    根据促销折扣后的应付金额，计算各使用券的实际抵扣金额。
    支持五种券类型：满减券、折扣券、无门槛券、阶梯券、兑换/特价券。
    """

    def calculate(
        self,
        promotion_payable: Decimal,
        used_coupons: List[UsedCoupon],
        combination_rules: Optional[List[Dict]] = None,
    ) -> Tuple[Decimal, List[Dict[str, Any]]]:
        """
        计算使用券抵扣

        Args:
            promotion_payable: 促销折扣后的应付金额
            used_coupons: 用户传入的使用券列表
            combination_rules: 可选的组合规则（内存配置）

        Returns:
            (coupon_discount, details)
        """
        if not used_coupons:
            return Decimal("0"), []

        # 1. 应用组合规则过滤互斥券
        checker = CouponCombinationChecker(combination_rules)
        filtered_coupons, excluded_info = checker.filter_coupons(used_coupons)

        total_coupon_discount = Decimal("0")
        remaining_payable = promotion_payable
        details = []

        for info in excluded_info:
            details.append({
                "code": info["code"],
                "coupon_type": info["coupon_type"],
                "deducted_amount": "0.00",
                "status": "excluded_mutex",
                "message": info["reason"],
            })

        for coupon in filtered_coupons:
            # 外部已计算抵扣金额的场景
            if coupon.used_amount is not None:
                deducted = min(coupon.used_amount, remaining_payable)
                if deducted > 0:
                    total_coupon_discount += deducted
                    remaining_payable -= deducted
                    details.append({
                        "code": coupon.code,
                        "coupon_type": coupon.coupon_type,
                        "deducted_amount": str(deducted.quantize(Decimal("0.01"))),
                        "status": "applied",
                        "message": f"外部已计算抵扣金额，实际抵扣 {deducted}",
                    })
                else:
                    details.append({
                        "code": coupon.code,
                        "coupon_type": coupon.coupon_type,
                        "deducted_amount": "0.00",
                        "status": "skipped_zero",
                        "message": "剩余应付金额为0，无需抵扣",
                    })
                continue

            coupon_type = coupon.coupon_type
            min_order = coupon.min_order_amount or Decimal("0")
            discount_value = coupon.discount_value or Decimal("0")

            if remaining_payable < min_order:
                details.append({
                    "code": coupon.code,
                    "coupon_type": coupon_type,
                    "deducted_amount": "0.00",
                    "status": "skipped_threshold",
                    "message": f"当前应付金额 {remaining_payable} 未达到使用门槛 {min_order}",
                })
                continue

            if coupon_type == "no_threshold":
                deducted = min(discount_value, remaining_payable)

            elif coupon_type in ("full_reduction", "special_price"):
                deducted = min(discount_value, remaining_payable)

            elif coupon_type == "percentage_discount":
                if discount_value <= 0 or discount_value > 1:
                    details.append({
                        "code": coupon.code,
                        "coupon_type": coupon_type,
                        "deducted_amount": "0.00",
                        "status": "skipped_invalid",
                        "message": f"折扣率 {discount_value} 无效，应在 0~1 之间",
                    })
                    continue
                deducted = (remaining_payable * (Decimal("1") - discount_value)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                deducted = min(deducted, remaining_payable)

            elif coupon_type == "tiered":
                deducted = self._calculate_tiered(remaining_payable, coupon.tiered_rules)
                deducted = min(deducted, remaining_payable)

            else:
                details.append({
                    "code": coupon.code,
                    "coupon_type": coupon_type,
                    "deducted_amount": "0.00",
                    "status": "skipped_unknown_type",
                    "message": f"未知券类型: {coupon_type}",
                })
                continue

            if deducted > 0:
                total_coupon_discount += deducted
                remaining_payable -= deducted
                details.append({
                    "code": coupon.code,
                    "coupon_type": coupon_type,
                    "deducted_amount": str(deducted.quantize(Decimal("0.01"))),
                    "status": "applied",
                    "message": f"抵扣成功，抵扣金额 {deducted}",
                })
            else:
                details.append({
                    "code": coupon.code,
                    "coupon_type": coupon_type,
                    "deducted_amount": "0.00",
                    "status": "skipped_zero",
                    "message": "计算后抵扣金额为0",
                })

        return total_coupon_discount, details

    @staticmethod
    def _calculate_tiered(payable: Decimal, tiered_rules: List[Dict]) -> Decimal:
        """
        计算阶梯券抵扣金额

        规则格式: [{"threshold": 300, "discount": 30}, ...]
        按 threshold 降序，找到最高适用阶梯，计算 (payable // threshold) * discount
        """
        if not tiered_rules:
            return Decimal("0")

        sorted_rules = sorted(
            tiered_rules,
            key=lambda x: x.get("threshold", 0),
            reverse=True
        )

        for rule in sorted_rules:
            threshold = Decimal(str(rule.get("threshold", "0")))
            discount = Decimal(str(rule.get("discount", "0")))
            if threshold <= 0:
                continue
            if payable >= threshold:
                tiers = int(payable // threshold)
                return (Decimal(str(tiers)) * discount).quantize(Decimal("0.01"))

        return Decimal("0")
