# mypromotion-engine-core

高性能、高精度电商促销计算引擎（Promotion Engine），促销引擎、营销规则引擎、优惠计算引擎、折扣引擎。

支持满减、满折、阶梯价、固定价、优惠券、积分抵扣、价格保护、退款分摊等复杂电商营销规则计算，支持促销互斥、叠加、优先级与最优优惠决策。适用于电商订单优惠、价格计算、营销活动等场景。

原生 Decimal 精度计算，可插拔架构，零框架依赖。纯 Python 实现，开箱即用。

[在线体验](https://mp.tooly.run/demo) · [PyPI](https://pypi.org/project/mypromotion-engine-core/)

**关键词**：促销引擎、电商优惠计算、满减计算、折扣引擎、优惠券系统、阶梯价计算、退款分摊、价格保护、Python 电商、Decimal 精度

---

## 在线体验

![促销引擎演示：支持满减、阶梯价、优惠券、退款模拟等功能的可视化操作界面](doc/assets/demo.gif)

### [🔗 立即访问在线体验](https://mp.tooly.run/demo)

---

## 30 秒上手：写一个促销规则

```bash
git clone https://github.com/faqtong/mypromotion-engine-core.git
cd mypromotion-engine-core
pip install -e .
```

```python
from decimal import Decimal
from promotion_engine import Engine, Cart, CartItem, Rule
from promotion_engine.types import CalculationContext

# 创建购物车，添加商品
cart = Cart()
cart.add_item(CartItem(sku="T001", price=Decimal("199.00"), quantity=2))
cart.add_item(CartItem(sku="T002", price=Decimal("89.00"), quantity=1))

# 配置促销规则：满 300 减 50
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

启动后可体验完整的促销规则管理功能：增删改查促销规则、实时促销计算、退款模拟、导出 JSON。

---

## 适用场景

- **电商促销平台**：满减、满折、阶梯价、优惠券叠加计算
- **零售门店**：会员折扣、固定价、积分抵扣
- **O2O 外卖**：满减配送费、首单优惠、用户分群定向
- **SaaS 促销服务商**：多租户促销规则引擎、开放 API 集成
- **财务对账**：退款分摊追溯、计算凭证快照、审计合规

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

> 本开源引擎与 [MyPromotion SaaS 平台](https://mp.tooly.run) 由同一团队维护。SaaS 基于本引擎构建，增加了多租户、用户分群、商品池、监控等企业级能力。

| 能力 | 开源引擎 | [SaaS 平台](https://mp.tooly.run) |
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

## 与其他方案对比

| 维度 | 开源引擎 | 手写代码 | 电子表格 | [MyPromotion SaaS](https://mp.tooly.run) |
|------|---------|----------|----------|----------------------------------------|
| 浮点精度 | ✅ Decimal 原生 | ❌ float 误差 | ❌ 公式错误 | ✅ Decimal 原生 |
| 规则互斥 | ✅ 四层互斥自动检查 | ❌ 人工硬编码 | ❌ 无法处理 | ✅ 四层互斥 + 规则级叠加控制 |
| 退款追溯 | ✅ SKU 级分摊明细 | ❌ 逻辑分散 | ❌ 无追溯 | ✅ 历史快照 + 审计明细 |
| 接入成本 | ✅ pip 安装即用 | ⚠️ 多人年研发 | ⚠️ 维护困难 | 💰 按需付费（现阶段免费） |
| 数据隐私 | ✅ 本地运行 | ✅ 自主可控 | ❌ 文件泄露风险 | ⚠️ 数据上云 |

## 常见问题

**Q: 这个引擎和直接用 `if/else` 写满减逻辑有什么区别？**

A: 手写代码在规则少时简单直接，但随着规则类型增加（满减、满折、阶梯价、优惠券、积分抵扣），互斥判断、叠加顺序、退款分摊会快速膨胀为难以维护的代码。本引擎把这些逻辑抽象为标准化管线，新增规则类型只需注册插件，无需改动核心代码。

**Q: 支持哪些 Python 版本？**

A: Python 3.9+，无额外依赖。可选 `pip install -e .[demo]` 安装 FastAPI 演示依赖。

**Q: 能否接入现有电商系统？**

A: 可以。引擎核心是纯 Python 库，输入购物车商品列表 + 促销规则列表，输出计算结果。与框架无关，可嵌入 Django、Flask、FastAPI 等任意后端。

**Q: 退款计算会重新算一遍吗？会不会和正向结果不一致？**

A: 不会。正向计算时生成 `trace` 凭证，记录每笔商品的分摊明细。退款时直接读取该凭证，按原分摊比例退还，从根本上消除偏差。

**Q: 生产环境如何部署？**

A: 提供 Docker + Docker Compose 一键部署，含 healthcheck 和日志滚动。详见项目根目录 `docker-compose.yml` 和 `deploy.sh`。

## 测试

```bash
pip install pytest
pytest tests/ -q
```

---

## License

Apache-2.0 © MyPromotion Team
