# -*- coding: utf-8 -*-
"""
目标跟踪滤波

核心思想：不要“平滑像素/角度”，而要在**世界系**里跟踪目标的 3D 位置。
因为云台自己会转，角度的抖动很大一部分只是“相机在动”，像素值本身没意义。
每个观测先用当时的 yaw/pitch 转成世界系坐标，再用匀速模型（CV）卡尔曼滤波，
预测时直接外推到“真正开火那一刻”。

降维技巧
--------
世界系里三个轴的噪声可以近似解耦，所以不做 6×6 矩阵运算，
而是并排跑 3 个 2 状态的 1 维卡尔曼（位置+速度）。
MicroPython 下这样每个轴只要十几次乘法，比矩阵库快得多，而且一样准。

状态: [p, v]   观测: p
F = [[1, dt], [0, 1]]
Q = q · [[dt³/3, dt²/2], [dt²/2, dt]]
H = [1, 0]      R = r
"""

import math


class CV1D(object):
    """一维匀速模型卡尔曼滤波"""

    __slots__ = ("p", "v", "p00", "p01", "p11", "q", "r", "ok")

    def __init__(self, q, r):
        self.q = float(q)
        self.r = float(r)
        self.p = 0.0
        self.v = 0.0
        self.p00 = 1.0
        self.p01 = 0.0
        self.p11 = 1.0
        self.ok = False

    def reset(self, z):
        self.p = float(z)
        self.v = 0.0
        # 第一次观测很不确定：位置方差给大一点，速度方差给大一点，
        # 这样前一两个观测就能把速度拉起来
        self.p00 = self.r * 100.0
        self.p01 = 0.0
        self.p11 = 100.0
        self.ok = True

    def predict(self, dt):
        if not self.ok:
            return
        p00 = self.p00 + 2.0 * dt * self.p01 + dt * dt * self.p11
        p01 = self.p01 + dt * self.p11
        p11 = self.p11
        self.p = self.p + self.v * dt
        dt2 = dt * dt
        self.p00 = p00 + self.q * dt2 * dt / 3.0
        self.p01 = p01 + self.q * dt2 * 0.5
        self.p11 = p11 + self.q * dt

    def update(self, z):
        if not self.ok:
            self.reset(z)
            return
        y = float(z) - self.p
        S = self.p00 + self.r
        if S < 1e-12:
            return
        k0 = self.p00 / S
        k1 = self.p01 / S
        p01_old = self.p01
        self.p = self.p + k0 * y
        self.v = self.v + k1 * y
        self.p00 = self.p00 - k0 * self.p00
        self.p01 = p01_old - k0 * p01_old
        self.p11 = self.p11 - k1 * p01_old

    def predict_at(self, dt):
        """不改变状态，返回 dt 秒后的位置"""
        return self.p + self.v * dt


class Tracker(object):
    """世界系下的 3D 目标跟踪器（单个目标）"""

    __slots__ = ("fx", "fy", "fz", "t", "inited", "miss", "hits")

    def __init__(self, q=2.0, r=4.0e-4):
        self.fx = CV1D(q, r)
        self.fy = CV1D(q, r)
        self.fz = CV1D(q, r)
        self.t = 0.0
        self.inited = False
        self.miss = 0
        self.hits = 0

    # ------------------------------------------------------------------
    def reset(self):
        self.fx.ok = False
        self.fy.ok = False
        self.fz.ok = False
        self.inited = False
        self.miss = 0
        self.hits = 0

    def is_valid(self):
        return self.inited and self.fx.ok

    def update(self, pos, now_s):
        """pos: 世界系 3D 点（相机光心为原点）；now_s: 秒"""
        if not self.inited:
            self.fx.reset(pos[0])
            self.fy.reset(pos[1])
            self.fz.reset(pos[2])
            self.t = now_s
            self.inited = True
            self.miss = 0
            self.hits = 1
            return

        dt = now_s - self.t
        if dt < 0.0:
            dt = 0.0
        elif dt > 0.5:          # 卡了/断线，别用大 dt 硬推
            dt = 0.5
        self.fx.predict(dt)
        self.fy.predict(dt)
        self.fz.predict(dt)
        self.fx.update(pos[0])
        self.fy.update(pos[1])
        self.fz.update(pos[2])
        self.t = now_s
        self.miss = 0
        if self.hits < 1000000:
            self.hits += 1

    def mark_miss(self):
        self.miss += 1
        return self.miss

    # ------------------------------------------------------------------
    def pos(self):
        return (self.fx.p, self.fy.p, self.fz.p)

    def vel(self):
        return (self.fx.v, self.fy.v, self.fz.v)

    def predict_at(self, now_s, horizon_s=0.0):
        """返回 now_s + horizon_s 时刻的预测位置"""
        dt = (now_s - self.t) + horizon_s
        if dt < 0.0:
            dt = 0.0
        elif dt > 1.0:
            dt = 1.0           # 预测太远会飞出天外，限幅
        return (self.fx.predict_at(dt),
                self.fy.predict_at(dt),
                self.fz.predict_at(dt))

    def speed(self):
        return math.sqrt(self.fx.v ** 2 + self.fy.v ** 2 + self.fz.v ** 2)
