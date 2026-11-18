"""Shape, reserve and furnish jungle landmarks on a shared tile plan."""

from math import atan2, cos, hypot, pi, sin, tau

import pygame

from elenor.config import DEEP_WATER, SHALLOW_WATER
from elenor.world.dungeon import Door


CARDINAL = ((1, 0), (0, 1), (-1, 0), (0, -1))


class LayoutError(Exception):
    """A candidate layout has no valid road, lot or threshold."""


def offset(point, direction, step=1):
    return point[0] + direction[0] * step, point[1] + direction[1] * step


def neighbors(point):
    return (offset(point, direction) for direction in CARDINAL)


def rect_cells(rect):
    return {
        (x, y)
        for y in range(rect.top, rect.bottom)
        for x in range(rect.left, rect.right)
    }


def bounds(cells):
    xs, ys = zip(*cells)
    return pygame.Rect(min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)


def oval(
    center,
    rx: float,
    ry: float,
    angle: float = 0,
    roughness: float = 0,
    phase: float = 0,
):
    """A rotated footprint with continuous, low-frequency scalloping."""
    cx, cy = center
    extent = int(max(rx, ry) * (1 + roughness)) + 1
    ct, st = cos(angle), sin(angle)
    result = set()
    for y in range(cy - extent, cy + extent + 1):
        for x in range(cx - extent, cx + extent + 1):
            u = ((x - cx) * ct + (y - cy) * st) / rx
            v = ((y - cy) * ct - (x - cx) * st) / ry
            theta = atan2(v, u)
            edge = 1 + roughness * (
                0.67 * sin(3 * theta + phase) + 0.33 * cos(5 * theta - phase)
            )
            if u * u + v * v <= edge * edge:
                result.add((x, y))
    return result


def erode(cells, steps=1):
    for _ in range(steps):
        cells = {
            point for point in cells if all(side in cells for side in neighbors(point))
        }
    return cells


def dilate(cells, steps=1):
    for _ in range(steps):
        cells = cells | {side for point in cells for side in neighbors(point)}
    return cells


def width_at(point, cells):
    return sum(side in cells for side in neighbors(point))


class Plan:
    """All writes share the same protected routes, wet ground and fixture footprint."""

    def __init__(self, dungeon, rng):
        self.d = dungeon
        self.rng = rng
        self.width = dungeon.width
        self.height = dungeon.height
        self.routes = set()
        self.water = set()
        self.structure = set()
        self.occupied = set()
        self.floor = set()
        self.bridges = set()
        self.hut_entries = set()

    def inside(self, point, margin=1):
        x, y = point
        return margin <= x < self.width - margin and margin <= y < self.height - margin

    def tile(self, point):
        x, y = point
        return self.d.grid[y][x]

    def paint(self, cells, tile, *, walk=True):
        painted = set()
        for x, y in cells:
            point = x, y
            if self.inside(point):
                self.d.grid[y][x] = tile
                self.d.overlays.pop(point, None)
                self.d.moss_tiles.discard(point)
                painted.add(point)
        if walk:
            self.floor.update(painted)
        else:
            self.floor.difference_update(painted)
        return painted

    def clearing(self, cells, tile):
        return self.paint(
            cells - self.water - self.structure - self.routes - self.occupied, tile
        )

    def prop(self, point, kind, *, on_route=False):
        if point not in self.floor or point in self.occupied or point in self.water:
            return False
        if point in self.routes and not on_route:
            return False
        self.occupied.add(point)
        self.d.jungle_props.append((*point, kind))
        return True

    def feature(self, point, action, sprite):
        if not self.prop(point, sprite, on_route=True):
            raise LayoutError(f"Passage {action} has no free threshold at {point}")
        self.routes.add(point)
        self.d.passages[point] = action

    def light(self, point, radius, color, *, brazier=False):
        if point in self.floor:
            x, y = point
            destination = self.d.braziers if brazier else self.d.room_lights
            destination.append(dict(x=x, y=y, radius=radius, color=color))

    def lamp(self, point, radius=104):
        self.light(point, radius, (1.14, 0.77, 0.44), brazier=True)

    def mist(self, point, radius, color=(0.44, 0.62, 0.66), density=0.4):
        x, y = point
        self.d.fog_zones.append(
            dict(
                wx=x + 0.5,
                wy=y + 0.5,
                radius=radius,
                color=color,
                density=density,
                kind="mist",
            )
        )

    def room(self, cells):
        self.d.rooms.append(bounds(cells))

    def pool(self, footprint, tile, *, deep=False):
        # Leave a full tile of dry margin between water and a marked path or fixture.
        forbidden = dilate(self.routes | self.occupied, 1) | self.structure
        if len(footprint) < 4 or not footprint <= self.floor - forbidden - self.water:
            return set()
        self.paint(footprint, tile, walk=True)
        self.water.update(footprint)
        if deep:
            self.paint(erode(footprint, 2), DEEP_WATER, walk=False)
        return footprint


