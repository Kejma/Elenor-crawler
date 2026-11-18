"""Landmark palettes and small hand-composed arrangements for the jungle generator."""

import math
import random

import pygame

from elenor.config import SHALLOW_WATER

# Each group dresses a single place: a hunting lodge, a shrine, a mine face...
FURNITURE = {
    "hut": [
        "tribal_bed tribal_stool tribal_pot fruit_basket",
        "tribal_bow_stand tribal_rack tribal_mask_shield blowgun_trap",
        "tribal_hammock tribal_table tribal_chest fish_drying_rack",
        "shaman_cauldron tribal_drum shaman_gong skull_brazier",
        "bamboo_cage tribal_skull_pole tribal_totem fruit_basket",
    ],
    "grove": [
        "banana_plant giant_fern jungle_bush_flowers",
        "jungle_boulder tree_stump jungle_bush",
        "bamboo_clump termite_mound snake_shed_skin",
    ],
    "marsh": [
        "hollow_log rafflesia_flower venus_flytrap",
        "bamboo_clump giant_fern jungle_bush",
    ],
    "ruins": [
        "giant_stone_head ancient_waystone marble_pillar_broken",
        "fallen_colossus marble_obelisk marble_urn",
    ],
    "bone": [
        "leviathan_rib_arch giant_beast_skull spine_pillar",
        "bone_wind_chimes bone_totem_altar bone_spike_barricade",
        "blood_thorn_bush corpse_pitcher_plant impaled_skeleton",
        "bone_throne bone_cage_hanging sacrificial_bone_table",
        "necrotic_brazier ossuary_chest bone_totem_altar",
    ],
    "temple": [
        "serpent_statue marble_altar incense_burner",
        "marble_bench marble_lectern marble_chest",
        "marble_pillar sun_gong marble_brazier",
        "marble_obelisk temple_sundial marble_urn",
        "marble_fountain holy_fire_bowl marble_statue",
        "marble_sarcophagus fallen_colossus marble_pillar_broken",
    ],
    "cave": [
        "minecart_wreck miner_skeleton amethyst_geode",
        "cave_stalagmite crystal_cluster giant_cave_mushroom",
        "bat_roost_rock stalagnate_column abyssal_fissure",
        "spider_cocoon spider_egg_sac sulfur_geyser",
    ],
}
# Common floor, accent floors, surrounding terrain and low details.
PALETTES = {
    "grove": (10, (11, 12), (21, 22), "fern fallen_leaves flowers_red flowers_blue"),
    "marsh": (23, (11, 42), (22, 17), "mangrove_roots bamboo_leaves mud_puddle"),
    "ruins": (24, (30, 16), (20, 36), "jungle_vines moss petals_gold"),
    "bone": (
        45,
        (46, 47),
        (56, 57),
        "ribcage_remains blood_vines bone_spikes_floor corrupted_spores shattered_skulls bones",
    ),
    "village": (12, (10, 24), (21, 22), "bamboo_leaves fallen_leaves"),
    "temple": (
        14,
        (15, 28, 29, 30, 31, 16),
        (19, 20, 35, 36),
        "marble_cracks gold_filigree petals_gold",
    ),
    "cave": (
        26,
        (49, 50),
        (7, 34, 54, 55),
        "glow_shrooms spider_web guano_droppings sulfur_cracks",
    ),
}


def mist(d, x, y, radius, color=(0.44, 0.62, 0.66)):
    d.fog_zones.append(
        dict(
            wx=x + 0.5,
            wy=y + 0.5,
            radius=radius,
            color=color,
            density=0.45,
            kind="mist",
        )
    )


def lamp(d, x, y, radius=110):
    d.braziers.append(dict(x=x, y=y, radius=radius, color=(1.15, 0.78, 0.44)))


