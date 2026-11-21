"""Pixel icons for general bags, gem pouches, potion belts, and the family strongbox."""

from functools import lru_cache

import pygame


# Fabric shadow, fabric light, stitching/accent, silhouette width.
STYLES = {
    "bag_small": ((112, 72, 51), (181, 130, 85), (243, 203, 133), 15),
    "bag_waxed": ((58, 91, 80), (100, 150, 114), (228, 189, 112), 16),
    "bag_leather": ((111, 52, 39), (176, 99, 64), (237, 167, 101), 18),
    "bag_reed": ((95, 76, 40), (169, 145, 82), (218, 214, 136), 20),
    "bag_scout": ((58, 72, 106), (107, 133, 171), (218, 214, 190), 19),
    "bag_frame": ((117, 59, 51), (178, 105, 87), (225, 183, 122), 21),
    "bag_big": ((91, 55, 102), (154, 96, 159), (245, 189, 140), 22),
    "bag_void": ((48, 42, 99), (93, 78, 159), (255, 207, 114), 23),
}

# Ювелирные сумки: (тень, свет, золото, цвет камня)
GEM_STYLES = {
    "bag_gem_velvet":  ((105, 34, 48),  (168, 56, 72),   (232, 188, 78),  (95, 230, 145)),
    "bag_gem_satchel": ((42, 78, 66),   (72, 128, 106),  (236, 194, 82),  (85, 195, 250)),
    "bag_gem_case":    ((62, 48, 96),   (104, 82, 156),  (242, 202, 88),  (250, 165, 58)),
    "bag_gem_trunk":   ((112, 62, 36),  (168, 96, 54),   (248, 210, 96),  (235, 62, 82)),
    "bag_gem_vault":   ((38, 34, 62),   (74, 66, 118),   (255, 224, 115), (195, 95, 255)),
}

# Пояса для зелий: (кожа, пряжка, цвета склянок)
BELT_STYLES = {
    "bag_belt_herb":   ((118, 82, 48),  (198, 158, 72), ((215, 62, 68), (85, 195, 92))),
    "bag_belt_alch":   ((92, 62, 46),   (218, 178, 76), ((215, 62, 68), (62, 152, 242), (92, 215, 112))),
    "bag_belt_apoth":  ((68, 54, 72),   (230, 190, 82), ((225, 68, 74), (68, 165, 248), (242, 182, 58), (112, 232, 118))),
    "bag_belt_master": ((54, 38, 62),   (252, 212, 98), ((235, 72, 82), (76, 178, 255), (188, 92, 252), (248, 196, 68))),
}


