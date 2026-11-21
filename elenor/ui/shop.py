"""Dungeon merchant shop modal: run-gold trading, tiered stock, and beer tips."""

import random
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

TIER_TITLES = {
    "poor":   ("Скудный привоз", (185, 168, 155)),
    "normal": ("Обычный привоз", UI_BORDER_HIGHLIGHT),
    "rich":   ("Богатый привоз!", (255, 224, 102)),
}

BEER_TIP_COST = 5  # 5 медных монет

BEER_TIP_LINES = [
    "«О, душа-человек! Выпью за твоё здоровье, когда вылезу из этой сырости!»",
    "«На пиво?! Да ты лучший клиент за весь месяц, держи спину ровно!»",
    "«Благодарю! Гуго мне давно в долг не наливает, а тут такая щедрость.»",
    "«Вот это разговор! Если что — я тебя не видел, а ты не видел, откуда товар.»",
    "«Ещё кружечку? Эх, споишь ты старого Шныря прямо за прилавком!»",
    "«Всё, после смены гуляем! За такого щедрого наёмника хоть до дна!»",
]

NO_BEER_MONEY_LINES = [
    "«Даже пяти медяков на пиво не нашлось? Иди потряси пару крыс сначала!»",
    "«Карманы пустые, а туда же — угощать лезет. Продай хоть что-нибудь!»",
]


def generate_merchant_stock(game, tier="normal"):
    """Generates random stock for the floor merchant; always includes >= 1 HP and >= 1 MP potion."""
    luck = getattr(getattr(game, "player", None), "luck", 1)
    floor_num = getattr(getattr(game, "dungeon", None), "floor_num", 2)
    items_db = game.loc.get("items", {})
    stock = []

    # 1. Гарантированные зелья лечения и маны
    if tier == "rich":
        hp_ids = ["potion_hp_strong", "potion_hp"]
        mp_count = random.choice([1, 2])
    elif tier == "poor":
        hp_ids = [random.choice(["potion_hp_weak", "herbal_salve", "potion_hp"])]
        mp_count = 1
    else:
        hp_ids = ["potion_hp"] + (["herbal_salve"] if random.random() < 0.45 else [])
        mp_count = 1

    for hid in hp_ids:
        stock.append(game.make_item(hid if hid in items_db else "potion_hp"))
    for _ in range(mp_count):
        stock.append(game.make_item("potion_mp"))

    # 2. Основной арсенал по уровню богатства лавки
    if tier == "poor":
        gear_n = random.randint(1, 2)
        bag_n = 1 if random.random() < 0.35 else 0
        scroll_n = 0
        luck_mod = max(1, luck - 1)
    elif tier == "rich":
        gear_n = random.randint(4, 5)
        bag_n = random.randint(1, 2)
        scroll_n = random.randint(1, 2)
        luck_mod = luck + 3 + max(0, floor_num - 2)
    else:
        gear_n = random.randint(2, 3)
        bag_n = 1
        scroll_n = 1 if random.random() < 0.65 else 0
        luck_mod = luck + max(0, floor_num - 2)

    seen_ids = set()
    for _ in range(gear_n):
        itm = game.roll_item_by_rarity(allowed_types=["equipment"], luck=luck_mod)
        if itm and itm.id not in seen_ids:
            seen_ids.add(itm.id)
            stock.append(itm)

    for _ in range(bag_n):
        bag = game.roll_bag_drop(luck_mod)
        if bag and bag.id not in seen_ids:
            seen_ids.add(bag.id)
            stock.append(bag)

    scroll_pool = [iid for iid in ("scroll_spark", "scroll_fireball", "oblivion_seal") if iid in items_db]
    for _ in range(scroll_n):
        if scroll_pool:
            sid = random.choice(scroll_pool if tier == "rich" else scroll_pool[:2])
            stock.append(game.make_item(sid))

    return stock


