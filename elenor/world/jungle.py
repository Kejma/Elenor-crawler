"""Connected night-jungle clearings, river landings and optional temple vaults."""

import math
import random
from collections import deque

import pygame

from elenor.config import (
    DEEP_WATER,
    MAP_COLS,
    MAP_ROWS,
    PEBBLE_SHORE,
    PIER,
    SHALLOW_WATER,
)
from elenor.world.dungeon import Door

# Interior ground, surrounding terrain, furnishings and ground cover.
BIOMES = {
    "grove": (10, 21, ("giant_fern", "banana_plant"), "ov_fern"),
    "marsh": (23, 22, ("hollow_log", "bamboo_clump"), "ov_mangrove_roots"),
    "bone": (45, 56, ("bone_totem_altar", "blood_thorn_bush"), "ov_ribcage_remains"),
    "hut": (13, 33, ("tribal_bed", "tribal_table"), "ov_bamboo_leaves"),
    "temple": (14, 20, ("marble_pillar", "marble_pillar"), "ov_marble_cracks"),
    "cave": (49, 34, ("amethyst_geode", "giant_cave_mushroom"), "ov_glow_shrooms"),
}


def _trail(dungeon, start, end, horizontal):
    """Join neighbouring clearings with a two-tile trail and a bend in the gap."""
    x, y = start
    ex, ey = end
    if horizontal:
        mid = (x + ex) // 2
        bends = [(mid, y), (mid, ey), end]
    else:
        mid = (y + ey) // 2
        bends = [(x, mid), (ex, mid), end]
    for bx, by in bends:
        dungeon._carve_rect(
            pygame.Rect(min(x, bx), min(y, by), abs(bx - x) + 2, abs(by - y) + 2), 12
        )
        x, y = bx, by


def _clearing(dungeon, room, biome):
    floor, wall, props, overlay = BIOMES[biome]
    if biome == "hut" and random.choice((True, False)):
        props = ("tribal_hammock", "tribal_bow_stand")
    elif biome == "cave" and random.choice((True, False)):
        floor, props = 50, ("crystal_cluster", "minecart_wreck")
    elif biome == "temple" and random.choice((True, False)):
        floor, props = 30, ("marble_pillar_broken", "serpent_statue")
    elif biome == "bone" and random.choice((True, False)):
        floor, props = 46, ("bone_wind_chimes", "spine_pillar")
    building = biome in ("hut", "temple")
    cx, cy = room.center
    for y in range(room.top, room.bottom):
        for x in range(room.left, room.right):
            rim = x in (room.left, room.right - 1) or y in (room.top, room.bottom - 1)
            distance = ((x - cx) / (room.w / 2)) ** 2 + ((y - cy) / (room.h / 2)) ** 2
            if (building and rim) or (not building and distance > 1):
                if dungeon.grid[y][x] != 12:
                    dungeon.grid[y][x] = wall
            elif biome == "hut" and abs(x - cx) <= 2 and abs(y - cy) <= 1:
                dungeon.grid[y][x] = 27
            elif biome == "temple" and (x == cx or y == cy):
                dungeon.grid[y][x] = 16
            else:
                dungeon.grid[y][x] = floor
                if random.random() < 0.12:
                    dungeon.overlays[x, y] = overlay
    for xy, kind in zip([(cx - 2, cy - 2), (cx + 2, cy + 2)], props):
        dungeon.jungle_props.append((*xy, kind))
    if biome == "cave":
        dungeon.room_lights.append(
            dict(x=cx - 2, y=cy - 2, color=(0.51, 0.52, 1.1), radius=92)
        )
    else:
        _brazier(dungeon, cx + 2, cy - 2)
    if biome in ("grove", "marsh"):
        dungeon.atmo_zones.append(dict(rect=room, kind="forest"))


def _brazier(dungeon, x, y, radius=98):
    dungeon.braziers.append(dict(x=x, y=y, radius=radius, color=(1.15, 0.78, 0.44)))


