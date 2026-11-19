"""Pixel visibility for emissive overlays, shared by CPU and GPU rendering."""
from functools import lru_cache
import math

import numpy as np
import pygame
from elenor.config import VIEW_W, VIEW_H, TILE_W, TILE_H, LOS_MAX_RADIUS

_X = np.arange(VIEW_W, dtype=np.float32)[:, None]
_Y = np.arange(VIEW_H, dtype=np.float32)[None, :]


@lru_cache(maxsize=144)
def _ray_fractions(steps):
    return tuple(i / steps for i in range(1, steps + 1))


class _CanopyOcclusion:
    """Shared wall and root flags, packed into rows for scalar canopy rays."""

    def __init__(self, dungeon, closed_doors):
        walls, roots = dungeon.sight_geometry(closed_doors)
        self.grid = (roots | (walls.astype(np.uint8) << 5)).astype(np.uint8, copy=False)
        self.rows = tuple(row.tobytes() for row in self.grid.T)
        self.width, self.height = walls.shape
        self.rate = 8 if dungeon.thickets else 3
        self.exposed_sides = {}

    def exposed(self, tile):
        sides = self.exposed_sides.get(tile)
        if sides is None:
            x, y = tile
            sides = tuple(
                (dx, dy) for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
                if not self.blocked(x + dx, y + dy)
            )
            self.exposed_sides[tile] = sides
        return sides

    def blocked(self, x, y):
        return not (0 <= x < self.width and 0 <= y < self.height) or self.rows[y][x] != 0

    def trace(self, x0, y0, x1, y1, max_dist, *, target_thicket):
        dx, dy = x1 - x0, y1 - y0
        dist = math.hypot(dx, dy)
        if dist > max_dist:
            return False
        steps = int(dist * self.rate) + 1
        rows, width, height = self.rows, self.width, self.height
        floor = math.floor
        target_x, target_y = target_thicket
        endpoint_in_target = target_x <= x1 < target_x + 1 and target_y <= y1 < target_y + 1
        previous_x, previous_y = floor(x0), floor(y0)
        row = None
        flag = 0
        check_root = False
        for t in _ray_fractions(steps):
            x, y = x0 + dx * t, y0 + dy * t
            cx, cy = floor(x), floor(y)
            if row is None or cx != previous_x or cy != previous_y:
                if not (0 <= cx < width and 0 <= cy < height):
                    return False
                row = rows[cy]
                flag = row[cx]
                if flag & 32:
                    return False
                if cx != previous_x and cy != previous_y and (
                    (not 0 <= previous_y < height or rows[previous_y][cx])
                    and (not 0 <= previous_x < width or row[previous_x])
                ):
                    return False
                previous_x, previous_y = cx, cy
                if endpoint_in_target and cx == target_x and cy == target_y:
                    return True
                check_root = flag and (cx != target_x or cy != target_y)
            if check_root:
                ox, oy = x - cx - .5, y - cy - .5
                if (ox * ox + oy * oy <= .22 ** 2
                        or abs(oy) <= .15 and flag & (2 if ox > 0 else 4)
                        or abs(ox) <= .15 and flag & (8 if oy > 0 else 16)):
                    return False
        return True

    def trace_batch(self, x0, y0, x1s, y1s, target_xs, target_ys, max_dist):
        count = len(x1s)
        out = np.zeros(count, dtype=bool)
        if not count:
            return out
        dx = x1s - x0
        dy = y1s - y0
        dist = np.hypot(dx, dy)
        idx = np.flatnonzero(dist <= max_dist)
        if not idx.size:
            return out

        steps = (dist[idx] * self.rate).astype(np.int32) + 1
        max_steps = int(steps.max())
        step_idx = np.arange(1, max_steps + 1, dtype=np.float32)[None, :]
        active = step_idx <= steps[:, None]
        t = np.minimum(step_idx, steps[:, None]) / steps[:, None]
        xs = x0 + dx[idx, None] * t
        ys = y0 + dy[idx, None] * t
        cx = np.floor(xs).astype(np.int32)
        cy = np.floor(ys).astype(np.int32)

        w, h = self.width, self.height
        oob = (cx < 0) | (cx >= w) | (cy < 0) | (cy >= h)
        cx_c = cx.clip(0, w - 1)
        cy_c = cy.clip(0, h - 1)
        flags = self.grid[cx_c, cy_c]
        blocked = oob | ((flags & 32) != 0)

        prev_x = np.empty_like(cx)
        prev_y = np.empty_like(cy)
        prev_x[:, 0] = math.floor(x0)
        prev_y[:, 0] = math.floor(y0)
        prev_x[:, 1:] = cx[:, :-1]
        prev_y[:, 1:] = cy[:, :-1]
        diag = (cx != prev_x) & (cy != prev_y) & active
        if diag.any():
            r_i, s_i = np.nonzero(diag)
            c_x, c_y = cx[r_i, s_i], cy[r_i, s_i]
            p_x, p_y = prev_x[r_i, s_i], prev_y[r_i, s_i]
            side1 = (p_y < 0) | (p_y >= h) | (c_x < 0) | (c_x >= w) | (self.grid[c_x.clip(0, w - 1), p_y.clip(0, h - 1)] != 0)
            side2 = (p_x < 0) | (p_x >= w) | (c_y < 0) | (c_y >= h) | (self.grid[p_x.clip(0, w - 1), c_y.clip(0, h - 1)] != 0)
            blocked[r_i, s_i] |= side1 & side2

        in_target = (cx == target_xs[idx, None]) & (cy == target_ys[idx, None])
        need_root = active & (~blocked) & (flags != 0) & (~in_target)
        if need_root.any():
            r_i, s_i = np.nonzero(need_root)
            fl = flags[r_i, s_i]
            ox = xs[r_i, s_i] - cx[r_i, s_i] - .5
            oy = ys[r_i, s_i] - cy[r_i, s_i] - .5
            hit_r = (
                (ox * ox + oy * oy <= .22 ** 2)
                | ((np.abs(oy) <= .15) & ((fl & np.where(ox > 0, 2, 4)) != 0))
                | ((np.abs(ox) <= .15) & ((fl & np.where(oy > 0, 8, 16)) != 0))
            )
            blocked[r_i, s_i] |= hit_r

        blocked &= active
        out[idx] = ~blocked.any(axis=1)
        return out

