from elenor.config import MERCHANT_ROOM_CHANCE
from collections import deque
import heapq
import math
import random
import pygame
import numpy as np
from elenor.config import MAP_COLS, MAP_ROWS, TILE_W, TILE_H, VIEW_W, VIEW_H, CANVAS_H, RAY_COUNT, LOS_MAX_RADIUS


class Door:
    def __init__(self, x, y, locked_by_lever=False):
        self.x = x
        self.y = y
        self.is_open = False
        self.locked = locked_by_lever


class Lever:
    def __init__(self, x, y, target_doors):
        self.x = x
        self.y = y
        self.pulled = False
        self.target_doors = target_doors


class Dungeon:
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
        self._ray_cos = np.cos(angles)[:, None]
        self._ray_sin = np.sin(angles)[:, None]
        self._ray_r = np.arange(2.0, LOS_MAX_RADIUS, 2.0, dtype=np.float32)[None, :]
        self._fov_surf = pygame.Surface((VIEW_W, VIEW_H))
        self._fov_full_mask = np.ones((VIEW_W, CANVAS_H), dtype=np.float32)
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

    def _carve_rect(self, rect, floor_id):
        for ry in range(rect.top, rect.bottom):
            for rx in range(rect.left, rect.right):
                if 1 <= rx < MAP_COLS - 1 and 1 <= ry < MAP_ROWS - 1:
                    self.grid[ry][rx] = floor_id

    def generate(self, floor_num=1, *, campaign="rats"):
        self.floor_num = floor_num
        self.ambient_light = (0.0, 0.0, 0.0)
        self.sunlight = None
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
        self.invalidate_light_cache()

        # =====================================================================
        # ЯРУС 1: ИНТРО — ДВОР У КОСТРА И ДОМ-ТАВЕРНА СО ВСЕМ ИНТЕРЬЕРОМ
        # =====================================================================
        self.invisible_bounds = set()
        if campaign == "jungle":
            from elenor.missions.jungle import generate_jungle_bank
            generate_jungle_bank(self)
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
                        self.fog_zones.append({"wx": px_c, "wy": py_c, "radius": w_rad + 1.4, "color": (0.48, 0.72, 0.85), "density": 0.48, "kind": "mist"})
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
            self.fog_zones.append({"wx": float(sealed_rect.centerx), "wy": float(sealed_rect.centery), "radius": 4.2, "color": (0.85, 0.28, 0.32), "density": 0.40, "kind": "mist"})

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

    def is_blocking_move(self, tx, ty):
        if not (0 <= tx < MAP_COLS and 0 <= ty < MAP_ROWS):
            return True
        if self.grid[ty][tx] in (1, 5, 6, 7, 17, 18, 19, 20, 21, 22, 33, 34, 35, 36, 51, 52, 53, 54, 55, 56, 57):
            return True
        if (tx, ty) in getattr(self, "solid_props", ()) or (tx, ty) in getattr(self, "invisible_bounds", ()):
            return True
        door = self.doors.get((tx, ty))
        if door and not door.is_open:
            return True
        return False

    def is_blocking_sight(self, tx, ty):
        if not (0 <= tx < MAP_COLS and 0 <= ty < MAP_ROWS):
            return True
        # Деревья (5, 21, 22, 56, 57) блокируют движение, но НЕ являются квадратными стенами для света!
        if self.grid[ty][tx] in (1, 6, 7, 17, 18, 19, 20, 33, 34, 35, 36, 51, 52, 53, 54, 55):
            return True
        door = self.doors.get((tx, ty))
        if door and not door.is_open:
            return True
        return False

    def has_line_of_sight(self, x0, y0, x1, y1, max_dist):
        dx = x1 - x0
        dy = y1 - y0
        dist = math.hypot(dx, dy)
        if dist > max_dist:
            return False
        steps = int(dist * 3.0) + 1
        for i in range(1, steps):
            t = i / steps
            cx = int(x0 + dx * t)
            cy = int(y0 + dy * t)
            if self.is_blocking_sight(cx, cy):
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

        for ty in range(max(0, ity - r_tiles), min(MAP_ROWS, ity + r_tiles + 1)):
            for tx in range(max(0, itx - r_tiles), min(MAP_COLS, itx + r_tiles + 1)):
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
        allowed_grid = np.zeros((MAP_COLS, MAP_ROWS), dtype=np.float32)

        for (ox, oy) in shared_open:
            allowed_grid[ox, oy] = 1.0
            # Стена подсвечивается только с той грани (ox, oy), которую реально видит игрок!
            # Это убирает паразитный просвет стен из соседнего зала через дверной проём.
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                wx, wy = ox + dx, oy + dy
                if 0 <= wx < MAP_COLS and 0 <= wy < MAP_ROWS and self.is_blocking_sight(wx, wy):
                    face_nx, face_ny = ox - wx, oy - wy
                    if (vx - (wx + 0.5)) * face_nx + (vy - (wy + 0.5)) * face_ny > -0.15:
                        allowed_grid[wx, wy] = 1.0
        return allowed_grid

    def compute_nox_fov(self, world_ox, world_oy, cam_x, cam_y, *, daylight_sight=None):
        self._last_viewer_pos = (world_ox / TILE_W, world_oy / TILE_H)
        cam_ix, cam_iy = int(round(cam_x)), int(round(cam_y))

        fov_surf = self._fov_surf
        fov_surf.fill((0, 0, 0))

        start_tx = max(0, min(MAP_COLS - 1, int(world_ox) // TILE_W))
        start_ty = max(0, min(MAP_ROWS - 1, int(world_oy) // TILE_H))

        if self._base_block_grid is None:
            base_bg = np.zeros((MAP_COLS, MAP_ROWS), dtype=bool)
            for ry in range(MAP_ROWS):
                row = self.grid[ry]
                for rx in range(MAP_COLS):
                    if row[rx] in (1, 6, 7, 17, 18, 19, 20, 33, 34, 35, 36, 51, 52, 53, 54, 55):
                        base_bg[rx, ry] = True
            self._base_block_grid = base_bg

        block_grid = self._base_block_grid.copy()
        for (dx, dy), door in self.doors.items():
            if not door.is_open:
                block_grid[dx, dy] = True
        block_grid[start_tx, start_ty] = False

        # Векторный расчёт всех 280 лучей одновременно через NumPy!
        wx = world_ox + self._ray_cos * self._ray_r
        wy = world_oy + self._ray_sin * self._ray_r
        tx = np.clip((wx // TILE_W).astype(np.int32), 0, MAP_COLS - 1)
        ty = np.clip((wy // TILE_H).astype(np.int32), 0, MAP_ROWS - 1)

        blocked = block_grid[tx, ty]
        # Защита от прострела диагональных стыков стен
        diag_step = (tx[:, 1:] != tx[:, :-1]) & (ty[:, 1:] != ty[:, :-1])
        diag_pinch = diag_step & block_grid[tx[:, 1:], ty[:, :-1]] & block_grid[tx[:, :-1], ty[:, 1:]]
        blocked[:, 1:] |= diag_pinch

        has_hit = blocked.any(axis=1)
        hit_idx = np.where(has_hit, np.argmax(blocked, axis=1), self._ray_r.shape[1] - 1)

        ray_indices = np.arange(RAY_COUNT)
        end_wx = wx[ray_indices, hit_idx]
        end_wy = wy[ray_indices, hit_idx]
        poly_points = list(zip((end_wx - cam_ix).astype(int).tolist(), (end_wy - cam_iy).astype(int).tolist()))

        step_indices = np.arange(self._ray_r.shape[1])[None, :]
        open_mask = step_indices < hit_idx[:, None]
        open_tx = tx[open_mask]
        open_ty = ty[open_mask]

        open_visible_tiles = set(zip(open_tx.tolist(), open_ty.tolist()))
        open_visible_tiles.add((start_tx, start_ty))
        visible_tiles = set(open_visible_tiles)

        hit_tx = tx[ray_indices[has_hit], hit_idx[has_hit]]
        hit_ty = ty[ray_indices[has_hit], hit_idx[has_hit]]
        visible_tiles.update(zip(hit_tx.tolist(), hit_ty.tolist()))

        if len(poly_points) >= 3:
            pygame.draw.polygon(fov_surf, (255, 255, 255), poly_points)

        for (ox, oy) in open_visible_tiles:
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)):
                nx, ny = ox + dx, oy + dy
                if 0 <= nx < MAP_COLS and 0 <= ny < MAP_ROWS and block_grid[nx, ny]:
                    visible_tiles.add((nx, ny))

        for (vtx, vty) in visible_tiles:
            if block_grid[vtx, vty]:
                pygame.draw.rect(
                    fov_surf,
                    (255, 255, 255),
                    (vtx * TILE_W - cam_ix, vty * TILE_H - cam_iy, TILE_W, TILE_H)
                )

        fov_red_view = pygame.surfarray.pixels3d(fov_surf)[:, :, 0]
        np.multiply(fov_red_view, 1.0 / 255.0, out=self._fov_full_mask[:, :VIEW_H], casting="unsafe")
        del fov_red_view

        if daylight_sight is not None:
            px = np.arange(VIEW_W, dtype=np.float32)[:, None] + cam_ix - world_ox
            py = np.arange(VIEW_H, dtype=np.float32)[None, :] + cam_iy - world_oy
            fade = np.clip((daylight_sight - np.hypot(px, py)) / 90, 0, 1)
            self._fov_full_mask[:, :VIEW_H] *= fade * fade * (3 - 2 * fade)

            def in_range(tile):
                x, y = tile
                return math.hypot((x + .5) * TILE_W - world_ox,
                                  (y + .5) * TILE_H - world_oy) < daylight_sight

            visible_tiles = {tile for tile in visible_tiles if in_range(tile)}
            open_visible_tiles = {tile for tile in open_visible_tiles if tile in visible_tiles}

        return self._fov_full_mask, visible_tiles, open_visible_tiles