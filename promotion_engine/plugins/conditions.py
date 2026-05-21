"""
条件检查插件（内置 12 个核心条件）

去 Django 化改动：
- 删除 UserProfile ORM 查询（user_birthday 改为读取 context.user_info）
- 删除动态用户分群查询（user_segment 改为静态字段匹配）
- 所有条件只依赖 context 和 items 的直接属性访问
"""
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

from .base import ConditionPlugin, PluginResult


class AmountThresholdCondition(ConditionPlugin):
    """金额门槛条件"""
    code = "min_order_amount"
    name = "金额门槛"
    description = "订单金额达到指定门槛"
    config_schema = {
        "type": "object",
        "required": ["amount"],
        "properties": {"amount": {"type": "number", "description": "最低金额"}},
    }

    def check(self, config: Dict, context: Any, items: List) -> PluginResult:
        amount = config.get("amount")
        threshold = Decimal(str(amount)) if amount is not None else Decimal("0")
        total = getattr(context, "current_payable_amount", None)
        if total is None:
            total = sum(item.total_amount for item in items)
        return PluginResult(
            success=total >= threshold,
            data={"threshold": float(threshold), "actual": float(total)},
            message=f"金额检查: {total} >= {threshold} = {total >= threshold}",
        )


class QtyThresholdCondition(ConditionPlugin):
    """数量门槛条件"""
    code = "min_quantity"
    name = "数量门槛"
    description = "商品数量达到指定门槛"
    config_schema = {
        "type": "object",
        "required": ["quantity"],
        "properties": {"quantity": {"type": "integer", "description": "最低数量"}},
    }

    def check(self, config: Dict, context: Any, items: List) -> PluginResult:
        qty = config.get("quantity")
        if qty is None:
            qty = config.get("min_quantity", 0)
        try:
            threshold = int(float(qty)) if qty is not None else 0
        except (ValueError, TypeError):
            threshold = 0
        total = sum(item.quantity for item in items)
        return PluginResult(
            success=total >= threshold,
            data={"threshold": threshold, "actual": total},
            message=f"数量检查: {total} >= {threshold} = {total >= threshold}",
        )


class UserGroupCondition(ConditionPlugin):
    """用户组条件"""
    code = "user_group"
    name = "用户组"
    description = "指定用户组才能享受"
    config_schema = {
        "type": "object",
        "required": ["group_ids"],
        "properties": {"group_ids": {"type": "array", "description": "允许的用户组ID列表"}},
    }

    def check(self, config: Dict, context: Any, items: List) -> PluginResult:
        group_ids = config.get("group_ids", [])
        allowed_list = [str(g) for g in group_ids]
        user_group = getattr(context, "user_group", None)
        user_group_str = str(user_group) if user_group is not None else None
        return PluginResult(
            success=user_group_str in allowed_list,
            data={"allowed_groups": allowed_list, "user_group": user_group},
            message=f"用户组检查: {user_group} in {allowed_list}",
        )


class ShippingMethodCondition(ConditionPlugin):
    """配送方式条件"""
    code = "shipping_method"
    name = "配送方式"
    description = "指定配送方式才能享受"
    config_schema = {
        "type": "object",
        "required": ["methods"],
        "properties": {"methods": {"type": "array", "description": "允许的配送方式列表"}},
    }

    def check(self, config: Dict, context: Any, items: List) -> PluginResult:
        allowed_methods = config.get("methods", [])
        method = getattr(context, "shipping_method", None)
        return PluginResult(
            success=method in allowed_methods,
            data={"allowed_methods": allowed_methods, "method": method},
            message=f"配送方式检查: {method} in {allowed_methods}",
        )


class ChannelCondition(ConditionPlugin):
    """购买渠道条件"""
    code = "channel"
    name = "购买渠道"
    description = "指定购买渠道才能享受"
    config_schema = {
        "type": "object",
        "required": ["channels"],
        "properties": {"channels": {"type": "array", "description": "允许的渠道列表"}},
    }

    def check(self, config: Dict, context: Any, items: List) -> PluginResult:
        allowed = config.get("channels", [])
        channel = getattr(context, "channel", None)
        return PluginResult(
            success=channel in allowed,
            data={"allowed": allowed, "channel": channel},
            message=f"渠道检查: {channel} in {allowed}",
        )


