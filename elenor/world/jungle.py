"""Connected night-jungle clearings, river landings and optional temple vaults."""

import math
import random

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

from elenor.world.jungle_sites import PALETTES, dress_site, lamp, mist


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


def _waterfront(dungeon, near_rooms, direction):
    river = random.choice((True, False))
    docks = random.sample(near_rooms, 2 if river else 1)
    center = docks[0].centerx
    radius = min(random.randint(19, 29), center - 1, dungeon.width - 2 - center)
    phase = random.uniform(0, math.tau)
    banks = {}
    for x in range(1, dungeon.width - 1):
        if river:
            inset = 10 + round(1.4 * math.sin(x / 8 + phase))
            width = 7 + round(math.sin(x / 6 + phase))
        else:
            shape = 1 - ((x - center) / radius) ** 2
            if shape <= 0:
                continue
            half = max(1, round(4 * math.sqrt(shape)))
            inset, width = 5 + half, half * 2 - 1
        bank = dungeon.height - 1 - inset if direction == 1 else inset
        banks[x] = bank
        for depth in range(-1, width):
            y = bank + depth * direction
            if not 0 < y < dungeon.height - 1:
                continue
            tile = PEBBLE_SHORE if depth == -1 else SHALLOW_WATER
            if 2 <= depth < width - 1:
                tile = DEEP_WATER
            dungeon.grid[y][x] = tile
            if depth == -1:
                dungeon.grid[y][x] = random.choice((25, 41, PEBBLE_SHORE))
                if random.random() < 0.12:
                    dungeon.overlays[x, y] = random.choice(
                        ("ov_shells_starfish", "ov_shore_foam")
                    )
            if depth == 0 and random.random() < 0.24:
                dungeon.overlays[x, y] = random.choice(
                    (
                        "ov_water_lily",
                        "ov_duckweed",
                        "ov_fish_shadows",
                        "ov_bobber_ripples",
                    )
                )
    if river:
        # A separate crossing leads to a small fishing camp on the other bank.
        bridge_room = next(room for room in near_rooms if room not in docks)
        x, cy = bridge_room.center
        bank = banks[x]
        landing = dungeon.height - 3 if direction == 1 else 2
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
        lamp(dungeon, x - 1, landing)
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
        dungeon.jungle_props.extend(
            [
                (x + 2, bank, "prop_fish_trap_net"),
                (x + 2, bank - direction, "prop_fisherman_stool"),
                (x - 1, bank - direction, "prop_tackle_box"),
            ]
        )
        mist(dungeon, x + 2, bank + direction * 3, 4)
        lamp(dungeon, x + 1, bank - direction, 142)


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


