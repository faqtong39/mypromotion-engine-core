"""
动作计算插件（内置 12 个核心动作）

去 Django 化改动：
- 删除 UserProfile ORM 查询（积分/余额改为读取 context.extra）
- 所有计算只依赖 items 和 context 的直接属性
"""
import random
from decimal import Decimal
from typing import Any, Dict, List

from .base import ActionPlugin, PluginResult


class FixedAmountAction(ActionPlugin):
    """固定金额减免"""
    code = "fixed_amount_reduction"
    name = "固定金额减免"
    description = "减免固定金额"
    config_schema = {
        "type": "object",
        "required": ["amount"],
        "properties": {"amount": {"type": "number", "description": "减免金额"}},
    }

    def calculate(self, config: Dict, items: List, context: Any) -> PluginResult:
        amount = config.get("amount")
        discount = Decimal(str(amount)) if amount is not None else Decimal("0")
        total_amount = sum(item.total_amount for item in items)
        discount = self.apply_limits(discount, total_amount)
        return PluginResult(success=True, data={"discount": discount, "rewards": []}, message=f"固定减免: {discount}")


class PercentageAction(ActionPlugin):
    """百分比折扣"""
    code = "percentage_discount"
    name = "百分比折扣"
    description = "如9折（90%）"
    config_schema = {
        "type": "object",
        "properties": {"percentage": {"type": "number", "description": "折扣百分比，90表示9折"}},
    }

    def calculate(self, config: Dict, items: List, context: Any) -> PluginResult:
        pct = config.get("percentage")
        percentage = Decimal(str(pct)) if pct is not None else Decimal("0")
        total_amount = sum(item.total_amount for item in items)
        rate = percentage / Decimal("100")
        discount = total_amount * (Decimal("1") - rate)
        discount = self.apply_limits(discount, total_amount)
        return PluginResult(
            success=True,
            data={"discount": discount, "rewards": []},
            message=f"百分比折扣: {percentage}%（{rate}折），减免{discount}",
        )


class FixedPriceAction(ActionPlugin):
    """固定价"""
    code = "fixed_price"
    name = "固定价"
    description = "商品以固定价格计算"
    config_schema = {
        "type": "object",
        "properties": {"price": {"type": "number", "description": "固定价格"}},
    }

    def calculate(self, config: Dict, items: List, context: Any) -> PluginResult:
        price = config.get("price")
        fixed_price = Decimal(str(price)) if price is not None else Decimal("0")
        total_quantity = sum(item.quantity for item in items)
        original = sum(item.total_amount for item in items)
        discount = original - (fixed_price * total_quantity)
        if discount < 0:
            discount = Decimal("0")
        discount = self.apply_limits(discount, original)
        return PluginResult(
            success=True,
            data={"discount": discount, "rewards": []},
            message=f"固定价: {fixed_price}/件，减免{discount}",
        )


class TieredPriceAction(ActionPlugin):
    """阶梯价（按数量）"""
    code = "tiered_price"
    name = "阶梯价（按数量）"
    description = "根据购买数量享受不同价格"
    config_schema = {
        "type": "object",
        "required": ["tiers"],
        "properties": {"tiers": {"type": "array", "description": "阶梯配置"}},
    }

    def _get_threshold(self, tier: Dict) -> int:
        return tier.get("min_quantity") or tier.get("threshold") or tier.get("quantity", 0)

    def _check_match(self, tier: Dict, total_quantity: int) -> bool:
        min_threshold = self._get_threshold(tier)
        max_threshold = tier.get("max_quantity")
        if total_quantity < min_threshold:
            return False
        if max_threshold is not None and total_quantity > max_threshold:
            return False
        return True

    def _get_price(self, tier: Dict, avg_price: Decimal) -> Decimal:
        if "price" in tier:
            return Decimal(str(tier.get("price", 0)))
        elif "discount_rate" in tier:
            return avg_price * Decimal(str(tier.get("discount_rate", 1)))
        return Decimal("0")

    def calculate(self, config: Dict, items: List, context: Any) -> PluginResult:
        tiers = config.get("tiers", [])
        if not tiers:
            return PluginResult(success=True, data={"discount": Decimal("0"), "rewards": []})
        total_quantity = sum(item.quantity for item in items)
        original = sum(item.total_amount for item in items)
        avg_price = original / total_quantity if total_quantity > 0 else Decimal("0")
        sorted_tiers = sorted(tiers, key=lambda x: self._get_threshold(x), reverse=True)
        for tier in sorted_tiers:
            if self._check_match(tier, total_quantity):
                new_price = self._get_price(tier, avg_price)
                new_total = new_price * total_quantity
                discount = original - new_total
                if discount < 0:
                    discount = Decimal("0")
                discount = self.apply_limits(discount, original)
                return PluginResult(
                    success=True,
                    data={"discount": discount, "rewards": [], "tier_applied": tier},
                    message=f"阶梯价: 数量{total_quantity}，适用阶梯{tier}",
                )
        return PluginResult(success=True, data={"discount": Decimal("0"), "rewards": []})


