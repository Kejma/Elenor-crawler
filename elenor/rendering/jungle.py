"""Procedural diffuse + normal asset generator for the Jungle & Marble Temple campaign."""

import math
import numpy as np
from elenor.rendering.assets import make_pair, enforce_crisp_rim_normals

# Нормали строго из 10-цветного компаса движка
N_FLAT = (128, 128, 255, 255)
N_UP = (128, 218, 200, 255)
N_DOWN = (128, 38, 200, 255)
N_LEFT = (45, 128, 200, 255)
N_RIGHT = (210, 128, 200, 255)
N_UL = (65, 195, 195, 255)
N_UR = (190, 195, 195, 255)
N_DL = (65, 60, 195, 255)
N_DR = (190, 60, 195, 255)
N_DEEP = (128, 128, 155, 255)


def get_moss_autotile_key(moss_set, x, y):
    """
    Возвращает ключ тайла мха (13 базовых форм со всеми внешними и внутренними углами
    + 3 формы для узких полосок в 1 тайл).
    """
    has_n = (x, y - 1) in moss_set
    has_s = (x, y + 1) in moss_set
    has_w = (x - 1, y) in moss_set
    has_e = (x + 1, y) in moss_set

    if not has_n and not has_s and not has_w and not has_e:
        return "moss_single"
    if has_w and has_e and not has_n and not has_s:
        return "moss_h"
    if has_n and has_s and not has_w and not has_e:
        return "moss_v"

    # 4 внешних угла
    if not has_n and not has_w:
        return "moss_nw"
    if not has_n and not has_e:
        return "moss_ne"
    if not has_s and not has_w:
        return "moss_sw"
    if not has_s and not has_e:
        return "moss_se"

    # 4 прямые стороны
    if not has_n:
        return "moss_n"
    if not has_s:
        return "moss_s"
    if not has_w:
        return "moss_w"
    if not has_e:
        return "moss_e"

    # Все 4 соседа по сторонам света есть — проверяем 4 внутренних диагональных угла!
    if (x - 1, y - 1) not in moss_set:
        return "moss_in_nw"
    if (x + 1, y - 1) not in moss_set:
        return "moss_in_ne"
    if (x - 1, y + 1) not in moss_set:
        return "moss_in_sw"
    if (x + 1, y + 1) not in moss_set:
        return "moss_in_se"

    return "moss_c"


def generate_moss_autotile_pair(variant):
    """
    Генерирует полупрозрачный 16x16 тайл пышного тропического мха с рваным органичным краем
    и объёмной фаской нормалей, чтобы его можно было класть поверх любого пола (мрамор, доски, грязь).
    """
    diff, norm = make_pair(16, 16, opaque=False)

    mask = [[False for _ in range(16)] for _ in range(16)]
    for y in range(16):
        for x in range(16):
            # Лёгкая волнистость края, которая совпадает на границах тайлов
            wave_x = math.sin(y * 0.78) * 1.15 + ((y * 13) % 3 - 1) * 0.45
            wave_y = math.cos(x * 0.78) * 1.15 + ((x * 17) % 3 - 1) * 0.45
            inside = True

            if variant == "moss_c":
                inside = True
            elif variant == "moss_n":
                inside = (y >= 3.2 + wave_y * 0.6)
            elif variant == "moss_s":
                inside = (y <= 12.2 + wave_y * 0.6)
            elif variant == "moss_w":
                inside = (x >= 3.2 + wave_x * 0.6)
            elif variant == "moss_e":
                inside = (x <= 12.2 + wave_x * 0.6)
            elif variant == "moss_nw":
                inside = (x >= 3.0 + wave_x * 0.5) and (y >= 3.0 + wave_y * 0.5) and (math.hypot(max(0.0, 6.0 - x), max(0.0, 6.0 - y)) <= 3.4)
            elif variant == "moss_ne":
                inside = (x <= 12.5 + wave_x * 0.5) and (y >= 3.0 + wave_y * 0.5) and (math.hypot(max(0.0, x - 9.0), max(0.0, 6.0 - y)) <= 3.4)
            elif variant == "moss_sw":
                inside = (x >= 3.0 + wave_x * 0.5) and (y <= 12.5 + wave_y * 0.5) and (math.hypot(max(0.0, 6.0 - x), max(0.0, y - 9.0)) <= 3.4)
            elif variant == "moss_se":
                inside = (x <= 12.5 + wave_x * 0.5) and (y <= 12.5 + wave_y * 0.5) and (math.hypot(max(0.0, x - 9.0), max(0.0, y - 9.0)) <= 3.4)
            elif variant == "moss_in_nw":
                inside = math.hypot(x - 0.0, y - 0.0) >= 4.4 + wave_x * 0.4
            elif variant == "moss_in_ne":
                inside = math.hypot(x - 15.0, y - 0.0) >= 4.4 + wave_x * 0.4
            elif variant == "moss_in_sw":
                inside = math.hypot(x - 0.0, y - 15.0) >= 4.4 + wave_x * 0.4
            elif variant == "moss_in_se":
                inside = math.hypot(x - 15.0, y - 15.0) >= 4.4 + wave_x * 0.4
            elif variant == "moss_h":
                inside = (3.0 + wave_y * 0.5 <= y <= 12.5 + wave_y * 0.5)
            elif variant == "moss_v":
                inside = (3.0 + wave_x * 0.5 <= x <= 12.5 + wave_x * 0.5)
            elif variant == "moss_single":
                inside = math.hypot(x - 7.5, y - 7.5) <= 5.4 + (wave_x + wave_y) * 0.35

            mask[y][x] = inside

    for y in range(16):
        for x in range(16):
            if not mask[y][x]:
                continue
            # Проверяем соседей для рельефного скоса нормалей на границе мха
            up_empty = (y > 0 and not mask[y - 1][x])
            dn_empty = (y < 15 and not mask[y + 1][x])
            lf_empty = (x > 0 and not mask[y][x - 1])
            rt_empty = (x < 15 and not mask[y][x + 1])
            is_rim = up_empty or dn_empty or lf_empty or rt_empty

            h_val = ((x * 67 + y * 131 + (x ^ y) * 29) % 19)
            if is_rim:
                col = (26, 56, 30, 235)
                if up_empty and lf_empty:
                    n_col = N_UL
                elif up_empty and rt_empty:
                    n_col = N_UR
                elif dn_empty and lf_empty:
                    n_col = N_DL
                elif dn_empty and rt_empty:
                    n_col = N_DR
                elif up_empty:
                    n_col = N_UP
                elif dn_empty:
                    n_col = N_DOWN
                elif lf_empty:
                    n_col = N_LEFT
                else:
                    n_col = N_RIGHT
            else:
                if h_val in (0, 1):
                    col = (64, 118, 52, 250)  # Светлые подушечки мха
                    n_col = N_UP
                elif h_val in (2, 3, 4):
                    col = (32, 68, 36, 245)  # Ложбинки между кочками
                    n_col = N_DEEP
                elif h_val == 5:
                    col = (84, 142, 58, 255)  # Молодой побег
                    n_col = N_FLAT
                else:
                    sh = (h_val % 3) * 4
                    col = (42 + sh, 88 + sh, 42 + sh, 248)
                    n_col = N_FLAT

            diff.set_at((x, y), col)
            norm.set_at((x, y), n_col)

    return diff, norm


def register_jungle_assets(assets):
    _register_jungle_base(assets)
    _register_jungle_variants(assets)
    _register_bone_jungle_and_caves(assets)


