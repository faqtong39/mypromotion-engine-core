# mypromotion-engine-core

> High-precision promotion calculation engine for Python. Supports full reduction, percentage discount, tiered pricing, fixed price, coupons, points deduction, price protection, and refund allocation. Decimal-native, mutex-aware, pluggable. Zero framework dependency.

[Live Demo](https://mp.tooly.run/demo) · [PyPI](https://pypi.org/project/mypromotion-engine-core/)

**Keywords**: promotion engine, e-commerce discount calculator, coupon system, tiered pricing, refund allocation, price protection, shopping cart promotion, Python e-commerce, Decimal precision

---

## Live Demo

![Promotion engine demo: visual interface for full reduction, tiered pricing, coupons, and refund simulation](doc/assets/demo.gif)

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

## Use Cases

- **E-commerce platforms**: full reduction, percentage discount, tiered pricing, coupon stacking
- **Retail stores**: member discounts, fixed price, points deduction
- **O2O delivery**: shipping fee reduction, first-order discounts, user-segment targeting
- **SaaS providers**: multi-tenant promotion rule engine, open API integration
- **Financial reconciliation**: refund allocation tracing, calculation snapshot, audit compliance

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

> This open-source engine and the [MyPromotion SaaS Platform](https://mp.tooly.run) are maintained by the same team. The SaaS is built on top of this engine, adding enterprise capabilities such as multi-tenancy, user segmentation, product pools, and monitoring.

| Capability | Open Source | [SaaS Platform](https://mp.tooly.run) |
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

## Comparison with Alternatives

| Dimension | Open Source | Hand-written code | Spreadsheet | [MyPromotion SaaS](https://mp.tooly.run) |
|-----------|-------------|-------------------|-------------|----------------------------------------|
| Float precision | ✅ Decimal-native | ❌ float errors | ❌ formula errors | ✅ Decimal-native |
| Rule mutex | ✅ 4-layer auto check | ❌ hard-coded | ❌ unsupported | ✅ 4-layer + rule-level stack control |
| Refund trace | ✅ Per-SKU allocation | ❌ scattered logic | ❌ no trace | ✅ Snapshot + audit trails |
| Integration cost | ✅ pip install | ⚠️ person-years | ⚠️ maintenance | 💰 Pay-as-you-go (free during early access) |
| Data privacy | ✅ Local execution | ✅ Self-controlled | ❌ leak risk | ⚠️ Cloud data |

## FAQ

**Q: How is this different from writing `if/else` for discounts?**

A: Hand-written code works for simple rules, but explodes in complexity when you add more types (full reduction, percentage, tiered pricing, coupons, points). The engine abstracts this into a standard pipeline. New rule types are just plugins—no core code changes needed.

**Q: Which Python versions are supported?**

A: Python 3.9+. Zero dependencies. Optional `pip install -e .[demo]` for FastAPI demo dependencies.

**Q: Can it integrate with my existing e-commerce backend?**

A: Yes. The engine core is a pure Python library. Pass in a cart item list + promotion rules, get back calculation results. Framework-agnostic—works with Django, Flask, FastAPI, or any Python backend.

**Q: Will refund calculations match the original order?**

A: Yes. The forward calculation generates a `trace` snapshot recording per-SKU allocation. Refunds read this snapshot directly and apply the original ratio, eliminating discrepancies.

**Q: How do I deploy to production?**

A: Docker + Docker Compose one-click deployment with healthcheck and log rotation. See `docker-compose.yml` and `deploy.sh` in the project root.

## Running Tests

```bash
pip install pytest
pytest tests/ -q
```

---

## License

Apache-2.0 © MyPromotion Team
