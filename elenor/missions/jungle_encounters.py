"""Place campaign encounters on the terrain their inhabitants use."""

import math
import random

from elenor.config import DEEP_WATER, PIER, SHALLOW_WATER
from elenor.entities import Enemy, SOLID_INTERACTABLE_KINDS
from elenor.puzzles.mirrors import reachable_floor_tiles
from elenor.puzzles.optics import MIRROR_SOLID_KINDS

# Each entry is the earliest valley in which a species can appear.
HABITATS = {
    "grove": ((1, "jungle_gremlin"), (1, "jungle_viper"), (1, "giant_wasp"), (2, "thorn_treant")),
    "marsh": ((2, "swamp_lurker"), (2, "myconid_shambler"), (3, "croc_warrior")),
    "riverbank": ((2, "swamp_lurker"), (2, "croc_warrior")),
    "village": ((2, "tribal_warrior"), (2, "tribal_hunter"), (3, "tribal_shaman")),
    "ruins": ((2, "giant_scorpion"), (2, "jade_scarab"), (3, "rust_monster")),
    "bone": ((3, "skull_spider"), (3, "bone_constrictor"), (4, "bone_jaguar")),
    "cave_squeeze": ((1, "cave_piercer"), (2, "rust_monster")),
    "cave_geode": ((1, "jade_scarab"), (2, "myconid_shambler"), (2, "rust_monster")),
    "cave_sump": ((1, "cave_angler"), (2, "myconid_shambler")),
    "cave_chasm": ((1, "cave_piercer"), (2, "giant_scorpion"), (3, "skull_spider")),
    "cave_gallery": ((1, "cave_piercer"), (2, "rust_monster"), (2, "giant_scorpion")),
    "temple_nave": ((1, "jade_scarab"), (2, "vedalken_mage"), (3, "marble_golem")),
    "temple_inner": ((1, "jade_scarab"), (2, "vedalken_mage"), (3, "vedalken_four_armed"), (3, "marble_golem")),
}

GUARDIANS = {
    "riverbank": (4, "croc_juggernaut"),
    "temple_inner": (5, "vedalken_arbiter"),
    "bone": (4, "ossuary_behemoth"),
}

# The first valley must be playable with fists if the player walks past supplies.
EARLY_STATS = {
    "jungle_gremlin": (9, 2, 4, 12),
    "jungle_viper": (10, 2, 4, 12),
    "giant_wasp": (8, 2, 4, 12),
    "jade_scarab": (13, 3, 5, 14),
    "cave_piercer": (14, 3, 6, 14),
    "cave_angler": (15, 3, 6, 14),
}
def populate_encounters(game, Interactable):
    d = game.dungeon
    depth = d.floor_num
    start = d.start_pos
    occupied = {(obj.x, obj.y) for obj in game.objects}
    solids = SOLID_INTERACTABLE_KINDS | MIRROR_SOLID_KINDS
    blocked = {(obj.x, obj.y) for obj in game.objects if obj.kind in solids}
    crossing = reachable_floor_tiles(d, start, blocked)
    open_tiles = {
        (x, y) for x, y in crossing - occupied - d.doors.keys() - d.levers.keys()
        if d.grid[y][x] not in (SHALLOW_WATER, DEEP_WATER, PIER, 32, 43, 44)
    }
    # Approaches stay safe even on the other side of a bend or a closed door.
    entry_buffer = 10 if d.interior else (13 if depth == 1 else 10)
    quiet = [start, *d.passages]
    camps = [
        position for position, kind in d.map_landmarks.items()
        if kind == "pier" or (depth == 1 and kind == "village")
    ]
    open_tiles = {
        p for p in open_tiles
        if all(math.dist(p, q) > entry_buffer for q in quiet)
        and all(math.dist(p, q) > 8 for q in camps)
    }

    groups = [(habitat, cells & open_tiles) for habitat, cells in d.jungle_habitats]
    rng = random
    rng.shuffle(groups)
    placed = []
    if d.interior:
        compact = d.jungle_gate is None
        limit = (5 if compact else 9) + min(5, depth - 1)
    else:
        limit = 11 if depth == 1 else 16 + min(8, depth - 2)
    spacing = 6.0 if d.interior else 7.5

    def spawn(point, kind, state):
        mob = Enemy(*point, kind=kind, state=state)
        if depth == 1:
            mob.max_hp, mob.dmg_min, mob.dmg_max, mob.xp_value = EARLY_STATS[kind]
            mob.hp = mob.max_hp
            mob.phys_def = mob.mag_def = 0
            mob.speed = min(mob.speed, 2.7)
            mob.detect_range = min(mob.detect_range, 4.1)
        else:
            growth = min(5, depth - 2)
            mob.max_hp = mob.hp = round(mob.max_hp * (1 + 0.09 * growth))
            if not mob.is_boss:
                mob.phys_def = min(mob.phys_def, 2 if depth == 2 else 4)
                mob.mag_def = min(mob.mag_def, 2 if depth == 2 else 4)
            mob.dmg_min += growth // 2
            mob.dmg_max += growth // 2
            mob.xp_value = round(mob.xp_value * (1 + 0.08 * growth))
        game.mobs.append(mob)
        placed.append(point)

    for habitat, cells in groups:
        boss = GUARDIANS.get(habitat)
        if not boss or depth < boss[0] or depth > boss[0] and rng.random() > 0.44:
            continue
        roomy = [
            (x, y) for x, y in sorted(cells)
            if all((x + dx, y + dy) in open_tiles for dx in (-1, 0, 1) for dy in (-1, 0, 1))
        ]
        if roomy:
            spawn(rng.choice(roomy), boss[1], "guarding")
            break

    for habitat, cells in groups * 3:
        if len(placed) >= limit:
            break
        kinds = [kind for earliest, kind in HABITATS[habitat] if earliest <= depth]
        candidates = [p for p in sorted(cells) if all(math.dist(p, q) >= spacing for q in placed)]
        if not candidates or not kinds:
            continue
        anchor = rng.choice(candidates)
        kind = rng.choice(kinds)
        hold = habitat in ("village", "temple_inner", "cave_squeeze", "cave_chasm") or kind in (
            "swamp_lurker", "cave_angler", "thorn_treant",
        )
        spawn(anchor, kind, "guarding" if hold else "patrolling")
        companions = [p for p in candidates if 2 <= math.dist(anchor, p) <= 4]
        if len(placed) < limit and companions and (kind == "tribal_shaman" or rng.random() < (0.25 if depth == 1 else 0.70)):
            allies = [other for other in kinds if other != "tribal_shaman"]
            spawn(rng.choice(companions), rng.choice(allies), "guarding" if hold else "patrolling")
