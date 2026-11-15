import math
import random
import pygame
import numpy as np
from config import (
    MAP_COLS, MAP_ROWS, TILE_W, TILE_H, VIEW_W, VIEW_H, SCALE,
    SCREEN_W, SCREEN_H, UI_PANEL_BG, UI_SLOT_BG, UI_BORDER_GOLD,
    UI_BORDER_WOOD, UI_BORDER_HIGHLIGHT, UI_TEXT_MAIN, UI_TEXT_DIM
)


class FXManager:
    """Управляет всеми графическими эффектами, объёмным туманом, вечными декалями и панелью FX-Лаборатории [F2]."""
    def __init__(self, game):
        self.game = game
        self.panel_open = False

        # 9 тумблеров графических улучшений
        self.flags = {
            "ao": True,             # 1. Fake Ambient Occlusion (угловые тени у стен и объектов в шейдере)
            "bloom": True,          # 2. Shader Bloom / Emissive (свечение огня, магии и глаз в темноте)
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
        self.active_clouds = []

        self.shake_timer = 0.0
        self.shake_max_timer = 0.0
        self.shake_amp = 0.0
        self.shake_offset = (0.0, 0.0)

        self.toggle_rects = {}
        self.action_rects = {}

    def _spawn_dust_in_zones(self, dungeon, count=55):
        self.dust_motes = []
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

    def clear_floor_decals(self):
        self.decal_surf.fill((0, 0, 0, 0))
        self.ripples.clear()

    def rebuild_wall_grid(self, dungeon):
        """Строит карту стен для Ambient Occlusion (БЕЗ деревьев 5!) и заселяет зоны тумана и спор."""
        self.wall_grid_np.fill(0.0)
        for ry in range(MAP_ROWS):
            for rx in range(MAP_COLS):
                # Деревья (5) не включены, чтобы вокруг них не было квадратных рамок AO!
                if dungeon.grid[ry][rx] in (1, 6, 7):
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
    def add_water_ripple(self, wx, wy):
        if not self.flags["water_ripples"]:
            return
        self.ripples.append({
            "wx": float(wx),
            "wy": float(wy) + 0.36,
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
                        if math.hypot(m.x - cld["wx"], m.y - cld["wy"]) <= cld["radius"]:
                            m.apply_status("poison", 2.5, add_popup, dmg_val=cld["dmg"])
                            m.hp -= cld["dmg"]
                            add_popup(m.x, m.y, f"-{cld['dmg']}", (110, 245, 95))
                            self.game._check_mob_death(m)

        # Пылинки и споры летают ТОЛЬКО внутри разрешённых тематических зон (`zone_rect`)!
        if self.flags["dust_motes"] and self.dust_motes:
            for dm in self.dust_motes:
                dm["phase"] += dt * 1.8
                dm["wx"] += (dm["vx"] + math.sin(dm["phase"]) * 0.12) * dt
                dm["wy"] += dm["vy"] * dt
                zr = dm["zone_rect"]
                if not (zr.left + 0.2 <= dm["wx"] <= zr.right - 0.2 and zr.top + 0.2 <= dm["wy"] <= zr.bottom - 0.2):
                    dm["wx"] = random.uniform(zr.left + 0.3, zr.right - 0.3)
                    dm["wy"] = random.uniform(zr.top + 0.3, zr.bottom - 0.3)

    # --- ГЕНЕРАТОР ТЕСТОВОЙ КОМНАТЫ (FX-ПОЛИГОН, ЭТАЖ 99) ---
    def enter_test_polygon(self, EnemyCls, InteractableCls):
        g = self.game
        d = g.dungeon
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
        lab_rect = pygame.Rect(18, 12, 24, 16)
        for ry in range(lab_rect.top, lab_rect.bottom):
            for rx in range(lab_rect.left, lab_rect.right):
                if rx < 25:
                    d.grid[ry][rx] = 4
                elif rx > 34:
                    d.grid[ry][rx] = 8
                else:
                    d.grid[ry][rx] = 0

        for ry in range(18, 23):
            for rx in range(27, 33):
                if 28 <= rx <= 31 and 19 <= ry <= 21:
                    d.grid[ry][rx] = 2
                else:
                    d.grid[ry][rx] = 3

        for px_c, py_c in ((23, 15), (23, 24), (36, 15), (36, 24)):
            d.grid[py_c][px_c] = 1

        d.rooms = [lab_rect]
        d.atmo_zones = [{"rect": lab_rect, "kind": "spores"}]
        d.fog_zones = [
            {"wx": 30.0, "wy": 20.5, "radius": 3.2, "color": (0.48, 0.75, 0.90), "density": 0.50, "kind": "mist"}
        ]
        d.start_pos = (25, 20)
        g.player.x, g.player.y = 25.5, 20.5
        g.player.hp = float(g.player.max_hp)
        g.player.mp = float(g.player.max_mp)

        d.braziers.append({"x": 22, "y": 14, "color": (1.25, 0.72, 0.28), "radius": 105.0})
        d.braziers.append({"x": 37, "y": 14, "color": (0.55, 0.95, 1.35), "radius": 105.0})
        d.room_lights.append({"x": 30, "y": 20, "color": (0.85, 0.75, 0.95), "radius": 135.0})

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
        g.objects.append(InteractableCls(39, 20, "npc_merchant"))
        for by_b in (16, 18, 22, 24):
            g.objects.append(InteractableCls(34, by_b, "barrel"))

        dummy_rat = EnemyCls(29, 15, kind="rat", state="sleeping")
        dummy_rat.max_hp = 9999
        dummy_rat.hp = 9999
        dummy_rat.speed = 0.0

        dummy_cult = EnemyCls(32, 15, kind="rat_cultist", state="sleeping")
        dummy_cult.max_hp = 9999
        dummy_cult.hp = 9999
        dummy_cult.speed = 0.0
        g.mobs.extend([dummy_rat, dummy_cult])

        solid_kinds = {"tavern_table", "bar_counter", "wine_cask", "bed", "fireplace", "shelf_bottles", "cauldron", "crate_stack"}
        d.solid_props = {(obj.x, obj.y) for obj in g.objects if obj.kind in solid_kinds}

        g.cam_x = g.player.x * TILE_W - VIEW_W * 0.5
        g.cam_y = g.player.y * TILE_H - VIEW_H * 0.5
        g.set_thought("FX-Полигон! Проверь мягкие тени колонн, круги под ногами в бассейне и 2.5D-туман!")
        g.sfx.play("levelup")

    def handle_event(self, event, EnemyCls, InteractableCls):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F2:
            self.panel_open = not self.panel_open
            self.game.sfx.play("ui")
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
        hint_txt = "[F2] FX-Лаборатория (Закрыть)" if self.panel_open else "[F2] FX-Лаборатория"
        h_s = r.font_small.render(hint_txt, True, (255, 225, 95) if self.panel_open else UI_TEXT_DIM)
        pygame.draw.rect(screen, (16, 14, 22), (SCREEN_W - h_s.get_width() - 20, 8, h_s.get_width() + 12, 22), border_radius=4)
        pygame.draw.rect(screen, UI_BORDER_WOOD, (SCREEN_W - h_s.get_width() - 20, 8, h_s.get_width() + 12, 22), 1, border_radius=4)
        screen.blit(h_s, (SCREEN_W - h_s.get_width() - 14, 11))

        if not self.panel_open:
            return

        pw, ph = 376, 545
        px, py = SCREEN_W - pw - 16, 36
        panel_rect = pygame.Rect(px, py, pw, ph)
        r.draw_pixel_frame(screen, panel_rect, UI_PANEL_BG, UI_BORDER_GOLD, False, 1.0)

        title = r.font_ui.render("🧪 ЭКСПЕРИМЕНТАЛЬНЫЕ FX [F2]", True, UI_BORDER_HIGHLIGHT)
        screen.blit(title, (px + (pw - title.get_width()) // 2, py + 12))

        items = [
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