class TimeWindowCondition(ConditionPlugin):
    """时间段条件"""
    code = "time_window"
    name = "时间段"
    description = "在指定时间段内才能享受"
    config_schema = {
        "type": "object",
        "properties": {
            "start_time": {"type": "string", "format": "datetime"},
            "end_time": {"type": "string", "format": "datetime"},
        },
    }

    @staticmethod
    def _parse_iso_datetime(dt_str: str) -> datetime:
        """兼容 Python 3.9 的 ISO 时间解析（支持 Z 后缀）"""
        s = dt_str.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)

    def check(self, config: Dict, context: Any, items: List) -> PluginResult:
        start_time_str = config.get("start_time")
        end_time_str = config.get("end_time")
        current = getattr(context, "current_time", None) or datetime.now()

        if start_time_str:
            try:
                start_dt = self._parse_iso_datetime(start_time_str)
            except ValueError:
                return PluginResult(success=False, data={}, message=f"开始时间格式错误: {start_time_str}")
            if current.tzinfo is not None and start_dt.tzinfo is None:
                from datetime import timezone
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            elif current.tzinfo is None and start_dt.tzinfo is not None:
                start_dt = start_dt.replace(tzinfo=None)
            if current < start_dt:
                return PluginResult(
                    success=False,
                    data={"current": str(current), "start": str(start_dt)},
                    message=f"未到开始时间: {start_dt}",
                )

        if end_time_str:
            try:
                end_dt = self._parse_iso_datetime(end_time_str)
            except ValueError:
                return PluginResult(success=False, data={}, message=f"结束时间格式错误: {end_time_str}")
            if current.tzinfo is not None and end_dt.tzinfo is None:
                from datetime import timezone
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            elif current.tzinfo is None and end_dt.tzinfo is not None:
                end_dt = end_dt.replace(tzinfo=None)
            if current > end_dt:
                return PluginResult(
                    success=False,
                    data={"current": str(current), "end": str(end_dt)},
                    message=f"已超过结束时间: {end_dt}",
                )

        return PluginResult(success=True, data={"current": str(current)}, message="在时间范围内")


class DayOfWeekCondition(ConditionPlugin):
    """星期几条件"""
    code = "day_of_week"
    name = "星期几限制"
    description = "在指定星期几才能享受"
    config_schema = {
        "type": "object",
        "required": ["days"],
        "properties": {"days": {"type": "array", "description": "0=周日,1=周一,...,6=周六"}},
    }

    def check(self, config: Dict, context: Any, items: List) -> PluginResult:
        raw_days = config.get("days", [])
        allowed_days = []
        for d in raw_days:
            if isinstance(d, int):
                allowed_days.append(d)
            elif isinstance(d, str) and d.strip().isdigit():
                allowed_days.append(int(d.strip()))

        current = getattr(context, "current_time", None) or datetime.now()
        current_weekday = current.weekday()
        day_mapping = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 0}
        current_day = day_mapping[current_weekday]
        day_names = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]

        if current_day not in allowed_days:
            return PluginResult(
                success=False,
                data={"current_day": current_day, "allowed_days": allowed_days},
                message=f"今天是{day_names[current_day]}，不在允许的星期列表中",
            )
        return PluginResult(
            success=True,
            data={"current_day": current_day},
            message=f"今天是{day_names[current_day]}，在允许的星期列表中",
        )


class MonthlyDateCondition(ConditionPlugin):
    """每月固定日期条件"""
    code = "monthly_date"
    name = "每月固定日期"
    description = "每月指定日期生效"
    config_schema = {
        "type": "object",
        "required": ["dates"],
        "properties": {"dates": {"type": "array", "description": "每月的几号，如[1,15]"}},
    }

    def check(self, config: Dict, context: Any, items: List) -> PluginResult:
        allowed_dates = config.get("dates", [])
        valid_dates = []
        for d in allowed_dates:
            val = None
            if isinstance(d, int) and 1 <= d <= 31:
                val = d
            elif isinstance(d, str) and d.strip().isdigit():
                val = int(d.strip())
                if not (1 <= val <= 31):
                    val = None
            if val is not None:
                valid_dates.append(val)

        if not valid_dates:
            return PluginResult(
                success=False, data={"dates": allowed_dates}, message="配置错误: 未指定有效的日期列表"
            )

        current = getattr(context, "current_time", None) or datetime.now()
        current_date = current.date() if hasattr(current, "date") else current
        current_day = current_date.day

        if current_day not in valid_dates:
            return PluginResult(
                success=False,
                data={"current_day": current_day, "allowed_dates": valid_dates},
                message=f"今天是{current_date}（{current_day}号），不在允许的日期列表{valid_dates}中",
            )
        return PluginResult(
            success=True,
            data={"current_day": current_day},
            message=f"今天是{current_date}（{current_day}号），在允许的日期列表中",
        )


