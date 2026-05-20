"""
互斥检查测试
"""
from promotion_engine.mutex import MutexChecker, MutexCheckResult
from promotion_engine.types import MutexGroup, SpecialMutexRule


def test_mutex_group():
    """策略类型互斥组测试"""
    groups = {
        "basic_discount": {
            "name": "基础折扣互斥组",
            "strategies": ["full_reduction", "full_discount", "special_price"],
            "priority": 100,
        }
    }
    checker = MutexChecker(mutex_groups=groups)

    class FakeRule:
        def __init__(self, code, stype):
            self.promotion_code = code
            self.strategy_type = stype
            self.stack_config = {}

    rule1 = FakeRule("R1", "full_reduction")
    rule2 = FakeRule("R2", "full_discount")

    # 先应用 R1
    checker.mark_applied(rule1)

    # R2 应该被互斥
    info = checker.check_mutex(rule2, [rule1])
    assert info.result == MutexCheckResult.MUTEX_BY_GROUP
    assert "基础折扣互斥组" in info.message or "mutex" in info.message


def test_special_mutex_bidirectional():
    """双向特殊互斥测试"""
    special_rules = [
        SpecialMutexRule(
            rule_a_id="R1",
            rule_b_id="R2",
            is_bidirectional=True,
            is_active=True,
        )
    ]
    checker = MutexChecker(special_mutex_rules=special_rules)

    class FakeRule:
        def __init__(self, code):
            self.promotion_code = code
            self.strategy_type = "test"
            self.stack_config = {}

    rule1 = FakeRule("R1")
    rule2 = FakeRule("R2")

    checker.mark_applied(rule1)
    info = checker.check_mutex(rule2, [rule1])
    assert info.result == MutexCheckResult.MUTEX_BY_SPECIAL


def test_stack_config_whitelist():
    """stack_config 白名单测试"""
    checker = MutexChecker()

    class FakeRule:
        def __init__(self, code, stack=None):
            self.promotion_code = code
            self.strategy_type = "test"
            self.stack_config = stack or {}

    rule1 = FakeRule("R1")
    rule2 = FakeRule("R2", stack={"stackable_with": ["R1"]})

    checker.mark_applied(rule1)
    info = checker.check_mutex(rule2, [rule1])
    assert info.result == MutexCheckResult.STACKABLE


def test_stack_config_blacklist():
    """stack_config 黑名单测试"""
    checker = MutexChecker()

    class FakeRule:
        def __init__(self, code, stack=None):
            self.promotion_code = code
            self.strategy_type = "test"
            self.stack_config = stack or {}

    rule1 = FakeRule("R1")
    rule2 = FakeRule("R2", stack={"mutex_with": ["R1"]})

    checker.mark_applied(rule1)
    info = checker.check_mutex(rule2, [rule1])
    assert info.result == MutexCheckResult.MUTEX_BY_GROUP


def test_force_stackable():
    """强制叠加测试"""
    checker = MutexChecker()

    class FakeRule:
        def __init__(self, code):
            self.promotion_code = code
            self.strategy_type = "test"
            self.stack_config = {"force_stackable": True}

    rule1 = FakeRule("R1")
    rule2 = FakeRule("R2")

    checker.mark_applied(rule1)
    info = checker.check_mutex(rule2, [rule1])
    assert info.result == MutexCheckResult.STACKABLE
