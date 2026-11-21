import random
import pygame
from elenor.config import SCREEN_W, SCREEN_H, UI_PANEL_BG, UI_SLOT_BG, UI_BORDER_WOOD, UI_BORDER_GOLD, UI_BORDER_HIGHLIGHT, UI_TEXT_MAIN, UI_TEXT_DIM, COIN_TEXT_COLOR
from elenor.rendering.normals import LiveLightPreview


from elenor.profile import DEFAULT_PROFILE, get_profile_dir, save_profile, reset_profile_progress, get_available_resolutions, get_desktop_size, resolution_index, WINDOW_MODES_LIST
from elenor.data.economy import format_copper_Trigger
from elenor.rendering.appearance import HERO_TYPES_ORDER, HERO_CUSTOMIZATION_DB, build_custom_hero_sprite
from elenor.ui.clipboard import paste_text
from elenor.world.run_seed import parse_run_seed

STRONGBOX_COSTS = (20000, 30000, 45000, 67500, 101250)

class MainMenuController:
    def __init__(self, game):
        self.game = game
        self.active_tab = 0
        self.upgrade_subtab = 0
        self.inspect_painting_id = None
        self.viewer_btn_rects = {}
        self.viewer_modal_rect = None
        self.scroll_x = 0.0
        self.preview_3d = LiveLightPreview(280, 320)
        self.preview_walk = False
        self.preview_cloak_color = [200, 70, 75]
        self.anim_timer = 0.0
        self.anim_frame = 0
        self.meltdown_timer = 0.0
        self.meltdown_active = False
        self.confirm_reset_timer = 0.0
        self.open_dropdown = None
        self.pending_display = None
        self.dropdown_item_rects = []
        self.can_resume = False
        self.seed_text = ""
        self.seed_focused = False
        self.seed_selected = False
        self.seed_error = False

        # Левый сайдбар и резиновая правая область, адаптивная под любой SCREEN_W / SCREEN_H
        self.sidebar_w = 300
        self.right_x = 32 + self.sidebar_w + 24
        self.panel_w = SCREEN_W - self.right_x - 32
        self.panel_stride = self.panel_w + 32

        self.nav_rects = [pygame.Rect(52, 220 + i * 86, self.sidebar_w - 40, 64) for i in range(4)]
        self.btn_rects = {}

    def sync_audio_and_display(self):
        prof = self.game.profile
        if hasattr(self.game, "sfx") and self.game.sfx:
            self.game.sfx.set_volume(prof.get("volume", 0.85))

    def handle_event(self, event, mouse_pos):
        prof = self.game.profile

        if self.seed_focused:
            if event.type == pygame.TEXTINPUT:
                self._edit_seed(event.text)
                return True
            if event.type == pygame.KEYDOWN:
                mods = getattr(event, "mod", 0)
                if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
                    self._focus_seed(False)
                elif mods & (pygame.KMOD_CTRL | pygame.KMOD_GUI):
                    if event.key == pygame.K_a:
                        self.seed_selected = True
                    elif event.key == pygame.K_v:
                        text = paste_text()
                        if text:
                            self._edit_seed(text.strip())
                elif event.key in (pygame.K_BACKSPACE, pygame.K_DELETE):
                    if self.seed_selected or event.key == pygame.K_DELETE:
                        self.seed_text = ""
                    else:
                        self.seed_text = self.seed_text[:-1]
                    self.seed_selected = self.seed_error = False
                return True
            
        if self.inspect_painting_id is not None:
            if event.type == pygame.MOUSEWHEEL:
                self._step_painting_viewer(-1 if event.y > 0 else 1, prof)
                return True
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.inspect_painting_id = None
                    self.game.sfx.play("ui")
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    self._step_painting_viewer(-1, prof)
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    self._step_painting_viewer(1, prof)
                return True
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = getattr(event, "pos", mouse_pos)
                for v_key, v_rect in self.viewer_btn_rects.items():
                    if v_rect.collidepoint(pos):
                        if v_key == "prev":
                            self._step_painting_viewer(-1, prof)
                        elif v_key == "next":
                            self._step_painting_viewer(1, prof)
                        elif v_key == "close":
                            self.inspect_painting_id = None
                            self.game.sfx.play("ui")
                        return True
                if self.viewer_modal_rect is None or not self.viewer_modal_rect.collidepoint(pos):
                    self.inspect_painting_id = None
                    self.game.sfx.play("ui")
                return True
            return True

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.open_dropdown is not None:
                    self.open_dropdown = None
                    return True
                if self.meltdown_active:
                    self.meltdown_active = False
                    self.active_tab = 0
                    return True
                if self.can_resume:
                    self._trigger_button("resume_run", prof)
                    return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._focus_seed(False)
            if self.open_dropdown is not None:
                for opt_val, opt_rect in self.dropdown_item_rects:
                    if opt_rect.collidepoint(mouse_pos):
                        self.game.sfx.play("ui")
                        setting = "window_mode" if self.open_dropdown == "win_mode" else "resolution_idx"
                        self.pending_display = setting, opt_val
                        self.open_dropdown = None
                        return True
                self.open_dropdown = None
                self.game.sfx.play("ui")
                return True

            for i, nr in enumerate(self.nav_rects):
                if nr.collidepoint(mouse_pos):
                    self.active_tab = i
                    self.open_dropdown = None
                    self.game.sfx.play("ui")
                    if i == 3:
                        self.meltdown_active = True
                        self.meltdown_timer = 0.0
                        self.game.sfx.play("cpu_meltdown")
                    else:
                        self.meltdown_active = False
                    return True

            if abs(self.scroll_x - self.active_tab * self.panel_stride) > 160.0:
                return True

            for b_key, b_rect in self.btn_rects.items():
                if b_rect.collidepoint(mouse_pos):
                    self._trigger_button(b_key, prof)
                    return True

        return False

    def _focus_seed(self, focused):
        if self.seed_focused == focused:
            return
        self.seed_focused = focused
        self.seed_selected = False
        if focused:
            pygame.key.start_text_input()
        else:
            pygame.key.stop_text_input()

    def _edit_seed(self, text):
        previous = "" if self.seed_selected else self.seed_text
        self.seed_text = (previous + text)[:32]
        self.seed_selected = self.seed_error = False

    def _trigger_button(self, b_key, prof):
        self.game.sfx.play("ui")
        h_type = prof.get("hero_type", "male")

        if b_key == "type_prev":
            idx = (HERO_TYPES_ORDER.index(h_type) - 1) % len(HERO_TYPES_ORDER)
            new_t = HERO_TYPES_ORDER[idx]
            if new_t == "ratfolk" and not prof.get("rat_king_defeated", False):
                self.game.sfx.play("hurt")
                return
            prof["hero_type"] = new_t
            prof["skin_idx"] = 0
            prof["head_idx"] = 0
            save_profile(prof)

        elif b_key == "type_next":
            idx = (HERO_TYPES_ORDER.index(h_type) + 1) % len(HERO_TYPES_ORDER)
            new_t = HERO_TYPES_ORDER[idx]
            if new_t == "ratfolk" and not prof.get("rat_king_defeated", False):
                self.game.sfx.play("hurt")
                return
            prof["hero_type"] = new_t
            prof["skin_idx"] = 0
            prof["head_idx"] = 0
            save_profile(prof)

        elif b_key == "unlock_ratfolk_dev":
            prof["rat_king_defeated"] = True
            prof["hero_type"] = "ratfolk"
            save_profile(prof)
            self.game.sfx.play("levelup")

        elif b_key in ("skin_prev", "skin_next"):
            skins = HERO_CUSTOMIZATION_DB[h_type]["skins"]
            step = -1 if b_key.endswith("prev") else 1
            prof["skin_idx"] = (prof.get("skin_idx", 0) + step) % len(skins)
            save_profile(prof)

        elif b_key in ("head_prev", "head_next"):
            heads = HERO_CUSTOMIZATION_DB[h_type]["heads"]
            step = -1 if b_key.endswith("prev") else 1
            prof["head_idx"] = (prof.get("head_idx", 0) + step) % len(heads)
            save_profile(prof)

        elif b_key in ("outfit_prev", "outfit_next"):
            outfits = HERO_CUSTOMIZATION_DB["outfits"]
            step = -1 if b_key.endswith("prev") else 1
            prof["outfit_idx"] = (prof.get("outfit_idx", 0) + step) % len(outfits)
            save_profile(prof)

        elif b_key == "toggle_preview_walk":
            self.preview_walk = not self.preview_walk

        elif b_key == "roll_preview_color":
            adjs = list(self.game.loc.get("adjectives", {}).values())
            if adjs:
                self.preview_cloak_color = list(random.choice(adjs).get("color", [200, 70, 75]))

        elif b_key == "run_seed":
            self._focus_seed(True)

        elif b_key in ("start_run", "start_jungle"):
            try:
                seed = parse_run_seed(self.seed_text)
            except ValueError:
                self.seed_error = True
                self._focus_seed(True)
                self.seed_selected = True
                self.game.sfx.play("hurt")
                return
            self._focus_seed(False)
            self.can_resume = False
            self.game.in_main_menu = False
            self.game.reset_run(campaign="jungle" if b_key == "start_jungle" else "rats", seed=seed)
            self.seed_text = ""

        elif b_key == "resume_run":
            self.can_resume = False
            self.game.in_main_menu = False

        elif b_key == "vol_down":
            prof["volume"] = round(max(0.0, prof.get("volume", 0.85) - 0.10), 2)
            save_profile(prof)
            self.sync_audio_and_display()

        elif b_key == "vol_up":
            prof["volume"] = round(min(1.0, prof.get("volume", 0.85) + 0.10), 2)
            save_profile(prof)
            self.sync_audio_and_display()

        elif b_key == "speed_cycle":
            prof["typewriter_mode"] = (prof.get("typewriter_mode", 1) + 1) % 3
            save_profile(prof)

        elif b_key in ("freq_prev", "freq_next"):
            step = -1 if b_key.endswith("prev") else 1
            prof["thought_freq_mode"] = (prof.get("thought_freq_mode", 2) + step) % 4
            save_profile(prof)

        elif b_key in ("toggle_minimap", "toggle_performance"):
            setting = {"toggle_minimap": "show_minimap", "toggle_performance": "show_performance"}[b_key]
            prof[setting] = not prof.get(setting, DEFAULT_PROFILE[setting])
            save_profile(prof)

        elif b_key == "dd_win_mode":
            self.open_dropdown = None if self.open_dropdown == "win_mode" else "win_mode"

        elif b_key == "dd_resolution":
            self.open_dropdown = None if self.open_dropdown == "resolution" else "resolution"

        elif b_key == "reset_progress":
            if self.confirm_reset_timer <= 0.0:
                self.confirm_reset_timer = 4.0
                self.game.sfx.play("alert")
            else:
                self.confirm_reset_timer = 0.0
                reset_profile_progress(prof)
                self.game.reset_run()
                self.can_resume = False
                self.game.sfx.play("crit")

        elif b_key == "cancel_meltdown":
            self.meltdown_active = False
            self.active_tab = 0

        elif b_key in ("upg_tab_0", "upg_tab_1", "upg_tab_2"):
            self.upgrade_subtab = int(b_key[-1])

        elif b_key == "strongbox_upgrade":
            lvl = int(prof.get("strongbox_level", 0))
            if lvl < len(STRONGBOX_COSTS):
                cost = STRONGBOX_COSTS[lvl]
                if prof.get("bank_copper", 0) >= cost:
                    prof["bank_copper"] = prof.get("bank_copper", 0) - cost
                    prof["strongbox_level"] = lvl + 1
                    prof["strongbox_enabled"] = True
                    save_profile(prof)
                    self.game.sfx.play("levelup")
                else:
                    self.game.sfx.play("hurt")

        elif b_key == "strongbox_toggle":
            if int(prof.get("strongbox_level", 0)) > 0:
                prof["strongbox_enabled"] = not prof.get("strongbox_enabled", True)
                save_profile(prof)

        elif b_key == "dev_add_gold":
            prof["bank_copper"] = prof.get("bank_copper", 0) + 25000
            save_profile(prof)
            self.game.sfx.play("coin_pickup")

        elif b_key == "dev_unlock_paintings":
            from elenor.rendering.paintings import PAINTINGS_DB
            prof["collected_paintings"] = list(PAINTINGS_DB.keys())
            save_profile(prof)
            self.game.sfx.play("levelup")

        elif b_key.startswith("inspect_paint:"):
            self.inspect_painting_id = b_key.split(":", 1)[1]

        elif b_key == "quit_now":
            pygame.quit()
            raise SystemExit

    def update(self, dt):
        target_x = self.active_tab * self.panel_stride
        self.scroll_x += (target_x - self.scroll_x) * min(1.0, 12.0 * dt)
        self.confirm_reset_timer = max(0.0, self.confirm_reset_timer - dt)

        self.anim_timer += dt
        fps = 7.0 if self.preview_walk else 2.2
        if self.anim_timer >= 1.0 / fps:
            self.anim_timer = 0.0
            self.anim_frame = (self.anim_frame + 1) % 4

        if self.meltdown_active:
            self.meltdown_timer += dt
            if self.meltdown_timer >= 3.2:
                pygame.quit()
                raise SystemExit

    def render(self, screen, dt, mouse_pos):
        r = self.game.renderer
        prof = self.game.profile
        screen.fill((12, 10, 16))
        self.btn_rects = {}

        # 1. ЛЕВАЯ КОЛОНКА МЕНЮ (Якорь: левый край)
        left_rect = pygame.Rect(32, 32, self.sidebar_w, SCREEN_H - 64)
        r.draw_pixel_frame(screen, left_rect, UI_PANEL_BG, UI_BORDER_GOLD, False, 1.0)

        title_1 = r.font_title.render("КРЫСИНЫЙ", True, UI_BORDER_HIGHLIGHT)
        title_2 = r.font_title.render("ПОГРЕБ", True, (225, 95, 85))
        screen.blit(title_1, (left_rect.centerx - title_1.get_width() // 2, 68))
        screen.blit(title_2, (left_rect.centerx - title_2.get_width() // 2, 98))
        r.draw_item_icon(screen, "torch", left_rect.centerx - 16, 136, 32)

        labels = ["ИГРАТЬ", "УЛУЧШИТЬ", "НАСТРОЙКИ", "ВЫХОД"]
        for i, nr in enumerate(self.nav_rects):
            is_sel = (self.active_tab == i)
            is_hov = nr.collidepoint(mouse_pos)
            if i == 3 and (is_hov or is_sel):
                bg = (75, 22, 28)
                bd = (255, 80, 80)
            else:
                bg = (52, 42, 38) if (is_sel or is_hov) else UI_SLOT_BG
                bd = UI_BORDER_HIGHLIGHT if is_sel else UI_BORDER_WOOD
            r.draw_pixel_frame(screen, nr, bg, bd, is_hov or is_sel, 1.0)
            lbl_s = r.font_title.render(labels[i], True, UI_TEXT_MAIN if (is_sel or is_hov) else UI_TEXT_DIM)
            screen.blit(lbl_s, (nr.centerx - lbl_s.get_width() // 2, nr.centery - lbl_s.get_height() // 2))

        bank_rect = pygame.Rect(52, left_rect.bottom - 130, self.sidebar_w - 40, 104)
        r.draw_pixel_frame(screen, bank_rect, UI_SLOT_BG, UI_BORDER_WOOD, False, 1.0)
        b_lbl = r.font_small.render("КАЗНА НАЁМНИКА:", True, UI_TEXT_DIM)
        screen.blit(b_lbl, (bank_rect.centerx - b_lbl.get_width() // 2, bank_rect.y + 16))
        cp_val = prof.get("bank_copper", 0)
        cp_str = format_copper_Trigger(cp_val)
        cp_s = r.font_ui.render(cp_str, True, COIN_TEXT_COLOR)
        screen.blit(cp_s, (bank_rect.centerx - cp_s.get_width() // 2, bank_rect.y + 44))
        raw_s = r.font_small.render(f"(Всего: {cp_val} медяков)", True, COIN_TEXT_COLOR)
        screen.blit(raw_s, (bank_rect.centerx - raw_s.get_width() // 2, bank_rect.y + 72))

        # 2. ПРАВАЯ РЕЗИНОВАЯ ОБЛАСТЬ С ЛИСТАЮЩИМИСЯ ОКНАМИ
        viewport_rect = pygame.Rect(self.right_x, 32, self.panel_w, SCREEN_H - 64)
        old_clip = screen.get_clip()
        screen.set_clip(viewport_rect)

        for tab_i in range(4):
            panel_x = int(self.right_x + tab_i * self.panel_stride - self.scroll_x)
            if panel_x + self.panel_w < self.right_x or panel_x > self.right_x + self.panel_w:
                continue
            p_rect = pygame.Rect(panel_x, 32, self.panel_w, SCREEN_H - 64)
            r.draw_pixel_frame(screen, p_rect, UI_PANEL_BG, UI_BORDER_GOLD, False, 1.0)

            if tab_i == 0:
                self._render_play_tab(screen, p_rect, dt, mouse_pos, prof)
            elif tab_i == 1:
                self._render_upgrade_tab(screen, p_rect, mouse_pos, prof)
            elif tab_i == 2:
                self._render_settings_tab(screen, p_rect, mouse_pos, prof)
            elif tab_i == 3:
                self._render_exit_tab(screen, p_rect, mouse_pos)

        screen.set_clip(old_clip)

        if self.can_resume and not self.meltdown_active:
            rect = self.nav_rects[-1].move(0, 105)
            self.btn_rects["resume_run"] = rect
            hover = rect.collidepoint(mouse_pos)
            r.draw_pixel_frame(screen, rect, (46, 92, 52) if hover else (32, 68, 38), UI_BORDER_GOLD, hover, 1.0)
            label = r.font_ui.render(self.game.loc["exploration_map"]["resume"], True, UI_TEXT_MAIN)
            screen.blit(label, label.get_rect(center=rect.center))

        if self.inspect_painting_id is not None:
            self._render_painting_viewer(screen, mouse_pos, prof)

    def _draw_selector_row(self, screen, x, y, w, label, val_text, prev_key, next_key, mouse_pos, locked=False):
        r = self.game.renderer
        lbl_s = r.font_small.render(label, True, UI_TEXT_DIM)
        screen.blit(lbl_s, (x + (w - lbl_s.get_width()) // 2, y))

        row_y = y + 22
        b_prev = pygame.Rect(x, row_y, 44, 42)
        b_next = pygame.Rect(x + w - 44, row_y, 44, 42)
        val_box = pygame.Rect(x + 52, row_y, w - 104, 42)

        self.btn_rects[prev_key] = b_prev
        self.btn_rects[next_key] = b_next

        for br, sym in ((b_prev, "<"), (b_next, ">")):
            hov = br.collidepoint(mouse_pos)
            r.draw_pixel_frame(screen, br, (52, 42, 38) if hov else UI_SLOT_BG, UI_BORDER_WOOD, hov, 1.0)
            s = r.font_title.render(sym, True, UI_TEXT_MAIN)
            screen.blit(s, (br.centerx - s.get_width() // 2, br.centery - s.get_height() // 2))

        r.draw_pixel_frame(screen, val_box, UI_SLOT_BG, (140, 65, 65) if locked else UI_BORDER_WOOD, False, 1.0)
        col = (255, 130, 120) if locked else UI_BORDER_HIGHLIGHT
        vs = r.font_ui.render(val_text, True, col)
        screen.blit(vs, (val_box.centerx - vs.get_width() // 2, val_box.centery - vs.get_height() // 2))

    def _render_play_tab(self, screen, p_rect, dt, mouse_pos, prof):
        r = self.game.renderer
        h_type = prof.get("hero_type", "male")
        if h_type == "ratfolk" and not prof.get("rat_king_defeated", False):
            h_type = "male"
            prof["hero_type"] = "male"

        type_db = HERO_CUSTOMIZATION_DB[h_type]
        skins = type_db["skins"]
        heads = type_db["heads"]
        outfits = HERO_CUSTOMIZATION_DB["outfits"]

        s_idx = prof.get("skin_idx", 0) % len(skins)
        h_idx = prof.get("head_idx", 0) % len(heads)
        o_idx = prof.get("outfit_idx", 0) % len(outfits)

        # Резиновое деление вкладки ИГРАТЬ на 2 равные колонки под любой экран!
        col_w = (p_rect.width - 72) // 2
        ed_rect = pygame.Rect(p_rect.x + 24, p_rect.y + 24, col_w, p_rect.height - 48)
        r.draw_pixel_frame(screen, ed_rect, UI_SLOT_BG, UI_BORDER_WOOD, False, 1.0)

        hdr = r.font_title.render("ОБЛИК ГЕРОЯ", True, UI_BORDER_HIGHLIGHT)
        screen.blit(hdr, (ed_rect.centerx - hdr.get_width() // 2, ed_rect.y + 20))

        prev_box = pygame.Rect(ed_rect.centerx - 144, ed_rect.y + 56, 288, 328)
        r.draw_pixel_frame(screen, prev_box, (16, 14, 22), UI_BORDER_GOLD, False, 1.0)

        d_hero, n_hero = build_custom_hero_sprite(
            cloak_color=tuple(self.preview_cloak_color),
            armor_class="none",
            has_helmet=False,
            has_torch=True,
            has_weapon=True,
            hero_type=h_type,
            skin_idx=s_idx,
            head_idx=h_idx,
            outfit_idx=o_idx,
            anim_frame=self.anim_frame,
            is_moving=self.preview_walk,
        )
        lit_surf = self.preview_3d.render(d_hero, n_hero, dt)
        screen.blit(lit_surf, (prev_box.x + 4, prev_box.y + 4))

        btn_w = (ed_rect.width - 84) // 2
        b_walk = pygame.Rect(ed_rect.x + 32, prev_box.bottom + 14, btn_w, 38)
        b_col = pygame.Rect(ed_rect.right - 32 - btn_w, prev_box.bottom + 14, btn_w, 38)
        self.btn_rects["toggle_preview_walk"] = b_walk
        self.btn_rects["roll_preview_color"] = b_col

        for br, txt in ((b_walk, "Анимация: БЕГ" if self.preview_walk else "Анимация: ПОКОЙ"), (b_col, "Цвет характера")):
            hov = br.collidepoint(mouse_pos)
            r.draw_pixel_frame(screen, br, (48, 38, 36) if hov else UI_PANEL_BG, UI_BORDER_WOOD, hov, 1.0)
            ts = r.font_small.render(txt, True, UI_TEXT_MAIN)
            screen.blit(ts, (br.centerx - ts.get_width() // 2, br.centery - ts.get_height() // 2))

        sel_x = ed_rect.x + 32
        sel_w = ed_rect.width - 64
        cur_y = b_walk.bottom + 22
        step_y = 82

        self._draw_selector_row(screen, sel_x, cur_y, sel_w, "ТИП ПЕРСОНАЖА:", type_db["title"], "type_prev", "type_next", mouse_pos)
        cur_y += step_y
        skin_label = "ОКРАС ШЕРСТИ:" if h_type == "ratfolk" else "ЦВЕТ КОЖИ:"
        self._draw_selector_row(screen, sel_x, cur_y, sel_w, skin_label, skins[s_idx][0], "skin_prev", "skin_next", mouse_pos)
        cur_y += step_y
        head_label = "ОСОБЕННОСТЬ ГОЛОВЫ:" if h_type == "ratfolk" else "ПРИЧЁСКА И ЛИЦО:"
        self._draw_selector_row(screen, sel_x, cur_y, sel_w, head_label, heads[h_idx][0], "head_prev", "head_next", mouse_pos)
        cur_y += step_y
        self._draw_selector_row(screen, sel_x, cur_y, sel_w, "БАЗОВОЕ ОДЕЯНИЕ:", outfits[o_idx][0], "outfit_prev", "outfit_next", mouse_pos)

        if not prof.get("rat_king_defeated", False):
            lock_txt = r.font_small.render("Крысолюд: убейте Крысиного Короля в Кампании I!", True, (235, 145, 115))
            screen.blit(lock_txt, (ed_rect.centerx - lock_txt.get_width() // 2, ed_rect.bottom - 68))
            dev_unlock = pygame.Rect(ed_rect.centerx - 120, ed_rect.bottom - 42, 240, 30)
            self.btn_rects["unlock_ratfolk_dev"] = dev_unlock
            hov_u = dev_unlock.collidepoint(mouse_pos)
            pygame.draw.rect(screen, (55, 38, 48) if hov_u else (32, 24, 34), dev_unlock, border_radius=4)
            pygame.draw.rect(screen, UI_BORDER_GOLD, dev_unlock, 1, border_radius=4)
            ut = r.font_small.render("[Открыть сейчас (Тест)]", True, (255, 220, 95))
            screen.blit(ut, (dev_unlock.centerx - ut.get_width() // 2, dev_unlock.centery - ut.get_height() // 2))
        else:
            ok_txt = r.font_small.render("★ Тип «Крысолюд» разблокирован!", True, (125, 240, 155))
            screen.blit(ok_txt, (ed_rect.centerx - ok_txt.get_width() // 2, ed_rect.bottom - 42))

        # ПРАВАЯ КОЛОНКА: ВЫБОР КОНТРАКТА И СТАРТ
        camp_rect = pygame.Rect(ed_rect.right + 24, p_rect.y + 24, col_w, p_rect.height - 48)
        r.draw_pixel_frame(screen, camp_rect, UI_SLOT_BG, UI_BORDER_WOOD, False, 1.0)

        chdr = r.font_title.render("ВЫБОР КОНТРАКТА", True, UI_BORDER_HIGHLIGHT)
        screen.blit(chdr, (camp_rect.centerx - chdr.get_width() // 2, camp_rect.y + 20))

        card_1 = pygame.Rect(camp_rect.x + 28, camp_rect.y + 64, camp_rect.width - 56, 280)
        r.draw_pixel_frame(screen, card_1, (30, 25, 36), UI_BORDER_GOLD, True, 1.0)

        c_title = r.font_title.render("I. КРЫСИНЫЙ ПОГРЕБ", True, (255, 220, 95))
        screen.blit(c_title, (card_1.x + 22, card_1.y + 20))

        status_str = "Пройдено ★" if prof.get("rat_king_defeated", False) else "Вступительный контракт"
        status_col = (120, 240, 150) if prof.get("rat_king_defeated", False) else (130, 200, 255)
        screen.blit(r.font_ui.render(status_str, True, status_col), (card_1.x + 22, card_1.y + 50))

        desc_text = (
            "В погребе таверны Гуго расплодились крысы величиной с волка, "
            "а на нижних ярусах сектанты под одним плащом плетут кровавые печати. "
            "Спуститесь на 4-й ярус и сокрушите Крысиного Короля!"
        )
        for i, ln in enumerate(r.wrap_text(desc_text, r.font_ui, card_1.width - 44)):
            screen.blit(r.font_ui.render(ln, True, UI_TEXT_MAIN), (card_1.x + 22, card_1.y + 90 + i * 24))

        rew_s = r.font_ui.render("Награда: Открытие типа «Крысолюд»", True, (255, 195, 85))
        screen.blit(rew_s, (card_1.x + 22, card_1.bottom - 38))

        card_2 = pygame.Rect(camp_rect.x + 28, card_1.bottom + 24, camp_rect.width - 56, 110)
        self.btn_rects["start_jungle"] = card_2
        hovering_jungle = card_2.collidepoint(mouse_pos)
        fishing_text = self.game.loc["fishing"]
        r.draw_pixel_frame(screen, card_2, (38, 65, 47) if hovering_jungle else (26, 42, 34),
                           UI_BORDER_GOLD, hovering_jungle, 1.0)
        screen.blit(r.font_title.render(fishing_text["campaign"], True, (175, 238, 161)),
                    (card_2.x + 22, card_2.y + 22))
        screen.blit(r.font_ui.render(fishing_text["campaign_note"], True, UI_TEXT_MAIN),
                    (card_2.x + 22, card_2.y + 58))

        diff_box = pygame.Rect(camp_rect.x + 28, card_2.bottom + 24, camp_rect.width - 56, 84)
        r.draw_pixel_frame(screen, diff_box, UI_PANEL_BG, UI_BORDER_WOOD, False, 1.0)
        screen.blit(r.font_small.render("СЛОЖНОСТЬ ПОХОДА:", True, UI_TEXT_DIM), (diff_box.x + 22, diff_box.y + 16))
        screen.blit(r.font_title.render("Обычная (Стандартный баланс)", True, UI_TEXT_MAIN), (diff_box.x + 22, diff_box.y + 42))

        labels = self.game.loc["run_seed"]
        seed_rect = pygame.Rect(diff_box.x, diff_box.bottom + 46, diff_box.width, 46)
        screen.blit(r.font_small.render(labels["label"], True, UI_TEXT_DIM), (seed_rect.x, seed_rect.y - 21))
        self.btn_rects["run_seed"] = seed_rect
        hover = self.seed_focused or seed_rect.collidepoint(mouse_pos)
        seed_border = (210, 105, 90) if self.seed_error else UI_BORDER_GOLD if hover else UI_BORDER_WOOD
        r.draw_pixel_frame(screen, seed_rect, UI_PANEL_BG, seed_border, hover, 1.0)
        seed_text = self.seed_text or labels["random"]
        value = r.font_ui.render(seed_text, True, UI_TEXT_MAIN if self.seed_text else UI_TEXT_DIM)
        value_rect = value.get_rect(midleft=(seed_rect.x + 16, seed_rect.centery))
        if self.seed_selected and self.seed_text:
            pygame.draw.rect(screen, (66, 55, 72), value_rect.inflate(8, 6))
        screen.blit(value, value_rect)
        if self.seed_focused and not self.seed_selected and pygame.time.get_ticks() % 1000 < 500:
            caret_x = value_rect.right + 2 if self.seed_text else value_rect.left
            pygame.draw.line(screen, UI_BORDER_HIGHLIGHT, (caret_x, seed_rect.y + 9), (caret_x, seed_rect.bottom - 9), 2)
        if self.seed_error:
            screen.blit(r.font_small.render(labels["invalid"], True, (245, 145, 125)), (seed_rect.x, seed_rect.bottom + 7))

        note_lines = r.wrap_text("Сид определяет Характер героя и цвет его плаща.", r.font_ui, camp_rect.width - 56)
        for i, ln in enumerate(note_lines):
            screen.blit(r.font_ui.render(ln, True, UI_TEXT_DIM), (camp_rect.x + 28, seed_rect.bottom + 37 + i * 24))

        start_btn = pygame.Rect(camp_rect.x + 28, camp_rect.bottom - 104, camp_rect.width - 56, 76)
        self.btn_rects["start_run"] = start_btn
        hov_st = start_btn.collidepoint(mouse_pos)
        r.draw_pixel_frame(screen, start_btn, (46, 92, 52) if hov_st else (32, 68, 38), UI_BORDER_GOLD, hov_st, 1.0)
        st_lbl = r.font_popup_big.render("В КРЫСИНЫЙ ПОГРЕБ", True, (255, 245, 200))
        screen.blit(st_lbl, (start_btn.centerx - st_lbl.get_width() // 2, start_btn.centery - st_lbl.get_height() // 2))

    def _render_upgrade_tab(self, screen, p_rect, mouse_pos, prof):
        from elenor.rendering.fishing import FISH_CATALOG_SPECS
        from elenor.rendering.paintings import PAINTINGS_DB

        r = self.game.renderer
        col_fish = set(prof.get("collected_fish", ()))
        col_paint = set(prof.get("collected_paintings", ()))

        # Три подвкладки сверху: Улучшения / Рыбы / Картины
        sub_labels = [
            "УЛУЧШЕНИЯ",
            f"РЫБЫ ({len(col_fish)}/{len(FISH_CATALOG_SPECS)})",
            f"КАРТИНЫ ({len(col_paint)}/{len(PAINTINGS_DB)})",
        ]
        tab_w = 260
        gap = 16
        start_x = p_rect.centerx - (tab_w * 3 + gap * 2) // 2
        for idx, lbl in enumerate(sub_labels):
            tr = pygame.Rect(start_x + idx * (tab_w + gap), p_rect.y + 24, tab_w, 42)
            self.btn_rects[f"upg_tab_{idx}"] = tr
            is_sel = (self.upgrade_subtab == idx)
            hov = tr.collidepoint(mouse_pos)
            bg = (52, 42, 38) if (is_sel or hov) else UI_SLOT_BG
            bd = UI_BORDER_GOLD if is_sel else UI_BORDER_WOOD
            r.draw_pixel_frame(screen, tr, bg, bd, is_sel or hov, 1.0)
            ts = r.font_ui.render(lbl, True, UI_BORDER_HIGHLIGHT if is_sel else UI_TEXT_MAIN)
            screen.blit(ts, ts.get_rect(center=tr.center))

        if self.upgrade_subtab == 1:
            self._render_fish_collection(screen, p_rect, col_fish, FISH_CATALOG_SPECS)
            return
        if self.upgrade_subtab == 2:
            self._render_paintings_collection(screen, p_rect, col_paint, PAINTINGS_DB)
            return

        lvl = int(prof.get("strongbox_level", 0))
        enabled = bool(prof.get("strongbox_enabled", True))
        bank = int(prof.get("bank_copper", 0))

        card_w = min(920, p_rect.width - 120)
        card = pygame.Rect(p_rect.centerx - card_w // 2, p_rect.y + 92, card_w, 300)
        r.draw_pixel_frame(screen, card, UI_SLOT_BG, UI_BORDER_GOLD if lvl > 0 else UI_BORDER_WOOD, False, 1.0)

        ic_box = pygame.Rect(card.x + 28, card.y + 28, 76, 76)
        r.draw_pixel_frame(screen, ic_box, UI_PANEL_BG, UI_BORDER_GOLD, False, 1.0)
        r.draw_item_icon(screen, "bag_strongbox", ic_box.x + 14, ic_box.y + 14, 48)

        title_s = r.font_title.render("СЕМЕЙНАЯ ШКАТУЛКА", True, UI_BORDER_HIGHLIGHT)
        screen.blit(title_s, (ic_box.right + 22, card.y + 30))

        st_txt = f"Уровень {lvl} / 5  ·  Мест: {lvl}" if lvl > 0 else "Не куплена  ·  Даёт 1 несгораемый слот"
        st_col = (125, 240, 155) if lvl > 0 else UI_TEXT_DIM
        screen.blit(r.font_ui.render(st_txt, True, st_col), (ic_box.right + 22, card.y + 60))

        for i in range(5):
            pip = pygame.Rect(ic_box.right + 22 + i * 32, card.y + 88, 24, 14)
            pygame.draw.rect(screen, UI_BORDER_GOLD if i < lvl else (36, 30, 44), pip, border_radius=2)
            pygame.draw.rect(screen, UI_BORDER_HIGHLIGHT if i < lvl else UI_BORDER_WOOD, pip, 1, border_radius=2)

        desc = (
            "Занимает один слот сумки и не снимается в походе. Любой предмет внутри шкатулки "
            "гарантированно выносится на экран итогов — даже если герой погибнет."
        )
        for i, ln in enumerate(r.wrap_text(desc, r.font_ui, card.width - 56)):
            screen.blit(r.font_ui.render(ln, True, UI_TEXT_MAIN), (card.x + 28, card.y + 124 + i * 24))

        btn_y = card.bottom - 74
        if lvl > 0:
            tog_r = pygame.Rect(card.x + 28, btn_y, 260, 50)
            self.btn_rects["strongbox_toggle"] = tog_r
            hov_t = tog_r.collidepoint(mouse_pos)
            bg_t = ((46, 92, 52) if hov_t else (32, 68, 38)) if enabled else ((56, 44, 48) if hov_t else (36, 28, 34))
            r.draw_pixel_frame(screen, tog_r, bg_t, UI_BORDER_GOLD if enabled else UI_BORDER_WOOD, hov_t, 1.0)
            t_lbl = r.font_ui.render("В походе: ВКЛ" if enabled else "В походе: ВЫКЛ", True, UI_TEXT_MAIN if enabled else UI_TEXT_DIM)
            screen.blit(t_lbl, t_lbl.get_rect(center=tog_r.center))

        upg_x = card.x + 308 if lvl > 0 else card.x + 28
        upg_w = card.right - 28 - upg_x
        upg_r = pygame.Rect(upg_x, btn_y, upg_w, 50)
        if lvl < len(STRONGBOX_COSTS):
            cost = STRONGBOX_COSTS[lvl]
            can_buy = bank >= cost
            self.btn_rects["strongbox_upgrade"] = upg_r
            hov_u = upg_r.collidepoint(mouse_pos)
            bg_u = ((58, 86, 46) if hov_u else (40, 64, 34)) if can_buy else ((52, 28, 32) if hov_u else (34, 22, 28))
            bd_u = UI_BORDER_GOLD if can_buy else (130, 62, 68)
            r.draw_pixel_frame(screen, upg_r, bg_u, bd_u, hov_u and can_buy, 1.0)
            action_txt = "КУПИТЬ (1 слот)" if lvl == 0 else f"УЛУЧШИТЬ ({lvl} → {lvl + 1} слот.)"
            price_str = format_copper_Trigger(cost, compact=True)
            lbl_u = r.font_ui.render(f"{action_txt}  ·  {price_str}", True, COIN_TEXT_COLOR if can_buy else (215, 120, 120))
            screen.blit(lbl_u, lbl_u.get_rect(center=upg_r.center))
        else:
            r.draw_pixel_frame(screen, upg_r, (28, 34, 32), UI_BORDER_GOLD, False, 1.0)
            lbl_u = r.font_ui.render("МАКСИМАЛЬНЫЙ УРОВЕНЬ (5 / 5)", True, (135, 240, 165))
            screen.blit(lbl_u, lbl_u.get_rect(center=upg_r.center))
        dev_gold_r = pygame.Rect(p_rect.centerx - 150, card.bottom + 24, 300, 34)
        self.btn_rects["dev_add_gold"] = dev_gold_r
        hov_g = dev_gold_r.collidepoint(mouse_pos)
        pygame.draw.rect(screen, (55, 38, 48) if hov_g else (32, 24, 34), dev_gold_r, border_radius=4)
        pygame.draw.rect(screen, UI_BORDER_GOLD, dev_gold_r, 1, border_radius=4)
        gt = r.font_small.render("[+25 пм в казну (Тест)]", True, (255, 220, 95))
        screen.blit(gt, gt.get_rect(center=dev_gold_r.center))

    def _render_fish_collection(self, screen, p_rect, collected, specs):
        r = self.game.renderer
        items = list(specs.items())
        cols = 8
        margin = 32
        gap = 10
        cell_w = (p_rect.width - margin * 2 - gap * (cols - 1)) // cols
        cell_h = 112
        top_y = p_rect.y + 88

        for idx, (fish_id, spec) in enumerate(items):
            row, col = divmod(idx, cols)
            cx = p_rect.x + margin + col * (cell_w + gap)
            cy = top_y + row * (cell_h + gap)
            if cy + cell_h > p_rect.bottom - 16:
                break
            rect = pygame.Rect(cx, cy, cell_w, cell_h)
            owned = fish_id in collected
            r.draw_pixel_frame(screen, rect, UI_SLOT_BG if owned else (18, 16, 22), UI_BORDER_GOLD if owned else (52, 46, 60), False, 1.0)
            if owned:
                r.draw_item_icon(screen, fish_id, rect.centerx - 24, rect.y + 12, 48)
                name = spec[0].removeprefix("Улов: ")
                for li, ln in enumerate(r.wrap_text(name, r.font_small, cell_w - 12)[:2]):
                    ls = r.font_small.render(ln, True, UI_TEXT_MAIN)
                    screen.blit(ls, ls.get_rect(midtop=(rect.centerx, rect.y + 66 + li * 16)))
            else:
                q_s = r.font_title.render("?", True, (70, 64, 82))
                screen.blit(q_s, q_s.get_rect(center=(rect.centerx, rect.y + 42)))
                u_s = r.font_small.render("Не поймано", True, (75, 68, 86))
                screen.blit(u_s, u_s.get_rect(midtop=(rect.centerx, rect.y + 72)))

    def _step_painting_viewer(self, delta, prof):
        from elenor.rendering.paintings import PAINTINGS_DB
        owned = [pid for pid in PAINTINGS_DB if pid in set(prof.get("collected_paintings", ()))]
        if not owned:
            self.inspect_painting_id = None
            return
        if self.inspect_painting_id not in owned:
            self.inspect_painting_id = owned[0]
        else:
            idx = (owned.index(self.inspect_painting_id) + delta) % len(owned)
            self.inspect_painting_id = owned[idx]
        self.game.sfx.play("ui")

    def _render_paintings_collection(self, screen, p_rect, collected, db):
        from elenor.config import RARITY_COLORS
        r = self.game.renderer
        items = list(db.items())
        cols = 6
        margin = 32
        gap = 12
        cell_w = (p_rect.width - margin * 2 - gap * (cols - 1)) // cols
        cell_h = 186
        top_y = p_rect.y + 84

        for idx, (pid, data) in enumerate(items):
            row, col = divmod(idx, cols)
            cx = p_rect.x + margin + col * (cell_w + gap)
            cy = top_y + row * (cell_h + gap)
            if cy + cell_h > p_rect.bottom - 52:
                break
            rect = pygame.Rect(cx, cy, cell_w, cell_h)
            owned = pid in collected
            r_col = RARITY_COLORS.get(data["rarity"], UI_BORDER_WOOD)
            r.draw_pixel_frame(screen, rect, UI_SLOT_BG if owned else (18, 16, 22), r_col if owned else (52, 46, 60), False, 1.0)
            if owned:
                self.btn_rects[f"inspect_paint:{pid}"] = rect
                r.draw_item_icon(screen, pid, rect.centerx - 56, rect.y + 10, 112)
                for li, ln in enumerate(r.wrap_text(data["name"], r.font_small, cell_w - 14)[:2]):
                    ls = r.font_small.render(ln, True, r_col)
                    screen.blit(ls, ls.get_rect(midtop=(rect.centerx, rect.y + 130 + li * 17)))
                hint = r.font_small.render("Нажми, чтобы открыть", True, UI_TEXT_DIM)
                screen.blit(hint, hint.get_rect(midbottom=(rect.centerx, rect.bottom - 6)))
            else:
                orient = data.get("orientation", "v")
                fw, fh = (68, 98) if orient == "v" else (98, 68)
                frame_r = pygame.Rect(rect.centerx - fw // 2, rect.y + 64 - fh // 2, fw, fh)
                pygame.draw.rect(screen, (26, 22, 32), frame_r)
                pygame.draw.rect(screen, (62, 54, 74), frame_r, 2)
                q_s = r.font_title.render("?", True, (78, 70, 92))
                screen.blit(q_s, q_s.get_rect(center=frame_r.center))
                u_s = r.font_small.render("Не найдено", True, (75, 68, 86))
                screen.blit(u_s, u_s.get_rect(midtop=(rect.centerx, rect.y + 136)))

        # Тестовая кнопка открытия всей галереи в самом низу вкладки
        dev_r = pygame.Rect(p_rect.centerx - 160, p_rect.bottom - 44, 320, 32)
        self.btn_rects["dev_unlock_paintings"] = dev_r
        pygame.draw.rect(screen, (36, 26, 38), dev_r, border_radius=4)
        pygame.draw.rect(screen, UI_BORDER_GOLD, dev_r, 1, border_radius=4)
        dt_s = r.font_small.render("[Открыть все картины (Тест)]", True, (255, 220, 95))
        screen.blit(dt_s, dt_s.get_rect(center=dev_r.center))

    def _render_painting_viewer(self, screen, mouse_pos, prof):
        from elenor.config import RARITY_COLORS
        from elenor.rendering.paintings import PAINTINGS_DB, get_painting_surface

        pid = self.inspect_painting_id
        data = PAINTINGS_DB.get(pid)
        if data is None:
            self.inspect_painting_id = None
            return

        r = self.game.renderer
        self.viewer_btn_rects = {}

        dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        dim.fill((6, 5, 12, 224))
        screen.blit(dim, (0, 0))

        orient = data.get("orientation", "v")
        scale = 10 if orient == "v" else 11
        card_surf = get_painting_surface(pid, scale=scale)
        cw, ch = card_surf.get_size()

        modal_w = max(680, cw + 190)
        modal_h = ch + 210
        mx = (SCREEN_W - modal_w) // 2
        my = (SCREEN_H - modal_h) // 2
        modal_r = pygame.Rect(mx, my, modal_w, modal_h)
        self.viewer_modal_rect = modal_r

        r_col = RARITY_COLORS.get(data["rarity"], UI_BORDER_GOLD)
        r.draw_pixel_frame(screen, modal_r, UI_PANEL_BG, r_col, False, 1.0)

        title_s = r.font_popup_big.render(data["name"], True, r_col)
        screen.blit(title_s, title_s.get_rect(midtop=(modal_r.centerx, my + 18)))

        owned = [k for k in PAINTINGS_DB if k in set(prof.get("collected_paintings", ()))]
        pos_tag = f"{owned.index(pid) + 1}/{len(owned)}" if pid in owned else ""
        rar_name = self.game.loc["ui"]["rarities"].get(data["rarity"], data["rarity"])
        dim_tag = "42×62 · Вертикальная" if orient == "v" else "62×42 · Горизонтальная"
        price_str = format_copper_Trigger(data["copper_value"], compact=True)
        meta_s = r.font_small.render(f"{rar_name}  ·  {dim_tag}  ·  Оценка: {price_str}  ·  {pos_tag}", True, UI_TEXT_DIM)
        screen.blit(meta_s, meta_s.get_rect(midtop=(modal_r.centerx, my + 52)))

        img_x = modal_r.centerx - cw // 2
        img_y = my + 80
        pygame.draw.rect(screen, (10, 8, 16), (img_x - 6, img_y - 6, cw + 12, ch + 12))
        pygame.draw.rect(screen, r_col, (img_x - 4, img_y - 4, cw + 8, ch + 8), 2)
        screen.blit(card_surf, (img_x, img_y))

        if len(owned) > 1:
            b_prev = pygame.Rect(mx + 22, img_y + ch // 2 - 30, 56, 60)
            b_next = pygame.Rect(modal_r.right - 78, img_y + ch // 2 - 30, 56, 60)
            self.viewer_btn_rects["prev"] = b_prev
            self.viewer_btn_rects["next"] = b_next
            for br, sym in ((b_prev, "<"), (b_next, ">")):
                hov = br.collidepoint(mouse_pos)
                r.draw_pixel_frame(screen, br, (58, 48, 44) if hov else UI_SLOT_BG, UI_BORDER_GOLD if hov else UI_BORDER_WOOD, hov, 1.0)
                ss = r.font_popup_big.render(sym, True, UI_TEXT_MAIN)
                screen.blit(ss, ss.get_rect(center=br.center))

        desc_y = img_y + ch + 16
        for li, ln in enumerate(r.wrap_text(data["desc"], r.font_ui, modal_w - 64)[:3]):
            ds = r.font_ui.render(ln, True, UI_TEXT_MAIN)
            screen.blit(ds, ds.get_rect(midtop=(modal_r.centerx, desc_y + li * 22)))

        hint_s = r.font_small.render("← / → или колесо мыши — листать  ·  ESC или клик вне окна — закрыть", True, UI_TEXT_DIM)
        screen.blit(hint_s, hint_s.get_rect(midbottom=(modal_r.centerx, modal_r.bottom - 12)))

        b_close = pygame.Rect(modal_r.right - 48, my + 14, 34, 34)
        self.viewer_btn_rects["close"] = b_close
        hov_c = b_close.collidepoint(mouse_pos)
        r.draw_pixel_frame(screen, b_close, (108, 34, 40) if hov_c else (56, 24, 30), UI_BORDER_HIGHLIGHT if hov_c else UI_BORDER_WOOD, hov_c, 1.0)
        xs = r.font_ui.render("X", True, UI_TEXT_MAIN)
        screen.blit(xs, xs.get_rect(center=b_close.center))

    def _draw_dropdown_box(self, screen, x, y, w, label, current_text, btn_key, is_open, mouse_pos, disabled=False):
        r = self.game.renderer
        lbl_s = r.font_small.render(label, True, UI_TEXT_DIM)
        screen.blit(lbl_s, (x + (w - lbl_s.get_width()) // 2, y))

        box_r = pygame.Rect(x, y + 22, w, 42)
        if disabled:
            r.draw_pixel_frame(screen, box_r, (20, 18, 24), (58, 52, 62), False, 0.7)
            val_s = r.font_ui.render(current_text, True, UI_TEXT_DIM)
            screen.blit(val_s, (box_r.centerx - val_s.get_width() // 2, box_r.centery - val_s.get_height() // 2))
            return box_r

        self.btn_rects[btn_key] = box_r
        hov = box_r.collidepoint(mouse_pos)
        bg = (52, 42, 38) if (hov or is_open) else UI_SLOT_BG
        bd = UI_BORDER_GOLD if is_open else UI_BORDER_WOOD
        r.draw_pixel_frame(screen, box_r, bg, bd, hov or is_open, 1.0)

        arrow = "▲" if is_open else "▼"
        val_s = r.font_ui.render(f"{current_text}   {arrow}", True, UI_BORDER_HIGHLIGHT)
        screen.blit(val_s, (box_r.centerx - val_s.get_width() // 2, box_r.centery - val_s.get_height() // 2))
        return box_r

    def _render_settings_tab(self, screen, p_rect, mouse_pos, prof):
        r = self.game.renderer
        hdr = r.font_title.render("НАСТРОЙКИ ИГРЫ", True, UI_BORDER_HIGHLIGHT)
        screen.blit(hdr, (p_rect.centerx - hdr.get_width() // 2, p_rect.y + 32))

        box_w = min(920, p_rect.width - 140)
        box = pygame.Rect(p_rect.centerx - box_w // 2, p_rect.y + 84, box_w, p_rect.height - 140)
        r.draw_pixel_frame(screen, box, UI_SLOT_BG, UI_BORDER_WOOD, False, 1.0)

        row_x = box.x + 80
        row_w = box.width - 160
        step_y = 84

        cur_wmode = prof.get("window_mode", "windowed")
        wmode_title = dict(WINDOW_MODES_LIST).get(cur_wmode, "В окне")
        dd_wmode_rect = self._draw_dropdown_box(
            screen, row_x, box.y + 32, row_w,
            "РЕЖИМ ОТОБРАЖЕНИЯ ЭКРАНА:", wmode_title,
            "dd_win_mode", self.open_dropdown == "win_mode", mouse_pos
        )

        avail = get_available_resolutions()
        cur_r_idx = resolution_index(prof, avail)
        is_borderless = (cur_wmode == "borderless")
        if is_borderless:
            dw, dh = get_desktop_size()
            res_title = f"Родное ({dw} x {dh})"
            if self.open_dropdown == "resolution":
                self.open_dropdown = None
        else:
            res_title = avail[cur_r_idx][2]
        dd_res_rect = self._draw_dropdown_box(
            screen, row_x, box.y + 32 + step_y, row_w,
            "РАЗРЕШЕНИЕ ЭКРАНА (16:9 FULL HD БАЗА):", res_title,
            "dd_resolution", self.open_dropdown == "resolution", mouse_pos,
            disabled=is_borderless
        )
        vol_pct = int(round(prof.get("volume", 0.85) * 100))
        self._draw_selector_row(screen, row_x, box.y + 32 + step_y * 2, row_w, "ГРОМКОСТЬ ЗВУКОВ:", f"{vol_pct}%", "vol_down", "vol_up", mouse_pos)

        modes = ["Обычная (Атмосферно)", "Быстрая (x2)", "Мгновенно"]
        m_idx = prof.get("typewriter_mode", 1) % 3
        self._draw_selector_row(screen, row_x, box.y + 32 + step_y * 3, row_w, "СКОРОСТЬ ТЕКСТА МЫСЛЕЙ:", modes[m_idx], "speed_cycle", "speed_cycle", mouse_pos)

        freq_modes = [
            "Только сюжетные и важные",
            "Редко (x0.5, КД 10 сек)",
            "Обычная (x1.0, КД 6 сек)",
            "Часто (x1.75, КД 3.5 сек)"
        ]
        f_idx = prof.get("thought_freq_mode", 2) % 4
        self._draw_selector_row(screen, row_x, box.y + 32 + step_y * 4, row_w, "ЧАСТОТА МЫСЛЕЙ ГЕРОЯ:", freq_modes[f_idx], "freq_prev", "freq_next", mouse_pos)

        map_labels = self.game.loc["exploration_map"]["settings"]
        for index, (key, setting, label, states) in enumerate((
            ("toggle_minimap", "show_minimap", map_labels["minimap"], (map_labels["off"], map_labels["on"])),
            ("toggle_performance", "show_performance", "Показывать производительность", ("Нет", "Да")),
        )):
            toggle_rect = pygame.Rect(row_x, box.y + 54 + step_y * 5 + index * 50, row_w, 42)
            self.btn_rects[key] = toggle_rect
            enabled = prof.get(setting, DEFAULT_PROFILE[setting])
            hover = toggle_rect.collidepoint(mouse_pos)
            bg = (52, 42, 38) if hover else UI_SLOT_BG
            r.draw_pixel_frame(screen, toggle_rect, bg, UI_BORDER_GOLD if enabled else UI_BORDER_WOOD, hover, 1.0)
            name = r.font_ui.render(label, True, UI_TEXT_MAIN)
            status = states[bool(enabled)]
            value = r.font_ui.render(status, True, UI_BORDER_HIGHLIGHT if enabled else UI_TEXT_DIM)
            screen.blit(name, name.get_rect(midleft=(toggle_rect.left + 20, toggle_rect.centery)))
            screen.blit(value, value.get_rect(midright=(toggle_rect.right - 20, toggle_rect.centery)))

        line_y = box.y + 40 + step_y * 6 + 50
        pygame.draw.line(screen, UI_BORDER_WOOD, (box.x + 50, line_y), (box.right - 50, line_y), 1)
        rst_btn = pygame.Rect(row_x, box.y + 62 + step_y * 6 + 50, row_w, 56)
        self.btn_rects["reset_progress"] = rst_btn
        hov_r = rst_btn.collidepoint(mouse_pos)
        if self.confirm_reset_timer > 0.0:
            r.draw_pixel_frame(screen, rst_btn, (135, 28, 34) if hov_r else (105, 20, 26), (255, 110, 110), True, 1.0)
            r_txt = r.font_ui.render("ТОЧНО СБРОСИТЬ ПРОГРЕСС? (КЛИКНИ ЕЩЁ РАЗ)", True, (255, 235, 210))
        else:
            r.draw_pixel_frame(screen, rst_btn, (68, 26, 32) if hov_r else (46, 20, 26), (175, 75, 75), hov_r, 1.0)
            r_txt = r.font_ui.render("СБРОСИТЬ ВЕСЬ ПРОГРЕСС (ЗОЛОТО, ШКАТУЛКА, КОЛЛЕКЦИИ)", True, (240, 165, 165))
        screen.blit(r_txt, (rst_btn.centerx - r_txt.get_width() // 2, rst_btn.centery - r_txt.get_height() // 2))

        save_hint = r.font_small.render(f"Папка сохранений: {get_profile_dir()}", True, UI_TEXT_DIM)
        screen.blit(save_hint, (box.centerx - save_hint.get_width() // 2, box.bottom - 58))
        hint = r.font_small.render("В игре: [ESC] — Меню | [F2] — FX-Лаборатория | [F3] — Отладка Вектора Билда", True, UI_TEXT_DIM)
        screen.blit(hint, (box.centerx - hint.get_width() // 2, box.bottom - 32))

        self.dropdown_item_rects = []
        if self.open_dropdown == "win_mode":
            options = [(k, title, k == cur_wmode) for k, title in WINDOW_MODES_LIST]
            self._render_dropdown_list_overlay(screen, dd_wmode_rect, options, mouse_pos)
        elif self.open_dropdown == "resolution":
            avail = get_available_resolutions()
            options = [(idx, title, idx == cur_r_idx) for idx, (_, _, title) in enumerate(avail)]
            self._render_dropdown_list_overlay(screen, dd_res_rect, options, mouse_pos)

    def _render_dropdown_list_overlay(self, screen, anchor_rect, options, mouse_pos):
        r = self.game.renderer
        item_h = 38
        list_h = len(options) * item_h + 12
        list_rect = pygame.Rect(anchor_rect.x, anchor_rect.bottom + 2, anchor_rect.width, list_h)
        pygame.draw.rect(screen, (6, 5, 10), (list_rect.x + 4, list_rect.y + 4, list_rect.width, list_rect.height))
        r.draw_pixel_frame(screen, list_rect, (22, 18, 28), UI_BORDER_GOLD, True, 1.0)

        for idx, (opt_val, opt_title, is_selected) in enumerate(options):
            ir = pygame.Rect(list_rect.x + 6, list_rect.y + 6 + idx * item_h, list_rect.width - 12, item_h - 2)
            self.dropdown_item_rects.append((opt_val, ir))
            hov = ir.collidepoint(mouse_pos)
            if hov:
                pygame.draw.rect(screen, (68, 54, 46), ir, border_radius=3)
                pygame.draw.rect(screen, UI_BORDER_HIGHLIGHT, ir, 1, border_radius=3)
            elif is_selected:
                pygame.draw.rect(screen, (42, 36, 48), ir, border_radius=3)
            prefix = "★ " if is_selected else "   "
            col = (255, 230, 110) if (is_selected or hov) else UI_TEXT_MAIN
            ts = r.font_ui.render(f"{prefix}{opt_title}", True, col)
            screen.blit(ts, (ir.x + 14, ir.centery - ts.get_height() // 2))

    def _render_exit_tab(self, screen, p_rect, mouse_pos):
        r = self.game.renderer
        box_w = min(920, p_rect.width - 140)
        box = pygame.Rect(p_rect.centerx - box_w // 2, p_rect.y + 110, box_w, 520)
        r.draw_pixel_frame(screen, box, (36, 14, 18), (255, 70, 70), True, 1.0)

        hdr = r.font_title.render("⚠ ПРОТОКОЛ СЖИГАНИЯ ПРОЦЕССОРА ⚠", True, (255, 95, 85))
        screen.blit(hdr, (box.centerx - hdr.get_width() // 2, box.y + 44))

        prog = min(1.0, self.meltdown_timer / 3.2)
        temp_c = int(65 + prog * 1450)
        t_lbl = r.font_popup_big.render(f"ТЕМПЕРАТУРА ЯДРА: {temp_c} °C", True, (255, 220, 80))
        screen.blit(t_lbl, (box.centerx - t_lbl.get_width() // 2, box.y + 115))

        bar_r = pygame.Rect(box.x + 80, box.y + 180, box.width - 160, 40)
        pygame.draw.rect(screen, (18, 8, 12), bar_r)
        pygame.draw.rect(screen, (255, int(180 * (1.0 - prog)), 40), (bar_r.x + 3, bar_r.y + 3, int((bar_r.width - 6) * prog), bar_r.height - 6))
        pygame.draw.rect(screen, (255, 90, 90), bar_r, 2)

        stages = [
            "Отключение кулеров и испарение термопасты...",
            "Скрытый майнинг КрысКоинов для Трактирщика Гуго...",
            "Призыв огненного бога Пиро прямо на материнскую плату...",
            "КРИТИЧЕСКИЙ ПЕРЕГРЕВ! Выход через пару мгновений!"
        ]
        st_txt = stages[min(len(stages) - 1, int(prog * len(stages)))]
        st_s = r.font_title.render(st_txt, True, UI_TEXT_MAIN)
        screen.blit(st_s, (box.centerx - st_s.get_width() // 2, box.y + 255))

        b_cancel = pygame.Rect(box.x + 80, box.bottom - 110, 310, 62)
        b_quit = pygame.Rect(box.right - 390, box.bottom - 110, 310, 62)
        self.btn_rects["cancel_meltdown"] = b_cancel
        self.btn_rects["quit_now"] = b_quit

        hov_c = b_cancel.collidepoint(mouse_pos)
        r.draw_pixel_frame(screen, b_cancel, (42, 85, 52) if hov_c else (28, 58, 36), UI_BORDER_GOLD, hov_c, 1.0)
        cs = r.font_ui.render("ОЙ, ПОЩАДИ ПРОЦ!", True, (220, 255, 220))
        screen.blit(cs, (b_cancel.centerx - cs.get_width() // 2, b_cancel.centery - cs.get_height() // 2))

        hov_q = b_quit.collidepoint(mouse_pos)
        r.draw_pixel_frame(screen, b_quit, (135, 32, 38) if hov_q else (92, 22, 28), (255, 110, 110), hov_q, 1.0)
        qs = r.font_ui.render("СЖЕЧЬ МГНОВЕННО!", True, (255, 220, 210))
        screen.blit(qs, (b_quit.centerx - qs.get_width() // 2, b_quit.centery - qs.get_height() // 2))
