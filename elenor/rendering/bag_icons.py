"""Pixel icons for the bag assortment."""

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


@lru_cache(maxsize=None)
def _icon(name, size):
    shade, light, accent, width = STYLES[name]
    icon = pygame.Surface((32, 32), pygame.SRCALPHA)
    left = 16 - width // 2
    right = left + width - 1
    top = 10 if name in ("bag_small", "bag_waxed") else 7
    bottom = 27
    outline = (26, 20, 25)
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
    if name in STYLES:
        surface.blit(_icon(name, size), (x, y))
