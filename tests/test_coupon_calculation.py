"""
券计算测试
"""
from decimal import Decimal

from promotion_engine.coupon_calculation import CouponUsageCalculator
from promotion_engine.types import UsedCoupon


def test_full_reduction_coupon():
    """满减券"""
    calc = CouponUsageCalculator()
    discount, details = calc.calculate(
        promotion_payable=Decimal("400"),
        used_coupons=[
            UsedCoupon(
                code="SAVE50",
                coupon_type="full_reduction",
                discount_value=Decimal("50"),
                min_order_amount=Decimal("300"),
            )
        ],
    )
    assert discount == Decimal("50")
    assert details[0]["status"] == "applied"


def test_percentage_discount_coupon():
    """折扣券"""
    calc = CouponUsageCalculator()
    discount, details = calc.calculate(
        promotion_payable=Decimal("400"),
        used_coupons=[
            UsedCoupon(
                code="DISCOUNT20",
                coupon_type="percentage_discount",
                discount_value=Decimal("0.8"),  # 8折
            )
        ],
    )
    assert discount == Decimal("80.00")


def test_no_threshold_coupon():
    """无门槛券"""
    calc = CouponUsageCalculator()
    discount, details = calc.calculate(
        promotion_payable=Decimal("100"),
        used_coupons=[
            UsedCoupon(
                code="FREE10",
                coupon_type="no_threshold",
                discount_value=Decimal("10"),
            )
        ],
    )
    assert discount == Decimal("10")


def test_tiered_coupon():
    """阶梯券：每满X减Y"""
    calc = CouponUsageCalculator()
    discount, details = calc.calculate(
        promotion_payable=Decimal("600"),
        used_coupons=[
            UsedCoupon(
                code="TIERED",
                coupon_type="tiered",
                tiered_rules=[
                    {"threshold": 300, "discount": 30},
                    {"threshold": 500, "discount": 60},
                ],
            )
        ],
    )
    # 600 >= 500， tiers = 1， discount = 60
    assert discount == Decimal("60.00")


def test_special_price_coupon():
    """特价/兑换券"""
    calc = CouponUsageCalculator()
    discount, details = calc.calculate(
        promotion_payable=Decimal("200"),
        used_coupons=[
            UsedCoupon(
                code="SPECIAL",
                coupon_type="special_price",
                discount_value=Decimal("30"),
            )
        ],
    )
    assert discount == Decimal("30")


def test_combination_mutex():
    """券组合互斥：不同类型只保留优先级最高的"""
    calc = CouponUsageCalculator()
    discount, details = calc.calculate(
        promotion_payable=Decimal("400"),
        used_coupons=[
            UsedCoupon(
                code="A", coupon_type="full_reduction",
                discount_value=Decimal("50"), priority=10,
            ),
            UsedCoupon(
                code="B", coupon_type="percentage_discount",
                discount_value=Decimal("0.8"), priority=5,
            ),
        ],
        combination_rules=[
            {"name": "满减与折扣互斥", "coupon_types": ["full_reduction", "percentage_discount"], "combination_mode": "mutex"}
        ],
    )
    # 互斥规则只保留优先级最高的 A
    assert discount == Decimal("50")
    codes = [d["code"] for d in details if d["status"] == "applied"]
    assert codes == ["A"]
    excluded = [d for d in details if d["status"] == "excluded_mutex"]
    assert len(excluded) == 1
    assert excluded[0]["code"] == "B"


def test_combination_stackable():
    """券组合叠加"""
    calc = CouponUsageCalculator()
    discount, details = calc.calculate(
        promotion_payable=Decimal("400"),
        used_coupons=[
            UsedCoupon(
                code="A", coupon_type="full_reduction",
                discount_value=Decimal("50"), priority=10,
            ),
            UsedCoupon(
                code="B", coupon_type="full_reduction",
                discount_value=Decimal("30"), priority=5,
            ),
        ],
        combination_rules=[
            {"name": "满减叠加", "coupon_types": ["full_reduction"], "combination_mode": "stackable"}
        ],
    )
    assert discount == Decimal("80")


def test_threshold_not_met():
    """未达到使用门槛"""
    calc = CouponUsageCalculator()
    discount, details = calc.calculate(
        promotion_payable=Decimal("200"),
        used_coupons=[
            UsedCoupon(
                code="SAVE50",
                coupon_type="full_reduction",
                discount_value=Decimal("50"),
                min_order_amount=Decimal("300"),
            )
        ],
    )
    assert discount == Decimal("0")
    assert details[0]["status"] == "skipped_threshold"


def test_multiple_coupons_priority():
    """多张券按优先级降序抵扣"""
    calc = CouponUsageCalculator()
    discount, details = calc.calculate(
        promotion_payable=Decimal("400"),
        used_coupons=[
            UsedCoupon(
                code="LOW", coupon_type="full_reduction",
                discount_value=Decimal("20"), priority=1,
            ),
            UsedCoupon(
                code="HIGH", coupon_type="full_reduction",
                discount_value=Decimal("50"), priority=10,
            ),
        ],
    )
    assert discount == Decimal("70")
    applied_order = [d["code"] for d in details if d["status"] == "applied"]
    assert applied_order == ["HIGH", "LOW"]


def test_payable_exhausted():
    """应付金额被抵扣完后停止"""
    calc = CouponUsageCalculator()
    discount, details = calc.calculate(
        promotion_payable=Decimal("50"),
        used_coupons=[
            UsedCoupon(
                code="BIG", coupon_type="full_reduction",
                discount_value=Decimal("100"), priority=10,
            ),
            UsedCoupon(
                code="SMALL", coupon_type="full_reduction",
                discount_value=Decimal("30"), priority=5,
            ),
        ],
    )
    # BIG 抵扣 50 后应付为 0，SMALL 被跳过
    assert discount == Decimal("50")
    assert any(d["code"] == "SMALL" and d["status"] == "skipped_zero" for d in details)
