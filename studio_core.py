import math
import pygame
import numpy as np

NORMAL_COMPASS = [
    ("flat",       "⏺ Плоско",     "Смотрит прямо в камеру (+Z)",         (128, 128, 255)),
    ("up",         "⬆ Верх",       "Верхняя грань: ловит свет сверху",    (128, 218, 200)),
    ("down",       "⬇ Низ",        "Нижняя кромка: ловит свет снизу",     (128, 38,  200)),
    ("left",       "⬅ Лево",       "Левый скос: бликует от света слева",  (45,  128, 200)),
    ("right",      "➡ Право",      "Правый скос: бликует справа",         (210, 128, 200)),
    ("up_left",    "↖ Верх-Лев",   "Северо-западный уголок",              (65,  195, 195)),
    ("up_right",   "↗ Верх-Прав",  "Северо-восточный уголок",             (190, 195, 195)),
    ("down_left",  "↙ Низ-Лев",    "Юго-западный скос",                   (65,  60,  195)),
    ("down_right", "↘ Низ-Прав",   "Юго-восточный скос",                  (190, 60,  195)),
    ("deep",       "▣ Впадина",    "Глубокий шов / щель между камнями",   (128, 128, 155)),
]

COMPASS_BY_KEY = {item[0]: item[3] for item in NORMAL_COMPASS}

# Точное горизонтальное отражение индексов компаса для симметрии по X (без погрешности 255-128=127!)
MIRROR_X_COMPASS_IDX = {
    0: 0,  # flat -> flat
    1: 1,  # up -> up
    2: 2,  # down -> down
    3: 4,  # left -> right
    4: 3,  # right -> left
    5: 6,  # up_left -> up_right
    6: 5,  # up_right -> up_left
    7: 8,  # down_left -> down_right
    8: 7,  # down_right -> down_left
    9: 9,  # deep -> deep
}

RPG_PALETTE = [
    (20, 18, 26),   (36, 33, 42),   (52, 46, 62),   (76, 68, 86),
    (105, 98, 118), (145, 150, 168),(190, 200, 215),(235, 240, 248),
    (55, 35, 20),   (85, 52, 30),   (115, 72, 40),  (155, 100, 55),
    (195, 145, 75), (225, 185, 85), (250, 220, 115),(255, 245, 180),
    (22, 42, 30),   (34, 68, 44),   (52, 102, 58),  (85, 155, 75),
    (135, 210, 105),(24, 48, 75),   (42, 85, 130),  (70, 145, 205),
    (110, 215, 245),(95, 30, 40),   (150, 42, 52),  (205, 60, 68),
    (245, 105, 95), (75, 32, 95),   (125, 55, 155), (185, 95, 220),
]


def snap_normal_rgb(r, g, b):
    """Приводит любой RGB нормали строго к одному из 10 эталонных цветов NORMAL_COMPASS."""
    dx = int(r) - 128
    dy = int(g) - 128

    dir_x = -1 if dx < -16 else (1 if dx > 16 else 0)
    dir_y = 1 if dy > 16 else (-1 if dy < -16 else 0)

    if dir_x == 0 and dir_y == 0:
        return COMPASS_BY_KEY["deep"] if b <= 192 else COMPASS_BY_KEY["flat"]
    if dir_x == 0 and dir_y == 1:
        return COMPASS_BY_KEY["up"]
    if dir_x == 0 and dir_y == -1:
        return COMPASS_BY_KEY["down"]
    if dir_x == -1 and dir_y == 0:
        return COMPASS_BY_KEY["left"]
    if dir_x == 1 and dir_y == 0:
        return COMPASS_BY_KEY["right"]
    if dir_x == -1 and dir_y == 1:
        return COMPASS_BY_KEY["up_left"]
    if dir_x == 1 and dir_y == 1:
        return COMPASS_BY_KEY["up_right"]
    if dir_x == -1 and dir_y == -1:
        return COMPASS_BY_KEY["down_left"]
    return COMPASS_BY_KEY["down_right"]


def quantize_normal_surface(norm_surf, diff_surf=None):
    """Квантует всю поверхность карты нормалей строго под 10 цветов NORMAL_COMPASS."""
    w, h = norm_surf.get_size()
    for y in range(h):
        for x in range(w):
            if diff_surf is not None and diff_surf.get_at((x, y))[3] <= 10:
                norm_surf.set_at((x, y), (128, 128, 255, 0))
                continue
            r, g, b, a = norm_surf.get_at((x, y))
            if a <= 10:
                norm_surf.set_at((x, y), (128, 128, 255, 0))
            else:
                sr, sg, sb = snap_normal_rgb(r, g, b)
                norm_surf.set_at((x, y), (sr, sg, sb, 255))
    return norm_surf


def flip_normal_pair_x(diff_surf, norm_surf):
    """Зеркалит пару (diffuse, normal) по горизонтали с честным отражением X-вектора нормали."""
    d_flip = pygame.transform.flip(diff_surf, True, False)
    n_flip = pygame.transform.flip(norm_surf, True, False)
    w, h = n_flip.get_size()
    for y in range(h):
        for x in range(w):
            r, g, b, a = n_flip.get_at((x, y))
            if a > 10:
                dx = int(r) - 128
                sr, sg, sb = snap_normal_rgb(128 - dx, g, b)
                n_flip.set_at((x, y), (sr, sg, sb, a))
    return d_flip, n_flip


