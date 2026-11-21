"""Crisp pixel-art icons for shields, off-hands, helmets, armor, boots, rings, and trinkets."""

import pygame


def _p(surf, x0, y0, sc, col, x, y, w=1, h=1):
    pygame.draw.rect(
        surf, col,
        (int(round(x0 + x * sc)), int(round(y0 + y * sc)),
         max(1, int(round(w * sc))), max(1, int(round(h * sc))))
    )


def _draw_ring_base(surf, x0, y0, sc, band, hi, dark, gem=None, gem_hi=None):
    # Окантовка и обод кольца
    for gx, gy in ((5, 4), (10, 4), (4, 5), (11, 5), (3, 6), (12, 6), (3, 10), (12, 10),
                   (4, 11), (11, 11), (5, 12), (10, 12)):
        _p(surf, x0, y0, sc, (22, 18, 28), gx, gy)
    _p(surf, x0, y0, sc, dark, 5, 12, 6, 2)
    _p(surf, x0, y0, sc, band, 4, 6, 2, 5)
    _p(surf, x0, y0, sc, band, 10, 6, 2, 5)
    _p(surf, x0, y0, sc, band, 5, 5, 6, 2)
    _p(surf, x0, y0, sc, band, 5, 11, 6, 2)
    _p(surf, x0, y0, sc, hi, 4, 6, 1, 3)
    _p(surf, x0, y0, sc, hi, 6, 5, 4, 1)
    if gem:
        _p(surf, x0, y0, sc, (22, 18, 28), 5, 2, 6, 4)
        _p(surf, x0, y0, sc, gem, 6, 3, 4, 3)
        if gem_hi:
            _p(surf, x0, y0, sc, gem_hi, 6, 3, 2, 1)