def canopy_visibility(dungeon, player_x, player_y, x, y, *, obstacles=None):
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
    target_tile = x, y
    if obstacles is not None:
        exposed = obstacles.exposed(target_tile)
        trace = obstacles.trace
    else:
        exposed = tuple((fx, fy) for fx, fy in faces if not dungeon.is_blocking_sight(x + fx, y + fy))
        trace = dungeon.has_line_of_sight
    grazing = 0
    max_dist = LOS_MAX_RADIUS / TILE_W
    for fx, fy in faces:
        if (fx, fy) not in exposed:
            continue
        face_x, face_y = cx + fx * .42, cy + fy * .42
        if trace(player_x, player_y, face_x, face_y, max_dist, target_thicket=target_tile):
            return 1.0
        low = trace(player_x, player_y, face_x - fy * .24, face_y - fx * .24,
                    max_dist, target_thicket=target_tile)
        high = trace(player_x, player_y, face_x + fy * .24, face_y + fx * .24,
                     max_dist, target_thicket=target_tile)
        grazing = max(grazing, low + high)
    return .32 * grazing


class CanopyVisibility:
    """Accumulate coverage in world tiles so a narrow moving ray cannot flash a sprite."""

    def __init__(self):
        self.grid = None
        self.view = None
        self.obstacles = None
        self.targets = {}
        self.previous = {}
        self.current = {}
        self.time = 0.0
        self.blend = 1.0

    def begin_frame(self, grid, time):
        if grid is not self.grid:
            self.grid = grid
            self.obstacles = None
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
        closed_doors = tuple(point for point, door in dungeon.doors.items() if not door.is_open)
        view = dungeon, dungeon.geometry_revision, x, y, closed_doors
        if view != self.view:
            if self.view is None or view[:2] != self.view[:2] or closed_doors != self.view[4]:
                self.obstacles = None
            self.view = view
            self.targets.clear()

    def prefetch(self, trees, visible_tiles=None):
        targets = self.targets
        missing = [(t[0], t[1]) for t in trees if (t[0], t[1]) not in targets]
        if not missing:
            return
        dungeon, _, px, py, closed_doors = self.view
        if self.obstacles is None:
            self.obstacles = _CanopyOcclusion(dungeon, closed_doors)
        obs = self.obstacles
        max_dist = LOS_MAX_RADIUS / TILE_W
        max_r2 = (max_dist + 1.0) ** 2

        center_tiles = []
        center_faces = []
        c_x1, c_y1, c_tx, c_ty = [], [], [], []
        tile_faces = {}
        for x, y in missing:
            tile = (x, y)
            cx, cy = x + 0.5, y + 0.5
            dx, dy = px - cx, py - cy
            if dx * dx + dy * dy > max_r2:
                targets[tile] = 0.0
                continue
            exposed = obs.exposed(tile)
            if not exposed:
                targets[tile] = 0.0
                continue
            h_f = (1 if dx > 0 else -1, 0)
            v_f = (0, 1 if dy > 0 else -1)
            faces = [
                f for f in ((h_f, v_f) if abs(dx) > abs(dy) else (v_f, h_f))
                if f in exposed and (visible_tiles is None or (x + f[0], y + f[1]) in visible_tiles)
            ]
            if not faces:
                targets[tile] = 0.0
                continue
            tile_faces[tile] = faces
            for fx, fy in faces:
                center_tiles.append(tile)
                center_faces.append((fx, fy))
                c_x1.append(cx + fx * .42)
                c_y1.append(cy + fy * .42)
                c_tx.append(x)
                c_ty.append(y)

        if not center_tiles:
            return
        hits = obs.trace_batch(
            px, py,
            np.asarray(c_x1, dtype=np.float64), np.asarray(c_y1, dtype=np.float32),
            np.asarray(c_tx, dtype=np.int32), np.asarray(c_ty, dtype=np.int32),
            max_dist,
        )
        for tile, hit in zip(center_tiles, hits):
            if hit:
                targets[tile] = 1.0

        unresolved = [tile for tile in tile_faces if tile not in targets]
        if not unresolved:
            return
        g_tiles = []
        g_x1, g_y1, g_tx, g_ty = [], [], [], []
        for tile in unresolved:
            x, y = tile
            cx, cy = x + 0.5, y + 0.5
            for fx, fy in tile_faces[tile]:
                face_x, face_y = cx + fx * .42, cy + fy * .42
                g_tiles.append(tile)
                g_x1.append(face_x - fy * .24)
                g_y1.append(face_y - fx * .24)
                g_tx.append(x)
                g_ty.append(y)
                g_x1.append(face_x + fy * .24)
                g_y1.append(face_y + fx * .24)
                g_tx.append(x)
                g_ty.append(y)

        g_hits = obs.trace_batch(
            px, py,
            np.asarray(g_x1, dtype=np.float64), np.asarray(g_y1, dtype=np.float32),
            np.asarray(g_tx, dtype=np.int32), np.asarray(g_ty, dtype=np.int32),
            max_dist,
        )
        best = {}
        for k, tile in enumerate(g_tiles):
            score = int(g_hits[2 * k]) + int(g_hits[2 * k + 1])
            if score > best.get(tile, 0):
                best[tile] = score
        for tile in unresolved:
            targets[tile] = .32 * best.get(tile, 0)

    def target(self, tile):
        if tile not in self.targets:
            dungeon, _, x, y, closed_doors = self.view
            if self.obstacles is None:
                self.obstacles = _CanopyOcclusion(dungeon, closed_doors)
            self.targets[tile] = canopy_visibility(dungeon, x, y, *tile, obstacles=self.obstacles)
        return self.targets[tile]

    def sample(self, tile, target):
        old = self.previous.get(tile, 0.0)
        value = target if abs(target - old) < 0.004 else old + (target - old) * self.blend
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