def _waterfront(dungeon, near_rooms, direction):
    river = random.choice((True, False))
    docks = random.sample(near_rooms, 2 if river else 1)
    center = docks[0].centerx
    radius = min(random.randint(11, 17), center - 1, MAP_COLS - 2 - center)
    phase = random.uniform(0, math.tau)
    banks = {}
    for x in range(1, MAP_COLS - 1):
        if river:
            inset = 10 + round(1.4 * math.sin(x / 8 + phase))
            width = 7 + round(math.sin(x / 6 + phase))
        else:
            shape = 1 - ((x - center) / radius) ** 2
            if shape <= 0:
                continue
            half = max(1, round(4 * math.sqrt(shape)))
            inset, width = 5 + half, half * 2 - 1
        bank = MAP_ROWS - 1 - inset if direction == 1 else inset
        banks[x] = bank
        for depth in range(-1, width):
            y = bank + depth * direction
            if not 0 < y < MAP_ROWS - 1:
                continue
            tile = PEBBLE_SHORE if depth == -1 else SHALLOW_WATER
            if 2 <= depth < width - 1:
                tile = DEEP_WATER
            dungeon.grid[y][x] = tile
            if depth == 0 and random.random() < 0.24:
                dungeon.overlays[x, y] = random.choice(("ov_water_lily", "ov_duckweed"))
    if river:
        # A separate crossing leads to a small fishing camp on the other bank.
        bridge_room = next(room for room in near_rooms if room not in docks)
        x, cy = bridge_room.center
        bank = banks[x]
        landing = MAP_ROWS - 3 if direction == 1 else 2
        _trail(dungeon, (x, cy), (x, bank - direction), False)
        for y in range(bank, landing, direction):
            dungeon.grid[y][x : x + 2] = [PIER, PIER]
            dungeon.overlays.pop((x, y), None)
            dungeon.overlays.pop((x + 1, y), None)
        dungeon._carve_rect(pygame.Rect(x - 3, landing - 1, 8, 3), PEBBLE_SHORE)
        dungeon.jungle_props.extend(
            [
                (x - 2, landing, "prop_fish_drying_line"),
                (x + 2, landing, "prop_bait_bucket"),
                (x + 3, landing, "chest"),
            ]
        )
        _brazier(dungeon, x - 1, landing)
    spots = random.sample(["snag", "eddy", "current"], len(docks))
    for room, spot in zip(docks, spots):
        x, cy = room.center
        bank = banks[x]
        _trail(dungeon, (x, cy), (x, bank - direction), False)
        for dx in (0, 1):
            for depth in (-1, 0, 1):
                y = bank + depth * direction
                dungeon.grid[y][x + dx] = PIER
                dungeon.overlays.pop((x + dx, y), None)
            dungeon.fishing_edges[x + dx, bank + direction] = spot
        # Leave a wadeable lip in front of both planks, including curved banks.
        for dx in (0, 1):
            dungeon.grid[bank + 2 * direction][x + dx] = SHALLOW_WATER
        dungeon.jungle_props.extend(
            [
                (x + 1, bank, "prop_fishing_rod_stand"),
                (x - 2, bank, "prop_reeds_tall"),
                (x - 2, bank + direction, "prop_wooden_rowboat"),
            ]
        )
        _brazier(dungeon, x + 1, bank - direction, 142)


def _mirror_shrine(dungeon, room, approach):
    cx, cy = room.center
    hall = pygame.Rect(cx - 7, cy - 4, 11, 9)
    vault = pygame.Rect(hall.right + 1, cy - 2, 4, 5)
    entry = (hall.centerx, hall.bottom if approach[1] > cy else hall.top - 1)
    gate = (hall.right, cy)
    _trail(dungeon, approach, entry, False)
    dungeon._carve_rect(hall.union(vault).inflate(2, 2), 19)
    dungeon._carve_rect(hall, 14)
    dungeon._carve_rect(vault, 30)
    for x, y in (entry, gate):
        dungeon.grid[y][x] = 14
    dungeon.doors[gate] = Door(*gate, locked_by_lever=True)
    dungeon.mirror_puzzle_info = dict(
        puzzle_rect=hall,
        sealed_rect=vault,
        entry_door=entry,
        gate_door=gate,
        tutorial=False,
        tiles=(19, 14),
    )
    dungeon.jungle_props.append((*vault.center, "chest"))
    dungeon.rooms.extend([hall, vault])


