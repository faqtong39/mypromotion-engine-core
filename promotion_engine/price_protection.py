"""
价格保护检查（纯函数版本，无数据库依赖）

输入商品列表 + 保护规则配置，输出冲突信息。
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional


def check_price_protection(
    items: List[Dict],
    config: Optional[Dict] = None,
    user_level: Optional[str] = None,
) -> Dict:
    """
    检查价格保护

    Args:
        items: 商品列表，每项包含：
            - sku: 商品编码
            - sku_name: 商品名称（可选）
            - sale_price: 促销价（Decimal/str/float）
            - cost_price: 成本价（可选）
            - member_price: 普通会员价（可选）
            - vip_price: VIP会员价（可选）
        config: 价格保护规则配置
        user_level: 用户会员等级编码（如 'member', 'vip'），用于匹配对应保护

    Returns:
        {
            'has_conflict': bool,
            'conflicts': List[Dict],
            'can_proceed': bool,
        }
    """
    if not config:
        return {"has_conflict": False, "conflicts": [], "can_proceed": True}

    conflicts = []

    for item in items:
        # 成本价保护
        if config.get("enable_cost_protection", True):
            conflict = _check_cost_protection(item, config)
            if conflict:
                conflicts.append(conflict)

        # 会员价保护（根据用户等级匹配）
        if user_level:
            conflict = _check_member_protection_by_level(item, config, user_level)
            if conflict:
                conflicts.append(conflict)
        else:
            if config.get("enable_member_protection", True):
                conflict = _check_member_protection(item, config, label="普通会员价", protection_type="member_protection")
                if conflict:
                    conflicts.append(conflict)
            if config.get("enable_vip_protection", True):
                conflict = _check_vip_protection(item, config)
                if conflict:
                    conflicts.append(conflict)

    has_block = any(c["action"] == "block" for c in conflicts)
    return {
        "has_conflict": len(conflicts) > 0,
        "conflicts": conflicts,
        "can_proceed": not has_block,
    }


def _check_cost_protection(item: Dict, config: Dict) -> Optional[Dict]:
    """成本价保护检测"""
    cost_price = item.get("cost_price")
    sale_price = item.get("sale_price")
    if not cost_price or not sale_price:
        return None

    try:
        cost = Decimal(str(cost_price))
        sale = Decimal(str(sale_price))
        margin = Decimal(str(config.get("min_gross_margin", 5)))
    except Exception:
        return None

    if cost <= 0:
        return None

    min_price = cost * (1 + margin / 100)
    min_price = min_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if sale < min_price:
        actual_margin = ((sale - cost) / cost * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        return {
            "type": "cost_protection",
            "type_display": "成本价保护",
            "sku": item.get("sku", ""),
            "sku_name": item.get("sku_name", ""),
            "sale_price": str(sale),
            "cost_price": str(cost),
            "min_price": str(min_price),
            "gross_margin": f"{actual_margin}%",
            "required_margin": f"{margin}%",
            "action": config.get("cost_protection_action", "block"),
            "message": f"售价低于成本价保护线（毛利率要求{margin}%，实际{actual_margin}%）",
        }
    return None


def _check_member_protection(item: Dict, config: Dict, label: str = "普通会员价", protection_type: str = "member_protection") -> Optional[Dict]:
    """普通会员价保护检测"""
    member_price = item.get("member_price")
    sale_price = item.get("sale_price")
    if not member_price or not sale_price:
        return None
    return _do_price_protection_check(
        item=item,
        price_value=member_price,
        threshold=config.get("member_price_threshold", Decimal("95.00")),
        price_label=label,
        protection_type=protection_type,
        action=config.get("member_protection_action", "warn"),
    )


def _check_vip_protection(item: Dict, config: Dict) -> Optional[Dict]:
    """VIP会员价保护检测"""
    vip_price = item.get("vip_price")
    sale_price = item.get("sale_price")
    if not vip_price or not sale_price:
        return None
    return _do_price_protection_check(
        item=item,
        price_value=vip_price,
        threshold=config.get("vip_price_threshold", Decimal("95.00")),
        price_label="VIP会员价",
        protection_type="vip_protection",
        action=config.get("vip_protection_action", "warn"),
    )


def _check_member_protection_by_level(item: Dict, config: Dict, user_level: str) -> Optional[Dict]:
    """根据用户等级匹配对应的价格保护"""
    member_levels = config.get("member_protection_levels", [])
    vip_levels = config.get("vip_protection_levels", [])

    if user_level in member_levels and config.get("enable_member_protection", True):
        return _check_member_protection(item, config)
    if user_level in vip_levels and config.get("enable_vip_protection", True):
        return _check_vip_protection(item, config)
    return None


def _do_price_protection_check(
    item: Dict,
    price_value,
    threshold,
    price_label: str,
    protection_type: str,
    action: str,
) -> Optional[Dict]:
    """统一的价格保护检测逻辑"""
    sale_price = item.get("sale_price")
    try:
        member = Decimal(str(price_value))
        sale = Decimal(str(sale_price))
        threshold_dec = Decimal(str(threshold))
    except Exception:
        return None

    if member <= 0:
        return None

    min_price = member * (threshold_dec / 100)
    min_price = min_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if sale < min_price:
        actual_ratio = (sale / member * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        return {
            "type": protection_type,
            "type_display": f"{price_label}保护",
            "sku": item.get("sku", ""),
            "sku_name": item.get("sku_name", ""),
            "sale_price": str(sale),
            "member_price": str(member),
            "min_price": str(min_price),
            "actual_ratio": f"{actual_ratio}%",
            "threshold": f"{threshold}%",
            "action": action,
            "message": f"促销价低于{price_label}保护线（阈值{threshold}%，实际{actual_ratio}%）",
        }
    return None
