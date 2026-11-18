"""Route planning and hydrology for the jungle campaign."""

from collections import deque
from dataclasses import dataclass
from heapq import heappop, heappush
from math import cos, hypot, pi, sin, tau
import random

from elenor.entities.objects import SOLID_INTERACTABLE_KINDS
from elenor.config import (
    DEEP_WATER,
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


@dataclass
class Site:
    center: Point
    kind: str
    radius: tuple[int, int]
    angle: float
    lot: set[Point] | None = None
    facing: Point = (1, 0)


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
            width = (2.0 if main else 1.26) + (1.04 if main else 0.66) * wave
            if main and abs(index - rest) < 7:
                width += (1 - abs(index - rest) / 7) * 2.1
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
    low_points = [(x, y) for x in range(55, 151, 8) for y in range(31, 96, 7)]
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
    return basin | bay


def river_shape(plan, relief):
    start_x = plan.rng.randint(79, 125)
    lower_x = plan.rng.randint(68, 137)
    bend = plan.rng.choice((-1, 1)) * plan.rng.randint(16, 43)
    elevation = min(range(62, 137), key=lambda x: relief[44][x])
    # Control points pull the stream across several different bands of the valley.
    first = start_x + bend * 0.6 + (elevation - start_x) * 0.4, plan.rng.randint(16, 39)
    second = lower_x - bend, plan.rng.randint(81, 108)
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
    return river


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


def bridge(plan, wet):
    """Find a short crossing of the main channel, with dry abutments at both ends."""
    candidates = []
    for y in range(17, HEIGHT - 17):
        line = sorted(x for x in range(16, WIDTH - 16) if (x, y) in wet)
        if not line or line[-1] - line[0] > 27:
            continue
        left, right = line[0] - 4, line[-1] + 4
        if any(
            (side, y + dy) in wet for side in (left, right) for dy in (-2, -1, 0, 1, 2)
        ):
            continue
        candidates.append((right - left, y, left, right))
    candidates.sort()
    if not candidates:
        return None
    _, y, left, right = plan.rng.choice(candidates[: min(19, len(candidates))])
    cells = {(x, row) for x in range(left, right + 1) for row in range(y - 1, y + 2)}
    plan.bridges.update(cells)
    plan.paint(cells, PIER)
    plan.routes.update(cells)
    crossings = ((left - 2, y), (right + 2, y))
    for bank in crossings:
        plan.clearing(oval(bank, 5, 4, roughness=0.2), PEBBLE_SHORE)
        plan.lamp(bank, 115)
    return crossings


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
    wet_area = lake_shape(plan, relief) if mode == "lake" else river_shape(plan, relief)
    wet = {point for point in wet_area if plan.inside(point)}
    deep = erode(wet, 2)
    shore_finish(plan, wet, deep, relief)
    shore_nodes = []
    if mode == "river":
        feet = bridge(plan, wet)
        if feet:
            shore_nodes.extend(feet)
    candidates = list(landing_candidates(plan, wet, deep))
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
        shore_nodes.append(build_landing(plan, landing))
    return shore_nodes


def feature_lot(plan, center, facing, kind):
    point = axis_frame(center, facing)
    if kind == "vault":
        return axis_rect(point, 1, 21, -6, 6)
    return axis_rect(point, 3, 29, -15, 15)


def free_lot(plan, centers, kind, occupied, forbidden):
    centers = list(centers)
    plan.rng.shuffle(centers)
    facings = list(CARDINAL)
    for center in centers:
        if any(distance(center, other) < 22 for other in occupied):
            continue
        plan.rng.shuffle(facings)
        for facing in facings:
            lot = feature_lot(plan, center, facing, kind)
            if all(plan.inside(point, 3) for point in lot) and not lot & forbidden:
                return Site(center, kind, (9, 7), 0, lot, facing)
    raise LayoutError(f"Cannot reserve a jungle {kind} site")


def region_for(d, rng):
    if d.floor_num == 1:
        return "grove"
    return rng.choice(("marsh", "marsh", "bone", "ruins", "grove"))


def choose_surface_sites(plan, relief, region, ridge, shore_nodes):
    rng = plan.rng
    start = (rng.randint(14, 22), rng.randint(25, HEIGHT - 26))
    village_options = [
        (x, y)
        for x in range(35, 62, 3)
        for y in range(max(22, start[1] - 24), min(HEIGHT - 22, start[1] + 25), 5)
        if (x, y) not in plan.water and distance((x, y), start) >= 24
    ]
    rng.shuffle(village_options)
    settlement = next(
        (point for point in village_options if not (oval(point, 17, 12) & plan.water)),
        None,
    )
    if settlement is None:
        raise LayoutError("No dry lot next to the opening grove")
    sites = [
        Site(
            start, "grove", (rng.randint(9, 13), rng.randint(7, 9)), rng.uniform(0, pi)
        ),
        Site(settlement, "village", (22, 17), rng.uniform(-0.5, 0.5)),
    ]
    reserved = set()
    # Settlement plots never get squeezed between a temple's foundations and a bank.
    protected = set().union(
        *(oval(site.center, *site.radius, site.angle, 0.2) for site in sites)
    )
    forbidden = dilate(plan.water | protected | plan.bridges | set(shore_nodes), 5)
    options = [
        (x, y) for x in range(27, WIDTH - 17, 5) for y in range(15, HEIGHT - 14, 5)
    ]
    for kind in ("temple", "cave"):
        candidates = [xy for xy in options if xy[0] > 63 and xy not in forbidden]
        site = free_lot(plan, candidates, kind, [s.center for s in sites], forbidden)
        sites.append(site)
        lots = site.lot or set()
        reserved.update(lots)
        forbidden.update(dilate(lots | {site.center}, 7))
    if plan.rng.random() < plan.d.puzzle_chance:
        shrine = free_lot(plan, options, "vault", [s.center for s in sites], forbidden)
        sites.append(shrine)
        lots = shrine.lot or set()
        reserved.update(lots)
        forbidden.update(dilate(lots | {shrine.center}, 5))
    # Spread larger clearings apart and let smaller spaces cluster around them.
    candidates = [(x, y) for x in range(13, WIDTH - 13) for y in range(13, HEIGHT - 13)]
    rng.shuffle(candidates)
    clearings = rng.randint(8, 12)
    margins = dilate(reserved, 3)
    for center in candidates:
        if clearings <= 0:
            break
        rx, ry = rng.randint(8, 15), rng.randint(6, 12)
        angle = rng.uniform(0, pi)
        if center in forbidden or any(
            distance(center, other.center) < max(16, rx + other.radius[0] * 0.59)
            for other in sites
        ):
            continue
        if any(distance(center, point) < 13 for point in shore_nodes):
            continue
        scenic = center[0] > 92 or (
            region == "marsh" and relief[center[1]][center[0]] < 0.42
        )
        biome = region if scenic else "grove"
        if biome == "grove" and relief[center[1]][center[0]] < 0.35:
            biome = "marsh"
        opened = oval(center, rx, ry, angle, 0.19)
        if opened & margins or len(opened & plan.water) > len(opened) * 0.12:
            continue
        if center in ridge and biome == "marsh":
            biome = "grove"
        sites.append(Site(center, biome, (rx, ry), angle))
        clearings -= 1
    return sites, reserved


def link_sites(plan, nodes, avoid, relief, *, loops=2):
    """Connect entrances and landmarks, then add short side circuits."""
    joined = {nodes[0]}
    pending = set(nodes[1:]) - joined
    edges = set()
    while pending:
        pairs = sorted((distance(a, b), a, b) for a in joined for b in pending)
        for _, start, end in pairs:
            path = path_curve(plan, start, end, avoid, relief)
            if not path:
                continue
            pavement = trail(plan, path, 12, avoid=avoid)
            mark_trail(plan, path, pavement)
            edges.add(frozenset((start, end)))
            pending.remove(end)
            joined.add(end)
            break
        else:
            raise LayoutError("No dry path between jungle landmarks")
    candidates = sorted(
        (distance(start, end), start, end)
        for index, start in enumerate(nodes)
        for end in nodes[index + 1 :]
        if frozenset((start, end)) not in edges and 22 < distance(start, end) < 53
    )
    plan.rng.shuffle(candidates)
    for _, start, end in candidates:
        if loops <= 0:
            break
        path = path_curve(plan, start, end, avoid, relief, allow_repair=False)
        if len(set(path) - plan.routes) < 13:
            continue
        pavement = trail(plan, path, 12, avoid=avoid, main=False)
        mark_trail(plan, path, pavement)
        loops -= 1


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
    shore = waterfront(plan, relief)
    sites, reserved = choose_surface_sites(plan, relief, region, ridge, shore)
    start = sites[0].center
    end = WIDTH - 3, plan.rng.randint(15, HEIGHT - 16)
    entry = 2, max(12, min(HEIGHT - 13, start[1] + plan.rng.randint(-16, 16)))
    avoid = (plan.water - plan.bridges) | reserved
    nodes = [s.center for s in sites] + shore + [end]
    if plan.d.floor_num > 1:
        nodes.append(entry)
    routing_cells = {
        (x, y) for y in range(1, HEIGHT - 1) for x in range(1, WIDTH - 1)
    } - avoid
    if set(nodes) - component(start, routing_cells):
        raise LayoutError("A landmark was cut off by a reserved feature")
    road = path_curve(plan, start, sites[1].center, avoid, relief)
    if not road:
        raise LayoutError("The opening grove could not reach its village")
    track = trail(plan, road, 12, avoid=avoid)
    mark_trail(plan, road, track)
    link_sites(plan, nodes, avoid, relief, loops=plan.rng.randint(2, 4))
    for site in sites:
        if site.kind in ("temple", "cave"):
            entrance(plan, site.center, site.kind, site.facing)
        elif site.kind == "vault":
            mirror_vault(plan, site.center, site.facing)
        else:
            footprint = oval(
                site.center, *site.radius, site.angle, 0.22, plan.rng.random() * tau
            )
            footprint -= reserved
            if site.kind == "village":
                village(plan, site.center, footprint)
            else:
                dress_glade(plan, site.center, footprint, site.kind)
    # The starting shelter and its fire are situated on a shoulder of the outward road.
    clearing = (
        plan.floor - plan.routes - plan.occupied - plan.water - plan.structure
    ) & oval(start, 8, 6)
    if clearing:
        point = min(clearing, key=lambda xy: distance(xy, start))
        plan.prop(point, "campfire")
        plan.lamp(point, 112)
    gateway(plan, "east", end[1], "forward")
    if plan.d.floor_num > 1:
        gateway(plan, "west", entry[1], "back")
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


def optional_vault(plan, focus):
    if plan.rng.random() >= plan.d.puzzle_chance:
        return
    edges = plan.floor - erode(plan.floor) - plan.water - plan.occupied
    choices = sorted(edges, key=lambda point: (distance(point, focus), point))
    for center in choices:
        # Find a wall face with enough unexcavated rock to hold the entire branch.
        normals = list(CARDINAL)
        plan.rng.shuffle(normals)
        for facing in normals:
            if offset(center, facing) in plan.floor:
                continue
            lot = feature_lot(plan, center, facing, "vault")
            if not lot & plan.floor and all(plan.inside(point, 2) for point in lot):
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
    optional_vault(plan, axis(54))
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
    optional_vault(plan, points[-1])
    return start


def validate_floor(plan, start):
    d = plan.d
    solid = {
        (x, y) for x, y, kind in d.jungle_props if kind in SOLID_INTERACTABLE_KINDS
    }
    locked = {position for position, door in d.doors.items() if door.locked}
    reachable = component(start, plan.floor - solid - locked)
    if (d.passages.keys() | d.fishing_edges.keys()) - reachable:
        raise LayoutError("A passage or fishing landing became inaccessible")
    if not d.interior:
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
    last_error = None
    for _ in range(10):
        dungeon.jungle_props = []
        dungeon.grid = [[21] * WIDTH for _ in range(HEIGHT)]
        dungeon.passages.clear()
        dungeon.fishing_edges.clear()
        dungeon.rooms.clear()
        dungeon.overlays.clear()
        dungeon.moss_tiles.clear()
        dungeon.braziers.clear()
        dungeon.room_lights.clear()
        dungeon.fog_zones.clear()
        dungeon.atmo_zones.clear()
        dungeon.invisible_bounds.clear()
        dungeon.doors.clear()
        dungeon.mirror_puzzle_info = None
        plan = Plan(dungeon, rng)
        relief = Relief(rng, WIDTH, HEIGHT).raster(WIDTH, HEIGHT)
        try:
            if dungeon.interior:
                bedrock(plan, relief, dungeon.interior)
                start = temple(plan) if dungeon.interior == "temple" else caves(plan)
            else:
                start = surface(plan, relief)
            validate_floor(plan, start)
        except LayoutError as error:
            last_error = error
        else:
            dungeon.start_pos = start
            return
    raise RuntimeError("Could not generate a connected jungle floor") from last_error
