"""A directional sun over a static canopy shadow map in world pixels."""

import math

import numpy as np

from elenor.config import MAP_COLS, MAP_ROWS, TILE_W, TILE_H, VIEW_W, VIEW_H

SUN_X, SUN_Y, SUN_Z = (v / math.hypot(0.55, 0.49, 0.69) for v in (0.55, 0.49, 0.69))
SUN_COLOR = (1.03, 0.94, 0.75)


def canopy_light(grid):
    light = np.ones((MAP_COLS * TILE_W, MAP_ROWS * TILE_H), dtype=np.float32)
    # Tree crowns sit above the trunks. Project them down and left, away from
    # the sun. Overlapping shadows retain the same floor of reflected light.
    for ty, row in enumerate(grid):
        for tx, tile in enumerate(row):
            if tile not in (21, 22):
                continue
            cx, cy = (tx + 0.5) * TILE_W - 16, (ty + 0.5) * TILE_H + 7
            rx, ry = (26, 18) if tile == 21 else (21, 14)
            x0, x1 = max(0, int(cx - rx)), min(light.shape[0], int(cx + rx) + 1)
            y0, y1 = max(0, int(cy - ry)), min(light.shape[1], int(cy + ry) + 1)
            if x0 >= x1 or y0 >= y1:
                continue
            x = (np.arange(x0, x1)[:, None] - cx) / rx
            y = (np.arange(y0, y1)[None, :] - cy) / ry
            edge = x * x + y * y + 0.09 * np.cos(x * 14) * np.sin(y * 11)
            shadow = np.clip((1 - edge) / 0.30, 0, 1)
            shadow *= shadow * (3 - 2 * shadow)
            patch = light[x0:x1, y0:y1]
            np.minimum(patch, 1 - 0.78 * shadow, out=patch)
    return light


def visible_sun(light, cam_x, cam_y):
    if light is None:
        return None
    x = np.clip(np.arange(VIEW_W) + int(cam_x), 0, light.shape[0] - 1)
    y = np.clip(np.arange(VIEW_H) + int(cam_y), 0, light.shape[1] - 1)
    return light[x[:, None], y[None, :]]


def apply_daylight(channels, normals, sun):
    if sun is None:
        return
    nx, ny, nz = (channel[:, :VIEW_H] for channel in normals)
    amount = np.maximum(0, nx * SUN_X + ny * SUN_Y + nz * SUN_Z) * sun
    for channel, color in zip(channels, SUN_COLOR):
        channel[:, :VIEW_H] += amount * color
