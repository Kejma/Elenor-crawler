import math
import pygame
import numpy as np
from elenor.config import VIEW_W, THOUGHT_ZONE_H, THOUGHT_BOX_W, THOUGHT_BOX_H, THOUGHT_BOX_X


def make_pair(w, h, opaque=False):
    diff = pygame.Surface((w, h), pygame.SRCALPHA)
    norm = pygame.Surface((w, h), pygame.SRCALPHA)
    norm.fill((128, 128, 255, 255 if opaque else 0))
    return diff, norm


def enforce_crisp_rim_normals(diff_surf, norm_surf):
    """
    Ensures transparent pixels have alpha=0 on the normal map AND snaps all normal pixels
    strictly to the 10-color NORMAL_COMPASS palette!
    """
    from elenor.rendering.normals import quantize_normal_surface
    quantize_normal_surface(norm_surf, diff_surf)
    return diff_surf, norm_surf


def build_hero_sprite(cloak_color, armor_class="none", has_helmet=False, has_torch=True, has_weapon=False):
    h_diff, h_norm = make_pair(16, 20)
    cr, cg, cb = cloak_color

    if armor_class == "plate":
        chest_col = (190, 200, 215)
    elif armor_class == "leather":
        chest_col = (145, 95, 55)
    elif armor_class == "cloth":
        chest_col = (max(20, cr - 30), max(20, cg - 30), max(20, cb - 30))
    else:
        chest_col = (210, 175, 145)

    for y in range(2, 19):
        for x in range(4, 12):
            if 2 <= y <= 7 and 5 <= x <= 10:
                if has_helmet:
                    col = (185, 198, 212) if y > 3 else (225, 235, 245)
                else:
                    col = (225, 185, 155) if y > 3 else (95, 65, 45)
                if y == 5 and x in (6, 9):
                    col = (25, 30, 40)
                nx = 80 if x < 7 else (175 if x > 8 else 128)
                ny = 200 if y < 4 else 128
                h_diff.set_at((x, y), col)
                h_norm.set_at((x, y), (nx, ny, 230))
            elif 8 <= y <= 15:
                col = cloak_color if x in (4, 11) else chest_col
                if y == 12 and 5 <= x <= 10:
                    col = (110, 75, 45)
                nx = 75 if x < 7 else (180 if x > 8 else 128)
                h_diff.set_at((x, y), col)
                h_norm.set_at((x, y), (nx, 140, 230))
            elif y >= 16 and x in (5, 6, 9, 10):
                h_diff.set_at((x, y), (70, 50, 40))
                h_norm.set_at((x, y), (128, 160, 220))

    if has_torch:
        for y in range(6, 12):
            col = (255, 205, 65) if y <= 7 else (120, 80, 45)
            h_diff.set_at((13, y), col)
            h_norm.set_at((13, y), (160, 200, 240))

# Right hand weapon
    if has_weapon:
        for y in range(4, 13):
            col = (205, 215, 230) if y < 11 else (140, 95, 45)
            h_diff.set_at((2, y), col)
            h_norm.set_at((2, y), (90, 190, 235))

    return enforce_crisp_rim_normals(h_diff, h_norm)

def generate_carpet_tile_pair(has_n, has_s, has_w, has_e):
    diff, norm = make_pair(16, 16, opaque=True)
    c_base_dark = (102, 28, 34)
    c_base_light = (118, 34, 42)
    gold_dark = (148, 105, 48)
    gold_bright = (205, 160, 68)
    fringe_col = (205, 192, 160)
    fringe_dark = (140, 125, 95)

    # 1. Тканевое бархатное полотно ковра
    for y in range(16):
        for x in range(16):
            col = c_base_light if (x + y) % 2 == 0 else c_base_dark
            diff.set_at((x, y), (*col, 255))
            norm.set_at((x, y), (128, 128, 255, 255))

    # 2. Золотая кайма вдоль свободных краёв
    if not has_n:
        for x in range(16):
            diff.set_at((x, 1), gold_dark)
            diff.set_at((x, 2), gold_bright)
            if x % 2 == 0:
                diff.set_at((x, 0), fringe_col)
            else:
                diff.set_at((x, 0), fringe_dark)
    if not has_s:
        for x in range(16):
            diff.set_at((x, 13), gold_bright)
            diff.set_at((x, 14), gold_dark)
            if x % 2 == 0:
                diff.set_at((x, 15), fringe_col)
            else:
                diff.set_at((x, 15), fringe_dark)
    if not has_w:
        for y in range(16):
            diff.set_at((1, y), gold_dark)
            diff.set_at((2, y), gold_bright)
            if y % 2 == 0:
                diff.set_at((0, y), fringe_col)
            else:
                diff.set_at((0, y), fringe_dark)
    if not has_e:
        for y in range(16):
            diff.set_at((13, y), gold_bright)
            diff.set_at((14, y), gold_dark)
            if y % 2 == 0:
                diff.set_at((15, y), fringe_col)
            else:
                diff.set_at((15, y), fringe_dark)

    # 3. Королевский медальон по центру (только если тайл полностью внутренний)
    if has_n and has_s and has_w and has_e:
        for y in range(4, 12):
            for x in range(4, 12):
                dist = abs(x - 7.5) + abs(y - 7.5)
                if dist <= 4.2:
                    m_col = gold_bright if dist in (2, 4) else (58, 86, 74)
                    diff.set_at((x, y), m_col)
        diff.set_at((7, 7), (235, 210, 120))
        diff.set_at((8, 7), (235, 210, 120))
        diff.set_at((7, 8), (235, 210, 120))
        diff.set_at((8, 8), (235, 210, 120))

    return diff, norm


def get_carpet_autotile_key(carpets_set, x, y):
    has_n = (x, y - 1) in carpets_set
    has_s = (x, y + 1) in carpets_set
    has_w = (x - 1, y) in carpets_set
    has_e = (x + 1, y) in carpets_set

    if not has_n and not has_s and not has_w and not has_e:
        return "carpet_single"
    if has_w and has_e and not has_n and not has_s:
        return "carpet_h"
    if has_n and has_s and not has_w and not has_e:
        return "carpet_v"

    if not has_n and not has_w:
        return "carpet_nw"
    if not has_n and not has_e:
        return "carpet_ne"
    if not has_s and not has_w:
        return "carpet_sw"
    if not has_s and not has_e:
        return "carpet_se"

    if not has_n:
        return "carpet_n"
    if not has_s:
        return "carpet_s"
    if not has_w:
        return "carpet_w"
    if not has_e:
        return "carpet_e"

    return "carpet_c"