def _network(cols, rows, omitted):
    """Random spanning tree with a few additional paths back to earlier clearings."""
    links = [
        (i, j)
        for i in range(cols * rows)
        if i != omitted
        for j in (i + 1, i + cols)
        if j < cols * rows
        and j != omitted
        and (j // cols == i // cols or j == i + cols)
    ]
    random.shuffle(links)
    components = list(range(cols * rows))
    paths = []
    for a, b in links:
        left, right = components[a], components[b]
        if left != right:
            components = [left if group == right else group for group in components]
        elif random.random() > 0.22:
            continue
        paths.append((a, b))
    return paths


def _passage(d, xy, action, sprite):
    d.passages[xy] = action
    d.jungle_props.append((*xy, sprite))


def _entrance(d, room, kind):
    # The door sits in a stone facade, with a walkable threshold towards the clearing.
    cx, cy = room.center
    x, y = cx + 6, cy - 4
    wall, floor, prop = (
        (19, 31, "serpent_statue") if kind == "temple" else (34, 26, "cave_stalagmite")
    )
    d._carve_rect(pygame.Rect(x - 2, y - 2, 5, 4), wall)
    d._carve_rect(pygame.Rect(x - 1, y, 3, 5), floor)
    d._carve_rect(pygame.Rect(cx, cy, x - cx + 1, 2), floor)
    d.jungle_props.append((x - 2, y + 2, prop))
    _passage(d, (x, y), kind, "stairs")
    lamp(d, x + 2, y + 2, 95)


def generate_jungle_floor(dungeon):
    d = dungeon
    cols, rows = 6, 4
    width, height = MAP_COLS * 3, MAP_ROWS * 3
    interior = d.interior
    direction = random.choice((-1, 1))
    rooms = []
    for row in range(rows):
        for col in range(cols):
            cx = 17 + 32 * col + random.randint(-2, 2)
            cy = 14 + 28 * row + random.randint(-2, 2)
            if direction < 0:
                cy = height - 1 - cy
            rw, rh = random.randrange(19, 29, 2), random.randrange(13, 21, 2)
            if interior and random.random() < 0.4:
                rw, rh = random.choice((13, 15)), random.choice((9, 11))
            room = pygame.Rect(0, 0, rw, rh)
            room.center = cx, cy
            rooms.append(room)
    start = cols * random.randrange(rows)
    shrine = None
    if random.random() < d.puzzle_chance:
        shrine = random.randrange(3, cols)
    ordinary = [i for i in range(len(rooms)) if i != shrine]
    paths = _network(cols, rows, shrine)
    if interior:
        themes = dict.fromkeys(ordinary, interior)
    else:
        # Begin on the green, western side. Each valley has one dominant landscape.
        far = "grove" if d.floor_num == 1 else random.choice(("bone", "marsh", "ruins"))
        themes = {i: ("grove" if i % cols < 2 else far) for i in ordinary}
        for row in range(rows):
            themes[row * cols + 1] = random.choice(("grove", "marsh"))
        candidates = [i for i in ordinary if i % cols in (2, 3)]
        if d.floor_num == 1:
            # The dirt road from the opening grove leads east to the settlement.
            village = min(i for i in candidates if i // cols == start // cols)
            for i in range(start, village):
                if i + 1 == shrine or i == shrine:
                    continue
                if (i, i + 1) not in paths:
                    paths.append((i, i + 1))
        else:
            village = random.choice(candidates)
        themes[village] = "village"
        village_y = rooms[village].centery
        rooms[village].size = (29, 21)
        rooms[village].center = (17 + 32 * (village % cols), village_y)
        if d.floor_num > 1:
            themes[start] = random.choice(("grove", far))
    d.jungle_props = []
    phase = random.uniform(0, math.tau)
    grid = []
    for y in range(height):
        line = []
        for x in range(width):
            band_y = y if direction > 0 else height - 1 - y
            col = max(0, min(cols - 1, int((x + 2 * math.sin(y / 5 + phase)) // 32)))
            row = max(
                0, min(rows - 1, int((band_y + 2 * math.cos(x / 6 + phase)) // 28))
            )
            theme = themes.get(row * cols + col) or interior or "grove"
            base, _, walls, _ = PALETTES[theme]
            pattern = math.sin(x * 0.23 + phase) + math.cos(y * 0.19 - phase)
            tile = walls[min(len(walls) - 1, int((pattern + 2) * 0.249 * len(walls)))]
            if not interior and 0 < x < width - 1 and 0 < y < height - 1:
                if pattern + 0.65 * math.sin(x * 1.7 + y * 2.3) > 0.35:
                    tile = base
                elif theme == "bone" and pattern < -1.6:
                    tile = random.choice((51, 52, 53))
            line.append(tile)
        grid.append(line)
    d.grid = grid
    for a, b in paths:
        _trail(d, rooms[a].center, rooms[b].center, a // cols == b // cols)
    d.rooms = [rooms[i] for i in ordinary]
    for i in ordinary:
        dress_site(d, rooms[i], themes[i])
    if not interior:
        _waterfront(d, random.sample(rooms[-cols:], 3), direction)
    if shrine is not None:
        _mirror_shrine(d, rooms[shrine], rooms[shrine + cols].center)
    d.start_pos = rooms[start].center
    sx, sy = d.start_pos
    if interior:
        corridor = 24 if interior == "temple" else 26
        for line in d.grid:
            for x, tile in enumerate(line):
                if tile == 12:
                    line[x] = corridor
        # The return stair rises to a lit opening in the chamber wall.
        opening = rooms[start].top + 1
        for y in range(opening, sy):
            for x in range(sx - 1, sx + 2):
                d.grid[y][x] = (
                    corridor if y % 2 else (31 if interior == "temple" else 50)
                )
                d.overlays.pop((x, y), None)
        _passage(d, (sx, opening), "up", "door_open")
        d.room_lights.append(dict(x=sx, y=opening, color=(0.80, 0.88, 0.71), radius=90))
        far_room = max(
            (rooms[i] for i in ordinary), key=lambda r: math.dist(r.center, d.start_pos)
        )
        d.jungle_props.append((*far_room.center, "chest"))
        return
    d.jungle_props.append((sx - 2, sy + 1, "campfire"))
    # Trails actually reach the boundary. Returning travellers arrive by the sign.
    exits = [
        (
            "forward",
            random.choice([i for i in ordinary if i % cols == cols - 1]),
            width - 2,
        )
    ]
    if d.floor_num > 1:
        exits.append(("back", start, 1))
    for action, idx, x in exits:
        cx, cy = rooms[idx].center
        _trail(d, (cx, cy), (x, cy), True)
        boundary = 0 if action == "back" else width - 1
        for y in (cy, cy + 1):
            d.grid[y][boundary] = 12
            d.invisible_bounds.add((boundary, y))
        _passage(d, (x, cy), action, "notice_board")
        lamp(d, x, cy + 1)
    sites = [i for i in ordinary if i % cols >= 2 and themes[i] != "village"]
    for i, kind in zip(random.sample(sites, 2), ("temple", "cave")):
        _entrance(d, rooms[i], kind)
