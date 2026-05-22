"""
FastAPI Demo 应用（可选依赖）

启动方式：
    pip install mypromotion-engine-core[demo]
    mypromotion-engine-demo

或（源码直接运行，无需 pip install）：
    cd mypromotion-engine-core
    $env:PYTHONPATH="."
    py demo/app.py
"""
import sys
from pathlib import Path

# 自动将项目根目录加入 sys.path，支持源码直接运行无需 pip install
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import json
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from promotion_engine import Engine, Cart, CartItem, Rule
from promotion_engine.types import CalculationContext, RuleAction, RuleCondition, RuleScope, UsedCoupon

app = FastAPI(title="Promotion Engine Demo")

# 静态文件
static_dir = Path(__file__).parent / "static"
app.mount("/demo", StaticFiles(directory=str(static_dir), html=True), name="demo")


class CartItemInput(BaseModel):
    sku: str
    price: str
    qty: int = 1
    category_id: str = ""
    tags: list = []


class CouponInput(BaseModel):
    code: str
    coupon_type: str = "fixed_amount"
    discount_value: str = "0"
    min_order_amount: str = "0"
    priority: int = 0


class RuleInput(BaseModel):
    promotion_code: str = ""
    strategy_type: str = "full_reduction"
    priority: int = 0
    conditions: list = []
    actions: list = []
    scopes: list = []
    stack_config: dict = {}


# 模拟规则库（零数据库，纯内存），用于演示 promotion_codes 查询能力。
# key 为 promotion_code（与 strategy_type 保持一致），value 为可直接构建 Rule 的字典。
RULE_STORE: dict[str, dict] = {}


class MutexGroupInput(BaseModel):
    code: str
    name: str = ""
    strategies: list = []
    rule_ids: list = []
    is_active: bool = True


class SpecialMutexRuleInput(BaseModel):
    name: str = ""
    rule_a_id: str = ""
    rule_b_id: str = ""
    is_bidirectional: bool = True
    priority_direction: str = "a"
    is_active: bool = True


class CalculateRequest(BaseModel):
    cart_items: list[CartItemInput]
    rules: list[RuleInput] = []
    promotion_codes: list[str] = []
    coupons: list[CouponInput] = []
    calculation_order: str = "promotions-first"
    shipping_fee: str = "0"
    user_group: str = ""
    is_first_order: bool = False
    mutex_groups: list[MutexGroupInput] = []
    special_mutex_rules: list[SpecialMutexRuleInput] = []


@app.get("/api/rules")
def list_rules():
    return list(RULE_STORE.values())


@app.post("/api/rules")
def save_rule(rule: RuleInput):
    code = (rule.promotion_code or rule.strategy_type).strip()
    if not code:
        return {"error": "promotion_code or strategy_type required"}, 400
    RULE_STORE[code] = {
        "promotion_code": code,
        "strategy_type": rule.strategy_type,
        "priority": rule.priority,
        "conditions": rule.conditions,
        "actions": rule.actions,
        "scopes": rule.scopes,
        "stack_config": rule.stack_config or {},
    }
    return {"code": code, "message": "saved"}


@app.delete("/api/rules/{code}")
def delete_rule(code: str):
    if code in RULE_STORE:
        del RULE_STORE[code]
        return {"message": "deleted"}
    return {"error": "not found"}, 404


def _to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    s = str(value).strip()
    if not s:
        return Decimal("0")
    try:
        return Decimal(s)
    except Exception:
        return Decimal("0")


