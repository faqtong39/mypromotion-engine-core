"""
引擎核心全面测试
"""
from decimal import Decimal

from promotion_engine import Engine, Cart, CartItem, Rule
from promotion_engine.types import (
    CalculationContext,
    RuleAction,
    RuleCondition,
    RuleScope,
    SpecialMutexRule,
)


# ==================== 基础促销计算 ====================

def test_full_reduction_basic():
    """满减基础测试"""
    cart = Cart()
    cart.add_item(CartItem(sku="A001", price=Decimal("199.00"), quantity=2))
    cart.add_item(CartItem(sku="A002", price=Decimal("89.00"), quantity=1))

    rule = Rule.full_reduction(threshold=300, amount=50)
    result = Engine().calculate(CalculationContext(cart_items=cart.items), [rule])

    assert result.original_amount == Decimal("487.00")
    assert result.total_discount == Decimal("50.00")
    assert result.payable_amount == Decimal("437.00")
    assert len(result.applied_promotions) == 1
    assert len(result.skipped_rules) == 0


def test_full_reduction_not_met():
    """满减门槛不满足"""
    cart = Cart()
    cart.add_item(CartItem(sku="A001", price=Decimal("100.00"), quantity=1))

    rule = Rule.full_reduction(threshold=300, amount=50)
    result = Engine().calculate(CalculationContext(cart_items=cart.items), [rule])

    assert len(result.applied_promotions) == 0
    assert result.skipped_rules[0]["reason"] == "conditions_not_met"


def test_percentage_discount_basic():
    """百分比折扣基础测试"""
    cart = Cart()
    cart.add_item(CartItem(sku="B001", price=Decimal("299.00"), quantity=1))

    rule = Rule.percentage_discount(percentage=90)
    result = Engine().calculate(CalculationContext(cart_items=cart.items), [rule])

    assert result.original_amount == Decimal("299.00")
    assert result.total_discount == Decimal("29.90")
    assert result.payable_amount == Decimal("269.10")


def test_percentage_discount_with_scope():
    """百分比折扣 + 范围过滤"""
    cart = Cart()
    cart.add_item(CartItem(sku="S001", price=Decimal("100.00"), quantity=1, category_id="cat1"))
    cart.add_item(CartItem(sku="S002", price=Decimal("200.00"), quantity=1, category_id="cat2"))

    rule = Rule.percentage_discount(
        percentage=50,
        scopes=[RuleScope(scope_type="category_items", config={"category_ids": ["cat1"]})],
    )
    result = Engine().calculate(CalculationContext(cart_items=cart.items), [rule])

    assert result.total_discount == Decimal("50.00")
    assert result.applied_promotions[0].applied_items == ["S001"]


def test_fixed_price_basic():
    """固定价基础测试"""
    cart = Cart()
    cart.add_item(CartItem(sku="P001", price=Decimal("200.00"), quantity=2))

    rule = Rule.fixed_price(price=Decimal("150.00"))
    result = Engine().calculate(CalculationContext(cart_items=cart.items), [rule])

    assert result.total_discount == Decimal("100.00")
    assert result.payable_amount == Decimal("300.00")


def test_fixed_price_higher_than_original():
    """固定价高于原价时不产生优惠"""
    cart = Cart()
    cart.add_item(CartItem(sku="P002", price=Decimal("100.00"), quantity=1))

    rule = Rule.fixed_price(price=Decimal("150.00"))
    result = Engine().calculate(CalculationContext(cart_items=cart.items), [rule])

    assert result.total_discount == Decimal("0.00")


def test_tiered_price_by_quantity():
    """阶梯价（按数量）测试"""
    cart = Cart()
    cart.add_item(CartItem(sku="T001", price=Decimal("100.00"), quantity=5))

    rule = Rule.tiered_price(tiers=[
        {"quantity": 1, "price": 100},
        {"quantity": 3, "price": 90},
        {"quantity": 5, "price": 80},
    ])
    result = Engine().calculate(CalculationContext(cart_items=cart.items), [rule])

    # 5件 × 80元 = 400元，原价500元，优惠100元
    assert result.total_discount == Decimal("100.00")
    assert result.payable_amount == Decimal("400.00")


