"""Pixel visibility for emissive overlays, shared by CPU and GPU rendering."""
import math

import numpy as np
import pygame
from elenor.config import VIEW_W, VIEW_H, TILE_W, TILE_H, LOS_MAX_RADIUS

_X = np.arange(VIEW_W, dtype=np.float32)[:, None]
_Y = np.arange(VIEW_H, dtype=np.float32)[None, :]


def canopy_visibility(dungeon, player_x, player_y, x, y):
    """Trace to the exposed faces of a tree independently of the floor ray fan."""
    cx, cy = x + 0.5, y + 0.5
    dx, dy = player_x - cx, player_y - cy
    if dx * dx + dy * dy > (LOS_MAX_RADIUS / TILE_W + 1.0) ** 2:
        return 0.0
    # In a straight row the end face can face the viewer while being covered by
    # the next tree. Prefer a genuinely exposed side, such as the corridor bank.
    horizontal = (1 if dx > 0 else -1, 0)
    vertical = (0, 1 if dy > 0 else -1)
    faces = (horizontal, vertical) if abs(dx) > abs(dy) else (vertical, horizontal)
    grazing = 0
    for fx, fy in faces:
        if dungeon.is_blocking_sight(x + fx, y + fy):
            continue
        face_x, face_y = cx + fx * .42, cy + fy * .42

        def visible(offset):
            return dungeon.has_line_of_sight(
                player_x, player_y, face_x + fy * offset, face_y + fx * offset,
                LOS_MAX_RADIUS / TILE_W, target_thicket=(x, y),
            )

        if visible(0):
            return 1.0
        grazing = max(grazing, visible(-.24) + visible(.24))
    return .32 * grazing


class CanopyVisibility:
    """Accumulate coverage in world tiles so a narrow moving ray cannot flash a sprite."""

    def __init__(self):
        self.grid = None
        self.view = None
        self.targets = {}
        self.previous = {}
        self.current = {}
        self.time = 0.0
        self.blend = 1.0

    def begin_frame(self, grid, time):
        if grid is not self.grid:
            self.grid = grid
            self.targets.clear()
            self.previous = {}
            self.blend = 1.0
        else:
            self.previous = self.current
            dt = min(0.10, max(0.0, time - self.time))
            self.blend = 1.0 - math.exp(-dt * 12.0)
        self.current = {}
        self.time = time

    def set_view(self, dungeon, x, y):
        view = dungeon, dungeon.geometry_revision, x, y
        if view != self.view:
            self.view = view
            self.targets.clear()

    def target(self, tile):
        if tile not in self.targets:
            dungeon, _, x, y = self.view
            self.targets[tile] = canopy_visibility(dungeon, x, y, *tile)
        return self.targets[tile]

    def sample(self, tile, target):
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


def misted_actor(sprite, time, strength):
    """Tint and thin the pixels of the silhouette while preserving its animation."""
    result = sprite.copy()
    width, height = sprite.get_size()
    x = _X[:width]
    y = _Y[:, :height]
    swirl = .5 + .5 * np.sin(x * .64 + y * .37 + np.sin(y * .48 - time * 3.0) * 1.25 + time * 4.0)
    opacity = .34 + swirl * .31 + y * (.08 / height)
    rgb = pygame.surfarray.pixels3d(result)
    gray = rgb.mean(axis=2)
    mist = gray[:, :, None] * .48 + np.array((49, 65, 82))
    tint = strength * .80
    rgb[:] = rgb * (1 - tint) + mist * tint
    del rgb
    alpha = pygame.surfarray.pixels_alpha(result)
    alpha[:] = alpha * (1 - strength + opacity * strength)
    del alpha
    return result


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