def rotate_normal_pair(diff_surf, norm_surf, k_ccw):
    """
    Поворачивает пару (diffuse, normal) на k_ccw * 90° против часовой стрелки,
    поворачивая векторы нормалей (nx, ny), чтобы 2.5D свет оставался физически точным!
    """
    k = k_ccw % 4
    if k == 0:
        return diff_surf.copy(), norm_surf.copy()
    d_rot = pygame.transform.rotate(diff_surf, 90 * k)
    n_rot = pygame.transform.rotate(norm_surf, 90 * k)
    w, h = n_rot.get_size()
    for y in range(h):
        for x in range(w):
            r, g, b, a = n_rot.get_at((x, y))
            if a > 10:
                dx = int(r) - 128
                dy = int(g) - 128
                if k == 1:
                    ndx, ndy = -dy, dx
                elif k == 2:
                    ndx, ndy = -dx, -dy
                else:
                    ndx, ndy = dy, -dx
                sr, sg, sb = snap_normal_rgb(128 + ndx, 128 + ndy, b)
                n_rot.set_at((x, y), (sr, sg, sb, a))
    return d_rot, n_rot


def rgb_to_hex(rgb):
    return "{:02X}{:02X}{:02X}".format(int(rgb[0]), int(rgb[1]), int(rgb[2]))


def hex_to_rgb(hex_str):
    clean = hex_str.strip().lstrip("#")
    if len(clean) == 6:
        try:
            return [int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16)]
        except ValueError:
            return None
    return None


def auto_bevel_normals(diff_surf):
    """Генерирует карту нормалей по силуэту и яркости, используя СТРОГО 10 цветов NORMAL_COMPASS."""
    w, h = diff_surf.get_size()
    norm = pygame.Surface((w, h), pygame.SRCALPHA)
    norm.fill((128, 128, 255, 255))

    def is_solid(x, y):
        if not (0 <= x < w and 0 <= y < h):
            return False
        return diff_surf.get_at((x, y))[3] > 20

    def luma(x, y):
        if not (0 <= x < w and 0 <= y < h):
            return 0.0
        r, g, b, a = diff_surf.get_at((x, y))
        if a <= 20:
            return 0.0
        return 0.299 * r + 0.587 * g + 0.114 * b

    for y in range(h):
        for x in range(w):
            if not is_solid(x, y):
                norm.set_at((x, y), (128, 128, 255, 255))
                continue

            up_empty = not is_solid(x, y - 1)
            dn_empty = not is_solid(x, y + 1)
            lt_empty = not is_solid(x - 1, y)
            rt_empty = not is_solid(x + 1, y)

            nx, ny, nz = 128, 128, 255

            if up_empty and not dn_empty:
                ny = 218
            elif dn_empty and not up_empty:
                ny = 38

            if lt_empty and not rt_empty:
                nx = 45
            elif rt_empty and not lt_empty:
                nx = 210

            if nx == 128 and ny == 128:
                c_lum = luma(x, y)
                if c_lum < 34:
                    nz = 155
                else:
                    dl_x = luma(x - 1, y) - luma(x + 1, y)
                    dl_y = luma(x, y - 1) - luma(x, y + 1)
                    nx = int(np.clip(128 + dl_x * 0.9, 45, 210))
                    ny = int(np.clip(128 - dl_y * 0.9, 38, 218))
                    nz = 215

            sr, sg, sb = snap_normal_rgb(nx, ny, nz)
            norm.set_at((x, y), (sr, sg, sb, 255))
    return norm

class CanvasHistory:
    def __init__(self, max_steps=40):
        self.undo_stack = []
        self.redo_stack = []
        self.max_steps = max_steps

    def _clone_frames(self, frames):
        return [(d.copy(), n.copy()) for d, n in frames]

    def push(self, frames):
        self.undo_stack.append(self._clone_frames(frames))
        if len(self.undo_stack) > self.max_steps:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self, cur_frames):
        if not self.undo_stack:
            return None
        self.redo_stack.append(self._clone_frames(cur_frames))
        return self.undo_stack.pop()

    def redo(self, cur_frames):
        if not self.redo_stack:
            return None
        self.undo_stack.append(self._clone_frames(cur_frames))
        return self.redo_stack.pop()


def flood_fill_surface(surf, start_pos, fill_color):
    w, h = surf.get_size()
    sx, sy = start_pos
    if not (0 <= sx < w and 0 <= y_check(sy, h)):
        return
    target_col = tuple(surf.get_at((sx, sy)))
    fill_col = tuple(fill_color)
    if target_col == fill_col:
        return

    stack = [(sx, sy)]
    visited = set()
    while stack:
        x, y = stack.pop()
        if (x, y) in visited:
            continue
        visited.add((x, y))
        if tuple(surf.get_at((x, y))) == target_col:
            surf.set_at((x, y), fill_col)
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited:
                    stack.append((nx, ny))