def test_tiered_amount_by_threshold():
    """阶梯优惠（按金额）测试"""
    cart = Cart()
    cart.add_item(CartItem(sku="T002", price=Decimal("250.00"), quantity=1))

    rule = Rule.tiered_amount(tiers=[
        {"threshold": 100, "amount": 10},
        {"threshold": 200, "amount": 30},
    ])
    result = Engine().calculate(CalculationContext(cart_items=cart.items), [rule])

    assert result.total_discount == Decimal("30.00")
    assert result.payable_amount == Decimal("220.00")


def test_free_shipping():
    """免运费基础测试"""
    cart = Cart()
    cart.add_item(CartItem(sku="F001", price=Decimal("50.00"), quantity=1))

    rule = Rule.free_shipping()
    result = Engine().calculate(
        CalculationContext(cart_items=cart.items, shipping_fee=Decimal("10.00")),
        [rule],
    )

    assert len(result.applied_promotions) == 1
    assert result.applied_promotions[0].free_shipping is True


def test_first_order():
    """首单优惠测试"""
    cart = Cart()
    cart.add_item(CartItem(sku="FO001", price=Decimal("200.00"), quantity=1))

    rule = Rule.first_order(amount=20)
    # 非首单用户
    result = Engine().calculate(CalculationContext(cart_items=cart.items, is_first_order=False), [rule])
    assert len(result.applied_promotions) == 0

    # 首单用户
    result = Engine().calculate(CalculationContext(cart_items=cart.items, is_first_order=True), [rule])
    assert result.total_discount == Decimal("20.00")
    assert result.payable_amount == Decimal("180.00")


def test_member_exclusive():
    """会员专享折扣测试"""
    cart = Cart()
    cart.add_item(CartItem(sku="M001", price=Decimal("200.00"), quantity=1))

    rule = Rule.member_exclusive(percentage=80, member_groups=["vip"])
    # 非会员
    result = Engine().calculate(CalculationContext(cart_items=cart.items, user_group="normal"), [rule])
    assert len(result.applied_promotions) == 0

    # VIP会员
    result = Engine().calculate(CalculationContext(cart_items=cart.items, user_group="vip"), [rule])
    assert result.total_discount == Decimal("40.00")
    assert result.payable_amount == Decimal("160.00")


def test_pre_sale():
    """预售定金膨胀测试"""
    cart = Cart()
    cart.add_item(CartItem(sku="PS001", price=Decimal("500.00"), quantity=1))

    rule = Rule.pre_sale(deposit=100, expansion_ratio=2)
    # 非预售期
    result = Engine().calculate(CalculationContext(cart_items=cart.items), [rule])
    assert len(result.applied_promotions) == 0

    # 预售期，已付定金
    result = Engine().calculate(
        CalculationContext(cart_items=cart.items, extra={"is_pre_sale": True, "deposit_paid": 100}),
        [rule],
    )
    assert result.total_discount == Decimal("200.00")
    assert result.payable_amount == Decimal("300.00")


def test_bundle_offer():
    """组合优惠测试（两件组合价 200，即每件 100）"""
    cart = Cart()
    cart.add_item(CartItem(sku="B001", price=Decimal("100.00"), quantity=1))
    cart.add_item(CartItem(sku="B002", price=Decimal("150.00"), quantity=1))

    rule = Rule.bundle_offer(price=Decimal("100.00"), skus=["B001", "B002"])
    result = Engine().calculate(CalculationContext(cart_items=cart.items), [rule])

    assert result.total_discount == Decimal("50.00")


# ==================== 互斥检查 ====================

