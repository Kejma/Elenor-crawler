from elenor.rendering.daylight import apply_daylight, visible_sun
import math
import pygame
import numpy as np
from elenor.config import TILE_W, TILE_H, VIEW_W, VIEW_H, CANVAS_H, THOUGHT_BOX_W, THOUGHT_BOX_H, THOUGHT_BOX_X, THOUGHT_BOX_Y, SCALE, SCREEN_W, HUD_HEIGHT, MAP_COLS, MAP_ROWS, UI_BG_DARK, UI_PANEL_BG, UI_SLOT_BG, UI_BORDER_OUTER, UI_BORDER_WOOD, UI_BORDER_GOLD, UI_BORDER_HIGHLIGHT, UI_TEXT_MAIN


from elenor.rendering.assets import make_pair, enforce_crisp_rim_normals, get_carpet_autotile_key, create_placeholder_assets
from elenor.rendering.lighting import GPULightShader
from elenor.ui.renderer import UIRendererMixin

class Renderer(UIRendererMixin):
    def __init__(self):
        self.assets = create_placeholder_assets()
        self.anim_bank = self.assets.pop("_anim_bank", {})
        self.hero_cache = {}
        self.rot_cache = {}
        self.water_normals = {}
        self.flip_cache = {}
        self.chill_cache = {}
        self.emissive_cache = {}
        self.alpha_mask_cache = {}
        self._shadow_small = pygame.Surface((10, 4), pygame.SRCALPHA)
        pygame.draw.ellipse(self._shadow_small, (8, 6, 12, 120), (0, 0, 10, 4))
        self._shadow_big = pygame.Surface((20, 6), pygame.SRCALPHA)
        pygame.draw.ellipse(self._shadow_big, (8, 6, 12, 120), (0, 0, 20, 6))
        self.gpu_shader = None
        try:
            self.gpu_shader = GPULightShader()
            print("[GPU] Аппаратный 2.5D-шейдер ModernGL успешно активирован!")
        except Exception as e:
            print(f"[CPU Fallback] ModernGL не найден ({e}), используем CPU-рендер.")
        self.diff_canvas = pygame.Surface((VIEW_W, CANVAS_H))
        self.norm_canvas = pygame.Surface((VIEW_W, CANVAS_H))
        self.emissive_canvas = pygame.Surface((VIEW_W, CANVAS_H))

        self.px = np.arange(VIEW_W, dtype=np.float32)[:, None]
        self.py = np.arange(CANVAS_H, dtype=np.float32)[None, :]
        self.entity_y_canvas = np.full((VIEW_W, CANVAS_H), -9999.0, dtype=np.float32)
        self.current_hud_lights = []

        self.font_thought = pygame.font.SysFont("consolas", 19, bold=True)
        self.font_ui = pygame.font.SysFont("consolas", 16, bold=True)
        self.font_small = pygame.font.SysFont("consolas", 14, bold=True)
        self.font_title = pygame.font.SysFont("consolas", 20, bold=True)
        self.font_popup = pygame.font.SysFont("consolas", 17, bold=True)
        self.font_popup_big = pygame.font.SysFont("consolas", 24, bold=True)

        hud_y = CANVAS_H * SCALE
        # Центрируем весь боевой пояс ([Q/E] + [1..4] + [5 пассивок]) ровно по центру экрана 1920px!
        belt_total_w = (4 * 58) + 18 + (4 * 58)
        belt_start_x = (SCREEN_W - belt_total_w) // 2
        ab_x = belt_start_x
        hb_x = ab_x + 4 * 58 + 18
        ps_x = hb_x + 4 * 58 + 24

        self.ability_rects = [pygame.Rect(ab_x + i * 58, hud_y + 22, 54, 56) for i in range(4)]
        self.hotbar_rects = [pygame.Rect(hb_x + i * 58, hud_y + 22, 54, 56) for i in range(4)]
        self.passive_slot_rects = []
        self.bag_btn_rect = pygame.Rect(SCREEN_W - 176, hud_y + 22, 156, 56)
        self.inv_slot_rects = []
        self.equip_slot_rects = {}
        self.stat_plus_rects = {}
        self.perk_card_rects = []
        self.modal_rect = pygame.Rect(0, 0, 0, 0)
        self.journal_btn_rect = pygame.Rect(0, 0, 0, 0)
        self.journal_filter_rects = {}

    def get_hero_pair(self, player):
        from elenor.rendering.appearance import build_custom_hero_sprite
        from elenor.rendering.normals import flip_normal_pair_x
        torso = player.equipment["torso"]
        armor_cls = torso.armor_class if torso else "none"
        has_helm = player.equipment["helmet"] is not None
        has_torch = player.has_lit_torch
        has_weap = player.equipment["right_hand"] is not None
        app = getattr(player, "appearance", {})
        h_type = app.get("hero_type", "male")
        s_idx = app.get("skin_idx", 0)
        hd_idx = app.get("head_idx", 0)
        o_idx = app.get("outfit_idx", 0)
        a_frame = getattr(player, "anim_frame", 0)
        moving = getattr(player, "is_moving", False)
        facing = getattr(player, "facing", -1)

        key = (player.cloak_color, armor_cls, has_helm, has_torch, has_weap, h_type, s_idx, hd_idx, o_idx, a_frame, moving, facing)
        if key not in self.hero_cache:
            d_s, n_s = build_custom_hero_sprite(
                cloak_color=player.cloak_color,
                armor_class=armor_cls,
                has_helmet=has_helm,
                has_torch=has_torch,
                has_weapon=has_weap,
                hero_type=h_type,
                skin_idx=s_idx,
                head_idx=hd_idx,
                outfit_idx=o_idx,
                anim_frame=a_frame,
                is_moving=moving,
            )
            if facing > 0:
                d_s, n_s = flip_normal_pair_x(d_s, n_s)
            self.hero_cache[key] = (d_s, n_s)
        return self.hero_cache[key]
    
    def get_tile_pair(self, key, c, r, salt=0):
        """Возвращает (diff, norm) для тайла или оверлея с учётом случайного поворота 0/90/180/270° по координатам клетки!"""
        base_pair = self.assets.get(key, self.assets["floor_0"])
        a_info = self.anim_bank.get(key)
        rrot = a_info.get("random_rot", False) if a_info else (key in ("floor_3", "floor_5", "ov_pebbles", "ov_moss", "ov_cracks", "ov_planks_wear"))
        if not rrot or (a_info and len(a_info.get("frames", [])) > 1):
            return base_pair

        rot_k = ((c * 73 + r * 151 + (c ^ r) * 31 + salt * 19) >> 1) & 3
        if rot_k == 0:
            return base_pair

        cache_key = (key, rot_k)
        if cache_key not in self.rot_cache:
            from elenor.rendering.normals import rotate_normal_pair
            self.rot_cache[cache_key] = rotate_normal_pair(base_pair[0], base_pair[1], rot_k)
        return self.rot_cache[cache_key]

    def get_mob_pair(self, sprite_key, facing, is_chilled=False, flash_mode=None):
        """Зеркалит спрайт моба, накладывает ледяной оттенок и Hit-Flash (красный или бело-золотой при крите)."""
        base_pair = self.assets.get(sprite_key, self.assets["rat"])
        a_info = self.anim_bank.get(sprite_key)
        frame_idx = 0
        if a_info and len(a_info.get("frames", [])) > 1:
            now_sec = pygame.time.get_ticks() * 0.001
            frame_idx = int(now_sec * a_info["fps"]) % len(a_info["frames"])

        if facing > 0:
            cache_key = (sprite_key, frame_idx)
            if cache_key not in self.flip_cache:
                from elenor.rendering.normals import flip_normal_pair_x
                self.flip_cache[cache_key] = flip_normal_pair_x(base_pair[0], base_pair[1])
            pair = self.flip_cache[cache_key]
        else:
            pair = base_pair

        if not is_chilled and not flash_mode:
            return pair

        fx_key = (sprite_key, frame_idx, facing > 0, is_chilled, flash_mode)
        if fx_key not in self.chill_cache:
            d_orig, n_orig = pair
            w, h = d_orig.get_size()
            d_out = d_orig.copy()
            for y in range(h):
                for x in range(w):
                    r, g, b, a = d_out.get_at((x, y))
                    if a > 10:
                        if flash_mode == "crit":
                            # Бело-золотая вспышка при критическом ударе!
                            nr = min(255, int(r * 0.35 + 255 * 0.65))
                            ng = min(255, int(g * 0.35 + 240 * 0.65))
                            nb = min(255, int(b * 0.35 + 150 * 0.65))
                        elif flash_mode == "hit":
                            # Сочная багрово-красная вспышка при обычном попадании!
                            nr = min(255, int(r * 0.35 + 255 * 0.65))
                            ng = max(0, int(g * 0.25))
                            nb = max(0, int(b * 0.25))
                        else:
                            nr = min(255, int(r * 0.55 + 25))
                            ng = min(255, int(g * 0.85 + 55))
                            nb = min(255, int(b * 1.25 + 85))
                        d_out.set_at((x, y), (nr, ng, nb, a))
            self.chill_cache[fx_key] = (d_out, n_orig)
        return self.chill_cache[fx_key]
        base_pair = self.assets.get(sprite_key, self.assets["rat"])
        a_info = self.anim_bank.get(sprite_key)
        frame_idx = 0
        if a_info and len(a_info.get("frames", [])) > 1:
            now_sec = pygame.time.get_ticks() * 0.001
            frame_idx = int(now_sec * a_info["fps"]) % len(a_info["frames"])

        if facing > 0:
            cache_key = (sprite_key, frame_idx)
            if cache_key not in self.flip_cache:
                from elenor.rendering.normals import flip_normal_pair_x
                self.flip_cache[cache_key] = flip_normal_pair_x(base_pair[0], base_pair[1])
            pair = self.flip_cache[cache_key]
        else:
            pair = base_pair

        if not is_chilled:
            return pair

        chill_key = (sprite_key, frame_idx, facing > 0)
        if chill_key not in self.chill_cache:
            d_orig, n_orig = pair
            w, h = d_orig.get_size()
            d_icy = d_orig.copy()
            for y in range(h):
                for x in range(w):
                    r, g, b, a = d_icy.get_at((x, y))
                    if a > 10:
                        nr = min(255, int(r * 0.55 + 25))
                        ng = min(255, int(g * 0.85 + 55))
                        nb = min(255, int(b * 1.25 + 85))
                        d_icy.set_at((x, y), (nr, ng, nb, a))
            self.chill_cache[chill_key] = (d_icy, n_orig)
        return self.chill_cache[chill_key]

    def get_world_loot_pair(self, item):
        """Builds crisp 16x20 pixel-art sprites for coins, gems, and equipment on the dungeon floor!"""
        if item is None or item.type not in ("equipment", "currency_coin", "gem"):
            return self.assets["loot"]
        if not hasattr(self, "world_item_cache"):
            self.world_item_cache = {}
        key = item.icon
        if key not in self.world_item_cache:
            d_surf, n_surf = make_pair(16, 20)

            if item.type == "currency_coin":
                # Рисуем россыпь из 3 плоских овальных монет (4x3 пикселя каждая) на каменном полу!
                c_pal = {
                    "coin_copper":   ((185, 96, 52),  (242, 162, 110), (92, 42, 22)),
                    "coin_silver":   ((175, 190, 210), (245, 252, 255), (78, 86, 102)),
                    "coin_gold":     ((230, 175, 35),  (255, 242, 145), (120, 82, 16)),
                    "coin_platinum": ((135, 220, 245), (240, 255, 255), (58, 105, 130)),
                }
                c_main, c_shine, c_edge = c_pal.get(key, c_pal["coin_gold"])
                # Координаты 3 лежащих плашмя монеток: левая, правая и верхняя внахлёст
                coins_xy = [(3, 15), (8, 16), (6, 13)]
                for cx0, cy0 in coins_xy:
                    # Тёмный гурт (ребро монеты снизу)
                    for dx in range(1, 4):
                        d_surf.set_at((cx0 + dx, cy0 + 2), c_edge)
                        n_surf.set_at((cx0 + dx, cy0 + 2), (128, 38, 200, 255))
                    # Плоское тело монеты (овал 5x2)
                    for dx in range(5):
                        d_surf.set_at((cx0 + dx, cy0 + 1), c_main)
                        n_surf.set_at((cx0 + dx, cy0 + 1), (128, 128, 255, 255))
                    for dx in range(1, 4):
                        col_top = c_shine if dx in (1, 2) else c_main
                        d_surf.set_at((cx0 + dx, cy0), col_top)
                        n_surf.set_at((cx0 + dx, cy0), (128, 218, 200, 255))

            elif item.type == "gem":
                # Рисуем чёткий гранёный самоцвет на полу (y=11..18)
                g_pal = {
                    "gem_green":  ((42, 185, 88),  (165, 255, 190), (22, 95, 45)),
                    "gem_red":    ((210, 38, 62),  (255, 155, 170), (110, 18, 32)),
                    "gem_blue":   ((50, 140, 240), (180, 230, 255), (25, 70, 135)),
                    "gem_orange": ((240, 110, 32), (255, 225, 130), (135, 50, 15)),
                    "gem_purple": ((170, 70, 240), (235, 190, 255), (85, 30, 130)),
                }
                g_main, g_hi, g_dark = g_pal.get(key, g_pal["gem_green"])
                for y in range(11, 18):
                    half_w = 1 if y in (11, 17) else (2 if y in (12, 16) else 3)
                    for x in range(8 - half_w, 8 + half_w):
                        if x < 7 and y <= 14:
                            col, n_col = g_hi, (65, 195, 195, 255)
                        elif x >= 8 and y >= 15:
                            col, n_col = g_dark, (190, 60, 195, 255)
                        else:
                            col, n_col = g_main, (128, 218, 200, 255)
                        d_surf.set_at((x, y), col)
                        n_surf.set_at((x, y), n_col)

            else:
                tmp32 = pygame.Surface((32, 32), pygame.SRCALPHA)
                self.draw_item_icon(tmp32, item.icon, 0, 0, 32)
                scaled16 = pygame.transform.scale(tmp32, (16, 16))
                d_surf.blit(scaled16, (0, 3))
                for y in range(3, 19):
                    for x in range(16):
                        c = d_surf.get_at((x, y))
                        if c[3] > 20:
                            nx = int(np.clip(128 + (x - 7.5) * 10, 55, 200))
                            ny = int(np.clip(195 - (y - 3) * 7, 70, 215))
                            n_surf.set_at((x, y), (nx, ny, 230, 255))

            self.world_item_cache[key] = enforce_crisp_rim_normals(d_surf, n_surf)
        return self.world_item_cache[key]

    def _eval_hud_normal_light(self, nat_x, nat_y, nx, ny, nz):
        """Evaluates directional normal-mapped lighting on HUD elements from player-relative lights!"""
        # Solid readable baseline ambient (0.80) with soft, cozy directional tinting
        r_m, g_m, b_m = 0.80, 0.80, 0.85
        for lgt in self.current_hud_lights:
            lx, ly, lz = lgt["pos"]
            rad = lgt["radius"]
            cr, cg, cb = lgt["color"]
            dx = lx - nat_x
            dy = -(ly - nat_y)
            dist = math.sqrt(dx * dx + dy * dy + lz * lz)
            if dist < rad:
                inv = 1.0 / max(0.001, dist)
                ndotl = max(0.0, nx * (dx * inv) + ny * (dy * inv) + nz * (lz * inv))
                atten = (1.0 - (dist / rad) ** 1.5)
                inten = ndotl * atten * 0.32
                r_m += inten * cr
                g_m += inten * cg
                b_m += inten * cb
        return min(1.25, r_m), min(1.25, g_m), min(1.25, b_m)

    def draw_pixel_frame(self, surface, rect, bg_col=UI_PANEL_BG, border_col=UI_BORDER_WOOD, highlight=False, illum=1.0):
        x, y, w, h = rect
        bd_base = UI_BORDER_HIGHLIGHT if highlight else border_col

        # If this frame is on the Bottom HUD and we have player-relative lights, shade all 4 bevels directionally!
        if y >= VIEW_H * SCALE - 10 and self.current_hud_lights:
            cx_nat = (x + w * 0.5) / SCALE
            cy_nat = (y + h * 0.5) / SCALE
            hw_nat = (w * 0.5) / SCALE
            hh_nat = (h * 0.5) / SCALE

            rm_c, gm_c, bm_c = self._eval_hud_normal_light(cx_nat, cy_nat, 0.0, 0.0, 1.0)
            rm_t, gm_t, bm_t = self._eval_hud_normal_light(cx_nat, cy_nat - hh_nat, 0.0, 0.85, 0.52)
            rm_b, gm_b, bm_b = self._eval_hud_normal_light(cx_nat, cy_nat + hh_nat, 0.0, -0.85, 0.52)
            rm_l, gm_l, bm_l = self._eval_hud_normal_light(cx_nat - hw_nat, cy_nat, -0.85, 0.0, 0.52)
            rm_r, gm_r, bm_r = self._eval_hud_normal_light(cx_nat + hw_nat, cy_nat, 0.85, 0.0, 0.52)

            def tint(col, rm, gm, bm):
                return (min(255, int(col[0] * rm)), min(255, int(col[1] * gm)), min(255, int(col[2] * bm)))

            bg_lit = tint(bg_col, rm_c, gm_c, bm_c)
            col_top = tint(bd_base, rm_t * 1.15, gm_t * 1.15, bm_t * 1.15)
            col_bot = tint(bd_base, rm_b * 0.85, gm_b * 0.85, bm_b * 0.85)
            col_left = tint(bd_base, rm_l, gm_l, bm_l)
            col_right = tint(bd_base, rm_r, gm_r, bm_r)
        else:
            mult = 0.65 + 0.35 * illum
            bg_lit = tuple(min(255, int(c * mult)) for c in bg_col)
            bd_lit = tuple(min(255, int(c * (0.7 + 0.3 * illum))) for c in bd_base)
            col_top = col_bot = col_left = col_right = bd_lit

        pygame.draw.rect(surface, UI_BORDER_OUTER, (x, y, w, h))
        # Draw 4 directional bevel edges (Top, Bottom, Left, Right)
        pygame.draw.rect(surface, col_top, (x + 2, y + 2, w - 4, 3))
        pygame.draw.rect(surface, col_bot, (x + 2, y + h - 5, w - 4, 3))
        pygame.draw.rect(surface, col_left, (x + 2, y + 4, 3, h - 8))
        pygame.draw.rect(surface, col_right, (x + w - 5, y + 4, 3, h - 8))

        pygame.draw.rect(surface, UI_BORDER_OUTER, (x + 5, y + 5, w - 10, h - 10))
        pygame.draw.rect(surface, bg_lit, (x + 7, y + 7, w - 14, h - 14))
        for rx, ry in ((x + 3, y + 3), (x + w - 6, y + 3), (x + 3, y + h - 6), (x + w - 6, y + h - 6)):
            pygame.draw.rect(surface, UI_BORDER_GOLD, (rx, ry, 3, 3))

    def draw_item_icon(self, surface, icon_name, x, y, size=32):
        from elenor.rendering.ability_icons import draw_ability_icon
        if draw_ability_icon(surface, icon_name, x, y, size):
            return
        cx, cy = x + size // 2, y + size // 2
        if icon_name == "torch":
            pygame.draw.line(surface, (140, 90, 45), (cx - 4, cy + 9), (cx + 2, cy - 2), 4)
            pygame.draw.circle(surface, (255, 195, 55), (cx + 3, cy - 5), 5)
            pygame.draw.circle(surface, (255, 110, 35), (cx + 3, cy - 5), 3)
        elif icon_name == "potion_red":
            pygame.draw.rect(surface, (195, 45, 55), (cx - 7, cy - 2, 14, 12))
            pygame.draw.rect(surface, (180, 155, 110), (cx - 3, cy - 8, 6, 6))
        elif icon_name == "potion_blue":
            pygame.draw.rect(surface, (45, 130, 225), (cx - 7, cy - 2, 14, 12))
            pygame.draw.rect(surface, (180, 155, 110), (cx - 3, cy - 8, 6, 6))
        elif icon_name == "bomb":
            pygame.draw.circle(surface, (255, 130, 40), (cx, cy), 8)
            pygame.draw.circle(surface, (255, 220, 90), (cx - 2, cy - 2), 4)
        elif icon_name == "skill_zap":
            pts = [(cx + 4, y + 4), (cx - 6, cy + 1), (cx + 1, cy + 1), (cx - 4, y + size - 4)]
            pygame.draw.lines(surface, (110, 225, 255), False, pts, 3)
        elif icon_name in ("weapon_cleaver", "weapon_sword", "weapon_2h", "weapon_mace"):
            col = (210, 135, 255) if icon_name == "weapon_2h" else ((130, 225, 250) if icon_name == "weapon_sword" else (185, 175, 180))
            w_line = 7 if icon_name == "weapon_2h" else 5
            pygame.draw.line(surface, col, (x + 6, y + size - 6), (x + size - 6, y + 6), w_line)
            if icon_name == "weapon_mace":
                pygame.draw.circle(surface, (200, 205, 215), (x + size - 8, y + 8), 6)
            pygame.draw.line(surface, (165, 120, 60), (x + 4, y + size - 4), (x + 12, y + size - 12), 4)
        elif icon_name == "weapon_dagger":
            pygame.draw.line(surface, (135, 85, 45), (x + 6, y + size - 6), (x + 12, y + size - 12), 4)
            pygame.draw.line(surface, (215, 175, 75), (x + 9, y + size - 14), (x + 14, y + size - 9), 3)
            pygame.draw.line(surface, (220, 230, 245), (x + 12, y + size - 12), (x + size - 5, y + 5), 3)
        elif icon_name == "weapon_curved":
            pts = [(x + 8, y + size - 8), (cx - 2, cy - 2), (cx + 5, cy - 8), (x + size - 5, y + 6)]
            pygame.draw.lines(surface, (215, 185, 115), False, pts, 4)
            pygame.draw.line(surface, (145, 85, 42), (x + 5, y + size - 5), (x + 10, y + size - 10), 4)
        elif icon_name == "weapon_katar":
            pygame.draw.line(surface, (195, 165, 75), (x + 5, y + size - 10), (x + 12, y + size - 5), 3)
            pygame.draw.line(surface, (195, 165, 75), (x + 8, y + size - 13), (x + 15, y + size - 8), 3)
            pygame.draw.polygon(surface, (210, 225, 240), [(x + 10, y + size - 14), (x + 16, y + size - 8), (x + size - 4, y + 4)])
        elif icon_name == "weapon_spear":
            pygame.draw.line(surface, (145, 95, 48), (x + 4, y + size - 4), (x + size - 8, y + 8), 3)
            pygame.draw.polygon(surface, (215, 225, 240), [(x + size - 11, y + 7), (x + size - 3, y + 3), (x + size - 7, y + 11)])
        elif icon_name == "weapon_halberd":
            pygame.draw.line(surface, (140, 90, 45), (x + 4, y + size - 4), (x + size - 5, y + 5), 3)
            pygame.draw.polygon(surface, (195, 205, 220), [(cx - 1, cy - 3), (cx + 10, cy - 6), (cx + 6, cy + 5)])
            pygame.draw.line(surface, (225, 180, 75), (cx - 2, cy - 2), (cx - 6, cy - 6), 3)
        elif icon_name == "weapon_flamberge":
            pts = [(x + 9, y + size - 9), (cx - 2, cy + 2), (cx, cy - 3), (cx + 5, cy - 4), (x + size - 4, y + 4)]
            pygame.draw.lines(surface, (245, 165, 75), False, pts, 4)
            pygame.draw.line(surface, (215, 185, 80), (x + 6, y + size - 13), (x + 13, y + size - 6), 3)
            pygame.draw.line(surface, (135, 75, 40), (x + 4, y + size - 4), (x + 9, y + size - 9), 4)
        elif icon_name == "weapon_thrown_jav":
            pygame.draw.line(surface, (155, 105, 55), (x + 5, y + size - 5), (cx + 3, cy - 3), 3)
            pygame.draw.line(surface, (185, 195, 210), (cx + 2, cy - 2), (x + size - 4, y + 4), 2)
            pygame.draw.circle(surface, (130, 135, 148), (cx + 2, cy - 2), 3)
        elif icon_name == "weapon_thrown_axe":
            pygame.draw.line(surface, (150, 95, 48), (x + 6, y + size - 6), (x + size - 8, y + 8), 4)
            pygame.draw.polygon(surface, (205, 215, 230), [(cx, cy - 4), (x + size - 4, y + 6), (cx + 7, cy + 5)])
        elif icon_name == "weapon_chakram":
            pygame.draw.circle(surface, (220, 235, 250), (cx, cy), 10, 3)
            pygame.draw.circle(surface, (255, 215, 90), (cx, cy), 7, 1)
        elif icon_name == "weapon_bolas":
            pygame.draw.line(surface, (145, 100, 55), (cx, cy), (cx - 8, cy - 6), 2)
            pygame.draw.line(surface, (145, 100, 55), (cx, cy), (cx + 8, cy - 5), 2)
            pygame.draw.line(surface, (145, 100, 55), (cx, cy), (cx, cy + 9), 2)
            for bx, by in ((cx - 8, cy - 6), (cx + 8, cy - 5), (cx, cy + 9)):
                pygame.draw.circle(surface, (175, 180, 192), (bx, by), 4)
        elif icon_name == "weapon_sling":
            pygame.draw.arc(surface, (165, 115, 62), (x + 6, y + 6, size - 12, size - 10), 0.4, 3.8, 3)
            pygame.draw.circle(surface, (185, 192, 205), (cx + 2, cy + 2), 5)
        elif icon_name == "shield":
            pygame.draw.circle(surface, (160, 170, 185), (cx, cy), 10)
            pygame.draw.circle(surface, (215, 175, 80), (cx, cy), 4)
        elif icon_name == "helmet":
            pygame.draw.rect(surface, (170, 180, 195), (cx - 8, cy - 7, 16, 14))
            pygame.draw.rect(surface, (30, 28, 38), (cx - 6, cy - 1, 12, 4))
        elif icon_name in ("armor_cloth", "armor_leather", "armor_plate"):
            col = (95, 75, 150) if icon_name == "armor_cloth" else ((145, 90, 50) if icon_name == "armor_leather" else (185, 195, 210))
            pygame.draw.rect(surface, col, (cx - 9, cy - 8, 18, 18))
            pygame.draw.rect(surface, UI_BORDER_GOLD, (cx - 9, cy - 8, 18, 18), 2)
        elif icon_name == "boots":
            pygame.draw.rect(surface, (135, 85, 45), (cx - 6, cy - 6, 8, 13))
            pygame.draw.rect(surface, (135, 85, 45), (cx - 6, cy + 2, 13, 6))
        elif icon_name == "ring":
            pygame.draw.circle(surface, (235, 195, 75), (cx, cy + 1), 7, 3)
            pygame.draw.circle(surface, (90, 240, 160), (cx, cy - 5), 3)
        elif icon_name == "trinket":
            pygame.draw.polygon(surface, (255, 165, 45), [(cx, cy - 9), (cx + 9, cy), (cx, cy + 9), (cx - 9, cy)])
            pygame.draw.circle(surface, (255, 240, 180), (cx, cy), 3)
        elif icon_name in ("bag_small", "bag_big"):
            col = (155, 100, 55) if icon_name == "bag_small" else (185, 125, 60)
            pygame.draw.rect(surface, col, (cx - 9, cy - 5, 18, 15))
            pygame.draw.rect(surface, (235, 195, 85), (cx - 4, cy - 1, 8, 4))
        elif icon_name == "lock":
            pygame.draw.rect(surface, (95, 88, 102), (cx - 7, cy - 2, 14, 11))
            pygame.draw.rect(surface, (95, 88, 102), (cx - 4, cy - 8, 8, 7), 2)
        elif icon_name in ("coin", "coin_copper", "coin_silver", "coin_gold", "coin_platinum"):
            c_map = {
                "coin": ((235, 185, 45), (255, 240, 140), (135, 95, 20)),
                "coin_copper": ((198, 108, 62), (245, 175, 125), (105, 48, 24)),
                "coin_silver": ((185, 200, 220), (245, 252, 255), (95, 105, 125)),
                "coin_gold": ((240, 188, 40), (255, 245, 150), (140, 98, 18)),
                "coin_platinum": ((140, 225, 250), (240, 255, 255), (65, 115, 145)),
            }
            main_c, hi_c, edge_c = c_map.get(icon_name, c_map["coin"])
            for ox, oy in ((-5, 3), (4, 4), (0, -3)):
                rx, ry = cx + ox - 7, cy + oy - 5
                pygame.draw.ellipse(surface, (20, 16, 26), (rx - 1, ry - 1, 16, 13))
                pygame.draw.ellipse(surface, edge_c, (rx, ry + 2, 14, 9))
                pygame.draw.ellipse(surface, main_c, (rx, ry, 14, 9))
                pygame.draw.ellipse(surface, hi_c, (rx + 2, ry + 1, 10, 6), 1)
        elif icon_name.startswith("gem_"):
            g_map = {
                "gem_green": ((45, 195, 95), (165, 255, 190)),
                "gem_red": ((215, 42, 65), (255, 155, 170)),
                "gem_blue": ((55, 145, 245), (180, 230, 255)),
                "gem_orange": ((245, 115, 35), (255, 225, 130)),
                "gem_purple": ((175, 75, 245), (235, 190, 255)),
            }
            main_c, hi_c = g_map.get(icon_name, g_map["gem_green"])
            pts_out = [(cx, cy - 10), (cx + 9, cy - 2), (cx + 6, cy + 9), (cx - 6, cy + 9), (cx - 9, cy - 2)]
            pts_in = [(cx, cy - 6), (cx + 5, cy - 1), (cx, cy + 5), (cx - 5, cy - 1)]
            pygame.draw.polygon(surface, (20, 16, 26), pts_out, 0)
            pygame.draw.polygon(surface, main_c, pts_out, 0)
            pygame.draw.polygon(surface, hi_c, pts_in, 0)
            pygame.draw.polygon(surface, (25, 20, 32), pts_out, 1)
        elif icon_name == "heart":
            pygame.draw.rect(surface, (225, 60, 70), (cx - 5, cy - 4, 10, 9))
        elif icon_name == "mana":
            pygame.draw.rect(surface, (70, 165, 250), (cx - 5, cy - 4, 10, 9))

    def wrap_text(self, text, font, max_w):
        from elenor.ui.text import wrap_lines
        return list(wrap_lines(text, font, max_w))

    def _get_entity_emissive_surf(self, d_surf, role_kind):
        """Создаёт точечную маску самосвечения ТОЛЬКО для глаз врагов и пламени костров/жаровен/факела."""
        key = (id(d_surf), role_kind)
        if key not in self.emissive_cache:
            w, h = d_surf.get_size()
            em = pygame.Surface((w, h), pygame.SRCALPHA)
            em.fill((0, 0, 0, 0))
            for y in range(h):
                for x in range(w):
                    r, g, b, a = d_surf.get_at((x, y))
                    if a <= 20:
                        continue
                    is_glow = False
                    if role_kind == "mob":
                        # У врагов светятся ТОЛЬКО яркие глаза (красные, жёлтые, голубые, зелёные), но не плащи и не корона!
                        is_eye_zone = (y >= 9) if w > 20 else True
                        if is_eye_zone:
                            if (r >= 235 and g <= 105 and b <= 85) or (r >= 245 and g >= 185 and b <= 75) or (g >= 240 and b >= 115) or (b >= 245 and g >= 245):
                                is_glow = True
                    elif role_kind == "fire_prop":
                        # У костров, жаровен и камина светится только само пламя
                        if r >= 210 and g >= 65 and b <= 165 and not (r < 225 and g > 145):
                            is_glow = True
                    elif role_kind == "hero":
                        # У героя светится только пламя зажжённого факела в руке (верхняя часть факела y <= 9 по краям x <= 3 или x >= 12)
                        if y <= 9 and (x <= 3 or x >= 12) and r >= 240 and g >= 115 and b <= 120:
                            is_glow = True
                    if is_glow:
                        em.set_at((x, y), (255, 255, 255, 255))
            self.emissive_cache[key] = em
        return self.emissive_cache[key]

    def render_frame(self, screen, dungeon, player, mobs, objects, projectiles, particles, popups, cam_x, cam_y, fov_mask, visible_tiles, lights, shown_thought, ui_texts, inv_open, hover_pos, drag_item, hover_target=None, levelup_choices=None, hud_lights=None):
        # Привязываем камеру к целым пикселям буфера, чтобы полностью убрать субпиксельное дрожание тайлов!
        cam_x = float(round(cam_x))
        cam_y = float(round(cam_y))

        now_sec = pygame.time.get_ticks() * 0.001
        for role_id, anim_info in self.anim_bank.items():
            fr_list = anim_info["frames"]
            if len(fr_list) > 1:
                self.assets[role_id] = fr_list[int(now_sec * anim_info["fps"]) % len(fr_list)]

        self.current_hud_lights = hud_lights or []
        self.diff_canvas.fill((12, 10, 16))
        self.norm_canvas.fill((128, 128, 255))
        self.emissive_canvas.fill((0, 0, 0))
        self.entity_y_canvas.fill(-9999.0)

        c0 = max(0, int(cam_x) // TILE_W)
        c1 = min(MAP_COLS, (int(cam_x) + VIEW_W) // TILE_W + 2)
        r0 = max(0, int(cam_y) // TILE_H)
        r1 = min(MAP_ROWS, (int(cam_y) + VIEW_H) // TILE_H + 2)

        tall_trees_to_draw = []
        TILE_ROLE_MAP = {
            1: "wall",
            6: "wall_wood",
            7: "wall_cave",
            8: "floor_5",
            9: "floor_6",
            10: "floor_jungle_grass",
            11: "floor_jungle_mud",
            12: "floor_jungle_soil",
            13: "floor_tribal_wood",
            14: "floor_marble_white",
            15: "floor_marble_dark",
            16: "floor_marble_mosaic",
            17: "wall_mud_rock",
            18: "wall_tribal_wood",
            19: "wall_marble_temple",
            20: "wall_marble_ruined",
            23: "floor_jungle_swamp",
            24: "floor_jungle_cobble",
            25: "floor_river_sand",
            26: "floor_cave_basalt",
            27: "floor_tribal_mat",
            28: "floor_marble_checker",
            29: "floor_marble_rose",
            30: "floor_marble_jade",
            31: "floor_temple_gold",
            32: "floor_temple_water",
            33: "wall_bamboo_weave",
            34: "wall_cave_crystal",
            35: "wall_marble_obsidian",
            36: "wall_temple_relief",
            37: "floor_lake_shallow",
            38: "floor_lake_deep",
            39: "floor_wooden_pier",
            40: "floor_pebble_shore",
        }
        TALL_TREE_MAP = {
            5: ("floor_3", "tall_tree"),
            21: ("floor_jungle_grass", "tall_jungle_tree"),
            22: ("floor_jungle_grass", "tall_palm_tree"),
        }

        tall_trees_to_draw = []
        for r in range(r0, r1):
            for c in range(c0, c1):
                sx = int(c * TILE_W - cam_x)
                sy = int(r * TILE_H - cam_y)
                t_val = dungeon.grid[r][c]
                if t_val in TALL_TREE_MAP:
                    key, tree_asset_key = TALL_TREE_MAP[t_val]
                    if (c, r) in visible_tiles:
                        tall_trees_to_draw.append((c, r, tree_asset_key))
                else:
                    key = TILE_ROLE_MAP.get(t_val, f"floor_{t_val}")
                d_surf, n_surf = self.get_tile_pair(key, c, r)
                if key in ("floor_lake_shallow", "floor_lake_deep"):
                    animation = self.anim_bank.get(key)
                    if animation and animation["frames"]:
                        frames = animation["frames"]
                        phase = (c * 11 + r * 7 + (c * r) % 5) % len(frames)
                        d_surf, n_surf = frames[(int(now_sec * animation["fps"]) + phase) % len(frames)]
                    # Lower the angular contrast of the authored waves in
                    # sunlight so a whole river does not read as diagonal bars.
                    cache_key = (key, n_surf)
                    if cache_key not in self.water_normals:
                        original = pygame.surfarray.array3d(n_surf)
                        softened = original * .43 + np.array((128, 128, 255)) * .57
                        self.water_normals[cache_key] = pygame.surfarray.make_surface(softened.astype(np.uint8))
                    n_surf = self.water_normals[cache_key]
                self.diff_canvas.blit(d_surf, (sx, sy))
                self.norm_canvas.blit(n_surf, (sx, sy))

                # Автотайлинг мха (13 базовых форм + 3 узкие полосы) поверх любого пола!
                if hasattr(dungeon, "moss_tiles") and (c, r) in dungeon.moss_tiles:
                    from elenor.rendering.jungle import get_moss_autotile_key
                    m_key = get_moss_autotile_key(dungeon.moss_tiles, c, r)
                    if m_key in self.assets:
                        m_diff, m_norm = self.assets[m_key]
                        self.diff_canvas.blit(m_diff, (sx, sy))
                        self.norm_canvas.blit(m_norm, (sx, sy))

                # Накладываем полупрозрачный оверлей (камушки, мох, папоротники, цветы, трещины) со случайным поворотом!
                ov_key = getattr(dungeon, "overlays", {}).get((c, r))
                if ov_key and ov_key in self.assets:
                    ov_d, ov_n = self.get_tile_pair(ov_key, c, r, salt=77)
                    self.diff_canvas.blit(ov_d, (sx, sy))
                    self.norm_canvas.blit(ov_n, (sx, sy))

                # Автотайлинг ковра: рисуется поверх досок, но строго под мебелью и персонажами
                if hasattr(dungeon, "carpets") and (c, r) in dungeon.carpets:
                    c_key = get_carpet_autotile_key(dungeon.carpets, c, r)
                    if c_key in self.assets:
                        c_diff, c_norm = self.assets[c_key]
                        self.diff_canvas.blit(c_diff, (sx, sy))
                        self.norm_canvas.blit(c_norm, (sx, sy))

                door = dungeon.doors.get((c, r))
                if door:
                    d_key = "door_open" if door.is_open else ("door_locked" if door.locked else "door_closed")
                    dd, dn = self.assets[d_key]
                    self.diff_canvas.blit(dd, (sx, sy))
                    self.norm_canvas.blit(dn, (sx, sy))

        fx_mgr = ui_texts.get("_fx_mgr")
        # 1. Наложение «Памяти поля боя» (вечная кровь, обломки бочек, вино и копоть на полу)
        if fx_mgr and fx_mgr.flags.get("battle_memory", True):
            self.diff_canvas.blit(fx_mgr.decal_surf, (0, 0), area=pygame.Rect(int(cam_x), int(cam_y), VIEW_W, VIEW_H))

        # 2. Круги на воде при ходьбе по лужам
        if fx_mgr and fx_mgr.flags.get("water_ripples", True):
            for rp in fx_mgr.ripples:
                prog_r = 1.0 - (rp["timer"] / rp["max_timer"])
                rx_s = int(rp["wx"] * TILE_W - cam_x)
                ry_s = int(rp["wy"] * TILE_H - cam_y)
                rad_w = max(2, int(2 + prog_r * 7))
                rad_h = max(1, int(1 + prog_r * 4))
                col_r = (85, 165, 210) if prog_r < 0.5 else (50, 110, 150)
                pygame.draw.ellipse(self.diff_canvas, col_r, (rx_s - rad_w, ry_s - rad_h, rad_w * 2, rad_h * 2), 1)

        render_list = [{
            "wx": player.x - 0.5 + player.bump_x,
            "wy": player.y - 0.5 + player.bump_y,
            "actor_wx": player.x,
            "actor_wy": player.y,
            "is_player": True,
            "is_actor": True,
            "emissive_role": "hero" if player.has_lit_torch else None,
            "pair": self.get_hero_pair(player),
            "alpha": 255
        }]

        for (tc, tr, tree_asset_key) in tall_trees_to_draw:
            behind_canopy = (tr - 1.8 <= player.y <= tr + 0.35) and (abs(player.x - (tc + 0.5)) <= 1.05)
            t_alpha = 105 if behind_canopy else 255
            render_list.append({
                "wx": float(tc), "wy": float(tr),
                "is_tree": True,
                "pair": self.assets.get(tree_asset_key, self.assets["tall_tree"]),
                "alpha": t_alpha
            })

        for (lx, ly), lev in dungeon.levers.items():
            if (lx, ly) in visible_tiles:
                render_list.append({
                    "wx": float(lx), "wy": float(ly),
                    "pair": self.assets["lever_on" if lev.pulled else "lever_off"],
                    "alpha": 255
                })
        for br in dungeon.braziers:
            if (br["x"], br["y"]) in visible_tiles:
                render_list.append({
                    "wx": float(br["x"]), "wy": float(br["y"]),
                    "is_light_source": True,
                    "emissive_role": "fire_prop",
                    "pair": self.assets["brazier"], "alpha": 255
                })
        for obj in objects:
            if not obj.used and (obj.x, obj.y) in visible_tiles:
                if obj.kind in ("woven_rug", "stairs", "trap", "mirror_rail_h", "mirror_rail_v"):
                    fd, fn = self.assets[obj.kind]
                    self.diff_canvas.blit(fd, (int(obj.x * TILE_W - cam_x), int(obj.y * TILE_H - cam_y - 4)))
                    self.norm_canvas.blit(fn, (int(obj.x * TILE_W - cam_x), int(obj.y * TILE_H - cam_y - 4)))
                    continue
                pair = self.get_world_loot_pair(obj.item) if obj.kind == "loot" else self.assets.get(obj.kind, self.assets["loot"])
                is_npc = (obj.kind in ("npc_innkeeper", "npc_merchant"))
                is_fire = (obj.kind in ("campfire", "fireplace", "light_emitter", "light_receiver_on"))
                render_list.append({
                    "wx": float(obj.x), "wy": float(obj.y),
                    "actor_wx": obj.x + 0.5, "actor_wy": obj.y + 0.5,
                    "is_actor": is_npc,
                    "is_light_source": is_fire,
                    "emissive_role": "fire_prop" if is_fire else None,
                    "pair": pair, "alpha": 255
                })

        use_hit_flash = fx_mgr.flags.get("hit_flash", True) if fx_mgr else True
        for m in mobs:
            mx_i, my_i = int(m.x), int(m.y)
            if getattr(m, "size_tiles", 1) >= 2:
                mob_vis = any((mx_i + dx, my_i + dy) in visible_tiles for dx in (-1, 0, 1) for dy in (-1, 0, 1))
            else:
                mob_vis = (mx_i, my_i) in visible_tiles
            if mob_vis:
                chilled = getattr(m, "slow_timer", 0.0) > 0.0
                f_mode = None
                if use_hit_flash and getattr(m, "hit_flash_timer", 0.0) > 0.0:
                    f_mode = "crit" if getattr(m, "hit_flash_crit", False) else "hit"
                render_list.append({
                    "wx": m.x - 0.5 + m.bump_x,
                    "wy": m.y - 0.5 + m.bump_y,
                    "actor_wx": m.x,
                    "actor_wy": m.y,
                    "is_actor": True,
                    "emissive_role": "mob",
                    "pair": self.get_mob_pair(m.sprite, getattr(m, "facing", -1), is_chilled=chilled, flash_mode=f_mode),
                    "alpha": 255
                })

        render_list.sort(key=lambda item: item["wy"])

        use_shadows = fx_mgr.flags.get("drop_shadows", True) if fx_mgr else True
        world_shadow_lights = [(br["x"] + 0.5, br["y"] + 0.5, br["radius"] / TILE_W) for br in dungeon.braziers]
        for obj in objects:
            if obj.kind in ("campfire", "fireplace"):
                world_shadow_lights.append((obj.x + 0.5, obj.y + 0.5, 7.2))

        for ent in render_list:
            d_surf, n_surf = ent["pair"]
            ew, eh = d_surf.get_size()
            draw_x = int(round(ent["wx"] * TILE_W - cam_x - (ew - TILE_W) // 2))
            draw_y = int(round(ent["wy"] * TILE_H - cam_y - (eh - TILE_H)))
            sole_sy = float(draw_y + eh - 2)
            if draw_y + eh > 0 and draw_y < VIEW_H:
                if use_shadows and ent.get("is_actor", False):
                    awx = ent.get("actor_wx", ent["wx"] + 0.5)
                    awy = ent.get("actor_wy", ent["wy"] + 0.5)
                    vec_x, vec_y, w_sum = 0.0, 0.0, 0.0
                    for lwx, lwy, lrad in world_shadow_lights:
                        dx_w = awx - lwx
                        dy_w = awy - lwy
                        dist_w = math.hypot(dx_w, dy_w)
                        if 0.1 < dist_w < lrad:
                            w_l = (1.0 - dist_w / lrad) ** 1.5
                            vec_x += (dx_w / dist_w) * w_l
                            vec_y += (dy_w / dist_w) * w_l
                            w_sum += w_l
                    if not ent.get("is_player", False) and player.has_lit_torch:
                        dx_p = awx - player.x
                        dy_p = awy - player.y
                        dist_p = math.hypot(dx_p, dy_p)
                        if 0.1 < dist_p < 7.5:
                            w_p = (1.0 - dist_p / 7.5) ** 1.4 * 1.5
                            vec_x += (dx_p / dist_p) * w_p
                            vec_y += (dy_p / dist_p) * w_p
                            w_sum += w_p

                    if w_sum > 0.01:
                        sh_dx = max(-3.5, min(3.5, (vec_x / w_sum) * 3.0))
                        sh_dy = max(-2.0, min(2.5, (vec_y / w_sum) * 1.8))
                    else:
                        sh_dx, sh_dy = 0.0, 0.5

                    if ew > 20:
                        sh_stamp, sh_w, sh_h = self._shadow_big, 20, 6
                    else:
                        sh_stamp, sh_w, sh_h = self._shadow_small, 10, 4
                    foot_cx = draw_x + ew * 0.5
                    self.diff_canvas.blit(sh_stamp, (int(round(foot_cx - sh_w * 0.5 + sh_dx)), int(round(sole_sy - sh_h * 0.5 + sh_dy))))

                if ent["alpha"] < 255:
                    d_tmp = d_surf.copy()
                    d_tmp.set_alpha(ent["alpha"])
                    self.diff_canvas.blit(d_tmp, (draw_x, draw_y))
                else:
                    self.diff_canvas.blit(d_surf, (draw_x, draw_y))
                    self.norm_canvas.blit(n_surf, (draw_x, draw_y))
                    em_role = ent.get("emissive_role")
                    if em_role:
                        em_s = self._get_entity_emissive_surf(d_surf, em_role)
                        self.emissive_canvas.blit(em_s, (draw_x, draw_y))

                    if not ent.get("is_light_source", False):
                        y_start_depth = draw_y + 28 if ent.get("is_tree", False) else draw_y
                        cx0, cx1 = max(0, draw_x), min(VIEW_W, draw_x + ew)
                        cy0, cy1 = max(0, y_start_depth), min(VIEW_H, draw_y + eh)
                        if cx0 < cx1 and cy0 < cy1:
                            s_id = id(d_surf)
                            a_mask = self.alpha_mask_cache.get(s_id)
                            if a_mask is None:
                                a_mask = pygame.surfarray.array_alpha(d_surf) > 15
                                self.alpha_mask_cache[s_id] = a_mask
                            mask_slice = a_mask[cx0 - draw_x:cx1 - draw_x, cy0 - draw_y:cy1 - draw_y]
                            np.copyto(self.entity_y_canvas[cx0:cx1, cy0:cy1], sole_sy, where=mask_slice)

        game_ref = ui_texts.get("_game_ref")
        cast = getattr(game_ref, "fishing_cast", None)
        if cast is not None:
            from elenor.rendering.fishing_cast import draw_fishing_cast
            draw_fishing_cast(self.diff_canvas, self.norm_canvas, cast, cam_x, cam_y, now_sec)

        tz_diff, tz_norm = self.assets["thought_zone"]
        self.diff_canvas.blit(tz_diff, (0, VIEW_H))
        self.norm_canvas.blit(tz_norm, (0, VIEW_H))

        ambient_light = getattr(dungeon, "ambient_light", (0.0, 0.0, 0.0))
        sunlight = visible_sun(getattr(dungeon, "sunlight", None), cam_x, cam_y)
        if self.gpu_shader is not None:
            en_ao = fx_mgr.flags.get("ao", True) if fx_mgr else True
            en_bloom = fx_mgr.flags.get("bloom", True) if fx_mgr else True
            en_fog = fx_mgr.flags.get("volumetric_fog", True) if fx_mgr else True
            w_grid = fx_mgr.wall_grid_np if fx_mgr else None
            clouds = fx_mgr.active_clouds if fx_mgr else None
            lit_surf = self.gpu_shader.render_lit_surface(
                self.diff_canvas, self.norm_canvas, self.entity_y_canvas,
                fov_mask, cam_x, cam_y, lights, self.current_hud_lights,
                wall_grid_np=w_grid, emissive_canvas=self.emissive_canvas,
                enable_ao=en_ao, enable_bloom=en_bloom,
                enable_fog=en_fog, active_clouds=clouds, now_sec=now_sec,
                ambient_light=ambient_light, sunlight=sunlight
            )
            r_mult = g_mult = b_mult = None
        else:
            diff = pygame.surfarray.array3d(self.diff_canvas).astype(np.float32)
            norm = pygame.surfarray.array3d(self.norm_canvas).astype(np.float32)

            nx = (norm[:, :, 0] - 128.0) / 127.0
            ny = (norm[:, :, 1] - 128.0) / 127.0
            nz = (norm[:, :, 2] - 128.0) / 127.0

            is_ent = self.entity_y_canvas > -9000.0
            if not hasattr(self, "_cpu_light_buffers"):
                self._cpu_light_buffers = np.zeros((7, VIEW_W, CANVAS_H), dtype=np.float32)
            self._cpu_light_buffers.fill(0)
            rim_canvas, r_mult, g_mult, b_mult, rim_add_r, rim_add_g, rim_add_b = self._cpu_light_buffers
            rim_canvas[1:-1, 1:VIEW_H - 1] = is_ent[1:-1, 1:VIEW_H - 1] & (
                (~is_ent[:-2, 1:VIEW_H - 1]) | (~is_ent[2:, 1:VIEW_H - 1]) |
                (~is_ent[1:-1, :VIEW_H - 2]) | (~is_ent[1:-1, 2:VIEW_H])
            )

            tx_screen = np.clip(((self.px[:, 0] + cam_x) // TILE_W).astype(np.int32), 0, MAP_COLS - 1)
            ty_screen = np.clip(((self.py[0, :VIEW_H] + cam_y) // TILE_H).astype(np.int32), 0, MAP_ROWS - 1)


            for channel, ambient in zip((r_mult, g_mult, b_mult), ambient_light):
                channel[:, :VIEW_H] = ambient
            apply_daylight((r_mult, g_mult, b_mult), (nx, ny, nz), sunlight)
            r_mult[:, VIEW_H:] = 0.74
            g_mult[:, VIEW_H:] = 0.74
            b_mult[:, VIEW_H:] = 0.80

            for lgt in lights:
                lx, ly, lz = lgt["pos"]
                radius = lgt["radius"]
                cr, cg, cb = lgt["color"]

                x0 = max(0, int(lx - radius - 2))
                x1 = min(VIEW_W, int(lx + radius + 3))
                y0 = max(0, int(ly - radius - 2))
                y1 = min(VIEW_H, int(ly + radius + 3))
                if x0 >= x1 or y0 >= y1:
                    continue

                dx = lx - self.px[x0:x1, :]
                dy = -(ly - self.py[:, y0:y1])

                ent_y = self.entity_y_canvas[x0:x1, y0:y1]
                light_foot_y = lgt.get("foot_y", ly + 4.0)
                if lgt.get("ignore_depth", False):
                    behind_ratio = np.zeros_like(ent_y)
                else:
                    behind_ratio = np.where(ent_y > -9000.0, np.clip((ent_y - light_foot_y) / 4.5, 0.0, 1.0), 0.0)

                dist = np.sqrt(dx * dx + dy * dy + lz * lz)
                inv_dist = 1.0 / np.maximum(dist, 0.001)

                sub_nx = nx[x0:x1, y0:y1]
                sub_ny = ny[x0:x1, y0:y1]
                sub_nz = nz[x0:x1, y0:y1]

                raw_dot = sub_nx * (dx * inv_dist) + sub_ny * (dy * inv_dist) + sub_nz * (lz * inv_dist)
                z_wrap = np.maximum(0.0, sub_nz * (lz * inv_dist)) * 0.65
                ndotl = np.maximum(z_wrap, raw_dot)
                atten = np.clip(1.0 - (dist / radius) ** 1.65, 0.0, 1.0)

                allowed_tiles = lgt.get("allowed_tiles")
                if allowed_tiles is not None:
                    if isinstance(allowed_tiles, np.ndarray):
                        atten = atten * allowed_tiles[tx_screen[x0:x1, None], ty_screen[None, y0:y1]]

                sub_rim = rim_canvas[x0:x1, y0:y1]
                front_shade = 1.0 - behind_ratio * (1.0 - sub_rim) * 0.65
                intensity = ndotl * atten * 1.45 * front_shade

                r_mult[x0:x1, y0:y1] += intensity * cr
                g_mult[x0:x1, y0:y1] += intensity * cg
                b_mult[x0:x1, y0:y1] += intensity * cb

                if not lgt.get("ignore_depth", False):
                    dist_2d = np.sqrt(dx * dx + dy * dy)
                    close_falloff = np.clip(1.0 - dist_2d / min(radius * 0.72, 48.0), 0.0, 1.0) ** 2.4
                    if isinstance(allowed_tiles, np.ndarray):
                        close_falloff = close_falloff * allowed_tiles[tx_screen[x0:x1, None], ty_screen[None, y0:y1]]
                    rim_boost = sub_rim * behind_ratio * close_falloff * 145.0
                    rim_add_r[x0:x1, y0:y1] += rim_boost * cr
                    rim_add_g[x0:x1, y0:y1] += rim_boost * cg
                    rim_add_b[x0:x1, y0:y1] += rim_boost * cb

            r_mult *= fov_mask
            g_mult *= fov_mask
            b_mult *= fov_mask

            out = np.empty_like(diff)
            base_r = diff[:, :, 0] * r_mult
            base_g = diff[:, :, 1] * g_mult
            base_b = diff[:, :, 2] * b_mult
            out[:, :, 0] = np.clip(np.where(rim_add_r > 0.5, np.minimum(228.0, base_r * 1.25 + rim_add_r * fov_mask), base_r), 0, 255)
            out[:, :, 1] = np.clip(np.where(rim_add_g > 0.5, np.minimum(222.0, base_g * 1.25 + rim_add_g * fov_mask), base_g), 0, 255)
            out[:, :, 2] = np.clip(np.where(rim_add_b > 0.5, np.minimum(220.0, base_b * 1.25 + rim_add_b * fov_mask), base_b), 0, 255)
            lit_surf = pygame.surfarray.make_surface(out.astype(np.uint8))

        scaled_view = pygame.transform.scale(lit_surf, (VIEW_W * SCALE, CANVAS_H * SCALE))
        screen.blit(scaled_view, (0, 0))

        if game_ref is not None and getattr(game_ref, "mirror_puzzles", None):
            from elenor.rendering.mirrors import render_mirror_puzzles_beams
            from elenor.rendering.visibility import overlay_visibility
            visibility = overlay_visibility(fov_mask, lights, cam_x, cam_y)
            render_mirror_puzzles_beams(screen, game_ref, cam_x, cam_y, visible_tiles, visibility)

        if game_ref is not None and getattr(game_ref, "physical_effects", None):
            from elenor.rendering.physical import render_physical
            from elenor.rendering.visibility import overlay_visibility
            render_physical(screen, game_ref, cam_x, cam_y, overlay_visibility(fov_mask,lights,cam_x,cam_y))

        # 5. Пылинки и споры, видимые ТОЛЬКО когда они пролетают сквозь лучи света!
        if fx_mgr and fx_mgr.flags.get("dust_motes", True):
            for dm in fx_mgr.dust_motes:
                mtx, mty = int(dm["wx"]), int(dm["wy"])
                if (mtx, mty) not in visible_tiles:
                    continue
                msx = dm["wx"] * TILE_W - cam_x
                msy = dm["wy"] * TILE_H - cam_y
                if not (2 <= msx < VIEW_W - 2 and 2 <= msy < VIEW_H - 2):
                    continue
                # Проверяем освещённость точки пылинки от реальных источников света (пропуская базовое ночное зрение lights[0])
                m_lum = 0.0
                m_col = [180, 170, 140]
                for lgt in lights[1:]:
                    lx, ly, lz = lgt["pos"]
                    rad = lgt["radius"]
                    d2 = math.hypot(msx - lx, msy - ly)
                    if d2 < rad * 0.85:
                        alw = lgt.get("allowed_tiles")
                        if isinstance(alw, np.ndarray) and alw[mtx, mty] < 0.5:
                            continue
                        inten = (1.0 - d2 / (rad * 0.85)) ** 1.4
                        if inten > m_lum:
                            m_lum = inten
                            cr, cg, cb = lgt["color"]
                            m_col = [min(255, int(195 * cr)), min(255, int(185 * cg)), min(255, int(165 * cb))]
                if m_lum > 0.18:
                    twinkle = 0.65 + 0.35 * math.sin(dm["phase"] * 2.5)
                    br_factor = min(1.0, m_lum * twinkle * 1.3)
                    final_c = (int(m_col[0] * br_factor), int(m_col[1] * br_factor), int(m_col[2] * br_factor))
                    sz_p = dm["size"] * 2
                    pygame.draw.rect(screen, final_c, (int(msx * SCALE), int(msy * SCALE), sz_p, sz_p))

        # Precision targeting works silently under the hood (visual reticle removed as requested)

        # Particles & Projectiles
        for pt in particles:
            sx = int((pt.wx * TILE_W - cam_x) * SCALE)
            sy = int((pt.wy * TILE_H - cam_y) * SCALE)
            if 0 <= sy < VIEW_H * SCALE:
                rad = max(2, int(pt.size * (pt.life / pt.max_life) * SCALE * 0.6))
                pygame.draw.circle(screen, pt.color, (sx, sy), rad)

        for pr in projectiles:
            sx = int((pr.wx * TILE_W - cam_x) * SCALE)
            sy = int((pr.wy * TILE_H - cam_y) * SCALE)
            if 0 <= sy < VIEW_H * SCALE:
                vk = getattr(pr, "visual_kind", "orb")
                ang = getattr(pr, "angle", 0.0)
                cos_a, sin_a = math.cos(ang), math.sin(ang)
                perp_x, perp_y = -sin_a, cos_a

                if vk == "spinning_dagger":
                    tip = (int(sx + cos_a * 14), int(sy + sin_a * 14))
                    guard_c = (int(sx - cos_a * 3), int(sy - sin_a * 3))
                    pommel = (int(sx - cos_a * 12), int(sy - sin_a * 12))
                    g1 = (int(guard_c[0] + perp_x * 6), int(guard_c[1] + perp_y * 6))
                    g2 = (int(guard_c[0] - perp_x * 6), int(guard_c[1] - perp_y * 6))
                    pygame.draw.line(screen, (20, 18, 26), pommel, tip, 6)
                    pygame.draw.line(screen, (135, 82, 42), pommel, guard_c, 4)
                    pygame.draw.line(screen, (215, 175, 70), g1, g2, 3)
                    pygame.draw.line(screen, (210, 220, 235), guard_c, tip, 4)
                    pygame.draw.line(screen, (250, 252, 255), guard_c, tip, 2)
                elif vk == "thrown_javelin":
                    tail = (int(sx - cos_a * 18), int(sy - sin_a * 18))
                    neck = (int(sx + cos_a * 6), int(sy + sin_a * 6))
                    tip = (int(sx + cos_a * 18), int(sy + sin_a * 18))
                    pygame.draw.line(screen, (20, 18, 26), tail, tip, 5)
                    pygame.draw.line(screen, (150, 98, 48), tail, neck, 3)
                    pygame.draw.line(screen, (220, 230, 245), neck, tip, 3)
                elif vk == "thrown_axe":
                    haft0 = (int(sx - cos_a * 12), int(sy - sin_a * 12))
                    haft1 = (int(sx + cos_a * 10), int(sy + sin_a * 10))
                    b1 = (int(haft1[0] + perp_x * 9), int(haft1[1] + perp_y * 9))
                    b2 = (int(sx + cos_a * 3 + perp_x * 7), int(sy + sin_a * 3 + perp_y * 7))
                    pygame.draw.line(screen, (145, 90, 44), haft0, haft1, 4)
                    pygame.draw.polygon(screen, (215, 225, 240), [haft1, b1, b2])
                elif vk == "thrown_chakram":
                    pygame.draw.circle(screen, (25, 22, 32), (sx, sy), 12, 5)
                    pygame.draw.circle(screen, (220, 235, 250), (sx, sy), 11, 3)
                    pygame.draw.circle(screen, (255, 220, 95), (int(sx + cos_a * 9), int(sy + sin_a * 9)), 3)
                elif vk == "thrown_bolas":
                    for b_i in range(3):
                        ba = ang + b_i * (2.0 * math.pi / 3.0)
                        bx = int(sx + math.cos(ba) * 11)
                        by = int(sy + math.sin(ba) * 11)
                        pygame.draw.line(screen, (155, 108, 58), (sx, sy), (bx, by), 2)
                        pygame.draw.circle(screen, (180, 185, 198), (bx, by), 4)
                elif vk == "sling_stone":
                    pygame.draw.circle(screen, (30, 28, 36), (sx, sy), 6)
                    pygame.draw.circle(screen, (190, 198, 210), (sx, sy), 4)
                else:
                    # Огненная / магическая комета с пламенным хвостом и пульсирующим ядром
                    c_r, c_g, c_b = pr.color
                    dark_tail = (max(0, c_r - 70), max(0, c_g // 2), max(0, c_b // 2))
                    tail_tip = (int(sx - cos_a * 26), int(sy - sin_a * 26))
                    tail_mid = (int(sx - cos_a * 16), int(sy - sin_a * 16))
                    w1 = (int(sx - cos_a * 4 + perp_x * 9), int(sy - sin_a * 4 + perp_y * 9))
                    w2 = (int(sx - cos_a * 4 - perp_x * 9), int(sy - sin_a * 4 - perp_y * 9))
                    pygame.draw.polygon(screen, dark_tail, [tail_tip, w1, w2])
                    pygame.draw.polygon(screen, pr.color, [tail_mid, (int(sx + perp_x * 6), int(sy + perp_y * 6)), (int(sx - perp_x * 6), int(sy - perp_y * 6))])
                    pygame.draw.circle(screen, dark_tail, (sx, sy), 11)
                    pygame.draw.circle(screen, pr.color, (sx, sy), 8)
                    pygame.draw.circle(screen, (255, 240, 155), (sx, sy), 5)
                    pygame.draw.circle(screen, (255, 255, 245), (int(sx + cos_a * 2), int(sy + sin_a * 2)), 3)

        # Enemy Awareness, HP, Ground Roots & Chattering Speech Bubbles (with Darkness Camouflage!)
        for m in mobs:
            mx_i, my_i = int(m.x), int(m.y)
            if getattr(m, "size_tiles", 1) >= 2:
                vis = any((mx_i + dx, my_i + dy) in visible_tiles for dx in (-1, 0, 1) for dy in (-1, 0, 1))
            else:
                vis = (mx_i, my_i) in visible_tiles

            # Check actual light intensity at the enemy's position on canvas so dark tiles NEVER leak enemy UI!
            cx_canv = max(0, min(VIEW_W - 1, int(m.x * TILE_W - cam_x)))
            cy_canv = max(0, min(VIEW_H - 1, int((m.y - 0.2) * TILE_H - cam_y)))
            if r_mult is not None:
                tile_lum = float(r_mult[cx_canv, cy_canv] + g_mult[cx_canv, cy_canv] + b_mult[cx_canv, cy_canv])
            elif fov_mask[cx_canv, cy_canv] <= 0.05:
                tile_lum = 0.0
            else:
                tile_lum = 0.0
                mtx = max(0, min(MAP_COLS - 1, int(m.x)))
                mty = max(0, min(MAP_ROWS - 1, int(m.y)))
                for lgt in lights:
                    lx, ly, lz = lgt["pos"]
                    rad = lgt["radius"]
                    dist_l = math.sqrt((lx - cx_canv) ** 2 + (ly - cy_canv) ** 2 + lz ** 2)
                    if dist_l < rad:
                        alw = lgt.get("allowed_tiles")
                        if isinstance(alw, np.ndarray) and alw[mtx, mty] < 0.5:
                            continue
                        cr, cg, cb = lgt["color"]
                        tile_lum += (1.0 - (dist_l / rad) ** 1.65) * (cr + cg + cb)
            is_lit = vis and (tile_lum > 0.16 or getattr(m, "glow_timer", 0.0) > 0.0)
            if is_lit:
                m.last_lit_pos = (m.x, m.y)

            dist_to_p = math.hypot(m.x - player.x, m.y - player.y)
            if is_lit or (m.current_speech and dist_to_p <= 11.5):
                head_off = 1.65 if getattr(m, "size_tiles", 1) >= 2 else 0.85
                sx = int((m.x * TILE_W - cam_x) * SCALE)
                sy = int(((m.y - head_off) * TILE_H - cam_y) * SCALE)
                foot_y = int((m.y * TILE_H - cam_y) * SCALE)

                # Clear visual indication on the enemy model when it begins channeling a pentagram!
                if is_lit and getattr(m, "cast_windup_timer", 0.0) > 0.0 and 0 <= foot_y < VIEW_H * SCALE:
                    w_ratio = m.cast_windup_timer / max(0.01, getattr(m, "cast_windup_max", 0.65))
                    body_cy = (sy + foot_y) // 2
                    ring_r = max(10, int((14 + 28 * w_ratio) * (1.4 if getattr(m, "size_tiles", 1) >= 2 else 1.0)))
                    pygame.draw.circle(screen, (255, 45, 70), (sx, body_cy), ring_r, 2)
                    pygame.draw.circle(screen, (255, 185, 80), (sx, body_cy), max(4, ring_r - 6), 1)
                    paw_span = 26 if getattr(m, "size_tiles", 1) >= 2 else 15
                    for px_off in (-paw_span, paw_span):
                        pygame.draw.circle(screen, (235, 35, 60), (sx + px_off, body_cy - 6), 7)
                        pygame.draw.circle(screen, (255, 225, 130), (sx + px_off, body_cy - 6), 4)

                # Draw thorny roots / ice shards around the enemy while rooted!
                if is_lit and getattr(m, "root_timer", 0.0) > 0.0 and 0 <= foot_y < VIEW_H * SCALE:
                    is_ice = getattr(m, "chill_after_root", 0.0) > 0.0
                    c_outer = (55, 145, 215) if is_ice else (65, 42, 24)
                    c_inner = (165, 240, 255) if is_ice else (85, 165, 70)
                    pygame.draw.ellipse(screen, (28, 36, 48) if is_ice else (38, 26, 18), (sx - 20, foot_y - 6, 40, 12))
                    for r_idx, rx_off in enumerate((-14, -7, 0, 7, 14)):
                        sway = int(math.sin(now_sec * 5.0 + r_idx) * (1 if is_ice else 3))
                        pts = [
                            (sx + rx_off, foot_y + 2),
                            (sx + rx_off - sway, foot_y - 10),
                            (sx + rx_off // 2 + sway, foot_y - 22)
                        ]
                        pygame.draw.lines(screen, c_outer, False, pts, 4)
                        pygame.draw.lines(screen, c_inner, False, pts, 2)

                # Крохотные пламенные партиклы на горящем противнике (без громоздких кругов и надписей!)
                if is_lit and getattr(m, "burn_timer", 0.0) > 0.0 and 0 <= foot_y < VIEW_H * SCALE:
                    span_x = 18 if getattr(m, "size_tiles", 1) >= 2 else 10
                    for p_i in range(6):
                        phase = (now_sec * 6.5 + p_i * 1.37 + m.x) % 1.0
                        px_off = int(math.sin(p_i * 2.4 + now_sec * 4.0) * span_x)
                        py_off = int(foot_y - 6 - phase * 26)
                        p_col = (255, 235, 110) if phase < 0.45 else (255, 115, 30)
                        sz = 3 if phase < 0.6 else 2
                        pygame.draw.rect(screen, p_col, (sx + px_off, py_off, sz, sz))

                # Звёздочки оглушения (Stun), кружащиеся над головой контуженного врага
                if is_lit and getattr(m, "stun_timer", 0.0) > 0.0 and 0 <= sy < VIEW_H * SCALE:
                    orbit_rx = 20 if getattr(m, "size_tiles", 1) >= 2 else 13
                    orbit_ry = 6 if getattr(m, "size_tiles", 1) >= 2 else 4
                    orbit_cy = sy - 14
                    for st_i in range(3):
                        ang_s = now_sec * 7.5 + st_i * (2.0 * math.pi / 3.0)
                        st_x = sx + int(math.cos(ang_s) * orbit_rx)
                        st_y = orbit_cy + int(math.sin(ang_s) * orbit_ry)
                        # Рисуем 4-лучевую золотую звёздочку с тёмной обводкой и белым центром
                        pygame.draw.line(screen, (25, 18, 12), (st_x - 4, st_y), (st_x + 4, st_y), 3)
                        pygame.draw.line(screen, (25, 18, 12), (st_x, st_y - 4), (st_x, st_y + 4), 3)
                        pygame.draw.line(screen, (255, 220, 65), (st_x - 3, st_y), (st_x + 3, st_y), 2)
                        pygame.draw.line(screen, (255, 220, 65), (st_x, st_y - 3), (st_x, st_y + 3), 2)
                        pygame.draw.rect(screen, (255, 255, 235), (st_x - 1, st_y - 1, 2, 2))

                # HP bars & Awareness ONLY render when the mob is actually illuminated (`is_lit`)! (Текстовые дебаффы убраны)
                if is_lit and 0 <= sy < VIEW_H * SCALE:
                    if m.hp < m.max_hp:
                        bar_w = 56 if getattr(m, "size_tiles", 1) >= 2 else 36
                        pygame.draw.rect(screen, (25, 15, 20), (sx - bar_w // 2, sy - 8, bar_w, 6))
                        w_hp = int((bar_w - 2) * (m.hp / m.max_hp))
                        pygame.draw.rect(screen, (220, 55, 65), (sx - bar_w // 2 + 1, sy - 7, w_hp, 4))

                    if getattr(m, "alert_bang_timer", 0.0) > 0.0:
                        lbl = self.font_popup.render("!", True, (255, 75, 75))
                        screen.blit(lbl, (sx - lbl.get_width() // 2, sy - 26))
                    elif m.state != "combat" and m.awareness > 2.0:
                        pct = m.awareness / 100.0
                        col = (255, int(235 * (1.0 - pct * 0.6)), 60)
                        pygame.draw.rect(screen, (20, 18, 25), (sx - 16, sy - 20, 32, 7))
                        pygame.draw.rect(screen, col, (sx - 15, sy - 19, int(30 * pct), 5))
                        lbl = self.font_small.render("?", True, col)
                        screen.blit(lbl, (sx - lbl.get_width() // 2, sy - 35))
                    elif m.state == "sleeping" and not m.current_speech:
                        lbl = self.font_small.render("Zzz...", True, (150, 175, 220))
                        screen.blit(lbl, (sx - lbl.get_width() // 2, sy - 24))
                    elif m.state == "eating" and not m.current_speech:
                        lbl = self.font_small.render("*хруст*", True, (215, 170, 120))
                        screen.blit(lbl, (sx - lbl.get_width() // 2, sy - 24))

                if m.current_speech:
                    # If the mob is in darkness, anchor the bubble at `last_lit_pos` or on the rim of player's light
                    # so speech bubbles NEVER act as a real-time wallhack/radar in the dark!
                    if is_lit:
                        bsx, bsy = sx, sy
                        txt_col = (240, 235, 210)
                    elif getattr(m, "last_lit_pos", None):
                        lx_p, ly_p = m.last_lit_pos
                        bsx = int((lx_p * TILE_W - cam_x) * SCALE)
                        bsy = int(((ly_p - head_off) * TILE_H - cam_y) * SCALE)
                        txt_col = (180, 175, 160)
                    else:
                        dir_x = (m.x - player.x) / max(0.01, dist_to_p)
                        dir_y = (m.y - player.y) / max(0.01, dist_to_p)
                        rim_d = min(dist_to_p, 3.2)
                        bsx = int(((player.x + dir_x * rim_d) * TILE_W - cam_x) * SCALE)
                        bsy = int(((player.y + dir_y * rim_d - 0.6) * TILE_H - cam_y) * SCALE)
                        txt_col = (165, 160, 150)

                    lines = self.wrap_text(m.current_speech, self.font_small, 250)
                    rendered = [self.font_small.render(ln, True, txt_col) for ln in lines]
                    bw = max(s.get_width() for s in rendered) + 14
                    bh = len(rendered) * 16 + 8
                    bx = max(8, min(SCREEN_W - bw - 8, bsx - bw // 2))
                    by = max(6, min(VIEW_H * SCALE - bh - 6, bsy - bh - 12))
                    pygame.draw.rect(screen, (20, 18, 26), (bx, by, bw, bh), border_radius=4)
                    pygame.draw.rect(screen, UI_BORDER_WOOD, (bx, by, bw, bh), 1, border_radius=4)
                    for li, r_surf in enumerate(rendered):
                        screen.blit(r_surf, (bx + (bw - r_surf.get_width()) // 2, by + 4 + li * 16))

        # Active Player Buff Visuals: Persephone Rejuvenation Fireflies & Pyro Ignite Flames!
        p_sx_scr = int((player.x * TILE_W - cam_x) * SCALE)
        p_sy_scr = int(((player.y - 0.35) * TILE_H - cam_y) * SCALE)
        p_foot_scr = int(((player.y + 0.05) * TILE_H - cam_y) * SCALE)
        if getattr(player, "rejuv_timer", 0.0) > 0.0:
            pygame.draw.ellipse(screen, (45, 165, 85), (p_sx_scr - 24, p_foot_scr - 8, 48, 16), 2)
            for ff_i in range(5):
                ang = now_sec * 3.4 + ff_i * (math.tau / 5.0)
                fx_s = p_sx_scr + int(math.cos(ang) * 23)
                fy_s = p_sy_scr + int(math.sin(ang * 1.5) * 14)
                pygame.draw.circle(screen, (55, 195, 95), (fx_s, fy_s), 6)
                pygame.draw.circle(screen, (115, 250, 145), (fx_s, fy_s), 4)
                pygame.draw.circle(screen, (235, 255, 235), (fx_s, fy_s), 2)
                # Восходящие изумрудные крестики исцеления
                rise = (now_sec * 1.8 + ff_i * 0.37) % 1.0
                cx_h = p_sx_scr + int(math.sin(ff_i * 2.1 + now_sec * 2.0) * 16)
                cy_h = int(p_foot_scr - 4 - rise * 38)
                pygame.draw.line(screen, (150, 255, 175), (cx_h - 3, cy_h), (cx_h + 3, cy_h), 2)
                pygame.draw.line(screen, (150, 255, 175), (cx_h, cy_h - 3), (cx_h, cy_h + 3), 2)
        if getattr(player, "ignite_timer", 0.0) > 0.0:
            pygame.draw.ellipse(screen, (215, 65, 20), (p_sx_scr - 24, p_foot_scr - 8, 48, 16), 3)
            pygame.draw.ellipse(screen, (255, 195, 70), (p_sx_scr - 20, p_foot_scr - 6, 40, 12), 1)
            for fl_i in range(6):
                ang = now_sec * 5.0 + fl_i * (math.tau / 6.0)
                fx_s = p_sx_scr + int(math.cos(ang) * 20)
                fy_s = p_sy_scr + 8 + int(math.sin(ang) * 10)
                h_fl = 10 + int(math.sin(now_sec * 14.0 + fl_i * 1.7) * 4)
                pygame.draw.polygon(screen, (220, 55, 20), [(fx_s - 5, fy_s), (fx_s, fy_s - h_fl - 4), (fx_s + 5, fy_s)])
                pygame.draw.polygon(screen, (255, 145, 35), [(fx_s - 3, fy_s), (fx_s, fy_s - h_fl), (fx_s + 3, fy_s)])
                pygame.draw.polygon(screen, (255, 240, 125), [(fx_s - 2, fy_s), (fx_s, fy_s - h_fl // 2), (fx_s + 2, fy_s)])

        for p in popups:
            sx = int((p.wx * TILE_W - cam_x) * SCALE)
            sy = int((p.wy * TILE_H - cam_y) * SCALE)
            if 0 <= sy < VIEW_H * SCALE:
                f_use = self.font_popup_big if getattr(p, "big", False) else self.font_popup
                txt_surf = f_use.render(p.text, True, p.color)
                sh_surf = f_use.render(p.text, True, (10, 8, 14))
                screen.blit(sh_surf, (sx - txt_surf.get_width() // 2 + 2, sy + 2))
                screen.blit(txt_surf, (sx - txt_surf.get_width() // 2, sy))

        # Render NPC Quest Marker & Speech Bubble (Innkeeper Hugo & Dungeon Merchant)
        for obj in objects:
            if not obj.used and obj.kind in ("npc_innkeeper", "npc_merchant") and (obj.x, obj.y) in visible_tiles:
                sx = int(((obj.x + 0.5) * TILE_W - cam_x) * SCALE)
                sy = int(((obj.y - 0.35) * TILE_H - cam_y) * SCALE)
                if getattr(obj, "speech_text", None):
                    lines = self.wrap_text(obj.speech_text, self.font_small, 260)
                    rendered = [self.font_small.render(ln, True, (255, 235, 175)) for ln in lines]
                    bw = max(s.get_width() for s in rendered) + 14
                    bh = len(rendered) * 16 + 8
                    bx = max(8, min(SCREEN_W - bw - 8, sx - bw // 2))
                    by = max(6, sy - bh - 10)
                    pygame.draw.rect(screen, (24, 20, 16), (bx, by, bw, bh), border_radius=4)
                    pygame.draw.rect(screen, UI_BORDER_GOLD, (bx, by, bw, bh), 1, border_radius=4)
                    for li, r_surf in enumerate(rendered):
                        screen.blit(r_surf, (bx + (bw - r_surf.get_width()) // 2, by + 4 + li * 16))
                else:
                    tag_str = "[?] Гуго" if obj.kind == "npc_innkeeper" else "[$] Скупщик"
                    tag_col = (255, 220, 75) if obj.kind == "npc_innkeeper" else (125, 245, 155)
                    q_lbl = self.font_ui.render(tag_str, True, tag_col)
                    screen.blit(q_lbl, (sx - q_lbl.get_width() // 2, sy - 20))

        # Render Cursor AoE target circle during windup
        if getattr(player, "pending_action", None):
            pa = player.pending_action
            if pa.get("kind") == "spell" and pa["item"].cast_type in ("aoe_cursor", "entangle_cursor"):
                cx_s = int((pa["tx"] * TILE_W - cam_x) * SCALE)
                cy_s = int((pa["ty"] * TILE_H - cam_y) * SCALE)
                r_px = int(pa["item"].aoe_radius * TILE_W * SCALE)
                pygame.draw.circle(screen, pa["item"].color, (cx_s, cy_s), r_px, 2)


        # Render Combat Skill & God Spell Visual FX
        for vfx in ui_texts.get("_visual_fx", []):
            prog = 1.0 - (vfx["timer"] / max(0.001, vfx["max_timer"]))

            if vfx["kind"] == "mana_shard":
                if (int(vfx["x"]), int(vfx["y"])) not in visible_tiles:
                    continue
                # Быстрое мигание в последние 1.2 секунды перед исчезновением осколка
                if vfx["timer"] < 1.2 and int(now_sec * 14.0) % 2 == 0:
                    continue
                cx_s = int((vfx["x"] * TILE_W - cam_x) * SCALE)
                bob = int(math.sin(now_sec * 6.5 + vfx["x"] * 3.0) * 4)
                cy_s = int((vfx["y"] * TILE_H - cam_y) * SCALE) - 6 + bob
                if 0 <= cy_s < VIEW_H * SCALE:
                    diamond_outer = [(cx_s, cy_s - 9), (cx_s + 6, cy_s), (cx_s, cy_s + 9), (cx_s - 6, cy_s)]
                    diamond_inner = [(cx_s, cy_s - 5), (cx_s + 3, cy_s), (cx_s, cy_s + 5), (cx_s - 3, cy_s)]
                    pygame.draw.polygon(screen, (45, 165, 245), diamond_outer)
                    pygame.draw.polygon(screen, (215, 250, 255), diamond_inner)
                    pygame.draw.polygon(screen, (15, 45, 85), diamond_outer, 1)

            elif vfx["kind"] == "fire_trail":
                cx_s = int((vfx["x"] * TILE_W - cam_x) * SCALE)
                cy_s = int((vfx["y"] * TILE_H - cam_y) * SCALE)
                if 0 <= cy_s < VIEW_H * SCALE:
                    fade = max(0.2, 1.0 - prog)
                    pygame.draw.ellipse(screen, (95, 25, 15), (cx_s - 15, cy_s - 6, 30, 14))
                    pygame.draw.ellipse(screen, (185, 55, 20), (cx_s - 11, cy_s - 4, 22, 10), 2)
                    seed_v = int((vfx["x"] * 37 + vfx["y"] * 73) * 10)
                    for f_i in range(5):
                        ox = ((seed_v + f_i * 11) % 21) - 10
                        oy = ((seed_v + f_i * 7) % 11) - 5
                        flick = int(math.sin(now_sec * 16.0 + f_i * 2.1 + vfx["x"] * 5.0) * 4 * fade)
                        fx_p = cx_s + ox
                        fy_p = cy_s + oy
                        h_flame = max(4, int(11 * fade) + flick)
                        pygame.draw.polygon(screen, (205, 50, 20), [(fx_p - 4, fy_p + 2), (fx_p, fy_p - h_flame - 3), (fx_p + 4, fy_p + 2)])
                        pygame.draw.polygon(screen, (255, 140, 30), [(fx_p - 3, fy_p + 1), (fx_p, fy_p - h_flame), (fx_p + 3, fy_p + 1)])
                        pygame.draw.polygon(screen, (255, 240, 115), [(fx_p - 2, fy_p + 1), (fx_p, fy_p - max(2, h_flame // 2)), (fx_p + 2, fy_p + 1)])

            elif vfx["kind"] == "frost_nova":
                cx_s = int((vfx["x"] * TILE_W - cam_x) * SCALE)
                cy_s = int((vfx["y"] * TILE_H - cam_y) * SCALE)
                r_px = max(8, int(vfx["radius"] * TILE_W * SCALE * (0.20 + prog * 0.80)))
                # Зубчатая корона из 12 ледяных пик по внешнему фронту
                star_pts = []
                for i_pt in range(24):
                    a_pt = i_pt * (math.tau / 24.0) + prog * 0.25
                    rad_pt = r_px * (1.06 if i_pt % 2 == 0 else 0.82)
                    star_pts.append((int(cx_s + math.cos(a_pt) * rad_pt), int(cy_s + math.sin(a_pt) * rad_pt)))
                pygame.draw.polygon(screen, (45, 140, 215), star_pts, 5)
                pygame.draw.polygon(screen, (115, 220, 255), star_pts, 3)
                pygame.draw.circle(screen, (225, 250, 255), (cx_s, cy_s), max(4, int(r_px * 0.72)), 2)
                for sp_i in range(6):
                    a = sp_i * (math.pi / 3.0)
                    p1 = (int(cx_s + math.cos(a) * (r_px * 0.25)), int(cy_s + math.sin(a) * (r_px * 0.25)))
                    p2 = (int(cx_s + math.cos(a) * (r_px * 1.08)), int(cy_s + math.sin(a) * (r_px * 1.08)))
                    pygame.draw.line(screen, (215, 248, 255), p1, p2, 3)

            elif vfx["kind"] == "chain_lightning":
                pts = vfx["points"]
                for i in range(len(pts) - 1):
                    x0_s = int((pts[i][0] * TILE_W - cam_x) * SCALE)
                    y0_s = int((pts[i][1] * TILE_H - cam_y) * SCALE)
                    x1_s = int((pts[i + 1][0] * TILE_W - cam_x) * SCALE)
                    y1_s = int((pts[i + 1][1] * TILE_H - cam_y) * SCALE)
                    zig = [(x0_s, y0_s)]
                    for seg in range(1, 6):
                        frac = seg / 6.0
                        jx = int(x0_s + (x1_s - x0_s) * frac + math.sin(now_sec * 48.0 + seg * 3.1 + i) * 10)
                        jy = int(y0_s + (y1_s - y0_s) * frac + math.cos(now_sec * 42.0 + seg * 4.7 + i) * 10)
                        zig.append((jx, jy))
                        # Боковое ответвление молнии из середины дуги
                        if seg in (2, 4):
                            bx = jx + int(math.cos(now_sec * 30.0 + seg + i) * 18)
                            by = jy + int(math.sin(now_sec * 30.0 + seg + i) * 18)
                            pygame.draw.line(screen, (75, 195, 255), (jx, jy), (bx, by), 3)
                            pygame.draw.line(screen, (235, 255, 255), (jx, jy), (bx, by), 1)
                    zig.append((x1_s, y1_s))
                    pygame.draw.lines(screen, (40, 125, 220), False, zig, 9)
                    pygame.draw.lines(screen, (105, 215, 255), False, zig, 5)
                    pygame.draw.lines(screen, (245, 255, 255), False, zig, 2)
                    # Электрическая звезда в узле попадания
                    pygame.draw.circle(screen, (95, 215, 255), (x1_s, y1_s), 12, 2)
                    pygame.draw.circle(screen, (245, 255, 255), (x1_s, y1_s), 6)

            elif vfx["kind"] == "entangle_zone":
                cx_s = int((vfx["x"] * TILE_W - cam_x) * SCALE)
                cy_s = int((vfx["y"] * TILE_H - cam_y) * SCALE)
                r_px = max(6, int(vfx["radius"] * TILE_W * SCALE))
                pygame.draw.circle(screen, (45, 95, 45), (cx_s, cy_s), r_px, 4)
                pygame.draw.circle(screen, (105, 225, 115), (cx_s, cy_s), max(4, r_px - 6), 2)
                grow = 1.0 - abs(prog - 0.45) * 1.4
                for v_i in range(9):
                    ang = v_i * (math.tau / 9.0)
                    rad_v = r_px * (0.35 if v_i % 2 == 0 else 0.72)
                    vx_b = cx_s + int(math.cos(ang) * rad_v)
                    vy_b = cy_s + int(math.sin(ang) * rad_v)
                    h_vine = max(6, int(32 * grow))
                    sway = int(math.sin(now_sec * 9.0 + v_i) * 6)
                    v_pts = [
                        (vx_b, vy_b),
                        (vx_b + sway, vy_b - h_vine // 2),
                        (vx_b - sway // 2, vy_b - h_vine),
                    ]
                    pygame.draw.lines(screen, (65, 42, 24), False, v_pts, 5)
                    pygame.draw.lines(screen, (85, 185, 75), False, v_pts, 2)
                    # Листок на верхушке лозы
                    tx_v, ty_v = v_pts[-1]
                    pygame.draw.polygon(screen, (145, 245, 130), [(tx_v, ty_v - 4), (tx_v + 4, ty_v), (tx_v, ty_v + 3), (tx_v - 4, ty_v)])

            elif vfx["kind"] == "beam":
                x1_s = int((vfx["x0"] * TILE_W - cam_x) * SCALE)
                y1_s = int((vfx["y0"] * TILE_H - cam_y) * SCALE)
                x2_s = int((vfx["x1"] * TILE_W - cam_x) * SCALE)
                y2_s = int((vfx["y1"] * TILE_H - cam_y) * SCALE)
                c_r, c_g, c_b = vfx["color"]
                fade = max(0.2, 1.0 - prog)
                outer_w = max(4, int(20 * fade))
                mid_w = max(2, int(11 * fade))
                core_w = max(1, int(4 * fade))
                pygame.draw.line(screen, (c_r // 2, c_g // 2, c_b // 2), (x1_s, y1_s), (x2_s, y2_s), outer_w)
                pygame.draw.line(screen, (c_r, c_g, c_b), (x1_s, y1_s), (x2_s, y2_s), mid_w)
                pygame.draw.line(screen, (255, 255, 240), (x1_s, y1_s), (x2_s, y2_s), core_w)
                pygame.draw.circle(screen, (c_r, c_g, c_b), (x1_s, y1_s), int(12 * fade))
                pygame.draw.circle(screen, (255, 255, 240), (x1_s, y1_s), int(6 * fade))
                pygame.draw.circle(screen, (c_r, c_g, c_b), (x2_s, y2_s), int(15 * fade))
                pygame.draw.circle(screen, (255, 255, 240), (x2_s, y2_s), int(7 * fade))

            elif vfx["kind"] == "whirlwind_slash":
                cx_s = int((player.x * TILE_W - cam_x) * SCALE)
                cy_s = int(((player.y - 0.22) * TILE_H - cam_y) * SCALE)
                rad_px = int(vfx["radius"] * TILE_W * SCALE)
                head_ang = prog * math.pi * 2.4
                pts_outer = []
                pts_core = []
                for step_i in range(18):
                    a = head_ang - step_i * 0.16
                    r_cur = rad_px * (1.0 - step_i * 0.015)
                    pts_outer.append((int(cx_s + math.cos(a) * r_cur), int(cy_s + math.sin(a) * r_cur)))
                    if step_i < 10:
                        pts_core.append((int(cx_s + math.cos(a) * r_cur), int(cy_s + math.sin(a) * r_cur)))
                if len(pts_outer) >= 2:
                    pygame.draw.lines(screen, vfx["color"], False, pts_outer, 10)
                if len(pts_core) >= 2:
                    pygame.draw.lines(screen, (255, 250, 235), False, pts_core, 4)

            elif vfx["kind"] == "slam_wave":
                cx_s = int((vfx["x"] * TILE_W - cam_x) * SCALE)
                cy_s = int((vfx["y"] * TILE_H - cam_y) * SCALE)
                base_a = vfx["angle"]
                cur_r = int((0.5 + prog * 1.9) * TILE_W * SCALE)
                arc_pts = []
                for step_i in range(13):
                    frac = (step_i / 12.0) * 2.0 - 1.0
                    a = base_a + frac * 0.85
                    arc_pts.append((int(cx_s + math.cos(a) * cur_r), int(cy_s + math.sin(a) * cur_r)))
                if len(arc_pts) >= 2:
                    pygame.draw.lines(screen, vfx["color"], False, arc_pts, 8)
                    pygame.draw.lines(screen, (255, 235, 180), False, arc_pts, 3)
                for ray_off in (-0.55, 0.0, 0.55):
                    ra = base_a + ray_off
                    ex = int(cx_s + math.cos(ra) * cur_r)
                    ey = int(cy_s + math.sin(ra) * cur_r)
                    pygame.draw.line(screen, vfx["color"], (cx_s, cy_s), (ex, ey), 3)

            elif vfx["kind"] == "aoe_ring":
                cx_s = int((vfx["x"] * TILE_W - cam_x) * SCALE)
                cy_s = int((vfx["y"] * TILE_H - cam_y) * SCALE)
                r_px = int(vfx["radius"] * TILE_W * SCALE * (0.7 + prog * 0.3))
                pygame.draw.circle(screen, vfx["color"], (cx_s, cy_s), max(4, r_px), 3)

            elif vfx["kind"] == "blood_pentagram":
                cx_s = int((vfx["x"] * TILE_W - cam_x) * SCALE)
                cy_s = int((vfx["y"] * TILE_H - cam_y) * SCALE)
                r_px = int(vfx["radius"] * TILE_W * SCALE)
                pulse_col = (255, int(40 + 175 * prog), int(55 + 90 * prog))
                dark_col = (145, 18, 32)
                pygame.draw.circle(screen, dark_col, (cx_s, cy_s), r_px + 3, 4)
                pygame.draw.circle(screen, pulse_col, (cx_s, cy_s), r_px, 2)
                pygame.draw.circle(screen, pulse_col, (cx_s, cy_s), int(r_px * max(0.15, prog)), 1)
                rot = -math.pi * 0.5 + prog * 0.35
                verts = [
                    (int(cx_s + math.cos(rot + i * 2.0 * math.pi / 5.0) * r_px),
                     int(cy_s + math.sin(rot + i * 2.0 * math.pi / 5.0) * r_px))
                    for i in range(5)
                ]
                star_order = [verts[0], verts[2], verts[4], verts[1], verts[3], verts[0]]
                pygame.draw.lines(screen, pulse_col, False, star_order, 3 if prog > 0.6 else 2)
                for vx_p, vy_p in verts:
                    pygame.draw.circle(screen, (255, 220, 120), (vx_p, vy_p), 3)

        # Typewriter Text in Dedicated Thought Box (адаптивно центрируется под SCALE = 4)
        if shown_thought:
            box_max_w = THOUGHT_BOX_W * SCALE - 68
            lines = self.wrap_text(shown_thought, self.font_thought, box_max_w)[:2]
            start_x = THOUGHT_BOX_X * SCALE + 34
            box_px_h = THOUGHT_BOX_H * SCALE
            line_step = 26
            total_txt_h = len(lines) * line_step
            start_y = THOUGHT_BOX_Y * SCALE + (box_px_h - total_txt_h) // 2 + 2
            for idx, ln in enumerate(lines):
                t_sh = self.font_thought.render(ln, True, (10, 8, 12))
                t_fg = self.font_thought.render(ln, True, UI_TEXT_MAIN)
                ly = start_y + idx * line_step
                screen.blit(t_sh, (start_x + 2, ly + 2))
                screen.blit(t_fg, (start_x, ly))

        # Bottom HUD Bar + Golden XP Bar
        hud_y = CANVAS_H * SCALE
        self.draw_pixel_frame(screen, (0, hud_y, SCREEN_W, HUD_HEIGHT), UI_BG_DARK, UI_BORDER_WOOD, False, player.illumination)

        xp_bar_x, xp_bar_y, xp_bar_w, xp_bar_h = 16, hud_y + 7, SCREEN_W - 32, 10
        pygame.draw.rect(screen, (14, 12, 18), (xp_bar_x, xp_bar_y, xp_bar_w, xp_bar_h))
        xp_ratio = min(1.0, player.xp / max(1, player.max_xp))
        if xp_ratio > 0:
            pygame.draw.rect(screen, (235, 185, 55), (xp_bar_x + 1, xp_bar_y + 1, int((xp_bar_w - 2) * xp_ratio), xp_bar_h - 2))
        pygame.draw.rect(screen, UI_BORDER_GOLD, (xp_bar_x, xp_bar_y, xp_bar_w, xp_bar_h), 1)

        # 1. Left of HP/MP Bars: Player Portrait Icon + Level Number Badge (No text labels!)
        port_rect = pygame.Rect(16, hud_y + 22, 58, 58)
        self.draw_pixel_frame(screen, port_rect, UI_SLOT_BG, UI_BORDER_GOLD, False, player.illumination)
        h_diff, _ = self.get_hero_pair(player)
        port_img = pygame.transform.scale(h_diff, (32, 40))
        screen.blit(port_img, (port_rect.x + 13, port_rect.y + 8))
        # Level badge on bottom-right corner of portrait
        lvl_s = self.font_small.render(str(player.level), True, (255, 225, 90))
        pygame.draw.rect(screen, (18, 15, 24), (port_rect.right - lvl_s.get_width() - 8, port_rect.bottom - 18, lvl_s.get_width() + 6, 16))
        pygame.draw.rect(screen, UI_BORDER_GOLD, (port_rect.right - lvl_s.get_width() - 8, port_rect.bottom - 18, lvl_s.get_width() + 6, 16), 1)
        screen.blit(lvl_s, (port_rect.right - lvl_s.get_width() - 5, port_rect.bottom - 17))

        # 2. Label-free HP & Mana Bars
        self._draw_pixel_bar(screen, 80, hud_y + 22, 176, 26, int(player.hp), player.max_hp, (185, 42, 52))
        self._draw_pixel_bar(screen, 80, hud_y + 54, 176, 26, int(player.mp), player.max_mp, (48, 125, 210))

        # 3. Compact Torch & D&D Currency Indicator
        from elenor.data.economy import format_copper_Trigger
        self.draw_pixel_frame(screen, (262, hud_y + 22, 88, 58), UI_SLOT_BG, UI_BORDER_WOOD, False, player.illumination)
        torch = player.get_active_torch()
        t_str = "[T] ВКЛ" if (torch and player.torch_on) else "[T] ТЕНЬ"
        t_col = (255, 200, 75) if (torch and player.torch_on) else (130, 175, 235)
        screen.blit(self.font_small.render(t_str, True, t_col), (270, hud_y + 29))
        coin_s = self.font_small.render(format_copper_Trigger(player.gold, compact=True), True, (255, 215, 80))
        screen.blit(coin_s, (262 + (88 - coin_s.get_width()) // 2, hud_y + 51))

        # 4A. Active Ability Slots [Q] and [E] (с серо-синим фильтром Warcraft 3 при нехватке маны!)
        hovered_hud_item = None
        key_labels = ("Q", "E", "R", "F")
        for i, rect in enumerate(self.ability_rects):
            is_hov = rect.collidepoint(hover_pos)
            item = player.ability_slots[i]
            is_oom = bool(item and item.type in ("spell", "permanent_spell") and player.mp < item.mp_cost)
            bd_col = (58, 78, 118) if is_oom else (item.rarity_color if item else (65, 105, 145))
            self.draw_pixel_frame(screen, rect, UI_SLOT_BG, bd_col, is_hov, player.illumination)
            if item:
                if is_oom:
                    ic_tmp = pygame.Surface((32, 32), pygame.SRCALPHA)
                    self.draw_item_icon(ic_tmp, item.icon, 0, 0, 32)
                    for py_i in range(32):
                        for px_i in range(32):
                            ir, ig, ib, ia = ic_tmp.get_at((px_i, py_i))
                            if ia > 10:
                                lum = int(0.299 * ir + 0.587 * ig + 0.114 * ib)
                                ic_tmp.set_at((px_i, py_i), (min(255, lum // 3 + 32), min(255, lum // 3 + 52), min(255, lum // 2 + 95), ia))
                    screen.blit(ic_tmp, (rect.x + 11, rect.y + 12))
                    oom_ov = pygame.Surface((rect.width - 14, rect.height - 14), pygame.SRCALPHA)
                    oom_ov.fill((22, 36, 68, 95))
                    screen.blit(oom_ov, (rect.x + 7, rect.y + 7))
                else:
                    self.draw_item_icon(screen, item.icon, rect.x + 11, rect.y + 12, 32)

                cd_left = player.cooldowns.get(item.id, 0.0)
                if cd_left > 0.0:
                    cd_ov = pygame.Surface((rect.width - 14, rect.height - 14), pygame.SRCALPHA)
                    cd_ov.fill((10, 8, 16, 175))
                    screen.blit(cd_ov, (rect.x + 7, rect.y + 7))
                    cd_s = self.font_small.render(f"{cd_left:.1f}с", True, (255, 195, 90))
                    screen.blit(cd_s, (rect.centerx - cd_s.get_width() // 2, rect.centery - 6))
                if is_hov:
                    hovered_hud_item = item
            screen.blit(self.font_small.render(key_labels[i], True, (110, 145, 195) if is_oom else (135, 215, 255)), (rect.x + 6, rect.y + 5))

        # 4B. 4 Consumable Slots [1..4]
        for i, rect in enumerate(self.hotbar_rects):
            is_hov = rect.collidepoint(hover_pos)
            item = player.hotbar[i]
            bd_col = item.rarity_color if item else UI_BORDER_WOOD
            self.draw_pixel_frame(screen, rect, UI_SLOT_BG, bd_col, is_hov, player.illumination)
            if item:
                self.draw_item_icon(screen, item.icon, rect.x + 10, rect.y + 12, 32)
                cd_left = player.cooldowns.get(item.id, 0.0)
                if cd_left > 0.0:
                    cd_ov = pygame.Surface((rect.width - 14, rect.height - 14), pygame.SRCALPHA)
                    cd_ov.fill((10, 8, 16, 175))
                    screen.blit(cd_ov, (rect.x + 7, rect.y + 7))
                    cd_s = self.font_small.render(f"{cd_left:.1f}с", True, (255, 195, 90))
                    screen.blit(cd_s, (rect.centerx - cd_s.get_width() // 2, rect.centery - 6))
                if is_hov:
                    hovered_hud_item = item
            screen.blit(self.font_small.render(str(i + 1), True, UI_BORDER_HIGHLIGHT), (rect.x + 6, rect.y + 5))

        # 5. 5 Passive Perk Slots with Hover Tooltip!
        from elenor.config import RARITY_COLORS
        perks_db = ui_texts.get("_perks_db", {})
        owned_passives = list(player.passive_perks.items())
        hovered_passive = None
        for p_idx, pr in enumerate(self.passive_slot_rects):
            if p_idx < len(owned_passives):
                pid, plvl = owned_passives[p_idx]
                pdata = perks_db.get(pid, {})
                p_col = RARITY_COLORS.get(pdata.get("rarity", "common"), UI_BORDER_GOLD)
                is_p_hov = pr.collidepoint(hover_pos)
                self.draw_pixel_frame(screen, pr, UI_SLOT_BG, p_col, is_p_hov, player.illumination)
                self.draw_item_icon(screen, pdata.get("icon", "trinket"), pr.x + 8, pr.y + 8, 32)
                lv_txt = self.font_small.render(str(plvl), True, (255, 235, 110))
                pygame.draw.rect(screen, (14, 12, 18), (pr.right - lv_txt.get_width() - 6, pr.bottom - 16, lv_txt.get_width() + 4, 14))
                screen.blit(lv_txt, (pr.right - lv_txt.get_width() - 4, pr.bottom - 16))
                if is_p_hov:
                    hovered_passive = (pid, plvl, pdata)
            else:
                self.draw_pixel_frame(screen, pr, (18, 15, 22), (65, 52, 48), False, player.illumination)

        # 6. Far Right: Inventory Button [I] + Occupied/Unlocked Slots Counter
        bag_hov = self.bag_btn_rect.collidepoint(hover_pos) or inv_open
        self.draw_pixel_frame(screen, self.bag_btn_rect, (52, 40, 36) if bag_hov else UI_PANEL_BG, UI_BORDER_GOLD, bag_hov, player.illumination)
        self.draw_item_icon(screen, "bag_small", self.bag_btn_rect.x + 8, self.bag_btn_rect.y + 10, 32)
        used_slots = sum(1 for i in range(player.unlocked_slots) if player.inventory[i] is not None)
        slot_col = (255, 110, 95) if used_slots >= player.unlocked_slots else (255, 220, 95)
        screen.blit(self.font_ui.render(ui_texts["bag_btn"], True, UI_TEXT_MAIN), (self.bag_btn_rect.x + 42, self.bag_btn_rect.y + 10))
        cnt_surf = self.font_small.render(f"Яч: {used_slots}/{player.unlocked_slots}", True, slot_col)
        screen.blit(cnt_surf, (self.bag_btn_rect.x + 42, self.bag_btn_rect.y + 29))

        world_hover_item = ui_texts.get("_world_hover_item")
        if levelup_choices:
            self._render_levelup_modal(screen, player, levelup_choices, ui_texts, hover_pos)
        elif inv_open:
            self._render_character_sheet_modal(screen, player, ui_texts, hover_pos, drag_item)
        elif hovered_hud_item:
            self._render_item_tooltip(screen, player, hovered_hud_item, ui_texts, hover_pos, compare=False)
        elif hovered_passive:
            self._render_passive_perk_tooltip(screen, player, hovered_passive, ui_texts, hover_pos)
        elif world_hover_item:
            self._render_item_tooltip(screen, player, world_hover_item, ui_texts, hover_pos, compare=True, world_item=True)