class IsFirstOrderCondition(ConditionPlugin):
    """首单条件"""
    code = "is_first_order"
    name = "首单用户"
    description = "仅限首单用户享受"
    config_schema = {"type": "object", "properties": {}}

    def check(self, config: Dict, context: Any, items: List) -> PluginResult:
        is_first = getattr(context, "is_first_order", False)
        return PluginResult(
            success=is_first,
            data={"is_first_order": is_first},
            message=f"首单检查: is_first_order={is_first}",
        )


class PaymentMethodCondition(ConditionPlugin):
    """支付方式条件"""
    code = "payment_method"
    name = "支付方式"
    description = "指定支付方式才能享受"
    config_schema = {
        "type": "object",
        "required": ["methods"],
        "properties": {"methods": {"type": "array", "description": "允许的支付方式列表"}},
    }

    def check(self, config: Dict, context: Any, items: List) -> PluginResult:
        allowed_methods = config.get("methods", [])
        method = getattr(context, "payment_method", None)
        return PluginResult(
            success=method in allowed_methods,
            data={"allowed_methods": allowed_methods, "method": method},
            message=f"支付方式检查: {method} in {allowed_methods}",
        )


class ComboItemsCondition(ConditionPlugin):
    """商品组合条件"""
    code = "combo_items"
    name = "商品组合"
    description = "指定商品组合才能享受"
    config_schema = {
        "type": "object",
        "required": ["skus"],
        "properties": {"skus": {"type": "array", "description": "需要的SKU组合列表"}},
    }

    def check(self, config: Dict, context: Any, items: List) -> PluginResult:
        required_skus = set(config.get("skus", []))
        item_skus = {item.sku for item in items}
        matched = required_skus & item_skus
        return PluginResult(
            success=matched == required_skus,
            data={"required": list(required_skus), "matched": list(matched)},
            message=f"商品组合检查: 需要{required_skus}, 拥有{item_skus}, 匹配{matched}",
        )


class UserBirthdayCondition(ConditionPlugin):
    """用户生日条件（静态版本）"""
    code = "user_birthday"
    name = "用户生日"
    description = "用户生日当天/当月生效"
    config_schema = {
        "type": "object",
        "properties": {
            "match_type": {
                "type": "string",
                "enum": ["exact", "month_only"],
                "default": "exact",
            }
        },
    }

    def check(self, config: Dict, context: Any, items: List) -> PluginResult:
        match_type = config.get("match_type", "exact")
        user_info = getattr(context, "user_info", {}) or {}
        birthday = user_info.get("birthday") if isinstance(user_info, dict) else None

        if not birthday:
            return PluginResult(
                success=False, data={}, message="用户未设置生日信息"
            )

        try:
            if isinstance(birthday, str):
                birthday_date = datetime.strptime(birthday, "%Y-%m-%d").date()
            elif isinstance(birthday, datetime):
                birthday_date = birthday.date()
            else:
                birthday_date = birthday

            today = datetime.now().date()

            if match_type == "exact":
                is_match = birthday_date.month == today.month and birthday_date.day == today.day
                desc = f"生日当天({birthday_date.month}/{birthday_date.day})"
            elif match_type == "month_only":
                is_match = birthday_date.month == today.month
                desc = f"生日月份({birthday_date.month}月)"
            else:
                return PluginResult(success=False, data={}, message=f"无效的匹配类型: {match_type}")

            return PluginResult(
                success=is_match,
                data={"birthday": str(birthday_date), "today": str(today), "match_type": match_type},
                message=f"生日检查: 今天{today}，用户生日{birthday_date}，{desc}，结果={'命中' if is_match else '未命中'}",
            )
        except (ValueError, TypeError) as e:
            return PluginResult(success=False, data={}, message=f"生日格式错误: {e}")


