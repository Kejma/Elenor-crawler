"""Half-resolution air scattering and layered fog with soft light shafts."""

from collections import OrderedDict
import math

import numpy as np
import pygame

from elenor.config import OPAQUE_WALL_TILES, TILE_H, TILE_W, VIEW_H, VIEW_W


_HALF_W, _HALF_H = (VIEW_W + 1) // 2, (VIEW_H + 1) // 2
_X = np.arange(_HALF_W, dtype=np.float32)[:, None] * 2 + 0.5
_Y = np.arange(_HALF_H, dtype=np.float32)[None, :] * 2 + 0.5
_RAY_COUNT = 720
_ANGLES = np.arange(_RAY_COUNT, dtype=np.float32) * (math.tau / _RAY_COUNT)
_RAY_X = np.cos(_ANGLES)[:, None]
_RAY_Y = np.sin(_ANGLES)[:, None]


class FogRenderer:
    def __init__(self):
        self.geometry = None
        self.blockers = None
        self.rays = OrderedDict()
        self.half = pygame.Surface((_HALF_W, _HALF_H), pygame.SRCALPHA)
        self.full = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)

    def _update_geometry(self, dungeon):
        doors = tuple((point, door.locked) for point, door in dungeon.doors.items() if not door.is_open)
        key = dungeon, dungeon.geometry_revision, doors
        if key == self.geometry:
            return
        self.geometry = key
        self.rays.clear()
        walls = np.isin(np.asarray(dungeon.grid).T, tuple(OPAQUE_WALL_TILES))
        blocked = walls.copy()
        for x, y in dungeon.thickets:
            blocked[x, y] = True
        self.blockers = blocked.repeat(TILE_W, axis=0).repeat(TILE_H, axis=1)

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

    def _shadow_distances(self, x, y, radius):
        # Snap by one native pixel and round the search range so flickering lights share the cache.
        lx, ly = round(x), round(y)
        reach = math.ceil(radius / TILE_W) * TILE_W
        key = lx, ly, reach
        if key in self.rays:
            self.rays.move_to_end(key)
            return self.rays[key]
        steps = np.arange(1, reach + 1, dtype=np.float32)[None, :]
        rx = np.floor(lx + steps * _RAY_X).astype(np.int32)
        ry = np.floor(ly + steps * _RAY_Y).astype(np.int32)
        width, height = self.blockers.shape
        inside = (0 <= rx) & (rx < width) & (0 <= ry) & (ry < height)
        hits = ~inside | self.blockers[rx.clip(0, width - 1), ry.clip(0, height - 1)]
        distances = np.where(hits.any(axis=1), hits.argmax(axis=1) + 1, reach + 2).astype(np.float32)
        self.rays[key] = distances
        if len(self.rays) > 48:
            self.rays.popitem(last=False)
        return distances

    @staticmethod
    def _coverage(stops, angle, distance):
        ray = np.floor(angle)
        weight = angle - ray
        index = ray.astype(np.int32) % _RAY_COUNT
        near = np.clip(.5 + (stops[index] - distance) * .30, 0.0, 1.0)
        far = np.clip(.5 + (stops[(index + 1) % _RAY_COUNT] - distance) * .30, 0.0, 1.0)
        return near + (far - near) * weight

    def _penumbra(self, stops, angle, distance):
        # Sample angular coverage across a widening footprint, in world pixels.
        # Filtering the distances themselves would blend a wall and a distant opening.
        spread = (.60 + np.minimum(distance * .013, 1.50)) * (_RAY_COUNT / math.tau)
        spread /= np.maximum(distance, 7.0)
        center = self._coverage(stops, angle, distance)
        left = self._coverage(stops, angle - spread, distance)
        right = self._coverage(stops, angle + spread, distance)
        return center * .58 + (left + right) * .21

    def _light_field(self, lights, visible, cam_x, cam_y, patch):
        x0, y0, x1, y1 = patch
        illumination = np.zeros((x1 - x0, y1 - y0, 3), dtype=np.float32)
        for light in lights:
            lx, ly, lz = light["pos"]
            radius = light["radius"] * 1.08
            i0, i1 = max(x0, math.floor((lx - radius) / 2)), min(x1, math.ceil((lx + radius) / 2))
            j0, j1 = max(y0, math.floor((ly - radius) / 2)), min(y1, math.ceil((ly + radius) / 2))
            if i0 >= i1 or j0 >= j1:
                continue
            dx, dy = _X[i0:i1] - lx, _Y[:, j0:j1] - ly
            dist = np.sqrt(dx * dx + dy * dy)
            if not ((dist < radius) & visible[i0:i1, j0:j1]).any():
                continue
            stops = self._shadow_distances(lx + cam_x, ly + cam_y, radius)
            angle = np.arctan2(dy, dx) * (_RAY_COUNT / math.tau)
            transmission = self._penumbra(stops, angle, dist)
            range_fade = np.clip(1.0 - np.hypot(dist, lz * .43) / radius, 0.0, 1.0)
            # A soft outer falloff and a brighter core give even small lights depth.
            edge = np.minimum(1.0, range_fade * 5.0)
            edge *= edge * (3.0 - 2.0 * edge)
            core = range_fade * range_fade
            scatter = (range_fade * .77 + core * .23) * edge * transmission
            scatter *= np.minimum(1.0, .62 + dist * .017)
            illumination[i0 - x0:i1 - x0, j0 - y0:j1 - y0] += (
                scatter[:, :, None] * np.asarray(light["color"], dtype=np.float32)
            )
        return illumination

    def render(self, screen, dungeon, clouds, lights, fov_mask, entity_y, cam_x, cam_y, time):
        visible = fov_mask[:VIEW_W:2, :VIEW_H:2] > .025
        xv, yv = np.nonzero(visible)
        if not xv.size:
            return
        # Only shade the visible part of the viewport, even when the source is elsewhere.
        i0, j0, i1, j1 = xv.min(), yv.min(), xv.max() + 1, yv.max() + 1
        patch = np.s_[i0:i1, j0:j1]
        self._update_geometry(dungeon)
        low = np.zeros((i1 - i0, j1 - j0), dtype=np.float32)
        upper = np.zeros_like(low)
        tint = np.zeros((*low.shape, 3), dtype=np.float32)
        x, y = _X + cam_x, _Y + cam_y
        for cloud in clouds:
            radius = cloud["radius"] * TILE_W
            if radius <= 0:
                continue
            cx, cy = cloud["wx"] * TILE_W, cloud["wy"] * TILE_H
            cx0, cx1 = max(i0, math.floor((cx - radius - cam_x) / 2)), min(i1, math.ceil((cx + radius - cam_x) / 2))
            cy0, cy1 = max(j0, math.floor((cy - radius - cam_y) / 2)), min(j1, math.ceil((cy + radius - cam_y) / 2))
            if cx0 >= cx1 or cy0 >= cy1:
                continue
            xx, yy = x[cx0:cx1], y[:, cy0:cy1]
            radial = np.clip(1 - ((xx - cx) ** 2 + (yy - cy) ** 2) / radius ** 2, 0, 1) ** 1.35
            if cloud.get("bounds"):
                bx, by, bw, bh = cloud["bounds"]
                edge_x = np.minimum(xx - bx * TILE_W, (bx + bw) * TILE_W - xx)
                edge_y = np.minimum(yy - by * TILE_H, (by + bh) * TILE_H - yy)
                radial *= np.clip(np.minimum(edge_x, edge_y) / 9.0, 0.0, 1.0)
            timer = cloud.get("timer")
            fade = 1.0 if timer is None else np.clip(timer / min(1.2, cloud["max_timer"]), 0, 1)
            density = radial * cloud["density"] * fade
            floor_noise = .69 + .17 * np.sin(xx * .085 + time * .47 + np.cos(yy * .13 - time * .31))
            floor_noise += .13 * np.cos(yy * .20 - time * .6 + np.sin(xx * .071 + time * .23))
            drift = np.sin(xx * .057 - time * .32 + np.cos(yy * .101 + time * .26))
            drift += .60 * np.cos((xx - yy) * .104 + time * .43)
            floor = density * floor_noise
            loft = density * np.clip((drift - .03) * .39, 0, .55)
            cloud_patch = np.s_[cx0-i0:cx1-i0, cy0-j0:cy1-j0]
            low[cloud_patch] += floor
            upper[cloud_patch] += loft
            tint[cloud_patch] += (floor + loft)[:, :, None] * np.asarray(cloud["color"], dtype=np.float32)

        illumination = self._light_field(lights, visible, cam_x, cam_y, (i0, j0, i1, j1))
        peak = illumination.max(axis=2)
        density = low + upper
        if not (peak > .001).any() and not (density > .001).any():
            return
        color = tint / np.maximum(.001, density[:, :, None])

        # Dry air catches just a little colored light. Fog contributes the heavier layers.
        xx, yy = x[i0:i1], y[:, j0:j1]
        grain = .88 + .07 * np.sin(xx * .094 + time * .33 + np.cos(yy * .09))
        grain += .05 * np.cos((xx - yy) * .137 - time * .48)
        air_alpha = np.minimum(.20, peak * .25) * grain
        air_color = illumination / np.maximum(.001, peak[:, :, None]) * 222.0

        fog_color = np.clip(color * (np.array((40, 47, 59), dtype=np.float32) + illumination * 400), 0, 255)
        feet = entity_y[:VIEW_W:2, :VIEW_H:2][patch]
        clearance = feet - _Y[:, j0:j1]
        ground_height = np.clip(1 - clearance / 13.0, .12, 1.0)
        upper_height = np.clip(1 - clearance / 26.0, .28, 1.0)
        thickness = low * ground_height + upper * upper_height
        fog_alpha = np.minimum(.57, 1 - np.exp(-thickness * 1.9))
        air_alpha *= (1 - fog_alpha) * (.77 + .23 * upper_height)
        combined = fog_alpha + air_alpha
        premultiplied = fog_color * fog_alpha[:, :, None] + air_color * air_alpha[:, :, None]

        rgb = pygame.surfarray.pixels3d(self.half)
        rgb[:] = 0
        rgb[patch] = premultiplied / np.maximum(.001, combined[:, :, None])
        del rgb
        alpha = pygame.surfarray.pixels_alpha(self.half)
        alpha[:] = 0
        alpha[patch] = combined * 255
        del alpha

        pygame.transform.smoothscale(self.half, self.full.get_size(), self.full)
        alpha = pygame.surfarray.pixels_alpha(self.full)
        sx = (np.arange(VIEW_W) + cam_x).astype(np.int32).clip(0, self.blockers.shape[0] - 1)
        sy = (np.arange(VIEW_H) + cam_y).astype(np.int32).clip(0, self.blockers.shape[1] - 1)
        np.multiply(alpha, fov_mask[:, :VIEW_H] * ~self.blockers[sx[:, None], sy], out=alpha, casting="unsafe")
        del alpha
        screen.blit(self.full, (0, 0))
