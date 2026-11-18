import math
import os
import random
import pygame

from elenor.config import SCREEN_W, SCREEN_H, TILE_W, TILE_H, VIEW_W, VIEW_H, CANVAS_H, SCALE, THOUGHT_BOX_X, THOUGHT_BOX_W, TORCH_Z_HEIGHT, PIER, SHALLOW_WATER, FALLEN_LOG
from elenor.entities import Enemy, Interactable, Particle
from elenor.missions.rats import update_mission_audio
from elenor.profile import apply_display_mode, map_window_to_logical, present_logical_canvas


from elenor.game.controller import GameController
from elenor.game.targeting import is_cursor_on_mob

from elenor.minigames.fishing import press_fishing, start_fishing, update_fishing
from elenor.ui.fishing import draw_fishing
from elenor.ui.exploration_map import chart_surface, draw_map
from elenor.ui.clipboard import copy_text


def _copy_journal_seed(game):
    copied = copy_text(str(game.run_seed))
    game.seed_copy_message = "copied" if copied else "copy_failed"
    game.seed_copy_until = pygame.time.get_ticks() + 2200
    game.sfx.play("ui" if copied else "hurt")


def main():
    os.environ["SDL_RENDER_SCALE_QUALITY"] = "0"
    os.environ["SDL_VIDEO_CENTERED"] = "1"
    pygame.init()

    # Внутренний эталонный холст игры (всегда 1152x858, чтобы ни один пиксель не мылился!)
    screen = pygame.Surface((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Elenor-crawler")
    clock = pygame.time.Clock()

    game = GameController()
    apply_display_mode(game.profile, game)
    running = True
    map_chart = None

    while running:
        dt = min(0.05, clock.tick(0) / 1000.0)
        t = pygame.time.get_ticks() * 0.005
        mouse_pos = map_window_to_logical(pygame.mouse.get_pos(), game.viewport_rect)

        if game.in_main_menu:
            game.sfx.start_menu_music("scottishe Sunshine.json")
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    break
                if game.in_main_menu:
                    if hasattr(event, "pos"):
                        event.pos = map_window_to_logical(event.pos, game.viewport_rect)
                    game.main_menu.handle_event(event, getattr(event, "pos", mouse_pos))
            if not running:
                break
            if not game.in_main_menu:
                continue
            game.main_menu.update(dt)
            game.main_menu.render(screen, dt, mouse_pos)
            present_logical_canvas(game.display_surface, screen, game.viewport_rect)
            pygame.display.flip()
            continue

        game.sfx.stop_menu_music(fade_ms=500)
        world_mx = (mouse_pos[0] / SCALE + game.cam_x) / TILE_W
        world_my = (mouse_pos[1] / SCALE + game.cam_y) / TILE_H

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break
            if game.in_main_menu:
                continue

            key_down = event.type == pygame.KEYDOWN and not getattr(event, "repeat", False)
            if game.map_open:
                if key_down and event.key in (pygame.K_m, pygame.K_ESCAPE):
                    game.map_open = False
                    map_chart = None
                    game.sfx.play("ui")
                continue
            if (key_down and event.key == pygame.K_m
                    and not game.inv_open and not game.levelup_choices and game.fishing_cast is None):
                game.map_open = True
                map_chart = chart_surface(game.dungeon)
                game.sfx.play("ui")
                continue
            if hasattr(event, "pos"):
                event.pos = map_window_to_logical(event.pos, game.viewport_rect)

            click_world = event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and event.pos[1] < VIEW_H * SCALE
            press_space = event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE and not getattr(event, "repeat", False)
            if click_world:
                aim = ((event.pos[0] / SCALE + game.cam_x) / TILE_W,
                       (event.pos[1] / SCALE + game.cam_y) / TILE_H)
            else:
                aim = (world_mx, world_my)

            cast = game.fishing_cast
            if cast is not None:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    game.fishing_cast = None
                elif press_space:
                    press_fishing(game)
                elif event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
                    cast.reeling = False
                elif event.type == pygame.WINDOWFOCUSLOST:
                    cast.reeling = False
                continue

            if hasattr(game, "fx") and game.fx:
                if game.fx.handle_event(event, Enemy, Interactable):
                    continue

            if hasattr(game, "dev_panel") and game.dev_panel:
                if game.dev_panel.handle_event(event, game, world_mx, world_my):
                    continue

            if game.inv_open and game.journal_open and not game.levelup_choices:
                copy_click = click_world and game.renderer.journal_seed_rect.collidepoint(event.pos)
                copy_key = (key_down and event.key == pygame.K_c
                            and getattr(event, "mod", 0) & (pygame.KMOD_CTRL | pygame.KMOD_GUI))
                if copy_click or copy_key:
                    _copy_journal_seed(game)
                    continue

            if game.campaign == "jungle" and (click_world or press_space):
                player_tile = int(game.player.x), int(game.player.y)
                if player_tile in game.dungeon.fishing_edges and not game.inv_open and not game.levelup_choices:
                    if (click_world or mouse_pos[1] < VIEW_H * SCALE) and start_fishing(game, *aim):
                        continue

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if game.inv_open:
                        game.inv_open = False
                    else:
                        game.in_main_menu = True
                        game.main_menu.can_resume = game.player.hp > 0
                    game.sfx.play("ui")
                    continue
                elif event.key == pygame.K_F5:
                    game.reset_run()
                elif event.key in (pygame.K_i, pygame.K_TAB):
                    game.inv_open = not game.inv_open
                    if not game.inv_open:
                        game.journal_open = False
                    game.drag_item = None
                    game.drag_source = None
                    game.sfx.play("ui")
                elif event.key == pygame.K_j:
                    if not game.inv_open:
                        game.inv_open = True
                        game.journal_open = True
                    else:
                        game.journal_open = not game.journal_open
                    game.drag_item = None
                    game.drag_source = None
                    game.sfx.play("ui")
                elif event.key == pygame.K_t:
                    game.trigger_torch_toggle()
                elif event.key == pygame.K_SPACE:
                    game.try_interact_or_melee(world_mx, world_my, via_mouse=False)
                elif event.key in (pygame.K_q, pygame.K_e, pygame.K_r, pygame.K_f):
                    if not game.inv_open and not game.levelup_choices:
                        ab_idx = (pygame.K_q, pygame.K_e, pygame.K_r, pygame.K_f).index(event.key)
                        game.use_or_equip_item(game.player.ability_slots[ab_idx], world_mx, world_my, from_hotbar=True)
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                    slot_idx = event.key - pygame.K_1
                    if game.levelup_choices and slot_idx < len(game.levelup_choices["choices"]):
                        game.select_perk_choice(slot_idx)
                        continue
                    if slot_idx < 4:
                        assigned = False
                        if game.inv_open:
                            for i, sr in enumerate(game.renderer.inv_slot_rects):
                                if i < game.player.unlocked_slots and sr.collidepoint(mouse_pos):
                                    itm = game.player.inventory[i]
                                    if itm and itm.type in ("consumable", "consumable_spell", "consumable_eraser"):
                                        game.player.hotbar[slot_idx] = itm
                                        game.sfx.play("ui")
                                        assigned = True
                                    break
                        if not assigned and not game.inv_open:
                            game.use_or_equip_item(game.player.hotbar[slot_idx], world_mx, world_my, from_hotbar=True)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if game.levelup_choices:
                        for idx, card_r in enumerate(game.renderer.perk_card_rects):
                            if card_r.collidepoint(mouse_pos):
                                game.select_perk_choice(idx)
                                break
                        continue
                    if game.renderer.bag_btn_rect.collidepoint(mouse_pos):
                        game.inv_open = not game.inv_open
                        game.drag_item = None
                        game.drag_source = None
                        game.sfx.play("ui")
                    else:
                        clicked_ui = False
                        for i, ar in enumerate(game.renderer.ability_rects):
                            if ar.collidepoint(mouse_pos):
                                game.use_or_equip_item(game.player.ability_slots[i], world_mx, world_my, from_hotbar=True)
                                clicked_ui = True
                                break
                        for i, hr in enumerate(game.renderer.hotbar_rects):
                            if hr.collidepoint(mouse_pos):
                                game.use_or_equip_item(game.player.hotbar[i], world_mx, world_my, from_hotbar=True)
                                clicked_ui = True
                                break
                        if game.inv_open:
                            clicked_ui = True
                            if game.renderer.journal_btn_rect.collidepoint(mouse_pos):
                                game.journal_open = not game.journal_open
                                game.journal_scroll = 0
                                game.drag_item = None
                                game.drag_source = None
                                game.sfx.play("ui")
                            elif game.journal_open:
                                for f_key, f_rect in game.renderer.journal_filter_rects.items():
                                    if f_rect.collidepoint(mouse_pos):
                                        game.journal_filters[f_key] = not game.journal_filters.get(f_key, True)
                                        game.journal_scroll = 0
                                        game.sfx.play("ui")
                                        break
                            else:
                                for s_key, s_rect in game.renderer.equip_slot_rects.items():
                                    if s_key != "bag" and s_rect.collidepoint(mouse_pos):
                                        itm = game.player.equipment.get(s_key)
                                        if itm:
                                            game.drag_item = itm
                                            game.drag_source = ("equip", s_key)
                                        break
                                for i, sr in enumerate(game.renderer.inv_slot_rects):
                                    if i < game.player.unlocked_slots and sr.collidepoint(mouse_pos):
                                        itm = game.player.inventory[i]
                                        if itm:
                                            game.drag_item = itm
                                            game.drag_source = ("pocket", i)
                                        break
                        if not clicked_ui and click_world:
                            game.try_interact_or_melee(*aim, via_mouse=True)

                elif event.button == 3:
                    if game.levelup_choices and game.levelup_choices.get("mode") == "erase":
                        game.levelup_choices = None
                        game.sfx.play("ui")
                    elif game.inv_open:
                        for i, sr in enumerate(game.renderer.inv_slot_rects):
                            if i < game.player.unlocked_slots and sr.collidepoint(mouse_pos):
                                itm = game.player.inventory[i]
                                if itm:
                                    game.drop_item_on_floor(itm)
                                break

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if game.drag_item:
                    dropped = False
                    for i, hr in enumerate(game.renderer.hotbar_rects):
                        if hr.collidepoint(mouse_pos) and game.drag_item.type in ("consumable", "consumable_spell", "consumable_eraser"):
                            game.player.hotbar[i] = game.drag_item
                            game.sfx.play("ui")
                            dropped = True
                            break

                    if not dropped and game.inv_open:
                        if not game.renderer.modal_rect.collidepoint(mouse_pos):
                            game.drop_item_on_floor(game.drag_item)
                            dropped = True
                        else:
                            for s_key, s_rect in game.renderer.equip_slot_rects.items():
                                if s_key != "bag" and s_rect.collidepoint(mouse_pos):
                                    if game.drag_source == ("equip", s_key):
                                        game.player.unequip_slot(s_key)
                                        game.sfx.play("ui")
                                    elif game.drag_item.type == "equipment":
                                        slot_match = (game.drag_item.slot == s_key) or (game.drag_item.slot == "ring" and s_key in ("ring_1", "ring_2"))
                                        if slot_match:
                                            game.use_or_equip_item(game.drag_item)
                                    dropped = True
                                    break

                            if not dropped:
                                for i, sr in enumerate(game.renderer.inv_slot_rects):
                                    if i < game.player.unlocked_slots and sr.collidepoint(mouse_pos):
                                        if game.drag_source == ("pocket", i):
                                            game.use_or_equip_item(game.drag_item)
                                        elif game.drag_source and game.drag_source[0] == "pocket":
                                            src_i = game.drag_source[1]
                                            game.player.swap_inventory_slots(src_i, i)
                                            game.sfx.play("ui")
                                        elif game.drag_source and game.drag_source[0] == "equip":
                                            eq_slot = game.drag_source[1]
                                            target_itm = game.player.inventory[i]
                                            if target_itm is None:
                                                game.player.inventory[i] = game.drag_item
                                                game.player.equipment[eq_slot] = None
                                                game.sfx.play("ui")
                                            elif target_itm.type == "equipment" and (target_itm.slot == eq_slot or (target_itm.slot == "ring" and eq_slot in ("ring_1", "ring_2"))):
                                                game.player.equipment[eq_slot] = target_itm
                                                game.player.inventory[i] = game.drag_item
                                                game.sfx.play("ui")
                                        break
                    game.drag_item = None
                    game.drag_source = None

            elif event.type == pygame.MOUSEWHEEL:
                if game.inv_open and game.journal_open:
                    game.journal_scroll = max(0, game.journal_scroll + event.y * 3)

        if not running:
            break
        if game.in_main_menu:
            continue
        if game.map_open:
            draw_map(screen, game, map_chart, mouse_pos)
            present_logical_canvas(game.display_surface, screen, game.viewport_rect)
            pygame.display.flip()
            clock.tick(30)
            continue

        # The bank is still rendered and its water animates during a cast.
        if game.fishing_cast is not None:
            if pygame.key.get_focused():
                update_fishing(game, dt)
            if game.fishing_cast is not None:
                dt = 0.0

        # --- REALTIME UPDATE ---
        game.update_typewriter(dt)

        if game.levelup_choices and game.levelup_choices.get("lock_timer", 0.0) > 0.0:
            game.levelup_choices["lock_timer"] = max(0.0, game.levelup_choices["lock_timer"] - dt)

        if game.player.levelup_delay_timer > 0.0:
            game.player.levelup_delay_timer = max(0.0, game.player.levelup_delay_timer - dt)
            if random.random() < 0.65:
                rx = game.player.x + random.uniform(-0.35, 0.35)
                ry = game.player.y + random.uniform(-0.2, 0.2)
                game.particles.append(Particle(rx, ry, 0.0, -2.2, (255, 235, 110), 2.8, 0.35))
            if game.player.levelup_delay_timer <= 0.0 and not game.levelup_choices and game.player.pending_perk_rolls > 0:
                game.roll_perk_choices()

        for obj in game.objects:
            if getattr(obj, "speech_timer", 0.0) > 0.0:
                obj.speech_timer = max(0.0, obj.speech_timer - dt)
                if obj.speech_timer <= 0.0:
                    obj.speech_text = None

        dev_open = getattr(getattr(game, "dev_panel", None), "is_open", False)

        if game.fishing_cast is None and game.player.hp > 0 and not game.inv_open and not game.levelup_choices and not dev_open:
            keys = pygame.key.get_pressed()
            dx = (1 if (keys[pygame.K_d] or keys[pygame.K_RIGHT]) else 0) - (1 if (keys[pygame.K_a] or keys[pygame.K_LEFT]) else 0)
            dy = (1 if (keys[pygame.K_s] or keys[pygame.K_DOWN]) else 0) - (1 if (keys[pygame.K_w] or keys[pygame.K_UP]) else 0)

            game.player.update_lunge(dt, game.dungeon)
            moved = game.player.move_realtime(dx, dy, dt, game.dungeon)
            if moved:
                game.world_active = True
                if game.player.step_sound_cd <= 0.0:
                    game.player.step_sound_cd = 0.28
                    t_step = game.dungeon.grid[int(game.player.y)][int(game.player.x)]
                    if t_step in (2, SHALLOW_WATER, 23, 32, 44):
                        green = t_step in (23, 44)
                        game.sfx.play("step_water")
                        game.fx.add_water_ripple(game.player.x, game.player.y, green=green)
                        splash = (130, 225, 100) if green else (115, 200, 245)
                        for _ in range(3):
                            ang = random.uniform(0, 6.28)
                            game.particles.append(Particle(game.player.x, game.player.y, math.cos(ang) * 1.4, math.sin(ang) * 1.4 - 0.8, splash, 2.2, 0.22))
                    elif t_step in (4, PIER, FALLEN_LOG):
                        game.sfx.play("step_wood")
                    elif t_step == 0:
                        game.sfx.play("step_stone")
                    else:
                        game.sfx.play("step_dirt")

                # Воспламенение Пиро: при ходьбе за спиной игрока остаётся горящий след!
                if getattr(game.player, "ignite_timer", 0.0) > 0.0:
                    game.player.ignite_trail_tick -= dt
                    if game.player.ignite_trail_tick <= 0.0:
                        game.player.ignite_trail_tick = 0.18
                        game.visual_fx.append({
                            "kind": "fire_trail",
                            "growth_credit": getattr(game.player, "ignite_growth_credit", None),
                            "x": game.player.x, "y": game.player.y,
                            "radius": 0.72,
                            "dmg": game.player.ignite_burn_dmg,
                            "color": (255, 110, 35),
                            "timer": 2.4, "max_timer": 2.4
                        })

        if game.fishing_cast is None and game.player.hp > 0 and not game.inv_open and not game.levelup_choices and not dev_open:
            if game.player.pending_action is not None:
                pa = game.player.pending_action
                pa["timer"] -= dt
                if pa["timer"] <= 0.0:
                    game.player.pending_action = None
                    game.world_active = True
                    if pa["kind"] == "melee":
                        game._execute_melee_swing(pa["tx"], pa["ty"])
                    elif pa["kind"] == "spell":
                        game._execute_skill_or_spell(pa["item"], pa["tx"], pa["ty"])
                    elif pa["kind"] == "light_torch":
                        game.player.torch_on = True
                        game.sfx.play("torch")
                        game.emit_noise(game.player.x, game.player.y, 6.8)
                        for _ in range(10):
                            ang = random.uniform(0, 6.28)
                            game.particles.append(Particle(
                                game.player.x, game.player.y - 0.25,
                                math.cos(ang) * 1.8, math.sin(ang) * 1.8 - 1.0,
                                (255, 200, 75), 2.8, 0.28
                            ))

        if game.fishing_cast is None and game.player.hp > 0 and not game.inv_open and not game.levelup_choices and not dev_open and game.world_active:
            from elenor.game.physical import update_physical
            update_physical(game, dt)
            game.update_world_reactions(dt, moved=moved)

            for obj in game.objects:
                if not obj.used and obj.kind == "trap":
                    if math.hypot(game.player.x - (obj.x + 0.5), game.player.y - (obj.y + 0.5)) <= 0.55:
                        obj.used = True
                        myopic_bonus = 4 if getattr(game.player, "quirk", "none") == "myopic" else 0
                        if random.randint(1, 20) + game.player.cunning + myopic_bonus >= 13:
                            game.sfx.play("ui")
                            if game.player.gain_xp(8):
                                game.trigger_levelup_shine()
                            # Успех обезвреживания — ФОНОВАЯ мысль (шанс 30%, не чаще раза в 6 сек)
                            game.trigger_event_thought("trap_disarm")
                            game.add_popup(obj.x + 0.5, obj.y + 0.5, "ОБЕЗВРЕЖЕНО (+8 XP)", (130, 240, 175))
                        else:
                            game.on_player_hit(random.randint(5, 8), is_magic=False)
                            game.emit_noise(obj.x + 0.5, obj.y + 0.5, 6.0)
                            # Провал на ловушке — ВАЖНАЯ мысль (100% объясняет, откуда прилетел урон!)
                            game.trigger_event_thought("trap_hit", force_important=True)

            game.ambient_timer -= dt
            if game.ambient_timer <= 0.0:
                game.ambient_timer = random.uniform(45.0, 75.0)
                if game.can_trigger_background_thought(chance=0.55):
                    game.set_thought(game.pick_text(game.player.thoughts["ambient"], "player_ambient"), important=False, chance=1.0)

            for m in list(game.mobs):
                m.update_ai(
                    dt, game.player, game.dungeon, game.mobs, game.projectiles, game.sfx, game.add_popup,
                    lambda damage, is_magic=False, source=m: game.on_player_hit(damage, is_magic, source=source)
                )
                # Если враг наступил в огненный след Воспламенения Пиро — он поджигается!
                for vfx in game.visual_fx:
                    if vfx["kind"] == "fire_trail" and math.hypot(m.x - vfx["x"], m.y - vfx["y"]) <= vfx["radius"]:
                        m.apply_status("burn", 2.4, game.add_popup, dmg_val=vfx["dmg"])
                        game.record_combat_growth(m, vfx.get("growth_credit"))
                        break
                if getattr(m, "pending_pentagram", False):
                    m.pending_pentagram = False
                    p_dmg = random.randint(m.dmg_min + 3, m.dmg_max + 5)
                    game.sfx.play("magic")
                    game.visual_fx.append({
                        "kind": "blood_pentagram",
                        "source": m,
                        "x": game.player.x,
                        "y": game.player.y,
                        "radius": 1.15 if not m.is_boss else 1.40,
                        "dmg": p_dmg,
                        "color": (245, 40, 65),
                        "timer": 0.50,
                        "max_timer": 0.50
                    })
                if m.hp <= 0:
                    game._check_mob_death(m)

            for pr in list(game.projectiles):
                if not pr.update(dt, game.dungeon, game.particles):
                    game.projectiles.remove(pr)
                    continue

                if pr.from_player:
                    for m in list(game.mobs):
                        if m in getattr(pr, "hit_mobs", set()):
                            continue
                        if is_cursor_on_mob(m, pr.wx, pr.wy):
                            pr.hit_mobs.add(m)
                            was_unaware = (m.state != "combat")
                            m.alert_to_combat(game.sfx, game.add_popup)

                            if getattr(pr, "is_weapon_proj", False):
                                # Штраф при стрельбе в упор (< 1.35 м): враг мешает натянуть пращу/замахнуться дротиком!
                                dist_to_shooter = math.hypot(m.x - game.player.x, m.y - game.player.y)
                                is_point_blank = (dist_to_shooter < 1.35)
                                if is_point_blank:
                                    pr.mag_dmg = max(1, int(pr.mag_dmg * 0.50))
                                    pr.knockback = max(0.05, pr.knockback * 0.35)

                                is_crit = was_unaware or (random.random() < getattr(pr, "crit_chance", 0.0))
                                raw_d = int(pr.mag_dmg * (1.75 if is_crit else 1.0))
                                eff_def = max(0, m.phys_def - getattr(pr, "armor_pierce", 0))
                                dmg = max(1, raw_d - eff_def)
                                if getattr(pr, "shatter_armor", 0) > 0 and m.phys_def > 0:
                                    m.phys_def = max(0, m.phys_def - pr.shatter_armor)
                                if getattr(pr, "life_steal", 0) > 0:
                                    game.player.hp = min(float(game.player.max_hp), game.player.hp + pr.life_steal)
                                if game.player.mp < game.player.max_mp:
                                    game.player.mp = min(float(game.player.max_mp), game.player.mp + game.player.mp_on_hit * 0.5)
                                # Только реальное попадание по наградным мобам развивает Ловкача!
                                if not getattr(m, "no_rewards", False):
                                    game.player.record_build_action("cunning", 0.16)
                            else:
                                is_crit = False
                                dmg = max(1, int(math.floor(pr.mag_dmg - m.mag_def)))

                            game.record_combat_growth(m, getattr(pr, "growth_credit", None))
                            m.hp -= dmg
                            m.hit_flash_timer = 0.12
                            m.hit_flash_crit = is_crit
                            game.fx.add_blood_splatter(m.x, m.y, count=6 if is_crit else 3, is_kill=False)

                            if pr.knockback > 0:
                                v_len = max(0.001, math.hypot(pr.vx, pr.vy))
                                m.apply_knockback(pr.vx / v_len, pr.vy / v_len, pr.knockback)
                            if pr.status and random.random() <= getattr(pr, "status_chance", 1.0):
                                m.apply_status(pr.status, pr.status_dur, game.add_popup, dmg_val=max(2, dmg // 3))

                            if is_crit:
                                game.sfx.play("crit")
                                game.fx.trigger_shake(1.6, 0.12)
                                game.add_popup(m.x, m.y, f"-{dmg}", (255, 230, 75), big=True)
                            else:
                                game.sfx.play("hit")
                                game.add_popup(m.x, m.y, f"-{dmg}", pr.color)

                            game._check_mob_death(m)

                            bounced = False
                            if getattr(pr, "bounces", 0) > 0:
                                nxt_m = min(
                                    (
                                        other for other in game.mobs
                                        if other is not m and other not in pr.hit_mobs and other.hp > 0
                                        and math.hypot(other.x - m.x, other.y - m.y) <= 3.8
                                        and game.dungeon.has_line_of_sight(m.x, m.y, other.x, other.y, 4.0)
                                    ),
                                    key=lambda other: math.hypot(other.x - m.x, other.y - m.y),
                                    default=None
                                )
                                if nxt_m is not None:
                                    pr.bounces -= 1
                                    bdx = nxt_m.x - pr.wx
                                    bdy = (nxt_m.y - 0.25) - pr.wy
                                    blen = max(0.001, math.hypot(bdx, bdy))
                                    spd = getattr(pr, "speed", math.hypot(pr.vx, pr.vy))
                                    pr.vx = (bdx / blen) * spd
                                    pr.vy = (bdy / blen) * spd
                                    pr.life = max(pr.life, 0.65)
                                    bounced = True

                            if not bounced and pr in game.projectiles:
                                game.projectiles.remove(pr)
                            break
                else:
                    if math.hypot(game.player.x - pr.wx, game.player.y - pr.wy) <= 0.55:
                        game.on_player_hit(pr.mag_dmg, is_magic=not pr.is_weapon_proj, source=getattr(pr, "source", None))
                        if pr in game.projectiles:
                            game.projectiles.remove(pr)

        evt_code = game.player.update_timers(dt if not game.inv_open and not game.levelup_choices and not dev_open else 0)
        if evt_code == "torch_burned_out":
            game.sfx.play("hurt")
            game.trigger_event_thought("torch_burned_out", force_important=True)

        from elenor.puzzles.mirrors import update_mirror_puzzles, inject_mirror_puzzle_lights
        game.fx.update(dt if not game.inv_open and not game.levelup_choices and not dev_open else 0, game.player, game.dungeon, game.mobs, game.add_popup)

        # Фоновая пространственная музыка активной кампании (управляется модулем миссии!)
        if not getattr(game.fx, "disco_active", False):
            update_mission_audio(game, dt)

        sh_x, sh_y = game.fx.shake_offset
        px_world = round(game.player.x * TILE_W)
        py_world = round(game.player.y * TILE_H)
        game.cam_x = max(0.0, min(float(game.dungeon.width * TILE_W - VIEW_W), px_world - VIEW_W * 0.5)) + round(sh_x)
        game.cam_y = max(0.0, min(float(game.dungeon.height * TILE_H - VIEW_H), py_world - VIEW_H * 0.5)) + round(sh_y)

        world_ox = game.player.x * TILE_W
        world_oy = game.player.y * TILE_H
        fov_mask, visible_tiles, player_open_tiles = game.dungeon.compute_nox_fov(
            world_ox, world_oy, game.cam_x, game.cam_y
        )
        game.current_visible_tiles = visible_tiles
        if (game.world_active and not game.inv_open and not game.levelup_choices
                and not dev_open and game.player.hp > 0):
            update_mirror_puzzles(game, dt)
        game.player.update_illumination(game.dungeon.braziers, game.dungeon.room_lights, game.objects, player_open_tiles)

        game.particles = [pt for pt in game.particles if pt is not None and pt.update(dt)]
        game.popups = [p for p in game.popups if p is not None and p.update(dt)]
        for vfx in list(game.visual_fx):
            if vfx["kind"] in ("blood_pentagram", "mana_shard") and (game.inv_open or game.levelup_choices or dev_open):
                continue
            if vfx["kind"] == "mana_shard" and game.player.hp > 0:
                d_sh = math.hypot(game.player.x - vfx["x"], game.player.y - vfx["y"])
                magnet_r = 1.45 if game.player.mp_shard_bonus > 0 else 1.05
                if d_sh <= magnet_r and d_sh > 0.01:
                    # Плавное притягивание осколка к герою на близкой дистанции
                    vfx["x"] += ((game.player.x - vfx["x"]) / d_sh) * 5.5 * dt
                    vfx["y"] += ((game.player.y - vfx["y"]) / d_sh) * 5.5 * dt
                if d_sh <= 0.58:
                    mp_restore = int(vfx["mp"] + game.player.mp_shard_bonus)
                    game.player.mp = min(float(game.player.max_mp), game.player.mp + mp_restore)
                    game.sfx.play("magic")
                    for _ in range(7):
                        ang = random.uniform(0, 6.28)
                        game.particles.append(Particle(vfx["x"], vfx["y"], math.cos(ang) * 1.8, math.sin(ang) * 1.8, (95, 225, 255), 2.5, 0.28))
                    game.visual_fx.remove(vfx)
                    continue
            vfx["timer"] -= dt
            if vfx["timer"] <= 0.0:
                game.visual_fx.remove(vfx)
                if vfx["kind"] == "fire_trail":
                    game.fx.add_scorch_mark(vfx["x"], vfx["y"], 0.42)
                elif vfx["kind"] == "blood_pentagram" and game.player.hp > 0:
                    game.fx.add_scorch_mark(vfx["x"], vfx["y"], 0.85)
                    game.fx.trigger_shake(2.4, 0.18)
                    game.sfx.play("crit")
                    game.visual_fx.append({
                        "kind": "aoe_ring",
                        "x": vfx["x"], "y": vfx["y"], "radius": vfx["radius"],
                        "color": (255, 75, 55), "timer": 0.26, "max_timer": 0.26
                    })
                    for _ in range(18):
                        ang = random.uniform(0, 6.28)
                        spd = random.uniform(1.2, 4.2)
                        game.particles.append(Particle(
                            vfx["x"] + math.cos(ang) * 0.25,
                            vfx["y"] + math.sin(ang) * 0.25,
                            math.cos(ang) * spd, math.sin(ang) * spd - 1.2,
                            random.choice([(255, 50, 65), (255, 165, 50), (190, 25, 45)]),
                            3.2, 0.38
                        ))
                    if math.hypot(game.player.x - vfx["x"], game.player.y - vfx["y"]) <= vfx["radius"]:
                        game.on_player_hit(vfx["dmg"], is_magic=True, source=vfx.get("source"))

        flicker = math.sin(t * 3.2) * 3.5 + math.cos(t * 6.7) * 1.8
        p_sx = world_ox - game.cam_x
        p_sy = world_oy - game.cam_y
        p_foot_sy = (game.player.y + 0.05) * TILE_H - game.cam_y

        lights = [
            {
                "pos": (p_sx, p_sy, TORCH_Z_HEIGHT),
                "foot_y": p_foot_sy + 2.0,
                "ignore_depth": True,
                "radius": game.player.dark_vision_radius,
                "color": (0.38, 0.48, 0.72)
            }
        ]
        if game.player.has_lit_torch:
            lights.append({
                "pos": (p_sx + 4, p_sy - 2, TORCH_Z_HEIGHT),
                "foot_y": p_foot_sy + 1.5,
                "radius": game.player.torch_light_radius + flicker,
                "color": (1.15, 0.80, 0.40)
            })

        # Свечение игрока во время подготовки каста, Воспламенения Пиро или Омоложения Персефоны!
        if getattr(game.player, "cast_glow_color", None) and game.player.pending_action:
            gc = game.player.cast_glow_color
            lights.append({
                "pos": (p_sx, p_sy - 3, 24.0),
                "foot_y": p_foot_sy + 2.0,
                "ignore_depth": True,
                "radius": 68.0,
                "color": (gc[0] / 190.0, gc[1] / 190.0, gc[2] / 190.0)
            })
        if getattr(game.player, "ignite_timer", 0.0) > 0.0:
            lights.append({
                "pos": (p_sx, p_sy - 2, 24.0),
                "foot_y": p_foot_sy + 2.0,
                "ignore_depth": True,
                "radius": 92.0 + flicker,
                "color": (1.35, 0.62, 0.22)
            })
        if getattr(game.player, "rejuv_timer", 0.0) > 0.0:
            lights.append({
                "pos": (p_sx, p_sy - 2, 24.0),
                "foot_y": p_foot_sy + 2.0,
                "ignore_depth": True,
                "radius": 64.0,
                "color": (0.42, 1.05, 0.55)
            })

        if game.player.shine_timer > 0.0:
            sh_ratio = game.player.shine_timer / 0.95
            lights.append({
                "pos": (p_sx, p_sy - 4, 28.0),
                "foot_y": p_foot_sy + 4.0,
                "ignore_depth": True,
                "radius": 95.0 * sh_ratio,
                "color": (1.65 * sh_ratio, 1.35 * sh_ratio, 0.50 * sh_ratio)
            })

        hud_cx = VIEW_W * 0.5
        hud_cy = VIEW_H + (CANVAS_H - VIEW_H) * 0.5
        hud_lights = []
        if game.player.has_lit_torch or getattr(game.player, "ignite_timer", 0.0) > 0.0:
            hud_lights.append({
                "pos": (THOUGHT_BOX_X + THOUGHT_BOX_W - 22.0, hud_cy, 22.0),
                "radius": 115.0 + flicker * 0.5,
                "color": (0.45, 0.32, 0.16)
            })
        if game.player.shine_timer > 0.0:
            hud_lights.append({
                "pos": (hud_cx, hud_cy, 24.0),
                "radius": 240.0,
                "color": (1.4, 1.15, 0.45)
            })

        def register_world_and_hud_light(wx_px, wy_px, foot_wy_px, z_h, rad, col, allowed_set, ignore_d=False):
            sx, sy = wx_px - game.cam_x, wy_px - game.cam_y
            if -rad <= sx <= VIEW_W + rad and -rad <= sy <= VIEW_H + rad:
                lights.append({
                    "pos": (sx, sy, z_h),
                    "foot_y": foot_wy_px - game.cam_y,
                    "ignore_depth": ignore_d,
                    "radius": rad,
                    "color": col,
                    "allowed_tiles": allowed_set
                })
            rel_dx = wx_px - world_ox
            rel_dy = wy_px - world_oy
            dist_to_player = math.hypot(rel_dx, rel_dy)
            max_sense = rad * 1.45
            if dist_to_player <= max_sense:
                prox = (1.0 - dist_to_player / max_sense) ** 1.25
                if dist_to_player > 2.0:
                    cos_a = rel_dx / dist_to_player
                    sin_a = rel_dy / dist_to_player
                else:
                    cos_a, sin_a = 0.0, 0.0

                reach_factor = min(1.0, dist_to_player / 18.0)
                hud_lx = hud_cx + cos_a * (THOUGHT_BOX_W * 0.48) * reach_factor
                hud_ly = hud_cy + sin_a * ((CANVAS_H - VIEW_H) * 0.46) * reach_factor

                spot_rad = 45.0 + 80.0 * prox
                inten = (0.18 + 0.32 * prox)
                hud_lights.append({
                    "pos": (hud_lx, hud_ly, 18.0),
                    "radius": spot_rad,
                    "color": (col[0] * inten, col[1] * inten, col[2] * inten)
                })

        if getattr(game.dev_panel, "reveal_map", False):
            fov_mask[:, :] = 1.0
            visible_tiles = {(c, r) for r in range(game.dungeon.height) for c in range(game.dungeon.width)}
            lights.append({"pos": (VIEW_W * 0.5, VIEW_H * 0.5, 180.0), "foot_y": 9999.0, "ignore_depth": True, "radius": 600.0, "color": (0.85, 0.85, 0.95)})

        for br in game.dungeon.braziers:
            lx_w, ly_w = br["x"] * TILE_W + 8, br["y"] * TILE_H + 6
            foot_w = (br["y"] + 0.5) * TILE_H
            rad = br["radius"] + flicker * 0.5
            if (abs(lx_w - world_ox) > VIEW_W + rad or abs(ly_w - world_oy) > VIEW_H + rad):
                continue
            l_open = game.dungeon.get_light_open_tiles(br["x"], br["y"], br["radius"])
            allowed = game.dungeon.build_shared_light_Allowed_tiles(player_open_tiles, l_open)
            if allowed is not None:
                register_world_and_hud_light(lx_w, ly_w, foot_w, 22.0, rad, br["color"], allowed)

        for rl in game.dungeon.room_lights:
            lx_w, ly_w = rl["x"] * TILE_W + 8, rl["y"] * TILE_H + 8
            foot_w = (rl["y"] + 0.5) * TILE_H
            rad = rl["radius"]
            if (abs(lx_w - world_ox) > VIEW_W + rad or abs(ly_w - world_oy) > VIEW_H + rad):
                continue
            # Дискотечные прожекторы и стробоскоп: строго экранируются стенами танцпола!
            if rl.get("is_disco_strobe") or "disco_idx" in rl:
                l_open = game.dungeon.get_light_open_tiles(37, 17, 125.0)
                allowed = game.dungeon.build_shared_light_Allowed_tiles(player_open_tiles, l_open)
                if allowed is not None:
                    register_world_and_hud_light(lx_w, ly_w, foot_w, 24.0, rad, rl["color"], allowed, ignore_d=False)
                continue
            l_open = game.dungeon.get_light_open_tiles(rl["x"], rl["y"], rad)
            allowed = game.dungeon.build_shared_light_Allowed_tiles(player_open_tiles, l_open)
            if allowed is not None:
                register_world_and_hud_light(lx_w, ly_w, foot_w, 32.0, rad, rl["color"], allowed, ignore_d=True)

        for obj in game.objects:
            if obj.kind in ("campfire", "fireplace"):
                lx_w, ly_w = obj.x * TILE_W + 8, obj.y * TILE_H + 8
                foot_w = (obj.y + 0.5) * TILE_H
                rad = 115.0 + flicker * 0.8
                l_open = game.dungeon.get_light_open_tiles(obj.x, obj.y, 115.0)
                allowed = game.dungeon.build_shared_light_Allowed_tiles(player_open_tiles, l_open)
                if allowed is not None:
                    register_world_and_hud_light(lx_w, ly_w, foot_w, 24.0, rad, (1.20, 0.72, 0.32), allowed)

        inject_mirror_puzzle_lights(game, lights, player_open_tiles, register_world_and_hud_light)

        for pr in game.projectiles:
            if getattr(pr, "emits_light", True) and (int(pr.wx), int(pr.wy)) in player_open_tiles:
                wx_p, wy_p = pr.wx * TILE_W, pr.wy * TILE_H
                register_world_and_hud_light(
                    wx_p, wy_p, wy_p, 16.0, 56.0,
                    (pr.color[0] / 220.0, pr.color[1] / 220.0, pr.color[2] / 220.0), None
                )

        # Свечение от огненных следов (берём только 2 самых свежих очага, чтобы не грузить проц!), Кольца холода и Молнии
        fire_lights_added = 0
        for vfx in reversed(game.visual_fx):
            if vfx["kind"] == "fire_trail":
                if fire_lights_added < 2 and (int(vfx["x"]), int(vfx["y"])) in player_open_tiles:
                    fire_lights_added += 1
                    sx_f, sy_f = vfx["x"] * TILE_W - game.cam_x, vfx["y"] * TILE_H - game.cam_y
                    lights.append({
                        "pos": (sx_f, sy_f, 14.0),
                        "foot_y": sy_f,
                        "ignore_depth": True,
                        "radius": 34.0,
                        "color": (0.85, 0.40, 0.15),
                        "allowed_tiles": None
                    })
            elif vfx["kind"] == "mana_shard" and (int(vfx["x"]), int(vfx["y"])) in player_open_tiles:
                wx_s, wy_s = vfx["x"] * TILE_W, vfx["y"] * TILE_H
                register_world_and_hud_light(wx_s, wy_s, wy_s, 14.0, 38.0, (0.35, 0.85, 1.25), None, ignore_d=True)
            elif vfx["kind"] == "frost_nova":
                wx_n, wy_n = vfx["x"] * TILE_W, vfx["y"] * TILE_H
                register_world_and_hud_light(wx_n, wy_n, wy_n, 20.0, vfx["radius"] * TILE_W * 1.25, (0.55, 1.15, 1.45), None, ignore_d=True)
            elif vfx["kind"] == "chain_lightning":
                pts = vfx["points"]
                for i in range(len(pts) - 1):
                    mx_l = (pts[i][0] + pts[i + 1][0]) * 0.5 * TILE_W
                    my_l = (pts[i][1] + pts[i + 1][1]) * 0.5 * TILE_H
                    register_world_and_hud_light(mx_l, my_l, my_l, 22.0, 72.0, (0.75, 1.35, 1.65), None, ignore_d=True)

        for m in game.mobs:
            if getattr(m, "glow_timer", 0.0) > 0.0 and (int(m.x), int(m.y)) in player_open_tiles:
                gc = getattr(m, "glow_color", (255, 120, 40))
                wx_m, wy_m = m.x * TILE_W, m.y * TILE_H
                register_world_and_hud_light(
                    wx_m, wy_m, wy_m, 18.0, 54.0,
                    (gc[0] / 200.0, gc[1] / 200.0, gc[2] / 200.0), None, ignore_d=True
                )

        world_hover_item = None
        if not game.inv_open and not game.levelup_choices and not dev_open:
            for obj in game.objects:
                if not obj.used and obj.kind == "loot" and obj.item and (obj.x, obj.y) in visible_tiles:
                    if math.hypot(world_mx - (obj.x + 0.5), world_my - (obj.y + 0.5)) <= 0.65:
                        world_hover_item = obj.item
                        break

        ui_bundle = dict(game.loc["ui"])
        ui_bundle["_game_ref"] = game
        ui_bundle["_survey_map"] = not game.inv_open and not game.dev_panel.reveal_map
        ui_bundle["_perks_db"] = game.loc.get("perks", {})
        ui_bundle["_world_hover_item"] = world_hover_item
        ui_bundle["_show_map_hud"] = (
            not game.inv_open and not game.levelup_choices and game.fishing_cast is None and not dev_open
        )
        ui_bundle["_visual_fx"] = game.visual_fx
        ui_bundle["_fx_mgr"] = game.fx
        ui_bundle["_journal_open"] = game.journal_open
        ui_bundle["_journal_logs"] = game.journal_logs
        ui_bundle["_journal_filters"] = game.journal_filters
        ui_bundle["_journal_scroll"] = game.journal_scroll

        hover_target = game.get_precision_hover_target(world_mx, target_wy=world_my)
        shown_str = game.target_thought[:int(game.shown_chars)]
        game.renderer.render_frame(
            screen=screen,
            dungeon=game.dungeon,
            player=game.player,
            mobs=game.mobs,
            objects=game.objects,
            projectiles=game.projectiles,
            particles=game.particles,
            popups=game.popups,
            cam_x=game.cam_x,
            cam_y=game.cam_y,
            fov_mask=fov_mask,
            visible_tiles=visible_tiles,
            lights=lights,
            shown_thought=shown_str,
            ui_texts=ui_bundle,
            inv_open=game.inv_open,
            hover_pos=mouse_pos,
            drag_item=game.drag_item,
            hover_target=hover_target,
            levelup_choices=game.levelup_choices,
            hud_lights=hud_lights
        )

        if game.campaign == "jungle" and not game.inv_open:
            draw_fishing(screen, game, (world_mx, world_my), fov_mask)

        if not game.inv_open and not game.levelup_choices and game.fishing_cast is None and not dev_open:
            passage = game.nearby_passage()
            if passage:
                _, action = passage
                label = game.renderer.font_ui.render(game.loc["jungle_passages"][action], True, (246, 225, 178))
                rect = label.get_rect(midbottom=(VIEW_W * SCALE // 2, VIEW_H * SCALE - 16))
                pygame.draw.rect(screen, (23, 32, 27), rect.inflate(18, 8), border_radius=4)
                screen.blit(label, rect)

        if hasattr(game, "fx") and game.fx:
            game.fx.render_panel(screen, mouse_pos)

        if hasattr(game, "dev_panel") and game.dev_panel:
            game.dev_panel.render(screen, game, mouse_pos)

        present_logical_canvas(game.display_surface, screen, game.viewport_rect)
        pygame.display.flip()

    pygame.quit()


