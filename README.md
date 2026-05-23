# mypromotion-engine-core

Python 高精度促销计算引擎。原生 Decimal，互斥感知，可插拔。零框架依赖。

[在线体验](https://mp.tooly.run/demo) · [文档](doc/opensource/开源核心功能范围定义.md) · [PyPI](https://pypi.org/project/mypromotion-engine-core/)

---

## 效果预览

![demo](doc/assets/demo.gif)

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

## 在线体验

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

| 能力 | 开源引擎（本仓库） | SaaS 平台（[MyPromotion](https://mp.tooly.run)） |
|------|------------------|------------------------------------------------|
| 核心计算 | Decimal 高精度、插件化架构、四层互斥、最优序计算 | 同开源 + 性能优化与集群部署 |
| 规则管理 | 代码 / JSON 配置规则 | 表单编辑器、55+ 模板、生命周期、模拟试算 |
| 定价与活动 | 满减 / 满折 / 固定价 / 阶梯价等基础玩法 | 动态定价、价格保护、积分抵扣、预售 / 分期 |
| 退款 | 3 种分摊策略、SKU 级追溯 | 同开源 + 历史快照归档与审计明细 |
| 多租户 | 单实例 | 租户隔离、人群圈选、商品池、多渠道投放 |
| 监控 | 基础事件日志 | 实时仪表盘、促销效果分析、用量计费报表 |
| 集成 | Python SDK、本地 Demo | 开放 API、多语言 SDK |
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
