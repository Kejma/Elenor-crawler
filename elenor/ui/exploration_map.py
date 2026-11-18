"""Exploration map and HUD minimap drawn only from remembered terrain."""

import pygame

from elenor.config import SCREEN_H, SCREEN_W

PAPER = (20, 29, 26)
INK = (11, 17, 17)
BORDER = (90, 112, 91)
TEXT = (231, 224, 199)
DIM = (170, 187, 171)

TERRAIN = {
    "trail": (171, 139, 91),
    "wood": (132, 95, 66),
    "grass": (58, 100, 72),
    "trees": (32, 61, 45),
    "floor": (123, 125, 112),
    "wall": (57, 60, 62),
    "deep": (34, 66, 95),
    "water": (71, 114, 141),
    "door": (200, 151, 91),
}
MARKER_STYLE = {
    "village": ("square", (242, 180, 94)),
    "pier": ("circle", (102, 233, 222)),
    "temple": ("triangle", (228, 171, 249)),
    "cave": ("arch", (200, 207, 248)),
    "onward": ("right", (230, 231, 185)),
    "back": ("left", (230, 231, 185)),
    "up": ("up", (230, 231, 185)),
    "down": ("down", (230, 231, 185)),
    "merchant": ("circle", (247, 205, 118)),
    "player": ("diamond", (253, 246, 212)),
}


def chart_surface(dungeon, region=None):
    """One pixel per known tile. The world grid is deliberately absent here."""
    surface = pygame.Surface((dungeon.width, dungeon.height) if region is None else region.size)
    surface.fill(INK)
    if region is None:
        for point, kind in dungeon.explored_tiles.items():
            surface.set_at(point, TERRAIN[kind])
    else:
        for y in range(region.height):
            for x in range(region.width):
                kind = dungeon.explored_tiles.get((region.x + x, region.y + y))
                if kind is not None:
                    surface.set_at((x, y), TERRAIN[kind])
    return surface


def discovered_landmarks(dungeon):
    for position, kind in (dungeon.map_landmarks | dungeon.passages).items():
        if kind in MARKER_STYLE and position in dungeon.explored_tiles:
            yield position, kind


def draw_marker(screen, kind, point, radius=8):
    x, y = point
    shape, color = MARKER_STYLE[kind]
    pygame.draw.circle(screen, INK, point, radius + 3)
    if shape == "diamond":
        pygame.draw.polygon(
            screen,
            color,
            [(x, y - radius), (x + radius, y), (x, y + radius), (x - radius, y)],
        )
    elif shape == "square":
        pygame.draw.rect(
            screen,
            color,
            (x - radius + 2, y - radius + 2, 2 * radius - 3, 2 * radius - 3),
            3,
        )
    elif shape == "arch":
        pygame.draw.arc(
            screen,
            color,
            (x - radius, y - radius + 1, 2 * radius, 2 * radius),
            0,
            3.15,
            3,
        )
        pygame.draw.line(
            screen, color, (x - radius + 1, y + 2), (x + radius - 2, y + 2), 3
        )
    elif shape == "circle":
        pygame.draw.circle(screen, color, point, radius - 2, 3)
    elif shape == "triangle":
        pygame.draw.polygon(
            screen,
            color,
            [
                (x, y - radius + 1),
                (x + radius - 1, y + radius - 2),
                (x - radius + 1, y + radius - 2),
            ],
            3,
        )
    else:
        tip, upper, lower = {
            "right": (
                (x + radius, y),
                (x - 3, y - radius + 1),
                (x - 3, y + radius - 1),
            ),
            "left": ((x - radius, y), (x + 3, y - radius + 1), (x + 3, y + radius - 1)),
            "up": ((x, y - radius), (x - radius + 1, y + 3), (x + radius - 1, y + 3)),
            "down": ((x, y + radius), (x - radius + 1, y - 3), (x + radius - 1, y - 3)),
        }[shape]
        pygame.draw.polygon(screen, color, [tip, upper, lower])


def draw_map_hud(screen, game):
    labels = game.loc["exploration_map"]
    font = game.renderer.font_small
    hint = font.render(labels["hint"], True, TEXT)
    if not game.profile["show_minimap"]:
        rect = hint.get_rect(topleft=(31, 24))
        pygame.draw.rect(screen, PAPER, rect.inflate(22, 12), border_radius=4)
        screen.blit(hint, rect)
        return

    tile_size = 7
    region = pygame.Rect(0, 0, 29, 21)
    region.center = (int(game.player.x), int(game.player.y))
    viewport = pygame.Rect(30, 47, region.width * tile_size, region.height * tile_size)
    panel = pygame.Rect(20, 16, viewport.width + 20, viewport.height + 41)
    pygame.draw.rect(screen, PAPER, panel, border_radius=5)
    pygame.draw.rect(screen, BORDER, panel, width=1, border_radius=5)
    screen.blit(hint, hint.get_rect(midleft=(viewport.left, 32)))
    north = font.render(labels["north"], True, DIM)
    screen.blit(north, north.get_rect(midright=(viewport.right, 32)))
    chart = chart_surface(game.dungeon, region)
    screen.blit(pygame.transform.scale(chart, viewport.size), viewport)

    def pixel(x, y):
        return (
            viewport.x + round((x - region.x) * tile_size),
            viewport.y + round((y - region.y) * tile_size),
        )

    original_clip = screen.get_clip()
    screen.set_clip(original_clip.clip(viewport))
    for (x, y), kind in discovered_landmarks(game.dungeon):
        if region.collidepoint(x, y):
            draw_marker(screen, kind, pixel(x + 0.5, y + 0.5), 5)
    draw_marker(screen, "player", pixel(game.player.x, game.player.y), 6)
    screen.set_clip(original_clip)


