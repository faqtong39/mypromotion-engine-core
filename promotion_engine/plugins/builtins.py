"""
内置插件注册中心

负责将所有内置的条件、动作、范围插件注册到 PluginManager。
"""
from . import conditions, actions, scopes


def register_builtin_plugins(manager):
    """注册所有内置插件"""
    # 条件插件（12个）
    manager.register_condition(conditions.AmountThresholdCondition)
    manager.register_condition(conditions.QtyThresholdCondition)
    manager.register_condition(conditions.UserGroupCondition)
    manager.register_condition(conditions.ShippingMethodCondition)
    manager.register_condition(conditions.ChannelCondition)
    manager.register_condition(conditions.TimeWindowCondition)
    manager.register_condition(conditions.DayOfWeekCondition)
    manager.register_condition(conditions.MonthlyDateCondition)
    manager.register_condition(conditions.IsFirstOrderCondition)
    manager.register_condition(conditions.PaymentMethodCondition)
    manager.register_condition(conditions.ComboItemsCondition)
    manager.register_condition(conditions.UserBirthdayCondition)

    # 动作插件（12个）
    manager.register_action(actions.FixedAmountAction)
    manager.register_action(actions.PercentageAction)
    manager.register_action(actions.FixedPriceAction)
    manager.register_action(actions.TieredPriceAction)
    manager.register_action(actions.TieredAmountAction)
    manager.register_action(actions.FreeShippingAction)
    manager.register_action(actions.PointsDeductAction)
    manager.register_action(actions.BalanceDeductAction)
    manager.register_action(actions.PreSaleAction)
    manager.register_action(actions.DiscountAmountLimitAction)
    manager.register_action(actions.InstallmentFreeAction)
    manager.register_action(actions.RandomReductionAction)

    # 范围插件（5个，不含动态商品池）
    manager.register_scope(scopes.AllItemsScope)
    manager.register_scope(scopes.SpecificItemsScope)
    manager.register_scope(scopes.CategoryItemsScope)
    manager.register_scope(scopes.TagItemsScope)
    manager.register_scope(scopes.ExceptItemsScope)
