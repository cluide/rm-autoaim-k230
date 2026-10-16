# -*- coding: utf-8 -*-
"""
坐标系与几何换算（这是整个自瞄最容易搞错的地方，先把这里对齐）

三个坐标系
----------
世界系 W：x 前, y 左, z 上
           yaw  绕 z 轴，向左（逆时针俯视）为正
           pitch 绕 y 轴，抬头为正
           和电控/陀螺仪的约定一致，零点由电控决定（我们只发增量，所以零点无所谓）

机体系 B：x 前, y 左, z 上（与云台 yaw 轴对齐，即"云台坐标系"）

相机系 C：x 右, y 下, z 沿光轴向前（OpenCV / 单目标定的标准约定）

转换链
------
    C --交换轴--> B --Rz(yaw)·Ry(-pitch)--> W

    x_B =  z_C        x_W = cψcθ·x_B - sψ·y_B - cψsθ·z_B
    y_B = -x_C   =>   y_W = sψcθ·x_B + cψ·y_B - sψsθ·z_B
    z_B = -y_C        z_W = sθ ·x_B +   0 ·y_B + cθ ·z_B

自检
----
self_check() 会把这两条链正反各走一遍，误差必须 < 1e-9。
改了这个文件就先跑 selftest.py，别上板瞎试。
"""

import math


# ----------------------------------------------------------------------
# 基础工具
# ----------------------------------------------------------------------
def wrap_pi(a):
    """把角度折到 (-pi, pi]，防止 ±180° 处跳变"""
    while a > math.pi:
        a -= 2.0 * math.pi
    while a <= -math.pi:
        a += 2.0 * math.pi
    return a


def dir_to_angles(w):
    """世界系方向向量 -> (yaw, pitch)，单位 rad"""
    return math.atan2(w[1], w[0]), math.atan2(w[2], math.hypot(w[0], w[1]))


def angle_between(w1, w2):
    """两个世界系方向向量的夹角（rad），用来做目标选择"""
    n1 = math.sqrt(w1[0] * w1[0] + w1[1] * w1[1] + w1[2] * w1[2])
    n2 = math.sqrt(w2[0] * w2[0] + w2[1] * w2[1] + w2[2] * w2[2])
    if n1 < 1e-9 or n2 < 1e-9:
        return math.pi
    d = (w1[0] * w2[0] + w1[1] * w2[1] + w1[2] * w2[2]) / (n1 * n2)
    if d > 1.0:
        d = 1.0
    elif d < -1.0:
        d = -1.0
    return math.acos(d)


# ----------------------------------------------------------------------
# 坐标系互换
# ----------------------------------------------------------------------
def cam_to_body(p):
    """相机系 -> 机体系"""
    x, y, z = p
    return (z, -x, -y)


def body_to_cam(p):
    """机体系 -> 相机系"""
    x, y, z = p
    return (-y, -z, x)


def body_to_world(p, yaw, pitch):
    """机体系 -> 世界系（先 pitch 后 yaw，与真实云台的运动顺序一致）"""
    cw = math.cos(yaw)
    sw = math.sin(yaw)
    ct = math.cos(pitch)
    st = math.sin(pitch)
    x = p[0]
    y = p[1]
    z = p[2]
    wx = cw * ct * x - sw * y - cw * st * z
    wy = sw * ct * x + cw * y - sw * st * z
    wz = st * x + ct * z
    return (wx, wy, wz)


def world_to_body(p, yaw, pitch):
    """世界系 -> 机体系（上面那个矩阵的转置，不用求逆）"""
    cw = math.cos(yaw)
    sw = math.sin(yaw)
    ct = math.cos(pitch)
    st = math.sin(pitch)
    x = p[0]
    y = p[1]
    z = p[2]
    bx = cw * ct * x + sw * ct * y + st * z
    by = -sw * x + cw * y
    bz = -cw * st * x - sw * st * y + ct * z
    return (bx, by, bz)


def cam_to_world(p, yaw, pitch):
    return body_to_world(cam_to_body(p), yaw, pitch)


def world_to_cam(p, yaw, pitch):
    return body_to_cam(world_to_body(p, yaw, pitch))


