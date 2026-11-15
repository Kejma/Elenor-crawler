import pygame
from config import (
    SCREEN_W, SCREEN_H, SCALE, TILE_W, TILE_H, RARITY_COLORS,
    UI_PANEL_BG, UI_SLOT_BG, UI_BORDER_GOLD, UI_BORDER_WOOD,
    UI_BORDER_HIGHLIGHT, UI_TEXT_MAIN, UI_TEXT_DIM
)
from entities import Enemy, Interactable


class DevPanel:
    def __init__(self):
        self.is_open = False
        self.reveal_map = False
        self.click_mode = None  # None, "teleport", or ("spawn_mob", kind) / ("spawn_obj", kind)
        self.active_tab = "items"  # "items", "perks", "spawner"

        self.font_title = pygame.font.SysFont("consolas", 16, bold=True)
        self.font_ui = pygame.font.SysFont("consolas", 13, bold=True)
        self.font_small = pygame.font.SysFont("consolas", 12, bold=True)
        self.buttons = []

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
                from mission_rats import attach_mob_dialogues
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
            p.unlocked_slots = 24
            p.bag_name = "Бездонный кофр (24 яч.)"
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
        elif b_id.startswith("give_item:"):
            item_id = b_id.split(":")[1]
            itm = game.make_item(item_id)
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

    def render(self, screen, game, mouse_pos):
        if self.click_mode and not self.is_open:
            lbl = self.font_title.render(f"РЕЖИМ ЧИТ-КЛИКА: {self.click_mode} [Нажми F1 для отмены]", True, (255, 220, 80))
            screen.blit(lbl, (20, 14))

        if not self.is_open:
            return

        self.buttons = []
        win_rect = pygame.Rect(80, 36, SCREEN_W - 160, 560)
        pygame.draw.rect(screen, (18, 15, 24), win_rect, border_radius=8)
        pygame.draw.rect(screen, UI_BORDER_GOLD, win_rect, 2, border_radius=8)

        title = self.font_title.render("🛠 DEV CHEAT PANEL [F1 — Закрыть] (Клик вне окна = применить спавн/телепорт на карту)", True, UI_BORDER_HIGHLIGHT)
        screen.blit(title, (win_rect.x + 20, win_rect.y + 14))

        # Top Quick Action Buttons
        p = game.player
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
        qx, qy = win_rect.x + 20, win_rect.y + 46
        for idx, (aid, atxt) in enumerate(quick_actions):
            col = idx % 5
            row = idx // 5
            r = pygame.Rect(qx + col * 190, qy + row * 34, 182, 28)
            hov = r.collidepoint(mouse_pos)
            pygame.draw.rect(screen, (48, 38, 64) if hov else UI_SLOT_BG, r, border_radius=4)
            pygame.draw.rect(screen, UI_BORDER_HIGHLIGHT if hov else UI_BORDER_WOOD, r, 1, border_radius=4)
            s = self.font_small.render(atxt, True, UI_TEXT_MAIN)
            screen.blit(s, (r.x + (r.width - s.get_width()) // 2, r.y + 7))
            self.buttons.append((aid, r))

        # Category Tabs
        tabs = [
            ("tab_items", "📦 Выдать Предмет", self.active_tab == "items"),
            ("tab_perks", "⚡ Управление Перками (ЛКМ+/ПКМ-)", self.active_tab == "perks"),
            ("tab_spawner", "👹 Спавнер Врагов и Объектов", self.active_tab == "spawner"),
        ]
        for ti, (tid, tlabel, tact) in enumerate(tabs):
            tr = pygame.Rect(win_rect.x + 20 + ti * 310, win_rect.y + 122, 295, 30)
            pygame.draw.rect(screen, (65, 50, 85) if tact else UI_PANEL_BG, tr, border_radius=4)
            pygame.draw.rect(screen, UI_BORDER_GOLD if tact else UI_BORDER_WOOD, tr, 2 if tact else 1, border_radius=4)
            ts = self.font_ui.render(tlabel, True, UI_BORDER_HIGHLIGHT if tact else UI_TEXT_DIM)
            screen.blit(ts, (tr.x + (tr.width - ts.get_width()) // 2, tr.y + 6))
            self.buttons.append((tid, tr))

        content_y = win_rect.y + 164

        if self.active_tab == "items":
            items_db = game.loc.get("items", {})
            for idx, (item_id, idata) in enumerate(items_db.items()):
                col = idx % 4
                row = idx // 4
                ir = pygame.Rect(win_rect.x + 20 + col * 238, content_y + row * 38, 230, 32)
                hov = ir.collidepoint(mouse_pos)
                r_col = RARITY_COLORS.get(idata.get("rarity", "common"), UI_TEXT_MAIN)
                pygame.draw.rect(screen, (42, 36, 56) if hov else UI_SLOT_BG, ir, border_radius=4)
                pygame.draw.rect(screen, r_col, ir, 2 if hov else 1, border_radius=4)
                game.renderer.draw_item_icon(screen, idata["icon"], ir.x + 4, ir.y + 2, 28)
                nm = self.font_small.render(idata["name"][:21], True, r_col)
                screen.blit(nm, (ir.x + 36, ir.y + 9))
                self.buttons.append((f"give_item:{item_id}", ir))

        elif self.active_tab == "perks":
            perks_db = game.loc.get("perks", {})
            for idx, (pid, pdata) in enumerate(perks_db.items()):
                col = idx % 3
                row = idx // 3
                pr = pygame.Rect(win_rect.x + 20 + col * 316, content_y + row * 54, 304, 46)
                hov = pr.collidepoint(mouse_pos)
                r_col = RARITY_COLORS.get(pdata.get("rarity", "common"), UI_TEXT_MAIN)
                cur_lvl = p.perks.get(pid, 0)
                pygame.draw.rect(screen, (45, 38, 60) if hov else UI_SLOT_BG, pr, border_radius=4)
                pygame.draw.rect(screen, r_col, pr, 2 if cur_lvl > 0 else 1, border_radius=4)
                game.renderer.draw_item_icon(screen, pdata["icon"], pr.x + 6, pr.y + 7, 32)
                nm = self.font_ui.render(f"{pdata['name']} [Ур.{cur_lvl}]", True, r_col)
                tp = self.font_small.render("Активный" if pdata.get("type") == "active" else "Пассивный", True, UI_TEXT_DIM)
                screen.blit(nm, (pr.x + 44, pr.y + 6))
                screen.blit(tp, (pr.x + 44, pr.y + 25))
                self.buttons.append((f"perk:{pid}", pr))

        elif self.active_tab == "spawner":
            mobs_list = [("rat", "Погребная крыса"), ("rat_cultist", "Крыса-сектант"), ("rat_king", "Крысиный Король"), ("skeleton", "Скелет-воин"), ("cultist", "Культист")]
            objs_list = [("barrel", "Винная бочка"), ("ritual_altar", "Кровавый алтарь"), ("chest", "Сундук"), ("campfire", "Костёр"), ("alchemy", "Алхимия"), ("rack", "Оружейная стойка"), ("stairs", "Лестница вниз")]
            screen.blit(self.font_ui.render("Выбери кого спавнить, затем кликай ЛКМ по карте вокруг окна:", True, UI_BORDER_HIGHLIGHT), (win_rect.x + 24, content_y))
            for i, (mk, mname) in enumerate(mobs_list):
                mr = pygame.Rect(win_rect.x + 24 + i * 186, content_y + 30, 176, 36)
                act = (self.click_mode == ("spawn_mob", mk))
                pygame.draw.rect(screen, (75, 40, 48) if act else UI_SLOT_BG, mr, border_radius=4)
                pygame.draw.rect(screen, (255, 110, 110) if act else UI_BORDER_WOOD, mr, 2 if act else 1, border_radius=4)
                screen.blit(self.font_small.render(f"Моб: {mname}", True, UI_TEXT_MAIN), (mr.x + 12, mr.y + 11))
                self.buttons.append((f"spawn_mob:{mk}", mr))

            for i, (ok, oname) in enumerate(objs_list):
                col = i % 4
                row = i // 4
                orr = pygame.Rect(win_rect.x + 24 + col * 230, content_y + 90 + row * 44, 218, 36)
                act = (self.click_mode == ("spawn_obj", ok))
                pygame.draw.rect(screen, (45, 65, 50) if act else UI_SLOT_BG, orr, border_radius=4)
                pygame.draw.rect(screen, (120, 240, 150) if act else UI_BORDER_WOOD, orr, 2 if act else 1, border_radius=4)
                screen.blit(self.font_small.render(f"Объект: {oname}", True, UI_TEXT_MAIN), (orr.x + 12, orr.y + 11))
                self.buttons.append((f"spawn_obj:{ok}", orr))