@lru_cache(maxsize=2)
def _survey_samples(visible_tiles, cam_x, cam_y):
    coordinates = tuple(visible_tiles)
    tiles = np.array(coordinates, dtype=np.int32)
    offsets = np.array((-4, 0, 4))
    xs = tiles[:, 0, None, None] * TILE_W + TILE_W // 2 - cam_x + offsets[None, :, None]
    ys = tiles[:, 1, None, None] * TILE_H + TILE_H // 2 - cam_y + offsets[None, None, :]
    on_screen = (0 <= xs) & (xs < VIEW_W) & (0 <= ys) & (ys < VIEW_H)
    xs = xs.clip(0, VIEW_W - 1)
    ys = ys.clip(0, VIEW_H - 1)
    return coordinates, xs, ys, on_screen


def visible_lit_tiles(lit_surface, fov_mask, visible_tiles, cam_x, cam_y, *, brightness=None):
    """Use the lit scene before overlays, with a few samples inside each tile."""
    if not visible_tiles:
        return set()
    tiles, xs, ys, on_screen = _survey_samples(frozenset(visible_tiles), round(cam_x), round(cam_y))
    if brightness is None:
        pixels = pygame.surfarray.pixels3d(lit_surface)
        lit = pixels[xs, ys].sum(axis=-1) >= 39
        del pixels
    else:
        lit = brightness[xs, ys] > 0
    readable = on_screen & (fov_mask[xs, ys] > 0.5) & lit
    return {tiles[i] for i in np.flatnonzero(readable.sum(axis=(1, 2)) >= 2)}
