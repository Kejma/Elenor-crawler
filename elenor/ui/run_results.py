"""Post-run summary modal: strongbox rescue, loot payout, and collectible choices."""

import pygame

from elenor.config import (
    COIN_TEXT_COLOR,
    SCREEN_H,
    SCREEN_W,
    UI_BORDER_GOLD,
    UI_BORDER_HIGHLIGHT,
    UI_BORDER_WOOD,
    UI_PANEL_BG,
    UI_SLOT_BG,
    UI_TEXT_DIM,
    UI_TEXT_MAIN,
)
from elenor.data.economy import format_copper_Trigger
from elenor.profile import save_profile


def build_run_results(game, victory):
    player = game.player
    prof = game.profile
    rescued = []

    if victory:
        for i in range(player.unlocked_slots):
            itm = player.inventory[i]
            if itm and (itm.type in ("gem", "fish", "painting") or getattr(itm, "is_collectible", False)):
                rescued.append(itm)
                player.inventory[i] = None
    else:
        for sec in player.inventory_sections():
            bag = sec.get("bag")
            if bag is not None and getattr(bag, "locked_bag", False):
                for idx in range(sec["start"], sec["start"] + sec["count"]):
                    itm = player.inventory[idx]
                    if itm is not None:
                        rescued.append(itm)
                        player.inventory[idx] = None

    auto_sold_count = 0
    auto_sold_cp = 0
    pending = []
    seen_new = set()

    for itm in rescued:
        val = getattr(itm, "sell_value", 0) or getattr(itm, "copper_value", 0)
        is_col = itm.type in ("fish", "painting") or getattr(itm, "is_collectible", False)
        if is_col:
            col_key = "collected_fish" if itm.type == "fish" else "collected_paintings"
            owned = set(prof.get(col_key, ()))
            if itm.id not in owned and itm.id not in seen_new:
                seen_new.add(itm.id)
                pending.append({
                    "item": itm,
                    "col_key": col_key,
                    "sell_val": val,
                    "choice": None,
                })
                continue
        if val > 0:
            auto_sold_count += 1
            auto_sold_cp += val

    run_coins = max(0, int(getattr(player, "gold", 0)))
    coins_kept = run_coins if victory else (run_coins // 2)
    player.gold = 0

    bank_gain = coins_kept + auto_sold_cp
    if bank_gain > 0:
        prof["bank_copper"] = prof.get("bank_copper", 0) + bank_gain
        save_profile(prof)

    game.strongbox_settled = True
    return {
        "victory": bool(victory),
        "floor": getattr(game.dungeon, "floor_num", 1),
        "hero_name": player.full_name,
        "has_strongbox": any(getattr(b, "locked_bag", False) for b in player.bag_slots if b),
        "run_coins": run_coins,
        "coins_kept": coins_kept,
        "auto_sold_count": auto_sold_count,
        "auto_sold_cp": auto_sold_cp,
        "extra_sold_cp": 0,
        "collected_count": 0,
        "pending": pending,
        "scroll": 0,
        "btn_rects": {},
    }


def _close_to_menu(game, res):
    prof = game.profile
    sold_rem = 0
    for entry in res["pending"]:
        if entry["choice"] is None:
            entry["choice"] = "sell"
            sold_rem += entry["sell_val"]
    if sold_rem > 0:
        prof["bank_copper"] = prof.get("bank_copper", 0) + sold_rem
        save_profile(prof)

    game.run_results = None
    game.rat_campaign_complete = False
    game.in_main_menu = True
    game.main_menu.can_resume = False
    game.player.buffered_combat = None
    game.sfx.play("ui")


def handle_run_results_event(game, event, mouse_pos):
    res = game.run_results
    if res is None:
        return False

    if event.type == pygame.MOUSEWHEEL:
        max_sc = max(0, len(res["pending"]) - 4)
        res["scroll"] = max(0, min(max_sc, res["scroll"] - event.y))
        return True

    if event.type == pygame.KEYDOWN:
        if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            if all(e["choice"] is not None for e in res["pending"]):
                _close_to_menu(game, res)
            return True
        return True

    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        pos = getattr(event, "pos", mouse_pos)
        for key, rect in list(res.get("btn_rects", {}).items()):
            if not rect.collidepoint(pos):
                continue
            if key == "finish":
                _close_to_menu(game, res)
                return True
            if isinstance(key, tuple) and len(key) == 2:
                action, idx = key
                entry = res["pending"][idx]
                if entry["choice"] is not None:
                    return True
                prof = game.profile
                if action == "collect":
                    entry["choice"] = "collect"
                    col_list = prof.setdefault(entry["col_key"], [])
                    if entry["item"].id not in col_list:
                        col_list.append(entry["item"].id)
                    res["collected_count"] += 1
                    save_profile(prof)
                    game.sfx.play("levelup")
                elif action == "sell":
                    entry["choice"] = "sell"
                    val = entry["sell_val"]
                    prof["bank_copper"] = prof.get("bank_copper", 0) + val
                    res["extra_sold_cp"] += val
                    save_profile(prof)
                    game.sfx.play("coin_pickup")
                return True
    return True


def render_run_results(screen, game, mouse_pos):
    res = game.run_results
    if res is None:
        return
    r = game.renderer
    res["btn_rects"] = {}

    dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    dim.fill((6, 5, 12, 205))
    screen.blit(dim, (0, 0))

    win_w, win_h = 880, 666
    wx = (SCREEN_W - win_w) // 2
    wy = (SCREEN_H - win_h) // 2
    win_r = pygame.Rect(wx, wy, win_w, win_h)
    bd_main = UI_BORDER_GOLD if res["victory"] else (195, 72, 72)
    r.draw_pixel_frame(screen, win_r, UI_PANEL_BG, bd_main, False, 1.0)

    hdr_txt = "ПОХОД ЗАВЕРШЁН — ПОБЕДА!" if res["victory"] else "ГЕРОЙ ПАЛ В ПОДЗЕМЕЛЬЕ"
    hdr_col = (255, 224, 108) if res["victory"] else (245, 98, 92)
    hdr_s = r.font_popup_big.render(hdr_txt, True, hdr_col)
    screen.blit(hdr_s, hdr_s.get_rect(midtop=(win_r.centerx, wy + 24)))

    sub_s = r.font_ui.render(f"{res['hero_name']}  ·  Ярус {res['floor']}", True, UI_TEXT_DIM)
    screen.blit(sub_s, sub_s.get_rect(midtop=(win_r.centerx, wy + 58)))

    # Сводка выручки
    sum_r = pygame.Rect(wx + 28, wy + 92, win_w - 56, 118)
    r.draw_pixel_frame(screen, sum_r, UI_SLOT_BG, UI_BORDER_WOOD, False, 1.0)

    run_coins = res.get("run_coins", 0)
    coins_kept = res.get("coins_kept", 0)
    if res["victory"]:
        coins_line = f"Монеты из похода: +{format_copper_Trigger(coins_kept)} (100%)"
        lead = f"Вынесено и продано скупщику: {res['auto_sold_count']} шт. (+{format_copper_Trigger(res['auto_sold_cp'])})"
    else:
        if run_coins > 0:
            coins_line = f"Монеты из похода (сохранена половина): +{format_copper_Trigger(coins_kept)} из {format_copper_Trigger(run_coins)}"
        else:
            coins_line = "Монеты из похода: 0мм"
        if res["has_strongbox"]:
            if res["auto_sold_count"] > 0 or res["pending"]:
                lead = f"Семейная шкатулка спасла добычу! Автопродажа: {res['auto_sold_count']} шт. (+{format_copper_Trigger(res['auto_sold_cp'])})"
            else:
                lead = "Семейная шкатулка была пуста — спасать оказалось нечего."
        else:
            lead = "Без Семейной шкатулки вещи из рюкзака остались в подземелье."

    total_cp = coins_kept + res["auto_sold_cp"] + res["extra_sold_cp"]
    screen.blit(r.font_ui.render(coins_line, True, COIN_TEXT_COLOR), (sum_r.x + 18, sum_r.y + 14))
    screen.blit(r.font_ui.render(lead, True, UI_TEXT_MAIN), (sum_r.x + 18, sum_r.y + 40))
    tot_line = f"Итого в казну за поход: +{format_copper_Trigger(total_cp)}   ·   В коллекции: +{res['collected_count']}"
    screen.blit(r.font_ui.render(tot_line, True, COIN_TEXT_COLOR), (sum_r.x + 18, sum_r.y + 66))
    bank_str = format_copper_Trigger(game.profile.get("bank_copper", 0))
    screen.blit(r.font_small.render(f"Всего в казне наёмника: {bank_str}", True, UI_TEXT_DIM), (sum_r.x + 18, sum_r.y + 92))
    
    # Блок новых коллекционных предметов
    list_r = pygame.Rect(wx + 28, sum_r.bottom + 16, win_w - 56, 344)
    r.draw_pixel_frame(screen, list_r, UI_SLOT_BG, UI_BORDER_WOOD, False, 1.0)
    sec_lbl = r.font_ui.render("НОВЫЕ КОЛЛЕКЦИОННЫЕ НАХОДКИ (РЫБЫ И КАРТИНЫ):", True, UI_BORDER_HIGHLIGHT)
    screen.blit(sec_lbl, (list_r.x + 18, list_r.y + 14))

    pending = res["pending"]
    if not pending:
        empty_s = r.font_ui.render("Новых коллекционных предметов в этом походе не вынесено.", True, UI_TEXT_DIM)
        screen.blit(empty_s, empty_s.get_rect(center=list_r.center))
    else:
        vis = 4
        sc = max(0, min(max(0, len(pending) - vis), res["scroll"]))
        res["scroll"] = sc
        row_y = list_r.y + 48
        for idx in range(sc, min(len(pending), sc + vis)):
            entry = pending[idx]
            itm = entry["item"]
            row_r = pygame.Rect(list_r.x + 16, row_y, list_r.width - 32, 66)
            r.draw_pixel_frame(screen, row_r, UI_PANEL_BG, itm.rarity_color, False, 1.0)

            r.draw_item_icon(screen, itm.icon, row_r.x + 14, row_r.centery - 20, 40)
            screen.blit(r.font_ui.render(itm.name, True, itm.rarity_color), (row_r.x + 68, row_r.y + 12))
            kind_s = "Коллекция: Рыбы" if itm.type == "fish" else "Коллекция: Картины"
            screen.blit(r.font_small.render(kind_s, True, UI_TEXT_DIM), (row_r.x + 68, row_r.y + 38))

            choice = entry["choice"]
            if choice is None:
                b_col = pygame.Rect(row_r.right - 364, row_r.y + 13, 170, 40)
                b_sell = pygame.Rect(row_r.right - 184, row_r.y + 13, 170, 40)
                res["btn_rects"][("collect", idx)] = b_col
                res["btn_rects"][("sell", idx)] = b_sell

                hc = b_col.collidepoint(mouse_pos)
                r.draw_pixel_frame(screen, b_col, (44, 88, 52) if hc else (30, 64, 38), (110, 225, 135), hc, 1.0)
                tc = r.font_small.render("В КОЛЛЕКЦИЮ", True, (220, 255, 225))
                screen.blit(tc, tc.get_rect(center=b_col.center))

                hs = b_sell.collidepoint(mouse_pos)
                r.draw_pixel_frame(screen, b_sell, (76, 58, 34) if hs else (52, 40, 26), UI_BORDER_GOLD, hs, 1.0)
                price_s = format_copper_Trigger(entry["sell_val"], compact=True)
                ts = r.font_small.render(f"ПРОДАТЬ · {price_s}", True, COIN_TEXT_COLOR)
                screen.blit(ts, ts.get_rect(center=b_sell.center))
            elif choice == "collect":
                done_s = r.font_ui.render("★ ДОБАВЛЕНО В КОЛЛЕКЦИЮ", True, (125, 245, 155))
                screen.blit(done_s, done_s.get_rect(midright=(row_r.right - 18, row_r.centery)))
            else:
                price_s = format_copper_Trigger(entry["sell_val"], compact=True)
                done_s = r.font_ui.render(f"ПРОДАНО (+{price_s})", True, COIN_TEXT_COLOR)
                screen.blit(done_s, done_s.get_rect(midright=(row_r.right - 18, row_r.centery)))
            row_y += 72

        if len(pending) > vis:
            hint_sc = r.font_small.render(f"Колесо мыши — прокрутка ({sc + 1}–{min(len(pending), sc + vis)} из {len(pending)})", True, UI_TEXT_DIM)
            screen.blit(hint_sc, hint_sc.get_rect(midbottom=(list_r.centerx, list_r.bottom - 6)))

    undecided = sum(1 for e in pending if e["choice"] is None)
    btn_r = pygame.Rect(win_r.centerx - 220, win_r.bottom - 74, 440, 52)
    res["btn_rects"]["finish"] = btn_r
    hov_f = btn_r.collidepoint(mouse_pos)
    r.draw_pixel_frame(screen, btn_r, (52, 92, 56) if hov_f else (34, 68, 40), UI_BORDER_GOLD, hov_f, 1.0)
    f_txt = "ПРОДАТЬ ОСТАТОК И В МЕНЮ" if undecided > 0 else "В ГЛАВНОЕ МЕНЮ"
    f_s = r.font_ui.render(f_txt, True, (255, 245, 205))
    screen.blit(f_s, f_s.get_rect(center=btn_r.center))