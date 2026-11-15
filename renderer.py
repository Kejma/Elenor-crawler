import math
import pygame
import numpy as np
from config import (
    TILE_W, TILE_H, SPRITE_W, SPRITE_H,
    VIEW_W, VIEW_H, THOUGHT_ZONE_H, CANVAS_H,
    THOUGHT_BOX_W, THOUGHT_BOX_H, THOUGHT_BOX_X, THOUGHT_BOX_Y,
    SCALE, SCREEN_W, SCREEN_H, HUD_HEIGHT, MAP_COLS, MAP_ROWS,
    UI_BG_DARK, UI_PANEL_BG, UI_SLOT_BG, UI_BORDER_OUTER,
    UI_BORDER_WOOD, UI_BORDER_GOLD, UI_BORDER_HIGHLIGHT,
    UI_TEXT_MAIN, UI_TEXT_DIM
)


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
    from studio_core import quantize_normal_surface
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

    # 14. Уютный потёртый домотканый ковёр с бахромой (`woven_rug`, 16x20) — спокойные тёплые тона без свечения!
    wr_diff, wr_norm = make_pair(16, 20)
    for y in range(5, 18):
        for x in range(1, 15):
            if x in (1, 14):
                # Мягкая нитяная бахрома по краям ковра (через строчку)
                if y % 2 == 0:
                    wr_diff.set_at((x, y), (128, 108, 82))
                    wr_norm.set_at((x, y), (128, 128, 255, 255))
                continue
            weave = ((x + y) % 2) * 6
            if x in (2, 13) or y in (5, 17):
                col = (76 - weave, 46 - weave // 2, 34)
            elif x in (4, 11) or y in (7, 15):
                col = (138 - weave, 96 - weave, 52)
            elif abs(x - 7.5) + abs(y - 11.0) <= 2.6:
                col = (146 - weave, 104 - weave, 56) if (abs(x - 7.5) + abs(y - 11.0) >= 1.5) else (68, 88, 76)
            else:
                col = (112 - weave, 34 - weave // 2, 38)
            wr_diff.set_at((x, y), col)
            wr_norm.set_at((x, y), (128, 128, 255, 255))
    assets["woven_rug"] = (wr_diff, wr_norm)

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

    from dtex_format import bootstrap_assets_if_needed, load_custom_dtex_animations
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


class GPULightShader:
    """Аппаратный 2.5D-шейдер освещения, нормалей, AO, точечного Emissive Bloom и 3D-Объёмного Тумана."""
    MAX_LIGHTS = 48
    MAX_HUD_LIGHTS = 32
    MAX_FOGS = 16

    def __init__(self):
        import moderngl
        self.moderngl = moderngl
        self.ctx = moderngl.create_standalone_context()

        self.tex_diff = self.ctx.texture((VIEW_W, CANVAS_H), 3, dtype="f1")
        self.tex_norm = self.ctx.texture((VIEW_W, CANVAS_H), 3, dtype="f1")
        self.tex_ent_y = self.ctx.texture((VIEW_W, CANVAS_H), 1, dtype="f4")
        self.tex_fov = self.ctx.texture((VIEW_W, CANVAS_H), 1, dtype="f4")
        self.tex_masks = self.ctx.texture((MAP_COLS, MAP_ROWS * self.MAX_LIGHTS), 1, dtype="f4")
        self.tex_walls = self.ctx.texture((MAP_COLS, MAP_ROWS), 1, dtype="f4")
        self.tex_emissive = self.ctx.texture((VIEW_W, CANVAS_H), 1, dtype="f1")
        self.tex_out = self.ctx.texture((VIEW_W, CANVAS_H), 3, dtype="f1")

        for tex in (self.tex_diff, self.tex_norm, self.tex_ent_y, self.tex_fov, self.tex_masks, self.tex_walls, self.tex_emissive, self.tex_out):
            tex.filter = (moderngl.NEAREST, moderngl.NEAREST)

        self.fbo = self.ctx.framebuffer(color_attachments=[self.tex_out])

        self.prog = self.ctx.program(
            vertex_shader="""
            #version 330 core
            in vec2 in_vert;
            void main() {
                gl_Position = vec4(in_vert, 0.0, 1.0);
            }
            """,
            fragment_shader=f"""
            #version 330 core
            uniform sampler2D u_diff;
            uniform sampler2D u_norm;
            uniform sampler2D u_ent_y;
            uniform sampler2D u_fov;
            uniform sampler2D u_light_masks;
            uniform sampler2D u_walls;
            uniform sampler2D u_emissive;

            uniform vec2 u_cam;
            uniform float u_time;
            uniform vec3 u_fx_flags; // x = enable_ao, y = enable_bloom, z = enable_fog
            uniform int u_num_lights;
            uniform vec4 u_light_pos_rad[{self.MAX_LIGHTS}];
            uniform vec4 u_light_col_foot[{self.MAX_LIGHTS}];
            uniform vec2 u_light_flags[{self.MAX_LIGHTS}];

            uniform int u_num_fogs;
            uniform vec4 u_fog_pos_rad[{self.MAX_FOGS}];
            uniform vec4 u_fog_col_dens[{self.MAX_FOGS}];

            uniform int u_num_hud_lights;
            uniform vec4 u_hud_pos_rad[{self.MAX_HUD_LIGHTS}];
            uniform vec4 u_hud_col[{self.MAX_HUD_LIGHTS}];

            out vec3 fragColor;

            float sample_light_mask_smooth(int light_idx, float wx_px, float wy_px) {{
                float gx = wx_px / {float(TILE_W)} - 0.5;
                float gy = wy_px / {float(TILE_H)} - 0.5;
                int x0 = clamp(int(floor(gx)), 0, {MAP_COLS - 1});
                int y0 = clamp(int(floor(gy)), 0, {MAP_ROWS - 1});
                int x1 = clamp(x0 + 1, 0, {MAP_COLS - 1});
                int y1 = clamp(y0 + 1, 0, {MAP_ROWS - 1});
                float fx = fract(gx);
                float fy = fract(gy);
                int base_y = light_idx * {MAP_ROWS};
                float m00 = texelFetch(u_light_masks, ivec2(x0, base_y + y0), 0).r;
                float m10 = texelFetch(u_light_masks, ivec2(x1, base_y + y0), 0).r;
                float m01 = texelFetch(u_light_masks, ivec2(x0, base_y + y1), 0).r;
                float m11 = texelFetch(u_light_masks, ivec2(x1, base_y + y1), 0).r;
                return mix(mix(m00, m10, fx), mix(m01, m11, fx), fy);
            }}

            float volumetric_fog_noise(vec2 wp, float t) {{
                float n1 = sin(wp.x * 0.17 + t * 1.3 + cos(wp.y * 0.14 - t * 0.9));
                float n2 = cos(wp.y * 0.23 - t * 1.1 + sin(wp.x * 0.21 + t * 0.8));
                float n3 = sin((wp.x + wp.y) * 0.31 - t * 1.7) * 0.5;
                return clamp((n1 + n2 + n3) * 0.22 + 0.58, 0.15, 1.0);
            }}

            void main() {{
                ivec2 p = ivec2(gl_FragCoord.xy);
                vec3 diff = texelFetch(u_diff, p, 0).rgb;
                vec3 norm_raw = texelFetch(u_norm, p, 0).rgb * 255.0;
                vec3 N = (norm_raw - 128.0) / 127.0;

                if (p.y < {VIEW_H}) {{
                    float ent_y = texelFetch(u_ent_y, p, 0).r;
                    float fov = texelFetch(u_fov, p, 0).r;

                    float sub_rim = 0.0;
                    if (ent_y > -9000.0 && p.x > 0 && p.x < {VIEW_W - 1} && p.y > 0 && p.y < {VIEW_H - 1}) {{
                        bool l_out = texelFetch(u_ent_y, p + ivec2(-1, 0), 0).r <= -9000.0;
                        bool r_out = texelFetch(u_ent_y, p + ivec2( 1, 0), 0).r <= -9000.0;
                        bool u_out = texelFetch(u_ent_y, p + ivec2( 0,-1), 0).r <= -9000.0;
                        bool d_out = texelFetch(u_ent_y, p + ivec2( 0, 1), 0).r <= -9000.0;
                        if (l_out || r_out || u_out || d_out) sub_rim = 1.0;
                    }}

                    float wx_px = float(p.x) + u_cam.x;
                    float wy_px = float(p.y) + u_cam.y;
                    int tx = clamp(int(floor(wx_px / {float(TILE_W)})), 0, {MAP_COLS - 1});
                    int ty = clamp(int(floor(wy_px / {float(TILE_H)})), 0, {MAP_ROWS - 1});

                    float is_wall_tile = texelFetch(u_walls, ivec2(tx, ty), 0).r;

                    // 1. FAKE AMBIENT OCCLUSION
                    float ao_mult = 1.0;
                    if (u_fx_flags.x > 0.5 && ent_y <= -9000.0 && is_wall_tile < 0.5) {{
                        float lx_t = mod(wx_px, {float(TILE_W)});
                        float ly_t = mod(wy_px, {float(TILE_H)});
                        float occ = 0.0;
                        if (ty > 0 && texelFetch(u_walls, ivec2(tx, ty - 1), 0).r > 0.5 && ly_t < 4.5) {{
                            occ = max(occ, (4.5 - ly_t) / 4.5 * 0.42);
                        }}
                        if (ty < {MAP_ROWS - 1} && texelFetch(u_walls, ivec2(tx, ty + 1), 0).r > 0.5 && ly_t > 12.5) {{
                            occ = max(occ, (ly_t - 12.5) / 3.5 * 0.28);
                        }}
                        if (tx > 0 && texelFetch(u_walls, ivec2(tx - 1, ty), 0).r > 0.5 && lx_t < 3.5) {{
                            occ = max(occ, (3.5 - lx_t) / 3.5 * 0.32);
                        }}
                        if (tx < {MAP_COLS - 1} && texelFetch(u_walls, ivec2(tx + 1, ty), 0).r > 0.5 && lx_t > 12.5) {{
                            occ = max(occ, (lx_t - 12.5) / 3.5 * 0.32);
                        }}
                        if (p.x > 1 && p.x < {VIEW_W - 2} && p.y > 2 && p.y < {VIEW_H - 2}) {{
                            float near_ent = 0.0;
                            if (texelFetch(u_ent_y, p + ivec2(0, -1), 0).r > -9000.0) near_ent = 0.26;
                            else if (texelFetch(u_ent_y, p + ivec2(0, -2), 0).r > -9000.0) near_ent = 0.14;
                            occ = max(occ, near_ent);
                        }}
                        ao_mult = 1.0 - occ;
                    }}

                    vec3 mult = vec3(0.0);
                    vec3 rim_add = vec3(0.0);

                    for (int i = 0; i < u_num_lights; ++i) {{
                        vec4 pos_rad = u_light_pos_rad[i];
                        float rad = pos_rad.w;
                        float dx = pos_rad.x - float(p.x);
                        float dy = -(pos_rad.y - float(p.y));
                        if (abs(dx) > rad + 2.0 || abs(dy) > rad + 2.0) continue;

                        vec2 flags = u_light_flags[i];
                        float mask_w = 1.0;
                        if (flags.y > 0.5) {{
                            mask_w = sample_light_mask_smooth(i, wx_px, wy_px);
                            if (mask_w < 0.02) continue;
                        }}

                        float lz = pos_rad.z;
                        float dist = sqrt(dx * dx + dy * dy + lz * lz);
                        if (dist >= rad) continue;

                        vec4 col_foot = u_light_col_foot[i];
                        float behind_ratio = 0.0;
                        if (flags.x < 0.5 && ent_y > -9000.0) {{
                            behind_ratio = clamp((ent_y - col_foot.w) / 4.5, 0.0, 1.0);
                        }}

                        float inv_dist = 1.0 / max(dist, 0.001);
                        float raw_dot = N.x * (dx * inv_dist) + N.y * (dy * inv_dist) + N.z * (lz * inv_dist);
                        float z_wrap = max(0.0, N.z * (lz * inv_dist)) * 0.65;
                        float ndotl = max(z_wrap, raw_dot);
                        float atten = clamp(1.0 - pow(dist / rad, 1.65), 0.0, 1.0) * mask_w;

                        float front_shade = 1.0 - behind_ratio * (1.0 - sub_rim) * 0.65;
                        float intensity = ndotl * atten * 1.45 * front_shade;
                        mult += intensity * col_foot.rgb;

                        if (flags.x < 0.5 && sub_rim > 0.5 && behind_ratio > 0.01) {{
                            float dist_2d = sqrt(dx * dx + dy * dy);
                            float close_fall = pow(clamp(1.0 - dist_2d / min(rad * 0.72, 48.0), 0.0, 1.0), 2.4) * mask_w;
                            float rim_boost = sub_rim * behind_ratio * close_fall * (145.0 / 255.0);
                            rim_add += rim_boost * col_foot.rgb;
                        }}
                    }}

                    // 2. СТРОГИЙ EMISSIVE BLOOM (свечение ТОЛЬКО там, где стоит метка в u_emissive: глаза мобов и огонь!)
                    vec3 bloom_add = vec3(0.0);
                    if (u_fx_flags.y > 0.5 && fov > 0.05) {{
                        float self_em = texelFetch(u_emissive, p, 0).r;
                        if (self_em > 0.1) {{
                            mult = max(mult, vec3(1.35 * self_em));
                        }}
                        if (p.x > 2 && p.x < {VIEW_W - 3} && p.y > 2 && p.y < {VIEW_H - 3}) {{
                            vec3 glow_sum = vec3(0.0);
                            for (int oy = -2; oy <= 2; oy += 1) {{
                                for (int ox = -2; ox <= 2; ox += 1) {{
                                    float em_n = texelFetch(u_emissive, p + ivec2(ox, oy), 0).r;
                                    if (em_n > 0.1) {{
                                        vec3 nc = texelFetch(u_diff, p + ivec2(ox, oy), 0).rgb;
                                        float w_d = 1.0 / (1.0 + float(ox * ox + oy * oy));
                                        glow_sum += nc * em_n * w_d;
                                    }}
                                }}
                            }}
                            bloom_add = glow_sum * 0.085 * fov;
                        }}
                    }}

                    mult *= fov * ao_mult;
                    rim_add *= fov;
                    vec3 base_c = diff * mult + bloom_add;
                    vec3 lit_out = vec3(
                        rim_add.r > (0.5 / 255.0) ? min(228.0 / 255.0, base_c.r * 1.25 + rim_add.r) : base_c.r,
                        rim_add.g > (0.5 / 255.0) ? min(222.0 / 255.0, base_c.g * 1.25 + rim_add.g) : base_c.g,
                        rim_add.b > (0.5 / 255.0) ? min(220.0 / 255.0, base_c.b * 1.25 + rim_add.b) : base_c.b
                    );

                    // 3. 3D ОБЪЁМНЫЙ ТУМАН С РАССЕИВАНИЕМ СВЕТА ПО ГРЕБНЯМ КЛУБОВ ДЫМА
                    if (u_fx_flags.z > 0.5 && fov > 0.05 && is_wall_tile < 0.5) {{
                        vec2 wp = vec2(wx_px, wy_px);
                        float wisp = volumetric_fog_noise(wp, u_time);
                        // Вычисляем 3D-нормаль каждого клуба тумана по градиенту плотности!
                        float w_rx = volumetric_fog_noise(wp + vec2(2.5, 0.0), u_time);
                        float w_uy = volumetric_fog_noise(wp - vec2(0.0, 2.5), u_time);
                        vec3 fog_N = normalize(vec3((wisp - w_rx) * 3.2, (w_uy - wisp) * 3.2, 0.52));

                        float height_mask = 1.0;
                        if (ent_y > -9000.0) {{
                            float h_above_feet = max(0.0, ent_y - float(p.y));
                            height_mask = clamp(1.0 - (h_above_feet - 3.0) / 9.0, 0.12, 1.0);
                        }}
                        for (int f = 0; f < u_num_fogs; ++f) {{
                            vec4 f_pr = u_fog_pos_rad[f];
                            float f_rad = f_pr.z;
                            float f_dist = distance(wp, f_pr.xy);
                            if (f_dist < f_rad) {{
                                vec4 f_cd = u_fog_col_dens[f];
                                float radial = pow(1.0 - f_dist / f_rad, 1.30);
                                float fog_alpha = clamp(radial * wisp * f_cd.w * height_mask, 0.0, 0.82);

                                // Считаем объёмное рассеивание света внутри тумана (гребни клубов вспыхивают со стороны факела!)
                                vec3 vol_light = (f_pr.w > 0.5) ? vec3(0.28, 0.52, 0.28) : vec3(0.10, 0.13, 0.20);
                                for (int i = 0; i < u_num_lights; ++i) {{
                                    vec4 l_pr = u_light_pos_rad[i];
                                    float l_rad = l_pr.w * 1.15;
                                    float l_dx = l_pr.x - float(p.x);
                                    float l_dy = -(l_pr.y - float(p.y));
                                    float l_d2 = sqrt(l_dx * l_dx + l_dy * l_dy);
                                    if (l_d2 < l_rad) {{
                                        float m_w = (u_light_flags[i].y > 0.5) ? sample_light_mask_smooth(i, wx_px, wy_px) : 1.0;
                                        if (m_w > 0.02) {{
                                            vec3 L_dir = normalize(vec3(l_dx, l_dy, 14.0));
                                            // Обращённый к свету край клуба дыма ярко бликует, а тыльная сторона клуба в тени!
                                            float puff_shade = clamp(dot(fog_N, L_dir) * 0.65 + 0.45, 0.15, 1.35);
                                            float scatter = pow(1.0 - l_d2 / l_rad, 1.45) * m_w;
                                            // Ореол рассеивания (Mie halo) вблизи источника света
                                            float halo = pow(clamp(1.0 - l_d2 / (l_rad * 0.55), 0.0, 1.0), 2.0) * 0.55;
                                            vol_light += u_light_col_foot[i].rgb * scatter * (puff_shade * 1.15 + halo);
                                        }}
                                    }}
                                }}
                                vec3 fog_lit = clamp(f_cd.rgb * vol_light, 0.0, 1.45);
                                lit_out = mix(lit_out, fog_lit, fog_alpha * fov);
                            }}
                        }}
                    }}

                    fragColor = clamp(lit_out, 0.0, 1.0);
                }} else {{
                    vec3 mult = vec3(0.74, 0.74, 0.80);
                    vec3 hud_glow = vec3(0.0);
                    for (int j = 0; j < u_num_hud_lights; ++j) {{
                        vec4 h_pos = u_hud_pos_rad[j];
                        float rad = h_pos.w;
                        float dx = h_pos.x - float(p.x);
                        float dy = -(h_pos.y - float(p.y));
                        if (abs(dx) > rad + 2.0) continue;
                        float dist_2d = sqrt(dx * dx + dy * dy);
                        if (dist_2d >= rad) continue;

                        float lz = h_pos.z;
                        float dist_3d = sqrt(dx * dx + dy * dy + lz * lz);
                        float inv_dist = 1.0 / max(dist_3d, 0.001);
                        float ndotl = max(0.0, N.x * (dx * inv_dist) + N.y * (dy * inv_dist) + N.z * (lz * inv_dist));
                        float atten = clamp(1.0 - pow(dist_2d / rad, 1.6), 0.0, 1.0);
                        vec3 h_col = u_hud_col[j].rgb;
                        mult += (ndotl * atten * 0.40) * h_col;
                        hud_glow += (pow(atten, 1.8) * (12.0 / 255.0)) * h_col;
                    }}
                    fragColor = clamp(diff * mult + hud_glow, 0.0, 1.0);
                }}
            }}
            """
        )

        self.prog["u_diff"].value = 0
        self.prog["u_norm"].value = 1
        self.prog["u_ent_y"].value = 2
        self.prog["u_fov"].value = 3
        self.prog["u_light_masks"].value = 4
        self.prog["u_walls"].value = 5
        self.prog["u_emissive"].value = 6

        quad = np.array([-1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0], dtype=np.float32)
        self.vbo = self.ctx.buffer(quad.tobytes())
        self.vao = self.ctx.simple_vertex_array(self.prog, self.vbo, "in_vert")

        self.pos_rad_buf = np.zeros((self.MAX_LIGHTS, 4), dtype=np.float32)
        self.col_foot_buf = np.zeros((self.MAX_LIGHTS, 4), dtype=np.float32)
        self.flags_buf = np.zeros((self.MAX_LIGHTS, 2), dtype=np.float32)
        self.masks_buf = np.zeros((self.MAX_LIGHTS, MAP_ROWS, MAP_COLS), dtype=np.float32)

        self.fog_pos_buf = np.zeros((self.MAX_FOGS, 4), dtype=np.float32)
        self.fog_col_buf = np.zeros((self.MAX_FOGS, 4), dtype=np.float32)

        self.hud_pos_buf = np.zeros((self.MAX_HUD_LIGHTS, 4), dtype=np.float32)
        self.hud_col_buf = np.zeros((self.MAX_HUD_LIGHTS, 4), dtype=np.float32)

    def render_lit_surface(self, diff_canvas, norm_canvas, entity_y_canvas, fov_mask, cam_x, cam_y, lights, hud_lights, wall_grid_np=None, emissive_canvas=None, enable_ao=True, enable_bloom=True, enable_fog=True, active_clouds=None, now_sec=0.0):
        self.tex_diff.write(pygame.image.tobytes(diff_canvas, "RGB"))
        self.tex_norm.write(pygame.image.tobytes(norm_canvas, "RGB"))
        self.tex_ent_y.write(np.ascontiguousarray(entity_y_canvas.T, dtype=np.float32).tobytes())
        self.tex_fov.write(np.ascontiguousarray(fov_mask.T, dtype=np.float32).tobytes())
        if wall_grid_np is not None:
            self.tex_walls.write(np.ascontiguousarray(wall_grid_np.T, dtype=np.float32).tobytes())
        if emissive_canvas is not None:
            em_arr = pygame.surfarray.array3d(emissive_canvas)[:, :, 0].T
            self.tex_emissive.write(np.ascontiguousarray(em_arr, dtype=np.uint8).tobytes())

        n_lgt = min(len(lights), self.MAX_LIGHTS)
        self.pos_rad_buf.fill(0.0)
        self.col_foot_buf.fill(0.0)
        self.flags_buf.fill(0.0)

        any_masks = False
        for i in range(n_lgt):
            lgt = lights[i]
            lx, ly, lz = lgt["pos"]
            cr, cg, cb = lgt["color"]
            self.pos_rad_buf[i] = (lx, ly, lz, lgt["radius"])
            self.col_foot_buf[i] = (cr, cg, cb, lgt.get("foot_y", ly + 4.0))
            ign_d = 1.0 if lgt.get("ignore_depth", False) else 0.0
            allowed = lgt.get("allowed_tiles")
            if isinstance(allowed, np.ndarray):
                self.flags_buf[i] = (ign_d, 1.0)
                self.masks_buf[i] = allowed.T
                any_masks = True
            else:
                self.flags_buf[i] = (ign_d, 0.0)

        if any_masks:
            self.tex_masks.write(self.masks_buf.tobytes())

        clouds = active_clouds or []
        n_fog = min(len(clouds), self.MAX_FOGS)
        self.fog_pos_buf.fill(0.0)
        self.fog_col_buf.fill(0.0)
        for f_i in range(n_fog):
            cld = clouds[f_i]
            fade = 1.0
            if cld.get("timer") is not None and cld.get("max_timer"):
                fade = min(1.0, cld["timer"] / min(1.2, cld["max_timer"]))
            is_p = 1.0 if cld.get("kind") == "poison" else 0.0
            self.fog_pos_buf[f_i] = (cld["wx"] * TILE_W, cld["wy"] * TILE_H, cld["radius"] * TILE_W, is_p)
            fc = cld["color"]
            self.fog_col_buf[f_i] = (fc[0], fc[1], fc[2], cld.get("density", 0.5) * fade)

        n_hud = min(len(hud_lights), self.MAX_HUD_LIGHTS)
        self.hud_pos_buf.fill(0.0)
        self.hud_col_buf.fill(0.0)
        for j in range(n_hud):
            hl = hud_lights[j]
            hx, hy, hz = hl["pos"]
            hcr, hcg, hcb = hl["color"]
            self.hud_pos_buf[j] = (hx, hy, hz, hl["radius"])
            self.hud_col_buf[j] = (hcr, hcg, hcb, 1.0)

        self.prog["u_cam"].value = (float(cam_x), float(cam_y))
        self.prog["u_time"].value = float(now_sec)
        self.prog["u_fx_flags"].value = (1.0 if enable_ao else 0.0, 1.0 if enable_bloom else 0.0, 1.0 if enable_fog else 0.0)
        self.prog["u_num_lights"].value = n_lgt
        self.prog["u_light_pos_rad"].write(self.pos_rad_buf.tobytes())
        self.prog["u_light_col_foot"].write(self.col_foot_buf.tobytes())
        self.prog["u_light_flags"].write(self.flags_buf.tobytes())

        self.prog["u_num_fogs"].value = n_fog
        self.prog["u_fog_pos_rad"].write(self.fog_pos_buf.tobytes())
        self.prog["u_fog_col_dens"].write(self.fog_col_buf.tobytes())

        self.prog["u_num_hud_lights"].value = n_hud
        self.prog["u_hud_pos_rad"].write(self.hud_pos_buf.tobytes())
        self.prog["u_hud_col"].write(self.hud_col_buf.tobytes())

        self.fbo.use()
        self.tex_diff.use(0)
        self.tex_norm.use(1)
        self.tex_ent_y.use(2)
        self.tex_fov.use(3)
        self.tex_masks.use(4)
        self.tex_walls.use(5)
        self.tex_emissive.use(6)
        self.vao.render(self.moderngl.TRIANGLE_STRIP)

        raw_rgb = self.fbo.read(components=3, alignment=1)
        return pygame.image.frombuffer(raw_rgb, (VIEW_W, CANVAS_H), "RGB")

class Renderer:
    def __init__(self):
        self.assets = create_placeholder_assets()
        self.anim_bank = self.assets.pop("_anim_bank", {})
        self.hero_cache = {}
        self.rot_cache = {}
        self.flip_cache = {}
        self.chill_cache = {}
        self.emissive_cache = {}
        self.gpu_shader = None
        try:
            self.gpu_shader = GPULightShader()
            print("[GPU] Аппаратный 2.5D-шейдер ModernGL успешно активирован!")
        except Exception as e:
            print(f"[CPU Fallback] ModernGL не найден ({e}), используем CPU-рендер.")
        self.diff_canvas = pygame.Surface((VIEW_W, CANVAS_H))
        self.norm_canvas = pygame.Surface((VIEW_W, CANVAS_H))
        self.emissive_canvas = pygame.Surface((VIEW_W, CANVAS_H))

        self.px = np.arange(VIEW_W, dtype=np.float32)[:, None]
        self.py = np.arange(CANVAS_H, dtype=np.float32)[None, :]
        self.entity_y_canvas = np.full((VIEW_W, CANVAS_H), -9999.0, dtype=np.float32)
        self.current_hud_lights = []

        self.font_thought = pygame.font.SysFont("consolas", 19, bold=True)
        self.font_ui = pygame.font.SysFont("consolas", 16, bold=True)
        self.font_small = pygame.font.SysFont("consolas", 14, bold=True)
        self.font_title = pygame.font.SysFont("consolas", 20, bold=True)
        self.font_popup = pygame.font.SysFont("consolas", 17, bold=True)
        self.font_popup_big = pygame.font.SysFont("consolas", 24, bold=True)

        hud_y = CANVAS_H * SCALE
        # Центрируем весь боевой пояс ([Q/E] + [1..4] + [5 пассивок]) ровно по центру экрана 1920px!
        belt_total_w = (2 * 58) + 18 + (4 * 58) + 24 + (5 * 54)
        belt_start_x = (SCREEN_W - belt_total_w) // 2
        ab_x = belt_start_x
        hb_x = ab_x + 2 * 58 + 18
        ps_x = hb_x + 4 * 58 + 24

        self.ability_rects = [pygame.Rect(ab_x + i * 58, hud_y + 22, 54, 56) for i in range(2)]
        self.hotbar_rects = [pygame.Rect(hb_x + i * 58, hud_y + 22, 54, 56) for i in range(4)]
        self.passive_slot_rects = [pygame.Rect(ps_x + i * 54, hud_y + 24, 48, 52) for i in range(5)]
        self.bag_btn_rect = pygame.Rect(SCREEN_W - 176, hud_y + 22, 156, 56)
        self.inv_slot_rects = []
        self.equip_slot_rects = {}
        self.stat_plus_rects = {}
        self.perk_card_rects = []
        self.modal_rect = pygame.Rect(0, 0, 0, 0)
        self.journal_btn_rect = pygame.Rect(0, 0, 0, 0)
        self.journal_filter_rects = {}

    def get_hero_pair(self, player):
        from menu_and_profile import build_custom_hero_sprite
        from studio_core import flip_normal_pair_x
        torso = player.equipment["torso"]
        armor_cls = torso.armor_class if torso else "none"
        has_helm = player.equipment["helmet"] is not None
        has_torch = player.has_lit_torch
        has_weap = player.equipment["right_hand"] is not None
        app = getattr(player, "appearance", {})
        h_type = app.get("hero_type", "male")
        s_idx = app.get("skin_idx", 0)
        hd_idx = app.get("head_idx", 0)
        o_idx = app.get("outfit_idx", 0)
        a_frame = getattr(player, "anim_frame", 0)
        moving = getattr(player, "is_moving", False)
        facing = getattr(player, "facing", -1)

        key = (player.cloak_color, armor_cls, has_helm, has_torch, has_weap, h_type, s_idx, hd_idx, o_idx, a_frame, moving, facing)
        if key not in self.hero_cache:
            d_s, n_s = build_custom_hero_sprite(
                cloak_color=player.cloak_color,
                armor_class=armor_cls,
                has_helmet=has_helm,
                has_torch=has_torch,
                has_weapon=has_weap,
                hero_type=h_type,
                skin_idx=s_idx,
                head_idx=hd_idx,
                outfit_idx=o_idx,
                anim_frame=a_frame,
                is_moving=moving,
            )
            if facing > 0:
                d_s, n_s = flip_normal_pair_x(d_s, n_s)
            self.hero_cache[key] = (d_s, n_s)
        return self.hero_cache[key]
    
    def get_tile_pair(self, key, c, r, salt=0):
        """Возвращает (diff, norm) для тайла или оверлея с учётом случайного поворота 0/90/180/270° по координатам клетки!"""
        base_pair = self.assets.get(key, self.assets["floor_0"])
        a_info = self.anim_bank.get(key)
        rrot = a_info.get("random_rot", False) if a_info else (key in ("floor_3", "floor_5", "ov_pebbles", "ov_moss", "ov_cracks", "ov_planks_wear"))
        if not rrot or (a_info and len(a_info.get("frames", [])) > 1):
            return base_pair

        rot_k = ((c * 73 + r * 151 + (c ^ r) * 31 + salt * 19) >> 1) & 3
        if rot_k == 0:
            return base_pair

        cache_key = (key, rot_k)
        if cache_key not in self.rot_cache:
            from studio_core import rotate_normal_pair
            self.rot_cache[cache_key] = rotate_normal_pair(base_pair[0], base_pair[1], rot_k)
        return self.rot_cache[cache_key]

    def get_mob_pair(self, sprite_key, facing, is_chilled=False, flash_mode=None):
        """Зеркалит спрайт моба, накладывает ледяной оттенок и Hit-Flash (красный или бело-золотой при крите)."""
        base_pair = self.assets.get(sprite_key, self.assets["rat"])
        a_info = self.anim_bank.get(sprite_key)
        frame_idx = 0
        if a_info and len(a_info.get("frames", [])) > 1:
            now_sec = pygame.time.get_ticks() * 0.001
            frame_idx = int(now_sec * a_info["fps"]) % len(a_info["frames"])

        if facing > 0:
            cache_key = (sprite_key, frame_idx)
            if cache_key not in self.flip_cache:
                from studio_core import flip_normal_pair_x
                self.flip_cache[cache_key] = flip_normal_pair_x(base_pair[0], base_pair[1])
            pair = self.flip_cache[cache_key]
        else:
            pair = base_pair

        if not is_chilled and not flash_mode:
            return pair

        fx_key = (sprite_key, frame_idx, facing > 0, is_chilled, flash_mode)
        if fx_key not in self.chill_cache:
            d_orig, n_orig = pair
            w, h = d_orig.get_size()
            d_out = d_orig.copy()
            for y in range(h):
                for x in range(w):
                    r, g, b, a = d_out.get_at((x, y))
                    if a > 10:
                        if flash_mode == "crit":
                            # Бело-золотая вспышка при критическом ударе!
                            nr = min(255, int(r * 0.35 + 255 * 0.65))
                            ng = min(255, int(g * 0.35 + 240 * 0.65))
                            nb = min(255, int(b * 0.35 + 150 * 0.65))
                        elif flash_mode == "hit":
                            # Сочная багрово-красная вспышка при обычном попадании!
                            nr = min(255, int(r * 0.35 + 255 * 0.65))
                            ng = max(0, int(g * 0.25))
                            nb = max(0, int(b * 0.25))
                        else:
                            nr = min(255, int(r * 0.55 + 25))
                            ng = min(255, int(g * 0.85 + 55))
                            nb = min(255, int(b * 1.25 + 85))
                        d_out.set_at((x, y), (nr, ng, nb, a))
            self.chill_cache[fx_key] = (d_out, n_orig)
        return self.chill_cache[fx_key]
        base_pair = self.assets.get(sprite_key, self.assets["rat"])
        a_info = self.anim_bank.get(sprite_key)
        frame_idx = 0
        if a_info and len(a_info.get("frames", [])) > 1:
            now_sec = pygame.time.get_ticks() * 0.001
            frame_idx = int(now_sec * a_info["fps"]) % len(a_info["frames"])

        if facing > 0:
            cache_key = (sprite_key, frame_idx)
            if cache_key not in self.flip_cache:
                from studio_core import flip_normal_pair_x
                self.flip_cache[cache_key] = flip_normal_pair_x(base_pair[0], base_pair[1])
            pair = self.flip_cache[cache_key]
        else:
            pair = base_pair

        if not is_chilled:
            return pair

        chill_key = (sprite_key, frame_idx, facing > 0)
        if chill_key not in self.chill_cache:
            d_orig, n_orig = pair
            w, h = d_orig.get_size()
            d_icy = d_orig.copy()
            for y in range(h):
                for x in range(w):
                    r, g, b, a = d_icy.get_at((x, y))
                    if a > 10:
                        nr = min(255, int(r * 0.55 + 25))
                        ng = min(255, int(g * 0.85 + 55))
                        nb = min(255, int(b * 1.25 + 85))
                        d_icy.set_at((x, y), (nr, ng, nb, a))
            self.chill_cache[chill_key] = (d_icy, n_orig)
        return self.chill_cache[chill_key]

    def get_world_loot_pair(self, item):
        """Builds crisp 16x20 pixel-art sprites for coins, gems, and equipment on the dungeon floor!"""
        if item is None or item.type not in ("equipment", "currency_coin", "gem"):
            return self.assets["loot"]
        if not hasattr(self, "world_item_cache"):
            self.world_item_cache = {}
        key = item.icon
        if key not in self.world_item_cache:
            d_surf, n_surf = make_pair(16, 20)

            if item.type == "currency_coin":
                # Рисуем россыпь из 3 плоских овальных монет (4x3 пикселя каждая) на каменном полу!
                c_pal = {
                    "coin_copper":   ((185, 96, 52),  (242, 162, 110), (92, 42, 22)),
                    "coin_silver":   ((175, 190, 210), (245, 252, 255), (78, 86, 102)),
                    "coin_gold":     ((230, 175, 35),  (255, 242, 145), (120, 82, 16)),
                    "coin_platinum": ((135, 220, 245), (240, 255, 255), (58, 105, 130)),
                }
                c_main, c_shine, c_edge = c_pal.get(key, c_pal["coin_gold"])
                # Координаты 3 лежащих плашмя монеток: левая, правая и верхняя внахлёст
                coins_xy = [(3, 15), (8, 16), (6, 13)]
                for cx0, cy0 in coins_xy:
                    # Тёмный гурт (ребро монеты снизу)
                    for dx in range(1, 4):
                        d_surf.set_at((cx0 + dx, cy0 + 2), c_edge)
                        n_surf.set_at((cx0 + dx, cy0 + 2), (128, 38, 200, 255))
                    # Плоское тело монеты (овал 5x2)
                    for dx in range(5):
                        d_surf.set_at((cx0 + dx, cy0 + 1), c_main)
                        n_surf.set_at((cx0 + dx, cy0 + 1), (128, 128, 255, 255))
                    for dx in range(1, 4):
                        col_top = c_shine if dx in (1, 2) else c_main
                        d_surf.set_at((cx0 + dx, cy0), col_top)
                        n_surf.set_at((cx0 + dx, cy0), (128, 218, 200, 255))

            elif item.type == "gem":
                # Рисуем чёткий гранёный самоцвет на полу (y=11..18)
                g_pal = {
                    "gem_green":  ((42, 185, 88),  (165, 255, 190), (22, 95, 45)),
                    "gem_red":    ((210, 38, 62),  (255, 155, 170), (110, 18, 32)),
                    "gem_blue":   ((50, 140, 240), (180, 230, 255), (25, 70, 135)),
                    "gem_orange": ((240, 110, 32), (255, 225, 130), (135, 50, 15)),
                    "gem_purple": ((170, 70, 240), (235, 190, 255), (85, 30, 130)),
                }
                g_main, g_hi, g_dark = g_pal.get(key, g_pal["gem_green"])
                for y in range(11, 18):
                    half_w = 1 if y in (11, 17) else (2 if y in (12, 16) else 3)
                    for x in range(8 - half_w, 8 + half_w):
                        if x < 7 and y <= 14:
                            col, n_col = g_hi, (65, 195, 195, 255)
                        elif x >= 8 and y >= 15:
                            col, n_col = g_dark, (190, 60, 195, 255)
                        else:
                            col, n_col = g_main, (128, 218, 200, 255)
                        d_surf.set_at((x, y), col)
                        n_surf.set_at((x, y), n_col)

            else:
                tmp32 = pygame.Surface((32, 32), pygame.SRCALPHA)
                self.draw_item_icon(tmp32, item.icon, 0, 0, 32)
                scaled16 = pygame.transform.scale(tmp32, (16, 16))
                d_surf.blit(scaled16, (0, 3))
                for y in range(3, 19):
                    for x in range(16):
                        c = d_surf.get_at((x, y))
                        if c[3] > 20:
                            nx = int(np.clip(128 + (x - 7.5) * 10, 55, 200))
                            ny = int(np.clip(195 - (y - 3) * 7, 70, 215))
                            n_surf.set_at((x, y), (nx, ny, 230, 255))

            self.world_item_cache[key] = enforce_crisp_rim_normals(d_surf, n_surf)
        return self.world_item_cache[key]

    def _eval_hud_normal_light(self, nat_x, nat_y, nx, ny, nz):
        """Evaluates directional normal-mapped lighting on HUD elements from player-relative lights!"""
        # Solid readable baseline ambient (0.80) with soft, cozy directional tinting
        r_m, g_m, b_m = 0.80, 0.80, 0.85
        for lgt in self.current_hud_lights:
            lx, ly, lz = lgt["pos"]
            rad = lgt["radius"]
            cr, cg, cb = lgt["color"]
            dx = lx - nat_x
            dy = -(ly - nat_y)
            dist = math.sqrt(dx * dx + dy * dy + lz * lz)
            if dist < rad:
                inv = 1.0 / max(0.001, dist)
                ndotl = max(0.0, nx * (dx * inv) + ny * (dy * inv) + nz * (lz * inv))
                atten = (1.0 - (dist / rad) ** 1.5)
                inten = ndotl * atten * 0.32
                r_m += inten * cr
                g_m += inten * cg
                b_m += inten * cb
        return min(1.25, r_m), min(1.25, g_m), min(1.25, b_m)

    def draw_pixel_frame(self, surface, rect, bg_col=UI_PANEL_BG, border_col=UI_BORDER_WOOD, highlight=False, illum=1.0):
        x, y, w, h = rect
        bd_base = UI_BORDER_HIGHLIGHT if highlight else border_col

        # If this frame is on the Bottom HUD and we have player-relative lights, shade all 4 bevels directionally!
        if y >= VIEW_H * SCALE - 10 and self.current_hud_lights:
            cx_nat = (x + w * 0.5) / SCALE
            cy_nat = (y + h * 0.5) / SCALE
            hw_nat = (w * 0.5) / SCALE
            hh_nat = (h * 0.5) / SCALE

            rm_c, gm_c, bm_c = self._eval_hud_normal_light(cx_nat, cy_nat, 0.0, 0.0, 1.0)
            rm_t, gm_t, bm_t = self._eval_hud_normal_light(cx_nat, cy_nat - hh_nat, 0.0, 0.85, 0.52)
            rm_b, gm_b, bm_b = self._eval_hud_normal_light(cx_nat, cy_nat + hh_nat, 0.0, -0.85, 0.52)
            rm_l, gm_l, bm_l = self._eval_hud_normal_light(cx_nat - hw_nat, cy_nat, -0.85, 0.0, 0.52)
            rm_r, gm_r, bm_r = self._eval_hud_normal_light(cx_nat + hw_nat, cy_nat, 0.85, 0.0, 0.52)

            def tint(col, rm, gm, bm):
                return (min(255, int(col[0] * rm)), min(255, int(col[1] * gm)), min(255, int(col[2] * bm)))

            bg_lit = tint(bg_col, rm_c, gm_c, bm_c)
            col_top = tint(bd_base, rm_t * 1.15, gm_t * 1.15, bm_t * 1.15)
            col_bot = tint(bd_base, rm_b * 0.85, gm_b * 0.85, bm_b * 0.85)
            col_left = tint(bd_base, rm_l, gm_l, bm_l)
            col_right = tint(bd_base, rm_r, gm_r, bm_r)
        else:
            mult = 0.65 + 0.35 * illum
            bg_lit = tuple(min(255, int(c * mult)) for c in bg_col)
            bd_lit = tuple(min(255, int(c * (0.7 + 0.3 * illum))) for c in bd_base)
            col_top = col_bot = col_left = col_right = bd_lit

        pygame.draw.rect(surface, UI_BORDER_OUTER, (x, y, w, h))
        # Draw 4 directional bevel edges (Top, Bottom, Left, Right)
        pygame.draw.rect(surface, col_top, (x + 2, y + 2, w - 4, 3))
        pygame.draw.rect(surface, col_bot, (x + 2, y + h - 5, w - 4, 3))
        pygame.draw.rect(surface, col_left, (x + 2, y + 4, 3, h - 8))
        pygame.draw.rect(surface, col_right, (x + w - 5, y + 4, 3, h - 8))

        pygame.draw.rect(surface, UI_BORDER_OUTER, (x + 5, y + 5, w - 10, h - 10))
        pygame.draw.rect(surface, bg_lit, (x + 7, y + 7, w - 14, h - 14))
        for rx, ry in ((x + 3, y + 3), (x + w - 6, y + 3), (x + 3, y + h - 6), (x + w - 6, y + h - 6)):
            pygame.draw.rect(surface, UI_BORDER_GOLD, (rx, ry, 3, 3))

    def draw_item_icon(self, surface, icon_name, x, y, size=32):
        cx, cy = x + size // 2, y + size // 2
        if icon_name == "torch":
            pygame.draw.line(surface, (140, 90, 45), (cx - 4, cy + 9), (cx + 2, cy - 2), 4)
            pygame.draw.circle(surface, (255, 195, 55), (cx + 3, cy - 5), 5)
            pygame.draw.circle(surface, (255, 110, 35), (cx + 3, cy - 5), 3)
        elif icon_name == "potion_red":
            pygame.draw.rect(surface, (195, 45, 55), (cx - 7, cy - 2, 14, 12))
            pygame.draw.rect(surface, (180, 155, 110), (cx - 3, cy - 8, 6, 6))
        elif icon_name == "potion_blue":
            pygame.draw.rect(surface, (45, 130, 225), (cx - 7, cy - 2, 14, 12))
            pygame.draw.rect(surface, (180, 155, 110), (cx - 3, cy - 8, 6, 6))
        elif icon_name == "bomb":
            pygame.draw.circle(surface, (255, 130, 40), (cx, cy), 8)
            pygame.draw.circle(surface, (255, 220, 90), (cx - 2, cy - 2), 4)
        elif icon_name == "skill_zap":
            pts = [(cx + 4, y + 4), (cx - 6, cy + 1), (cx + 1, cy + 1), (cx - 4, y + size - 4)]
            pygame.draw.lines(surface, (110, 225, 255), False, pts, 3)
        elif icon_name in ("weapon_cleaver", "weapon_sword", "weapon_2h", "weapon_mace"):
            col = (210, 135, 255) if icon_name == "weapon_2h" else ((130, 225, 250) if icon_name == "weapon_sword" else (185, 175, 180))
            w_line = 7 if icon_name == "weapon_2h" else 5
            pygame.draw.line(surface, col, (x + 6, y + size - 6), (x + size - 6, y + 6), w_line)
            if icon_name == "weapon_mace":
                pygame.draw.circle(surface, (200, 205, 215), (x + size - 8, y + 8), 6)
            pygame.draw.line(surface, (165, 120, 60), (x + 4, y + size - 4), (x + 12, y + size - 12), 4)
        elif icon_name == "shield":
            pygame.draw.circle(surface, (160, 170, 185), (cx, cy), 10)
            pygame.draw.circle(surface, (215, 175, 80), (cx, cy), 4)
        elif icon_name == "helmet":
            pygame.draw.rect(surface, (170, 180, 195), (cx - 8, cy - 7, 16, 14))
            pygame.draw.rect(surface, (30, 28, 38), (cx - 6, cy - 1, 12, 4))
        elif icon_name in ("armor_cloth", "armor_leather", "armor_plate"):
            col = (95, 75, 150) if icon_name == "armor_cloth" else ((145, 90, 50) if icon_name == "armor_leather" else (185, 195, 210))
            pygame.draw.rect(surface, col, (cx - 9, cy - 8, 18, 18))
            pygame.draw.rect(surface, UI_BORDER_GOLD, (cx - 9, cy - 8, 18, 18), 2)
        elif icon_name == "boots":
            pygame.draw.rect(surface, (135, 85, 45), (cx - 6, cy - 6, 8, 13))
            pygame.draw.rect(surface, (135, 85, 45), (cx - 6, cy + 2, 13, 6))
        elif icon_name == "ring":
            pygame.draw.circle(surface, (235, 195, 75), (cx, cy + 1), 7, 3)
            pygame.draw.circle(surface, (90, 240, 160), (cx, cy - 5), 3)
        elif icon_name == "trinket":
            pygame.draw.polygon(surface, (255, 165, 45), [(cx, cy - 9), (cx + 9, cy), (cx, cy + 9), (cx - 9, cy)])
            pygame.draw.circle(surface, (255, 240, 180), (cx, cy), 3)
        elif icon_name in ("bag_small", "bag_big"):
            col = (155, 100, 55) if icon_name == "bag_small" else (185, 125, 60)
            pygame.draw.rect(surface, col, (cx - 9, cy - 5, 18, 15))
            pygame.draw.rect(surface, (235, 195, 85), (cx - 4, cy - 1, 8, 4))
        elif icon_name == "lock":
            pygame.draw.rect(surface, (95, 88, 102), (cx - 7, cy - 2, 14, 11))
            pygame.draw.rect(surface, (95, 88, 102), (cx - 4, cy - 8, 8, 7), 2)
        elif icon_name in ("coin", "coin_copper", "coin_silver", "coin_gold", "coin_platinum"):
            c_map = {
                "coin": ((235, 185, 45), (255, 240, 140), (135, 95, 20)),
                "coin_copper": ((198, 108, 62), (245, 175, 125), (105, 48, 24)),
                "coin_silver": ((185, 200, 220), (245, 252, 255), (95, 105, 125)),
                "coin_gold": ((240, 188, 40), (255, 245, 150), (140, 98, 18)),
                "coin_platinum": ((140, 225, 250), (240, 255, 255), (65, 115, 145)),
            }
            main_c, hi_c, edge_c = c_map.get(icon_name, c_map["coin"])
            for ox, oy in ((-5, 3), (4, 4), (0, -3)):
                rx, ry = cx + ox - 7, cy + oy - 5
                pygame.draw.ellipse(surface, (20, 16, 26), (rx - 1, ry - 1, 16, 13))
                pygame.draw.ellipse(surface, edge_c, (rx, ry + 2, 14, 9))
                pygame.draw.ellipse(surface, main_c, (rx, ry, 14, 9))
                pygame.draw.ellipse(surface, hi_c, (rx + 2, ry + 1, 10, 6), 1)
        elif icon_name.startswith("gem_"):
            g_map = {
                "gem_green": ((45, 195, 95), (165, 255, 190)),
                "gem_red": ((215, 42, 65), (255, 155, 170)),
                "gem_blue": ((55, 145, 245), (180, 230, 255)),
                "gem_orange": ((245, 115, 35), (255, 225, 130)),
                "gem_purple": ((175, 75, 245), (235, 190, 255)),
            }
            main_c, hi_c = g_map.get(icon_name, g_map["gem_green"])
            pts_out = [(cx, cy - 10), (cx + 9, cy - 2), (cx + 6, cy + 9), (cx - 6, cy + 9), (cx - 9, cy - 2)]
            pts_in = [(cx, cy - 6), (cx + 5, cy - 1), (cx, cy + 5), (cx - 5, cy - 1)]
            pygame.draw.polygon(surface, (20, 16, 26), pts_out, 0)
            pygame.draw.polygon(surface, main_c, pts_out, 0)
            pygame.draw.polygon(surface, hi_c, pts_in, 0)
            pygame.draw.polygon(surface, (25, 20, 32), pts_out, 1)
        elif icon_name == "heart":
            pygame.draw.rect(surface, (225, 60, 70), (cx - 5, cy - 4, 10, 9))
        elif icon_name == "mana":
            pygame.draw.rect(surface, (70, 165, 250), (cx - 5, cy - 4, 10, 9))

    def wrap_text(self, text, font, max_w):
        words = text.split(" ")
        lines = []
        cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            if font.size(test)[0] <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def _get_entity_emissive_surf(self, d_surf, role_kind):
        """Создаёт точечную маску самосвечения ТОЛЬКО для глаз врагов и пламени костров/жаровен/факела."""
        key = (id(d_surf), role_kind)
        if key not in self.emissive_cache:
            w, h = d_surf.get_size()
            em = pygame.Surface((w, h), pygame.SRCALPHA)
            em.fill((0, 0, 0, 0))
            for y in range(h):
                for x in range(w):
                    r, g, b, a = d_surf.get_at((x, y))
                    if a <= 20:
                        continue
                    is_glow = False
                    if role_kind == "mob":
                        # У врагов светятся ТОЛЬКО яркие глаза (красные, жёлтые, голубые, зелёные), но не плащи и не корона!
                        is_eye_zone = (y >= 9) if w > 20 else True
                        if is_eye_zone:
                            if (r >= 235 and g <= 105 and b <= 85) or (r >= 245 and g >= 185 and b <= 75) or (g >= 240 and b >= 115) or (b >= 245 and g >= 245):
                                is_glow = True
                    elif role_kind == "fire_prop":
                        # У костров, жаровен и камина светится только само пламя
                        if r >= 210 and g >= 65 and b <= 165 and not (r < 225 and g > 145):
                            is_glow = True
                    elif role_kind == "hero":
                        # У героя светится только пламя зажжённого факела в руке (верхняя часть факела y <= 9 по краям x <= 3 или x >= 12)
                        if y <= 9 and (x <= 3 or x >= 12) and r >= 240 and g >= 115 and b <= 120:
                            is_glow = True
                    if is_glow:
                        em.set_at((x, y), (255, 255, 255, 255))
            self.emissive_cache[key] = em
        return self.emissive_cache[key]

    def render_frame(self, screen, dungeon, player, mobs, objects, projectiles, particles, popups, cam_x, cam_y, fov_mask, visible_tiles, lights, shown_thought, ui_texts, inv_open, hover_pos, drag_item, hover_target=None, levelup_choices=None, hud_lights=None):
        # Привязываем камеру к целым пикселям буфера, чтобы полностью убрать субпиксельное дрожание тайлов!
        cam_x = float(round(cam_x))
        cam_y = float(round(cam_y))

        now_sec = pygame.time.get_ticks() * 0.001
        for role_id, anim_info in self.anim_bank.items():
            fr_list = anim_info["frames"]
            if len(fr_list) > 1:
                self.assets[role_id] = fr_list[int(now_sec * anim_info["fps"]) % len(fr_list)]

        self.current_hud_lights = hud_lights or []
        self.diff_canvas.fill((12, 10, 16))
        self.norm_canvas.fill((128, 128, 255))
        self.emissive_canvas.fill((0, 0, 0))
        self.entity_y_canvas.fill(-9999.0)

        c0 = max(0, int(cam_x) // TILE_W)
        c1 = min(MAP_COLS, (int(cam_x) + VIEW_W) // TILE_W + 2)
        r0 = max(0, int(cam_y) // TILE_H)
        r1 = min(MAP_ROWS, (int(cam_y) + VIEW_H) // TILE_H + 2)

        tall_trees_to_draw = []
        for r in range(r0, r1):
            for c in range(c0, c1):
                sx = int(c * TILE_W - cam_x)
                sy = int(r * TILE_H - cam_y)
                t_val = dungeon.grid[r][c]
                if t_val == 1:
                    key = "wall"
                elif t_val == 6:
                    key = "wall_wood"
                elif t_val == 7:
                    key = "wall_cave"
                elif t_val == 8:
                    key = "floor_5"
                elif t_val == 9:
                    key = "floor_6"
                elif t_val == 5:
                    # Draw seamless forest grass underneath tall pine trees!
                    key = "floor_3"
                    if (c, r) in visible_tiles:
                        tall_trees_to_draw.append((c, r))
                else:
                    key = f"floor_{t_val}"
                d_surf, n_surf = self.get_tile_pair(key, c, r)
                self.diff_canvas.blit(d_surf, (sx, sy))
                self.norm_canvas.blit(n_surf, (sx, sy))

                # Накладываем полупрозрачный оверлей (камушки, мох, трещины, потёртости) со случайным поворотом!
                ov_key = getattr(dungeon, "overlays", {}).get((c, r))
                if ov_key and ov_key in self.assets:
                    ov_d, ov_n = self.get_tile_pair(ov_key, c, r, salt=77)
                    self.diff_canvas.blit(ov_d, (sx, sy))
                    self.norm_canvas.blit(ov_n, (sx, sy))

                door = dungeon.doors.get((c, r))
                if door:
                    d_key = "door_open" if door.is_open else ("door_locked" if door.locked else "door_closed")
                    dd, dn = self.assets[d_key]
                    self.diff_canvas.blit(dd, (sx, sy))
                    self.norm_canvas.blit(dn, (sx, sy))

        fx_mgr = ui_texts.get("_fx_mgr")
        # 1. Наложение «Памяти поля боя» (вечная кровь, обломки бочек, вино и копоть на полу)
        if fx_mgr and fx_mgr.flags.get("battle_memory", True):
            self.diff_canvas.blit(fx_mgr.decal_surf, (0, 0), area=pygame.Rect(int(cam_x), int(cam_y), VIEW_W, VIEW_H))

        # 2. Круги на воде при ходьбе по лужам
        if fx_mgr and fx_mgr.flags.get("water_ripples", True):
            for rp in fx_mgr.ripples:
                prog_r = 1.0 - (rp["timer"] / rp["max_timer"])
                rx_s = int(rp["wx"] * TILE_W - cam_x)
                ry_s = int(rp["wy"] * TILE_H - cam_y)
                rad_w = max(2, int(2 + prog_r * 7))
                rad_h = max(1, int(1 + prog_r * 4))
                col_r = (85, 165, 210) if prog_r < 0.5 else (50, 110, 150)
                pygame.draw.ellipse(self.diff_canvas, col_r, (rx_s - rad_w, ry_s - rad_h, rad_w * 2, rad_h * 2), 1)

        render_list = [{
            "wx": player.x - 0.5 + player.bump_x,
            "wy": player.y - 0.5 + player.bump_y,
            "actor_wx": player.x,
            "actor_wy": player.y,
            "is_player": True,
            "is_actor": True,
            "emissive_role": "hero" if player.has_lit_torch else None,
            "pair": self.get_hero_pair(player),
            "alpha": 255
        }]

        for (tc, tr) in tall_trees_to_draw:
            behind_canopy = (tr - 1.8 <= player.y <= tr + 0.35) and (abs(player.x - (tc + 0.5)) <= 1.05)
            t_alpha = 105 if behind_canopy else 255
            render_list.append({
                "wx": float(tc), "wy": float(tr),
                "is_tree": True,
                "pair": self.assets["tall_tree"],
                "alpha": t_alpha
            })

        for (lx, ly), lev in dungeon.levers.items():
            if (lx, ly) in visible_tiles:
                render_list.append({
                    "wx": float(lx), "wy": float(ly),
                    "pair": self.assets["lever_on" if lev.pulled else "lever_off"],
                    "alpha": 255
                })
        for br in dungeon.braziers:
            if (br["x"], br["y"]) in visible_tiles:
                render_list.append({
                    "wx": float(br["x"]), "wy": float(br["y"]),
                    "is_light_source": True,
                    "emissive_role": "fire_prop",
                    "pair": self.assets["brazier"], "alpha": 255
                })
        for obj in objects:
            if not obj.used and (obj.x, obj.y) in visible_tiles:
                if obj.kind in ("woven_rug", "stairs", "trap"):
                    fd, fn = self.assets[obj.kind]
                    self.diff_canvas.blit(fd, (int(obj.x * TILE_W - cam_x), int(obj.y * TILE_H - cam_y - 4)))
                    self.norm_canvas.blit(fn, (int(obj.x * TILE_W - cam_x), int(obj.y * TILE_H - cam_y - 4)))
                    continue
                pair = self.get_world_loot_pair(obj.item) if obj.kind == "loot" else self.assets.get(obj.kind, self.assets["loot"])
                is_npc = (obj.kind in ("npc_innkeeper", "npc_merchant"))
                is_fire = (obj.kind in ("campfire", "fireplace"))
                render_list.append({
                    "wx": float(obj.x), "wy": float(obj.y),
                    "actor_wx": obj.x + 0.5, "actor_wy": obj.y + 0.5,
                    "is_actor": is_npc,
                    "is_light_source": is_fire,
                    "emissive_role": "fire_prop" if is_fire else None,
                    "pair": pair, "alpha": 255
                })

        use_hit_flash = fx_mgr.flags.get("hit_flash", True) if fx_mgr else True
        for m in mobs:
            mx_i, my_i = int(m.x), int(m.y)
            if getattr(m, "size_tiles", 1) >= 2:
                mob_vis = any((mx_i + dx, my_i + dy) in visible_tiles for dx in (-1, 0, 1) for dy in (-1, 0, 1))
            else:
                mob_vis = (mx_i, my_i) in visible_tiles
            if mob_vis:
                chilled = getattr(m, "slow_timer", 0.0) > 0.0
                f_mode = None
                if use_hit_flash and getattr(m, "hit_flash_timer", 0.0) > 0.0:
                    f_mode = "crit" if getattr(m, "hit_flash_crit", False) else "hit"
                render_list.append({
                    "wx": m.x - 0.5 + m.bump_x,
                    "wy": m.y - 0.5 + m.bump_y,
                    "actor_wx": m.x,
                    "actor_wy": m.y,
                    "is_actor": True,
                    "emissive_role": "mob",
                    "pair": self.get_mob_pair(m.sprite, getattr(m, "facing", -1), is_chilled=chilled, flash_mode=f_mode),
                    "alpha": 255
                })

        render_list.sort(key=lambda item: item["wy"])

        use_shadows = fx_mgr.flags.get("drop_shadows", True) if fx_mgr else True
        sh_surf = pygame.Surface((28, 12), pygame.SRCALPHA) if use_shadows else None
        world_shadow_lights = [(br["x"] + 0.5, br["y"] + 0.5, br["radius"] / TILE_W) for br in dungeon.braziers]
        for obj in objects:
            if obj.kind in ("campfire", "fireplace"):
                world_shadow_lights.append((obj.x + 0.5, obj.y + 0.5, 7.2))

        for ent in render_list:
            d_surf, n_surf = ent["pair"]
            ew, eh = d_surf.get_size()
            draw_x = int(round(ent["wx"] * TILE_W - cam_x - (ew - TILE_W) // 2))
            draw_y = int(round(ent["wy"] * TILE_H - cam_y - (eh - TILE_H)))
            sole_sy = float(draw_y + eh - 2)
            if draw_y + eh > 0 and draw_y < VIEW_H:
                if use_shadows and ent.get("is_actor", False):
                    awx = ent.get("actor_wx", ent["wx"] + 0.5)
                    awy = ent.get("actor_wy", ent["wy"] + 0.5)
                    vec_x, vec_y, w_sum = 0.0, 0.0, 0.0
                    for lwx, lwy, lrad in world_shadow_lights:
                        dx_w = awx - lwx
                        dy_w = awy - lwy
                        dist_w = math.hypot(dx_w, dy_w)
                        if 0.1 < dist_w < lrad:
                            w_l = (1.0 - dist_w / lrad) ** 1.5
                            vec_x += (dx_w / dist_w) * w_l
                            vec_y += (dy_w / dist_w) * w_l
                            w_sum += w_l
                    if not ent.get("is_player", False) and player.has_lit_torch:
                        dx_p = awx - player.x
                        dy_p = awy - player.y
                        dist_p = math.hypot(dx_p, dy_p)
                        if 0.1 < dist_p < 7.5:
                            w_p = (1.0 - dist_p / 7.5) ** 1.4 * 1.5
                            vec_x += (dx_p / dist_p) * w_p
                            vec_y += (dy_p / dist_p) * w_p
                            w_sum += w_p

                    if w_sum > 0.01:
                        sh_dx = max(-3.5, min(3.5, (vec_x / w_sum) * 3.0))
                        sh_dy = max(-2.0, min(2.5, (vec_y / w_sum) * 1.8))
                    else:
                        sh_dx, sh_dy = 0.0, 0.5

                    sh_w = 20 if ew > 20 else 10
                    sh_h = 6 if ew > 20 else 4
                    sh_surf.fill((0, 0, 0, 0))
                    pygame.draw.ellipse(sh_surf, (8, 6, 12, 120), (0, 0, sh_w, sh_h))
                    foot_cx = draw_x + ew * 0.5
                    self.diff_canvas.blit(sh_surf, (int(round(foot_cx - sh_w * 0.5 + sh_dx)), int(round(sole_sy - sh_h * 0.5 + sh_dy))))

                if ent["alpha"] < 255:
                    d_tmp = d_surf.copy()
                    d_tmp.set_alpha(ent["alpha"])
                    self.diff_canvas.blit(d_tmp, (draw_x, draw_y))
                else:
                    self.diff_canvas.blit(d_surf, (draw_x, draw_y))
                    self.norm_canvas.blit(n_surf, (draw_x, draw_y))
                    em_role = ent.get("emissive_role")
                    if em_role:
                        em_s = self._get_entity_emissive_surf(d_surf, em_role)
                        self.emissive_canvas.blit(em_s, (draw_x, draw_y))

                    # Источники света (жаровни, костры, камин) НЕ записываются в буфер глубины, чтобы не затенять и не обводить контуром самих себя!
                    if not ent.get("is_light_source", False):
                        y_start_depth = draw_y + 28 if ent.get("is_tree", False) else draw_y
                        cx0, cx1 = max(0, draw_x), min(VIEW_W, draw_x + ew)
                        cy0, cy1 = max(0, y_start_depth), min(VIEW_H, draw_y + eh)
                        if cx0 < cx1 and cy0 < cy1:
                            alpha_slice = pygame.surfarray.array_alpha(d_surf)[cx0 - draw_x:cx1 - draw_x, cy0 - draw_y:cy1 - draw_y]
                            self.entity_y_canvas[cx0:cx1, cy0:cy1] = np.where(alpha_slice > 15, sole_sy, self.entity_y_canvas[cx0:cx1, cy0:cy1])

        tz_diff, tz_norm = self.assets["thought_zone"]
        self.diff_canvas.blit(tz_diff, (0, VIEW_H))
        self.norm_canvas.blit(tz_norm, (0, VIEW_H))

        if self.gpu_shader is not None:
            en_ao = fx_mgr.flags.get("ao", True) if fx_mgr else True
            en_bloom = fx_mgr.flags.get("bloom", True) if fx_mgr else True
            en_fog = fx_mgr.flags.get("volumetric_fog", True) if fx_mgr else True
            w_grid = fx_mgr.wall_grid_np if fx_mgr else None
            clouds = fx_mgr.active_clouds if fx_mgr else None
            lit_surf = self.gpu_shader.render_lit_surface(
                self.diff_canvas, self.norm_canvas, self.entity_y_canvas,
                fov_mask, cam_x, cam_y, lights, self.current_hud_lights,
                wall_grid_np=w_grid, emissive_canvas=self.emissive_canvas,
                enable_ao=en_ao, enable_bloom=en_bloom,
                enable_fog=en_fog, active_clouds=clouds, now_sec=now_sec
            )
            r_mult = g_mult = b_mult = None
        else:
            diff = pygame.surfarray.array3d(self.diff_canvas).astype(np.float32)
            norm = pygame.surfarray.array3d(self.norm_canvas).astype(np.float32)

            nx = (norm[:, :, 0] - 128.0) / 127.0
            ny = (norm[:, :, 1] - 128.0) / 127.0
            nz = (norm[:, :, 2] - 128.0) / 127.0

            is_ent = self.entity_y_canvas > -9000.0
            rim_canvas = np.zeros((VIEW_W, CANVAS_H), dtype=np.float32)
            rim_canvas[1:-1, 1:VIEW_H - 1] = is_ent[1:-1, 1:VIEW_H - 1] & (
                (~is_ent[:-2, 1:VIEW_H - 1]) | (~is_ent[2:, 1:VIEW_H - 1]) |
                (~is_ent[1:-1, :VIEW_H - 2]) | (~is_ent[1:-1, 2:VIEW_H])
            )

            tx_screen = np.clip(((self.px[:, 0] + cam_x) // TILE_W).astype(np.int32), 0, MAP_COLS - 1)
            ty_screen = np.clip(((self.py[0, :VIEW_H] + cam_y) // TILE_H).astype(np.int32), 0, MAP_ROWS - 1)

            r_mult = np.zeros((VIEW_W, CANVAS_H), dtype=np.float32)
            g_mult = np.zeros((VIEW_W, CANVAS_H), dtype=np.float32)
            b_mult = np.zeros((VIEW_W, CANVAS_H), dtype=np.float32)
            rim_add_r = np.zeros((VIEW_W, CANVAS_H), dtype=np.float32)
            rim_add_g = np.zeros((VIEW_W, CANVAS_H), dtype=np.float32)
            rim_add_b = np.zeros((VIEW_W, CANVAS_H), dtype=np.float32)

            r_mult[:, VIEW_H:] = 0.74
            g_mult[:, VIEW_H:] = 0.74
            b_mult[:, VIEW_H:] = 0.80

            for lgt in lights:
                lx, ly, lz = lgt["pos"]
                radius = lgt["radius"]
                cr, cg, cb = lgt["color"]

                x0 = max(0, int(lx - radius - 2))
                x1 = min(VIEW_W, int(lx + radius + 3))
                y0 = max(0, int(ly - radius - 2))
                y1 = min(VIEW_H, int(ly + radius + 3))
                if x0 >= x1 or y0 >= y1:
                    continue

                dx = lx - self.px[x0:x1, :]
                dy = -(ly - self.py[:, y0:y1])

                ent_y = self.entity_y_canvas[x0:x1, y0:y1]
                light_foot_y = lgt.get("foot_y", ly + 4.0)
                if lgt.get("ignore_depth", False):
                    behind_ratio = np.zeros_like(ent_y)
                else:
                    behind_ratio = np.where(ent_y > -9000.0, np.clip((ent_y - light_foot_y) / 4.5, 0.0, 1.0), 0.0)

                dist = np.sqrt(dx * dx + dy * dy + lz * lz)
                inv_dist = 1.0 / np.maximum(dist, 0.001)

                sub_nx = nx[x0:x1, y0:y1]
                sub_ny = ny[x0:x1, y0:y1]
                sub_nz = nz[x0:x1, y0:y1]

                raw_dot = sub_nx * (dx * inv_dist) + sub_ny * (dy * inv_dist) + sub_nz * (lz * inv_dist)
                z_wrap = np.maximum(0.0, sub_nz * (lz * inv_dist)) * 0.65
                ndotl = np.maximum(z_wrap, raw_dot)
                atten = np.clip(1.0 - (dist / radius) ** 1.65, 0.0, 1.0)

                allowed_tiles = lgt.get("allowed_tiles")
                if allowed_tiles is not None:
                    if isinstance(allowed_tiles, np.ndarray):
                        atten = atten * allowed_tiles[tx_screen[x0:x1, None], ty_screen[None, y0:y1]]

                sub_rim = rim_canvas[x0:x1, y0:y1]
                front_shade = 1.0 - behind_ratio * (1.0 - sub_rim) * 0.65
                intensity = ndotl * atten * 1.45 * front_shade

                r_mult[x0:x1, y0:y1] += intensity * cr
                g_mult[x0:x1, y0:y1] += intensity * cg
                b_mult[x0:x1, y0:y1] += intensity * cb

                if not lgt.get("ignore_depth", False):
                    dist_2d = np.sqrt(dx * dx + dy * dy)
                    close_falloff = np.clip(1.0 - dist_2d / min(radius * 0.72, 48.0), 0.0, 1.0) ** 2.4
                    if isinstance(allowed_tiles, np.ndarray):
                        close_falloff = close_falloff * allowed_tiles[tx_screen[x0:x1, None], ty_screen[None, y0:y1]]
                    rim_boost = sub_rim * behind_ratio * close_falloff * 145.0
                    rim_add_r[x0:x1, y0:y1] += rim_boost * cr
                    rim_add_g[x0:x1, y0:y1] += rim_boost * cg
                    rim_add_b[x0:x1, y0:y1] += rim_boost * cb

            r_mult *= fov_mask
            g_mult *= fov_mask
            b_mult *= fov_mask

            out = np.empty_like(diff)
            base_r = diff[:, :, 0] * r_mult
            base_g = diff[:, :, 1] * g_mult
            base_b = diff[:, :, 2] * b_mult
            out[:, :, 0] = np.clip(np.where(rim_add_r > 0.5, np.minimum(228.0, base_r * 1.25 + rim_add_r * fov_mask), base_r), 0, 255)
            out[:, :, 1] = np.clip(np.where(rim_add_g > 0.5, np.minimum(222.0, base_g * 1.25 + rim_add_g * fov_mask), base_g), 0, 255)
            out[:, :, 2] = np.clip(np.where(rim_add_b > 0.5, np.minimum(220.0, base_b * 1.25 + rim_add_b * fov_mask), base_b), 0, 255)
            lit_surf = pygame.surfarray.make_surface(out.astype(np.uint8))

        scaled_view = pygame.transform.scale(lit_surf, (VIEW_W * SCALE, CANVAS_H * SCALE))
        screen.blit(scaled_view, (0, 0))

        # 5. Пылинки и споры, видимые ТОЛЬКО когда они пролетают сквозь лучи света!
        if fx_mgr and fx_mgr.flags.get("dust_motes", True):
            for dm in fx_mgr.dust_motes:
                mtx, mty = int(dm["wx"]), int(dm["wy"])
                if (mtx, mty) not in visible_tiles:
                    continue
                msx = dm["wx"] * TILE_W - cam_x
                msy = dm["wy"] * TILE_H - cam_y
                if not (2 <= msx < VIEW_W - 2 and 2 <= msy < VIEW_H - 2):
                    continue
                # Проверяем освещённость точки пылинки от реальных источников света (пропуская базовое ночное зрение lights[0])
                m_lum = 0.0
                m_col = [180, 170, 140]
                for lgt in lights[1:]:
                    lx, ly, lz = lgt["pos"]
                    rad = lgt["radius"]
                    d2 = math.hypot(msx - lx, msy - ly)
                    if d2 < rad * 0.85:
                        alw = lgt.get("allowed_tiles")
                        if isinstance(alw, np.ndarray) and alw[mtx, mty] < 0.5:
                            continue
                        inten = (1.0 - d2 / (rad * 0.85)) ** 1.4
                        if inten > m_lum:
                            m_lum = inten
                            cr, cg, cb = lgt["color"]
                            m_col = [min(255, int(195 * cr)), min(255, int(185 * cg)), min(255, int(165 * cb))]
                if m_lum > 0.18:
                    twinkle = 0.65 + 0.35 * math.sin(dm["phase"] * 2.5)
                    br_factor = min(1.0, m_lum * twinkle * 1.3)
                    final_c = (int(m_col[0] * br_factor), int(m_col[1] * br_factor), int(m_col[2] * br_factor))
                    sz_p = dm["size"] * 2
                    pygame.draw.rect(screen, final_c, (int(msx * SCALE), int(msy * SCALE), sz_p, sz_p))

        # Precision targeting works silently under the hood (visual reticle removed as requested)

        # Particles & Projectiles
        for pt in particles:
            sx = int((pt.wx * TILE_W - cam_x) * SCALE)
            sy = int((pt.wy * TILE_H - cam_y) * SCALE)
            if 0 <= sy < VIEW_H * SCALE:
                rad = max(2, int(pt.size * (pt.life / pt.max_life) * SCALE * 0.6))
                pygame.draw.circle(screen, pt.color, (sx, sy), rad)

        for pr in projectiles:
            sx = int((pr.wx * TILE_W - cam_x) * SCALE)
            sy = int((pr.wy * TILE_H - cam_y) * SCALE)
            if 0 <= sy < VIEW_H * SCALE:
                if getattr(pr, "visual_kind", "orb") == "spinning_dagger":
                    ang = getattr(pr, "angle", 0.0)
                    cos_a, sin_a = math.cos(ang), math.sin(ang)
                    perp_x, perp_y = -sin_a, cos_a
                    tip = (int(sx + cos_a * 14), int(sy + sin_a * 14))
                    guard_c = (int(sx - cos_a * 3), int(sy - sin_a * 3))
                    pommel = (int(sx - cos_a * 12), int(sy - sin_a * 12))
                    g1 = (int(guard_c[0] + perp_x * 6), int(guard_c[1] + perp_y * 6))
                    g2 = (int(guard_c[0] - perp_x * 6), int(guard_c[1] - perp_y * 6))
                    # Dark outline, wooden grip, brass crossguard & gleaming steel blade
                    pygame.draw.line(screen, (20, 18, 26), pommel, tip, 6)
                    pygame.draw.line(screen, (135, 82, 42), pommel, guard_c, 4)
                    pygame.draw.line(screen, (215, 175, 70), g1, g2, 3)
                    pygame.draw.line(screen, (210, 220, 235), guard_c, tip, 4)
                    pygame.draw.line(screen, (250, 252, 255), guard_c, tip, 2)
                else:
                    pygame.draw.circle(screen, (255, 255, 255), (sx, sy), 7)
                    pygame.draw.circle(screen, pr.color, (sx, sy), 11, 3)

        # Enemy Awareness, HP, Ground Roots & Chattering Speech Bubbles (with Darkness Camouflage!)
        for m in mobs:
            mx_i, my_i = int(m.x), int(m.y)
            if getattr(m, "size_tiles", 1) >= 2:
                vis = any((mx_i + dx, my_i + dy) in visible_tiles for dx in (-1, 0, 1) for dy in (-1, 0, 1))
            else:
                vis = (mx_i, my_i) in visible_tiles

            # Check actual light intensity at the enemy's position on canvas so dark tiles NEVER leak enemy UI!
            cx_canv = max(0, min(VIEW_W - 1, int(m.x * TILE_W - cam_x)))
            cy_canv = max(0, min(VIEW_H - 1, int((m.y - 0.2) * TILE_H - cam_y)))
            if r_mult is not None:
                tile_lum = float(r_mult[cx_canv, cy_canv] + g_mult[cx_canv, cy_canv] + b_mult[cx_canv, cy_canv])
            elif fov_mask[cx_canv, cy_canv] <= 0.05:
                tile_lum = 0.0
            else:
                tile_lum = 0.0
                mtx = max(0, min(MAP_COLS - 1, int(m.x)))
                mty = max(0, min(MAP_ROWS - 1, int(m.y)))
                for lgt in lights:
                    lx, ly, lz = lgt["pos"]
                    rad = lgt["radius"]
                    dist_l = math.sqrt((lx - cx_canv) ** 2 + (ly - cy_canv) ** 2 + lz ** 2)
                    if dist_l < rad:
                        alw = lgt.get("allowed_tiles")
                        if isinstance(alw, np.ndarray) and alw[mtx, mty] < 0.5:
                            continue
                        cr, cg, cb = lgt["color"]
                        tile_lum += (1.0 - (dist_l / rad) ** 1.65) * (cr + cg + cb)
            is_lit = vis and (tile_lum > 0.16 or getattr(m, "glow_timer", 0.0) > 0.0)
            if is_lit:
                m.last_lit_pos = (m.x, m.y)

            dist_to_p = math.hypot(m.x - player.x, m.y - player.y)
            if is_lit or (m.current_speech and dist_to_p <= 11.5):
                head_off = 1.65 if getattr(m, "size_tiles", 1) >= 2 else 0.85
                sx = int((m.x * TILE_W - cam_x) * SCALE)
                sy = int(((m.y - head_off) * TILE_H - cam_y) * SCALE)
                foot_y = int((m.y * TILE_H - cam_y) * SCALE)

                # Clear visual indication on the enemy model when it begins channeling a pentagram!
                if is_lit and getattr(m, "cast_windup_timer", 0.0) > 0.0 and 0 <= foot_y < VIEW_H * SCALE:
                    w_ratio = m.cast_windup_timer / max(0.01, getattr(m, "cast_windup_max", 0.65))
                    body_cy = (sy + foot_y) // 2
                    ring_r = max(10, int((14 + 28 * w_ratio) * (1.4 if getattr(m, "size_tiles", 1) >= 2 else 1.0)))
                    pygame.draw.circle(screen, (255, 45, 70), (sx, body_cy), ring_r, 2)
                    pygame.draw.circle(screen, (255, 185, 80), (sx, body_cy), max(4, ring_r - 6), 1)
                    paw_span = 26 if getattr(m, "size_tiles", 1) >= 2 else 15
                    for px_off in (-paw_span, paw_span):
                        pygame.draw.circle(screen, (235, 35, 60), (sx + px_off, body_cy - 6), 7)
                        pygame.draw.circle(screen, (255, 225, 130), (sx + px_off, body_cy - 6), 4)

                # Draw thorny roots / ice shards around the enemy while rooted!
                if is_lit and getattr(m, "root_timer", 0.0) > 0.0 and 0 <= foot_y < VIEW_H * SCALE:
                    is_ice = getattr(m, "chill_after_root", 0.0) > 0.0
                    c_outer = (55, 145, 215) if is_ice else (65, 42, 24)
                    c_inner = (165, 240, 255) if is_ice else (85, 165, 70)
                    pygame.draw.ellipse(screen, (28, 36, 48) if is_ice else (38, 26, 18), (sx - 20, foot_y - 6, 40, 12))
                    for r_idx, rx_off in enumerate((-14, -7, 0, 7, 14)):
                        sway = int(math.sin(now_sec * 5.0 + r_idx) * (1 if is_ice else 3))
                        pts = [
                            (sx + rx_off, foot_y + 2),
                            (sx + rx_off - sway, foot_y - 10),
                            (sx + rx_off // 2 + sway, foot_y - 22)
                        ]
                        pygame.draw.lines(screen, c_outer, False, pts, 4)
                        pygame.draw.lines(screen, c_inner, False, pts, 2)

                # Крохотные пламенные партиклы на горящем противнике (без громоздких кругов и надписей!)
                if is_lit and getattr(m, "burn_timer", 0.0) > 0.0 and 0 <= foot_y < VIEW_H * SCALE:
                    span_x = 18 if getattr(m, "size_tiles", 1) >= 2 else 10
                    for p_i in range(6):
                        phase = (now_sec * 6.5 + p_i * 1.37 + m.x) % 1.0
                        px_off = int(math.sin(p_i * 2.4 + now_sec * 4.0) * span_x)
                        py_off = int(foot_y - 6 - phase * 26)
                        p_col = (255, 235, 110) if phase < 0.45 else (255, 115, 30)
                        sz = 3 if phase < 0.6 else 2
                        pygame.draw.rect(screen, p_col, (sx + px_off, py_off, sz, sz))

                # HP bars & Awareness ONLY render when the mob is actually illuminated (`is_lit`)! (Текстовые дебаффы убраны)
                if is_lit and 0 <= sy < VIEW_H * SCALE:
                    if m.hp < m.max_hp:
                        bar_w = 56 if getattr(m, "size_tiles", 1) >= 2 else 36
                        pygame.draw.rect(screen, (25, 15, 20), (sx - bar_w // 2, sy - 8, bar_w, 6))
                        w_hp = int((bar_w - 2) * (m.hp / m.max_hp))
                        pygame.draw.rect(screen, (220, 55, 65), (sx - bar_w // 2 + 1, sy - 7, w_hp, 4))

                    if getattr(m, "alert_bang_timer", 0.0) > 0.0:
                        lbl = self.font_popup.render("!", True, (255, 75, 75))
                        screen.blit(lbl, (sx - lbl.get_width() // 2, sy - 26))
                    elif m.state != "combat" and m.awareness > 2.0:
                        pct = m.awareness / 100.0
                        col = (255, int(235 * (1.0 - pct * 0.6)), 60)
                        pygame.draw.rect(screen, (20, 18, 25), (sx - 16, sy - 20, 32, 7))
                        pygame.draw.rect(screen, col, (sx - 15, sy - 19, int(30 * pct), 5))
                        lbl = self.font_small.render("?", True, col)
                        screen.blit(lbl, (sx - lbl.get_width() // 2, sy - 35))
                    elif m.state == "sleeping" and not m.current_speech:
                        lbl = self.font_small.render("Zzz...", True, (150, 175, 220))
                        screen.blit(lbl, (sx - lbl.get_width() // 2, sy - 24))
                    elif m.state == "eating" and not m.current_speech:
                        lbl = self.font_small.render("*хруст*", True, (215, 170, 120))
                        screen.blit(lbl, (sx - lbl.get_width() // 2, sy - 24))

                if m.current_speech:
                    # If the mob is in darkness, anchor the bubble at `last_lit_pos` or on the rim of player's light
                    # so speech bubbles NEVER act as a real-time wallhack/radar in the dark!
                    if is_lit:
                        bsx, bsy = sx, sy
                        txt_col = (240, 235, 210)
                    elif getattr(m, "last_lit_pos", None):
                        lx_p, ly_p = m.last_lit_pos
                        bsx = int((lx_p * TILE_W - cam_x) * SCALE)
                        bsy = int(((ly_p - head_off) * TILE_H - cam_y) * SCALE)
                        txt_col = (180, 175, 160)
                    else:
                        dir_x = (m.x - player.x) / max(0.01, dist_to_p)
                        dir_y = (m.y - player.y) / max(0.01, dist_to_p)
                        rim_d = min(dist_to_p, 3.2)
                        bsx = int(((player.x + dir_x * rim_d) * TILE_W - cam_x) * SCALE)
                        bsy = int(((player.y + dir_y * rim_d - 0.6) * TILE_H - cam_y) * SCALE)
                        txt_col = (165, 160, 150)

                    lines = self.wrap_text(m.current_speech, self.font_small, 250)
                    rendered = [self.font_small.render(ln, True, txt_col) for ln in lines]
                    bw = max(s.get_width() for s in rendered) + 14
                    bh = len(rendered) * 16 + 8
                    bx = max(8, min(SCREEN_W - bw - 8, bsx - bw // 2))
                    by = max(6, min(VIEW_H * SCALE - bh - 6, bsy - bh - 12))
                    pygame.draw.rect(screen, (20, 18, 26), (bx, by, bw, bh), border_radius=4)
                    pygame.draw.rect(screen, UI_BORDER_WOOD, (bx, by, bw, bh), 1, border_radius=4)
                    for li, r_surf in enumerate(rendered):
                        screen.blit(r_surf, (bx + (bw - r_surf.get_width()) // 2, by + 4 + li * 16))

        # Active Player Buff Visuals: Persephone Rejuvenation Fireflies & Pyro Ignite Flames!
        p_sx_scr = int((player.x * TILE_W - cam_x) * SCALE)
        p_sy_scr = int(((player.y - 0.35) * TILE_H - cam_y) * SCALE)
        if getattr(player, "rejuv_timer", 0.0) > 0.0:
            for ff_i in range(4):
                ang = now_sec * 3.6 + ff_i * (math.pi * 0.5)
                fx_s = p_sx_scr + int(math.cos(ang) * 22)
                fy_s = p_sy_scr + int(math.sin(ang * 1.5) * 14)
                pygame.draw.circle(screen, (95, 245, 130), (fx_s, fy_s), 4)
                pygame.draw.circle(screen, (220, 255, 225), (fx_s, fy_s), 2)
        if getattr(player, "ignite_timer", 0.0) > 0.0:
            for fl_i in range(5):
                ang = now_sec * 5.2 + fl_i * (2.0 * math.pi / 5.0)
                fx_s = p_sx_scr + int(math.cos(ang) * 18)
                fy_s = p_sy_scr + 6 + int(math.sin(ang) * 10)
                pygame.draw.circle(screen, (255, 105, 30), (fx_s, fy_s), 5)
                pygame.draw.circle(screen, (255, 230, 95), (fx_s, fy_s), 2)

        for p in popups:
            sx = int((p.wx * TILE_W - cam_x) * SCALE)
            sy = int((p.wy * TILE_H - cam_y) * SCALE)
            if 0 <= sy < VIEW_H * SCALE:
                f_use = self.font_popup_big if getattr(p, "big", False) else self.font_popup
                txt_surf = f_use.render(p.text, True, p.color)
                sh_surf = f_use.render(p.text, True, (10, 8, 14))
                screen.blit(sh_surf, (sx - txt_surf.get_width() // 2 + 2, sy + 2))
                screen.blit(txt_surf, (sx - txt_surf.get_width() // 2, sy))

        # Render NPC Quest Marker & Speech Bubble (Innkeeper Hugo & Dungeon Merchant)
        for obj in objects:
            if not obj.used and obj.kind in ("npc_innkeeper", "npc_merchant") and (obj.x, obj.y) in visible_tiles:
                sx = int(((obj.x + 0.5) * TILE_W - cam_x) * SCALE)
                sy = int(((obj.y - 0.35) * TILE_H - cam_y) * SCALE)
                if getattr(obj, "speech_text", None):
                    lines = self.wrap_text(obj.speech_text, self.font_small, 260)
                    rendered = [self.font_small.render(ln, True, (255, 235, 175)) for ln in lines]
                    bw = max(s.get_width() for s in rendered) + 14
                    bh = len(rendered) * 16 + 8
                    bx = max(8, min(SCREEN_W - bw - 8, sx - bw // 2))
                    by = max(6, sy - bh - 10)
                    pygame.draw.rect(screen, (24, 20, 16), (bx, by, bw, bh), border_radius=4)
                    pygame.draw.rect(screen, UI_BORDER_GOLD, (bx, by, bw, bh), 1, border_radius=4)
                    for li, r_surf in enumerate(rendered):
                        screen.blit(r_surf, (bx + (bw - r_surf.get_width()) // 2, by + 4 + li * 16))
                else:
                    tag_str = "[?] Гуго" if obj.kind == "npc_innkeeper" else "[$] Скупщик"
                    tag_col = (255, 220, 75) if obj.kind == "npc_innkeeper" else (125, 245, 155)
                    q_lbl = self.font_ui.render(tag_str, True, tag_col)
                    screen.blit(q_lbl, (sx - q_lbl.get_width() // 2, sy - 20))

        # Render Cursor AoE target circle during windup
        if getattr(player, "pending_action", None):
            pa = player.pending_action
            if pa.get("kind") == "spell" and pa["item"].cast_type in ("aoe_cursor", "entangle_cursor"):
                cx_s = int((pa["tx"] * TILE_W - cam_x) * SCALE)
                cy_s = int((pa["ty"] * TILE_H - cam_y) * SCALE)
                r_px = int(pa["item"].aoe_radius * TILE_W * SCALE)
                pygame.draw.circle(screen, pa["item"].color, (cx_s, cy_s), r_px, 2)

        # Render Combat Skill & God Spell Visual FX
        for vfx in ui_texts.get("_visual_fx", []):
            prog = 1.0 - (vfx["timer"] / max(0.001, vfx["max_timer"]))

            if vfx["kind"] == "mana_shard":
                if (int(vfx["x"]), int(vfx["y"])) not in visible_tiles:
                    continue
                # Быстрое мигание в последние 1.2 секунды перед исчезновением осколка
                if vfx["timer"] < 1.2 and int(now_sec * 14.0) % 2 == 0:
                    continue
                cx_s = int((vfx["x"] * TILE_W - cam_x) * SCALE)
                bob = int(math.sin(now_sec * 6.5 + vfx["x"] * 3.0) * 4)
                cy_s = int((vfx["y"] * TILE_H - cam_y) * SCALE) - 6 + bob
                if 0 <= cy_s < VIEW_H * SCALE:
                    diamond_outer = [(cx_s, cy_s - 9), (cx_s + 6, cy_s), (cx_s, cy_s + 9), (cx_s - 6, cy_s)]
                    diamond_inner = [(cx_s, cy_s - 5), (cx_s + 3, cy_s), (cx_s, cy_s + 5), (cx_s - 3, cy_s)]
                    pygame.draw.polygon(screen, (45, 165, 245), diamond_outer)
                    pygame.draw.polygon(screen, (215, 250, 255), diamond_inner)
                    pygame.draw.polygon(screen, (15, 45, 85), diamond_outer, 1)

            elif vfx["kind"] == "fire_trail":
                cx_s = int((vfx["x"] * TILE_W - cam_x) * SCALE)
                cy_s = int((vfx["y"] * TILE_H - cam_y) * SCALE)
                if 0 <= cy_s < VIEW_H * SCALE:
                    fade = max(0.2, 1.0 - prog)
                    # Небольшие пиксельные язычки пламени и тлеющие угли на полу вместо огромных кругов!
                    seed_v = int((vfx["x"] * 37 + vfx["y"] * 73) * 10)
                    for f_i in range(4):
                        ox = ((seed_v + f_i * 11) % 19) - 9
                        oy = ((seed_v + f_i * 7) % 11) - 5
                        flick = int(math.sin(now_sec * 14.0 + f_i * 2.1 + vfx["x"] * 5.0) * 3 * fade)
                        fx_p = cx_s + ox
                        fy_p = cy_s + oy
                        h_flame = max(3, int(7 * fade) + flick)
                        # Тлеющий уголёк у основания + маленький язычок огня (3px шириной)
                        pygame.draw.rect(screen, (195, 55, 20), (fx_p - 2, fy_p, 5, 3))
                        pygame.draw.rect(screen, (255, 130, 30), (fx_p - 1, fy_p - h_flame, 3, h_flame))
                        pygame.draw.rect(screen, (255, 235, 105), (fx_p - 1, fy_p - max(2, h_flame // 2), 3, max(2, h_flame // 2)))

            elif vfx["kind"] == "frost_nova":
                cx_s = int((vfx["x"] * TILE_W - cam_x) * SCALE)
                cy_s = int((vfx["y"] * TILE_H - cam_y) * SCALE)
                r_px = max(6, int(vfx["radius"] * TILE_W * SCALE * (0.25 + prog * 0.75)))
                pygame.draw.circle(screen, (80, 195, 255), (cx_s, cy_s), r_px, 5)
                pygame.draw.circle(screen, (225, 250, 255), (cx_s, cy_s), max(4, r_px - 6), 2)
                for sp_i in range(8):
                    a = sp_i * (math.pi * 0.25) + prog * 0.4
                    p1 = (int(cx_s + math.cos(a) * (r_px * 0.65)), int(cy_s + math.sin(a) * (r_px * 0.65)))
                    p2 = (int(cx_s + math.cos(a) * (r_px * 1.05)), int(cy_s + math.sin(a) * (r_px * 1.05)))
                    pygame.draw.line(screen, (210, 245, 255), p1, p2, 3)

            elif vfx["kind"] == "chain_lightning":
                pts = vfx["points"]
                for i in range(len(pts) - 1):
                    x0_s = int((pts[i][0] * TILE_W - cam_x) * SCALE)
                    y0_s = int((pts[i][1] * TILE_H - cam_y) * SCALE)
                    x1_s = int((pts[i + 1][0] * TILE_W - cam_x) * SCALE)
                    y1_s = int((pts[i + 1][1] * TILE_H - cam_y) * SCALE)
                    zig = [(x0_s, y0_s)]
                    for seg in range(1, 5):
                        frac = seg / 5.0
                        jx = int(x0_s + (x1_s - x0_s) * frac + math.sin(now_sec * 40.0 + seg * 3 + i) * 8)
                        jy = int(y0_s + (y1_s - y0_s) * frac + math.cos(now_sec * 35.0 + seg * 5 + i) * 8)
                        zig.append((jx, jy))
                    zig.append((x1_s, y1_s))
                    pygame.draw.lines(screen, (75, 195, 255), False, zig, 6)
                    pygame.draw.lines(screen, (240, 255, 255), False, zig, 2)
                    pygame.draw.circle(screen, (200, 245, 255), (x1_s, y1_s), 8)

            elif vfx["kind"] == "entangle_zone":
                cx_s = int((vfx["x"] * TILE_W - cam_x) * SCALE)
                cy_s = int((vfx["y"] * TILE_H - cam_y) * SCALE)
                r_px = max(6, int(vfx["radius"] * TILE_W * SCALE))
                pygame.draw.circle(screen, (55, 145, 65), (cx_s, cy_s), r_px, 2)
                for v_i in range(7):
                    ang = v_i * (2.0 * math.pi / 7.0)
                    vx_b = cx_s + int(math.cos(ang) * (r_px * 0.65))
                    vy_b = cy_s + int(math.sin(ang) * (r_px * 0.65))
                    h_vine = int(26 * (1.0 - abs(prog - 0.5)))
                    pygame.draw.line(screen, (65, 45, 25), (vx_b, vy_b), (vx_b, vy_b - h_vine), 4)
                    pygame.draw.line(screen, (95, 215, 105), (vx_b, vy_b), (vx_b + 4, vy_b - h_vine), 2)

            elif vfx["kind"] == "beam":
                x1_s = int((vfx["x0"] * TILE_W - cam_x) * SCALE)
                y1_s = int((vfx["y0"] * TILE_H - cam_y) * SCALE)
                x2_s = int((vfx["x1"] * TILE_W - cam_x) * SCALE)
                y2_s = int((vfx["y1"] * TILE_H - cam_y) * SCALE)
                c_r, c_g, c_b = vfx["color"]
                fade = max(0.2, 1.0 - prog)
                outer_w = max(4, int(20 * fade))
                mid_w = max(2, int(11 * fade))
                core_w = max(1, int(4 * fade))
                pygame.draw.line(screen, (c_r // 2, c_g // 2, c_b // 2), (x1_s, y1_s), (x2_s, y2_s), outer_w)
                pygame.draw.line(screen, (c_r, c_g, c_b), (x1_s, y1_s), (x2_s, y2_s), mid_w)
                pygame.draw.line(screen, (255, 255, 240), (x1_s, y1_s), (x2_s, y2_s), core_w)
                pygame.draw.circle(screen, (c_r, c_g, c_b), (x1_s, y1_s), int(12 * fade))
                pygame.draw.circle(screen, (255, 255, 240), (x1_s, y1_s), int(6 * fade))
                pygame.draw.circle(screen, (c_r, c_g, c_b), (x2_s, y2_s), int(15 * fade))
                pygame.draw.circle(screen, (255, 255, 240), (x2_s, y2_s), int(7 * fade))

            elif vfx["kind"] == "whirlwind_slash":
                cx_s = int((player.x * TILE_W - cam_x) * SCALE)
                cy_s = int(((player.y - 0.22) * TILE_H - cam_y) * SCALE)
                rad_px = int(vfx["radius"] * TILE_W * SCALE)
                head_ang = prog * math.pi * 2.4
                pts_outer = []
                pts_core = []
                for step_i in range(18):
                    a = head_ang - step_i * 0.16
                    r_cur = rad_px * (1.0 - step_i * 0.015)
                    pts_outer.append((int(cx_s + math.cos(a) * r_cur), int(cy_s + math.sin(a) * r_cur)))
                    if step_i < 10:
                        pts_core.append((int(cx_s + math.cos(a) * r_cur), int(cy_s + math.sin(a) * r_cur)))
                if len(pts_outer) >= 2:
                    pygame.draw.lines(screen, vfx["color"], False, pts_outer, 10)
                if len(pts_core) >= 2:
                    pygame.draw.lines(screen, (255, 250, 235), False, pts_core, 4)

            elif vfx["kind"] == "slam_wave":
                cx_s = int((vfx["x"] * TILE_W - cam_x) * SCALE)
                cy_s = int((vfx["y"] * TILE_H - cam_y) * SCALE)
                base_a = vfx["angle"]
                cur_r = int((0.5 + prog * 1.9) * TILE_W * SCALE)
                arc_pts = []
                for step_i in range(13):
                    frac = (step_i / 12.0) * 2.0 - 1.0
                    a = base_a + frac * 0.85
                    arc_pts.append((int(cx_s + math.cos(a) * cur_r), int(cy_s + math.sin(a) * cur_r)))
                if len(arc_pts) >= 2:
                    pygame.draw.lines(screen, vfx["color"], False, arc_pts, 8)
                    pygame.draw.lines(screen, (255, 235, 180), False, arc_pts, 3)
                for ray_off in (-0.55, 0.0, 0.55):
                    ra = base_a + ray_off
                    ex = int(cx_s + math.cos(ra) * cur_r)
                    ey = int(cy_s + math.sin(ra) * cur_r)
                    pygame.draw.line(screen, vfx["color"], (cx_s, cy_s), (ex, ey), 3)

            elif vfx["kind"] == "aoe_ring":
                cx_s = int((vfx["x"] * TILE_W - cam_x) * SCALE)
                cy_s = int((vfx["y"] * TILE_H - cam_y) * SCALE)
                r_px = int(vfx["radius"] * TILE_W * SCALE * (0.7 + prog * 0.3))
                pygame.draw.circle(screen, vfx["color"], (cx_s, cy_s), max(4, r_px), 3)

            elif vfx["kind"] == "blood_pentagram":
                cx_s = int((vfx["x"] * TILE_W - cam_x) * SCALE)
                cy_s = int((vfx["y"] * TILE_H - cam_y) * SCALE)
                r_px = int(vfx["radius"] * TILE_W * SCALE)
                pulse_col = (255, int(40 + 175 * prog), int(55 + 90 * prog))
                dark_col = (145, 18, 32)
                pygame.draw.circle(screen, dark_col, (cx_s, cy_s), r_px + 3, 4)
                pygame.draw.circle(screen, pulse_col, (cx_s, cy_s), r_px, 2)
                pygame.draw.circle(screen, pulse_col, (cx_s, cy_s), int(r_px * max(0.15, prog)), 1)
                rot = -math.pi * 0.5 + prog * 0.35
                verts = [
                    (int(cx_s + math.cos(rot + i * 2.0 * math.pi / 5.0) * r_px),
                     int(cy_s + math.sin(rot + i * 2.0 * math.pi / 5.0) * r_px))
                    for i in range(5)
                ]
                star_order = [verts[0], verts[2], verts[4], verts[1], verts[3], verts[0]]
                pygame.draw.lines(screen, pulse_col, False, star_order, 3 if prog > 0.6 else 2)
                for vx_p, vy_p in verts:
                    pygame.draw.circle(screen, (255, 220, 120), (vx_p, vy_p), 3)

        # Typewriter Text in Dedicated Thought Box (адаптивно центрируется под SCALE = 4)
        if shown_thought:
            box_max_w = THOUGHT_BOX_W * SCALE - 68
            lines = self.wrap_text(shown_thought, self.font_thought, box_max_w)[:2]
            start_x = THOUGHT_BOX_X * SCALE + 34
            box_px_h = THOUGHT_BOX_H * SCALE
            line_step = 26
            total_txt_h = len(lines) * line_step
            start_y = THOUGHT_BOX_Y * SCALE + (box_px_h - total_txt_h) // 2 + 2
            for idx, ln in enumerate(lines):
                t_sh = self.font_thought.render(ln, True, (10, 8, 12))
                t_fg = self.font_thought.render(ln, True, UI_TEXT_MAIN)
                ly = start_y + idx * line_step
                screen.blit(t_sh, (start_x + 2, ly + 2))
                screen.blit(t_fg, (start_x, ly))

        # Bottom HUD Bar + Golden XP Bar
        hud_y = CANVAS_H * SCALE
        self.draw_pixel_frame(screen, (0, hud_y, SCREEN_W, HUD_HEIGHT), UI_BG_DARK, UI_BORDER_WOOD, False, player.illumination)

        xp_bar_x, xp_bar_y, xp_bar_w, xp_bar_h = 16, hud_y + 7, SCREEN_W - 32, 10
        pygame.draw.rect(screen, (14, 12, 18), (xp_bar_x, xp_bar_y, xp_bar_w, xp_bar_h))
        xp_ratio = min(1.0, player.xp / max(1, player.max_xp))
        if xp_ratio > 0:
            pygame.draw.rect(screen, (235, 185, 55), (xp_bar_x + 1, xp_bar_y + 1, int((xp_bar_w - 2) * xp_ratio), xp_bar_h - 2))
        pygame.draw.rect(screen, UI_BORDER_GOLD, (xp_bar_x, xp_bar_y, xp_bar_w, xp_bar_h), 1)

        # 1. Left of HP/MP Bars: Player Portrait Icon + Level Number Badge (No text labels!)
        port_rect = pygame.Rect(16, hud_y + 22, 58, 58)
        self.draw_pixel_frame(screen, port_rect, UI_SLOT_BG, UI_BORDER_GOLD, False, player.illumination)
        h_diff, _ = self.get_hero_pair(player)
        port_img = pygame.transform.scale(h_diff, (32, 40))
        screen.blit(port_img, (port_rect.x + 13, port_rect.y + 8))
        # Level badge on bottom-right corner of portrait
        lvl_s = self.font_small.render(str(player.level), True, (255, 225, 90))
        pygame.draw.rect(screen, (18, 15, 24), (port_rect.right - lvl_s.get_width() - 8, port_rect.bottom - 18, lvl_s.get_width() + 6, 16))
        pygame.draw.rect(screen, UI_BORDER_GOLD, (port_rect.right - lvl_s.get_width() - 8, port_rect.bottom - 18, lvl_s.get_width() + 6, 16), 1)
        screen.blit(lvl_s, (port_rect.right - lvl_s.get_width() - 5, port_rect.bottom - 17))

        # 2. Label-free HP & Mana Bars
        self._draw_pixel_bar(screen, 80, hud_y + 22, 176, 26, int(player.hp), player.max_hp, (185, 42, 52))
        self._draw_pixel_bar(screen, 80, hud_y + 54, 176, 26, int(player.mp), player.max_mp, (48, 125, 210))

        # 3. Compact Torch & D&D Currency Indicator
        from menu_and_profile import format_copper_Trigger
        self.draw_pixel_frame(screen, (262, hud_y + 22, 88, 58), UI_SLOT_BG, UI_BORDER_WOOD, False, player.illumination)
        torch = player.get_active_torch()
        t_str = "[F] ВКЛ" if (torch and player.torch_on) else "[F] ТЕНЬ"
        t_col = (255, 200, 75) if (torch and player.torch_on) else (130, 175, 235)
        screen.blit(self.font_small.render(t_str, True, t_col), (270, hud_y + 29))
        coin_s = self.font_small.render(format_copper_Trigger(player.gold, compact=True), True, (255, 215, 80))
        screen.blit(coin_s, (262 + (88 - coin_s.get_width()) // 2, hud_y + 51))

        # 4A. Active Ability Slots [Q] and [E] (с серо-синим фильтром Warcraft 3 при нехватке маны!)
        hovered_hud_item = None
        key_labels = ("Q", "E")
        for i, rect in enumerate(self.ability_rects):
            is_hov = rect.collidepoint(hover_pos)
            item = player.ability_slots[i]
            is_oom = bool(item and item.type in ("spell", "permanent_spell") and player.mp < item.mp_cost)
            bd_col = (58, 78, 118) if is_oom else (item.rarity_color if item else (65, 105, 145))
            self.draw_pixel_frame(screen, rect, UI_SLOT_BG, bd_col, is_hov, player.illumination)
            if item:
                if is_oom:
                    ic_tmp = pygame.Surface((32, 32), pygame.SRCALPHA)
                    self.draw_item_icon(ic_tmp, item.icon, 0, 0, 32)
                    for py_i in range(32):
                        for px_i in range(32):
                            ir, ig, ib, ia = ic_tmp.get_at((px_i, py_i))
                            if ia > 10:
                                lum = int(0.299 * ir + 0.587 * ig + 0.114 * ib)
                                ic_tmp.set_at((px_i, py_i), (min(255, lum // 3 + 32), min(255, lum // 3 + 52), min(255, lum // 2 + 95), ia))
                    screen.blit(ic_tmp, (rect.x + 11, rect.y + 12))
                    oom_ov = pygame.Surface((rect.width - 14, rect.height - 14), pygame.SRCALPHA)
                    oom_ov.fill((22, 36, 68, 95))
                    screen.blit(oom_ov, (rect.x + 7, rect.y + 7))
                else:
                    self.draw_item_icon(screen, item.icon, rect.x + 11, rect.y + 12, 32)

                cd_left = player.cooldowns.get(item.id, 0.0)
                if cd_left > 0.0:
                    cd_ov = pygame.Surface((rect.width - 14, rect.height - 14), pygame.SRCALPHA)
                    cd_ov.fill((10, 8, 16, 175))
                    screen.blit(cd_ov, (rect.x + 7, rect.y + 7))
                    cd_s = self.font_small.render(f"{cd_left:.1f}с", True, (255, 195, 90))
                    screen.blit(cd_s, (rect.centerx - cd_s.get_width() // 2, rect.centery - 6))
                if is_hov:
                    hovered_hud_item = item
            screen.blit(self.font_small.render(key_labels[i], True, (110, 145, 195) if is_oom else (135, 215, 255)), (rect.x + 6, rect.y + 5))

        # 4B. 4 Consumable Slots [1..4]
        for i, rect in enumerate(self.hotbar_rects):
            is_hov = rect.collidepoint(hover_pos)
            item = player.hotbar[i]
            bd_col = item.rarity_color if item else UI_BORDER_WOOD
            self.draw_pixel_frame(screen, rect, UI_SLOT_BG, bd_col, is_hov, player.illumination)
            if item:
                self.draw_item_icon(screen, item.icon, rect.x + 10, rect.y + 12, 32)
                cd_left = player.cooldowns.get(item.id, 0.0)
                if cd_left > 0.0:
                    cd_ov = pygame.Surface((rect.width - 14, rect.height - 14), pygame.SRCALPHA)
                    cd_ov.fill((10, 8, 16, 175))
                    screen.blit(cd_ov, (rect.x + 7, rect.y + 7))
                    cd_s = self.font_small.render(f"{cd_left:.1f}с", True, (255, 195, 90))
                    screen.blit(cd_s, (rect.centerx - cd_s.get_width() // 2, rect.centery - 6))
                if is_hov:
                    hovered_hud_item = item
            screen.blit(self.font_small.render(str(i + 1), True, UI_BORDER_HIGHLIGHT), (rect.x + 6, rect.y + 5))

        # 5. 5 Passive Perk Slots with Hover Tooltip!
        from config import RARITY_COLORS
        perks_db = ui_texts.get("_perks_db", {})
        owned_passives = list(player.passive_perks.items())
        hovered_passive = None
        for p_idx, pr in enumerate(self.passive_slot_rects):
            if p_idx < len(owned_passives):
                pid, plvl = owned_passives[p_idx]
                pdata = perks_db.get(pid, {})
                p_col = RARITY_COLORS.get(pdata.get("rarity", "common"), UI_BORDER_GOLD)
                is_p_hov = pr.collidepoint(hover_pos)
                self.draw_pixel_frame(screen, pr, UI_SLOT_BG, p_col, is_p_hov, player.illumination)
                self.draw_item_icon(screen, pdata.get("icon", "trinket"), pr.x + 8, pr.y + 8, 32)
                lv_txt = self.font_small.render(str(plvl), True, (255, 235, 110))
                pygame.draw.rect(screen, (14, 12, 18), (pr.right - lv_txt.get_width() - 6, pr.bottom - 16, lv_txt.get_width() + 4, 14))
                screen.blit(lv_txt, (pr.right - lv_txt.get_width() - 4, pr.bottom - 16))
                if is_p_hov:
                    hovered_passive = (pid, plvl, pdata)
            else:
                self.draw_pixel_frame(screen, pr, (18, 15, 22), (65, 52, 48), False, player.illumination)

        # 6. Far Right: Inventory Button [I] + Occupied/Unlocked Slots Counter
        bag_hov = self.bag_btn_rect.collidepoint(hover_pos) or inv_open
        self.draw_pixel_frame(screen, self.bag_btn_rect, (52, 40, 36) if bag_hov else UI_PANEL_BG, UI_BORDER_GOLD, bag_hov, player.illumination)
        self.draw_item_icon(screen, "bag_small", self.bag_btn_rect.x + 8, self.bag_btn_rect.y + 10, 32)
        used_slots = sum(1 for i in range(player.unlocked_slots) if player.inventory[i] is not None)
        slot_col = (255, 110, 95) if used_slots >= player.unlocked_slots else (255, 220, 95)
        screen.blit(self.font_ui.render(ui_texts["bag_btn"], True, UI_TEXT_MAIN), (self.bag_btn_rect.x + 42, self.bag_btn_rect.y + 10))
        cnt_surf = self.font_small.render(f"Яч: {used_slots}/{player.unlocked_slots}", True, slot_col)
        screen.blit(cnt_surf, (self.bag_btn_rect.x + 42, self.bag_btn_rect.y + 29))

        world_hover_item = ui_texts.get("_world_hover_item")
        if levelup_choices:
            self._render_levelup_modal(screen, player, levelup_choices, ui_texts, hover_pos)
        elif inv_open:
            self._render_character_sheet_modal(screen, player, ui_texts, hover_pos, drag_item)
        elif hovered_hud_item:
            self._render_item_tooltip(screen, player, hovered_hud_item, ui_texts, hover_pos, compare=False)
        elif hovered_passive:
            self._render_passive_perk_tooltip(screen, player, hovered_passive, ui_texts, hover_pos)
        elif world_hover_item:
            self._render_item_tooltip(screen, player, world_hover_item, ui_texts, hover_pos, compare=True, world_item=True)

    def _draw_pixel_bar(self, screen, x, y, w, h, cur, maximum, fill_col):
        pygame.draw.rect(screen, UI_BORDER_OUTER, (x, y, w, h))
        pygame.draw.rect(screen, UI_BORDER_WOOD, (x + 2, y + 2, w - 4, h - 4))
        pygame.draw.rect(screen, (28, 18, 24), (x + 4, y + 4, w - 8, h - 8))
        ratio = max(0.0, min(1.0, cur / max(1, maximum)))
        fill_w = int((w - 8) * ratio)
        if fill_w > 0:
            pygame.draw.rect(screen, fill_col, (x + 4, y + 4, fill_w, h - 8))
            pygame.draw.rect(screen, (255, 255, 255), (x + 4, y + 4, fill_w, 3))
        txt = self.font_small.render(f"{cur}/{maximum}", True, UI_TEXT_MAIN)
        screen.blit(txt, (x + (w - txt.get_width()) // 2, y + 5))

    def _clean_perk_desc(self, raw_desc):
        """Strips redundant uppercase prefix like 'ЗАКЛИНАНИЕ (3 Маны | КД 1.4с): ' from perk descriptions."""
        if ":" in raw_desc:
            head, tail = raw_desc.split(":", 1)
            if any(k in head.upper() for k in ("ЗАКЛИНАНИЕ", "БОЕВОЙ ПРИЁМ", "ПАССИВНО", "АВТО-МАГИЯ")):
                return tail.strip()
        return raw_desc.strip()

    def _get_perk_progression_lines(self, player, pid, pdata, cur_lvl, target_lvl):
        """Returns concrete numerical stat lines (or Old -> New additive % comparisons from base) for levelup cards."""
        is_upgrade = (cur_lvl > 0 and target_lvl > cur_lvl)
        if pdata.get("type") == "active":
            is_combat = (pdata.get("skill_kind") == "combat")
            stat_add = player.phys_attack if is_combat else player.mag_attack
            existing_sp = next((h for h in player.ability_slots if h and h.id == pid), None)
            upg_roll = pdata.get("upgrade_roll", {})
            stat_labels = {
                "power": "Регенерация ХП" if pid == "persephone_rejuvenation" else ("Урон горения" if pid == "pyro_ignite" else "Урон"),
                "cooldown": "Перезарядка",
                "duration": "Длительность",
                "status_dur": "Время контроля",
                "aoe_radius": "Область",
                "bounces": "Отскоки",
            }
            if not is_upgrade or existing_sp is None:
                lines = []
                for st_k in pdata.get("upgradable_stats", ["power", "cooldown"]):
                    lbl = stat_labels.get(st_k, st_k)
                    val = pdata.get(st_k, 0)
                    if st_k == "power":
                        tot = int(math.floor(val + stat_add))
                        lines.append(f"{lbl}: {tot} ({int(val)}+{stat_add})")
                    elif st_k in ("cooldown", "duration", "status_dur"):
                        lines.append(f"{lbl}: {float(val):.2f}с")
                    elif st_k == "aoe_radius":
                        lines.append(f"{lbl}: {float(val):.1f}м")
                    elif st_k == "bounces":
                        lines.append(f"{lbl}: {int(val)}")
                return lines
            else:
                lines = []
                for st_k, add_pct in upg_roll.items():
                    lbl = stat_labels.get(st_k, st_k)
                    base_v = existing_sp.base_stats.get(st_k, pdata.get(st_k, 0))
                    old_pct = existing_sp.stat_bonuses_pct.get(st_k, 0.0)
                    new_pct = old_pct + add_pct
                    o_val = player.eval_stat_with_pct(pid, st_k, base_v, old_pct)
                    n_val = player.eval_stat_with_pct(pid, st_k, base_v, new_pct)
                    pct_int = int(round(add_pct * 100))
                    if st_k == "power":
                        o_tot = int(math.floor(o_val + stat_add))
                        n_tot = int(math.floor(n_val + stat_add))
                        lines.append(f"{lbl}: {o_tot} -> {n_tot} (+{pct_int}%)")
                    elif st_k in ("cooldown", "duration", "status_dur"):
                        lines.append(f"{lbl}: {o_val:.2f}с -> {n_val:.2f}с (+{pct_int}%)")
                    elif st_k == "aoe_radius":
                        lines.append(f"{lbl}: {o_val:.1f}м -> {n_val:.1f}м (+{pct_int}%)")
                    elif st_k == "bounces":
                        lines.append(f"{lbl}: {int(o_val)} -> {int(n_val)} (+{pct_int}%)")
                return lines

        # Passive perks numerical breakdown
        def fmt(label, per_lvl, unit="", is_float=False):
            if not is_upgrade:
                v = per_lvl * max(1, target_lvl)
                val_s = f"{v:.2f}" if is_float else f"{int(v)}"
                return f"{label}: + {val_s}{unit}" if per_lvl > 0 else f"{label}: {val_s}{unit}"
            v0 = per_lvl * cur_lvl
            v1 = per_lvl * target_lvl
            s0 = f"{v0:.2f}" if is_float else f"{int(v0)}"
            s1 = f"{v1:.2f}" if is_float else f"{int(v1)}"
            sign = "+" if per_lvl > 0 else ""
            return f"{label}: {sign}{s0}{unit} -> {sign}{s1}{unit}"

        if pid == "tough_skin":
            return [fmt("Макс. здоровье", 8, " ХП")]
        elif pid == "iron_grip":
            return [fmt("Физ. атака", 2, " ед.")]
        elif pid == "clear_mind":
            return [fmt("Маг. мощь", 2, " ед."), fmt("Макс. мана", 3, " МП")]
        elif pid == "cat_step":
            return [fmt("Шум шагов", -18, "%"), fmt("Уклонение", 5, "%")]
        elif pid == "keen_edge":
            return [fmt("Шанс крита", 8, "%"), fmt("Тело (Сила)", 1, " ед.")]
        elif pid == "stone_ribs":
            return [fmt("Физ. и Маг. броня", 3, " ед.")]
        elif pid == "blood_hunger":
            return [fmt("Вампиризм в бою", 2, " ХП")]
        elif pid == "titan_blood":
            return [fmt("Макс. здоровье", 18, " ХП"), fmt("Физ. броня", 3, " ед."), fmt("Реген ХП", 1.2, "/с", True)]
        elif pid == "storm_aura":
            if not is_upgrade:
                l_use = max(1, target_lvl)
                dmg = max(1, 1 + l_use + player.mag_attack // 4)
                cd = max(1.35, 3.0 - (l_use - 1) * 0.35)
                return [f"Урон авто-молнии: {dmg} ед.", f"Интервал разряда: {cd:.2f}с"]
            d0 = max(1, 1 + cur_lvl + player.mag_attack // 4)
            d1 = max(1, 1 + target_lvl + player.mag_attack // 4)
            c0 = max(1.35, 3.0 - (cur_lvl - 1) * 0.35)
            c1 = max(1.35, 3.0 - (target_lvl - 1) * 0.35)
            return [f"Урон молнии: {d0} -> {d1}", f"Интервал: {c0:.2f}с -> {c1:.2f}с"]
        return []

    def _render_passive_perk_tooltip(self, screen, player, passive_tuple, ui_texts, mouse_pos):
        from config import RARITY_COLORS
        pid, plvl, pdata = passive_tuple
        r_col = RARITY_COLORS.get(pdata.get("rarity", "common"), UI_BORDER_GOLD)
        rar_title = ui_texts["rarities"].get(pdata.get("rarity", "common"), "Особенность")

        lines = [(f"{rar_title} (Пассивный дар, Ур.{plvl})", r_col)]
        for st_line in self._get_perk_progression_lines(player, pid, pdata, plvl, plvl):
            lines.append((st_line, (125, 240, 155)))
        clean_d = self._clean_perk_desc(pdata.get("desc", ""))
        for d_ln in self.wrap_text(clean_d, self.font_small, 265):
            lines.append((d_ln, UI_TEXT_DIM))

        card_w = 295
        card_h = 46 + len(lines) * 19
        tx = max(16, min(SCREEN_W - card_w - 16, mouse_pos[0] - card_w // 2))
        ty = max(16, mouse_pos[1] - card_h - 18)

        self.draw_pixel_frame(screen, (tx, ty, card_w, card_h), (20, 17, 26), r_col, False, 1.0)
        screen.blit(self.font_ui.render(pdata.get("name", pid), True, r_col), (tx + 14, ty + 12))
        for i, (txt, col) in enumerate(lines):
            screen.blit(self.font_small.render(txt, True, col), (tx + 14, ty + 36 + i * 19))

    def _render_levelup_modal(self, screen, player, modal_data, ui_texts, hover_pos):
        from config import RARITY_COLORS
        choices = modal_data["choices"]
        lock_timer = modal_data.get("lock_timer", 0.0)
        is_erase_mode = modal_data.get("mode") == "erase"

        overlay = pygame.Surface((SCREEN_W, VIEW_H * SCALE), pygame.SRCALPHA)
        overlay.fill((8, 6, 14, 195))
        screen.blit(overlay, (0, 0))

        if is_erase_mode:
            banner_txt = "ПЕЧАТЬ ЗАБВЕНИЯ: ВЫБЕРИ ОСОБЕННОСТЬ ДЛЯ СТИРАНИЯ [ПКМ — Отмена]"
            b_col = (225, 120, 255)
        elif lock_timer > 0.0:
            banner_txt = f"НОВЫЙ УРОВЕНЬ ({player.level})! Защита от случайного клика: {lock_timer:.1f} сек..."
            b_col = (180, 175, 190)
        else:
            banner_txt = f"НОВЫЙ УРОВЕНЬ ({player.level})! ВЫБЕРИ ДАР [Акт: {len(player.active_perks)}/2 | Пасс: {len(player.passive_perks)}/5]"
            b_col = UI_BORDER_HIGHLIGHT

        b_surf = self.font_title.render(banner_txt, True, b_col)
        screen.blit(b_surf, ((SCREEN_W - b_surf.get_width()) // 2, 42))

        self.perk_card_rects = []
        n_cards = len(choices)
        if n_cards == 0:
            return
        card_w = 215 if n_cards > 3 else 292
        card_h = 355
        gap = 14 if n_cards > 3 else 26
        total_w = n_cards * card_w + (n_cards - 1) * gap
        start_x = (SCREEN_W - total_w) // 2
        card_y = 88

        for idx, perk in enumerate(choices):
            rect = pygame.Rect(start_x + idx * (card_w + gap), card_y, card_w, card_h)
            self.perk_card_rects.append(rect)
            is_hov = rect.collidepoint(hover_pos) and (lock_timer <= 0.0)
            r_col = RARITY_COLORS.get(perk["rarity"], (215, 215, 220))

            self.draw_pixel_frame(screen, rect, (32, 26, 42) if is_hov else (22, 18, 30), r_col, is_hov, 1.0)

            k_lbl = self.font_ui.render(f"[{idx + 1}]", True, UI_BORDER_HIGHLIGHT)
            screen.blit(k_lbl, (rect.x + 12, rect.y + 12))

            cur_lvl = player.perks.get(perk["id"], 0)
            if is_erase_mode:
                lvl_str = f"СТЕРЕТЬ (Ур.{cur_lvl})"
                l_col = (255, 95, 95)
            else:
                lvl_str = f"Ур.{cur_lvl} -> {cur_lvl + 1}" if cur_lvl > 0 else ("АКТИВ [Q/E]" if perk.get("type") == "active" else "ПАССИВ")
                l_col = (130, 240, 160) if cur_lvl > 0 else ((110, 210, 255) if perk.get("type") == "active" else UI_TEXT_DIM)

            l_surf = self.font_small.render(lvl_str, True, l_col)
            screen.blit(l_surf, (rect.right - 12 - l_surf.get_width(), rect.y + 14))

            ic_box = pygame.Rect(rect.centerx - 28, rect.y + 42, 56, 56)
            self.draw_pixel_frame(screen, ic_box, UI_SLOT_BG, r_col, False, 1.0)
            self.draw_item_icon(screen, perk["icon"], ic_box.x + 12, ic_box.y + 12, 32)

            n_surf = self.font_ui.render(perk["name"][:22], True, r_col)
            screen.blit(n_surf, (rect.centerx - n_surf.get_width() // 2, rect.y + 108))

            rar_name = ui_texts["rarities"].get(perk["rarity"], perk["rarity"])
            r_surf = self.font_small.render(rar_name, True, UI_TEXT_DIM)
            screen.blit(r_surf, (rect.centerx - r_surf.get_width() // 2, rect.y + 128))

            pygame.draw.line(screen, r_col, (rect.x + 16, rect.y + 150), (rect.right - 16, rect.y + 150), 1)

            # Numerical stat lines / Old -> New upgrade preview!
            target_lvl = cur_lvl if is_erase_mode else (cur_lvl + 1)
            stat_lines = self._get_perk_progression_lines(player, perk["id"], perk, cur_lvl, target_lvl)
            cur_y = rect.y + 160
            for st_ln in stat_lines:
                st_col = (115, 245, 145) if cur_lvl > 0 and not is_erase_mode else (255, 215, 110)
                st_s = self.font_small.render(st_ln[:28], True, st_col)
                screen.blit(st_s, (rect.centerx - st_s.get_width() // 2, cur_y))
                cur_y += 18

            cur_y += 6
            clean_desc = self._clean_perk_desc(perk.get("desc", ""))
            desc_lines = self.wrap_text(clean_desc, self.font_small, card_w - 26)
            for ln in desc_lines[:5]:
                if cur_y + 16 > rect.bottom - 10:
                    break
                d_s = self.font_small.render(ln, True, UI_TEXT_MAIN)
                screen.blit(d_s, (rect.centerx - d_s.get_width() // 2, cur_y))
                cur_y += 18

    def _render_character_sheet_modal(self, screen, player, ui_texts, hover_pos, drag_item):
        win_w, win_h = 960, 510
        wx = (SCREEN_W - win_w) // 2
        wy = (VIEW_H * SCALE - win_h) // 2 + 20
        self.modal_rect = pygame.Rect(wx, wy, win_w, win_h)

        self.draw_pixel_frame(screen, self.modal_rect, UI_PANEL_BG, UI_BORDER_GOLD, False, 1.0)
        journal_open = ui_texts.get("_journal_open", False)

        # Кнопка переключения между Куклой Героя и Журналом в правом верхнем углу окна инвентаря
        self.journal_btn_rect = pygame.Rect(wx + win_w - 224, wy + 10, 204, 32)
        j_hov = self.journal_btn_rect.collidepoint(hover_pos)
        j_bg = (58, 46, 40) if (j_hov or journal_open) else UI_SLOT_BG
        self.draw_pixel_frame(screen, self.journal_btn_rect, j_bg, UI_BORDER_GOLD, j_hov or journal_open, 1.0)
        j_lbl_txt = "НАЗАД К ГЕРОЮ" if journal_open else "ЖУРНАЛ ЗАПИСЕЙ [J]"
        j_lbl = self.font_small.render(j_lbl_txt, True, (255, 230, 110) if journal_open else UI_TEXT_MAIN)
        screen.blit(j_lbl, (self.journal_btn_rect.centerx - j_lbl.get_width() // 2, self.journal_btn_rect.centery - j_lbl.get_height() // 2))

        if journal_open:
            self._render_journal_view(screen, wx, wy, win_w, win_h, ui_texts, hover_pos)
            return

        title = self.font_title.render(f"{ui_texts['inv_title']} — {player.full_name} ({ui_texts['lvl']} {player.level})", True, UI_BORDER_HIGHLIGHT)
        screen.blit(title, (wx + 24, wy + 16))

        col1_rect = pygame.Rect(wx + 18, wy + 48, 250, 418)
        self.draw_pixel_frame(screen, col1_rect, UI_SLOT_BG, UI_BORDER_WOOD, False, 1.0)

        xp_txt = self.font_small.render(f"{ui_texts['xp']}: {player.xp} / {player.max_xp}", True, (245, 205, 80))
        screen.blit(xp_txt, (col1_rect.x + 16, col1_rect.y + 14))
        pygame.draw.rect(screen, (14, 12, 18), (col1_rect.x + 16, col1_rect.y + 34, 218, 10))
        ratio = min(1.0, player.xp / max(1, player.max_xp))
        pygame.draw.rect(screen, (235, 185, 55), (col1_rect.x + 17, col1_rect.y + 35, int(216 * ratio), 8))

        self.stat_plus_rects = {}
        primary_stats = [
            ("body", ui_texts["body"], player.body, (235, 145, 130)),
            ("cunning", ui_texts["cunning"], player.cunning, (135, 230, 165)),
            ("mind", ui_texts["mind"], player.mind, (150, 200, 255)),
        ]
        for idx, (st_key, st_label, st_val, st_col) in enumerate(primary_stats):
            ry = col1_rect.y + 56 + idx * 38
            pygame.draw.rect(screen, (32, 27, 38), (col1_rect.x + 14, ry, 222, 32))
            pygame.draw.rect(screen, (75, 62, 55), (col1_rect.x + 14, ry, 222, 32), 1)
            screen.blit(self.font_ui.render(st_label, True, UI_TEXT_MAIN), (col1_rect.x + 20, ry + 7))
            screen.blit(self.font_title.render(str(st_val), True, st_col), (col1_rect.x + 166, ry + 6))

        ledger_y = col1_rect.y + 180
        pygame.draw.line(screen, UI_BORDER_WOOD, (col1_rect.x + 14, ledger_y - 6), (col1_rect.right - 14, ledger_y - 6), 2)
        derived = [
            (ui_texts["phys_atk"], f"{player.phys_attack} (Крит {int(player.crit_chance*100)}%)"),
            (ui_texts["mag_atk"], f"+{player.mag_attack} (Удар +{player.mp_on_hit:.1f} МП)"),
            (ui_texts["phys_def"], f"{player.phys_defense} ед."),
            (ui_texts["mag_def"], f"{player.mag_defense} ед."),
            ("Уклонение", f"{int(player.dodge_chance*100)}%"),
            (ui_texts["noise"], f"{int(player.noise_factor*100)}%"),
            (ui_texts["vision"], f"{int(player.torch_light_radius)}/{int(player.dark_vision_radius)}"),
            ("Способности", f"Акт:{len(player.active_perks)}/2 Пасс:{len(player.passive_perks)}/5"),
        ]
        for idx, (k_txt, v_txt) in enumerate(derived):
            ly = ledger_y + idx * 27
            if idx % 2 == 0:
                pygame.draw.rect(screen, (28, 24, 34), (col1_rect.x + 14, ly - 2, 222, 24))
            screen.blit(self.font_small.render(k_txt, True, UI_TEXT_DIM), (col1_rect.x + 18, ly + 2))
            v_surf = self.font_small.render(v_txt, True, UI_TEXT_MAIN)
            screen.blit(v_surf, (col1_rect.right - 18 - v_surf.get_width(), ly + 2))

        col2_rect = pygame.Rect(wx + 278, wy + 48, 274, 418)
        self.draw_pixel_frame(screen, col2_rect, UI_SLOT_BG, UI_BORDER_WOOD, False, 1.0)

        ped_rect = pygame.Rect(col2_rect.x + 89, col2_rect.y + 104, 96, 116)
        self.draw_pixel_frame(screen, ped_rect, (18, 15, 22), UI_BORDER_WOOD, False, 1.0)
        h_diff, _ = self.get_hero_pair(player)
        big_hero = pygame.transform.scale(h_diff, (16 * 4, 20 * 4))
        screen.blit(big_hero, (ped_rect.x + 16, ped_rect.y + 18))

        cx = col2_rect.x + 137
        cy = col2_rect.y + 162
        doll_layout = {
            "helmet":     pygame.Rect(cx - 32, col2_rect.y + 18, 64, 68),
            "trinket":    pygame.Rect(col2_rect.right - 80, col2_rect.y + 18, 64, 68),
            "right_hand": pygame.Rect(col2_rect.x + 16, cy - 42, 64, 68),
            "left_hand":  pygame.Rect(col2_rect.right - 80, cy - 42, 64, 68),
            "torso":      pygame.Rect(cx - 32, cy + 68, 64, 68),
            "ring_1":     pygame.Rect(col2_rect.x + 16, cy + 42, 64, 68),
            "ring_2":     pygame.Rect(col2_rect.right - 80, cy + 42, 64, 68),
            "boots":      pygame.Rect(cx - 32, col2_rect.bottom - 82, 64, 68),
            "bag":        pygame.Rect(col2_rect.x + 16, col2_rect.bottom - 82, 64, 68),
        }
        self.equip_slot_rects = doll_layout
        hovered_item = None
        hovered_from_inventory = False

        main_weap = player.equipment["right_hand"]
        two_hand_active = main_weap is not None and main_weap.two_handed

        for s_key, s_rect in doll_layout.items():
            is_hov = s_rect.collidepoint(hover_pos)
            itm = player.equipment.get(s_key) if s_key != "bag" else None
            bd_col = itm.rarity_color if itm else UI_BORDER_WOOD
            self.draw_pixel_frame(screen, s_rect, UI_PANEL_BG, bd_col, is_hov, 1.0)

            lbl_str = ui_texts["slots"][s_key][:8]
            lbl_s = self.font_small.render(lbl_str, True, UI_TEXT_DIM)
            screen.blit(lbl_s, (s_rect.x + (s_rect.width - lbl_s.get_width()) // 2, s_rect.y + 48))

            if s_key == "bag":
                ic = "bag_big" if player.unlocked_slots >= 15 else ("bag_small" if player.unlocked_slots >= 6 else None)
                if ic:
                    self.draw_item_icon(screen, ic, s_rect.x + 16, s_rect.y + 10, 32)
            elif s_key == "left_hand" and two_hand_active:
                self.draw_item_icon(screen, main_weap.icon, s_rect.x + 16, s_rect.y + 10, 32)
                lk = self.font_small.render("2H", True, (220, 120, 120))
                screen.blit(lk, (s_rect.x + 8, s_rect.y + 8))
            elif itm:
                self.draw_item_icon(screen, itm.icon, s_rect.x + 16, s_rect.y + 10, 32)
                if is_hov:
                    hovered_item = itm
                    hovered_from_inventory = False

        col3_rect = pygame.Rect(wx + 562, wy + 48, 380, 418)
        self.draw_pixel_frame(screen, col3_rect, UI_SLOT_BG, UI_BORDER_WOOD, False, 1.0)
        p_head = self.font_ui.render(f"{player.bag_name} [{player.unlocked_slots}/24]", True, UI_BORDER_HIGHLIGHT)
        screen.blit(p_head, (col3_rect.x + 16, col3_rect.y + 12))

        self.inv_slot_rects = []
        grid_x, grid_y = col3_rect.x + 14, col3_rect.y + 38

        for idx in range(player.max_possible_slots):
            col = idx % 4
            row = idx // 4
            sr = pygame.Rect(grid_x + col * 89, grid_y + row * 61, 84, 57)
            self.inv_slot_rects.append(sr)
            unlocked = idx < player.unlocked_slots
            is_hov = sr.collidepoint(hover_pos) and unlocked

            if not unlocked:
                self.draw_pixel_frame(screen, sr, (16, 14, 20), (55, 45, 50), False, 1.0)
                self.draw_item_icon(screen, "lock", sr.x + 26, sr.y + 12, 32)
            else:
                itm = player.inventory[idx]
                bd_col = itm.rarity_color if itm else UI_BORDER_WOOD
                self.draw_pixel_frame(screen, sr, UI_PANEL_BG, bd_col, is_hov, 1.0)
                if itm:
                    self.draw_item_icon(screen, itm.icon, sr.x + 26, sr.y + 6, 32)
                    short_name = itm.name.split(" ")[0][:8]
                    nm = self.font_small.render(short_name, True, itm.rarity_color)
                    screen.blit(nm, (sr.x + (sr.width - nm.get_width()) // 2, sr.y + 38))
                    if is_hov:
                        hovered_item = itm
                        hovered_from_inventory = True

        hint_s = self.font_small.render("ЛКМ — Использовать/Надеть | Цифры [1-4] — Расходник на пояс | ПКМ — Выбросить", True, UI_TEXT_DIM)
        screen.blit(hint_s, (wx + (win_w - hint_s.get_width()) // 2, wy + win_h - 26))

        if drag_item:
            self.draw_item_icon(screen, drag_item.icon, hover_pos[0] - 16, hover_pos[1] - 16, 32)
        elif hovered_item:
            self._render_item_tooltip(screen, player, hovered_item, ui_texts, hover_pos, compare=hovered_from_inventory)

    def _render_journal_view(self, screen, wx, wy, win_w, win_h, ui_texts, hover_pos):
        title = self.font_title.render("ЖУРНАЛ ПОХОДА (ПОСЛЕДНИЕ 100 ЗАПИСЕЙ)", True, UI_BORDER_HIGHLIGHT)
        screen.blit(title, (wx + 24, wy + 16))

        filters = ui_texts.get("_journal_filters", {"combat": True, "event": True, "speech": True})
        logs = ui_texts.get("_journal_logs", [])
        scroll = int(ui_texts.get("_journal_scroll", 0))

        # Панель из 3 чекбоксов фильтрации
        filter_defs = [
            ("combat", "Боевые логи", (245, 135, 125)),
            ("event",  "События",     (245, 215, 110)),
            ("speech", "Реплики",     (135, 215, 255)),
        ]
        self.journal_filter_rects = {}
        fx_cur = wx + 24
        fy_cur = wy + 50
        for f_key, f_name, f_col in filter_defs:
            f_rect = pygame.Rect(fx_cur, fy_cur, 195, 32)
            self.journal_filter_rects[f_key] = f_rect
            is_on = filters.get(f_key, True)
            hov = f_rect.collidepoint(hover_pos)
            bg = (36, 48, 40) if is_on else (28, 22, 30)
            if hov:
                bg = (48, 64, 52) if is_on else (40, 30, 42)
            pygame.draw.rect(screen, bg, f_rect, border_radius=4)
            pygame.draw.rect(screen, f_col if is_on else UI_BORDER_WOOD, f_rect, 1, border_radius=4)
            mark = "[✓]" if is_on else "[ ]"
            txt_s = self.font_small.render(f"{mark} {f_name}", True, f_col if is_on else UI_TEXT_DIM)
            screen.blit(txt_s, (f_rect.x + 12, f_rect.y + 8))
            fx_cur += 208

        filtered_logs = [entry for entry in logs if filters.get(entry["cat"], True)]
        cnt_s = self.font_small.render(f"Записей: {len(filtered_logs)} / {len(logs)}", True, UI_TEXT_DIM)
        screen.blit(cnt_s, (wx + win_w - cnt_s.get_width() - 28, fy_cur + 8))

        # Основное поле списка записей
        box_rect = pygame.Rect(wx + 20, wy + 90, win_w - 40, win_h - 130)
        self.draw_pixel_frame(screen, box_rect, UI_SLOT_BG, UI_BORDER_WOOD, False, 1.0)

        tag_map = {
            "combat": ("[БОЙ]",     (245, 130, 120)),
            "event":  ("[СОБЫТИЕ]", (245, 215, 105)),
            "speech": ("[РЕПЛИКА]", (130, 215, 255)),
        }

        # Разбиваем отфильтрованные записи на строки с переносом
        rendered_rows = []
        max_text_w = box_rect.width - 145
        for entry in filtered_logs:
            cat = entry["cat"]
            tag_str, tag_col = tag_map.get(cat, ("[ЛОГ]", UI_TEXT_DIM))
            col = entry.get("color") or tag_col
            wrapped = self.wrap_text(entry["text"], self.font_small, max_text_w)
            for idx_w, ln in enumerate(wrapped):
                rendered_rows.append((tag_str if idx_w == 0 else "", tag_col, ln, col))

        line_h = 20
        vis_rows = (box_rect.height - 20) // line_h
        max_scroll = max(0, len(rendered_rows) - vis_rows)
        scroll = max(0, min(max_scroll, scroll))

        start_idx = max(0, len(rendered_rows) - vis_rows - scroll)
        end_idx = len(rendered_rows) - scroll
        visible_slice = rendered_rows[start_idx:end_idx]

        row_y = box_rect.y + 12
        for tag_str, tag_col, ln_txt, ln_col in visible_slice:
            if tag_str:
                t_s = self.font_small.render(tag_str, True, tag_col)
                screen.blit(t_s, (box_rect.x + 14, row_y))
            l_s = self.font_small.render(ln_txt, True, ln_col)
            screen.blit(l_s, (box_rect.x + 110, row_y))
            row_y += line_h

        # Ползунок прокрутки справа
        if max_scroll > 0:
            track_x = box_rect.right - 14
            track_y = box_rect.y + 10
            track_h = box_rect.height - 20
            pygame.draw.rect(screen, (14, 12, 18), (track_x, track_y, 6, track_h))
            thumb_h = max(24, int(track_h * (vis_rows / max(1, len(rendered_rows)))))
            scroll_ratio = 1.0 - (scroll / max(1, max_scroll))
            thumb_y = track_y + int((track_h - thumb_h) * scroll_ratio)
            pygame.draw.rect(screen, UI_BORDER_GOLD, (track_x, thumb_y, 6, thumb_h), border_radius=2)

        hint_s = self.font_small.render("Колесо мыши — Прокрутка журнала | Галочки сверху — Фильтр категорий | [J] — Закрыть журнал", True, UI_TEXT_DIM)
        screen.blit(hint_s, (wx + (win_w - hint_s.get_width()) // 2, wy + win_h - 26))

    def _build_item_stat_lines(self, player, item, ui_texts, comp_item=None):
        from menu_and_profile import format_copper_Trigger
        lines = []
        rarity_title = ui_texts["rarities"].get(item.rarity, item.rarity)
        lines.append((rarity_title, item.rarity_color))

        # Лаконичный формат для Драгоценностей и Монет
        if item.type in ("gem", "currency_coin"):
            lines.append((format_copper_Trigger(item.copper_value), (255, 220, 85)))
            lines.append(("Драгоценность." if item.type == "gem" else "Монеты.", UI_TEXT_MAIN))
            for d_ln in self.wrap_text(item.desc, self.font_small, 260):
                lines.append((d_ln, UI_TEXT_DIM))
            return lines

        if getattr(item, "heal_hp", 0) > 0:
            eff_heal = player.get_heal_amount(item)
            bonus_tag = " (+25% Ипохондрик)" if eff_heal > item.heal_hp else ""
            lines.append((f"Исцеление: +{eff_heal} ХП{bonus_tag}", (115, 245, 140)))

        if getattr(item, "god", ""):
            lines.append((f"Покровитель: {item.god}", (255, 215, 95)))

        if item.type == "consumable_spell":
            tot_scroll = int(math.floor(item.power * 1.65 + player.mag_attack * 1.5))
            lines.append((f"Одноразовый свиток (КД {item.cooldown:.1f}с): Урон {tot_scroll}", (120, 225, 255)))
        elif item.type == "permanent_spell":
            tot_spell = int(math.floor(item.power + player.mag_attack))
            pwr_lbl = "Исцеление" if item.id == "persephone_rejuvenation" else ("Урон горения" if item.id == "pyro_ignite" else "Урон")
            lines.append((f"Заклинание ({item.mp_cost} Маны | КД {item.cooldown:.2f}с): {pwr_lbl} {tot_spell}", (130, 240, 165)))
        elif item.type == "combat_skill":
            tot_skill = int(math.floor(item.power + player.phys_attack))
            lines.append((f"Боевой приём (0 Маны | КД {item.cooldown:.2f}с): Урон {tot_skill}", (255, 205, 110)))

        if getattr(item, "duration", 0.0) > 0.0:
            lines.append((f"Длительность баффа: {item.duration:.2f} сек.", (255, 200, 120)))
        if getattr(item, "status_dur", 0.0) > 0.0:
            lines.append((f"Время контроля: {item.status_dur:.2f} сек.", (165, 225, 255)))
        if getattr(item, "aoe_radius", 0.0) > 0.0 and item.cast_type in ("frost_nova", "entangle_cursor", "aoe_cursor"):
            lines.append((f"Радиус области: {item.aoe_radius:.1f} м", (165, 225, 255)))
        if item.cast_type == "chain_lightning":
            lines.append((f"Макс. отскоков молнии: {int(item.bounces)}", (155, 235, 255)))

        if item.slot == "right_hand":
            spd_str = f"{1.0 / max(0.1, item.atk_cd):.1f} уд/с"
            t_str = "Все в дуге" if item.max_targets > 5 else f"{item.max_targets} ц."
            lines.append((f"Темп: {spd_str} | Дальн: {item.reach:.1f}м | Дуга: {int(item.arc_deg)}° ({t_str})", (255, 210, 125)))
            if item.armor_pierce > 0:
                lines.append((f"Пролом брони: игнорирует {item.armor_pierce} ед. защиты", (255, 165, 95)))
        if item.two_handed:
            lines.append(("Двуручное оружие (Обе руки)", (255, 175, 95)))
        if item.life_steal > 0:
            lines.append((f"Вампиризм: +{item.life_steal} ХП за удар", (245, 95, 110)))
        if item.is_torch:
            lines.append(("Источник вечного огня [Клавиша F]", (255, 215, 90)))
        if getattr(item, "armor_class", "none") == "cloth":
            lines.append(("Поток маны: +1 МП за удар и с осколков", (130, 205, 255)))

        stat_pairs = [
            ("phys_bonus", ui_texts["phys_atk"]),
            ("mag_bonus", ui_texts["mag_atk"]),
            ("phys_def", ui_texts["phys_def"]),
            ("mag_def", ui_texts["mag_def"]),
            ("vision_bonus", ui_texts["vision"]),
        ]
        for attr, label in stat_pairs:
            val = getattr(item, attr, 0)
            old_val = getattr(comp_item, attr, 0) if comp_item else 0
            diff = val - old_val
            if val != 0 or (comp_item and diff != 0):
                base_str = f"{label}: {'+' if val > 0 else ''}{val}"
                if comp_item is not None and diff != 0:
                    d_str = f" ({'+' if diff > 0 else ''}{diff})"
                    col = (100, 240, 120) if diff > 0 else (255, 105, 105)
                    lines.append((base_str + d_str, col))
                else:
                    lines.append((base_str, UI_TEXT_MAIN))

        n_val = int(item.noise_mod * 100)
        n_old = int(comp_item.noise_mod * 100) if comp_item else 0
        n_diff = n_val - n_old
        if n_val != 0 or (comp_item and n_diff != 0):
            b_str = f"{ui_texts['noise']}: {'+' if n_val > 0 else ''}{n_val}%"
            if comp_item is not None and n_diff != 0:
                d_str = f" ({'+' if n_diff > 0 else ''}{n_diff}%)"
                col = (100, 240, 120) if n_diff < 0 else (255, 105, 105)
                lines.append((b_str + d_str, col))
            else:
                lines.append((b_str, UI_TEXT_MAIN))

        clean_desc = self._clean_perk_desc(item.desc)
        for d_ln in self.wrap_text(clean_desc, self.font_small, 260):
            lines.append((d_ln, UI_TEXT_DIM))
        return lines

    def _render_item_tooltip(self, screen, player, item, ui_texts, mouse_pos, compare=False, world_item=False):
        comp_item = player.get_comparison_item(item) if compare else None
        main_lines = self._build_item_stat_lines(player, item, ui_texts, comp_item)

        card_w = 295
        card_h = 46 + len(main_lines) * 19

        if world_item:
            tx, ty = 16, 16
            cx = tx + card_w + 8
        else:
            ty = max(16, min(SCREEN_H - card_h - 16, mouse_pos[1] - card_h // 2))
            total_w = card_w * 2 + 8 if comp_item else card_w
            if mouse_pos[0] + 18 + total_w > SCREEN_W - 12:
                tx = max(16, mouse_pos[0] - card_w - 16)
                cx = max(8, tx - card_w - 8)
            else:
                tx = mouse_pos[0] + 18
                cx = tx + card_w + 8

        self.draw_pixel_frame(screen, (tx, ty, card_w, card_h), (20, 17, 26), item.rarity_color, False, 1.0)
        screen.blit(self.font_ui.render(item.name, True, item.rarity_color), (tx + 14, ty + 12))
        for i, (txt, col) in enumerate(main_lines):
            screen.blit(self.font_small.render(txt, True, col), (tx + 14, ty + 36 + i * 19))

        if comp_item:
            comp_lines = self._build_item_stat_lines(player, comp_item, ui_texts, None)
            ch = 46 + len(comp_lines) * 19
            self.draw_pixel_frame(screen, (cx, ty, card_w, ch), (18, 15, 22), comp_item.rarity_color, False, 1.0)
            screen.blit(self.font_ui.render(f"[Надето] {comp_item.name}", True, comp_item.rarity_color), (cx + 14, ty + 12))
            for i, (txt, col) in enumerate(comp_lines):
                screen.blit(self.font_small.render(txt, True, col), (cx + 14, ty + 36 + i * 19))