# ----------------------------------------------------------------------
# 相机模型
# ----------------------------------------------------------------------
class Camera(object):
    """针孔相机 + 用 bbox 高度反推距离"""

    __slots__ = ("fx", "fy", "cx", "cy")

    def __init__(self, fx, fy, cx, cy):
        self.fx = float(fx)
        self.fy = float(fy)
        self.cx = float(cx)
        self.cy = float(cy)

    # --- 像素 -> 相机系（给定光轴方向距离 z） ---
    def unproject(self, u, v, z):
        return ((u - self.cx) * z / self.fx,
                (v - self.cy) * z / self.fy,
                z)

    # --- 相机系 -> 像素 ---
    def project(self, p):
        if p[2] <= 1e-6:
            return None
        return (self.fx * p[0] / p[2] + self.cx,
                self.fy * p[1] / p[2] + self.cy)

    # --- 像素 -> 射线（单位向量，相机系）---
    def ray(self, u, v):
        x = (u - self.cx) / self.fx
        y = (v - self.cy) / self.fy
        n = math.sqrt(x * x + y * y + 1.0)
        return (x / n, y / n, 1.0 / n)

    def armor_center(self, x1, y1, x2, y2, armor_h, h_scale=1.0):
        """
        bbox（左上右下，像素）-> 装甲板中心在相机系下的 3D 点，单位米。

        原理：正面平行时，高度为 H 的物体在图上占 h 像素，则 z = fy·H/h。
        装甲板绕竖轴转动时只有宽度会透视缩短，高度不变 —— 所以用高度测距
        比用宽度稳得多，这是 RM 单目测距的常规做法。

        目标太远/框太矮（<4px）时返回 None，交给滤波去预测。
        """
        hpx = float(y2 - y1)
        if hpx < 4.0:
            return None
        z = self.fy * (armor_h * h_scale) / hpx
        u = (float(x1) + float(x2)) * 0.5
        v = (float(y1) + float(y2)) * 0.5
        return self.unproject(u, v, z)

    def angle_of_ray(self, u, v):
        """像素 -> 相对光轴的角度 (dyaw, dpitch)，只用来粗看/自检"""
        dx = (u - self.cx) / self.fx
        dy = (v - self.cy) / self.fy
        return math.atan(dx), math.atan(dy)


# ----------------------------------------------------------------------
# 自检
# ----------------------------------------------------------------------
def self_check(verbose=False):
    """返回 (ok, msg)。把正反变换走一遍，误差必须可以忽略。"""
    err = 0.0
    for yaw in (-2.5, -0.7, 0.0, 0.3, 1.9):
        for pitch in (-0.5, -0.1, 0.0, 0.15, 0.4):
            for p in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0),
                      (0.3, -0.4, 2.5)):
                w = body_to_world(p, yaw, pitch)
                b = world_to_body(w, yaw, pitch)
                err = max(err, abs(b[0] - p[0]), abs(b[1] - p[1]), abs(b[2] - p[2]))

                c = body_to_cam(p)
                p2 = cam_to_body(c)
                err = max(err, abs(p2[0] - p[0]), abs(p2[1] - p[1]), abs(p2[2] - p[2]))

    # 光轴方向必须是 (cosθcosψ, cosθsinψ, sinθ)
    for yaw, pitch in ((0.0, 0.0), (0.5, 0.0), (0.5, 0.3), (-1.2, -0.25)):
        axis = cam_to_world((0.0, 0.0, 1.0), yaw, pitch)
        ey, ep = dir_to_angles(axis)
        err = max(err, abs(wrap_pi(ey - yaw)), abs(ep - pitch))

    # 像素 <-> 3D 往返
    cam = Camera(460.0, 460.0, 320.0, 180.0)
    pt = cam.armor_center(300, 150, 340, 190, 0.125)
    if pt is None:
        return False, "armor_center 返回 None"
    # z 应该 = fy*0.125/40 = 1.4375
    err = max(err, abs(pt[2] - 460.0 * 0.125 / 40.0))

    ok = err < 1e-9
    msg = "geometry 自检 %s, 最大误差 %.3e" % ("通过" if ok else "失败", err)
    if verbose:
        print(msg)
    return ok, msg
