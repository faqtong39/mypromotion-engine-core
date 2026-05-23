# mypromotion-engine-core

High-precision promotion calculation engine for Python. Decimal-native, mutex-aware, pluggable. Zero framework dependency.

[Live Demo](https://mp.tooly.run/demo) · [Docs](doc/opensource/开源核心功能范围定义.md) · [PyPI](https://pypi.org/project/mypromotion-engine-core/)

---

## Preview

![demo](doc/assets/demo.gif)

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

| Capability | Open Source (this repo) | SaaS Platform ([MyPromotion](https://mp.tooly.run)) |
|------------|------------------------|-----------------------------------------------------|
| Core Engine | Decimal precision, pluggable architecture, 4-layer mutex, optimal ordering | Same as open source + performance optimization and cluster deployment |
| Rule Management | Code / JSON configuration | Form editor, 55+ templates, lifecycle, simulation |
| Pricing & Campaigns | Full reduction / percentage / fixed price / tiered pricing | Dynamic pricing, price protection, points deduction, pre-sale / installments |
| Refund | 3 allocation strategies, per-SKU traceability | Same as open source + historical snapshot archiving and audit detail |
| Multi-tenancy | Single instance | Tenant isolation, segmentation, product pools, multi-channel |
| Monitoring | Basic event logs | Real-time dashboard, campaign analytics, usage billing |
| Integration | Python SDK, local Demo | Open API, multi-language SDKs |
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
