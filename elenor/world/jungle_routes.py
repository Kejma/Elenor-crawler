"""Gated through-routes inside temples and caves."""

from collections import deque

from elenor.entities.objects import JUNGLE_KEY_COLORS, SOLID_INTERACTABLE_KINDS
from elenor.world.dungeon import Door, Lever
from elenor.world.jungle_sites import CARDINAL, LayoutError, dilate, neighbors, offset

KEY_COLORS = tuple(JUNGLE_KEY_COLORS)


def route_kind(depth, variant=0):
    """A surface approach hides which of its two interiors leads onward."""
    return ("cave", "temple", "temple", "cave", "temple", "cave")[(depth - 1 + variant) % 6]


def add_through_route(plan, start, far_end):
    d = plan.d
    solid = {(x, y) for x, y, kind in d.jungle_props if kind in SOLID_INTERACTABLE_KINDS}
    locked = {position for position, door in d.doors.items() if door.locked}
    walk = plan.floor - solid - locked
    distances = {start: 0}
    queue = deque([start])
    while queue:
        point = queue.popleft()
        for other in neighbors(point):
            if other in walk and other not in distances:
                distances[other] = distances[point] + 1
                queue.append(other)
    edges = (plan.floor - plan.occupied - plan.water) & distances.keys()
    candidates = sorted(edges, key=lambda p: (abs(p[0]-far_end[0]) + abs(p[1]-far_end[1]), p))
    for base in candidates:
        if distances[base] < 23:
            continue
        directions = list(CARDINAL)
        plan.rng.shuffle(directions)
        for facing in directions:
            corridor = [offset(base, facing, step) for step in range(1, 8)]
            shell = dilate(set(corridor))
            if (shell & plan.floor) - {base} or not all(plan.inside(p, 2) for p in shell):
                continue

            material = 24 if d.interior == "temple" else 8
            plan.paint(corridor, material)
            plan.routes.update(corridor)
            plan.feature(corridor[-1], "onward", "stairs")
            plan.lamp(corridor[-1], 116)
            gate = Door(*corridor[2], locked_by_lever=True)
            gate_tile = corridor[2]
            d.doors[gate_tile] = gate
            d.jungle_gate = gate_tile
            _place_control(plan, distances, base, solid, gate)
            return
    raise LayoutError("A through-route needs an isolated corridor beyond the last chamber")


def _place_control(plan, distances, base, solid, gate):
    d = plan.d
    available = distances.keys() - plan.occupied - plan.water - solid - d.doors.keys()
    choices = [
        p for p in available
        if 9 <= distances[p] < distances[base] and abs(p[0] - base[0]) + abs(p[1] - base[1]) >= 7
        and p not in plan.routes
    ]
    if not choices:
        choices = [p for p in available if distances[p] >= 6]
    if not choices:
        raise LayoutError("No reachable room for the route control")
    choices.sort(key=lambda p: (distances[p], p))
    position = plan.rng.choice(choices[len(choices) // 4:])

    if d.floor_num % 3 == 2:
        d.levers[position] = Lever(position[0], position[1], [gate])
        d.jungle_controls[position] = "lever"
        plan.occupied.add(position)
    else:
        color = KEY_COLORS[((d.floor_num - 1) // 2) % len(KEY_COLORS)]
        gate.key_color = color
        d.jungle_controls[position] = color
        plan.prop(position, f"jungle_key_{color}", on_route=True)
    plan.lamp(position, 98)
