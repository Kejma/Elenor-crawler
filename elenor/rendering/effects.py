import math
import random
import pygame
import numpy as np
from elenor.config import OPAQUE_WALL_TILES, MAP_COLS, MAP_ROWS, TILE_W, TILE_H, VIEW_W, VIEW_H, SCREEN_W, SCREEN_H, UI_PANEL_BG, UI_SLOT_BG, UI_BORDER_GOLD, UI_BORDER_WOOD, UI_BORDER_HIGHLIGHT, UI_TEXT_MAIN, UI_TEXT_DIM


class FXManager:
    """Управляет всеми графическими эффектами, объёмным туманом, вечными декалями и панелями [F2] / [F3]."""
    def __init__(self, game):
        self.game = game
        self.panel_open = False
        self.f3_open = False
        self.f3_btn_rects = {}

        # Тумблеры графических улучшений
        self.flags = {
            "tonemap": True,
            "reflected_light": True,
            "ao": True,             # 1. Fake Ambient Occlusion (угловые тени у стен и объектов в шейдере)
            "bloom": True,          # 2. Shader Bloom / Emissive (свечение огня, магии и глаз в темноте)
            "gpu_fog": True,
            "volumetric_fog": True, # 3. 2.5D Объёмный туман и Ядовитые облака
            "drop_shadows": True,   # 4. Мягкие падающие тени под ногами существ
            "battle_memory": True,  # 5. Память поля боя (вечная кровь, обломки бочек, вино, копоть)
            "dust_motes": True,     # 6. Пылинки и споры (только в тематических зонах и на улице!)
            "water_ripples": True,  # 7. Круги по воде строго под подошвами сапог
            "hit_flash": True,      # 8. Hit-Flash (красный при обычном ударе, бело-золотой при крите)
            "screenshake": True,    # 9. Мягкая микро-тряска камеры при критах и взрывах
        }

        self.decal_surf = pygame.Surface((MAP_COLS * TILE_W, MAP_ROWS * TILE_H), pygame.SRCALPHA)
        self.wall_grid_np = np.zeros((MAP_COLS, MAP_ROWS), dtype=np.float32)

        self.ripples = []
        self.dust_motes = []
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

    def _spawn_jungle_motes(self, dungeon):
        rng = self.mote_rng
        outdoors = not dungeon.interior
        for y, row in enumerate(dungeon.grid):
            for x, tile in enumerate(row):
                if rng.random() >= 0.24 or dungeon.is_blocking_move(x, y):
                    continue
                # Fireflies favor vegetated openings and banks. Interiors get drifting dust.
                kind = ("firefly" if outdoors and tile in (10, 11, 23, 37, 40, 45, 46)
                        and rng.random() < .35 else "dust")
                anchor = (x + rng.uniform(.30, .70), y + rng.uniform(.30, .70))
                self.dust_motes.append({
                    "wx": anchor[0], "wy": anchor[1], "anchor": anchor, "kind": kind,
                    "phase": rng.uniform(0, math.tau), "size": 1,
                    "rate": rng.uniform(.5, 1.5),
                })

    def clear_floor_decals(self):
        self.decal_surf.fill((0, 0, 0, 0))
        self.ripples.clear()

    def rebuild_wall_grid(self, dungeon):
        """Строит карту стен для Ambient Occlusion (БЕЗ деревьев 5!) и заселяет зоны тумана и спор."""
        size = (dungeon.width, dungeon.height)
        if self.wall_grid_np.shape != size:
            self.wall_grid_np = np.zeros(size, dtype=np.float32)
            self.decal_surf = pygame.Surface((size[0]*TILE_W, size[1]*TILE_H), pygame.SRCALPHA)
        self.wall_grid_np.fill(0.0)
        for ry in range(dungeon.height):
            for rx in range(dungeon.width):
                # Деревья (5) не включены, чтобы вокруг них не было квадратных рамок AO!
                if dungeon.grid[ry][rx] in OPAQUE_WALL_TILES:
                    self.wall_grid_np[rx, ry] = 1.0

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
    def add_blood_splatter(self, wx, wy, count=5, is_kill=False):
        if not self.flags["battle_memory"]:
            return
        cx = int(wx * TILE_W)
        cy = int((wy + 0.25) * TILE_H)
        n_drops = count * 2 if is_kill else count
        spread = 7 if is_kill else 5
        for _ in range(n_drops):
            ox = cx + random.randint(-spread, spread)
            oy = cy + random.randint(-spread + 1, spread + 1)
            col = random.choice([
                (135, 16, 24, 215),
                (168, 22, 30, 225),
                (98, 12, 18, 200),
            ])
            sz = random.choice([1, 1, 2]) if not is_kill else random.choice([1, 2, 2, 3])
            pygame.draw.rect(self.decal_surf, col, (ox, oy, sz, sz))

    def add_barrel_debris(self, tx, ty):
        if not self.flags["battle_memory"]:
            return
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
        if not self.flags["battle_memory"]:
            return
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
        if not self.flags["water_ripples"]:
            return
        self.ripples.append({
            "wx": float(wx),
            "wy": float(wy) + 0.36,
            "green": green,
            "timer": 0.55,
            "max_timer": 0.55
        })

    def trigger_shake(self, amplitude=1.8, duration=0.14):
        if not self.flags["screenshake"]:
            return
        self.shake_amp = max(self.shake_amp, float(amplitude))
        self.shake_max_timer = max(0.01, float(duration))
        self.shake_timer = max(self.shake_timer, float(duration))

    def update(self, dt, player, dungeon, mobs=None, add_popup=None):
        if dt <= 0:
            return
        if self.shake_timer > 0.0 and self.flags["screenshake"]:
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
        if self.flags["dust_motes"] and self.dust_motes:
            for dm in self.dust_motes:
                if "anchor" in dm:
                    dm["phase"] += dt * dm["rate"]
                    x, y = dm["anchor"]
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
        d.invalidate_light_cache()

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

    def render_panel(self, screen, mouse_pos):
        r = self.game.renderer
        hint_txt = "[F2] FX-Лаб | [F3] Телеметрия билда"
        h_s = r.font_small.render(hint_txt, True, (255, 225, 95) if (self.panel_open or self.f3_open) else UI_TEXT_DIM)
        pygame.draw.rect(screen, (16, 14, 22), (SCREEN_W - h_s.get_width() - 20, 8, h_s.get_width() + 12, 22), border_radius=4)
        pygame.draw.rect(screen, UI_BORDER_WOOD, (SCREEN_W - h_s.get_width() - 20, 8, h_s.get_width() + 12, 22), 1, border_radius=4)
        screen.blit(h_s, (SCREEN_W - h_s.get_width() - 14, 11))

        if self.f3_open:
            self._render_f3_telemetry(screen, mouse_pos)

        if not self.panel_open:
            return

        pw, ph = 376, 664
        px, py = SCREEN_W - pw - 16, 36
        panel_rect = pygame.Rect(px, py, pw, ph)
        r.draw_pixel_frame(screen, panel_rect, UI_PANEL_BG, UI_BORDER_GOLD, False, 1.0)

        title = r.font_ui.render("🧪 ЭКСПЕРИМЕНТАЛЬНЫЕ FX [F2]", True, UI_BORDER_HIGHLIGHT)
        screen.blit(title, (px + (pw - title.get_width()) // 2, py + 12))

        items = [
            ("tonemap", "Тонмаппинг"),
            ("reflected_light", "Отражённый свет"),
            ("gpu_fog", "Расчёт тумана на GPU"),
            ("ao",             "1. Ambient Occlusion (Угловые тени)"),
            ("bloom",          "2. Shader Bloom (Свечение огня/магии)"),
            ("volumetric_fog", "3. 2.5D Объёмный туман / Ядовитый газ"),
            ("drop_shadows",   "4. Падающие тени существ (Drop Shadows)"),
            ("battle_memory",  "5. Память боя (Кровь / Обломки / Копоть)"),
            ("dust_motes",     "6. Пыль/Споры (Только лес и спец-залы)"),
            ("water_ripples",  "7. Круги по воде под сапогами"),
            ("hit_flash",      "8. Hit-Flash (Красный / Бело-золотой)"),
            ("screenshake",    "9. Мягкая микро-тряска камеры"),
        ]

        self.toggle_rects = {}
        cur_y = py + 40
        for key, label in items:
            row_r = pygame.Rect(px + 16, cur_y, pw - 32, 32)
            self.toggle_rects[key] = row_r
            hov = row_r.collidepoint(mouse_pos)
            on = self.flags[key]
            bg = (38, 52, 42) if on else (32, 24, 30)
            if hov:
                bg = (52, 70, 56) if on else (46, 34, 42)
            pygame.draw.rect(screen, bg, row_r, border_radius=4)
            pygame.draw.rect(screen, (95, 215, 120) if on else (90, 65, 65), row_r, 1, border_radius=4)

            mark = "[✓]" if on else "[ ]"
            m_col = (125, 250, 150) if on else (220, 110, 110)
            screen.blit(r.font_small.render(f"{mark} {label}", True, m_col if on else UI_TEXT_DIM), (row_r.x + 10, row_r.y + 8))
            cur_y += 36

        cur_y += 6
        pygame.draw.line(screen, UI_BORDER_WOOD, (px + 16, cur_y), (px + pw - 16, cur_y), 1)
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
            br = pygame.Rect(px + 16, cur_y, pw - 32, 33)
            self.action_rects[b_key] = br
            hov = br.collidepoint(mouse_pos)
            r.draw_pixel_frame(screen, br, (62, 105, 72) if (hov and b_key == "tp_lab") else b_col, UI_BORDER_GOLD if b_key == "tp_lab" else UI_BORDER_WOOD, hov, 1.0)
            ts = r.font_small.render(b_txt, True, (255, 240, 180) if b_key == "tp_lab" else UI_TEXT_MAIN)
            screen.blit(ts, (br.centerx - ts.get_width() // 2, br.centery - ts.get_height() // 2))
            cur_y += 37

        half_w = (pw - 38) // 2
        for idx, (b_key, b_txt, b_col) in enumerate(buttons[2:]):
            col_i = idx % 2
            row_i = idx // 2
            br = pygame.Rect(px + 16 + col_i * (half_w + 6), cur_y + row_i * 35, half_w, 31)
            self.action_rects[b_key] = br
            hov = br.collidepoint(mouse_pos)
            r.draw_pixel_frame(screen, br, (48, 40, 52) if hov else b_col, UI_BORDER_WOOD, hov, 1.0)
            ts = r.font_small.render(b_txt, True, UI_TEXT_MAIN)
            screen.blit(ts, (br.centerx - ts.get_width() // 2, br.centery - ts.get_height() // 2))

    def _render_f3_telemetry(self, screen, mouse_pos):
        """Отрисовывает панель [F3] с детальным раскладом Вектора Билда (Силач/Ловкач/Маг) и внутренних переменных."""
        from elenor.config import get_rarity_weights
        r = self.game.renderer
        g = self.game
        p = g.player

        pw, ph = 450, 520
        px, py = 16, 36
        panel_rect = pygame.Rect(px, py, pw, ph)
        r.draw_pixel_frame(screen, panel_rect, (18, 16, 26), UI_BORDER_GOLD, False, 1.0)

        hdr = r.font_ui.render("📊 [F3] ОТЛАДКА ВЕКТОРА БИЛДА И ПЕРЕМЕННЫХ", True, UI_BORDER_HIGHLIGHT)
        screen.blit(hdr, (px + (pw - hdr.get_width()) // 2, py + 12))

        # Считаем покомпонентный вклад в каждую ветку (Статы / Экипировка / Перки / Боевые действия)
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

        cur_y = py + 40
        for b_key, b_title, b_col in branches:
            tot = total_scores[b_key]
            share = tot / total_sum
            mult = 1.0 + 1.45 * share

            box_b = pygame.Rect(px + 14, cur_y, pw - 28, 66)
            pygame.draw.rect(screen, (26, 22, 34), box_b, border_radius=4)
            pygame.draw.rect(screen, b_col, box_b, 1, border_radius=4)

            top_line = f"{b_title}: {tot:.2f} очк. | Доля: {int(round(share * 100))}% -> Шанс перков: x{mult:.2f}"
            screen.blit(r.font_small.render(top_line, True, b_col), (box_b.x + 8, box_b.y + 6))

            sub_line = (
                f"Статы: {stat_part[b_key]:.1f}  |  Шмот: {equip_part[b_key]:.1f}  |  "
                f"Перки: {perk_part[b_key]:.1f}  |  Действия: {p.action_affinity[b_key]:.2f}"
            )
            screen.blit(r.font_small.render(sub_line, True, UI_TEXT_MAIN), (box_b.x + 8, box_b.y + 25))

            # Полоска доли ветки
            bar_w = box_b.width - 16
            pygame.draw.rect(screen, (14, 12, 18), (box_b.x + 8, box_b.y + 46, bar_w, 12))
            pygame.draw.rect(screen, b_col, (box_b.x + 9, box_b.y + 47, int((bar_w - 2) * share), 10))
            cur_y += 72

        # Кнопки живого тестирования притяжки перков
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
            br = pygame.Rect(px + 14 + ci * (bw + 6), cur_y + ri * 32, bw, 28)
            self.f3_btn_rects[bk] = br
            hov = br.collidepoint(mouse_pos)
            pygame.draw.rect(screen, (52, 44, 62) if hov else (34, 28, 44), br, border_radius=4)
            pygame.draw.rect(screen, UI_BORDER_GOLD if bk == "test_roll" else UI_BORDER_WOOD, br, 1, border_radius=4)
            ts = r.font_small.render(bt, True, (255, 230, 110) if bk == "test_roll" else UI_TEXT_MAIN)
            screen.blit(ts, (br.centerx - ts.get_width() // 2, br.centery - ts.get_height() // 2))
        cur_y += 70

        pygame.draw.line(screen, UI_BORDER_WOOD, (px + 14, cur_y), (px + pw - 14, cur_y), 1)
        cur_y += 8

        # Блок 2: Веса редкости (с учётом текущей Удачи) и внутренние переменные движка
        rw = get_rarity_weights(p.luck)
        rw_str = f"Веса редкости (Удача {p.luck}): Белые {rw[0]:.0f}% | Зел {rw[1]:.1f}% | Син {rw[2]:.1f}% | Эпик {rw[3]:.1f}% | Лег {rw[4]:.1f}%"
        screen.blit(r.font_small.render(rw_str, True, (255, 215, 110)), (px + 14, cur_y))
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
            screen.blit(r.font_small.render(v_ln, True, UI_TEXT_DIM), (px + 14, cur_y))
            cur_y += 19
