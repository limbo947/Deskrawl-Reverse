# -*- coding: utf-8 -*-
"""编辑撤销/重做（A5）：整档快照式，一个 QUndoStack 管全应用。

为什么用「整档快照 + 事后比对」而不是给每类编辑写一个命令类：
编辑入口有十几个（面板数值、词条行、装配增删、目标勾选、参考技能…），逐个写命令既能漏
又能与 widget 内部状态打架；而 `profile.to_dict()` 是唯一事实源的完整投影，比对两份快照
即可判定「这次到底改了什么」，且天然覆盖将来新增的字段。代价是每次编辑多一次序列化
（实测亚毫秒）。副作用是撤销后草稿对象被整体替换——所以必须整页 reload 重建编辑器，
不能指望旧控件还握着正确的引用。

视图态（当前槽 / 「与当前装备相同」记忆位）不算编辑：切槽看一眼不该占掉一步撤销。
"""
import copy
import time

from PySide6.QtGui import QUndoCommand, QUndoStack

# 不算「编辑」的字段：随会话持久化，但改变它们不改变任何数值
_VIEW_FIELDS = ('compare_slot', 'like_current_pref')

# 合并窗口：连续同类改动（逐字符输入名称、连点微调）合成一步，否则一次输入要 undo 十几次
_MERGE_WINDOW = 0.8

# 快照差异 → 撤销菜单里的中文动作名（按「数据块」优先，越具体越先判）
_LABELS = [
    ('assembled', '装配增删'),
    ('slot_current', '当前件'),
    ('weapon_current', '当前武器'),
    ('slot_candidate', '候选件'),
    ('weapon_candidate', '候选武器'),
    ('target', '目标设置'),
    ('paragon', '巅峰点数'),
    ('base', '面板数值'),
    ('ability_mods', '天赋修正'),
    ('talent_', '天赋修正'),
    ('bag_items', '背包数据'),
    ('skill_', '参考技能'),
    ('damage_type', '伤害类型'),
    ('hero_class', '职业'),
    ('primary_stat', '职业主属性'),
    ('name', '构建名称'),
]


def snapshot(profile) -> dict:
    """可比较的档案投影（剔除视图态字段）。

    候选草稿里的 `like_current` 也要剔：它是「与当前装备相同」开关的记忆位，勾选确实会改
    词条（那部分照常入栈），但开关标记本身跟着换槽自动沿用，留着会让「切槽看一眼」长出新步骤。
    """
    data = profile.to_dict()
    for key in _VIEW_FIELDS:
        data.pop(key, None)
    for key in ('weapon_candidate', 'slot_candidate'):
        block = data.get(key)
        if isinstance(block, dict):
            if 'like_current' in block:
                block['like_current'] = False
            for draft in block.values():
                if isinstance(draft, dict):
                    draft.pop('like_current', None)
    return data


def label_for(before: dict, after: dict) -> str:
    """两份快照 → 动作名（只用于菜单文案，判错也不影响正确性）。"""
    keys = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
    for prefix, label in _LABELS:
        if any(k == prefix or k.startswith(prefix) for k in keys):
            return label
    return '编辑'


class _SnapshotCommand(QUndoCommand):
    """一次编辑的前后快照；撤销/重做就是把对应快照灌回 profile 再整页回填。"""

    ID = 4242

    def __init__(self, profile, before, after, label, on_applied):
        super().__init__(label)
        self._profile = profile
        self._before = before
        self._after = after
        self._on_applied = on_applied
        self._ts = time.monotonic()

    def id(self):                     # noqa: A003 —— Qt 覆写（用于 mergeWith 配对）
        return self.ID

    def mergeWith(self, other):       # noqa: N802 —— Qt 覆写
        """同动作、短时间窗内 → 合并成一步（保留最早的 before、最新的 after）。"""
        if other is None or not isinstance(other, _SnapshotCommand):
            return False
        if other.text() != self.text() or other._ts - self._ts > _MERGE_WINDOW:
            return False
        self._after = other._after
        self._ts = other._ts
        return True

    def undo(self):
        self._apply(self._before)

    def redo(self):
        self._apply(self._after)

    def _apply(self, target):
        from .core.profile import CharacterProfile

        if snapshot(self._profile) == target:
            return                    # push 时 QUndoStack 会调一次 redo：内容已就位就不必再灌一遍
        self._profile.replace_with(CharacterProfile.from_dict(copy.deepcopy(target)))
        self._on_applied()


class ProfileUndoStack(QUndoStack):
    """档案撤销栈：`capture()` 在每次编辑后调用，靠快照差异决定入栈与否。"""

    def __init__(self, profile, on_applied, parent=None):
        super().__init__(parent)
        self._profile = profile
        self._on_applied = on_applied
        self._snapshot = snapshot(profile)
        self.setUndoLimit(100)
        # 撤销/重做后基线必须跟着回到「当前实际状态」：否则下一次编辑会把旧的新快照当 before，
        # 再按 Ctrl+Z 就跳到用户从没见过的状态（栈本身不报错，只是数值不对）。
        self.indexChanged.connect(lambda _index: self._sync_baseline())

    def capture(self) -> bool:
        """比对当前档案与上次提交的快照；变了就压一条（可合并）。返回是否产生了新步骤。"""
        now = snapshot(self._profile)
        if now == self._snapshot:
            return False
        label = label_for(self._snapshot, now)
        self.push(_SnapshotCommand(self._profile, self._snapshot, now, label, self._on_applied))
        self._snapshot = now
        return True

    def _sync_baseline(self):
        """把比对基线对齐到档案当前状态（撤销/重做/入栈后由 indexChanged 触发）。"""
        self._snapshot = snapshot(self._profile)

    def reset(self):
        """换数据源（导入/加载构建）后重新起算：那些操作本身不入撤销栈。"""
        self.clear()
        self._sync_baseline()
