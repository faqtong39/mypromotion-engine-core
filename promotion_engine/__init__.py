"""
mypromotion-engine-core

High-precision promotion calculation engine for Python.
Decimal-native, mutex-aware, pluggable. Zero framework dependency.

Quick start:
    from decimal import Decimal
    from promotion_engine import Engine, Cart, CartItem, Rule

    cart = Cart()
    cart.add_item(CartItem(sku="T001", price=Decimal("199.00"), qty=2))
    rules = [Rule.full_reduction(threshold=300, amount=50)]
    engine = Engine()
    result = engine.calculate(cart, rules)
    print(result.payable_amount)
"""

from .types import (
    Cart,
    CartItem,
    CalculationContext,
    PromotionResult,
    CalculationResult,
    Rule,
    RuleCondition,
    RuleAction,
    RuleScope,
    UsedCoupon,
    MutexGroup,
    SpecialMutexRule,
)
from .engine import PromotionEngine as Engine

__all__ = [
    "Engine",
    "Cart",
    "CartItem",
    "CalculationContext",
    "PromotionResult",
    "CalculationResult",
    "Rule",
    "RuleCondition",
    "RuleAction",
    "RuleScope",
    "UsedCoupon",
    "MutexGroup",
    "SpecialMutexRule",
]

__version__ = "0.1.0"
