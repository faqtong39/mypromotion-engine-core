# mypromotion-engine-core

> High-precision promotion calculation engine for Python.  
> Decimal-native, mutex-aware, pluggable. Zero framework dependency.

[🚀 Live Demo](https://your-demo-url.com) | [📖 Docs](doc/opensource/开源核心功能范围定义.md) | [🐍 PyPI](https://pypi.org/project/mypromotion-engine-core/)

---

## What it does

Input: a shopping cart + a list of promotion rules  
Output: the exact payable amount, with full transparency on why each rule applied or was skipped.

## Why this exists

Most e-commerce platforms calculate promotions with:

- **Float arithmetic** → rounding errors (0.1 + 0.2 != 0.3)
- **Black-box logic** → you don't know why a rule didn't apply
- **No per-item allocation trace** → refunds become guesswork

This engine fixes all three. Every calculation uses `Decimal`, every skipped rule carries a reason, and every discount can be traced down to individual SKUs.

## Quick start (< 1 minute)

```bash
pip install mypromotion-engine-core
```

```python
from decimal import Decimal
from promotion_engine import Engine, Cart, CartItem, Rule

cart = Cart()
cart.add_item(CartItem(sku="T001", price=Decimal("199.00"), qty=2))
cart.add_item(CartItem(sku="T002", price=Decimal("89.00"), qty=1))

rules = [Rule.full_reduction(threshold=300, amount=50)]
engine = Engine()

context = CalculationContext(cart_items=cart.items)
result = engine.calculate(context, rules)

print(result.payable_amount)   # 437.00
print(result.total_discount)   # 50.00
```

## Try the Demo

```bash
pip install mypromotion-engine-core[demo]
mypromotion-engine-demo
```

Then open your browser at `http://127.0.0.1:8000/demo/`

## Key features

- **Decimal-native**: No float rounding errors anywhere in the pipeline
- **Mutex transparency**: 4-layer mutex checking with explicit skip reasons
  - Special mutex rules (bidirectional / unidirectional with replacement)
  - Stack config whitelist/blacklist (`stackable_with` / `mutex_with`)
  - Strategy-type mutex groups
  - Force-stackable override
- **Optimal ordering**: Automatically compare `promotions-first` vs `coupons-first` and pick the cheapest
- **Pluggable**: Add custom conditions/actions/scopes via a simple registration API
- **Price protection**: Built-in cost-price and member-price guardrails
- **Refund-ready**: Per-item discount allocation with 3 strategies (`proportional`, `keep_discount`, `full_refund_discount`)
- **Framework-agnostic**: Pure Python, no Django/Flask/FastAPI required

## Architecture

```
Cart + Rules
    │
    ▼
Scope Filter ──► Mutex Check ──► Condition Check ──► Discount Calc ──► Result
    │                │                  │                   │
    ▼                ▼                  ▼                   ▼
SKU list      skip reasons       pass/fail           Decimal precision
```

## Advanced examples

### Example: Tiered pricing

```python
from promotion_engine import Rule, RuleAction

rule = Rule(
    promotion_code="TIERED",
    strategy_type="tiered_price",
    actions=[
        RuleAction(action_type="tiered_price", config={
            "tiers": [
                {"quantity": 1, "price": 100},
                {"quantity": 3, "price": 90},
                {"quantity": 5, "price": 80},
            ]
        })
    ],
)
```

### Example: Mutex groups with replacement

```python
from promotion_engine import Engine, MutexGroup, SpecialMutexRule

engine = Engine(
    mutex_groups={
        "discount": {
            "strategies": ["full_reduction", "full_discount"],
            "priority": 100,
        }
    },
    special_mutex_rules=[
        SpecialMutexRule(
            rule_a_id="BIG_SALE",
            rule_b_id="SMALL_SALE",
            is_bidirectional=False,
            priority_direction="a",
        )
    ],
)
```

### Example: Optimal sequence comparison

```python
context = CalculationContext(
    cart_items=cart.items,
    calculation_order="optimal",  # auto-compare and pick cheapest
)
```

## Running tests

```bash
pip install pytest
pytest tests/
```

## Comparison with other engines

| Feature | mypromotion-engine-core | Spree | Sylius | json-rules-engine |
|---------|------------------------|-------|--------|-------------------|
| Decimal precision | ✅ Native | ❌ Float | ❌ Float | ❌ Float |
| Per-item allocation | ✅ Built-in | ❌ No | ❌ No | ❌ No |
| Refund traceability | ✅ Core lib | ❌ Re-calc | ❌ Re-calc | ❌ No |
| Mutex engine depth | 4 layers | 1 layer | 1 layer | 0 |
| Framework coupling | None | Rails | Symfony | Node only |

## Full SaaS Platform

This repository contains the **core calculation engine only**.

For the complete SaaS platform with:

- Admin dashboard & rule management UI
- Multi-tenant isolation
- Dynamic user segmentation & product pools
- Trace/snapshot persistence & refund execution
- Real-time monitoring & audit logs

See [MyPromotion](https://your-saas-domain.com) — the commercial platform built on top of this open-source core.

## License

Apache-2.0 © MyPromotion Team