def test_mutex_group_by_strategy_type():
    """策略类型互斥组测试"""
    cart = Cart()
    cart.add_item(CartItem(sku="C001", price=Decimal("500.00"), quantity=1))

    rule1 = Rule.full_reduction(threshold=400, amount=100, promotion_code="R1", priority=100)
    rule2 = Rule.full_reduction(threshold=400, amount=50, promotion_code="R2", priority=90)

    engine = Engine(mutex_groups={
        "discount": {"strategies": ["full_reduction"], "priority": 100}
    })
    result = engine.calculate(CalculationContext(cart_items=cart.items), [rule1, rule2])

    assert len(result.applied_promotions) == 1
    assert result.applied_promotions[0].promotion_code == "R1"
    assert result.skipped_rules[0]["reason"] == "mutex"


def test_mutex_special_bidirectional():
    """双向特殊互斥测试"""
    cart = Cart()
    cart.add_item(CartItem(sku="C002", price=Decimal("500.00"), quantity=1))

    rule1 = Rule.full_reduction(threshold=400, amount=100, promotion_code="R1", priority=100)
    rule2 = Rule.full_reduction(threshold=400, amount=50, promotion_code="R2", priority=90)

    engine = Engine(
        special_mutex_rules=[
            SpecialMutexRule(rule_a_id="R1", rule_b_id="R2", is_bidirectional=True, is_active=True)
        ]
    )
    result = engine.calculate(CalculationContext(cart_items=cart.items), [rule1, rule2])

    assert len(result.applied_promotions) == 1
    assert result.skipped_rules[0]["reason"] == "mutex"


def test_mutex_replace_unidirectional():
    """单向互斥替换回滚测试：高优先级先应用，低优先级被互斥跳过"""
    cart = Cart()
    cart.add_item(CartItem(sku="C003", price=Decimal("500.00"), quantity=1))

    # R2 优先级高先应用，R1 优先级低后被互斥
    rule1 = Rule.full_reduction(threshold=400, amount=50, promotion_code="R1", priority=50)
    rule2 = Rule.full_reduction(threshold=400, amount=100, promotion_code="R2", priority=100)

    engine = Engine(
        mutex_groups={"discount": {"strategies": ["full_reduction"], "priority": 100}},
        special_mutex_rules=[
            SpecialMutexRule(
                rule_a_id="R2", rule_b_id="R1",
                is_bidirectional=False, priority_direction="a", is_active=True
            )
        ]
    )
    result = engine.calculate(CalculationContext(cart_items=cart.items), [rule1, rule2])

    # R2（priority=100）先计算，应付 = 400
    # R1（priority=50）后计算，被单向互斥跳过
    assert len(result.applied_promotions) == 1
    assert result.applied_promotions[0].promotion_code == "R2"
    assert result.applied_promotions[0].discount == Decimal("100.00")
    assert result.payable_amount == Decimal("400.00")
    assert any(r["reason"] == "mutex" for r in result.skipped_rules)


def test_mutex_stack_config_blacklist():
    """stack_config 黑名单互斥测试"""
    cart = Cart()
    cart.add_item(CartItem(sku="C004", price=Decimal("500.00"), quantity=1))

    rule1 = Rule.full_reduction(threshold=400, amount=100, promotion_code="R1", priority=100)
    rule2 = Rule.full_reduction(threshold=400, amount=50, promotion_code="R2", priority=90, stack_config={"mutex_with": ["R1"]})

    engine = Engine()
    result = engine.calculate(CalculationContext(cart_items=cart.items), [rule1, rule2])

    assert len(result.applied_promotions) == 1
    assert result.skipped_rules[0]["reason"] == "mutex"


def test_mutex_stack_config_whitelist():
    """stack_config 白名单叠加测试"""
    cart = Cart()
    cart.add_item(CartItem(sku="C005", price=Decimal("500.00"), quantity=1))

    rule1 = Rule.full_reduction(threshold=400, amount=100, promotion_code="R1", priority=100)
    rule2 = Rule.percentage_discount(percentage=90, promotion_code="R2", priority=90, stack_config={"stackable_with": ["R1"]})

    engine = Engine(mutex_groups={
        "discount": {"strategies": ["full_reduction", "full_discount"], "priority": 100}
    })
    result = engine.calculate(CalculationContext(cart_items=cart.items), [rule1, rule2])

    assert len(result.applied_promotions) == 2


