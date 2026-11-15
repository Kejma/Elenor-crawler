import math
import random

# --- MISSION 1 BESTIARY PROFILES (HARDCORE TUNING) ---
MOB_PROFILES = {
    "rat": {
        "sprite": "rat",
        "hp": 15,
        "speed": 3.20,
        "dmg_min": 4,
        "dmg_max": 7,
        "phys_def": 1,
        "mag_def": 0,
        "detect_range": 5.2,
        "perception": 1.05,
        "is_ranged": False,
        "is_boss": False,
        "size_tiles": 1,
        "xp": 14,
    },
    "rat_cultist": {
        "sprite": "rat_cultist",
        "hp": 28,
        "speed": 2.65,
        "dmg_min": 6,
        "dmg_max": 10,
        "phys_def": 2,
        "mag_def": 3,
        "detect_range": 6.4,
        "perception": 1.15,
        "is_ranged": True,
        "proj_color": (235, 50, 70),
        "is_boss": False,
        "size_tiles": 1,
        "xp": 24,
    },
    "rat_king": {
        "sprite": "rat_king",
        "hp": 240,
        "speed": 2.35,
        "dmg_min": 11,
        "dmg_max": 16,
        "phys_def": 5,
        "mag_def": 5,
        "detect_range": 8.5,
        "perception": 1.45,
        "is_ranged": True,
        "proj_color": (255, 40, 60),
        "is_boss": True,
        "size_tiles": 2,
        "xp": 160,
    },
    "wolf": {
        "sprite": "wolf",
        "hp": 14,
        "speed": 2.95,
        "dmg_min": 3,
        "dmg_max": 6,
        "phys_def": 0,
        "mag_def": 0,
        "detect_range": 5.2,
        "perception": 1.05,
        "is_ranged": False,
        "is_boss": False,
        "size_tiles": 1,
        "xp": 12,
    },
    "skeleton": {
        "sprite": "skeleton",
        "hp": 22,
        "speed": 2.50,
        "dmg_min": 5,
        "dmg_max": 8,
        "phys_def": 2,
        "mag_def": 0,
        "detect_range": 5.2,
        "perception": 0.95,
        "is_ranged": False,
        "is_boss": False,
        "size_tiles": 1,
        "xp": 16,
    },
    "cultist": {
        "sprite": "cultist",
        "hp": 20,
        "speed": 2.30,
        "dmg_min": 5,
        "dmg_max": 9,
        "phys_def": 1,
        "mag_def": 3,
        "detect_range": 6.0,
        "perception": 1.10,
        "is_ranged": True,
        "proj_color": (215, 75, 255),
        "is_boss": False,
        "size_tiles": 1,
        "xp": 18,
    },
    "necromancer": {
        "sprite": "necromancer",
        "hp": 28,
        "speed": 2.00,
        "dmg_min": 6,
        "dmg_max": 10,
        "phys_def": 2,
        "mag_def": 5,
        "detect_range": 6.5,
        "perception": 1.20,
        "is_ranged": True,
        "proj_color": (85, 255, 130),
        "is_boss": False,
        "size_tiles": 1,
        "xp": 26,
    },
    "brute": {
        "sprite": "brute",
        "hp": 36,
        "speed": 1.85,
        "dmg_min": 7,
        "dmg_max": 11,
        "phys_def": 4,
        "mag_def": 1,
        "detect_range": 4.8,
        "perception": 0.85,
        "is_ranged": False,
        "is_boss": False,
        "size_tiles": 1,
        "xp": 24,
    },
}


def get_mission_texts(loc_dict):
    """Возвращает словарь текстов Кампании I напрямую из locales/ru/rat_mission.json."""
    return loc_dict.get("mission_1", {})

def attach_mob_dialogues(mob, loc_dict):
    m1 = get_mission_texts(loc_dict)
    if mob.kind == "rat_cultist":
        mob.solo_lines = list(m1.get("rat_solo", []))
    elif mob.kind == "rat_king":
        mob.solo_lines = list(m1.get("boss_lines", []))


