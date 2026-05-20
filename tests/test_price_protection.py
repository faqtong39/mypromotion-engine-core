"""
价格保护测试
"""
from decimal import Decimal

from promotion_engine.price_protection import check_price_protection


def test_cost_protection_block():
    """成本价保护拦截测试"""
    items = [
        {"sku": "SKU001", "sale_price": "90.00", "cost_price": "100.00", "sku_name": "商品A"},
    ]
    config = {
        "enable_cost_protection": True,
        "min_gross_margin": "5.00",
        "cost_protection_action": "block",
    }
    result = check_price_protection(items, config)

    assert result["has_conflict"] is True
    assert result["can_proceed"] is False
    assert len(result["conflicts"]) == 1
    assert result["conflicts"][0]["type"] == "cost_protection"
    assert result["conflicts"][0]["action"] == "block"


def test_cost_protection_ok():
    """成本价保护通过测试"""
    items = [
        {"sku": "SKU002", "sale_price": "120.00", "cost_price": "100.00"},
    ]
    config = {
        "enable_cost_protection": True,
        "min_gross_margin": "5.00",
    }
    result = check_price_protection(items, config)

    assert result["has_conflict"] is False
    assert result["can_proceed"] is True


def test_member_price_protection_warn():
    """会员价保护警告测试"""
    items = [
        {"sku": "SKU003", "sale_price": "90.00", "member_price": "100.00"},
    ]
    config = {
        "enable_member_protection": True,
        "member_price_threshold": "95.00",
        "member_protection_action": "warn",
    }
    result = check_price_protection(items, config)

    assert result["has_conflict"] is True
    assert result["can_proceed"] is True  # warn 不拦截
    assert result["conflicts"][0]["action"] == "warn"


def test_user_level_matching():
    """用户等级匹配测试"""
    items = [
        {"sku": "SKU004", "sale_price": "91.00", "member_price": "100.00", "vip_price": "95.00"},
    ]
    config = {
        "enable_member_protection": True,
        "member_price_threshold": "95.00",
        "member_protection_levels": ["member"],
        "enable_vip_protection": True,
        "vip_price_threshold": "95.00",
        "vip_protection_levels": ["vip", "svip"],
    }

    # 普通会员命中 member_protection
    result = check_price_protection(items, config, user_level="member")
    assert result["has_conflict"] is True

    # VIP 命中 vip_protection（sale_price=90 < vip_price*0.95=90.25，不冲突）
    result = check_price_protection(items, config, user_level="vip")
    assert result["has_conflict"] is False


def test_no_config():
    """无配置时默认通过"""
    items = [{"sku": "SKU005", "sale_price": "1.00", "cost_price": "100.00"}]
    result = check_price_protection(items, config=None)
    assert result["has_conflict"] is False
    assert result["can_proceed"] is True