def open_merchant_shop(game, npc):
    if getattr(npc, "shop_stock", None) is None:
        tier = getattr(npc, "shop_tier", getattr(game.dungeon, "merchant_tier", "normal"))
        npc.shop_tier = tier
        npc.shop_stock = generate_merchant_stock(game, tier)
        npc.beer_tips = 0

    tier = npc.shop_tier
    greetings = {
        "poor":   "«Сегодня полки пустоваты, зато куплю твой хабар без лишних вопросов.»",
        "normal": "«Заходи, приценивайся! Оплата монетами из похода — честный обмен.»",
        "rich":   "«Ого, вовремя заглянул! Только-только разгрузил свежий обоз — гляди, какая красота!»",
    }
    game.inv_open = False
    game.journal_open = False
    game.levelup_choices = None
    game.player.buffered_combat = None
    game.shop_state = {
        "npc": npc,
        "tier": tier,
        "status": greetings.get(tier, greetings["normal"]),
        "status_col": UI_TEXT_MAIN,
        "inv_scroll": 0,
        "buy_rects": [],
        "sell_rects": [],
        "btn_rects": {},
    }
    game.sfx.play("ui")


def _sell_all_gems_to_run_wallet(game, st):
    player = game.player
    sold_cnt = 0
    total_cp = 0
    for idx in range(player.unlocked_slots):
        itm = player.inventory[idx]
        if itm and itm.type == "gem":
            val = getattr(itm, "sell_value", 0) or getattr(itm, "copper_value", 0)
            if val > 0:
                sold_cnt += 1
                total_cp += val
                player.remove_item_everywhere(itm)
    if sold_cnt > 0:
        player.gold += total_cp
        val_str = format_copper_Trigger(total_cp)
        st["status"] = f"Продано драгоценностей ({sold_cnt} шт.) за +{val_str} в кошелёк похода!"
        st["status_col"] = COIN_TEXT_COLOR
        game.add_log("event", f"Продано Шнырю драгоценностей ({sold_cnt} шт.): +{val_str}.", COIN_TEXT_COLOR)
        game.sfx.play("coin_pickup")
    else:
        st["status"] = "В поклаже нет обычных драгоценностей (рыбы и картины продаются вручную)."
        st["status_col"] = UI_TEXT_DIM
        game.sfx.play("hurt")


def _buy_item(game, st, idx):
    npc = st["npc"]
    stock = npc.shop_stock
    if not (0 <= idx < len(stock)):
        return
    itm = stock[idx]
    price = max(1, getattr(itm, "buy_value", 0) or getattr(itm, "copper_value", 10))
    if game.player.gold < price:
        st["status"] = f"Не хватает монет! Нужно {format_copper_Trigger(price, compact=True)}."
        st["status_col"] = (245, 115, 110)
        game.sfx.play("hurt")
        return

    placed = False
    if itm.type == "bag" and None in game.player.bag_slots:
        placed = game.equip_bag(itm, game.player.bag_slots.index(None))
    if not placed:
        placed = game.player.add_item_to_inventory(itm)
    if not placed:
        st["status"] = "Нет свободного места в поклаже!"
        st["status_col"] = (245, 165, 110)
        game.sfx.play("hurt")
        return

    game.player.gold -= price
    stock.pop(idx)
    p_str = format_copper_Trigger(price, compact=True)
    st["status"] = f"Куплено: {itm.name} (-{p_str})."
    st["status_col"] = (130, 245, 155)
    game.add_log("event", f"Куплено у Шныря: {itm.name} за {p_str}.", COIN_TEXT_COLOR)
    game.sfx.play("coin_pickup")


def _sell_player_item(game, st, slot_idx):
    player = game.player
    if not (0 <= slot_idx < player.unlocked_slots):
        return
    itm = player.inventory[slot_idx]
    if itm is None:
        return
    val = getattr(itm, "sell_value", 0) or getattr(itm, "copper_value", 0)
    if val <= 0 or itm.type == "quest_key":
        st["status"] = "Шнырь отмахивается: «За такое я и медяка не дам.»"
        st["status_col"] = UI_TEXT_DIM
        game.sfx.play("hurt")
        return

    player.remove_item_everywhere(itm)
    player.gold += val
    v_str = format_copper_Trigger(val, compact=True)
    st["status"] = f"Продано: {itm.name} (+{v_str} в кошелёк похода)."
    st["status_col"] = COIN_TEXT_COLOR
    game.add_log("event", f"Продано Шнырю: {itm.name} (+{v_str}).", COIN_TEXT_COLOR)
    game.sfx.play("coin_pickup")


