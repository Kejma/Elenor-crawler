"""High-res supersampled (4x) painterly renderer downscaled cleanly to 42x62 / 62x42."""

import math
import numpy as np
import pygame


def _smin(a, b, k=1.4):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1.0 - h) + a * h - k * h * (1.0 - h)


def _sd_capsule(X, Y, x0, y0, x1, y1, r0, r1):
    dx, dy = x1 - x0, y1 - y0
    l2 = dx * dx + dy * dy + 1e-6
    t = np.clip(((X - x0) * dx + (Y - y0) * dy) / l2, 0.0, 1.0)
    px = x0 + t * dx
    py = y0 + t * dy
    r = r0 + t * (r1 - r0)
    return np.hypot(X - px, Y - py) - r


def _sd_ellipse(X, Y, cx, cy, rx, ry, angle=0.0):
    dx = X - cx
    dy = Y - cy
    if angle != 0.0:
        ca, sa = math.cos(angle), math.sin(angle)
        dx, dy = dx * ca + dy * sa, -dx * sa + dy * ca
    k = np.hypot(dx / rx, dy / ry)
    return (k - 1.0) * min(rx, ry)


def _blur3(arr):
    p = np.pad(arr, 1, mode="edge")
    return (
        p[:-2, :-2] + 2.0 * p[:-2, 1:-1] + p[:-2, 2:]
        + 2.0 * p[1:-1, :-2] + 4.0 * p[1:-1, 1:-1] + 2.0 * p[1:-1, 2:]
        + p[2:, :-2] + 2.0 * p[2:, 1:-1] + p[2:, 2:]
    ) * (1.0 / 16.0)


def _mix(base, top, alpha):
    a = np.clip(alpha, 0.0, 1.0)[..., None]
    return base * (1.0 - a) + top * a


def _radial_glow(X, Y, cx, cy, rad, power=1.8):
    d = np.hypot(X - cx, Y - cy) / max(1e-4, rad)
    return np.clip(1.0 - d, 0.0, 1.0) ** power