def detail_patch(plan, cells, overlay, count, *, radius=(2, 5), density=0.66):
    if not cells:
        return
    centers = plan.rng.sample(sorted(cells), min(count, len(cells)))
    for center in centers:
        rx = plan.rng.randint(*radius)
        ry = plan.rng.randint(1, max(1, rx - 1))
        shape = oval(
            center, rx, ry, plan.rng.random() * pi, 0.18, plan.rng.random() * tau
        )
        for point in sorted(shape & cells - plan.occupied):
            if plan.rng.random() < density:
                if overlay == "moss":
                    plan.d.moss_tiles.add(point)
                else:
                    plan.d.overlays[point] = overlay


def prop_group(plan, group, cells, anchor, spacing=1):
    """Furnish visible clusters around landmarks, leaving travel lanes alone."""
    available = cells & plan.floor - plan.routes - plan.occupied - plan.water
    for kind in group:
        if not available:
            break
        # Draw among the nearest candidates so the group reads as one composition.
        close = sorted(
            available,
            key=lambda point: (
                hypot(point[0] - anchor[0], point[1] - anchor[1]),
                point,
            ),
        )
        point = plan.rng.choice(close[:4])
        plan.prop(point, kind)
        available.difference_update(dilate({point}, spacing))


GROVE_GROUPS = (
    ("banana_plant", "giant_fern", "jungle_bush_flowers"),
    ("jungle_boulder", "tree_stump", "jungle_bush"),
    ("bamboo_clump", "termite_mound", "snake_shed_skin"),
)

MARSH_GROUPS = (
    ("hollow_log", "rafflesia_flower", "venus_flytrap"),
    ("bamboo_clump", "giant_fern", "jungle_bush"),
)

BONE_GROUPS = (
    ("leviathan_rib_arch", "giant_beast_skull", "spine_pillar"),
    ("bone_wind_chimes", "bone_totem_altar", "bone_spike_barricade"),
    ("blood_thorn_bush", "corpse_pitcher_plant", "impaled_skeleton"),
    ("bone_throne", "bone_cage_hanging", "sacrificial_bone_table"),
    ("necrotic_brazier", "ossuary_chest", "bone_totem_altar"),
)

RUIN_GROUPS = (
    ("giant_stone_head", "ancient_waystone", "marble_pillar_broken"),
    ("fallen_colossus", "marble_obelisk", "marble_urn"),
)

HUT_GROUPS = (
    ("tribal_bed", "tribal_stool", "tribal_pot", "fruit_basket"),
    ("tribal_bow_stand", "tribal_rack", "tribal_mask_shield", "blowgun_trap"),
    ("tribal_hammock", "tribal_table", "tribal_chest", "fish_drying_rack"),
    ("shaman_cauldron", "tribal_drum", "shaman_gong", "skull_brazier"),
    ("bamboo_cage", "tribal_skull_pole", "tribal_totem", "fruit_basket"),
)


