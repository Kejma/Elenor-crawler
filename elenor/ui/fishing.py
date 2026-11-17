"""A cast marker, a compact tension meter and the result of a cast."""

import pygame

from elenor.config import SCALE, TILE_H, TILE_W, VIEW_H, VIEW_W
from elenor.minigames.fishing import FINISHED, cast_route
from elenor.rendering.fishing import FISH_CATALOG_SPECS


def draw_fishing(screen, game, aim, fov_mask):
    renderer = game.renderer
    texts = game.loc["fishing"]
    cast = game.fishing_cast
    center = VIEW_W * SCALE // 2
    parchment = (242, 231, 196)

    if cast is None or cast.phase in FINISHED:
        route = cast_route(game.dungeon, (game.player.x, game.player.y), aim)
        if route is not None:
            x = round(aim[0] * TILE_W - game.cam_x)
            y = round(aim[1] * TILE_H - game.cam_y)
            if 0 <= x < VIEW_W and 0 <= y < VIEW_H and fov_mask[x, y] > 0.3:
                pygame.draw.ellipse(
                    screen, (202, 228, 184), (x * SCALE - 10, y * SCALE - 4, 20, 8), 2
                )

    if cast is not None and cast.phase == "reel":
        rect = pygame.Rect(28, 24, 214, 51)
        renderer.draw_pixel_frame(screen, rect, (26, 37, 34), (136, 117, 66))
        screen.blit(
            renderer.font_small.render(texts["tension"], True, parchment),
            (rect.x + 13, rect.y + 10),
        )
        bar = pygame.Rect(rect.x + 13, rect.y + 32, rect.width - 26, 8)
        pygame.draw.rect(screen, (66, 72, 59), bar)
        color = (229, 95, 72) if cast.tension >= 0.70 else (224, 190, 101)
        pygame.draw.rect(
            screen, color, (bar.x, bar.y, round(bar.width * cast.tension), bar.height)
        )
        notch = bar.x + round(bar.width * 0.70)
        pygame.draw.line(
            screen, (251, 227, 176), (notch, bar.y - 2), (notch, bar.bottom + 1)
        )
        return

    if cast is None:
        message = texts["count"].format(
            total=sum(game.fishing_catches.values()), kinds=len(game.fishing_catches)
        )
        label = renderer.font_ui.render(message, True, parchment)
        screen.blit(label, label.get_rect(midtop=(center, 22)))
        return
    if cast.phase not in FINISHED:
        return

    message = texts[cast.phase]
    fish_art = None
    if cast.phase == "caught":
        name = FISH_CATALOG_SPECS[cast.fish_id][0].removeprefix("Улов: ")
        message = message.format(fish=name)
        fish_art = pygame.transform.scale_by(renderer.assets[cast.fish_id][0], 2)
    label = renderer.font_title.render(message, True, parchment)
    art_width = fish_art.get_width() + 10 if fish_art else 0
    rect = pygame.Rect(0, 21, label.get_width() + art_width + 42, 56)
    rect.centerx = center
    renderer.draw_pixel_frame(screen, rect, (26, 37, 34), (136, 117, 66))
    if fish_art:
        screen.blit(fish_art, fish_art.get_rect(midleft=(rect.x + 21, rect.centery)))
    screen.blit(label, label.get_rect(midleft=(rect.x + 21 + art_width, rect.centery)))
