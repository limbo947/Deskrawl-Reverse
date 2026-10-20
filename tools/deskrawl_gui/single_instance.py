# -*- coding: utf-8 -*-
"""单实例锁（E8）：第二个进程把已有窗口切到前台，而不是只弹一句「已在运行」。

为什么单独成文件：这一层只谈 QLocalServer/QLocalSocket，与主窗口装配无关；塞回 app.py
会让那个文件继续长，而 app.py 已接近行数上限（棘轮规则要求只降不升）。

为什么是「三态原因」而不是 bool/None：调用方必须区分
  · 已有实例 → 应退出（会话文件被别人持有）；
  · 监听失败 → 应提示后照常启动（单实例只保护会话文件，不该让工具打不开）。
把两者混成一个 None，就会把「锁坏了」当成「别人在跑」，用户从此打不开工具。
"""
from PySide6.QtNetwork import QLocalServer, QLocalSocket

NAME = 'DeskrawlCalcGui'          # 固定名：便携版与源码运行共用同一把锁，双开即被拦


def acquire():
    """抢锁：返回 (QLocalServer | None, 原因)。

    原因取值：'' = 拿到锁；'exists' = 已有实例在跑；其余 = 监听失败的中文原因。
    上次异常退出可能留下残锁，故先 removeServer 再 listen（否则重启后自己把自己挡住）。
    """
    probe = QLocalSocket()
    probe.connectToServer(NAME)
    if probe.waitForConnected(200):
        probe.disconnectFromServer()       # 连上即「已有实例」：这次连接会让对方前置窗口
        return None, 'exists'
    QLocalServer.removeServer(NAME)
    server = QLocalServer()
    if not server.listen(NAME):
        why = server.errorString()
        server.deleteLater()
        return None, f'本地套接字监听失败：{why}'
    return server, ''


def activate(win, server):
    """消费待处理连接并把窗口前置（第二实例的请求就是「把我在用的那个窗口拿上来」）。

    必须逐个 nextPendingConnection：不消费，连接对象会一直挂在 server 上；调用方还在
    启动时补收一次，覆盖「抢锁成功 → 窗口建好」之间到达的连接（那时信号还没有接收者）。
    """
    while server.hasPendingConnections():
        conn = server.nextPendingConnection()
        if conn is not None:
            conn.disconnectFromServer()
            conn.deleteLater()
    if win is None:
        return
    if win.isMinimized():
        win.showNormal()
    win.raise_()
    win.activateWindow()


__all__ = ['NAME', 'acquire', 'activate']
