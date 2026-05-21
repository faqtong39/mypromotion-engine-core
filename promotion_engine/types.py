"""
促销引擎核心数据类型

所有 Django Model 已替换为 dataclass，ORM 关系替换为直接属性访问。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union


@dataclass
class CartItem:
    """购物车商品项"""
    sku: str
    quantity: int
    price: Decimal
    category_id: Optional[str] = None
    brand_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    # 扩展字段：成本价、会员价等（用于价格保护检测）
    cost_price: Optional[Decimal] = None
    member_price: Optional[Decimal] = None
    vip_price: Optional[Decimal] = None

    def __post_init__(self):
        from decimal import Decimal as D
        self.price = D(str(self.price))
        if self.cost_price is not None:
            self.cost_price = D(str(self.cost_price))
        if self.member_price is not None:
            self.member_price = D(str(self.member_price))
        if self.vip_price is not None:
            self.vip_price = D(str(self.vip_price))

    @property
    def total_amount(self) -> Decimal:
        return (self.price * self.quantity).quantize(Decimal("0.01"))


@dataclass
class UsedCoupon:
    """用户已使用的优惠券（输入抵扣券）"""
    code: str                          # 券实例编码
    coupon_type: str                   # 券类型
    discount_value: Optional[Decimal] = None
    min_order_amount: Optional[Decimal] = None
    tiered_rules: List[Dict] = field(default_factory=list)
    used_amount: Optional[Decimal] = None
    priority: int = 0


@dataclass
class RuleCondition:
    """规则条件定义（替代 Django RuleCondition Model）"""
    condition_type: str
    config: Dict[str, Any] = field(default_factory=dict)
    logic_operator: str = "AND"        # 'AND' 或 'OR'
    sort_order: int = 0

    def __post_init__(self):
        if self.logic_operator not in ("AND", "OR"):
            self.logic_operator = "AND"


@dataclass
class RuleAction:
    """规则优惠动作定义（替代 Django RuleAction Model）"""
    action_type: str
    config: Dict[str, Any] = field(default_factory=dict)
    max_discount: Optional[Decimal] = None
    sort_order: int = 0


@dataclass
class RuleScope:
    """规则应用范围（替代 Django RuleScope Model）"""
    scope_type: str
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Rule:
    """促销规则（替代 Django PromotionRule Model）

    使用方式：
        rule = Rule(
            promotion_code="SUMMER2026",
            strategy_type="full_reduction",
            priority=100,
            conditions=[RuleCondition(condition_type="min_order_amount", config={"amount": 300})],
            actions=[RuleAction(action_type="fixed_amount_reduction", config={"amount": 50})],
            scopes=[RuleScope(scope_type="all_items", config={})],
        )
    """
    promotion_code: str
    strategy_type: str
    name: str = ""
    description: str = ""
    priority: int = 0
    status: str = "active"             # active / draft / paused / expired
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    stack_config: Dict[str, Any] = field(default_factory=dict)
    conditions: List[RuleCondition] = field(default_factory=list)
    actions: List[RuleAction] = field(default_factory=list)
    scopes: List[RuleScope] = field(default_factory=list)
    # 价格保护
    enable_price_protection: bool = False
    price_protection_config: Optional[Dict[str, Any]] = None
    # 售后策略
    refund_config: Dict[str, Any] = field(default_factory=dict)

    # --- 便捷构造方法 ---

    @classmethod
    def full_reduction(
        cls,
        threshold: Union[str, float, Decimal],
        amount: Union[str, float, Decimal],
        promotion_code: str = "",
        priority: int = 0,
        scopes: Optional[List[RuleScope]] = None,
        stack_config: Optional[Dict] = None,
    ) -> Rule:
        """满减规则快捷构造"""
        code = promotion_code or f"FR_{threshold}_{amount}"
        return cls(
            promotion_code=code,
            name=f"满{threshold}减{amount}",
            strategy_type="full_reduction",
            priority=priority,
            conditions=[RuleCondition(condition_type="min_order_amount", config={"amount": float(threshold)})],
            actions=[RuleAction(action_type="fixed_amount_reduction", config={"amount": float(amount)})],
            scopes=scopes or [RuleScope(scope_type="all_items", config={})],
            stack_config=stack_config or {},
        )

    @classmethod
    def percentage_discount(
        cls,
        percentage: Union[str, float, Decimal],
        promotion_code: str = "",
        priority: int = 0,
        scopes: Optional[List[RuleScope]] = None,
        stack_config: Optional[Dict] = None,
    ) -> Rule:
        """满折/百分比折扣快捷构造"""
        code = promotion_code or f"PD_{percentage}"
        return cls(
            promotion_code=code,
            name=f"{percentage}%折扣",
            strategy_type="full_discount",
            priority=priority,
            conditions=[RuleCondition(condition_type="min_order_amount", config={"amount": 0})],
            actions=[RuleAction(action_type="percentage_discount", config={"percentage": float(percentage)})],
            scopes=scopes or [RuleScope(scope_type="all_items", config={})],
            stack_config=stack_config or {},
        )

    @classmethod
    def fixed_price(
        cls,
        price: Union[str, float, Decimal],
        promotion_code: str = "",
        priority: int = 0,
        scopes: Optional[List[RuleScope]] = None,
        stack_config: Optional[Dict] = None,
    ) -> Rule:
        """固定价快捷构造"""
        code = promotion_code or f"FP_{price}"
        return cls(
            promotion_code=code,
            name=f"固定价{price}",
            strategy_type="special_price",
            priority=priority,
            conditions=[],
            actions=[RuleAction(action_type="fixed_price", config={"price": float(price)})],
            scopes=scopes or [RuleScope(scope_type="all_items", config={})],
            stack_config=stack_config or {},
        )

    @classmethod
    def free_shipping(
        cls,
        threshold: Union[str, float, Decimal] = 0,
        promotion_code: str = "",
        priority: int = 0,
    ) -> Rule:
        """包邮规则快捷构造"""
        code = promotion_code or f"FS_{threshold}"
        conditions = []
        if threshold:
            conditions.append(RuleCondition(condition_type="min_order_amount", config={"amount": float(threshold)}))
        return cls(
            promotion_code=code,
            name=f"满{threshold}包邮" if threshold else "包邮",
            strategy_type="free_shipping",
            priority=priority,
            conditions=conditions,
            actions=[RuleAction(action_type="free_shipping", config={})],
            scopes=[RuleScope(scope_type="all_items", config={})],
        )

    @classmethod
    def tiered_price(
        cls,
        tiers: List[Dict],
        promotion_code: str = "",
        priority: int = 0,
        scopes: Optional[List[RuleScope]] = None,
        stack_config: Optional[Dict] = None,
    ) -> Rule:
        """阶梯价（按数量）快捷构造

        tiers 格式:
            [{"quantity": 1, "price": 100}, {"quantity": 3, "price": 90}]
        """
        code = promotion_code or "TIERED_PRICE"
        return cls(
            promotion_code=code,
            name="阶梯价",
            strategy_type="tiered_price",
            priority=priority,
            conditions=[],
            actions=[RuleAction(action_type="tiered_price", config={"tiers": tiers})],
            scopes=scopes or [RuleScope(scope_type="all_items", config={})],
            stack_config=stack_config or {},
        )

    @classmethod
    def tiered_amount(
        cls,
        tiers: List[Dict],
        promotion_code: str = "",
        priority: int = 0,
        scopes: Optional[List[RuleScope]] = None,
        stack_config: Optional[Dict] = None,
    ) -> Rule:
        """阶梯优惠（按金额）快捷构造

        tiers 格式:
            [{"threshold": 100, "amount": 10}, {"threshold": 200, "amount": 30}]
        """
        code = promotion_code or "TIERED_AMOUNT"
        return cls(
            promotion_code=code,
            name="阶梯优惠",
            strategy_type="tiered_amount",
            priority=priority,
            conditions=[],
            actions=[RuleAction(action_type="tiered_amount", config={"tiers": tiers})],
            scopes=scopes or [RuleScope(scope_type="all_items", config={})],
            stack_config=stack_config or {},
        )

    @classmethod
    def first_order(
        cls,
        amount: Union[str, float, Decimal],
        promotion_code: str = "",
        priority: int = 0,
    ) -> Rule:
        """首单优惠快捷构造"""
        code = promotion_code or "FIRST_ORDER"
        return cls(
            promotion_code=code,
            name=f"首单减{amount}",
            strategy_type="first_order",
            priority=priority,
            conditions=[RuleCondition(condition_type="is_first_order", config={})],
            actions=[RuleAction(action_type="fixed_amount_reduction", config={"amount": float(amount)})],
            scopes=[RuleScope(scope_type="all_items", config={})],
        )

    @classmethod
    def member_exclusive(
        cls,
        percentage: Union[str, float, Decimal],
        member_groups: List[str],
        promotion_code: str = "",
        priority: int = 0,
    ) -> Rule:
        """会员专享折扣快捷构造"""
        code = promotion_code or "MEMBER"
        return cls(
            promotion_code=code,
            name=f"会员{percentage}%折扣",
            strategy_type="member_exclusive",
            priority=priority,
            conditions=[RuleCondition(condition_type="user_group", config={"group_ids": member_groups})],
            actions=[RuleAction(action_type="percentage_discount", config={"percentage": float(percentage)})],
            scopes=[RuleScope(scope_type="all_items", config={})],
        )

    @classmethod
    def pre_sale(
        cls,
        deposit: Union[str, float, Decimal],
        expansion_ratio: Union[str, float, Decimal],
        promotion_code: str = "",
        priority: int = 0,
    ) -> Rule:
        """预售定金膨胀快捷构造"""
        code = promotion_code or "PRESALE"
        return cls(
            promotion_code=code,
            name=f"预售定金{deposit}抵{float(deposit)*float(expansion_ratio)}",
            strategy_type="pre_sale",
            priority=priority,
            conditions=[],
            actions=[RuleAction(action_type="pre_sale", config={"deposit": float(deposit), "expansion_ratio": float(expansion_ratio)})],
            scopes=[RuleScope(scope_type="all_items", config={})],
        )

    @classmethod
    def bundle_offer(
        cls,
        price: Union[str, float, Decimal],
        skus: List[str],
        promotion_code: str = "",
        priority: int = 0,
    ) -> Rule:
        """组合优惠价快捷构造"""
        code = promotion_code or "BUNDLE"
        return cls(
            promotion_code=code,
            name=f"组合价{price}",
            strategy_type="bundle_offer",
            priority=priority,
            conditions=[RuleCondition(condition_type="combo_items", config={"skus": skus})],
            actions=[RuleAction(action_type="fixed_price", config={"price": float(price)})],
            scopes=[RuleScope(scope_type="specific_items", config={"skus": skus})],
        )


@dataclass
class CalculationContext:
    """计算上下文"""
    user_id: int = 0
    cart_items: List[CartItem] = field(default_factory=list)
    promotion_codes: List[str] = field(default_factory=list)
    channel: Optional[str] = None
    shipping_method: Optional[str] = None
    user_group: Optional[str] = None
    payment_method: Optional[str] = None
    current_time: datetime = field(default_factory=datetime.now)
    extra: Dict[str, Any] = field(default_factory=dict)
    is_first_order: bool = False
    shipping_fee: Decimal = field(default_factory=lambda: Decimal("0"))
    _current_payable_amount: Optional[Decimal] = None
    user_info: Dict[str, Any] = field(default_factory=dict)
    used_coupons: List[UsedCoupon] = field(default_factory=list)
    calculation_order: Union[List[str], str] = field(default_factory=lambda: ["promotions", "coupons"])

    @property
    def total_amount(self) -> Decimal:
        return sum(item.total_amount for item in self.cart_items)

    @property
    def current_payable_amount(self) -> Decimal:
        if self._current_payable_amount is None:
            return self.total_amount
        return self._current_payable_amount

    def update_payable_amount(self, amount: Decimal) -> None:
        self._current_payable_amount = amount

    @property
    def total_quantity(self) -> int:
        return sum(item.quantity for item in self.cart_items)


@dataclass
class PromotionResult:
    """单个促销计算结果"""
    promotion_code: str
    strategy_type: str
    discount: Decimal
    applied_items: List[str] = field(default_factory=list)
    message: str = ""
    rewards: List[Dict] = field(default_factory=list)
    tier_details: List[Dict] = field(default_factory=list)
    free_shipping: bool = False
    # 开源扩展：售后分摊明细（仅在需要时填充）
    item_discounts: List[Dict] = field(default_factory=list)
    refund_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CalculationResult:
    """整体计算结果"""
    applied_promotions: List[PromotionResult] = field(default_factory=list)
    total_discount: Decimal = field(default_factory=lambda: Decimal("0"))
    payable_amount: Decimal = field(default_factory=lambda: Decimal("0"))
    original_amount: Decimal = field(default_factory=lambda: Decimal("0"))
    messages: List[str] = field(default_factory=list)
    skipped_rules: List[Dict] = field(default_factory=list)
    coupon_discount: Decimal = field(default_factory=lambda: Decimal("0"))
    used_coupons: List[Dict] = field(default_factory=list)
    shipping_fee: Decimal = field(default_factory=lambda: Decimal("0"))
    # 价格保护冲突信息
    price_protection_conflicts: List[Dict] = field(default_factory=list)
    price_protection_can_proceed: bool = True


@dataclass
class Cart:
    """购物车容器"""
    items: List[CartItem] = field(default_factory=list)

    def add_item(self, item: CartItem) -> None:
        self.items.append(item)

    @property
    def total_amount(self) -> Decimal:
        return sum(item.total_amount for item in self.items)


# ==================== 互斥相关类型 ====================

@dataclass
class MutexGroup:
    """互斥组配置（替代 Django MutexGroup Model）"""
    code: str
    name: str = ""
    description: str = ""
    strategy_types: List[str] = field(default_factory=list)
    is_active: bool = True
    priority: int = 0


@dataclass
class SpecialMutexRule:
    """特殊互斥规则（替代 Django SpecialMutexRule Model）"""
    name: str = ""
    description: str = ""
    rule_a_id: str = ""
    rule_b_id: str = ""
    is_bidirectional: bool = True
    priority_direction: str = "a"       # 'a' 或 'b'，单向互斥时生效
    is_active: bool = True
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None


# ==================== 价格保护相关类型 ====================

@dataclass
class PriceProtectionConfig:
    """价格保护规则配置"""
    # 成本价保护
    enable_cost_protection: bool = True
    min_gross_margin: Decimal = field(default_factory=lambda: Decimal("5.00"))
    cost_protection_action: str = "block"   # block / warn

    # 普通会员价保护
    enable_member_protection: bool = True
    member_price_threshold: Decimal = field(default_factory=lambda: Decimal("95.00"))
    member_protection_action: str = "warn"
    member_protection_levels: List[str] = field(default_factory=list)

    # VIP会员价保护
    enable_vip_protection: bool = True
    vip_price_threshold: Decimal = field(default_factory=lambda: Decimal("95.00"))
    vip_protection_action: str = "warn"
    vip_protection_levels: List[str] = field(default_factory=list)
