"""World geometry and cached angular shadow distances for point lights."""

from collections import OrderedDict
import math

import numpy as np

from elenor.config import OPAQUE_WALL_TILES, TILE_H, TILE_W
from elenor.entities.objects import SOLID_INTERACTABLE_KINDS

SHADOW_RAYS = 720
_ANGLES = np.arange(SHADOW_RAYS, dtype=np.float32) * (math.tau / SHADOW_RAYS)
_RAY_X = np.cos(_ANGLES)[:, None]
_RAY_Y = np.sin(_ANGLES)[:, None]
_FURNITURE = SOLID_INTERACTABLE_KINDS | {"bookshelf", "barrel", "chest", "chair_bench", "stool"}
# Footprint radii and height in native world pixels.
_PROP_SHAPES = {
    "chair_bench": (5.5, 3.0, 4.0),
    "stool": (3.0, 3.0, 4.0),
    "marble_bench": (6.0, 3.0, 5.0),
    "tavern_table": (5.5, 4.5, 8.0),
    "tribal_table": (5.5, 4.5, 8.0),
    "bar_counter": (4.5, 7.8, 10.0),
    "bookshelf": (6.5, 4.5, 18.0),
    "grandfather_clock": (3.5, 3.0, 17.0),
    "marble_pillar": (5.0, 5.0, 23.0),
    "stalagnate_column": (5.0, 5.0, 23.0),
    "bed": (6.5, 5.5, 5.0),
    "fireplace": (6.0, 4.0, 15.0),
}
_DEFAULT_PROP_SHAPE = (5.0, 4.5, 9.0)
PROP_SAMPLE_STEPS = (1.5, 4.5, 8.0, 12.0, 17.0)
_PROP_X, _PROP_Y = np.ogrid[:TILE_W, :TILE_H]


