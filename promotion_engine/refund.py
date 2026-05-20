"""
售后退款分摊计算（纯函数版本，无数据库依赖）

提供三种退款分摊策略的数学实现。
"""
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Dict, List, Optional


class RefundStrategy(Enum):
    """退款分摊策略"""
    PROPORTIONAL = "proportional"           # 按比例分摊（默认）
    KEEP_DISCOUNT = "keep_discount"         # 优惠不退还
    FULL_REFUND_DISCOUNT = "full_refund_discount"  # 优惠全退


def calculate_item_discounts(
    order_items: List[Dict],
    total_discount: Decimal,
    strategy: str = "proportional",
) -> List[Dict]:
    """
    根据退款策略计算商品级分摊明细

    Args:
        order_items: 订单商品列表（含 sku, price, quantity）
        total_discount: 总优惠金额
        strategy: 分摊策略（proportional / keep_discount / full_refund_discount）

    Returns:
        item_discounts 列表，每个元素含：
            - sku
            - quantity
            - original_price
            - allocated_discount
            - payable
            - strategy
    """
    if strategy == RefundStrategy.KEEP_DISCOUNT.value:
        return [
            {
                "sku": item["sku"],
                "quantity": item.get("quantity", 1),
                "original_price": str(Decimal(str(item["price"])) * item.get("quantity", 1)),
                "allocated_discount": "0.00",
                "payable": str(Decimal(str(item["price"])) * item.get("quantity", 1)),
                "strategy": RefundStrategy.KEEP_DISCOUNT.value,
            }
            for item in order_items
        ]

    if strategy == RefundStrategy.FULL_REFUND_DISCOUNT.value:
        result = _calculate_proportional(order_items, total_discount)
        for d in result:
            d["strategy"] = RefundStrategy.FULL_REFUND_DISCOUNT.value
        return result

    # 默认 proportional
    return _calculate_proportional(order_items, total_discount)


def _calculate_proportional(order_items: List[Dict], total_discount: Decimal) -> List[Dict]:
    """按比例分摊优惠"""
    total_amount = sum(Decimal(str(item["price"])) * item.get("quantity", 1) for item in order_items)
    item_discounts = []
    remaining_discount = Decimal(str(total_discount))

    for i, item in enumerate(order_items):
        item_total = Decimal(str(item["price"])) * item.get("quantity", 1)

        if i == len(order_items) - 1:
            allocated = remaining_discount
        else:
            if total_amount > 0:
                ratio = item_total / total_amount
                allocated = (Decimal(str(total_discount)) * ratio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            else:
                allocated = Decimal("0")
            remaining_discount -= allocated

        item_discounts.append({
            "sku": item["sku"],
            "quantity": item.get("quantity", 1),
            "original_price": str(item_total.quantize(Decimal("0.01"))),
            "allocated_discount": str(allocated.quantize(Decimal("0.01"))),
            "payable": str((item_total - allocated).quantize(Decimal("0.01"))),
            "strategy": RefundStrategy.PROPORTIONAL.value,
        })

    return item_discounts


def calculate_refund(
    order_items: List[Dict],
    item_discounts: List[Dict],
    refund_items: List[Dict],
    total_paid: Decimal,
    refunded_total: Decimal = Decimal("0"),
) -> Dict:
    """
    计算本次退款金额

    Args:
        order_items: 原始订单商品
        item_discounts: 商品级分摊明细（来自 calculate_item_discounts）
        refund_items: 本次退款商品（含 sku, quantity）
        total_paid: 订单实付金额
        refunded_total: 已退款累计金额

    Returns:
        {
            "refund_amount": str,
            "remaining_payable": str,
            "refunded_total": str,
            "refund_items": List[Dict],
        }
    """
    item_discounts_map = {d["sku"]: d for d in item_discounts}
    original_qty_map = {item["sku"]: item.get("quantity", 1) for item in order_items}

    remaining = total_paid - refunded_total
    if remaining <= 0:
        return {
            "refund_amount": "0.00",
            "remaining_payable": str(remaining.quantize(Decimal("0.01"))),
            "refunded_total": str(refunded_total.quantize(Decimal("0.01"))),
            "refund_items": [],
            "message": "该订单已无剩余可退金额",
        }

    refund_original = Decimal("0")
    allocated_discount = Decimal("0")
    item_details = []

    for item in refund_items:
        sku = item["sku"]
        qty = item.get("quantity", 1)
        detail = item_discounts_map.get(sku)
        if not detail:
            continue
        original_qty = original_qty_map.get(sku, 1)

        ratio = Decimal(str(qty)) / Decimal(str(original_qty)) if original_qty > 0 else Decimal("1")
        item_original = (Decimal(str(detail.get("original_price", "0"))) * ratio).quantize(Decimal("0.01"))

        if detail.get("strategy") == RefundStrategy.FULL_REFUND_DISCOUNT.value:
            item_allocated = Decimal(str(detail.get("allocated_discount", "0"))).quantize(Decimal("0.01"))
        else:
            item_allocated = (Decimal(str(detail.get("allocated_discount", "0"))) * ratio).quantize(Decimal("0.01"))

        refund_original += item_original
        allocated_discount += item_allocated

        item_details.append({
            "sku": sku,
            "quantity": qty,
            "original_price": str(item_original),
            "allocated_discount": str(item_allocated),
            "refund_amount": str(item_original - item_allocated),
        })

    refund_amount = refund_original - allocated_discount
    was_capped = False
    cap_reason = ""
    if refund_amount > remaining:
        was_capped = True
        cap_reason = f"计算退款金额 {refund_amount} 超过剩余可退金额 {remaining}，已截断"
        refund_amount = remaining
    refund_amount = max(refund_amount, Decimal("0"))

    # 截断后按比例重新分配 item_details
    if was_capped and item_details:
        total_calculated = sum(Decimal(d["refund_amount"]) for d in item_details)
        if total_calculated > 0:
            distributed = Decimal("0")
            for i, d in enumerate(item_details):
                if i == len(item_details) - 1:
                    new_amount = (refund_amount - distributed).quantize(Decimal("0.01"))
                else:
                    ratio = Decimal(d["refund_amount"]) / total_calculated
                    new_amount = (refund_amount * ratio).quantize(Decimal("0.01"))
                    distributed += new_amount
                d["refund_amount"] = str(new_amount)
                d["capped"] = True

    result = {
        "refund_amount": str(refund_amount.quantize(Decimal("0.01"))),
        "remaining_payable": str((remaining - refund_amount).quantize(Decimal("0.01"))),
        "refunded_total": str((refunded_total + refund_amount).quantize(Decimal("0.01"))),
        "refund_items": item_details,
    }
    if was_capped:
        result["capped"] = True
        result["cap_reason"] = cap_reason
    return result
