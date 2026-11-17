"""Semantic pixel glyphs for active skills; cached at each requested size."""

import math
import pygame

CACHE = {}


def draw_ability_icon(surface, name, x, y, size):
    if not name.startswith("ability_"):
        return False
    key = name, size
    if key not in CACHE:
        icon = pygame.Surface((32, 32), pygame.SRCALPHA)
        glyph = name[8:]
        warm, cold, green, white = (
            (245, 155, 65),
            (100, 215, 255),
            (100, 225, 135),
            (240, 235, 215),
        )

        def line(col, pts, w=2):
            pygame.draw.lines(icon, col, False, pts, w)

        def ring(col, r):
            pygame.draw.circle(icon, col, (16, 16), r, 2)

        def blade(a, b, col=white):
            line((145, 105, 65), [(a[0] - 2, a[1] + 2), a], 3)
            line(col, [a, b], 3)
            pygame.draw.polygon(
                icon,
                col,
                [(b[0] - 3, b[1] + 1), (b[0] + 1, b[1] - 3), (b[0] + 2, b[1] + 2)],
            )

        if glyph == "hamstring":
            line(white,[(12,4),(12,19),(24,24)],5)
            line(green,[(5,27),(26,27),(21,22)],2)
        elif glyph == "fan_blades":
            pygame.draw.arc(icon,white,(3,9,26,15),0,math.pi,2)
            for px in (5,10,15,20,25):line(white,[(px,17),(px,11)],2)
        elif glyph == "venom_strike":
            pygame.draw.polygon(icon,(100,140,195),[(16,3),(6,10),(3,28),(29,28),(26,10)],2)
            line(white,[(11,13),(14,13)]);line(white,[(18,13),(21,13)])
        elif glyph == "piercing_shot":
            blade((8,25),(23,5))
            line((235,90,80),[(4,7),(10,7),(7,4),(7,11)])
        elif glyph in ("firebolt", "ignite"):
            pygame.draw.polygon(
                icon,
                warm,
                [(10, 26), (6, 18), (13, 10), (15, 3), (22, 13), (25, 20), (21, 27)],
            )
            pygame.draw.polygon(
                icon, (255, 235, 125), [(12, 25), (12, 18), (18, 13), (21, 25)]
            )
            if glyph == "ignite":
                ring((255, 85, 40), 14)
            else:
                line(warm, [(3, 27), (7, 23)])
                line(warm, [(2, 19), (6, 17)])
        elif glyph == "frost":
            for a in range(0, 360, 60):
                dx, dy = math.cos(math.radians(a)), math.sin(math.radians(a))
                line(cold, [(16, 16), (16 + 12 * dx, 16 + 12 * dy)])
                for sign in (-1, 1):
                    line(
                        cold,
                        [
                            (
                                16 + 8 * dx - sign * 3 * dy - 3 * dx,
                                16 + 8 * dy + sign * 3 * dx - 3 * dy,
                            ),
                            (16 + 8 * dx, 16 + 8 * dy),
                        ],
                    )
        elif glyph == "lightning":
            pygame.draw.polygon(
                icon, cold, [(19, 2), (7, 18), (15, 18), (11, 30), (26, 12), (18, 12)]
            )
        elif glyph == "renewal":
            line(green, [(16, 7), (16, 25)], 5)
            line(green, [(7, 16), (25, 16)], 5)
            pygame.draw.arc(icon, green, (2, 2, 28, 28), 0.2, 4.5, 2)
        elif glyph == "roots":
            line(green, [(16, 3), (16, 19), (8, 28)])
            line(green, [(16, 19), (24, 28)])
            line(green, [(16, 13), (6, 9), (9, 5)])
            line(green, [(16, 10), (25, 5)])
        elif glyph in ("whirlwind", "war_stomp"):
            for r in (7, 12):
                pygame.draw.arc(icon, warm, (16 - r, 16 - r, r * 2, r * 2), 0.3, 5.5, 2)
            if glyph == "whirlwind":
                blade((10, 20), (22, 8))
            else:
                pygame.draw.rect(icon, white, (12, 8, 7, 14))
                pygame.draw.rect(icon, white, (12, 20, 12, 5))
        elif glyph in ("earth_slam", "heavy_strike", "shield_bash", "cleave"):
            if glyph == "shield_bash":
                pygame.draw.polygon(
                    icon, warm, [(7, 5), (25, 5), (24, 20), (16, 28), (8, 20)], 3
                )
            elif glyph == "cleave":
                blade((8, 25), (23, 8))
                pygame.draw.arc(icon, warm, (3, 3, 26, 26), 0.1, 2, 3)
            else:
                line(warm, [(8, 26), (20, 10)], 4)
                pygame.draw.polygon(
                    icon, white, [(13, 5), (20, 3), (28, 11), (22, 18)], 0
                )
                if glyph == "earth_slam":
                    line(warm, [(3, 28), (10, 25), (16, 29), (23, 25), (30, 28)])
        elif glyph in ("throw_knife", "piercing_shot", "fan_blades"):
            blade((9, 24), (22, 8), green)
            if glyph == "fan_blades":
                blade((6, 21), (5, 7))
                blade((14, 26), (28, 20))
            elif glyph == "piercing_shot":
                line(green, [(2, 26), (29, 3)])
                line(green, [(22, 3), (29, 3), (29, 10)])
            else:
                line(green, [(2, 22), (7, 18)])
                line(green, [(5, 29), (10, 24)])
        elif glyph == "poison_flask":
            pygame.draw.circle(icon, green, (16, 21), 9, 2)
            pygame.draw.rect(icon, green, (12, 5, 8, 10), 2)
            pygame.draw.line(icon, white, (11, 4), (21, 4), 3)
            pygame.draw.circle(icon, green, (16, 23), 4)
        elif glyph == "hamstring":
            line(white, [(19, 3), (12, 15), (21, 28)], 4)
            line(green, [(4, 18), (27, 12)], 3)
        elif glyph == "venom_strike":
            blade((6, 26), (21, 6))
            pygame.draw.polygon(icon, green, [(25, 16), (21, 24), (25, 29), (29, 24)])
        CACHE[key] = pygame.transform.scale(icon, (size, size))
    surface.blit(CACHE[key], (x, y))
    return True