def find_pool(plan, candidates, tile, *, deep=False):
    room = candidates - plan.routes - plan.occupied - plan.water
    centers = sorted(erode(room, 2))
    plan.rng.shuffle(centers)
    for center in centers[:36]:
        basin = oval(
            center,
            plan.rng.uniform(2.8, 6),
            plan.rng.uniform(1.6, 3.8),
            plan.rng.random() * pi,
            0.23,
            plan.rng.random() * tau,
        )
        if basin <= candidates and plan.pool(basin, tile, deep=deep):
            return center, basin
    return None


def dress_glade(plan, center, cells, biome):
    """The rims carry vegetation, the hollows collect water, the tracks stay dry."""
    tile, accents, groups, details = {
        "grove": (
            10,
            11,
            GROVE_GROUPS,
            ("ov_fern", "ov_flowers_red", "ov_fallen_leaves"),
        ),
        "marsh": (
            23,
            42,
            MARSH_GROUPS,
            ("ov_mangrove_roots", "ov_mud_puddle", "ov_bamboo_leaves"),
        ),
        "bone": (
            45,
            46,
            BONE_GROUPS,
            (
                "ov_ribcage_remains",
                "ov_blood_vines",
                "ov_shattered_skulls",
                "ov_bone_spikes_floor",
                "ov_corrupted_spores",
                "ov_bones",
            ),
        ),
        "ruins": (
            24,
            30,
            RUIN_GROUPS,
            ("ov_jungle_vines", "ov_gold_filigree", "ov_petals_gold"),
        ),
    }[biome]
    plan.clearing(cells, tile)
    dry = cells & plan.floor - plan.water - plan.routes - plan.structure
    if not dry:
        return
    dry_points = sorted(dry)
    accent_center = plan.rng.choice(dry_points)
    plan.clearing(oval(accent_center, 5, 3, plan.rng.random() * pi, 0.3) & dry, accents)
    if biome == "marsh" or plan.rng.random() < 0.57:
        pool_tile = 43 if biome == "bone" else SHALLOW_WATER
        pool = find_pool(plan, dry, pool_tile)
        if pool:
            pond_center, pond = pool
            dry -= pond
            plan.mist(pond_center, plan.rng.uniform(3, 6))
            if biome == "bone":
                # A remnant boardwalk follows the peat rim as a dry overlook.
                rim = sorted((dilate(pond) - pond) & dry)
                plan.clearing(set(rim[:6]), 48)
    edges = dry - erode(dry, 3)
    anchors = sorted(edges)
    plan.rng.shuffle(anchors)
    if anchors:
        for anchor in (
            anchors[0],
            max(
                anchors,
                key=lambda xy: hypot(xy[0] - anchors[0][0], xy[1] - anchors[0][1]),
            ),
        ):
            local = {
                point
                for point in edges
                if hypot(point[0] - anchor[0], point[1] - anchor[1]) < 6
            }
            prop_group(plan, plan.rng.choice(groups), local, anchor)
    for overlay in plan.rng.sample(details, min(3, len(details))):
        detail_patch(plan, dry, overlay, 2)
    if biome in ("grove", "marsh"):
        detail_patch(plan, dry, "moss", 3, radius=(2, 4))
        plan.d.atmo_zones.append(dict(rect=bounds(cells), kind="forest"))
        flower = min(
            dry_points, key=lambda xy: hypot(xy[0] - center[0], xy[1] - center[1])
        )
        if flower not in plan.water:
            plan.d.overlays[flower] = "ov_flowers_blue"
            plan.light(flower, 118, (0.43, 0.77, 0.79))
    else:
        light_tile = min(
            plan.routes & cells or dry,
            key=lambda xy: hypot(xy[0] - center[0], xy[1] - center[1]),
        )
        plan.lamp(light_tile, 125)
    plan.room(cells)


def wall_shell(plan, inner, wall):
    """One continuous masonry perimeter around a protected room."""
    exterior = dilate(inner) - inner
    plan.paint(exterior, wall, walk=False)
    plan.structure.update(inner | exterior)
    return exterior