def draw_equip_icon(surf, icon_name, x, y, size=32):
    sc = size / 16.0
    out = (20, 16, 26)

    # ================= ЛЕВАЯ РУКА: ЩИТЫ И ФОКУСЫ =================
    if icon_name in ("shield_buckler", "shield"):
        _p(surf, x, y, sc, out, 4, 3, 8, 10)
        _p(surf, x, y, sc, out, 3, 4, 10, 8)
        _p(surf, x, y, sc, (120, 130, 146), 4, 4, 8, 8)
        _p(surf, x, y, sc, (168, 178, 195), 5, 5, 6, 6)
        _p(surf, x, y, sc, (218, 178, 78), 7, 7, 2, 2)
        _p(surf, x, y, sc, (250, 230, 145), 7, 7, 1, 1)
        return True

    if icon_name == "shield_heater":
        _p(surf, x, y, sc, out, 3, 2, 10, 7)
        _p(surf, x, y, sc, out, 4, 9, 8, 3)
        _p(surf, x, y, sc, out, 6, 12, 4, 2)
        _p(surf, x, y, sc, (150, 160, 178), 4, 3, 8, 6)
        _p(surf, x, y, sc, (125, 134, 152), 5, 9, 6, 2)
        _p(surf, x, y, sc, (105, 112, 130), 7, 11, 2, 2)
        _p(surf, x, y, sc, (185, 52, 58), 5, 4, 6, 5)
        _p(surf, x, y, sc, (225, 182, 75), 7, 4, 2, 7)
        _p(surf, x, y, sc, (225, 182, 75), 5, 6, 6, 1)
        return True

    if icon_name == "shield_spiked":
        _p(surf, x, y, sc, out, 3, 3, 10, 10)
        _p(surf, x, y, sc, (115, 74, 44), 4, 4, 8, 8)
        _p(surf, x, y, sc, (86, 52, 30), 4, 7, 8, 2)
        _p(surf, x, y, sc, (168, 175, 188), 4, 4, 8, 1)
        _p(surf, x, y, sc, (168, 175, 188), 4, 11, 8, 1)
        _p(surf, x, y, sc, (215, 222, 236), 6, 6, 4, 4)
        _p(surf, x, y, sc, (250, 252, 255), 7, 7, 2, 2)
        return True

    if icon_name == "shield_pavise":
        _p(surf, x, y, sc, out, 3, 1, 10, 14)
        _p(surf, x, y, sc, (132, 92, 54), 4, 2, 8, 12)
        _p(surf, x, y, sc, (165, 172, 186), 4, 2, 8, 2)
        _p(surf, x, y, sc, (165, 172, 186), 4, 12, 8, 2)
        _p(surf, x, y, sc, (195, 198, 208), 7, 3, 2, 10)
        _p(surf, x, y, sc, (225, 185, 85), 5, 6, 6, 2)
        return True

    if icon_name == "offhand_lantern":
        _p(surf, x, y, sc, out, 5, 2, 6, 12)
        _p(surf, x, y, sc, (185, 142, 62), 6, 2, 4, 2)
        _p(surf, x, y, sc, (145, 105, 45), 5, 4, 6, 2)
        _p(surf, x, y, sc, (255, 195, 65), 6, 6, 4, 5)
        _p(surf, x, y, sc, (255, 245, 180), 7, 7, 2, 3)
        _p(surf, x, y, sc, (145, 105, 45), 5, 11, 6, 3)
        return True

    if icon_name == "offhand_orb":
        _p(surf, x, y, sc, out, 4, 3, 8, 10)
        _p(surf, x, y, sc, out, 3, 4, 10, 8)
        _p(surf, x, y, sc, (48, 155, 140), 4, 4, 8, 8)
        _p(surf, x, y, sc, (95, 225, 195), 5, 5, 6, 6)
        _p(surf, x, y, sc, (215, 255, 240), 6, 5, 3, 2)
        _p(surf, x, y, sc, (205, 165, 70), 5, 12, 6, 2)
        return True

    if icon_name == "offhand_censer":
        _p(surf, x, y, sc, (165, 145, 110), 7, 2, 2, 4)
        _p(surf, x, y, sc, out, 4, 6, 8, 8)
        _p(surf, x, y, sc, (195, 148, 62), 5, 7, 6, 6)
        _p(surf, x, y, sc, (255, 125, 42), 6, 8, 4, 2)
        _p(surf, x, y, sc, (255, 225, 115), 7, 8, 2, 1)
        _p(surf, x, y, sc, (135, 95, 42), 5, 12, 6, 1)
        return True

    if icon_name == "offhand_gauntlet":
        _p(surf, x, y, sc, out, 4, 3, 8, 11)
        _p(surf, x, y, sc, (130, 140, 156), 5, 4, 6, 6)
        _p(surf, x, y, sc, (182, 192, 208), 5, 4, 2, 4)
        _p(surf, x, y, sc, (92, 62, 42), 5, 10, 6, 3)
        _p(surf, x, y, sc, (215, 175, 72), 5, 9, 6, 1)
        return True

    if icon_name == "offhand_tablet":
        _p(surf, x, y, sc, out, 3, 2, 10, 12)
        _p(surf, x, y, sc, (92, 88, 102), 4, 3, 8, 10)
        _p(surf, x, y, sc, (124, 120, 136), 4, 3, 7, 2)
        _p(surf, x, y, sc, (95, 220, 255), 6, 5, 4, 1)
        _p(surf, x, y, sc, (95, 220, 255), 5, 7, 6, 1)
        _p(surf, x, y, sc, (95, 220, 255), 6, 9, 3, 1)
        return True

    # ================= ГОЛОВА: ШЛЕМЫ, КАПЮШОНЫ, ВЕНЦЫ =================
    if icon_name == "helm_hood":
        _p(surf, x, y, sc, out, 4, 2, 8, 12)
        _p(surf, x, y, sc, (68, 92, 62), 5, 3, 6, 10)
        _p(surf, x, y, sc, (95, 124, 82), 5, 3, 4, 3)
        _p(surf, x, y, sc, (24, 22, 30), 6, 6, 4, 5)
        _p(surf, x, y, sc, (165, 130, 75), 4, 11, 8, 2)
        return True

    if icon_name in ("helm_sallet", "helmet"):
        _p(surf, x, y, sc, out, 3, 3, 10, 10)
        _p(surf, x, y, sc, (148, 158, 175), 4, 4, 8, 8)
        _p(surf, x, y, sc, (205, 215, 232), 5, 4, 5, 3)
        _p(surf, x, y, sc, (26, 24, 34), 5, 8, 6, 2)
        _p(surf, x, y, sc, (110, 118, 134), 3, 10, 10, 2)
        return True

    if icon_name == "helm_crown":
        _p(surf, x, y, sc, out, 2, 5, 12, 7)
        _p(surf, x, y, sc, (185, 132, 48), 3, 8, 10, 3)
        _p(surf, x, y, sc, (238, 185, 72), 3, 6, 2, 3)
        _p(surf, x, y, sc, (238, 185, 72), 7, 4, 2, 5)
        _p(surf, x, y, sc, (238, 185, 72), 11, 6, 2, 3)
        _p(surf, x, y, sc, (255, 90, 45), 7, 8, 2, 2)
        _p(surf, x, y, sc, (255, 220, 110), 7, 8, 1, 1)
        return True

    if icon_name == "helm_kettle":
        _p(surf, x, y, sc, out, 4, 3, 8, 6)
        _p(surf, x, y, sc, out, 2, 8, 12, 4)
        _p(surf, x, y, sc, (150, 158, 172), 5, 4, 6, 5)
        _p(surf, x, y, sc, (198, 206, 220), 6, 4, 3, 3)
        _p(surf, x, y, sc, (125, 132, 146), 3, 9, 10, 2)
        return True

    if icon_name == "helm_coif":
        _p(surf, x, y, sc, out, 4, 3, 8, 10)
        _p(surf, x, y, sc, (158, 132, 96), 5, 4, 6, 8)
        _p(surf, x, y, sc, (192, 168, 126), 6, 4, 4, 3)
        _p(surf, x, y, sc, (118, 92, 62), 6, 7, 4, 4)
        return True

    if icon_name == "helm_mask":
        _p(surf, x, y, sc, out, 4, 2, 8, 12)
        _p(surf, x, y, sc, (218, 208, 186), 5, 3, 6, 10)
        _p(surf, x, y, sc, (175, 162, 140), 5, 10, 6, 3)
        _p(surf, x, y, sc, (24, 18, 26), 6, 6, 2, 2)
        _p(surf, x, y, sc, (24, 18, 26), 9, 6, 2, 2)
        _p(surf, x, y, sc, (185, 45, 52), 7, 3, 2, 2)
        return True

    if icon_name == "helm_circlet":
        _p(surf, x, y, sc, out, 3, 6, 10, 5)
        _p(surf, x, y, sc, (195, 132, 72), 4, 7, 8, 3)
        _p(surf, x, y, sc, (242, 182, 112), 5, 7, 6, 1)
        _p(surf, x, y, sc, (85, 205, 255), 7, 6, 2, 3)
        return True

    if icon_name == "helm_bascinet":
        _p(surf, x, y, sc, (215, 205, 185), 2, 3, 2, 4)
        _p(surf, x, y, sc, (215, 205, 185), 12, 3, 2, 4)
        _p(surf, x, y, sc, out, 4, 3, 8, 10)
        _p(surf, x, y, sc, (135, 142, 158), 5, 4, 6, 8)
        _p(surf, x, y, sc, (195, 202, 218), 6, 4, 3, 4)
        _p(surf, x, y, sc, (24, 20, 30), 6, 8, 4, 2)
        return True

    if icon_name == "helm_miner":
        _p(surf, x, y, sc, out, 3, 5, 10, 7)
        _p(surf, x, y, sc, (165, 118, 56), 4, 6, 8, 5)
        _p(surf, x, y, sc, (210, 162, 86), 5, 6, 5, 2)
        _p(surf, x, y, sc, (255, 220, 85), 7, 3, 2, 3)
        _p(surf, x, y, sc, (255, 250, 205), 7, 3, 1, 2)
        return True

    # ================= ТОРС: ДОСПЕХИ И МАНТИИ =================
    if icon_name in ("armor_robe", "armor_cloth"):
        _p(surf, x, y, sc, out, 3, 2, 10, 12)
        _p(surf, x, y, sc, (86, 64, 142), 4, 3, 8, 10)
        _p(surf, x, y, sc, (124, 96, 188), 5, 4, 3, 8)
        _p(surf, x, y, sc, (218, 178, 72), 7, 3, 2, 10)
        _p(surf, x, y, sc, (218, 178, 72), 4, 9, 8, 1)
        return True

    if icon_name in ("armor_brigandine", "armor_leather"):
        _p(surf, x, y, sc, out, 3, 2, 10, 12)
        _p(surf, x, y, sc, (128, 78, 44), 4, 3, 8, 10)
        _p(surf, x, y, sc, (162, 102, 58), 5, 4, 6, 4)
        for rx in (5, 8, 10):
            for ry in (5, 8, 11):
                _p(surf, x, y, sc, (205, 185, 115), rx, ry)
        return True

    if icon_name in ("armor_cuirass", "armor_plate"):
        _p(surf, x, y, sc, out, 3, 2, 10, 12)
        _p(surf, x, y, sc, (152, 162, 180), 4, 3, 8, 10)
        _p(surf, x, y, sc, (212, 222, 238), 5, 4, 4, 5)
        _p(surf, x, y, sc, (98, 106, 122), 4, 10, 8, 2)
        _p(surf, x, y, sc, (220, 178, 75), 7, 3, 2, 9)
        return True

    if icon_name == "armor_cloak":
        _p(surf, x, y, sc, out, 3, 2, 10, 12)
        _p(surf, x, y, sc, (48, 44, 66), 4, 3, 8, 10)
        _p(surf, x, y, sc, (78, 72, 108), 5, 4, 3, 8)
        _p(surf, x, y, sc, (175, 185, 205), 6, 3, 4, 2)
        return True

    if icon_name == "armor_gambeson":
        _p(surf, x, y, sc, out, 3, 2, 10, 12)
        _p(surf, x, y, sc, (166, 138, 98), 4, 3, 8, 10)
        for sx in (6, 9):
            _p(surf, x, y, sc, (118, 92, 62), sx, 3, 1, 10)
        _p(surf, x, y, sc, (110, 62, 38), 4, 9, 8, 2)
        return True

    if icon_name == "armor_jerkin":
        _p(surf, x, y, sc, out, 3, 2, 10, 12)
        _p(surf, x, y, sc, (116, 86, 52), 4, 3, 8, 10)
        _p(surf, x, y, sc, (168, 126, 68), 4, 6, 3, 3)
        _p(surf, x, y, sc, (168, 126, 68), 9, 6, 3, 3)
        _p(surf, x, y, sc, (168, 126, 68), 5, 10, 6, 3)
        _p(surf, x, y, sc, (225, 185, 80), 7, 7, 2, 2)
        return True

    if icon_name == "armor_scale":
        _p(surf, x, y, sc, out, 3, 2, 10, 12)
        _p(surf, x, y, sc, (82, 118, 112), 4, 3, 8, 10)
        for ry in (4, 6, 8, 10):
            for rx in (4, 6, 8, 10):
                _p(surf, x, y, sc, (145, 188, 178) if (rx + ry) % 4 == 0 else (105, 148, 140), rx, ry, 2, 1)
        return True

    if icon_name == "armor_coat":
        _p(surf, x, y, sc, out, 3, 2, 10, 12)
        _p(surf, x, y, sc, (58, 96, 72), 4, 3, 8, 10)
        _p(surf, x, y, sc, (152, 108, 62), 4, 8, 8, 2)
        _p(surf, x, y, sc, (85, 215, 245), 5, 9, 2, 3)
        _p(surf, x, y, sc, (225, 78, 85), 9, 9, 2, 3)
        return True

    if icon_name == "armor_doublet":
        _p(surf, x, y, sc, out, 3, 2, 10, 12)
        _p(surf, x, y, sc, (148, 46, 56), 4, 3, 8, 10)
        _p(surf, x, y, sc, (195, 72, 82), 5, 4, 3, 6)
        _p(surf, x, y, sc, (232, 192, 82), 7, 4, 2, 8)
        return True

    # ================= НОГИ: САПОГИ И ПОНОЖИ =================
    if icon_name in ("boots_greaves", "boots"):
        _p(surf, x, y, sc, out, 3, 3, 7, 10)
        _p(surf, x, y, sc, out, 3, 9, 10, 4)
        _p(surf, x, y, sc, (132, 142, 158), 4, 4, 5, 8)
        _p(surf, x, y, sc, (186, 196, 212), 5, 4, 2, 6)
        _p(surf, x, y, sc, (112, 120, 136), 4, 10, 8, 2)
        return True

    if icon_name == "boots_soft":
        _p(surf, x, y, sc, out, 3, 4, 7, 9)
        _p(surf, x, y, sc, out, 3, 9, 10, 4)
        _p(surf, x, y, sc, (118, 82, 52), 4, 5, 5, 7)
        _p(surf, x, y, sc, (158, 118, 76), 4, 10, 8, 2)
        _p(surf, x, y, sc, (78, 118, 72), 4, 5, 5, 2)
        return True

    if icon_name == "boots_courier":
        _p(surf, x, y, sc, out, 3, 3, 7, 10)
        _p(surf, x, y, sc, out, 3, 9, 10, 4)
        _p(surf, x, y, sc, (156, 98, 48), 4, 4, 5, 8)
        _p(surf, x, y, sc, (192, 128, 66), 4, 10, 8, 2)
        _p(surf, x, y, sc, (238, 218, 145), 9, 4, 3, 2)
        return True

    if icon_name == "boots_sabatons":
        _p(surf, x, y, sc, out, 3, 3, 7, 10)
        _p(surf, x, y, sc, out, 3, 9, 11, 4)
        _p(surf, x, y, sc, (162, 170, 186), 4, 4, 5, 8)
        _p(surf, x, y, sc, (218, 224, 238), 5, 10, 8, 2)
        _p(surf, x, y, sc, (218, 175, 72), 4, 7, 5, 1)
        return True

    if icon_name == "boots_waders":
        _p(surf, x, y, sc, out, 3, 2, 7, 11)
        _p(surf, x, y, sc, out, 3, 9, 10, 4)
        _p(surf, x, y, sc, (68, 76, 62), 4, 3, 5, 9)
        _p(surf, x, y, sc, (98, 112, 88), 5, 3, 3, 2)
        _p(surf, x, y, sc, (82, 88, 72), 4, 10, 8, 2)
        return True

    if icon_name == "boots_sandals":
        _p(surf, x, y, sc, out, 3, 8, 10, 5)
        _p(surf, x, y, sc, (148, 104, 62), 4, 10, 8, 2)
        _p(surf, x, y, sc, (218, 182, 92), 5, 6, 1, 5)
        _p(surf, x, y, sc, (218, 182, 92), 8, 6, 1, 5)
        _p(surf, x, y, sc, (105, 195, 245), 6, 8, 3, 2)
        return True

    if icon_name == "boots_spurred":
        _p(surf, x, y, sc, out, 4, 3, 7, 10)
        _p(surf, x, y, sc, out, 4, 9, 9, 4)
        _p(surf, x, y, sc, (92, 48, 46), 5, 4, 5, 8)
        _p(surf, x, y, sc, (132, 68, 62), 5, 10, 7, 2)
        _p(surf, x, y, sc, (238, 198, 82), 2, 10, 3, 2)
        return True

    # ================= КОЛЬЦА =================
    ring_styles = {
        "ring":          ((225, 185, 68), (255, 232, 140), (140, 105, 30), (90, 235, 155), (195, 255, 225)),
        "ring_amber":    ((220, 178, 68), (255, 228, 135), (138, 102, 28), (245, 165, 38), (255, 235, 145)),
        "ring_blood":    ((165, 148, 145), (218, 205, 202), (92, 78, 76),  (215, 35, 52),  (255, 140, 150)),
        "ring_iron":     ((138, 146, 160), (198, 208, 224), (78, 84, 96),  (168, 176, 192), (235, 242, 255)),
        "ring_sapphire": ((190, 204, 224), (240, 248, 255), (108, 118, 136), (55, 155, 248), (175, 230, 255)),
        "ring_silver":   ((195, 212, 225), (248, 254, 255), (112, 128, 142), (140, 235, 245), (235, 255, 255)),
        "ring_ember":    ((105, 82, 76),  (155, 122, 110), (58, 44, 42),  (255, 112, 32), (255, 232, 118)),
        "ring_bone":     ((208, 198, 175), (242, 235, 218), (135, 124, 105), None, None),
        "ring_emerald":  ((185, 152, 78), (235, 202, 118), (110, 86, 38), (52, 198, 92),  (168, 255, 188)),
        "ring_onyx":     ((115, 110, 128), (168, 162, 185), (56, 52, 68), (38, 34, 52),   (120, 112, 148)),
    }
    if icon_name in ring_styles:
        _draw_ring_base(surf, x, y, sc, *ring_styles[icon_name])
        return True

    # ================= АМУЛЕТЫ И ТАЛИСМАНЫ =================
    if icon_name in ("trinket_eye", "trinket"):
        _p(surf, x, y, sc, out, 3, 4, 10, 8)
        _p(surf, x, y, sc, (205, 162, 65), 4, 5, 8, 6)
        _p(surf, x, y, sc, (75, 185, 240), 5, 6, 6, 4)
        _p(surf, x, y, sc, (22, 26, 42), 7, 6, 2, 4)
        _p(surf, x, y, sc, (230, 250, 255), 6, 6, 1, 1)
        return True

    if icon_name == "trinket_heart":
        _p(surf, x, y, sc, out, 3, 4, 10, 7)
        _p(surf, x, y, sc, out, 5, 11, 6, 3)
        _p(surf, x, y, sc, (118, 124, 138), 4, 5, 4, 5)
        _p(surf, x, y, sc, (118, 124, 138), 8, 5, 4, 5)
        _p(surf, x, y, sc, (118, 124, 138), 6, 10, 4, 3)
        _p(surf, x, y, sc, (215, 58, 62), 7, 7, 2, 3)
        return True

    if icon_name == "trinket_fang":
        _p(surf, x, y, sc, (168, 118, 62), 4, 3, 8, 2)
        _p(surf, x, y, sc, out, 5, 4, 6, 10)
        _p(surf, x, y, sc, (232, 224, 202), 6, 5, 4, 5)
        _p(surf, x, y, sc, (202, 192, 168), 7, 10, 3, 3)
        return True

    if icon_name == "trinket_prism":
        _p(surf, x, y, sc, out, 5, 2, 6, 12)
        _p(surf, x, y, sc, (75, 165, 245), 6, 3, 4, 10)
        _p(surf, x, y, sc, (175, 232, 255), 6, 4, 2, 7)
        _p(surf, x, y, sc, (235, 252, 255), 7, 5, 1, 3)
        return True

    if icon_name == "trinket_bell":
        _p(surf, x, y, sc, out, 5, 3, 6, 10)
        _p(surf, x, y, sc, out, 3, 9, 10, 3)
        _p(surf, x, y, sc, (215, 172, 68), 6, 4, 4, 6)
        _p(surf, x, y, sc, (245, 212, 108), 4, 9, 8, 2)
        _p(surf, x, y, sc, (150, 115, 45), 7, 11, 2, 2)
        return True

    if icon_name == "trinket_buckle":
        _p(surf, x, y, sc, out, 3, 4, 10, 8)
        _p(surf, x, y, sc, (188, 142, 62), 4, 5, 8, 6)
        _p(surf, x, y, sc, (78, 52, 34), 6, 6, 4, 4)
        _p(surf, x, y, sc, (238, 205, 102), 7, 6, 2, 4)
        return True

    if icon_name == "trinket_medal":
        _p(surf, x, y, sc, (175, 45, 52), 5, 2, 6, 4)
        _p(surf, x, y, sc, out, 4, 5, 8, 8)
        _p(surf, x, y, sc, (225, 182, 68), 5, 6, 6, 6)
        _p(surf, x, y, sc, (255, 235, 145), 7, 7, 2, 4)
        return True

    if icon_name == "trinket_jar":
        _p(surf, x, y, sc, out, 4, 3, 8, 11)
        _p(surf, x, y, sc, (155, 108, 58), 6, 3, 4, 2)
        _p(surf, x, y, sc, (82, 125, 115), 5, 5, 6, 8)
        _p(surf, x, y, sc, (215, 255, 115), 6, 7, 2, 2)
        _p(surf, x, y, sc, (245, 255, 175), 8, 10, 2, 2)
        return True
