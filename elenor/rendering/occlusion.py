"""World geometry and cached angular shadow distances for point lights."""

from collections import OrderedDict
import math

import numpy as np

from elenor.config import OPAQUE_WALL_TILES, TILE_H, TILE_W

SHADOW_RAYS = 720
_ANGLES = np.arange(SHADOW_RAYS, dtype=np.float32) * (math.tau / SHADOW_RAYS)
_RAY_X = np.cos(_ANGLES)[:, None]
_RAY_Y = np.sin(_ANGLES)[:, None]
_FURNITURE = {"bookshelf", "barrel", "chest"}


class LightOcclusion:
    def __init__(self):
        self.geometry = None
        self.version = 0
        self.blockers = None
        self.rays = OrderedDict()

    def update(self, dungeon, objects=()):
        doors = tuple((point, door.locked) for point, door in dungeon.doors.items() if not door.is_open)
        furniture = frozenset(dungeon.solid_props) | frozenset(
            (obj.x, obj.y) for obj in objects if not obj.used and obj.kind in _FURNITURE
        )
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

        for x, y in furniture:
            if 0 <= x < dungeon.width and 0 <= y < dungeon.height and (x, y) not in dungeon.doors:
                self.blockers[x * TILE_W + 3:x * TILE_W + 13, y * TILE_H + 3:y * TILE_H + 13] = True
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


    def surface_visibility(self, dx, dy, x, y, lx, ly, radius, viewer):
        """Shadow mask for the software renderer, including exposed wall faces."""
        stops = self.distances(lx, ly, radius)
        if stops.min() > radius + 2.0:
            return 1.0
        distance = np.hypot(dx, dy)
        angle = np.arctan2(-dy, -dx) * (SHADOW_RAYS / math.tau)
        receiver = distance - 1.0
        tx = (x // TILE_W).astype(np.int32).clip(0, self.walls.shape[0] - 1)
        ty = (y // TILE_H).astype(np.int32).clip(0, self.walls.shape[1] - 1)
        wall = self.walls[tx, ty]
        if wall.any():
            local_x, local_y = x % TILE_W, y % TILE_H
            exit_x = np.where(dx > 0, TILE_W - local_x, local_x) * distance / np.maximum(np.abs(dx), .001)
            exit_y = np.where(dy > 0, TILE_H - local_y, local_y) * distance / np.maximum(np.abs(dy), .001)
            from_x = (viewer[0] - (x - local_x + TILE_W * .5)) * np.sign(dx) > 0
            from_y = (viewer[1] - (y - local_y + TILE_H * .5)) * np.sign(dy) > 0
            receiving_face = np.where(exit_x < exit_y, from_x, from_y)
            receiver -= np.where(wall & receiving_face, np.minimum(exit_x, exit_y), 0.0)
        return self.penumbra(stops, angle, distance, receiver)