def _register_jungle_base(assets):
    # =========================================================================
    # 1. ПОЛЫ И ПОВЕРХНОСТИ (16x16, opaque=True)
    # =========================================================================

    # 1.1 Тропическая густая трава (floor_jungle_grass) — сочная изумрудная зелень
    jg_d, jg_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            h = ((x * 83 + y * 149 + (x * y) * 23) ^ ((x + 5) * 31 + (y + 3) * 17)) % 31
            if h in (0, 1, 2):
                col, nc = (52, 108, 48, 255), N_FLAT
            elif h in (3, 4):
                col, nc = (68, 128, 54, 255), N_FLAT
            elif h in (5, 6, 7):
                col, nc = (24, 54, 28, 255), N_DEEP
            else:
                sh = (h % 4) * 3
                col, nc = (34 + sh, 76 + sh, 36 + sh, 255), N_FLAT
            jg_d.set_at((x, y), col)
            jg_n.set_at((x, y), nc)
    assets["floor_jungle_grass"] = (jg_d, jg_n)

    # 1.2 Влажная тропическая грязь (floor_jungle_mud)
    jm_d, jm_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            h = ((x * 71 + y * 113 + x * y * 19) ^ (x * 29 + y * 41)) % 29
            if h in (0, 1, 2):
                col, nc = (72, 48, 34, 255), N_FLAT
            elif h in (3, 4, 5):
                col, nc = (38, 25, 18, 255), N_DEEP
            else:
                sh = (h % 5) - 2
                col, nc = (54 + sh, 36 + sh, 25 + sh, 255), N_FLAT
            jm_d.set_at((x, y), col)
            jm_n.set_at((x, y), nc)
    assets["floor_jungle_mud"] = (jm_d, jm_n)

    # 1.3 Лесная подстилка с корнями и опадом (floor_jungle_soil)
    js_d, js_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            h = ((x * 59 + y * 101 + (x ^ y) * 37) % 27)
            is_root = ((x + y * 2) % 13 == 0) or ((x * 2 - y) % 15 == 0)
            if is_root:
                col, nc = (86, 58, 36, 255), N_FLAT
            elif h in (0, 1):
                col, nc = (46, 78, 38, 255), N_FLAT  # Упавший листок
            elif h in (2, 3):
                col, nc = (98, 68, 34, 255), N_FLAT  # Сухой жёлтый лист
            elif h in (4, 5):
                col, nc = (36, 26, 20, 255), N_DEEP
            else:
                sh = (h % 4) * 2
                col, nc = (48 + sh, 35 + sh, 26 + sh, 255), N_FLAT
            js_d.set_at((x, y), col)
            js_n.set_at((x, y), nc)
    assets["floor_jungle_soil"] = (js_d, js_n)

    # 1.4 Деревянный бамбуковый настил аборигенов (floor_tribal_wood)
    tw_d, tw_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        pole_y = y % 4
        joint_x = ((y // 4) * 6 + 4) % 16
        for x in range(16):
            if pole_y == 0:
                tw_d.set_at((x, y), (42, 28, 18, 255))
                tw_n.set_at((x, y), N_DEEP)
            elif x in (joint_x, (joint_x + 1) % 16):
                # Перевязь из пальмового волокна на стыке бамбука
                tw_d.set_at((x, y), (148, 118, 68, 255))
                tw_n.set_at((x, y), N_FLAT)
            else:
                grain = ((x * 17 + y * 31) % 5) - 2
                if pole_y == 1:
                    col = (108 + grain, 82 + grain, 46 + grain, 255)
                elif pole_y == 2:
                    col = (96 + grain, 72 + grain, 40 + grain, 255)
                else:
                    col = (78 + grain, 58 + grain, 32 + grain, 255)
                tw_d.set_at((x, y), col)
                tw_n.set_at((x, y), N_FLAT)
    assets["floor_tribal_wood"] = (tw_d, tw_n)

    # 1.5 Белый полированный мрамор храма с прожилками (floor_marble_white)
    mw_d, mw_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            is_seam = (x == 0 or y == 0 or (y == 8 and x >= 8) or (x == 8 and y < 8))
            if is_seam:
                mw_d.set_at((x, y), (145, 138, 132, 255))
                mw_n.set_at((x, y), N_DEEP)
                continue
            vein = abs((x + y * 2 + ((x * y) % 5)) % 14 - 7)
            gold_vein = ((x * 3 - y * 2) % 19 == 0)
            if gold_vein:
                col = (212, 182, 115, 255)
            elif vein == 0:
                col = (182, 178, 172, 255)
            elif (x == 1 or y == 1):
                col = (238, 234, 226, 255)
            else:
                sh = ((x * 11 + y * 23) % 5) - 2
                col = (220 + sh, 215 + sh, 206 + sh, 255)
            mw_d.set_at((x, y), col)
            mw_n.set_at((x, y), N_FLAT)
    assets["floor_marble_white"] = (mw_d, mw_n)

    # 1.6 Тёмный изумрудно-обсидиановый мрамор храма (floor_marble_dark)
    md_d, md_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            if x in (0, 15) or y in (0, 15):
                md_d.set_at((x, y), (24, 32, 30, 255))
                md_n.set_at((x, y), N_DEEP)
            elif x in (1, 14) or y in (1, 14):
                md_d.set_at((x, y), (168, 138, 72, 255))  # Золотая инкрустация по периметру плиты
                md_n.set_at((x, y), N_FLAT)
            else:
                vein = ((x * 2 + y * 3) % 11 == 0)
                col = (72, 112, 96, 255) if vein else (40, 58, 54, 255)
                md_d.set_at((x, y), col)
                md_n.set_at((x, y), N_FLAT)
    assets["floor_marble_dark"] = (md_d, md_n)

    # 1.7 Мраморная солнечная мозаика (floor_marble_mosaic)
    mm_d, mm_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            dist = abs(x - 7.5) + abs(y - 7.5)
            if x == 0 or y == 0:
                col, nc = (145, 138, 132, 255), N_DEEP
            elif dist <= 2.2:
                col, nc = (52, 168, 122, 255), N_FLAT  # Нефритовое ядро в центре
            elif 3.2 <= dist <= 5.2:
                col, nc = (218, 175, 72, 255), N_FLAT  # Золотая звезда солнца
            elif 5.2 < dist <= 6.5:
                col, nc = (145, 112, 52, 255), N_DEEP
            else:
                col, nc = (218, 212, 202, 255), N_FLAT
            mm_d.set_at((x, y), col)
            mm_n.set_at((x, y), nc)
    assets["floor_marble_mosaic"] = (mm_d, mm_n)

    # =========================================================================
    # 2. СТЕНЫ И ВЫСОКИЕ ДЕРЕВЬЯ ДЖУНГЛЕЙ (16x16 и 24x38)
    # =========================================================================

    # 2.1 Грязево-каменистая стена джунглей (wall_mud_rock)
    wmr_d, wmr_n = make_pair(16, 16, opaque=True)
    wmr_d.fill((48, 32, 22, 255))
    wmr_n.fill(N_DEEP)
    boulders = [(1, 1, 6, 5), (8, 1, 7, 6), (1, 7, 7, 5), (9, 8, 6, 6), (2, 13, 6, 3)]
    for bx, by, bw, bh in boulders:
        for y in range(by, by + bh):
            for x in range(bx, bx + bw):
                is_rock = (bx + by) % 2 == 0
                base = (88, 82, 76) if is_rock else (96, 64, 42)
                if y == by:
                    col = (min(255, base[0] + 22), min(255, base[1] + 20), min(255, base[2] + 18), 255)
                    nc = N_UP
                elif y == by + bh - 1:
                    col = (max(15, base[0] - 24), max(15, base[1] - 20), max(15, base[2] - 16), 255)
                    nc = N_DOWN
                elif x == bx:
                    col, nc = (*base, 255), N_LEFT
                elif x == bx + bw - 1:
                    col, nc = (*base, 255), N_RIGHT
                else:
                    col, nc = (*base, 255), N_FLAT
                wmr_d.set_at((x, y), col)
                wmr_n.set_at((x, y), nc)
    # Свисающие сверху корни и мох
    for x in (3, 4, 11, 12):
        for y in range(0, 4 if x < 8 else 5):
            wmr_d.set_at((x, y), (48, 96, 44, 255))
            wmr_n.set_at((x, y), N_UP)
    assets["wall_mud_rock"] = (wmr_d, wmr_n)

    # 2.2 Деревянная стена построек аборигенов: бамбук, колья, верёвки и орнамент (wall_tribal_wood)
    wtw_d, wtw_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            post_x = x % 4
            if post_x == 0:
                wtw_d.set_at((x, y), (42, 26, 16, 255))
                wtw_n.set_at((x, y), N_DEEP)
            elif y in (4, 11):
                # Горизонтальная канатная стяжка
                wtw_d.set_at((x, y), (185, 148, 82, 255) if (x + y) % 2 == 0 else (142, 108, 56, 255))
                wtw_n.set_at((x, y), N_UP if y == 4 else N_DOWN)
            elif y in (7, 8):
                # Племенной красно-белый геометрический узор по центру кольев
                pat = (x // 4 + y) % 2 == 0
                wtw_d.set_at((x, y), (195, 58, 42, 255) if pat else (225, 212, 180, 255))
                wtw_n.set_at((x, y), N_FLAT)
            else:
                col = (128, 88, 46, 255) if post_x == 1 else ((108, 72, 38, 255) if post_x == 2 else (82, 54, 28, 255))
                nc = N_LEFT if post_x == 1 else (N_RIGHT if post_x == 3 else N_FLAT)
                if y == 0:
                    col, nc = (148, 106, 58, 255), N_UP
                wtw_d.set_at((x, y), col)
                wtw_n.set_at((x, y), nc)
    assets["wall_tribal_wood"] = (wtw_d, wtw_n)

    # 2.3 Стена белокаменного мраморного храма с золотым фризом (wall_marble_temple)
    wmt_d, wmt_n = make_pair(16, 16, opaque=True)
    wmt_d.fill((128, 122, 118, 255))
    wmt_n.fill(N_DEEP)
    blocks = [(0, 0, 7, 5), (8, 0, 8, 5), (0, 9, 11, 6), (12, 9, 4, 6)]
    for bx, by, bw, bh in blocks:
        for y in range(by, by + bh):
            for x in range(bx, bx + bw):
                vein = ((x * 3 + y * 5) % 13 == 0)
                base = (192, 186, 178) if vein else (226, 220, 210)
                if y == by:
                    col, nc = (246, 242, 234, 255), N_UP
                elif y == by + bh - 1:
                    col, nc = (172, 165, 156, 255), N_DOWN
                elif x == bx:
                    col, nc = (*base, 255), N_LEFT
                elif x == bx + bw - 1:
                    col, nc = (*base, 255), N_RIGHT
                else:
                    col, nc = (*base, 255), N_FLAT
                wmt_d.set_at((x, y), col)
                wmt_n.set_at((x, y), nc)
    # Золотой храмовый меандр-фриз (y=6..7)
    for x in range(16):
        is_gold = (x % 4 in (0, 1, 2))
        wmt_d.set_at((x, 6), (235, 192, 78, 255) if is_gold else (58, 148, 112, 255))
        wmt_n.set_at((x, 6), N_UP)
        wmt_d.set_at((x, 7), (178, 136, 48, 255) if is_gold else (38, 104, 78, 255))
        wmt_n.set_at((x, 7), N_DOWN)
    assets["wall_marble_temple"] = (wmt_d, wmt_n)

    # 2.4 Разрушенная мраморная стена, оплетённая лианами (wall_marble_ruined)
    wmr2_d = wmt_d.copy()
    wmr2_n = wmt_n.copy()
    vine_coords = [
        (2, 0), (2, 1), (3, 2), (3, 3), (4, 4), (4, 5), (3, 6), (3, 7), (2, 8), (2, 9),
        (11, 0), (12, 1), (12, 2), (11, 3), (11, 4), (10, 5), (10, 6), (11, 7), (12, 8), (12, 9), (13, 10), (13, 11)
    ]
    for vx, vy in vine_coords:
        wmr2_d.set_at((vx, vy), (46, 108, 48, 255))
        wmr2_n.set_at((vx, vy), N_UP)
        if vx + 1 < 16:
            wmr2_d.set_at((vx + 1, vy), (32, 78, 36, 255))
            wmr2_n.set_at((vx + 1, vy), N_RIGHT)
    for cx, cy in ((6, 11), (7, 12), (7, 13), (8, 14)):
        wmr2_d.set_at((cx, cy), (75, 70, 68, 255))
        wmr2_n.set_at((cx, cy), N_DEEP)
    assets["wall_marble_ruined"] = (wmr2_d, wmr2_n)

    # 2.5 Высокое тропическое дерево с лианами (tall_jungle_tree 24x38 + иконка tree_jungle 16x16)
    jt_d, jt_n = make_pair(24, 38)
    for y in range(2, 38):
        for x in range(1, 23):
            # Широкие корни-контрфорсы у основания и мощный ствол (y=22..37)
            root_spread = max(0, (y - 29) // 2)
            if y >= 22 and (9 - root_spread <= x <= 14 + root_spread):
                col = (104, 68, 42) if x < 12 else (74, 46, 28)
                nc = N_LEFT if x < 11 else (N_RIGHT if x > 12 else N_FLAT)
                jt_d.set_at((x, y), col)
                jt_n.set_at((x, y), nc)
            # Пышная многоярусная шапка кроны (y=2..25)
            if y <= 25:
                d1 = math.hypot((x - 11.5) * 0.85, (y - 12.0) * 1.05)
                d2 = math.hypot((x - 6.5) * 1.0, (y - 16.0) * 1.1)
                d3 = math.hypot((x - 16.5) * 1.0, (y - 16.0) * 1.1)
                if min(d1, d2, d3) <= 8.5:
                    sh = (x * 5 + y * 7) % 5
                    if y < 9 or sh == 0:
                        col, nc = (68, 142, 54), N_UP
                    elif y > 20 or sh == 4:
                        col, nc = (24, 58, 28), N_DOWN
                    else:
                        col = (44, 106, 44) if sh in (1, 2) else (34, 82, 36)
                        nc = N_LEFT if x < 9 else (N_RIGHT if x > 14 else N_FLAT)
                    jt_d.set_at((x, y), col)
                    jt_n.set_at((x, y), nc)
    # Свисающие с кроны лианы и яркие орхидеи
    for lx, ly_end in ((5, 31), (8, 28), (15, 30), (18, 32)):
        for ly in range(18, ly_end):
            jt_d.set_at((lx, ly), (56, 124, 52) if ly % 2 == 0 else (38, 88, 38))
            jt_n.set_at((lx, ly), N_LEFT if lx < 12 else N_RIGHT)
    for fx, fy in ((7, 11), (15, 9), (11, 15), (17, 17)):
        jt_d.set_at((fx, fy), (245, 78, 95))
        jt_d.set_at((fx + 1, fy), (255, 215, 75))
    assets["tall_jungle_tree"] = (jt_d, jt_n)

    jti_d, jti_n = make_pair(16, 16)
    for y in range(1, 15):
        for x in range(2, 14):
            if y >= 10 and 6 <= x <= 9:
                jti_d.set_at((x, y), (98, 64, 38))
                jti_n.set_at((x, y), N_LEFT if x <= 7 else N_RIGHT)
            elif math.hypot(x - 7.5, y - 6.5) <= 5.5:
                jti_d.set_at((x, y), (58, 132, 50) if y < 6 else (36, 86, 38))
                jti_n.set_at((x, y), N_UP if y < 6 else N_FLAT)
    assets["tree_jungle"] = (jti_d, jti_n)

    # 2.6 Высокая кокосовая пальма (tall_palm_tree 24x38 + иконка tree_palm 16x16)
    pt_d, pt_n = make_pair(24, 38)
    # Изогнутый кольчатый ствол пальмы (y=13..36)
    for y in range(13, 37):
        curve_x = 11.5 + math.sin((36 - y) * 0.13) * 2.2
        half_t = 2.1 if y > 32 else (1.6 if y > 22 else 1.3)
        for x in range(2, 22):
            if abs(x - curve_x) <= half_t:
                is_ring = (y % 3 == 0)
                col = (92, 60, 36) if is_ring else ((136, 94, 54) if x <= curve_x else (106, 70, 40))
                nc = N_DOWN if is_ring else (N_LEFT if x < curve_x else N_RIGHT)
                pt_d.set_at((x, y), col)
                pt_n.set_at((x, y), nc)
    # Кокосы под листьями (y=12..15)
    for cx_c, cy_c in ((11, 14), (14, 14), (12, 15)):
        for dy_c in (0, 1):
            for dx_c in (0, 1):
                pt_d.set_at((cx_c + dx_c, cy_c + dy_c), (78, 48, 26))
                pt_n.set_at((cx_c + dx_c, cy_c + dy_c), N_UP)
    # Раскидистые дуги пальмовых листьев
    top_x, top_y = 13.0, 12.0
    fronds = [
        (-1.0, -0.35, 11), (-0.85, 0.25, 11), (-0.45, -0.75, 9),
        (1.0, -0.35, 10), (0.85, 0.25, 10), (0.45, -0.75, 9), (0.0, -0.95, 8)
    ]
    for dx_f, dy_f, f_len in fronds:
        for step in range(1, f_len + 1):
            t = step / float(f_len)
            fx = int(round(top_x + dx_f * step))
            fy = int(round(top_y + dy_f * step + (t * t) * 4.2))
            for w_off in range(-2, 3):
                px_f, py_f = fx, fy + w_off
                if 0 <= px_f < 24 and 0 <= py_f < 38:
                    col = (82, 168, 56) if w_off <= 0 else (46, 112, 40)
                    nc = N_UP if w_off <= 0 else N_DOWN
                    pt_d.set_at((px_f, py_f), col)
                    pt_n.set_at((px_f, py_f), nc)
    assets["tall_palm_tree"] = (pt_d, pt_n)

    pti_d, pti_n = make_pair(16, 16)
    for y in range(6, 15):
        for x in (7, 8):
            pti_d.set_at((x, y), (128, 86, 48) if y % 2 else (94, 62, 34))
            pti_n.set_at((x, y), N_LEFT if x == 7 else N_RIGHT)
    for dx_i, dy_i in ((-4, -2), (-5, 1), (4, -2), (5, 1), (0, -4)):
        for s_i in range(1, 6):
            px_i = int(7.5 + (dx_i / 5.0) * s_i)
            py_i = int(6.0 + (dy_i / 5.0) * s_i + (s_i / 5.0) ** 2 * 1.5)
            if 0 <= px_i < 16 and 0 <= py_i < 16:
                pti_d.set_at((px_i, py_i), (76, 158, 52))
                pti_n.set_at((px_i, py_i), N_UP)
                if py_i + 1 < 16:
                    pti_d.set_at((px_i, py_i + 1), (46, 108, 38))
                    pti_n.set_at((px_i, py_i + 1), N_DOWN)
    assets["tree_palm"] = (pti_d, pti_n)

    # =========================================================================
    # 3. АВТОТАЙЛИНГ МХА (13 базовых форм + 3 узкие полоски = 16 тайлов)
    # =========================================================================
    moss_variants = (
        "moss_c", "moss_n", "moss_s", "moss_w", "moss_e",
        "moss_nw", "moss_ne", "moss_sw", "moss_se",
        "moss_in_nw", "moss_in_ne", "moss_in_sw", "moss_in_se",
        "moss_h", "moss_v", "moss_single",
    )
    for m_var in moss_variants:
        assets[m_var] = generate_moss_autotile_pair(m_var)

    # =========================================================================
    # 4. НАКЛАДЫВАЕМЫЕ ОВЕРЛЕИ ДЖУНГЛЕЙ И ХРАМА (16x16, opaque=False)
    # =========================================================================

    # 4.1 Розетка папоротника (ov_fern)
    of_d, of_n = make_pair(16, 16, opaque=False)
    for ang_deg in (25, 75, 135, 200, 255, 315):
        rad = math.radians(ang_deg)
        dx, dy = math.cos(rad), math.sin(rad)
        for r_step in range(1, 7):
            fx = int(round(7.5 + dx * r_step))
            fy = int(round(7.5 + dy * r_step))
            if 1 <= fx < 15 and 1 <= fy < 15:
                of_d.set_at((fx, fy), (68, 148, 56, 235))
                of_n.set_at((fx, fy), N_FLAT)
                if r_step in (3, 5):
                    px_s, py_s = int(round(fx - dy)), int(round(fy + dx))
                    if 1 <= px_s < 15 and 1 <= py_s < 15:
                        of_d.set_at((px_s, py_s), (46, 108, 42, 220))
                        of_n.set_at((px_s, py_s), N_FLAT)
    of_d.set_at((7, 7), (95, 178, 68, 245))
    of_n.set_at((7, 7), N_FLAT)
    assets["ov_fern"] = (of_d, of_n)

    # 4.2 Алые тропические цветы гибискуса (ov_flowers_red)
    ofr_d, ofr_n = make_pair(16, 16, opaque=False)
    for bx, by in ((4, 5), (11, 6), (6, 12)):
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ofr_d.set_at((bx + dx, by + dy), (225, 52, 68, 240))
            ofr_n.set_at((bx + dx, by + dy), N_FLAT)
        for dx, dy in ((-1, -1), (1, 1)):
            ofr_d.set_at((bx + dx, by + dy), (44, 108, 46, 215))
            ofr_n.set_at((bx + dx, by + dy), N_FLAT)
        ofr_d.set_at((bx, by), (255, 220, 75, 250))
        ofr_n.set_at((bx, by), N_FLAT)
    assets["ov_flowers_red"] = (ofr_d, ofr_n)

    # 4.3 Светящиеся лазурные цветы джунглей (ov_flowers_blue)
    ofb_d, ofb_n = make_pair(16, 16, opaque=False)
    for bx, by in ((5, 4), (11, 10), (4, 11)):
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ofb_d.set_at((bx + dx, by + dy), (65, 195, 245, 240))
            ofb_n.set_at((bx + dx, by + dy), N_FLAT)
        ofb_d.set_at((bx - 1, by + 1), (42, 104, 52, 215))
        ofb_n.set_at((bx - 1, by + 1), N_FLAT)
        ofb_d.set_at((bx, by), (225, 250, 255, 255))
        ofb_n.set_at((bx, by), N_FLAT)
    assets["ov_flowers_blue"] = (ofb_d, ofb_n)

    # 4.4 Ползучие лианы и корни на полу (ov_jungle_vines)
    ovv_d, ovv_n = make_pair(16, 16, opaque=False)
    for i in range(2, 14):
        vy = int(round(7.5 + math.sin(i * 0.6) * 3.2))
        ovv_d.set_at((i, vy), (52, 108, 44, 225))
        ovv_n.set_at((i, vy), N_FLAT)
        if i % 3 == 0 and vy + 1 < 15:
            ovv_d.set_at((i, vy + 1), (78, 152, 58, 225))
            ovv_n.set_at((i, vy + 1), N_FLAT)
    assets["ov_jungle_vines"] = (ovv_d, ovv_n)

    # 4.5 Опавшие листья монстеры и пальмы (ov_fallen_leaves)
    ofl_d, ofl_n = make_pair(16, 16, opaque=False)
    leaves = [((4, 4), (62, 118, 44, 215)), ((10, 5), (148, 96, 38, 215)), ((6, 11), (48, 98, 42, 215)), ((11, 12), (168, 118, 44, 215))]
    for (lx, ly), lcol in leaves:
        for dx, dy in ((0, 0), (1, 0), (0, 1), (-1, 1), (1, -1)):
            ofl_d.set_at((lx + dx, ly + dy), lcol)
            ofl_n.set_at((lx + dx, ly + dy), N_FLAT)
    assets["ov_fallen_leaves"] = (ofl_d, ofl_n)

    # 4.6 Трещины и золотая крошка на мраморе (ov_marble_cracks)
    omc_d, omc_n = make_pair(16, 16, opaque=False)
    m_crack = [(3, 2), (4, 3), (5, 4), (5, 5), (6, 6), (7, 7), (8, 8), (9, 8), (10, 9), (11, 11), (6, 8), (5, 10), (4, 12)]
    for cx_p, cy_p in m_crack:
        omc_d.set_at((cx_p, cy_p), (92, 86, 82, 225))
        omc_n.set_at((cx_p, cy_p), N_DEEP)
    for gx, gy in ((6, 5), (8, 7), (5, 9)):
        omc_d.set_at((gx, gy), (218, 178, 75, 220))
        omc_n.set_at((gx, gy), N_FLAT)
    assets["ov_marble_cracks"] = (omc_d, omc_n)

    # =========================================================================
    # 5. ПРИРОДНЫЕ ПРОПСЫ ДЖУНГЛЕЙ: КУСТЫ, ПЕНЬКИ, ПАПОРОТНИКИ (16x20)
    # =========================================================================

    # 5.1 Густой тропический куст (jungle_bush)
    jb_d, jb_n = make_pair(16, 20)
    for y in range(7, 19):
        for x in range(1, 15):
            d = math.hypot((x - 7.5) * 0.9, (y - 13.5) * 1.1)
            if d <= 6.2:
                sh = (x * 3 + y * 5) % 4
                if y <= 10 or sh == 0:
                    col, nc = (68, 148, 56), N_UP
                elif y >= 16:
                    col, nc = (26, 62, 30), N_DOWN
                else:
                    col = (46, 112, 44) if sh in (1, 2) else (36, 88, 36)
                    nc = N_LEFT if x < 6 else (N_RIGHT if x > 9 else N_FLAT)
                jb_d.set_at((x, y), col)
                jb_n.set_at((x, y), nc)
    assets["jungle_bush"] = enforce_crisp_rim_normals(jb_d, jb_n)

    # 5.2 Цветущий куст гибискуса (jungle_bush_flowers)
    jbf_d = jb_d.copy()
    jbf_n = jb_n.copy()
    for fx, fy in ((4, 10), (10, 9), (6, 14), (11, 14), (8, 11)):
        for dx, dy in ((0, 0), (1, 0), (0, 1)):
            jbf_d.set_at((fx + dx, fy + dy), (238, 58, 82))
        jbf_d.set_at((fx, fy), (255, 225, 80))
    assets["jungle_bush_flowers"] = enforce_crisp_rim_normals(jbf_d, jbf_n)

    # 5.3 Гигантский папоротник со спиральными вайями (giant_fern)
    gf_d, gf_n = make_pair(16, 20)
    frond_arcs = [(-1.0, 5), (-0.55, 3), (0.0, 2), (0.55, 3), (1.0, 5)]
    for dir_x, top_y in frond_arcs:
        for y in range(top_y, 19):
            t = (18 - y) / float(max(1, 18 - top_y))
            fx = int(round(7.5 + dir_x * (t * 5.2)))
            for w_f in (-1, 0, 1):
                if 1 <= fx + w_f < 15:
                    col = (82, 168, 60) if w_f == 0 else (46, 112, 42)
                    nc = N_UP if y < 11 else (N_LEFT if dir_x < 0 else N_RIGHT)
                    gf_d.set_at((fx + w_f, y), col)
                    gf_n.set_at((fx + w_f, y), nc)
    assets["giant_fern"] = enforce_crisp_rim_normals(gf_d, gf_n)

    # 5.4 Мшистый пень с древесными грибами (tree_stump)
    ts_d, ts_n = make_pair(16, 20)
    for y in range(9, 19):
        spread = 1 if y >= 16 else 0
        for x in range(4 - spread, 12 + spread):
            if y in (9, 10) and 4 <= x <= 11:
                # Светлый срез дерева с годовыми кольцами
                ring = abs(x - 7.5) in (1.5, 3.5)
                col = (148, 106, 62) if ring else (188, 145, 92)
                nc = N_UP
            else:
                is_moss = ((x + y) % 5 == 0 and y <= 15)
                col = (52, 112, 46) if is_moss else ((98, 62, 36) if x < 8 else (72, 44, 26))
                nc = N_LEFT if x < 6 else (N_RIGHT if x > 9 else N_FLAT)
            ts_d.set_at((x, y), col)
            ts_n.set_at((x, y), nc)
    # Яркие шляпки грибов-трутовиков сбоку
    for mx_s, my_s in ((3, 13), (4, 13), (11, 14), (12, 14)):
        ts_d.set_at((mx_s, my_s), (235, 165, 55))
        ts_n.set_at((mx_s, my_s), N_UP)
    assets["tree_stump"] = enforce_crisp_rim_normals(ts_d, ts_n)

    # 5.5 Поваленное трухлявое бревно во мху (hollow_log)
    hl_d, hl_n = make_pair(16, 20)
    for y in range(11, 18):
        for x in range(1, 15):
            if x in (1, 2) and 12 <= y <= 16:
                hl_d.set_at((x, y), (32, 22, 16) if x == 2 else (138, 96, 56))
                hl_n.set_at((x, y), N_LEFT)
            elif y in (11, 12) and (x * 3 + y) % 3 != 0:
                hl_d.set_at((x, y), (56, 124, 48))
                hl_n.set_at((x, y), N_UP)
            else:
                col = (104, 66, 38) if y < 15 else (68, 42, 24)
                nc = N_UP if y <= 13 else N_DOWN
                hl_d.set_at((x, y), col)
                hl_n.set_at((x, y), nc)
    assets["hollow_log"] = enforce_crisp_rim_normals(hl_d, hl_n)

    # 5.6 Замшелый джунглевый валун (jungle_boulder)
    jbo_d, jbo_n = make_pair(16, 20)
    for y in range(8, 19):
        for x in range(2, 14):
            if math.hypot((x - 7.5) * 0.9, (y - 14.0) * 1.1) <= 5.6:
                if y <= 11 and (x + y) % 2 == 0:
                    col, nc = (54, 118, 48), N_UP
                elif y <= 12:
                    col, nc = (118, 114, 108), N_UP
                elif y >= 16:
                    col, nc = (62, 58, 56), N_DOWN
                else:
                    col = (92, 88, 84) if x < 8 else (76, 72, 70)
                    nc = N_LEFT if x < 6 else (N_RIGHT if x > 9 else N_FLAT)
                jbo_d.set_at((x, y), col)
                jbo_n.set_at((x, y), nc)
    assets["jungle_boulder"] = enforce_crisp_rim_normals(jbo_d, jbo_n)

    # =========================================================================
    # 6. ДЕРЕВЯННЫЕ ПОСТРОЙКИ И ПРИМИТИВНАЯ МЕБЕЛЬ АБОРИГЕНОВ (16x20)
    # =========================================================================

    # 6.1 Тотемный столб духов с перьями и горящими глазами (tribal_totem)
    tt_d, tt_n = make_pair(16, 20)
    for y in range(2, 19):
        # Крылья/перья тотема сверху (y=4..7)
        if 4 <= y <= 7:
            for x in (2, 3, 4, 11, 12, 13):
                col = (225, 62, 52) if y % 2 == 0 else (52, 185, 165)
                tt_d.set_at((x, y), col)
                tt_n.set_at((x, y), N_UP)
        for x in range(5, 11):
            if y in (5, 12) and x in (6, 9):
                col = (245, 205, 55) if y == 5 else (65, 245, 185)  # Светящиеся глаза двух масок
                nc = N_FLAT
            elif y in (8, 15) and 6 <= x <= 9:
                col, nc = (225, 215, 195), N_UP  # Оскаленные белые зубы
            elif y in (3, 10):
                col, nc = (195, 55, 45), N_UP    # Боевой раскрас лба
            else:
                col = (122, 78, 42) if x < 8 else (92, 56, 30)
                nc = N_LEFT if x == 5 else (N_RIGHT if x == 10 else N_FLAT)
            tt_d.set_at((x, y), col)
            tt_n.set_at((x, y), nc)
    assets["tribal_totem"] = enforce_crisp_rim_normals(tt_d, tt_n)

    # 6.2 Низкий плетёный стол аборигенов с чашей фруктов (tribal_table)
    tb_d, tb_n = make_pair(16, 20)
    for y in range(9, 19):
        for x in range(1, 15):
            if 9 <= y <= 12:
                is_cord = x in (3, 12)
                col = (178, 142, 78) if is_cord else ((128, 88, 46) if (x + y) % 2 == 0 else (106, 70, 36))
                tb_d.set_at((x, y), col)
                tb_n.set_at((x, y), N_FLAT)
            elif x in (2, 3, 12, 13):
                tb_d.set_at((x, y), (86, 54, 28))
                tb_n.set_at((x, y), N_LEFT if x < 8 else N_RIGHT)
    # Глиняная миска с тропическими плодами на столе
    for x in range(6, 10):
        tb_d.set_at((x, 8), (168, 78, 48))
        tb_n.set_at((x, 8), N_FLAT)
    tb_d.set_at((7, 7), (245, 195, 55))
    tb_d.set_at((8, 7), (225, 58, 68))
    assets["tribal_table"] = enforce_crisp_rim_normals(tb_d, tb_n)

    # 6.3 Пень-табурет со шкурой ягуара (tribal_stool)
    tst_d, tst_n = make_pair(16, 20)
    for y in range(11, 18):
        for x in range(4, 12):
            if y in (11, 12, 13):
                spot = (x + y) % 3 == 0
                col = (52, 32, 20) if spot else (218, 158, 56)
                nc = N_FLAT
            else:
                col = (104, 66, 36) if x < 8 else (78, 48, 26)
                nc = N_LEFT if x <= 5 else (N_RIGHT if x >= 10 else N_FLAT)
            tst_d.set_at((x, y), col)
            tst_n.set_at((x, y), nc)
    assets["tribal_stool"] = enforce_crisp_rim_normals(tst_d, tst_n)

    # 6.4 Спальная циновка из пальмовых листьев и бамбука (tribal_bed)
    tbd_d, tbd_n = make_pair(16, 20)
    for y in range(4, 19):
        for x in range(2, 14):
            if y in (4, 18) or x in (2, 13):
                col = (118, 82, 42)
                nc = N_LEFT if x == 2 else (N_RIGHT if x == 13 else N_FLAT)
            elif 5 <= y <= 8 and 4 <= x <= 11:
                # Деревянный подголовник с резьбой
                col = (158, 62, 48) if y == 6 else (138, 94, 48)
                nc = N_FLAT
            else:
                weave = (x + y) % 2 == 0
                col = (92, 142, 62) if weave else (74, 118, 48)
                nc = N_FLAT
            tbd_d.set_at((x, y), col)
            tbd_n.set_at((x, y), nc)
    assets["tribal_bed"] = enforce_crisp_rim_normals(tbd_d, tbd_n)

    # 6.5 Оружейная стойка с кремневыми копьями и племенным щитом (tribal_rack)
    trk_d, trk_n = make_pair(16, 20)
    for y in range(3, 19):
        for x in (3, 7, 12):
            trk_d.set_at((x, y), (210, 215, 225) if y <= 5 else (118, 76, 40))
            trk_n.set_at((x, y), N_UP if y <= 5 else N_FLAT)
        if y in (8, 16):
            for x in range(2, 14):
                trk_d.set_at((x, y), (96, 62, 32))
                trk_n.set_at((x, y), N_UP)
    # Овальный расписной щит в центре стойки
    for y in range(8, 16):
        for x in range(5, 11):
            if math.hypot((x - 7.5) * 1.1, (y - 11.5) * 0.85) <= 3.2:
                col = (215, 62, 48) if (x + y) % 2 == 0 else (235, 195, 72)
                trk_d.set_at((x, y), col)
                trk_n.set_at((x, y), N_UP)
    assets["tribal_rack"] = enforce_crisp_rim_normals(trk_d, trk_n)

    # 6.6 Ритуальный кожаный барабан (tribal_drum)
    tdr_d, tdr_n = make_pair(16, 20)
    for y in range(7, 19):
        w_d = 4 if 8 <= y <= 14 else 3
        for x in range(8 - w_d, 8 + w_d):
            if y in (7, 8):
                col, nc = (228, 212, 178), N_FLAT
            elif y in (9, 10):
                col, nc = (195, 55, 45) if (x + y) % 2 == 0 else (228, 212, 178), N_UP
            else:
                col = (118, 72, 38) if x < 8 else (88, 52, 26)
                nc = N_LEFT if x < 7 else (N_RIGHT if x > 8 else N_FLAT)
            tdr_d.set_at((x, y), col)
            tdr_n.set_at((x, y), nc)
    assets["tribal_drum"] = enforce_crisp_rim_normals(tdr_d, tdr_n)

    # 6.7 Расписная глиняная амфора аборигенов (tribal_pot)
    pot_diffuse, pot_normal = make_pair(16, 20)
    for y in range(6, 19):
        rad_p = 2 if y in (6, 7, 18) else (3 if y in (8, 17) else 5)
        for x in range(8 - rad_p, 8 + rad_p):
            if y in (11, 12):
                col = (232, 218, 185) if (x + y) % 2 == 0 else (46, 158, 132)
            else:
                col = (186, 86, 52) if x < 8 else (142, 62, 36)
            nc = N_UP if y <= 8 else (N_LEFT if x < 7 else (N_RIGHT if x > 8 else N_FLAT))
            pot_diffuse.set_at((x, y), col)
            pot_normal.set_at((x, y), nc)
    assets["tribal_pot"] = enforce_crisp_rim_normals(pot_diffuse, pot_normal)

    # 6.8 Костяной фетиш-шест с рогатым черепом (tribal_skull_pole)
    tsp_d, tsp_n = make_pair(16, 20)
    for y in range(3, 19):
        if y >= 8:
            for x in (7, 8):
                tsp_d.set_at((x, y), (108, 68, 36))
                tsp_n.set_at((x, y), N_LEFT if x == 7 else N_RIGHT)
    # Рога и череп сверху (y=3..9)
    for x in range(2, 14):
        hy = 4 if x in (2, 13) else (5 if x in (3, 4, 11, 12) else 6)
        tsp_d.set_at((x, hy), (185, 175, 155))
        tsp_n.set_at((x, hy), N_UP)
    for y in range(4, 10):
        for x in range(5, 11):
            if y == 6 and x in (6, 9):
                col = (245, 65, 55)  # Горящие глазницы
            else:
                col = (232, 224, 205) if y < 8 else (198, 188, 168)
            tsp_d.set_at((x, y), col)
            tsp_n.set_at((x, y), N_UP if y <= 6 else N_FLAT)
    assets["tribal_skull_pole"] = enforce_crisp_rim_normals(tsp_d, tsp_n)

    # 6.9 Плетёный сундук джунглей с нефритовым замком (tribal_chest)
    tch_d, tch_n = make_pair(16, 20)
    for y in range(8, 19):
        for x in range(2, 14):
            if x in (2, 13) or y in (8, 12, 18):
                col = (188, 148, 68)
            else:
                col = (118, 82, 42) if (x + y) % 2 == 0 else (94, 62, 30)
            if 7 <= x <= 8 and 11 <= y <= 13:
                col = (62, 215, 145)  # Нефритовая застёжка
            nc = N_UP if y <= 11 else (N_LEFT if x < 6 else (N_RIGHT if x > 9 else N_FLAT))
            tch_d.set_at((x, y), col)
            tch_n.set_at((x, y), nc)
    assets["tribal_chest"] = enforce_crisp_rim_normals(tch_d, tch_n)

    # =========================================================================
    # 7. ОБЪЕКТЫ И ПРОПСЫ МРАМОРНОГО ХРАМА (16x20)
    # =========================================================================

    # 7.1 Стройная колонна из белого мрамора с золотой капителью (marble_pillar)
    mp_d, mp_n = make_pair(16, 20)
    for y in range(1, 19):
        w_p = 5 if y in (1, 2, 17, 18) else 4
        for x in range(8 - w_p, 8 + w_p):
            if y in (2, 16):
                col, nc = (228, 186, 78), N_UP
            else:
                flute = (x % 2 == 0)
                if x < 6:
                    col, nc = (198, 192, 184), N_LEFT
                elif x > 9:
                    col, nc = (175, 168, 160), N_RIGHT
                else:
                    col = (242, 238, 228) if flute else (218, 212, 202)
                    nc = N_UP if y <= 3 else N_FLAT
            mp_d.set_at((x, y), col)
            mp_n.set_at((x, y), nc)
    assets["marble_pillar"] = enforce_crisp_rim_normals(mp_d, mp_n)

    # 7.2 Обрушенная мраморная колонна в лианах (marble_pillar_broken)
    mpb_d, mpb_n = make_pair(16, 20)
    for y in range(9, 19):
        w_p = 5 if y in (17, 18) else 4
        for x in range(8 - w_p, 8 + w_p):
            if y == 9 and x in (4, 5, 10, 11):
                continue
            if y == 16:
                col, nc = (228, 186, 78), N_UP
            elif (x + y) % 5 == 0 and y <= 14:
                col, nc = (52, 122, 48), N_UP
            else:
                col = (232, 226, 216) if x <= 8 else (188, 182, 174)
                nc = N_UP if y <= 11 else (N_LEFT if x < 7 else N_RIGHT)
            mpb_d.set_at((x, y), col)
            mpb_n.set_at((x, y), nc)
    assets["marble_pillar_broken"] = enforce_crisp_rim_normals(mpb_d, mpb_n)

    # 7.3 Алтарь Солнечного Храма из белого мрамора, золота и нефрита (marble_altar)
    ma_d, ma_n = make_pair(16, 20)
    for y in range(7, 19):
        w_a = 6 if y in (7, 8, 17, 18) else 5
        for x in range(8 - w_a, 8 + w_a):
            if y in (7, 8) and 5 <= x <= 10:
                col, nc = (56, 198, 138), N_FLAT  # Нефритовая чаша на столешнице
            elif y in (9, 16) or x in (8 - w_a, 8 + w_a - 1):
                col, nc = (232, 188, 76), N_FLAT
            else:
                col = (236, 230, 220) if y < 12 else (206, 200, 190)
                nc = N_FLAT
            ma_d.set_at((x, y), col)
            ma_n.set_at((x, y), nc)
    assets["marble_altar"] = enforce_crisp_rim_normals(ma_d, ma_n)

    # 7.4 Золотая храмовая жаровня на белом мраморном пьедестале (marble_brazier)
    mb_d, mb_n = make_pair(16, 20)
    for y in range(5, 19):
        for x in range(4, 12):
            if y < 11:
                if math.hypot(x - 7.5, y - 8.5) <= 3.6:
                    col = (255, 240, 135) if abs(x - 7.5) <= 1.2 and y >= 8 else ((255, 165, 45) if (x + y) % 2 == 0 else (235, 85, 30))
                    mb_d.set_at((x, y), col)
                    mb_n.set_at((x, y), N_UP)
            elif y in (11, 12):
                mb_d.set_at((x, y), (242, 198, 82))
                mb_n.set_at((x, y), N_UP)
            elif 5 <= x <= 10:
                col = (232, 226, 216) if x < 8 else (196, 190, 180)
                mb_d.set_at((x, y), col)
                mb_n.set_at((x, y), N_LEFT if x < 7 else N_RIGHT)
    assets["marble_brazier"] = enforce_crisp_rim_normals(mb_d, mb_n)

    # 7.5 Статуя мраморного стража с изумрудными глазами (marble_statue)
    ms_d, ms_n = make_pair(16, 20)
    for y in range(2, 19):
        for x in range(4, 12):
            if y <= 4 and x in (4, 11):
                ms_d.set_at((x, y), (235, 192, 75))  # Золотой гребень шлема
                ms_n.set_at((x, y), N_UP)
            elif 3 <= y <= 8 and 5 <= x <= 10:
                col = (65, 250, 155) if (y == 5 and x in (6, 9)) else (236, 230, 220)
                ms_d.set_at((x, y), col)
                ms_n.set_at((x, y), N_UP)
            elif 9 <= y <= 15:
                col = (228, 186, 76) if y == 9 else ((232, 226, 216) if x < 8 else (198, 192, 182))
                ms_d.set_at((x, y), col)
                ms_n.set_at((x, y), N_LEFT if x < 7 else (N_RIGHT if x > 8 else N_FLAT))
            elif y >= 16:
                ms_d.set_at((x, y), (182, 176, 168))
                ms_n.set_at((x, y), N_UP if y == 16 else N_FLAT)
    assets["marble_statue"] = enforce_crisp_rim_normals(ms_d, ms_n)

    # 7.6 Храмовая мраморная купель с чистой водой и лотосом (marble_fountain)
    mf_d, mf_n = make_pair(16, 20)
    for y in range(7, 19):
        for x in range(2, 14):
            d_f = math.hypot((x - 7.5) * 0.85, (y - 12.0) * 1.15)
            if d_f <= 5.5:
                if d_f <= 3.6 and y <= 14:
                    # Изумрудно-голубая вода и розовый цветок лотоса в центре
                    is_lotus = (7 <= x <= 8 and 10 <= y <= 11)
                    col = (245, 135, 175) if is_lotus else (68, 185, 215)
                    nc = N_FLAT
                else:
                    col = (238, 232, 222) if y <= 11 else ((228, 186, 78) if y == 13 else (196, 190, 180))
                    nc = N_FLAT
                mf_d.set_at((x, y), col)
                mf_n.set_at((x, y), nc)
    assets["marble_fountain"] = enforce_crisp_rim_normals(mf_d, mf_n)

    # 7.7 Белый мраморный саркофаг с золотой маской (marble_sarcophagus)
    msa_d, msa_n = make_pair(16, 20)
    for y in range(4, 19):
        for x in range(3, 13):
            if x in (3, 12) or y in (4, 18):
                col = (188, 182, 172)
            elif 6 <= y <= 10 and 6 <= x <= 9:
                col = (52, 188, 135) if (y == 7 and x in (6, 9)) else (238, 195, 78)
            elif x in (7, 8) and 11 <= y <= 16:
                col = (225, 182, 72)
            else:
                col = (236, 230, 220) if x < 8 else (212, 206, 196)
            msa_d.set_at((x, y), col)
            msa_n.set_at((x, y), N_FLAT)
    assets["marble_sarcophagus"] = enforce_crisp_rim_normals(msa_d, msa_n)

    # 7.8 Бело-золотая мраморная урна храма (marble_urn)
    mu_d, mu_n = make_pair(16, 20)
    for y in range(6, 19):
        rad_u = 2 if y in (6, 7, 17, 18) else (3 if y in (8, 16) else 4)
        for x in range(8 - rad_u, 8 + rad_u):
            if y in (6, 11, 12, 18):
                col = (235, 192, 78)
            else:
                col = (238, 232, 222) if x < 8 else (202, 196, 186)
            nc = N_UP if y <= 8 else (N_LEFT if x < 7 else (N_RIGHT if x > 8 else N_FLAT))
            mu_d.set_at((x, y), col)
            mu_n.set_at((x, y), nc)
    assets["marble_urn"] = enforce_crisp_rim_normals(mu_d, mu_n)


def _register_jungle_variants(assets):
    # =========================================================================
    # 8. РАСШИРЕННЫЙ ПАК ПОВЕРХНОСТЕЙ И СТЕН (ВОДА СЕНОТОВ, МРАМОР, БОЛОТО)
    # =========================================================================

    # 8.1 Анимированная 3-кадровая лазурная вода храмовых купален и сенотов (floor_temple_water)
    temple_water_frames = []
    tau_w = 2.0 * math.pi / 16.0
    for frame_i in range(3):
        phase = frame_i * (2.0 * math.pi / 3.0)
        tw_d2, tw_n2 = make_pair(16, 16, opaque=True)
        for y in range(16):
            for x in range(16):
                w1 = math.sin(x * tau_w + y * tau_w + phase)
                w2 = math.cos(x * tau_w - y * tau_w * 2.0 - phase)
                wv = (w1 + w2) * 0.5
                c_r = int(28 + (wv + 1.0) * 18)
                c_g = int(115 + (wv + 1.0) * 32)
                c_b = int(128 + (wv + 1.0) * 35)
                if wv > 0.58:
                    c_r, c_g, c_b = 165, 242, 235
                nc = N_UP if w1 > 0.35 else (N_DOWN if w1 < -0.35 else N_FLAT)
                tw_d2.set_at((x, y), (c_r, c_g, c_b, 255))
                tw_n2.set_at((x, y), nc)
        temple_water_frames.append((tw_d2, tw_n2))
    assets["floor_temple_water"] = temple_water_frames[0]
    assets["_temple_water_frames"] = temple_water_frames

    # 8.2 Тропическая трясина с ряской и пузырями (floor_jungle_swamp)
    sw_d, sw_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            h = ((x * 61 + y * 109 + x * y * 17) % 23)
            if (x - 5) ** 2 + (y - 6) ** 2 <= 2.2 or (x - 11) ** 2 + (y - 12) ** 2 <= 2.2:
                col, nc = (78, 138, 48, 255), N_UP  # Кочки ряски
            elif h in (0, 1):
                col, nc = (62, 112, 44, 255), N_FLAT
            elif h == 2:
                col, nc = (95, 162, 72, 255), N_UP  # Болотный пузырь
            else:
                sh = (h % 4) * 2
                col, nc = (28 + sh, 52 + sh, 30 + sh, 255), N_FLAT
            sw_d.set_at((x, y), col)
            sw_n.set_at((x, y), nc)
    assets["floor_jungle_swamp"] = (sw_d, sw_n)

    # 8.3 Древняя брусчатка джунглей со мхом в швах (floor_jungle_cobble)
    jc_d, jc_n = make_pair(16, 16, opaque=True)
    jc_d.fill((36, 78, 38, 255))
    jc_n.fill(N_DEEP)
    cobbles = [(1, 1, 6, 6), (8, 1, 7, 5), (1, 8, 8, 7), (10, 7, 5, 8)]
    for bx, by, bw, bh in cobbles:
        for y in range(by, by + bh):
            for x in range(bx, bx + bw):
                sh = ((x * 19 + y * 37) % 7) - 3
                col = (94 + sh, 92 + sh, 84 + sh, 255)
                if x == bx and y == by:
                    col = (112, 110, 100, 255)
                jc_d.set_at((x, y), col)
                jc_n.set_at((x, y), N_FLAT)
    assets["floor_jungle_cobble"] = (jc_d, jc_n)

    # 8.4 Золотистый речной песок с волнами прибоя (floor_river_sand)
    rs_d, rs_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            ripple = int(math.sin((x + y * 0.5) * 0.8) * 6)
            grain = ((x * 43 + y * 89) % 7) - 3
            if (x * 17 + y * 31) % 29 == 0:
                col, nc = (235, 215, 165, 255), N_FLAT  # Ракушка / кварц
            else:
                col, nc = (194 + ripple + grain, 162 + ripple + grain, 102 + grain, 255), N_FLAT
            rs_d.set_at((x, y), col)
            rs_n.set_at((x, y), nc)
    assets["floor_river_sand"] = (rs_d, rs_n)

    # 8.5 Тёмный шестигранный базальт пещер (floor_cave_basalt)
    cb_d2, cb_n2 = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            hx = (x + (4 if (y // 8) % 2 else 0)) % 8
            hy = y % 8
            if hx == 0 or hy == 0:
                col, nc = (22, 24, 30, 255), N_DEEP
            else:
                sh = ((x * 23 + y * 41) % 5) - 2
                col, nc = (44 + sh, 48 + sh, 58 + sh, 255), N_FLAT
            cb_d2.set_at((x, y), col)
            cb_n2.set_at((x, y), nc)
    assets["floor_cave_basalt"] = (cb_d2, cb_n2)

    # 8.6 Плетёная тростниковая циновка для пола хижин (floor_tribal_mat)
    tm_d, tm_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            herring = ((x + y) // 2) % 2 == 0
            is_border = x in (0, 15) or y in (0, 15)
            if is_border:
                col = (165, 52, 42, 255) if (x + y) % 2 == 0 else (122, 38, 30, 255)
            else:
                col = (182, 146, 82, 255) if herring else (154, 118, 62, 255)
            tm_d.set_at((x, y), col)
            tm_n.set_at((x, y), N_FLAT)
    assets["floor_tribal_mat"] = (tm_d, tm_n)

    # 8.7 Шахматный бело-изумрудный мраморный пол (floor_marble_checker)
    mc_d, mc_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            if x in (0, 8) or y in (0, 8):
                col, nc = (168, 138, 72, 255), N_DEEP
            else:
                is_white = ((x // 8) + (y // 8)) % 2 == 0
                vein = ((x * 3 + y * 5) % 11 == 0)
                if is_white:
                    col = (195, 190, 182, 255) if vein else (232, 226, 218, 255)
                else:
                    col = (68, 138, 108, 255) if vein else (38, 86, 68, 255)
                nc = N_FLAT
            mc_d.set_at((x, y), col)
            mc_n.set_at((x, y), nc)
    assets["floor_marble_checker"] = (mc_d, mc_n)

    # 8.8 Розовый кварцевый мрамор с золотыми прожилками (floor_marble_rose)
    mr_d2, mr_n2 = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            if x == 0 or y == 0:
                col, nc = (148, 108, 112, 255), N_DEEP
            elif (x * 2 - y * 3) % 17 == 0:
                col, nc = (228, 188, 92, 255), N_FLAT
            elif (x + y * 2) % 9 == 0:
                col, nc = (198, 148, 154, 255), N_FLAT
            else:
                sh = ((x * 13 + y * 29) % 5) - 2
                col, nc = (228 + sh, 186 + sh, 190 + sh, 255), N_FLAT
            mr_d2.set_at((x, y), col)
            mr_n2.set_at((x, y), nc)
    assets["floor_marble_rose"] = (mr_d2, mr_n2)

    # 8.9 Полированный зелёный нефрит святилища (floor_marble_jade)
    mj_d, mj_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            if x == 0 or y == 0:
                col, nc = (24, 62, 46, 255), N_DEEP
            elif x in (1, 14) and y in (1, 14):
                col, nc = (232, 192, 82, 255), N_FLAT
            else:
                vein = ((x * 5 + y * 3) % 13 == 0)
                col = (92, 188, 138, 255) if vein else (48, 128, 92, 255)
                nc = N_FLAT
            mj_d.set_at((x, y), col)
            mj_n.set_at((x, y), nc)
    assets["floor_marble_jade"] = (mj_d, mj_n)

    # 8.10 Золотая процессионная плита солнечного храма (floor_temple_gold)
    tg_d, tg_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            d_c = max(abs(x - 7.5), abs(y - 7.5))
            if x == 0 or y == 0:
                col, nc = (118, 86, 32, 255), N_DEEP
            elif d_c in (2.5, 5.5):
                col, nc = (248, 218, 112, 255), N_FLAT
            elif d_c <= 1.5:
                col, nc = (58, 195, 142, 255), N_FLAT
            else:
                col, nc = (208, 164, 64, 255), N_FLAT
            tg_d.set_at((x, y), col)
            tg_n.set_at((x, y), nc)
    assets["floor_temple_gold"] = (tg_d, tg_n)

    # 8.11 Плетёная тростниковая стена хижины аборигенов (wall_bamboo_weave)
    wbw_d, wbw_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            if y in (0, 1, 14, 15):
                wbw_d.set_at((x, y), (92, 138, 52, 255) if y < 2 else (72, 46, 26, 255))
                wbw_n.set_at((x, y), N_UP if y < 2 else N_DOWN)
            elif x in (0, 15):
                wbw_d.set_at((x, y), (88, 56, 32, 255))
                wbw_n.set_at((x, y), N_LEFT if x == 0 else N_RIGHT)
            else:
                over = ((x // 2) + (y // 2)) % 2 == 0
                col = (168, 128, 68, 255) if over else (132, 96, 48, 255)
                nc = N_UP if (over and y % 2 == 0) else (N_LEFT if (not over and x % 2 == 0) else N_FLAT)
                wbw_d.set_at((x, y), col)
                wbw_n.set_at((x, y), nc)
    assets["wall_bamboo_weave"] = (wbw_d, wbw_n)

    # 8.12 Скальная стена пещеры с биолюминесцентными кристаллами (wall_cave_crystal)
    wcc_d = assets["wall_cave"][0].copy()
    wcc_n = assets["wall_cave"][1].copy()
    crystals_xy = [(3, 4), (4, 3), (4, 4), (11, 10), (12, 9), (12, 10), (7, 12), (8, 11)]
    for cx_p, cy_p in crystals_xy:
        wcc_d.set_at((cx_p, cy_p), (95, 245, 225, 255) if (cx_p + cy_p) % 2 == 0 else (45, 185, 215, 255))
        wcc_n.set_at((cx_p, cy_p), N_UP)
    assets["wall_cave_crystal"] = (wcc_d, wcc_n)

    # 8.13 Чёрный обсидианово-золотой монолит храма (wall_marble_obsidian)
    wmo_d, wmo_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            if x in (0, 15) or y in (0, 7, 15):
                col, nc = (218, 178, 72, 255), N_UP if y in (0, 7) else N_DEEP
            else:
                shine = ((x + y * 2) % 9 == 0)
                col = (68, 62, 88, 255) if shine else (32, 28, 42, 255)
                nc = N_UP if y in (1, 8) else (N_DOWN if y in (6, 14) else N_FLAT)
            wmo_d.set_at((x, y), col)
            wmo_n.set_at((x, y), nc)
    assets["wall_marble_obsidian"] = (wmo_d, wmo_n)

    # 8.14 Стена храма с барельефом Пернатого Змея (wall_temple_relief)
    wtr_d = assets["wall_marble_temple"][0].copy()
    wtr_n = assets["wall_marble_temple"][1].copy()
    for y in range(3, 13):
        for x in range(3, 13):
            if y in (3, 12) or x in (3, 12):
                wtr_d.set_at((x, y), (225, 182, 72, 255))
                wtr_n.set_at((x, y), N_UP)
            elif (x - 7.5) ** 2 + (y - 7.5) ** 2 <= 9.0:
                is_eye = (x in (6, 9) and y == 6)
                col = (235, 55, 65, 255) if is_eye else (52, 178, 122, 255)
                wtr_d.set_at((x, y), col)
                wtr_n.set_at((x, y), N_UP)
    assets["wall_temple_relief"] = (wtr_d, wtr_n)

    # =========================================================================
    # 9. ДОПОЛНИТЕЛЬНЫЕ ОВЕРЛЕИ (16x16, opaque=False)
    # =========================================================================

    # 9.1 Кувшинки с цветущим розовым лотосом (ov_water_lily)
    owl_d, owl_n = make_pair(16, 16, opaque=False)
    for lx, ly, rad in ((5.5, 6.0, 3.2), (11.5, 11.5, 2.5)):
        for y in range(16):
            for x in range(16):
                if math.hypot(x - lx, y - ly) <= rad and not (x > lx and y == int(ly)):
                    owl_d.set_at((x, y), (56, 138, 52, 235))
                    owl_n.set_at((x, y), N_FLAT)
    for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
        owl_d.set_at((5 + dx, 5 + dy), (248, 145, 185, 250))
        owl_n.set_at((5 + dx, 5 + dy), N_FLAT)
    owl_d.set_at((5, 5), (255, 230, 95, 255))
    assets["ov_water_lily"] = (owl_d, owl_n)

    # 9.2 Светящиеся неоновые грибочки пещер (ov_glow_shrooms)
    ogs_d, ogs_n = make_pair(16, 16, opaque=False)
    for sx, sy in ((4, 5), (11, 6), (7, 12), (12, 11)):
        ogs_d.set_at((sx, sy + 1), (185, 215, 225, 225))
        ogs_n.set_at((sx, sy + 1), N_FLAT)
        for dx in (-1, 0, 1):
            ogs_d.set_at((sx + dx, sy), (75, 245, 215, 245))
            ogs_n.set_at((sx + dx, sy), N_FLAT)
    assets["ov_glow_shrooms"] = (ogs_d, ogs_n)

    # 9.3 Россыпь золотых и алых храмовых лепестков (ov_petals_gold)
    opg_d, opg_n = make_pair(16, 16, opaque=False)
    for px, py, is_g in ((3, 4, True), (6, 3, False), (11, 5, True), (5, 10, True), (9, 12, False), (13, 10, True), (8, 7, True)):
        col = (248, 202, 68, 230) if is_g else (235, 72, 82, 230)
        opg_d.set_at((px, py), col)
        opg_n.set_at((px, py), N_FLAT)
        opg_d.set_at((px + 1, py), col)
        opg_n.set_at((px + 1, py), N_FLAT)
    assets["ov_petals_gold"] = (opg_d, opg_n)

    # 9.4 Опавшие узкие листья бамбука (ov_bamboo_leaves)
    obl_d, obl_n = make_pair(16, 16, opaque=False)
    for lx, ly, dx, dy in ((3, 4, 1, 1), (10, 3, -1, 1), (5, 11, 1, 0), (11, 12, 1, -1)):
        for s in range(4):
            obl_d.set_at((lx + dx * s, ly + dy * s), (86, 152, 58, 225))
            obl_n.set_at((lx + dx * s, ly + dy * s), N_FLAT)
    assets["ov_bamboo_leaves"] = (obl_d, obl_n)

    # 9.5 Узловатые корни мангров (ov_mangrove_roots)
    omr_d, omr_n = make_pair(16, 16, opaque=False)
    for i in range(1, 15):
        ry1 = int(round(4.5 + math.sin(i * 0.5) * 2.0))
        ry2 = int(round(11.5 - math.cos(i * 0.5) * 2.0))
        for ry in (ry1, ry2):
            omr_d.set_at((i, ry), (98, 64, 38, 235))
            omr_n.set_at((i, ry), N_FLAT)
    assets["ov_mangrove_roots"] = (omr_d, omr_n)

    # 9.6 Выбеленные кости и череп в зарослях (ov_bones)
    obn_d, obn_n = make_pair(16, 16, opaque=False)
    for y in range(5, 9):
        for x in range(5, 9):
            obn_d.set_at((x, y), (35, 30, 32, 235) if (y == 7 and x in (6, 8)) else (225, 218, 198, 240))
            obn_n.set_at((x, y), N_FLAT)
    for i in range(4):
        obn_d.set_at((9 + i, 10 + i), (218, 210, 190, 235))
        obn_n.set_at((9 + i, 10 + i), N_FLAT)
        obn_d.set_at((12 - i, 10 + i), (218, 210, 190, 235))
        obn_n.set_at((12 - i, 10 + i), N_FLAT)
    assets["ov_bones"] = (obn_d, obn_n)

    # 9.7 Блестящая лужица тропического дождя (ov_mud_puddle)
    omp_d, omp_n = make_pair(16, 16, opaque=False)
    for y in range(4, 13):
        for x in range(3, 14):
            if math.hypot((x - 8.0) * 0.8, (y - 8.0) * 1.1) <= 3.8:
                col = (115, 175, 205, 195) if (x + y == 13) else (48, 92, 118, 185)
                omp_d.set_at((x, y), col)
                omp_n.set_at((x, y), N_FLAT)
    assets["ov_mud_puddle"] = (omp_d, omp_n)

    # 9.8 Золотая храмовая инкрустация-розетка для мраморного пола (ov_gold_filigree)
    ogf_d, ogf_n = make_pair(16, 16, opaque=False)
    for y in range(2, 14):
        for x in range(2, 14):
            d = abs(x - 7.5) + abs(y - 7.5)
            if 4.5 <= d <= 5.5 or (x in (7, 8) and 3 <= y <= 12) or (y in (7, 8) and 3 <= x <= 12):
                ogf_d.set_at((x, y), (235, 192, 78, 225))
                ogf_n.set_at((x, y), N_FLAT)
    assets["ov_gold_filigree"] = (ogf_d, ogf_n)

    # =========================================================================
    # 10. ПРИРОДНЫЕ И ПЕЩЕРНЫЕ ПРОПСЫ ДЖУНГЛЕЙ (16x20)
    # =========================================================================

    # 10.1 Хищная венерина мухоловка с зубастыми челюстями (venus_flytrap)
    vf_d, vf_n = make_pair(16, 20)
    for y in range(11, 19):
        for x in (6, 7, 8, 9):
            if (x + y) % 2 == 0:
                vf_d.set_at((x, y), (48, 128, 46))
                vf_n.set_at((x, y), N_UP)
    for cx_h, cy_h in ((5, 9), (10, 8)):
        for dy in range(-2, 3):
            for dx in range(-3, 4):
                if dx * dx + dy * dy <= 8:
                    col = (215, 48, 68) if dy == 0 else ((245, 240, 220) if abs(dy) == 1 and dx % 2 == 0 else (72, 168, 56))
                    vf_d.set_at((cx_h + dx, cy_h + dy), col)
                    vf_n.set_at((cx_h + dx, cy_h + dy), N_UP if dy <= 0 else N_DOWN)
    assets["venus_flytrap"] = enforce_crisp_rim_normals(vf_d, vf_n)

    # 10.2 Роща молодых стеблей бамбука (bamboo_clump)
    bc_d, bc_n = make_pair(16, 20)
    for sx in (3, 4, 7, 8, 11, 12):
        for y in range(2, 19):
            is_node = (y % 4 == 0)
            col = (142, 178, 78) if is_node else ((86, 152, 54) if sx % 2 == 1 else (62, 118, 42))
            bc_d.set_at((sx, y), col)
            bc_n.set_at((sx, y), N_UP if is_node else (N_LEFT if sx % 2 == 1 else N_RIGHT))
    for lx, ly in ((2, 5), (5, 7), (9, 4), (13, 6), (14, 10)):
        bc_d.set_at((lx, ly), (102, 178, 64))
        bc_n.set_at((lx, ly), N_UP)
    assets["bamboo_clump"] = enforce_crisp_rim_normals(bc_d, bc_n)

    # 10.3 Гигантский пятнистый цветок раффлезии (rafflesia_flower)
    rf_d, rf_n = make_pair(16, 20)
    for y in range(8, 19):
        for x in range(1, 15):
            d = math.hypot((x - 7.5) * 0.85, (y - 13.5) * 1.1)
            if d <= 5.8:
                if d <= 2.2:
                    col, nc = (68, 22, 32) if (x + y) % 2 else (215, 165, 55), N_DEEP
                else:
                    spot = (x * 3 + y * 5) % 5 == 0
                    col = (245, 225, 195) if spot else (198, 48, 58)
                    nc = N_UP if y <= 12 else N_DOWN
                rf_d.set_at((x, y), col)
                rf_n.set_at((x, y), nc)
    assets["rafflesia_flower"] = enforce_crisp_rim_normals(rf_d, rf_n)

    # 10.4 Банановое дерево с жёлтой гроздью бананов (banana_plant)
    bp_d, bp_n = make_pair(16, 20)
    for y in range(8, 19):
        for x in (7, 8):
            bp_d.set_at((x, y), (88, 128, 52) if x == 7 else (64, 96, 38))
            bp_n.set_at((x, y), N_LEFT if x == 7 else N_RIGHT)
    # Широкие тропические листья и золотая гроздь бананов
    for y in range(2, 11):
        for x in range(2, 14):
            if abs(y - (5 + abs(x - 7.5) * 0.6)) <= 1.8:
                bp_d.set_at((x, y), (78, 162, 54) if y < 6 else (52, 118, 40))
                bp_n.set_at((x, y), N_UP)
    for y in range(9, 13):
        for x in (5, 6):
            bp_d.set_at((x, y), (255, 218, 55))
            bp_n.set_at((x, y), N_UP)
    assets["banana_plant"] = enforce_crisp_rim_normals(bp_d, bp_n)

    # 10.5 Высокий глиняный термитник джунглей (termite_mound)
    tm_d2, tm_n2 = make_pair(16, 20)
    for y in range(3, 19):
        half_w = 2 if y < 6 else (3 if y < 10 else (4 if y < 15 else 5))
        for x in range(8 - half_w, 8 + half_w):
            is_hole = (x in (7, 9) and y in (8, 13)) or (x == 6 and y == 16)
            if is_hole:
                col, nc = (32, 18, 12), N_DEEP
            else:
                col = (158, 96, 54) if x < 8 else (122, 72, 38)
                nc = N_LEFT if x < 7 else (N_RIGHT if x > 8 else N_UP)
            tm_d2.set_at((x, y), col)
            tm_n2.set_at((x, y), nc)
    assets["termite_mound"] = enforce_crisp_rim_normals(tm_d2, tm_n2)

    # 10.6 Друза светящихся изумрудно-бирюзовых кристаллов пещеры (crystal_cluster)
    cc_d, cc_n = make_pair(16, 20)
    shards = [(5, 8, 18, 2), (8, 4, 18, 3), (11, 7, 18, 2)]
    for cx_s, y0, y1, hw in shards:
        for y in range(y0, y1):
            w_cur = 1 if y <= y0 + 2 else hw
            for x in range(cx_s - w_cur + 1, cx_s + w_cur):
                col = (195, 255, 245) if x < cx_s else ((75, 235, 205) if x == cx_s else (38, 158, 152))
                nc = N_LEFT if x < cx_s else (N_RIGHT if x > cx_s else N_UP)
                cc_d.set_at((x, y), col)
                cc_n.set_at((x, y), nc)
    assets["crystal_cluster"] = enforce_crisp_rim_normals(cc_d, cc_n)

    # 10.7 Острый каменный сталагмит пещеры (cave_stalagmite)
    cs_d, cs_n = make_pair(16, 20)
    for y in range(3, 19):
        hw = max(1, (y - 1) // 3)
        for x in range(8 - hw, 8 + hw):
            col = (108, 98, 94) if x < 8 else (72, 64, 62)
            if y % 4 == 0:
                col = (88, 78, 74)
            nc = N_LEFT if x < 7 else (N_RIGHT if x > 8 else N_UP)
            cs_d.set_at((x, y), col)
            cs_n.set_at((x, y), nc)
    assets["cave_stalagmite"] = enforce_crisp_rim_normals(cs_d, cs_n)

    # 10.8 Древний путевой камень со светящейся руной в лианах (ancient_waystone)
    aw_d, aw_n = make_pair(16, 20)
    for y in range(3, 19):
        hw = 3 if y < 6 else 4
        for x in range(8 - hw, 8 + hw):
            if 7 <= y <= 12 and x in (7, 8):
                col, nc = (75, 245, 195), N_UP
            elif (x + y) % 5 == 0 and y < 14:
                col, nc = (52, 118, 48), N_UP
            else:
                col = (128, 124, 118) if x < 8 else (92, 88, 84)
                nc = N_LEFT if x < 7 else (N_RIGHT if x > 8 else N_FLAT)
            aw_d.set_at((x, y), col)
            aw_n.set_at((x, y), nc)
    assets["ancient_waystone"] = enforce_crisp_rim_normals(aw_d, aw_n)

    # 10.9 Каменная голова ольмекского колосса во мху (giant_stone_head)
    gsh_d, gsh_n = make_pair(16, 20)
    for y in range(4, 19):
        for x in range(2, 14):
            if y in (4, 5) and (x + y) % 2 == 0:
                col, nc = (54, 122, 48), N_UP
            elif y == 10 and x in (4, 5, 10, 11):
                col, nc = (42, 38, 40), N_DEEP
            elif y in (14, 15) and 5 <= x <= 10:
                col, nc = (78, 74, 70), N_DOWN
            else:
                col = (124, 118, 112) if x < 8 else (92, 86, 82)
                nc = N_UP if y <= 7 else (N_LEFT if x < 5 else (N_RIGHT if x > 10 else N_FLAT))
            gsh_d.set_at((x, y), col)
            gsh_n.set_at((x, y), nc)
    assets["giant_stone_head"] = enforce_crisp_rim_normals(gsh_d, gsh_n)

    # 10.10 Сброшенная шкура гигантской анаконды (snake_shed_skin)
    ss_d, ss_n = make_pair(16, 20)
    for i in range(4, 18):
        sx = int(round(7.5 + math.sin(i * 0.55) * 3.5))
        for dx in (-1, 0, 1):
            col = (198, 192, 168) if (i + dx) % 2 == 0 else (148, 142, 120)
            ss_d.set_at((sx + dx, i), col)
            ss_n.set_at((sx + dx, i), N_UP if dx == 0 else N_FLAT)
    assets["snake_shed_skin"] = enforce_crisp_rim_normals(ss_d, ss_n)

    # =========================================================================
    # 11. ДОПОЛНИТЕЛЬНАЯ МЕБЕЛЬ И УТВАРЬ АБОРИГЕНОВ (16x20)
    # =========================================================================

    # 11.1 Котёл шамана с бурлящим изумрудным зельем и черепами (shaman_cauldron)
    sc_d, sc_n = make_pair(16, 20)
    for y in range(8, 19):
        for x in range(3, 13):
            if (x - 7.5) ** 2 + (y - 13.5) ** 2 <= 22.0:
                if y in (8, 9):
                    col, nc = (85, 245, 135) if 5 <= x <= 10 else (68, 52, 42), N_UP
                elif y == 12 and x in (5, 8, 10):
                    col, nc = (228, 218, 195), N_UP  # Черепа на ободе котла
                else:
                    col, nc = (58, 44, 36) if x < 8 else (42, 30, 24), N_LEFT if x < 7 else N_RIGHT
                sc_d.set_at((x, y), col)
                sc_n.set_at((x, y), nc)
    assets["shaman_cauldron"] = enforce_crisp_rim_normals(sc_d, sc_n)

    # 11.2 Бамбуковая сушилка с тропической рыбой (fish_drying_rack)
    fdr_d, fdr_n = make_pair(16, 20)
    for y in range(4, 19):
        for x in range(2, 14):
            if y == 5 or x in (3, 12):
                fdr_d.set_at((x, y), (128, 88, 46))
                fdr_n.set_at((x, y), N_UP if y == 5 else N_FLAT)
            elif 7 <= y <= 14 and x in (5, 6, 9, 10):
                col = (235, 125, 65) if y in (9, 10) else (165, 195, 215)
                fdr_d.set_at((x, y), col)
                fdr_n.set_at((x, y), N_UP)
    assets["fish_drying_rack"] = enforce_crisp_rim_normals(fdr_d, fdr_n)

    # 11.3 Плетёный гамак между двух бамбуковых столбов (tribal_hammock)
    th_d, th_n = make_pair(16, 20)
    for y in range(5, 19):
        for x in (2, 13):
            th_d.set_at((x, y), (118, 78, 40))
            th_n.set_at((x, y), N_UP)
    for x in range(3, 13):
        sag = int(math.sin(((x - 3) / 9.0) * math.pi) * 4.0)
        for dy in range(3):
            col = (215, 68, 52) if (x + dy) % 2 == 0 else (232, 192, 95)
            th_d.set_at((x, 9 + sag + dy), col)
            th_n.set_at((x, 9 + sag + dy), N_FLAT)
    assets["tribal_hammock"] = enforce_crisp_rim_normals(th_d, th_n)

    # 11.4 Шаманская жаровня в рогатом черепе зверя (skull_brazier)
    skb_d, skb_n = make_pair(16, 20)
    for y in range(5, 19):
        for x in range(3, 13):
            if y < 10 and math.hypot(x - 7.5, y - 8.0) <= 3.2:
                col = (255, 240, 120) if abs(x - 7.5) <= 1.0 else (245, 110, 35)
                skb_d.set_at((x, y), col)
                skb_n.set_at((x, y), N_UP)
            elif 10 <= y <= 15 and 4 <= x <= 11:
                col = (245, 95, 40) if (y == 12 and x in (6, 9)) else (228, 218, 195)
                skb_d.set_at((x, y), col)
                skb_n.set_at((x, y), N_UP)
            elif y >= 16 and x in (5, 7, 8, 10):
                skb_d.set_at((x, y), (104, 66, 36))
                skb_n.set_at((x, y), N_FLAT)
    assets["skull_brazier"] = enforce_crisp_rim_normals(skb_d, skb_n)

    # 11.5 Бамбуковая ловушка-турель с ядовитыми дротиками (blowgun_trap)
    bt_d, bt_n = make_pair(16, 20)
    for y in range(7, 19):
        for x in (6, 7, 8, 9):
            bt_d.set_at((x, y), (92, 148, 52) if y % 3 != 0 else (158, 122, 62))
            bt_n.set_at((x, y), N_LEFT if x <= 7 else N_RIGHT)
    for x in range(3, 13):
        bt_d.set_at((x, 9), (128, 86, 44))
        bt_n.set_at((x, 9), N_UP)
    bt_d.set_at((2, 9), (95, 245, 125))  # Ядовитое жало дротика
    assets["blowgun_trap"] = enforce_crisp_rim_normals(bt_d, bt_n)

    # 11.6 Запертая бамбуковая клетка (bamboo_cage)
    bcg_d, bcg_n = make_pair(16, 20)
    for y in range(5, 19):
        for x in range(3, 13):
            if y in (5, 11, 18) or x in (3, 6, 9, 12):
                col = (168, 132, 68) if y in (5, 18) else (128, 96, 48)
                bcg_d.set_at((x, y), col)
                bcg_n.set_at((x, y), N_UP if y == 5 else N_FLAT)
    assets["bamboo_cage"] = enforce_crisp_rim_normals(bcg_d, bcg_n)

    # 11.7 Плетёная корзина с манго, ананасами и папайей (fruit_basket)
    fb_d, fb_n = make_pair(16, 20)
    for y in range(9, 19):
        for x in range(3, 13):
            if y <= 12:
                col = (248, 195, 48) if (x + y) % 3 == 0 else ((235, 85, 52) if x % 2 == 0 else (78, 168, 56))
                nc = N_UP
            else:
                col = (148, 106, 54) if (x + y) % 2 == 0 else (116, 78, 38)
                nc = N_LEFT if x < 6 else (N_RIGHT if x > 9 else N_FLAT)
            fb_d.set_at((x, y), col)
            fb_n.set_at((x, y), nc)
    assets["fruit_basket"] = enforce_crisp_rim_normals(fb_d, fb_n)

    # 11.8 Охотничья стойка с луками и колчанами стрел с перьями (tribal_bow_stand)
    tbs_d, tbs_n = make_pair(16, 20)
    for y in range(4, 19):
        if y in (8, 17):
            for x in range(3, 13):
                tbs_d.set_at((x, y), (98, 62, 34))
                tbs_n.set_at((x, y), N_UP)
        bx = 5 + int(math.sin(((y - 4) / 14.0) * math.pi) * 3.0)
        tbs_d.set_at((bx, y), (148, 98, 48))
        tbs_n.set_at((bx, y), N_UP)
        tbs_d.set_at((5, y), (215, 210, 195))  # Тетива
        if x := 10:
            tbs_d.set_at((x, y), (235, 65, 55) if y <= 6 else (128, 86, 44))
            tbs_n.set_at((x, y), N_UP)
    assets["tribal_bow_stand"] = enforce_crisp_rim_normals(tbs_d, tbs_n)

    # 11.9 Большая ритуальная маска с перьями на подставке (tribal_mask_shield)
    tms_d, tms_n = make_pair(16, 20)
    for y in range(2, 19):
        for x in range(3, 13):
            if y <= 5:
                col = (52, 215, 175) if x % 2 == 0 else (235, 72, 58)
                tms_d.set_at((x, y), col)
                tms_n.set_at((x, y), N_UP)
            elif 6 <= y <= 15 and math.hypot((x - 7.5) * 0.9, (y - 10.5) * 0.85) <= 4.2:
                if y == 9 and x in (6, 9):
                    col = (255, 225, 65)
                elif y == 13 and 6 <= x <= 9:
                    col = (235, 228, 210)
                else:
                    col = (168, 52, 42) if (x + y) % 3 == 0 else (118, 74, 38)
                tms_d.set_at((x, y), col)
                tms_n.set_at((x, y), N_UP)
            elif y >= 15 and x in (7, 8):
                tms_d.set_at((x, y), (88, 54, 28))
                tms_n.set_at((x, y), N_FLAT)
    assets["tribal_mask_shield"] = enforce_crisp_rim_normals(tms_d, tms_n)

    # 11.10 Шаманский бубен на деревянной раме (shaman_gong)
    sg_d, sg_n = make_pair(16, 20)
    for y in range(3, 19):
        for x in range(2, 14):
            if y == 4 or x in (3, 12):
                sg_d.set_at((x, y), (118, 76, 40))
                sg_n.set_at((x, y), N_UP if y == 4 else N_FLAT)
            elif math.hypot(x - 7.5, y - 10.5) <= 3.8:
                d_r = math.hypot(x - 7.5, y - 10.5)
                col = (195, 58, 48) if d_r <= 1.5 else (228, 212, 178)
                sg_d.set_at((x, y), col)
                sg_n.set_at((x, y), N_FLAT)
    assets["shaman_gong"] = enforce_crisp_rim_normals(sg_d, sg_n)

    # =========================================================================
    # 12. ДОПОЛНИТЕЛЬНЫЕ ОБЪЕКТЫ МРАМОРНОГО ХРАМА (16x20)
    # =========================================================================

    # 12.1 Крылатая нефритово-золотая статуя Пернатого Змея (serpent_statue)
    sst_d, sst_n = make_pair(16, 20)
    for y in range(2, 19):
        for x in range(2, 14):
            if y >= 15 and 4 <= x <= 11:
                sst_d.set_at((x, y), (228, 222, 212) if y > 15 else (232, 188, 76))
                sst_n.set_at((x, y), N_UP if y == 15 else N_FLAT)
            elif 4 <= y <= 10 and x in (2, 3, 4, 11, 12, 13):
                sst_d.set_at((x, y), (238, 195, 78) if y % 2 == 0 else (58, 198, 142))
                sst_n.set_at((x, y), N_UP)
            elif 3 <= y <= 14 and abs(x - (7.5 + math.sin(y * 0.6) * 1.5)) <= 2.0:
                col = (245, 55, 68) if (y == 4 and x in (7, 8)) else (52, 188, 128)
                sst_d.set_at((x, y), col)
                sst_n.set_at((x, y), N_UP)
    assets["serpent_statue"] = enforce_crisp_rim_normals(sst_d, sst_n)

    # 12.2 Большой солнечный золотой гонг в мраморной арке (sun_gong)
    sng_d, sng_n = make_pair(16, 20)
    for y in range(2, 19):
        for x in range(2, 14):
            if y in (2, 3) or x in (2, 3, 12, 13):
                sng_d.set_at((x, y), (236, 230, 220) if x < 8 else (202, 196, 186))
                sng_n.set_at((x, y), N_UP if y <= 3 else N_FLAT)
            elif math.hypot(x - 7.5, y - 10.5) <= 4.2:
                d_g = math.hypot(x - 7.5, y - 10.5)
                col = (255, 240, 140) if d_g <= 1.6 else ((238, 192, 68) if d_g <= 3.2 else (188, 142, 42))
                sng_d.set_at((x, y), col)
                sng_n.set_at((x, y), N_FLAT)
    assets["sun_gong"] = enforce_crisp_rim_normals(sng_d, sng_n)

    # 12.3 Мраморная скамья с бархатной подушкой и золотом (marble_bench)
    mbn_d, mbn_n = make_pair(16, 20)
    for y in range(10, 18):
        for x in range(2, 14):
            if y in (10, 11) and 4 <= x <= 11:
                col = (48, 168, 122)  # Изумрудная подушка
            elif y in (10, 11, 12):
                col = (236, 230, 220) if y < 12 else (228, 186, 76)
            elif x in (3, 4, 11, 12):
                col = (212, 206, 196)
            else:
                continue
            mbn_d.set_at((x, y), col)
            mbn_n.set_at((x, y), N_FLAT)
    assets["marble_bench"] = enforce_crisp_rim_normals(mbn_d, mbn_n)

    # 12.4 Храмовый пюпитр с золотой скрижалью древних (marble_lectern)
    ml_d, ml_n = make_pair(16, 20)
    for y in range(4, 19):
        hw = 4 if 5 <= y <= 9 else (3 if y >= 16 else 2)
        for x in range(8 - hw, 8 + hw):
            if 5 <= y <= 9 and 5 <= x <= 10:
                col = (58, 215, 155) if (y in (6, 8) and 6 <= x <= 9) else (238, 195, 78)
            else:
                col = (236, 230, 220) if x < 8 else (202, 196, 186)
            ml_d.set_at((x, y), col)
            ml_n.set_at((x, y), N_FLAT)
    assets["marble_lectern"] = enforce_crisp_rim_normals(ml_d, ml_n)

    # 12.5 Золотая курильница с клубами лазурного благовония (incense_burner)
    ib_d, ib_n = make_pair(16, 20)
    for y in range(3, 19):
        if y <= 8:
            sx = int(round(7.5 + math.sin(y * 0.9) * 1.6))
            ib_d.set_at((sx, y), (165, 235, 245))
            ib_n.set_at((sx, y), N_UP)
        else:
            hw = 4 if 9 <= y <= 12 else (2 if y < 17 else 3)
            for x in range(8 - hw, 8 + hw):
                col = (58, 198, 145) if y == 10 else ((242, 198, 82) if x < 8 else (192, 148, 48))
                ib_d.set_at((x, y), col)
                ib_n.set_at((x, y), N_UP if y <= 10 else N_FLAT)
    assets["incense_burner"] = enforce_crisp_rim_normals(ib_d, ib_n)

    # 12.6 Белокаменный обелиск со светящимися иероглифами (marble_obelisk)
    mo_d2, mo_n2 = make_pair(16, 20)
    for y in range(1, 19):
        hw = 1 if y <= 2 else (2 if y <= 4 else (4 if y >= 17 else 3))
        for x in range(8 - hw, 8 + hw):
            if y <= 3:
                col, nc = (245, 202, 82), N_UP  # Золотой пирамидион наверху
            elif x in (7, 8) and y in (6, 8, 10, 12, 14):
                col, nc = (68, 245, 185), N_UP  # Светящиеся нефритовые глифы
            else:
                col = (238, 232, 222) if x < 8 else (198, 192, 182)
                nc = N_LEFT if x < 7 else (N_RIGHT if x > 8 else N_FLAT)
            mo_d2.set_at((x, y), col)
            mo_n2.set_at((x, y), nc)
    assets["marble_obelisk"] = enforce_crisp_rim_normals(mo_d2, mo_n2)

    # 12.7 Ковчег-сундук из белого мрамора, золота и изумрудов (marble_chest)
    mch_d, mch_n = make_pair(16, 20)
    for y in range(8, 19):
        for x in range(2, 14):
            if x in (2, 13) or y in (8, 12, 18):
                col = (238, 195, 78)
            elif 7 <= x <= 8 and 11 <= y <= 13:
                col = (55, 235, 155)
            else:
                col = (236, 230, 220) if y < 12 else (208, 202, 192)
            mch_d.set_at((x, y), col)
            mch_n.set_at((x, y), N_FLAT)
    assets["marble_chest"] = enforce_crisp_rim_normals(mch_d, mch_n)

    # 12.8 Астрономические солнечные часы храма (temple_sundial)
    tsd_d, tsd_n = make_pair(16, 20)
    for y in range(6, 19):
        for x in range(3, 13):
            if y <= 12 and math.hypot((x - 7.5) * 0.9, (y - 9.5) * 1.1) <= 4.2:
                is_gnomon = (x == 7 and 6 <= y <= 9)
                col = (245, 202, 82) if is_gnomon else (236, 230, 220)
                tsd_d.set_at((x, y), col)
                tsd_n.set_at((x, y), N_FLAT)
            elif y > 12 and (5 <= x <= 10 or y >= 17):
                tsd_d.set_at((x, y), (212, 206, 196))
                tsd_n.set_at((x, y), N_FLAT)
    assets["temple_sundial"] = enforce_crisp_rim_normals(tsd_d, tsd_n)

    # 12.9 Чаша со священным изумрудно-золотым пламенем (holy_fire_bowl)
    hfb_d, hfb_n = make_pair(16, 20)
    for y in range(4, 19):
        for x in range(3, 13):
            if y <= 11 and math.hypot(x - 7.5, y - 8.5) <= 4.0:
                col = (235, 255, 220) if abs(x - 7.5) <= 1.2 and y >= 7 else ((75, 245, 155) if (x + y) % 2 == 0 else (245, 205, 75))
                hfb_d.set_at((x, y), col)
                hfb_n.set_at((x, y), N_UP)
            elif 12 <= y <= 15 and 4 <= x <= 11:
                hfb_d.set_at((x, y), (238, 195, 78) if y == 12 else (232, 226, 216))
                hfb_n.set_at((x, y), N_UP)
            elif y >= 16 and 5 <= x <= 10:
                hfb_d.set_at((x, y), (198, 192, 182))
                hfb_n.set_at((x, y), N_FLAT)
    assets["holy_fire_bowl"] = enforce_crisp_rim_normals(hfb_d, hfb_n)

    # 12.10 Поверженный мраморный колосс в зарослях (fallen_colossus)
    fc_d, fc_n = make_pair(16, 20)
    for y in range(9, 19):
        for x in range(1, 15):
            if math.hypot((x - 7.5) * 0.75, (y - 14.0) * 1.1) <= 5.2:
                if (x + y) % 5 == 0 and y <= 13:
                    col, nc = (54, 124, 48), N_UP
                elif x in (5, 9) and y == 13:
                    col, nc = (228, 186, 76), N_UP
                else:
                    col = (234, 228, 218) if y <= 13 else (192, 186, 176)
                    nc = N_UP if y <= 13 else N_DOWN
                fc_d.set_at((x, y), col)
                fc_n.set_at((x, y), nc)
    assets["fallen_colossus"] = enforce_crisp_rim_normals(fc_d, fc_n)


def _register_bone_jungle_and_caves(assets):
    # =========================================================================
    # 13. КОСТЯНЫЕ ДЖУНГЛИ И ГЛУБОКИЕ ПЕЩЕРЫ: ПОЛЫ, ЖИДКОСТИ, СТЕНЫ, ДЕРЕВЬЯ
    # =========================================================================
    tau_b = 2.0 * math.pi / 16.0

    # 13.1 Кипящая смоляная яма (floor_tar_pit, 3 кадра анимации)
    tar_frames = []
    for fi in range(3):
        ph = fi * (2.0 * math.pi / 3.0)
        td, tn = make_pair(16, 16, opaque=True)
        for y in range(16):
            for x in range(16):
                w1 = math.sin(x * tau_b + y * tau_b + ph)
                w2 = math.cos(x * tau_b - y * tau_b + ph)
                wv = (w1 + w2) * 0.5
                v_c = int(18 + (wv + 1.0) * 10)
                col = (v_c, v_c - 2, v_c + 4, 255)
                nc = N_UP if w1 > 0.45 else (N_DOWN if w1 < -0.45 else N_FLAT)
                # Вязкие смоляные пузыри с фиолетовым нефтяным бликом
                b_x = 5 if fi != 2 else 6
                b_y = 6 if fi != 1 else 5
                if math.hypot(x - b_x, y - b_y) <= (1.2 + fi * 0.4) or math.hypot(x - 11, y - 11) <= (2.0 - fi * 0.4):
                    col = (68, 58, 82, 255) if (x + y) % 2 == 0 else (38, 34, 48, 255)
                    nc = N_UP
                td.set_at((x, y), col)
                tn.set_at((x, y), nc)
        tar_frames.append((td, tn))
    assets["floor_tar_pit"] = tar_frames[0]
    assets["_tar_pit_frames"] = tar_frames

    # 13.2 Кислотная пещерная лужа (floor_acid_pool, 3 кадра анимации)
    acid_frames = []
    for fi in range(3):
        ph = fi * (2.0 * math.pi / 3.0)
        ad, an = make_pair(16, 16, opaque=True)
        for y in range(16):
            for x in range(16):
                w1 = math.sin(x * tau_b + y * tau_b + ph)
                w2 = math.cos(x * tau_b - y * tau_b * 2.0 - ph)
                wv = (w1 + w2) * 0.5
                cr = int(42 + (wv + 1.0) * 28)
                cg = int(135 + (wv + 1.0) * 48)
                cb = int(28 + (wv + 1.0) * 18)
                if wv > 0.58:
                    cr, cg, cb = 195, 255, 110
                nc = N_UP if w1 > 0.35 else (N_DOWN if w1 < -0.35 else N_FLAT)
                ad.set_at((x, y), (cr, cg, cb, 255))
                an.set_at((x, y), nc)
        acid_frames.append((ad, an))
    assets["floor_acid_pool"] = acid_frames[0]
    assets["_acid_pool_frames"] = acid_frames

    # 13.3 Мёртвая трава костяных джунглей с осколками костей и багровой росой (floor_bone_grass)
    bg_d, bg_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            h = ((x * 73 + y * 139 + x * y * 19) % 29)
            if h in (0, 1):
                col, nc = (195, 186, 162, 255), N_FLAT  # Осколок белой кости в траве
            elif h == 2:
                col, nc = (158, 38, 48, 255), N_FLAT    # Капля багровой смолы/крови
            elif h in (3, 4, 5):
                col, nc = (28, 30, 26, 255), N_DEEP
            else:
                sh = (h % 4) * 3
                col, nc = (48 + sh, 54 + sh, 42 + sh, 255), N_FLAT
            bg_d.set_at((x, y), col)
            bg_n.set_at((x, y), nc)
    assets["floor_bone_grass"] = (bg_d, bg_n)

    # 13.4 Утоптанная костяная крошка и черепа (floor_bone_grave)
    bgr_d, bgr_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            h = ((x * 61 + y * 107 + (x ^ y) * 23) % 23)
            if h in (0, 1, 2):
                col, nc = (212, 202, 178, 255), N_FLAT
            elif h in (3, 4, 5):
                col, nc = (168, 156, 134, 255), N_FLAT
            elif h in (6, 7):
                col, nc = (42, 34, 32, 255), N_DEEP
            else:
                sh = (h % 4) * 3
                col, nc = (86 + sh, 76 + sh, 66 + sh, 255), N_FLAT
            bgr_d.set_at((x, y), col)
            bgr_n.set_at((x, y), nc)
    assets["floor_bone_grave"] = (bgr_d, bgr_n)

    # 13.5 Кроваво-бурая трясина костяных джунглей (floor_blood_marsh)
    bm_d, bm_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            h = ((x * 89 + y * 131 + x * y * 13) % 25)
            if (x - 6) ** 2 + (y - 7) ** 2 <= 3.2:
                col, nc = (148, 28, 38, 255), N_FLAT
            elif h in (0, 1):
                col, nc = (185, 42, 52, 255), N_FLAT
            elif h in (2, 3, 4):
                col, nc = (34, 18, 22, 255), N_DEEP
            else:
                sh = (h % 4) * 2
                col, nc = (56 + sh, 28 + sh, 30 + sh, 255), N_FLAT
            bm_d.set_at((x, y), col)
            bm_n.set_at((x, y), nc)
    assets["floor_blood_marsh"] = (bm_d, bm_n)

    # 13.6 Мостки из связанных позвоночников и бедренных костей (floor_bone_bridge)
    bb_d, bb_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        bone_row = y % 4
        for x in range(16):
            if bone_row == 0:
                bb_d.set_at((x, y), (26, 20, 24, 255))
                bb_n.set_at((x, y), N_DEEP)
            elif x in (2, 13):
                # Жилы и кожаные ремни, стягивающие кости
                bb_d.set_at((x, y), (138, 38, 44, 255))
                bb_n.set_at((x, y), N_FLAT)
            else:
                is_joint = x in (0, 1, 7, 8, 14, 15)
                if bone_row == 1:
                    col = (228, 220, 198, 255) if is_joint else (208, 198, 175, 255)
                elif bone_row == 2:
                    col = (195, 185, 162, 255)
                else:
                    col = (148, 138, 118, 255)
                bb_d.set_at((x, y), col)
                bb_n.set_at((x, y), N_FLAT)
    assets["floor_bone_bridge"] = (bb_d, bb_n)

    # 13.7 Пещерный пол, заросший биолюминесцентным фиолетовым мицелием (floor_cave_fungus)
    cf_d, cf_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            h = ((x * 79 + y * 127 + (x ^ y) * 31) % 27)
            vein = ((x + y * 2) % 9 == 0) or ((x * 2 - y) % 11 == 0)
            if vein:
                col, nc = (138, 72, 215, 255), N_FLAT
            elif h == 0:
                col, nc = (195, 135, 255, 255), N_FLAT
            elif h in (1, 2, 3):
                col, nc = (28, 22, 38, 255), N_DEEP
            else:
                sh = (h % 4) * 2
                col, nc = (44 + sh, 36 + sh, 58 + sh, 255), N_FLAT
            cf_d.set_at((x, y), col)
            cf_n.set_at((x, y), nc)
    assets["floor_cave_fungus"] = (cf_d, cf_n)

    # 13.8 Острый колотый обсидиановый пол глубокой пещеры (floor_cave_obsidian)
    co_d, co_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            shard = ((x * 3 + y * 5) % 14 == 0)
            glint = ((x - y * 2) % 17 == 0)
            if shard:
                col, nc = (18, 14, 26, 255), N_DEEP
            elif glint:
                col, nc = (92, 78, 128, 255), N_FLAT
            else:
                sh = ((x * 19 + y * 37) % 5) - 2
                col, nc = (34 + sh, 30 + sh, 46 + sh, 255), N_FLAT
            co_d.set_at((x, y), col)
            co_n.set_at((x, y), nc)
    assets["floor_cave_obsidian"] = (co_d, co_n)

    # 13.9 Стена из гигантских переплетённых рёбер и багровых жил (wall_bone_ribs)
    wbr_d, wbr_n = make_pair(16, 16, opaque=True)
    wbr_d.fill((48, 20, 26, 255))
    wbr_n.fill(N_DEEP)
    for y in range(16):
        for x in range(16):
            # Центральный вертикальный позвоночный столб
            if 6 <= x <= 9:
                is_disc = (y % 4 == 0)
                col = (128, 34, 42, 255) if is_disc else ((228, 218, 195, 255) if x in (7, 8) else (175, 164, 142, 255))
                nc = N_DEEP if is_disc else (N_LEFT if x == 6 else (N_RIGHT if x == 9 else N_UP))
                wbr_d.set_at((x, y), col)
                wbr_n.set_at((x, y), nc)
            # Дуги массивных рёбер по бокам
            rib_y = (y + int(abs(x - 7.5) * 0.45)) % 4
            if rib_y in (1, 2):
                col = (232, 224, 202, 255) if rib_y == 1 else (178, 168, 145, 255)
                nc = N_UP if rib_y == 1 else N_DOWN
                wbr_d.set_at((x, y), col)
                wbr_n.set_at((x, y), nc)
    assets["wall_bone_ribs"] = (wbr_d, wbr_n)

    # 13.10 Стена-оссуарий, сложенная из черепов и тёмного камня (wall_skull_catacomb)
    wsc_d, wsc_n = make_pair(16, 16, opaque=True)
    wsc_d.fill((28, 22, 26, 255))
    wsc_n.fill(N_DEEP)
    skulls = [(1, 1), (6, 1), (11, 1), (3, 6), (9, 6), (1, 11), (6, 11), (11, 11)]
    for sx, sy in skulls:
        for dy in range(4):
            for dx in range(4):
                if dy == 3 and dx in (0, 3):
                    continue
                is_socket = (dy == 2 and dx in (1, 2))
                if is_socket:
                    col, nc = (32, 20, 24, 255), N_DEEP
                elif dy == 0:
                    col, nc = (228, 218, 195, 255), N_UP
                else:
                    col = (205, 195, 172, 255) if dx < 2 else (168, 158, 136, 255)
                    nc = N_LEFT if dx == 0 else (N_RIGHT if dx == 3 else N_FLAT)
                wsc_d.set_at((sx + dx, sy + dy), col)
                wsc_n.set_at((sx + dx, sy + dy), nc)
    assets["wall_skull_catacomb"] = (wsc_d, wsc_n)

    # 13.11 Сгнивший чёрный частокол в кровавых шипастых лозах (wall_corrupted_wood)
    wcw_d, wcw_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            px_mod = x % 4
            if px_mod == 0:
                wcw_d.set_at((x, y), (22, 16, 20, 255))
                wcw_n.set_at((x, y), N_DEEP)
            else:
                col = (68, 56, 58, 255) if px_mod == 1 else ((54, 44, 46, 255) if px_mod == 2 else (40, 32, 34, 255))
                nc = N_LEFT if px_mod == 1 else (N_RIGHT if px_mod == 3 else N_FLAT)
                wcw_d.set_at((x, y), col)
                wcw_n.set_at((x, y), nc)
    # Диагональные пульсирующие кровавые лозы с шипами
    for i in range(16):
        vy1 = (i + 3) % 16
        vy2 = (15 - i) % 16
        for vx, vy in ((i, vy1), (i, vy2)):
            wcw_d.set_at((vx, vy), (195, 34, 48, 255))
            wcw_n.set_at((vx, vy), N_UP)
            if (vx + vy) % 3 == 0 and vy > 0:
                wcw_d.set_at((vx, vy - 1), (238, 185, 175, 255))  # Белый костяной шип
    assets["wall_corrupted_wood"] = (wcw_d, wcw_n)

    # 13.12 Скальная стена пещеры, затянутая густой паутиной (wall_cave_web)
    wcwb_d = assets["wall_cave"][0].copy()
    wcwb_n = assets["wall_cave"][1].copy()
    for y in range(16):
        for x in range(16):
            if (x + y in (5, 9, 13, 18, 22)) or (x - y in (-9, -4, 4, 9)):
                wcwb_d.set_at((x, y), (215, 220, 230, 255) if (x + y) % 2 == 0 else (162, 168, 180, 255))
                wcwb_n.set_at((x, y), N_UP)
    assets["wall_cave_web"] = (wcwb_d, wcwb_n)

    # 13.13 Базальтовая стена пещеры с раскалёнными лавовыми трещинами (wall_cave_magma)
    wcm_d = assets["wall_cave"][0].copy()
    wcm_n = assets["wall_cave"][1].copy()
    for y in range(16):
        for x in range(16):
            r, g, b, _ = wcm_d.get_at((x, y))
            wcm_d.set_at((x, y), (max(18, r - 18), max(16, g - 16), max(20, b - 10), 255))
    magma_px = [(2, 3), (3, 4), (4, 5), (5, 5), (6, 6), (7, 7), (8, 8), (9, 9), (10, 11), (11, 12), (12, 13), (6, 8), (5, 10), (4, 12)]
    for mx_p, my_p in magma_px:
        wcm_d.set_at((mx_p, my_p), (255, 215, 70, 255) if (mx_p + my_p) % 2 == 0 else (245, 95, 30, 255))
        wcm_n.set_at((mx_p, my_p), N_UP)
    assets["wall_cave_magma"] = (wcm_d, wcm_n)

    # 13.14 Высокое костяное дерево с черепами и багровой листвой (tall_bone_tree 24x38 + tree_bone 16x16)
    bt_d, bt_n = make_pair(24, 38)
    for y in range(3, 38):
        for x in range(2, 22):
            # Ствол из сросшихся белых позвонков и костей (y=18..37)
            spread = max(0, (y - 30) // 2)
            if y >= 18 and (9 - spread <= x <= 14 + spread):
                is_joint = (y % 3 == 0)
                col = (148, 136, 116) if is_joint else ((228, 220, 198) if x < 12 else (188, 178, 155))
                nc = N_DOWN if is_joint else (N_LEFT if x < 11 else (N_RIGHT if x > 12 else N_FLAT))
                bt_d.set_at((x, y), col)
                bt_n.set_at((x, y), nc)
            # Крона из костяных ветвей-фаланг и багровых шипов (y=3..22)
            if y <= 22:
                d_c = math.hypot((x - 11.5) * 0.85, (y - 12.0) * 1.05)
                if d_c <= 8.8:
                    is_bone_branch = (abs((x - 11.5) - (y - 14)) <= 1.2) or (abs((11.5 - x) - (y - 14)) <= 1.2)
                    if is_bone_branch and y >= 9:
                        col, nc = (228, 220, 198), N_UP
                    elif (x * 5 + y * 7) % 3 != 0:
                        col = (195, 38, 52) if y < 11 else ((138, 24, 36) if y < 17 else (82, 16, 26))
                        nc = N_UP if y < 11 else N_DOWN
                    else:
                        continue
                    bt_d.set_at((x, y), col)
                    bt_n.set_at((x, y), nc)
    # Подвешенные на ветвях черепа со светящимися зелёными глазами
    for sk_x, sk_y in ((6, 20), (17, 19)):
        for dy in range(3):
            for dx in range(-1, 2):
                bt_d.set_at((sk_x + dx, sk_y + dy), (225, 215, 192))
                bt_n.set_at((sk_x + dx, sk_y + dy), N_UP)
        bt_d.set_at((sk_x - 1, sk_y + 1), (95, 255, 135))
        bt_d.set_at((sk_x + 1, sk_y + 1), (95, 255, 135))
    assets["tall_bone_tree"] = bt_d, bt_n

    bti_d, bti_n = make_pair(16, 16)
    for y in range(2, 15):
        for x in range(2, 14):
            if y >= 9 and 6 <= x <= 9:
                bti_d.set_at((x, y), (222, 212, 190) if x <= 7 else (178, 168, 146))
                bti_n.set_at((x, y), N_LEFT if x <= 7 else N_RIGHT)
            elif math.hypot(x - 7.5, y - 6.5) <= 5.2:
                bti_d.set_at((x, y), (195, 38, 52) if (x + y) % 2 == 0 else (225, 215, 192))
                bti_n.set_at((x, y), N_UP)
    assets["tree_bone"] = (bti_d, bti_n)

    # 13.15 Высокий мёртвый пепельный мангр в паутине и кровавых лозах (tall_dead_mangrove 24x38 + tree_dead_mangrove 16x16)
    dm_d, dm_n = make_pair(24, 38)
    # Корни-ходули у основания (y=26..37)
    for r_dir in (-1.0, -0.45, 0.45, 1.0):
        for y in range(26, 37):
            rx = int(round(11.5 + r_dir * ((y - 25) * 0.65)))
            for dx in (0, 1):
                if 2 <= rx + dx < 22:
                    dm_d.set_at((rx + dx, y), (78, 66, 72) if dx == 0 else (52, 42, 48))
                    dm_n.set_at((rx + dx, y), N_LEFT if dx == 0 else N_RIGHT)
    # Искорёженный ствол и сухие корявые ветви с паутиной (y=4..27)
    for y in range(14, 28):
        for x in range(9, 15):
            dm_d.set_at((x, y), (82, 70, 76) if x < 12 else (56, 46, 52))
            dm_n.set_at((x, y), N_LEFT if x < 11 else N_RIGHT)
    branches = [(-0.9, 6), (-0.5, 4), (0.0, 3), (0.5, 4), (0.9, 6)]
    for b_dir, top_y in branches:
        for y in range(top_y, 17):
            bx = int(round(11.5 + b_dir * (17 - y) * 0.75))
            for dx in (-1, 0, 1):
                if 1 <= bx + dx < 23:
                    col = (195, 200, 212) if (y + dx) % 4 == 0 else (74, 62, 68)
                    dm_d.set_at((bx + dx, y), col)
                    dm_n.set_at((bx + dx, y), N_UP)
    # Свисающие кровавые лозы
    for lx in (5, 9, 14, 18):
        for ly in range(12, 26):
            if (lx + ly) % 2 == 0:
                dm_d.set_at((lx, ly), (185, 34, 48))
                dm_n.set_at((lx, ly), N_UP)
    assets["tall_dead_mangrove"] = (dm_d, dm_n)

    dmi_d, dmi_n = make_pair(16, 16)
    for y in range(2, 15):
        for x in range(3, 13):
            if (6 <= x <= 9 and y >= 7) or abs(x - 7.5) == (10 - y):
                dmi_d.set_at((x, y), (82, 70, 76))
                dmi_n.set_at((x, y), N_UP)
    assets["tree_dead_mangrove"] = (dmi_d, dmi_n)

    # =========================================================================
    # 14. ОВЕРЛЕИ КОСТЯНЫХ ДЖУНГЛЕЙ И ГЛУБОКИХ ПЕЩЕР (16x16, opaque=False)
    # =========================================================================

    # 14.1 Полузасыпанная грудная клетка скелета (ov_ribcage_remains)
    orr_d, orr_n = make_pair(16, 16, opaque=False)
    for y in range(3, 13):
        orr_d.set_at((7, y), (205, 195, 172, 240))
        orr_n.set_at((7, y), N_FLAT)
        if y % 2 == 0:
            for x in range(4, 12):
                orr_d.set_at((x, y), (225, 215, 192, 240))
                orr_n.set_at((x, y), N_FLAT)
    assets["ov_ribcage_remains"] = (orr_d, orr_n)

    # 14.2 Ползучие кровавые шипастые лозы (ov_blood_vines)
    obv_d, obv_n = make_pair(16, 16, opaque=False)
    for i in range(2, 14):
        vy = int(round(7.5 + math.sin(i * 0.65) * 3.5))
        obv_d.set_at((i, vy), (185, 28, 42, 235))
        obv_n.set_at((i, vy), N_FLAT)
        if i % 3 == 0:
            obv_d.set_at((i, max(1, vy - 1)), (235, 225, 205, 245))
            obv_n.set_at((i, max(1, vy - 1)), N_FLAT)
    assets["ov_blood_vines"] = (obv_d, obv_n)

    # 14.3 Густая напольная паутина (ov_spider_web)
    osw_d, osw_n = make_pair(16, 16, opaque=False)
    for y in range(2, 14):
        for x in range(2, 14):
            d = math.hypot(x - 7.5, y - 7.5)
            if d <= 5.8 and (x == 7 or y == 7 or abs(x - y) <= 0 or abs(x + y - 15) <= 0 or int(d) in (3, 5)):
                osw_d.set_at((x, y), (215, 222, 232, 185))
                osw_n.set_at((x, y), N_FLAT)
    assets["ov_spider_web"] = (osw_d, osw_n)

    # 14.4 Пещерный гуано и мелкие косточки под гнездом нетопырей (ov_guano_droppings)
    ogd_d, ogd_n = make_pair(16, 16, opaque=False)
    for gx, gy, r_g in ((5.5, 6.0, 2.5), (10.5, 10.5, 3.0), (10.0, 5.0, 1.8)):
        for y in range(16):
            for x in range(16):
                if math.hypot(x - gx, y - gy) <= r_g:
                    col = (218, 212, 195, 215) if (x + y) % 3 == 0 else (128, 118, 108, 195)
                    ogd_d.set_at((x, y), col)
                    ogd_n.set_at((x, y), N_FLAT)
    assets["ov_guano_droppings"] = (ogd_d, ogd_n)

    # 14.5 Жёлто-зелёные серные трещины в полу пещеры (ov_sulfur_cracks)
    osc_d, osc_n = make_pair(16, 16, opaque=False)
    s_px = [(2, 4), (3, 5), (4, 6), (5, 6), (6, 7), (7, 8), (8, 8), (9, 9), (10, 10), (11, 12), (7, 9), (6, 11)]
    for cx_p, cy_p in s_px:
        osc_d.set_at((cx_p, cy_p), (225, 215, 55, 235))
        osc_n.set_at((cx_p, cy_p), N_DEEP)
        if cx_p + 1 < 15:
            osc_d.set_at((cx_p + 1, cy_p), (118, 158, 42, 195))
            osc_n.set_at((cx_p + 1, cy_p), N_FLAT)
    assets["ov_sulfur_cracks"] = (osc_d, osc_n)

    # 14.6 Костяные шипы, пробивающиеся сквозь землю (ov_bone_spikes_floor)
    obs_d, obs_n = make_pair(16, 16, opaque=False)
    for sx, sy in ((4, 6), (11, 5), (6, 12), (12, 11)):
        for dy in range(3):
            obs_d.set_at((sx, sy - dy), (235, 228, 210, 245) if dy == 2 else (178, 168, 146, 235))
            obs_n.set_at((sx, sy - dy), N_FLAT)
        obs_d.set_at((sx - 1, sy), (128, 32, 38, 215))
        obs_d.set_at((sx + 1, sy), (128, 32, 38, 215))
    assets["ov_bone_spikes_floor"] = (obs_d, obs_n)

    # 14.7 Багрово-фиолетовые споры некротической плесени (ov_corrupted_spores)
    ocs_d, ocs_n = make_pair(16, 16, opaque=False)
    for sx, sy in ((4, 4), (10, 5), (6, 10), (11, 11), (8, 7)):
        for dx, dy in ((0, 0), (1, 0), (0, 1), (-1, 0)):
            ocs_d.set_at((sx + dx, sy + dy), (128, 36, 82, 210))
            ocs_n.set_at((sx + dx, sy + dy), N_FLAT)
        ocs_d.set_at((sx, sy), (235, 75, 135, 245))
    assets["ov_corrupted_spores"] = (ocs_d, ocs_n)

    # 14.8 Расколотые черепа и челюсти на земле (ov_shattered_skulls)
    ossk_d, ossk_n = make_pair(16, 16, opaque=False)
    for sx, sy in ((3, 4), (9, 9)):
        for dy in range(4):
            for dx in range(4):
                if (dx, dy) in ((1, 2), (3, 2)):
                    col = (28, 22, 26, 235)
                else:
                    col = (218, 208, 185, 240)
                ossk_d.set_at((sx + dx, sy + dy), col)
                ossk_n.set_at((sx + dx, sy + dy), N_FLAT)
    assets["ov_shattered_skulls"] = (ossk_d, ossk_n)

    # =========================================================================
    # 15. ПРОПСЫ КОСТЯНЫХ ДЖУНГЛЕЙ (16x20 и 32x20)
    # =========================================================================

    # 15.1 Костяной тотем-алтарь из трёх рогатых черепов с кровавыми свечами (bone_totem_altar)
    bta_d, bta_n = make_pair(16, 20)
    for y in range(2, 19):
        for x in range(3, 13):
            if y in (4, 10, 15) and x in (3, 4, 11, 12):
                bta_d.set_at((x, y), (168, 156, 134))
                bta_n.set_at((x, y), N_UP)
            elif 5 <= x <= 10:
                if y in (5, 11, 16) and x in (6, 9):
                    col, nc = (245, 55, 65), N_UP
                elif y in (2, 3) and x in (6, 9):
                    col, nc = (255, 215, 75), N_UP  # Пламя свечей на макушке
                else:
                    col = (228, 218, 195) if x < 8 else (182, 172, 148)
                    nc = N_LEFT if x == 5 else (N_RIGHT if x == 10 else N_FLAT)
                bta_d.set_at((x, y), col)
                bta_n.set_at((x, y), nc)
    assets["bone_totem_altar"] = enforce_crisp_rim_normals(bta_d, bta_n)

    # 15.2 Гигантская арка из рёбер древнего левиафана (leviathan_rib_arch, 32x20 — 2x1 тайла!)
    lra_d, lra_n = make_pair(32, 20)
    for x in range(2, 30):
        arch_y = int(round(3.0 + ((x - 15.5) / 13.5) ** 2 * 15.0))
        for rib_off in (-3, 0, 3):
            rx = x + rib_off
            if 1 <= rx < 31 and 1 <= arch_y < 19:
                for dy in range(3):
                    if arch_y + dy < 19:
                        col = (232, 224, 202) if dy == 0 else ((195, 185, 162) if dy == 1 else (142, 132, 112))
                        nc = N_UP if dy == 0 else (N_LEFT if rx < 16 else N_RIGHT)
                        lra_d.set_at((rx, arch_y + dy), col)
                        lra_n.set_at((rx, arch_y + dy), nc)
    assets["leviathan_rib_arch"] = enforce_crisp_rim_normals(lra_d, lra_n)

    # 15.3 Огромный череп доисторического зверя с некро-огнём в пасти (giant_beast_skull, 32x20 — 2x1 тайла!)
    gbs_d, gbs_n = make_pair(32, 20)
    for y in range(3, 19):
        for x in range(2, 30):
            # Изогнутые саблезубые бивни по бокам
            if 6 <= y <= 17 and x in (2, 3, 4, 27, 28, 29):
                gbs_d.set_at((x, y), (242, 236, 218) if y < 12 else (195, 185, 162))
                gbs_n.set_at((x, y), N_UP)
            elif math.hypot((x - 15.5) * 0.72, (y - 11.0) * 1.05) <= 8.2:
                # Огромные глазницы со светящимся некро-зелёным огнём
                if 8 <= y <= 11 and (9 <= x <= 12 or 19 <= x <= 22):
                    col = (115, 255, 135) if (x + y) % 2 == 0 else (38, 128, 62)
                    nc = N_DEEP
                # Зубастая пасть внизу
                elif y >= 15 and 9 <= x <= 22:
                    col = (245, 240, 225) if x % 2 == 0 else (42, 24, 30)
                    nc = N_UP if x % 2 == 0 else N_DEEP
                else:
                    col = (232, 224, 202) if y <= 8 else ((205, 195, 172) if x < 16 else (168, 158, 136))
                    nc = N_UP if y <= 8 else (N_LEFT if x < 13 else (N_RIGHT if x > 18 else N_FLAT))
                gbs_d.set_at((x, y), col)
                gbs_n.set_at((x, y), nc)
    assets["giant_beast_skull"] = enforce_crisp_rim_normals(gbs_d, gbs_n)

    # 15.4 Колонна из сросшихся позвонков гиганта (spine_pillar)
    sp_d, sp_n = make_pair(16, 20)
    for y in range(1, 19):
        is_vertebra = (y % 3 != 0)
        hw = 5 if is_vertebra else 3
        for x in range(8 - hw, 8 + hw):
            if not is_vertebra:
                col, nc = (148, 36, 46), N_DEEP
            else:
                col = (232, 224, 202) if x < 8 else (188, 178, 155)
                nc = N_LEFT if x < 6 else (N_RIGHT if x > 9 else N_UP)
            sp_d.set_at((x, y), col)
            sp_n.set_at((x, y), nc)
    assets["spine_pillar"] = enforce_crisp_rim_normals(sp_d, sp_n)

    # 15.5 Трон костяного шамана из черепов и рёбер (bone_throne)
    bth_d, bth_n = make_pair(16, 20)
    for y in range(2, 19):
        hw = 4 if y < 11 else 6
        for x in range(8 - hw, 8 + hw):
            if 11 <= y <= 14 and 5 <= x <= 10:
                col, nc = (168, 32, 44), N_FLAT  # Багровая шкура на сиденье
            elif y == 4 and x in (6, 9):
                col, nc = (245, 65, 65), N_UP
            else:
                col = (228, 218, 195) if (x + y) % 2 == 0 else (182, 172, 148)
                nc = N_UP if y <= 5 else N_FLAT
            bth_d.set_at((x, y), col)
            bth_n.set_at((x, y), nc)
    assets["bone_throne"] = enforce_crisp_rim_normals(bth_d, bth_n)

    # 15.6 Подвесная клетка из рёбер на костяной балке (bone_cage_hanging)
    bch_d, bch_n = make_pair(16, 20)
    for x in range(3, 13):
        bch_d.set_at((x, 2), (168, 156, 134))
        bch_n.set_at((x, 2), N_UP)
    for y in range(6, 18):
        for x in range(4, 12):
            if y in (6, 17) or x in (4, 6, 9, 11):
                bch_d.set_at((x, y), (225, 215, 192))
                bch_n.set_at((x, y), N_UP if y == 6 else N_FLAT)
    bch_d.set_at((7, 4), (145, 135, 115))
    bch_d.set_at((7, 5), (145, 135, 115))
    assets["bone_cage_hanging"] = enforce_crisp_rim_normals(bch_d, bch_n)

    # 15.7 Куст кровавого терновника с белыми костяными шипами (blood_thorn_bush)
    btb_d, btb_n = make_pair(16, 20)
    for y in range(6, 19):
        for x in range(1, 15):
            if math.hypot((x - 7.5) * 0.9, (y - 13.0) * 1.05) <= 6.0:
                sh = (x * 3 + y * 5) % 5
                if sh == 0:
                    col, nc = (238, 230, 210), N_UP  # Острый костяной шип
                elif sh == 1:
                    col, nc = (235, 48, 62), N_UP    # Кровавый бутон
                else:
                    col, nc = (92, 22, 32) if y < 13 else (54, 14, 22), N_FLAT
                btb_d.set_at((x, y), col)
                btb_n.set_at((x, y), nc)
    assets["blood_thorn_bush"] = enforce_crisp_rim_normals(btb_d, btb_n)

    # 15.8 Плотоядный гигантский кувшиночник с кислотой и костью внутри (corpse_pitcher_plant)
    cpp_d, cpp_n = make_pair(16, 20)
    for y in range(5, 19):
        hw = 4 if y in (6, 7) else (3 if y < 11 else 5)
        for x in range(8 - hw, 8 + hw):
            if y in (6, 7) and 5 <= x <= 10:
                col, nc = (135, 255, 85), N_UP  # Кислотный пищеварительный сок внутри
            elif y in (3, 4, 5) and x in (7, 8):
                col, nc = (235, 228, 210), N_UP  # Торчащая из кувшина кость жертвы
            else:
                vein = (x + y) % 3 == 0
                col = (168, 38, 62) if vein else (68, 118, 48)
                nc = N_LEFT if x < 7 else (N_RIGHT if x > 8 else N_FLAT)
            cpp_d.set_at((x, y), col)
            cpp_n.set_at((x, y), nc)
    assets["corpse_pitcher_plant"] = enforce_crisp_rim_normals(cpp_d, cpp_n)

    # 15.9 Скелет на скрещённых костяных пиках (impaled_skeleton)
    is_d, is_n = make_pair(16, 20)
    for i in range(2, 19):
        sx1 = max(2, min(13, 3 + (i - 2) // 2))
        sx2 = max(2, min(13, 12 - (i - 2) // 2))
        is_d.set_at((sx1, i), (142, 96, 52))
        is_n.set_at((sx1, i), N_UP)
        is_d.set_at((sx2, i), (142, 96, 52))
        is_n.set_at((sx2, i), N_UP)
    for y in range(4, 15):
        for x in range(5, 11):
            if 4 <= y <= 8 and 6 <= x <= 9:
                col = (32, 24, 28) if (y == 6 and x in (6, 9)) else (228, 218, 195)
                is_d.set_at((x, y), col)
                is_n.set_at((x, y), N_UP)
            elif y % 2 == 0 or x in (7, 8):
                is_d.set_at((x, y), (202, 192, 168))
                is_n.set_at((x, y), N_FLAT)
    assets["impaled_skeleton"] = enforce_crisp_rim_normals(is_d, is_n)

    # 15.10 Заграждение из заострённых бивней и костей (bone_spike_barricade)
    bsb_d, bsb_n = make_pair(16, 20)
    for sx, top_y in ((3, 6), (6, 4), (9, 5), (12, 6)):
        for y in range(top_y, 19):
            for dx in (-1, 0, 1):
                if y <= top_y + 2 and dx != 0:
                    continue
                col = (185, 34, 44) if y in (11, 12) else ((232, 224, 202) if dx <= 0 else (178, 168, 146))
                bsb_d.set_at((sx + dx, y), col)
                bsb_n.set_at((sx + dx, y), N_UP if y <= top_y + 3 else N_FLAT)
    assets["bone_spike_barricade"] = enforce_crisp_rim_normals(bsb_d, bsb_n)

    # 15.11 Костяная жаровня с мертвецким фиолетово-зелёным огнём (necrotic_brazier)
    nb_d, nb_n = make_pair(16, 20)
    for y in range(4, 19):
        for x in range(3, 13):
            if y <= 10 and math.hypot(x - 7.5, y - 8.0) <= 3.8:
                col = (195, 255, 215) if abs(x - 7.5) <= 1.2 else ((95, 245, 135) if (x + y) % 2 == 0 else (155, 65, 235))
                nb_d.set_at((x, y), col)
                nb_n.set_at((x, y), N_UP)
            elif 11 <= y <= 18 and abs(x - 7.5) <= (4.5 if y <= 13 else 3.0):
                col = (225, 215, 192) if x < 8 else (175, 165, 142)
                nb_d.set_at((x, y), col)
                nb_n.set_at((x, y), N_LEFT if x < 7 else N_RIGHT)
    assets["necrotic_brazier"] = enforce_crisp_rim_normals(nb_d, nb_n)

    # 15.12 Костяной сундук-оссуарий из рёбер с замком-черепом (ossuary_chest)
    oc_d, oc_n = make_pair(16, 20)
    for y in range(8, 19):
        for x in range(2, 14):
            if x in (2, 13) or y in (8, 12, 18) or x % 2 == 0:
                col = (228, 218, 195) if y < 13 else (188, 178, 155)
            else:
                col = (138, 28, 38)  # Багровый бархат/плоть под рёбрами
            if 6 <= x <= 9 and 10 <= y <= 13:
                col = (95, 255, 135) if (y == 11 and x in (6, 9)) else (242, 236, 218)
            oc_d.set_at((x, y), col)
            oc_n.set_at((x, y), N_FLAT)
    assets["ossuary_chest"] = enforce_crisp_rim_normals(oc_d, oc_n)

    # 15.13 Жертвенный стол из огромной плоской кости-лопатки (sacrificial_bone_table)
    sbt_d, sbt_n = make_pair(16, 20)
    for y in range(8, 19):
        for x in range(1, 15):
            if 8 <= y <= 12:
                is_blood = (5 <= x <= 10 and 9 <= y <= 11)
                col = (188, 28, 38) if is_blood else (225, 215, 192)
                sbt_d.set_at((x, y), col)
                sbt_n.set_at((x, y), N_FLAT)
            elif x in (3, 4, 11, 12):
                sbt_d.set_at((x, y), (175, 165, 142))
                sbt_n.set_at((x, y), N_FLAT)
    assets["sacrificial_bone_table"] = enforce_crisp_rim_normals(sbt_d, sbt_n)

    # 15.14 Вешала «ловцов душ» с подвешенными черепами и костями (bone_wind_chimes)
    bwc_d, bwc_n = make_pair(16, 20)
    for y in range(2, 19):
        for x in (2, 13):
            bwc_d.set_at((x, y), (168, 156, 134))
            bwc_n.set_at((x, y), N_UP)
    for x in range(2, 14):
        bwc_d.set_at((x, 3), (218, 208, 185))
        bwc_n.set_at((x, 3), N_UP)
    for cx_c in (5, 8, 11):
        for y in range(4, 15):
            col = (95, 245, 185) if y == 8 else (225, 215, 192)
            bwc_d.set_at((cx_c, y), col)
            bwc_n.set_at((cx_c, y), N_UP)
    assets["bone_wind_chimes"] = enforce_crisp_rim_normals(bwc_d, bwc_n)

    # =========================================================================
    # 16. ПРОПСЫ ГЛУБОКИХ ПЕЩЕР (16x20 и 32x20)
    # =========================================================================

    # 16.1 Кокон гигантского паука с оплетённой жертвой (spider_cocoon)
    spc_d, spc_n = make_pair(16, 20)
    for y in range(3, 19):
        hw = 2 if y in (3, 4, 17, 18) else (3 if y in (5, 15, 16) else 4)
        for x in range(8 - hw, 8 + hw):
            if 6 <= y <= 8 and 6 <= x <= 9:
                col = (245, 55, 55) if (y == 7 and x in (6, 9)) else (168, 162, 148)
            else:
                web_line = (x + y) % 3 == 0
                col = (238, 242, 248) if web_line else (188, 195, 208)
            nc = N_LEFT if x < 7 else (N_RIGHT if x > 8 else N_UP)
            spc_d.set_at((x, y), col)
            spc_n.set_at((x, y), nc)
    assets["spider_cocoon"] = enforce_crisp_rim_normals(spc_d, spc_n)

    # 16.2 Гнездо светящихся паучьих яиц в паутине (spider_egg_sac)
    ses_d, ses_n = make_pair(16, 20)
    for ex, ey, er in ((5.5, 14.0, 3.2), (10.5, 14.5, 3.0), (8.0, 11.0, 3.4)):
        for y in range(6, 19):
            for x in range(2, 14):
                d = math.hypot(x - ex, y - ey)
                if d <= er:
                    col = (185, 255, 125) if d <= 1.2 else (218, 226, 235)
                    ses_d.set_at((x, y), col)
                    ses_n.set_at((x, y), N_UP if d <= 1.5 else N_FLAT)
    assets["spider_egg_sac"] = enforce_crisp_rim_normals(ses_d, ses_n)

    # 16.3 Гигантский биолюминесцентный пещерный гриб (giant_cave_mushroom)
    gcm_d, gcm_n = make_pair(16, 20)
    for y in range(2, 19):
        if y <= 9:
            hw = max(2, int(math.sin(((y - 1) / 9.0) * math.pi) * 6.5))
            for x in range(8 - hw, 8 + hw):
                spot = (x * 3 + y * 5) % 6 == 0
                col = (195, 245, 255) if spot else ((138, 65, 225) if y < 7 else (88, 38, 158))
                gcm_d.set_at((x, y), col)
                gcm_n.set_at((x, y), N_UP if y <= 6 else N_DOWN)
        else:
            for x in range(6, 10):
                gcm_d.set_at((x, y), (205, 198, 222) if x < 8 else (162, 154, 182))
                gcm_n.set_at((x, y), N_LEFT if x < 8 else N_RIGHT)
    assets["giant_cave_mushroom"] = enforce_crisp_rim_normals(gcm_d, gcm_n)

    # 16.4 Расколотая аметистовая жеода с кристаллами внутри (amethyst_geode)
    ag_d, ag_n = make_pair(16, 20)
    for y in range(5, 19):
        for x in range(2, 14):
            d = math.hypot((x - 7.5) * 0.9, (y - 12.0) * 0.85)
            if d <= 5.6:
                if d <= 3.6 and y <= 15:
                    col = (238, 185, 255) if (x + y) % 2 == 0 else (168, 68, 235)
                    nc = N_DEEP
                else:
                    col = (88, 82, 96) if x < 8 else (62, 56, 70)
                    nc = N_LEFT if x < 6 else (N_RIGHT if x > 9 else N_UP)
                ag_d.set_at((x, y), col)
                ag_n.set_at((x, y), nc)
    assets["amethyst_geode"] = enforce_crisp_rim_normals(ag_d, ag_n)

    # 16.5 Кипящий серный гейзер / фумарол пещеры (sulfur_geyser)
    sgy_d, sgy_n = make_pair(16, 20)
    for y in range(3, 19):
        if y <= 9:
            sx = int(round(7.5 + math.sin(y * 0.8) * 1.8))
            for dx in (-1, 0, 1):
                sgy_d.set_at((sx + dx, y), (195, 235, 95) if dx == 0 else (128, 168, 58))
                sgy_n.set_at((sx + dx, y), N_UP)
        else:
            hw = 3 + (y - 10) // 2
            for x in range(8 - hw, 8 + hw):
                col = (235, 215, 55) if y in (10, 11) else ((96, 88, 72) if x < 8 else (68, 62, 50))
                sgy_d.set_at((x, y), col)
                sgy_n.set_at((x, y), N_UP if y <= 11 else N_FLAT)
    assets["sulfur_geyser"] = enforce_crisp_rim_normals(sgy_d, sgy_n)

    # 16.6 Сросшаяся пещерная колонна-сталагнат (stalagnate_column)
    stc_d, stc_n = make_pair(16, 20)
    for y in range(0, 20):
        hw = max(2, int(5.5 - math.sin((y / 19.0) * math.pi) * 3.2))
        for x in range(8 - hw, 8 + hw):
            col = (118, 106, 98) if x < 8 else (78, 68, 64)
            if y % 4 == 0:
                col = (94, 84, 78)
            nc = N_LEFT if x < 7 else (N_RIGHT if x > 8 else N_FLAT)
            stc_d.set_at((x, y), col)
            stc_n.set_at((x, y), nc)
    assets["stalagnate_column"] = enforce_crisp_rim_normals(stc_d, stc_n)

    # 16.7 Опрокинутая шахтёрская вагонетка с золотой рудой (minecart_wreck)
    mw_d2, mw_n2 = make_pair(16, 20)
    for y in range(8, 19):
        for x in range(2, 14):
            if y >= 16 and x in (4, 5, 10, 11):
                col, nc = (52, 56, 66), N_UP  # Чугунные колёса
            elif 8 <= y <= 10 and 4 <= x <= 11:
                col = (245, 202, 68) if (x + y) % 2 == 0 else (88, 82, 92)  # Самородки руды
                nc = N_UP
            elif 10 <= y <= 16:
                col = (112, 74, 54) if y in (10, 16) or x in (2, 13) else (76, 82, 94)
                nc = N_FLAT
            else:
                continue
            mw_d2.set_at((x, y), col)
            mw_n2.set_at((x, y), nc)
    assets["minecart_wreck"] = enforce_crisp_rim_normals(mw_d2, mw_n2)

    # 16.8 Скелет погибшего рудокопа с киркой и каской (miner_skeleton)
    msk_d, msk_n = make_pair(16, 20)
    for y in range(7, 19):
        for x in range(2, 14):
            if 7 <= y <= 11 and 5 <= x <= 10:
                col = (235, 185, 55) if y <= 8 else (225, 215, 192)  # Жёлтая каска на черепе
                msk_d.set_at((x, y), col)
                msk_n.set_at((x, y), N_UP)
            elif 12 <= y <= 17 and 4 <= x <= 11 and (x + y) % 2 == 0:
                msk_d.set_at((x, y), (195, 185, 162))
                msk_n.set_at((x, y), N_FLAT)
            elif x == 12 and 9 <= y <= 17:
                msk_d.set_at((x, y), (185, 195, 210) if y <= 11 else (128, 86, 44))  # Кирка рядом
                msk_n.set_at((x, y), N_UP)
    assets["miner_skeleton"] = enforce_crisp_rim_normals(msk_d, msk_n)

    # 16.9 Скальный зубец со стаей спящих нетопырей (bat_roost_rock)
    brr_d, brr_n = make_pair(16, 20)
    for y in range(2, 19):
        hw = 5 if y <= 8 else 3
        for x in range(8 - hw, 8 + hw):
            if 5 <= y <= 9 and x in (4, 5, 8, 9, 11):
                is_eye = (y == 7)
                col, nc = (255, 48, 58) if is_eye else (34, 28, 42), N_UP
            else:
                col = (98, 90, 86) if x < 8 else (68, 62, 58)
                nc = N_LEFT if x < 7 else N_RIGHT
            brr_d.set_at((x, y), col)
            brr_n.set_at((x, y), nc)
    assets["bat_roost_rock"] = enforce_crisp_rim_normals(brr_d, brr_n)

    # 16.10 Провал в Бездну со светящимся разломом (abyssal_fissure, 32x20 — 2x1 тайла!)
    af_d, af_n = make_pair(32, 20)
    for y in range(5, 18):
        for x in range(2, 30):
            jag = int(math.sin(x * 0.65) * 1.8)
            dy = abs(y - (11 + jag))
            if dy <= 4 and 4 <= x <= 27:
                if dy == 0:
                    col, nc = (215, 145, 255), N_DEEP
                elif dy <= 2:
                    col, nc = (98, 38, 168), N_DEEP
                else:
                    col, nc = (32, 18, 48), N_DOWN if y < 11 else N_UP
                af_d.set_at((x, y), col)
                af_n.set_at((x, y), nc)
    assets["abyssal_fissure"] = enforce_crisp_rim_normals(af_d, af_n)