def _give_beer_tip(game, st):
    npc = st["npc"]
    if game.player.gold < BEER_TIP_COST:
        line = random.choice(NO_BEER_MONEY_LINES)
        st["status"] = line
        st["status_col"] = (245, 140, 120)
        game.sfx.play("hurt")
        return

    game.player.gold -= BEER_TIP_COST
    tips = getattr(npc, "beer_tips", 0)
    npc.beer_tips = tips + 1
    line = BEER_TIP_LINES[min(tips, len(BEER_TIP_LINES) - 1)]
    st["status"] = f"{line}  (Кружек угощено: {npc.beer_tips})"
    st["status_col"] = (255, 222, 115)
    npc.speech_text = line
    npc.speech_timer = 5.5
    game.set_thought(line, important=True)
    game.add_log("speech", f"Шнырю на пиво (-5мм): {line}", (255, 222, 115))
    game.sfx.play("coin_pickup")


def handle_shop_event(game, event, mouse_pos):
    st = getattr(game, "shop_state", None)
    if st is None:
        return False

    if event.type == pygame.KEYDOWN:
        if event.key in (pygame.K_ESCAPE, pygame.K_i, pygame.K_TAB):
            game.shop_state = None
            game.sfx.play("ui")
        return True

    if event.type == pygame.MOUSEWHEEL:
        max_sc = st.get("max_inv_scroll", 0)
        st["inv_scroll"] = max(0, min(max_sc, st.get("inv_scroll", 0) - event.y * 42))
        return True

    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        pos = getattr(event, "pos", mouse_pos)
        for key, rect in list(st.get("btn_rects", {}).items()):
            if rect.collidepoint(pos):
                if key == "close":
                    game.shop_state = None
                    game.sfx.play("ui")
                elif key == "sell_gems":
                    _sell_all_gems_to_run_wallet(game, st)
                elif key == "beer_tip":
                    _give_beer_tip(game, st)
                return True

        for idx, rect in st.get("buy_rects", []):
            if rect.collidepoint(pos):
                _buy_item(game, st, idx)
                return True

        for slot_idx, rect in st.get("sell_rects", []):
            if rect.collidepoint(pos):
                _sell_player_item(game, st, slot_idx)
                return True

        modal_r = st.get("modal_rect")
        if modal_r is not None and not modal_r.collidepoint(pos):
            game.shop_state = None
            game.sfx.play("ui")
        return True

    return True


