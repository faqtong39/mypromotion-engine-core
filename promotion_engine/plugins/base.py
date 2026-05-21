"""
促销计算插件基类和插件管理器

架构设计:
1. PluginBase - 所有插件的基类
2. ConditionPlugin - 条件检查插件基类
3. ActionPlugin - 动作计算插件基类
4. ScopePlugin - 范围过滤插件基类
5. PluginManager - 插件管理器，负责加载和管理插件
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple, Type


@dataclass
class PluginResult:
    """插件执行结果"""
    success: bool
    data: Any = None
    message: str = ""
    metadata: Dict = field(default_factory=dict)


class PluginBase(ABC):
    """插件基类"""

    code: str = ""
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    config_schema: Dict = field(default_factory=dict)
    config_drivable: bool = False

    def validate_config(self, config: Dict) -> Tuple[bool, str]:
        required_fields = self.config_schema.get("required", [])
        for f in required_fields:
            if f not in config:
                return False, f"缺少必填字段: {f}"
        return True, ""

    @classmethod
    def get_metadata(cls) -> Dict:
        return {
            "code": cls.code,
            "name": cls.name,
            "description": cls.description,
            "version": cls.version,
            "config_schema": cls.config_schema,
            "config_drivable": cls.config_drivable,
        }


class ConditionPlugin(PluginBase):
    """条件检查插件基类"""

    @abstractmethod
    def check(self, config: Dict, context: Any, items: List) -> PluginResult:
        pass


class ActionPlugin(PluginBase):
    """动作计算插件基类"""

    @abstractmethod
    def calculate(self, config: Dict, items: List, context: Any) -> PluginResult:
        pass

    def apply_limits(
        self,
        discount: Decimal,
        total_amount: Decimal,
        max_discount: Optional[Decimal] = None,
    ) -> Decimal:
        if not isinstance(discount, Decimal):
            discount = Decimal(str(discount))
        if not isinstance(total_amount, Decimal):
            total_amount = Decimal(str(total_amount))
        if max_discount and not isinstance(max_discount, Decimal):
            max_discount = Decimal(str(max_discount))

        if max_discount and discount > max_discount:
            discount = max_discount
        if discount > total_amount:
            discount = total_amount
        if discount < 0:
            discount = Decimal("0")
        return discount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class ScopePlugin(PluginBase):
    """范围过滤插件基类"""

    @abstractmethod
    def filter_items(self, config: Dict, items: List) -> PluginResult:
        pass


class PluginManager:
    """插件管理器（纯内存注册表，无数据库依赖）"""

    def __init__(self):
        self._condition_plugins: Dict[str, Type[ConditionPlugin]] = {}
        self._action_plugins: Dict[str, Type[ActionPlugin]] = {}
        self._scope_plugins: Dict[str, Type[ScopePlugin]] = {}
        self._load_builtin_plugins()

    def _load_builtin_plugins(self):
        from . import builtins

        builtins.register_builtin_plugins(self)

    # ==================== 注册方法 ====================

    def register_condition(self, plugin_class: Type[ConditionPlugin]) -> None:
        if not issubclass(plugin_class, ConditionPlugin):
            raise ValueError(f"{plugin_class} must be a subclass of ConditionPlugin")
        self._condition_plugins[plugin_class.code] = plugin_class

    def register_action(self, plugin_class: Type[ActionPlugin]) -> None:
        if not issubclass(plugin_class, ActionPlugin):
            raise ValueError(f"{plugin_class} must be a subclass of ActionPlugin")
        self._action_plugins[plugin_class.code] = plugin_class

    def register_scope(self, plugin_class: Type[ScopePlugin]) -> None:
        if not issubclass(plugin_class, ScopePlugin):
            raise ValueError(f"{plugin_class} must be a subclass of ScopePlugin")
        self._scope_plugins[plugin_class.code] = plugin_class

    # ==================== 执行方法 ====================

    def check_condition(
        self, condition_type: str, config: Dict, context: Any, items: List
    ) -> bool:
        result = self.check_condition_with_result(condition_type, config, context, items)
        return result.success

    def check_condition_with_result(
        self, condition_type: str, config: Dict, context: Any, items: List
    ) -> PluginResult:
        plugin_class = self._condition_plugins.get(condition_type)
        if not plugin_class:
            return PluginResult(
                success=False, message=f"未找到条件插件: {condition_type}"
            )
        try:
            plugin = plugin_class()
            return plugin.check(config, context, items)
        except Exception as e:
            return PluginResult(success=False, message=f"条件检查异常: {e}")

    def calculate_action(
        self, action_type: str, config: Dict, items: List, context: Any
    ) -> Tuple[Decimal, List, str]:
        plugin_class = self._action_plugins.get(action_type)
        if not plugin_class:
            return Decimal("0"), [], f"未找到动作插件: {action_type}"
        try:
            plugin = plugin_class()
            result = plugin.calculate(config, items, context)
            if not result.success:
                return Decimal("0"), [], result.message or "优惠计算失败"
            data = result.data or {}
            discount = Decimal(str(data.get("discount", 0)))
            rewards = data.get("rewards", [])
            return discount, rewards, result.message or ""
        except Exception as e:
            return Decimal("0"), [], f"优惠计算异常: {e}"

    def filter_scope(self, scope_type: str, config: Dict, items: List) -> List:
        plugin_class = self._scope_plugins.get(scope_type)
        if not plugin_class:
            return items
        try:
            plugin = plugin_class()
            result = plugin.filter_items(config, items)
            if not result.success or result.data is None:
                return []
            if isinstance(result.data, dict):
                return result.data.get("filtered_items", [])
            return result.data
        except Exception:
            return []

    # ==================== 查询方法 ====================

    def has_condition_plugin(self, code: str) -> bool:
        return code in self._condition_plugins

    def has_action_plugin(self, code: str) -> bool:
        return code in self._action_plugins

    def has_scope_plugin(self, code: str) -> bool:
        return code in self._scope_plugins

    def get_available_conditions(self) -> List[Dict]:
        return [cls.get_metadata() for cls in self._condition_plugins.values()]

    def get_available_actions(self) -> List[Dict]:
        return [cls.get_metadata() for cls in self._action_plugins.values()]

    def get_available_scopes(self) -> List[Dict]:
        return [cls.get_metadata() for cls in self._scope_plugins.values()]


class ConfigDrivenCondition(ConditionPlugin):
    """
    配置驱动的条件插件

    通过 JSON 配置定义简单比较逻辑，无需编写代码。
    支持的比较操作: eq, ne, gt, gte, lt, lte, in, contains
    """
    code = "_config_driven_condition"
    name = "配置驱动条件"
    config_drivable = True
    config_schema = {
        "type": "object",
        "required": ["field", "operator", "value"],
        "properties": {
            "field": {"type": "string", "description": "字段路径，如 context.user_group"},
            "operator": {
                "type": "string",
                "enum": ["eq", "ne", "gt", "gte", "lt", "lte", "in", "contains"],
            },
            "value": {"description": "比较值"},
            "default_result": {"type": "boolean", "default": False},
        },
    }

    def check(self, config: Dict, context: Any, items: List) -> PluginResult:
        field_path = config.get("field", "")
        operator = config.get("operator", "eq")
        compare_value = config.get("value")
        default_result = config.get("default_result", False)

        actual_value = self._get_field_value(field_path, context, items)
        if actual_value is None:
            return PluginResult(
                success=default_result,
                message=f"字段 {field_path} 不存在，使用默认值",
            )

        result = self._compare(actual_value, operator, compare_value)
        return PluginResult(
            success=result,
            data={"field": field_path, "actual": actual_value, "expected": compare_value},
        )

    def _get_field_value(self, field_path: str, context: Any, items: List) -> Any:
        if field_path.startswith("context."):
            attr = field_path[8:]
            return getattr(context, attr, None)
        elif field_path == "items.total_amount":
            return sum(item.total_amount for item in items)
        elif field_path == "items.total_quantity":
            return sum(item.quantity for item in items)
        elif field_path == "items.count":
            return len(items)
        return None

    def _compare(self, actual: Any, operator: str, expected: Any) -> bool:
        try:
            if operator == "eq":
                return actual == expected
            elif operator == "ne":
                return actual != expected
            elif operator == "gt":
                return actual > expected
            elif operator == "gte":
                return actual >= expected
            elif operator == "lt":
                return actual < expected
            elif operator == "lte":
                return actual <= expected
            elif operator == "in":
                return actual in expected
            elif operator == "contains":
                return expected in actual
        except Exception:
            return False
        return False


class ConfigDrivenAction(ActionPlugin):
    """
    配置驱动的动作插件

    通过 JSON 配置定义简单优惠计算，无需编写代码。
    支持的计算类型: fixed, percentage, formula
    """
    code = "_config_driven_action"
    name = "配置驱动动作"
    config_drivable = True
    config_schema = {
        "type": "object",
        "required": ["calculation_type"],
        "properties": {
            "calculation_type": {
                "type": "string",
                "enum": ["fixed", "percentage", "formula"],
            },
            "value": {"type": "number", "description": "固定值或百分比"},
            "formula": {"type": "string", "description": "公式表达式"},
        },
    }

    def calculate(self, config: Dict, items: List, context: Any) -> PluginResult:
        calc_type = config.get("calculation_type")
        total_amount = sum(item.total_amount for item in items)
        discount = Decimal("0")

        if calc_type == "fixed":
            discount = Decimal(str(config.get("value", 0)))
        elif calc_type == "percentage":
            rate = Decimal(str(config.get("value", 0)))
            discount = total_amount * rate / Decimal("100")
        elif calc_type == "formula":
            formula = config.get("formula", "0")
            discount = self._safe_eval(formula, {
                "total": total_amount,
                "quantity": sum(item.quantity for item in items),
            })

        discount = self.apply_limits(discount, total_amount)
        return PluginResult(
            success=True,
            data={"discount": discount, "rewards": []},
        )

    def _safe_eval(self, formula: str, variables: Dict) -> Decimal:
        try:
            allowed_chars = set("0123456789.+-*/() ")
            for var_name in variables:
                allowed_chars.add(var_name)

            expr = formula
            for var_name, var_value in variables.items():
                expr = expr.replace(var_name, str(var_value))

            if not all(c in allowed_chars for c in expr):
                return Decimal("0")

            result = eval(expr, {"__builtins__": {}}, {})
            return Decimal(str(result))
        except Exception:
            return Decimal("0")