def _scale_mob_for_floor(mob, floor_num):
    """Scales Mission 1 enemies by dungeon depth so skipping rooms is lethal!"""
    if mob.is_boss:
        return
    # Floor 2 = depth 1, Floor 3 = depth 2, Floor 4 = depth 3
    depth = max(0, floor_num - 2)
    hp_mult = 1.0 + depth * 0.38
    dmg_mult = 1.0 + depth * 0.28
    mob.max_hp = int(round(mob.max_hp * hp_mult))
    mob.hp = mob.max_hp
    mob.dmg_min = int(round(mob.dmg_min * dmg_mult))
    mob.dmg_max = max(mob.dmg_min + 1, int(round(mob.dmg_max * dmg_mult)))
    mob.phys_def += depth // 2
    mob.mag_def += depth // 2
    mob.xp_value = int(round(mob.xp_value * (1.0 + depth * 0.25)))


def populate_mission_floor(game, floor_num, EnemyCls, InteractableCls):
    """
    Floor 1: Night Courtyard + Rich Tavern Interior (10 unique decorative props, NPC Hugo, 1 starter weapon rack).
    Floor 2: Wooden Cellar (Rat packs, breakable barrels that drop loot on floor).
    Floor 3: Stone Cellar (Rat Cultists casting pentagrams + armored cellar rats).
    Floor 4: Caves & Giant 18x14 Rat King Boss Chamber (240 HP 2x2 Boss + Cultist retinue).
    """
    m1 = get_mission_texts(game.loc)
    rat_chats = m1.get("rat_chats", [])

    # =========================================================================
    # ЯРУС 1: ДВОР И ДОМ-ТАВЕРНА (АТМОСФЕРНЫЙ ИНТЕРЬЕР БЕЗ ХАЛЯВНОГО ЛУТА)
    # =========================================================================
    if floor_num == 1:
        # Костёр во дворе перед входом + доска заказов у крыльца
        game.objects.append(InteractableCls(10, 20, "campfire"))
        game.objects.append(InteractableCls(15, 18, "notice_board"))

        # Главный зал таверны: Камин, поленница, лютня, трофей вепря, часы, доспех, столы, стойка и Гуго
        game.objects.append(InteractableCls(25, 15, "fireplace"))
        game.objects.append(InteractableCls(27, 15, "firewood_pile"))
        game.objects.append(InteractableCls(23, 15, "lute_stand"))
        game.objects.append(InteractableCls(21, 15, "mounted_boar"))
        game.objects.append(InteractableCls(19, 16, "armor_stand"))
        game.objects.append(InteractableCls(19, 22, "coat_rack"))
        game.objects.append(InteractableCls(19, 24, "notice_board"))

        for tx, ty in ((21, 17), (25, 17), (21, 22), (25, 22)):
            game.objects.append(InteractableCls(tx, ty, "tavern_table"))
        for bx_bench, by_bench in ((20, 17), (26, 17), (20, 22), (26, 22)):
            game.objects.append(InteractableCls(bx_bench, by_bench, "chair_bench"))

        game.objects.append(InteractableCls(29, 19, "npc_innkeeper"))
        for by_bar in (18, 19, 20, 21):
            game.objects.append(InteractableCls(28, by_bar, "bar_counter"))
        game.objects.append(InteractableCls(30, 16, "shelf_bottles"))
        game.objects.append(InteractableCls(30, 23, "wine_cask"))
        game.objects.append(InteractableCls(27, 24, "grandfather_clock"))

        # Северная комната (хозяйская спальня Гуго — кровати, часы, бадья для умывания, книжный шкаф, ковёр)
        game.objects.append(InteractableCls(20, 9, "bed"))
        game.objects.append(InteractableCls(23, 9, "bed"))
        game.objects.append(InteractableCls(26, 9, "grandfather_clock"))
        game.objects.append(InteractableCls(29, 9, "bookshelf"))
        game.objects.append(InteractableCls(20, 12, "wash_basin"))
        game.objects.append(InteractableCls(29, 12, "crate_stack"))

        # Южная комната (кухня и винокурня — котёл, вешала с окороками, бадья, бочки, поленница)
        game.objects.append(InteractableCls(20, 28, "cauldron"))
        game.objects.append(InteractableCls(22, 28, "firewood_pile"))
        game.objects.append(InteractableCls(25, 28, "meat_rack"))
        game.objects.append(InteractableCls(24, 30, "tavern_table"))
        game.objects.append(InteractableCls(28, 28, "wine_cask"))
        game.objects.append(InteractableCls(29, 30, "wine_cask"))
        game.objects.append(InteractableCls(20, 31, "wash_basin"))
        game.objects.append(InteractableCls(27, 31, "crate_stack"))

        # Восточный чулан: стартовая оружейная стойка, доспех, окорока, ящики и спуск в погреб!
        game.objects.append(InteractableCls(35, 17, "rack"))
        game.objects.append(InteractableCls(33, 17, "armor_stand"))
        game.objects.append(InteractableCls(38, 17, "wine_cask"))
        game.objects.append(InteractableCls(40, 17, "meat_rack"))
        game.objects.append(InteractableCls(35, 23, "crate_stack"))
        game.objects.append(InteractableCls(41, 20, "stairs"))
        return

    # =========================================================================
    # ЯРУСЫ 2, 3, 4: ДЕРЕВЯННЫЙ ПОДВАЛ -> КАМЕННЫЙ ПОДВАЛ -> ПЕЩЕРЫ С БОССОМ
    # =========================================================================
    # Размещаем Скупщика Шныря в укромном углу стартовой комнаты каждого этажа!
    if game.dungeon.rooms:
        r0 = game.dungeon.rooms[0]
        mx_npc, my_npc = r0.left + 1, r0.top + 1
        if not game.dungeon.is_blocking_move(mx_npc, my_npc):
            game.objects.append(InteractableCls(mx_npc, my_npc, "npc_merchant"))

    for idx, room in enumerate(game.dungeon.rooms[1:], start=1):
        rx, ry = room.center
        is_last_room = (idx == len(game.dungeon.rooms) - 1)

        if is_last_room:
            if floor_num >= 4:
                # ОГРОМНЫЙ ЗАЛ КРЫСИНОГО КОРОЛЯ (2x2 тайла + свита сектантов и крыс)!
                game.objects.append(InteractableCls(rx - 3, ry, "ritual_altar"))
                boss = EnemyCls(rx + 2, ry, kind="rat_king", state="patrolling")
                game.mobs.append(boss)
                guard_spots = [
                    (room.left + 3, room.top + 3, "rat_cultist"),
                    (room.left + 3, room.bottom - 4, "rat_cultist"),
                    (room.right - 4, room.top + 4, "rat_cultist"),
                    (rx, room.top + 3, "rat"),
                    (rx, room.bottom - 4, "rat"),
                ]
                for gx, gy, g_kind in guard_spots:
                    if not game.dungeon.is_blocking_move(gx, gy):
                        g_mob = EnemyCls(gx, gy, kind=g_kind, state="patrolling")
                        _scale_mob_for_floor(g_mob, floor_num)
                        game.mobs.append(g_mob)
                continue
            else:
                game.objects.append(InteractableCls(rx, ry, "stairs"))
        else:
            if floor_num == 2:
                if idx % 2 == 0:
                    game.objects.append(InteractableCls(rx, ry, "barrel"))
                elif idx % 5 == 1:
                    game.objects.append(InteractableCls(rx, ry, "rack"))
                elif idx % 6 == 3:
                    game.objects.append(InteractableCls(rx, ry, "chest"))
                elif random.random() < 0.16:
                    game.objects.append(InteractableCls(rx, ry, "loot", game.roll_item_by_rarity()))
            elif floor_num == 3:
                if idx % 5 == 0:
                    game.objects.append(InteractableCls(rx, ry, "chest"))
                elif idx % 6 == 2:
                    game.objects.append(InteractableCls(rx, ry, "alchemy"))
                elif idx % 7 == 3:
                    game.objects.append(InteractableCls(rx, ry, "bookshelf"))
                elif idx % 6 == 4:
                    game.objects.append(InteractableCls(rx, ry, "rack"))
                elif idx % 3 == 1:
                    game.objects.append(InteractableCls(rx, ry, "barrel"))
                elif random.random() < 0.16:
                    game.objects.append(InteractableCls(rx, ry, "loot", game.roll_item_by_rarity()))
            else:
                if idx % 5 == 0:
                    game.objects.append(InteractableCls(rx, ry, "idol"))
                elif idx % 6 == 2:
                    game.objects.append(InteractableCls(rx, ry, "chest"))
                elif idx % 7 == 4:
                    game.objects.append(InteractableCls(rx, ry, "alchemy"))
                elif idx % 4 == 1:
                    game.objects.append(InteractableCls(rx, ry, "barrel"))
                elif random.random() < 0.18:
                    game.objects.append(InteractableCls(rx, ry, "loot", game.roll_item_by_rarity()))

        if idx % 3 == 1 and floor_num in (2, 3, 4):
            tx, ty = room.left + 1, room.bottom - 2
            if not game.dungeon.is_blocking_move(tx, ty):
                game.objects.append(InteractableCls(tx, ty, "trap"))

        # Плотное заселение комнат крысами и крысами-сектантами (по 2-3 врага на комнату!)
        mx = random.randint(room.left + 1, room.right - 2)
        my = random.randint(room.top + 1, room.bottom - 2)
        if not game.dungeon.is_blocking_move(mx, my) and math.hypot(mx - rx, my - ry) > 1.0:
            spawned = []
            if floor_num == 2:
                # Ярус 2 (Деревянный погреб): только обычные погребные крысы!
                state = random.choices(["sleeping", "eating", "patrolling"], weights=[15, 30, 55])[0]
                spawned.append(EnemyCls(mx, my, kind="rat", state=state))
                if not game.dungeon.is_blocking_move(mx + 1, my):
                    spawned.append(EnemyCls(mx + 1, my, kind="rat", state="patrolling"))
            elif floor_num == 3:
                # Ярус 3 (Каменный подвал): парочки крыс-сектантов с пентаграммами + крысы-охранники
                if idx % 2 == 0 and rat_chats and not game.dungeon.is_blocking_move(mx + 1, my):
                    dialogue = random.choice(rat_chats)
                    m1_mob = EnemyCls(mx, my, kind="rat_cultist", state="chatting", chat_lines=dialogue)
                    m2_mob = EnemyCls(mx + 1, my, kind="rat_cultist", state="chatting", chat_lines=[])
                    m1_mob.chat_partner = m2_mob
                    m2_mob.chat_partner = m1_mob
                    spawned.extend([m1_mob, m2_mob])
                else:
                    spawned.append(EnemyCls(mx, my, kind="rat_cultist", state="patrolling"))
                    if not game.dungeon.is_blocking_move(mx + 1, my):
                        spawned.append(EnemyCls(mx + 1, my, kind="rat", state="patrolling"))
                    if idx % 3 == 0 and not game.dungeon.is_blocking_move(mx, my + 1):
                        spawned.append(EnemyCls(mx, my + 1, kind="rat", state="eating"))
            else:
                # Ярус 4 (Пещеры): элитные патрули сектантов и стаи крыс
                if idx % 2 == 0 and rat_chats and not game.dungeon.is_blocking_move(mx + 1, my):
                    dialogue = random.choice(rat_chats)
                    m1_mob = EnemyCls(mx, my, kind="rat_cultist", state="chatting", chat_lines=dialogue)
                    m2_mob = EnemyCls(mx + 1, my, kind="rat_cultist", state="chatting", chat_lines=[])
                    m1_mob.chat_partner = m2_mob
                    m2_mob.chat_partner = m1_mob
                    spawned.extend([m1_mob, m2_mob])
                    if not game.dungeon.is_blocking_move(mx, my + 1):
                        spawned.append(EnemyCls(mx, my + 1, kind="rat", state="patrolling"))
                else:
                    spawned.append(EnemyCls(mx, my, kind="rat_cultist", state="patrolling"))
                    if not game.dungeon.is_blocking_move(mx + 1, my):
                        spawned.append(EnemyCls(mx + 1, my, kind="rat_cultist", state="patrolling"))

            for sm in spawned:
                _scale_mob_for_floor(sm, floor_num)
                game.mobs.append(sm)

    for m in game.mobs:
        attach_mob_dialogues(m, game.loc)


