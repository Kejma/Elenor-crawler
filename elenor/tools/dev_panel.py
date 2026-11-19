import pygame
from elenor.config import SCREEN_W, RARITY_COLORS, UI_PANEL_BG, UI_SLOT_BG, UI_BORDER_GOLD, UI_BORDER_WOOD, UI_BORDER_HIGHLIGHT, UI_TEXT_MAIN, UI_TEXT_DIM
from elenor.entities import Enemy, Interactable


class DevPanel:
    def __init__(self):
        self.is_open = False
        self.reveal_map = False
        self.click_mode = None  # None, "teleport", or ("spawn_mob", kind) / ("spawn_obj", kind)
        self.active_tab = "items"  # "items", "perks", "spawner"
        self.spawn_rarity_idx = 0
        self.spawn_rarities = ["common", "uncommon", "rare", "epic", "legendary"]

        self.font_title = pygame.font.SysFont("consolas", 16, bold=True)
        self.font_ui = pygame.font.SysFont("consolas", 13, bold=True)
        self.font_small = pygame.font.SysFont("consolas", 12, bold=True)
        self.buttons = []
        self._panel_surf = None
        self._panel_layout_key = None
        self._panel_key = None
        self._banner_key = None
        self._banner_surf = None
        self._lbl_cache = {}

    def handle_event(self, event, game, world_mx, world_my):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_F1, pygame.K_BACKQUOTE):
                self.is_open = not self.is_open
                self.click_mode = None
                game.sfx.play("ui")
                return True

        if not self.is_open:
            # Allow world click actions when panel is minimized during teleport/spawn mode
            if self.click_mode and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._execute_world_click(game, world_mx, world_my)
                return True
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
            mx, my = event.pos
            win_rect = pygame.Rect(80, 36, SCREEN_W - 160, 560)

            if not win_rect.collidepoint((mx, my)):
                if self.click_mode and event.button == 1:
                    self._execute_world_click(game, world_mx, world_my)
                return True

            for b_id, rect in self.buttons:
                if rect.collidepoint((mx, my)):
                    self._trigger_button(b_id, event.button, game)
                    return True
            return True

        return False

    def _execute_world_click(self, game, wx, wy):
        tx, ty = int(wx), int(wy)
        if self.click_mode == "teleport":
            game.player.x, game.player.y = float(tx) + 0.5, float(ty) + 0.5
            game.sfx.play("magic")
            game.add_popup(game.player.x, game.player.y, "ТЕЛЕПОРТ!", (120, 235, 255))
        elif isinstance(self.click_mode, tuple):
            mode, kind = self.click_mode
            if mode == "spawn_mob":
                m = Enemy(tx, ty, kind=kind, state="patrolling")
                ep = game.balance_data.get("enemies", {}).get(kind)
                if ep:
                    m.apply_balance_profile(ep, floor_num=game.dungeon.floor_num)
                from elenor.missions.rats import attach_mob_dialogues
                attach_mob_dialogues(m, game.loc)
                game.mobs.append(m)
                game.sfx.play("alert")
            elif mode == "spawn_obj":
                game.objects.append(Interactable(tx, ty, kind))
                game.sfx.play("ui")

    def _trigger_button(self, b_id, mouse_btn, game):
        p = game.player
        game.sfx.play("ui")

        if b_id == "tab_items":
            self.active_tab = "items"
        elif b_id == "tab_perks":
            self.active_tab = "perks"
        elif b_id == "tab_spawner":
            self.active_tab = "spawner"
        elif b_id == "act_heal":
            p.hp = float(p.max_hp)
            p.mp = float(p.max_mp)
            game.add_popup(p.x, p.y, "ПОЛНЫЙ ХИЛ", (110, 250, 140))
        elif b_id == "act_god":
            p.god_mode = not getattr(p, "god_mode", False)
        elif b_id == "act_fov":
            self.reveal_map = not self.reveal_map
        elif b_id == "act_lvl_up":
            p.level += 1
            p.max_xp = int(p.max_xp * 1.55)
            p.pending_perk_rolls += 1
            p.hp = float(p.max_hp)
            p.mp = float(p.max_mp)
            game.roll_perk_choices()
            self.is_open = False
        elif b_id == "act_lvl_down":
            if p.level > 1:
                p.level -= 1
                p.max_xp = max(25, int(p.max_xp / 1.55))
                p.xp = 0
                p.hp = min(p.hp, float(p.max_hp))
                p.mp = min(p.mp, float(p.max_mp))
                game.add_popup(p.x, p.y, f"Откат -> Ур.{p.level}", (255, 140, 100))
        elif b_id == "act_unlock_bag":
            for index, bag in enumerate(p.bag_slots):
                if bag is None or bag.id != "void_chest_bag":
                    game.equip_bag(game.make_item("void_chest_bag"), index)
        elif b_id == "act_gold":
            p.gold += 100
        elif b_id == "act_next_floor":
            game.descend_to_next_floor()
        elif b_id == "act_teleport":
            self.click_mode = "teleport" if self.click_mode != "teleport" else None
        elif b_id == "act_kill_all":
            for m in list(game.mobs):
                m.hp = 0
                game._check_mob_death(m)
        elif b_id == "act_cycle_rarity":
            step = -1 if mouse_btn == 3 else 1
            self.spawn_rarity_idx = (self.spawn_rarity_idx + step) % len(self.spawn_rarities)
        elif b_id.startswith("give_item:"):
            item_id = b_id.split(":")[1]
            chosen_rar = self.spawn_rarities[self.spawn_rarity_idx]
            itm = game.make_item(item_id, rarity=chosen_rar)
            if not p.add_item_to_inventory(itm):
                if not p.try_auto_equip_if_slot_empty(itm):
                    game.objects.append(Interactable(int(p.x), int(p.y), "loot", itm))
            game.add_popup(p.x, p.y, f"+{itm.name}", itm.rarity_color)
        elif b_id.startswith("perk:"):
            perk_id = b_id.split(":")[1]
            if mouse_btn == 3:
                p.remove_perk(perk_id)
            else:
                p.apply_perk(perk_id, game.loc.get("perks", {}))
        elif b_id.startswith("spawn_mob:"):
            kind = b_id.split(":")[1]
            self.click_mode = ("spawn_mob", kind)
        elif b_id.startswith("spawn_obj:"):
            kind = b_id.split(":")[1]
            self.click_mode = ("spawn_obj", kind)

    def _label(self, font, text, color):
        key = (id(font), text, color)
        surf = self._lbl_cache.get(key)
        if surf is None:
            if len(self._lbl_cache) >= 512:
                self._lbl_cache.clear()
            surf = font.render(text, True, color)
            self._lbl_cache[key] = surf
        return surf

    def render(self, screen, game, mouse_pos):
        window = getattr(game, "gl_window", None)
        if self.click_mode and not self.is_open:
            if self.click_mode != self._banner_key or self._banner_surf is None:
                self._banner_surf = self.font_title.render(
                    f"РЕЖИМ ЧИТ-КЛИКА: {self.click_mode} [Нажми F1 для отмены]", True, (255, 220, 80)
                )
                self._banner_key = self.click_mode
            if window is not None:
                window.set_dev_panel(
                    "dev_banner", pygame.Rect(20, 14, *self._banner_surf.get_size()),
                    self._banner_key, self._banner_surf,
                )
            else:
                screen.blit(self._banner_surf, (20, 14))

        if not self.is_open:
            return

        win_rect = pygame.Rect(80, 36, SCREEN_W - 160, 560)
        ox, oy = win_rect.x, win_rect.y
        p = game.player
        layout_key = (
            self.active_tab,
            self.click_mode,
            self.reveal_map,
            getattr(p, "god_mode", False),
            self.spawn_rarity_idx if self.active_tab == "items" else None,
            tuple(sorted(p.perks.items())) if self.active_tab == "perks" else None,
        )
        if layout_key == self._panel_layout_key and self.buttons:
            hov_id = next((bid for bid, r in self.buttons if r.collidepoint(mouse_pos)), None)
        else:
            hov_id = "__rebuild__"
        full_key = (layout_key, hov_id)

        if full_key != self._panel_key or self._panel_surf is None:
            if self._panel_surf is None or self._panel_surf.get_size() != win_rect.size:
                self._panel_surf = pygame.Surface(win_rect.size, pygame.SRCALPHA)
            surf = self._panel_surf
            surf.fill((0, 0, 0, 0))
            local_win = pygame.Rect(0, 0, win_rect.width, win_rect.height)
            self.buttons = []

            pygame.draw.rect(surf, (18, 15, 24), local_win, border_radius=8)
            pygame.draw.rect(surf, UI_BORDER_GOLD, local_win, 2, border_radius=8)

            title = self._label(self.font_title, "🛠 DEV CHEAT PANEL [F1 — Закрыть] (Клик вне окна = применить спавн/телепорт на карту)", UI_BORDER_HIGHLIGHT)
            surf.blit(title, (20, 14))

            quick_actions = [
                ("act_heal", "Полный Хил"),
                ("act_god", f"Бессмертие: {'ВКЛ' if getattr(p, 'god_mode', False) else 'ВЫКЛ'}"),
                ("act_fov", f"Открыть карту: {'ВКЛ' if self.reveal_map else 'ВЫКЛ'}"),
                ("act_lvl_up", "+1 Уровень (Дар)"),
                ("act_lvl_down", "-1 Уровень"),
                ("act_unlock_bag", "Открыть 24 яч."),
                ("act_gold", "+100 Золота"),
                ("act_next_floor", "След. Этаж >>"),
                ("act_teleport", f"Телепорт: {'АКТИВЕН' if self.click_mode == 'teleport' else 'ВЫКЛ'}"),
                ("act_kill_all", "Убить всех мобов"),
            ]
            qx, qy = 20, 46
            for idx, (aid, atxt) in enumerate(quick_actions):
                col = idx % 5
                row = idx // 5
                lr = pygame.Rect(qx + col * 190, qy + row * 34, 182, 28)
                sr = lr.move(ox, oy)
                hov = sr.collidepoint(mouse_pos)
                pygame.draw.rect(surf, (48, 38, 64) if hov else UI_SLOT_BG, lr, border_radius=4)
                pygame.draw.rect(surf, UI_BORDER_HIGHLIGHT if hov else UI_BORDER_WOOD, lr, 1, border_radius=4)
                s = self._label(self.font_small, atxt, UI_TEXT_MAIN)
                surf.blit(s, (lr.x + (lr.width - s.get_width()) // 2, lr.y + 7))
                self.buttons.append((aid, sr))

            tabs = [
                ("tab_items", "📦 Выдать Предмет", self.active_tab == "items"),
                ("tab_perks", "⚡ Управление Перками (ЛКМ+/ПКМ-)", self.active_tab == "perks"),
                ("tab_spawner", "👹 Спавнер Врагов и Объектов", self.active_tab == "spawner"),
            ]
            for ti, (tid, tlabel, tact) in enumerate(tabs):
                ltr = pygame.Rect(20 + ti * 310, 122, 295, 30)
                str_r = ltr.move(ox, oy)
                pygame.draw.rect(surf, (65, 50, 85) if tact else UI_PANEL_BG, ltr, border_radius=4)
                pygame.draw.rect(surf, UI_BORDER_GOLD if tact else UI_BORDER_WOOD, ltr, 2 if tact else 1, border_radius=4)
                ts = self._label(self.font_ui, tlabel, UI_BORDER_HIGHLIGHT if tact else UI_TEXT_DIM)
                surf.blit(ts, (ltr.x + (ltr.width - ts.get_width()) // 2, ltr.y + 6))
                self.buttons.append((tid, str_r))

            content_y = 164

            if self.active_tab == "items":
                cur_rar = self.spawn_rarities[self.spawn_rarity_idx]
                rar_col_btn = RARITY_COLORS.get(cur_rar, UI_TEXT_MAIN)
                rar_names_ru = {"common": "ОБЫЧНОЕ [I]", "uncommon": "ДОБРОТНОЕ [II]", "rare": "РЕДКОЕ [III]", "epic": "ЭПИЧЕСКОЕ [IV]", "legendary": "ЛЕГЕНДАРНОЕ [V]"}
                l_rar = pygame.Rect(win_rect.width - 360, 122, 340, 30)
                pygame.draw.rect(surf, (36, 30, 48), l_rar, border_radius=4)
                pygame.draw.rect(surf, rar_col_btn, l_rar, 2, border_radius=4)
                rt_s = self._label(self.font_ui, f"Тир оружия: {rar_names_ru[cur_rar]} (ЛКМ/ПКМ)", rar_col_btn)
                surf.blit(rt_s, (l_rar.x + (l_rar.width - rt_s.get_width()) // 2, l_rar.y + 6))
                self.buttons.append(("act_cycle_rarity", l_rar.move(ox, oy)))

                items_db = game.loc.get("items", {})
                for idx, (item_id, idata) in enumerate(items_db.items()):
                    col = idx % 7
                    row = idx // 7
                    lir = pygame.Rect(16 + col * 246, content_y + row * 31, 240, 27)
                    sir = lir.move(ox, oy)
                    hov = sir.collidepoint(mouse_pos)
                    is_weap = (idata.get("type") == "equipment" and idata.get("slot") == "right_hand" and not idata.get("is_torch", False))
                    r_col = rar_col_btn if is_weap else RARITY_COLORS.get(idata.get("rarity", "common"), UI_TEXT_MAIN)
                    pygame.draw.rect(surf, (42, 36, 56) if hov else UI_SLOT_BG, lir, border_radius=4)
                    pygame.draw.rect(surf, r_col, lir, 2 if hov else 1, border_radius=4)
                    game.renderer.draw_item_icon(surf, idata["icon"], lir.x + 2, lir.y, 26)
                    nm = self._label(self.font_small, idata["name"][:22], r_col)
                    surf.blit(nm, (lir.x + 32, lir.y + 6))
                    self.buttons.append((f"give_item:{item_id}", sir))

            elif self.active_tab == "perks":
                perks_db = game.loc.get("perks", {})
                for idx, (pid, pdata) in enumerate(perks_db.items()):
                    col = idx % 3
                    row = idx // 3
                    lpr = pygame.Rect(20 + col * 316, content_y + row * 54, 304, 46)
                    spr = lpr.move(ox, oy)
                    hov = spr.collidepoint(mouse_pos)
                    r_col = RARITY_COLORS.get(pdata.get("rarity", "common"), UI_TEXT_MAIN)
                    cur_lvl = p.perks.get(pid, 0)
                    pygame.draw.rect(surf, (45, 38, 60) if hov else UI_SLOT_BG, lpr, border_radius=4)
                    pygame.draw.rect(surf, r_col, lpr, 2 if cur_lvl > 0 else 1, border_radius=4)
                    game.renderer.draw_item_icon(surf, pdata["icon"], lpr.x + 6, lpr.y + 7, 32)
                    nm = self._label(self.font_ui, f"{pdata['name']} [Ур.{cur_lvl}]", r_col)
                    tp = self._label(self.font_small, "Активный" if pdata.get("type") == "active" else "Пассивный", UI_TEXT_DIM)
                    surf.blit(nm, (lpr.x + 44, lpr.y + 6))
                    surf.blit(tp, (lpr.x + 44, lpr.y + 25))
                    self.buttons.append((f"perk:{pid}", spr))

            elif self.active_tab == "spawner":
                mobs_list = [("rat", "Погребная крыса"), ("rat_cultist", "Крыса-сектант"), ("rat_king", "Крысиный Король"), ("skeleton", "Скелет-воин"), ("cultist", "Культист")]
                objs_list = [("barrel", "Винная бочка"), ("ritual_altar", "Кровавый алтарь"), ("chest", "Сундук"), ("campfire", "Костёр"), ("alchemy", "Алхимия"), ("rack", "Оружейная стойка"), ("stairs", "Лестница вниз")]
                surf.blit(self._label(self.font_ui, "Выбери кого спавнить, затем кликай ЛКМ по карте вокруг окна:", UI_BORDER_HIGHLIGHT), (24, content_y))
                for i, (mk, mname) in enumerate(mobs_list):
                    lmr = pygame.Rect(24 + i * 186, content_y + 30, 176, 36)
                    smr = lmr.move(ox, oy)
                    act = (self.click_mode == ("spawn_mob", mk))
                    pygame.draw.rect(surf, (75, 40, 48) if act else UI_SLOT_BG, lmr, border_radius=4)
                    pygame.draw.rect(surf, (255, 110, 110) if act else UI_BORDER_WOOD, lmr, 2 if act else 1, border_radius=4)
                    surf.blit(self._label(self.font_small, f"Моб: {mname}", UI_TEXT_MAIN), (lmr.x + 12, lmr.y + 11))
                    self.buttons.append((f"spawn_mob:{mk}", smr))

                for i, (ok, oname) in enumerate(objs_list):
                    col = i % 4
                    row = i // 4
                    lor = pygame.Rect(24 + col * 230, content_y + 90 + row * 44, 218, 36)
                    sor = lor.move(ox, oy)
                    act = (self.click_mode == ("spawn_obj", ok))
                    pygame.draw.rect(surf, (45, 65, 50) if act else UI_SLOT_BG, lor, border_radius=4)
                    pygame.draw.rect(surf, (120, 240, 150) if act else UI_BORDER_WOOD, lor, 2 if act else 1, border_radius=4)
                    surf.blit(self._label(self.font_small, f"Объект: {oname}", UI_TEXT_MAIN), (lor.x + 12, lor.y + 11))
                    self.buttons.append((f"spawn_obj:{ok}", sor))

            self._panel_layout_key = layout_key
            hov_after = next((bid for bid, r in self.buttons if r.collidepoint(mouse_pos)), None)
            self._panel_key = (layout_key, hov_after)

        if window is not None:
            window.set_dev_panel("dev_panel", win_rect, self._panel_key, self._panel_surf)
        else:
            screen.blit(self._panel_surf, win_rect.topleft)