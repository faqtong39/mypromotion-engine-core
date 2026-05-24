# mypromotion-engine-core

High-precision promotion calculation engine for Python. Decimal-native, mutex-aware, pluggable. Zero framework dependency.

[Live Demo](https://mp.tooly.run/demo) · [PyPI](https://pypi.org/project/mypromotion-engine-core/)

---

## Live Demo

![demo](doc/assets/demo.gif)

### [🔗 Visit Live Demo](https://mp.tooly.run/demo)

---

## 30-Second Quick Start

```bash
git clone https://github.com/faqtong/mypromotion-engine-core.git
cd mypromotion-engine-core
pip install -e .
```

```python
from decimal import Decimal
from promotion_engine import Engine, Cart, CartItem, Rule
from promotion_engine.types import CalculationContext

cart = Cart()
cart.add_item(CartItem(sku="T001", price=Decimal("199.00"), quantity=2))
cart.add_item(CartItem(sku="T002", price=Decimal("89.00"), quantity=1))

engine = Engine()
context = CalculationContext(cart_items=cart.items)
result = engine.calculate(context, rules=[Rule.full_reduction(threshold=300, amount=50)])

print(result.payable_amount)  # 437.00
print(result.total_discount)  # 50.00
```

---

## Try the Demo

```bash
git clone https://github.com/faqtong/mypromotion-engine-core.git
cd mypromotion-engine-core
python demo/app.py
```

Open your browser at `http://127.0.0.1:8000/demo/`

Features: create/edit/delete rules, real-time calculation, refund simulation, export JSON.

---

## Key Features

| Feature | Description |
|---------|-------------|
| Decimal-native | Decimal throughout the entire pipeline. No float rounding errors. |
| 4-layer mutex | Special mutex / whitelist-blacklist / strategy mutex groups / force-stackable override |
| Optimal ordering | Auto-compare promotions-first vs coupons-first and pick the cheaper one |
| Pluggable | Conditions, actions, and scopes all extendable via a simple registration API |
| Refund-ready | Per-SKU discount allocation with 3 strategies: proportional, keep_discount, full_refund_discount |
| Framework-agnostic | Pure Python. No Django/Flask/FastAPI required. |

---

## Architecture

```
Cart + Rules
    |
    v
Scope Filter --> Mutex Check --> Condition Check --> Discount Calc --> Result
    |                |                  |                   |
    v                v                  v                   v
SKU match       skip reasons       pass/fail           Decimal precision
```

---

## Open Source vs SaaS

| Capability | Open Source | SaaS Platform |
|------------|-------------|---------------|
| Rule Management | In-memory rule library, visual creation | Visual admin, 55+ templates |
| Promotion Strategies | Full reduction, fixed price, tiered pricing | 15 core strategies (discount, seckill, pre-sale, coupon, points, etc.) |
| Calculation | Code-based lookup, sequence/mutex/replace | Code-based lookup, rule-level stack control (whitelist/blacklist/force-stack/max-stack) |
| Price Protection | None | Automatic price-drop refund, dedicated price protection module |
| After-sales Policy | 3 allocation strategies (proportional/keep-discount/full-refund) | Same as open source + reusable after-sales policy templates |
| Refund Traceability | Per-SKU traceability | Same as open source + snapshot archiving & audit trails |
| User Segmentation | None | Dynamic cohorts, targeted delivery |
| Product Pool | None | Dynamic pools, whitelist/blacklist |
| Multi-tenancy | None | Tenant isolation, permission levels |
| Monitoring & Integration | Basic event logs, Python SDK | Real-time dashboard, Open API, multi-language SDKs |
| Security | Basic authentication | Three-level rate limiting, OAuth2 / RBAC, audit compliance |

---

## Running Tests

```bash
pip install pytest
pytest tests/ -q
```

---

## License

Apache-2.0 © MyPromotion Team
