# -*- coding: utf-8 -*-
"""内存导入链的错误态：带 code 的统一异常。

为什么单独成文件：定位基元（memory_locate）与快照校验（memory_validate）都要抛它，
而两者又都被 memory_import 反向依赖——放在任一方都会绕成循环导入。它是叶子模块，
只依赖 stdlib。
"""


class MemoryImportError(Exception):
    """导入失败。kind: 'env'=环境/进程/角色未加载；'version'=指纹失配；'data'=结构/校验。

    code 供 GUI 侧做「六类错误态 → 中文文案」的稳定映射（不靠消息子串猜），
    取值：no_process / no_hero / denied / py32 / fingerprint；空串=其他数据类失败。
    """

    def __init__(self, msg, kind='data', code=''):
        super().__init__(msg)
        self.kind = kind
        self.code = code
