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


class CalculateRequest(BaseModel):
    cart_items: list[CartItemInput]
    rules: list[RuleInput]
    coupons: list[CouponInput] = []
    calculation_order: str = "promotions-first"
    shipping_fee: str = "0"
    user_group: str = ""


def _to_decimal(value) -> Decimal:
    return Decimal(str(value)) if value is not None else Decimal("0")


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
        conditions = [RuleCondition(**c) for c in r.conditions]
        actions = [RuleAction(**a) for a in r.actions]
        scopes = [RuleScope(**s) for s in r.scopes]
        rules.append(Rule(
            promotion_code=r.promotion_code or r.strategy_type,
            strategy_type=r.strategy_type,
            priority=r.priority,
            conditions=conditions,
            actions=actions,
            scopes=scopes,
            stack_config=r.stack_config,
        ))

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
    )

    engine = Engine()
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
