from collections import deque
import heapq
import math
import random
import pygame
import numpy as np
from elenor.config import MAP_COLS, MAP_ROWS, TILE_W, TILE_H, VIEW_W, VIEW_H, CANVAS_H, RAY_COUNT, LOS_MAX_RADIUS, MERCHANT_ROOM_CHANCE, DEEP_WATER, OPAQUE_WALL_TILES


class Door:
    def __init__(self, x, y, locked_by_lever=False):
        self.x = x
        self.y = y
        self.is_open = False
        self.locked = locked_by_lever
        self.key_color = None


class Lever:
    def __init__(self, x, y, target_doors):
        self.x = x
        self.y = y
        self.pulled = False
        self.target_doors = target_doors


class Dungeon:
    revealed_fov = np.ones((CANVAS_H, VIEW_W), dtype=np.float32).T
    revealed_fov.flags.writeable = False

    def __init__(self, puzzle_profile="procedural", puzzle_chance=0.12, merchant_chance=MERCHANT_ROOM_CHANCE):
        # The campaign opts into its fixed introduction explicitly.
        if puzzle_profile not in ("rats", "procedural"):
            raise ValueError("Unknown puzzle profile")
        self.puzzle_profile = puzzle_profile
        self.puzzle_chance = max(0.0, min(1.0, float(puzzle_chance)))
        self.merchant_chance = max(0.0, min(1.0, float(merchant_chance)))
        self.floor_num = 1
        self.grid = [[1 for _ in range(MAP_COLS)] for _ in range(MAP_ROWS)]
        self.rooms = []
        self.braziers = []
        self.room_lights = []
        self.doors = {}
        self.levers = {}
        self.solid_props = set()
        self.overlays = {}
        self._light_cache = {}
        self._last_viewer_pos = (8.0, 20.0)
        # Предвычисленные матрицы лучей для мгновенного векторного расчёта FOV
        angles = np.radians(np.arange(RAY_COUNT, dtype=np.float32) * (360.0 / RAY_COUNT))
        radii = np.arange(2.0, LOS_MAX_RADIUS, 2.0, dtype=np.float32)[None, :]
        self._ray_dx = np.cos(angles)[:, None] * radii
        self._ray_dy = np.sin(angles)[:, None] * radii
        self._ray_indices = np.arange(RAY_COUNT)
        self._ray_steps = np.arange(radii.shape[1])[None, :]
        c_ang = np.radians(np.arange(120, dtype=np.float32) * (360.0 / 120))
        c_rad = np.arange(2.0, LOS_MAX_RADIUS, 4.0, dtype=np.float32)[None, :]
        self._coarse_dx = np.cos(c_ang)[:, None] * c_rad
        self._coarse_dy = np.sin(c_ang)[:, None] * c_rad
        self._coarse_steps = np.arange(c_rad.shape[1])[None, :]
        self._coarse_fov_key = None
        self._fov_surf = pygame.Surface((VIEW_W, VIEW_H), depth=8)
        self._fov_full_mask = np.ones((CANVAS_H, VIEW_W), dtype=np.float32).T
        self._base_block_grid = None
        self.forest_rect = pygame.Rect(3, 12, 14, 16)
        self.start_pos = (8, 20)
        self.boss_room = None
        self.carpets = set()
        self.moss_tiles = set()
        self.generate(floor_num=1)

    def _has_adjacent_door(self, x, y):
        for nx, ny in ((x, y), (x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if (nx, ny) in self.doors:
                return True
        return False

    def invalidate_light_cache(self):
        self.geometry_revision = getattr(self, "geometry_revision", 0) + 1
        self._light_cache = {}
        self._base_block_grid = None
        self._fov_key = None
        self._world_fov_key = None
        self._sight_doors = None
        self._coarse_fov_key = None

    def invalidate_terrain(self, area=None):
        """Mark a terrain edit. A tile rectangle limits the redraw to nearby chunks."""
        self.terrain_revision = getattr(self, "terrain_revision", 0) + 1
        self.terrain_dirty_area = None if area is None else pygame.Rect(area)
        self.invalidate_light_cache()

    @property
    def width(self):
        return len(self.grid[0])

    @property
    def height(self):
        return len(self.grid)

    def _carve_rect(self, rect, floor_id):
        for ry in range(rect.top, rect.bottom):
            for rx in range(rect.left, rect.right):
                if 1 <= rx < self.width - 1 and 1 <= ry < self.height - 1:
                    self.grid[ry][rx] = floor_id

    def generate(self, floor_num=1, *, campaign="rats", interior=None, route_variant=0):
        self.floor_num = floor_num
        self.campaign = campaign
        self.thickets = set()
        self.passages = {}
        self.jungle_gate = None
        self.jungle_controls = {}
        self.jungle_keys = set()
        self.jungle_starter_cache = None
        self.jungle_bag_cache = None
        self.explored_tiles = {}
        self.exploration_revision = 0
        self.map_landmarks = {}
        self.interior = interior
        self.jungle_route_variant = route_variant
        self.fishing_edges = {}
        self.rooms = []
        self.braziers = []
        self.room_lights = []
        self.doors = {}
        self.levers = {}
        self.solid_props = set()
        self.overlays = {}
        self.carpets = set()
        self.moss_tiles = set()
        self.atmo_zones = []
        self.fog_zones = []
        self.merchant_room = None
        self.boss_room = None
        self.pre_boss_puzzle_info = None
        self.mirror_puzzle_info = None
        self.invalidate_terrain()

        # =====================================================================
        # ЯРУС 1: ИНТРО — ДВОР У КОСТРА И ДОМ-ТАВЕРНА СО ВСЕМ ИНТЕРЬЕРОМ
        # =====================================================================
        self.invisible_bounds = set()
        if campaign == "jungle":
            from elenor.world.jungle import generate_jungle_floor
            generate_jungle_floor(self)
            trees = {21, 22, 56, 57}
            trunks = {(x, y) for y, row in enumerate(self.grid)
                      for x, tile in enumerate(row) if tile in trees}
            self.thickets = {
                (x, y) for x, y in trunks
                if any(neighbour in trunks for neighbour in
                       ((x+1, y), (x-1, y), (x, y+1), (x, y-1)))
            }
            return

        # =====================================================================
        # ЯРУС 1: ЖИВОПИСНЫЙ ЛЕС С БОЛЬШОЙ ДОРОГОЙ, ТРОПОЙ И ДОМОМ-ТАВЕРНОЙ
        # =====================================================================
        if floor_num == 1:
            self.grid = [[3 for _ in range(MAP_COLS)] for _ in range(MAP_ROWS)]

            # 1. Естественный лес вокруг (не коробка, а живые куртины деревьев, сквозь которые виден дальний лес!)
            for ry in range(MAP_ROWS):
                for rx in range(MAP_COLS):
                    if rx >= 46 or ry <= 3 or ry >= MAP_ROWS - 4:
                        self.grid[ry][rx] = 5
                    elif rx < 17:
                        # Органичные рощицы сосен вдоль большой дороги
                        h_tree = (rx * 37 + ry * 73 + (rx ^ ry) * 19) % 17
                        dist_trail = abs(ry - 20) if 4 <= rx <= 17 else 99
                        dist_road = abs(rx - 5 + int(math.sin(ry * 0.25) * 1.2))
                        if dist_road > 2.2 and dist_trail > 2.8 and h_tree in (0, 1, 2, 3, 4):
                            self.grid[ry][rx] = 5

            # 2. Большая лесная дорога (код 9 = floor_6) с севера на юг и тропа к крыльцу таверны
            for ry in range(1, MAP_ROWS - 1):
                road_cx = 5 + int(math.sin(ry * 0.22) * 1.2)
                for rx in range(road_cx - 1, road_cx + 2):
                    if 1 <= rx < 16:
                        self.grid[ry][rx] = 9

            # Тропа от большой дороги к дверям таверны + поляна у костра
            for ry in range(16, 25):
                for rx in range(6, 17):
                    if math.hypot(rx - 10, ry - 20) <= 4.2:
                        self.grid[ry][rx] = 3
            for rx in range(5, 17):
                self.grid[20][rx] = 9
                if (rx + 1) % 2 == 0:
                    self.grid[19][rx] = 9
                else:
                    self.grid[21][rx] = 9
            self.grid[20][15] = 4
            self.grid[20][16] = 4

            # Невидимая коллизия по краям лесной поляны и дороги (лес и уходящий тракт видно, но уйти за край нельзя!)
            for ry in range(MAP_ROWS):
                for rx in range(18):
                    if rx < 3 or ry < 11 or ry > 29:
                        self.invisible_bounds.add((rx, ry))

            # 3. Здание Таверны (бревенчатые стены `6` = wall_wood, полы `4` = доски)
            for ry in range(7, 34):
                for rx in range(17, 46):
                    self.grid[ry][rx] = 6

            main_hall = pygame.Rect(18, 15, 14, 11)   # Главный зал со столами и стойкой Гуго
            north_room = pygame.Rect(19, 8, 12, 6)    # Спальня Гуго
            south_room = pygame.Rect(19, 27, 12, 6)   # Кухня и винокурня
            pantry_room = pygame.Rect(33, 16, 11, 9)  # Задний чулан со стойкой оружия и спуском в подвал

            for r in (main_hall, north_room, south_room, pantry_room):
                self._carve_rect(r, 4)

            self.grid[15][25] = 0
            self.grid[15][26] = 0

            for dx, dy in ((17, 20), (22, 14), (24, 26), (32, 20)):
                self.grid[dy][dx] = 4
                self.doors[(dx, dy)] = Door(dx, dy, locked_by_lever=False)

            # Большой парадный ковёр в Главном Зале (перед камином и между столами)
            for cy in range(18, 23):
                for cx in range(21, 27):
                    self.carpets.add((cx, cy))

            # Уютный ковёр в хозяйской спальне Гуго
            for cy in range(10, 14):
                for cx in range(22, 27):
                    self.carpets.add((cx, cy))

            yard = pygame.Rect(4, 13, 13, 15)
            self.forest_rect = yard
            self.rooms = [yard, main_hall, north_room, south_room, pantry_room]
            self.start_pos = (6, 20)

            # Освещение дороги, костра и тёплого интерьера таверны
            self.room_lights.append({"x": 8, "y": 20, "color": (0.45, 0.58, 0.85), "radius": 135.0})
            self.room_lights.append({"x": 5, "y": 11, "color": (0.38, 0.50, 0.78), "radius": 110.0})
            self.room_lights.append({"x": 5, "y": 29, "color": (0.38, 0.50, 0.78), "radius": 110.0})
            self.room_lights.append({"x": main_hall.centerx, "y": main_hall.centery, "color": (1.20, 0.82, 0.42), "radius": 145.0})
            self.room_lights.append({"x": north_room.centerx, "y": north_room.centery, "color": (1.05, 0.75, 0.40), "radius": 95.0})
            self.room_lights.append({"x": south_room.centerx, "y": south_room.centery, "color": (1.05, 0.72, 0.38), "radius": 95.0})
            self.room_lights.append({"x": pantry_room.centerx, "y": pantry_room.centery, "color": (1.00, 0.68, 0.35), "radius": 100.0})

            self.braziers.append({"x": 24, "y": 15, "color": (1.25, 0.72, 0.28), "radius": 95.0})
            self.braziers.append({"x": 19, "y": 16, "color": (1.15, 0.75, 0.35), "radius": 82.0})
            self.braziers.append({"x": 30, "y": 24, "color": (1.15, 0.75, 0.35), "radius": 82.0})
            self.braziers.append({"x": 34, "y": 17, "color": (1.10, 0.68, 0.30), "radius": 80.0})
            # Атмосферная пыльца/светлячки и клочья ночного тумана ТОЛЬКО на улице в лесу (внутри таверны чисто!)
            self.atmo_zones.append({"rect": pygame.Rect(1, 2, 15, MAP_ROWS - 4), "kind": "forest"})
            self.fog_zones.append({"wx": 5.5, "wy": 14.0, "radius": 3.4, "color": (0.45, 0.62, 0.85), "density": 0.42, "kind": "mist"})
            self.fog_zones.append({"wx": 6.0, "wy": 26.0, "radius": 3.6, "color": (0.45, 0.62, 0.85), "density": 0.42, "kind": "mist"})

            # Раскладываем полупрозрачные оверлеи: камушки и мох на лесной дороге
            for ry in range(1, MAP_ROWS - 1):
                for rx in range(1, MAP_COLS - 1):
                    t_id = self.grid[ry][rx]
                    h_ov = (rx * 61 + ry * 107 + (rx ^ ry) * 29) % 100
                    if t_id == 9:  # Лесная дорога
                        if h_ov < 48:
                            self.overlays[(rx, ry)] = "ov_pebbles"
                        elif h_ov < 62:
                            self.overlays[(rx, ry)] = "ov_moss"
            return

        # =====================================================================
        # ЯРУСЫ 2, 3, 4: ДЕРЕВЯННЫЙ ПОДВАЛ -> КАМЕННЫЙ ПОДВАЛ -> ПЕЩЕРЫ С БОССОМ
        # =====================================================================
        if floor_num == 2:
            base_wall = 6  # Бревенчатые стены погреба
        elif floor_num == 3:
            base_wall = 1  # Каменная кирпичная кладка
        else:
            base_wall = 7  # Дикая скальная порода пещер

        self.grid = [[base_wall for _ in range(MAP_COLS)] for _ in range(MAP_ROWS)]

        reserved_puzzle_zone = None

        tutorial = self.puzzle_profile == "rats"
        has_puzzle_zone = (floor_num >= 4) if tutorial else random.random() < self.puzzle_chance
        zone_info = None
        if has_puzzle_zone:
            # Случайно выбираем сторону света и смещение для комплекса [Зал Головоломки -> Зал Босса]
            zone_dir = random.choice(["east", "west", "north", "south"])
            depth = min(3, max(0, floor_num - 2))
            pw, ph = (11, 9) if tutorial else (11 + depth * 2, 9 + depth * 2)
            bw, bh = (18, 14) if tutorial else (7, 7)
            if zone_dir == "east":
                bx = MAP_COLS - bw - 3
                by = random.randint(max(4, ph // 2 - bh // 2 + 2),
                                    min(MAP_ROWS - bh - 4, MAP_ROWS - 2 - bh // 2 + ph // 2 - ph))
                sealed_rect = pygame.Rect(bx, by, bw, bh)
                p_rect = pygame.Rect(bx - pw - 1, sealed_rect.centery - ph // 2, pw, ph)
                entry_door_xy = (p_rect.left - 1, p_rect.centery)
                gate_door_xy = (sealed_rect.left - 1, p_rect.centery)
                outer_entry_xy = (p_rect.left - 2, p_rect.centery)
            elif zone_dir == "west":
                bx = 3
                by = random.randint(max(4, ph // 2 - bh // 2 + 2),
                                    min(MAP_ROWS - bh - 4, MAP_ROWS - 2 - bh // 2 + ph // 2 - ph))
                sealed_rect = pygame.Rect(bx, by, bw, bh)
                p_rect = pygame.Rect(bx + bw + 1, sealed_rect.centery - ph // 2, pw, ph)
                entry_door_xy = (p_rect.right, p_rect.centery)
                gate_door_xy = (sealed_rect.right, p_rect.centery)
                outer_entry_xy = (p_rect.right + 1, p_rect.centery)
            elif zone_dir == "north":
                bw, bh = (18, 12) if tutorial else (7, 7)
                bx = random.randint(8, MAP_COLS - bw - 8)
                by = 3
                sealed_rect = pygame.Rect(bx, by, bw, bh)
                p_rect = pygame.Rect(sealed_rect.centerx - pw // 2, by + bh + 1, pw, ph)
                entry_door_xy = (p_rect.centerx, p_rect.bottom)
                gate_door_xy = (p_rect.centerx, sealed_rect.bottom)
                outer_entry_xy = (p_rect.centerx, p_rect.bottom + 1)
            else:  # "south"
                bw, bh = (18, 12) if tutorial else (7, 7)
                bx = random.randint(8, MAP_COLS - bw - 8)
                by = MAP_ROWS - bh - 3
                sealed_rect = pygame.Rect(bx, by, bw, bh)
                p_rect = pygame.Rect(sealed_rect.centerx - pw // 2, by - ph - 1, pw, ph)
                entry_door_xy = (p_rect.centerx, p_rect.top - 1)
                gate_door_xy = (p_rect.centerx, sealed_rect.top - 1)
                outer_entry_xy = (p_rect.centerx, p_rect.top - 2)

            reserved_puzzle_zone = sealed_rect.union(p_rect).inflate(4, 4)
            zone_info = {
                "dir": zone_dir,
                "puzzle_rect": p_rect,
                "sealed_rect": sealed_rect,
                "entry_door": entry_door_xy,
                "gate_door": gate_door_xy,
                "outer_entry": outer_entry_xy,
                "tutorial": tutorial,
            }
            self.mirror_puzzle_info = zone_info
            if tutorial:
                self.pre_boss_puzzle_info = dict(zone_info, boss_rect=sealed_rect, boss_door=gate_door_xy)

        attempts = 85 if floor_num >= 4 else 65

        for _ in range(attempts):
            w = random.randint(6, 10)
            h = random.randint(5, 8)
            x = random.randint(3, MAP_COLS - w - 3)
            y = random.randint(3, MAP_ROWS - h - 3)
            new_rect = pygame.Rect(x, y, w, h)

            if reserved_puzzle_zone and new_rect.inflate(2, 2).colliderect(reserved_puzzle_zone):
                continue

            if not any(new_rect.inflate(2, 2).colliderect(r) for r in self.rooms):
                bend_first_horiz = True
                if self.rooms and reserved_puzzle_zone:
                    px, py = self.rooms[-1].center
                    cx, cy = new_rect.center
                    inner_res = reserved_puzzle_zone.inflate(-2, -2)
                    h1 = pygame.Rect(min(px, cx), py, abs(cx - px) + 1, 2)
                    v1 = pygame.Rect(cx, min(py, cy), 2, abs(cy - py) + 1)
                    if h1.colliderect(inner_res) or v1.colliderect(inner_res):
                        v2 = pygame.Rect(px, min(py, cy), 2, abs(cy - py) + 1)
                        h2 = pygame.Rect(min(px, cx), cy, abs(cx - px) + 1, 2)
                        if v2.colliderect(inner_res) or h2.colliderect(inner_res):
                            continue
                        bend_first_horiz = False

                base_fl = 4 if floor_num == 2 else (0 if floor_num == 3 else 8)
                for ry in range(y, y + h):
                    for rx in range(x, x + w):
                        if floor_num >= 4 and (rx in (x, x + w - 1)) and (ry in (y, y + h - 1)) and random.random() < 0.65:
                            continue
                        self.grid[ry][rx] = base_fl

                if floor_num == 2 and len(self.rooms) > 0 and random.random() < 0.30:
                    self.atmo_zones.append({"rect": new_rect, "kind": "dust"})
                elif floor_num in (3, 4) and len(self.rooms) > 0:
                    feat_roll = random.random()
                    if feat_roll < 0.35 and w >= 6 and h >= 6:
                        px_c = random.uniform(x + 2.2, x + w - 2.2)
                        py_c = random.uniform(y + 2.0, y + h - 2.0)
                        w_rad = random.uniform(1.15, 1.75)
                        for ry in range(y + 1, y + h - 1):
                            for rx in range(x + 1, x + w - 1):
                                d_p = math.hypot(rx + 0.5 - px_c, ry + 0.5 - py_c)
                                if d_p <= w_rad:
                                    self.grid[ry][rx] = 2
                                elif d_p <= w_rad + 1.05 and floor_num == 3:
                                    self.grid[ry][rx] = 3
                        self.atmo_zones.append({"rect": new_rect, "kind": "spores"})
                    elif feat_roll < 0.68:
                        corner_x = x if random.random() < 0.5 else (x + w - 1)
                        corner_y = y if random.random() < 0.5 else (y + h - 1)
                        m_rad = random.uniform(1.8, 2.8)
                        for ry in range(y, y + h):
                            for rx in range(x, x + w):
                                if self.grid[ry][rx] in (0, 8):
                                    if math.hypot(rx - corner_x, ry - corner_y) <= m_rad:
                                        self.grid[ry][rx] = 3
                        self.atmo_zones.append({"rect": new_rect, "kind": "spores"})

                if self.rooms:
                    px, py = self.rooms[-1].center
                    cx, cy = new_rect.center
                    cor_tile = 4 if floor_num == 2 else (0 if floor_num == 3 else 8)
                    if bend_first_horiz:
                        for hx in range(min(px, cx), max(px, cx) + 1):
                            if self.grid[py][hx] in (1, 5, 6, 7):
                                self.grid[py][hx] = cor_tile
                        for vy in range(min(py, cy), max(py, cy) + 1):
                            if self.grid[vy][cx] in (1, 5, 6, 7):
                                self.grid[vy][cx] = cor_tile
                    else:
                        for vy in range(min(py, cy), max(py, cy) + 1):
                            if self.grid[vy][px] in (1, 5, 6, 7):
                                self.grid[vy][px] = cor_tile
                        for hx in range(min(px, cx), max(px, cx) + 1):
                            if self.grid[cy][hx] in (1, 5, 6, 7):
                                self.grid[cy][hx] = cor_tile

                self.rooms.append(new_rect)

        # Вырезаем Зал Босса и предбоссовый Зал Головоломки в выбранной стороне света!
        if zone_info is not None:
            info = zone_info
            sealed_rect = info["sealed_rect"]
            p_rect = info["puzzle_rect"]
            bx, by, bw, bh = sealed_rect.x, sealed_rect.y, sealed_rect.w, sealed_rect.h

            zone_floor = 4 if floor_num == 2 else (0 if floor_num == 3 else 8)
            for ry in range(by, by + bh):
                for rx in range(bx, bx + bw):
                    dist_c = math.hypot(rx - sealed_rect.centerx, ry - sealed_rect.centery)
                    if (rx in (bx, bx + bw - 1) and ry in (by, by + bh - 1)):
                        continue
                    self.grid[ry][rx] = (0 if dist_c <= 4.2 else 8) if tutorial else zone_floor

            for ry in range(p_rect.top, p_rect.bottom):
                for rx in range(p_rect.left, p_rect.right):
                    self.grid[ry][rx] = zone_floor

            ox, oy = info["outer_entry"]
            # Route outside the reserved complex; an L-shaped fallback could
            # cut a second entrance straight through the sealed room.
            self.grid[oy][ox] = zone_floor
            blocked = sealed_rect.union(p_rect).inflate(2, 2)
            start = (ox, oy)
            q = deque([start])
            parents = {start: None}
            destination = None
            room_tiles = {(x, y) for r in self.rooms
                          for y in range(r.top, r.bottom)
                          for x in range(r.left, r.right)
                          if self.grid[y][x] not in (1, 5, 6, 7)}
            while q:
                x, y = q.popleft()
                if (x, y) in room_tiles:
                    destination = (x, y)
                    break
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    pt = x + dx, y + dy
                    if (1 <= pt[0] < MAP_COLS - 1 and 1 <= pt[1] < MAP_ROWS - 1
                            and not blocked.collidepoint(pt) and pt not in parents):
                        parents[pt] = (x, y)
                        q.append(pt)
            if destination is None:
                raise RuntimeError("Could not connect the puzzle entrance")
            while destination is not None:
                x, y = destination
                self.grid[y][x] = zone_floor
                destination = parents[destination]

            ed_x, ed_y = info["entry_door"]
            bd_x, bd_y = info["gate_door"]
            self.grid[ed_y][ed_x] = zone_floor
            self.grid[bd_y][bd_x] = zone_floor
            self.doors[(ed_x, ed_y)] = Door(ed_x, ed_y, locked_by_lever=False)
            self.doors[(bd_x, bd_y)] = Door(bd_x, bd_y, locked_by_lever=True)

            self.rooms.append(sealed_rect)
            self.boss_room = sealed_rect if tutorial else None
            self.atmo_zones.append({"rect": sealed_rect, "kind": "ash"})

        self.start_pos = self.rooms[0].center if self.rooms else (6, 20)

        # Двери и рычаги (в пещерах на 4 ярусе обычных дверей между норами нет, только вход к боссу)
        if floor_num in (2, 3):
            locked_doors = []
            for r_idx, room in enumerate(self.rooms[1:], start=1):
                candidates = []
                for rx in range(room.left, room.right):
                    for ry in (room.top - 1, room.bottom):
                        if 1 <= ry < MAP_ROWS - 1 and self.grid[ry][rx] not in (1, 5, 6, 7):
                            if self.grid[ry][rx - 1] in (1, 6, 7) and self.grid[ry][rx + 1] in (1, 6, 7):
                                candidates.append((rx, ry))
                for ry in range(room.top, room.bottom):
                    for rx in (room.left - 1, room.right):
                        if 1 <= rx < MAP_COLS - 1 and self.grid[ry][rx] not in (1, 5, 6, 7):
                            if self.grid[ry - 1][rx] in (1, 6, 7) and self.grid[ry + 1][rx] in (1, 6, 7):
                                candidates.append((rx, ry))

                for dx, dy in candidates[:2]:
                    if not self._has_adjacent_door(dx, dy):
                        is_locked = (floor_num == 3 and r_idx % 5 == 0 and len(locked_doors) < 2)
                        d_obj = Door(dx, dy, locked_by_lever=is_locked)
                        self.doors[(dx, dy)] = d_obj
                        if is_locked:
                            locked_doors.append(d_obj)

            if locked_doors and len(self.rooms) >= 4:
                for i, ld in enumerate(locked_doors):
                    target_room = self.rooms[min(len(self.rooms) - 1, i + 1)]
                    # A normal lever must also be on the starting side of all
                    # locked doors, including the puzzle gate.
                    reachable = {self.start_pos}
                    q = deque([self.start_pos])
                    while q:
                        tx, ty = q.popleft()
                        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                            pt = nx, ny = tx + dx, ty + dy
                            door = self.doors.get(pt)
                            if (0 <= nx < MAP_COLS and 0 <= ny < MAP_ROWS and pt not in reachable
                                    and self.grid[ny][nx] not in (1, 5, 6, 7)
                                    and not (door and door.locked)):
                                reachable.add(pt)
                                q.append(pt)
                    candidates = sorted(reachable - self.doors.keys() - self.levers.keys() - {self.start_pos})
                    preferred = [pt for pt in candidates if target_room.collidepoint(pt)]
                    if preferred or candidates:
                        lx, ly = random.choice(preferred or candidates)
                        self.levers[(lx, ly)] = Lever(lx, ly, [ld])
                    else:
                        ld.locked = False

        from elenor.world.merchant import reserve_merchant_room
        reserve_merchant_room(self)

        # Расстановка света и жаровен по ярусам
        for idx, r in enumerate(self.rooms):
            if r is self.merchant_room:
                continue
            if r is self.boss_room:
                b_col = (1.30, 0.42, 0.38)
                self.room_lights.append({
                    "x": r.centerx, "y": r.centery,
                    "color": b_col,
                    "radius": 210.0
                })
                for bx_pos, by_pos in (
                    (r.left + 3, r.top + 3),
                    (r.right - 4, r.top + 3),
                    (r.left + 3, r.bottom - 4),
                    (r.right - 4, r.bottom - 4),
                ):
                    self.braziers.append({"x": bx_pos, "y": by_pos, "color": (1.25, 0.55, 0.25), "radius": 105.0})
            elif idx % 3 == 0:
                if floor_num == 2:
                    theme_col = (1.15, 0.78, 0.38)
                elif floor_num == 3:
                    theme_col = (0.65, 0.85, 1.05)
                else:
                    theme_col = (0.95, 0.48, 0.42)
                self.room_lights.append({
                    "x": r.centerx, "y": r.centery,
                    "color": theme_col,
                    "radius": max(r.width, r.height) * TILE_W * 0.95
                })
                self.braziers.append({"x": r.left + 1, "y": r.top + 1, "color": (1.15, 0.68, 0.28), "radius": 84.0})
            elif idx % 2 == 1:
                bx_p, by_p = r.left + 1, r.top + 1
                self.braziers.append({"x": bx_p, "y": by_p, "color": (1.1, 0.62, 0.25), "radius": 80.0})

        # Раскладываем полупрозрачные оверлеи только на камень и грунт (НИКОГДА на стены и деревянный пол!)
        for ry in range(1, MAP_ROWS - 1):
            for rx in range(1, MAP_COLS - 1):
                t_id = self.grid[ry][rx]
                if t_id in (1, 4, 5, 6, 7):
                    continue
                h_ov = (rx * 71 + ry * 113 + (rx * ry) * 19) % 100
                if t_id == 0:  # Каменная плита
                    if h_ov < 22:
                        self.overlays[(rx, ry)] = "ov_moss"
                    elif h_ov < 42:
                        self.overlays[(rx, ry)] = "ov_cracks"
                    elif h_ov < 52:
                        self.overlays[(rx, ry)] = "ov_pebbles"
                elif t_id == 8:  # Пещерный грунт
                    if h_ov < 30:
                        self.overlays[(rx, ry)] = "ov_pebbles"
                    elif h_ov < 46:
                        self.overlays[(rx, ry)] = "ov_cracks"
                    elif h_ov < 56:
                        self.overlays[(rx, ry)] = "ov_moss"

        self._place_cellar_mist()

    def _place_cellar_mist(self):
        # Atmosphere has its own stream. It must not shift a seeded layout or its loot.
        rng = random.Random(0)
        rng.setstate(random.getstate())
        if rng.random() >= .50:
            return
        candidates = [room for room in self.rooms[1:]
                      if room != self.merchant_room and min(room.size) >= 4]
        for room in rng.sample(candidates, min(len(candidates), rng.randint(1, 2))):
            center_x = room.left + room.width * .5
            center_y = room.top + room.height * .5
            color = (.60, .65, .75) if room != self.boss_room else (.72, .49, .48)
            self.fog_zones.append(dict(
                wx=center_x, wy=center_y, radius=math.hypot(*room.size) * .52,
                color=color, density=rng.uniform(.60, .78), kind="mist", bounds=tuple(room),
            ))

    def is_blocking_move(self, tx, ty):
        if not (0 <= tx < self.width and 0 <= ty < self.height):
            return True
        if self.grid[ty][tx] in (1, 5, 6, 7, 17, 18, 19, 20, 21, 22, 33, 34, 35, 36, DEEP_WATER, 51, 52, 53, 54, 55, 56, 57):
            return True
        if (tx, ty) in getattr(self, "solid_props", ()) or (tx, ty) in getattr(self, "invisible_bounds", ()):
            return True
        door = self.doors.get((tx, ty))
        if door and not door.is_open:
            return True
        return False

    def is_blocking_sight(self, tx, ty, *, include_thickets=True):
        if not (0 <= tx < self.width and 0 <= ty < self.height):
            return True
        # Isolated jungle trees admit light. Interlocking crowns occlude both light and vision.
        if (include_thickets and (tx, ty) in self.thickets) or self.grid[ty][tx] in OPAQUE_WALL_TILES:
            return True
        door = self.doors.get((tx, ty))
        if door and not door.is_open:
            return True
        return False

    def is_blocking_projectile(self, tx, ty):
        if not (0 <= tx < self.width and 0 <= ty < self.height):
            return True
        door = self.doors.get((tx, ty))
        return self.grid[ty][tx] in OPAQUE_WALL_TILES or bool(door and not door.is_open)

    def has_line_of_sight(self, x0, y0, x1, y1, max_dist, *, target_thicket=None):
        dx = x1 - x0
        dy = y1 - y0
        dist = math.hypot(dx, dy)
        if dist > max_dist:
            return False
        steps = int(dist * (8.0 if self.thickets else 3.0)) + 1
        previous = None
        start_tile = (math.floor(x0), math.floor(y0))
        thickets = self.thickets
        grid, doors = self.grid, self.doors
        width, height = self.width, self.height
        for i in range(1, steps + (target_thicket is not None)):
            t = i / steps
            x, y = x0 + dx * t, y0 + dy * t
            cx, cy = math.floor(x), math.floor(y)
            tile = cx, cy
            if tile != previous:
                # Walls and doors occupy their entire tile. Only roots need sub-tile checks.
                if not (0 <= cx < width and 0 <= cy < height) or grid[cy][cx] in OPAQUE_WALL_TILES:
                    return False
                door = doors.get(tile)
                if door and not door.is_open:
                    return False
                if target_thicket is not None:
                    px, py = previous if previous is not None else start_tile
                    if (px != cx and py != cy
                            and self.is_blocking_sight(cx, py) and self.is_blocking_sight(px, cy)):
                        return False
                inside_root = tile != target_thicket and tile in thickets
                previous = tile
            if inside_root:
                ox, oy = x - cx - 0.5, y - cy - 0.5
                if (ox * ox + oy * oy <= 0.22 ** 2
                        or abs(oy) <= 0.15 and (cx + (1 if ox > 0 else -1), cy) in self.thickets
                        or abs(ox) <= 0.15 and (cx, cy + (1 if oy > 0 else -1)) in self.thickets):
                    return False
        return True

    def find_path(self, start_tile, goal_tile, max_expanded=220):
        sx, sy = int(start_tile[0]), int(start_tile[1])
        gx, gy = int(goal_tile[0]), int(goal_tile[1])
        if (sx, sy) == (gx, gy):
            return []

        open_heap = []
        heapq.heappush(open_heap, (0.0, (sx, sy)))
        came_from = {}
        g_score = {(sx, sy): 0.0}
        expanded = 0

        neighbors = [
            (1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
            (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)
        ]

        best_node = None
        best_h = 999999.0

        while open_heap and expanded < max_expanded:
            _, current = heapq.heappop(open_heap)
            expanded += 1

            if current == (gx, gy):
                best_node = current
                break

            cx, cy = current
            for dx, dy, step_cost in neighbors:
                nx, ny = cx + dx, cy + dy
                if (nx, ny) != (gx, gy) and self.is_blocking_move(nx, ny):
                    continue

                if dx != 0 and dy != 0:
                    if self.is_blocking_move(cx + dx, cy) or self.is_blocking_move(cx, cy + dy):
                        continue

                tile_penalty = 1.35 if self.grid[ny][nx] == 2 else 1.0
                tentative_g = g_score[current] + step_cost * tile_penalty

                if tentative_g < g_score.get((nx, ny), 999999.0):
                    came_from[(nx, ny)] = current
                    g_score[(nx, ny)] = tentative_g
                    h = math.hypot(gx - nx, gy - ny)
                    if h < best_h:
                        best_h = h
                        best_node = (nx, ny)
                    heapq.heappush(open_heap, (tentative_g + h * 1.1, (nx, ny)))

        if best_node is None:
            return []
        path = []
        curr = best_node
        while curr in came_from:
            path.append((curr[0] + 0.5, curr[1] + 0.5))
            curr = came_from[curr]
        path.reverse()
        return path

    def get_light_open_tiles(self, tile_x, tile_y, radius_px):
        itx, ity = int(tile_x), int(tile_y)
        key = (itx, ity, int(radius_px))
        if key in self._light_cache:
            return self._light_cache[key]

        open_tiles = set()
        r_tiles = int(math.ceil(radius_px / TILE_W)) + 1
        ox, oy = itx + 0.5, ity + 0.5

        for ty in range(max(0, ity - r_tiles), min(self.height, ity + r_tiles + 1)):
            for tx in range(max(0, itx - r_tiles), min(self.width, itx + r_tiles + 1)):
                if not self.is_blocking_sight(tx, ty):
                    dist = math.hypot((tx + 0.5) - ox, (ty + 0.5) - oy)
                    if dist <= r_tiles:
                        # Проверяем видимость центра или уголков клетки, чтобы одиночная колонна 1x1 не гасила пол квадратами!
                        if (
                            self.has_line_of_sight(ox, oy, tx + 0.5, ty + 0.5, r_tiles + 0.5)
                            or self.has_line_of_sight(ox, oy, tx + 0.18, ty + 0.18, r_tiles + 0.5)
                            or self.has_line_of_sight(ox, oy, tx + 0.82, ty + 0.82, r_tiles + 0.5)
                        ):
                            open_tiles.add((tx, ty))

        self._light_cache[key] = open_tiles
        return open_tiles

    def build_shared_light_Allowed_tiles(self, player_open_tiles, light_open_tiles):
        shared_open = player_open_tiles & light_open_tiles
        if not shared_open:
            return None

        vx, vy = self._last_viewer_pos
        allowed_grid = np.zeros((self.width, self.height), dtype=np.float32)

        for (ox, oy) in shared_open:
            allowed_grid[ox, oy] = 1.0
            # Стена подсвечивается только с той грани (ox, oy), которую реально видит игрок!
            # Это убирает паразитный просвет стен из соседнего зала через дверной проём.
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                wx, wy = ox + dx, oy + dy
                if 0 <= wx < self.width and 0 <= wy < self.height and self.is_blocking_sight(wx, wy):
                    face_nx, face_ny = ox - wx, oy - wy
                    if (vx - (wx + 0.5)) * face_nx + (vy - (wy + 0.5)) * face_ny > -0.15:
                        allowed_grid[wx, wy] = 1.0
        return allowed_grid

    def sight_geometry(self, closed_doors):
        """Tile obstacles and sub-tile root geometry shared by visibility passes."""
        if self._base_block_grid is None:
            base_bg = np.zeros((self.width, self.height), dtype=bool)
            for ry in range(self.height):
                row = self.grid[ry]
                for rx in range(self.width):
                    if row[rx] in OPAQUE_WALL_TILES:
                        base_bg[rx, ry] = True
            roots = np.zeros((self.width, self.height), dtype=np.uint8)
            for x, y in self.thickets:
                roots[x, y] = 1 + sum(
                    bit for bit, dx, dy in ((2, 1, 0), (4, -1, 0), (8, 0, 1), (16, 0, -1))
                    if (x + dx, y + dy) in self.thickets
                )
            self._fov_roots = roots
            self._base_block_grid = base_bg

        if closed_doors != self._sight_doors:
            walls = self._base_block_grid.copy()
            for dx, dy in closed_doors:
                walls[dx, dy] = True
            self._closed_sight_grid = walls
            self._sight_doors = closed_doors
        return self._closed_sight_grid, self._fov_roots

    def _trace_floor_rays(self, world_x, world_y, walls, root_grid, x0, y0):
        """Trace the existing samples in bands, retiring rays at their first hit."""
        width, height = walls.shape
        step_count = self._ray_steps.size
        has_roots = bool(root_grid.any())
        packed_flags = (root_grid | (walls.astype(np.uint8) << 5)).ravel() if has_roots else None
        wall_flags = walls.ravel()
        band_size = 48 if has_roots else step_count
        active = self._ray_indices
        endpoints = np.empty(len(active), np.intp)
        open_grid = np.zeros_like(walls)
        open_flags = open_grid.ravel()
        hit_grid = np.zeros_like(walls)
        last_x = last_y = None
        for begin in range(0, step_count, band_size):
            end = min(begin + band_size, step_count)
            count = end - begin
            if begin == 0:
                wx = world_x + self._ray_dx[:, :end]
                wy = world_y + self._ray_dy[:, :end]
            else:
                wx = world_x + self._ray_dx[active, begin:end]
                wy = world_y + self._ray_dy[active, begin:end]
            # Convert to world tiles before clamping to the local footprint.
            tx = (wx.astype(np.int32) // TILE_W - x0).clip(0, width - 1)
            ty = (wy.astype(np.int32) // TILE_H - y0).clip(0, height - 1)
            tile_indices = tx * height + ty
            flags = packed_flags[tile_indices] if packed_flags is not None else None
            blocked = (flags & 32) != 0 if flags is not None else wall_flags[tile_indices]
            if last_x is not None:
                x, y = tx[:, 0], ty[:, 0]
                blocked[:, 0] |= (x != last_x) & (y != last_y) & walls[x, last_y] & walls[last_x, y]

            # A diagonal step between two closed side tiles cannot transmit sight.
            changed_x = tx[:, 1:] != tx[:, :-1]
            changed_y = ty[:, 1:] != ty[:, :-1]
            ray, step = np.nonzero(changed_x & changed_y)
            blocked[ray, step + 1] |= walls[tx[ray, step + 1], ty[ray, step]] & walls[tx[ray, step], ty[ray, step + 1]]

            if flags is not None:
                root_ray, root_step = np.nonzero((flags != 0) & ~blocked)
                roots = flags[root_ray, root_step]
                ox = wx[root_ray, root_step] / TILE_W - (tx[root_ray, root_step] + x0) - .5
                oy = wy[root_ray, root_step] / TILE_H - (ty[root_ray, root_step] + y0) - .5
                trunks = ox * ox + oy * oy <= .22 ** 2
                branch_x = (np.abs(oy) <= .15) & ((np.where(ox > 0, 2, 4) & roots) != 0)
                branch_y = (np.abs(ox) <= .15) & ((np.where(oy > 0, 8, 16) & roots) != 0)
                blocked[root_ray, root_step] = trunks | branch_x | branch_y

            # argmax also returns zero for a ray with no hits.
            first_hit = blocked.argmax(axis=1)
            hit = (first_hit != 0) | blocked[:, 0]
            final_band = end == step_count
            # An unobstructed ray ends at the same last sample as the original fan.
            limit = np.where(hit, first_hit, count - int(final_band))
            open_samples = self._ray_steps[:, :count] < limit[:, None]
            # Only the first unobstructed sample in a tile can add it to the set.
            open_samples[:, 1:] &= changed_x | changed_y
            open_flags[tile_indices[open_samples]] = True
            hit_rows = np.flatnonzero(hit)
            hit_grid[tx[hit_rows, limit[hit_rows]], ty[hit_rows, limit[hit_rows]]] = True
            done = hit | final_band
            endpoints[active[done]] = begin + limit[done]
            remaining = ~done
            active = active[remaining]
            if not active.size:
                break
            last_x, last_y = tx[remaining, -1], ty[remaining, -1]
        return endpoints, open_grid, hit_grid

    def _world_floor_visibility(self, world_x, world_y, closed_doors):
        terrain, root_grid = self.sight_geometry(closed_doors)
        width, height = terrain.shape
        start_x = max(0, min(width - 1, int(world_x) // TILE_W))
        start_y = max(0, min(height - 1, int(world_y) // TILE_H))
        # Only tiles within the fan and the extra ring of adjacent wall faces
        # can contribute to this frame's visibility.
        radius_x = math.ceil(LOS_MAX_RADIUS / TILE_W) + 1
        radius_y = math.ceil(LOS_MAX_RADIUS / TILE_H) + 1
        x0, x1 = max(0, start_x - radius_x), min(width, start_x + radius_x + 1)
        y0, y1 = max(0, start_y - radius_y), min(height, start_y + radius_y + 1)
        walls = terrain[x0:x1, y0:y1].copy()
        roots = root_grid[x0:x1, y0:y1]
        width, height = walls.shape
        walls[start_x - x0, start_y - y0] = False

        endpoints, open_grid, hit_grid = self._trace_floor_rays(world_x, world_y, walls, roots, x0, y0)
        open_grid[start_x - x0, start_y - y0] = True
        nearby = np.zeros_like(open_grid)
        padded = np.pad(open_grid, 1)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)):
            nearby |= padded[1 + dx:1 + dx + width, 1 + dy:1 + dy + height]
        visible_grid = open_grid | (nearby & walls) | hit_grid
        open_x, open_y = np.nonzero(open_grid)
        visible_x, visible_y = np.nonzero(visible_grid)
        wall_x, wall_y = np.nonzero(visible_grid & walls)
        end_x = world_x + self._ray_dx[self._ray_indices, endpoints]
        end_y = world_y + self._ray_dy[self._ray_indices, endpoints]
        return (
            end_x, end_y, tuple(zip((wall_x + x0).tolist(), (wall_y + y0).tolist())),
            frozenset(zip((visible_x + x0).tolist(), (visible_y + y0).tolist())),
            frozenset(zip((open_x + x0).tolist(), (open_y + y0).tolist())),
        )

    def compute_nox_fov(self, world_ox, world_oy, cam_x, cam_y):
        self._last_viewer_pos = (world_ox / TILE_W, world_oy / TILE_H)
        cam_x, cam_y = round(cam_x), round(cam_y)
        closed_doors = tuple(point for point, door in self.doors.items() if not door.is_open)
        world_key = world_ox, world_oy, closed_doors
        key = world_key, cam_x, cam_y
        if self._fov_key == key:
            return self._fov_result
        # Camera shake only changes the screen projection of the same rays.
        if self._world_fov_key != world_key:
            self._world_fov = self._world_floor_visibility(world_ox, world_oy, closed_doors)
            self._world_fov_key = world_key

        end_x, end_y, walls, visible_tiles, open_tiles = self._world_fov
        points = list(zip((end_x - cam_x).astype(int).tolist(), (end_y - cam_y).astype(int).tolist()))
        surface = self._fov_surf
        surface.fill(0)
        if len(points) >= 3:
            pygame.draw.polygon(surface, 1, points)
        for x, y in walls:
            pygame.draw.rect(surface, 1, (x * TILE_W - cam_x, y * TILE_H - cam_y, TILE_W, TILE_H))
        np.copyto(self._fov_full_mask[:, :VIEW_H], pygame.surfarray.pixels2d(surface))

        mask = self._fov_full_mask.view()
        mask.flags.writeable = False
        self._fov_key = key
        self._fov_result = mask, visible_tiles, open_tiles
        return self._fov_result
    
    def compute_coarse_visibility(self, world_ox, world_oy):
        self._last_viewer_pos = (world_ox / TILE_W, world_oy / TILE_H)
        qx = round(world_ox * 0.25) * 4.0
        qy = round(world_oy * 0.25) * 4.0
        closed_doors = tuple(point for point, door in self.doors.items() if not door.is_open)
        key = (qx, qy, closed_doors)
        if self._coarse_fov_key == key:
            return self._coarse_fov_result

        terrain, root_grid = self.sight_geometry(closed_doors)
        width, height = terrain.shape
        start_x = max(0, min(width - 1, int(qx) // TILE_W))
        start_y = max(0, min(height - 1, int(qy) // TILE_H))
        radius_x = math.ceil(LOS_MAX_RADIUS / TILE_W) + 1
        radius_y = math.ceil(LOS_MAX_RADIUS / TILE_H) + 1
        x0, x1 = max(0, start_x - radius_x), min(width, start_x + radius_x + 1)
        y0, y1 = max(0, start_y - radius_y), min(height, start_y + radius_y + 1)
        walls = terrain[x0:x1, y0:y1].copy()
        roots = root_grid[x0:x1, y0:y1]
        lw, lh = walls.shape
        walls[start_x - x0, start_y - y0] = False

        wx = qx + self._coarse_dx
        wy = qy + self._coarse_dy
        tx = (wx.astype(np.int32) // TILE_W - x0).clip(0, lw - 1)
        ty = (wy.astype(np.int32) // TILE_H - y0).clip(0, lh - 1)
        blocked = walls[tx, ty]
        changed_x = tx[:, 1:] != tx[:, :-1]
        changed_y = ty[:, 1:] != ty[:, :-1]
        ray, step = np.nonzero(changed_x & changed_y)
        blocked[ray, step + 1] |= walls[tx[ray, step + 1], ty[ray, step]] & walls[tx[ray, step], ty[ray, step + 1]]

        if roots.any():
            r_vals = roots[tx, ty]
            rr, rs = np.nonzero((r_vals != 0) & ~blocked)
            if rr.size:
                rf = r_vals[rr, rs]
                ox = wx[rr, rs] / TILE_W - (tx[rr, rs] + x0) - .5
                oy = wy[rr, rs] / TILE_H - (ty[rr, rs] + y0) - .5
                trunks = ox * ox + oy * oy <= .22 ** 2
                bx = (np.abs(oy) <= .15) & ((np.where(ox > 0, 2, 4) & rf) != 0)
                by = (np.abs(ox) <= .15) & ((np.where(oy > 0, 8, 16) & rf) != 0)
                blocked[rr, rs] = trunks | bx | by

        first_hit = blocked.argmax(axis=1)
        hit = (first_hit != 0) | blocked[:, 0]
        count = self._coarse_steps.size
        limit = np.where(hit, first_hit, count)
        open_samples = self._coarse_steps < limit[:, None]
        open_samples[:, 1:] &= changed_x | changed_y

        open_grid = np.zeros_like(walls)
        open_grid[tx[open_samples], ty[open_samples]] = True
        open_grid[start_x - x0, start_y - y0] = True

        padded_open = np.pad(open_grid, 1)
        dilated = open_grid.copy()
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            dilated |= padded_open[1 + dx:1 + dx + lw, 1 + dy:1 + dy + lh]
        open_expanded = dilated & ~walls

        padded_vis = np.pad(open_expanded, 1)
        nearby_walls = np.zeros_like(walls)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)):
            nearby_walls |= padded_vis[1 + dx:1 + dx + lw, 1 + dy:1 + dy + lh]

        hit_grid = np.zeros_like(walls)
        hit_rows = np.flatnonzero(hit)
        hit_grid[tx[hit_rows, first_hit[hit_rows]], ty[hit_rows, first_hit[hit_rows]]] = True

        visible_grid = open_expanded | (nearby_walls & walls) | hit_grid
        open_x, open_y = np.nonzero(open_expanded)
        vis_x, vis_y = np.nonzero(visible_grid)
        result = (
            frozenset(zip((vis_x + x0).tolist(), (vis_y + y0).tolist())),
            frozenset(zip((open_x + x0).tolist(), (open_y + y0).tolist())),
        )
        self._coarse_fov_key = key
        self._coarse_fov_result = result
        return result
