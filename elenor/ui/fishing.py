"""World-space float and compact instructions for the active fishing cast."""

import math

import pygame

from elenor.config import SCALE, TILE_H, TILE_W, VIEW_H, VIEW_W
from elenor.minigames.fishing import FINISHED
from elenor.rendering.fishing import FISH_CATALOG_SPECS


def draw_fishing(screen, game):
    renderer = game.renderer
    texts = game.loc["fishing"]
    cast = game.fishing_cast
    count = texts["count"].format(
        total=sum(game.fishing_catches.values()), kinds=len(game.fishing_catches)
    )
    world_width, world_height = VIEW_W * SCALE, VIEW_H * SCALE

    def point(x, y):
        return (
            round((x * TILE_W - game.cam_x) * SCALE),
            round((y * TILE_H - game.cam_y) * SCALE),
        )

    def label(text, font, color, position):
        image = font.render(text, True, color)
        screen.blit(image, image.get_rect(center=position))

    parchment = (242, 231, 196)
    if cast is None:
        stand = next(
            (
                obj
                for obj in game.objects
                if hasattr(obj, "fishing_spot")
                and math.hypot(obj.x + 0.5 - game.player.x, obj.y + 0.5 - game.player.y)
                <= 1.65
            ),
            None,
        )
        if stand:
            px, py = point(stand.x + 0.5, stand.y + 0.5)
            label(
                texts[stand.fishing_spot], renderer.font_title, parchment, (px, py - 78)
            )
            label(texts["stand_hint"], renderer.font_ui, parchment, (px, py - 54))
        label(count, renderer.font_ui, parchment, (world_width // 2, 24))
        return

    phase = cast.phase
    finished = phase in FINISHED
    if not finished:
        phase_time = pygame.time.get_ticks() * 0.001
        ox, oy = point(*cast.origin)
        x, y = point(*cast.target)
        wet = phase != "cast"
        if not wet:
            fraction = min(1, cast.elapsed / 0.36)
            x = round(ox + (x - ox) * fraction)
            y = round(oy + (y - oy) * fraction - 32 * math.sin(math.pi * fraction))
        elif phase == "reel":
            x = round(
                x
                + (ox - x) * cast.progress * 0.73
                + math.sin(phase_time * 8) * (9 if cast.surging else 3)
            )
            y = round(y + (oy - y) * cast.progress * 0.64)
        clip = screen.get_clip()
        screen.set_clip((0, 0, world_width, world_height))
        pygame.draw.line(screen, (83, 113, 98), (ox + 5, oy - 22), (x, y), 2)
        if wet:
            pulse = int(8 + (phase_time * (32 if cast.bob else 16)) % 20)
            pygame.draw.ellipse(
                screen,
                (113, 205, 191),
                (x - pulse, y - pulse // 3, 2 * pulse, max(4, pulse * 2 // 3)),
                2,
            )
        # The full bite submerges the red float. Keep the splash visible.
        if phase != "bite":
            float_y = y - 6 + round(cast.bob * 11)
            pygame.draw.rect(screen, (236, 238, 209), (x - 4, float_y - 7, 8, 8))
            pygame.draw.rect(screen, (224, 70, 53), (x - 5, float_y, 10, 6))
        else:
            for dx, dy in ((-10, -7), (8, -12), (13, -2)):
                pygame.draw.rect(screen, (219, 250, 231), (x + dx, y + dy, 4, 3))
        screen.set_clip(clip)

    panel = pygame.Rect(0, world_height - 154, 578, 142)
    panel.centerx = world_width // 2
    renderer.draw_pixel_frame(screen, panel, (24, 36, 32), (126, 113, 65))
    label(
        texts[cast.spot],
        renderer.font_ui,
        (169, 214, 173),
        (panel.centerx, panel.top + 19),
    )
    message = texts[phase]
    if phase == "reel":
        if cast.tension >= 0.71:
            message = texts["high_tension"]
        elif cast.surging:
            message = texts["surge"]
    if phase == "caught":
        name = FISH_CATALOG_SPECS[cast.fish_id][0].removeprefix("Улов: ")
        message = message.format(fish=name)
        fish_art = renderer.assets[cast.fish_id][0]
        screen.blit(
            pygame.transform.scale_by(fish_art, 3), (panel.left + 17, panel.top + 46)
        )
    for index, line in enumerate(
        renderer.wrap_text(message, renderer.font_title, panel.width - 112)
    ):
        label(
            line,
            renderer.font_title,
            parchment,
            (panel.centerx, panel.top + 47 + index * 23),
        )
    if phase == "reel":
        for index, (key, value, color) in enumerate(
            (
                (
                    "tension",
                    cast.tension,
                    (230, 105, 76) if cast.tension >= 0.71 else (230, 190, 108),
                ),
                ("progress", cast.progress, (115, 196, 165)),
            )
        ):
            bar_x = panel.left + 103 + index * 246
            label(
                texts[key], renderer.font_small, parchment, (bar_x + 70, panel.top + 72)
            )
            bar = pygame.Rect(bar_x, panel.top + 83, 140, 12)
            pygame.draw.rect(screen, (51, 66, 60), bar)
            pygame.draw.rect(
                screen, color, (bar.x, bar.y, round(min(1, value) * bar.w), bar.h)
            )
    label(
        texts["retry" if finished else "exit"],
        renderer.font_small,
        (179, 196, 177),
        (panel.centerx, panel.bottom - 19),
    )
    label(count, renderer.font_ui, parchment, (world_width // 2, 24))