@app.post("/api/calculate")
def calculate(req: CalculateRequest):
    cart = Cart()
    for item in req.cart_items:
        cart.add_item(CartItem(
            sku=item.sku,
            price=_to_decimal(item.price),
            quantity=item.qty,
            category_id=item.category_id or None,
            tags=item.tags,
        ))

    rules = []
    for r in req.rules:
        conditions = []
        for c in r.conditions:
            cond_type = c.get("condition_type", "")
            config = dict(c.get("config", {}))
            # 兼容扁平化参数（如 operator/value）自动合并到 config
            for key in ("operator", "value", "amount", "quantity", "group", "days"):
                if key in c and key not in config:
                    config[key] = c[key]
            conditions.append(RuleCondition(condition_type=cond_type, config=config))
        actions = []
        for a in r.actions:
            act_type = a.get("action_type", "")
            config = dict(a.get("config", {}))
            # 兼容扁平化参数自动合并到 config
            for key in ("amount", "price", "percentage", "points", "tiers", "deposit", "expansion_ratio", "max_discount"):
                if key in a and key not in config:
                    config[key] = a[key]
            actions.append(RuleAction(action_type=act_type, config=config))
        scopes = []
        for s in r.scopes:
            scope_type = s.get("scope_type", "")
            config = dict(s.get("config", {}))
            for key in ("skus", "category_ids", "tags", "except_skus"):
                if key in s and key not in config:
                    config[key] = s[key]
            scopes.append(RuleScope(scope_type=scope_type, config=config))
        rules.append(Rule(
            promotion_code=r.promotion_code or r.strategy_type,
            strategy_type=r.strategy_type,
            priority=r.priority,
            conditions=conditions,
            actions=actions,
            scopes=scopes,
            stack_config=r.stack_config,
        ))

    # promotion_codes 处理：若 rules 为空则从模拟规则库加载；若已有 rules 则按 codes 过滤
    if req.promotion_codes:
        if not req.rules:
            for code in req.promotion_codes:
                tpl = RULE_STORE.get(code)
                if not tpl:
                    continue
                conditions = [RuleCondition(condition_type=c.get("condition_type", ""), config=dict(c.get("config", {}))) for c in tpl["conditions"]]
                actions = [RuleAction(action_type=a.get("action_type", ""), config=dict(a.get("config", {}))) for a in tpl["actions"]]
                scopes = [RuleScope(scope_type=s.get("scope_type", ""), config=dict(s.get("config", {}))) for s in tpl["scopes"]]
                rules.append(Rule(
                    promotion_code=tpl["promotion_code"],
                    strategy_type=tpl["strategy_type"],
                    priority=tpl["priority"],
                    conditions=conditions,
                    actions=actions,
                    scopes=scopes,
                    stack_config=tpl.get("stack_config", {}),
                ))
        else:
            codes = set(req.promotion_codes)
            rules = [r for r in rules if r.promotion_code in codes]

    order_map = {
        "promotions-first": ["promotions", "coupons"],
        "coupons-first": ["coupons", "promotions"],
        "optimal": "optimal",
    }
    calculation_order = order_map.get(req.calculation_order, ["promotions", "coupons"])

    used_coupons = []
    for c in req.coupons:
        used_coupons.append(UsedCoupon(
            code=c.code,
            coupon_type=c.coupon_type,
            discount_value=_to_decimal(c.discount_value) if c.discount_value else None,
            min_order_amount=_to_decimal(c.min_order_amount) if c.min_order_amount else None,
            priority=c.priority,
        ))

    context = CalculationContext(
        cart_items=cart.items,
        shipping_fee=_to_decimal(req.shipping_fee),
        user_group=req.user_group or None,
        calculation_order=calculation_order,
        used_coupons=used_coupons,
        is_first_order=req.is_first_order,
    )

    from promotion_engine.types import MutexGroup, SpecialMutexRule

    mutex_groups = {}
    for mg in req.mutex_groups:
        code = mg.code or ""
        mutex_groups[code] = {
            "name": mg.name or code,
            "strategies": mg.strategies or [],
            "rule_ids": mg.rule_ids or [],
            "is_active": mg.is_active,
        }

    special_rules = []
    for sm in req.special_mutex_rules:
        special_rules.append(SpecialMutexRule(
            name=sm.name or "",
            rule_a_id=sm.rule_a_id or "",
            rule_b_id=sm.rule_b_id or "",
            is_bidirectional=sm.is_bidirectional,
            priority_direction=sm.priority_direction or "a",
            is_active=sm.is_active,
        ))

    engine = Engine(
        calculation_order=calculation_order,
        mutex_groups=mutex_groups if mutex_groups else None,
        special_mutex_rules=special_rules if special_rules else None,
    )
    result = engine.calculate(context, rules)

    def decimal_default(obj):
        if isinstance(obj, Decimal):
            return str(obj)
        raise TypeError

    return json.loads(json.dumps({
        "applied_promotions": [
            {
                "promotion_code": p.promotion_code,
                "strategy_type": p.strategy_type,
                "discount": p.discount,
                "applied_items": p.applied_items,
                "message": p.message,
                "rewards": p.rewards,
                "free_shipping": p.free_shipping,
            }
            for p in result.applied_promotions
        ],
        "skipped_rules": result.skipped_rules,
        "used_coupons": [
            {"code": c.get("code", ""), "coupon_type": c.get("coupon_type", ""), "discount": c.get("discount", "0")}
            for c in result.used_coupons
        ],
        "summary": {
            "original_amount": result.original_amount,
            "total_discount": result.total_discount,
            "coupon_discount": result.coupon_discount,
            "shipping_fee": result.shipping_fee,
            "payable_amount": result.payable_amount,
        },
    }, default=decimal_default))


@app.get("/api/health")
def health():
    return {"status": "ok"}


def main():
    import uvicorn
    import webbrowser
    from threading import Timer

    host = "127.0.0.1"
    port = 8000
    url = f"http://{host}:{port}/demo/"

    def open_browser():
        webbrowser.open(url)

    Timer(1.5, open_browser).start()
    print(f"\n🚀 Promotion Engine Demo starting at {url}\n")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
