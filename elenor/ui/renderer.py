import math
from collections import Counter
import pygame
from elenor.data.abilities import (
    PASSIVES, PASSIVE_SLOT_LIMIT, VECTOR_COLORS, acquisition_bonuses, passive_power_at, perk_branch,
)
from elenor.config import VIEW_H, SCALE, SCREEN_W, SCREEN_H, TILE_W, UI_PANEL_BG, UI_SLOT_BG, UI_BORDER_OUTER, UI_BORDER_WOOD, UI_BORDER_GOLD, UI_BORDER_HIGHLIGHT, UI_TEXT_MAIN, UI_TEXT_DIM, RARITY_COLORS, COIN_TEXT_COLOR
from elenor.entities.objects import JUNGLE_KEY_COLORS


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
                stats = pdata.get("upgradable_stats", ["power", "cooldown"])
                bonuses = acquisition_bonuses(pdata.get("rarity", "common"), stats)
                for st_k in stats:
                    lbl = stat_labels.get(st_k, st_k)
                    val = (getattr(existing_sp, st_k) if existing_sp is not None
                           else player.eval_stat_with_pct(pid, st_k, pdata.get(st_k, 0), bonuses[st_k]))
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

        if pid in PASSIVES:
            bonus = player.passive_bonuses.get(pid, 0.0)
            if not cur_lvl:
                bonus = acquisition_bonuses(pdata.get("rarity", "common"), ["power"])["power"]
            unit, factor = (" с", 1) if pid == "warding_pulse" else ("%", 100)

            def format_power(total_bonus):
                value = passive_power_at(pid, total_bonus) * factor
                return f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",") + unit

            amount = format_power(bonus)
            if is_upgrade:
                amount += f" → {format_power(bonus + pdata.get('upgrade_roll', {}).get('power', 0.0))}"
            return [f"{pdata.get('stat_label', 'Эффект')}: {amount}"]
        return []

    def _render_passive_perk_tooltip(self, screen, player, passive_tuple, mouse_pos):
        pid, plvl, pdata = passive_tuple
        r_col = VECTOR_COLORS.get(perk_branch(pid, pdata), UI_BORDER_WOOD)
        lines = [(f"Пассивный дар · Ур. {plvl}", r_col)]
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

    def _draw_rarity_glow(self, screen, rect, tier, color, time, hovered):
        if tier == 0:
            return
        # Soft pixels outside the card, with stronger glints at higher ranks.
        glow_w = 3 + 3 * tier
        key = rect.size, tier, color, hovered
        cache = self.perk_glow_cache
        if key not in cache:
            glow = pygame.Surface(rect.inflate(2 * glow_w, 2 * glow_w).size, pygame.SRCALPHA)
            inner = pygame.Rect(glow_w, glow_w, *rect.size)
            for offset in range(glow_w, 0, -1):
                strength = (1.0 - offset / (glow_w + 1)) ** 2
                alpha = int((18 + 11 * tier + 16 * hovered) * strength)
                pygame.draw.rect(glow, (*color, alpha), inner.inflate(2 * offset, 2 * offset), 1, border_radius=6)
            cache[key] = glow
        screen.blit(cache[key], rect.move(-glow_w, -glow_w))

        rim = rect.inflate(-13, -13)
        for index in range((0, 3, 6, 11, 17)[tier]):
            side = index % 4
            along = (index * 0.381966 + time * (0.055 + tier * 0.009)) % 1.0
            offset = 3 + (index * 5 % (glow_w - 2))
            wave = 0.5 + 0.5 * math.sin(time * 2.4 + index * 2.39)
            if side < 2:
                x = round(rect.left + along * rect.width)
                y = rect.top - offset if side == 0 else rect.bottom + offset
            else:
                x = rect.left - offset if side == 2 else rect.right + offset
                y = round(rect.top + along * rect.height)
            brightness = 0.39 + 0.48 * wave
            spark = tuple(int(channel * brightness) for channel in color)
            radius = 1 + int(tier >= 3 and wave > 0.45) + int(tier == 4 and wave > 0.8)
            pygame.draw.line(screen, spark, (x - radius, y), (x + radius, y))
            pygame.draw.line(screen, spark, (x, y - radius), (x, y + radius))
            if radius >= 2:
                screen.set_at((x, y), tuple((255 + c) // 2 for c in color))
        if tier >= 3:
            for x, direction in ((rim.left, 1), (rim.right, -1)):
                for y, inward in ((rim.top, 1), (rim.bottom, -1)):
                    arm = 9 if tier == 3 else 15
                    pygame.draw.lines(screen, color, False, [
                        (x, y + inward * arm), (x, y + inward * 3),
                        (x + direction * 3, y), (x + direction * arm, y),
                    ], 2)
                    if tier == 4:
                        pygame.draw.polygon(screen, (255, 230, 158), [
                            (x, y - 3), (x + 3, y), (x, y + 3), (x - 3, y),
                        ])

    def _render_levelup_modal(self, screen, player, modal_data, ui_texts, hover_pos):
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
            banner_txt = f"НОВЫЙ УРОВЕНЬ ({player.level})! ВЫБЕРИ ДАР  ·  Активные {len(player.active_perks)}/4  ·  Пассивные {len(player.passive_perks)}/{PASSIVE_SLOT_LIMIT}"
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
        per_row = 5 if is_erase_mode else n_cards
        time = pygame.time.get_ticks() / 1000.0
        for idx, perk in enumerate(choices):
            row, column = divmod(idx, per_row)
            row_cards = min(per_row, n_cards - row * per_row)
            total_w = row_cards * card_w + (row_cards - 1) * gap
            x = (SCREEN_W - total_w) // 2 + column * (card_w + gap)
            rect = pygame.Rect(x, 88 + row * (card_h + gap), card_w, card_h)
            self.perk_card_rects.append(rect)
            is_hov = rect.collidepoint(hover_pos) and (lock_timer <= 0.0)
            rarity = perk.get("rarity", "common")
            if is_erase_mode:
                r_col = VECTOR_COLORS.get(perk_branch(perk["id"], perk), UI_BORDER_WOOD)
                tier = 0
            else:
                r_col = RARITY_COLORS[rarity]
                tier = tuple(RARITY_COLORS).index(rarity)

            self.draw_pixel_frame(screen, rect, (32, 26, 42) if is_hov else (22, 18, 30), r_col, False, 1.0)

            self._draw_rarity_glow(screen, rect, tier, r_col, time, is_hov)

            k_lbl = self.font_ui.render(f"[{idx + 1}]", True, UI_BORDER_HIGHLIGHT)
            screen.blit(k_lbl, (rect.x + 12, rect.y + 12))

            cur_lvl = player.perks.get(perk["id"], 0)
            if is_erase_mode:
                lvl_str = "СТЕРЕТЬ"
                l_col = (255, 95, 95)
            else:
                lvl_str = "УЛУЧШЕНИЕ" if cur_lvl > 0 else "НОВАЯ"
                l_col = UI_TEXT_MAIN

            l_surf = self.font_small.render(lvl_str, True, l_col)
            screen.blit(l_surf, (rect.right - 12 - l_surf.get_width(), rect.y + 14))

            ic_box = pygame.Rect(rect.centerx - 28, rect.y + 42, 56, 56)
            self.draw_pixel_frame(screen, ic_box, UI_SLOT_BG, r_col, False, 1.0)
            self.draw_item_icon(screen, perk["icon"], ic_box.x + 12, ic_box.y + 12, 32)

            n_surf = self.font_ui.render(perk["name"], True, r_col)
            if n_surf.get_width() > rect.width - 24:
                n_surf = self.font_small.render(perk["name"], True, r_col)
            screen.blit(n_surf, (rect.centerx - n_surf.get_width() // 2, rect.y + 108))

            ability_type = "Активная" if perk.get("type") == "active" else "Пассивная"
            type_surf = self.font_small.render(ability_type, True, UI_TEXT_DIM)
            screen.blit(type_surf, type_surf.get_rect(midright=(rect.right - 12, rect.y + 34)))
            if not is_erase_mode:
                rar_name = ui_texts["perk_ranks"][rarity]
                r_surf = self.font_small.render(rar_name, True, r_col)
                screen.blit(r_surf, (rect.centerx - r_surf.get_width() // 2, rect.y + 128))

            pygame.draw.line(screen, r_col, (rect.x + 16, rect.y + 150), (rect.right - 16, rect.y + 150), 1)

            # Numerical stat lines / Old -> New upgrade preview!
            target_lvl = cur_lvl if is_erase_mode else (cur_lvl + 1)
            stat_lines = self._get_perk_progression_lines(player, perk["id"], perk, cur_lvl, target_lvl)
            cur_y = rect.y + 160
            for st_ln in stat_lines:
                for stat_line in self.wrap_text(st_ln, self.font_small, card_w - 26):
                    st_s = self.font_small.render(stat_line, True, UI_TEXT_MAIN)
                    screen.blit(st_s, (rect.centerx - st_s.get_width() // 2, cur_y))
                    cur_y += 18

            cur_y += 6
            clean_desc = self._clean_perk_desc(perk.get("desc", ""))
            desc_lines = self.wrap_text(clean_desc, self.font_small, card_w - 26)
            for ln in desc_lines:
                if cur_y + 16 > rect.bottom - 10:
                    break
                d_s = self.font_small.render(ln, True, UI_TEXT_MAIN)
                screen.blit(d_s, (rect.centerx - d_s.get_width() // 2, cur_y))
                cur_y += 18

    def _draw_inventory_label(self, screen, text, x, y, color=UI_TEXT_MAIN, *, align="topleft", font=None):
        label = (font or self.font_small).render(text, True, color)
        screen.blit(label, label.get_rect(**{align: (x, y)}))

    def _render_character_sheet_modal(self, screen, player, ui_texts, hover_pos, drag_item):
        win_w, win_h = 1140, 578
        wx = (SCREEN_W - win_w) // 2
        wy = (VIEW_H * SCALE - win_h) // 2
        self.modal_rect = pygame.Rect(wx, wy, win_w, win_h)
        self.draw_pixel_frame(screen, self.modal_rect, UI_PANEL_BG, UI_BORDER_GOLD, False, 1.0)
        journal_open = ui_texts.get("_journal_open", False)

        self.journal_btn_rect = pygame.Rect(wx + win_w - 224, wy + 15, 204, 34)
        hovered = self.journal_btn_rect.collidepoint(hover_pos)
        self.draw_pixel_frame(screen, self.journal_btn_rect, UI_SLOT_BG, UI_BORDER_GOLD, hovered, 1.0)
        journal_label = "К герою" if journal_open else "Журнал [J]"
        self._draw_inventory_label(screen, journal_label, *self.journal_btn_rect.center, align="center")
        if journal_open:
            self._render_journal_view(screen, wx, wy, win_w, win_h, ui_texts, hover_pos)
            return

        self._draw_inventory_label(screen, player.full_name, wx + 24, wy + 15, UI_BORDER_HIGHLIGHT, font=self.font_title)
        self._draw_inventory_label(screen, f"Уровень {player.level}", wx + 24, wy + 43, UI_TEXT_DIM)
        stats = pygame.Rect(wx + 20, wy + 71, 320, 454)
        gear = pygame.Rect(stats.right + 10, stats.y, 310, stats.height)
        storage = pygame.Rect(gear.right + 10, gear.y, 450, gear.height)
        for rect, title in ((stats, "Характеристики"), (gear, "Снаряжение"), (storage, "Поклажа")):
            self.draw_pixel_frame(screen, rect, UI_SLOT_BG, UI_BORDER_WOOD, False, 1.0)
            self._draw_inventory_label(screen, title, rect.x + 16, rect.y + 13, UI_BORDER_HIGHLIGHT, font=self.font_ui)

        x, right = stats.x + 16, stats.right - 16
        xp_y = stats.y + 44
        self._draw_inventory_label(screen, "Опыт", x, xp_y, UI_TEXT_DIM)
        self._draw_inventory_label(screen, f"{player.xp} / {player.max_xp}", right, xp_y, align="topright")
        pygame.draw.rect(screen, (13, 11, 16), (x, xp_y + 20, right - x, 7))
        ratio = min(1.0, player.xp / max(1, player.max_xp))
        pygame.draw.rect(screen, (225, 180, 76), (x, xp_y + 20, round((right - x) * ratio), 7))

        for index, (label, value, color) in enumerate((
            ("Сила", player.body, VECTOR_COLORS["body"]),
            ("Ловкость", player.cunning, VECTOR_COLORS["cunning"]),
            ("Магия", player.mind, VECTOR_COLORS["mind"]),
        )):
            y = stats.y + 84 + index * 32
            pygame.draw.rect(screen, (36, 30, 41), (x, y, right - x, 27))
            pygame.draw.rect(screen, color, (x, y, 2, 27))
            self._draw_inventory_label(screen, label, x + 10, y + 5, font=self.font_ui)
            self._draw_inventory_label(screen, str(value), right - 9, y + 4, color, align="topright", font=self.font_ui)

        stats_list = (
            ("Здоровье", f"{int(player.hp)} / {player.max_hp}"),
            ("Мана", f"{int(player.mp)} / {player.max_mp}"),
            ("Физическая атака", str(player.phys_attack)),
            ("Магическая мощь", str(player.mag_attack)),
            ("Физическая защита", str(player.phys_defense)),
            ("Магическая защита", str(player.mag_defense)),
            ("Шанс критического удара", f"{player.crit_chance:.1%}"),
            ("Шанс уклонения", f"{player.dodge_chance:.0%}"),
            ("Мана за попадание", f"{player.mp_on_hit:.1f}"),
            ("Шум шагов", f"{player.noise_factor:.0%}"),
            ("Обзор с факелом", f"{player.torch_light_radius / TILE_W:.1f} м"),
            ("Обзор в темноте", f"{player.dark_vision_radius / TILE_W:.1f} м"),
        )
        for index, (label, value) in enumerate(stats_list):
            y = stats.y + 188 + index * 22
            if index % 2 == 0:
                pygame.draw.rect(screen, (28, 24, 34), (x, y - 2, right - x, 21))
            self._draw_inventory_label(screen, label, x + 5, y, UI_TEXT_DIM)
            self._draw_inventory_label(screen, value.replace(".", ","), right - 5, y, align="topright")

        cx = gear.centerx
        portrait = pygame.Rect(cx - 47, gear.y + 137, 94, 147)
        self.draw_pixel_frame(screen, portrait, (18, 15, 22), UI_BORDER_WOOD, False, 1.0)
        hero, _ = self.get_hero_pair(player)
        art = pygame.transform.scale(hero, (64, 80))
        screen.blit(art, art.get_rect(center=portrait.center))

        self.equip_slot_rects = {
            key: pygame.Rect(center - 48, gear.y + top, 96, 67)
            for key, center, top in (
                ("helmet", cx, 51), ("trinket", gear.right - 56, 51),
                ("right_hand", gear.x + 56, 137), ("left_hand", gear.right - 56, 137),
                ("ring_1", gear.x + 56, 217), ("ring_2", gear.right - 56, 217),
                ("torso", cx, 297), ("boots", cx, 373),
            )
        }
        hovered_item = None
        compares = False
        weapon = player.equipment["right_hand"]
        for slot, rect in self.equip_slot_rects.items():
            item = player.equipment[slot]
            if slot == "left_hand" and weapon and weapon.two_handed:
                item = weapon
            is_hovered = rect.collidepoint(hover_pos)
            self.draw_pixel_frame(screen, rect, UI_PANEL_BG, item.rarity_color if item else UI_BORDER_WOOD, is_hovered, 1.0)
            label = ui_texts["slots"][slot]
            self._draw_inventory_label(screen, label, rect.centerx, rect.bottom - 13, UI_TEXT_DIM, align="center")
            if item:
                self.draw_item_icon(screen, item.icon, rect.centerx - 16, rect.y + 8, 32)
                if is_hovered:
                    hovered_item = item

        used = sum(item is not None for item in player.inventory)
        self._draw_inventory_label(screen, f"{used} / {player.unlocked_slots} мест", storage.right - 16,
                                   storage.y + 14, UI_TEXT_DIM, align="topright")
        self.bag_slot_rects = [pygame.Rect(storage.x + 15 + i * 213, storage.y + 42, 207, 54) for i in range(2)]
        filter_short = {"any": "Общая", "treasure": "Сокровища", "consumable": "Зелья/Свитки"}
        filter_colors = {
            "any": UI_BORDER_WOOD,
            "treasure": (235, 192, 78),
            "consumable": (88, 188, 238),
        }
        for index, rect in enumerate(self.bag_slot_rects):
            item = player.bag_slots[index]
            is_hovered = rect.collidepoint(hover_pos)
            is_locked_box = bool(item and getattr(item, "locked_bag", False))
            bd_col = UI_BORDER_GOLD if is_locked_box else (item.rarity_color if item else UI_BORDER_WOOD)
            self.draw_pixel_frame(screen, rect, UI_PANEL_BG, bd_col, is_hovered, 1.0)
            if item:
                self.draw_item_icon(screen, item.icon, rect.x + 8, rect.y + 11, 32)
                self._draw_inventory_label(screen, item.name, rect.x + 44, rect.y + 10, UI_BORDER_HIGHLIGHT if is_locked_box else UI_TEXT_MAIN)
                flt = getattr(item, "bag_filter", "any")
                tag = f"+{item.slots} · Несгораемая" if is_locked_box else f"+{item.slots} · {filter_short.get(flt, 'Общая')}"
                tag_col = UI_BORDER_GOLD if is_locked_box else filter_colors.get(flt, UI_TEXT_DIM)
                self._draw_inventory_label(screen, tag, rect.x + 44, rect.y + 29, tag_col)
                if is_hovered:
                    hovered_item, compares = item, False
            else:
                self._draw_inventory_label(screen, f"Место для сумки {index + 1}", *rect.center, UI_TEXT_DIM, align="center")

        # Крупные ячейки (6 в ряд, иконки 32x32) с вертикальной прокруткой
        vp_rect = pygame.Rect(storage.x + 12, storage.y + 102, storage.width - 24, (storage.y + 389) - (storage.y + 102) - 6)
        self.inv_viewport_rect = vp_rect
        per_row = 6
        cell_w, cell_h = 62, 48
        stride_x, stride_y = 67, 52

        sections = player.inventory_sections()
        total_content_h = 0
        for sec in sections:
            rows_used = (sec["count"] + per_row - 1) // per_row
            total_content_h += 22 + rows_used * stride_y + 8
        self.inv_max_scroll = max(0, total_content_h - vp_rect.height)

        game_ref = ui_texts.get("_game_ref")
        inv_scroll = getattr(game_ref, "inv_scroll", 0) if game_ref is not None else 0
        inv_scroll = max(0, min(self.inv_max_scroll, int(inv_scroll)))
        if game_ref is not None:
            game_ref.inv_scroll = inv_scroll

        old_clip = screen.get_clip()
        screen.set_clip(old_clip.clip(vp_rect))

        self.inv_slot_rects = []
        sec_y = vp_rect.y - inv_scroll
        for sec in sections:
            flt = sec["filter"]
            is_strongbox = bool(sec.get("bag") and getattr(sec["bag"], "locked_bag", False))
            accent = UI_BORDER_GOLD if is_strongbox else filter_colors.get(flt, UI_BORDER_WOOD)
            hdr_rect = pygame.Rect(vp_rect.x + 3, sec_y, vp_rect.width - 14, 19)
            pygame.draw.rect(screen, (42, 34, 26) if is_strongbox else (32, 27, 40), hdr_rect, border_radius=2)
            pygame.draw.rect(screen, accent, (hdr_rect.x, hdr_rect.y, 3, hdr_rect.height))
            sec_used = sum(1 for idx in range(sec["start"], sec["start"] + sec["count"]) if player.inventory[idx] is not None)
            title_txt = sec["title"]
            if is_strongbox:
                title_txt += "  [Несгораемая]"
            elif flt == "treasure":
                title_txt += "  [Только сокровища]"
            elif flt == "consumable":
                title_txt += "  [Только зелья и свитки]"
            self._draw_inventory_label(screen, title_txt, hdr_rect.x + 8, hdr_rect.y + 2, accent if (is_strongbox or flt != "any") else UI_TEXT_MAIN)
            self._draw_inventory_label(screen, f"{sec_used}/{sec['count']}", hdr_rect.right - 6, hdr_rect.y + 2, UI_TEXT_DIM, align="topright")
            sec_y += 22

            compatible_drag = (drag_item is None) or player.item_fits_filter(drag_item, flt)
            for rel_i in range(sec["count"]):
                abs_i = sec["start"] + rel_i
                row, col = divmod(rel_i, per_row)
                rect = pygame.Rect(vp_rect.x + 4 + col * stride_x, sec_y + row * stride_y, cell_w, cell_h)
                clipped_r = rect.clip(vp_rect)
                self.inv_slot_rects.append(clipped_r)
                if clipped_r.width <= 0 or clipped_r.height <= 0:
                    continue
                item = player.inventory[abs_i]
                is_hovered = clipped_r.collidepoint(hover_pos)
                if item:
                    border = item.rarity_color
                elif drag_item is not None and not compatible_drag:
                    border = (48, 38, 46)
                else:
                    border = accent if (is_strongbox or flt != "any") else UI_BORDER_WOOD
                bg = (20, 17, 24) if (drag_item is not None and not compatible_drag) else ((30, 25, 20) if is_strongbox else UI_PANEL_BG)
                self.draw_pixel_frame(screen, rect, bg, border, is_hovered and compatible_drag, 1.0)
                if item:
                    self.draw_item_icon(screen, item.icon, rect.centerx - 16, rect.centery - 16, 32)
                    if is_hovered:
                        hovered_item, compares = item, item.type == "equipment"
            rows_used = (sec["count"] + per_row - 1) // per_row
            sec_y += rows_used * stride_y + 8

        screen.set_clip(old_clip)

        if self.inv_max_scroll > 0:
            track_x = vp_rect.right - 7
            track_y = vp_rect.y + 2
            track_h = vp_rect.height - 4
            pygame.draw.rect(screen, (14, 12, 18), (track_x, track_y, 5, track_h))
            thumb_h = max(24, int(track_h * (vp_rect.height / max(1, total_content_h))))
            thumb_y = track_y + int((track_h - thumb_h) * (inv_scroll / max(1, self.inv_max_scroll)))
            pygame.draw.rect(screen, UI_BORDER_GOLD, (track_x, thumb_y, 5, thumb_h), border_radius=2)

        key_y = storage.y + 389
        pygame.draw.line(screen, UI_BORDER_WOOD, (storage.x + 15, key_y), (storage.right - 15, key_y))
        self._draw_inventory_label(screen, "Ключи", storage.x + 16, key_y + 18, UI_BORDER_HIGHLIGHT, font=self.font_ui)
        if (key_item := self._render_keyring(screen, player, ui_texts, storage.x + 80, key_y + 11, hover_pos)) is not None:
            hovered_item, compares = key_item, False

        hint = "Перетащи вещь, чтобы надеть · Правая кнопка снимает сумку или выбрасывает вещь из поклажи"
        self._draw_inventory_label(screen, hint, self.modal_rect.centerx, wy + 544, UI_TEXT_DIM, align="midtop")
        if drag_item:
            self.draw_item_icon(screen, drag_item.icon, hover_pos[0] - 16, hover_pos[1] - 16, 32)
        elif hovered_item:
            self._render_item_tooltip(screen, player, hovered_item, ui_texts, hover_pos, compare=compares)

    def _render_keyring(self, screen, player, ui_texts, x, y, hover_pos):
        game = ui_texts.get("_game_ref")
        local_keys = getattr(getattr(game, "dungeon", None), "jungle_keys", set())
        collected_keys = set(local_keys)
        for location in getattr(game, "jungle_locations", {}).values():
            collected_keys.update(location[0].jungle_keys)
        names = game.loc.get("jungle_route", {}) if game else {}
        keys = []
        for color, tint in JUNGLE_KEY_COLORS.items():
            if color in collected_keys:
                name = names.get(color, color)
                if color not in local_keys:
                    name += " · Другая локация"
                    tint = tuple(round(channel * .62) for channel in tint)
                keys.append((f"jungle_key_{color}", name, tint, None, 1))
        counts = Counter(item.id for item in player.quest_items)
        seen = set()
        for item in player.quest_items:
            if item.id not in seen:
                keys.append((item.icon, item.name, item.rarity_color, item, counts[item.id]))
                seen.add(item.id)
        if not keys:
            self._draw_inventory_label(screen, "Пока пусто", x, y + 8, UI_TEXT_DIM)
            return None
        hovered_item = None
        name_rect = None
        for index, (icon, name, color, item, count) in enumerate(keys):
            rect = pygame.Rect(x + index * 44, y, 40, 36)
            hovered = rect.collidepoint(hover_pos)
            self.draw_pixel_frame(screen, rect, UI_PANEL_BG, color, hovered, 1.0)
            self.draw_item_icon(screen, icon, rect.centerx - 16, rect.y + 2, 32)
            if count > 1:
                self._draw_inventory_label(screen, str(count), rect.right - 5, rect.bottom - 16, align="topright")
            if hovered:
                if item:
                    hovered_item = item
                else:
                    name_rect = (*rect.midbottom, name, color)
        if name_rect:
            nx, ny, name, color = name_rect
            label = self.font_small.render(name, True, color)
            pos = label.get_rect(midtop=(nx, ny + 5)).inflate(14, 8)
            self.draw_pixel_frame(screen, pos, UI_PANEL_BG, color, False, 1.0)
            screen.blit(label, label.get_rect(center=pos.center))
        return hovered_item

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
            rect = pygame.Rect(wx + 20, list_top, win_w - 40, 35)
            self.journal_seed_rect = rect
            hover = rect.collidepoint(hover_pos)
            self.draw_pixel_frame(screen, rect, UI_SLOT_BG, UI_BORDER_GOLD, hover, 1.0)
            message = game.seed_copy_message if pygame.time.get_ticks() < game.seed_copy_until else "copy"
            text = self.font_small.render(labels[message], True, UI_TEXT_MAIN)
            screen.blit(text, text.get_rect(midright=(rect.right - 14, rect.centery)))
            seed = self.font_ui.render(f'{labels["label"]}  {game.run_seed}', True, UI_TEXT_MAIN)
            screen.blit(seed, seed.get_rect(midleft=(rect.x + 14, rect.centery)))
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

        is_coin = item.type == "currency_coin"

        def add_wrapped(text, color):
            for ln in self.wrap_text(str(text), self.font_small, max_w):
                raw_lines.append((ln, COIN_TEXT_COLOR if is_coin else color))

        if item.type not in ("permanent_spell", "combat_skill", "spell"):
            rarity_title = ui_texts["rarities"].get(item.rarity, item.rarity)
            if item.two_handed:
                rarity_title += " • Двуручное"
            elif item.weap_style == "thrown":
                rarity_title += " • Метательное"
            add_wrapped(rarity_title, item.rarity_color)

        if item.type == "bag":
            add_wrapped(f"Дополнительные места: +{item.slots}", UI_TEXT_MAIN)
            flt = getattr(item, "bag_filter", "any")
            if flt == "treasure":
                add_wrapped("Отсек: только драгоценности и коллекционки", UI_BORDER_HIGHLIGHT)
            elif flt == "consumable":
                add_wrapped("Отсек: только зелья, свитки и расходники", (110, 215, 255))

        # Лаконичный формат для Драгоценностей, Монет и Коллекций
        if item.type in ("gem", "currency_coin", "fish", "painting"):
            add_wrapped(format_copper_Trigger(item.copper_value), UI_BORDER_HIGHLIGHT)
            if item.type in ("fish", "painting"):
                col_title = "Коллекция: Рыбы" if item.type == "fish" else "Коллекция: Картины"
                game_ref = ui_texts.get("_game_ref")
                prof = getattr(game_ref, "profile", {}) if game_ref else {}
                col_key = "collected_fish" if item.type == "fish" else "collected_paintings"
                already = item.id in prof.get(col_key, ())
                status_txt = "Уже в коллекции" if already else "Новая для коллекции!"
                status_col = UI_TEXT_DIM if already else (125, 245, 155)
                add_wrapped(f"{col_title} · {status_txt}", status_col)
            else:
                add_wrapped("Драгоценность." if item.type == "gem" else "Монеты.", UI_TEXT_MAIN)
            add_wrapped(item.desc, UI_TEXT_DIM)
            return raw_lines
        
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
        if getattr(item, "hp_bonus", 0) > 0:
            add_wrapped(f"Макс. здоровье: +{item.hp_bonus}", UI_TEXT_MAIN)
        if getattr(item, "mp_bonus", 0) > 0:
            add_wrapped(f"Макс. мана: +{item.mp_bonus}", UI_TEXT_MAIN)
        if getattr(item, "dodge_bonus", 0.0) > 0:
            add_wrapped(f"Уклонение: +{int(round(item.dodge_bonus * 100))}%", UI_TEXT_MAIN)
        if getattr(item, "speed_bonus", 0.0) != 0:
            sp = int(round(item.speed_bonus * 100))
            add_wrapped(f"Скорость шага: {'+' if sp > 0 else ''}{sp}%", UI_TEXT_MAIN)
        if getattr(item, "heal_received_bonus", 0.0) > 0:
            add_wrapped(f"Входящее лечение: +{int(round(item.heal_received_bonus * 100))}%", UI_TEXT_MAIN)
        if getattr(item, "mana_received_bonus", 0.0) > 0:
            add_wrapped(f"Получение маны: +{int(round(item.mana_received_bonus * 100))}%", UI_TEXT_MAIN)
        if getattr(item, "extra_slots", 0) > 0:
            add_wrapped(f"Доп. места поклажи: +{item.extra_slots}", UI_BORDER_HIGHLIGHT)
        if getattr(item, "glow_radius", 0.0) > 0:
            add_wrapped(f"Собственное свечение: {item.glow_radius / TILE_W:.1f} м", UI_BORDER_HIGHLIGHT)

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

        sell_val = getattr(item, "sell_value", 0)
        if sell_val > 0 and item.type in ("equipment", "bag", "consumable", "consumable_spell", "consumable_eraser"):
            add_wrapped(f"Цена продажи: {format_copper_Trigger(sell_val, compact=True)}", COIN_TEXT_COLOR)

        clean_desc = self._clean_perk_desc(item.desc)
        if clean_desc:
            add_wrapped(clean_desc, UI_TEXT_DIM)
        return raw_lines

    def _render_item_tooltip(self, screen, player, item, ui_texts, mouse_pos, compare=False, world_item=False):
        comp_item = player.get_comparison_item(item) if compare else None
        main_lines = self._build_item_stat_lines(player, item, ui_texts, comp_item)

        card_w = 308
        card_h = 48 + len(main_lines) * 19
        comp_lines = self._build_item_stat_lines(player, comp_item, ui_texts) if comp_item else []
        comp_height = 48 + len(comp_lines) * 19 if comp_item else 0
        if world_item:
            tx = 16
            ty = max(16, VIEW_H * SCALE - 16 - card_h)
            cx = tx + card_w + 8
            comp_y = max(16, VIEW_H * SCALE - 16 - comp_height)
        else:
            ty = max(16, min(SCREEN_H - card_h - 16, mouse_pos[1] - card_h // 2))
            total_w = card_w * 2 + 8 if comp_item else card_w
            if mouse_pos[0] + 18 + total_w > SCREEN_W - 12:
                tx = max(16, mouse_pos[0] - card_w - 16)
                cx = max(8, tx - card_w - 8)
            else:
                tx = mouse_pos[0] + 18
                cx = tx + card_w + 8
            comp_y = ty

        if world_item:
            old_clip = screen.get_clip()
            screen.set_clip(old_clip.clip((0, 0, SCREEN_W, VIEW_H * SCALE)))
        color = (VECTOR_COLORS.get(item.branch, UI_BORDER_WOOD)
                 if item.type in ("permanent_spell", "combat_skill", "spell") else item.rarity_color)
        self.draw_pixel_frame(screen, (tx, ty, card_w, card_h), (20, 17, 26), color, False, 1.0)
        title_color = COIN_TEXT_COLOR if item.type == "currency_coin" else color
        screen.blit(self.font_ui.render(item.name, True, title_color), (tx + 14, ty + 12))
        for i, (txt, col) in enumerate(main_lines):
            screen.blit(self.font_small.render(txt, True, col), (tx + 14, ty + 36 + i * 19))

        if comp_item:
            self.draw_pixel_frame(screen, (cx, comp_y, card_w, comp_height), (18, 15, 22), comp_item.rarity_color, False, 1.0)
            screen.blit(self.font_ui.render(f"[Надето] {comp_item.name}", True, comp_item.rarity_color), (cx + 14, comp_y + 12))
            for i, (txt, col) in enumerate(comp_lines):
                screen.blit(self.font_small.render(txt, True, col), (cx + 14, comp_y + 36 + i * 19))
        if world_item:
            screen.set_clip(old_clip)