def test_mutex_force_stackable():
    """强制叠加测试"""
    cart = Cart()
    cart.add_item(CartItem(sku="C006", price=Decimal("500.00"), quantity=1))

    rule1 = Rule.full_reduction(threshold=400, amount=100, promotion_code="R1", priority=100)
    rule2 = Rule.full_reduction(threshold=400, amount=50, promotion_code="R2", priority=90, stack_config={"force_stackable": True})

    engine = Engine(mutex_groups={
        "discount": {"strategies": ["full_reduction"], "priority": 100}
    })
    result = engine.calculate(CalculationContext(cart_items=cart.items), [rule1, rule2])

    assert len(result.applied_promotions) == 2


# ==================== 计算顺序与最优 ====================

def test_calculation_order_promotions_first():
    """促销先计算测试"""
    cart = Cart()
    cart.add_item(CartItem(sku="D001", price=Decimal("400.00"), quantity=1))

    rule = Rule.percentage_discount(percentage=80, promotion_code="DISCOUNT80")
    result = Engine().calculate(
        CalculationContext(cart_items=cart.items, calculation_order=["promotions", "coupons"]),
        [rule],
    )
    assert result.payable_amount == Decimal("320.00")


def test_calculation_order_optimal():
    """最优顺序自动选择测试"""
    cart = Cart()
    cart.add_item(CartItem(sku="D002", price=Decimal("400.00"), quantity=1))

    # 只有一个规则，optimal 和 promotions-first 结果相同
    rule = Rule.full_reduction(threshold=300, amount=50, promotion_code="FR50")
    result = Engine().calculate(
        CalculationContext(cart_items=cart.items, calculation_order="optimal"),
        [rule],
    )
    assert result.payable_amount == Decimal("350.00")


# ==================== 范围过滤 ====================

def test_scope_specific_items():
    """指定 SKU 范围测试"""
    cart = Cart()
    cart.add_item(CartItem(sku="S001", price=Decimal("100.00"), quantity=1))
    cart.add_item(CartItem(sku="S002", price=Decimal("200.00"), quantity=1))

    rule = Rule.full_reduction(
        threshold=50, amount=10, promotion_code="SKU_ONLY",
        scopes=[RuleScope(scope_type="specific_items", config={"skus": ["S001"]})],
    )
    result = Engine().calculate(CalculationContext(cart_items=cart.items), [rule])

    assert result.total_discount == Decimal("10.00")
    assert result.applied_promotions[0].applied_items == ["S001"]


def test_scope_except_items():
    """排除 SKU 范围测试"""
    cart = Cart()
    cart.add_item(CartItem(sku="S001", price=Decimal("100.00"), quantity=1))
    cart.add_item(CartItem(sku="S002", price=Decimal("200.00"), quantity=1))

    rule = Rule.percentage_discount(
        percentage=50, promotion_code="EXCEPT",
        scopes=[RuleScope(scope_type="except_items", config={"except_skus": ["S002"]})],
    )
    result = Engine().calculate(CalculationContext(cart_items=cart.items), [rule])

    assert result.total_discount == Decimal("50.00")
    assert result.applied_promotions[0].applied_items == ["S001"]


def test_scope_tag_items():
    """标签范围测试"""
    cart = Cart()
    cart.add_item(CartItem(sku="S001", price=Decimal("100.00"), quantity=1, tags=["hot"]))
    cart.add_item(CartItem(sku="S002", price=Decimal("200.00"), quantity=1, tags=["new"]))

    rule = Rule.percentage_discount(
        percentage=50, promotion_code="TAG",
        scopes=[RuleScope(scope_type="tag_items", config={"tags": ["hot"]})],
    )
    result = Engine().calculate(CalculationContext(cart_items=cart.items), [rule])

    assert result.total_discount == Decimal("50.00")


# ==================== 边界条件 ====================

def test_empty_cart():
    """空购物车测试"""
    rule = Rule.full_reduction(threshold=300, amount=50)
    result = Engine().calculate(CalculationContext(cart_items=[]), [rule])

    assert result.payable_amount == Decimal("0.00")
    assert len(result.applied_promotions) == 0