def furnish_hut(plan, hut, door, outward, contents):
    floor = rect_cells(hut.inflate(-2, -2))
    wall_shell(plan, floor, plan.rng.choice((18, 33)))
    # Square exterior corners remain masonry.
    plan.paint(rect_cells(hut) - floor, plan.rng.choice((18, 33)), walk=False)
    plan.paint(floor | {door}, 13)
    path_start = offset(door, outward, -1)
    aisle = {
        tile
        for tile in floor
        if (tile[0] == path_start[0] if outward[1] else tile[1] == path_start[1])
    }
    plan.routes.update(aisle | {door})
    plan.hut_entries.add(path_start)
    cells = floor - aisle
    hearth = plan.rng.choice(sorted(cells))
    plan.lamp(hearth, 83)
    mat = {
        point
        for point in floor
        if hypot(point[0] - hearth[0], point[1] - hearth[1]) < 2.3
    }
    plan.paint(mat, 27)
    # Place the bulkiest furnishings against the far wall first.
    wall_row = {point for point in cells if offset(point, outward, -1) not in floor}
    if wall_row:
        prop_group(plan, contents[:1], wall_row, plan.rng.choice(sorted(wall_row)), 1)
    prop_group(plan, contents[1:], cells, hearth, 1)
    plan.room(floor)


def hut_candidates(plan, limit, street):
    """Lots along the usable edge of a street, facing the closest fork or court."""
    for door in sorted(dilate(street, 2) - dilate(street, 1)):
        if not limit.collidepoint(door):
            continue
        for outward in CARDINAL:
            threshold = offset(door, outward)
            if offset(threshold, outward) not in street:
                continue
            width, depth = plan.rng.choice(((5, 6), (6, 7), (7, 5), (8, 6), (6, 8)))
            tangent = -outward[1], outward[0]
            start = offset(door, tangent, -plan.rng.randint(1, width - 2))
            footprint = {
                offset(offset(start, tangent, side), outward, -row)
                for side in range(width)
                for row in range(depth)
            }
            if all(
                limit.collidepoint(point) and plan.inside(point, 2)
                for point in footprint
            ):
                yield door, outward, footprint


def village(plan, center, cells):
    plan.clearing(cells, 10)
    # An irregular common branches away from the old trail.
    court = oval(center, 5.5, 3.8, plan.rng.random() * pi, 0.2)
    street = (plan.routes & cells) | court
    plan.paint(court - plan.water - plan.structure, 24)
    plan.routes.update(court & plan.floor)
    limit = bounds(cells).inflate(-2, -2)
    lots = list(hut_candidates(plan, limit, street))
    plan.rng.shuffle(lots)
    chosen = []
    for door, outward, footprint in lots:
        setback = dilate(footprint, 1)
        if setback & (plan.routes | plan.water | plan.structure | plan.occupied):
            continue
        if any(
            hypot(door[0] - other[0], door[1] - other[1]) < 6 for other, _, _ in chosen
        ):
            continue
        chosen.append((door, outward, footprint))
        plan.structure.update(footprint)
        if len(chosen) == 6:
            break
    contents = plan.rng.sample(HUT_GROUPS, len(HUT_GROUPS))
    for index, (door, outward, footprint) in enumerate(chosen):
        plan.paint({offset(door, outward)}, 24)
        furnish_hut(
            plan, bounds(footprint), door, outward, contents[index % len(contents)]
        )
    # The square is open even with market furniture and drying racks at its rim.
    outer = (dilate(court, 3) - court) & plan.floor - plan.structure
    totem_anchor = offset(center, plan.rng.choice(CARDINAL), 5)
    prop_group(
        plan, ("tribal_totem", "campfire", "fruit_basket"), outer, totem_anchor, 1
    )
    if not any(kind == "tribal_totem" for _, _, kind in plan.d.jungle_props):
        point = min(court & plan.floor - plan.occupied)
        plan.prop(point, "tribal_totem", on_route=True)
    plan.lamp(center, 156)
    detail_patch(plan, cells & plan.floor - plan.structure, "ov_bamboo_leaves", 3)
    plan.room(cells)


