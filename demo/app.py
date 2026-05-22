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
import logging
import logging.handlers
import os
import threading
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, APIRouter
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from promotion_engine import Engine, Cart, CartItem, Rule
from promotion_engine.types import CalculationContext, RuleAction, RuleCondition, RuleScope, UsedCoupon
from promotion_engine.refund import calculate_item_discounts, calculate_refund

app = FastAPI(title="Promotion Engine Demo")
api_router = APIRouter()

# 静态文件（在 api_router include 之后注册，避免拦截 /demo/api/* 请求）
static_dir = Path(__file__).parent / "static"


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


# 模拟规则库（零数据库，纯内存），按 Session ID 隔离。
# 结构: {session_id: {promotion_code: rule_dict}}
RULE_STORE: dict[str, dict[str, dict]] = {}
store_lock = threading.Lock()
MAX_RULES_PER_SESSION = 5
DATA_TTL_HOURS = 24

# 事件日志（按天滚动文件存储，映射到宿主机）
LOG_DIR = os.environ.get("LOG_DIR", os.path.join(os.path.dirname(__file__), "logs"))
os.makedirs(LOG_DIR, exist_ok=True)

_event_logger = logging.getLogger("promo_events")
_event_logger.setLevel(logging.INFO)
_event_logger.propagate = False

_log_handler = logging.handlers.TimedRotatingFileHandler(
    os.path.join(LOG_DIR, "events.log"),
    when="midnight", interval=1, backupCount=7, encoding="utf-8"
)
_log_handler.setFormatter(logging.Formatter(
    fmt="%(asctime)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
))
_event_logger.addHandler(_log_handler)


def _log_event(sid: str, event: str, data: Optional[dict] = None, ua: str = "", ip: str = ""):
    """记录事件到滚动日志文件"""
    if not sid or sid == 'default':
        return
    record = {
        "timestamp": datetime.now().isoformat(),
        "session_id": sid,
        "event": event,
        "data": data or {},
        "ua": ua[:200] if ua else "",
        "ip": ip,
    }
    _event_logger.info(json.dumps(record, ensure_ascii=False))


def _get_client_info(request: Request):
    """提取客户端信息 (ua, ip)"""
    ua = request.headers.get("user-agent", "")
    ip = request.headers.get("x-real-ip", "") or request.headers.get("x-forwarded-for", "").split(",")[0].strip() or request.client.host if request.client else ""
    return ua, ip


def get_session_id(request: Request) -> str:
    sid = request.headers.get('X-Session-ID', '').strip()
    return sid or 'default'


def cleanup_expired_data():
    """清理超过 DATA_TTL_HOURS 的数据"""
    cutoff = datetime.now() - timedelta(hours=DATA_TTL_HOURS)
    with store_lock:
        for sid in list(RULE_STORE.keys()):
            for code in list(RULE_STORE[sid].keys()):
                created_at = RULE_STORE[sid][code].get('_created_at')
                if created_at and datetime.fromisoformat(created_at) < cutoff:
                    del RULE_STORE[sid][code]
            if not RULE_STORE[sid]:
                del RULE_STORE[sid]


def _schedule_cleanup():
    """每小时执行一次清理"""
    cleanup_expired_data()
    threading.Timer(3600, _schedule_cleanup).start()


# 启动定时清理
_schedule_cleanup()


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
    user_points: str = "0"
    is_first_order: bool = False
    mutex_groups: list[MutexGroupInput] = []
    special_mutex_rules: list[SpecialMutexRuleInput] = []


@api_router.get("/rules")
def list_rules(request: Request):
    sid = get_session_id(request)
    with store_lock:
        rules = list(RULE_STORE.get(sid, {}).values())
    ua, ip = _get_client_info(request)
    _log_event(sid, "list_rules", {"count": len(rules)}, ua=ua, ip=ip)
    return rules