def generate_jungle_floor(dungeon):
    dungeon.jungle_props = []
    # The waterfront can lie on either side. Regions vary independently of the trails.
    direction = random.choice((-1, 1))
    rooms = []
    for band in (8, 22):
        for column in (11, 32, 53):
            room = pygame.Rect(
                0, 0, random.randrange(9, 16, 2), random.choice((7, 9, 11))
            )
            y = band + random.randint(-1, 1)
            room.center = (
                column + random.randint(-2, 2),
                y if direction == 1 else MAP_ROWS - 1 - y,
            )
            rooms.append(room)

    shrine = random.randrange(3) if random.random() < dungeon.puzzle_chance else None
    ordinary = [i for i in range(6) if i != shrine]
    themes = ["hut", "cave", "bone", "marsh", "grove"]
    if shrine is None:
        themes.append("temple")
    random.shuffle(themes)
    region = dict(zip(ordinary, themes))
    # Extend each landmark's vegetation beyond its clearing. Warping the
    # nearest-centre boundaries avoids straight biome borders along trails.
    phase = random.uniform(0, math.tau)
    dungeon.grid = []
    for y in range(MAP_ROWS):
        row = []
        for x in range(MAP_COLS):
            wx = x + 2.4 * math.sin(y / 4 + phase)
            wy = y + 2.0 * math.cos(x / 5 - phase)
            nearest = min(
                range(len(rooms)),
                key=lambda i: (
                    (rooms[i].centerx - wx) ** 2 + (rooms[i].centery - wy) ** 2
                ),
            )
            growth = math.sin(x / 4 + phase) + math.cos(y / 3 - phase)
            biome = region.get(nearest, "temple")
            if biome == "bone":
                tile = 57 if growth > 0.5 else 56
            elif biome == "cave":
                tile = 54 if growth > 0.8 else 34
            else:
                tile = 17 if growth < -0.7 else (22 if biome == "marsh" else 21)
            # Gaps between stands of trees give the player small explorable
            # pockets beside trails. Keep the outer map boundary closed.
            if 0 < x < MAP_COLS - 1 and 0 < y < MAP_ROWS - 1:
                clearing = growth + 0.65 * math.sin(x * 1.7 + y * 2.3 + phase)
                if clearing > 0.65:
                    tile = (
                        BIOMES[biome][0] if biome in ("bone", "marsh", "cave") else 10
                    )
            row.append(tile)
        dungeon.grid.append(row)
    start = random.choice(ordinary)
    # Grow a spanning tree, then add a shortcut when the grid admits one.
    links = [
        (a, b)
        for a, b in ((0, 1), (1, 2), (3, 4), (4, 5), (0, 3), (1, 4), (2, 5))
        if shrine not in (a, b)
    ]
    visited = {start}
    selected = []
    while len(visited) < len(ordinary):
        edge = random.choice(
            [e for e in links if (e[0] in visited) != (e[1] in visited)]
        )
        selected.append(edge)
        visited.update(edge)
    extras = [e for e in links if e not in selected]
    if extras and random.random() < 0.7:
        selected.append(random.choice(extras))
    for a, b in selected:
        _trail(dungeon, rooms[a].center, rooms[b].center, a // 3 == b // 3)

    for idx, biome in zip(ordinary, themes):
        _clearing(dungeon, rooms[idx], biome)
    dungeon.rooms = [rooms[i] for i in ordinary]
    _waterfront(dungeon, rooms[3:], direction)
    if shrine is not None:
        _mirror_shrine(dungeon, rooms[shrine], rooms[shrine + 3].center)

    dungeon.start_pos = rooms[start].center
    sx, sy = dungeon.start_pos
    dungeon.jungle_props.append((sx - 2, sy + 1, "campfire"))
    # Put the stairs in a distant landmark along the actual trail network.
    distances = {start: 0}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for a, b in selected:
            if node in (a, b):
                other = b if a == node else a
                if other not in distances:
                    distances[other] = distances[node] + 1
                    queue.append(other)
    exit_room = rooms[max(distances, key=distances.__getitem__)]
    dungeon.jungle_props.append((*exit_room.center, "stairs"))
