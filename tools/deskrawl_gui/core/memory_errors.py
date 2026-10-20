# -*- coding: utf-8 -*-
"""内存导入链的错误态：带 code 的统一异常 + 「code → 中文文案」的稳定映射。

为什么单独成文件：定位基元（memory_locate）与快照校验（memory_validate）都要抛它，
而两者又都被 memory_import 反向依赖——放在任一方都会绕成循环导入。它是叶子模块，
只依赖 stdlib。

文案也放这里而不是主窗口：错误态与文案是一对事实（新增 code 必须同时给用户一句人话），
分居两处时最容易出现「抛了新 code、弹窗却回落到通用文案」的静默降级。
"""

# 六类错误态 → (弹窗标题, 中文正文)。未识别的 code 一律回落到「读取校验失败」，
# 保证任何异常都不会裸抛英文堆栈给用户。
IMPORT_ERROR_TEXTS = {
    'no_process': ('游戏未运行',
                   '未找到游戏进程。请先启动游戏并进入角色，再使用「数据导入」。'),
    'no_hero': ('角色未加载',
                '游戏在运行，但未检测到已加载的角色（可能停留在主菜单/加载中）。\n请进入角色后重试。'),
    'denied': ('权限不足',
               '打开游戏进程被拒绝：游戏可能以管理员身份运行。\n请以管理员身份重启本工具后重试。'),
    'py32': ('Python 位数不符',
             '当前 Python 为 32 位，无法读取 64 位游戏进程。\n请使用 64 位解释器运行本工具。'),
    'fingerprint': ('版本指纹不符',
                    '游戏版本或静态数据已变化，导入被拒绝（防止读出错位数据）。\n'
                    '请重新导出 schema/so_dump，并更新 memory_offsets.json 指纹后重试。'),
    'data': ('读取校验失败',
             '读取结果未通过结构/值域/双读一致性校验（游戏状态可能在变化）。\n'
             '请稍后重试（城镇/菜单中更稳定）。'),
}


class MemoryImportError(Exception):
    """导入失败。kind: 'env'=环境/进程/角色未加载；'version'=指纹失配；'data'=结构/校验。

    code 供 GUI 侧做「六类错误态 → 中文文案」的稳定映射（不靠消息子串猜），
    取值：no_process / no_hero / denied / py32 / fingerprint；空串=其他数据类失败。
    """

    def __init__(self, msg, kind='data', code=''):
        super().__init__(msg)
        self.kind = kind
        self.code = code


def describe_import_error(exc) -> tuple:
    """导入异常 → (弹窗标题, 中文正文)。GUI 与自检共用这一处映射。"""
    code = getattr(exc, 'code', '') or ''
    title, text = IMPORT_ERROR_TEXTS.get(code, IMPORT_ERROR_TEXTS['data'])
    return title, f'{text}\n\n（详情：{exc}）'


__all__ = ['MemoryImportError', 'IMPORT_ERROR_TEXTS', 'describe_import_error']
