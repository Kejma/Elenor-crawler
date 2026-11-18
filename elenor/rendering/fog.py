"""Half-resolution layered fog with soft light shafts."""

import math

import numpy as np
import pygame

from elenor.config import TILE_H, TILE_W, VIEW_H, VIEW_W
from elenor.rendering.occlusion import LightOcclusion, SHADOW_RAYS


_HALF_W, _HALF_H = (VIEW_W + 1) // 2, (VIEW_H + 1) // 2
_X = np.arange(_HALF_W, dtype=np.float32)[:, None] * 2 + 0.5
_Y = np.arange(_HALF_H, dtype=np.float32)[None, :] * 2 + 0.5


class FogRenderer:
    def __init__(self, occlusion=None):
        self.owns_occlusion = occlusion is None
        self.occlusion = LightOcclusion() if self.owns_occlusion else occlusion
        self.half = pygame.Surface((_HALF_W, _HALF_H), pygame.SRCALPHA)
        self.full = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)

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
            stops = self.occlusion.distances(lx + cam_x, ly + cam_y, radius)
            angle = np.arctan2(dy, dx) * (SHADOW_RAYS / math.tau)
            transmission = self.occlusion.penumbra(stops, angle, dist)
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
        if not clouds:
            return
        if self.owns_occlusion:
            self.occlusion.update(dungeon)
        visible = fov_mask[:VIEW_W:2, :VIEW_H:2] > .025
        xv, yv = np.nonzero(visible)
        if not xv.size:
            return
        # Only shade the visible part of the viewport, even when the source is elsewhere.
        i0, j0, i1, j1 = xv.min(), yv.min(), xv.max() + 1, yv.max() + 1
        patch = np.s_[i0:i1, j0:j1]
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

        density = low + upper
        volume_pixels = (density > .001) & visible[patch]
        xv, yv = np.nonzero(volume_pixels)
        if not xv.size:
            return
        inner = np.s_[xv.min():xv.max() + 1, yv.min():yv.max() + 1]
        i0, j0, i1, j1 = i0 + inner[0].start, j0 + inner[1].start, i0 + inner[0].stop, j0 + inner[1].stop
        visible[patch] = volume_pixels
        patch = np.s_[i0:i1, j0:j1]
        low, upper = low[inner], upper[inner]
        color = tint[inner] / np.maximum(.001, density[inner][:, :, None])
        illumination = self._light_field(lights, visible, cam_x, cam_y, (i0, j0, i1, j1))
        fog_color = np.clip(color * (np.array((40, 47, 59), dtype=np.float32) + illumination * 400), 0, 255)
        feet = entity_y[:VIEW_W:2, :VIEW_H:2][patch]
        clearance = feet - _Y[:, j0:j1]
        ground_height = np.clip(1 - clearance / 13.0, .12, 1.0)
        upper_height = np.clip(1 - clearance / 26.0, .28, 1.0)
        thickness = low * ground_height + upper * upper_height
        fog_alpha = np.minimum(.57, 1 - np.exp(-thickness * 1.9))
        rgb = pygame.surfarray.pixels3d(self.half)
        rgb[:] = 0
        rgb[patch] = fog_color
        del rgb
        alpha = pygame.surfarray.pixels_alpha(self.half)
        alpha[:] = 0
        alpha[patch] = fog_alpha * 255
        del alpha

        pygame.transform.smoothscale(self.half, self.full.get_size(), self.full)
        alpha = pygame.surfarray.pixels_alpha(self.full)
        sx = (np.arange(VIEW_W) + cam_x).astype(np.int32).clip(0, self.occlusion.blockers.shape[0] - 1)
        sy = (np.arange(VIEW_H) + cam_y).astype(np.int32).clip(0, self.occlusion.blockers.shape[1] - 1)
        np.multiply(alpha, fov_mask[:, :VIEW_H] * ~self.occlusion.blockers[sx[:, None], sy], out=alpha, casting="unsafe")
        del alpha
        screen.blit(self.full, (0, 0))