def handle_mission_object_interaction(game, obj, EnemyCls, InteractableCls):
    """Обрабатывает уникальные объекты Кампании I (Трактирщик Гуго, декор таверны, бочки, кровавый алтарь)."""
    m1 = get_mission_texts(game.loc)
    prop_thoughts_db = game.loc.get("prop_thoughts", {})

    if obj.kind == "npc_innkeeper":
        npc_cfg = m1.get("npc_innkeeper", {})
        speaker = npc_cfg.get("name", "Трактирщик Гуго")
        if game.try_sell_gems_to_npc(obj, speaker_name=speaker):
            return True

        lines = npc_cfg.get("greeting_lines", ["..."])
        line = lines[obj.talk_index % len(lines)] if lines else "..."
        obj.talk_index += 1
        obj.speech_text = line
        obj.speech_timer = 5.5
        game.sfx.play("mob_talk")
        game.set_thought(line, important=True)
        return True

    if obj.kind in prop_thoughts_db:
        game.sfx.play("step")
        # Осмотр мебели — ФОНОВАЯ мысль (срабатывает с шансом 75% и не чаще раза в 6 секунд!)
        if game.can_trigger_background_thought(chance=0.75):
            game.set_thought(game.pick_text(prop_thoughts_db[obj.kind], f"prop_{obj.kind}"), important=False, chance=1.0)
        return True

    if obj.kind == "barrel":
        obj.used = True
        if hasattr(game, "fx") and game.fx:
            game.fx.add_barrel_debris(obj.x, obj.y)
            game.fx.trigger_shake(1.8, 0.14)
        game.sfx.play("crit")
        game.emit_noise(obj.x + 0.5, obj.y + 0.5, 5.8)
        roll = random.random()
        if roll < 0.26:
            weap_id = random.choice(["rusty_dagger", "wooden_club"])
            itm = game.make_item(weap_id)
            game.objects.append(InteractableCls(obj.x, obj.y, "loot", itm))
            game.trigger_event_thought("barrel_weapon", item=itm.name)
            game.add_popup(obj.x + 0.5, obj.y + 0.5, f"Выпало: {itm.name}", itm.rarity_color)
        elif roll < 0.52:
            pot_id = random.choice(["potion_hp", "potion_hp_weak", "herbal_salve"])
            pot = game.make_item(pot_id if pot_id in game.loc.get("items", {}) else "potion_hp")
            game.objects.append(InteractableCls(obj.x, obj.y, "loot", pot))
            game.trigger_event_thought("barrel_potion", item=pot.name)
            game.add_popup(obj.x + 0.5, obj.y + 0.5, f"Выпало: {pot.name}", (120, 245, 140))
        elif roll < 0.76:
            loot_itm = game.roll_currency_or_gem_drop(allow_gem=True)
            game.objects.append(InteractableCls(obj.x, obj.y, "loot", loot_itm))
            game.sfx.play("coin_drop")
            game.trigger_event_thought("barrel_treasure", item=loot_itm.name)
            game.add_popup(obj.x + 0.5, obj.y + 0.5, f"Выпало: {loot_itm.name}", loot_itm.rarity_color)
        else:
            ambush_rat = EnemyCls(obj.x, obj.y, kind="rat", state="combat")
            _scale_mob_for_floor(ambush_rat, game.dungeon.floor_num)
            ambush_rat.awareness = 100.0
            ambush_rat.alert_bang_timer = 0.38
            game.mobs.append(ambush_rat)
            game.sfx.play("alert")
            # Крыса из бочки — ВАЖНОЕ событие (100% срабатывание)!
            game.trigger_event_thought("barrel_rat_ambush")
            game.add_popup(obj.x + 0.5, obj.y + 0.5, "ЗАСАДА!", (255, 95, 95))
        return True

    if obj.kind == "ritual_altar":
        if any(getattr(m, "is_boss", False) for m in game.mobs):
            game.sfx.play("hurt")
            game.trigger_event_thought("altar_locked")
            return True
        obj.used = True
        game.sfx.play("magic")
        game.emit_noise(obj.x + 0.5, obj.y + 0.5, 7.5)
        game.player.hp = float(game.player.max_hp)
        game.player.mp = float(game.player.max_mp)
        drop = game.roll_item_by_rarity(allowed_types=["equipment"])
        game.objects.append(InteractableCls(obj.x, obj.y, "loot", drop))
        game.trigger_event_thought("altar_heal", item=drop.name)
        game.add_popup(obj.x + 0.5, obj.y + 0.5, "ПОЛНОЕ ИСЦЕЛЕНИЕ!", (120, 245, 155))
        return True

    return False