def y_check(sy, h):
    return sy < h


class LiveLightPreview:
    def __init__(self, preview_w=216, preview_h=216):
        self.pw = preview_w
        self.ph = preview_h
        self.orbit_angle = 0.0
        self.auto_orbit = True
        self.tile_3x3 = False
        self.random_rot = False
        self.play_anim = True
        self.light_z = 26.0
        self.light_radius = 120.0
        self.torch_warmth = True

    def render(self, diff_surf, norm_surf, dt, rel_mouse=None):
        if self.auto_orbit:
            self.orbit_angle += dt * 1.8

        sw, sh = diff_surf.get_size()
        grid_mult = 3 if self.tile_3x3 else 1
        work_w, work_h = sw * grid_mult, sh * grid_mult

        d_work = pygame.Surface((work_w, work_h), pygame.SRCALPHA)
        n_work = pygame.Surface((work_w, work_h), pygame.SRCALPHA)
        for y in range(work_h):
            for x in range(work_w):
                bg = (24, 22, 32) if (x // 4 + y // 4) % 2 == 0 else (30, 28, 40)
                d_work.set_at((x, y), bg)
                n_work.set_at((x, y), (128, 128, 255))

        for gy in range(grid_mult):
            for gx in range(grid_mult):
                if self.tile_3x3 and self.random_rot and sw == sh:
                    rot_k = ((gx * 3 + gy * 5 + 1) % 4) if (gx != 1 or gy != 1) else 0
                    cell_d, cell_n = rotate_normal_pair(diff_surf, norm_surf, rot_k)
                else:
                    cell_d, cell_n = diff_surf, norm_surf
                d_work.blit(cell_d, (gx * sw, gy * sh))
                for py in range(sh):
                    for px in range(sw):
                        if cell_d.get_at((px, py))[3] > 15:
                            n_work.set_at((gx * sw + px, gy * sh + py), cell_n.get_at((px, py)))

        cx, cy = work_w * 0.5, work_h * 0.5
        if rel_mouse is not None and not self.auto_orbit:
            lx = rel_mouse[0] * work_w
            ly = rel_mouse[1] * work_h
        else:
            r_orbit = max(work_w, work_h) * 0.55
            lx = cx + math.cos(self.orbit_angle) * r_orbit
            ly = cy + math.sin(self.orbit_angle) * r_orbit

        diff_arr = pygame.surfarray.array3d(d_work).astype(np.float32)
        norm_arr = pygame.surfarray.array3d(n_work).astype(np.float32)

        px_grid = np.arange(work_w, dtype=np.float32)[:, None]
        py_grid = np.arange(work_h, dtype=np.float32)[None, :]

        nx = (norm_arr[:, :, 0] - 128.0) / 127.0
        ny = (norm_arr[:, :, 1] - 128.0) / 127.0
        nz = (norm_arr[:, :, 2] - 128.0) / 127.0

        dx = lx - px_grid
        dy = -(ly - py_grid)
        dz = self.light_z

        dist = np.sqrt(dx * dx + dy * dy + dz * dz)
        inv_dist = 1.0 / np.maximum(dist, 0.001)

        raw_dot = nx * (dx * inv_dist) + ny * (dy * inv_dist) + nz * (dz * inv_dist)
        flat_dot = np.maximum(0.0, nz * (dz * inv_dist))
        ndotl = np.maximum(flat_dot * 0.55, raw_dot)
        atten = np.clip(1.0 - (dist / self.light_radius) ** 1.6, 0.0, 1.0)
        intensity = ndotl * atten * 1.65

        amb_r, amb_g, amb_b = 0.16, 0.17, 0.28
        if self.torch_warmth:
            tr, tg, tb = 1.12, 0.80, 0.42
        else:
            tr, tg, tb = 0.55, 0.85, 1.15

        out = np.empty_like(diff_arr)
        out[:, :, 0] = np.clip(diff_arr[:, :, 0] * (amb_r + intensity * tr), 0, 255)
        out[:, :, 1] = np.clip(diff_arr[:, :, 1] * (amb_g + intensity * tg), 0, 255)
        out[:, :, 2] = np.clip(diff_arr[:, :, 2] * (amb_b + intensity * tb), 0, 255)

        lit_surf = pygame.surfarray.make_surface(out.astype(np.uint8))

        scale = min(self.pw // work_w, self.ph // work_h)
        scaled_w, scaled_h = work_w * scale, work_h * scale
        scaled_lit = pygame.transform.scale(lit_surf, (scaled_w, scaled_h))

        final_surf = pygame.Surface((self.pw, self.ph))
        final_surf.fill((16, 14, 22))
        ox = (self.pw - scaled_w) // 2
        oy = (self.ph - scaled_h) // 2
        final_surf.blit(scaled_lit, (ox, oy))

        dot_x = int(ox + (lx / work_w) * scaled_w)
        dot_y = int(oy + (ly / work_h) * scaled_h)
        pygame.draw.circle(final_surf, (255, 220, 90), (dot_x, dot_y), 5)
        pygame.draw.circle(final_surf, (20, 15, 25), (dot_x, dot_y), 5, 1)

        return final_surf