import math
import pygame
from elenor.config import VIEW_H, SCALE, SCREEN_W, SCREEN_H, UI_PANEL_BG, UI_SLOT_BG, UI_BORDER_OUTER, UI_BORDER_WOOD, UI_BORDER_GOLD, UI_BORDER_HIGHLIGHT, UI_TEXT_MAIN, UI_TEXT_DIM


class UIRendererMixin:
    def _draw_pixel_bar(self, screen, x, y, w, h, cur, maximum, fill_col):
        pygame.draw.rect(screen, UI_BORDER_OUTER, (x, y, w, h))
        pygame.draw.rect(screen, UI_BORDER_WOOD, (x + 2, y + 2, w - 4, h - 4))
        pygame.draw.rect(screen, (28, 18, 24), (x + 4, y + 4, w - 8, h - 8))
        ratio = max(0.0, min(1.0, cur / max(1, maximum)))
        fill_w = int((w - 8) * ratio)
        if fill_w > 0:
            pygame.draw.rect(screen, fill_col, (x + 4, y + 4, fill_w, h - 8))
            pygame.draw.rect(screen, (255, 255, 255), (x + 4, y + 4, fill_w, 3))
        txt = self.font_small.render(f"{cur}/{maximum}", True, UI_TEXT_MAIN)
        screen.blit(txt, (x + (w - txt.get_width()) // 2, y + 5))

    def _clean_perk_desc(self, raw_desc):
        """Strips redundant uppercase prefix like 'ЗАКЛИНАНИЕ (3 Маны | КД 1.4с): ' from perk descriptions."""
        if ":" in raw_desc:
            head, tail = raw_desc.split(":", 1)
            if any(k in head.upper() for k in ("ЗАКЛИНАНИЕ", "БОЕВОЙ ПРИЁМ", "ПАССИВНО", "АВТО-МАГИЯ")):
                return tail.strip()
        return raw_desc.strip()

    def _get_perk_progression_lines(self, player, pid, pdata, cur_lvl, target_lvl):
        """Returns concrete numerical stat lines (or Old -> New additive % comparisons from base) for levelup cards."""
        is_upgrade = (cur_lvl > 0 and target_lvl > cur_lvl)
        if pdata.get("type") == "active":
            is_combat = (pdata.get("skill_kind") == "combat")
            stat_add = player.phys_attack if is_combat else player.mag_attack
            existing_sp = next((h for h in player.ability_slots if h and h.id == pid), None)
            upg_roll = pdata.get("upgrade_roll", {})
            stat_labels = {
                "power": "Регенерация ХП" if pid == "persephone_rejuvenation" else ("Урон горения" if pid == "pyro_ignite" else "Урон"),
                "cooldown": "Перезарядка",
                "duration": "Длительность",
                "status_dur": "Время контроля",
                "aoe_radius": "Область",
                "bounces": "Отскоки",
            }
            if not is_upgrade or existing_sp is None:
                lines = []
                for st_k in pdata.get("upgradable_stats", ["power", "cooldown"]):
                    lbl = stat_labels.get(st_k, st_k)
                    val = pdata.get(st_k, 0)
                    if st_k == "power":
                        tot = int(math.floor(val + stat_add))
                        lines.append(f"{lbl}: {tot} ({int(val)}+{stat_add})")
                    elif st_k in ("cooldown", "duration", "status_dur"):
                        lines.append(f"{lbl}: {float(val):.2f}с")
                    elif st_k == "aoe_radius":
                        lines.append(f"{lbl}: {float(val):.1f}м")
                    elif st_k == "bounces":
                        lines.append(f"{lbl}: {int(val)}")
                return lines
            else:
                lines = []
                for st_k, add_pct in upg_roll.items():
                    lbl = stat_labels.get(st_k, st_k)
                    base_v = existing_sp.base_stats.get(st_k, pdata.get(st_k, 0))
                    old_pct = existing_sp.stat_bonuses_pct.get(st_k, 0.0)
                    new_pct = old_pct + add_pct
                    o_val = player.eval_stat_with_pct(pid, st_k, base_v, old_pct)
                    n_val = player.eval_stat_with_pct(pid, st_k, base_v, new_pct)
                    pct_int = int(round(add_pct * 100))
                    if st_k == "power":
                        o_tot = int(math.floor(o_val + stat_add))
                        n_tot = int(math.floor(n_val + stat_add))
                        lines.append(f"{lbl}: {o_tot} -> {n_tot} (+{pct_int}%)")
                    elif st_k in ("cooldown", "duration", "status_dur"):
                        lines.append(f"{lbl}: {o_val:.2f}с -> {n_val:.2f}с (+{pct_int}%)")
                    elif st_k == "aoe_radius":
                        lines.append(f"{lbl}: {o_val:.1f}м -> {n_val:.1f}м (+{pct_int}%)")
                    elif st_k == "bounces":
                        lines.append(f"{lbl}: {int(o_val)} -> {int(n_val)} (+{pct_int}%)")
                return lines

        # Passive perks numerical breakdown
        def fmt(label, per_lvl, unit="", is_float=False):
            if not is_upgrade:
                v = per_lvl * max(1, target_lvl)
                val_s = f"{v:.2f}" if is_float else f"{int(v)}"
                return f"{label}: + {val_s}{unit}" if per_lvl > 0 else f"{label}: {val_s}{unit}"
            v0 = per_lvl * cur_lvl
            v1 = per_lvl * target_lvl
            s0 = f"{v0:.2f}" if is_float else f"{int(v0)}"
            s1 = f"{v1:.2f}" if is_float else f"{int(v1)}"
            sign = "+" if per_lvl > 0 else ""
            return f"{label}: {sign}{s0}{unit} -> {sign}{s1}{unit}"

        if pid == "tough_skin":
            return [fmt("Макс. здоровье", 8, " ХП")]
        elif pid == "iron_grip":
            return [fmt("Физ. атака", 2, " ед.")]
        elif pid == "clear_mind":
            return [fmt("Маг. мощь", 2, " ед."), fmt("Макс. мана", 3, " МП")]
        elif pid == "cat_step":
            return [fmt("Шум шагов", -18, "%"), fmt("Уклонение", 5, "%")]
        elif pid == "keen_edge":
            return [fmt("Шанс крита", 8, "%"), fmt("Тело (Сила)", 1, " ед.")]
        elif pid == "stone_ribs":
            return [fmt("Физ. и Маг. броня", 3, " ед.")]
        elif pid == "blood_hunger":
            return [fmt("Вампиризм в бою", 2, " ХП")]
        elif pid == "titan_blood":
            return [fmt("Макс. здоровье", 18, " ХП"), fmt("Физ. броня", 3, " ед."), fmt("Реген ХП", 1.2, "/с", True)]
        elif pid == "storm_aura":
            if not is_upgrade:
                l_use = max(1, target_lvl)
                dmg = max(1, 1 + l_use + player.mag_attack // 4)
                cd = max(1.35, 3.0 - (l_use - 1) * 0.35)
                return [f"Урон авто-молнии: {dmg} ед.", f"Интервал разряда: {cd:.2f}с"]
            d0 = max(1, 1 + cur_lvl + player.mag_attack // 4)
            d1 = max(1, 1 + target_lvl + player.mag_attack // 4)
            c0 = max(1.35, 3.0 - (cur_lvl - 1) * 0.35)
            c1 = max(1.35, 3.0 - (target_lvl - 1) * 0.35)
            return [f"Урон молнии: {d0} -> {d1}", f"Интервал: {c0:.2f}с -> {c1:.2f}с"]
        return []

    def _render_passive_perk_tooltip(self, screen, player, passive_tuple, ui_texts, mouse_pos):
        from elenor.config import RARITY_COLORS
        pid, plvl, pdata = passive_tuple
        r_col = RARITY_COLORS.get(pdata.get("rarity", "common"), UI_BORDER_GOLD)
        rar_title = ui_texts["rarities"].get(pdata.get("rarity", "common"), "Особенность")

        lines = [(f"{rar_title} (Пассивный дар, Ур.{plvl})", r_col)]
        for st_line in self._get_perk_progression_lines(player, pid, pdata, plvl, plvl):
            lines.append((st_line, (125, 240, 155)))
        clean_d = self._clean_perk_desc(pdata.get("desc", ""))
        for d_ln in self.wrap_text(clean_d, self.font_small, 265):
            lines.append((d_ln, UI_TEXT_DIM))

        card_w = 295
        card_h = 46 + len(lines) * 19
        tx = max(16, min(SCREEN_W - card_w - 16, mouse_pos[0] - card_w // 2))
        ty = max(16, mouse_pos[1] - card_h - 18)

        self.draw_pixel_frame(screen, (tx, ty, card_w, card_h), (20, 17, 26), r_col, False, 1.0)
        screen.blit(self.font_ui.render(pdata.get("name", pid), True, r_col), (tx + 14, ty + 12))
        for i, (txt, col) in enumerate(lines):
            screen.blit(self.font_small.render(txt, True, col), (tx + 14, ty + 36 + i * 19))

    def _render_levelup_modal(self, screen, player, modal_data, ui_texts, hover_pos):
        from elenor.config import RARITY_COLORS
        choices = modal_data["choices"]
        lock_timer = modal_data.get("lock_timer", 0.0)
        is_erase_mode = modal_data.get("mode") == "erase"

        overlay = pygame.Surface((SCREEN_W, VIEW_H * SCALE), pygame.SRCALPHA)
        overlay.fill((8, 6, 14, 195))
        screen.blit(overlay, (0, 0))

        if is_erase_mode:
            banner_txt = "ПЕЧАТЬ ЗАБВЕНИЯ: ВЫБЕРИ ОСОБЕННОСТЬ ДЛЯ СТИРАНИЯ [ПКМ — Отмена]"
            b_col = (225, 120, 255)
        elif lock_timer > 0.0:
            banner_txt = f"НОВЫЙ УРОВЕНЬ ({player.level})! Защита от случайного клика: {lock_timer:.1f} сек..."
            b_col = (180, 175, 190)
        else:
            banner_txt = f"НОВЫЙ УРОВЕНЬ ({player.level})! ВЫБЕРИ ДАР [Акт: {len(player.active_perks)}/4]"
            b_col = UI_BORDER_HIGHLIGHT

        b_surf = self.font_title.render(banner_txt, True, b_col)
        screen.blit(b_surf, ((SCREEN_W - b_surf.get_width()) // 2, 42))

        self.perk_card_rects = []
        n_cards = len(choices)
        if n_cards == 0:
            return
        card_w = 215 if n_cards > 3 else 292
        card_h = 355
        gap = 14 if n_cards > 3 else 26
        total_w = n_cards * card_w + (n_cards - 1) * gap
        start_x = (SCREEN_W - total_w) // 2
        card_y = 88

        for idx, perk in enumerate(choices):
            rect = pygame.Rect(start_x + idx * (card_w + gap), card_y, card_w, card_h)
            self.perk_card_rects.append(rect)
            is_hov = rect.collidepoint(hover_pos) and (lock_timer <= 0.0)
            r_col = RARITY_COLORS.get(perk["rarity"], (215, 215, 220))

            self.draw_pixel_frame(screen, rect, (32, 26, 42) if is_hov else (22, 18, 30), r_col, is_hov, 1.0)

            k_lbl = self.font_ui.render(f"[{idx + 1}]", True, UI_BORDER_HIGHLIGHT)
            screen.blit(k_lbl, (rect.x + 12, rect.y + 12))

            cur_lvl = player.perks.get(perk["id"], 0)
            if is_erase_mode:
                lvl_str = f"СТЕРЕТЬ (Ур.{cur_lvl})"
                l_col = (255, 95, 95)
            else:
                lvl_str = f"Ур.{cur_lvl} -> {cur_lvl + 1}" if cur_lvl > 0 else ("АКТИВ [Q/E/R/F]" if perk.get("type") == "active" else "ПАССИВ")
                l_col = (130, 240, 160) if cur_lvl > 0 else ((110, 210, 255) if perk.get("type") == "active" else UI_TEXT_DIM)

            l_surf = self.font_small.render(lvl_str, True, l_col)
            screen.blit(l_surf, (rect.right - 12 - l_surf.get_width(), rect.y + 14))

            ic_box = pygame.Rect(rect.centerx - 28, rect.y + 42, 56, 56)
            self.draw_pixel_frame(screen, ic_box, UI_SLOT_BG, r_col, False, 1.0)
            self.draw_item_icon(screen, perk["icon"], ic_box.x + 12, ic_box.y + 12, 32)

            n_surf = self.font_ui.render(perk["name"][:22], True, r_col)
            screen.blit(n_surf, (rect.centerx - n_surf.get_width() // 2, rect.y + 108))

            rar_name = ui_texts["rarities"].get(perk["rarity"], perk["rarity"])
            r_surf = self.font_small.render(rar_name, True, UI_TEXT_DIM)
            screen.blit(r_surf, (rect.centerx - r_surf.get_width() // 2, rect.y + 128))

            pygame.draw.line(screen, r_col, (rect.x + 16, rect.y + 150), (rect.right - 16, rect.y + 150), 1)

            # Numerical stat lines / Old -> New upgrade preview!
            target_lvl = cur_lvl if is_erase_mode else (cur_lvl + 1)
            stat_lines = self._get_perk_progression_lines(player, perk["id"], perk, cur_lvl, target_lvl)
            cur_y = rect.y + 160
            for st_ln in stat_lines:
                st_col = (115, 245, 145) if cur_lvl > 0 and not is_erase_mode else (255, 215, 110)
                st_s = self.font_small.render(st_ln[:28], True, st_col)
                screen.blit(st_s, (rect.centerx - st_s.get_width() // 2, cur_y))
                cur_y += 18

            cur_y += 6
            clean_desc = self._clean_perk_desc(perk.get("desc", ""))
            desc_lines = self.wrap_text(clean_desc, self.font_small, card_w - 26)
            for ln in desc_lines[:5]:
                if cur_y + 16 > rect.bottom - 10:
                    break
                d_s = self.font_small.render(ln, True, UI_TEXT_MAIN)
                screen.blit(d_s, (rect.centerx - d_s.get_width() // 2, cur_y))
                cur_y += 18

    def _render_character_sheet_modal(self, screen, player, ui_texts, hover_pos, drag_item):
        win_w, win_h = 960, 510
        wx = (SCREEN_W - win_w) // 2
        wy = (VIEW_H * SCALE - win_h) // 2 + 20
        self.modal_rect = pygame.Rect(wx, wy, win_w, win_h)

        self.draw_pixel_frame(screen, self.modal_rect, UI_PANEL_BG, UI_BORDER_GOLD, False, 1.0)
        journal_open = ui_texts.get("_journal_open", False)

        # Кнопка переключения между Куклой Героя и Журналом в правом верхнем углу окна инвентаря
        self.journal_btn_rect = pygame.Rect(wx + win_w - 224, wy + 10, 204, 32)
        j_hov = self.journal_btn_rect.collidepoint(hover_pos)
        j_bg = (58, 46, 40) if (j_hov or journal_open) else UI_SLOT_BG
        self.draw_pixel_frame(screen, self.journal_btn_rect, j_bg, UI_BORDER_GOLD, j_hov or journal_open, 1.0)
        j_lbl_txt = "НАЗАД К ГЕРОЮ" if journal_open else "ЖУРНАЛ ЗАПИСЕЙ [J]"
        j_lbl = self.font_small.render(j_lbl_txt, True, (255, 230, 110) if journal_open else UI_TEXT_MAIN)
        screen.blit(j_lbl, (self.journal_btn_rect.centerx - j_lbl.get_width() // 2, self.journal_btn_rect.centery - j_lbl.get_height() // 2))

        if journal_open:
            self._render_journal_view(screen, wx, wy, win_w, win_h, ui_texts, hover_pos)
            return

        title = self.font_title.render(f"{ui_texts['inv_title']} — {player.full_name} ({ui_texts['lvl']} {player.level})", True, UI_BORDER_HIGHLIGHT)
        screen.blit(title, (wx + 24, wy + 16))

        col1_rect = pygame.Rect(wx + 18, wy + 48, 250, 418)
        self.draw_pixel_frame(screen, col1_rect, UI_SLOT_BG, UI_BORDER_WOOD, False, 1.0)

        xp_txt = self.font_small.render(f"{ui_texts['xp']}: {player.xp} / {player.max_xp}", True, (245, 205, 80))
        screen.blit(xp_txt, (col1_rect.x + 16, col1_rect.y + 14))
        pygame.draw.rect(screen, (14, 12, 18), (col1_rect.x + 16, col1_rect.y + 34, 218, 10))
        ratio = min(1.0, player.xp / max(1, player.max_xp))
        pygame.draw.rect(screen, (235, 185, 55), (col1_rect.x + 17, col1_rect.y + 35, int(216 * ratio), 8))

        self.stat_plus_rects = {}
        primary_stats = [
            ("body", ui_texts["body"], player.body, (235, 145, 130)),
            ("cunning", ui_texts["cunning"], player.cunning, (135, 230, 165)),
            ("mind", ui_texts["mind"], player.mind, (150, 200, 255)),
        ]
        for idx, (st_key, st_label, st_val, st_col) in enumerate(primary_stats):
            ry = col1_rect.y + 56 + idx * 38
            pygame.draw.rect(screen, (32, 27, 38), (col1_rect.x + 14, ry, 222, 32))
            pygame.draw.rect(screen, (75, 62, 55), (col1_rect.x + 14, ry, 222, 32), 1)
            screen.blit(self.font_ui.render(st_label, True, UI_TEXT_MAIN), (col1_rect.x + 20, ry + 7))
            screen.blit(self.font_title.render(str(st_val), True, st_col), (col1_rect.x + 166, ry + 6))

        ledger_y = col1_rect.y + 180
        pygame.draw.line(screen, UI_BORDER_WOOD, (col1_rect.x + 14, ledger_y - 6), (col1_rect.right - 14, ledger_y - 6), 2)
        derived = [
            (ui_texts["phys_atk"], f"{player.phys_attack} (Крит {int(player.crit_chance*100)}%)"),
            (ui_texts["mag_atk"], f"+{player.mag_attack} (Удар +{player.mp_on_hit:.1f} МП)"),
            (ui_texts["phys_def"], f"{player.phys_defense} ед."),
            (ui_texts["mag_def"], f"{player.mag_defense} ед."),
            ("Уклонение", f"{int(player.dodge_chance*100)}%"),
            (ui_texts["noise"], f"{int(player.noise_factor*100)}%"),
            (ui_texts["vision"], f"{int(player.torch_light_radius)}/{int(player.dark_vision_radius)}"),
            ("Способности", f"Акт:{len(player.active_perks)}/4"),
        ]
        for idx, (k_txt, v_txt) in enumerate(derived):
            ly = ledger_y + idx * 27
            if idx % 2 == 0:
                pygame.draw.rect(screen, (28, 24, 34), (col1_rect.x + 14, ly - 2, 222, 24))
            screen.blit(self.font_small.render(k_txt, True, UI_TEXT_DIM), (col1_rect.x + 18, ly + 2))
            v_surf = self.font_small.render(v_txt, True, UI_TEXT_MAIN)
            screen.blit(v_surf, (col1_rect.right - 18 - v_surf.get_width(), ly + 2))

        col2_rect = pygame.Rect(wx + 278, wy + 48, 274, 418)
        self.draw_pixel_frame(screen, col2_rect, UI_SLOT_BG, UI_BORDER_WOOD, False, 1.0)

        ped_rect = pygame.Rect(col2_rect.x + 89, col2_rect.y + 104, 96, 116)
        self.draw_pixel_frame(screen, ped_rect, (18, 15, 22), UI_BORDER_WOOD, False, 1.0)
        h_diff, _ = self.get_hero_pair(player)
        big_hero = pygame.transform.scale(h_diff, (16 * 4, 20 * 4))
        screen.blit(big_hero, (ped_rect.x + 16, ped_rect.y + 18))

        cx = col2_rect.x + 137
        cy = col2_rect.y + 162
        doll_layout = {
            "helmet":     pygame.Rect(cx - 32, col2_rect.y + 18, 64, 68),
            "trinket":    pygame.Rect(col2_rect.right - 80, col2_rect.y + 18, 64, 68),
            "right_hand": pygame.Rect(col2_rect.x + 16, cy - 42, 64, 68),
            "left_hand":  pygame.Rect(col2_rect.right - 80, cy - 42, 64, 68),
            "torso":      pygame.Rect(cx - 32, cy + 68, 64, 68),
            "ring_1":     pygame.Rect(col2_rect.x + 16, cy + 42, 64, 68),
            "ring_2":     pygame.Rect(col2_rect.right - 80, cy + 42, 64, 68),
            "boots":      pygame.Rect(cx - 32, col2_rect.bottom - 82, 64, 68),
            "bag":        pygame.Rect(col2_rect.x + 16, col2_rect.bottom - 82, 64, 68),
        }
        self.equip_slot_rects = doll_layout
        hovered_item = None
        hovered_from_inventory = False

        main_weap = player.equipment["right_hand"]
        two_hand_active = main_weap is not None and main_weap.two_handed

        for s_key, s_rect in doll_layout.items():
            is_hov = s_rect.collidepoint(hover_pos)
            itm = player.equipment.get(s_key) if s_key != "bag" else None
            bd_col = itm.rarity_color if itm else UI_BORDER_WOOD
            self.draw_pixel_frame(screen, s_rect, UI_PANEL_BG, bd_col, is_hov, 1.0)

            lbl_str = ui_texts["slots"][s_key][:8]
            lbl_s = self.font_small.render(lbl_str, True, UI_TEXT_DIM)
            screen.blit(lbl_s, (s_rect.x + (s_rect.width - lbl_s.get_width()) // 2, s_rect.y + 48))

            if s_key == "bag":
                ic = "bag_big" if player.unlocked_slots >= 15 else ("bag_small" if player.unlocked_slots >= 6 else None)
                if ic:
                    self.draw_item_icon(screen, ic, s_rect.x + 16, s_rect.y + 10, 32)
            elif s_key == "left_hand" and two_hand_active:
                self.draw_item_icon(screen, main_weap.icon, s_rect.x + 16, s_rect.y + 10, 32)
                lk = self.font_small.render("2H", True, (220, 120, 120))
                screen.blit(lk, (s_rect.x + 8, s_rect.y + 8))
            elif itm:
                self.draw_item_icon(screen, itm.icon, s_rect.x + 16, s_rect.y + 10, 32)
                if is_hov:
                    hovered_item = itm
                    hovered_from_inventory = False

        col3_rect = pygame.Rect(wx + 562, wy + 48, 380, 418)
        self.draw_pixel_frame(screen, col3_rect, UI_SLOT_BG, UI_BORDER_WOOD, False, 1.0)
        p_head = self.font_ui.render(f"{player.bag_name} [{player.unlocked_slots}/24]", True, UI_BORDER_HIGHLIGHT)
        screen.blit(p_head, (col3_rect.x + 16, col3_rect.y + 12))

        self.inv_slot_rects = []
        grid_x, grid_y = col3_rect.x + 14, col3_rect.y + 38

        for idx in range(player.max_possible_slots):
            col = idx % 4
            row = idx // 4
            sr = pygame.Rect(grid_x + col * 89, grid_y + row * 61, 84, 57)
            self.inv_slot_rects.append(sr)
            unlocked = idx < player.unlocked_slots
            is_hov = sr.collidepoint(hover_pos) and unlocked

            if not unlocked:
                self.draw_pixel_frame(screen, sr, (16, 14, 20), (55, 45, 50), False, 1.0)
                self.draw_item_icon(screen, "lock", sr.x + 26, sr.y + 12, 32)
            else:
                itm = player.inventory[idx]
                bd_col = itm.rarity_color if itm else UI_BORDER_WOOD
                self.draw_pixel_frame(screen, sr, UI_PANEL_BG, bd_col, is_hov, 1.0)
                if itm:
                    self.draw_item_icon(screen, itm.icon, sr.x + 26, sr.y + 6, 32)
                    short_name = itm.name.split(" ")[0][:8]
                    nm = self.font_small.render(short_name, True, itm.rarity_color)
                    screen.blit(nm, (sr.x + (sr.width - nm.get_width()) // 2, sr.y + 38))
                    if is_hov:
                        hovered_item = itm
                        hovered_from_inventory = True

        hint_s = self.font_small.render("ЛКМ — Использовать/Надеть | Цифры [1-4] — Расходник на пояс | ПКМ — Выбросить", True, UI_TEXT_DIM)
        screen.blit(hint_s, (wx + (win_w - hint_s.get_width()) // 2, wy + win_h - 26))

        if drag_item:
            self.draw_item_icon(screen, drag_item.icon, hover_pos[0] - 16, hover_pos[1] - 16, 32)
        elif hovered_item:
            self._render_item_tooltip(screen, player, hovered_item, ui_texts, hover_pos, compare=hovered_from_inventory)

    def _render_journal_view(self, screen, wx, wy, win_w, win_h, ui_texts, hover_pos):
        title = self.font_title.render("ЖУРНАЛ ПОХОДА (ПОСЛЕДНИЕ 100 ЗАПИСЕЙ)", True, UI_BORDER_HIGHLIGHT)
        screen.blit(title, (wx + 24, wy + 16))

        filters = ui_texts.get("_journal_filters", {"combat": True, "event": True, "speech": True})
        logs = ui_texts.get("_journal_logs", [])
        scroll = int(ui_texts.get("_journal_scroll", 0))

        # Панель из 3 чекбоксов фильтрации
        filter_defs = [
            ("combat", "Боевые логи", (245, 135, 125)),
            ("event",  "События",     (245, 215, 110)),
            ("speech", "Реплики",     (135, 215, 255)),
        ]
        self.journal_filter_rects = {}
        fx_cur = wx + 24
        fy_cur = wy + 50
        for f_key, f_name, f_col in filter_defs:
            f_rect = pygame.Rect(fx_cur, fy_cur, 195, 32)
            self.journal_filter_rects[f_key] = f_rect
            is_on = filters.get(f_key, True)
            hov = f_rect.collidepoint(hover_pos)
            bg = (36, 48, 40) if is_on else (28, 22, 30)
            if hov:
                bg = (48, 64, 52) if is_on else (40, 30, 42)
            pygame.draw.rect(screen, bg, f_rect, border_radius=4)
            pygame.draw.rect(screen, f_col if is_on else UI_BORDER_WOOD, f_rect, 1, border_radius=4)
            mark = "[✓]" if is_on else "[ ]"
            txt_s = self.font_small.render(f"{mark} {f_name}", True, f_col if is_on else UI_TEXT_DIM)
            screen.blit(txt_s, (f_rect.x + 12, f_rect.y + 8))
            fx_cur += 208

        filtered_logs = [entry for entry in logs if filters.get(entry["cat"], True)]
        cnt_s = self.font_small.render(f"Записей: {len(filtered_logs)} / {len(logs)}", True, UI_TEXT_DIM)
        screen.blit(cnt_s, (wx + win_w - cnt_s.get_width() - 28, fy_cur + 8))

        game = ui_texts.get("_game_ref")
        list_top = wy + 90
        if game is not None:
            labels = game.loc["run_seed"]
            rect = pygame.Rect(wx + win_w - 216, list_top, 190, 32)
            self.journal_seed_rect = rect
            hover = rect.collidepoint(hover_pos)
            self.draw_pixel_frame(screen, rect, UI_SLOT_BG, UI_BORDER_GOLD, hover, 1.0)
            message = game.seed_copy_message if pygame.time.get_ticks() < game.seed_copy_until else "copy"
            text = self.font_small.render(labels[message], True, UI_TEXT_MAIN)
            screen.blit(text, text.get_rect(center=rect.center))
            seed = self.font_ui.render(f'{labels["label"]}  {game.run_seed}', True, UI_TEXT_DIM)
            screen.blit(seed, seed.get_rect(midleft=(wx + 24, rect.centery)))
            list_top = rect.bottom + 8

        # Основное поле списка записей
        box_rect = pygame.Rect(wx + 20, list_top, win_w - 40, wy + win_h - 40 - list_top)
        self.draw_pixel_frame(screen, box_rect, UI_SLOT_BG, UI_BORDER_WOOD, False, 1.0)

        tag_map = {
            "combat": ("[БОЙ]",     (245, 130, 120)),
            "event":  ("[СОБЫТИЕ]", (245, 215, 105)),
            "speech": ("[РЕПЛИКА]", (130, 215, 255)),
        }

        # Разбиваем отфильтрованные записи на строки с переносом
        rendered_rows = []
        max_text_w = box_rect.width - 145
        for entry in filtered_logs:
            cat = entry["cat"]
            tag_str, tag_col = tag_map.get(cat, ("[ЛОГ]", UI_TEXT_DIM))
            col = entry.get("color") or tag_col
            wrapped = self.wrap_text(entry["text"], self.font_small, max_text_w)
            for idx_w, ln in enumerate(wrapped):
                rendered_rows.append((tag_str if idx_w == 0 else "", tag_col, ln, col))

        line_h = 20
        vis_rows = (box_rect.height - 20) // line_h
        max_scroll = max(0, len(rendered_rows) - vis_rows)
        scroll = max(0, min(max_scroll, scroll))

        start_idx = max(0, len(rendered_rows) - vis_rows - scroll)
        end_idx = len(rendered_rows) - scroll
        visible_slice = rendered_rows[start_idx:end_idx]

        row_y = box_rect.y + 12
        for tag_str, tag_col, ln_txt, ln_col in visible_slice:
            if tag_str:
                t_s = self.font_small.render(tag_str, True, tag_col)
                screen.blit(t_s, (box_rect.x + 14, row_y))
            l_s = self.font_small.render(ln_txt, True, ln_col)
            screen.blit(l_s, (box_rect.x + 110, row_y))
            row_y += line_h

        # Ползунок прокрутки справа
        if max_scroll > 0:
            track_x = box_rect.right - 14
            track_y = box_rect.y + 10
            track_h = box_rect.height - 20
            pygame.draw.rect(screen, (14, 12, 18), (track_x, track_y, 6, track_h))
            thumb_h = max(24, int(track_h * (vis_rows / max(1, len(rendered_rows)))))
            scroll_ratio = 1.0 - (scroll / max(1, max_scroll))
            thumb_y = track_y + int((track_h - thumb_h) * scroll_ratio)
            pygame.draw.rect(screen, UI_BORDER_GOLD, (track_x, thumb_y, 6, thumb_h), border_radius=2)

        hint_s = self.font_small.render("Колесо мыши — Прокрутка журнала | Галочки сверху — Фильтр категорий | [J] — Закрыть журнал", True, UI_TEXT_DIM)
        screen.blit(hint_s, (wx + (win_w - hint_s.get_width()) // 2, wy + win_h - 26))

    def _build_item_stat_lines(self, player, item, ui_texts, comp_item=None):
        from elenor.data.economy import format_copper_Trigger
        raw_lines = []
        max_w = 276  # Гарантированный отступ внутри карточки шириной 308 px

        def add_wrapped(text, color):
            for ln in self.wrap_text(str(text), self.font_small, max_w):
                raw_lines.append((ln, color))

        rarity_title = ui_texts["rarities"].get(item.rarity, item.rarity)
        if item.two_handed:
            rarity_title += " • Двуручное"
        elif item.weap_style == "thrown":
            rarity_title += " • Метательное"
        add_wrapped(rarity_title, item.rarity_color)

        # Лаконичный формат для Драгоценностей и Монет
        if item.type in ("gem", "currency_coin"):
            add_wrapped(format_copper_Trigger(item.copper_value), UI_BORDER_HIGHLIGHT)
            add_wrapped("Драгоценность." if item.type == "gem" else "Монеты.", UI_TEXT_MAIN)
            add_wrapped(item.desc, UI_TEXT_DIM)
            return raw_lines

        if getattr(item, "heal_hp", 0) > 0:
            eff_heal = player.get_heal_amount(item)
            bonus_tag = " (+25% Ипохондрик)" if eff_heal > item.heal_hp else ""
            add_wrapped(f"Исцеление: +{eff_heal} ХП{bonus_tag}", UI_TEXT_MAIN)

        if getattr(item, "god", ""):
            add_wrapped(f"Покровитель: {item.god}", UI_BORDER_HIGHLIGHT)

        if item.type == "consumable_spell":
            tot_scroll = int(math.floor(item.power * 1.65 + player.mag_attack * 1.5))
            add_wrapped(f"Одноразовый свиток (КД {item.cooldown:.1f}с) — Урон {tot_scroll}", UI_TEXT_MAIN)
        elif item.type == "permanent_spell":
            tot_spell = int(math.floor(item.power + player.mag_attack))
            pwr_lbl = "Исцеление" if item.id == "persephone_rejuvenation" else ("Урон горения" if item.id == "pyro_ignite" else "Урон")
            add_wrapped(f"Заклинание ({item.mp_cost} Маны | КД {item.cooldown:.2f}с) — {pwr_lbl} {tot_spell}", UI_TEXT_MAIN)
        elif item.type == "combat_skill":
            tot_skill = int(math.floor(item.power + player.phys_attack))
            add_wrapped(f"Боевой приём (0 Маны | КД {item.cooldown:.2f}с) — Урон {tot_skill}", UI_TEXT_MAIN)

        if item.type in ("consumable_spell", "permanent_spell", "combat_skill"):
            if getattr(item, "duration", 0.0) > 0.0:
                add_wrapped(f"Длительность: {item.duration:.2f} сек.", UI_TEXT_MAIN)
            if getattr(item, "status_dur", 0.0) > 0.0:
                add_wrapped(f"Время контроля: {item.status_dur:.2f} сек.", UI_TEXT_MAIN)
            if getattr(item, "aoe_radius", 0.0) > 0.0 and item.cast_type in ("frost_nova", "entangle_cursor", "aoe_cursor"):
                add_wrapped(f"Радиус области: {item.aoe_radius:.1f} м", UI_TEXT_MAIN)
            if item.cast_type == "chain_lightning":
                add_wrapped(f"Макс. отскоков молнии: {int(item.bounces)}", UI_TEXT_MAIN)

        # Основные числовые бонусы экипировки (в едином спокойном цвете UI_TEXT_MAIN)
        stat_pairs = [
            ("phys_bonus", ui_texts["phys_atk"]),
            ("mag_bonus", ui_texts["mag_atk"]),
            ("phys_def", ui_texts["phys_def"]),
            ("mag_def", ui_texts["mag_def"]),
            ("vision_bonus", ui_texts["vision"]),
        ]
        for attr, label in stat_pairs:
            val = getattr(item, attr, 0)
            old_val = getattr(comp_item, attr, 0) if comp_item else 0
            diff = val - old_val
            if val != 0 or (comp_item and diff != 0):
                base_str = f"{label}: {'+' if val > 0 else ''}{val}"
                if comp_item is not None and diff != 0:
                    d_str = f" ({'+' if diff > 0 else ''}{diff})"
                    col = (100, 240, 120) if diff > 0 else (255, 105, 105)
                    add_wrapped(base_str + d_str, col)
                else:
                    add_wrapped(base_str, UI_TEXT_MAIN)

        if getattr(item, "dmg_min", 0) > 0:
            # С учётом вклада характеристик героя
            scale_k = 1.35 if item.two_handed else 1.0
            stat_add = int(round(player.phys_attack * scale_k))
            total_min = item.dmg_min + stat_add
            total_max = item.dmg_max + stat_add
            add_wrapped(f"Урон: {total_min}–{total_max}", UI_TEXT_MAIN)

        if item.armor_pierce > 0:
            add_wrapped(f"Пролом брони: +{item.armor_pierce}", UI_TEXT_MAIN)
        if getattr(item, "crit_bonus", 0.0) > 0:
            add_wrapped(f"Шанс крита: +{int(round(item.crit_bonus * 100))}%", UI_TEXT_MAIN)
        if item.life_steal > 0:
            add_wrapped(f"Вампиризм: +{item.life_steal} ХП", UI_TEXT_MAIN)

        n_val = int(item.noise_mod * 100)
        n_old = int(comp_item.noise_mod * 100) if comp_item else 0
        n_diff = n_val - n_old
        if n_val != 0 or (comp_item and n_diff != 0):
            b_str = f"{ui_texts['noise']}: {'+' if n_val > 0 else ''}{n_val}%"
            if comp_item is not None and n_diff != 0:
                d_str = f" ({'+' if n_diff > 0 else ''}{n_diff}%)"
                col = (100, 240, 120) if n_diff < 0 else (255, 105, 105)
                add_wrapped(b_str + d_str, col)
            else:
                add_wrapped(b_str, UI_TEXT_MAIN)

        if item.is_torch:
            add_wrapped("Источник вечного огня [Клавиша F]", UI_BORDER_HIGHLIGHT)
        if getattr(item, "armor_class", "none") == "cloth":
            add_wrapped("Поток маны — +1 МП за удар и с осколков", UI_BORDER_HIGHLIGHT)

        # Уникальное свойство оружия без слова «Фишка:» и без двойных двоеточий
        if getattr(item, "feature_tag", ""):
            clean_feat = item.feature_tag.replace(": ", " — ", 1)
            add_wrapped(clean_feat, UI_BORDER_HIGHLIGHT)

        clean_desc = self._clean_perk_desc(item.desc)
        if clean_desc:
            add_wrapped(clean_desc, UI_TEXT_DIM)
        return raw_lines

    def _render_item_tooltip(self, screen, player, item, ui_texts, mouse_pos, compare=False, world_item=False):
        comp_item = player.get_comparison_item(item) if compare else None
        main_lines = self._build_item_stat_lines(player, item, ui_texts, comp_item)

        card_w = 308
        card_h = 48 + len(main_lines) * 19

        if world_item:
            tx, ty = 16, 16
            cx = tx + card_w + 8
        else:
            ty = max(16, min(SCREEN_H - card_h - 16, mouse_pos[1] - card_h // 2))
            total_w = card_w * 2 + 8 if comp_item else card_w
            if mouse_pos[0] + 18 + total_w > SCREEN_W - 12:
                tx = max(16, mouse_pos[0] - card_w - 16)
                cx = max(8, tx - card_w - 8)
            else:
                tx = mouse_pos[0] + 18
                cx = tx + card_w + 8

        self.draw_pixel_frame(screen, (tx, ty, card_w, card_h), (20, 17, 26), item.rarity_color, False, 1.0)
        screen.blit(self.font_ui.render(item.name, True, item.rarity_color), (tx + 14, ty + 12))
        for i, (txt, col) in enumerate(main_lines):
            screen.blit(self.font_small.render(txt, True, col), (tx + 14, ty + 36 + i * 19))

        if comp_item:
            comp_lines = self._build_item_stat_lines(player, comp_item, ui_texts, None)
            ch = 48 + len(comp_lines) * 19
            self.draw_pixel_frame(screen, (cx, ty, card_w, ch), (18, 15, 22), comp_item.rarity_color, False, 1.0)
            screen.blit(self.font_ui.render(f"[Надето] {comp_item.name}", True, comp_item.rarity_color), (cx + 14, ty + 12))
            for i, (txt, col) in enumerate(comp_lines):
                screen.blit(self.font_small.render(txt, True, col), (cx + 14, ty + 36 + i * 19))
