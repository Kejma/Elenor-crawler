"""Aim marker and a line-tension gauge that stays beside the angler."""

import math

import pygame

from elenor.config import SCALE, TILE_H, TILE_W, VIEW_H, VIEW_W
from elenor.minigames.fishing import cast_route


def _draw_tension(screen, player_x, player_y, cast):
    world_width, world_height = VIEW_W * SCALE, VIEW_H * SCALE
    gauge = pygame.Rect(0, 0, 116, 24)
    gauge.centerx = player_x
    above = cast.target[1] >= cast.origin[1]
    above_y, below_y = player_y - 108, player_y + 12
    gauge.y = above_y if above else below_y
    if gauge.top < 8:
        gauge.y = below_y
    elif gauge.bottom > world_height - 8:
        gauge.y = above_y
    gauge.clamp_ip(pygame.Rect(8, 8, world_width - 16, world_height - 16))
    pygame.draw.rect(screen, (9, 15, 17), gauge.move(2, 3), border_radius=8)
    pygame.draw.rect(screen, (27, 40, 42), gauge, border_radius=8)
    pygame.draw.rect(screen, (158, 132, 80), gauge, width=2, border_radius=8)

    hook_x, hook_y = gauge.x + 11, gauge.y + 7
    brass = (232, 200, 130)
    pygame.draw.line(screen, brass, (hook_x + 5, hook_y), (hook_x + 5, hook_y + 7), 2)
    pygame.draw.arc(screen, brass, (hook_x, hook_y + 3, 7, 9), 3.1, 6.3, 2)
    track = pygame.Rect(gauge.x + 26, gauge.y + 8, gauge.width - 35, 8)
    pygame.draw.rect(screen, (65, 74, 65), track, border_radius=3)
    color = (237, 102, 79) if cast.tension >= 0.70 else (225, 192, 111)
    fill = track.copy()
    fill.width = round(track.width * min(cast.tension, 1))
    if fill.width:
        pygame.draw.rect(screen, color, fill, border_radius=3)
    notch = track.x + round(track.width * 0.70)
    pygame.draw.line(
        screen, (248, 225, 177), (notch, track.top - 1), (notch, track.bottom)
    )


def draw_fishing(screen, game, aim, fov_mask):
    px = round((game.player.x * TILE_W - game.cam_x) * SCALE)
    py = round((game.player.y * TILE_H - game.cam_y) * SCALE)
    if game.catch_display:
        fish_id, since = game.catch_display
        elapsed = (pygame.time.get_ticks() - since) / 1000
        if elapsed < 1.4:
            art = game.renderer.assets[fish_id][0]
            angle = elapsed / 1.4 * math.tau
            # Turn around the vertical axis like a trophy suspended over the hero.
            width = max(2, round(art.get_width() * 2.5 * abs(math.cos(angle))))
            icon = pygame.transform.scale(art, (width, round(art.get_height() * 2.5)))
            if math.cos(angle) < 0:
                icon = pygame.transform.flip(icon, True, False)
            screen.blit(
                icon,
                icon.get_rect(midbottom=(px, py - 76 - round(8 * math.sin(angle / 2)))),
            )
        else:
            game.catch_display = None

    cast = game.fishing_cast
    if cast is not None:
        if cast.phase == "reel":
            _draw_tension(screen, px, py, cast)
        elif cast.phase in ("wait", "bite"):
            label = game.renderer.font_small.render(
                game.loc["fishing"]["hook_hint"], True, (241, 224, 181)
            )
            rect = label.get_rect(midbottom=(VIEW_W * SCALE // 2, VIEW_H * SCALE - 16))
            pygame.draw.rect(screen, (25, 33, 32), rect.inflate(16, 8), border_radius=5)
            screen.blit(label, rect)
        return

    if (int(game.player.x), int(game.player.y)) not in game.dungeon.fishing_edges:
        return
    if cast_route(game.dungeon, (game.player.x, game.player.y), aim) is not None:
        x = round(aim[0] * TILE_W - game.cam_x)
        y = round(aim[1] * TILE_H - game.cam_y)
        if 0 <= x < VIEW_W and 0 <= y < VIEW_H and fov_mask[x, y] > 0.3:
            pygame.draw.ellipse(
                screen, (202, 228, 184), (x * SCALE - 10, y * SCALE - 4, 20, 8), 2
            )

    message = game.loc["fishing"]["count"].format(
        total=sum(game.fishing_catches.values()), kinds=len(game.fishing_catches)
    )
    label = game.renderer.font_ui.render(message, True, (242, 231, 196))
    screen.blit(label, label.get_rect(midtop=(VIEW_W * SCALE // 2, 22)))
