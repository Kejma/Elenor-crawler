"""Procedural diffuse + normal asset generator for the Fishing minigame (lake, shore, gear & 47 catches)."""

import math
from elenor.rendering.assets import make_pair, enforce_crisp_rim_normals

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


def _clamp_rgb(r, g, b, a=255):
    return (max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b))), a)


def _build_fish_sprite(spec):
    """Универсальный процедурный генератор силуэта, плавников, чешуи и деталей рыбы."""
    big = spec.get("big", False)
    w, h = (32, 20) if big else (16, 20)
    diff, norm = make_pair(w, h)

    kind = spec.get("kind", "fish")
    c_back = spec["back"]
    c_mid = spec["mid"]
    c_belly = spec["belly"]
    c_fin = spec["fin"]
    c_accent = spec.get("accent", c_fin)
    c_eye = spec.get("eye", (25, 25, 35))
    pat = spec.get("pattern", "scales")

    # 1. СПЕЦИАЛЬНЫЕ ФОРМЫ: Ракушка, Тигровый Рак, Угри/Змеи
    if kind == "shell":
        for y in range(6, 18):
            for x in range(2, 14):
                dx, dy = x - 7.5, y - 12.5
                dist = math.hypot(dx * 0.9, dy * 1.1)
                if dist <= 5.5 or (y >= 15 and abs(dx) <= 2.5):
                    rib = int(math.atan2(dy, dx) * 9.0) % 2 == 0
                    if y == 12 and 4 <= x <= 11:
                        col, nc = c_accent, N_DEEP  # Створка с жемчужным проблеском
                    elif dy < 0:
                        col = c_mid if rib else c_back
                        nc = N_UP if dy < -2 else N_FLAT
                    else:
                        col = c_belly if rib else c_mid
                        nc = N_DOWN
                    diff.set_at((x, y), (*col, 255))
                    norm.set_at((x, y), nc)
        return enforce_crisp_rim_normals(diff, norm)

    if kind == "crayfish":
        # Тигровый рак: клешни сверху, панцирь в тигровых полосках, веерный хвост снизу
        for y in range(3, 19):
            for x in range(2, 14):
                # Большие клешни (y=3..8)
                if 4 <= y <= 8 and x in (2, 3, 4, 11, 12, 13):
                    if y == 4 and x in (3, 12):
                        continue
                    col = c_accent if y <= 5 else c_mid
                    diff.set_at((x, y), (*col, 255))
                    norm.set_at((x, y), N_UP)
                # Головогрудь и брюшко с тигровыми полосами (y=6..16)
                elif 6 <= y <= 16:
                    hw = 3 if y <= 11 else 2
                    if abs(x - 7.5) <= hw:
                        stripe = (y % 2 == 0)
                        col = c_back if stripe else c_mid
                        if y == 7 and x in (6, 9):
                            col = c_eye
                        diff.set_at((x, y), (*col, 255))
                        norm.set_at((x, y), N_LEFT if x < 7 else (N_RIGHT if x > 8 else N_UP))
                    elif y in (9, 11, 13) and abs(x - 7.5) <= 4.5:
                        diff.set_at((x, y), (*c_fin, 255))
                        norm.set_at((x, y), N_FLAT)
                # Хвостовой веер (y=17..18)
                elif y >= 17 and abs(x - 7.5) <= 3.5:
                    diff.set_at((x, y), (*c_fin, 255))
                    norm.set_at((x, y), N_DOWN)
        # Длинные усы
        for ux, uy in ((5, 3), (4, 2), (10, 3), (11, 2)):
            diff.set_at((ux, uy), (*c_accent, 255))
            norm.set_at((ux, uy), N_UP)
        return enforce_crisp_rim_normals(diff, norm)

    if kind == "serpent":
        # Извивающееся змеевидное тело (Угорь, Глубоководный Уж, Извивающаяся Щука)
        for x in range(1, w - 1):
            t = (x - 1) / float(max(1, w - 3))
            cy = 10.5 + math.sin(t * math.pi * 2.1) * 3.2
            thick = 2.4 if 0.15 <= t <= 0.75 else 1.6
            # Спинной гребень/плавник
            if 0.2 <= t <= 0.85:
                fy = int(round(cy - thick - 1))
                if 1 <= fy < h - 1:
                    diff.set_at((x, fy), (*c_fin, 255))
                    norm.set_at((x, fy), N_UP)
            for y in range(1, h - 1):
                dy = y - cy
                if abs(dy) <= thick:
                    if dy < -0.5:
                        col, nc = c_back, N_UP
                    elif dy > 0.7:
                        col, nc = c_belly, N_DOWN
                    else:
                        col, nc = c_mid, N_FLAT
                    if pat == "collar" and x in (3, 4) and dy <= 0.5:
                        col = c_accent  # Жёлтые «ушки» ужа на шее
                    elif pat == "lava" and (x + y) % 3 == 0:
                        col = c_accent  # Раскалённые прожилки обжигающего угря
                    elif pat == "spots" and (x * 3 + y) % 4 == 0:
                        col = c_accent
                    diff.set_at((x, y), (*col, 255))
                    norm.set_at((x, y), nc)
        # Глаз и пасть слева
        hy = int(round(10.5 + math.sin(0.1 * math.pi * 2.1) * 3.2))
        diff.set_at((2, max(2, hy - 1)), (*c_eye, 255))
        norm.set_at((2, max(2, hy - 1)), N_UP)
        return enforce_crisp_rim_normals(diff, norm)

    # 2. ОСНОВНОЙ РЫБИЙ СИЛУЭТ (16x20 и 32x20)
    paddle = (kind == "paddlefish")
    sabre = (kind == "sabre")
    sturgeon = (kind == "sturgeon")
    piranha = (kind == "piranha")
    catfish = (kind == "catfish")
    rotan = (kind == "rotan")

    head_x0 = (6 if big else 4) if paddle else (2 if big else 1)
    body_x1 = (w - 7) if big else (w - 4)
    tail_x1 = w - 2
    cy_base = 10.5
    max_half_h = spec.get("thickness", 4.6 if big else 3.8)
    if piranha:
        max_half_h += 1.4
    elif sabre or sturgeon:
        max_half_h -= 0.9

    # Длинный нос-весло для Веслоносов
    if paddle:
        for x in range(1, head_x0 + 1):
            for y in range(int(cy_base) - 1, int(cy_base) + 2):
                col = c_back if y < cy_base else c_mid
                diff.set_at((x, y), (*col, 255))
                norm.set_at((x, y), N_UP if y < cy_base else N_DOWN)

    # Рисуем спинной, брюшной и анальный плавники ДО тела, чтобы тело легло поверх основания
    dorsal_style = spec.get("dorsal", "normal")
    d_start = head_x0 + (5 if big else 3)
    d_end = body_x1 - (3 if big else 1)
    for x in range(d_start, d_end + 1):
        t = (x - head_x0) / float(max(1, body_x1 - head_x0))
        arch = math.sin(t * math.pi) * max_half_h
        curve_y = -1.2 * math.sin(t * math.pi) if sabre else 0.0
        top_y = int(round(cy_base + curve_y - arch))
        fin_h = 3 if dorsal_style in ("sail", "crown", "spiky") else 2
        if dorsal_style == "spiky" and x % 2 == 1:
            fin_h = 1
        for dy in range(1, fin_h + 1):
            py = max(1, top_y - dy)
            col = c_accent if (dorsal_style == "crown" and dy == fin_h) else c_fin
            diff.set_at((x, py), (*col, 255))
            norm.set_at((x, py), N_UP)

        # Нижние плавники
        bot_y = int(round(cy_base + curve_y + arch))
        if x in (d_start + 1, d_start + 2) or (sabre and x >= d_start + 2) or x >= d_end - 2:
            for dy in (1, 2):
                py = min(h - 2, bot_y + dy)
                diff.set_at((x, py), (*c_fin, 255))
                norm.set_at((x, py), N_DOWN)

    # Хвостовой плавник
    for x in range(body_x1, tail_x1 + 1):
        ft = (x - body_x1 + 1) / float(max(1, tail_x1 - body_x1 + 1))
        spread = int(round(1.2 + ft * (4.2 if big else 3.2)))
        for y in range(int(cy_base) - spread, int(cy_base) + spread + 1):
            # Вырез вилки хвоста у большинства рыб (кроме сомов и налимов с круглым хвостом)
            if not catfish and not rotan and x == tail_x1 and abs(y - cy_base) <= 1.0:
                continue
            if 1 <= y < h - 1:
                col = c_accent if abs(y - cy_base) >= spread - 0.8 else c_fin
                diff.set_at((x, y), (*col, 255))
                norm.set_at((x, y), N_RIGHT)

    # Само тело рыбы
    for x in range(head_x0, body_x1 + 1):
        t = (x - head_x0) / float(max(1, body_x1 - head_x0))
        profile = math.sin((t ** 0.75) * math.pi)
        if rotan or catfish:
            profile = max(profile, 0.78 if t < 0.35 else profile)
        hh = max(1.2, profile * max_half_h)
        curve_y = -1.2 * math.sin(t * math.pi) if sabre else 0.0
        # Горб лобика у Толстолобика или крупных лососей
        top_bump = 1.2 if (pat == "forehead" and t < 0.4) else 0.0
        y0 = max(1, int(round(cy_base + curve_y - hh - top_bump)))
        y1 = min(h - 2, int(round(cy_base + curve_y + hh)))

        for y in range(y0, y1 + 1):
            rel_y = (y - (cy_base + curve_y)) / max(1.0, hh)
            if rel_y < -0.32:
                col, nc = c_back, N_UP
            elif rel_y > 0.38:
                col, nc = c_belly, N_DOWN
            else:
                col, nc = c_mid, N_FLAT
            if t < 0.18:
                nc = N_LEFT

            # Индивидуальные узоры чешуи и окраски
            if pat == "stripes" and ((x // (2 if big else 1)) % 2 == 0) and rel_y < 0.45:
                col = c_back if rel_y < 0.1 else c_accent
            elif pat == "spots" and ((x * 3 + y * 5) % 5 == 0) and abs(rel_y) < 0.55:
                col = c_accent
            elif pat == "lateral_band" and abs(rel_y) <= 0.22:
                col = c_accent
            elif pat == "scutes" and (y == y0 or (abs(rel_y) <= 0.18 and x % 2 == 0)):
                col = c_accent  # Костяные щитки стерляди / панцирника
            elif pat == "armor" and ((x % 3 == 0) or abs(rel_y) < 0.2):
                col = c_accent if abs(rel_y) < 0.2 else c_back
            elif pat == "wavy" and ((x + y) % 3 == 0) and rel_y < 0.25:
                col = c_accent
            elif pat == "moon" and ((x - y) % 4 == 0) and abs(rel_y) < 0.45:
                col = c_accent
            elif pat == "scarred" and abs((x - head_x0 - 6) - (y - y0)) <= 0 and abs(rel_y) < 0.5:
                col = c_accent

            diff.set_at((x, y), (*col, 255))
            norm.set_at((x, y), nc)

    # Жаберная крышка и грудной плавник
    gill_x = head_x0 + (4 if big else 3)
    for gy in range(int(cy_base) - 1, int(cy_base) + 2):
        if 1 <= gy < h - 1:
            diff.set_at((gill_x, gy), _clamp_rgb(c_back[0] - 18, c_back[1] - 18, c_back[2] - 18))
            norm.set_at((gill_x, gy), N_DEEP)
    diff.set_at((gill_x + 1, int(cy_base) + 1), (*c_fin, 255))
    diff.set_at((gill_x + 2, int(cy_base) + 2), (*c_fin, 255))

    # Глаз (у Крупноглазой салаки и Толстолобика — со смещением/размером)
    eye_x = head_x0 + (2 if big else 1)
    eye_y = int(cy_base) + (1 if pat == "forehead" else -1)
    diff.set_at((eye_x, eye_y), (*c_eye, 255))
    norm.set_at((eye_x, eye_y), N_UP)
    if spec.get("big_eye", False):
        for dx_e, dy_e in ((1, 0), (0, 1), (1, 1)):
            diff.set_at((eye_x + dx_e, eye_y + dy_e), (245, 245, 250, 255) if (dx_e, dy_e) != (0, 0) else (*c_eye, 255))

    # Особые приметы: зубы пираньи/зубатки/щуки, усы сома/налима/стерляди, пузыри пьянки, фонарик светлячка
    if spec.get("fangs", False):
        for fx in range(head_x0, head_x0 + (4 if big else 3)):
            if fx % 2 == 0:
                diff.set_at((fx, int(cy_base) + 1), (245, 245, 240, 255))
    if spec.get("whiskers", False):
        for wy_off, wx_len in ((1, 3), (2, 4), (3, 3)):
            for step in range(wx_len):
                wx = max(0, head_x0 - step + 1)
                wy = min(h - 1, int(cy_base) + wy_off + step // 2)
                diff.set_at((wx, wy), (*c_accent, 255))
                norm.set_at((wx, wy), N_DOWN)
    if spec.get("bubbles", False):
        for bx, by in ((head_x0, 4), (head_x0 + 2, 2), (head_x0 + 4, 5)):
            diff.set_at((bx, by), (*c_accent, 255))
            norm.set_at((bx, by), N_UP)
    if spec.get("lantern_tail", False):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                tx_l, ty_l = tail_x1 + dx, int(cy_base) + dy
                if 0 <= tx_l < w and 0 <= ty_l < h:
                    col_l = (255, 255, 215) if (dx == 0 and dy == 0) else (255, 215, 55)
                    diff.set_at((tx_l, ty_l), (*col_l, 255))
                    norm.set_at((tx_l, ty_l), N_UP)

    return enforce_crisp_rim_normals(diff, norm)


# Полный реестр всех 47 видов улова
FISH_CATALOG_SPECS = {
    "fish_closed_shell": ("Улов: Закрытая Ракушка", (16, 20), {
        "kind": "shell", "back": (118, 96, 82), "mid": (158, 134, 112), "belly": (195, 175, 152), "fin": (88, 72, 62), "accent": (235, 245, 255),
    }),
    "fish_striped_perch": ("Улов: Окунь Полосатый", (16, 20), {
        "back": (38, 78, 42), "mid": (92, 148, 68), "belly": (215, 222, 185), "fin": (235, 72, 42), "accent": (28, 52, 30),
        "pattern": "stripes", "dorsal": "spiky", "eye": (245, 185, 45),
    }),
    "fish_bitterling": ("Улов: Горчак Стайный", (16, 20), {
        "back": (68, 112, 128), "mid": (175, 198, 212), "belly": (235, 165, 185), "fin": (215, 95, 125), "accent": (75, 215, 195),
        "pattern": "lateral_band", "thickness": 4.2,
    }),
    "fish_young_catfish": ("Улов: Молодой Сом", (16, 20), {
        "kind": "catfish", "back": (52, 58, 48), "mid": (82, 92, 74), "belly": (168, 162, 132), "fin": (64, 70, 58), "accent": (122, 108, 82),
        "whiskers": True, "pattern": "spots",
    }),
    "fish_bigeye_sprat": ("Улов: Крупнаглазая Салака", (16, 20), {
        "back": (48, 92, 138), "mid": (182, 212, 232), "belly": (238, 244, 250), "fin": (142, 178, 205), "accent": (255, 255, 255),
        "big_eye": True, "thickness": 3.0,
    }),
    "fish_peled": ("Улов: Пелядь", (16, 20), {
        "back": (62, 88, 112), "mid": (192, 208, 222), "belly": (238, 242, 246), "fin": (118, 138, 156), "accent": (42, 58, 76),
        "pattern": "spots", "thickness": 4.0,
    }),
    "fish_scaly_goby": ("Улов: Редкочешуйчатый Бычок", (16, 20), {
        "kind": "rotan", "back": (92, 68, 46), "mid": (138, 106, 72), "belly": (188, 164, 128), "fin": (112, 84, 56), "accent": (225, 195, 125),
        "pattern": "scutes", "dorsal": "spiky",
    }),
    "fish_young_drunkard": ("Улов: Пьянка Молодая", (16, 20), {
        "back": (158, 72, 108), "mid": (222, 135, 168), "belly": (245, 212, 185), "fin": (245, 185, 65), "accent": (255, 238, 135),
        "bubbles": True, "eye": (245, 55, 95),
    }),
    "fish_redfin_roach": ("Улов: Краснопёрая Сорога", (16, 20), {
        "back": (58, 86, 68), "mid": (178, 194, 182), "belly": (232, 236, 228), "fin": (235, 42, 48), "accent": (255, 145, 45),
        "eye": (245, 95, 35), "thickness": 4.1,
    }),
    "fish_young_roach": ("Улов: Молодая Сорожка", (16, 20), {
        "back": (74, 98, 82), "mid": (188, 202, 192), "belly": (236, 240, 234), "fin": (215, 112, 78), "accent": (155, 175, 165),
        "thickness": 3.2,
    }),
    "fish_toothless_male": ("Улов: Беззубик Самец", (16, 20), {
        "back": (46, 118, 138), "mid": (92, 182, 168), "belly": (235, 185, 82), "fin": (238, 85, 65), "accent": (255, 225, 75),
        "dorsal": "sail", "pattern": "spots",
    }),
    "fish_neon_chub": ("Улов: Флуоресцентный Голавль", (16, 20), {
        "back": (28, 68, 98), "mid": (55, 195, 225), "belly": (165, 255, 235), "fin": (95, 255, 135), "accent": (215, 255, 120),
        "pattern": "lateral_band", "eye": (185, 255, 95),
    }),
    "fish_mud_armored": ("Улов: Иловый Панцирник", (16, 20), {
        "kind": "sturgeon", "back": (68, 56, 44), "mid": (104, 88, 68), "belly": (156, 138, 112), "fin": (82, 68, 52), "accent": (192, 172, 135),
        "pattern": "armor", "dorsal": "spiky",
    }),
    "fish_slippery_mackerel": ("Улов: Скользкая Скумбрия", (16, 20), {
        "back": (28, 92, 118), "mid": (98, 188, 195), "belly": (228, 242, 245), "fin": (72, 148, 168), "accent": (22, 54, 78),
        "pattern": "wavy", "thickness": 3.4,
    }),
    "fish_brown_rotan": ("Улов: Бурый Ротан", (16, 20), {
        "kind": "rotan", "back": (72, 46, 32), "mid": (118, 78, 52), "belly": (168, 128, 92), "fin": (94, 62, 42), "accent": (46, 28, 18),
        "pattern": "spots", "dorsal": "spiky",
    }),
    "fish_kelp_mackerel": ("Улов: Водорослевая Макрель", (16, 20), {
        "back": (38, 96, 44), "mid": (98, 168, 68), "belly": (198, 225, 138), "fin": (148, 188, 52), "accent": (26, 64, 30),
        "pattern": "wavy", "dorsal": "sail",
    }),
    "fish_coal_wolffish": ("Улов: Угольная Зубатка", (16, 20), {
        "kind": "piranha", "back": (28, 28, 36), "mid": (52, 54, 66), "belly": (88, 92, 106), "fin": (42, 44, 54), "accent": (128, 135, 155),
        "fangs": True, "pattern": "stripes", "eye": (245, 215, 65),
    }),
    "fish_green_rotan": ("Улов: Зелёный Ротан", (16, 20), {
        "kind": "rotan", "back": (34, 78, 38), "mid": (68, 132, 58), "belly": (148, 188, 112), "fin": (52, 104, 46), "accent": (215, 185, 65),
        "pattern": "spots", "dorsal": "spiky",
    }),
    "fish_scad": ("Улов: Ставрида", (16, 20), {
        "back": (58, 102, 138), "mid": (178, 202, 218), "belly": (235, 240, 245), "fin": (235, 195, 55), "accent": (245, 215, 85),
        "pattern": "lateral_band", "thickness": 3.6,
    }),
    "fish_stone_sterlet": ("Улов: Стерлять Каменная", (16, 20), {
        "kind": "sturgeon", "back": (78, 76, 84), "mid": (122, 118, 128), "belly": (195, 192, 185), "fin": (98, 94, 104), "accent": (235, 232, 225),
        "pattern": "scutes", "whiskers": True,
    }),
    "fish_toothless_female": ("Улов: Беззубик Самка", (16, 20), {
        "back": (98, 112, 64), "mid": (168, 178, 112), "belly": (238, 228, 178), "fin": (185, 128, 195), "accent": (225, 165, 235),
        "thickness": 4.4,
    }),
    "fish_swamp_sterlet": ("Улов: Стерлять Болотная", (16, 20), {
        "kind": "sturgeon", "back": (42, 74, 40), "mid": (78, 118, 62), "belly": (168, 185, 128), "fin": (58, 92, 48), "accent": (198, 225, 115),
        "pattern": "scutes", "whiskers": True,
    }),
    "fish_fermented_drunkard": ("Улов: Пьянка Забродившая", (16, 20), {
        "back": (112, 28, 68), "mid": (178, 52, 98), "belly": (228, 148, 112), "fin": (195, 225, 75), "accent": (245, 248, 195),
        "bubbles": True, "thickness": 4.8, "eye": (255, 235, 75),
    }),
    "fish_moon_herring": ("Улов: Лунная Сельдь", (16, 20), {
        "back": (52, 82, 148), "mid": (165, 205, 248), "belly": (235, 248, 255), "fin": (125, 185, 245), "accent": (255, 250, 195),
        "pattern": "moon", "dorsal": "sail", "eye": (255, 245, 165),
    }),
    "fish_big_catfish": ("Улов: Крупный Усатый Сом (2x1)", (32, 20), {
        "big": True, "kind": "catfish", "back": (44, 52, 42), "mid": (76, 88, 68), "belly": (178, 168, 132), "fin": (58, 66, 52), "accent": (138, 122, 88),
        "whiskers": True, "pattern": "spots", "thickness": 5.2,
    }),
    "fish_rainbow_trout": ("Улов: Радужная Кумжа", (16, 20), {
        "back": (48, 92, 78), "mid": (168, 192, 178), "belly": (232, 236, 228), "fin": (215, 125, 135), "accent": (242, 88, 138),
        "pattern": "lateral_band",
    }),
    "fish_silver_coho": ("Улов: Серебристый Кижуч", (16, 20), {
        "back": (42, 78, 118), "mid": (192, 212, 228), "belly": (242, 246, 250), "fin": (138, 165, 188), "accent": (235, 245, 255),
        "pattern": "spots",
    }),
    "fish_flame_piranha": ("Улов: Пламенная Пиранья", (16, 20), {
        "kind": "piranha", "back": (92, 28, 24), "mid": (215, 68, 32), "belly": (255, 185, 45), "fin": (245, 42, 32), "accent": (255, 240, 115),
        "fangs": True, "dorsal": "spiky", "eye": (255, 235, 85),
    }),
    "fish_young_paddlefish": ("Улов: Молодой Веслонос", (16, 20), {
        "kind": "paddlefish", "back": (58, 82, 108), "mid": (118, 148, 175), "belly": (205, 218, 228), "fin": (88, 115, 142), "accent": (165, 192, 215),
    }),
    "fish_silver_carp": ("Улов: Толстолобик", (16, 20), {
        "back": (68, 88, 76), "mid": (178, 194, 186), "belly": (232, 238, 234), "fin": (132, 148, 138), "accent": (215, 225, 218),
        "pattern": "forehead", "thickness": 4.5,
    }),
    "fish_wriggling_pike": ("Улов: Извивающаяся Щука", (16, 20), {
        "kind": "serpent", "back": (38, 76, 36), "mid": (78, 128, 56), "belly": (212, 218, 168), "fin": (168, 92, 48), "accent": (232, 218, 112),
        "pattern": "spots",
    }),
    "fish_tiger_crayfish": ("Улов: Тигровый Рак", (16, 20), {
        "kind": "crayfish", "back": (42, 28, 24), "mid": (218, 92, 38), "belly": (245, 168, 82), "fin": (168, 62, 28), "accent": (248, 128, 45),
    }),
    "fish_searing_eel": ("Улов: Обжигающий Угорь", (16, 20), {
        "kind": "serpent", "back": (118, 32, 24), "mid": (235, 95, 32), "belly": (255, 215, 75), "fin": (255, 145, 35), "accent": (255, 248, 165),
        "pattern": "lava", "eye": (255, 250, 180),
    }),
    "fish_yellow_burbot": ("Улов: Налим Желтокожий", (16, 20), {
        "kind": "catfish", "back": (118, 92, 32), "mid": (188, 152, 54), "belly": (235, 212, 128), "fin": (148, 115, 42), "accent": (88, 64, 24),
        "pattern": "spots", "whiskers": True,
    }),
    "fish_aradon_paddlefish": ("Улов: Арадонский Веслонос (2x1)", (32, 20), {
        "big": True, "kind": "paddlefish", "back": (36, 68, 128), "mid": (78, 138, 205), "belly": (225, 235, 248), "fin": (228, 178, 62), "accent": (248, 212, 95),
        "pattern": "lateral_band", "dorsal": "sail",
    }),
    "fish_sabrefish": ("Улов: Рыба-Сабля", (16, 20), {
        "kind": "sabre", "back": (72, 108, 138), "mid": (198, 218, 235), "belly": (242, 248, 255), "fin": (215, 175, 78), "accent": (255, 255, 255),
    }),
    "fish_big_burbot": ("Улов: Крупный Налим (2x1)", (32, 20), {
        "big": True, "kind": "catfish", "back": (64, 52, 32), "mid": (118, 96, 54), "belly": (188, 168, 115), "fin": (92, 74, 42), "accent": (52, 40, 24),
        "pattern": "spots", "whiskers": True, "thickness": 4.8,
    }),
    "fish_snow_char": ("Улов: Снежная Мальма", (16, 20), {
        "back": (58, 118, 168), "mid": (165, 218, 245), "belly": (238, 248, 255), "fin": (225, 68, 82), "accent": (255, 255, 255),
        "pattern": "spots", "dorsal": "crown",
    }),
    "fish_alpha_roach": ("Улов: Вожак-Сорога (2x1)", (32, 20), {
        "big": True, "back": (48, 72, 58), "mid": (168, 186, 175), "belly": (228, 232, 222), "fin": (235, 35, 42), "accent": (255, 195, 55),
        "dorsal": "crown", "pattern": "scarred", "eye": (255, 65, 35), "thickness": 5.4,
    }),
    "fish_big_coho": ("Улов: Крупный Серебристый Кижуч (2x1)", (32, 20), {
        "big": True, "back": (38, 72, 108), "mid": (188, 208, 225), "belly": (218, 88, 98), "fin": (148, 62, 74), "accent": (242, 248, 255),
        "pattern": "spots", "fangs": True, "thickness": 5.0,
    }),
    "fish_angel_snapper": ("Улов: Ангельский Луциан", (16, 20), {
        "back": (215, 178, 88), "mid": (242, 236, 225), "belly": (255, 252, 245), "fin": (115, 225, 248), "accent": (255, 225, 115),
        "dorsal": "sail", "pattern": "moon", "eye": (75, 215, 245), "thickness": 4.4,
    }),
    "fish_big_sabrefish": ("Улов: Крупная Рыба-Сабля (2x1)", (32, 20), {
        "big": True, "kind": "sabre", "back": (58, 96, 132), "mid": (205, 225, 242), "belly": (245, 250, 255), "fin": (235, 185, 68), "accent": (255, 255, 255),
        "thickness": 3.8,
    }),
    "fish_big_swamp_pike": ("Улов: Крупная Болотная Щука (2x1)", (32, 20), {
        "big": True, "back": (32, 68, 34), "mid": (68, 118, 48), "belly": (188, 198, 138), "fin": (138, 82, 42), "accent": (212, 202, 96),
        "pattern": "spots", "fangs": True, "thickness": 4.4,
    }),
    "fish_river_firefly": ("Улов: Речной Светлячок", (16, 20), {
        "back": (28, 36, 62), "mid": (52, 74, 118), "belly": (95, 145, 185), "fin": (115, 225, 195), "accent": (255, 240, 95),
        "lantern_tail": True, "big_eye": True, "eye": (255, 235, 85), "thickness": 3.2,
    }),
    "fish_deep_water_snake": ("Улов: Глубоководный Уж", (16, 20), {
        "kind": "serpent", "back": (24, 34, 42), "mid": (44, 62, 74), "belly": (118, 138, 148), "fin": (62, 88, 98), "accent": (248, 205, 55),
        "pattern": "collar", "eye": (245, 85, 65),
    }),
    "fish_giant_fierce_catfish": ("Улов: Гигантский Свирепый Сом (2x1)", (32, 20), {
        "big": True, "kind": "catfish", "back": (28, 26, 36), "mid": (58, 52, 68), "belly": (138, 118, 108), "fin": (168, 48, 52), "accent": (235, 75, 65),
        "whiskers": True, "fangs": True, "dorsal": "spiky", "pattern": "scarred", "eye": (255, 65, 55), "thickness": 5.8,
    }),
    "fish_albino_paddlefish": ("Улов: Альбинос Веслонос (2x1)", (32, 20), {
        "big": True, "kind": "paddlefish", "back": (218, 212, 225), "mid": (242, 238, 246), "belly": (255, 252, 255), "fin": (238, 188, 198), "accent": (248, 215, 112),
        "eye": (235, 45, 68), "dorsal": "sail", "thickness": 4.8,
    }),
}


def register_fishing_assets(assets):
    # =========================================================================
    # 1. ОЗЁРНАЯ ВОДА И БЕРЕГОВЫЕ ПОВЕРХНОСТИ (16x16, opaque=True)
    # =========================================================================
    tau = 2.0 * math.pi / 16.0

    # 1.1 Мелководье озера с прозрачным песчаным дном (3 кадра анимации)
    shallow_frames = []
    for fi in range(3):
        ph = fi * (2.0 * math.pi / 3.0)
        sd, sn = make_pair(16, 16, opaque=True)
        for y in range(16):
            for x in range(16):
                w1 = math.sin(x * tau + y * tau + ph)
                w2 = math.cos(x * tau - y * tau * 2.0 - ph)
                wv = (w1 + w2) * 0.5
                cr = int(58 + (wv + 1.0) * 18)
                cg = int(128 + (wv + 1.0) * 24)
                cb = int(142 + (wv + 1.0) * 26)
                if wv > 0.60:
                    cr, cg, cb = 185, 235, 240
                nc = N_UP if w1 > 0.35 else (N_DOWN if w1 < -0.35 else N_FLAT)
                sd.set_at((x, y), (cr, cg, cb, 255))
                sn.set_at((x, y), nc)
        shallow_frames.append((sd, sn))
    assets["floor_lake_shallow"] = shallow_frames[0]
    assets["_lake_shallow_frames"] = shallow_frames

    # 1.2 Глубокая озёрная вода (3 кадра анимации)
    deep_frames = []
    for fi in range(3):
        ph = fi * (2.0 * math.pi / 3.0)
        dd, dn = make_pair(16, 16, opaque=True)
        for y in range(16):
            for x in range(16):
                w1 = math.sin(x * tau + y * tau + ph)
                w2 = math.cos(x * tau - y * tau * 2.0 - ph)
                wv = (w1 + w2) * 0.5
                cr = int(16 + (wv + 1.0) * 10)
                cg = int(54 + (wv + 1.0) * 20)
                cb = int(98 + (wv + 1.0) * 26)
                if wv > 0.62:
                    cr, cg, cb = 92, 168, 215
                nc = N_UP if w1 > 0.35 else (N_DOWN if w1 < -0.35 else N_FLAT)
                dd.set_at((x, y), (cr, cg, cb, 255))
                dn.set_at((x, y), nc)
        deep_frames.append((dd, dn))
    assets["floor_lake_deep"] = deep_frames[0]
    assets["_lake_deep_frames"] = deep_frames

    # 1.3 Мокрый береговой песок (floor_wet_sand)
    ws_d, ws_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            h = ((x * 53 + y * 97 + x * y * 13) % 19)
            sh = (h % 5) - 2
            col = (142 + sh, 116 + sh, 78 + sh, 255)
            nc = N_DEEP if h == 0 else N_FLAT
            ws_d.set_at((x, y), col)
            ws_n.set_at((x, y), nc)
    assets["floor_wet_sand"] = (ws_d, ws_n)

    # 1.4 Галечный озёрный плёс (floor_pebble_shore)
    ps_d, ps_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            cell = ((x // 3) * 7 + (y // 3) * 13) % 5
            edge = (x % 3 == 0 or y % 3 == 0)
            if edge:
                col, nc = (68, 64, 58, 255), N_DEEP
            else:
                p_cols = [(128, 124, 118), (108, 114, 122), (142, 128, 112), (96, 98, 104), (156, 148, 136)]
                col, nc = (*p_cols[cell], 255), N_FLAT
            ps_d.set_at((x, y), col)
            ps_n.set_at((x, y), nc)
    assets["floor_pebble_shore"] = (ps_d, ps_n)

    # 1.5 Илистый берег с корневищами камыша (floor_reed_mud)
    rm_d, rm_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            h = ((x * 67 + y * 113 + (x ^ y) * 19) % 23)
            if h in (0, 1):
                col, nc = (68, 96, 48, 255), N_FLAT
            elif h in (2, 3, 4):
                col, nc = (36, 30, 24, 255), N_DEEP
            else:
                sh = (h % 4) * 2
                col, nc = (52 + sh, 44 + sh, 34 + sh, 255), N_FLAT
            rm_d.set_at((x, y), col)
            rm_n.set_at((x, y), nc)
    assets["floor_reed_mud"] = (rm_d, rm_n)

    # 1.6 Мокрый деревянный настил рыбацкого пирса (floor_wooden_pier)
    wp_d, wp_n = make_pair(16, 16, opaque=True)
    for y in range(16):
        for x in range(16):
            if x % 4 == 0 or y in (0, 15):
                wp_d.set_at((x, y), (32, 52, 68, 255))  # Щели над водой
                wp_n.set_at((x, y), N_DEEP)
            else:
                g = ((x * 19 + y * 31) % 7) - 3
                is_nail = y in (2, 13) and x % 4 == 2
                col = (165, 172, 182, 255) if is_nail else (92 + g, 66 + g, 44 + g, 255)
                wp_d.set_at((x, y), col)
                wp_n.set_at((x, y), N_FLAT)
    assets["floor_wooden_pier"] = (wp_d, wp_n)

    # =========================================================================
    # 2. БЕРЕГОВЫЕ И ОЗЁРНЫЕ ОВЕРЛЕИ (16x16, opaque=False)
    # =========================================================================

    # 2.1 Пена озёрного прибоя (ov_shore_foam)
    osf_d, osf_n = make_pair(16, 16, opaque=False)
    for x in range(1, 15):
        fy = int(round(7.5 + math.sin(x * 0.55) * 2.5))
        osf_d.set_at((x, fy), (225, 248, 255, 225))
        osf_n.set_at((x, fy), N_FLAT)
        osf_d.set_at((x, fy + 1), (145, 208, 232, 180))
        osf_n.set_at((x, fy + 1), N_FLAT)
    assets["ov_shore_foam"] = (osf_d, osf_n)

    # 2.2 Речные ракушки и цветные камушки на песке (ov_shells_starfish)
    oss_d, oss_n = make_pair(16, 16, opaque=False)
    for sx, sy, col in ((4, 5, (238, 218, 195, 235)), (11, 4, (225, 145, 128, 235)), (7, 11, (195, 215, 228, 235)), (12, 12, (235, 195, 115, 235))):
        for dx, dy in ((0, 0), (1, 0), (0, 1)):
            oss_d.set_at((sx + dx, sy + dy), col)
            oss_n.set_at((sx + dx, sy + dy), N_FLAT)
    assets["ov_shells_starfish"] = (oss_d, oss_n)

    # 2.3 Пятна озёрной ряски и кувшинок (ov_duckweed)
    odw_d, odw_n = make_pair(16, 16, opaque=False)
    for y in range(2, 14):
        for x in range(2, 14):
            if ((x * 29 + y * 53) % 7) in (0, 1) and math.hypot(x - 7.5, y - 7.5) <= 5.5:
                odw_d.set_at((x, y), (78, 156, 54, 215))
                odw_n.set_at((x, y), N_FLAT)
    assets["ov_duckweed"] = (odw_d, odw_n)

    # 2.4 Тёмные силуэты косяка рыб под водой (ov_fish_shadows)
    ofs_d, ofs_n = make_pair(16, 16, opaque=False)
    for fx, fy in ((4, 5), (9, 8), (5, 12)):
        for dx in range(4):
            ofs_d.set_at((fx + dx, fy), (14, 38, 62, 175))
            ofs_n.set_at((fx + dx, fy), N_FLAT)
        ofs_d.set_at((fx + 1, fy - 1), (14, 38, 62, 175))
        ofs_d.set_at((fx + 1, fy + 1), (14, 38, 62, 175))
    assets["ov_fish_shadows"] = (ofs_d, ofs_n)

    # 2.5 Рыбацкий поплавок с кругами на воде (ov_bobber_ripples)
    obr_d, obr_n = make_pair(16, 16, opaque=False)
    for y in range(2, 14):
        for x in range(2, 14):
            d = math.hypot((x - 7.5) * 0.85, (y - 8.5) * 1.15)
            if 3.6 <= d <= 4.4:
                obr_d.set_at((x, y), (175, 232, 248, 195))
                obr_n.set_at((x, y), N_FLAT)
    for y in range(5, 10):
        col = (238, 52, 52, 255) if y <= 7 else (245, 245, 250, 255)
        obr_d.set_at((7, y), col)
        obr_d.set_at((8, y), col)
        obr_n.set_at((7, y), N_FLAT)
        obr_n.set_at((8, y), N_FLAT)
    assets["ov_bobber_ripples"] = (obr_d, obr_n)

    # =========================================================================
    # 3. РЫБАЦКИЕ ПРОПСЫ НА БЕРЕГУ И ПИРСЕ (16x20 и 32x20)
    # =========================================================================

    # 3.1 Высокий озёрный камыш с коричневыми початками рогоза (prop_reeds_tall)
    rt_d, rt_n = make_pair(16, 20)
    for sx in (3, 5, 8, 10, 12):
        for y in range(3, 19):
            sway = int(math.sin((18 - y) * 0.25 + sx) * 0.8)
            px = max(1, min(14, sx + sway))
            is_head = (5 <= y <= 8 and sx in (5, 10))
            col = (108, 62, 34) if is_head else ((72, 142, 52) if sx % 2 == 0 else (52, 108, 38))
            rt_d.set_at((px, y), col)
            rt_n.set_at((px, y), N_UP if is_head else N_FLAT)
    assets["prop_reeds_tall"] = enforce_crisp_rim_normals(rt_d, rt_n)

    # 3.2 Заброшенная удочка на деревянной рогатине (prop_fishing_rod_stand)
    fr_d, fr_n = make_pair(16, 20)
    for y in range(11, 19):
        fr_d.set_at((6, y), (112, 74, 38))
        fr_n.set_at((6, y), N_UP)
    for step in range(13):
        rx = 2 + step
        ry = 15 - step
        fr_d.set_at((rx, ry), (158, 112, 54))
        fr_n.set_at((rx, ry), N_UP)
    for ly in range(4, 15):
        fr_d.set_at((14, ly), (195, 215, 230))
    fr_d.set_at((14, 15), (238, 58, 58))
    assets["prop_fishing_rod_stand"] = enforce_crisp_rim_normals(fr_d, fr_n)

    # 3.3 Рыбацкий ящик со снастями и блёснами (prop_tackle_box)
    tb_d, tb_n = make_pair(16, 20)
    for y in range(9, 19):
        for x in range(2, 14):
            if y in (9, 13, 18) or x in (2, 13):
                col = (188, 152, 68)
            elif y < 13:
                col = (225, 62, 58) if x in (5, 6) else ((72, 195, 235) if x in (9, 10) else (48, 62, 78))
            else:
                col = (72, 98, 86)
            tb_d.set_at((x, y), col)
            tb_n.set_at((x, y), N_FLAT)
    assets["prop_tackle_box"] = enforce_crisp_rim_normals(tb_d, tb_n)

    # 3.4 Плетёная ивовая верша / сеть-ловушка для рыбы (prop_fish_trap_net)
    fn_d, fn_n = make_pair(16, 20)
    for y in range(8, 18):
        hw = 3 if y in (8, 17) else 6
        for x in range(8 - hw, 8 + hw):
            mesh = (x + y) % 2 == 0
            col = (158, 122, 68) if mesh else (112, 84, 44)
            fn_d.set_at((x, y), col)
            fn_n.set_at((x, y), N_UP if y <= 11 else N_FLAT)
    assets["prop_fish_trap_net"] = enforce_crisp_rim_normals(fn_d, fn_n)

    # 3.5 Деревянное ведро с наживкой и уловом (prop_bait_bucket)
    bb_d, bb_n = make_pair(16, 20)
    for y in range(8, 19):
        hw = 5 if y <= 12 else 4
        for x in range(8 - hw, 8 + hw):
            if y in (8, 9):
                col = (68, 152, 195) if 5 <= x <= 10 else (122, 82, 44)
            elif y in (11, 16):
                col = (88, 96, 108)
            else:
                col = (132, 88, 48) if x < 8 else (98, 64, 34)
            bb_d.set_at((x, y), col)
            bb_n.set_at((x, y), N_UP if y <= 10 else (N_LEFT if x < 7 else N_RIGHT))
    # Серебристый рыбий хвост, торчащий из ведра
    for tx, ty in ((9, 6), (10, 5), (10, 7), (9, 7)):
        bb_d.set_at((tx, ty), (185, 208, 225))
        bb_n.set_at((tx, ty), N_UP)
    assets["prop_bait_bucket"] = enforce_crisp_rim_normals(bb_d, bb_n)

    # 3.6 Рыбацкие вешала с гирляндой вяленой рыбы (prop_fish_drying_line)
    fdl_d, fdl_n = make_pair(16, 20)
    for y in range(3, 19):
        for x in (2, 13):
            fdl_d.set_at((x, y), (118, 78, 42))
            fdl_n.set_at((x, y), N_UP)
    for x in range(2, 14):
        fdl_d.set_at((x, 5), (195, 178, 138))
        fdl_n.set_at((x, 5), N_UP)
    for fx in (5, 8, 11):
        for y in range(6, 14):
            col = (225, 72, 58) if y == 13 else (182, 198, 212)
            fdl_d.set_at((fx, y), col)
            fdl_n.set_at((fx, y), N_UP)
    assets["prop_fish_drying_line"] = enforce_crisp_rim_normals(fdl_d, fdl_n)

    # 3.7 Складной табурет рыбака на берегу (prop_fisherman_stool)
    fs_d, fs_n = make_pair(16, 20)
    for y in range(10, 19):
        for x in range(4, 12):
            if y in (10, 11):
                fs_d.set_at((x, y), (68, 128, 92) if (x + y) % 2 == 0 else (52, 98, 72))
                fs_n.set_at((x, y), N_FLAT)
            elif abs((x - 4) - (y - 11)) <= 1 or abs((11 - x) - (y - 11)) <= 1:
                fs_d.set_at((x, y), (128, 86, 46))
                fs_n.set_at((x, y), N_FLAT)
    assets["prop_fisherman_stool"] = enforce_crisp_rim_normals(fs_d, fs_n)

    # 3.8 Деревянная рыбацкая лодка с вёслами (prop_wooden_rowboat, 32x20 — 2x1 тайла!)
    rb_d, rb_n = make_pair(32, 20)
    for y in range(6, 18):
        for x in range(2, 30):
            dx = (x - 15.5) / 13.5
            dy = (y - 12.0) / 5.5
            if dx * dx + dy * dy <= 1.0:
                is_rim = (dx * dx + dy * dy >= 0.72)
                is_bench = (x in (9, 10, 15, 16, 21, 22) and not is_rim)
                if is_rim:
                    col, nc = (148, 98, 52), N_UP
                elif is_bench:
                    col, nc = (132, 86, 44), N_FLAT
                else:
                    col, nc = (86, 54, 28) if y % 2 == 0 else (72, 44, 22), N_FLAT
                rb_d.set_at((x, y), col)
                rb_n.set_at((x, y), nc)
    assets["prop_wooden_rowboat"] = enforce_crisp_rim_normals(rb_d, rb_n)

    # =========================================================================
    # 4. ГЕНЕРАЦИЯ ВСЕХ 47 УНИКАЛЬНЫХ ВИДОВ РЫБ И УЛОВА
    # =========================================================================
    for role_id, (_ru_name, _sz, spec_dict) in FISH_CATALOG_SPECS.items():
        assets[role_id] = _build_fish_sprite(spec_dict)