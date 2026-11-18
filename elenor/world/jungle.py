"""Route planning and hydrology for the jungle campaign."""

from collections import deque
from dataclasses import dataclass
from heapq import heappop, heappush
from math import cos, hypot, pi, sin, tau
import random

from elenor.entities.objects import SOLID_INTERACTABLE_KINDS
from elenor.config import (
    DEEP_WATER,
    FALLEN_LOG,
    MAP_COLS,
    MAP_ROWS,
    PEBBLE_SHORE,
    PIER,
    SHALLOW_WATER,
)
from elenor.world.jungle_sites import (
    CARDINAL,
    LayoutError,
    Plan,
    axis_frame,
    axis_rect,
    build_temple,
    cave_chamber,
    detail_patch,
    dilate,
    dress_cave,
    dress_glade,
    entrance,
    erode,
    mirror_vault,
    neighbors,
    offset,
    oval,
    village,
)

WIDTH, HEIGHT = MAP_COLS * 3, MAP_ROWS * 3
Point = tuple[int, int]


def distance(a, b):
    return hypot(a[0] - b[0], a[1] - b[1])


def smoothstep(t):
    return t * t * (3 - 2 * t)


def component(start, allowed):
    members = {start}
    queue = deque([start])
    while queue:
        for step in neighbors(queue.popleft()):
            if step in allowed and step not in members:
                members.add(step)
                queue.append(step)
    return members


