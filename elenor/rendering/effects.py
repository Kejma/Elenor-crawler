from functools import lru_cache
import math
import random
import pygame
import numpy as np
from elenor.config import DEEP_WATER, SHALLOW_WATER, OPAQUE_WALL_TILES, MAP_COLS, MAP_ROWS, TILE_W, TILE_H, VIEW_W, VIEW_H, SCREEN_W, SCREEN_H, UI_PANEL_BG, UI_SLOT_BG, UI_BORDER_GOLD, UI_BORDER_WOOD, UI_BORDER_HIGHLIGHT, UI_TEXT_MAIN, UI_TEXT_DIM
from elenor.data.blood import BLOOD_PALETTES


STEP_LIQUID_TILES = frozenset((2, 23, 32, 44, SHALLOW_WATER, DEEP_WATER))
_RIPPLE_COLORS = {
    "water": ((85, 165, 210), (50, 110, 150)),
    "green": ((128, 214, 102), (62, 137, 70)),
    "blood": ((207, 61, 67), (135, 34, 42)),
}


@lru_cache(maxsize=32)
def _ripple_pixels(rx, ry):
    surf = pygame.Surface((2 * rx, 2 * ry))
    pygame.draw.ellipse(surf, (255, 255, 255), surf.get_rect(), 1)
    return tuple((int(x) - rx, int(y) - ry) for x, y in zip(*np.nonzero(pygame.surfarray.array2d(surf))))


def _is_red_blood(color):
    return color.a >= 180 and color.r > 75 and color.r > 2 * color.g and color.r > 2 * color.b