def axis_frame(origin, forward):
    """Convert offsets measured from the entrance into world coordinates."""
    tangent = -forward[1], forward[0]

    def point(distance, side=0):
        return offset(offset(origin, forward, distance), tangent, side)

    return point


def axis_rect(point, first, last, left, right):
    return {
        point(depth, side)
        for depth in range(first, last + 1)
        for side in range(left, right + 1)
    }


def entrance(plan, center, kind, facing):
    """A landmark with a forecourt and a threshold built into its enclosing mass."""
    point = axis_frame(center, facing)
    if kind == "temple":
        temple_front(plan, point)
    else:
        cave_mouth(plan, point)


def temple_front(plan, point):
    court = axis_rect(point, -5, 10, -8, 8)
    plan.clearing(court, 24)
    terrace = axis_rect(point, 6, 13, -7, 7)
    plan.paint(terrace, 29)
    building = axis_rect(point, 14, 25, -10, 10)
    plan.paint(building - plan.routes, 20, walk=False)
    temple_face = axis_rect(point, 14, 16, -9, 9)
    plan.paint(temple_face - plan.routes, 19, walk=False)
    plan.structure.update(court | terrace | building)
    for depth, side_tile in ((4, 16), (5, 30), (8, 31), (12, 16)):
        plan.paint(axis_rect(point, depth, depth, -4, 4), side_tile)
    approach = axis_rect(point, 2, 18, -1, 1)
    plan.paint(approach, 31)
    plan.routes.update(approach)
    for side in (-1, 1):
        for depth in (3, 11):
            plan.prop(
                point(depth, side * 5),
                plan.rng.choice(
                    ("marble_pillar", "marble_pillar_broken", "marble_obelisk")
                ),
            )
        plan.prop(point(13, side * 3), "serpent_statue")
        plan.lamp(point(11, side * 3), 135)
    detail_patch(plan, court - approach, "ov_jungle_vines", 4)
    plan.feature(point(18), "temple", "stairs")
    plan.room(court)


def cave_mouth(plan, point):
    angle = atan2(point(1)[1] - point(0)[1], point(1)[0] - point(0)[0])
    wall = oval(point(15), 12, 10, angle, 0.25, plan.rng.random() * tau)
    forecourt = oval(point(2), 10, 7, angle, 0.2)
    plan.clearing(forecourt, 11)
    plan.paint(wall - plan.routes, 34, walk=False)
    plan.structure.update(wall | forecourt)
    outer_slope = axis_rect(point, 3, 10, -3, 3)
    throat = axis_rect(point, 9, 16, -1, 1)
    plan.paint(outer_slope, 50)
    plan.paint(throat, 26)
    plan.routes.update(throat | axis_rect(point, 0, 8, -1, 1))
    for side in (-1, 1):
        prop_group(
            plan,
            ("cave_stalagmite", "jungle_boulder"),
            forecourt - outer_slope,
            point(5, side * 5),
        )
    detail_patch(plan, forecourt, "ov_mangrove_roots", 3)
    plan.light(point(13), 115, (0.37, 0.57, 0.88))
    plan.mist(point(7), 5)
    plan.feature(point(15), "cave", "door_open")


def mirror_vault(plan, center, forward):
    """A walled side branch with exactly one gate into the reward chamber."""
    point = axis_frame(center, forward)
    hall = bounds(axis_rect(point, 3, 13, -4, 4))
    sealed = bounds(axis_rect(point, 15, 20, -3, 3))
    compound = rect_cells(hall.union(sealed).inflate(2, 2))
    plan.paint(compound, 19, walk=False)
    plan.structure.update(compound)
    plan.paint(rect_cells(hall), 14)
    plan.paint(rect_cells(sealed), 30)
    entry, gate = point(2), point(14)
    plan.paint({entry, gate, point(1)}, 14)
    plan.d.doors[gate] = Door(*gate, locked_by_lever=True)
    plan.d.mirror_puzzle_info = dict(
        puzzle_rect=hall,
        sealed_rect=sealed,
        entry_door=entry,
        gate_door=gate,
        tutorial=False,
        tiles=(19, 14),
    )
    plan.prop(sealed.center, "chest")
    plan.room(rect_cells(hall))
    plan.room(rect_cells(sealed))
    plan.lamp(point(1), 103)