def render_shop(screen, game, mouse_pos):
    st = getattr(game, "shop_state", None)
    if st is None:
        return
    r = game.renderer
    player = game.player
    npc = st["npc"]
    stock = npc.shop_stock

    dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    dim.fill((6, 5, 12, 195))
    screen.blit(dim, (0, 0))

    win_w, win_h = 1120, 620
    wx = (SCREEN_W - win_w) // 2
    wy = (SCREEN_H - win_h) // 2
    modal_r = pygame.Rect(wx, wy, win_w, win_h)
    st["modal_rect"] = modal_r
    st["btn_rects"] = {}
    st["buy_rects"] = []
    st["sell_rects"] = []

    r.draw_pixel_frame(screen, modal_r, UI_PANEL_BG, UI_BORDER_GOLD, False, 1.0)

    # Шапка
    tier_lbl, tier_col = TIER_TITLES.get(st["tier"], TIER_TITLES["normal"])
    title_s = r.font_title.render(f"ЛАВКА ШНЫРЯ  ·  {tier_lbl}", True, tier_col)
    screen.blit(title_s, (wx + 24, wy + 18))

    wallet_str = format_copper_Trigger(player.gold)
    wal_s = r.font_ui.render(f"Монеты в походе: {wallet_str}", True, COIN_TEXT_COLOR)
    screen.blit(wal_s, (wx + win_w - wal_s.get_width() - 72, wy + 20))

    b_close = pygame.Rect(modal_r.right - 48, wy + 14, 34, 34)
    st["btn_rects"]["close"] = b_close
    hov_c = b_close.collidepoint(mouse_pos)
    r.draw_pixel_frame(screen, b_close, (108, 34, 40) if hov_c else (56, 24, 30), UI_BORDER_WOOD, hov_c, 1.0)
    xs = r.font_ui.render("X", True, UI_TEXT_MAIN)
    screen.blit(xs, xs.get_rect(center=b_close.center))

    # Две колонки: Прилавок (слева) и Поклажа героя (справа)
    left_r = pygame.Rect(wx + 20, wy + 58, 534, 430)
    right_r = pygame.Rect(left_r.right + 12, wy + 58, 534, 430)
    r.draw_pixel_frame(screen, left_r, UI_SLOT_BG, UI_BORDER_WOOD, False, 1.0)
    r.draw_pixel_frame(screen, right_r, UI_SLOT_BG, UI_BORDER_WOOD, False, 1.0)

    screen.blit(r.font_ui.render("ПРИЛАВОК (клик — купить)", True, UI_BORDER_HIGHLIGHT), (left_r.x + 16, left_r.y + 12))
    screen.blit(r.font_ui.render("ВАША ПОКЛАЖА (клик — продать)", True, UI_BORDER_HIGHLIGHT), (right_r.x + 16, right_r.y + 12))

    hovered_item = None
    hover_compare = False

    # 1. Левая панель: товары торговца (2 колонки карточек)
    if not stock:
        empty_s = r.font_ui.render("Прилавок пуст — ты скупил вообще всё!", True, UI_TEXT_DIM)
        screen.blit(empty_s, empty_s.get_rect(center=left_r.center))
    else:
        col_w = 246
        row_h = 56
        gap_x, gap_y = 10, 8
        for idx, itm in enumerate(stock[:12]):
            row, col = divmod(idx, 2)
            ir = pygame.Rect(left_r.x + 16 + col * (col_w + gap_x), left_r.y + 42 + row * (row_h + gap_y), col_w, row_h)
            st["buy_rects"].append((idx, ir))
            price = max(1, getattr(itm, "buy_value", 0) or getattr(itm, "copper_value", 10))
            can_buy = player.gold >= price
            hov = ir.collidepoint(mouse_pos)
            bg = (46, 38, 54) if hov else UI_PANEL_BG
            r.draw_pixel_frame(screen, ir, bg, itm.rarity_color, hov, 1.0)
            r.draw_item_icon(screen, itm.icon, ir.x + 8, ir.centery - 16, 32)
            name_cut = itm.name if len(itm.name) <= 22 else (itm.name[:21] + "…")
            screen.blit(r.font_small.render(name_cut, True, itm.rarity_color), (ir.x + 46, ir.y + 9))
            p_str = format_copper_Trigger(price, compact=True)
            p_col = COIN_TEXT_COLOR if can_buy else (225, 98, 95)
            screen.blit(r.font_small.render(f"Купить: {p_str}", True, p_col), (ir.x + 46, ir.y + 29))
            if hov:
                hovered_item = itm
                hover_compare = (itm.type == "equipment")

    # 2. Правая панель: поклажа игрока со скроллом (6 в ряд)
    vp_r = pygame.Rect(right_r.x + 12, right_r.y + 40, right_r.width - 24, right_r.height - 52)
    per_row = 6
    cell_w, cell_h = 76, 62
    stride_x, stride_y = 82, 68

    carried = [(i, player.inventory[i]) for i in range(player.unlocked_slots) if player.inventory[i] is not None]
    rows_cnt = max(1, (len(carried) + per_row - 1) // per_row)
    total_h = rows_cnt * stride_y
    st["max_inv_scroll"] = max(0, total_h - vp_r.height)
    sc = max(0, min(st["max_inv_scroll"], st.get("inv_scroll", 0)))
    st["inv_scroll"] = sc

    if not carried:
        e_s = r.font_ui.render("В поклаже пусто.", True, UI_TEXT_DIM)
        screen.blit(e_s, e_s.get_rect(center=vp_r.center))
    else:
        old_clip = screen.get_clip()
        screen.set_clip(old_clip.clip(vp_r))
        for pos_i, (slot_idx, itm) in enumerate(carried):
            row, col = divmod(pos_i, per_row)
            cr = pygame.Rect(vp_r.x + 4 + col * stride_x, vp_r.y + row * stride_y - sc, cell_w, cell_h)
            clipped = cr.clip(vp_r)
            if clipped.width <= 0 or clipped.height <= 0:
                continue
            st["sell_rects"].append((slot_idx, clipped))
            hov = clipped.collidepoint(mouse_pos)
            val = getattr(itm, "sell_value", 0) or getattr(itm, "copper_value", 0)
            r.draw_pixel_frame(screen, cr, (46, 38, 54) if hov else UI_PANEL_BG, itm.rarity_color, hov, 1.0)
            r.draw_item_icon(screen, itm.icon, cr.centerx - 16, cr.y + 6, 32)
            v_str = format_copper_Trigger(val, compact=True) if val > 0 else "—"
            v_s = r.font_small.render(v_str, True, COIN_TEXT_COLOR if val > 0 else UI_TEXT_DIM)
            screen.blit(v_s, v_s.get_rect(midbottom=(cr.centerx, cr.bottom - 5)))
            if hov:
                hovered_item = itm
                hover_compare = False
        screen.set_clip(old_clip)

    # Нижняя панель: статус + кнопки «Продать драгоценности» и «Дать на пиво»
    st_box = pygame.Rect(wx + 20, left_r.bottom + 10, win_w - 40, 36)
    pygame.draw.rect(screen, (20, 17, 28), st_box, border_radius=4)
    pygame.draw.rect(screen, UI_BORDER_WOOD, st_box, 1, border_radius=4)
    st_s = r.font_small.render(st["status"], True, st["status_col"])
    screen.blit(st_s, st_s.get_rect(midleft=(st_box.x + 14, st_box.centery)))

    btn_y = st_box.bottom + 12
    # Подсчёт обычных драгоценностей (без коллекционок)
    gem_cp = sum(
        (getattr(itm, "sell_value", 0) or getattr(itm, "copper_value", 0))
        for itm in player.inventory[:player.unlocked_slots]
        if itm and itm.type == "gem"
    )
    b_gems = pygame.Rect(wx + 20, btn_y, 370, 50)
    st["btn_rects"]["sell_gems"] = b_gems
    hov_g = b_gems.collidepoint(mouse_pos)
    bg_g = ((68, 56, 32) if hov_g else (48, 38, 24)) if gem_cp > 0 else (28, 24, 32)
    r.draw_pixel_frame(screen, b_gems, bg_g, UI_BORDER_GOLD if gem_cp > 0 else UI_BORDER_WOOD, hov_g and gem_cp > 0, 1.0)
    g_txt = f"ПРОДАТЬ ДРАГОЦЕННОСТИ (+{format_copper_Trigger(gem_cp, compact=True)})" if gem_cp > 0 else "ДРАГОЦЕННОСТЕЙ НЕТ"
    gs = r.font_small.render(g_txt, True, COIN_TEXT_COLOR if gem_cp > 0 else UI_TEXT_DIM)
    screen.blit(gs, gs.get_rect(center=b_gems.center))

    # Кнопка «Дать на пиво»
    b_beer = pygame.Rect(b_gems.right + 16, btn_y, 290, 50)
    st["btn_rects"]["beer_tip"] = b_beer
    hov_b = b_beer.collidepoint(mouse_pos)
    r.draw_pixel_frame(screen, b_beer, (64, 52, 34) if hov_b else (42, 34, 26), UI_BORDER_HIGHLIGHT if hov_b else UI_BORDER_WOOD, hov_b, 1.0)
    bs = r.font_ui.render(f"ДАТЬ НА ПИВО ({BEER_TIP_COST}мм)", True, (255, 222, 115))
    screen.blit(bs, bs.get_rect(center=b_beer.center))

    # Кнопка «Уйти»
    b_exit = pygame.Rect(modal_r.right - 220, btn_y, 200, 50)
    st["btn_rects"]["close"] = b_exit
    hov_e = b_exit.collidepoint(mouse_pos)
    r.draw_pixel_frame(screen, b_exit, (54, 42, 48) if hov_e else UI_SLOT_BG, UI_BORDER_WOOD, hov_e, 1.0)
    es = r.font_ui.render("ЗАКРЫТЬ [ESC]", True, UI_TEXT_MAIN)
    screen.blit(es, es.get_rect(center=b_exit.center))

    # Тултип предмета при наведении
    if hovered_item is not None:
        ui_bundle = dict(game.loc["ui"], _game_ref=game)
        r._render_item_tooltip(screen, player, hovered_item, ui_bundle, mouse_pos, compare=hover_compare)