def create_placeholder_assets():
    assets = {}

    # 1. Каменная плита подвала (floor_0): тёсаный брусчатый камень с глубокими швами
    f_diff, f_norm = make_pair(16, 16, opaque=True)
    f_diff.fill((46, 44, 54, 255))
    f_norm.fill((128, 128, 240, 255))
    slabs = [(0, 0, 7, 7), (8, 0, 8, 7), (0, 8, 9, 8), (10, 8, 6, 8)]
    for sx, sy, sw, sh in slabs:
        for y in range(sy, sy + sh):
            for x in range(sx, sx + sw):
                noise = ((x * 37 + y * 59) % 7) - 3
                c = (52 + noise, 50 + noise, 60 + noise)
                nx, ny, nz = 128, 128, 245
                if y == sy:
                    c = (64, 62, 74)
                    ny, nz = 185, 220
                elif y == sy + sh - 1:
                    c = (34, 32, 42)
                    ny, nz = 80, 220
                if x == sx:
                    nx, nz = 85, 220
                elif x == sx + sw - 1:
                    nx, nz = 175, 220
                f_diff.set_at((x, y), c)
                f_norm.set_at((x, y), (nx, ny, nz, 255))
    # Швы раствора между плитами
    for i in range(16):
        f_diff.set_at((i, 7), (24, 22, 30))
        f_norm.set_at((i, 7), (128, 65, 190, 255))
    for y in range(7):
        f_diff.set_at((7, y), (24, 22, 30))
        f_norm.set_at((7, y), (65, 128, 190, 255))
    for y in range(8, 16):
        f_diff.set_at((9, y), (24, 22, 30))
        f_norm.set_at((9, y), (65, 128, 190, 255))
    assets["floor_0"] = (f_diff, f_norm)

    # 2. Бесшовная 3-кадровая подземная вода (floor_2)
    water_frames = []
    tau = 2.0 * math.pi / 16.0
    for frame_i in range(3):
        phase = frame_i * (2.0 * math.pi / 3.0)
        wa_diff, wa_norm = make_pair(16, 16, opaque=True)
        for y in range(16):
            for x in range(16):
                w1 = math.sin(x * tau + y * tau + phase)
                w2 = math.cos(x * tau - y * tau * 2.0 - phase)
                wave_val = (w1 + w2) * 0.5
                c_r = int(20 + (wave_val + 1.0) * 8)
                c_g = int(48 + (wave_val + 1.0) * 16)
                c_b = int(76 + (wave_val + 1.0) * 20)
                if wave_val > 0.62:
                    c_r, c_g, c_b = 58, 105, 142
                nx = int(128 + w1 * 34)
                ny = int(128 - w2 * 34)
                wa_diff.set_at((x, y), (c_r, c_g, c_b, 255))
                wa_norm.set_at((x, y), (nx, ny, 235, 255))
        water_frames.append((wa_diff, wa_norm))
    assets["floor_2"] = water_frames[0]
    assets["_water_frames"] = water_frames

    # 3. Лесной мох / Трава (floor_3) — изотропные нормали для идеального вращения на 90/180/270°!
    mo_diff, mo_norm = make_pair(16, 16, opaque=True)
    mo_diff.fill((28, 46, 33, 255))
    mo_norm.fill((128, 128, 255, 255))
    for y in range(16):
        for x in range(16):
            h_val = ((x * 73 + y * 151 + (x * y) * 31) ^ ((x + 3) * 19 + (y + 7) * 23)) % 37
            if h_val < 5:
                mo_diff.set_at((x, y), (36, 58, 40, 255))
                mo_norm.set_at((x, y), (128, 128, 255, 255))
            elif h_val in (7, 8):
                mo_diff.set_at((x, y), (22, 36, 26, 255))
                mo_norm.set_at((x, y), (128, 128, 155, 255))
            elif h_val == 12:
                mo_diff.set_at((x, y), (44, 70, 46, 255))
                mo_norm.set_at((x, y), (128, 128, 255, 255))
    assets["floor_3"] = (mo_diff, mo_norm)

    # 4. Мягкий, малоконтрастный дощатый настил (floor_4) для идеальной читаемости объектов и врагов!
    wo_diff, wo_norm = make_pair(16, 16, opaque=True)
    for y in range(16):
        plank_row = y // 4
        seam_x = (plank_row * 7 + 5) % 16
        for x in range(16):
            if y % 4 == 0 or x == seam_x:
                wo_diff.set_at((x, y), (56, 38, 25, 255))
                wo_norm.set_at((x, y), (128, 128, 255, 255))
            else:
                grain = ((x * 13 + y * 29) % 5) - 2
                base_r = 68 if y % 4 == 1 else 64
                base_g = 46 if y % 4 == 1 else 43
                base_b = 30 if y % 4 == 1 else 28
                wo_diff.set_at((x, y), (base_r + grain, base_g + grain // 2, base_b, 255))
                wo_norm.set_at((x, y), (128, 128, 255, 255))
    assets["floor_4"] = (wo_diff, wo_norm)

    # 5. Пещерный грунт (floor_5 / код сетки 8) — симметричные нормали для вращения без швов!
    cv_diff, cv_norm = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            h_v = ((x * 97 + y * 131 + x * y * 17) ^ (x * 13 + y * 43)) % 29
            if h_v in (0, 1):
                cv_diff.set_at((x, y), (58, 49, 45, 255))
                cv_norm.set_at((x, y), (128, 128, 255, 255))
            elif h_v in (2, 3, 4):
                cv_diff.set_at((x, y), (38, 32, 30, 255))
                cv_norm.set_at((x, y), (128, 128, 155, 255))
            else:
                sh = (h_v % 5) - 2
                cv_diff.set_at((x, y), (48 + sh, 40 + sh, 37 + sh, 255))
                cv_norm.set_at((x, y), (128, 128, 255, 255))
    assets["floor_5"] = (cv_diff, cv_norm)

    # 5b. Лесная грунтовая дорога с мягкой колеёй БЕЗ камней (`floor_6` / код сетки 9)
    rd_diff, rd_norm = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            h_r = ((x * 53 + y * 97 + x * y * 13) ^ (x * 19 + y * 31)) % 19
            is_rut = x in (4, 5, 10, 11)
            if is_rut:
                col = (62, 44, 29, 255) if h_r % 2 == 0 else (56, 40, 26, 255)
                n_col = (128, 128, 155, 255)
            else:
                sh = (h_r % 5) - 2
                col = (76 + sh, 54 + sh, 35 + sh, 255)
                n_col = (128, 128, 255, 255)
            rd_diff.set_at((x, y), col)
            rd_norm.set_at((x, y), n_col)
    assets["floor_6"] = (rd_diff, rd_norm)

    # --- ПОЛУПРОЗРАЧНЫЕ НАКЛАДЫВАЕМЫЕ ОВЕРЛЕИ (16x16, ЧЕСТНЫЕ 4-СТОРОННИЕ ГРАНИ ДЛЯ ВРАЩЕНИЯ) ---
    # Оверлей 1: Россыпь 2x2 камушков (`ov_pebbles`) — единый цвет камня, объём даёт 4-гранная пирамидка нормалей!
    ov_p_d, ov_p_n = make_pair(16, 16, opaque=False)
    for bx, by in ((3, 3), (11, 4), (6, 10), (12, 12)):
        ov_p_d.set_at((bx, by),         (96, 90, 86, 215))
        ov_p_n.set_at((bx, by),         (65, 195, 195, 255))   # ↖ Верх-Лев
        ov_p_d.set_at((bx + 1, by),     (96, 90, 86, 215))
        ov_p_n.set_at((bx + 1, by),     (190, 195, 195, 255))  # ↗ Верх-Прав
        ov_p_d.set_at((bx, by + 1),     (96, 90, 86, 215))
        ov_p_n.set_at((bx, by + 1),     (65, 60, 195, 255))    # ↙ Низ-Лев
        ov_p_d.set_at((bx + 1, by + 1), (96, 90, 86, 215))
        ov_p_n.set_at((bx + 1, by + 1), (190, 60, 195, 255))   # ↘ Низ-Прав
    assets["ov_pebbles"] = (ov_p_d, ov_p_n)

    # Оверлей 2: Пятна влажного мха (`ov_moss`) — по краям 4-сторонний скос от центра пятна
    ov_m_d, ov_m_n = make_pair(16, 16, opaque=False)
    moss_patches = [(4.5, 5.5, 3.0), (11.0, 11.0, 3.4), (10.5, 4.0, 2.0)]
    for mx_c, my_c, m_rad in moss_patches:
        for y in range(16):
            for x in range(16):
                d_m = math.hypot(x - mx_c, y - my_c) + (((x * 17 + y * 31) % 5) * 0.18)
                if d_m <= m_rad:
                    col = (42, 78, 44, 195) if (x + y) % 2 == 0 else (34, 64, 38, 185)
                    ov_m_d.set_at((x, y), col)
                    ov_m_n.set_at((x, y), (128, 128, 255, 255))
    assets["ov_moss"] = (ov_m_d, ov_m_n)

    # Оверлей 3: Трещины и сколы в камне/грунте (`ov_cracks`) — чистая впадина (128, 128, 155)
    ov_c_d, ov_c_n = make_pair(16, 16, opaque=False)
    crack_px = [(2, 3), (3, 4), (4, 5), (5, 5), (6, 6), (7, 7), (8, 7), (9, 8), (10, 9), (11, 11), (6, 8), (5, 9), (4, 11)]
    for cx_p, cy_p in crack_px:
        ov_c_d.set_at((cx_p, cy_p), (20, 18, 24, 215))
        ov_c_n.set_at((cx_p, cy_p), (128, 128, 155, 255))
    assets["ov_cracks"] = (ov_c_d, ov_c_n)

    # Оверлей 4: Потёртости и сучки (`ov_planks_wear`)
    ov_w_d, ov_w_n = make_pair(16, 16, opaque=False)
    for x in range(3, 12):
        ov_w_d.set_at((x, 6), (48, 28, 16, 180))
        ov_w_n.set_at((x, 6), (128, 128, 155, 255))
    for x in range(6, 14):
        ov_w_d.set_at((x, 13), (52, 32, 18, 175))
        ov_w_n.set_at((x, 13), (128, 128, 155, 255))
    assets["ov_planks_wear"] = (ov_w_d, ov_w_n)

    # 6. Сырая каменная стена подвала (wall / код сетки 1)
    w_diff, w_norm = make_pair(16, 16, opaque=True)
    w_diff.fill((22, 22, 28, 255))
    w_norm.fill((128, 128, 180, 255))
    bricks = [(1, 1, 6, 6), (9, 1, 6, 6), (0, 9, 4, 6), (6, 9, 6, 6), (14, 9, 2, 6)]
    for bx, by, bw, bh in bricks:
        for y in range(by, by + bh):
            for x in range(bx, bx + bw):
                moss = ((x + y * 3) % 11 == 0)
                c = (52, 68, 56) if moss else (68, 66, 78)
                nx, ny, nz = 128, 128, 250
                if y == by:
                    c = (88, 86, 100)
                    ny, nz = 215, 200
                elif y == by + bh - 1:
                    c = (44, 42, 52)
                    ny, nz = 45, 200
                if x == bx:
                    nx, nz = 50, 200
                elif x == bx + bw - 1:
                    nx, nz = 205, 200
                w_diff.set_at((x, y), c)
                w_norm.set_at((x, y), (nx, ny, nz, 255))
    assets["wall"] = (w_diff, w_norm)

    # 7. Бревенчатая стена таверны и деревянного погреба (wall_wood / код сетки 6)
    ww_diff, ww_norm = make_pair(16, 16, opaque=True)
    for y in range(16):
        log_y = y % 5
        for x in range(16):
            if x in (0, 15):
                # Вертикальные опорные брусья
                col = (72, 44, 24, 255) if x == 0 else (54, 32, 18, 255)
                nx = 180 if x == 0 else 75
                ww_diff.set_at((x, y), col)
                ww_norm.set_at((x, y), (nx, 128, 220, 255))
            elif log_y == 0:
                # Тёмный паз между брёвнами
                ww_diff.set_at((x, y), (34, 20, 12, 255))
                ww_norm.set_at((x, y), (128, 55, 185, 255))
            else:
                g = ((x * 17 + y * 7) % 7) - 3
                if log_y == 1:
                    col = (122 + g, 78 + g, 44 + g, 255)
                    ny = 210
                elif log_y in (2, 3):
                    col = (104 + g, 64 + g, 35 + g, 255)
                    ny = 140
                else:
                    col = (76 + g, 46 + g, 25 + g, 255)
                    ny = 75
                ww_diff.set_at((x, y), col)
                ww_norm.set_at((x, y), (128, ny, 225, 255))
    assets["wall_wood"] = (ww_diff, ww_norm)

    # 8. Скальный свод пещеры (wall_cave / код сетки 7)
    wc_diff, wc_norm = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            cell_x = (x + (y // 4) * 3) // 5
            cell_y = y // 5
            edge_x = (x + (y // 4) * 3) % 5
            edge_y = y % 5
            crag = ((cell_x * 31 + cell_y * 53) % 9) - 4
            if edge_x == 0 or edge_y == 0:
                wc_diff.set_at((x, y), (26, 20, 22, 255))
                wc_norm.set_at((x, y), (75, 70, 190, 255))
            elif edge_y == 1:
                wc_diff.set_at((x, y), (74 + crag, 58 + crag, 54 + crag, 255))
                wc_norm.set_at((x, y), (115, 205, 215, 255))
            elif edge_y == 4:
                wc_diff.set_at((x, y), (40 + crag, 32 + crag, 30 + crag, 255))
                wc_norm.set_at((x, y), (145, 65, 210, 255))
            else:
                nx = 85 if edge_x == 1 else (175 if edge_x == 4 else 128)
                wc_diff.set_at((x, y), (58 + crag, 46 + crag, 43 + crag, 255))
                wc_norm.set_at((x, y), (nx, 135, 225, 255))
    assets["wall_cave"] = (wc_diff, wc_norm)

    # Tall 16x16 base icon for studio + Tall 24x38 Canopy Tree for in-game forest!
    tr_diff, tr_norm = make_pair(16, 16)
    assets["tree"] = (tr_diff, tr_norm)

    tall_d, tall_n = make_pair(24, 38)
    for y in range(2, 38):
        for x in range(2, 22):
            # Sturdy bark trunk at bottom
            if y >= 28 and 9 <= x <= 14:
                col = (82, 52, 32) if x < 12 else (58, 36, 22)
                nx = 85 if x < 11 else (175 if x > 12 else 128)
                tall_d.set_at((x, y), col)
                tall_n.set_at((x, y), (nx, 128, 220, 255))
            elif y < 31:
                # 3-tiered lush pine canopy
                rel_y = y - 2
                tier = rel_y // 10
                tier_y = rel_y % 10
                max_half_w = 2.0 + tier * 2.2 + tier_y * 0.68
                dist_x = abs(x - 11.5)
                if dist_x <= max_half_w:
                    shade = (x * 3 + y * 5) % 4
                    if tier_y < 3:
                        col = (46, 94, 56) if shade else (36, 78, 46)
                        ny = 205
                    elif tier_y > 7:
                        col = (18, 42, 26)
                        ny = 65
                    else:
                        col = (30, 68, 42) if shade != 0 else (24, 54, 34)
                        ny = 140
                    nx = int(np.clip(128 + (x - 11.5) * 9.5, 45, 210))
                    tall_d.set_at((x, y), col)
                    tall_n.set_at((x, y), (nx, ny, 215, 255))
    assets["tall_tree"] = (tall_d, tall_n)

    dc_diff, dc_norm = make_pair(16, 16)
    dc_diff.fill((95, 60, 35))
    for y in range(16):
        for x in range(16):
            col = (55, 35, 20) if (x in (0, 15) or y in (0, 15)) else ((130, 135, 145) if y in (4, 11) else (95, 60, 35))
            dc_diff.set_at((x, y), col)
            dc_norm.set_at((x, y), (165 if x % 4 == 0 else 128, 195 if y in (4, 11) else 128, 225))
    assets["door_closed"] = (dc_diff, dc_norm)

    dl_diff, dl_norm = make_pair(16, 16)
    dl_diff.fill((25, 22, 30))
    for y in range(16):
        for x in range(16):
            if x in (2, 6, 10, 14) or y in (3, 12):
                dl_diff.set_at((x, y), (150, 155, 170))
                dl_norm.set_at((x, y), (175, 195, 230))
    assets["door_locked"] = (dl_diff, dl_norm)

    do_diff, do_norm = make_pair(16, 16)
    for y in range(16):
        for x in range(3):
            do_diff.set_at((x, y), (85, 52, 30))
            do_norm.set_at((x, y), (185, 128, 220))
    assets["door_open"] = (do_diff, do_norm)

    for state_name, tilt in (("lever_off", -3), ("lever_on", 3)):
        lv_d, lv_n = make_pair(16, 20)
        for y in range(14, 19):
            for x in range(5, 11):
                lv_d.set_at((x, y), (90, 95, 110))
                lv_n.set_at((x, y), (128, 200, 220))
        for i in range(8):
            lx = 8 + int((i / 7.0) * tilt)
            ly = 14 - i
            lv_d.set_at((lx, ly), (220, 80, 70) if i == 7 else (175, 145, 90))
            lv_n.set_at((lx, ly), (175, 195, 235))
        assets[state_name] = (lv_d, lv_n)

    tz_diff, tz_norm = make_pair(VIEW_W, THOUGHT_ZONE_H)
    for y in range(THOUGHT_ZONE_H):
        for x in range(VIEW_W):
            col = (68, 60, 82) if y < 2 else (26, 23, 33)
            ny = 225 if y < 2 else 128
            tz_diff.set_at((x, y), col)
            tz_norm.set_at((x, y), (128, ny, 220))

    bx0 = THOUGHT_BOX_X
    by0 = (THOUGHT_ZONE_H - THOUGHT_BOX_H) // 2
    for y in range(THOUGHT_BOX_H):
        for x in range(THOUGHT_BOX_W):
            in_border = (x < 5 or x >= THOUGHT_BOX_W - 5 or y < 5 or y >= THOUGHT_BOX_H - 5)
            px, py = bx0 + x, by0 + y
            if in_border:
                col = (98, 66, 48)
                nx, ny, nz = 128, 128, 210
                if y < 2:
                    col = (140, 98, 70)
                    ny, nz = 230, 175
                elif y >= THOUGHT_BOX_H - 2:
                    col = (52, 34, 24)
                    ny, nz = 35, 175
                if x < 2:
                    nx, nz = 40, 175
                elif x >= THOUGHT_BOX_W - 2:
                    nx, nz = 215, 175
                if (x in (2, 3, THOUGHT_BOX_W - 4, THOUGHT_BOX_W - 3)) and (y in (2, 3, THOUGHT_BOX_H - 4, THOUGHT_BOX_H - 3)):
                    col = (220, 180, 85)
                    ny, nz = 215, 225
                tz_diff.set_at((px, py), col)
                tz_norm.set_at((px, py), (nx, ny, nz))
            else:
                tz_diff.set_at((px, py), (18, 16, 24))
                tz_norm.set_at((px, py), (128, 128, 250))
    assets["thought_zone"] = (tz_diff, tz_norm)

    wf_diff, wf_norm = make_pair(16, 20)
    for y in range(9, 19):
        for x in range(2, 14):
            if 9 <= y <= 13 and 9 <= x <= 13:
                col = (255, 190, 50) if (y == 10 and x == 12) else (115, 110, 105)
                wf_diff.set_at((x, y), col)
                wf_norm.set_at((x, y), (165, 195, 225))
            elif 12 <= y <= 16 and 3 <= x <= 11:
                wf_diff.set_at((x, y), (95, 90, 85))
                wf_norm.set_at((x, y), (128, 185, 225))
            elif y >= 17 and x in (4, 6, 9, 11):
                wf_diff.set_at((x, y), (70, 65, 60))
    assets["wolf"] = (wf_diff, wf_norm)

    e_diff, e_norm = make_pair(16, 20)
    for y in range(3, 19):
        for x in range(4, 12):
            if 3 <= y <= 8 and 5 <= x <= 10:
                col = (255, 70, 70) if (y == 6 and x in (6, 9)) else (210, 205, 190)
                e_diff.set_at((x, y), col)
                e_norm.set_at((x, y), (75 if x < 7 else 180, 200 if y < 5 else 128, 225))
            elif 9 <= y <= 14 and (y % 2 == 1 or x in (7, 8)):
                e_diff.set_at((x, y), (185, 180, 165))
                e_norm.set_at((x, y), (128, 175, 220))
            elif y >= 15 and x in (6, 9):
                e_diff.set_at((x, y), (170, 165, 150))
    assets["skeleton"] = (e_diff, e_norm)

    cu_diff, cu_norm = make_pair(16, 20)
    for y in range(2, 19):
        for x in range(4, 12):
            if 2 <= y <= 7 and 5 <= x <= 10:
                col = (180, 255, 255) if (y == 5 and x in (6, 9)) else (115, 45, 145)
                cu_diff.set_at((x, y), col)
                cu_norm.set_at((x, y), (90 if x < 8 else 170, 195, 230))
            elif 8 <= y <= 18:
                col = (85, 32, 110) if x not in (7, 8) else (195, 155, 75)
                cu_diff.set_at((x, y), col)
                cu_norm.set_at((x, y), (80 if x < 8 else 175, 140, 225))
    assets["cultist"] = (cu_diff, cu_norm)

    ne_diff, ne_norm = make_pair(16, 20)
    for y in range(2, 19):
        for x in range(3, 13):
            if 2 <= y <= 7 and 5 <= x <= 10:
                col = (90, 255, 120) if (y == 5 and x in (6, 9)) else (40, 65, 55)
                ne_diff.set_at((x, y), col)
                ne_norm.set_at((x, y), (128, 205, 235))
            elif 8 <= y <= 18 and 4 <= x <= 11:
                col = (30, 50, 42) if x not in (7, 8) else (95, 225, 130)
                ne_diff.set_at((x, y), col)
                ne_norm.set_at((x, y), (85 if x < 8 else 170, 150, 225))
            if x == 12 and 4 <= y <= 17:
                ne_diff.set_at((x, y), (110, 255, 140) if y < 7 else (130, 95, 55))
    assets["necromancer"] = (ne_diff, ne_norm)

    br_e_diff, br_e_norm = make_pair(16, 20)
    for y in range(1, 19):
        for x in range(2, 14):
            if 1 <= y <= 6 and 5 <= x <= 10:
                col = (255, 140, 50) if (y == 4 and x in (6, 9)) else (155, 170, 140)
                br_e_diff.set_at((x, y), col)
                br_e_norm.set_at((x, y), (128, 205, 230))
            elif 7 <= y <= 15:
                col = (115, 125, 105) if x not in (2, 13) else (85, 70, 55)
                br_e_diff.set_at((x, y), col)
                br_e_norm.set_at((x, y), (70 if x < 7 else 185, 160, 225))
            elif y >= 16 and x in (4, 5, 10, 11):
                br_e_diff.set_at((x, y), (65, 55, 45))
    assets["brute"] = (br_e_diff, br_e_norm)

    c_diff, c_norm = make_pair(16, 20)
    for y in range(8, 19):
        for x in range(2, 14):
            col = (195, 165, 70) if (x in (2, 13) or y in (8, 12, 18)) else (140, 85, 40)
            c_diff.set_at((x, y), col)
            c_norm.set_at((x, y), (80 if x < 6 else 175, 210 if y < 12 else 110, 225))
    assets["chest"] = (c_diff, c_norm)

    i_diff, i_norm = make_pair(16, 20)
    for y in range(2, 19):
        for x in range(4, 12):
            if y < 6 and x in (4, 11):
                continue
            col = (70, 230, 220) if (y in (6, 11, 14) and x in (7, 8)) else (85, 95, 110)
            i_diff.set_at((x, y), col)
            i_norm.set_at((x, y), (70 if x < 7 else 185, 200 if y < 6 else 135, 230))
    assets["idol"] = (i_diff, i_norm)

    l_diff, l_norm = make_pair(16, 20)
    for y in range(11, 19):
        for x in range(4, 12):
            if (x - 7.5) ** 2 + (y - 15.0) ** 2 <= 14:
                col = (165, 115, 65) if y != 13 else (225, 190, 80)
                l_diff.set_at((x, y), col)
                l_norm.set_at((x, y), (80 if x < 7 else 175, 205 if y < 14 else 110, 225))
    assets["loot"] = (l_diff, l_norm)

    # 3-Frame Animated Campfire (criss-cross logs, glowing embers & dancing 3-phase flame tongues!)
    campfire_frames = []
    flame_shifts = [(-1, 0, 1), (0, 1, -1), (1, -1, 0)]
    for f_idx in range(3):
        cf_diff, cf_norm = make_pair(16, 20)
        # Stone ring & crossed charred logs at the base (y=15..18)
        for y in range(15, 19):
            for x in range(3, 13):
                if (x in (3, 12) and y >= 16) or (y == 18 and 4 <= x <= 11):
                    cf_diff.set_at((x, y), (72, 68, 76))
                    cf_norm.set_at((x, y), (90 if x < 8 else 165, 110, 210, 255))
                elif 4 <= x <= 11:
                    ember = (f_idx + x + y) % 3 == 0
                    cf_diff.set_at((x, y), (210, 85, 30) if ember else (88, 52, 28))
                    cf_norm.set_at((x, y), (128, 185, 225, 255))
        # Animated dancing flames (y=6..15)
        s_top, s_mid, s_spark = flame_shifts[f_idx]
        for y in range(6, 16):
            rel = 15 - y
            center_x = 7.5 + (s_top * 0.7 if rel > 5 else s_mid * 0.4)
            half_w = max(0.8, (10 - rel) * 0.48)
            for x in range(2, 14):
                dist = abs(x - center_x)
                if dist <= half_w:
                    if dist <= half_w * 0.38 and y >= 10:
                        col = (255, 245, 155)  # White-hot inner core
                    elif dist <= half_w * 0.72 and y >= 8:
                        col = (255, 175, 45)   # Bright orange middle flame
                    else:
                        col = (225, 68, 28)    # Crimson outer flame lick
                    nx = int(np.clip(128 + (x - center_x) * 14, 55, 200))
                    cf_diff.set_at((x, y), col)
                    cf_norm.set_at((x, y), (nx, 210, 245, 255))
        # Rising spark pixel
        sp_x = 7 + s_spark * 2
        sp_y = 5 + (f_idx % 2)
        cf_diff.set_at((sp_x, sp_y), (255, 220, 95))
        cf_norm.set_at((sp_x, sp_y), (128, 220, 245, 255))
        campfire_frames.append((cf_diff, cf_norm))

    assets["campfire"] = campfire_frames[0]
    assets["_campfire_frames"] = campfire_frames

    # Wine Barrel (16x20) for Floor 1 Cellar
    ba_diff, ba_norm = make_pair(16, 20)
    for y in range(5, 19):
        curve = 1 if 8 <= y <= 15 else 0
        for x in range(3 - curve, 13 + curve):
            is_hoop = y in (7, 11, 16)
            shade = abs(x - 7.5)
            if is_hoop:
                col = (95, 102, 115) if shade < 3.5 else (62, 66, 76)
                ny = 165
            else:
                col = (135, 82, 42) if shade < 2.5 else ((105, 62, 30) if shade < 4.5 else (75, 44, 22))
                if x % 3 == 0:
                    col = (max(20, col[0] - 12), max(15, col[1] - 10), max(10, col[2] - 8))
                ny = 195 if y < 8 else (85 if y > 16 else 135)
            nx = int(np.clip(128 + (x - 7.5) * 14, 40, 215))
            ba_diff.set_at((x, y), col)
            ba_norm.set_at((x, y), (nx, ny, 220, 255))
    # Brass spigot on front
    ba_diff.set_at((8, 13), (225, 185, 75))
    ba_diff.set_at((8, 14), (185, 40, 55))
    assets["barrel"] = (ba_diff, ba_norm)

    # Blood Ritual Altar (16x20) for Floor 3 Boss Room
    al_diff, al_norm = make_pair(16, 20)
    for y in range(8, 19):
        w_half = 6 if y in (8, 9, 17, 18) else 5
        for x in range(8 - w_half, 8 + w_half):
            is_blood = (y in (8, 9) and 5 <= x <= 10) or (x in (6, 9) and 10 <= y <= 14)
            col = (195, 32, 45) if is_blood else ((85, 78, 92) if y < 11 else (58, 52, 64))
            nx = 80 if x < 6 else (175 if x > 9 else 128)
            ny = 210 if y <= 9 else 120
            al_diff.set_at((x, y), col)
            al_norm.set_at((x, y), (nx, ny, 225, 255))
    assets["ritual_altar"] = (al_diff, al_norm)

    # 1. Ordinary Cellar Rat (`rat`, 16x20)
    rt_diff, rt_norm = make_pair(16, 20)
    for y in range(12, 19):
        for x in range(3, 14):
            if (13 <= y <= 17 and 5 <= x <= 11) or (14 <= y <= 17 and 3 <= x <= 5):
                col = (115, 102, 96) if y < 16 else (82, 72, 68)
                nx = int(128 + (x - 8) * 12)
                ny = 195 if y <= 14 else 95
                rt_diff.set_at((x, y), col)
                rt_norm.set_at((x, y), (nx, ny, 220, 255))
    # Pink tail, ears & red eye
    for tx, ty in ((12, 16), (13, 15), (14, 14)):
        rt_diff.set_at((tx, ty), (205, 135, 140))
        rt_norm.set_at((tx, ty), (165, 165, 210, 255))
    rt_diff.set_at((4, 15), (245, 55, 55))
    rt_diff.set_at((6, 12), (185, 120, 125))
    assets["rat"] = (rt_diff, rt_norm)

    # 2. ДВЕ КРЫСЫ ДРУГ НА ДРУГЕ ПОД ПЛАЩОМ (`rat_cultist`, 16x20)
    rc_diff, rc_norm = make_pair(16, 20)
    # Верхняя крыса в багровом капюшоне (y=3..9)
    for y in range(3, 10):
        for x in range(4, 12):
            if 5 <= y <= 8 and 3 <= x <= 7:
                # Вытянутая серая мордочка верхней крысы
                rc_diff.set_at((x, y), (128, 112, 106))
                rc_norm.set_at((x, y), (95, 185, 225, 255))
            elif 5 <= x <= 11:
                rc_diff.set_at((x, y), (145, 32, 46) if y < 8 else (115, 24, 36))
                rc_norm.set_at((x, y), (int(128 + (x - 8) * 14), 195, 220, 255))
    rc_diff.set_at((3, 6), (225, 135, 145))  # Розовый нос верхней крысы
    rc_diff.set_at((6, 6), (255, 220, 65))   # Светящийся жёлтый глаз верхней крысы
    rc_diff.set_at((8, 3), (205, 130, 138))  # Розовое ухо, торчащее из дырки в капюшоне

    # Плащ на плечах и НИЖНЯЯ КРЫСА, выглядывающая из распаха плаща на животе (y=10..18)
    for y in range(10, 18):
        for x in range(3, 13):
            if 11 <= y <= 14 and 4 <= x <= 8:
                # Вторая (нижняя) крыса выглядывает из распахнутого плаща!
                rc_diff.set_at((x, y), (112, 98, 92))
                rc_norm.set_at((x, y), (100, 160, 230, 255))
            else:
                col = (125, 28, 42) if x in (3, 12) or (x + y) % 4 == 0 else (98, 20, 32)
                rc_diff.set_at((x, y), col)
                rc_norm.set_at((x, y), (int(128 + (x - 8) * 12), 130, 220, 255))
    rc_diff.set_at((4, 12), (225, 135, 145))  # Розовый нос нижней крысы
    rc_diff.set_at((6, 12), (255, 95, 75))    # Глаз нижней крысы
    rc_diff.set_at((5, 14), (210, 145, 150))  # Лапки нижней крысы, держащие полы плаща
    rc_diff.set_at((8, 14), (210, 145, 150))
    # Лапы нижней крысы на полу и ДВА хвоста сзади!
    for lx in (5, 6, 9, 10):
        rc_diff.set_at((lx, 18), (195, 130, 135))
        rc_norm.set_at((lx, 18), (128, 150, 220, 255))
    for tx, ty in ((12, 16), (13, 15), (14, 14), (12, 18), (13, 18), (14, 17)):
        rc_diff.set_at((tx, ty), (205, 135, 140))
        rc_norm.set_at((tx, ty), (165, 155, 210, 255))
    assets["rat_cultist"] = (rc_diff, rc_norm)

    # 3. БОСС КРЫСИНЫЙ КОРОЛЬ 2x2 ТАЙЛА (`rat_king`, 32x36 пикселей)
    rk_diff, rk_norm = make_pair(32, 36)
    # Массивная зубчатая золотая корона с рубинами (y=2..8)
    for y in range(2, 9):
        for x in range(10, 22):
            if y >= 5 or x in (10, 11, 14, 15, 16, 17, 20, 21):
                col = (225, 40, 55) if (y == 6 and x in (12, 16, 19)) else ((255, 215, 70) if y < 7 else (205, 160, 42))
                rk_diff.set_at((x, y), col)
                rk_norm.set_at((x, y), (int(128 + (x - 15.5) * 8), 215, 235, 255))

    # Гигантская многоголовая туша в рваной королевской мантии (y=8..33)
    for y in range(8, 34):
        for x in range(3, 29):
            dist_body = math.hypot((x - 15.5) * 0.88, (y - 21.0) * 0.92)
            if dist_body <= 11.2:
                is_mantle = (y >= 13 and (x <= 7 or x >= 24 or (11 <= y <= 15 and 9 <= x <= 22)))
                if is_mantle:
                    col = (168, 30, 44) if (x + y) % 3 != 0 else (122, 20, 32)
                else:
                    fur = ((x * 19 + y * 31) % 5)
                    col = (132, 114, 108) if fur == 0 else ((112, 96, 90) if fur < 3 else (86, 72, 68))
                nx = int(np.clip(128 + (x - 15.5) * 7.5, 30, 225))
                ny = int(np.clip(128 - (y - 20.0) * 6.5, 40, 220))
                rk_diff.set_at((x, y), col)
                rk_norm.set_at((x, y), (nx, ny, 225, 255))

    # Пять оскаленных крысиных голов со светящимися глазами, носами и клыками
    heads = [(15, 10), (9, 13), (21, 13), (7, 19), (23, 19)]
    for hx, hy in heads:
        for dy_h in range(-1, 3):
            for dx_h in range(-2, 3):
                px_h, py_h = hx + dx_h, hy + dy_h
                if 2 <= px_h < 30 and 6 <= py_h < 32:
                    rk_diff.set_at((px_h, py_h), (138, 120, 114))
                    rk_norm.set_at((px_h, py_h), (128 + dx_h * 18, 195, 235, 255))
        rk_diff.set_at((hx - 1, hy), (255, 45, 45))      # Левый горящий глаз
        rk_diff.set_at((hx + 1, hy), (255, 45, 45))      # Правый горящий глаз
        rk_diff.set_at((hx, hy + 1), (225, 135, 145))    # Розовый нос
        rk_diff.set_at((hx - 1, hy + 2), (245, 240, 225)) # Белые резцы
        rk_diff.set_at((hx + 1, hy + 2), (245, 240, 225))

    # Клубок связанных крысиных хвостов у основания (y=31..35)
    for x in range(5, 27):
        ty = 32 + int(math.sin(x * 0.9) * 1.5)
        for dy_t in (0, 1):
            rk_diff.set_at((x, ty + dy_t), (205, 135, 142) if dy_t == 0 else (165, 100, 108))
            rk_norm.set_at((x, ty + dy_t), (128, 185 if dy_t == 0 else 95, 220, 255))
    assets["rat_king"] = (rk_diff, rk_norm)

    # 4. Трактирщик Гуго (`npc_innkeeper`, 16x20)
    np_diff, np_norm = make_pair(16, 20)
    for y in range(3, 19):
        for x in range(4, 12):
            if y <= 7 and 5 <= x <= 10:
                col = (115, 68, 38) if y >= 6 else (225, 180, 145)
                np_diff.set_at((x, y), col)
                np_norm.set_at((x, y), (int(128 + (x - 7.5) * 14), 195, 225, 255))
            elif y > 7:
                is_apron = (6 <= x <= 9 and 10 <= y <= 17)
                col = (225, 218, 195) if is_apron else (52, 110, 68)
                np_diff.set_at((x, y), col)
                np_norm.set_at((x, y), (int(128 + (x - 7.5) * 14), 135, 225, 255))
    np_diff.set_at((6, 4), (30, 25, 35))
    np_diff.set_at((9, 4), (30, 25, 35))
    assets["npc_innkeeper"] = (np_diff, np_norm)

    # 4b. Подпольный Скупщик Шнырь (`npc_merchant`, 16x20) — в плаще с капюшоном, золотыми очками и тюком за спиной
    me_diff, me_norm = make_pair(16, 20)
    for y in range(4, 17):
        for x in range(10, 15):
            me_diff.set_at((x, y), (145, 92, 42) if y % 3 != 0 else (195, 155, 65))
            me_norm.set_at((x, y), (210, 195, 200, 255))
    for y in range(3, 19):
        for x in range(3, 12):
            if y <= 8 and 4 <= x <= 10:
                col = (58, 42, 74) if (y <= 5 or x in (4, 10)) else (195, 165, 140)
                me_diff.set_at((x, y), col)
                me_norm.set_at((x, y), (45 if x < 6 else 128, 218 if y <= 5 else 128, 200, 255))
            elif y > 8:
                is_trim = (x in (5, 8) and 9 <= y <= 17)
                col = (225, 185, 70) if is_trim else ((68, 48, 86) if (x + y) % 2 == 0 else (48, 34, 64))
                me_diff.set_at((x, y), col)
                me_norm.set_at((x, y), (45 if x <= 5 else 128, 128, 200, 255))
    # Блестящие золотые пенсне-очки на носу
    me_diff.set_at((5, 6), (255, 225, 85))
    me_diff.set_at((8, 6), (255, 225, 85))
    assets["npc_merchant"] = (me_diff, me_norm)

    # 5. Трактирный стол с кружкой эля (`tavern_table`, 16x20)
    tt_diff, tt_norm = make_pair(16, 20)
    for y in range(8, 19):
        for x in range(1, 15):
            if 8 <= y <= 12:
                col = (138, 86, 44) if y < 11 else (96, 58, 28)
                if x in (1, 14) or y == 8:
                    col = (156, 100, 52)
                tt_diff.set_at((x, y), col)
                tt_norm.set_at((x, y), (128, 210 if y < 11 else 80, 230, 255))
            elif x in (2, 3, 12, 13):
                tt_diff.set_at((x, y), (82, 48, 24))
                tt_norm.set_at((x, y), (95 if x < 8 else 165, 128, 215, 255))
    # Кружка пенного эля на столе
    for y in range(5, 9):
        for x in range(5, 8):
            tt_diff.set_at((x, y), (245, 240, 215) if y == 5 else (215, 155, 45))
            tt_norm.set_at((x, y), (160, 195, 235, 255))
    assets["tavern_table"] = (tt_diff, tt_norm)

    # 6. Барная стойка Гуго (`bar_counter`, 16x20)
    bc_diff, bc_norm = make_pair(16, 20)
    for y in range(6, 19):
        for x in range(0, 16):
            if 6 <= y <= 9:
                col = (152, 96, 48) if y < 9 else (102, 62, 30)
                bc_diff.set_at((x, y), col)
                bc_norm.set_at((x, y), (128, 215 if y < 9 else 85, 235, 255))
            else:
                panel = (x in (3, 4, 11, 12) and 11 <= y <= 16)
                col = (78, 46, 24) if panel else (108, 66, 34)
                bc_diff.set_at((x, y), col)
                bc_norm.set_at((x, y), (128, 140, 220, 255))
    assets["bar_counter"] = (bc_diff, bc_norm)

    # 7. Большая горизонтальная винная бочка на козлах (`wine_cask`, 16x20)
    wc_p_diff, wc_p_norm = make_pair(16, 20)
    for y in range(6, 16):
        for x in range(2, 14):
            is_hoop = x in (4, 11)
            col = (85, 92, 105) if is_hoop else ((142, 82, 42) if y < 11 else (98, 54, 26))
            ny = int(np.clip(128 - (y - 10.5) * 16, 50, 215))
            wc_p_diff.set_at((x, y), col)
            wc_p_norm.set_at((x, y), (128, ny, 225, 255))
    for y in range(15, 19):
        for x in (4, 5, 10, 11):
            wc_p_diff.set_at((x, y), (72, 42, 22))
            wc_p_norm.set_at((x, y), (128, 128, 210, 255))
    wc_p_diff.set_at((2, 11), (225, 185, 70))
    assets["wine_cask"] = (wc_p_diff, wc_p_norm)

    # 8. Кровать с подушкой и одеялом (`bed`, 16x20) — плоская нормаль +Z на матрасе, чтобы была видна с любого ракурса!
    bd_diff, bd_norm = make_pair(16, 20)
    for y in range(4, 19):
        for x in range(2, 14):
            if y in (4, 5, 18) or x in (2, 13):
                col = (112, 68, 36) if y <= 5 else (92, 54, 28)
                nx, ny = (45 if x == 2 else (210 if x == 13 else 128)), (218 if y == 4 else 128)
            elif 6 <= y <= 9 and 4 <= x <= 11:
                col = (232, 224, 205)  # Подушка
                nx, ny = 128, 128
            else:
                col = (168, 48, 54) if y < 15 else (132, 36, 42)  # Одеяло
                nx, ny = 128, 128
            bd_diff.set_at((x, y), col)
            bd_norm.set_at((x, y), (nx, ny, 255, 255))
    assets["bed"] = (bd_diff, bd_norm)

    # 9. Каменный камин с огнём (`fireplace`, 16x20)
    fp_diff, fp_norm = make_pair(16, 20)
    for y in range(3, 19):
        for x in range(1, 15):
            in_hearth = (y >= 10 and 4 <= x <= 11)
            if not in_hearth:
                col = (92, 88, 102) if (x + y) % 3 != 0 else (68, 64, 76)
                if y in (3, 4, 9):
                    col = (115, 110, 125)
                fp_diff.set_at((x, y), col)
                fp_norm.set_at((x, y), (90 if x < 5 else (165 if x > 10 else 128), 195 if y <= 9 else 128, 225, 255))
            else:
                if y >= 16:
                    fp_diff.set_at((x, y), (75, 44, 24))
                elif (x - 7.5) ** 2 + (y - 14.0) ** 2 <= 9.5:
                    col = (255, 230, 110) if abs(x - 7.5) <= 1.5 and y >= 13 else (245, 115, 35)
                    fp_diff.set_at((x, y), col)
                    fp_norm.set_at((x, y), (128, 215, 245, 255))
                else:
                    fp_diff.set_at((x, y), (24, 20, 26))
    assets["fireplace"] = (fp_diff, fp_norm)

    # 10. Полка с бутылками (`shelf_bottles`, 16x20)
    sb_diff, sb_norm = make_pair(16, 20)
    for y in range(2, 19):
        for x in range(2, 14):
            if y in (2, 8, 13, 18) or x in (2, 13):
                sb_diff.set_at((x, y), (92, 56, 30))
                sb_norm.set_at((x, y), (128, 195 if y in (2, 8, 13) else 120, 220, 255))
            elif y in (5, 6, 7, 10, 11, 12, 15, 16, 17) and x in (4, 5, 7, 8, 10, 11):
                b_col = (55, 165, 95) if x in (4, 5) else ((195, 135, 45) if x in (7, 8) else (175, 45, 75))
                sb_diff.set_at((x, y), b_col)
                sb_norm.set_at((x, y), (160, 195, 235, 255))
    assets["shelf_bottles"] = (sb_diff, sb_norm)

    # 11. Деревянная скамья (`chair_bench`, 16x20)
    cb_diff, cb_norm = make_pair(16, 20)
    for y in range(11, 18):
        for x in range(3, 13):
            if y in (11, 12):
                cb_diff.set_at((x, y), (128, 78, 40))
                cb_norm.set_at((x, y), (128, 205, 225, 255))
            elif x in (4, 11):
                cb_diff.set_at((x, y), (82, 48, 24))
                cb_norm.set_at((x, y), (128, 128, 215, 255))
    assets["chair_bench"] = (cb_diff, cb_norm)

    # 12. Вешалка с плащом и шляпой (`coat_rack`, 16x20)
    cr_diff, cr_norm = make_pair(16, 20)
    for y in range(3, 19):
        if y == 18:
            for x in range(5, 11):
                cr_diff.set_at((x, y), (92, 56, 30))
                cr_norm.set_at((x, y), (128, 195, 220, 255))
        elif 7 <= y <= 15 and 5 <= x <= 9:
            pass
        cr_diff.set_at((7, y), (108, 66, 36))
        cr_norm.set_at((7, y), (128, 160, 225, 255))
    # Шляпа сверху и висящий зелёный плащ сбоку
    for x in range(5, 11):
        cr_diff.set_at((x, 4), (135, 92, 45))
        cr_norm.set_at((x, 4), (128, 210, 230, 255))
    for y in range(7, 16):
        for x in range(8, 12):
            cr_diff.set_at((x, y), (52, 108, 68) if x < 11 else (38, 82, 50))
            cr_norm.set_at((x, y), (160, 145, 225, 255))
    assets["coat_rack"] = (cr_diff, cr_norm)

    # 13. Чугунный котёл с похлёбкой (`cauldron`, 16x20)
    ca_diff, ca_norm = make_pair(16, 20)
    for y in range(8, 19):
        for x in range(3, 13):
            if (x - 7.5) ** 2 + (y - 13.5) ** 2 <= 22.0:
                if y in (8, 9):
                    col = (215, 165, 65) if 5 <= x <= 10 else (58, 62, 72)
                    ny = 215
                else:
                    col = (52, 56, 66) if abs(x - 7.5) < 3.2 else (36, 38, 46)
                    ny = int(np.clip(128 - (y - 13) * 14, 55, 205))
                nx = int(np.clip(128 + (x - 7.5) * 14, 45, 210))
                ca_diff.set_at((x, y), col)
                ca_norm.set_at((x, y), (nx, ny, 225, 255))
    assets["cauldron"] = (ca_diff, ca_norm)

    # 14. Автотайлинг ковра (12 фрагментов: центр, стороны, углы и полосы)
    carpet_configs = {
        "carpet_c":      (True,  True,  True,  True),
        "carpet_n":      (False, True,  True,  True),
        "carpet_s":      (True,  False, True,  True),
        "carpet_w":      (True,  True,  False, True),
        "carpet_e":      (True,  True,  True,  False),
        "carpet_nw":     (False, True,  False, True),
        "carpet_ne":     (False, True,  True,  False),
        "carpet_sw":     (True,  False, False, True),
        "carpet_se":     (True,  False, True,  False),
        "carpet_h":      (False, False, True,  True),
        "carpet_v":      (True,  True,  False, False),
        "carpet_single": (False, False, False, False),
    }
    for c_id, (hn, hs, hw, he) in carpet_configs.items():
        assets[c_id] = generate_carpet_tile_pair(hn, hs, hw, he)

    # 15. Сколоченные деревянные ящики (`crate_stack`, 16x20)
    cs_diff, cs_norm = make_pair(16, 20)
    for y in range(6, 19):
        for x in range(2, 14):
            is_frame = x in (2, 13) or y in (6, 18) or abs((x - 2) - (y - 6)) <= 1
            col = (132, 86, 44) if is_frame else (98, 62, 32)
            nx = 45 if x < 5 else (210 if x > 10 else 128)
            ny = 218 if y <= 8 else 128
            cs_diff.set_at((x, y), col)
            cs_norm.set_at((x, y), (nx, ny, 255, 255))
    assets["crate_stack"] = (cs_diff, cs_norm)

    # 16. Старинные напольные часы с маятником (`grandfather_clock`, 16x20)
    gc_d, gc_n = make_pair(16, 20)
    for y in range(2, 19):
        w_half = 4 if y in (2, 3, 17, 18) else 3
        for x in range(8 - w_half, 8 + w_half):
            if 4 <= y <= 7 and 6 <= x <= 9:
                col = (215, 205, 180) if (x, y) != (7, 5) else (40, 35, 45)
            elif 10 <= y <= 15 and 6 <= x <= 9:
                col = (195, 160, 65) if (x in (7, 8) and y in (12, 13)) else (32, 24, 28)
            else:
                col = (118, 68, 36) if x == 8 - w_half or y <= 3 else (86, 48, 24)
            nx = 45 if x <= 6 else (210 if x >= 9 else 128)
            ny = 218 if y <= 3 else 128
            gc_d.set_at((x, y), col)
            gc_n.set_at((x, y), (nx, ny, 255, 255))
    assets["grandfather_clock"] = (gc_d, gc_n)

    # 17. Трофейная голова вепря на щите (`mounted_boar`, 16x20)
    mb_d, mb_n = make_pair(16, 20)
    for y in range(4, 15):
        for x in range(4, 12):
            if (x - 7.5) ** 2 + (y - 9.0) ** 2 <= 18.0:
                mb_d.set_at((x, y), (125, 76, 38))
                mb_n.set_at((x, y), (128, 218 if y < 7 else 128, 200, 255))
    for y in range(6, 14):
        for x in range(5, 11):
            mb_d.set_at((x, y), (78, 56, 44) if y < 11 else (62, 44, 34))
            mb_n.set_at((x, y), (45 if x < 7 else (210 if x > 8 else 128), 218 if y <= 8 else 38, 200, 255))
    mb_d.set_at((4, 11), (235, 230, 210))
    mb_d.set_at((11, 11), (235, 230, 210))
    mb_d.set_at((6, 8), (195, 45, 45))
    mb_d.set_at((9, 8), (195, 45, 45))
    assets["mounted_boar"] = (mb_d, mb_n)

    # 18. Доска объявлений и розыска (`notice_board`, 16x20)
    nb_d, nb_n = make_pair(16, 20)
    for y in range(3, 19):
        for x in range(2, 14):
            if y < 14:
                is_border = x in (2, 13) or y in (3, 13)
                col = (92, 56, 30) if is_border else (68, 42, 22)
                if (4 <= x <= 7 and 5 <= y <= 9) or (9 <= x <= 11 and 6 <= y <= 11):
                    col = (218, 205, 175) if y % 2 == 0 else (185, 170, 140)
                nb_d.set_at((x, y), col)
                nb_n.set_at((x, y), (128, 218 if y == 3 else 128, 255, 255))
            elif x in (3, 12):
                nb_d.set_at((x, y), (78, 46, 24))
                nb_n.set_at((x, y), (128, 128, 255, 255))
    assets["notice_board"] = (nb_d, nb_n)

    # 19. Забытая лютня барда на подставке (`lute_stand`, 16x20)
    ls_d, ls_n = make_pair(16, 20)
    for y in range(4, 18):
        if 4 <= y <= 10:
            ls_d.set_at((8, y), (92, 56, 30))
            ls_n.set_at((8, y), (128, 218, 200, 255))
        if 10 <= y <= 17:
            for x in range(5, 12):
                if (x - 8.0) ** 2 + (y - 13.5) ** 2 <= 10.5:
                    col = (42, 32, 26) if (x == 8 and y in (12, 13)) else ((168, 108, 52) if x <= 8 else (128, 78, 36))
                    ls_d.set_at((x, y), col)
                    ls_n.set_at((x, y), (45 if x < 8 else 210, 218 if y < 13 else 128, 200, 255))
    assets["lute_stand"] = (ls_d, ls_n)

    # 20. Деревянная бадья для умывания (`wash_basin`, 16x20)
    wb_d, wb_n = make_pair(16, 20)
    for y in range(9, 19):
        for x in range(3, 13):
            if y in (9, 10):
                col = (65, 135, 175) if 5 <= x <= 10 else (122, 76, 38)
                wb_d.set_at((x, y), col)
                wb_n.set_at((x, y), (128, 218, 200, 255))
            else:
                is_hoop = y in (12, 16)
                col = (78, 84, 96) if is_hoop else ((112, 68, 34) if x < 8 else (88, 52, 26))
                if x in (11, 12) and 10 <= y <= 14:
                    col = (220, 212, 195)  # Белый рушник через край бадьи
                wb_d.set_at((x, y), col)
                wb_n.set_at((x, y), (45 if x < 6 else (210 if x > 9 else 128), 128, 200, 255))
    assets["wash_basin"] = (wb_d, wb_n)

    # 21. Вешала с копчёными окороками (`meat_rack`, 16x20)
    mr_d, mr_n = make_pair(16, 20)
    for y in range(3, 19):
        for x in range(2, 14):
            if y == 4 or x in (3, 12):
                mr_d.set_at((x, y), (88, 54, 28))
                mr_n.set_at((x, y), (128, 218 if y == 4 else 128, 200, 255))
            elif 6 <= y <= 14 and x in (5, 6, 7, 9, 10):
                col = (225, 215, 195) if y in (6, 7) else ((165, 68, 52) if y < 12 else (128, 48, 36))
                mr_d.set_at((x, y), col)
                mr_n.set_at((x, y), (45 if x in (5, 9) else 210, 218 if y <= 8 else 128, 200, 255))
    assets["meat_rack"] = (mr_d, mr_n)

    # 22. Поленница берёзовых дров (`firewood_pile`, 16x20)
    fw_d, fw_n = make_pair(16, 20)
    logs_xy = [(3, 16), (7, 16), (11, 16), (5, 13), (9, 13), (7, 10)]
    for lx, ly in logs_xy:
        for dy_l in range(3):
            for dx_l in range(4):
                is_end = (dx_l in (0, 1) and dy_l in (1, 2))
                col = (195, 160, 110) if is_end else ((215, 210, 200) if (lx + dy_l) % 2 == 0 else (112, 72, 38))
                fw_d.set_at((lx + dx_l, ly + dy_l), col)
                fw_n.set_at((lx + dx_l, ly + dy_l), (45 if is_end else 128, 218 if dy_l == 0 else 128, 200, 255))
    assets["firewood_pile"] = (fw_d, fw_n)

    # 23. Старый рыцарский доспех на стойке (`armor_stand`, 16x20)
    as_d, as_n = make_pair(16, 20)
    for y in range(2, 19):
        for x in range(4, 12):
            if 2 <= y <= 6 and 6 <= x <= 9:
                col = (28, 26, 34) if y == 4 else (175, 185, 202)
                as_d.set_at((x, y), col)
                as_n.set_at((x, y), (45 if x <= 6 else 210, 218 if y <= 3 else 128, 200, 255))
            elif 7 <= y <= 14 and 4 <= x <= 11:
                col = (185, 195, 212) if y <= 10 else (142, 152, 168)
                as_d.set_at((x, y), col)
                as_n.set_at((x, y), (45 if x <= 6 else (210 if x >= 9 else 128), 218 if y <= 8 else 128, 200, 255))
            elif y >= 15 and x in (7, 8):
                as_d.set_at((x, y), (92, 56, 30))
                as_n.set_at((x, y), (128, 128, 200, 255))
    assets["armor_stand"] = (as_d, as_n)

    bk_diff, bk_norm = make_pair(16, 20)
    for y in range(2, 19):
        for x in range(2, 14):
            col = (95, 60, 35)
            if y in (6, 11, 16) or x in (2, 13):
                col = (70, 42, 24)
            elif 3 <= x <= 12:
                book_cols = [(185, 55, 60), (55, 125, 185), (65, 165, 85), (195, 165, 65)]
                col = book_cols[(x + y // 5) % 4]
            bk_diff.set_at((x, y), col)
            bk_norm.set_at((x, y), (128, 200 if y % 5 == 0 else 128, 225))
    assets["bookshelf"] = (bk_diff, bk_norm)

    al_diff, al_norm = make_pair(16, 20)
    for y in range(6, 19):
        for x in range(2, 14):
            if y >= 12:
                if y in (12, 13) or x in (3, 12):
                    al_diff.set_at((x, y), (110, 72, 42))
                    al_norm.set_at((x, y), (128, 205, 220))
            else:
                if x in (5, 6):
                    al_diff.set_at((x, y), (80, 235, 145))
                    al_norm.set_at((x, y), (160, 210, 240))
                elif x in (9, 10) and y >= 8:
                    al_diff.set_at((x, y), (235, 75, 165))
                    al_norm.set_at((x, y), (160, 210, 240))
    assets["alchemy"] = (al_diff, al_norm)

    rk_diff, rk_norm = make_pair(16, 20)
    for y in range(4, 19):
        for x in range(3, 13):
            if x in (4, 11) or y in (8, 16):
                rk_diff.set_at((x, y), (105, 70, 40))
                rk_norm.set_at((x, y), (128, 190, 220))
            elif x in (7, 8) and 4 <= y <= 15:
                rk_diff.set_at((x, y), (195, 205, 220))
                rk_norm.set_at((x, y), (165, 195, 235))
    assets["rack"] = (rk_diff, rk_norm)

    tp_diff, tp_norm = make_pair(16, 20)
    for y in range(13, 19):
        for x in range(3, 13):
            if (x + y) % 3 == 0:
                tp_diff.set_at((x, y), (185, 190, 205))
                tp_norm.set_at((x, y), (128, 220, 235))
    assets["trap"] = (tp_diff, tp_norm)

    st_diff, st_norm = make_pair(16, 20)
    for y in range(6, 19):
        for x in range(2, 14):
            step_idx = (y - 6) // 3
            col = max(12, 65 - step_idx * 12)
            st_diff.set_at((x, y), (col, col, col + 10))
            st_norm.set_at((x, y), (128, 210 if (y - 6) % 3 == 0 else 80, 210))
    assets["stairs"] = (st_diff, st_norm)

    br_diff, br_norm = make_pair(16, 20)
    for y in range(7, 19):
        for x in range(4, 12):
            if y < 11:
                col = (255, 190, 70) if (x + y) % 2 == 0 else (255, 110, 40)
                br_diff.set_at((x, y), col)
                br_norm.set_at((x, y), (128, 220, 240))
            elif y >= 11 and 5 <= x <= 10:
                br_diff.set_at((x, y), (75, 70, 85))
                br_norm.set_at((x, y), (75 if x < 7 else 180, 160, 220))
    assets["brazier"] = (br_diff, br_norm)

    from elenor.rendering.merchant import register_merchant_assets
    register_merchant_assets(assets)

    from elenor.rendering.mirrors import register_mirror_puzzle_assets
    register_mirror_puzzle_assets(assets)

    from elenor.rendering.jungle import register_jungle_assets
    register_jungle_assets(assets)

    from elenor.rendering.fishing import register_fishing_assets
    register_fishing_assets(assets)

    from elenor.rendering.jungle_bestiary import register_jungle_bestiary_assets
    register_jungle_bestiary_assets(assets)
    from elenor.rendering.jungle_fixtures import register_jungle_fixtures
    register_jungle_fixtures(assets, make_pair)

    from elenor.data.textures import bootstrap_assets_if_needed, load_custom_dtex_animations

    bootstrap_assets_if_needed(assets, build_hero_sprite)
    anim_bank = load_custom_dtex_animations(assets)

    # Enforce crisp contour vs chest normals on all upright 16x20 & 24x38 sprites!
    for k, pair in list(assets.items()):
        if isinstance(pair, tuple) and len(pair) == 2 and pair[0].get_height() > 16 and k != "thought_zone":
            assets[k] = enforce_crisp_rim_normals(pair[0], pair[1])
    for role_id, a_info in anim_bank.items():
        if a_info["frames"] and a_info["frames"][0][0].get_height() > 16:
            a_info["frames"] = [enforce_crisp_rim_normals(d, n) for d, n in a_info["frames"]]

    assets["_anim_bank"] = anim_bank
    return assets