def axial_chamber(point, depth, length, breadth, apse=False):
    """Enclose an orthogonal nave, optionally stepping inward at a closed apse."""
    half_width = breadth // 2
    half_length = length // 2
    cells = set()
    for across in range(-half_length, half_length + 1):
        inset = max(0, across - half_length + 3) if apse else 0
        for side in range(-half_width + inset, half_width - inset + 1):
            cells.add(point(depth + across, side))
    return cells


def aisle(plan, cells, floor):
    plan.paint(cells, floor)
    plan.routes.update(cells)


def door_band(plan, point, depth, width, tile):
    for side in range(-width // 2 + 1, width // 2 + 1):
        plan.d.grid[point(depth, side)[1]][point(depth, side)[0]] = tile
        plan.d.overlays[point(depth, side)] = "ov_gold_filigree"


def temple_gallery(plan, point, depth, cells, style):
    floor, border, ornament = style
    plan.paint(cells, floor)
    plan.paint(cells - erode(cells, 1), border)
    # Single processional axis, with paired colonnades running the length of the hall.
    spine = {
        point(step, side)
        for step in range(depth - 14, depth + 15)
        for side in (-1, 0, 1)
    }
    aisle(plan, spine & cells, ornament)
    for step in range(depth - 7, depth + 8, 4):
        for side in (-4, 4):
            xy = point(step, side)
            if xy in cells:
                plan.prop(
                    xy,
                    plan.rng.choice(
                        ("marble_pillar", "marble_pillar", "marble_pillar_broken")
                    ),
                )
    for side in (-1, 1):
        plan.lamp(point(depth + 2, side * 3), 126)
        detail_patch(plan, cells - spine, "ov_marble_cracks", 3)


def branch_room(plan, point, depth, side, purpose, colors):
    """Attach a transverse gallery to a real doorway in the longitudinal wall."""
    sign = 1 if side > 0 else -1
    wall, floor, accent = colors
    first = min(side - 4, side + 4)
    last = max(side - 4, side + 4)
    length = plan.rng.choice((9, 11, 13))
    room = axis_rect(point, depth - length // 2, depth + length // 2, first, last)
    wall_shell(plan, room, wall)
    plan.paint(room, floor)
    hallway = axis_rect(
        point, depth - 1, depth + 1, min(1 * sign, side), max(1 * sign, side)
    )
    aisle(plan, hallway, accent)
    prop_choices = {
        "archive": ("marble_lectern", "marble_bench", "marble_urn", "incense_burner"),
        "burials": ("marble_sarcophagus", "marble_chest", "fallen_colossus"),
        "baths": ("marble_fountain", "holy_fire_bowl", "marble_statue"),
        "offerings": ("temple_sundial", "sun_gong", "marble_brazier", "marble_obelisk"),
    }
    cells = room - plan.routes
    anchor = point(depth - 3, side + sign * 2)
    if purpose == "baths":
        plan.paint(oval(anchor, 2.8, 2.2, 0.3, 0.12) & cells, 32)
        plan.water.update({xy for xy in cells if plan.tile(xy) == 32})
    prop_group(plan, prop_choices[purpose], cells, anchor)
    plan.lamp(point(depth + 2, side - sign * 2), 108)
    detail_patch(plan, cells - plan.water, "ov_petals_gold", 2)
    plan.room(room)


def temple_sanctuary(plan, point, depth, room, color):
    """A raised end of the building, with the altar visible along the nave."""
    plan.paint(room, color)
    for step in range(depth - 6, depth + 4, 3):
        plan.paint(axis_rect(point, step, step, -4, 4) & room, 31)
    run = axis_rect(point, depth - 11, depth + 2, -1, 1) & room
    aisle(plan, run, 16)
    plan.prop(point(depth + 3), "marble_altar")
    for side in (-1, 1):
        group = ("serpent_statue", "incense_burner", "marble_statue")
        cells = {
            xy
            for xy in room
            if hypot(
                xy[0] - point(depth, side * 5)[0], xy[1] - point(depth, side * 5)[1]
            )
            < 4
        }
        prop_group(plan, group, cells, point(depth + 1, side * 4))
        plan.lamp(point(depth + 2, side * 3), 126)
    plan.light(point(depth + 1), 180, (0.89, 0.58, 0.26))


def cloister(plan, point, bands, side, colors):
    """Vaulted side aisle joining two annexes into an alternate processional loop."""
    wall, _, trim = colors
    first, last = bands
    nave = axis_rect(
        point, first, last, min(side - 1, side + 1), max(side - 1, side + 1)
    )
    shell = dilate(nave) - nave - plan.floor
    plan.paint(shell, wall, walk=False)
    plan.structure.update(shell | nave)
    aisle(plan, nave, trim)
    for depth in range(first + 4, last - 3, 6):
        for distance in (-2, 2):
            landing = point(depth, side + distance)
            if landing in plan.floor:
                plan.prop(landing, "marble_pillar")
    detail_patch(plan, nave, "ov_marble_cracks", 5, radius=(1, 3))
    plan.lamp(point((first + last) // 2, side), 115)


def build_temple(plan, origin, forward):
    """Draw an entrance spine with paced thresholds and off-axis annexes."""
    point = axis_frame(origin, forward)
    wall, floor, trim, motif = plan.rng.choice(
        ((19, 14, 30, 16), (35, 28, 15, 31), (36, 29, 30, 16))
    )
    intervals = (
        (6, plan.rng.choice((9, 11)), 9, False),
        (25, plan.rng.choice((15, 19)), plan.rng.choice((11, 15)), False),
        (52, plan.rng.choice((19, 23)), plan.rng.choice((13, 17)), False),
        (82, 19, plan.rng.choice((13, 17)), True),
    )
    chambers = []
    for depth, length, breadth, apse in intervals:
        room = axial_chamber(point, depth, length, breadth, apse)
        chambers.append(room)
        wall_shell(plan, room, wall)
        plan.room(room)
    for index, ((depth, _, _, _), room) in enumerate(zip(intervals, chambers)):
        if index == len(intervals) - 1:
            temple_sanctuary(plan, point, depth, room, floor)
        elif index == 0:
            plan.paint(room, 24)
            plan.paint(room - erode(room, 1), trim)
            for side in (-1, 1):
                plan.prop(point(depth + 2, side * 3), "marble_urn")
                plan.lamp(point(depth + 1, side * 2), 115)
        else:
            temple_gallery(plan, point, depth, room, (floor, trim, motif))
    all_rooms = set().union(*chambers)
    through = set()
    for depth in range(85):
        sleeves = (
            (0, 1) if depth in range(32, 42) or depth in range(64, 73) else (-1, 0, 1)
        )
        strip = {point(depth, side) for side in sleeves}
        through.update(strip)
        aisle(plan, strip - all_rooms, floor if depth % 3 == 0 else trim)
        plan.routes.update(strip)
    # The cross section contracts at vestibules and opens again into the naves.
    hallway_rim = dilate(through) - through - all_rooms
    plan.paint(hallway_rim, wall, walk=False)
    plan.structure.update(through | hallway_rim)
    for step, span in ((13, 3), (38, 2), (64, 2)):
        door_band(plan, point, step, span, 31)
        plan.lamp(point(step + 2, 1), 106)
    options = ["archive", "burials", "baths", "offerings"]
    plan.rng.shuffle(options)
    side = plan.rng.choice((-1, 1))
    layout = plan.rng.choice(("cloister", "annexes", "paired"))
    if layout == "cloister":
        annexes = ((25, 19), (52, 19), (78, -18))
    elif layout == "paired":
        annexes = ((48, 18), (53, -19), (78, 20), (24, -17))
    else:
        annexes = ((24, 17), (53, -23), (78, 18))
    for depth, reach in annexes:
        purpose = options.pop()
        branch_room(plan, point, depth, reach * side, purpose, (wall, floor, trim))
    if layout == "cloister":
        cloister(plan, point, (25, 52), 19 * side, (wall, floor, trim))
    plan.feature(point(1), "up", "door_open")
    plan.light(point(1), 123, (0.71, 0.86, 0.73))
    plan.prop(point(83, 0), "chest", on_route=True)
    return point(4), point


CAVE_GROUPS = (
    ("minecart_wreck", "miner_skeleton", "amethyst_geode"),
    ("cave_stalagmite", "crystal_cluster", "giant_cave_mushroom"),
    ("bat_roost_rock", "stalagnate_column", "abyssal_fissure"),
    ("spider_cocoon", "spider_egg_sac", "sulfur_geyser"),
)


def cave_chamber(plan, center, vein, kind):
    """Build one pocket within the rock, with lateral rims and one or more recesses."""
    angle = plan.rng.uniform(-pi, pi)
    rx, ry = {
        "mouth": (8, 5),
        "squeeze": (5, 4),
        "gallery": (11, 7),
        "sump": (13, 8),
        "geode": (10, 7),
        "chasm": (13, 9),
    }[kind]
    main = oval(center, rx, ry, angle, 0.22, plan.rng.random() * tau)
    spur = offset(center, plan.rng.choice(CARDINAL), plan.rng.randint(3, 6))
    recess = oval(spur, max(3, rx // 2), max(2, ry // 2), angle - 0.5, 0.21)
    shell = {point for point in main | recess if plan.inside(point, 3)}
    palette = {
        "mouth": (8, 11),
        "squeeze": (8, 50),
        "gallery": (8, 26),
        "sump": (11, 49),
        "geode": (50, 49),
        "chasm": (50, 26),
    }[kind]
    plan.clearing(shell, palette[0])
    # Water and minerals drip along different sides of the same bedrock seam.
    plan.clearing(
        oval(vein, rx * 0.56, ry * 0.63, angle + 0.8, 0.18) & shell, palette[1]
    )
    plan.room(shell)
    return shell


def dress_cave(plan, center, cells, kind):
    dry = cells & plan.floor - plan.routes - plan.structure - plan.water
    if kind in ("sump", "chasm", "geode"):
        pool = find_pool(
            plan, dry, 44 if kind == "chasm" else SHALLOW_WATER, deep=kind == "sump"
        )
        if pool:
            pond_center, pond = pool
            dry -= pond
            plan.mist(pond_center, 5.2, (0.41, 0.62, 0.69))
    if not dry:
        return
    sides = dry - erode(dry, 2)
    anchor = plan.rng.choice(sorted(sides))
    group = CAVE_GROUPS[
        {
            "mouth": 0,
            "squeeze": 2,
            "gallery": plan.rng.randrange(len(CAVE_GROUPS)),
            "sump": 1,
            "geode": 1,
            "chasm": 3,
        }[kind]
    ]
    prop_group(plan, group, sides, anchor)
    ribs = sides - plan.occupied
    if kind != "mouth" and ribs:
        shelf = plan.rng.choice(sorted(ribs))
        # Pins of stone are placed at a room's side, leaving marked tunnels clear.
        for index, xy in enumerate(
            sorted(oval(shelf, 2.7, 1.4, plan.rng.random() * pi) & ribs)
        ):
            if index < 5 and width_at(xy, cells) < 4:
                plan.prop(xy, "stalagnate_column", on_route=False)
    detail_patch(plan, dry, "ov_guano_droppings", 2)
    if kind in ("chasm", "squeeze"):
        detail_patch(plan, dry, "ov_spider_web", 3)
        detail_patch(plan, dry, "ov_sulfur_cracks", 2)
    source = min(dry, key=lambda xy: hypot(xy[0] - center[0], xy[1] - center[1]))
    plan.d.overlays[source] = "ov_glow_shrooms"
    plan.light(source, 91 if kind == "squeeze" else 146, (0.46, 0.57, 0.96))
    if kind in ("gallery", "sump"):
        plan.mist(source, 4.0, (0.38, 0.54, 0.69), 0.32)