def render_goblin_hut_card():
    """Painterly 42x62 portrait of the jungle-hut goblin woman (4x supersampled)."""
    W, H, SS = 42, 62, 4
    SW, SH = W * SS, H * SS

    xs = (np.arange(SW, dtype=np.float32) + 0.5) / SS
    ys = (np.arange(SH, dtype=np.float32) + 0.5) / SS
    X, Y = np.meshgrid(xs, ys)

    # =====================================================================
    # 1. ФОН: тёплая хижина с фонарём слева + ночной проём джунглей справа
    # =====================================================================
    t_y = Y / float(H)
    wall_top = np.array([46.0, 29.0, 23.0], dtype=np.float32)
    wall_bot = np.array([22.0, 14.0, 15.0], dtype=np.float32)
    bg = wall_top * (1.0 - t_y[..., None]) + wall_bot * t_y[..., None]

    # Вертикальные доски стены хижины (слегка размытые, мягкий контраст)
    plank_wave = 0.5 + 0.5 * np.sin((X - 1.5) * (math.pi / 3.8))
    plank_seam = np.exp(-((np.mod(X + 1.0, 7.6) - 3.8) ** 2) / 0.14)
    grain = np.sin(Y * 0.75 + np.sin(X * 0.6) * 2.0) * 0.5 + 0.5
    bg += (plank_wave[..., None] * 6.0 + grain[..., None] * 3.5 - plank_seam[..., None] * 11.0)

    # Правый проём окна/двери в ночные джунгли (x > 25.5, мягкий край косяка)
    win_mask = np.clip((X - 25.0) * 0.9, 0.0, 1.0) * np.clip((48.0 - Y) * 0.35, 0.0, 1.0)
    j_top = np.array([14.0, 38.0, 42.0], dtype=np.float32)
    j_bot = np.array([18.0, 58.0, 44.0], dtype=np.float32)
    jungle_bg = j_top * (1.0 - t_y[..., None]) + j_bot * t_y[..., None]
    # Силуэты листьев на фоне проёма
    leaf1 = _sd_ellipse(X, Y, 37.5, 11.0, 6.5, 3.2, -0.45)
    leaf2 = _sd_ellipse(X, Y, 38.5, 22.0, 5.5, 2.8, 0.35)
    leaf3 = _sd_ellipse(X, Y, 35.0, 36.0, 7.0, 3.5, -0.3)
    leaves = np.clip(-np.minimum(np.minimum(leaf1, leaf2), leaf3) * 0.8, 0.0, 1.0)
    jungle_bg = _mix(jungle_bg, np.array([10.0, 26.0, 22.0], dtype=np.float32), leaves * 0.75)
    bg = _mix(bg, jungle_bg, win_mask)

    # Тёплый боке-фонарь в хижине (слева) и светлячки в джунглях (справа)
    lantern_halo = _radial_glow(X, Y, 6.2, 16.5, 22.0, 1.9)
    lantern_core = _radial_glow(X, Y, 6.2, 16.5, 4.2, 2.2)
    bg += lantern_halo[..., None] * np.array([98.0, 56.0, 22.0], dtype=np.float32)
    bg += lantern_core[..., None] * np.array([150.0, 128.0, 72.0], dtype=np.float32)

    moon_mist = _radial_glow(X, Y, 34.5, 17.0, 18.0, 1.7) * win_mask
    bg += moon_mist[..., None] * np.array([28.0, 72.0, 68.0], dtype=np.float32)

    for fx, fy, fr in ((35.5, 14.5, 2.2), (38.0, 26.5, 1.8), (33.5, 34.0, 2.0), (37.0, 44.0, 1.6)):
        ff = _radial_glow(X, Y, fx, fy, fr, 2.0)
        bg += ff[..., None] * np.array([135.0, 195.0, 95.0], dtype=np.float32)

    # =====================================================================
    # 2. АНАТОМИЯ (пропорции ~1:7, плавный контрапост, 3D-высота Z)
    # =====================================================================
    # Голова (классический овал с лёгким заострением к подбородку, без чиби-увеличения)
    hx, hy = 21.3, 11.7
    dx_h = X - hx
    dy_h = Y - hy
    # Плавный наклон головы на ~4 градуса
    ca, sa = math.cos(0.07), math.sin(0.07)
    hx_l = dx_h * ca + dy_h * sa
    hy_l = -dx_h * sa + dy_h * ca
    # Узкий женственный подбородок ниже линии щёк
    jaw_taper = np.where(hy_l > 0.6, 1.0 - 0.11 * np.clip(hy_l - 0.6, 0.0, 4.5), 1.0)
    head_r = np.hypot(hx_l / (3.35 * jaw_taper), hy_l / 4.65)
    d_head = (head_r - 1.0) * 3.4

    # Длинные изящные уши гоблинши (слегка отведены назад и вверх)
    d_ear_l = _smin(
        _sd_capsule(X, Y, 18.2, 12.2, 13.5, 11.4, 1.25, 0.85),
        _sd_capsule(X, Y, 13.5, 11.4, 9.6, 10.4, 0.85, 0.28),
        k=0.7,
    )
    d_ear_r = _smin(
        _sd_capsule(X, Y, 24.4, 12.1, 29.0, 11.2, 1.25, 0.85),
        _sd_capsule(X, Y, 29.0, 11.2, 33.0, 10.1, 0.85, 0.28),
        k=0.7,
    )
    d_ears = np.minimum(d_ear_l, d_ear_r)

    # Шея и плавный переход трапеций в плечи
    d_neck = _sd_capsule(X, Y, 21.4, 15.8, 21.3, 20.6, 1.50, 1.78)
    d_sh_l = _sd_capsule(X, Y, 21.2, 20.4, 14.7, 21.5, 1.8, 1.95)
    d_sh_r = _sd_capsule(X, Y, 21.4, 20.6, 28.0, 22.1, 1.8, 1.95)

    # Плавный контур торса (грудная клетка -> осиная талия -> пышные бёдра)
    y_ctrl = np.array([19.5, 21.5, 24.5, 28.0, 31.5, 34.5, 37.5, 40.5, 43.8, 47.0, 50.0], dtype=np.float32)
    cx_ctrl = np.array([21.3, 21.3, 21.1, 20.9, 20.7, 20.8, 21.2, 21.8, 22.4, 22.3, 22.0], dtype=np.float32)
    hw_ctrl = np.array([4.8,  6.2,  5.9,  5.5,  4.8,  4.45, 5.3,  6.7,  7.75, 7.5,  6.8], dtype=np.float32)
    torso_cx = np.interp(Y, y_ctrl, cx_ctrl)
    torso_hw = np.interp(Y, y_ctrl, hw_ctrl)
    dx_t = np.abs(X - torso_cx) - torso_hw
    dy_t = np.maximum(19.8 - Y, Y - 49.0)
    d_torso = np.where((dx_t > 0) & (dy_t > 0), np.hypot(dx_t, dy_t), np.maximum(dx_t, dy_t))

    # Естественные бёдра вниз к нижнему краю (плавно сходятся с тазом)
    d_thigh_l = _sd_capsule(X, Y, 18.0, 45.8, 17.2, 62.5, 3.95, 3.35)
    d_thigh_r = _sd_capsule(X, Y, 25.6, 45.8, 25.0, 62.5, 4.15, 3.60)
    d_legs = _smin(d_thigh_l, d_thigh_r, k=0.9)

    # Объединяем торс, шею, плечи и ноги мягким органическим швом
    d_core = _smin(d_torso, d_legs, k=1.4)
    d_core = _smin(d_core, d_sh_l, k=1.3)
    d_core = _smin(d_core, d_sh_r, k=1.3)
    d_core = _smin(d_core, d_neck, k=1.2)
    d_core = _smin(d_core, d_head, k=0.45)

    # Руки: левая — на бедре (грациозный изгиб), правая — слегка отведена вдоль корпуса
    d_arm_l = _smin(
        _sd_capsule(X, Y, 14.6, 21.8, 11.4, 31.2, 1.85, 1.42),
        _sd_capsule(X, Y, 11.4, 31.2, 15.2, 39.6, 1.38, 1.05),
        k=0.7,
    )
    d_arm_r = _smin(
        _sd_capsule(X, Y, 28.0, 22.3, 30.8, 31.6, 1.82, 1.40),
        _sd_capsule(X, Y, 30.8, 31.6, 29.0, 41.0, 1.36, 1.05),
        k=0.7,
    )
    d_arms = np.minimum(d_arm_l, d_arm_r)

    d_body_all = _smin(_smin(d_core, d_arms, k=0.65), d_ears, k=0.35)
    body_mask = np.clip(-d_body_all * 2.8 + 0.5, 0.0, 1.0)

    # =====================================================================
    # 3. 3D-ВЫСОТА И СКУЛЬПТУРА (объём груди, скулы, нос, ключицы)
    # =====================================================================
    Z = np.sqrt(np.maximum(0.0, -d_body_all)) * 2.45

    # Уши чуть более плоские и отведены назад
    ear_only = (d_ears < 0.0) & (d_head > 0.2)
    Z = np.where(ear_only, np.sqrt(np.maximum(0.0, -d_ears)) * 1.15, Z)

    # Плавная лепка груди (каплевидный объём, без приклеенных шариков)
    def _breast_dome(cx, cy, rx, ry):
        u = (X - cx) / rx
        v = (Y - cy) / ry
        # Лёгкая естественная тяжесть книзу
        v_shaped = np.where(v < 0.0, v * 0.85, v * 1.10)
        r2 = u * u + v_shaped * v_shaped
        return np.sqrt(np.maximum(0.0, 1.0 - r2)) * 2.35

    br_l = _breast_dome(17.9, 27.6, 3.05, 3.25)
    br_r = _breast_dome(23.7, 27.9, 3.15, 3.35)
    Z = np.maximum(Z, np.where(d_torso < 0.6, Z * 0.58 + np.maximum(br_l, br_r), Z))
    # Мягкая ложбинка декольте и ключиц
    cleavage = np.exp(-((X - 20.85) ** 2) / 0.35 - ((Y - 27.6) ** 2) / 3.2)
    Z -= cleavage * 0.55
    clav = np.exp(-((Y - 21.0 - np.abs(X - 21.3) * 0.14) ** 2) / 0.25) * np.clip(1.0 - np.abs(X - 21.3) / 6.0, 0.0, 1.0)
    Z += clav * 0.32
    # Пупок и мягкий контур бедра
    navel = np.exp(-((X - 21.2) ** 2) / 0.18 - ((Y - 37.0) ** 2) / 0.35)
    Z -= navel * 0.38
    thigh_gap = np.exp(-((X - 21.4) ** 2) / 0.30) * np.clip((Y - 47.5) * 0.4, 0.0, 1.0)
    Z -= thigh_gap * 0.85

    # Лёгкая 3D-лепка лица (скулы, переносица, подбородок)
    nose_ridge = np.exp(-((X - 20.9) ** 2) / 0.22 - ((Y - 13.0) ** 2) / 1.4)
    nose_tip = np.exp(-((X - 20.85) ** 2) / 0.30 - ((Y - 13.85) ** 2) / 0.28)
    Z += (nose_ridge * 0.45 + nose_tip * 0.55) * (d_head < 0.0)

    Z_smooth = _blur3(Z)
    dZ_dy, dZ_dx = np.gradient(Z_smooth, 1.0 / SS)
    nx, ny, nz = -dZ_dx, -dZ_dy, np.ones_like(Z_smooth) * 1.15
    inv_n = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz + 1e-6)
    nx, ny, nz = nx * inv_n, ny * inv_n, nz * inv_n

    # =====================================================================
    # 4. ОСВЕЩЕНИЕ КОЖИ (тёплый ключ слева + изумрудный контровой справа + SSS)
    # =====================================================================
    # Направления света (единичные векторы)
    lk = np.array([-0.68, -0.34, 0.65], dtype=np.float32)
    lk /= np.linalg.norm(lk)
    lr = np.array([0.82, -0.22, 0.52], dtype=np.float32)
    lr /= np.linalg.norm(lr)

    ndotl_k = np.clip(nx * lk[0] + ny * lk[1] + nz * lk[2], 0.0, 1.0)
    ndotl_r = np.clip(nx * lr[0] + ny * lr[1] + nz * lr[2], 0.0, 1.0)
    fresnel = np.clip(1.0 - nz, 0.0, 1.0) ** 2.1

    # Постепенное затенение под грудью, подбородком и в складках рук (AO)
    ao = np.ones_like(Z)
    ao *= 1.0 - 0.34 * np.exp(-((X - 21.3) ** 2) / 4.2 - ((Y - 17.1) ** 2) / 1.2)  # тень под подбородком
    ao *= 1.0 - 0.28 * np.exp(-((X - 20.8) ** 2) / 22.0 - ((Y - 31.1) ** 2) / 1.3)  # тень под грудью
    ao *= 1.0 - 0.32 * cleavage
    ao *= 1.0 - 0.26 * thigh_gap

    # Благородная оливково-нефритовая кожа с тёплым подсвечиванием (SSS)
    skin_base = np.zeros((SH, SW, 3), dtype=np.float32)
    skin_base[:] = np.array([138.0, 180.0, 102.0], dtype=np.float32)

    # Мягкий тёплый румянец на щеках, плечах, груди и ушках
    blush_map = (
        0.55 * _radial_glow(X, Y, 18.8, 13.2, 2.0, 1.6)
        + 0.45 * _radial_glow(X, Y, 23.3, 13.3, 1.8, 1.6)
        + 0.35 * _radial_glow(X, Y, 20.9, 13.8, 1.1, 1.8)
        + 0.25 * _radial_glow(X, Y, 15.0, 21.8, 3.0, 1.8)
        + 0.30 * _radial_glow(X, Y, 11.8, 11.1, 3.0, 1.6) * (d_ear_l < 0.0)
        + 0.30 * _radial_glow(X, Y, 30.8, 10.9, 3.0, 1.6) * (d_ear_r < 0.0)
    )
    skin_base = _mix(skin_base, np.array([186.0, 136.0, 96.0], dtype=np.float32), np.clip(blush_map, 0.0, 0.55))

    # Мягкая тень в ушной раковине
    ear_hollow = (
        _radial_glow(X, Y, 15.0, 11.9, 2.6, 1.5) * (d_ear_l < 0.0)
        + _radial_glow(X, Y, 27.6, 11.8, 2.6, 1.5) * (d_ear_r < 0.0)
    )
    skin_base = _mix(skin_base, np.array([96.0, 122.0, 68.0], dtype=np.float32), np.clip(ear_hollow * 0.55, 0.0, 0.55))

    # Расчёт живописного освещения кожи (ambient + key + SSS warmth + specular + emerald rim)
    sss_band = np.exp(-((ndotl_k - 0.22) ** 2) / 0.045) * 0.26
    spec_h = np.clip(nx * (-0.36) + ny * (-0.22) + nz * 0.90, 0.0, 1.0) ** 14.0

    light_rgb = (
        np.array([0.34, 0.38, 0.36], dtype=np.float32) * ao[..., None]
        + ndotl_k[..., None] * ao[..., None] * np.array([0.88, 0.78, 0.62], dtype=np.float32)
        + sss_band[..., None] * np.array([0.34, 0.22, 0.08], dtype=np.float32)
        + (ndotl_r * fresnel)[..., None] * np.array([0.48, 0.94, 0.72], dtype=np.float32)
    )
    skin_lit = skin_base * light_rgb + (spec_h * ao)[..., None] * np.array([42.0, 38.0, 24.0], dtype=np.float32)

    # =====================================================================
    # 5. ДЕТАЛИ ЛИЦА (глаза, ресницы, брови, губки — мягко и соразмерно)
    # =====================================================================
    # Мягкие тени глазниц
    sock_l = _radial_glow(X, Y, 19.3, 12.1, 1.65, 1.6)
    sock_r = _radial_glow(X, Y, 22.8, 12.2, 1.65, 1.6)
    skin_lit = _mix(skin_lit, skin_lit * 0.74, np.clip((sock_l + sock_r) * 0.55, 0.0, 0.55))

    for ex, ey, tilt in ((19.35, 12.05, -0.14), (22.75, 12.15, 0.14)):
        # Миндалевидная форма глаза
        d_eye = _sd_ellipse(X, Y, ex, ey, 0.95, 0.52, tilt)
        eye_m = np.clip(-d_eye * 5.0 + 0.5, 0.0, 1.0)
        sclera = np.array([228.0, 230.0, 214.0], dtype=np.float32)
        skin_lit = _mix(skin_lit, sclera, eye_m)
        # Золотисто-янтарная радужка
        d_iris = np.hypot(X - (ex - 0.08), Y - ey) - 0.48
        iris_m = np.clip(-d_iris * 5.5 + 0.5, 0.0, 1.0) * eye_m
        iris_col = np.array([232.0, 168.0, 46.0], dtype=np.float32)
        skin_lit = _mix(skin_lit, iris_col, iris_m)
        # Зрачок и крошечный блик
        d_pup = np.hypot(X - (ex - 0.08), Y - ey) - 0.22
        pup_m = np.clip(-d_pup * 6.0 + 0.5, 0.0, 1.0) * eye_m
        skin_lit = _mix(skin_lit, np.array([28.0, 22.0, 24.0], dtype=np.float32), pup_m)
        glint = np.clip(1.0 - np.hypot(X - (ex - 0.25), Y - (ey - 0.14)) * 3.8, 0.0, 1.0) * eye_m
        skin_lit = _mix(skin_lit, np.array([255.0, 252.0, 236.0], dtype=np.float32), glint * 0.9)
        # Верхняя линия ресниц (тёмно-оливково-коричневая, не глухая чёрная)
        d_lash = _sd_capsule(X, Y, ex - 1.05, ey - 0.25, ex + 1.05, ey - 0.35 + tilt * 0.5, 0.22, 0.26)
        lash_m = np.clip(-d_lash * 5.0 + 0.5, 0.0, 1.0)
        skin_lit = _mix(skin_lit, np.array([26.0, 24.0, 28.0], dtype=np.float32), lash_m * 0.85)

    # Брови
    d_brow_l = _sd_capsule(X, Y, 18.2, 10.95, 20.3, 10.75, 0.20, 0.18)
    d_brow_r = _sd_capsule(X, Y, 21.8, 10.80, 23.9, 11.05, 0.18, 0.20)
    brows = np.clip(-np.minimum(d_brow_l, d_brow_r) * 4.5 + 0.5, 0.0, 1.0)
    skin_lit = _mix(skin_lit, np.array([34.0, 30.0, 32.0], dtype=np.float32), brows * 0.78)

    # Мягкая тень под кончиком носа
    nose_sh = _radial_glow(X, Y, 20.95, 14.2, 0.85, 1.8)
    skin_lit = _mix(skin_lit, skin_lit * 0.72, nose_sh * 0.65)

    # Деликатные губы с лёгкой лукавой усмешкой
    d_lip = _sd_ellipse(X, Y, 21.05, 15.05, 1.25, 0.44, -0.06)
    lip_m = np.clip(-d_lip * 4.5 + 0.5, 0.0, 1.0)
    lip_col = np.array([166.0, 86.0, 78.0], dtype=np.float32) * (0.65 + 0.55 * ndotl_k[..., None])
    lip_hi = _radial_glow(X, Y, 20.9, 15.18, 0.65, 2.0) * lip_m
    lip_col += lip_hi[..., None] * np.array([58.0, 42.0, 36.0], dtype=np.float32)
    skin_lit = _mix(skin_lit, lip_col, lip_m * 0.88)

    # =====================================================================
    # 6. ОДЕЖДА И УКРАШЕНИЯ (ткань со складками, повторяющая 3D-освещение)
    # =====================================================================
    # Драпированный терракотово-алый топ-повязка на груди
    top_top = 26.1 + 0.95 * np.exp(-((X - 20.85) ** 2) / 3.2) + 0.18 * (X - 21.0)
    top_bot = 31.35 + 0.4 * np.sin((X - 15.0) * 0.7)
    top_mask = (
        np.clip((Y - top_top) * 2.4, 0.0, 1.0)
        * np.clip((top_bot - Y) * 2.4, 0.0, 1.0)
        * np.clip((1.0 - np.abs(X - 20.8) / 6.2) * 3.0, 0.0, 1.0)
        * body_mask
    )
    # Складки на ткани
    fold_t = 0.5 + 0.5 * np.sin((Y - 27.0) * 2.6 + (X - 21.0) * 0.45)
    cloth_top = np.array([154.0, 56.0, 44.0], dtype=np.float32) * (0.86 + 0.26 * fold_t[..., None])
    cloth_top_lit = cloth_top * light_rgb
    skin_lit = _mix(skin_lit, cloth_top_lit, top_mask)

    # Тонкие завязки топа к шее + золотой кулон в центре
    d_strap_l = _sd_capsule(X, Y, 18.6, 26.5, 20.1, 19.6, 0.26, 0.22)
    d_strap_r = _sd_capsule(X, Y, 23.0, 26.7, 22.5, 19.8, 0.26, 0.22)
    straps = np.clip(-np.minimum(d_strap_l, d_strap_r) * 4.5 + 0.5, 0.0, 1.0) * body_mask
    skin_lit = _mix(skin_lit, np.array([116.0, 62.0, 42.0], dtype=np.float32) * light_rgb, straps)

    # Низкая набедренная драпировка из тёмно-изумрудной ткани с золотой каймой и высоким разрезом слева
    skirt_top = 41.0 + (X - 15.0) * 0.20 + 0.45 * np.sin((X - 15.0) * 0.4)
    # Разрез открывает левое бедро (слева от наклонной линии)
    slit_x = 18.2 + (Y - 43.0) * 0.28
    slit_open = np.clip((X - slit_x) * 1.6, 0.0, 1.0)
    hip_band = np.clip((skirt_top + 3.4 - Y) * 1.4, 0.0, 1.0)
    skirt_area = np.maximum(slit_open, hip_band)
    skirt_mask = np.clip((Y - skirt_top) * 2.4, 0.0, 1.0) * skirt_area * body_mask

    fold_s = 0.5 + 0.5 * np.sin((X - 22.0) * 1.5 - (Y - 42.0) * 0.55)
    cloth_bot = np.array([42.0, 74.0, 52.0], dtype=np.float32) * (0.82 + 0.34 * fold_s[..., None])
    # Золотой плетёный пояс по верхнему краю драпировки
    belt_m = np.exp(-((Y - (skirt_top + 0.65)) ** 2) / 0.32) * skirt_mask
    cloth_bot = _mix(cloth_bot, np.array([218.0, 172.0, 74.0], dtype=np.float32), belt_m * 0.9)
    skin_lit = _mix(skin_lit, cloth_bot * light_rgb, skirt_mask)

    # Золотые украшения (серьги в ушах, кулон, браслеты на запястье)
    gold_col = np.array([242.0, 198.0, 88.0], dtype=np.float32)
    jewel_m = np.zeros_like(Z)
    for jx, jy, jr in ((13.5, 12.2, 0.60), (29.2, 12.0, 0.55), (20.85, 29.0, 0.65), (14.4, 37.8, 0.95)):
        jewel_m = np.maximum(jewel_m, np.clip((jr - np.hypot(X - jx, Y - jy)) * 4.5 + 0.5, 0.0, 1.0))
    skin_lit = _mix(skin_lit, gold_col, jewel_m * 0.92)

    # =====================================================================
    # 7. ВОЛОСЫ (задний слой + передние пряди с живым блеском)
    # =====================================================================
    # Задняя волна волос (рисуется МЕЖДУ фоном и телом)
    d_hback = _smin(
        _sd_ellipse(X, Y, 21.8, 12.2, 5.2, 5.8, 0.08),
        _sd_ellipse(X, Y, 24.8, 22.5, 5.8, 11.5, -0.18),
        k=2.0,
    )
    d_hback = _smin(d_hback, _sd_ellipse(X, Y, 17.5, 18.5, 3.6, 7.2, 0.25), k=1.5)
    hback_mask = np.clip(-d_hback * 2.2 + 0.5, 0.0, 1.0)

    strand_noise = 0.5 + 0.5 * np.sin(X * 3.6 + np.sin(Y * 0.5) * 2.4)
    hair_dark = np.array([20.0, 18.0, 26.0], dtype=np.float32)
    hair_warm = np.array([76.0, 56.0, 44.0], dtype=np.float32)
    hair_cool = np.array([42.0, 74.0, 76.0], dtype=np.float32)

    # Раскрашиваем задние волосы с мягким блеском по сторонам
    hb_col = hair_dark + strand_noise[..., None] * np.array([14.0, 12.0, 16.0], dtype=np.float32)
    hb_col += _radial_glow(X, Y, 16.5, 14.0, 10.0, 1.8)[..., None] * hair_warm * 0.65
    hb_col += _radial_glow(X, Y, 29.0, 18.0, 10.0, 1.8)[..., None] * hair_cool * 0.70

    # Передняя шапка волос, косая чёлка и пряди, обрамляющие лицо (заправлены за уши!)
    d_hfront = _smin(
        _sd_ellipse(X, Y, 21.5, 8.6, 4.1, 2.5, 0.08),
        _sd_capsule(X, Y, 18.2, 9.2, 17.6, 12.4, 1.15, 0.55),
        k=0.8,
    )
    d_hfront = _smin(d_hfront, _sd_capsule(X, Y, 24.4, 9.0, 25.4, 13.8, 1.25, 0.75), k=0.8)
    # Изящная прядь поверх правого плеча
    d_hfront = _smin(d_hfront, _sd_capsule(X, Y, 25.4, 13.8, 26.6, 25.8, 1.35, 0.70), k=0.9)
    # Диагональная мягкая чёлка на лоб
    d_hfront = _smin(d_hfront, _sd_capsule(X, Y, 19.2, 8.6, 23.6, 10.1, 1.05, 0.65), k=0.7)
    hfront_mask = np.clip(-d_hfront * 2.8 + 0.5, 0.0, 1.0)

    # Анизотропный блик на макушке и волне волос
    crown_hi = np.exp(-((Y - 8.6 - (X - 21.3) * 0.12) ** 2) / 0.85) * hfront_mask
    hf_col = hair_dark + strand_noise[..., None] * np.array([18.0, 15.0, 20.0], dtype=np.float32)
    hf_col += crown_hi[..., None] * np.array([82.0, 72.0, 62.0], dtype=np.float32)
    hf_col += (np.clip((22.0 - X) / 6.0, 0.0, 1.0) * hfront_mask)[..., None] * hair_warm * 0.55
    hf_col += (np.clip((X - 23.0) / 5.0, 0.0, 1.0) * hfront_mask)[..., None] * hair_cool * 0.65

    # =====================================================================
    # 8. СБОРКА СЛОЁВ + ПЕРЕДНИЙ ПЛАН + СЖАТИЕ 4x -> 42x62
    # =====================================================================
    # Мягкая падающая тень силуэта на стену хижины
    sh_mask = np.roll(np.maximum(body_mask, hback_mask), shift=(6, 8), axis=(0, 1))
    canvas = _mix(bg, bg * 0.48, _blur3(_blur3(sh_mask)) * 0.65)
    # Задние волосы -> тело с одеждой и лицом -> передние пряди волос
    canvas = _mix(canvas, hb_col, hback_mask)
    canvas = _mix(canvas, skin_lit, body_mask)
    canvas = _mix(canvas, hf_col, hfront_mask)

    # Лёгкая тёплая воздушная дымка от фонаря слева и мягкая виньетка по краям
    canvas += _radial_glow(X, Y, 5.0, 16.0, 24.0, 2.2)[..., None] * np.array([28.0, 16.0, 6.0], dtype=np.float32)
    vig = np.hypot((X - W * 0.5) / (W * 0.56), (Y - H * 0.5) / (H * 0.56))
    canvas *= np.clip(1.12 - (vig ** 2.6) * 0.34, 0.62, 1.05)[..., None]

    # Точное усреднение 4x4 блоков -> эффект честно сжатой живописной картины 42x62!
    img = canvas.reshape(H, SS, W, SS, 3).mean(axis=(1, 3))

    # Лёгкая живописная S-кривая контраста (чуть сочнее цвета после сжатия)
    n01 = np.clip(img / 255.0, 0.0, 1.0)
    n01 = np.clip(n01 * 0.86 + (n01 * n01 * (3.0 - 2.0 * n01)) * 0.14, 0.0, 1.0)
    rgb_u8 = np.clip(n01 * 255.0, 0, 255).astype(np.uint8)

    # Переводим (H, W, 3) -> (W, H, 3) для Pygame
    surf = pygame.surfarray.make_surface(np.transpose(rgb_u8, (1, 0, 2))).convert_alpha()

    # Тонкая 1px рама тёплого дерева/бронзы по самому краю, чтобы оставить 40x60 чистого арта
    pygame.draw.rect(surf, (38, 24, 18), (0, 0, W, H), 1)
    for cx, cy in ((0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1)):
        surf.set_at((cx, cy), (186, 142, 66))
    return surf


HIGH_QUALITY_PAINTERS = {
    "paint_goblin_hut": render_goblin_hut_card,
}