class YearlyDateCondition(ConditionPlugin):
    """每年固定日期条件 - 每年指定日期生效，如双11、双12、元旦等"""
    code = "yearly_date"
    name = "每年固定日期"
    description = "每年指定日期生效，如双11、双12、元旦等"
    config_schema = {
        "type": "object",
        "properties": {
            "month": {"type": "integer", "description": "月份（1-12）"},
            "day": {"type": "integer", "description": "日期（1-31）"},
            "duration_days": {"type": "integer", "default": 1, "description": "促销持续天数，默认为1天"},
            "start_year": {"type": "integer", "description": "开始年份（如2026）"},
            "end_year": {"type": "integer", "description": "结束年份（如2030）"},
        },
    }

    def check(self, config: Dict, context: Any, items: List) -> PluginResult:
        from datetime import date, timedelta
        from calendar import monthrange

        target_month = config.get("month")
        target_day = config.get("day")
        duration_days = config.get("duration_days", 1)
        start_year = config.get("start_year")
        end_year = config.get("end_year")

        def _to_int(val):
            if isinstance(val, int):
                return val
            if isinstance(val, str) and val.strip().isdigit():
                return int(val.strip())
            return val

        target_month = _to_int(target_month)
        target_day = _to_int(target_day)
        duration_days = _to_int(duration_days)
        if start_year is not None:
            start_year = _to_int(start_year)
        if end_year is not None:
            end_year = _to_int(end_year)

        if target_month is None or target_day is None:
            return PluginResult(
                success=False,
                data={"month": target_month, "day": target_day},
                message="配置错误: 必须指定month和day",
            )

        if not isinstance(target_month, int) or not (1 <= target_month <= 12):
            return PluginResult(
                success=False,
                data={"month": target_month},
                message=f"配置错误: month必须是1-12之间的整数，当前为{target_month}",
            )

        if not isinstance(target_day, int) or not (1 <= target_day <= 31):
            return PluginResult(
                success=False,
                data={"day": target_day},
                message=f"配置错误: day必须是1-31之间的整数，当前为{target_day}",
            )

        if not isinstance(duration_days, int) or duration_days < 1:
            return PluginResult(
                success=False,
                data={"duration_days": duration_days},
                message=f"配置错误: duration_days必须是正整数，当前为{duration_days}",
            )

        current = getattr(context, "current_time", None) or datetime.now()
        current_date = current.date() if hasattr(current, "date") else current

        # 检查年份范围
        if start_year and current_date.year < start_year:
            return PluginResult(
                success=False,
                data={"current_year": current_date.year, "start_year": start_year},
                message=f"当前年份{current_date.year}早于开始年份{start_year}",
            )

        if end_year and current_date.year > end_year:
            return PluginResult(
                success=False,
                data={"current_year": current_date.year, "end_year": end_year},
                message=f"当前年份{current_date.year}晚于结束年份{end_year}",
            )

        # 计算今年促销的开始和结束日期
        try:
            promo_start = date(current_date.year, target_month, target_day)
        except ValueError:
            last_day = monthrange(current_date.year, target_month)[1]
            target_day = min(target_day, last_day)
            promo_start = date(current_date.year, target_month, target_day)

        promo_end = promo_start + timedelta(days=duration_days - 1)

        # 检查当前日期是否在促销期间
        if current_date < promo_start:
            return PluginResult(
                success=False,
                data={
                    "current_date": str(current_date),
                    "promo_start": str(promo_start),
                    "promo_end": str(promo_end),
                },
                message=f"促销尚未开始，开始日期: {promo_start}",
            )

        if current_date > promo_end:
            return PluginResult(
                success=False,
                data={
                    "current_date": str(current_date),
                    "promo_start": str(promo_start),
                    "promo_end": str(promo_end),
                },
                message=f"促销已结束，结束日期: {promo_end}",
            )

        return PluginResult(
            success=True,
            data={
                "current_date": str(current_date),
                "promo_start": str(promo_start),
                "promo_end": str(promo_end),
                "day_of_promo": (current_date - promo_start).days + 1,
            },
            message=f"今天是促销第{(current_date - promo_start).days + 1}天，促销期间: {promo_start} 至 {promo_end}",
        )
