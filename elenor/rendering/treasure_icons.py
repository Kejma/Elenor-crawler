"""Crisp 16x16 procedural pixel-art icons for lootable treasures (format: tr:<shape>:<palette>)."""

import pygame


_PALETTES = {
    # (dark, main, highlight, accent)
    "pewter":   ((94, 100, 112),  (144, 152, 166), (202, 210, 224), (232, 238, 248)),
    "tin":      ((108, 114, 124), (160, 166, 178), (214, 220, 232), (242, 246, 252)),
    "iron":     ((68, 72, 82),    (108, 114, 128), (156, 164, 180), (195, 204, 220)),
    "copper":   ((122, 62, 34),   (186, 102, 56),  (234, 152, 98),  (252, 210, 155)),
    "brass":    ((134, 96, 36),   (196, 148, 56),  (238, 198, 96),  (255, 236, 165)),
    "bronze":   ((112, 74, 40),   (168, 114, 62),  (214, 162, 98),  (242, 204, 142)),
    "wood":     ((84, 52, 30),    (128, 82, 46),   (168, 116, 68),  (215, 175, 82)),
    "clay":     ((118, 66, 46),   (168, 98, 68),   (210, 140, 102), (238, 212, 168)),
    "ochre":    ((124, 92, 44),   (178, 138, 68),  (222, 186, 112), (92, 66, 36)),
    "bone":     ((142, 132, 112), (204, 194, 172), (238, 232, 214), (110, 98, 82)),
    "ivory":    ((164, 154, 136), (222, 214, 196), (248, 244, 234), (195, 152, 68)),
    "silver":   ((118, 130, 148), (178, 192, 212), (230, 240, 252), (255, 255, 255)),
    "gold":     ((168, 118, 24),  (232, 182, 46),  (255, 234, 130), (255, 250, 205)),
    "platinum": ((112, 152, 176), (174, 218, 240), (232, 250, 255), (255, 255, 255)),
    "amber":    ((152, 76, 18),   (228, 136, 28),  (255, 208, 92),  (186, 134, 54)),
    "jade":     ((32, 98, 68),    (58, 156, 108),  (124, 218, 164), (228, 186, 72)),
    "emerald":  ((22, 108, 48),   (48, 188, 88),   (142, 248, 168), (235, 194, 68)),
    "ruby":     ((126, 22, 38),   (212, 42, 62),   (255, 138, 152), (238, 190, 62)),
    "sapphire": ((28, 64, 148),   (56, 136, 238),  (156, 218, 255), (238, 196, 78)),
    "amethyst": ((86, 36, 132),   (156, 72, 228),  (222, 168, 255), (232, 188, 72)),
    "obsidian": ((28, 24, 38),    (52, 46, 72),    (98, 88, 132),   (225, 182, 72)),
    "crimson":  ((104, 26, 36),   (166, 46, 56),   (218, 86, 94),   (232, 188, 76)),
    "azure":    ((34, 68, 108),   (64, 118, 176),  (128, 188, 236), (228, 186, 78)),
    "forest":   ((36, 72, 42),    (66, 118, 68),   (118, 174, 112), (218, 184, 92)),
}


def _p(surf, x0, y0, sc, col, x, y, w=1, h=1):
    pygame.draw.rect(
        surf, col,
        (int(round(x0 + x * sc)), int(round(y0 + y * sc)),
         max(1, int(round(w * sc))), max(1, int(round(h * sc))))
    )