@lru_cache(maxsize=None)
def _icon(name, size):
    icon = pygame.Surface((32, 32), pygame.SRCALPHA)
    outline = (24, 18, 26)

    if name == "bag_strongbox":
        pygame.draw.rect(icon, outline, (4, 7, 24, 19), border_radius=3)
        pygame.draw.rect(icon, (92, 52, 34), (6, 9, 20, 15), border_radius=2)
        pygame.draw.rect(icon, (134, 78, 48), (6, 9, 20, 6), border_radius=2)
        pygame.draw.rect(icon, (226, 182, 64), (5, 8, 22, 17), 2, border_radius=2)
        pygame.draw.line(icon, (248, 216, 110), (6, 15), (25, 15), 2)
        pygame.draw.rect(icon, outline, (13, 13, 6, 7))
        pygame.draw.rect(icon, (252, 218, 108), (14, 14, 4, 5))
        pygame.draw.rect(icon, outline, (15, 16, 2, 2))
        return pygame.transform.scale(icon, (size, size))

    if name in GEM_STYLES:
        shade, light, gold, gem = GEM_STYLES[name]
        pygame.draw.rect(icon, outline, (11, 4, 10, 6), 2, border_radius=2)
        pygame.draw.line(icon, gold, (12, 6), (19, 6), 2)
        body = [(6, 25), (5, 14), (9, 9), (23, 9), (27, 14), (26, 25), (22, 28), (10, 28)]
        pygame.draw.polygon(icon, outline, body)
        inner = [(x + (1 if x < 16 else -1), y + (1 if y < 18 else -1)) for x, y in body]
        pygame.draw.polygon(icon, shade, inner)
        pygame.draw.polygon(icon, light, [(7, 14), (10, 10), (22, 10), (25, 14), (22, 18), (10, 18)])
        pygame.draw.line(icon, gold, (9, 10), (23, 10), 2)
        pygame.draw.polygon(icon, outline, [(16, 15), (21, 20), (16, 25), (11, 20)])
        pygame.draw.polygon(icon, gem, [(16, 16), (20, 20), (16, 24), (12, 20)])
        pygame.draw.polygon(icon, (245, 252, 255), [(16, 17), (18, 19), (16, 21), (14, 19)])
        return pygame.transform.scale(icon, (size, size))

    if name in BELT_STYLES:
        leather, buckle, vials = BELT_STYLES[name]
        pygame.draw.rect(icon, outline, (2, 12, 28, 9), border_radius=2)
        pygame.draw.rect(icon, leather, (4, 14, 24, 5))
        pygame.draw.rect(icon, buckle, (13, 13, 6, 7), 2)
        n = len(vials)
        xs = [9, 21] if n == 2 else ([7, 16, 25] if n == 3 else [6, 12, 20, 26])
        for vx, col in zip(xs, vials):
            pygame.draw.rect(icon, outline, (vx - 3, 7, 6, 16), border_radius=2)
            pygame.draw.rect(icon, (195, 168, 118), (vx - 1, 8, 2, 3))
            pygame.draw.rect(icon, col, (vx - 2, 11, 4, 10))
            pygame.draw.rect(icon, (245, 250, 255), (vx - 2, 12, 1, 4))
            pygame.draw.line(icon, leather, (vx - 3, 16), (vx + 2, 16), 2)
        return pygame.transform.scale(icon, (size, size))

    shade, light, accent, width = STYLES[name]
    left = 16 - width // 2
    right = left + width - 1
    top = 10 if name in ("bag_small", "bag_waxed") else 7
    bottom = 27
    body = [(left, bottom - 3), (left, top + 7), (left + 3, top + 2),
            (right - 3, top + 2), (right, top + 7), (right, bottom - 3),
            (right - 3, bottom), (left + 3, bottom)]

    pygame.draw.rect(icon, outline, (12, top - 4, 8, 8), 2, border_radius=2)
    pygame.draw.line(icon, light, (13, top - 3), (18, top - 3))
    if name == "bag_frame":
        pygame.draw.line(icon, accent, (left - 2, 5), (left - 2, 29), 2)
        pygame.draw.line(icon, accent, (right + 2, 5), (right + 2, 29), 2)
    pygame.draw.polygon(icon, outline, body)
    inner = [(x + (1 if x < 16 else -1), y + (1 if y < 17 else -1)) for x, y in body]
    pygame.draw.polygon(icon, shade, inner)
    flap = [(left + 1, top + 6), (left + 4, top + 2), (right - 4, top + 2),
            (right - 1, top + 6), (right - 3, top + 11), (left + 3, top + 11)]
    pygame.draw.polygon(icon, light, flap)
    pygame.draw.line(icon, accent, (left + 4, top + 3), (right - 5, top + 3))
    if name == "bag_reed":
        for y in range(top + 13, bottom - 1, 2):
            for x in range(left + 3 + y % 3, right - 2, 3):
                icon.set_at((x, y), accent)
    elif name == "bag_void":
        pygame.draw.polygon(icon, accent, [(16, 16), (20, 21), (16, 26), (12, 21)], 1)
        pygame.draw.polygon(icon, (220, 197, 255), [(16, 18), (18, 21), (16, 24), (14, 21)])
    else:
        for x in (left + 3, right - 3):
            pygame.draw.line(icon, light, (x, top + 12), (x, bottom - 3))
        pygame.draw.rect(icon, outline, (13, top + 8, 6, 5))
        pygame.draw.rect(icon, accent, (14, top + 9, 4, 2))
    return pygame.transform.scale(icon, (size, size))


def draw_bag_icon(surface, name, x, y, size):
    if name in STYLES or name in GEM_STYLES or name in BELT_STYLES or name == "bag_strongbox":
        surface.blit(_icon(name, size), (x, y))