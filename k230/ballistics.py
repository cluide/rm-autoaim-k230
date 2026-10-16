# -*- coding: utf-8 -*-
"""
弹道解算

要解决的问题：目标在水平距离 L、比枪口高 h 的地方，初速 v0，枪该抬多少度？

思路（工程上最省算力又够准）
---------------------------
1. 启动时用数值积分算一条“水平发射”的落点曲线 drop(x)：子弹飞过水平距离 x 时
   掉下去多少米；同时记录飞行时间 tof(x)。只算一次，约 600~1500 个积分步。
2. 之后每帧只做插值：  theta = atan2(h + drop(L), L)
   这是经典的弹道补偿近似。在 RM 的小角度（< 5°）下，它与“精确迭代求解”的
   差别远小于 0.5 mrad（5 m 处约 2.5 mm），完全够用。

为什么不在每帧迭代求解：K230 上是 MicroPython，每帧 20 次二分 × 30 步积分
要 2~5 ms，白吃帧率。启动时算一次表只要 10 ms 左右。

阻力模型：a = -k·|v|·v  +  重力
k 是唯一需要标定的参数（用打靶数据拟合，见 docs/tuning.md）。
k = 0 时退化成纯重力，可以用来对照。
"""

import math


class BallisticSolver(object):
    """一条弹道表 + 查表接口。初速 v 是由电控实时给的，变了就 rebuild。"""

    __slots__ = ("v0", "k", "g", "dx", "x_max", "xs", "drops", "tofs", "valid")

    def __init__(self, v0, k=0.02, g=9.81, x_max=12.0, dx=0.5):
        self.v0 = float(v0)
        self.k = float(k)
        self.g = float(g)
        self.dx = float(dx)
        self.x_max = float(x_max)
        self.xs = []
        self.drops = []
        self.tofs = []
        self.valid = False
        self.rebuild(v0)

    # ------------------------------------------------------------------
    # 建表
    # ------------------------------------------------------------------
    def rebuild(self, v0):
        """用当前初速重算落点曲线。约 10 ms，只在初速明显变化时调用。"""
        self.v0 = float(v0)
        k = self.k
        g = self.g
        dx = self.dx
        x_max = self.x_max

        xs = []
        drops = []
        tofs = []

        # 半隐式欧拉积分，dt 取 1 ms：12 m / 15 m·s⁻¹ 约 0.9 s -> 900 步
        dt = 0.001
        x = 0.0
        z = 0.0
        vx = self.v0
        vz = 0.0
        t = 0.0
        next_x = dx
        while next_x <= x_max + 1e-9 and t < 4.0:
            sp = math.sqrt(vx * vx + vz * vz)
            ax = -k * sp * vx
            az = -k * sp * vz - g
            vx += ax * dt
            vz += az * dt
            x += vx * dt
            z += vz * dt
            t += dt
            if x >= next_x:
                xs.append(next_x)
                drops.append(-z)          # 掉下去多少（正数）
                tofs.append(t)
                next_x += dx

        if len(xs) == 0:
            # 初速离谱（比如 0），退化成纯重力抛物线，保证不出异常
            xs = [dx]
            drops = [0.5 * g * (dx / max(self.v0, 1.0)) ** 2]
            tofs = [dx / max(self.v0, 1.0)]

        self.xs = xs
        self.drops = drops
        self.tofs = tofs
        self.valid = True
        return self

    def needs_rebuild(self, v_new, dv=1.0):
        return (not self.valid) or abs(v_new - self.v0) > dv

    # ------------------------------------------------------------------
    # 查表
    # ------------------------------------------------------------------
    @staticmethod
    def _interp(xs, ys, x):
        n = len(xs)
        if x <= xs[0]:
            # 近处用抛物线/匀速近似，线性外推到 0
            return ys[0] * (x / xs[0]) if xs[0] > 0 else 0.0
        if x >= xs[n - 1]:
            return ys[n - 1]          # 超量程就不外推，宁可直接命中
        # 二分找区间（n 只有 24，线性扫也够，但二分更稳）
        lo = 0
        hi = n - 1
        while hi - lo > 1:
            mid = (lo + hi) >> 1
            if xs[mid] <= x:
                lo = mid
            else:
                hi = mid
        x0 = xs[lo]
        x1 = xs[lo + 1]
        y0 = ys[lo]
        y1 = ys[lo + 1]
        if x1 - x0 < 1e-9:
            return y0
        return y0 + (y1 - y0) * (x - x0) / (x1 - x0)

    def drop(self, L):
        """水平距离 L 处的下落量（米，正数）"""
        return self._interp(self.xs, self.drops, L)

    def time_of_flight(self, L):
        """飞到水平距离 L 需要的时间（秒），用来做提前量"""
        if L < self.dx:
            return L / self.v0 if self.v0 > 1e-3 else 0.0
        return self._interp(self.xs, self.tofs, L)

    def solve_pitch(self, L, h):
        """
        求枪管仰角（弧度）。
        L: 水平距离(m)  h: 目标比枪口高多少(m，高为正)
        """
        if L < 1e-3:
            return 0.0
        drop = self.drop(L)
        return math.atan2(h + drop, L)

    # ------------------------------------------------------------------
    # 精确解（只给电脑上的自检 / 参数拟合用，板端不要每帧调）
    # ------------------------------------------------------------------
    def solve_pitch_exact(self, L, h, lo=-0.6, hi=1.2, iters=40):
        """二分 + 数值积分求精确仰角，用于验证查表近似的误差"""
        for _ in range(iters):
            mid = 0.5 * (lo + hi)
            land = self._landing(mid, L)
            if land < h:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi)

    def _landing(self, theta, L):
        """以仰角 theta 发射，飞到水平距离 L 时的高度"""
        k = self.k
        g = self.g
        vx = self.v0 * math.cos(theta)
        vz = self.v0 * math.sin(theta)
        dt = 0.0005
        x = 0.0
        z = 0.0
        while x < L and z > -50.0:
            sp = math.sqrt(vx * vx + vz * vz)
            vx += -k * sp * vx * dt
            vz += (-k * sp * vz - g) * dt
            x += vx * dt
            z += vz * dt
        return z


def gravity_drop(L, h, v0, g=9.81):
    """无阻力闭式解，留给“第 1 天先跑通”用，也是标定 k 的基准"""
    if L < 1e-3:
        return 0.0
    v2 = v0 * v0
    disc = v2 * v2 - g * (g * L * L + 2.0 * h * v2)
    if disc < 0.0:
        return None                     # 打不到
    return math.atan((v2 - math.sqrt(disc)) / (g * L))