class LightOcclusion:
    def __init__(self):
        self.geometry = None
        self.version = 0
        self.blockers = None
        self.rays = OrderedDict()

    def update(self, dungeon, objects=()):
        doors = tuple((point, door.locked) for point, door in dungeon.doors.items() if not door.is_open)
        seen_props = {
            (obj.x, obj.y): obj for obj in objects
            if obj.kind in _FURNITURE or (obj.x, obj.y) in dungeon.solid_props
        }
        furniture = frozenset((x, y, obj.kind) for (x, y), obj in seen_props.items() if not obj.used)
        furniture |= frozenset((x, y, None) for x, y in dungeon.solid_props - seen_props.keys())
        key = dungeon, dungeon.geometry_revision, doors, furniture
        if key == self.geometry:
            return
        self.geometry = key
        self.version += 1
        self.rays.clear()
        tiles = np.asarray(dungeon.grid).T
        walls = self.walls = np.isin(tiles, tuple(OPAQUE_WALL_TILES))
        blocked = walls.copy()
        for x, y in dungeon.thickets:
            blocked[x, y] = True
        self.blockers = blocked.repeat(TILE_W, axis=0).repeat(TILE_H, axis=1)

        self.prop_heights = np.zeros_like(self.blockers, dtype=np.uint8)
        self.has_props = bool(furniture)
        for x, y, kind in furniture:
            if 0 <= x < dungeon.width and 0 <= y < dungeon.height and (x, y) not in dungeon.doors:
                rx, ry, height = _PROP_SHAPES.get(kind, _DEFAULT_PROP_SHAPE)
                dist = ((_PROP_X + .5 - TILE_W / 2) / rx) ** 2 + ((_PROP_Y + .5 - TILE_H / 2) / ry) ** 2
                footprint = np.clip((1.0 - dist) * 2.5, 0, 1) * height
                x0, y0 = x * TILE_W, y * TILE_H
                self.prop_heights[x0:x0 + TILE_W, y0:y0 + TILE_H] = np.rint(footprint * 10)
        for x, y in zip(*np.nonzero(np.isin(tiles, (5, 21, 22, 56, 57)) & ~blocked)):
            self.blockers[x * TILE_W + 5:x * TILE_W + 11, y * TILE_H + 5:y * TILE_H + 11] = True

        for (x, y), grate in doors:
            x0, y0 = x * TILE_W, y * TILE_H
            tile = self.blockers[x0:x0 + TILE_W, y0:y0 + TILE_H]
            if not grate:
                tile[:] = True
                continue
            horizontal_walls = sum(0 <= x + dx < dungeon.width and walls[x + dx, y] for dx in (-1, 1))
            vertical_walls = sum(0 <= y + dy < dungeon.height and walls[x, y + dy] for dy in (-1, 1))
            if horizontal_walls >= vertical_walls:
                tile[2::4, TILE_H // 2 - 1:TILE_H // 2 + 2] = True
            else:
                tile[TILE_W // 2 - 1:TILE_W // 2 + 2, 2::4] = True

    @staticmethod
    def light_key(x, y, radius):
        return round(x), round(y), math.ceil(radius / TILE_W) * TILE_W

    def distances(self, x, y, radius):
        # Snap by one native pixel and round the search range so flickering lights share the cache.
        key = self.light_key(x, y, radius)
        lx, ly, reach = key
        if key in self.rays:
            self.rays.move_to_end(key)
            return self.rays[key]
        steps = np.arange(1, reach + 1, dtype=np.float32)[None, :]
        rx = np.floor(lx + steps * _RAY_X).astype(np.int32)
        ry = np.floor(ly + steps * _RAY_Y).astype(np.int32)
        width, height = self.blockers.shape
        inside = (0 <= rx) & (rx < width) & (0 <= ry) & (ry < height)
        hits = ~inside | self.blockers[rx.clip(0, width - 1), ry.clip(0, height - 1)]
        if 0 <= lx < width and 0 <= ly < height and self.blockers[lx, ly]:
            # A lamp mounted inside a fixture can shine out of its own footprint.
            hits = ~inside | (hits & np.maximum.accumulate(~hits, axis=1))
        distances = np.where(hits.any(axis=1), hits.argmax(axis=1) + 1, reach + 2).astype(np.float32)
        self.rays[key] = distances
        if len(self.rays) > 48:
            self.rays.popitem(last=False)
        return distances

    @staticmethod
    def _coverage(stops, angle, distance):
        ray = np.floor(angle)
        weight = angle - ray
        index = ray.astype(np.int32) % SHADOW_RAYS
        near = np.clip(.5 + (stops[index] - distance) * .30, 0.0, 1.0)
        far = np.clip(.5 + (stops[(index + 1) % SHADOW_RAYS] - distance) * .30, 0.0, 1.0)
        return near + (far - near) * weight

    def penumbra(self, stops, angle, distance, receiver=None):
        # Sample angular coverage across a widening footprint, in world pixels.
        # Filtering the distances themselves would blend a wall and a distant opening.
        spread = (.60 + np.minimum(distance * .013, 1.50)) * (SHADOW_RAYS / math.tau)
        spread /= np.maximum(distance, 7.0)
        target = distance if receiver is None else receiver
        center = self._coverage(stops, angle, target)
        left = self._coverage(stops, angle - spread, target)
        right = self._coverage(stops, angle + spread, target)
        return center * .58 + (left + right) * .21


    def _wall_face_distance(self, dx, dy, x, y, distance, viewer):
        nx = np.where(dx > 0, 1, -1)
        ny = np.where(dy > 0, 1, -1)
        local_x, local_y = x % TILE_W, y % TILE_H
        edge_x = x - local_x + np.where(nx > 0, TILE_W, 0)
        edge_y = y - local_y + np.where(ny > 0, TILE_H, 0)
        exit_x = np.abs(edge_x - x) * distance / np.maximum(np.abs(dx), .001)
        exit_y = np.abs(edge_y - y) * distance / np.maximum(np.abs(dy), .001)

        def open_at(wx, wy):
            tx = (wx // TILE_W).astype(np.int32).clip(0, self.walls.shape[0] - 1)
            ty = (wy // TILE_H).astype(np.int32).clip(0, self.walls.shape[1] - 1)
            return ~self.walls[tx, ty]

        inv_distance = 1 / np.maximum(distance, .001)
        near_x, near_y = edge_x + nx * .75, edge_y + ny * .75
        open_x = open_at(near_x, y) & open_at(near_x, y + dy * inv_distance * (exit_x + .75))
        open_y = open_at(x, near_y) & open_at(x + dx * inv_distance * (exit_y + .75), near_y)
        face_x = (exit_x <= distance) & ((viewer[0] - edge_x) * nx > 0) & open_x
        face_y = (exit_y <= distance) & ((viewer[1] - edge_y) * ny > 0) & open_y
        # Put the receiver just outside its own wall, so penumbra taps cannot self-shadow the face.
        exit_x = np.where(face_x, exit_x + 2.4 * distance / np.maximum(np.abs(dx), .001), 0)
        exit_y = np.where(face_y, exit_y + 2.4 * distance / np.maximum(np.abs(dy), .001), 0)
        # An invalid axis is zero. If both are exposed, use the first crossing.
        return np.where((exit_x > 0) & (exit_y > 0), np.minimum(exit_x, exit_y), np.maximum(exit_x, exit_y))

    def _prop_visibility(self, dx, dy, x, y, distance, light_z):
        width, height = self.prop_heights.shape
        margin = math.ceil(PROP_SAMPLE_STEPS[-1])
        x0, x1 = max(0, int(x.min()) - margin), min(width, int(x.max()) + margin + 1)
        y0, y1 = max(0, int(y.min()) - margin), min(height, int(y.max()) + margin + 1)
        if x0 >= x1 or y0 >= y1 or not self.prop_heights[x0:x1, y0:y1].any():
            return 1.0
        direction = 1 / np.maximum(distance, .001)
        max_shade = np.zeros_like(distance)
        for step in PROP_SAMPLE_STEPS:
            px = np.floor(x + dx * direction * step).astype(np.int32)
            py = np.floor(y + dy * direction * step).astype(np.int32)
            inside = (0 <= px) & (px < width) & (0 <= py) & (py < height)
            h = self.prop_heights[px.clip(0, width - 1), py.clip(0, height - 1)] * .1
            reach = np.clip((distance - step - 4) / 6, 0, 1)
            shade = np.clip((h - light_z * step * direction) * .34, 0, 1)
            shade *= np.minimum(.55, h * .045) * (1 - step / 22) * reach * inside
            np.maximum(max_shade, shade, out=max_shade)
        return 1 - max_shade

    def surface_visibility(self, dx, dy, x, y, lx, ly, radius, viewer, light_z=22.0):
        """Shadow mask for software rendering, including the lit faces of walls."""
        stops = self.distances(lx, ly, radius)
        has_hard = stops.min() < radius + 2.0
        if not has_hard and not self.has_props:
            return 1.0
        distance = np.hypot(dx, dy)
        visibility = 1.0
        wall = None
        if has_hard:
            angle = np.arctan2(-dy, -dx) * (SHADOW_RAYS / math.tau)
            receiver = distance - 1.0
            tx = (x // TILE_W).astype(np.int32).clip(0, self.walls.shape[0] - 1)
            ty = (y // TILE_H).astype(np.int32).clip(0, self.walls.shape[1] - 1)
            wall = self.walls[tx, ty]
            if wall.any():
                face = self._wall_face_distance(dx, dy, x, y, distance, viewer)
                receiver -= np.where(wall, face, 0.0)
            visibility = self.penumbra(stops, angle, distance, receiver)
        if self.has_props:
            props = self._prop_visibility(dx, dy, x, y, distance, light_z)
            visibility *= np.where(wall, 1.0, props) if wall is not None else props
        return visibility