class TieredAmountAction(ActionPlugin):
    """阶梯优惠（按金额）"""
    code = "tiered_amount"
    name = "阶梯优惠（按金额）"
    description = "根据订单金额享受不同优惠"
    config_schema = {
        "type": "object",
        "required": ["tiers"],
        "properties": {"tiers": {"type": "array", "description": "阶梯配置"}},
    }

    def calculate(self, config: Dict, items: List, context: Any) -> PluginResult:
        tiers = config.get("tiers", [])
        if not tiers:
            return PluginResult(success=True, data={"discount": Decimal("0"), "rewards": []})
        total_amount = sum(item.total_amount for item in items)
        sorted_tiers = sorted(tiers, key=lambda x: x.get("threshold", 0), reverse=True)
        for tier in sorted_tiers:
            threshold = Decimal(str(tier.get("threshold", 0)))
            if total_amount >= threshold:
                discount = Decimal(str(tier.get("amount", 0)))
                discount = self.apply_limits(discount, total_amount)
                return PluginResult(
                    success=True,
                    data={"discount": discount, "rewards": [], "tier_applied": tier},
                    message=f"阶梯优惠: 金额{total_amount}，适用阶梯{tier}",
                )
        return PluginResult(success=True, data={"discount": Decimal("0"), "rewards": []})


class FreeShippingAction(ActionPlugin):
    """免运费"""
    code = "free_shipping"
    name = "免运费"
    description = "免除订单运费"
    config_schema = {"type": "object", "properties": {}}

    def calculate(self, config: Dict, items: List, context: Any) -> PluginResult:
        shipping_fee = getattr(context, "shipping_fee", Decimal("0"))
        return PluginResult(
            success=True,
            data={
                "discount": Decimal("0"),
                "rewards": [{"type": "free_shipping", "message": "订单免运费"}],
                "free_shipping": True,
                "shipping_fee": shipping_fee,
            },
            message="免运费",
        )


class PointsDeductAction(ActionPlugin):
    """积分抵扣"""
    code = "points_deduct"
    name = "积分抵扣"
    description = "使用积分抵扣订单金额"
    config_schema = {
        "type": "object",
        "properties": {
            "points_ratio": {"type": "number", "default": 100, "description": "多少积分抵1元"},
            "max_deduct_amount": {"type": "number", "default": 0, "description": "0表示不限制"},
        },
    }

    def calculate(self, config: Dict, items: List, context: Any) -> PluginResult:
        points_ratio = Decimal(str(config.get("points_ratio", 100)))
        max_deduct_amount = Decimal(str(config.get("max_deduct_amount", 0)))
        extra = getattr(context, "extra", {}) or {}
        user_points = Decimal(str(extra.get("points", 0)))

        if user_points <= 0:
            return PluginResult(success=False, data={"discount": Decimal("0")}, message="用户积分不足")

        total_amount = sum(item.total_amount for item in items)
        max_deduct = min(max_deduct_amount, total_amount) if max_deduct_amount > 0 else total_amount
        points_value = user_points / points_ratio
        actual_deduct = min(points_value, max_deduct)
        points_used = int(actual_deduct * points_ratio)

        if actual_deduct <= 0:
            return PluginResult(success=False, data={"discount": Decimal("0")}, message="积分抵扣金额为0")

        return PluginResult(
            success=True,
            data={
                "discount": actual_deduct,
                "rewards": [],
                "points_used": points_used,
                "points_remaining": int(user_points) - points_used,
            },
            message=f"积分抵扣: 使用{points_used}积分，抵扣{actual_deduct}元",
        )


class BalanceDeductAction(ActionPlugin):
    """余额抵扣"""
    code = "balance_deduct"
    name = "余额抵扣"
    description = "使用账户余额抵扣订单金额"
    config_schema = {
        "type": "object",
        "properties": {
            "max_deduct_amount": {"type": "number", "default": 0, "description": "0表示不限制"},
        },
    }

    def calculate(self, config: Dict, items: List, context: Any) -> PluginResult:
        max_deduct_amount = Decimal(str(config.get("max_deduct_amount", 0)))
        extra = getattr(context, "extra", {}) or {}
        user_balance = Decimal(str(extra.get("balance", 0)))

        if user_balance <= 0:
            return PluginResult(success=False, data={"discount": Decimal("0")}, message="用户余额不足")

        total_amount = sum(item.total_amount for item in items)
        if max_deduct_amount > 0:
            use_amount = min(user_balance, max_deduct_amount, total_amount)
        else:
            use_amount = min(user_balance, total_amount)

        if use_amount <= 0:
            return PluginResult(success=False, data={"discount": Decimal("0")}, message="余额抵扣金额为0")

        return PluginResult(
            success=True,
            data={"discount": use_amount, "rewards": [], "balance_used": use_amount, "balance_remaining": user_balance - use_amount},
            message=f"余额抵扣: 使用{use_amount}元",
        )


