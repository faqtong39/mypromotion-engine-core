"""
范围过滤插件（内置 5 个核心范围）

去 Django 化改动：
- 删除 ProductPoolScope 的动态数据库查询（商品池改为静态 SKU 列表）
- 所有范围过滤只依赖 items 的直接属性
"""
from typing import Any, Dict, List

from .base import PluginResult, ScopePlugin


class AllItemsScope(ScopePlugin):
    """全部商品"""
    code = "all_items"
    name = "全部商品"
    description = "适用于所有商品"
    config_schema = {"type": "object", "properties": {}}

    def filter_items(self, config: Dict, items: List) -> PluginResult:
        return PluginResult(success=True, data=items, message=f"全部商品: {len(items)}件")


class SpecificItemsScope(ScopePlugin):
    """指定商品（静态 SKU 列表）"""
    code = "specific_items"
    name = "指定商品"
    description = "仅适用于指定SKU商品"
    config_schema = {
        "type": "object",
        "properties": {"skus": {"type": "array", "description": "SKU编码列表"}},
    }

    def filter_items(self, config: Dict, items: List) -> PluginResult:
        allowed_ids = set(config.get("skus") or [])
        filtered = [item for item in items if item.sku in allowed_ids]
        return PluginResult(success=True, data=filtered, message=f"SKU过滤: {len(filtered)}/{len(items)}件")


class CategoryItemsScope(ScopePlugin):
    """指定品类"""
    code = "category_items"
    name = "指定品类"
    description = "仅适用于指定品类商品"
    config_schema = {
        "type": "object",
        "properties": {"category_ids": {"type": "array", "description": "品类ID列表"}},
    }

    def filter_items(self, config: Dict, items: List) -> PluginResult:
        raw_categories = config.get("category_ids") or []
        allowed_categories = set(str(c) for c in raw_categories)
        filtered = [item for item in items if str(item.category_id) in allowed_categories]
        return PluginResult(success=True, data=filtered, message=f"品类过滤: {len(filtered)}/{len(items)}件")


class TagItemsScope(ScopePlugin):
    """按标签选择"""
    code = "tag_items"
    name = "按标签选择"
    description = "选择特定标签的商品"
    config_schema = {
        "type": "object",
        "properties": {"tags": {"type": "array", "description": "标签列表"}},
    }

    def filter_items(self, config: Dict, items: List) -> PluginResult:
        target_tags = set(config.get("tags") or [])
        filtered = []
        for item in items:
            item_tags = getattr(item, "tags", []) or []
            if isinstance(item_tags, str):
                item_tags = [item_tags]
            if set(item_tags) & target_tags:
                filtered.append(item)
        return PluginResult(success=True, data=filtered, message=f"标签过滤: {len(filtered)}/{len(items)}件")


class ExceptItemsScope(ScopePlugin):
    """排除特定商品"""
    code = "except_items"
    name = "排除特定商品"
    description = "排除指定SKU商品"
    config_schema = {
        "type": "object",
        "properties": {"except_skus": {"type": "array", "description": "要排除的SKU编码列表"}},
    }

    def filter_items(self, config: Dict, items: List) -> PluginResult:
        excluded_ids = set(config.get("except_skus") or [])
        filtered = [item for item in items if item.sku not in excluded_ids]
        return PluginResult(success=True, data=filtered, message=f"排除过滤: {len(filtered)}/{len(items)}件")
