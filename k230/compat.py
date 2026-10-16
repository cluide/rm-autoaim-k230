# -*- coding: utf-8 -*-
"""
MicroPython / CPython 兼容层

目的：让 k230/ 下的所有“纯算法”模块（geometry / ballistics / tracker / autoaim）
既能跑在 K230 的 MicroPython 上，也能直接在电脑上用 CPython 跑
（tools/sim_pipeline.py 就是靠这个在电脑上验证算法，不用上板）。
"""

try:
    # MicroPython / CanMV 固件
    from time import ticks_ms, ticks_diff
    from time import sleep_ms as _sleep_ms

    MICROPYTHON = True
except ImportError:                      # CPython（电脑上仿真）
    import time as _time

    MICROPYTHON = False

    def ticks_ms():
        return int(_time.time() * 1000.0)

    def ticks_diff(a, b):
        return a - b

    def _sleep_ms(ms):
        _time.sleep(ms / 1000.0)


class Timer:
    """轻量计时器：elapsed() 返回毫秒"""

    __slots__ = ("t0",)

    def __init__(self):
        self.t0 = ticks_ms()

    def reset(self):
        self.t0 = ticks_ms()

    def elapsed(self):
        return ticks_diff(ticks_ms(), self.t0)


def clamp(v, lo, hi):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v