def draw_map(screen, game, chart, mouse_pos):
    dungeon = game.dungeon
    renderer = game.renderer
    labels = game.loc["exploration_map"]
    screen.fill(PAPER)

    if game.campaign == "jungle":
        heading = labels[dungeon.interior or "valley"].format(number=dungeon.floor_num)
    else:
        heading = labels["tavern"] if dungeon.floor_num == 1 else labels["floor"].format(number=dungeon.floor_num)
    screen.blit(renderer.font_ui.render(labels["title"], True, DIM), (70, 43))
    screen.blit(renderer.font_title.render(heading, True, TEXT), (70, 71))
    close = renderer.font_ui.render(labels["close"], True, DIM)
    screen.blit(close, close.get_rect(topright=(SCREEN_W - 71, 85)))

    viewport = pygame.Rect(70, 147, SCREEN_W - 470, SCREEN_H - 207)
    legend = pygame.Rect(viewport.right + 28, viewport.top, 320, viewport.height)
    pygame.draw.rect(screen, INK, viewport)
    pygame.draw.rect(screen, BORDER, viewport, 2)
    pygame.draw.line(screen, BORDER, legend.topleft, legend.bottomleft, width=2)
    tile_size = max(
        1,
        min(
            (viewport.width - 36) // chart.get_width(),
            (viewport.height - 36) // chart.get_height(),
        ),
    )
    map_rect = pygame.Rect(
        0, 0, chart.get_width() * tile_size, chart.get_height() * tile_size
    )
    map_rect.center = viewport.center
    screen.blit(pygame.transform.scale(chart, map_rect.size), map_rect)
    north = renderer.font_ui.render(labels["north"], True, TEXT)
    screen.blit(north, north.get_rect(midtop=(viewport.right - 24, viewport.top + 13)))
    pygame.draw.line(
        screen,
        DIM,
        (viewport.right - 24, viewport.top + 36),
        (viewport.right - 24, viewport.top + 53),
        2,
    )

    def pixel(point):
        return (
            round(map_rect.x + point[0] * tile_size),
            round(map_rect.y + point[1] * tile_size),
        )

    marker_hitboxes = []
    for (x, y), kind in discovered_landmarks(dungeon):
        marker_pos = pixel((x + 0.5, y + 0.5))
        draw_marker(screen, kind, marker_pos)
        marker_hitboxes.append((marker_pos, kind))
    player_pos = pixel((game.player.x, game.player.y))
    draw_marker(screen, "player", player_pos, 10)
    marker_hitboxes.append((player_pos, "player"))
    hovered = min(
        marker_hitboxes,
        key=lambda item: pygame.Vector2(item[0]).distance_squared_to(mouse_pos),
    )
    if (
        viewport.collidepoint(mouse_pos)
        and pygame.Vector2(hovered[0]).distance_squared_to(mouse_pos) <= 14**2
    ):
        point, kind = hovered
        tip = renderer.font_ui.render(labels["markers"][kind], True, TEXT)
        rect = tip.get_rect(midbottom=(point[0], point[1] - 15)).inflate(22, 14)
        rect.clamp_ip(viewport.inflate(-10, -10))
        pygame.draw.rect(screen, PAPER, rect)
        pygame.draw.rect(screen, BORDER, rect, 1)
        screen.blit(tip, tip.get_rect(center=rect.center))

    x, y = legend.x + 24, legend.y + 18
    screen.blit(renderer.font_ui.render(labels["terrain"], True, DIM), (x, y))
    y += 43
    for kind in (
        "trail",
        "wood",
        "grass",
        "trees",
        "water",
        "deep",
        "floor",
        "wall",
        "door",
    ):
        pygame.draw.rect(screen, TERRAIN[kind], (x, y + 1, 17, 17))
        screen.blit(
            renderer.font_ui.render(labels["tiles"][kind], True, TEXT), (x + 30, y)
        )
        y += 34
    y += 24
    screen.blit(renderer.font_ui.render(labels["landmarks"], True, DIM), (x, y))
    y += 43
    for kind in ("player", *(kind for kind in MARKER_STYLE if kind != "player")):
        if kind == "player" or any(marker == kind for _, marker in marker_hitboxes):
            draw_marker(screen, kind, (x + 8, y + 9))
            screen.blit(
                renderer.font_ui.render(labels["markers"][kind], True, TEXT),
                (x + 30, y),
            )
            y += 34
