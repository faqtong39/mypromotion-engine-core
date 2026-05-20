"""
售后分摊测试
"""
from decimal import Decimal

from promotion_engine.refund import RefundStrategy, calculate_item_discounts, calculate_refund


def test_proportional_allocation():
    """按比例分摊测试"""
    order_items = [
        {"sku": "A001", "price": "100.00", "quantity": 2},
        {"sku": "A002", "price": "200.00", "quantity": 1},
    ]
    result = calculate_item_discounts(
        order_items=order_items,
        total_discount=Decimal("50.00"),
        strategy=RefundStrategy.PROPORTIONAL.value,
    )

    assert len(result) == 2
    assert result[0]["sku"] == "A001"
    assert result[0]["original_price"] == "200.00"
    # 200/400 * 50 = 25
    assert result[0]["allocated_discount"] == "25.00"
    assert result[0]["payable"] == "175.00"
    assert result[1]["allocated_discount"] == "25.00"
    assert result[1]["payable"] == "175.00"


def test_keep_discount():
    """优惠不退还测试"""
    order_items = [
        {"sku": "B001", "price": "100.00", "quantity": 1},
    ]
    result = calculate_item_discounts(
        order_items=order_items,
        total_discount=Decimal("20.00"),
        strategy=RefundStrategy.KEEP_DISCOUNT.value,
    )

    assert result[0]["allocated_discount"] == "0.00"
    assert result[0]["payable"] == "100.00"
    assert result[0]["strategy"] == RefundStrategy.KEEP_DISCOUNT.value


def test_full_refund_discount():
    """优惠全退测试"""
    order_items = [
        {"sku": "C001", "price": "100.00", "quantity": 1},
        {"sku": "C002", "price": "100.00", "quantity": 1},
    ]
    result = calculate_item_discounts(
        order_items=order_items,
        total_discount=Decimal("30.00"),
        strategy=RefundStrategy.FULL_REFUND_DISCOUNT.value,
    )

    assert result[0]["strategy"] == RefundStrategy.FULL_REFUND_DISCOUNT.value
    assert result[0]["allocated_discount"] == "15.00"


def test_calculate_refund():
    """退款计算测试"""
    order_items = [
        {"sku": "D001", "price": "100.00", "quantity": 2},
        {"sku": "D002", "price": "200.00", "quantity": 1},
    ]
    item_discounts = calculate_item_discounts(
        order_items=order_items,
        total_discount=Decimal("50.00"),
    )

    # 退 1 件 D001
    refund_result = calculate_refund(
        order_items=order_items,
        item_discounts=item_discounts,
        refund_items=[{"sku": "D001", "quantity": 1}],
        total_paid=Decimal("350.00"),
    )

    # D001 原价 100，分摊优惠 25/2=12.5，退款 87.50
    assert refund_result["refund_amount"] == "87.50"
    assert Decimal(refund_result["remaining_payable"]) == Decimal("262.50")


def test_refund_capped():
    """退款截断测试"""
    order_items = [
        {"sku": "E001", "price": "100.00", "quantity": 1},
    ]
    item_discounts = calculate_item_discounts(
        order_items=order_items,
        total_discount=Decimal("10.00"),
    )

    # 已退 80，只剩 10 可退
    refund_result = calculate_refund(
        order_items=order_items,
        item_discounts=item_discounts,
        refund_items=[{"sku": "E001", "quantity": 1}],
        total_paid=Decimal("90.00"),
        refunded_total=Decimal("80.00"),
    )

    assert refund_result["refund_amount"] == "10.00"
    assert refund_result["capped"] is True
