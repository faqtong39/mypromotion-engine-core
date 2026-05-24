# mypromotion-engine-core

Python 高精度促销计算引擎。原生 Decimal，互斥感知，可插拔。零框架依赖。

[在线体验](https://mp.tooly.run/demo) · [PyPI](https://pypi.org/project/mypromotion-engine-core/)

---

## 在线体验

![demo](doc/assets/demo.gif)

### [🔗 立即访问在线体验](https://mp.tooly.run/demo)

---

## 30 秒上手

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

## 本地运行

```bash
git clone https://github.com/faqtong/mypromotion-engine-core.git
cd mypromotion-engine-core
python demo/app.py
```

浏览器打开 `http://127.0.0.1:8000/demo/`

支持：增删改查促销规则、实时计算、退款模拟、导出 JSON。

---

## 核心特性

| 特性 | 说明 |
|------|------|
| Decimal 原生 | 全链路 Decimal，彻底避免浮点误差 |
| 四层互斥 | 特殊互斥规则 / 白名单黑名单 / 策略互斥组 / 强制叠加 |
| 最优序 | 自动比较先促销后券 vs 先券后促销，选更便宜的 |
| 可插拔 | 条件、动作、范围均通过注册 API 扩展 |
| 退款可追溯 | 按 SKU 分摊折扣，支持比例退还 / 保留优惠 / 全额退 |

---

## 架构

```
购物车 + 规则列表
    |
    v
范围过滤 --> 互斥检查 --> 条件检查 --> 折扣计算 --> 结果
    |              |             |             |
    v              v             v             v
SKU 命中      跳过原因       通过/拒绝      Decimal 精度
```

---

## 开源引擎 vs SaaS 平台

| 能力 | 开源引擎 | SaaS 平台 |
|------|----------|-----------|
| 规则管理 | 内存规则库，可视化创建 | 可视化后台，55+ 业务模板 |
| 支持的促销策略 | 满减、固定价、阶梯价等基础策略 | 15 种核心策略（满减、满折、秒杀、预售、优惠券、积分抵扣等） |
| 计算方式 | 编码查库，支持顺序/互斥/替换 | 编码查库，规则级叠加控制（白名单/黑名单/强制叠加/最大叠加数） |
| 价格保护 | 无 | 降价自动退差价，独立价格保护模块 |
| 售后策略 | 3 种分摊策略（比例退还/保留优惠/全额退） | 同开源 + 可复用售后策略模板 |
| 退款追溯 | SKU 级追溯 | 同开源 + 历史快照归档与审计明细 |
| 用户分群 | 无 | 动态人群包，精准投放 |
| 商品池管理 | 无 | 动态商品池，黑白名单 |
| 多租户 | 无 | 租户隔离，权限分级 |
| 监控与集成 | 基础事件日志，Python SDK | 实时仪表盘、开放 API、多语言 SDK |
| 安全 | 基础鉴权 | 三级限流、OAuth2 / RBAC、审计合规 |

---

## 测试

```bash
pip install pytest
pytest tests/ -q
```

---

## License

Apache-2.0 © MyPromotion Team
