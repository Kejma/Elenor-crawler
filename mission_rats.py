import math
import random
from entities import MOB_PROFILES


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

    if floor_num >= 4:
        from puzzle_mirrors import spawn_pre_boss_mirror_puzzle
        spawn_pre_boss_mirror_puzzle(
            game, InteractableCls,
            beam_color=(255, 45, 55),
            spawn_chance=1.0
        )

    for m in game.mobs:
        attach_mob_dialogues(m, game.loc)


def handle_mission_object_interaction(game, obj, EnemyCls, InteractableCls):
    """
    Обрабатывает СТРОГО сюжетные объекты Кампании I:
    Трактирщик Гуго, реплики осмотра мебели таверны и ритуальный алтарь Крысиного Короля.
    Базовые пропсы (бочки, сундуки, стойки) обрабатываются общим движком!
    """
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
        game.play_spatial("mob_talk", obj.x + 0.5, obj.y + 0.5)
        game.set_thought(line, important=True)
        return True

    if obj.kind in prop_thoughts_db:
        game.play_spatial("step", obj.x + 0.5, obj.y + 0.5)
        if game.can_trigger_background_thought(chance=0.75):
            game.set_thought(game.pick_text(prop_thoughts_db[obj.kind], f"prop_{obj.kind}"), important=False, chance=1.0)
        return True

    if obj.kind == "ritual_altar":
        if any(getattr(m, "is_boss", False) for m in game.mobs):
            game.play_spatial("hurt", obj.x + 0.5, obj.y + 0.5)
            game.trigger_event_thought("altar_locked")
            return True
        obj.used = True
        game.play_spatial("magic", obj.x + 0.5, obj.y + 0.5)
        game.emit_noise(obj.x + 0.5, obj.y + 0.5, 7.5)
        game.player.hp = float(game.player.max_hp)
        game.player.mp = float(game.player.max_mp)
        drop = game.roll_item_by_rarity(allowed_types=["equipment"])
        game.objects.append(InteractableCls(obj.x, obj.y, "loot", drop))
        game.trigger_event_thought("altar_heal", item=drop.name)
        game.add_popup(obj.x + 0.5, obj.y + 0.5, "ПОЛНОЕ ИСЦЕЛЕНИЕ!", (120, 245, 155))
        return True

    return False


def update_mission_audio(game, dt):
    """
    Звуковой менеджер Кампании I:
    На 4 ярусе (пещеры) транслирует пространственный ритуал от Крысиного Короля.
    В покое — спокойный шаманский бубен, в бою — тревожный боевой марш, после смерти — тишина.
    """
    if getattr(game.dungeon, "floor_num", 1) == 4:
        living_boss = next((m for m in game.mobs if getattr(m, "is_boss", False) and m.hp > 0), None)
        if living_boss is not None:
            theme = "ritual_combat" if living_boss.state == "combat" else "ritual_idle"
            game.sfx.update_ambient_spatial(
                theme,
                game.player.x, game.player.y,
                living_boss.x, living_boss.y,
                dungeon=game.dungeon, max_dist=42.0, max_air_dist=26.0, dt=dt
            )
            return

    # На остальных этажах или после гибели босса музыка ритуала плавно затухает
    game.sfx.update_ambient_spatial(None, game.player.x, game.player.y, 0.0, 0.0, dt=dt)