def village(d, room):
    """Four short doorways facing the shared green, axes kept clear for through traffic."""
    cx, cy = room.center
    d._carve_rect(room, 10)
    d._carve_rect(pygame.Rect(room.left, cy, room.w, 2), 24)
    houses = random.sample(FURNITURE["hut"], 4)
    for (dx, dy), furniture in zip(((-1, -1), (1, -1), (-1, 1), (1, 1)), houses):
        hut = pygame.Rect(0, 0, random.choice((7, 9)), 7)
        hut.center = cx + dx * 8, cy + dy * 6
        d._carve_rect(hut, random.choice((18, 33)))
        d._carve_rect(hut.inflate(-2, -2), 13)
        hx, hy = hut.center
        d._carve_rect(pygame.Rect(hx - 1, hy, 3, 2), 27)
        door_y = hut.bottom - 1 if dy < 0 else hut.top
        d.grid[door_y][hx] = 13
        lamp(d, hx + 1, door_y + dy, 90)
        for (ox, oy), kind in zip(
            ((-2, -dy * 2), (2, -dy * 2), (-2, dy), (2, dy)), furniture.split()
        ):
            d.jungle_props.append((hx + ox, hy + oy, kind))
    d.jungle_props.extend(
        [(cx - 3, cy - 2, "tribal_totem"), (cx + 3, cy + 2, "campfire")]
    )


def dress_site(d, room, theme):
    if theme == "village":
        village(d, room)
        return
    floor, accents, walls, details = PALETTES[theme]
    cx, cy = room.center
    temple = theme == "temple"
    inner = room.inflate(-2, -2)
    details = details.split()
    accent = random.choice(accents)
    phase = random.uniform(0, math.tau)
    for y in range(room.top, room.bottom):
        for x in range(room.left, room.right):
            dx, dy = x - cx, y - cy
            if temple:
                inside = inner.collidepoint(x, y)
                detail = abs(dx) < 2 or abs(dy) < 2
            else:
                wave = math.sin(dx * 0.55 + phase) * math.cos(dy * 0.48)
                inside = (dx / (room.w * 0.5)) ** 2 + (
                    dy / (room.h * 0.5)
                ) ** 2 < 0.94 + 0.12 * wave
                detail = wave > 0.45
            if inside:
                d.grid[y][x] = accent if detail else floor
                if random.random() < 0.12:
                    d.overlays[x, y] = "ov_" + random.choice(details)
            elif temple and d.grid[y][x] != 12:
                d.grid[y][x] = walls[(x // 4 + y // 4) % len(walls)]
    # Keep the two main axes free. Dress the sides in small related groups.
    items = random.choice(FURNITURE[theme]).split()
    for (dx, dy), kind in zip(((-3, -2), (4, -3), (-4, 2)), items):
        d.jungle_props.append((cx + dx, cy + dy, kind))
    if theme == "temple" and room.w >= 19:
        # Paired columns flank an unobstructed ceremonial aisle.
        for x in (room.left + 4, room.right - 5):
            for y in (room.top + 3, room.bottom - 4):
                d.jungle_props.append((x, y, "marble_pillar"))
    wet = theme == "marsh" or random.random() < 0.42
    if wet and theme != "ruins":
        basin = {
            "grove": SHALLOW_WATER,
            "marsh": SHALLOW_WATER,
            "bone": 43,
            "temple": 32,
            "cave": random.choice((44, 49)),
        }[theme]
        px, py = cx + random.choice((-1, 1)) * room.w // 4, cy + room.h // 5
        rx, ry = random.choice(((2, 1), (3, 2), (4, 2)))
        for y in range(py - ry, py + ry + 1):
            for x in range(px - rx, px + rx + 1):
                if (x - px) ** 2 / rx**2 + (y - py) ** 2 / ry**2 <= 1:
                    d.grid[y][x] = 48 if theme == "bone" and y == py else basin
                    d.overlays.pop((x, y), None)
        if theme in ("grove", "marsh", "cave"):
            mist(d, px, py, random.uniform(2.5, 4.5))
    if theme in ("grove", "marsh"):
        d.atmo_zones.append(dict(rect=room, kind="forest"))
        for y in range(cy - 5, cy - 2):
            for x in range(cx - 3, cx + 2):
                if random.random() < 0.72 and d.grid[y][x] == 10:
                    d.moss_tiles.add((x, y))
    if theme == "cave":
        d.room_lights.append(
            dict(x=cx - 3, y=cy - 2, color=(0.46, 0.54, 1.1), radius=106)
        )
    elif theme in ("grove", "marsh"):
        # Luminous flowers give wild glades a visible source of cool light.
        d.overlays[cx + 2, cy - 2] = "ov_flowers_blue"
        d.room_lights.append(
            dict(x=cx + 2, y=cy - 2, color=(0.46, 0.77, 0.84), radius=110)
        )
    else:
        lamp(d, cx + 2, cy - 2)