def draw_treasure_icon(surf, icon_name, x, y, size=32):
    if not icon_name.startswith("tr:"):
        return False
    parts = icon_name.split(":")
    if len(parts) != 3:
        return False
    _, shape, pal_name = parts
    dk, mn, hi, ac = _PALETTES.get(pal_name, _PALETTES["gold"])
    sc = size / 16.0
    out = (20, 16, 26)

    if shape == "plate":
        _p(surf, x, y, sc, out, 3, 3, 10, 10)
        _p(surf, x, y, sc, dk, 4, 4, 8, 8)
        _p(surf, x, y, sc, mn, 5, 5, 6, 6)
        _p(surf, x, y, sc, dk, 6, 6, 4, 4)
        _p(surf, x, y, sc, hi, 5, 5, 2, 1)
        _p(surf, x, y, sc, ac, 7, 7, 2, 2)
        return True

    if shape == "cup":
        _p(surf, x, y, sc, out, 4, 2, 8, 6)
        _p(surf, x, y, sc, out, 6, 8, 4, 4)
        _p(surf, x, y, sc, out, 4, 12, 8, 2)
        _p(surf, x, y, sc, mn, 5, 3, 6, 4)
        _p(surf, x, y, sc, hi, 6, 3, 2, 3)
        _p(surf, x, y, sc, dk, 7, 7, 2, 5)
        _p(surf, x, y, sc, mn, 5, 12, 6, 1)
        _p(surf, x, y, sc, ac, 7, 5, 2, 1)
        return True

    if shape == "candle":
        _p(surf, x, y, sc, out, 6, 2, 4, 4)
        _p(surf, x, y, sc, (242, 234, 214), 7, 3, 2, 3)
        _p(surf, x, y, sc, (255, 205, 72), 7, 2, 2, 1)
        _p(surf, x, y, sc, out, 4, 6, 8, 8)
        _p(surf, x, y, sc, mn, 5, 6, 6, 2)
        _p(surf, x, y, sc, dk, 7, 8, 2, 4)
        _p(surf, x, y, sc, hi, 4, 12, 8, 2)
        return True

    if shape == "ingot":
        _p(surf, x, y, sc, out, 2, 5, 12, 7)
        _p(surf, x, y, sc, dk, 3, 8, 10, 3)
        _p(surf, x, y, sc, mn, 4, 6, 8, 3)
        _p(surf, x, y, sc, hi, 5, 6, 5, 1)
        _p(surf, x, y, sc, ac, 6, 7, 2, 1)
        return True

    if shape == "box":
        _p(surf, x, y, sc, out, 2, 4, 12, 9)
        _p(surf, x, y, sc, dk, 3, 5, 10, 7)
        _p(surf, x, y, sc, mn, 4, 5, 8, 3)
        _p(surf, x, y, sc, hi, 5, 5, 4, 1)
        _p(surf, x, y, sc, ac, 3, 8, 10, 1)
        _p(surf, x, y, sc, ac, 7, 7, 2, 3)
        return True

    if shape == "brooch":
        _p(surf, x, y, sc, out, 4, 3, 8, 10)
        _p(surf, x, y, sc, ac, 5, 4, 6, 8)
        _p(surf, x, y, sc, mn, 6, 5, 4, 6)
        _p(surf, x, y, sc, hi, 6, 5, 2, 2)
        return True

    if shape == "painting":
        _p(surf, x, y, sc, out, 2, 3, 12, 10)
        _p(surf, x, y, sc, ac, 3, 4, 10, 8)
        _p(surf, x, y, sc, dk, 4, 5, 8, 6)
        _p(surf, x, y, sc, mn, 4, 5, 8, 3)
        _p(surf, x, y, sc, hi, 9, 6, 2, 2)
        return True

    if shape == "portrait":
        _p(surf, x, y, sc, out, 3, 2, 10, 12)
        _p(surf, x, y, sc, ac, 4, 3, 8, 10)
        _p(surf, x, y, sc, dk, 5, 4, 6, 8)
        _p(surf, x, y, sc, (226, 190, 160), 7, 5, 2, 3)
        _p(surf, x, y, sc, mn, 6, 8, 4, 4)
        _p(surf, x, y, sc, hi, 7, 8, 2, 1)
        return True

    if shape == "watch":
        _p(surf, x, y, sc, ac, 7, 2, 2, 2)
        _p(surf, x, y, sc, out, 3, 4, 10, 10)
        _p(surf, x, y, sc, mn, 4, 5, 8, 8)
        _p(surf, x, y, sc, hi, 5, 6, 6, 6)
        _p(surf, x, y, sc, out, 7, 7, 1, 3)
        _p(surf, x, y, sc, out, 7, 9, 3, 1)
        return True

    if shape == "idol":
        _p(surf, x, y, sc, out, 4, 2, 8, 12)
        _p(surf, x, y, sc, mn, 5, 3, 6, 10)
        _p(surf, x, y, sc, hi, 6, 4, 4, 4)
        _p(surf, x, y, sc, ac, 6, 5, 1, 1)
        _p(surf, x, y, sc, ac, 9, 5, 1, 1)
        _p(surf, x, y, sc, dk, 5, 10, 6, 3)
        return True

    if shape == "scepter":
        _p(surf, x, y, sc, out, 3, 2, 10, 12)
        for i in range(7):
            _p(surf, x, y, sc, mn, 4 + i, 12 - i, 2, 2)
        _p(surf, x, y, sc, hi, 9, 3, 4, 4)
        _p(surf, x, y, sc, ac, 10, 4, 2, 2)
        return True

    if shape == "crown":
        _p(surf, x, y, sc, out, 2, 5, 12, 7)
        _p(surf, x, y, sc, mn, 3, 8, 10, 3)
        _p(surf, x, y, sc, hi, 3, 6, 2, 3)
        _p(surf, x, y, sc, hi, 7, 4, 2, 5)
        _p(surf, x, y, sc, hi, 11, 6, 2, 3)
        _p(surf, x, y, sc, ac, 7, 8, 2, 2)
        return True

    if shape == "vase":
        _p(surf, x, y, sc, out, 5, 2, 6, 3)
        _p(surf, x, y, sc, out, 3, 5, 10, 8)
        _p(surf, x, y, sc, out, 5, 12, 6, 2)
        _p(surf, x, y, sc, mn, 6, 3, 4, 2)
        _p(surf, x, y, sc, mn, 4, 6, 8, 6)
        _p(surf, x, y, sc, hi, 5, 6, 2, 4)
        _p(surf, x, y, sc, ac, 4, 9, 8, 1)
        _p(surf, x, y, sc, dk, 6, 12, 4, 1)
        return True

    if shape == "spoon":
        _p(surf, x, y, sc, out, 7, 2, 6, 6)
        _p(surf, x, y, sc, mn, 8, 3, 4, 4)
        _p(surf, x, y, sc, hi, 9, 3, 2, 2)
        for i in range(6):
            _p(surf, x, y, sc, out, 3 + i, 12 - i, 2, 2)
            _p(surf, x, y, sc, dk if i < 2 else mn, 3 + i, 12 - i, 1, 1)
        return True

    if shape == "mirror":
        _p(surf, x, y, sc, out, 4, 2, 8, 8)
        _p(surf, x, y, sc, out, 6, 10, 4, 4)
        _p(surf, x, y, sc, mn, 5, 3, 6, 6)
        _p(surf, x, y, sc, (190, 224, 240), 6, 4, 4, 4)
        _p(surf, x, y, sc, (245, 252, 255), 6, 4, 2, 2)
        _p(surf, x, y, sc, dk, 7, 10, 2, 3)
        return True

    if shape == "tome":
        _p(surf, x, y, sc, out, 3, 2, 10, 12)
        _p(surf, x, y, sc, dk, 4, 3, 2, 10)
        _p(surf, x, y, sc, mn, 6, 3, 6, 10)
        _p(surf, x, y, sc, hi, 7, 4, 4, 2)
        _p(surf, x, y, sc, ac, 7, 7, 4, 3)
        return True

    if shape == "necklace":
        for gx, gy in ((4, 3), (11, 3), (3, 4), (12, 4), (3, 6), (12, 6),
                       (4, 8), (11, 8), (5, 9), (10, 9), (6, 10), (9, 10)):
            _p(surf, x, y, sc, out, gx, gy, 1, 1)
        for gx, gy in ((4, 4), (11, 4), (4, 6), (11, 6), (5, 8), (10, 8), (6, 9), (9, 9)):
            _p(surf, x, y, sc, hi, gx, gy, 1, 1)
        _p(surf, x, y, sc, out, 6, 10, 4, 4)
        _p(surf, x, y, sc, mn, 7, 11, 2, 2)
        _p(surf, x, y, sc, ac, 7, 11, 1, 1)
        return True

    if shape == "mask":
        _p(surf, x, y, sc, out, 3, 2, 10, 12)
        _p(surf, x, y, sc, mn, 4, 3, 8, 10)
        _p(surf, x, y, sc, hi, 5, 3, 6, 3)
        _p(surf, x, y, sc, out, 5, 6, 2, 2)
        _p(surf, x, y, sc, out, 9, 6, 2, 2)
        _p(surf, x, y, sc, dk, 6, 10, 4, 1)
        _p(surf, x, y, sc, ac, 7, 3, 2, 2)
        return True

    if shape == "bottle":
        _p(surf, x, y, sc, out, 6, 2, 4, 4)
        _p(surf, x, y, sc, out, 4, 6, 8, 8)
        _p(surf, x, y, sc, ac, 7, 2, 2, 2)
        _p(surf, x, y, sc, dk, 7, 4, 2, 2)
        _p(surf, x, y, sc, mn, 5, 7, 6, 6)
        _p(surf, x, y, sc, hi, 6, 8, 2, 3)
        _p(surf, x, y, sc, (238, 228, 200), 6, 9, 4, 2)
        return True

    if shape == "chess":
        _p(surf, x, y, sc, out, 5, 2, 6, 4)
        _p(surf, x, y, sc, out, 6, 6, 4, 5)
        _p(surf, x, y, sc, out, 4, 11, 8, 3)
        _p(surf, x, y, sc, hi, 6, 3, 4, 2)
        _p(surf, x, y, sc, mn, 7, 5, 2, 6)
        _p(surf, x, y, sc, dk, 5, 12, 6, 1)
        _p(surf, x, y, sc, ac, 7, 3, 2, 1)
        return True

    return False