class FXManager:
    """Управляет всеми графическими эффектами, объёмным туманом, вечными декалями и панелями [F2] / [F3]."""
    def __init__(self, game):
        self.game = game
        self.panel_open = False
        self.f3_open = False
        self.f3_btn_rects = {}
        self._fx_hint_state = None
        self._f2_surf = None
        self._f2_key = None
        self._f3_surf = None
        self._f3_key = None
        self._lbl_cache = {}

        # Тумблеры графических улучшений
        self.flags = {
            "gi": True,
            "specular": True,
            "water_reflections": True,
            "eye_adaptation": True,
            "canopy_wind": True,
            "color_grade": True,
            "heat_combat": True,
            "night_rain": True,
        }

        self.eye_adapt_params = {
            "key": 0.30,
            "strength": 0.35,
            "min_exp": 0.76,
            "max_exp": 1.32,
            "speed_bright": 3.50,
            "speed_dark": 0.75,
            "radius": 2.50,
        }
        self._eye_adapt_defaults = dict(self.eye_adapt_params)
        self.slider_rects = {}
        self._dragging_slider = None

        self.decal_surf = pygame.Surface((MAP_COLS * TILE_W, MAP_ROWS * TILE_H), pygame.SRCALPHA)
        self.decal_revision = 0

        self.wall_grid_np = np.zeros((MAP_COLS, MAP_ROWS), dtype=np.float32)
        self.outdoor_grid_np = np.zeros((MAP_COLS, MAP_ROWS), dtype=np.uint8)
        self.weather_rain = 0.0
        self.weather_target = 0.0
        self.weather_timer = random.uniform(10.0, 22.0)

        self.ripples = []
        self.gibs = []
        self.dust_motes = []
        self._mote_chunks = {}
        self._free_motes = []
        self._mote_view_key = None
        self._mote_view_list = ()
        self.mote_rng = random.Random()
        self.active_clouds = []

        self.shake_timer = 0.0
        self.shake_max_timer = 0.0
        self.shake_amp = 0.0
        self.shake_offset = (0.0, 0.0)

        self.toggle_rects = {}
        self.action_rects = {}
        self.disco_active = False
        self.disco_center = (37.5, 17.5)
        self.disco_time = 0.0

    def _spawn_dust_in_zones(self, dungeon, count=55):
        self.dust_motes = []
        self._mote_chunks = {}
        self._free_motes = []
        self._mote_view_key = None
        self._mote_view_list = ()
        if getattr(dungeon, "campaign", None) == "jungle":
            self._spawn_jungle_motes(dungeon)
            return
        zones = getattr(dungeon, "atmo_zones", [])
        if not zones:
            return
        for _ in range(count):
            z = random.choice(zones)
            r = z["rect"]
            self.dust_motes.append({
                "wx": random.uniform(r.left + 0.3, r.right - 0.3),
                "wy": random.uniform(r.top + 0.3, r.bottom - 0.3),
                "vx": random.uniform(-0.16, 0.16),
                "vy": random.uniform(-0.20, -0.04),
                "phase": random.uniform(0.0, 6.28),
                "size": random.choice([1, 2, 2]),
                "zone_rect": r,
                "kind": z.get("kind", "dust")
            })
        self._free_motes = self.dust_motes

    def _spawn_jungle_motes(self, dungeon):
        rng = self.mote_rng
        outdoors = not dungeon.interior
        for y, row in enumerate(dungeon.grid):
            for x, tile in enumerate(row):
                if rng.random() >= 0.24 or dungeon.is_blocking_move(x, y):
                    continue
                kind = ("firefly" if outdoors and tile in (10, 11, 23, 37, 40, 45, 46)
                        and rng.random() < .35 else "dust")
                anchor = (x + rng.uniform(.30, .70), y + rng.uniform(.30, .70))
                mote = {
                    "wx": anchor[0], "wy": anchor[1], "anchor": anchor, "kind": kind,
                    "phase": rng.uniform(0, math.tau), "size": 1,
                    "rate": rng.uniform(.5, 1.5),
                }
                self.dust_motes.append(mote)
                self._mote_chunks.setdefault((x // 8, y // 8), []).append(mote)

    def motes_in_view(self, cam_x, cam_y):
        if not self._mote_chunks:
            return self._free_motes
        x0 = (int(cam_x) // TILE_W - 1) // 8
        x1 = ((int(cam_x) + VIEW_W) // TILE_W + 1) // 8
        y0 = (int(cam_y) // TILE_H - 1) // 8
        y1 = ((int(cam_y) + VIEW_H) // TILE_H + 1) // 8
        key = (x0, y0, x1, y1)
        if key != self._mote_view_key:
            out = list(self._free_motes)
            chunks = self._mote_chunks
            for cy in range(y0, y1 + 1):
                for cx in range(x0, x1 + 1):
                    bucket = chunks.get((cx, cy))
                    if bucket:
                        out.extend(bucket)
            self._mote_view_key = key
            self._mote_view_list = out
        return self._mote_view_list

    def clear_floor_decals(self):
        self.decal_surf.fill((0, 0, 0, 0))
        self.has_decals = False
        self.decal_revision += 1
        self.ripples.clear()
        self.gibs.clear()

    def rebuild_wall_grid(self, dungeon):
        """Строит карту стен для Ambient Occlusion (БЕЗ деревьев 5!) и заселяет зоны тумана и спор."""
        size = (dungeon.width, dungeon.height)
        if self.wall_grid_np.shape != size:
            self.wall_grid_np = np.zeros(size, dtype=np.float32)
            self.decal_surf = pygame.Surface((size[0]*TILE_W, size[1]*TILE_H), pygame.SRCALPHA)
            self.has_decals = False
            self.decal_revision += 1
        self.wall_grid_np.fill(0.0)
        for ry in range(dungeon.height):
            for rx in range(dungeon.width):
                # Деревья (5) не включены, чтобы вокруг них не было квадратных рамок AO!
                if dungeon.grid[ry][rx] in OPAQUE_WALL_TILES:
                    self.wall_grid_np[rx, ry] = 1.0
        outdoor = np.zeros(size, dtype=np.uint8)
        if dungeon.campaign == "jungle" and not getattr(dungeon, "interior", None):
            outdoor.fill(255)
        elif dungeon.campaign == "rats" and dungeon.floor_num == 1:
            for ry in range(dungeon.height):
                for rx in range(dungeon.width):
                    if dungeon.grid[ry][rx] in (2, 3, 5, 9):
                        outdoor[rx, ry] = 255
        self.outdoor_grid_np = outdoor

        self.active_clouds = []
        for fz in getattr(dungeon, "fog_zones", []):
            self.active_clouds.append({
                "wx": float(fz["wx"]),
                "wy": float(fz["wy"]),
                "radius": float(fz.get("radius", 3.0)),
                "color": tuple(fz.get("color", (0.50, 0.68, 0.85))),
                "density": float(fz.get("density", 0.45)),
                "kind": fz.get("kind", "mist"),
                "bounds": fz.get("bounds"),
                "timer": None,
                "max_timer": None,
                "dmg": 0,
                "tick": 0.0
            })
        self._spawn_dust_in_zones(dungeon)

    # --- ОБЪЁМНЫЙ ТУМАН И ЯДОВИТЫЕ ОБЛАКА ---
    def add_gas_cloud(self, wx, wy, radius=2.3, duration=5.0, kind="poison", dmg=3):
        col = (0.32, 0.95, 0.38) if kind == "poison" else (0.52, 0.68, 0.85)
        dens = 0.68 if kind == "poison" else 0.48
        self.active_clouds.append({
            "wx": float(wx),
            "wy": float(wy),
            "radius": float(radius),
            "color": col,
            "density": dens,
            "kind": kind,
            "timer": float(duration) if duration else None,
            "max_timer": float(duration) if duration else None,
            "dmg": int(dmg),
            "tick": 0.25
        })

    # --- ПАМЯТЬ ПОЛЯ БОЯ (ВЕЧНЫЕ ДЕКАЛИ НА ПОЛУ) ---
    def add_blood_splatter(self, wx, wy, count=5, is_kill=False, *, blood_color="red"):
        self.has_decals = True
        self.decal_revision += 1
        cx = int(wx * TILE_W)
        cy = int((wy + 0.25) * TILE_H)
        palette = BLOOD_PALETTES[blood_color].floor
        if is_kill:
            for _ in range(random.randint(2, 3)):
                pw = random.randint(8, 15)
                ph = random.randint(5, 9)
                px = cx + random.randint(-5, 5) - pw // 2
                py = cy + random.randint(-3, 4) - ph // 2
                pygame.draw.ellipse(self.decal_surf, random.choice(palette[:3]), (px, py, pw, ph))
            for _ in range(random.randint(4, 7)):
                ang = random.uniform(0.0, math.tau)
                dist = random.uniform(7.0, 17.0)
                ex = int(cx + math.cos(ang) * dist)
                ey = int(cy + math.sin(ang) * dist * 0.78)
                pygame.draw.line(self.decal_surf, random.choice(palette), (cx, cy), (ex, ey), random.choice([1, 2]))
        else:
            pw = random.randint(4, 7)
            ph = random.randint(3, 5)
            pygame.draw.ellipse(self.decal_surf, palette[0], (cx - pw // 2, cy - ph // 2, pw, ph))

        n_drops = count * 6 if is_kill else count * 3
        spread = 15 if is_kill else 10
        for _ in range(n_drops):
            ang = random.uniform(0.0, math.tau)
            r = (random.random() ** 0.65) * spread
            ox = int(cx + math.cos(ang) * r)
            oy = int(cy + math.sin(ang) * r * 0.82)
            col = random.choice(palette)
            sz = random.choice([1, 1, 2, 2]) if not is_kill else random.choice([1, 2, 2, 3, 3])
            pygame.draw.rect(self.decal_surf, col, (ox, oy, sz, sz))

    def _splat_wall_blood(self, wx, wy, dx=0.0, dy=0.0, big=False, *, blood_color="red"):
        self.has_decals = True
        self.decal_revision += 1
        cx = int(wx * TILE_W + dx * 3.0)
        cy = int(wy * TILE_H + dy * 3.0)
        blood_pal = BLOOD_PALETTES[blood_color].wall
        n_splat = random.randint(10, 18) if big else random.randint(5, 9)
        rad = 8 if big else 5
        for _ in range(n_splat):
            sx = cx + random.randint(-rad, rad)
            sy = cy + random.randint(-rad, rad)
            sz = random.choice([2, 3, 3, 4]) if big else random.choice([1, 2, 2, 3])
            pygame.draw.rect(self.decal_surf, random.choice(blood_pal), (sx, sy, sz, sz))
        n_drips = random.randint(3, 6) if big else random.randint(1, 3)
        for _ in range(n_drips):
            dr_x = cx + random.randint(-rad + 1, rad - 1)
            dr_y = cy + random.randint(-3, 2)
            dr_len = random.randint(6, 16) if big else random.randint(4, 10)
            pygame.draw.line(self.decal_surf, random.choice(blood_pal[:2]), (dr_x, dr_y), (dr_x, dr_y + dr_len), random.choice([1, 2]))

    def spawn_gibs(self, wx, wy, count=2, is_boss=False, *, blood_color="red"):
        palette = BLOOD_PALETTES[blood_color]
        for _ in range(count):
            ang = random.uniform(0.0, math.tau)
            spd = random.uniform(4.2, 13.5) if is_boss else random.uniform(2.4, 6.2)
            roll = random.random()
            if is_boss and roll > 0.88:
                kind = "crown"
                col = (242, 195, 52)
                w, h = 2, 2
            elif roll > 0.72:
                kind = "bone"
                col = (224, 214, 194)
                w, h = 3, 1
            elif roll > 0.48:
                kind = "limb"
                col = random.choice(palette.limb)
                w, h = 3, 2
            else:
                kind = "meat"
                col = random.choice(palette.meat)
                w, h = 2, 2
            self.gibs.append({
                "wx": float(wx) + random.uniform(-0.2, 0.2),
                "wy": float(wy) + random.uniform(-0.2, 0.2),
                "z": random.uniform(3.0, 9.0) if is_boss else random.uniform(2.0, 6.0),
                "vx": math.cos(ang) * spd,
                "vy": math.sin(ang) * spd,
                "vz": random.uniform(28.0, 68.0) if is_boss else random.uniform(18.0, 42.0),
                "kind": kind,
                "color": col,
                "blood_color": blood_color,
                "w": w,
                "h": h,
                "trail_cd": 0.0,
                "life": random.uniform(2.2, 3.8),
            })

    def add_boss_bloodbath(self, wx, wy, dungeon):
        self.has_decals = True
        self.decal_revision += 1
        cx = int(wx * TILE_W)
        cy = int((wy + 0.2) * TILE_H)
        blood_pal = BLOOD_PALETTES["red"].wall
        # Огромное озеро крови вокруг места гибели босса
        for _ in range(14):
            pw = random.randint(20, 46)
            ph = random.randint(14, 30)
            px = cx + random.randint(-26, 26) - pw // 2
            py = cy + random.randint(-18, 18) - ph // 2
            pygame.draw.ellipse(self.decal_surf, random.choice(blood_pal[:3]), (px, py, pw, ph))

        # 95 мощных артериальных лучей на 12-15 тайлов — достанут до всех стен зала!
        for _ in range(95):
            ang = random.uniform(0.0, math.tau)
            dx, dy = math.cos(ang), math.sin(ang)
            max_px = random.uniform(85.0, 240.0)
            step = 3.0
            d = 4.0
            while d < max_px:
                px = int(cx + dx * d)
                py = int(cy + dy * d)
                tx, ty = px // TILE_W, py // TILE_H
                if not (0 <= tx < dungeon.width and 0 <= ty < dungeon.height):
                    break
                if dungeon.grid[ty][tx] in OPAQUE_WALL_TILES:
                    self._splat_wall_blood(px / TILE_W, py / TILE_H, dx, dy, big=True)
                    # Плюс лужица на полу прямо у подножия забрызганной стены
                    bx_f = int(px - dx * 5.0)
                    by_f = int(py - dy * 5.0)
                    pygame.draw.ellipse(self.decal_surf, random.choice(blood_pal[:2]), (bx_f - 5, by_f - 3, 10, 6))
                    break
                chance = 0.85 if d < 55.0 else (0.55 if d < 120.0 else 0.32)
                if random.random() < chance:
                    sz = random.choice([2, 3, 3]) if d < 50.0 else random.choice([1, 2, 2])
                    pygame.draw.rect(self.decal_surf, random.choice(blood_pal), (px + random.randint(-3, 3), py + random.randint(-3, 3), sz, sz))
                d += step

        # 35 летающих кусков мяса, костей и короны — полетят по всему залу и разобьются о стены!
        self.spawn_gibs(wx, wy, count=35, is_boss=True)

        from elenor.entities import Particle
        for _ in range(140):
            ang = random.uniform(0.0, math.tau)
            spd = random.uniform(1.8, 7.5)
            roll = random.random()
            if roll < 0.72:
                pcol = random.choice([(195, 20, 28), (140, 12, 20), (235, 32, 40)])
                psz = random.uniform(2.2, 4.6)
            elif roll < 0.88:
                pcol = (110, 22, 26)
                psz = random.uniform(3.2, 5.0)
            elif roll < 0.95:
                pcol = (225, 215, 195)
                psz = random.uniform(2.0, 3.0)
            else:
                pcol = (255, 210, 65)
                psz = random.uniform(2.2, 3.4)
            self.game.particles.append(Particle(
                wx + random.uniform(-0.4, 0.4),
                wy + random.uniform(-0.4, 0.4),
                math.cos(ang) * spd,
                math.sin(ang) * spd,
                pcol, size=psz, life=random.uniform(0.45, 1.05),
            ))
        self.trigger_shake(5.5, 0.55)

    def add_barrel_debris(self, tx, ty):
        self.has_decals = True
        self.decal_revision += 1
        cx = int((tx + 0.5) * TILE_W)
        cy = int((ty + 0.5) * TILE_H)
        pygame.draw.ellipse(self.decal_surf, (95, 18, 36, 175), (cx - 6, cy - 3, 12, 7))
        pygame.draw.ellipse(self.decal_surf, (130, 25, 48, 190), (cx - 4, cy - 2, 8, 4))
        planks = [(-6, -4, 4, 2), (3, -5, 4, 2), (-5, 3, 5, 2), (2, 2, 4, 2)]
        for px, py, pw, ph in planks:
            col = random.choice([(122, 74, 36, 235), (96, 56, 26, 235)])
            pygame.draw.rect(self.decal_surf, col, (cx + px, cy + py, pw, ph))
        pygame.draw.rect(self.decal_surf, (78, 84, 96, 225), (cx - 2, cy - 5, 5, 1))

    def add_scorch_mark(self, wx, wy, radius_tiles=0.55):
        self.has_decals = True
        self.decal_revision += 1
        cx = int(wx * TILE_W)
        cy = int(wy * TILE_H)
        r_px = max(3, int(radius_tiles * TILE_W * 0.65))
        for _ in range(14):
            ang = random.uniform(0.0, 6.28)
            dist = random.uniform(0.0, r_px)
            ox = int(cx + math.cos(ang) * dist)
            oy = int(cy + math.sin(ang) * dist * 0.75)
            alpha = int(random.uniform(95, 165) * (1.0 - dist / (r_px + 1.0)))
            pygame.draw.rect(self.decal_surf, (16, 14, 18, alpha), (ox, oy, 2, 2))

    # --- КРУГИ НА ВОДЕ (СТРОГО ПОД ПОДОШВАМИ САПОГ: wy + 0.36!) ---
    def add_water_ripple(self, wx, wy, *, green=False):
        self._add_ripple(wx, wy, "green" if green else "water")

    def add_blood_ripple(self, wx, wy):
        if not self.has_decals:
            return False
        px, py = int(wx * TILE_W), int((wy + .36) * TILE_H)
        bounds = self.decal_surf.get_rect().clip((px - 2, py - 2, 5, 5))
        coverage = sum(
            _is_red_blood(self.decal_surf.get_at((x, y)))
            for y in range(bounds.top, bounds.bottom)
            for x in range(bounds.left, bounds.right)
        )
        if coverage < 17:
            return False
        self._add_ripple(wx, wy, "blood")
        return True

    def _add_ripple(self, wx, wy, kind):
        self.ripples.append({"wx": wx, "wy": wy + .36, "kind": kind, "timer": .55, "max_timer": .55})

    def draw_ripples(self, target, dungeon, cam_x, cam_y):
        clip = target.get_clip()
        grid = dungeon.grid
        width, height = dungeon.width, dungeon.height
        for ripple in self.ripples:
            progress = 1 - ripple["timer"] / ripple["max_timer"]
            rx, ry = int(2 + progress * 7), int(1 + progress * 4)
            wx, wy = int(ripple["wx"] * TILE_W), int(ripple["wy"] * TILE_H)
            sx, sy = int(wx - cam_x), int(wy - cam_y)
            if not clip.colliderect((sx - rx, sy - ry, 2 * rx, 2 * ry)):
                continue
            kind = ripple["kind"]
            color = _RIPPLE_COLORS[kind][progress >= .5]
            for dx, dy in _ripple_pixels(rx, ry):
                x, y = wx + dx, wy + dy
                tx, ty = x // TILE_W, y // TILE_H
                if not (0 <= tx < width and 0 <= ty < height and clip.collidepoint(sx + dx, sy + dy)):
                    continue
                if kind == "blood":
                    if grid[ty][tx] in OPAQUE_WALL_TILES or not _is_red_blood(self.decal_surf.get_at((x, y))):
                        continue
                elif grid[ty][tx] not in STEP_LIQUID_TILES:
                    continue
                target.set_at((sx + dx, sy + dy), color)

    def trigger_shake(self, amplitude=1.8, duration=0.14):
        self.shake_amp = max(self.shake_amp, float(amplitude))
        self.shake_max_timer = max(0.01, float(duration))
        self.shake_timer = max(self.shake_timer, float(duration))

    def update(self, dt, player, dungeon, mobs=None, add_popup=None):
        if dt <= 0:
            return
        if dungeon.campaign == "jungle" and not getattr(dungeon, "interior", None):
            self.weather_timer -= dt
            if self.weather_timer <= 0.0:
                roll = random.random()
                if roll < 0.50:
                    self.weather_target = 0.0
                elif roll < 0.82:
                    self.weather_target = random.uniform(0.28, 0.52)
                else:
                    self.weather_target = random.uniform(0.58, 0.82)
                self.weather_timer = random.uniform(18.0, 42.0)
            diff_w = self.weather_target - self.weather_rain
            step_w = 0.07 * dt
            if abs(diff_w) <= step_w:
                self.weather_rain = self.weather_target
            else:
                self.weather_rain += step_w if diff_w > 0.0 else -step_w
        else:
            self.weather_rain = 0.0
        if self.shake_timer > 0.0:
            self.shake_timer = max(0.0, self.shake_timer - dt)
            fade = self.shake_timer / self.shake_max_timer
            cur_a = self.shake_amp * fade
            self.shake_offset = (
                random.uniform(-cur_a, cur_a),
                random.uniform(-cur_a, cur_a)
            )
            if self.shake_timer <= 0.0:
                self.shake_amp = 0.0
                self.shake_offset = (0.0, 0.0)
        else:
            self.shake_offset = (0.0, 0.0)

        for rp in list(self.ripples):
            rp["timer"] -= dt
            if rp["timer"] <= 0.0:
                self.ripples.remove(rp)

        for gb in list(self.gibs):
            blood_color = gb["blood_color"]
            palette = BLOOD_PALETTES[blood_color]
            gb["life"] -= dt
            gb["trail_cd"] -= dt
            nx = gb["wx"] + gb["vx"] * dt
            ny = gb["wy"] + gb["vy"] * dt

            tx_n, ty_c = int(nx), int(gb["wy"])
            if 0 <= tx_n < dungeon.width and 0 <= ty_c < dungeon.height and dungeon.grid[ty_c][tx_n] in OPAQUE_WALL_TILES:
                self._splat_wall_blood(nx, gb["wy"], 1.0 if gb["vx"] > 0 else -1.0, 0.0, big=(abs(gb["vx"]) > 5.0), blood_color=blood_color)
                gb["vx"] = -gb["vx"] * 0.40
                gb["vy"] *= 0.65
            else:
                gb["wx"] = nx

            tx_c, ty_n = int(gb["wx"]), int(ny)
            if 0 <= tx_c < dungeon.width and 0 <= ty_n < dungeon.height and dungeon.grid[ty_n][tx_c] in OPAQUE_WALL_TILES:
                self._splat_wall_blood(gb["wx"], ny, 0.0, 1.0 if gb["vy"] > 0 else -1.0, big=(abs(gb["vy"]) > 5.0), blood_color=blood_color)
                gb["vy"] = -gb["vy"] * 0.40
                gb["vx"] *= 0.65
            else:
                gb["wy"] = ny

            gb["z"] += gb["vz"] * dt
            gb["vz"] -= 130.0 * dt
            if gb["z"] <= 0.0:
                gb["z"] = 0.0
                if abs(gb["vz"]) > 11.0:
                    gb["vz"] = -gb["vz"] * 0.44
                    gb["vx"] *= 0.68
                    gb["vy"] *= 0.68
                    # Брызг крови в точке отскока от пола
                    bx_p = int(gb["wx"] * TILE_W)
                    by_p = int(gb["wy"] * TILE_H)
                    pygame.draw.ellipse(self.decal_surf, palette.bounce, (bx_p - 3, by_p - 2, 6, 4))
                    self.has_decals = True
                    self.decal_revision += 1
                else:
                    gb["vz"] = 0.0
                    drag = max(0.0, 1.0 - 8.5 * dt)
                    gb["vx"] *= drag
                    gb["vy"] *= drag

            spd_cur = math.hypot(gb["vx"], gb["vy"])
            if gb["trail_cd"] <= 0.0 and spd_cur > 1.1:
                gb["trail_cd"] = 0.025
                bx_p = int(gb["wx"] * TILE_W) + random.randint(-1, 1)
                by_p = int(gb["wy"] * TILE_H) + random.randint(-1, 1)
                pygame.draw.rect(self.decal_surf, random.choice(palette.trail), (bx_p, by_p, random.choice([1, 2]), random.choice([1, 2])))
                self.has_decals = True
                self.decal_revision += 1

            if (gb["z"] <= 0.0 and spd_cur < 0.25) or gb["life"] <= 0.0:
                # Впекаем остановившийся кусок навсегда в пол
                bx_p = int(gb["wx"] * TILE_W)
                by_p = int(gb["wy"] * TILE_H)
                pygame.draw.ellipse(self.decal_surf, palette.settled, (bx_p - 3, by_p - 1, 6, 4))
                pygame.draw.rect(self.decal_surf, (*gb["color"], 245), (bx_p - gb["w"] // 2, by_p - gb["h"] // 2, gb["w"], gb["h"]))
                self.has_decals = True
                self.decal_revision += 1
                self.gibs.remove(gb)

        # Обновление облаков тумана и ядовитого газа
        for cld in list(self.active_clouds):
            if cld["timer"] is not None:
                cld["timer"] -= dt
                if cld["timer"] <= 0.0:
                    self.active_clouds.remove(cld)
                    continue
            if cld["kind"] == "poison" and mobs and add_popup:
                cld["tick"] -= dt
                if cld["tick"] <= 0.0:
                    cld["tick"] = 0.65
                    for m in list(mobs):
                        if (math.hypot(m.x - cld["wx"], m.y - cld["wy"]) <= cld["radius"]
                                and dungeon.has_line_of_sight(cld["wx"],cld["wy"],m.x,m.y,cld["radius"]+.5)):
                            if "growth_credit" not in cld:
                                m.apply_status("poison", 2.5, add_popup, dmg_val=cld["dmg"])
                            self.game.record_combat_growth(m,cld.get("growth_credit"))
                            m.hp -= cld["dmg"]
                            add_popup(m.x, m.y, f"-{cld['dmg']}", (110, 245, 95))
                            self.game._check_mob_death(m)

        # Пылинки и споры летают ТОЛЬКО внутри разрешённых тематических зон (`zone_rect`)!
        if self.dust_motes:
            for dm in self.motes_in_view(getattr(self.game, "cam_x", 0.0), getattr(self.game, "cam_y", 0.0)):
                if "anchor" in dm:
                    x, y = dm["anchor"]
                    dm["phase"] += dt * dm["rate"]
                    amplitude = .27 if dm["kind"] == "firefly" else .13
                    dm["wx"] = x + math.cos(dm["phase"]) * amplitude
                    dm["wy"] = y + math.sin(dm["phase"] * 1.38) * amplitude
                    continue
                dm["phase"] += dt * 1.8
                dm["wx"] += (dm["vx"] + math.sin(dm["phase"]) * 0.12) * dt
                dm["wy"] += dm["vy"] * dt
                zr = dm["zone_rect"]
                if not (zr.left + 0.2 <= dm["wx"] <= zr.right - 0.2 and zr.top + 0.2 <= dm["wy"] <= zr.bottom - 0.2):
                    dm["wx"] = random.uniform(zr.left + 0.3, zr.right - 0.3)
                    dm["wy"] = random.uniform(zr.top + 0.3, zr.bottom - 0.3)

        # Анимация дискотеки: вращение цветных лучей, пульсация стробоскопа и пространственный звук
        if self.disco_active:
            self.disco_time += dt
            cx, cy = self.disco_center
            bpm = 128.0
            beat_phase = (self.disco_time * (bpm / 60.0)) % 1.0

            # 1. Центральный стробоскоп вспыхивает на каждый бит
            strobe_flash = max(0.0, 1.0 - beat_phase * 3.5)
            # 2. Вращение 4 цветных прожекторов по эллиптической орбите вокруг диско-шара
            orbit_r = 2.4

            for rl in dungeon.room_lights:
                if rl.get("is_disco_strobe", False):
                    rl["radius"] = 95.0 + strobe_flash * 40.0
                    int_s = 0.4 + strobe_flash * 1.4
                    rl["color"] = (1.4 * int_s, 1.1 * int_s, 1.8 * int_s)
                elif "disco_idx" in rl:
                    idx = rl["disco_idx"]
                    ang = self.disco_time * 2.2 + idx * (math.pi * 0.5)
                    rl["x"] = cx + math.cos(ang) * orbit_r
                    rl["y"] = cy + math.sin(ang) * (orbit_r * 0.75)
                    rl["radius"] = 78.0 + math.sin(self.disco_time * 4.0 + idx) * 14.0

            # 3. Обновляем пространственную музыку с физикой слоёв стен и мягким сглаживанием
            self.game.sfx.update_disco_spatial(player.x, player.y, cx, cy, dungeon=dungeon, max_dist=30.0, dt=dt)

            # 4. Цветные искры-конфетти на танцполе
            if random.random() < 0.35:
                spark_c = random.choice([
                    (255, 60, 180), (60, 230, 255), (140, 255, 70), (255, 215, 60)
                ])
                from elenor.entities import Particle
                self.game.particles.append(Particle(
                    cx + random.uniform(-2.8, 2.8),
                    cy + random.uniform(-2.2, 2.2),
                    random.uniform(-0.4, 0.4),
                    random.uniform(-0.6, -0.1),
                    spark_c, size=random.uniform(1.8, 3.0), life=0.45
                ))

    # --- ГЕНЕРАТОР ТЕСТОВОЙ КОМНАТЫ (FX-ПОЛИГОН, ЭТАЖ 99) ---
    def enter_test_polygon(self, EnemyCls, InteractableCls):
        g = self.game
        d = g.dungeon
        d.thickets = set()
        d.passages = {}
        d.explored_tiles = {}
        d.map_landmarks = {}
        d.floor_num = 99
        d.rooms = []
        d.braziers = []
        d.room_lights = []
        d.doors = {}
        d.levers = {}
        d.solid_props = set()
        d.overlays = {}
        d.invisible_bounds = set()
        d.invalidate_terrain()

        d.grid = [[1 for _ in range(MAP_COLS)] for _ in range(MAP_ROWS)]

        # 1. Главный зал лабы (x=18..40, y=12..25)
        lab_rect = pygame.Rect(18, 12, 23, 14)
        for ry in range(lab_rect.top, lab_rect.bottom):
            for rx in range(lab_rect.left, lab_rect.right):
                if rx < 25:
                    d.grid[ry][rx] = 4
                elif rx > 33:
                    d.grid[ry][rx] = 8
                else:
                    d.grid[ry][rx] = 0

        # Бассейн с водой слева
        for ry in range(18, 23):
            for rx in range(26, 32):
                if 27 <= rx <= 30 and 19 <= ry <= 21:
                    d.grid[ry][rx] = 2
                else:
                    d.grid[ry][rx] = 3

        # Опорные колонны стоят строго в левой зоне, ковёр танцпола свободен
        for px_c, py_c in ((22, 15), (22, 22), (29, 15), (29, 22)):
            d.grid[py_c][px_c] = 1

        # 2. АКУСТИЧЕСКОЕ КРЫЛО СПРАВА (x=41..60, y=14..25)
        # Южный коридор-галерея (y=22..24, x=37..60)
        for ry in (22, 23, 24):
            for rx in range(37, 60):
                d.grid[ry][rx] = 0
        d.grid[21][37] = 0
        d.grid[21][38] = 0

        # Комната I (за 1 стеной от диско): x=43..46, y=14..20
        for ry in range(14, 21):
            for rx in range(43, 47):
                d.grid[ry][rx] = 0
        d.grid[21][44] = 0  # вход из коридора

        # Комната II (за 2 стенами от диско): x=49..52, y=14..20
        for ry in range(14, 21):
            for rx in range(49, 53):
                d.grid[ry][rx] = 0
        d.grid[21][50] = 0  # вход из коридора

        # Комната III (бункер за 3 стенами): x=55..58, y=14..20
        for ry in range(14, 21):
            for rx in range(55, 59):
                d.grid[ry][rx] = 0
        d.grid[21][56] = 0  # вход из коридора

        poly_rect = pygame.Rect(18, 12, 42, 14)
        d.rooms = [poly_rect]
        d.atmo_zones = [{"rect": poly_rect, "kind": "spores"}]
        d.fog_zones = [
            {"wx": 28.5, "wy": 20.5, "radius": 3.0, "color": (0.48, 0.75, 0.90), "density": 0.45, "kind": "mist"}
        ]
        d.start_pos = (25, 20)
        g.player.x, g.player.y = 25.5, 20.5
        g.player.hp = float(g.player.max_hp)
        g.player.mp = float(g.player.max_mp)

        # Танцпол дискотеки (x=35..40, y=14..20) — ровный ковер
        d.carpets = set()
        for cy in range(14, 21):
            for cx in range(35, 41):
                d.carpets.add((cx, cy))

        d.braziers.append({"x": 22, "y": 14, "color": (1.25, 0.72, 0.28), "radius": 105.0})
        d.braziers.append({"x": 45, "y": 23, "color": (1.10, 0.65, 0.30), "radius": 75.0})
        d.braziers.append({"x": 51, "y": 23, "color": (1.10, 0.65, 0.30), "radius": 75.0})
        d.braziers.append({"x": 57, "y": 23, "color": (1.10, 0.65, 0.30), "radius": 75.0})
        d.room_lights.append({"x": 26, "y": 18, "color": (0.85, 0.75, 0.95), "radius": 120.0})

        # Источники света дискотеки
        self.disco_active = True
        self.disco_center = (37.5, 17.5)
        self.disco_time = 0.0

        d.room_lights.append({"x": 37.5, "y": 17.5, "color": (1.4, 1.2, 1.8), "radius": 110.0, "is_disco_strobe": True})
        disco_spot_colors = [
            (1.5, 0.2, 0.8),  # Hot Magenta
            (0.2, 1.3, 1.5),  # Electric Cyan
            (0.3, 1.5, 0.2),  # Acid Lime
            (1.5, 0.9, 0.1),  # Vivid Amber
        ]
        for i, sc in enumerate(disco_spot_colors):
            d.room_lights.append({"x": 37.5, "y": 17.5, "color": sc, "radius": 85.0, "disco_idx": i})

        g.popups = []
        g.projectiles = []
        g.particles = []
        g.visual_fx = []
        g.mobs = []
        g.objects = []
        self.clear_floor_decals()
        self.rebuild_wall_grid(d)

        g.objects.append(InteractableCls(20, 20, "campfire"))
        g.objects.append(InteractableCls(20, 14, "bed"))
        g.objects.append(InteractableCls(20, 25, "rack"))
        g.objects.append(InteractableCls(26, 14, "npc_merchant"))
        for by_b in (16, 18, 22, 24):
            g.objects.append(InteractableCls(33, by_b, "barrel"))

        # «Диско-шар» на пьедестале в центре танцпола
        g.objects.append(InteractableCls(37, 17, "idol"))

        # Предметы в акустических комнатах для ориентира
        g.objects.append(InteractableCls(44, 15, "chair_bench"))
        g.objects.append(InteractableCls(50, 15, "armor_stand"))
        g.objects.append(InteractableCls(56, 15, "chest"))

        dummy_rat = EnemyCls(27, 15, kind="rat", state="sleeping")
        dummy_rat.max_hp = 9999
        dummy_rat.hp = 9999
        dummy_rat.speed = 0.0

        # Танцующий скелет на танцполе
        disco_skel = EnemyCls(39, 18, kind="skeleton", state="sleeping")
        disco_skel.max_hp = 9999
        disco_skel.hp = 9999
        disco_skel.speed = 0.0
        g.mobs.extend([dummy_rat, disco_skel])

        solid_kinds = {"tavern_table", "bar_counter", "wine_cask", "bed", "fireplace", "shelf_bottles", "cauldron", "crate_stack"}
        d.solid_props = {(obj.x, obj.y) for obj in g.objects if obj.kind in solid_kinds}

        g.cam_x = g.player.x * TILE_W - VIEW_W * 0.5
        g.cam_y = g.player.y * TILE_H - VIEW_H * 0.5
        g.renderer.terrain.warm(d)

        g.sfx.start_disco_track()
        g.set_thought("Акустическое крыло готово! Проверь звук на танцполе и в 3 комнатах справа (за 1, 2 и 3 стенами)!")
        g.sfx.play("levelup")

    def handle_event(self, event, EnemyCls, InteractableCls):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F2:
                self.panel_open = not self.panel_open
                self.game.sfx.play("ui")
                return True
            if event.key == pygame.K_F3:
                self.f3_open = not self.f3_open
                self.game.sfx.play("ui")
                return True

        if self.f3_open and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            p = self.game.player
            for b_key, b_rect in self.f3_btn_rects.items():
                if b_rect.collidepoint((mx, my)):
                    self.game.sfx.play("ui")
                    if b_key == "add_body":
                        p.record_build_action("body", 2.0)
                    elif b_key == "add_cunning":
                        p.record_build_action("cunning", 2.0)
                    elif b_key == "add_mind":
                        p.record_build_action("mind", 2.0)
                    elif b_key == "reset_aff":
                        p.action_affinity = {"body": 0.0, "cunning": 0.0, "mind": 0.0}
                    elif b_key == "add_luck":
                        p.luck = (p.luck % 10) + 1
                    elif b_key == "test_roll":
                        p.pending_perk_rolls = max(1, p.pending_perk_rolls)
                        self.game.roll_perk_choices()
                    return True

        if not self.panel_open:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            for k, rect in self.toggle_rects.items():
                if rect.collidepoint((mx, my)):
                    self.flags[k] = not self.flags[k]
                    self.game.sfx.play("ui")
                    return True

            for act_k, rect in self.action_rects.items():
                if rect.collidepoint((mx, my)):
                    self.game.sfx.play("ui")
                    px, py = self.game.player.x, self.game.player.y
                    if act_k == "tp_lab":
                        self.enter_test_polygon(EnemyCls, InteractableCls)
                    elif act_k == "tp_floor1":
                        self.disco_active = False
                        self.game.sfx.stop_disco_track()
                        self.game.sfx.disco_cur_dry = [0.0, 0.0]
                        self.game.sfx.disco_cur_muff = [0.0, 0.0]
                        self.game.reset_run()
                    elif act_k == "spawn_poison":
                        self.add_gas_cloud(px + 2.0, py, radius=2.4, duration=7.0, kind="poison", dmg=4)
                        self.game.sfx.play("magic")
                    elif act_k == "spawn_mist":
                        self.add_gas_cloud(px, py, radius=3.2, duration=12.0, kind="mist", dmg=0)
                    elif act_k == "splat_blood":
                        self.add_blood_splatter(px + random.uniform(-0.8, 0.8), py + random.uniform(-0.8, 0.8), count=8, is_kill=True)
                        self.add_scorch_mark(px + random.uniform(-1.0, 1.0), py + random.uniform(-1.0, 1.0), 0.6)
                    elif act_k == "clear_decals":
                        self.clear_floor_decals()
                        self.active_clouds = [c for c in self.active_clouds if c["timer"] is None]
                    return True
        return False
    
    def _panel_label(self, font, text, color):
        key = (id(font), text, color)
        surf = self._lbl_cache.get(key)
        if surf is None:
            if len(self._lbl_cache) >= 256:
                self._lbl_cache.clear()
            surf = font.render(text, True, color)
            self._lbl_cache[key] = surf
        return surf

    def render_panel(self, screen, mouse_pos):
        r = self.game.renderer
        window = getattr(self.game, "gl_window", None)
        hint_state = (self.panel_open, self.f3_open)
        if window is None or window.top_dirty or window.full_dirty or window.prev_full_dirty or hint_state != self._fx_hint_state:
            hint_txt = "[F2] FX-Лаб | [F3] Телеметрия билда"
            from elenor.ui.hud import hud_label
            h_s = hud_label(r.font_small, hint_txt, (255, 225, 95) if (self.panel_open or self.f3_open) else UI_TEXT_DIM)
            pygame.draw.rect(screen, (16, 14, 22), (SCREEN_W - h_s.get_width() - 20, 8, h_s.get_width() + 12, 22), border_radius=4)
            pygame.draw.rect(screen, UI_BORDER_WOOD, (SCREEN_W - h_s.get_width() - 20, 8, h_s.get_width() + 12, 22), 1, border_radius=4)
            screen.blit(h_s, (SCREEN_W - h_s.get_width() - 14, 11))
            self._fx_hint_state = hint_state
            if window is not None:
                window.top_dirty = True

        if self.f3_open:
            self._render_f3_telemetry(screen, mouse_pos, window)

        if not self.panel_open:
            return

        pw, ph = 376, 498
        px, py = SCREEN_W - pw - 16, 36
        panel_rect = pygame.Rect(px, py, pw, ph)
        hov_k = next((k for k, rect in self.toggle_rects.items() if rect.collidepoint(mouse_pos)), None)
        if hov_k is None:
            hov_k = next((k for k, rect in self.action_rects.items() if rect.collidepoint(mouse_pos)), None)
        f2_key = (tuple(self.flags.items()), hov_k, bool(self.toggle_rects))
        if f2_key != self._f2_key or self._f2_surf is None:
            if self._f2_surf is None or self._f2_surf.get_size() != (pw, ph):
                self._f2_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
            surf = self._f2_surf
            surf.fill((0, 0, 0, 0))
            r.draw_pixel_frame(surf, (0, 0, pw, ph), UI_PANEL_BG, UI_BORDER_GOLD, False, 1.0)

            title = self._panel_label(r.font_ui, "🧪 ЭКСПЕРИМЕНТАЛЬНЫЕ FX [F2]", UI_BORDER_HIGHLIGHT)
            surf.blit(title, ((pw - title.get_width()) // 2, 12))

            items = [
                ("gi",                "2D Global Illumination (GI)"),
                ("specular",          "PBR-блики и рябь воды"),
                ("water_reflections", "Отражения в воде (SSR)"),
                ("eye_adaptation",    "Адаптация глаз (Eye Adaptation)"),
                ("canopy_wind",       "Ветер в кронах деревьев"),
                ("color_grade",       "Биомный цветокор (Cinematic)"),
                ("heat_combat",       "Марево огня + боевой пост-FX"),
                ("night_rain",        "Ночной дождь и мокрые полы"),
            ]

            self.toggle_rects = {}
            cur_y = 40
            for key, label in items:
                local_r = pygame.Rect(16, cur_y, pw - 32, 32)
                screen_r = local_r.move(px, py)
                self.toggle_rects[key] = screen_r
                hov = screen_r.collidepoint(mouse_pos)
                on = self.flags[key]
                bg = (38, 52, 42) if on else (32, 24, 30)
                if hov:
                    bg = (52, 70, 56) if on else (46, 34, 42)
                pygame.draw.rect(surf, bg, local_r, border_radius=4)
                pygame.draw.rect(surf, (95, 215, 120) if on else (90, 65, 65), local_r, 1, border_radius=4)

                mark = "[✓]" if on else "[ ]"
                m_col = (125, 250, 150) if on else (220, 110, 110)
                surf.blit(self._panel_label(r.font_small, f"{mark} {label}", m_col if on else UI_TEXT_DIM), (local_r.x + 10, local_r.y + 8))
                cur_y += 36

            cur_y += 6
            pygame.draw.line(surf, UI_BORDER_WOOD, (16, cur_y), (pw - 16, cur_y), 1)
            cur_y += 8

            self.action_rects = {}
            buttons = [
                ("tp_lab",       "★ ТЕЛЕПОРТ В FX-ПОЛИГОН (ТЕСТ-ЗАЛ)", (42, 82, 52)),
                ("tp_floor1",    "Вернуться в Таверну Гуго (Этаж 1)",  (48, 38, 54)),
                ("spawn_poison", "+ Ядовитое облако",                  (32, 65, 38)),
                ("spawn_mist",   "+ Густой туман",                     UI_SLOT_BG),
                ("splat_blood",  "+ Кровь и копоть",                   UI_SLOT_BG),
                ("clear_decals", "Очистить всё",                       UI_SLOT_BG),
            ]

            for b_key, b_txt, b_col in buttons[:2]:
                local_br = pygame.Rect(16, cur_y, pw - 32, 33)
                screen_br = local_br.move(px, py)
                self.action_rects[b_key] = screen_br
                hov = screen_br.collidepoint(mouse_pos)
                r.draw_pixel_frame(surf, local_br, (62, 105, 72) if (hov and b_key == "tp_lab") else b_col, UI_BORDER_GOLD if b_key == "tp_lab" else UI_BORDER_WOOD, hov, 1.0)
                ts = self._panel_label(r.font_small, b_txt, (255, 240, 180) if b_key == "tp_lab" else UI_TEXT_MAIN)
                surf.blit(ts, (local_br.centerx - ts.get_width() // 2, local_br.centery - ts.get_height() // 2))
                cur_y += 37

            half_w = (pw - 38) // 2
            for idx, (b_key, b_txt, b_col) in enumerate(buttons[2:]):
                col_i = idx % 2
                row_i = idx // 2
                local_br = pygame.Rect(16 + col_i * (half_w + 6), cur_y + row_i * 35, half_w, 31)
                screen_br = local_br.move(px, py)
                self.action_rects[b_key] = screen_br
                hov = screen_br.collidepoint(mouse_pos)
                r.draw_pixel_frame(surf, local_br, (48, 40, 52) if hov else b_col, UI_BORDER_WOOD, hov, 1.0)
                ts = self._panel_label(r.font_small, b_txt, UI_TEXT_MAIN)
                surf.blit(ts, (local_br.centerx - ts.get_width() // 2, local_br.centery - ts.get_height() // 2))

            hov_after = next((k for k, rect in self.toggle_rects.items() if rect.collidepoint(mouse_pos)), None)
            if hov_after is None:
                hov_after = next((k for k, rect in self.action_rects.items() if rect.collidepoint(mouse_pos)), None)
            self._f2_key = (tuple(self.flags.items()), hov_after, True)

        if window is not None:
            window.set_dev_panel("fx_f2", panel_rect, self._f2_key, self._f2_surf)
        else:
            screen.blit(self._f2_surf, (px, py))

    def _render_f3_telemetry(self, screen, mouse_pos, window=None):
        """Отрисовывает панель [F3] с детальным раскладом Вектора Билда (Силач/Ловкач/Маг) и внутренних переменных."""
        from elenor.config import get_rarity_weights
        r = self.game.renderer
        g = self.game
        p = g.player

        pw, ph = 690, 550
        px, py = 16, 218
        panel_rect = pygame.Rect(px, py, pw, ph)
        hov_b = next((k for k, rect in self.f3_btn_rects.items() if rect.collidepoint(mouse_pos)), None)
        tick_4hz = pygame.time.get_ticks() // 250
        f3_key = (
            tick_4hz, hov_b, p.luck,
            round(p.action_affinity["body"], 2),
            round(p.action_affinity["cunning"], 2),
            round(p.action_affinity["mind"], 2),
            len(p.perks), bool(self.f3_btn_rects),
            self.flags.get("eye_adaptation", True),
            self.flags.get("color_grade", True),
        )
        if f3_key != self._f3_key or self._f3_surf is None:
            if self._f3_surf is None or self._f3_surf.get_size() != (pw, ph):
                self._f3_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
            surf = self._f3_surf
            surf.fill((0, 0, 0, 0))
            r.draw_pixel_frame(surf, (0, 0, pw, ph), (18, 16, 26), UI_BORDER_GOLD, False, 1.0)

            hdr = self._panel_label(r.font_ui, "📊 [F3] ОТЛАДКА ВЕКТОРА БИЛДА И ПЕРЕМЕННЫХ", UI_BORDER_HIGHLIGHT)
            surf.blit(hdr, ((pw - hdr.get_width()) // 2, 12))

            stat_part = {
                "body": max(0.0, (p.body - 1) * 1.5),
                "cunning": max(0.0, (p.cunning - 1) * 1.5),
                "mind": max(0.0, (p.mind - 1) * 1.5),
            }
            equip_part = {"body": 0.0, "cunning": 0.0, "mind": 0.0}
            for itm in p.equipment.values():
                if not itm or itm.is_torch:
                    continue
                if itm.armor_class == "plate" or itm.two_handed or itm.weap_style in ("mace", "cleaver", "axe"):
                    equip_part["body"] += 2.5
                if itm.armor_class == "leather" or itm.weap_style in ("dagger", "spear") or itm.noise_mod < 0:
                    equip_part["cunning"] += 2.5
                if itm.armor_class == "cloth" or itm.mag_bonus > 0 or itm.mp_regen > 0:
                    equip_part["mind"] += 2.8
                equip_part["body"] += itm.phys_bonus * 0.7 + itm.phys_def * 0.5
                equip_part["mind"] += itm.mag_bonus * 1.1 + itm.mag_def * 0.6

            perk_tags = {
                "tough_skin": "body", "iron_grip": "body", "stone_ribs": "body",
                "titan_blood": "body", "blood_hunger": "body", "whirlwind": "body", "earth_slam": "body",
                "cat_step": "cunning", "keen_edge": "cunning", "throw_knife": "cunning", "poison_flask": "cunning",
                "clear_mind": "mind", "storm_aura": "mind",
                "pyro_firebolt": "mind", "pyro_ignite": "mind",
                "stratos_frost_nova": "mind", "stratos_chain_lightning": "mind",
                "persephone_rejuvenation": "mind", "persephone_entangle": "mind"
            }
            perk_part = {"body": 0.0, "cunning": 0.0, "mind": 0.0}
            for pid, lvl in p.perks.items():
                perk_part[perk_tags.get(pid, "body")] += lvl * 3.0

            total_scores = p.get_build_affinities()
            total_sum = sum(total_scores.values()) + 1.0

            branches = [
                ("body",    "СИЛАЧ (Тело)",     (235, 115, 105)),
                ("cunning", "ЛОВКАЧ (Ловк.)",   (115, 235, 150)),
                ("mind",    "МАГ (Разум)",      (120, 195, 255)),
            ]

            cur_y = 40
            for b_key, b_title, b_col in branches:
                tot = total_scores[b_key]
                share = tot / total_sum
                mult = 1.0 + 1.45 * share

                box_b = pygame.Rect(14, cur_y, pw - 28, 66)
                pygame.draw.rect(surf, (26, 22, 34), box_b, border_radius=4)
                pygame.draw.rect(surf, b_col, box_b, 1, border_radius=4)

                top_line = f"{b_title}: {tot:.2f} очк. | Доля: {int(round(share * 100))}% -> Шанс перков: x{mult:.2f}"
                surf.blit(r.font_small.render(top_line, True, b_col), (box_b.x + 8, box_b.y + 6))

                sub_line = (
                    f"Статы: {stat_part[b_key]:.1f}  |  Шмот: {equip_part[b_key]:.1f}  |  "
                    f"Перки: {perk_part[b_key]:.1f}  |  Действия: {p.action_affinity[b_key]:.2f}"
                )
                surf.blit(r.font_small.render(sub_line, True, UI_TEXT_MAIN), (box_b.x + 8, box_b.y + 25))

                bar_w = box_b.width - 16
                pygame.draw.rect(surf, (14, 12, 18), (box_b.x + 8, box_b.y + 46, bar_w, 12))
                pygame.draw.rect(surf, b_col, (box_b.x + 9, box_b.y + 47, int((bar_w - 2) * share), 10))
                cur_y += 72

            self.f3_btn_rects = {}
            btn_specs = [
                ("add_body",    "+2 Силач"),
                ("add_cunning", "+2 Ловкач"),
                ("add_mind",    "+2 Маг"),
                ("reset_aff",   "Сброс действ."),
                ("add_luck",    f"Удача: {p.luck} (+1)"),
                ("test_roll",   "🎲 Тест Перков"),
            ]
            bw = (pw - 40) // 3
            for idx, (bk, bt) in enumerate(btn_specs):
                ci = idx % 3
                ri = idx // 3
                local_br = pygame.Rect(14 + ci * (bw + 6), cur_y + ri * 32, bw, 28)
                screen_br = local_br.move(px, py)
                self.f3_btn_rects[bk] = screen_br
                hov = screen_br.collidepoint(mouse_pos)
                pygame.draw.rect(surf, (52, 44, 62) if hov else (34, 28, 44), local_br, border_radius=4)
                pygame.draw.rect(surf, UI_BORDER_GOLD if bk == "test_roll" else UI_BORDER_WOOD, local_br, 1, border_radius=4)
                ts = self._panel_label(r.font_small, bt, (255, 230, 110) if bk == "test_roll" else UI_TEXT_MAIN)
                surf.blit(ts, (local_br.centerx - ts.get_width() // 2, local_br.centery - ts.get_height() // 2))
            cur_y += 70

            pygame.draw.line(surf, UI_BORDER_WOOD, (14, cur_y), (pw - 14, cur_y), 1)
            cur_y += 8

            rw = get_rarity_weights(p.luck)
            rw_str = f"Редкость (Удача {p.luck}): Бел {rw[0]:.0f}% | Зел {rw[1]:.1f}% | Син {rw[2]:.1f}% | Эпик {rw[3]:.1f}% | Лег {rw[4]:.1f}%"
            surf.blit(r.font_small.render(rw_str, True, (255, 215, 110)), (14, cur_y))
            cur_y += 22

            postfx = getattr(r.gpu_shader, "postfx", None)
            grade_lbl = (postfx.active_grade_name if (postfx and self.flags.get("color_grade", True)) else "ВЫКЛ")
            if not self.flags.get("eye_adaptation", True):
                exp_line = f"Адаптация: ВЫКЛ (x1.00)  |  Цветокор: {grade_lbl}"
                exp_col = UI_TEXT_DIM
            elif postfx is not None:
                exp_info = postfx.read_exposure()
                if exp_info is not None:
                    cur_e, avg_l, tgt_e = exp_info
                    exp_line = f"Эксп: x{cur_e:.2f}->x{tgt_e:.2f} (ярк {avg_l:.3f})  |  Грейд: {grade_lbl}"
                    exp_col = (130, 235, 255)
                else:
                    exp_line = f"Адаптация: нет данных  |  Грейд: {grade_lbl}"
                    exp_col = UI_TEXT_DIM
            else:
                exp_line = "Пост-эффекты: недоступны (CPU-рендер)"
                exp_col = UI_TEXT_DIM
            surf.blit(r.font_small.render(exp_line, True, exp_col), (14, cur_y))
            cur_y += 22

            win_res = g.display_surface.get_size() if hasattr(g, "display_surface") and g.display_surface else (SCREEN_W, SCREEN_H)
            vars_lines = [
                f"Характер: {p.full_name}  |  Причуда (Quirk): {getattr(p, 'quirk', 'none')}",
                f"Освещённость героя: {p.illumination:.2f}  |  Шум шагов: {int(p.noise_factor * 100)}%  |  Мана за удар: +{p.mp_on_hit:.1f}",
                f"Таймер фоновых мыслей: {g.bg_thought_cd:.1f}с  |  Блок важной мысли: {g.important_thought_lock:.1f}с",
                f"Очередь важных мыслей: {len(g.important_thought_queue)} шт.  |  Записей в журнале: {len(g.journal_logs)}/100",
                f"Окно: {win_res[0]}x{win_res[1]} (Внутренний рендер: {SCREEN_W}x{SCREEN_H} Nearest-Neighbor)",
            ]
            for v_ln in vars_lines:
                surf.blit(r.font_small.render(v_ln, True, UI_TEXT_DIM), (14, cur_y))
                cur_y += 19

            hov_after = next((k for k, rect in self.f3_btn_rects.items() if rect.collidepoint(mouse_pos)), None)
            self._f3_key = (
                tick_4hz, hov_after, p.luck,
                round(p.action_affinity["body"], 2),
                round(p.action_affinity["cunning"], 2),
                round(p.action_affinity["mind"], 2),
                len(p.perks), True,
                self.flags.get("eye_adaptation", True),
            )

        if window is not None:
            window.set_dev_panel("fx_f3", panel_rect, self._f3_key, self._f3_surf)
        else:
            screen.blit(self._f3_surf, (px, py))