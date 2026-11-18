"""Procedural diffuse + normal asset generator for Jungle, Tribal, Vedalken, Cave & Bone Jungle mobs."""

import math
from elenor.rendering.assets import make_pair, enforce_crisp_rim_normals

N_FLAT = (128, 128, 255, 255)
N_UP = (128, 218, 200, 255)
N_DOWN = (128, 38, 200, 255)
N_LEFT = (45, 128, 200, 255)
N_RIGHT = (210, 128, 200, 255)
N_DEEP = (128, 128, 155, 255)

# Цвета со свечением в темноте (пробивают порог _get_entity_emissive_surf в renderer.py)
GLOW_RED = (255, 52, 58)
GLOW_GOLD = (255, 225, 65)
GLOW_GREEN = (85, 250, 135)
GLOW_CYAN = (110, 250, 255)


def register_jungle_bestiary_assets(assets):
    # =========================================================================
    # 1. АБОРИГЕНЫ: БЛИЖНИЙ БОЙ, ДАЛЬНИЙ БОЙ, ШАМАН (16x20)
    # =========================================================================

    # 1.1 Абориген-воин (tribal_warrior): загорелая кожа, боевой раскрас, макуауитль и щит
    tw_d, tw_n = make_pair(16, 20)
    for y in range(2, 19):
        for x in range(4, 12):
            if 2 <= y <= 3 and x in (6, 7, 8, 9):
                col = (215, 58, 48) if x % 2 == 0 else (48, 178, 142)  # Перья на голове
                tw_d.set_at((x, y), col)
                tw_n.set_at((x, y), N_UP)
            elif 4 <= y <= 8 and 5 <= x <= 10:
                if y == 6 and x in (6, 9):
                    col = GLOW_GOLD
                elif y == 7 and x in (5, 6, 9, 10):
                    col = (218, 210, 195)  # Белый боевой раскрас на скулах
                else:
                    col = (148, 92, 56) if x < 8 else (118, 72, 42)
                tw_d.set_at((x, y), col)
                tw_n.set_at((x, y), N_LEFT if x < 7 else (N_RIGHT if x > 8 else N_UP))
            elif 9 <= y <= 15 and 5 <= x <= 10:
                is_strap = (abs(x - (y - 4)) <= 0) or (y in (13, 14))
                col = (72, 138, 52) if y in (13, 14) else ((218, 208, 185) if is_strap else (142, 88, 52))
                tw_d.set_at((x, y), col)
                tw_n.set_at((x, y), N_LEFT if x < 7 else (N_RIGHT if x > 8 else N_FLAT))
            elif y >= 16 and x in (5, 6, 9, 10):
                tw_d.set_at((x, y), (118, 72, 42))
                tw_n.set_at((x, y), N_FLAT)
    # Обсидиановый меч-макуауитль в левой руке (x=1..3) и расписной щит справа (x=11..14)
    for y in range(4, 15):
        tw_d.set_at((2, y), (128, 82, 42))
        tw_n.set_at((2, y), N_UP)
        if y % 2 == 1 and y <= 12:
            tw_d.set_at((1, y), (32, 28, 44))  # Острые зубья обсидиана
            tw_d.set_at((3, y), (32, 28, 44))
    for y in range(8, 16):
        for x in range(11, 15):
            if math.hypot(x - 12.5, (y - 11.5) * 0.8) <= 2.2:
                col = (215, 62, 48) if (x + y) % 2 == 0 else (225, 178, 65)
                tw_d.set_at((x, y), col)
                tw_n.set_at((x, y), N_RIGHT)
    assets["tribal_warrior"] = enforce_crisp_rim_normals(tw_d, tw_n)

    # 1.2 Абориген-охотник с духовой трубкой (tribal_hunter): тёмная кожа, лиственный плащ
    th_d, th_n = make_pair(16, 20)
    for y in range(3, 19):
        for x in range(4, 12):
            if 3 <= y <= 5 and 5 <= x <= 10:
                th_d.set_at((x, y), (56, 128, 48) if (x + y) % 2 == 0 else (38, 88, 34))
                th_n.set_at((x, y), N_UP)
            elif 6 <= y <= 8 and 5 <= x <= 10:
                col = GLOW_GREEN if (y == 6 and x in (6, 9)) else (88, 52, 34)
                th_d.set_at((x, y), col)
                th_n.set_at((x, y), N_UP)
            elif 9 <= y <= 15 and 5 <= x <= 10:
                is_leaf = (x in (5, 10) or y == 14)
                col = (48, 112, 42) if is_leaf else (82, 48, 30)
                th_d.set_at((x, y), col)
                th_n.set_at((x, y), N_LEFT if x < 7 else (N_RIGHT if x > 8 else N_FLAT))
            elif y >= 16 and x in (6, 9):
                th_d.set_at((x, y), (74, 42, 26))
                th_n.set_at((x, y), N_FLAT)
    # Длинная бамбуковая духовая трубка у губ (x=1..7, y=7..8) с ядовитым дротиком на конце
    for x in range(1, 7):
        th_d.set_at((x, 7), (158, 122, 62) if x % 2 == 0 else (118, 88, 44))
        th_n.set_at((x, 7), N_UP)
    th_d.set_at((0, 7), GLOW_GREEN)
    assets["tribal_hunter"] = enforce_crisp_rim_normals(th_d, th_n)

    # 1.3 Абориген-шаман (tribal_shaman): тёмная кожа, рогатая маска черепа, посох с изумрудным пламенем
    ts_d, ts_n = make_pair(16, 20)
    for y in range(1, 19):
        for x in range(3, 13):
            # Перьевая корона и рога черепной маски (y=1..4)
            if 1 <= y <= 3 and x in (4, 6, 7, 8, 9, 11):
                ts_d.set_at((x, y), (225, 58, 52) if x % 2 == 0 else (58, 195, 165))
                ts_n.set_at((x, y), N_UP)
            elif 4 <= y <= 8 and 5 <= x <= 10:
                col = GLOW_GREEN if (y == 6 and x in (6, 9)) else (225, 215, 192)
                ts_d.set_at((x, y), col)
                ts_n.set_at((x, y), N_UP)
            elif 9 <= y <= 16 and 4 <= x <= 11:
                is_bones = (y in (10, 12) and 6 <= x <= 9)
                col = (218, 208, 185) if is_bones else ((78, 46, 30) if x in (6, 7, 8, 9) else (138, 34, 42))
                ts_d.set_at((x, y), col)
                ts_n.set_at((x, y), N_LEFT if x < 7 else (N_RIGHT if x > 8 else N_FLAT))
            elif y >= 17 and x in (6, 9):
                ts_d.set_at((x, y), (68, 38, 24))
                ts_n.set_at((x, y), N_FLAT)
    # Шаманский посох слева со светящимся черепом-фетишем
    for y in range(4, 18):
        ts_d.set_at((2, y), (112, 72, 38))
        ts_n.set_at((2, y), N_LEFT)
    for dx, dy in ((0, 0), (-1, 1), (1, 1), (0, 1)):
        ts_d.set_at((2 + dx, 3 + dy), GLOW_GREEN)
        ts_n.set_at((2 + dx, 3 + dy), N_UP)
    assets["tribal_shaman"] = enforce_crisp_rim_normals(ts_d, ts_n)

    # =========================================================================
    # 2. РЕПТИЛИИ-ПОЛУКРОКОДИЛЫ: ВОИН (16x20) И ДЖАГГЕРНАУТ (32x36)
    # =========================================================================

    # 2.1 Полукрокодил-воин (croc_warrior, 16x20): чешуйчатая броня, вытянутая зубастая пасть, тяжёлый тесак
    cw_d, cw_n = make_pair(16, 20)
    for y in range(2, 19):
        for x in range(2, 15):
            # Вытянутая вперёд крокодилья челюсть (x=2..9, y=3..7)
            if 3 <= y <= 7 and 2 <= x <= 10:
                if y == 4 and x == 7:
                    col = GLOW_GOLD
                elif y == 6 and x in (3, 5, 7):
                    col = (228, 224, 210)  # Клыки
                else:
                    col = (52, 118, 56) if y < 6 else (158, 168, 112)
                cw_d.set_at((x, y), col)
                cw_n.set_at((x, y), N_UP if y <= 5 else N_DOWN)
            # Могучий торс с золотыми наплечниками и шипастым хвостом сзади (y=8..16)
            elif 8 <= y <= 16 and 4 <= x <= 14:
                if x >= 12 and y < 13:
                    continue
                is_belly = (5 <= x <= 8 and y <= 15)
                is_armor = (y in (8, 9) and 5 <= x <= 10)
                if is_armor:
                    col = (218, 175, 65)
                elif is_belly:
                    col = (172, 178, 118) if y % 2 == 0 else (142, 148, 96)
                else:
                    col = (44, 98, 48) if (x + y) % 2 == 0 else (32, 74, 36)
                cw_d.set_at((x, y), col)
                cw_n.set_at((x, y), N_LEFT if x < 7 else (N_RIGHT if x > 9 else N_FLAT))
            elif y >= 17 and x in (5, 6, 9, 10):
                cw_d.set_at((x, y), (38, 82, 42))
                cw_n.set_at((x, y), N_FLAT)
    # Тяжёлый бронзовый тесак в лапе
    for y in range(6, 15):
        cw_d.set_at((1, y), (205, 168, 72) if y < 12 else (112, 72, 38))
        cw_n.set_at((1, y), N_LEFT)
        if y <= 11:
            cw_d.set_at((2, y), (225, 195, 95))
    assets["croc_warrior"] = enforce_crisp_rim_normals(cw_d, cw_n)

    # 2.2 Гигантский Полукрокодил-Джаггернаут (croc_juggernaut, 32x36 — 2x2 тайла!)
    cj_d, cj_n = make_pair(32, 36)
    for y in range(4, 35):
        for x in range(3, 30):
            # Массивная крокодилья голова с гребнем и золотым венцом (y=5..13, x=5..20)
            if 5 <= y <= 13 and 5 <= x <= 21:
                if y == 9 and x in (11, 14):
                    col = GLOW_GOLD  # Хищные жёлтые глаза (y=9 >= 9 -> светится в темноте!)
                elif y == 11 and x in (6, 8, 10, 12):
                    col = (228, 224, 210)
                elif y in (5, 6) and x % 2 == 0:
                    col = (218, 175, 62)
                else:
                    col = (48, 112, 52) if y < 11 else (156, 166, 110)
                cj_d.set_at((x, y), col)
                cj_n.set_at((x, y), N_UP if y <= 8 else N_LEFT)
            # Огромный бронированный торс и мощный хвост (y=13..30)
            elif 13 <= y <= 30:
                d_body = math.hypot((x - 16.0) * 0.85, (y - 21.0) * 0.95)
                is_tail = (22 <= y <= 31 and 20 <= x <= 29 and abs(y - (18 + (x - 18) * 0.9)) <= 3.0)
                if d_body <= 9.2 or is_tail:
                    if 13 <= y <= 16 and 9 <= x <= 22:
                        col = (222, 178, 65)  # Золотые храмовые латы на плечах
                    elif 11 <= x <= 17 and 17 <= y <= 28:
                        col = (175, 182, 122) if y % 3 != 0 else (138, 145, 92)  # Брюшные пластины
                    else:
                        col = (42, 98, 46) if (x + y) % 2 == 0 else (28, 68, 32)
                    nc = N_LEFT if x < 13 else (N_RIGHT if x > 19 else N_FLAT)
                    cj_d.set_at((x, y), col)
                    cj_n.set_at((x, y), nc)
            # Когтистые лапы (y=30..34)
            elif y >= 30 and (9 <= x <= 13 or 18 <= x <= 22):
                cj_d.set_at((x, y), (225, 220, 200) if y == 34 else (38, 86, 42))
                cj_n.set_at((x, y), N_DOWN)
    # Огромная двуручная каменная секира-монолит слева (x=2..6, y=8..32)
    for y in range(8, 33):
        cj_d.set_at((5, y), (118, 76, 40))
        cj_n.set_at((5, y), N_LEFT)
        if 10 <= y <= 20:
            for ax in range(1, 8):
                col = (62, 198, 142) if (ax == 4 and 13 <= y <= 17) else ((218, 212, 202) if ax < 5 else (168, 162, 152))
                cj_d.set_at((ax, y), col)
                cj_n.set_at((ax, y), N_LEFT if ax < 4 else N_UP)
    assets["croc_juggernaut"] = enforce_crisp_rim_normals(cj_d, cj_n)

    # =========================================================================
    # 3. ВЕДАЛКЕНЫ: СИНЕ-ФИОЛЕТОВЫЕ БЕЗВОЛОСЫЕ МАГИ (2 и 4 РУКИ + БОСС 2x2)
    # =========================================================================

    # 3.1 Ведалкен-маг (vedalken_mage, 16x20): высокий, лысый, синяя кожа, золотая мантия
    vm_d, vm_n = make_pair(16, 20)
    for y in range(1, 19):
        for x in range(4, 12):
            # Высокий гладкий череп без волос (y=1..6)
            if 1 <= y <= 6 and 5 <= x <= 10:
                if y == 1 and x in (5, 10):
                    continue
                col = GLOW_CYAN if (y == 4 and x in (6, 9)) else ((82, 128, 198) if x < 8 else (62, 98, 162))
                vm_d.set_at((x, y), col)
                vm_n.set_at((x, y), N_UP if y <= 3 else (N_LEFT if x < 7 else N_RIGHT))
            # Стройное одеяние из белого мраморного шёлка и золота (y=7..18)
            elif 7 <= y <= 18:
                if y in (7, 8) or x in (7, 8):
                    col = (225, 182, 72)
                else:
                    col = (218, 222, 232) if x < 8 else (178, 184, 198)
                vm_d.set_at((x, y), col)
                vm_n.set_at((x, y), N_LEFT if x < 7 else (N_RIGHT if x > 8 else N_FLAT))
    # Руки и парящая сфера эфира слева
    for y in (8, 9):
        vm_d.set_at((3, y), (82, 128, 198))
        vm_d.set_at((12, y), (62, 98, 162))
    for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
        vm_d.set_at((2 + dx, 6 + dy), GLOW_CYAN)
        vm_n.set_at((2 + dx, 6 + dy), N_UP)
    assets["vedalken_mage"] = enforce_crisp_rim_normals(vm_d, vm_n)

    # 3.2 Четырёхрукий Ведалкен-архонт (vedalken_four_armed, 16x20): фиолетово-индиговая кожа, 4 руки с чарами
    vf_d, vf_n = make_pair(16, 20)
    for y in range(1, 19):
        for x in range(5, 11):
            if 1 <= y <= 6:
                if y == 1 and x in (5, 10):
                    continue
                col = GLOW_CYAN if (y == 4 and x in (6, 9)) else ((122, 92, 185) if x < 8 else (94, 68, 148))
                vf_d.set_at((x, y), col)
                vf_n.set_at((x, y), N_UP if y <= 3 else N_FLAT)
            elif 7 <= y <= 18:
                col = (225, 182, 72) if (y in (7, 12) or x in (7, 8)) else ((52, 38, 86) if x < 8 else (38, 26, 66))
                vf_d.set_at((x, y), col)
                vf_n.set_at((x, y), N_LEFT if x < 7 else (N_RIGHT if x > 8 else N_FLAT))
    # Верхняя пара рук (поднята вверх с магическими печатями) и нижняя пара рук (разведена в стороны)
    arms_coords = [
        (4, 7), (3, 6), (2, 5),   # Верхняя левая рука
        (11, 7), (12, 6), (13, 5), # Верхняя правая рука
        (4, 11), (3, 11), (2, 12), # Нижняя левая рука
        (11, 11), (12, 11), (13, 12), # Нижняя правая рука
    ]
    for ax, ay in arms_coords:
        vf_d.set_at((ax, ay), (122, 92, 185) if ax < 8 else (94, 68, 148))
        vf_n.set_at((ax, ay), N_LEFT if ax < 8 else N_RIGHT)
    for gx, gy in ((2, 4), (13, 4), (1, 12), (14, 12)):
        vf_d.set_at((gx, gy), GLOW_CYAN if gy < 8 else GLOW_GOLD)
        vf_n.set_at((gx, gy), N_UP)
    assets["vedalken_four_armed"] = enforce_crisp_rim_normals(vf_d, vf_n)

    # 3.3 Верховный Ведалкен-Демиург (vedalken_arbiter, 32x36 — Босс Мраморного Храма 2x2!)
    va_d, va_n = make_pair(32, 36)
    # Сияющий золотой солнечный нимб за спиной (y=2..14)
    for y in range(2, 16):
        for x in range(8, 24):
            d_h = math.hypot(x - 15.5, y - 9.0)
            if 5.2 <= d_h <= 6.8:
                va_d.set_at((x, y), (228, 186, 68))
                va_n.set_at((x, y), N_UP)
    # Высокая безволосая голова и парящая мантия Демиурга (y=5..33)
    for y in range(5, 34):
        for x in range(9, 23):
            if 5 <= y <= 12 and 12 <= x <= 19:
                if y == 9 and x in (13, 14, 17, 18):
                    col = GLOW_CYAN  # Светящиеся глаза (y=9)
                elif y == 7 and x in (15, 16):
                    col = GLOW_GOLD  # Третий глаз на лбу
                else:
                    col = (108, 118, 198) if x < 16 else (82, 88, 162)
                va_d.set_at((x, y), col)
                va_n.set_at((x, y), N_UP if y <= 8 else N_FLAT)
            elif y >= 13:
                hw = 4 + (y - 13) // 4
                if abs(x - 15.5) <= hw:
                    is_gold = (y in (13, 14, 22, 32) or abs(x - 15.5) <= 1.2)
                    if is_gold:
                        col = (228, 186, 72)
                    else:
                        col = (226, 222, 214) if x < 16 else (188, 184, 176)
                    va_d.set_at((x, y), col)
                    va_n.set_at((x, y), N_LEFT if x < 14 else (N_RIGHT if x > 17 else N_FLAT))
    # 4 длинные руки Ведалкена с парящими сферами стихий
    for step in range(7):
        # Верхняя пара рук
        va_d.set_at((11 - step, 14 - step // 2), (108, 118, 198))
        va_d.set_at((20 + step, 14 - step // 2), (82, 88, 162))
        # Нижняя пара рук
        va_d.set_at((11 - step, 19 + step // 2), (108, 118, 198))
        va_d.set_at((20 + step, 19 + step // 2), (82, 88, 162))
    for ox, oy, ocol in ((4, 9, GLOW_CYAN), (27, 9, GLOW_CYAN), (4, 22, GLOW_GOLD), (27, 22, GLOW_GOLD)):
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                va_d.set_at((ox + dx, oy + dy), ocol)
                va_n.set_at((ox + dx, oy + dy), N_UP)
    assets["vedalken_arbiter"] = enforce_crisp_rim_normals(va_d, va_n)

    # =========================================================================
    # 4. ДИКИЕ СУЩЕСТВА И МОНСТРЫ D&D (16x20)
    # =========================================================================

    # 4.1 Болотник (swamp_lurker): сгорбленная тварь из тины, водорослей и коряг
    sl_d, sl_n = make_pair(16, 20)
    for y in range(4, 19):
        for x in range(3, 13):
            if math.hypot((x - 7.5) * 0.9, (y - 11.5) * 0.8) <= 5.5:
                if y == 7 and x in (5, 8):
                    col = GLOW_GOLD
                elif (x + y * 2) % 4 == 0:
                    col = (72, 138, 48)
                else:
                    col = (44, 78, 38) if x < 8 else (32, 56, 28)
                sl_d.set_at((x, y), col)
                sl_n.set_at((x, y), N_UP if y <= 8 else (N_LEFT if x < 7 else N_RIGHT))
    assets["swamp_lurker"] = enforce_crisp_rim_normals(sl_d, sl_n)

    # 4.2 Гремлин джунглей (jungle_gremlin): огромные острые уши, ехидная морда, кинжал
    jg_d, jg_n = make_pair(16, 20)
    for y in range(6, 19):
        for x in range(2, 14):
            # Длинные горизонтальные уши (y=7..8, x=2..4 и 11..13)
            if y in (7, 8) and x in (2, 3, 4, 11, 12, 13):
                jg_d.set_at((x, y), (118, 148, 56))
                jg_n.set_at((x, y), N_UP)
            elif 6 <= y <= 11 and 5 <= x <= 10:
                if y == 8 and x in (6, 9):
                    col = GLOW_RED
                elif y == 10 and 6 <= x <= 9:
                    col = (228, 224, 205)  # Зубастая ухмылка
                else:
                    col = (108, 138, 52)
                jg_d.set_at((x, y), col)
                jg_n.set_at((x, y), N_UP)
            elif 12 <= y <= 18 and 5 <= x <= 10:
                col = (128, 82, 42) if y in (14, 15) else (88, 115, 44)
                jg_d.set_at((x, y), col)
                jg_n.set_at((x, y), N_FLAT)
    for y in range(10, 15):
        jg_d.set_at((2, y), (198, 208, 220))
        jg_n.set_at((2, y), N_LEFT)
    assets["jungle_gremlin"] = enforce_crisp_rim_normals(jg_d, jg_n)

    # 4.3 Изумрудная кобра джунглей (jungle_viper)
    jv_d, jv_n = make_pair(16, 20)
    for y in range(3, 19):
        for x in range(3, 13):
            # Раздутый капюшон и голова (y=3..9)
            if 3 <= y <= 9 and abs(x - 7.5) <= (3.8 if 5 <= y <= 8 else 2.2):
                if y == 5 and x in (6, 9):
                    col = GLOW_RED
                elif y == 7 and x in (5, 10):
                    col = (228, 185, 55)  # Узор на капюшоне
                else:
                    col = (68, 168, 56) if x < 8 else (46, 122, 40)
                jv_d.set_at((x, y), col)
                jv_n.set_at((x, y), N_UP if y <= 5 else N_FLAT)
            # Свёрнутые кольца хвоста внизу (y=10..18)
            elif y >= 10:
                sx = 7.5 + math.sin(y * 0.85) * 3.0
                if abs(x - sx) <= 2.2:
                    col = (178, 198, 112) if abs(x - sx) < 0.8 else (54, 138, 46)
                    jv_d.set_at((x, y), col)
                    jv_n.set_at((x, y), N_UP)
    assets["jungle_viper"] = enforce_crisp_rim_normals(jv_d, jv_n)

    # 4.4 Гигантский скорпион (giant_scorpion): клешни и загнутый хвост с ядовитым жалом
    gs_d, gs_n = make_pair(16, 20)
    for y in range(2, 19):
        for x in range(2, 14):
            # Загнутый над спиной хвост с ядовитым зелёным жалом (y=2..8, x=7..12)
            if 2 <= y <= 8 and 6 <= x <= 12:
                if (x in (6, 7) and y in (3, 4)):
                    gs_d.set_at((x, y), GLOW_GREEN)
                    gs_n.set_at((x, y), N_UP)
                elif abs(x - (9 + math.sin((y - 2) * 0.5) * 2)) <= 1.2:
                    gs_d.set_at((x, y), (148, 72, 36))
                    gs_n.set_at((x, y), N_UP)
            # Клешни спереди (x=2..4, y=9..14) и сегментированное тело
            if 10 <= y <= 17 and 4 <= x <= 12:
                col = GLOW_RED if (y == 12 and x in (5, 6)) else ((128, 58, 28) if (x + y) % 2 == 0 else (92, 40, 20))
                gs_d.set_at((x, y), col)
                gs_n.set_at((x, y), N_UP if y <= 13 else N_DOWN)
            if x in (2, 3) and y in (8, 9, 14, 15):
                gs_d.set_at((x, y), (158, 78, 38))
                gs_n.set_at((x, y), N_LEFT)
    assets["giant_scorpion"] = enforce_crisp_rim_normals(gs_d, gs_n)

    # 4.5 Гриболюд-миконид (myconid_shambler): широкая шляпка со светящимися спорами
    ms_d, ms_n = make_pair(16, 20)
    for y in range(2, 19):
        if y <= 9:
            hw = max(2, int(math.sin(((y - 1) / 9.0) * math.pi) * 6.8))
            for x in range(8 - hw, 8 + hw):
                spot = (x * 3 + y * 5) % 6 == 0
                col = GLOW_CYAN if spot else ((148, 62, 198) if y < 7 else (98, 38, 138))
                ms_d.set_at((x, y), col)
                ms_n.set_at((x, y), N_UP if y <= 6 else N_DOWN)
        else:
            hw = 3 if y <= 15 else 4
            for x in range(8 - hw, 8 + hw):
                if y >= 16 and x in (7, 8):
                    continue
                col = GLOW_CYAN if (y == 11 and x in (6, 9)) else ((208, 198, 218) if x < 8 else (168, 158, 182))
                ms_d.set_at((x, y), col)
                ms_n.set_at((x, y), N_LEFT if x < 7 else (N_RIGHT if x > 8 else N_FLAT))
    assets["myconid_shambler"] = enforce_crisp_rim_normals(ms_d, ms_n)

    # 4.6 Древолюд-шиповик (thorn_treant): ходячее дерево с горящим дуплом-пастью и кроной
    tt_d, tt_n = make_pair(16, 20)
    for y in range(1, 19):
        for x in range(2, 14):
            if y <= 7 and math.hypot(x - 7.5, y - 4.5) <= 5.5:
                col = (68, 142, 48) if (x + y) % 2 == 0 else (185, 42, 52)
                tt_d.set_at((x, y), col)
                tt_n.set_at((x, y), N_UP)
            elif 7 < y <= 18 and 4 <= x <= 11:
                if y == 16 and x in (7, 8):
                    continue
                if y == 9 and x in (6, 9):
                    col = GLOW_GOLD
                elif y == 12 and 6 <= x <= 9:
                    col = (32, 18, 14)
                else:
                    col = (108, 68, 38) if x % 2 == 0 else (78, 48, 26)
                tt_d.set_at((x, y), col)
                tt_n.set_at((x, y), N_LEFT if x < 7 else (N_RIGHT if x > 8 else N_FLAT))
    assets["thorn_treant"] = enforce_crisp_rim_normals(tt_d, tt_n)

    # 4.7 Огромная пчела-шершень (giant_wasp): прозрачные крылья, полосатое брюшко и жало
    gw_d, gw_n = make_pair(16, 20)
    # Полупрозрачные перепончатые крылья сверху (y=2..8)
    for y in range(2, 9):
        for x in range(4, 13):
            if math.hypot(x - 8.5, y - 5.0) <= 3.8:
                gw_d.set_at((x, y), (185, 222, 232))
                gw_n.set_at((x, y), N_UP)
    # Голова, грудь и полосатое брюшко с жалом (y=8..16)
    for y in range(8, 16):
        for x in range(2, 14):
            if math.hypot((x - 8.0) * 0.75, (y - 11.5) * 1.1) <= 4.2:
                if x <= 4 and y == 10:
                    col = GLOW_RED
                elif x >= 7:
                    col = (225, 178, 38) if (x + y) % 2 == 0 else (34, 28, 32)
                else:
                    col = (188, 138, 36)
                gw_d.set_at((x, y), col)
                gw_n.set_at((x, y), N_UP if y <= 11 else N_DOWN)
    gw_d.set_at((14, 13), (225, 225, 215))  # Острое жало сзади
    assets["giant_wasp"] = enforce_crisp_rim_normals(gw_d, gw_n)

    # 4.8 Ржавник из D&D (rust_monster): рыже-хитиновый панцирь, две перистые антенны и хвост-пропеллер
    rm_d, rm_n = make_pair(16, 20)
    for y in range(8, 18):
        for x in range(3, 14):
            if 9 <= y <= 15 and 4 <= x <= 11:
                is_plate = (x % 2 == 0)
                col = (198, 92, 38) if is_plate else (148, 62, 24)
                if y == 10 and x == 5:
                    col = GLOW_GOLD
                rm_d.set_at((x, y), col)
                rm_n.set_at((x, y), N_UP if y <= 11 else N_FLAT)
            elif y >= 15 and x in (5, 7, 9, 10):
                rm_d.set_at((x, y), (112, 48, 20))
                rm_n.set_at((x, y), N_DOWN)
    # Две длинные перистые антенны спереди (x=1..5, y=4..10) и хвост-веер сзади (x=12..14, y=7..11)
    for step in range(5):
        rm_d.set_at((4 - step, 9 - step), (225, 135, 52))
        rm_d.set_at((4 - step, 11 + step // 2), (225, 135, 52))
        rm_n.set_at((4 - step, 9 - step), N_UP)
    for ty in range(7, 12):
        rm_d.set_at((12, ty), (178, 82, 34))
        rm_d.set_at((13, ty), (215, 118, 48))
        rm_n.set_at((13, ty), N_RIGHT)
    assets["rust_monster"] = enforce_crisp_rim_normals(rm_d, rm_n)

    # 4.9 Пронзатель из D&D (cave_piercer): каменный сталактит-мимик с хищным глазом и зубастой пастью
    cp_d, cp_n = make_pair(16, 20)
    for y in range(2, 19):
        hw = max(1, (19 - y) // 3) if y >= 7 else 5
        for x in range(8 - hw, 8 + hw):
            if y == 8 and x in (6, 9):
                col = GLOW_RED
            elif y == 6 and x % 2 == 0:
                col = (228, 224, 210)  # Зубы по верхнему раструбу
            else:
                col = (112, 102, 98) if x < 8 else (76, 68, 66)
            cp_d.set_at((x, y), col)
            cp_n.set_at((x, y), N_LEFT if x < 7 else (N_RIGHT if x > 8 else N_UP))
    assets["cave_piercer"] = enforce_crisp_rim_normals(cp_d, cp_n)

    # =========================================================================
    # 5. ДОПОЛНИТЕЛЬНЫЕ МОНСТРЫ ХРАМА, ПЕЩЕР И КОСТЯНЫХ ДЖУНГЛЕЙ
    # =========================================================================

    # 5.1 Оживший Мраморный Голем-Страж (marble_golem, 16x20)
    mg_d, mg_n = make_pair(16, 20)
    for y in range(2, 19):
        for x in range(3, 13):
            if 2 <= y <= 6 and 5 <= x <= 10:
                col = GLOW_GREEN if (y == 4 and x in (6, 9)) else (226, 220, 210)
                mg_d.set_at((x, y), col)
                mg_n.set_at((x, y), N_UP)
            elif 7 <= y <= 15:
                if 7 <= x <= 8 and 9 <= y <= 11:
                    col = GLOW_GREEN  # Светящееся нефритовое ядро в груди
                elif y in (7, 14) or x in (3, 12):
                    col = (225, 182, 72)
                else:
                    col = (228, 222, 212) if x < 8 else (192, 186, 176)
                mg_d.set_at((x, y), col)
                mg_n.set_at((x, y), N_LEFT if x < 6 else (N_RIGHT if x > 9 else N_FLAT))
            elif y >= 16 and x in (4, 5, 10, 11):
                mg_d.set_at((x, y), (192, 186, 176))
                mg_n.set_at((x, y), N_FLAT)
    assets["marble_golem"] = enforce_crisp_rim_normals(mg_d, mg_n)

    # 5.2 Храмовый Нефритовый Скарабей (jade_scarab, 16x20)
    js_d, js_n = make_pair(16, 20)
    for y in range(8, 18):
        for x in range(3, 13):
            if math.hypot((x - 7.5) * 0.9, (y - 13.0) * 1.0) <= 4.6:
                if y == 11 and x in (5, 10):
                    col = GLOW_GOLD
                elif x in (7, 8) or y == 13:
                    col = (225, 182, 72)
                else:
                    col = (52, 178, 122) if x < 8 else (36, 128, 88)
                js_d.set_at((x, y), col)
                js_n.set_at((x, y), N_UP if y <= 12 else N_DOWN)
    js_d.set_at((5, 8), (225, 182, 72))
    js_d.set_at((10, 8), (225, 182, 72))
    assets["jade_scarab"] = enforce_crisp_rim_normals(js_d, js_n)

    # 5.3 Черепопаук костяных джунглей (skull_spider, 16x20)
    ss_d, ss_n = make_pair(16, 20)
    for lx_off in (-5, -4, -3, 3, 4, 5):
        for ly in range(11, 18):
            if ( abs(lx_off) + ly ) % 2 == 0:
                ss_d.set_at((8 + lx_off, ly), (168, 158, 136))
                ss_n.set_at((8 + lx_off, ly), N_UP)
    for y in range(6, 16):
        for x in range(4, 12):
            if math.hypot(x - 7.5, y - 10.5) <= 4.2:
                if y == 10 and x in (6, 9):
                    col = GLOW_RED
                elif y == 14 and x % 2 == 0:
                    col = (32, 22, 26)
                else:
                    col = (228, 218, 195) if y < 12 else (188, 178, 155)
                ss_d.set_at((x, y), col)
                ss_n.set_at((x, y), N_UP if y <= 10 else N_FLAT)
    assets["skull_spider"] = enforce_crisp_rim_normals(ss_d, ss_n)

    # 5.4 Ягуар в костяном черепном наголовнике (bone_jaguar, 16x20)
    bj_d, bj_n = make_pair(16, 20)
    for y in range(8, 19):
        for x in range(2, 15):
            if 8 <= y <= 12 and 2 <= x <= 7:
                col = GLOW_GREEN if (y == 10 and x == 4) else (228, 218, 195)
                bj_d.set_at((x, y), col)
                bj_n.set_at((x, y), N_UP)
            elif 11 <= y <= 15 and 5 <= x <= 13:
                spot = (x * 3 + y * 5) % 4 == 0
                col = (38, 26, 22) if spot else (218, 152, 52)
                bj_d.set_at((x, y), col)
                bj_n.set_at((x, y), N_UP)
            elif y >= 16 and x in (4, 6, 10, 12):
                bj_d.set_at((x, y), (178, 122, 42))
                bj_n.set_at((x, y), N_DOWN)
    assets["bone_jaguar"] = enforce_crisp_rim_normals(bj_d, bj_n)

    # 5.5 Костяной удав (bone_constrictor, 16x20)
    bc_d, bc_n = make_pair(16, 20)
    for y in range(4, 19):
        sx = 7.5 + math.sin(y * 0.65) * 3.5
        for x in range(2, 14):
            if abs(x - sx) <= 2.4:
                if y == 5 and abs(x - sx) <= 1.0:
                    col = GLOW_RED
                elif y % 2 == 0:
                    col = (228, 218, 195)
                else:
                    col = (128, 32, 42)
                bc_d.set_at((x, y), col)
                bc_n.set_at((x, y), N_UP if y % 2 == 0 else N_FLAT)
    assets["bone_constrictor"] = enforce_crisp_rim_normals(bc_d, bc_n)

    # 5.6 Пещерный удильщик со светящейся приманкой (cave_angler, 16x20)
    ca_d, ca_n = make_pair(16, 20)
    for y in range(7, 18):
        for x in range(3, 14):
            if math.hypot((x - 8.0) * 0.85, (y - 13.0) * 1.0) <= 4.8:
                if y == 13 and x <= 7 and x % 2 == 0:
                    col = (228, 224, 210)
                elif y == 10 and x == 5:
                    col = GLOW_CYAN
                else:
                    col = (44, 52, 76) if y < 13 else (28, 34, 52)
                ca_d.set_at((x, y), col)
                ca_n.set_at((x, y), N_UP if y <= 12 else N_DOWN)
    # Стебелёк-удочка и яркий биолюминесцентный фонарик перед пастью (x=2, y=6)
    for ax, ay in ((6, 7), (5, 5), (3, 5)):
        ca_d.set_at((ax, ay), (82, 112, 148))
    for dx in (0, 1):
        for dy in (0, 1):
            ca_d.set_at((2 + dx, 6 + dy), GLOW_CYAN)
            ca_n.set_at((2 + dx, 6 + dy), N_UP)
    assets["cave_angler"] = enforce_crisp_rim_normals(ca_d, ca_n)

    # 5.7 Исполин Оссуария (ossuary_behemoth, 32x36 — Босс Костяных Джунглей 2x2!)
    ob_d, ob_n = make_pair(32, 36)
    for y in range(3, 35):
        for x in range(3, 29):
            d_b = math.hypot((x - 15.5) * 0.82, (y - 19.0) * 0.90)
            if d_b <= 11.2:
                # Пылающее некро-ядро и 3 черепных лика с горящими глазами (y >= 9!)
                if (y in (10, 11) and x in (13, 18)) or (y == 14 and x in (8, 11, 20, 23)):
                    col, nc = GLOW_GREEN, N_UP
                elif 18 <= y <= 23 and 13 <= x <= 18 and (x + y) % 2 == 0:
                    col, nc = GLOW_GREEN, N_DEEP  # Некротическое пламя внутри грудной клетки
                elif y % 3 == 0 or abs(x - 15.5) <= 1.8:
                    col = (228, 218, 195) if x < 16 else (188, 178, 155)
                    nc = N_UP if y < 14 else (N_LEFT if x < 14 else N_RIGHT)
                else:
                    col = (128, 28, 38) if (x + y) % 2 == 0 else (68, 18, 26)
                    nc = N_DEEP
                ob_d.set_at((x, y), col)
                ob_n.set_at((x, y), nc)
    # Изогнутые рога-бивни на плечах исполина
    for step in range(7):
        ob_d.set_at((6 - step // 2, 10 - step), (228, 218, 195))
        ob_d.set_at((25 + step // 2, 10 - step), (188, 178, 155))
        ob_n.set_at((6 - step // 2, 10 - step), N_UP)
        ob_n.set_at((25 + step // 2, 10 - step), N_UP)
    assets["ossuary_behemoth"] = enforce_crisp_rim_normals(ob_d, ob_n)