class PreSaleAction(ActionPlugin):
    """预售定金膨胀"""
    code = "pre_sale"
    name = "预售定金膨胀"
    description = "定金膨胀抵扣，如100抵200"
    config_schema = {
        "type": "object",
        "required": ["deposit", "expansion_ratio"],
        "properties": {
            "deposit": {"type": "number", "description": "定金金额"},
            "expansion_ratio": {"type": "number", "description": "膨胀倍数"},
        },
    }

    def calculate(self, config: Dict, items: List, context: Any) -> PluginResult:
        deposit = Decimal(str(config.get("deposit", 0)))
        expansion_ratio = Decimal(str(config.get("expansion_ratio", 1)))
        expansion = deposit * expansion_ratio
        extra = getattr(context, "extra", {}) or {}
        deposit_paid = Decimal(str(extra.get("deposit_paid", 0)))
        is_pre_sale = extra.get("is_pre_sale", False)
        total_amount = sum(item.total_amount for item in items)

        if is_pre_sale and deposit_paid >= deposit:
            discount = self.apply_limits(expansion, total_amount)
            return PluginResult(
                success=True,
                data={"discount": discount, "rewards": [], "deposit": deposit, "expansion": expansion},
                message=f"预售定金膨胀: 定金{deposit}元抵{expansion}元 (×{expansion_ratio})",
            )
        elif is_pre_sale:
            return PluginResult(
                success=True,
                data={"discount": Decimal("0"), "rewards": [], "deposit_required": deposit},
                message=f"预售期: 需支付定金{deposit}元",
            )
        else:
            return PluginResult(success=False, data={"discount": Decimal("0")}, message="非预售期，不享受预售优惠")


class DiscountAmountLimitAction(ActionPlugin):
    """折扣金额限制"""
    code = "discount_amount_limit"
    name = "折扣金额限制"
    description = "设置最高折扣金额上限"
    config_schema = {
        "type": "object",
        "required": ["max_discount"],
        "properties": {"max_discount": {"type": "number", "description": "最高折扣金额"}},
    }

    def calculate(self, config: Dict, items: List, context: Any) -> PluginResult:
        max_discount = Decimal(str(config.get("max_discount", 0)))
        return PluginResult(
            success=True,
            data={"discount": Decimal("0"), "rewards": [], "max_discount": max_discount},
            message=f"折扣金额上限: ¥{max_discount}",
        )


class InstallmentFreeAction(ActionPlugin):
    """分期免息"""
    code = "installment_free"
    name = "分期免息"
    description = "大额商品分期免息"
    config_schema = {
        "type": "object",
        "properties": {
            "periods": {"type": "array", "description": "免息期数"},
            "fee_bearer": {"type": "string", "default": "merchant"},
        },
    }

    def calculate(self, config: Dict, items: List, context: Any) -> PluginResult:
        periods = config.get("periods", [3, 6, 12])
        fee_bearer = config.get("fee_bearer", "merchant")
        return PluginResult(
            success=True,
            data={
                "discount": Decimal("0"),
                "rewards": [],
                "installment": {"available_periods": periods, "fee_bearer": fee_bearer, "interest_free": True},
            },
            message=f"分期免息: 支持{periods}期，手续费由{fee_bearer}承担",
        )


class RandomReductionAction(ActionPlugin):
    """随机立减"""
    code = "random_reduction"
    name = "随机立减"
    description = "支付时随机减免一定金额"
    config_schema = {
        "type": "object",
        "properties": {
            "min_amount": {"type": "number", "default": 1},
            "max_amount": {"type": "number", "default": 10},
        },
    }

    def calculate(self, config: Dict, items: List, context: Any) -> PluginResult:
        min_amount = Decimal(str(config.get("min_amount", 1)))
        max_amount = Decimal(str(config.get("max_amount", 10)))
        total_amount = sum(item.total_amount for item in items)
        mean = float((min_amount + max_amount) / 2)
        std = float((max_amount - min_amount) / 4)
        random_value = random.gauss(mean, std)
        random_value = max(float(min_amount), min(float(max_amount), random_value))
        discount = Decimal(str(round(random_value, 2)))
        discount = self.apply_limits(discount, total_amount)
        return PluginResult(
            success=True,
            data={"discount": discount, "rewards": [], "random_info": {"min": float(min_amount), "max": float(max_amount), "actual": float(discount)}},
            message=f"随机立减: 减免{discount}元（范围{min_amount}-{max_amount}元）",
        )
