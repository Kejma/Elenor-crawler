"""Pixel visibility for emissive overlays, shared by CPU and GPU rendering."""
import math

import numpy as np
import pygame
from elenor.config import VIEW_W, VIEW_H, TILE_W, TILE_H

_X = np.arange(VIEW_W, dtype=np.float32)[:, None]
_Y = np.arange(VIEW_H, dtype=np.float32)[None, :]


def canopy_visibility(fov_mask, tile_x, tile_y):
    """Fade the crown as the visible area of its footprint grows."""
    x0, x1 = max(0, tile_x + 3), min(VIEW_W, tile_x + TILE_W - 3)
    y0, y1 = max(0, tile_y + 3), min(VIEW_H, tile_y + TILE_H - 3)
    if x0 >= x1 or y0 >= y1:
        return 0.0
    coverage = fov_mask[x0:x1, y0:y1].sum() / ((x1 - x0) * (y1 - y0))
    strength = min(1.0, max(0.0, (float(coverage) - 0.35) / 0.48))
    return strength * strength * (3.0 - 2.0 * strength)


class CanopyVisibility:
    """Accumulate coverage in world tiles so a narrow moving ray cannot flash a sprite."""

    def __init__(self):
        self.grid = None
        self.previous = {}
        self.current = {}
        self.time = 0.0
        self.blend = 1.0

    def begin_frame(self, grid, time):
        if grid is not self.grid:
            self.grid = grid
            self.previous = {}
            self.blend = 1.0
        else:
            self.previous = self.current
            dt = min(0.10, max(0.0, time - self.time))
            self.blend = 1.0 - math.exp(-dt * 12.0)
        self.current = {}
        self.time = time

    def sample(self, tile, mask, x, y):
        target = canopy_visibility(mask, x, y)
        old = self.previous.get(tile, 0.0)
        value = old + (target - old) * self.blend
        if value > 0.006 or target > 0.0:
            self.current[tile] = value
        return value


def canopy_opacity(tree_x, tree_y, player_x, player_y):
    horizontal = (1.28 - abs(player_x - (tree_x + 0.5))) / 0.46
    vertical = min(player_y - tree_y + 2.0, tree_y + 0.55 - player_y) / 0.42
    blend = max(0.0, min(1.0, horizontal, vertical))
    return round(255 - 150 * blend * blend * (3.0 - 2.0 * blend))


def overlay_visibility(fov_mask, lights, cam_x, cam_y):
    """Combine wall occlusion with the falloff of the current frame's lights.

    Evaluate in native pixels, independent of surface colours and GL readback.
    This preserves soft dark edges even for a self-emissive overlay.
    """
    illumination = np.zeros((VIEW_W, VIEW_H), dtype=np.float32)
    tx = ((np.arange(VIEW_W) + cam_x) // TILE_W).astype(int)
    ty = ((np.arange(VIEW_H) + cam_y) // TILE_H).astype(int)
    for light in lights:
        lx, ly, lz = light['pos']
        radius = light['radius']
        if radius <= 0:
            continue
        x0, x1 = max(0, int(lx - radius)), min(VIEW_W, int(lx + radius) + 1)
        y0, y1 = max(0, int(ly - radius)), min(VIEW_H, int(ly + radius) + 1)
        if x0 >= x1 or y0 >= y1:
            continue
        distance = np.sqrt((_X[x0:x1] - lx) ** 2 + (_Y[:, y0:y1] - ly) ** 2 + lz ** 2)
        strength = np.clip(1.0 - (distance / radius) ** 1.65, 0, 1)
        allowed = light.get('allowed_tiles')
        if isinstance(allowed, np.ndarray):
            strength *= allowed[tx[x0:x1, None].clip(0, allowed.shape[0]-1), ty[None, y0:y1].clip(0, allowed.shape[1]-1)]
        illumination[x0:x1, y0:y1] += strength * max(light['color'])
    return np.clip(illumination, 0, 1) * np.clip(fov_mask[:, :VIEW_H], 0, 1)


def mask_overlay(surface, visibility, cache):
    """Multiply RGBA once after drawing every glow and mirror highlight."""
    native = cache.get('_visibility_native')
    scaled = cache.get('_visibility_scaled')
    if native is None or scaled is None or scaled.get_size() != surface.get_size():
        native = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
        scaled = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        cache['_visibility_native'], cache['_visibility_scaled'] = native, scaled
    native.fill((255, 255, 255, 255))
    alpha = pygame.surfarray.pixels_alpha(native)
    alpha[:] = (visibility * 255).astype(np.uint8)
    del alpha
    pygame.transform.scale(native, surface.get_size(), scaled)
    surface.blit(scaled, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)


def visible_lit_tiles(lit_surface, fov_mask, visible_tiles, cam_x, cam_y):
    """Use the lit scene before overlays, with a few samples inside each tile."""
    if not visible_tiles:
        return set()
    tiles = np.array(list(visible_tiles), dtype=np.int32)
    offsets = np.array((-4, 0, 4))
    xs = tiles[:, 0, None, None] * TILE_W + TILE_W // 2 - round(cam_x) + offsets[None, :, None]
    ys = tiles[:, 1, None, None] * TILE_H + TILE_H // 2 - round(cam_y) + offsets[None, None, :]
    on_screen = (0 <= xs) & (xs < VIEW_W) & (0 <= ys) & (ys < VIEW_H)
    xs = xs.clip(0, VIEW_W - 1)
    ys = ys.clip(0, VIEW_H - 1)
    pixels = pygame.surfarray.pixels3d(lit_surface)
    light = pixels[xs, ys].sum(axis=-1)
    del pixels
    readable = on_screen & (fov_mask[xs, ys] > 0.5) & (light >= 39)
    return {tuple(tile) for tile in tiles[readable.sum(axis=(1, 2)) >= 2].tolist()}