def test_zero_discount():
    """零金额优惠测试"""
    cart = Cart()
    cart.add_item(CartItem(sku="Z001", price=Decimal("100.00"), quantity=1))

    rule = Rule.full_reduction(threshold=0, amount=0)
    result = Engine().calculate(CalculationContext(cart_items=cart.items), [rule])

    assert result.total_discount == Decimal("0.00")


def test_negative_discount_protection():
    """负折扣保护测试：固定价高于原价时不产生负折扣"""
    cart = Cart()
    cart.add_item(CartItem(sku="N001", price=Decimal("50.00"), quantity=1))

    rule = Rule.fixed_price(price=Decimal("100.00"))
    result = Engine().calculate(CalculationContext(cart_items=cart.items), [rule])

    assert result.total_discount == Decimal("0.00")


# ==================== 多规则组合 ====================

def test_multiple_rules_stacking():
    """多规则叠加测试（不同策略类型，无互斥）"""
    cart = Cart()
    cart.add_item(CartItem(sku="M001", price=Decimal("500.00"), quantity=1))

    rule1 = Rule.full_reduction(threshold=400, amount=100, promotion_code="FR100", priority=100)
    rule2 = Rule.free_shipping(threshold=0, promotion_code="FREE_SHIP", priority=50)

    result = Engine().calculate(CalculationContext(cart_items=cart.items), [rule1, rule2])

    assert len(result.applied_promotions) == 2
    assert result.total_discount == Decimal("100.00")
    assert any(p.free_shipping for p in result.applied_promotions)


def test_priority_order():
    """优先级排序测试：高优先级先计算"""
    cart = Cart()
    cart.add_item(CartItem(sku="P001", price=Decimal("500.00"), quantity=1))

    rule1 = Rule.full_reduction(threshold=400, amount=200, promotion_code="HIGH", priority=200)
    rule2 = Rule.full_reduction(threshold=400, amount=100, promotion_code="LOW", priority=100)

    engine = Engine(mutex_groups={
        "discount": {"strategies": ["full_reduction"], "priority": 100}
    })
    result = engine.calculate(CalculationContext(cart_items=cart.items), [rule1, rule2])

    assert result.applied_promotions[0].promotion_code == "HIGH"
    assert result.applied_promotions[0].discount == Decimal("200.00")


# ==================== 条件逻辑 ====================

def test_condition_or_logic():
    """OR 条件逻辑测试"""
    cart = Cart()
    cart.add_item(CartItem(sku="O001", price=Decimal("100.00"), quantity=1))

    rule = Rule(
        promotion_code="OR_TEST",
        strategy_type="full_reduction",
        priority=100,
        conditions=[
            RuleCondition(condition_type="min_order_amount", config={"amount": 500}, logic_operator="OR"),
            RuleCondition(condition_type="min_quantity", config={"quantity": 1}),
        ],
        actions=[RuleAction(action_type="fixed_amount_reduction", config={"amount": 10})],
    )
    result = Engine().calculate(CalculationContext(cart_items=cart.items), [rule])

    assert len(result.applied_promotions) == 1
    assert result.total_discount == Decimal("10.00")


def test_condition_and_logic():
    """AND 条件逻辑测试（默认）"""
    cart = Cart()
    cart.add_item(CartItem(sku="A001", price=Decimal("100.00"), quantity=1))

    rule = Rule(
        promotion_code="AND_TEST",
        strategy_type="full_reduction",
        priority=100,
        conditions=[
            RuleCondition(condition_type="min_order_amount", config={"amount": 50}, logic_operator="AND"),
            RuleCondition(condition_type="min_quantity", config={"quantity": 2}),
        ],
        actions=[RuleAction(action_type="fixed_amount_reduction", config={"amount": 10})],
    )
    result = Engine().calculate(CalculationContext(cart_items=cart.items), [rule])

    assert len(result.applied_promotions) == 0
    assert result.skipped_rules[0]["reason"] == "conditions_not_met"
