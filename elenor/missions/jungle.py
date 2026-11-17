"""Campaign II's first playable location, a fishing stretch on the river."""

import math
import random

import pygame

from elenor.config import MAP_COLS, MAP_ROWS

SHALLOW_WATER, DEEP_WATER, PIER, PEBBLE_SHORE = range(37, 41)
FISHING_STAND = "prop_fishing_rod_stand"
SPOTS = ((13, "eddy"), (32, "snag"), (51, "current"))


def shoreline(x):
    return 17 + round(1.6 * math.sin(x / 7) + 1.1 * math.sin(x / 3.7))


def generate_jungle_bank(dungeon):
    # Called after Dungeon has reset all floor-owned state.
    rng = random.Random(206)
    dungeon.ambient_light = (0.76, 0.80, 0.69)
    dungeon.grid = []
    for y in range(MAP_ROWS):
        row = []
        for x in range(MAP_COLS):
            bank = shoreline(x)
            if x in (0, MAP_COLS - 1) or y in (0, MAP_ROWS - 1):
                tile = 17
            elif y >= bank + 3:
                tile = DEEP_WATER
            elif y >= bank:
                tile = SHALLOW_WATER
                if rng.random() < 0.18:
                    dungeon.overlays[x, y] = rng.choice(
                        ("ov_water_lily", "ov_duckweed", "ov_fish_shadows")
                    )
            elif y >= bank - 2:
                tile = PEBBLE_SHORE if rng.random() < 0.45 else 25
            elif y < 7 or (y < bank - 4 and rng.random() < 0.29):
                tile = rng.choice((21, 21, 22))
            else:
                tile = rng.choice((10, 10, 12, 11))
                if rng.random() < 0.23:
                    dungeon.overlays[x, y] = rng.choice(
                        ("ov_fern", "ov_flowers_red", "ov_bamboo_leaves")
                    )
            row.append(tile)
        dungeon.grid.append(row)

    # A continuous footpath joins the three clearings.
    for x in range(1, MAP_COLS - 1):
        bank = shoreline(x)
        dungeon.grid[bank - 3][x] = 12
        dungeon.grid[bank - 4][x] = 12
    for x, _ in SPOTS:
        bank = shoreline(x)
        for y in range(bank - 1, bank + 2):
            for tx in (x - 1, x, x + 1):
                dungeon.grid[y][tx] = PIER
                dungeon.overlays.pop((tx, y), None)
        dungeon.overlays[x, bank + 2] = "ov_bobber_ripples"

    # Readably distinct water around the three approaches.
    for x, y_offset in ((10, 1), (11, 2), (15, 1), (16, 2), (17, 0)):
        dungeon.overlays[x, shoreline(x) + y_offset] = "ov_water_lily"
    for x in range(48, 57):
        if 50 <= x <= 52:
            continue
        dungeon.overlays[x, shoreline(x) + 1] = "ov_shore_foam"

    first_x = SPOTS[0][0]
    dungeon.start_pos = first_x, shoreline(first_x) - 2
    dungeon.rooms = [pygame.Rect(1, 7, MAP_COLS - 2, 14)]


def populate_jungle_bank(game, Interactable):
    for x, spot in SPOTS:
        bank = shoreline(x)
        stand = Interactable(x, bank, FISHING_STAND)
        stand.fishing_spot = spot
        stand.fishing_target = x + 0.5, bank + 2.7
        game.objects.append(stand)
        for tx, ty, kind in (
            (x - 1, bank - 1, "prop_bait_bucket"),
            (x + 1, bank - 1, "prop_fisherman_stool"),
            (x - 2, bank, "prop_reeds_tall"),
            (x + 2, bank, "prop_reeds_tall"),
        ):
            game.objects.append(Interactable(tx, ty, kind))
    game.objects.append(Interactable(34, shoreline(34) + 1, "hollow_log"))
    game.objects.append(Interactable(11, shoreline(11) + 1, "prop_wooden_rowboat"))
    for x, y, kind in (
        (8, 11, "banana_plant"),
        (17, 9, "giant_fern"),
        (24, 11, "bamboo_clump"),
        (41, 9, "jungle_bush_flowers"),
        (47, 11, "prop_fish_drying_line"),
        (55, 12, "prop_tackle_box"),
    ):
        if not game.dungeon.is_blocking_move(x, y):
            game.objects.append(Interactable(x, y, kind))
