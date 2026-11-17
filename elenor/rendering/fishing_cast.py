"""Light the fishing gear and bobber with the scene's ordinary world pass."""

import math

import pygame

from elenor.config import TILE_H, TILE_W, VIEW_H, VIEW_W
from elenor.minigames.fishing import FINISHED


def draw_fishing_cast(diffuse, normals, cast, cam_x, cam_y, now):
    if cast.phase in FINISHED:
        return

    def project(x, y):
        return round(x * TILE_W - cam_x), round(y * TILE_H - cam_y)

    ox, oy = project(*cast.origin)
    fx, fy = project(*cast.float_position)
    direction = -1 if cast.target[0] < cast.origin[0] else 1
    hand = (ox + 3 * direction, oy - 6)
    bending = round(cast.tension * 4) if cast.phase == "reel" else 0
    rod = (
        hand,
        (ox + 8 * direction, oy - 10),
        (ox + 14 * direction, oy - 12 + bending),
    )
    if cast.phase == "cast":
        fy -= round(8 * math.sin(math.pi * min(1, cast.elapsed / 0.36)))
    elif cast.phase != "bite":
        # The water-plane position follows the validated route. Only the
        # height of the float changes when it bobs or the fish tugs.
        fy += round(cast.bob * 3 + math.sin(now * 16) * (1 if cast.surging else 0.4))

    for canvas, is_normal in ((diffuse, False), (normals, True)):
        old_clip = canvas.get_clip()
        canvas.set_clip((0, 0, VIEW_W, VIEW_H))
        flat = (128, 128, 255)
        pygame.draw.lines(canvas, flat if is_normal else (165, 109, 58), False, rod)
        pygame.draw.line(
            canvas, flat if is_normal else (163, 181, 159), rod[-1], (fx, fy)
        )
        if cast.phase != "cast":
            radius = 2 + int((now * (9 if cast.surging or cast.bob else 4)) % 4)
            pygame.draw.ellipse(
                canvas,
                flat if is_normal else (150, 208, 186),
                (fx - radius, fy - 1, 2 * radius + 1, 4),
                1,
            )
        if cast.phase == "bite":
            for dx, dy in ((-3, -2), (3, -3), (4, 1)):
                pygame.draw.rect(
                    canvas,
                    flat if is_normal else (220, 250, 232),
                    (fx + dx, fy + dy, 1, 1),
                )
        else:
            pygame.draw.rect(
                canvas, flat if is_normal else (241, 236, 200), (fx - 1, fy - 3, 3, 2)
            )
            pygame.draw.rect(
                canvas, flat if is_normal else (227, 76, 52), (fx - 1, fy - 1, 3, 2)
            )
        canvas.set_clip(old_clip)