class Relief:
    """Layered value noise shared by vegetation, drainage and route costs."""

    def __init__(self, rng, width, height):
        self.layers = []
        for scale, weight in ((34, 0.65), (13, 0.25), (6, 0.10)):
            values = [
                [rng.random() for _ in range(width // scale + 2)]
                for _ in range(height // scale + 2)
            ]
            self.layers.append((scale, weight, values))

    def at(self, x, y):
        height = 0.0
        for scale, weight, values in self.layers:
            gx, tx = divmod(x, scale)
            gy, ty = divmod(y, scale)
            u, v = smoothstep(tx / scale), smoothstep(ty / scale)
            a, b = values[gy][gx : gx + 2]
            c, d = values[gy + 1][gx : gx + 2]
            height += weight * ((a + (b - a) * u) * (1 - v) + (c + (d - c) * u) * v)
        return height

    def raster(self, width, height):
        return [[self.at(x, y) for x in range(width)] for y in range(height)]


def surface_background(plan, relief, region):
    """Contiguous stands occupy all space outside explicitly opened ground."""
    ridge = []
    limit = plan.rng.randint(94, 122)
    for y, line in enumerate(relief):
        row = plan.d.grid[y]
        bluff = round(15 * sin(y / 29 + limit))
        for x, height in enumerate(line):
            if height > 0.71:
                tile = 17
            elif region == "bone" and x > limit + bluff:
                if height < 0.29:
                    tile = (51, 52, 53)[min(2, int(height * 11))]
                else:
                    tile = 57 if height > 0.5 else 56
            elif region == "ruins" and x > limit + bluff and height > 0.55:
                tile = 36 if height > 0.64 else 20
            elif height < (0.55 if region == "marsh" else 0.37):
                tile = 22
            else:
                tile = 21
            row[x] = tile
            if height > 0.62:
                ridge.append((x, y))
    return set(ridge)


def cubic(start, end, first, second, t):
    remaining = 1 - t
    return tuple(
        remaining**3 * a
        + 3 * remaining**2 * t * b
        + 3 * remaining * t * t * c
        + t**3 * d
        for a, b, c, d in zip(start, first, second, end)
    )


def curve(plan, start, end, bend, *, bias: float = 1):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = max(1, distance(start, end))
    normal_x, normal_y = -dy / length, dx / length
    first = (
        start[0] + dx * 0.32 + normal_x * bend,
        start[1] + dy * 0.32 + normal_y * bend,
    )
    second = (
        start[0] + dx * 0.71 + normal_x * bend * bias,
        start[1] + dy * 0.71 + normal_y * bend * bias,
    )
    steps = max(2, round(length * 2 + abs(bend)))
    points = []
    previous = None
    for i in range(steps + 1):
        x, y = cubic(start, end, first, second, i / steps)
        point = round(x), round(y)
        if not plan.inside(point) or point == previous:
            continue
        if previous and point[0] != previous[0] and point[1] != previous[1]:
            points.append((point[0], previous[1]))
        points.append(point)
        previous = point
    return points


def search_path(plan, start, end, avoid, relief, wanted):
    """Repair a curve when a riverbank or a reserved landmark intercepts it."""
    wanted = set(wanted)
    queue = [(distance(start, end), 0.0, start)]
    previous = {}
    cost = {start: 0.0}
    while queue:
        _, score, point = heappop(queue)
        if point == end:
            path = [point]
            while point != start:
                point = previous[point]
                path.append(point)
            return path[::-1]
        if score > cost[point]:
            continue
        for step in neighbors(point):
            if step in avoid or not plan.inside(step):
                continue
            x, y = step
            elevation = relief[y][x] if relief else 0.4
            deviation_penalty = 0 if step in wanted else 0.25
            base = 0.83 if step in plan.routes else (1.06 + elevation * elevation * 1.2)
            candidate = score + base + deviation_penalty
            if candidate < cost.get(step, float("inf")):
                cost[step] = candidate
                previous[step] = point
                # Distance favours natural diagonals while expansion preserves cardinal paths.
                heappush(
                    queue, (candidate + distance(step, end) * 1.12, candidate, step)
                )
    return []


def path_curve(plan, start, end, avoid, relief, *, allow_repair=True):
    length = distance(start, end)
    side = plan.rng.choice((-1, 1))
    bend = side * min(length * 0.33, plan.rng.uniform(5, 22))
    wanted = curve(plan, start, end, bend, bias=plan.rng.uniform(-1.1, 1.2))
    for path in (
        wanted,
        curve(plan, start, end, -bend, bias=0.8),
        curve(plan, start, end, bend * 0.36),
    ):
        if (
            path
            and path[0] == start
            and path[-1] == end
            and not avoid.intersection(path)
        ):
            return path
    if allow_repair:
        return search_path(plan, start, end, avoid, relief, wanted)
    return []


def trail(plan, points, tile, *, avoid=None, main=True, underground=False):
    if avoid is None:
        avoid = set()
    shape = set()
    center = len(points) // 2
    phase = plan.rng.uniform(0, tau)
    rest = plan.rng.choice((center, max(1, center // 2)))
    for index, (x, y) in enumerate(points):
        wave = 0.5 + 0.5 * sin(index * 0.16 + phase)
        if underground:
            width = (1.1 if main else 0.9) + (0.75 if main else 0.32) * wave
        else:
            width = 1.48 + 0.61 * wave
            if main and abs(index - rest) < 7:
                width += (1 - abs(index - rest) / 7) * 0.72
        limit = int(width) + 1
        for ry in range(y - limit, y + limit + 1):
            for rx in range(x - limit, x + limit + 1):
                if (rx - x) ** 2 + (ry - y) ** 2 <= width * width:
                    shape.add((rx, ry))
    trail_tiles = shape - avoid - plan.water - plan.structure - plan.bridges
    plan.paint(trail_tiles, tile)
    plan.routes.update(trail_tiles)
    plan.routes.update(set(points) & plan.bridges)
    return trail_tiles


def lake_shape(plan, relief):
    low_points = [(x, y) for x in range(94, 153, 8) for y in range(31, 96, 7)]
    plan.rng.shuffle(low_points)
    center = min(low_points[:19], key=lambda point: relief[point[1]][point[0]])
    orientation = plan.rng.uniform(0, pi)
    basin = oval(
        center,
        plan.rng.randint(14, 26),
        plan.rng.randint(9, 15),
        orientation,
        0.28,
        plan.rng.random() * tau,
    )
    ox = round(cos(orientation) * 17)
    oy = round(sin(orientation) * 17)
    bay = oval(
        (center[0] + ox, center[1] + oy),
        12,
        7,
        orientation + 0.7,
        0.19,
        plan.rng.random() * tau,
    )
    return {point for point in basin | bay if point[0] >= 71}


def river_shape(plan, relief):
    start_x = plan.rng.randint(89, 123)
    lower_x = plan.rng.randint(85, 128)
    bend = plan.rng.choice((-1, 1)) * plan.rng.randint(16, 43)
    elevation = min(range(62, 137), key=lambda x: relief[44][x])
    # Control points pull the stream across several different bands of the valley.
    first = (
        max(87, min(125, start_x + bend * 0.6 + (elevation - start_x) * 0.4)),
        plan.rng.randint(16, 39),
    )
    second = max(88, min(127, lower_x - bend)), plan.rng.randint(81, 108)
    river = set()
    phase = plan.rng.uniform(0, tau)
    for i in range(HEIGHT * 2 + 1):
        t = i / (HEIGHT * 2)
        x, y = cubic((start_x, 0), (lower_x, HEIGHT - 1), first, second, t)
        radius = (
            3.7 + 2.65 * (0.5 + 0.5 * sin(t * 9 + phase)) + 0.9 * cos(t * 19 - phase)
        )
        river.update(oval((round(x), round(y)), radius, radius))
    if plan.rng.random() < 0.5:
        x, y = cubic((start_x, 0), (lower_x, HEIGHT - 1), first, second, 0.58)
        # Cut a backwater off the active current, with a wider landing area.
        bay = oval(
            (round(x) + plan.rng.choice((-7, 7)), round(y)), 14, 7, 0.8, 0.24, phase
        )
        river.update(bay)
    # A reach downstream of the bend has enough flooded area for a bar.
    t = plan.rng.uniform(0.4, 0.61)
    x, y = cubic((start_x, 0), (lower_x, HEIGHT - 1), first, second, t)
    eddy = round(x), round(y)
    river.update(oval(eddy, 10, 12, 0.12, 0.15, phase))
    bar = oval(
        eddy, plan.rng.uniform(2.4, 3.4), plan.rng.uniform(4, 6), 0.15, 0.22, phase
    )
    return river, bar


def shore_finish(plan, wet, deep, relief):
    plan.paint(wet - deep, SHALLOW_WATER)
    plan.paint(deep, DEEP_WATER, walk=False)
    plan.water.update(wet)
    bank = dilate(wet, 2) - wet
    outer = bank - dilate(wet)
    dry = {xy for xy in bank if plan.inside(xy)}
    for x, y in dry:
        elevation = relief[y][x]
        if elevation < 0.37:
            tile = 42 if (x, y) in outer else 41
        elif elevation > 0.64:
            tile = PEBBLE_SHORE
        else:
            tile = 25 if (x, y) in outer else 41
        plan.paint({(x, y)}, tile)
    border = dilate(wet, 2) - dilate(wet)
    detail_patch(plan, border & plan.floor, "ov_shells_starfish", 11)
    detail_patch(plan, (wet - deep) & plan.floor, "ov_water_lily", 11)
    detail_patch(plan, (wet - deep) & plan.floor, "ov_duckweed", 13)
    detail_patch(plan, wet - deep, "ov_shore_foam", 10, radius=(2, 4))
    detail_patch(plan, deep, "ov_fish_shadows", 9, radius=(2, 4))
    detail_patch(plan, wet - deep, "ov_bobber_ripples", 6, radius=(1, 2))
    for x, y in plan.rng.sample(sorted(wet), min(8, len(wet))):
        plan.mist((x, y), plan.rng.uniform(3.6, 7))


def river_crossings(plan, wet, island):
    """Place crossings in separate reaches before any land routes are planned."""
    channel = {}
    for x, y in wet:
        left, right = channel.get(y, (x, x))
        channel[y] = min(x, left), max(x, right)
    landings = []
    ford_rows = [plan.rng.randint(14, 25), plan.rng.randint(96, 109)]
    if plan.rng.random() < 0.73:
        ford_rows.insert(1, sorted(y for _, y in island)[len(island) // 2])
    for y in ford_rows:
        width = plan.rng.choice((3, 4))
        for row in range(y - 1, y - 1 + width):
            left, right = channel[row]
            sand = {(x, row) for x in range(left - 3, right + 4)}
            shallows = sand & wet & plan.water
            bottleneck = {(x, row) for x in range(left, right + 1)}
            plan.paint(sand - shallows, PEBBLE_SHORE)
            plan.paint(shallows, SHALLOW_WATER)
            plan.bridges.update(sand)
            plan.routes.update(bottleneck)
            for point in sorted(shallows):
                if plan.rng.random() < 0.12:
                    plan.d.overlays[point] = "ov_water_lily"
        left, right = channel[y]
        landings.extend(((left - 2, y), (right + 2, y)))

    bands = [range(32, 45), range(78, 91)]
    plan.rng.shuffle(bands)
    suitable = [
        y
        for band in bands
        for y in band
        if all(abs(y - ford) >= 8 for ford in ford_rows)
    ]
    row = min(suitable, key=lambda y: channel[y][1] - channel[y][0])
    left, right = channel[row]
    trunk = {(x, row) for x in range(left - 1, right + 2)}
    bank = {(x, row) for x in (left - 2, left - 1, right + 1, right + 2)}
    plan.paint(bank, PEBBLE_SHORE)
    plan.paint(trunk, FALLEN_LOG)
    plan.bridges.update(trunk | bank)
    plan.routes.update(trunk | bank)
    plan.light((left - 2, row), 63, (0.4, 0.62, 0.58))
    landings.extend(((left - 2, row), (right + 2, row)))
    plan.crossing_approaches = list(zip(landings[::2], landings[1::2]))
    return landings


@dataclass
class Landing:
    bank: Point
    lip: Point
    direction: Point
    profile: str
    wet_length: int


def landing_candidates(plan, wet, deep):
    for bank in sorted(dilate(wet) - wet):
        if not plan.inside(bank, 9) or bank in plan.bridges:
            continue
        for direction in CARDINAL:
            if any(offset(bank, direction, -step) in wet for step in range(1, 6)):
                continue
            for reach in (1, 2, 3):
                lip = offset(bank, direction, reach)
                next_cell = offset(lip, direction)
                after = offset(lip, direction, 3)
                if next_cell not in wet - deep or after not in deep:
                    continue
                if all(
                    offset(bank, direction, step) in wet for step in range(1, reach + 1)
                ):
                    yield Landing(bank, lip, direction, "eddy", reach)
                    break


def build_landing(plan, landing):
    direction = landing.direction
    point = axis_frame(landing.bank, direction)
    shore = oval(point(-3), 6, 5, roughness=0.14, phase=plan.rng.random() * tau)
    plan.clearing(shore, PEBBLE_SHORE)
    plan.routes.update({point(step) for step in range(-5, 0)})
    reach = landing.wet_length
    stem = axis_rect(point, -1, reach, 0, 1)
    style = plan.rng.choice(("jetty", "platform", "elbow"))
    if style == "platform":
        stem.update(axis_rect(point, max(0, reach - 1), reach, -2, 2))
    elif style == "elbow":
        stem.update(axis_rect(point, -1, 0, -3, 1))
    painted = plan.paint(stem, PIER)
    plan.bridges.update(painted)
    plan.routes.update(painted)
    for side in range(-2, 3):
        edge = point(reach, side)
        if (
            edge in painted
            and point(reach + 1, side) in plan.water
            and plan.tile(point(reach + 1, side)) == SHALLOW_WATER
            and plan.tile(point(reach + 3, side)) == DEEP_WATER
        ):
            plan.d.fishing_edges[edge] = landing.profile
    plan.lamp(point(-2), 152)
    plan.mist(point(reach + 3), 5.4)
    # Dry cabinets, racks and the hauled-up boat are distributed around the
    # landing's actual bank, where curved shores leave different usable feet.
    available = (shore & plan.floor) - plan.water - plan.occupied - dilate(plan.routes)
    bank_side = plan.rng.choice((-1, 1))
    fixtures = (
        ("prop_reeds_tall", point(0, bank_side * 3)),
        ("prop_wooden_rowboat", point(-1, bank_side * 4)),
        ("prop_fishing_rod_stand", point(-1, -bank_side * 2)),
        ("prop_fish_trap_net", point(-3, bank_side * 3)),
        ("prop_fisherman_stool", point(-3, -bank_side * 3)),
        ("prop_tackle_box", point(-4, -bank_side * 3)),
        ("prop_fish_drying_line", point(-5, bank_side * 3)),
        ("prop_bait_bucket", point(-4, bank_side * 2)),
    )
    for kind, anchor in fixtures:
        if not available:
            break
        position = min(available, key=lambda xy: (distance(xy, anchor), xy))
        if plan.prop(position, kind):
            available.remove(position)
    return point(-4)


def waterfront(plan, relief):
    mode = plan.rng.choice(("river", "river", "lake"))
    if mode == "lake":
        wet_area, island = lake_shape(plan, relief), set()
    else:
        wet_area, island = river_shape(plan, relief)
    wet = {point for point in wet_area if plan.inside(point)}
    deep = erode(wet, 2) - dilate(island)
    shore_finish(plan, wet, deep, relief)
    if island:
        plan.paint(island, 25)
        plan.water.difference_update(island)
        detail_patch(plan, island, "ov_duckweed", 2, radius=(1, 2))
    shore_nodes = river_crossings(plan, wet, island) if mode == "river" else []
    deep = {point for point in deep if plan.tile(point) == DEEP_WATER}
    wet = plan.water - plan.bridges
    walkable_land = {
        (x, y) for y in range(1, HEIGHT - 1) for x in range(1, WIDTH - 1)
    } - wet
    mainland = component((2, HEIGHT // 2), walkable_land)
    candidates = [
        landing
        for landing in landing_candidates(plan, wet, deep)
        if landing.bank in mainland
        and offset(landing.bank, landing.direction, -4) in mainland
    ]
    plan.rng.shuffle(candidates)
    ports = []
    for landing in candidates:
        if any(distance(landing.bank, port.bank) < 29 for port in ports):
            continue
        if any(distance(landing.bank, foot) < 14 for foot in shore_nodes):
            continue
        ports.append(landing)
        if len(ports) == (3 if mode == "river" else 2):
            break
    if not ports:
        ports = candidates[:1]
    for landing, profile in zip(
        ports, plan.rng.sample(["snag", "eddy", "current"], len(ports))
    ):
        landing.profile = profile
        shore = build_landing(plan, landing)
        shore_nodes.append(shore)
        plan.landing_approaches.add(shore)
    return shore_nodes


def feature_lot(plan, center, facing, kind):
    point = axis_frame(center, facing)
    if kind == "vault":
        return axis_rect(point, 1, 21, -6, 6)
    return axis_rect(point, 3, 29, -15, 15)


def region_for(d, rng):
    if d.floor_num == 1:
        return "grove"
    return rng.choice(("marsh", "marsh", "bone", "ruins", "grove"))


def mark_trail(plan, path, ground):
    if not ground or len(path) < 18:
        return
    # Gravel and tiny blooms mark stretches or shoulders, without a repeated checker.
    for index in range(7, len(path) - 4, 17):
        center = path[index]
        rim = sorted({point for point in ground if 1.4 < distance(point, center) < 4})
        if rim:
            detail_patch(plan, set(rim), "ov_pebbles", 1, radius=(1, 2), density=0.52)
        if index % 3 == 1 and center in plan.floor:
            plan.d.overlays[center] = "ov_flowers_blue"
            plan.light(center, 77, (0.42, 0.62, 0.66))


def cut_through(plan, points, biome, avoid, *, natural):
    """Scrub still covers the walkable gap. Only game trails expose bits of dirt."""
    if not points:
        return
    grass = {"bone": 45, "marsh": 23, "ruins": 10, "grove": 10}[biome]
    mud = 46 if biome == "bone" else 11
    sides = plan.rng.choice((-1, 1))
    phase = plan.rng.uniform(0, tau)
    for i, point in enumerate(points):
        patch = {point}
        if natural and (i % 7 in (1, 2, 3)):
            patch.update(oval(point, 2.1, 1.55, phase, 0.16, phase))
        elif not natural and i % 9 in (2, 3, 4) and i + 1 < len(points):
            following = points[i + 1]
            dx, dy = following[0] - point[0], following[1] - point[1]
            patch.add((point[0] + dy * sides, point[1] - dx * sides))
        patch = {
            tile
            for tile in patch
            if tile not in avoid
            and tile not in plan.routes
            and tile not in plan.water
            and tile not in plan.structure
        }
        exposed = not natural and sin(i * 0.34 + phase) > 0.27
        plan.routes.update(plan.paint(patch, mud if exposed else grass))
    if natural:
        beacon = points[min(len(points) - 1, max(2, len(points) // 2))]
        if beacon in plan.floor - plan.water:
            plan.d.overlays[beacon] = "ov_glow_shrooms"
            plan.light(beacon, 93, (0.35, 0.63, 0.69))


def facade_lot(center, facing, kind, compact):
    point = axis_frame(center, facing)
    if kind == "temple":
        flank = 7 if compact else 10
        return axis_rect(point, -5, 13, -8, 8) | axis_rect(
            point, 14, 20 if compact else 25, -flank, flank
        )
    angle = 0 if facing[0] else pi / 2
    radius = (9.8, 8.55) if compact else (14.7, 12.2)
    return oval(point(15), *radius, angle) | oval(point(2), 12.2, 8.55, angle)


def build_facade(plan, center, kind, facing, compact, lot):
    entrance(plan, center, kind, facing, compact)
    point = axis_frame(center, facing)
    ramp = axis_rect(point, -12, 0, 0, 1)
    plan.paint(ramp, 24 if kind == "temple" else 11)
    plan.routes.update(ramp)
    plan.structure.update(lot | ramp)
    return point(-12)


def place_facade(plan, kind, north):
    """Local lot search. Both banks have room outside the river's floodplain."""
    candidates = [
        (x, y)
        for x in range(125, 175, 5)
        for y in (range(16, 49, 4) if north else range(76, 111, 4))
    ]
    plan.rng.shuffle(candidates)
    forbidden = plan.water | plan.structure | plan.bridges | plan.floor
    for compact in (False, True):
        for center in candidates:
            if center in forbidden:
                continue
            facing_options = list(CARDINAL)
            plan.rng.shuffle(facing_options)
            for facing in facing_options:
                lot = facade_lot(center, facing, kind, compact)
                point = axis_frame(center, facing)
                layout = lot | axis_rect(point, -13, 0, 0, 1)
                if layout & forbidden or not all(
                    plan.inside(tile, 3) for tile in layout
                ):
                    continue
                return build_facade(plan, center, kind, facing, compact, lot)
    center = (164, 31 if north else 95)
    facing = (1, 0)
    lot = facade_lot(center, facing, kind, True)
    return build_facade(plan, center, kind, facing, True, lot)


def glade_sites(plan, relief, region, ridge):
    rng = plan.rng
    chosen = []
    blocked = dilate(plan.structure | plan.water | plan.occupied | plan.bridges, 2)
    candidates = [(x, y) for x in range(13, WIDTH - 13) for y in range(13, HEIGHT - 13)]
    rng.shuffle(candidates)
    target = rng.randint(8, 12)
    for center in candidates:
        if center in blocked:
            continue
        rx, ry = rng.randint(7, 14), rng.randint(6, 11)
        angle = rng.uniform(0, pi)
        footprint = oval(center, rx, ry, angle, 0.22, rng.random() * tau)
        if len(footprint & blocked) > len(footprint) * 0.16:
            continue
        scenic = center[0] > 90 or (
            region == "marsh" and relief[center[1]][center[0]] < 0.42
        )
        biome = region if scenic else "grove"
        if (
            biome == "grove"
            and relief[center[1]][center[0]] < 0.35
            and center not in ridge
        ):
            biome = "marsh"
        chosen.append((center, footprint - blocked, biome))
        blocked.update(dilate(footprint, 4))
        if len(chosen) >= target:
            break
    return chosen


def connect_to_route(
    plan, destination, entries, avoid, relief, biome, *, natural=False
):
    """Nearby gateways are preferred. Search can route around a wide meander."""
    starts = sorted(entries, key=lambda point: distance(point, destination))
    for source in starts[:4]:
        path = path_curve(plan, source, destination, avoid, relief, allow_repair=False)
        if path:
            break
    else:
        source = starts[0]
        path = search_path(plan, source, destination, avoid, relief, ())
    if path:
        cut_through(plan, path, biome, avoid, natural=natural)
    return bool(path)


def solid_fixtures(plan):
    return {
        (x, y) for x, y, kind in plan.d.jungle_props if kind in SOLID_INTERACTABLE_KINDS
    }


def join_access(plan, start, destinations, biome):
    """Fix only the approach to a disconnected feature, pursuing the nearest open route."""
    solid = solid_fixtures(plan)
    avoid = (plan.water - plan.floor) | (plan.structure - plan.floor) | solid
    reached = component(start, plan.floor - solid)
    for target in sorted(destinations):
        if target in reached:
            continue
        queue = deque([target])
        previous = {target: None}
        while queue:
            tail = queue.popleft()
            if tail in reached:
                path = [tail]
                while path[-1] != target:
                    path.append(previous[path[-1]])
                cut_through(plan, path, biome, avoid, natural=True)
                reached = component(start, plan.floor - solid)
                break
            for point in neighbors(tail):
                if point not in previous and point not in avoid and plan.inside(point):
                    previous[point] = tail
                    queue.append(point)


def gateway(plan, side, y, action):
    x = 2 if side == "west" else WIDTH - 3
    boundary = 0 if side == "west" else WIDTH - 1
    for yy in range(y - 1, y + 2):
        for xx in range(min(x, boundary), max(x, boundary) + 1):
            plan.d.grid[yy][xx] = 12
            if xx == boundary:
                plan.d.invisible_bounds.add((xx, yy))
    plan.feature((x, y), action, "notice_board")
    plan.lamp((x, y), 108)


def surface(plan, relief):
    region = region_for(plan.d, plan.rng)
    ridge = surface_background(plan, relief, region)
    waterfront(plan, relief)
    start = (plan.rng.randint(12, 17), plan.rng.randint(24, HEIGHT - 25))
    hearth = (
        plan.rng.randint(43, 47),
        max(25, min(HEIGHT - 26, start[1] + plan.rng.randint(-17, 17))),
    )
    west_gate, east_gate = village(plan, hearth, (1, 0))
    north = bool(plan.rng.getrandbits(1))
    temple_gate = place_facade(plan, "temple", north)
    cave_gate = place_facade(plan, "cave", not north)
    end = WIDTH - 3, plan.rng.randint(18, HEIGHT - 19)
    entry = 2, start[1]
    gates = {west_gate, east_gate, temple_gate, cave_gate}
    impassable = (plan.water - plan.bridges) | (plan.structure - gates) | plan.occupied
    main = set()
    for first, last in (
        (start, west_gate),
        (east_gate, temple_gate),
        (temple_gate, end),
    ):
        points = path_curve(plan, first, last, impassable, relief)
        main.update(trail(plan, points, 12, avoid=impassable))
        main.update((first, last))
        mark_trail(plan, points, main)
    landmark_entries = main
    for bank_side in zip(*plan.crossing_approaches):
        sorted_bank = sorted(bank_side, key=lambda point: point[1])
        dry_avoid = impassable | plan.water
        for first, last in zip(sorted_bank, sorted_bank[1:]):
            bank_path = path_curve(plan, first, last, dry_avoid, relief)
            cut_through(plan, bank_path, region, dry_avoid, natural=False)
        nearest = min(
            sorted_bank, key=lambda point: min(distance(point, route) for route in main)
        )
        connect_to_route(plan, nearest, main, dry_avoid, relief, region)
    if plan.d.floor_num > 1:
        cut_through(
            plan,
            path_curve(plan, start, entry, impassable, relief),
            region,
            impassable,
            natural=False,
        )
    connect_to_route(plan, cave_gate, landmark_entries, impassable, relief, region)

    # Each landing has a dry starting tile; the shore and pier already exist.
    for bank in sorted(plan.landing_approaches):
        connect_to_route(plan, bank, landmark_entries, impassable, relief, region)
    for index, (center, footprint, biome) in enumerate(
        glade_sites(plan, relief, region, ridge)
    ):
        natural = index % 3 != 0
        if connect_to_route(
            plan, center, landmark_entries, impassable, relief, biome, natural=natural
        ):
            dress_glade(plan, center, footprint, biome)
    meadow = oval(start, 8, 7, 0.35, 0.18)
    dress_glade(plan, start, meadow, "grove")
    clearing = (
        plan.floor - plan.routes - plan.occupied - plan.water - plan.structure
    ) & meadow
    if clearing:
        point = min(clearing, key=lambda point: distance(point, start))
        plan.prop(point, "campfire")
        plan.lamp(point, 112)
    gateway(plan, "east", end[1], "forward")
    if plan.d.floor_num > 1:
        gateway(plan, "west", entry[1], "back")
    ends = {point for crossing in plan.crossing_approaches for point in crossing}
    targets = plan.d.passages.keys() | plan.d.fishing_edges.keys() | ends
    join_access(plan, start, targets, region)
    optional_vault(plan, temple_gate, start)
    return start


def bedrock(plan, relief, kind):
    for y, line in enumerate(relief):
        for x, altitude in enumerate(line):
            if kind == "temple":
                stone = 19 if altitude < 0.53 else 35
            elif altitude < 0.34:
                stone = 54
            elif altitude > 0.69:
                stone = 55
            elif altitude > 0.51:
                stone = 34
            else:
                stone = 7
            plan.d.grid[y][x] = stone


def optional_vault(plan, focus, start):
    if plan.rng.random() >= plan.d.puzzle_chance:
        return
    edges = (plan.floor - erode(plan.floor) - plan.water - plan.occupied) & component(
        start, plan.floor - solid_fixtures(plan)
    )
    choices = sorted(edges, key=lambda point: (distance(point, focus), point))
    for center in choices:
        # Find a wall face with enough unexcavated rock to hold the entire branch.
        normals = list(CARDINAL)
        plan.rng.shuffle(normals)
        for facing in normals:
            if offset(center, facing) in plan.floor:
                continue
            lot = feature_lot(plan, center, facing, "vault")
            if not lot & (plan.floor | plan.water | plan.structure) and all(
                plan.inside(point, 2) for point in lot
            ):
                mirror_vault(plan, center, facing)
                return


def temple(plan):
    facing = plan.rng.choice(CARDINAL)
    if facing[0]:
        origin = (
            plan.rng.randint(22, 31) if facing[0] > 0 else plan.rng.randint(161, 175),
            plan.rng.randint(48, 78),
        )
    else:
        origin = (
            plan.rng.randint(51, 143),
            plan.rng.randint(13, 22) if facing[1] > 0 else plan.rng.randint(103, 113),
        )
    start, axis = build_temple(plan, origin, facing)
    optional_vault(plan, axis(24), start)
    return start


def cave_nodes(plan):
    """Follow a fault with alternate pockets and short subsidiary passages."""
    y = plan.rng.randint(44, 76)
    start = plan.rng.randint(17, 24), y
    points = [start]
    folded = plan.rng.random() < 0.42
    for index in range(1, 7):
        if folded:
            motion = ((28, -22), (35, -9), (39, 13), (15, 28), (-23, 24), (-31, 6))[
                index - 1
            ]
            dx, dy = (step + plan.rng.randint(-6, 6) for step in motion)
        else:
            dx = plan.rng.randint(19, 29)
            dy = plan.rng.choice((-1, 1)) * plan.rng.randint(6, 21)
        x = min(WIDTH - 17, points[-1][0] + dx)
        y = max(19, min(HEIGHT - 20, y + dy))
        points.append((x, y))
    if plan.rng.random() < 0.5:
        points = [(WIDTH - 1 - x, y) for x, y in points]
    return points


def cave_spurs(plan, points):
    branches = []
    for index in plan.rng.sample(range(1, len(points) - 1), 4):
        x, y = points[index]
        directions = [-1, 1]
        plan.rng.shuffle(directions)
        for side in directions:
            fork = x + plan.rng.randint(-14, 14), y + side * plan.rng.randint(20, 35)
            if plan.inside(fork, 14) and all(
                distance(fork, point) > 17 for point in points + branches
            ):
                branches.append(fork)
                yield points[index], fork
                break


def caves(plan):
    points = cave_nodes(plan)
    spurs = list(cave_spurs(plan, points))
    rooms = []
    kinds = ["mouth", "squeeze", "geode", "chasm", "gallery", "sump", "gallery"]
    middle = kinds[1:-1]
    plan.rng.shuffle(middle)
    kinds[1:-1] = middle
    for center, kind in zip(points, kinds):
        vein = offset(center, plan.rng.choice(CARDINAL), 5)
        rooms.append((center, cave_chamber(plan, center, vein, kind), kind))
    for _, fork in spurs:
        kind = plan.rng.choice(("squeeze", "sump", "geode", "gallery"))
        rooms.append(
            (fork, cave_chamber(plan, fork, offset(fork, (0, 1), 4), kind), kind)
        )
    for start, end in zip(points, points[1:]):
        path = path_curve(plan, start, end, set(), None)
        trail(plan, path, 8, underground=True)
    for start, end in spurs:
        path = path_curve(plan, start, end, set(), None)
        trail(plan, path, 50, main=False, underground=True)
        # Some branches loop back to another chamber, with the rest ending in niches.
        candidate = min(
            (point for point in points if point != start),
            key=lambda point: distance(point, end),
        )
        if distance(end, candidate) < 35 and plan.rng.random() < 0.55:
            second = path_curve(plan, end, candidate, set(), None)
            trail(plan, second, 8, main=False, underground=True)
    start = points[0]
    threshold = offset(start, (-1, 0), 5)
    trail(plan, path_curve(plan, start, threshold, set(), None), 8, underground=True)
    plan.feature(threshold, "up", "door_open")
    for center, cells, kind in rooms:
        dress_cave(plan, center, cells, kind)
    plan.light(threshold, 105, (0.63, 0.76, 0.79))
    plan.prop(points[-1], "chest", on_route=True)
    optional_vault(plan, points[-1], start)
    return start


def validate_floor(plan, start):
    d = plan.d
    solid = solid_fixtures(plan)
    locked = {position for position, door in d.doors.items() if door.locked}
    reachable = component(start, plan.floor - solid - locked)
    if (d.passages.keys() | d.fishing_edges.keys()) - reachable:
        raise LayoutError("A passage or fishing landing became inaccessible")
    if not d.interior:
        if any(
            point not in reachable
            for pair in plan.crossing_approaches
            for point in pair
        ):
            raise LayoutError("A river crossing needs two reachable approaches")
        if not d.fishing_edges:
            raise LayoutError("No usable landing")
        if len(plan.hut_entries) < 3 or plan.hut_entries - reachable:
            raise LayoutError("The village needs three or more accessible huts")
    info = d.mirror_puzzle_info
    if d.interior:
        reward_tiles = {
            (x, y)
            for x, y, kind in d.jungle_props
            if kind == "chest"
            and (not info or not info["sealed_rect"].collidepoint(x, y))
        }
        if not reward_tiles or reward_tiles - reachable:
            raise LayoutError("The main underground reward needs a walkable approach")
    if info and (
        info["entry_door"] not in reachable
        or info["sealed_rect"].center in reachable
        or info["sealed_rect"].center not in component(start, plan.floor - solid)
    ):
        raise LayoutError("The mirror vault must have a single accessible gate")


def generate_jungle_floor(dungeon):
    """Keep the campaign's public transitions, state and fishing interfaces."""
    rng = random.Random(random.getrandbits(64))
    dungeon.jungle_props = []
    dungeon.grid = [[21] * WIDTH for _ in range(HEIGHT)]
    plan = Plan(dungeon, rng)
    relief = Relief(rng, WIDTH, HEIGHT).raster(WIDTH, HEIGHT)
    if dungeon.interior:
        bedrock(plan, relief, dungeon.interior)
        start = temple(plan) if dungeon.interior == "temple" else caves(plan)
    else:
        start = surface(plan, relief)
    validate_floor(plan, start)
    dungeon.start_pos = start