# ================= СОКРОВИЩА И ДОБЫЧА ДЛЯ СКУПЩИКА =================
    if icon_name == "loot_plate":
        _p(surf, x, y, sc, out, 3, 3, 10, 10)
        _p(surf, x, y, sc, (142, 150, 164), 4, 4, 8, 8)
        _p(surf, x, y, sc, (192, 200, 214), 5, 5, 6, 6)
        _p(surf, x, y, sc, (124, 132, 146), 6, 6, 4, 4)
        _p(surf, x, y, sc, (230, 236, 245), 5, 5, 2, 1)
        return True

    if icon_name == "loot_candlestick":
        _p(surf, x, y, sc, out, 6, 2, 4, 4)
        _p(surf, x, y, sc, (240, 232, 210), 7, 3, 2, 3)
        _p(surf, x, y, sc, (255, 200, 70), 7, 2, 2, 1)
        _p(surf, x, y, sc, out, 5, 6, 6, 8)
        _p(surf, x, y, sc, (198, 136, 58), 6, 6, 4, 2)
        _p(surf, x, y, sc, (175, 114, 45), 7, 8, 2, 4)
        _p(surf, x, y, sc, (228, 168, 78), 4, 12, 8, 2)
        return True

    if icon_name == "loot_goblet":
        _p(surf, x, y, sc, out, 4, 2, 8, 6)
        _p(surf, x, y, sc, out, 6, 8, 4, 4)
        _p(surf, x, y, sc, out, 4, 12, 8, 2)
        _p(surf, x, y, sc, (150, 158, 172), 5, 3, 6, 4)
        _p(surf, x, y, sc, (205, 214, 228), 6, 3, 2, 3)
        _p(surf, x, y, sc, (128, 136, 150), 7, 7, 2, 5)
        _p(surf, x, y, sc, (150, 158, 172), 5, 12, 6, 1)
        return True

    if icon_name == "loot_silver_ingot":
        _p(surf, x, y, sc, out, 2, 5, 12, 7)
        _p(surf, x, y, sc, (156, 168, 188), 3, 8, 10, 3)
        _p(surf, x, y, sc, (215, 226, 242), 4, 6, 8, 3)
        _p(surf, x, y, sc, (248, 252, 255), 5, 6, 4, 1)
        return True

    if icon_name == "loot_box":
        _p(surf, x, y, sc, out, 2, 4, 12, 9)
        _p(surf, x, y, sc, (126, 76, 44), 3, 5, 10, 7)
        _p(surf, x, y, sc, (162, 104, 58), 4, 5, 8, 3)
        _p(surf, x, y, sc, (215, 174, 72), 3, 8, 10, 1)
        _p(surf, x, y, sc, (245, 212, 105), 7, 7, 2, 3)
        return True

    if icon_name == "loot_brooch":
        _p(surf, x, y, sc, out, 4, 3, 8, 10)
        _p(surf, x, y, sc, (186, 134, 56), 5, 4, 6, 8)
        _p(surf, x, y, sc, (235, 148, 32), 6, 5, 4, 6)
        _p(surf, x, y, sc, (255, 215, 95), 6, 5, 2, 2)
        _p(surf, x, y, sc, (65, 36, 18), 8, 8, 1, 1)
        return True

    if icon_name == "loot_chalice":
        _p(surf, x, y, sc, out, 4, 2, 8, 6)
        _p(surf, x, y, sc, out, 6, 8, 4, 4)
        _p(surf, x, y, sc, out, 4, 12, 8, 2)
        _p(surf, x, y, sc, (224, 176, 52), 5, 3, 6, 4)
        _p(surf, x, y, sc, (255, 232, 135), 6, 3, 2, 3)
        _p(surf, x, y, sc, (215, 42, 62), 7, 5, 2, 1)
        _p(surf, x, y, sc, (186, 138, 38), 7, 7, 2, 5)
        _p(surf, x, y, sc, (224, 176, 52), 5, 12, 6, 1)
        return True

    if icon_name == "loot_painting":
        _p(surf, x, y, sc, out, 2, 3, 12, 10)
        _p(surf, x, y, sc, (182, 134, 58), 3, 4, 10, 8)
        _p(surf, x, y, sc, (42, 66, 84), 4, 5, 8, 3)
        _p(surf, x, y, sc, (48, 76, 52), 4, 8, 8, 3)
        _p(surf, x, y, sc, (228, 232, 200), 9, 6, 2, 1)
        _p(surf, x, y, sc, (92, 64, 42), 5, 7, 2, 3)
        return True

    if icon_name == "loot_watch":
        _p(surf, x, y, sc, (222, 180, 68), 7, 2, 2, 2)
        _p(surf, x, y, sc, out, 3, 4, 10, 10)
        _p(surf, x, y, sc, (222, 180, 68), 4, 5, 8, 8)
        _p(surf, x, y, sc, (238, 234, 220), 5, 6, 6, 6)
        _p(surf, x, y, sc, (28, 24, 34), 7, 7, 1, 3)
        _p(surf, x, y, sc, (28, 24, 34), 7, 9, 3, 1)
        return True

    if icon_name == "loot_gold_ingot":
        _p(surf, x, y, sc, out, 2, 5, 12, 7)
        _p(surf, x, y, sc, (196, 138, 28), 3, 8, 10, 3)
        _p(surf, x, y, sc, (244, 194, 52), 4, 6, 8, 3)
        _p(surf, x, y, sc, (255, 244, 156), 5, 6, 4, 1)
        return True

    if icon_name == "loot_portrait":
        _p(surf, x, y, sc, out, 3, 2, 10, 12)
        _p(surf, x, y, sc, (218, 174, 62), 4, 3, 8, 10)
        _p(surf, x, y, sc, (54, 32, 46), 5, 4, 6, 8)
        _p(surf, x, y, sc, (224, 188, 158), 7, 5, 2, 3)
        _p(surf, x, y, sc, (165, 42, 52), 6, 8, 4, 4)
        _p(surf, x, y, sc, (242, 235, 220), 7, 8, 2, 1)
        return True

    if icon_name == "loot_idol":
        _p(surf, x, y, sc, out, 4, 2, 8, 12)
        _p(surf, x, y, sc, (42, 138, 92), 5, 3, 6, 10)
        _p(surf, x, y, sc, (88, 198, 138), 6, 4, 4, 4)
        _p(surf, x, y, sc, (235, 195, 72), 6, 5, 1, 1)
        _p(surf, x, y, sc, (235, 195, 72), 9, 5, 1, 1)
        _p(surf, x, y, sc, (28, 92, 62), 5, 10, 6, 3)
        return True

    if icon_name == "loot_scepter":
        _p(surf, x, y, sc, out, 3, 2, 10, 12)
        for i in range(7):
            _p(surf, x, y, sc, (218, 172, 52), 4 + i, 12 - i, 2, 2)
        _p(surf, x, y, sc, (255, 230, 120), 9, 3, 4, 4)
        _p(surf, x, y, sc, (175, 68, 242), 10, 4, 2, 2)
        return True

    if icon_name == "loot_crown_loot":
        _p(surf, x, y, sc, out, 2, 5, 12, 7)
        _p(surf, x, y, sc, (226, 182, 58), 3, 8, 10, 3)
        _p(surf, x, y, sc, (252, 224, 118), 3, 6, 2, 3)
        _p(surf, x, y, sc, (252, 224, 118), 7, 4, 2, 5)
        _p(surf, x, y, sc, (252, 224, 118), 11, 6, 2, 3)
        _p(surf, x, y, sc, (48, 36, 68), 7, 8, 2, 2)
        _p(surf, x, y, sc, (185, 85, 255), 7, 8, 1, 1)
        return True

    if icon_name == "loot_masterpiece":
        _p(surf, x, y, sc, out, 2, 2, 12, 12)
        _p(surf, x, y, sc, (238, 194, 62), 3, 3, 10, 10)
        _p(surf, x, y, sc, (40, 48, 92), 4, 4, 8, 8)
        _p(surf, x, y, sc, (245, 198, 72), 5, 5, 3, 3)
        _p(surf, x, y, sc, (215, 78, 52), 8, 6, 3, 4)
        _p(surf, x, y, sc, (120, 215, 235), 5, 9, 6, 2)
        return True
    
    return False