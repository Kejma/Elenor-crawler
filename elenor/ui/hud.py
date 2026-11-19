"""Retained gameplay HUD. Only changed text and widget state are rasterized."""
from functools import lru_cache, partial

import pygame

from elenor.config import (
    CANVAS_H, COIN_TEXT_COLOR, HUD_HEIGHT, SCALE, SCREEN_W, THOUGHT_BOX_H, THOUGHT_BOX_W,
    THOUGHT_BOX_X, THOUGHT_BOX_Y, UI_BG_DARK, UI_BORDER_GOLD, UI_BORDER_HIGHLIGHT,
    UI_BORDER_WOOD, UI_PANEL_BG, UI_SLOT_BG, UI_TEXT_MAIN, VIEW_H,
)
from elenor.data.abilities import VECTOR_COLORS, perk_branch
from elenor.data.economy import format_copper_Trigger


HUD_Y = CANVAS_H * SCALE
_KEY_LABELS = ("Q", "E", "R", "F", "1", "2", "3", "4")


@lru_cache(maxsize=128)
def hud_label(font, text, color):
    return font.render(text, True, color)


class HudLayers:
    def __init__(self):
        self.thought_key = None
        self.thought_blits = ()
        self.thought_screen_key = None
        self.bottom_key = None
        self.bottom = None
        self.light_tick = None
        self.lights = ()
        self.portrait = None
        self.portrait_image = None
        self.cooldown_overlay = None
        self._bottom_pool = None
        self._bottom_masks = None
        self._bottom_idx = 0

    def draw_thought(self, screen, renderer, text, window=None):
        if window is not None:
            if text == self.thought_screen_key and not window.prev_full_dirty:
                return
            screen.fill((0, 0, 0, 0), (0, VIEW_H * SCALE, SCREEN_W, HUD_Y - VIEW_H * SCALE))
            window.thought_dirty = True
            self.thought_screen_key = text
        if not text:
            return
        if text != self.thought_key:
            font = renderer.font_thought
            lines = renderer.wrap_text(text, font, THOUGHT_BOX_W * SCALE - 68)[:2]
            x = THOUGHT_BOX_X * SCALE + 34
            y = THOUGHT_BOX_Y * SCALE + (THOUGHT_BOX_H * SCALE - len(lines) * 26) // 2 + 2
            self.thought_blits = []
            for line in lines:
                self.thought_blits.append((font.render(line, True, (10, 8, 12)), (x + 2, y + 2)))
                self.thought_blits.append((font.render(line, True, UI_TEXT_MAIN), (x, y)))
                y += 26
            self.thought_key = text
        screen.blits(self.thought_blits, doreturn=False)

    def draw_bottom(self, screen, renderer, player, ui_texts, hover_pos, drag_item, inv_open, ticks, window=None):
        # Decorative light can flicker every game frame. Sample it at 20 Hz,
        # while changes to health, input and ability state take effect immediately.
        light_tick = ticks // 100
        torch_on = player.has_lit_torch
        light_sources = renderer.current_hud_lights
        light_key = light_tick, torch_on, bool(player.ignite_timer), bool(player.shine_timer), bool(light_sources)
        if self.light_tick != light_key:
            self.light_tick = light_key
            self.lights = light_sources

        portrait, _ = renderer.get_hero_pair(player)
        if portrait is not self.portrait:
            self.portrait = portrait
            self.portrait_image = pygame.transform.scale(portrait, (32, 40))

        slots = []
        hovered_item = None
        for active, rects, items in ((True, renderer.ability_rects, player.ability_slots),
                                     (False, renderer.hotbar_rects, player.hotbar)):
            for rect, item in zip(rects, items):
                hovered = rect.collidepoint(hover_pos)
                color = UI_BORDER_WOOD
                oom = False
                icon = cooldown = None
                if item is not None:
                    color = VECTOR_COLORS.get(item.branch, UI_BORDER_WOOD) if active else item.rarity_color
                    oom = active and item.type in ("spell", "permanent_spell") and player.mp < player.ability_mana_cost(item)
                    if not active or drag_item is not item:
                        icon = item.icon
                        remaining = player.cooldowns.get(item.id, 0.0)
                        if remaining > 0:
                            cooldown = f"{remaining:.1f}с"
                        if hovered:
                            hovered_item = item
                slots.append((hovered, color, oom, icon, cooldown))

        passives = []
        hovered_passive = None
        perks_db = ui_texts.get("_perks_db", {})
        for rect, (pid, level) in zip(renderer.passive_slot_rects, player.passive_perks.items()):
            data = perks_db.get(pid, {})
            color = VECTOR_COLORS.get(perk_branch(pid, data), UI_BORDER_WOOD)
            ready = player.passive_active(pid) or (pid == "firm_stance" and player.stance_ready())
            flash = player.passive_flash(pid)
            hovered = rect.collidepoint(hover_pos)
            passives.append((level, color, data.get("icon", "trinket"), ready, flash, hovered))
            if hovered:
                hovered_passive = pid, level, data

        xp_width = int((SCREEN_W - 34) * min(1.0, player.xp / max(1, player.max_xp)))
        hp, mp = (int(player.hp), player.max_hp), (int(player.mp), player.max_mp)
        capacity = player.unlocked_slots
        used = sum(item is not None for item in player.inventory[:capacity])
        bag_hovered = inv_open or renderer.bag_btn_rect.collidepoint(hover_pos)
        illumination = 1.0 if self.lights else player.illumination
        masks = screen.get_masks()
        light_sig = tuple(
            (round(l["pos"][0] * 0.25), round(l["pos"][1] * 0.25), round(l["radius"] * 0.125),
             round(l["color"][0] * 10), round(l["color"][1] * 10), round(l["color"][2] * 10))
            for l in self.lights
        )
        key = (masks, light_sig, round(illumination, 2), portrait, xp_width, player.level,
               hp, mp, torch_on, player.gold, tuple(slots), tuple(passives),
               bag_hovered, ui_texts["bag_btn"], used, capacity)
        if key != self.bottom_key:
            if self._bottom_pool is None or self._bottom_masks != masks:
                self._bottom_pool = (
                    pygame.Surface((SCREEN_W, HUD_HEIGHT), pygame.SRCALPHA, 32, masks),
                    pygame.Surface((SCREEN_W, HUD_HEIGHT), pygame.SRCALPHA, 32, masks),
                )
                self._bottom_masks = masks
            self._bottom_idx ^= 1
            bottom = self._bottom_pool[self._bottom_idx]
            bottom.fill((0, 0, 0, 255))
            self._paint_bottom(bottom, renderer, illumination, xp_width, player.level, hp, mp, torch_on,
                               player.gold, slots, passives, bag_hovered, ui_texts["bag_btn"], used, capacity)
            self.bottom = bottom
            self.bottom_key = key
        if window is None or self.bottom is not window.uploaded_hud or window.prev_full_dirty:
            screen.blit(self.bottom, (0, HUD_Y))
        return self.bottom, hovered_item, hovered_passive

    def _paint_bottom(self, screen, renderer, illumination, xp_width, level, hp, mp, torch_on,
                      gold, slots, passives, bag_hovered, bag_label, used, capacity):
        frame = partial(renderer.draw_pixel_frame, screen, illum=illumination, light_y_offset=HUD_Y, lights=self.lights)
        label = partial(hud_label, renderer.font_small)
        draw_icon = partial(renderer.draw_item_icon, screen)
        frame(screen.get_rect(), UI_BG_DARK, UI_BORDER_WOOD)
        pygame.draw.rect(screen, (14, 12, 18), (16, 7, SCREEN_W - 32, 10))
        if xp_width > 0:
            pygame.draw.rect(screen, (235, 185, 55), (17, 8, xp_width, 8))
        pygame.draw.rect(screen, UI_BORDER_GOLD, (16, 7, SCREEN_W - 32, 10), 1)

        frame((16, 22, 58, 58), UI_SLOT_BG, UI_BORDER_GOLD)
        screen.blit(self.portrait_image, (29, 30))
        lvl = label(str(level), (255, 225, 90))
        badge = (66 - lvl.get_width(), 62, lvl.get_width() + 6, 16)
        pygame.draw.rect(screen, (18, 15, 24), badge)
        pygame.draw.rect(screen, UI_BORDER_GOLD, badge, 1)
        screen.blit(lvl, (69 - lvl.get_width(), 63))
        renderer._draw_pixel_bar(screen, 80, 22, 176, 26, *hp, (185, 42, 52))
        renderer._draw_pixel_bar(screen, 80, 54, 176, 26, *mp, (48, 125, 210))

        frame((262, 22, 88, 58), UI_SLOT_BG, UI_BORDER_WOOD)
        torch_text, torch_color = ("[T] ВКЛ", (255, 200, 75)) if torch_on else ("[T] ТЕНЬ", (130, 175, 235))
        screen.blit(label(torch_text, torch_color), (270, 29))
        coins = label(format_copper_Trigger(gold, compact=True), COIN_TEXT_COLOR)
        screen.blit(coins, (262 + (88 - coins.get_width()) // 2, 51))

        for i, (rect, state) in enumerate(zip(renderer.ability_rects + renderer.hotbar_rects, slots)):
            r = rect.move(0, -HUD_Y)
            hovered, color, oom, icon, cooldown = state
            active = i < len(renderer.ability_rects)
            frame(r, (43, 35, 48) if active and hovered else UI_SLOT_BG, color, hovered and not active)
            if icon is not None:
                if oom:
                    screen.blit(renderer._mana_icon(icon), (r.x + 11, r.y + 12))
                    size = (r.width - 14, r.height - 14)
                    overlay = renderer.mana_slot_overlays.get(size)
                    if overlay is None:
                        overlay = pygame.Surface(size, pygame.SRCALPHA)
                        overlay.fill((22, 36, 68, 95))
                        renderer.mana_slot_overlays[size] = overlay
                    screen.blit(overlay, (r.x + 7, r.y + 7))
                else:
                    draw_icon(icon, r.x + (11 if active else 10), r.y + 12, 32)
                if cooldown is not None:
                    size = (r.width - 14, r.height - 14)
                    if self.cooldown_overlay is None or self.cooldown_overlay.get_size() != size:
                        self.cooldown_overlay = pygame.Surface(size, pygame.SRCALPHA)
                        self.cooldown_overlay.fill((10, 8, 16, 175))
                    screen.blit(self.cooldown_overlay, (r.x + 7, r.y + 7))
                    text = label(cooldown, (255, 195, 90))
                    screen.blit(text, (r.centerx - text.get_width() // 2, r.centery - 6))
            key_color = (110, 145, 195) if oom else (135, 215, 255) if active else UI_BORDER_HIGHLIGHT
            screen.blit(label(_KEY_LABELS[i], key_color), (r.x + 6, r.y + 5))

        for i, rect in enumerate(renderer.passive_slot_rects):
            r = rect.move(0, -HUD_Y)
            if i >= len(passives):
                frame(r, (18, 15, 22), (65, 52, 48))
                continue
            rank, color, icon, ready, flash, hovered = passives[i]
            brightness = .23 * ready + .60 * flash ** 2
            rim = tuple(round(c + (250 - c) * brightness) for c in color)
            base = (43, 35, 48) if hovered else UI_SLOT_BG
            background = tuple(round(c + hue * brightness * .14) for c, hue in zip(base, color))
            frame(r, background, rim)
            if flash > .05:
                sparks = tuple(round(c * (.45 + .55 * flash)) for c in color)
                pygame.draw.rect(screen, sparks, r.inflate(4, 4), 1)
                for cx, cy in (r.topleft, r.topright, r.bottomleft, r.bottomright):
                    pygame.draw.rect(screen, rim, (cx - 2, cy - 2, 4, 4))
            draw_icon(icon, r.x + 8, r.y + 8, 32)
            text = label(str(rank), (255, 235, 110))
            pygame.draw.rect(screen, (14, 12, 18), (r.right - text.get_width() - 6, r.bottom - 16, text.get_width() + 4, 14))
            screen.blit(text, (r.right - text.get_width() - 4, r.bottom - 16))
            if ready:
                pygame.draw.rect(screen, rim, (r.x + 5, r.y + 5, 6, 3))

        bag = renderer.bag_btn_rect.move(0, -HUD_Y)
        frame(bag, (52, 40, 36) if bag_hovered else UI_PANEL_BG, UI_BORDER_GOLD, bag_hovered)
        draw_icon("bag_small", bag.x + 8, bag.y + 10, 32)
        count_color = (255, 110, 95) if used >= capacity else (255, 220, 95)
        screen.blit(hud_label(renderer.font_ui, bag_label, UI_TEXT_MAIN), (bag.x + 42, bag.y + 10))
        screen.blit(label(f"{used} / {capacity}", count_color), (bag.x + 42, bag.y + 29))