@api_router.post("/rules")
def save_rule(request: Request, rule: RuleInput):
    code = (rule.promotion_code or rule.strategy_type).strip()
    if not code:
        raise HTTPException(status_code=400, detail="promotion_code or strategy_type required")
    sid = get_session_id(request)
    with store_lock:
        session_rules = RULE_STORE.setdefault(sid, {})
        if code not in session_rules and len(session_rules) >= MAX_RULES_PER_SESSION:
            raise HTTPException(status_code=400, detail=f"每个用户最多保存 {MAX_RULES_PER_SESSION} 条规则")
        session_rules[code] = {
            "promotion_code": code,
            "strategy_type": rule.strategy_type,
            "priority": rule.priority,
            "conditions": rule.conditions,
            "actions": rule.actions,
            "scopes": rule.scopes,
            "stack_config": rule.stack_config or {},
            "_created_at": datetime.now().isoformat(),
        }
    ua, ip = _get_client_info(request)
    _log_event(sid, "save_rule", {"code": code, "strategy_type": rule.strategy_type}, ua=ua, ip=ip)
    return {"code": code, "message": "saved"}


@api_router.delete("/rules/{code}")
def delete_rule(request: Request, code: str):
    sid = get_session_id(request)
    with store_lock:
        session_rules = RULE_STORE.get(sid, {})
        if code in session_rules:
            del session_rules[code]
            ua, ip = _get_client_info(request)
            _log_event(sid, "delete_rule", {"code": code}, ua=ua, ip=ip)
            return {"message": "deleted"}
    raise HTTPException(status_code=404, detail="not found")


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


@api_router.post("/calculate")
def calculate(request: Request, req: CalculateRequest):
    sid = get_session_id(request)
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
            sid = get_session_id(request)
            with store_lock:
                session_rules = RULE_STORE.get(sid, {})
                for code in req.promotion_codes:
                    tpl = session_rules.get(code)
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
        extra={"points": str(_to_decimal(req.user_points))},
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

    # 计算商品级分摊明细（用于退款演示）
    order_items = [{"sku": item.sku, "price": str(item.price), "quantity": item.quantity} for item in cart.items]
    total_discount = Decimal(str(result.total_discount))
    item_discounts = calculate_item_discounts(order_items, total_discount, strategy="proportional")

    def decimal_default(obj):
        if isinstance(obj, Decimal):
            return str(obj)
        raise TypeError

    response = json.loads(json.dumps({
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
        "item_discounts": item_discounts,
        "summary": {
            "original_amount": result.original_amount,
            "total_discount": result.total_discount,
            "coupon_discount": result.coupon_discount,
            "shipping_fee": result.shipping_fee,
            "payable_amount": result.payable_amount,
        },
    }, default=decimal_default))
    ua, ip = _get_client_info(request)
    _log_event(sid, "checkout", {"payable": str(result.payable_amount), "codes": req.promotion_codes}, ua=ua, ip=ip)
    return response


class RefundRequest(BaseModel):
    order_items: list = []
    item_discounts: list = []
    refund_items: list = []
    total_paid: str = "0"
    refunded_total: str = "0"
    strategy: str = "proportional"


@api_router.post("/refund")
def refund(request: Request, req: RefundRequest):
    sid = get_session_id(request)
    total_paid = _to_decimal(req.total_paid)
    refunded_total = _to_decimal(req.refunded_total)
    # 如果前端没传 item_discounts，根据策略重新计算
    item_discounts = req.item_discounts
    if not item_discounts and req.order_items:
        total_original = sum(Decimal(str(i.get("price", "0"))) * i.get("quantity", 1) for i in req.order_items)
        item_discounts = calculate_item_discounts(
            req.order_items,
            total_original - total_paid,
            strategy=req.strategy,
        )
    result = calculate_refund(
        order_items=req.order_items,
        item_discounts=item_discounts,
        refund_items=req.refund_items,
        total_paid=total_paid,
        refunded_total=refunded_total,
    )
    ua, ip = _get_client_info(request)
    _log_event(sid, "refund", {"amount": result.get("refund_amount"), "items": req.refund_items}, ua=ua, ip=ip)
    return result


@api_router.get("/health")
def health():
    return {"status": "ok"}


# 同时挂载到 /api 和 /demo/api，兼容直接访问与 nginx 反向代理
# 注意：/demo/api 必须在 /demo 静态文件 mount 之前注册，否则会被 StaticFiles 拦截
app.include_router(api_router, prefix="/api")
app.include_router(api_router, prefix="/demo/api")

# 静态文件 mount 放在 router 之后，避免拦截 /demo/api/* 请求
app.mount("/demo", StaticFiles(directory=str(static_dir), html=True), name="demo")


def main():
    import uvicorn
    import os

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    display_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    url = f"http://{display_host}:{port}/demo/"

    print(f"\nPromotion Engine Demo starting at {url}\n")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
