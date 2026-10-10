# -*- coding: utf-8 -*-
"""四类装配（宝石/符文/天赋/套装）的「部位/等级」参数与文案单一来源。

历史上这份定义在 candidate_rank_view 与 assembly_browser 各复制一份（且与 profile 的
COMPARE_SLOTS 槽 id 是两套编号体系：这里是宝石镶嵌部位 category 0/1/2），合并为装配中心时
收敛到本模块，避免再漂移。
"""
from __future__ import annotations

from typing import List, Tuple

# 宝石镶嵌部位 category（AssemblyItem.category 仅宝石使用；0=护甲 1=饰品 2=武器）
GEM_CATEGORIES: List[Tuple[int, str]] = [(0, '护甲'), (1, '饰品'), (2, '武器')]
# 非宝石类别的等级参数标签
LEVEL_LABELS = {'rune': '符文等级', 'talent': '天赋点数', 'runeset': '套装件数'}
# 默认武器孔：本工具以「武器对比」为主，护甲孔宝石多半不加 DPS（历史默认值，勿改）
DEFAULT_GEM_CATEGORY = 2


def gem_label(category: int) -> str:
    """部位 category → 中文名；非法值回落占位，避免已装配清单因脏数据 KeyError 崩溃。"""
    for value, label in GEM_CATEGORIES:
        if value == int(category):
            return label
    return f'部位{category}'


def kind_param_label(kind: str) -> str:
    """参数条的标签：宝石调部位、其余按类别叫等级/点数/件数。"""
    return '镶嵌部位' if kind == 'gem' else LEVEL_LABELS.get(kind, '等级')


def assembly_params(kind: str, *, level: int, category: int) -> Tuple[int, int]:
    """归一化为 AssemblyItem(level, category)：宝石等级恒 1（区别由部位表达）、非宝石 category 恒 2。"""
    if kind == 'gem':
        return 1, int(category)
    return int(level), DEFAULT_GEM_CATEGORY


def assembled_extra_text(kind: str, level: int, category: int) -> str:
    """已装配清单行尾参数文案（与加入时的参数语义一一对应）。"""
    if kind == 'gem':
        return f'部位{gem_label(category)}'
    return f'{LEVEL_LABELS.get(kind, "等级")}{level}'


__all__ = ['GEM_CATEGORIES', 'LEVEL_LABELS', 'DEFAULT_GEM_CATEGORY',
           'gem_label', 'kind_param_label', 'assembly_params', 'assembled_extra_text']
