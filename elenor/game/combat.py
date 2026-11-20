import math
import random

from elenor.entities import Enemy, Interactable, Projectile, Particle
from elenor.entities.objects import JUNGLE_CHESTS, JUNGLE_KEY_COLORS, JUNGLE_VASES
from elenor.config import COIN_TEXT_COLOR, COMBAT_INPUT_WINDOW
from elenor.audio.abilities import ability_sound
from elenor.data.abilities import PASSIVES, spell_school
from elenor.data.blood import BLOOD_PALETTES
from elenor.missions.rats import get_mission_texts, handle_mission_object_interaction
from elenor.profile import save_profile



from elenor.game.targeting import dungeon_los_ok, is_cursor_on_mob

class CombatMixin:
    def on_player_hit(self, raw_dmg, is_magic=False, source=None):
        if getattr(self.player, "god_mode", False):
            self.add_popup(self.player.x, self.player.y, "БЕССМЕРТИЕ", (255, 225, 90))
            return
        if random.random() < self.player.dodge_chance:
            # Уворот даёт умеренную прибавку через трёхплечевые весы
            if not getattr(source, "no_rewards", False):
                self.player.record_build_action("cunning", 0.08)
            if self.player.passive_power("sidestep"):
                self.player.activate_passive("sidestep", PASSIVES["sidestep"]["duration"])
            self.add_popup(self.player.x, self.player.y, "УВОРОТ", (140, 230, 255))
            self.add_log("combat", "Уклонение от вражеской атаки!", (140, 230, 255))
            self.trigger_event_thought("combat_dodge")
            return

        if getattr(self.player, "ignite_timer", 0.0) > 0.0 and not is_magic:
            for m in self.mobs:
                if math.hypot(m.x - self.player.x, m.y - self.player.y) <= 1.95:
                    m.apply_status("burn", 2.8, self.add_popup, dmg_val=self.player.ignite_burn_dmg)
                    self.record_combat_growth(m, getattr(self.player, "ignite_growth_credit", None))

        defense = self.player.mag_defense if is_magic else self.player.phys_defense
        reduction = 0.55 if self.player.guard_timer > 0 else 1.0
        if self.player.passive_active("firm_stance"):
            reduction *= 1.0 - self.player.passive_power("firm_stance")
        dmg = max(1, math.floor((raw_dmg - defense) * reduction))
        self.player.hp = max(0.0, self.player.hp - dmg)
        self.sfx.play("hurt")
        self.add_log("combat", f"Получен урон: -{dmg} ХП ({'магия' if is_magic else 'физ. удар'}).", (255, 110, 110))
        col = (205, 110, 255) if is_magic else (255, 85, 85)
        self.add_popup(self.player.x, self.player.y, f"-{dmg}", col)

        if self.player.hp <= 0:
            self.trigger_event_thought("death", force_important=True)
        else:
            self.check_hypochondriac_panic()
            if self.player.hp <= 7 and self.low_hp_thought_cd <= 0.0:
                self.low_hp_thought_cd = 14.0
                self.trigger_event_thought("low_hp", force_important=True)


    def get_precision_hover_target(self, target_wx, target_wy):
        px, py = self.player.x, self.player.y
        weap = self.player.equipment["right_hand"]
        reach = (weap.reach if weap else 1.55) + 0.35

        for m in self.mobs:
            if is_cursor_on_mob(m, target_wx, target_wy) and math.hypot(m.x - px, m.y - py) <= reach:
                return ("enemy", m.x, m.y, "Атака [ЛКМ]")

        for (dx, dy), door in self.dungeon.doors.items():
            cx, cy = dx + 0.5, dy + 0.5
            if math.hypot(target_wx - cx, target_wy - cy) <= 0.60 and math.hypot(px - cx, py - cy) <= 1.75:
                return ("door", cx, cy, "Дверь [ЛКМ]")

        for (lx, ly), lev in self.dungeon.levers.items():
            cx, cy = lx + 0.5, ly + 0.5
            if not lev.pulled and math.hypot(target_wx - cx, target_wy - cy) <= 0.60 and math.hypot(px - cx, py - cy) <= 1.75:
                return ("lever", cx, cy, "Рычаг [ЛКМ]")

        for obj in self.objects:
            if not obj.used and obj.kind != "trap":
                cx, cy = obj.x + 0.5, obj.y + 0.5
                if math.hypot(target_wx - cx, target_wy - cy) <= 0.58 and math.hypot(px - cx, py - cy) <= 1.70:
                    return ("object", cx, cy, "")

        return None


    def try_interact_or_melee(self, target_wx, target_wy, via_mouse=True):
        if self.player.hp <= 0 or self.inv_open:
            return
        px, py = self.player.x, self.player.y

        if via_mouse:
            enemy_under_cursor = any(
                is_cursor_on_mob(m, target_wx, target_wy)
                for m in self.mobs
            )
            if not enemy_under_cursor:
                if self._try_precise_interaction(target_wx, target_wy, max_cursor_dist=0.58):
                    return
            self._perform_melee_attack(target_wx, target_wy)
        else:
            passage = self.nearby_passage()
            if passage:
                obj, action = passage
                if action == "stairs":
                    self._use_stairs()
                else:
                    self.travel_jungle(action)
                return
            if not self._try_precise_interaction(px, py, max_cursor_dist=1.65):
                self._perform_melee_attack(target_wx, target_wy)

    def nearby_passage(self):
        px, py = self.player.x, self.player.y
        passages = [
            (obj, self.dungeon.passages.get((obj.x, obj.y), "stairs"))
            for obj in self.objects
            if not obj.used and (obj.kind == "stairs" or (obj.x, obj.y) in self.dungeon.passages)
            and math.hypot(px - obj.x - 0.5, py - obj.y - 0.5) <= 1.65
            and self.dungeon.has_line_of_sight(px, py, obj.x + 0.5, obj.y + 0.5, 1.65)
        ]
        return min(passages, key=lambda pair: math.hypot(px - pair[0].x - 0.5, py - pair[0].y - 0.5), default=None)

    def _use_stairs(self):
        px, py = self.player.x, self.player.y
        if any(m.state == "combat" and math.hypot(m.x - px, m.y - py) <= 3.2 for m in self.mobs):
            self.sfx.play("hurt")
            self.trigger_event_thought("stairs_combat")
            self.add_popup(px, py, "В БОЮ!", (255, 95, 95))
        else:
            self.descend_to_next_floor()


    def _try_precise_interaction(self, ref_wx, ref_wy, max_cursor_dist):
        px, py = self.player.x, self.player.y

        nearby_loot = [
            obj for obj in self.objects
            if not obj.used and obj.kind == "loot"
            and math.hypot(px - (obj.x + 0.5), py - (obj.y + 0.5)) <= 1.85
            and math.hypot(ref_wx - (obj.x + 0.5), ref_wy - (obj.y + 0.5)) <= max_cursor_dist
        ]
        if nearby_loot:
            nearby_loot.sort(key=lambda o: math.hypot(ref_wx - (o.x + 0.5), ref_wy - (o.y + 0.5)))
            return self._pickup_loot_object(nearby_loot[0])

        nearby_doors = [
            ((dx, dy), door)
            for (dx, dy), door in self.dungeon.doors.items()
            if math.hypot(px - (dx + 0.5), py - (dy + 0.5)) <= 1.70
            and math.hypot(ref_wx - (dx + 0.5), ref_wy - (dy + 0.5)) <= max_cursor_dist
        ]
        if nearby_doors:
            nearby_doors.sort(key=lambda pair: math.hypot(ref_wx - (pair[0][0] + 0.5), ref_wy - (pair[0][1] + 0.5)))
            (dx, dy), door = nearby_doors[0]
            if door.locked and door.key_color:
                key = door.key_color
                labels = self.loc["jungle_route"]
                if key in self.dungeon.jungle_keys:
                    door.locked = False
                    self.add_popup(dx + 0.5, dy + 0.5, labels["opened"], JUNGLE_KEY_COLORS[key])
                else:
                    self.sfx.play("hurt")
                    self.add_popup(dx + 0.5, dy + 0.5, f'{labels["needed"]} · {labels[key]}', JUNGLE_KEY_COLORS[key])
                    return True
            if door.locked:
                self.sfx.play("hurt")
                self.emit_noise(dx + 0.5, dy + 0.5, 4.5)
                self.trigger_event_thought("door_locked")
                labels = self.loc["jungle_route"]
                if (dx, dy) == self.dungeon.jungle_gate:
                    label = labels["mechanism"]
                elif any(door in puzzle.target_doors for puzzle in self.mirror_puzzles):
                    label = labels["mirror_lock"]
                else:
                    label = "ЗАПЕРТО"
                self.add_popup(dx + 0.5, dy + 0.5, label, (255, 120, 100))
            else:
                if door.is_open:
                    if (int(px) == dx and int(py) == dy) or any(int(m.x) == dx and int(m.y) == dy for m in self.mobs):
                        self.sfx.play("step")
                        self.add_popup(dx + 0.5, dy + 0.5, "Проём занят!", (255, 195, 95))
                        return True
                    if abs(px - (dx + 0.5)) < 0.80 and abs(py - (dy + 0.5)) < 0.80:
                        if abs(px - (dx + 0.5)) >= abs(py - (dy + 0.5)):
                            self.player.x = (dx + 1.30) if px > (dx + 0.5) else (dx - 0.30)
                        else:
                            self.player.y = (dy + 1.30) if py > (dy + 0.5) else (dy - 0.30)

                door.is_open = not door.is_open
                self.dungeon.invalidate_light_cache()
                self.play_spatial("door", dx + 0.5, dy + 0.5)
                self.emit_noise(dx + 0.5, dy + 0.5, 3.8)
                if door.is_open:
                    self.trigger_event_thought("door_open")
            return True

        for (lx, ly), lev in self.dungeon.levers.items():
            cx, cy = lx + 0.5, ly + 0.5
            if not lev.pulled and math.hypot(px - cx, py - cy) <= 1.70 and math.hypot(ref_wx - cx, ref_wy - cy) <= max_cursor_dist:
                lev.pulled = True
                for d in lev.target_doors:
                    d.locked = False
                    d.is_open = True
                self.dungeon.invalidate_light_cache()
                self.play_spatial("door", cx, cy)
                self.emit_noise(cx, cy, 7.0)
                self.trigger_event_thought("lever_pull")
                self.add_popup(cx, cy, "ОТКРЫТО!", (130, 245, 160))
                return True

        cand_objs = [
            obj for obj in self.objects
            if not obj.used and obj.kind not in ("trap", "ceramic_shards")
            and math.hypot(px - (obj.x + 0.5), py - (obj.y + 0.5)) <= (2.65 if obj.kind in ("npc_innkeeper", "npc_merchant") else 1.85)
            and math.hypot(ref_wx - (obj.x + 0.5), ref_wy - (obj.y + 0.5)) <= max_cursor_dist
        ]
        if not cand_objs:
            return False

        cand_objs.sort(key=lambda o: math.hypot(ref_wx - (o.x + 0.5), ref_wy - (o.y + 0.5)))
        obj = cand_objs[0]

        passage = self.dungeon.passages.get((obj.x, obj.y))
        if passage:
            self.travel_jungle(passage)
            return True

        if obj.kind == "merchant_counter":
            self.interact_with_merchant(obj.merchant_owner)
            return True
        if obj.kind == "npc_merchant":
            self.interact_with_merchant(obj)
            return True

        from elenor.puzzles.mirrors import handle_mirror_puzzle_interaction
        if handle_mirror_puzzle_interaction(self, obj):
            return True

        if handle_mission_object_interaction(self, obj, Enemy, Interactable):
            return True

        if obj.kind == "stairs":
            self._use_stairs()
            return True

        if obj.kind == "campfire":
            if not self.player_owns_any_torch():
                new_torch = self.make_item("pitch_torch")
                if not self.player.try_auto_equip_if_slot_empty(new_torch):
                    if not self.player.add_item_to_inventory(new_torch):
                        self.objects.append(Interactable(obj.x, obj.y, "loot", new_torch))
                self.sfx.play("torch")
                self.trigger_event_thought("campfire_take_torch")
                self.add_popup(obj.x + 0.5, obj.y + 0.5, "+Смоляной факел", (255, 200, 80))
            else:
                self.inspect_prop(obj)
            return True

        if obj.kind == "loot":
            return self._pickup_loot_object(obj)

        ox_c, oy_c = obj.x + 0.5, obj.y + 0.5

        key_color = self.dungeon.jungle_controls.get((obj.x, obj.y))
        if key_color in JUNGLE_KEY_COLORS and obj.kind.startswith("jungle_key_"):
            self.dungeon.jungle_keys.add(key_color)
            text = self.loc["jungle_route"][key_color]
            self.sfx.play("ui")
            self.add_log("event", text)
            self.add_popup(ox_c, oy_c, text, JUNGLE_KEY_COLORS[key_color])
        elif obj.kind in JUNGLE_VASES:
            obj.kind = "ceramic_shards"
            self.dungeon.solid_props.discard((obj.x, obj.y))
            self.play_spatial("hit", ox_c, oy_c)
            self.emit_noise(ox_c, oy_c, 5.5)
            for _ in range(9):
                ang = random.uniform(0, math.tau)
                speed = random.uniform(1.2, 3.5)
                self.particles.append(Particle(ox_c, oy_c, math.cos(ang) * speed,
                                               math.sin(ang) * speed, (209, 178, 129), 2.5, 0.26))
            if random.random() < 0.10:
                drop = self.roll_currency_or_gem_drop(allow_gem=True, gem_mult=0.25)
                self.objects.append(Interactable(obj.x, obj.y, "loot", drop))
            return True
        elif obj.kind in JUNGLE_CHESTS:
            if (obj.x, obj.y) == self.dungeon.jungle_starter_cache:
                drop = self.make_item("rusty_dagger", rarity="common")
            elif (obj.x, obj.y) == self.dungeon.jungle_bag_cache:
                drop = self.make_item("small_pouch")
            else:
                drop = self.roll_item_by_rarity(allowed_types=["equipment", "consumable", "bag"])
            self.objects.append(Interactable(obj.x, obj.y, "loot", drop))
            self.sfx.play("door")
            self.trigger_event_thought("chest_pick_ok", item=drop.name)
            self.add_popup(ox_c, oy_c, drop.name, drop.rarity_color)
        elif obj.kind == "barrel":
            if hasattr(self, "fx") and self.fx:
                self.fx.add_barrel_debris(obj.x, obj.y)
                self.fx.trigger_shake(1.8, 0.14)
            self.play_spatial("crit", ox_c, oy_c)
            self.emit_noise(ox_c, oy_c, 5.8)
            roll = random.random()
            if roll < 0.26:
                itm = self.roll_weapon_drop()
                self.objects.append(Interactable(obj.x, obj.y, "loot", itm))
                self.trigger_event_thought("barrel_weapon", item=itm.name)
                self.add_popup(ox_c, oy_c, f"Выпало: {itm.name}", itm.rarity_color)
            elif roll < 0.52:
                pot_id = random.choice(["potion_hp", "potion_hp_weak", "herbal_salve"])
                pot = self.make_item(pot_id if pot_id in self.loc.get("items", {}) else "potion_hp")
                self.objects.append(Interactable(obj.x, obj.y, "loot", pot))
                self.trigger_event_thought("barrel_potion", item=pot.name)
                self.add_popup(ox_c, oy_c, f"Выпало: {pot.name}", (120, 245, 140))
            elif roll < 0.76:
                loot_itm = self.roll_currency_or_gem_drop(allow_gem=True)
                self.objects.append(Interactable(obj.x, obj.y, "loot", loot_itm))
                self.play_spatial("coin_drop", ox_c, oy_c)
                self.trigger_event_thought("barrel_treasure", item=loot_itm.name)
                self.add_popup(ox_c, oy_c, f"Выпало: {loot_itm.name}", loot_itm.rarity_color)
            else:
                ambush_mob = Enemy(obj.x, obj.y, kind="rat", state="combat")
                ambush_mob.apply_balance_profile(self.balance_data.get("enemies", {}).get("rat"), floor_num=self.dungeon.floor_num)
                ambush_mob.awareness = 100.0
                ambush_mob.alert_bang_timer = 0.38
                self.mobs.append(ambush_mob)
                self.play_spatial("alert", ox_c, oy_c)
                self.trigger_event_thought("barrel_rat_ambush")
                self.add_popup(ox_c, oy_c, "ЗАСАДА!", (255, 95, 95))

        elif obj.kind == "bookshelf":
            self.play_spatial("magic", ox_c, oy_c)
            self.emit_noise(ox_c, oy_c, 3.5)
            self.trigger_event_thought("bookshelf_read")
            if self.player.gain_xp(15):
                self.trigger_levelup_shine()
            scroll = self.roll_item_by_rarity(allowed_types=["consumable_spell"])
            if not self.player.add_item_to_inventory(scroll):
                self.objects.append(Interactable(obj.x, obj.y, "loot", scroll))
            self.add_popup(ox_c, oy_c, "+15 ОПЫТ / Свиток", (130, 220, 255))

        elif obj.kind == "alchemy":
            self.player.hp_bonus += 4
            self.player.hp = min(float(self.player.max_hp), self.player.hp + 10)
            pot = self.roll_item_by_rarity(allowed_types=["consumable"])
            if not self.player.add_item_to_inventory(pot):
                self.objects.append(Interactable(obj.x, obj.y, "loot", pot))
            self.play_spatial("heal", ox_c, oy_c)
            self.emit_noise(ox_c, oy_c, 4.0)
            self.trigger_event_thought("alchemy_use")
            self.add_popup(ox_c, oy_c, "+4 Макс.ХП / Зелье", (120, 245, 155))

        elif obj.kind == "rack":
            gear = self.roll_item_by_rarity(allowed_types=["equipment"])
            self.objects.append(Interactable(obj.x, obj.y, "loot", gear))
            self.play_spatial("ui", ox_c, oy_c)
            self.emit_noise(ox_c, oy_c, 4.5)
            self.trigger_event_thought("rack_loot", item=gear.name)
            self.add_popup(ox_c, oy_c, f"Выпало: {gear.name}", gear.rarity_color)

        elif obj.kind == "chest":
            opened = True
            if random.randint(1, 20) + self.player.cunning >= 11:
                if random.random() < 0.60:
                    treasure = self.roll_item_by_rarity(allowed_types=["equipment"])
                else:
                    treasure = self.roll_currency_or_gem_drop()
                self.objects.append(Interactable(obj.x, obj.y, "loot", treasure))
                self.play_spatial("coin_drop", ox_c, oy_c)
                self.emit_noise(ox_c, oy_c, 4.0)
                self.trigger_event_thought("chest_pick_ok", item=treasure.name)
                self.add_popup(ox_c, oy_c, f"В сундуке: {treasure.name}", treasure.rarity_color)
            elif self.player.body >= 3:
                coin_drop = self.roll_currency_or_gem_drop(allow_gem=False)
                self.objects.append(Interactable(obj.x, obj.y, "loot", coin_drop))
                self.play_spatial("crit", ox_c, oy_c)
                self.emit_noise(ox_c, oy_c, 8.5)
                self.trigger_event_thought("chest_smash", item=coin_drop.name)
                self.add_popup(ox_c, oy_c, f"Выпало: {coin_drop.name}", COIN_TEXT_COLOR)
            else:
                opened = False
                self.player.hp = max(1.0, self.player.hp - 2)
                self.play_spatial("hurt", ox_c, oy_c)
                self.emit_noise(ox_c, oy_c, 6.0)
                self.trigger_event_thought("chest_fail", force_important=True)
                self.add_popup(ox_c, oy_c, "СЛОМАНО (-2 ХП)", (255, 95, 95))
            if opened and self.campaign == "jungle" and self.dungeon.interior:
                gear = self.roll_item_by_rarity(allowed_types=["equipment"])
                self.objects.append(Interactable(obj.x, obj.y, "loot", gear))

        elif obj.kind == "idol":
            if self.player.mind >= 3:
                self.player.hp = min(float(self.player.max_hp), self.player.hp + 12)
                self.player.mp = min(float(self.player.max_mp), self.player.mp + 10)
                self.player.trait_vision_mod += 10
                self.play_spatial("magic", ox_c, oy_c)
                self.trigger_event_thought("idol_smart")
                self.add_popup(ox_c, oy_c, "+12 ХП / +Обзор", (110, 245, 190))
            else:
                self.play_spatial("step", ox_c, oy_c)
                self.trigger_event_thought("idol_dumb")
        else:
            self.inspect_prop(obj)
            return True

        obj.used = True
        return True


    def buffer_combat_input(self, wait, tx, ty, item=None):
        if 0.0 < wait <= COMBAT_INPUT_WINDOW:
            self.player.buffered_combat = {"timer": COMBAT_INPUT_WINDOW, "tx": tx, "ty": ty, "item": item}
            return True
        return False

    def update_buffered_combat(self, dt):
        player = self.player
        buffered = player.buffered_combat
        if buffered is None:
            return

        item = buffered["item"]
        cooldown = player.attack_cd if item is None else player.cooldowns.get(item.id, 0.0)
        if player.pending_action is None and cooldown <= 0.0:
            player.buffered_combat = None
            tx, ty = buffered["tx"], buffered["ty"]
            if item is None:
                self._perform_melee_attack(tx, ty)
            elif any(slot is item for slot in (*player.ability_slots, *player.hotbar)):
                self.use_or_equip_item(item, tx, ty, from_hotbar=True)
        else:
            buffered["timer"] -= dt
            if buffered["timer"] <= 0.0:
                player.buffered_combat = None

    def _perform_melee_attack(self, target_wx, target_wy):
        pending = self.player.pending_action
        wait = max(self.player.attack_cd, pending["timer"] if pending is not None else 0.0)
        if self.player.attack_cd > 0.0 or pending is not None:
            self.buffer_combat_input(wait, target_wx, target_wy)
            return
        self.player.buffered_combat = None
        self.world_active = True
        weap = self.player.equipment["right_hand"]
        windup = weap.windup if weap else 0.0
        atk_cd = weap.atk_cd if weap else 0.30
        self.player.attack_cd = atk_cd + windup

        if windup > 0.0:
            dx, dy = target_wx - self.player.x, target_wy - self.player.y
            length = max(0.001, math.hypot(dx, dy))
            self.player.trigger_bump(dx / length * 0.22, dy / length * 0.22)
            self.sfx.play("skill_windup")
            self.player.pending_action = {
                "kind": "melee",
                "timer": windup,
                "max_timer": windup,
                "tx": target_wx,
                "ty": target_wy
            }
        else:
            self._execute_melee_swing(target_wx, target_wy)


    def _physical_attack_context(self, *, check_surprise=False):
        if not check_surprise and not self.player.passive_power("quiet_work"):
            return {}
        return {"unaware_targets": {mob for mob in self.mobs if mob.state != "combat"}}

    def _trigger_firm_stance(self):
        p = self.player
        if p.stance_ready():
            p.activate_passive("firm_stance", PASSIVES["firm_stance"]["duration"])

    def _physical_hit_damage(self, mob, power, armor_pierce, was_unaware=False, action=None):
        p = self.player
        now = p.passive_time
        quiet = p.passive_power("quiet_work")
        if quiet and action is not None and not action.get("quiet_work_used"):
            if was_unaware or mob in action.get("unaware_targets", ()):
                power *= 1.0 + quiet
                action["quiet_work_used"] = True
                p.flash_passive("quiet_work")

        switch = p.passive_power("change_target")
        if (switch and p.passive_active("change_target") and mob is not p.last_killed_target
                and not (action and action.get("change_target_kill"))):
            power *= 1.0 + switch
            p.passive_until.pop("change_target", None)
            p.flash_passive("change_target")
            p.last_killed_target = None

        armor = mob.phys_def
        breaker = p.passive_power("armor_breaker")
        if breaker and armor > 0:
            settings = PASSIVES["armor_breaker"]
            if now >= mob.armor_breaker_ready_at:
                mob.armor_breaker_until = now + settings["duration"]
                mob.armor_breaker_ready_at = now + settings["cooldown"]
                p.flash_passive("armor_breaker")
            if now < mob.armor_breaker_until:
                armor -= max(1, round(armor * breaker))
        return max(1, int(power) - max(0, armor - armor_pierce))

    def _trigger_spell_passives(self, item, mana_paid):
        school = spell_school(item)
        if not school:
            return
        p = self.player
        p.recent_spell_schools[school] = p.passive_time
        if p.passive_power("divine_pact") and 0 < mana_paid < item.mp_cost:
            p.flash_passive("divine_pact")
        focus = p.passive_power("spell_focus")
        if focus:
            for other in p.ability_slots:
                if other and other.id != item.id and spell_school(other) == school and other.id in p.cooldowns:
                    p.cooldowns[other.id] *= 1.0 - focus
                    p.flash_passive("spell_focus")

        pulse = p.passive_power("warding_pulse")
        if not pulse or p.passive_time < p.passive_ready_at.get("warding_pulse", 0.0):
            return
        settings = PASSIVES["warding_pulse"]
        radius = settings["radius"]
        p.passive_ready_at["warding_pulse"] = p.passive_time + settings["cooldown"]
        p.flash_passive("warding_pulse")
        self.visual_fx.append({
            "kind": "aoe_ring", "x": p.x, "y": p.y, "radius": radius,
            "color": (145, 195, 255), "timer": 0.28, "max_timer": 0.28,
        })
        for mob in self.mobs:
            if (math.hypot(mob.x - p.x, mob.y - p.y) <= radius
                    and self.dungeon.has_line_of_sight(p.x, p.y, mob.x, mob.y, radius + 0.5)):
                mob.apply_status("slow", pulse, self.add_popup)

    def _execute_melee_swing(self, target_wx, target_wy):
        px, py = self.player.x, self.player.y
        weap = self.player.equipment["right_hand"]

        hidden_strike = getattr(self.player,"stealth_timer",0)>0
        self.player.stealth_timer = 0
        style = weap.weap_style if weap else "fist"
        reach = weap.reach if weap else 1.38
        arc_deg = weap.arc_deg if weap else 50.0
        max_targets = weap.max_targets if weap else 1
        armor_pierce = weap.armor_pierce if weap else 0
        knockback = weap.knockback if weap else 0.25
        life_steal = (weap.life_steal if weap else 0) + self.player.perk_lifesteal

        origin_y = py - 0.22
        dx = target_wx - px
        dy = target_wy - origin_y
        dist = max(0.001, math.hypot(dx, dy))
        nx, ny = dx / dist, dy / dist

        action = self._physical_attack_context(check_surprise=True)
        # 1. МЕТАТЕЛЬНОЕ ОРУЖИЕ В ПРАВОЙ РУКЕ (с замедлением при броске)
        if style == "thrown" and weap is not None:
            self.emit_noise(px, py, 4.2)
            self.player.trigger_bump(nx * 0.35, ny * 0.35)
            self.player.throw_slowdown_timer = 0.28  # Замедление ног во время броска!
            self.sfx.play("skill_windup")
            w_min = getattr(weap, "dmg_min", 2)
            w_max = getattr(weap, "dmg_max", 4)
            base_dmg = random.randint(w_min, w_max) + self.player.phys_attack + (self.player.cunning // 3)
            self.projectiles.append(Projectile(
                px, origin_y, nx, ny,
                speed=weap.proj_speed,
                mag_dmg=base_dmg,
                color=weap.color,
                from_player=True,
                status=weap.status,
                status_dur=weap.status_dur,
                knockback=knockback,
                visual_kind=getattr(weap, "proj_visual", "spinning_dagger"),
                emits_light=False,
                is_weapon_proj=True,
                armor_pierce=armor_pierce,
                shatter_armor=getattr(weap, "shatter_armor", 0),
                bounces=max(0, int(getattr(weap, "bounces", 0))),
                crit_chance=self.player.crit_chance,
                status_chance=getattr(weap, "status_chance", 1.0),
                life_steal=life_steal,
                max_dist=reach + 0.85
            ))
            self.projectiles[-1].passive_action = action
            return

        wide = self.player.passive_power("wide_swing")
        wide_attack = bool(wide and self.player.passive_active("wide_swing"))
        if wide_attack:
            arc_deg = min(360, arc_deg * (1.0 + wide))
            self.player.passive_until.pop("wide_swing", None)
            self.player.flash_passive("wide_swing")
        # 2. ПЛАВНЫЙ ВЫПАД С ШАГОМ ВПЕРЁД (Сабля, Гладиус, Фальката, Эсток, Фламберг)
        lunge = getattr(weap, "lunge_dist", 0.0) if weap else 0.0
        if lunge > 0.0:
            self.player.trigger_lunge(nx, ny, lunge)

        self.emit_noise(px, py, 5.2)
        base_ang = math.atan2(ny, nx)
        self.player.trigger_bump(
            nx * (0.48 if style in ("dagger", "spear") else 0.32),
            ny * (0.48 if style in ("dagger", "spear") else 0.32)
        )

        half_arc_rad = math.radians(arc_deg * 0.5)
        if style in ("dagger", "spear", "fist"):
            steps = 11 if reach >= 2.2 else (9 if style == "spear" else 6)
            col = (180, 240, 255) if style == "spear" else (240, 240, 250)
            for i in range(1, steps + 1):
                r_step = (i / steps) * reach * 0.90
                self.particles.append(Particle(
                    px + nx * r_step, origin_y + ny * r_step,
                    nx * 2.8, ny * 2.8, col, 2.6, 0.14
                ))
        else:
            spark_count = 18 if arc_deg >= 140 else (14 if arc_deg >= 90 else 10)
            col = (255, 195, 110) if arc_deg >= 100 else (230, 240, 255)
            for i in range(spark_count):
                frac = (i / max(1, spark_count - 1)) * 2.0 - 1.0
                ang = base_ang + frac * half_arc_rad
                r_dist = reach * 0.78
                self.particles.append(Particle(
                    px + math.cos(ang) * r_dist, origin_y + math.sin(ang) * r_dist,
                    math.cos(ang) * 2.2, math.sin(ang) * 2.2, col, 3.0, 0.18
                ))

        cos_threshold = math.cos(min(math.pi, half_arc_rad + 0.18))
        candidates = []
        for m in self.mobs:
            size_pad = 0.55 if getattr(m, "size_tiles", 1) >= 2 else 0.0
            foot_dist = math.hypot(m.x - px, m.y - py)
            torso_dist = math.hypot(m.x - px, (m.y - 0.32) - origin_y)
            md = max(0.0, min(foot_dist, torso_dist) - size_pad)
            if md <= reach + 0.25 and self.dungeon.has_line_of_sight(px, py, m.x, m.y, reach + 1.0):
                hit_model = False
                if is_cursor_on_mob(m, target_wx, target_wy):
                    hit_model = True
                else:
                    for sample_y in (m.y, m.y - 0.30, m.y - 0.62):
                        vx_m = m.x - px
                        vy_m = sample_y - origin_y
                        proj = max(0.0, min(reach, vx_m * nx + vy_m * ny))
                        perp_dist = math.hypot(vx_m - nx * proj, vy_m - ny * proj)
                        if perp_dist <= 0.52:
                            hit_model = True
                            break
                        s_len = max(0.001, math.hypot(vx_m, vy_m))
                        if (vx_m * nx + vy_m * ny) / s_len >= cos_threshold:
                            hit_model = True
                            break

                if hit_model:
                    candidates.append((md, m))

        candidates.sort(key=lambda pair: pair[0])
        targets_selected = candidates[:max_targets]

        multi_hit = getattr(weap, "multi_hit", 1) if weap else 1
        any_killed = False
        hit_count = 0

        for md, m in targets_selected:
            for hit_i in range(multi_hit):
                if m not in self.mobs or m.hp <= 0:
                    break
                was_unaware = m.state != "combat" or (hit_i == 0 and m in action["unaware_targets"])
                dmg, is_crit = self.player.roll_melee_damage(unaware=was_unaware)

                backstab = getattr(weap, "backstab_bonus", 0.0)
                if backstab > 1.0 and (hidden_strike or was_unaware or max(m.stun_timer, m.root_timer, m.slow_timer) > 0):
                    # Suited blades retain a modest precision advantage on vulnerable targets.
                    dmg = int(dmg * (1.0 + min(0.30, (backstab - 1.0) * 0.18)))
                if m.state != "combat":
                    m.alert_to_combat(self.sfx, self.add_popup)

                # Остриё на дистанции (Sweet Spot)
                if weap and getattr(weap, "sweet_spot", False) and md >= reach * 0.56:
                    dmg = int(dmg * 1.45)
                    for _ in range(5):
                        ang_s = random.uniform(0, 6.28)
                        self.particles.append(Particle(m.x, m.y - 0.3, math.cos(ang_s) * 2.6, math.sin(ang_s) * 2.6, (255, 215, 70), 3.0, 0.22))

                # Штраф в упор у сверхдлинной пики
                if weap and getattr(weap, "close_penalty", False) and md < 1.15:
                    dmg = max(1, int(dmg * 0.50))

                if hidden_strike:
                    dmg = int(dmg * 1.35)
                final_dmg = self._physical_hit_damage(m, dmg, armor_pierce, was_unaware, action)
                m.hp -= final_dmg
                if hit_i == 0:
                    hit_count += 1

                # Раскол лат
                shatter = getattr(weap, "shatter_armor", 0) if weap else 0
                if shatter > 0 and m.phys_def > 0:
                    m.phys_def = max(0, m.phys_def - shatter)

                # Крюк-захват или отталкивание
                k_dx = m.x - px
                k_dy = m.y - py
                k_len = max(0.001, math.hypot(k_dx, k_dy))
                if weap and getattr(weap, "hook_pull", False):
                    if md > 0.95:
                        m.apply_knockback(-k_dx / k_len, -k_dy / k_len, knockback)
                else:
                    m.apply_knockback(k_dx / k_len, k_dy / k_len, knockback)

                # Наложение статусов от оружия
                if weap and weap.status and random.random() <= getattr(weap, "status_chance", 1.0):
                    m.apply_status(weap.status, weap.status_dur, self.add_popup, dmg_val=max(2, final_dmg // 3))

                if life_steal > 0:
                    self.player.hp = min(float(self.player.max_hp), self.player.hp + life_steal)
                    self.add_popup(self.player.x, self.player.y, f"+{life_steal}", (120, 245, 140))

                if self.player.mp < self.player.max_mp:
                    mp_gain = self.player.mp_on_hit * (1.5 if is_crit else 1.0)
                    self.player.mp = min(float(self.player.max_mp), self.player.mp + mp_gain)

                m.hit_flash_timer = 0.12
                m.hit_flash_crit = is_crit
                self.fx.add_blood_splatter(m.x, m.y, count=6 if is_crit else 3, is_kill=False, blood_color=m.blood_color)

                y_pop_off = -0.22 * hit_i
                if is_crit:
                    if not getattr(m, "no_rewards", False):
                        self.player.record_build_action("cunning", 0.22)
                    self.sfx.play("crit")
                    self.fx.trigger_shake(2.0, 0.14)
                    self.add_log("combat", f"Критический удар по врагу ({m.kind}): -{final_dmg} ХП!", (255, 230, 95))
                    self.add_popup(m.x, m.y + y_pop_off, f"-{final_dmg}", (255, 230, 75), big=True)
                else:
                    if not getattr(m, "no_rewards", False):
                        self.player.record_build_action("body", 0.15)
                    self.sfx.play("hit")
                    self.add_log("combat", f"Удар по врагу ({m.kind}): -{final_dmg} ХП.")
                    self.add_popup(m.x, m.y + y_pop_off, f"-{final_dmg}", (255, 245, 230))

                if m.hp <= 0:
                    any_killed = True
                self._check_mob_death(m, action)

        p = self.player
        if hit_count:
            self._trigger_firm_stance()
        if (wide and not wide_attack and hit_count >= 2
                and p.passive_time >= p.passive_ready_at.get("wide_swing", 0.0)):
            p.activate_passive("wide_swing", math.inf)
            p.passive_ready_at["wide_swing"] = p.passive_time + PASSIVES["wide_swing"]["cooldown"]

        if any_killed and weap and getattr(weap, "reset_cd_on_kill", False):
            self.player.attack_cd = 0.05

        if not targets_selected:
            self.sfx.play("step")


    def _has_clear_shot(self, x0, y0, x1, y1):
        """Checks both wall sightline AND solid furniture/obstacles for spells that don't ignore obstacles."""
        dist = math.hypot(x1 - x0, y1 - y0)
        steps = int(dist * 3.0) + 1
        for i in range(1, steps):
            t = i / steps
            cx, cy = int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t)
            if self.dungeon.is_blocking_move(cx, cy):
                return False
        return True


    def _execute_skill_or_spell(self, item, target_wx, target_wy, mana_paid=0.0):
        self.player.cast_glow_color = None
        px, py = self.player.x, self.player.y
        is_combat = item.type == "combat_skill"
        action = self._physical_attack_context() if is_combat else {}
        if getattr(item,"shape",None) not in ("stealth","trap","evade"):
            self.emit_noise(px, py, 7.2)
        if getattr(item,"shape",None) not in ("stealth","trap","evade","guard"):
            self.player.stealth_timer = 0
        if item.type == "consumable_spell":
            total_pwr = int(math.floor(item.power * 1.65 + self.player.mag_attack * 1.5))
            growth = ("mind", 0.30)
        elif is_combat:
            _, weapon_high = self.player.melee_damage_range()
            agility_bonus = self.player.cunning // 3 if item.branch == "cunning" else 0
            total_pwr = weapon_high + max(1, int(item.power)) + agility_bonus
            growth = (item.branch, 0.30)
        else:
            total_pwr = int(math.floor(item.power + self.player.mag_attack))
            growth = ("mind", 0.35)
        growth_credit = {"action": growth, "awarded": False, **action}
        c_type = getattr(item, "cast_type", "projectile")
        release_sound = ability_sound(getattr(item, "id", ""))
        if c_type not in ("targeted", "chain_lightning"):
            self._trigger_spell_passives(item, mana_paid)
            self.sfx.play(release_sound)

        if c_type == "physical":
            self._execute_physical_ability(item, total_pwr, target_wx, target_wy, growth_credit)
            return

        if item.life_steal > 0:
            self.player.hp = min(float(self.player.max_hp), self.player.hp + item.life_steal)

        if item.type == "consumable_spell":
            self.player.remove_item_everywhere(item)

        # 1. БОГ ПИРО: Воспламенение (бафф на себя + огненный след + поджог атакующих)
        if c_type == "self_ignite":
            if hasattr(self, "fx") and self.fx:
                self.fx.trigger_shake(1.5, 0.14)
            dur = max(1.5, float(getattr(item, "duration", 5.0)))
            self.player.ignite_timer = dur
            self.player.ignite_growth_credit = growth_credit
            self.player.ignite_burn_dmg = max(1, int(math.floor(item.power + self.player.mag_attack * 0.45)))
            self.visual_fx.append({
                "kind": "aoe_ring",
                "x": px, "y": py, "radius": 1.65,
                "color": (255, 135, 40), "timer": 0.28, "max_timer": 0.28
            })
            self.visual_fx.append({
                "kind": "fire_trail",
                "growth_credit": growth_credit,
                "x": px, "y": py, "radius": 0.85,
                "dmg": self.player.ignite_burn_dmg,
                "color": (255, 110, 35), "timer": 2.6, "max_timer": 2.6
            })
            for _ in range(18):
                ang = random.uniform(0.0, 6.28)
                spd = random.uniform(1.2, 3.4)
                self.particles.append(Particle(
                    px, py - 0.2, math.cos(ang) * spd, math.sin(ang) * spd - 1.2,
                    random.choice([(255, 110, 30), (255, 220, 90), (235, 60, 25)]), 2.9, 0.34
                ))
            return

        # 2. БОГ СТРАТОС: Кольцо холода (мгновенная ледяная волна вокруг героя, игнорирует мебель, но не стены; root -> slow)
        if c_type == "frost_nova":
            if hasattr(self, "fx") and self.fx:
                self.fx.trigger_shake(1.6, 0.14)
            rad = float(getattr(item, "aoe_radius", 2.4))
            root_d = float(getattr(item, "status_dur", 1.2))
            self.visual_fx.append({
                "kind": "frost_nova",
                "x": px, "y": py, "radius": rad,
                "color": item.color, "timer": 0.42, "max_timer": 0.42
            })
            for _ in range(20):
                ang = random.uniform(0.0, 6.28)
                spd = random.uniform(1.8, 4.2)
                self.particles.append(Particle(
                    px + math.cos(ang) * 0.25, py + math.sin(ang) * 0.25,
                    math.cos(ang) * spd, math.sin(ang) * spd,
                    random.choice([(95, 215, 255), (215, 250, 255), (65, 165, 235)]), 2.8, 0.32
                ))
            for m in list(self.mobs):
                if math.hypot(m.x - px, m.y - py) <= rad and self.dungeon.has_line_of_sight(px, py, m.x, m.y, rad + 0.5):
                    m.alert_to_combat(self.sfx, self.add_popup)
                    dmg = max(1, int(math.floor(total_pwr - m.mag_def)))
                    m.hp -= dmg
                    m.apply_status("root", root_d, self.add_popup)
                    m.chill_after_root = max(1.5, root_d * 1.6)
                    m.glow_timer = root_d
                    m.glow_color = (110, 225, 255)
                    self.add_popup(m.x, m.y, f"-{dmg}", item.color)
                    self.record_combat_growth(m, growth_credit)
                    self._check_mob_death(m)
            return

        # 3. БОГ СТРАТОС: Удар молнии (цепочка искр по всем видимым целям с возвратом на 2-й круг!)
        if c_type == "chain_lightning":
            target_mob = min(
                (
                    m for m in self.mobs
                    if math.hypot(m.x - target_wx, (m.y - 0.3) - target_wy) <= 2.6
                    and self._has_clear_shot(px, py, m.x, m.y)
                ),
                key=lambda m: math.hypot(m.x - target_wx, (m.y - 0.3) - target_wy),
                default=None
            )
            if not target_mob:
                if item.type in ("spell", "permanent_spell"):
                    self.player.mp = min(float(self.player.max_mp), self.player.mp + mana_paid)
                self.player.cooldowns.pop(item.id, None)
                self.add_popup(target_wx, target_wy, "Нет цели!", (195, 195, 210))
                return

            self._trigger_spell_passives(item, mana_paid)
            self.sfx.play(release_sound)
            if hasattr(self, "fx") and self.fx:
                self.fx.trigger_shake(1.7, 0.14)
            max_bounces = int(getattr(item, "bounces", 1))
            jump_range = float(getattr(item, "aoe_radius", 4.5))
            hit_sequence = [target_mob]
            visited_in_round = {target_mob}
            curr_m = target_mob

            for _ in range(max_bounces):
                unvisited = [
                    m for m in self.mobs
                    if m is not curr_m and m not in visited_in_round and m.hp > 0
                    and math.hypot(m.x - curr_m.x, m.y - curr_m.y) <= jump_range
                    and self._has_clear_shot(curr_m.x, curr_m.y, m.x, m.y)
                ]
                if not unvisited:
                    visited_in_round = {curr_m}
                    unvisited = [
                        m for m in self.mobs
                        if m is not curr_m and m.hp > 0
                        and math.hypot(m.x - curr_m.x, m.y - curr_m.y) <= jump_range
                        and self._has_clear_shot(curr_m.x, curr_m.y, m.x, m.y)
                    ]
                if not unvisited:
                    break
                nxt_m = min(unvisited, key=lambda m: math.hypot(m.x - curr_m.x, m.y - curr_m.y))
                hit_sequence.append(nxt_m)
                visited_in_round.add(nxt_m)
                curr_m = nxt_m

            chain_pts = [(px, py - 0.25)] + [(m.x, m.y - 0.3) for m in hit_sequence]
            self.visual_fx.append({
                "kind": "chain_lightning",
                "points": chain_pts,
                "color": item.color,
                "timer": 0.38, "max_timer": 0.38
            })
            for m in hit_sequence:
                if m in self.mobs:
                    m.alert_to_combat(self.sfx, self.add_popup)
                    dmg = max(1, int(math.floor(total_pwr - m.mag_def)))
                    m.hp -= dmg
                    m.glow_timer = 0.85
                    m.glow_color = (150, 240, 255)
                    for _ in range(9):
                        ang = random.uniform(0.0, 6.28)
                        spd = random.uniform(1.4, 3.8)
                        self.particles.append(Particle(
                            m.x, m.y - 0.3, math.cos(ang) * spd, math.sin(ang) * spd,
                            random.choice([(115, 225, 255), (235, 255, 255)]), 2.6, 0.24
                        ))
                    self.add_popup(m.x, m.y, f"-{dmg}", item.color)
                    self.record_combat_growth(m, growth_credit)
                    self._check_mob_death(m)
            return

        # 4. БОГ ПЕРСЕФОНА: Омоложение (мгновенный хил + ускоряющаяся регенерация со светлячками)
        if c_type == "self_rejuvenation":
            dur = max(1.0, float(getattr(item, "duration", 5.0)))
            instant_heal = max(2, int(math.floor(total_pwr * 0.38)))
            rem_heal = max(2.0, float(total_pwr - instant_heal))
            if self.player.hp < self.player.max_hp:
                self.player.record_build_action(*growth)
            self.player.hp = min(float(self.player.max_hp), self.player.hp + instant_heal)
            self.player.rejuv_timer = dur
            self.player.rejuv_rate = rem_heal / dur
            for _ in range(14):
                ang = random.uniform(0.0, 6.28)
                self.particles.append(Particle(
                    px + math.cos(ang) * 0.45, py + math.sin(ang) * 0.35,
                    math.cos(ang) * 0.6, -random.uniform(1.2, 2.6),
                    random.choice([(95, 245, 140), (215, 255, 195), (245, 225, 110)]), 2.7, 0.42
                ))
            self.add_popup(px, py, f"+{instant_heal}", (115, 245, 145), "heart")
            return

        # 5. БОГ ПЕРСЕФОНА: Опутывание (корни в области курсора, враги стоят, но могут бить/стрелять)
        if c_type == "entangle_cursor":
            rad = float(getattr(item, "aoe_radius", 2.1))
            root_d = float(getattr(item, "status_dur", 2.2))
            self.visual_fx.append({
                "kind": "entangle_zone",
                "x": target_wx, "y": target_wy, "radius": rad,
                "color": item.color, "timer": 0.50, "max_timer": 0.50
            })
            for _ in range(14):
                ang = random.uniform(0.0, 6.28)
                dist_p = random.uniform(0.1, rad * 0.85)
                self.particles.append(Particle(
                    target_wx + math.cos(ang) * dist_p, target_wy + math.sin(ang) * dist_p,
                    math.cos(ang) * 0.8, -random.uniform(1.0, 2.4),
                    random.choice([(95, 225, 115), (145, 95, 50), (185, 255, 175)]), 2.6, 0.35
                ))
            for m in list(self.mobs):
                if math.hypot(m.x - target_wx, (m.y - 0.2) - target_wy) <= rad:
                    m.alert_to_combat(self.sfx, self.add_popup)
                    dmg = max(1, int(math.floor(total_pwr - m.mag_def)))
                    m.hp -= dmg
                    m.apply_status("root", root_d, self.add_popup)
                    self.add_popup(m.x, m.y, f"-{dmg}", item.color)
                    self.record_combat_growth(m, growth_credit)
                    self._check_mob_death(m)
            return

        if c_type == "aoe_self":
            self.visual_fx.append({
                "kind": "whirlwind_slash",
                "x": px, "y": py, "radius": 2.15,
                "color": item.color, "timer": 0.28, "max_timer": 0.28
            })
            for m in list(self.mobs):
                if math.hypot(m.x - px, m.y - py) <= 2.25:
                    m.alert_to_combat(self.sfx, self.add_popup)
                    dmg = max(1, int(math.floor(total_pwr - m.phys_def)))
                    m.hp -= dmg
                    k_dx, k_dy = m.x - px, m.y - py
                    kl = max(0.001, math.hypot(k_dx, k_dy))
                    m.apply_knockback(k_dx / kl, k_dy / kl, item.knockback)
                    m.apply_status(item.status, item.status_dur, self.add_popup)
                    self.add_popup(m.x, m.y, f"-{dmg}", item.color)
                    self.record_combat_growth(m, growth_credit)
                    self._check_mob_death(m)
            return

        if c_type == "slam_cone":
            dx, dy = target_wx - px, target_wy - (py - 0.2)
            base_a = math.atan2(dy, dx)
            self.visual_fx.append({
                "kind": "slam_wave",
                "x": px, "y": py - 0.15, "angle": base_a,
                "color": item.color, "timer": 0.30, "max_timer": 0.30
            })
            for m in list(self.mobs):
                if (math.hypot(m.x - px, m.y - py) <= item.aoe_radius
                        and math.cos(math.atan2(m.y-py, m.x-px)-base_a) >= .5
                        and self.dungeon.has_line_of_sight(px,py,m.x,m.y,item.aoe_radius+1)):
                    m.alert_to_combat(self.sfx, self.add_popup)
                    total_damage = max(1, total_pwr - m.phys_def)
                    m.hp -= total_damage
                    k_dx, k_dy = m.x - px, m.y - py
                    kl = max(0.001, math.hypot(k_dx, k_dy))
                    m.apply_knockback(k_dx / kl, k_dy / kl, item.knockback)
                    m.apply_status(item.status, item.status_dur, self.add_popup)
                    self.add_popup(m.x, m.y, f"-{total_damage}", item.color)
                    self.record_combat_growth(m, growth_credit)
                    self._check_mob_death(m)
            return

        if c_type == "beam":
            origin_y = py - 0.22
            dx, dy = target_wx - px, target_wy - origin_y
            d = max(0.001, math.hypot(dx, dy))
            nx, ny = dx / d, dy / d
            end_x, end_y = px, origin_y
            for step_i in range(1, 40):
                cx = px + nx * (step_i * 0.22)
                cy = origin_y + ny * (step_i * 0.22)
                if self.dungeon.is_blocking_move(int(cx), int(cy)):
                    end_x, end_y = cx, cy
                    break
                end_x, end_y = cx, cy

            self.visual_fx.append({
                "kind": "beam",
                "x0": px, "y0": origin_y, "x1": end_x, "y1": end_y,
                "color": item.color, "timer": 0.32, "max_timer": 0.32
            })
            beam_len = math.hypot(end_x - px, end_y - origin_y)
            for m in list(self.mobs):
                vx_m, vy_m = m.x - px, (m.y - 0.25) - origin_y
                proj = max(0.0, min(beam_len, vx_m * nx + vy_m * ny))
                if math.hypot(vx_m - nx * proj, vy_m - ny * proj) <= 0.62:
                    m.alert_to_combat(self.sfx, self.add_popup)
                    dmg = max(1, int(math.floor(total_pwr - m.mag_def)))
                    m.hp -= dmg
                    m.apply_status(item.status, item.status_dur, self.add_popup)
                    self.add_popup(m.x, m.y, f"-{dmg}", item.color)
                    self.record_combat_growth(m, growth_credit)
                    self._check_mob_death(m)
            return

        if c_type == "targeted":
            target_mob = min(
                (m for m in self.mobs if math.hypot(m.x - target_wx, (m.y - 0.3) - target_wy) <= 2.4 and dungeon_los_ok(self.dungeon, px, py, m.x, m.y)),
                key=lambda m: math.hypot(m.x - target_wx, (m.y - 0.3) - target_wy),
                default=None
            )
            if not target_mob:
                if item.type in ("spell", "permanent_spell"):
                    self.player.mp = min(float(self.player.max_mp), self.player.mp + mana_paid)
                self.player.cooldowns.pop(item.id, None)
                self.add_popup(target_wx, target_wy, "Нет цели!", (195, 195, 210))
                return
            self._trigger_spell_passives(item, mana_paid)
            self.sfx.play(release_sound)
            target_mob.alert_to_combat(self.sfx, self.add_popup)
            dmg = max(1, int(math.floor(total_pwr - target_mob.mag_def)))
            target_mob.hp -= dmg
            target_mob.apply_status(item.status, item.status_dur, self.add_popup)
            self.record_combat_growth(target_mob, growth_credit)
            self._check_mob_death(target_mob)
            return

        if c_type == "aoe_cursor":
            rad = item.aoe_radius
            if item.status == "poison" and hasattr(self, "fx") and self.fx:
                self.fx.add_gas_cloud(target_wx, target_wy, radius=rad + 0.35, duration=max(4.5, item.status_dur + 1.5), kind="poison", dmg=max(2, total_pwr // 3))
            self.visual_fx.append({
                "kind": "aoe_ring",
                "x": target_wx, "y": target_wy, "radius": rad,
                "color": item.color, "timer": 0.35, "max_timer": 0.35
            })
            for m in list(self.mobs):
                if math.hypot(m.x - target_wx, (m.y - 0.2) - target_wy) <= rad:
                    m.alert_to_combat(self.sfx, self.add_popup)
                    dmg = max(1, int(math.floor(total_pwr - m.mag_def)))
                    m.hp -= dmg
                    m.apply_status(item.status, item.status_dur, self.add_popup, dmg_val=max(2, total_pwr // 3))
                    self.add_popup(m.x, m.y, f"-{dmg}", item.color)
                    self.record_combat_growth(m, growth_credit)
                    self._check_mob_death(m)
            return

        is_dagger = (item.id == "throw_knife" or is_combat or item.icon in ("weapon_cleaver", "weapon_sword"))
        projectile = self._fire_spell_bolt(
            total_pwr, item.color, target_wx, target_wy,
            speed=item.proj_speed, status=item.status, status_dur=item.status_dur, knockback=item.knockback,
            visual_kind="spinning_dagger" if is_dagger else "orb",
            emits_light=not is_dagger, play_sound=False
        )
        projectile.growth_credit = growth_credit


    def _fire_spell_bolt(self, mag_dmg, color, target_wx, target_wy, speed=9.2, status=None, status_dur=0.0, knockback=0.0, visual_kind="orb", emits_light=True, *, play_sound=True):
        if target_wx is None or target_wy is None:
            target_wx, target_wy = self.player.x + 1.0, self.player.y
        dx = target_wx - self.player.x
        dy = target_wy - (self.player.y - 0.2)
        d = max(0.001, math.hypot(dx, dy))
        if play_sound:
            self.sfx.play("hit" if visual_kind == "spinning_dagger" else "magic")
        self.projectiles.append(Projectile(
            self.player.x, self.player.y - 0.2, dx / d, dy / d,
            speed=speed, mag_dmg=mag_dmg, color=color, from_player=True,
            status=status, status_dur=status_dur, knockback=knockback,
            visual_kind=visual_kind, emits_light=emits_light
        ))
        return self.projectiles[-1]


    def record_combat_growth(self, target, credit):
        """Share one growth credit across all targets/bounces of a cast."""
        if credit and not credit["awarded"] and not getattr(target, "no_rewards", False):
            self.player.record_build_action(*credit["action"])
            credit["awarded"] = True


    def _check_mob_death(self, m, action=None):
        if m.hp <= 0 and m in self.mobs:
            self.mobs.remove(m)
            if m.kind == "rat_king":
                self.fx.add_boss_bloodbath(m.x, m.y, self.dungeon)
                self.sfx.play("crit")
            else:
                self.fx.add_blood_splatter(m.x, m.y, count=10, is_kill=True, blood_color=m.blood_color)
                if random.random() < 0.75:
                    self.fx.spawn_gibs(m.x, m.y, count=random.randint(1, 3), blood_color=m.blood_color)
            if getattr(m, "no_rewards", False):
                self.add_log("combat", f"Враг из засады повержен: {m.kind} (0 опыта).", (165, 165, 175))
                for _ in range(10):
                    ang = random.uniform(0, 6.28)
                    spd = random.uniform(0.8, 2.8)
                    self.particles.append(Particle(m.x, m.y, math.cos(ang) * spd, math.sin(ang) * spd, (190, 180, 170), 2.8, 0.40))
                return
            p = self.player
            if p.passive_power("change_target") and p.passive_time >= p.passive_ready_at.get("change_target", 0.0):
                settings = PASSIVES["change_target"]
                p.last_killed_target = m
                p.activate_passive("change_target", settings["duration"])
                p.passive_ready_at["change_target"] = p.passive_time + settings["cooldown"]
                if action is not None:
                    action["change_target_kill"] = True
            name = self.loc.get("jungle_enemy_names", {}).get(m.kind, m.kind)
            self.add_log("combat", f"Враг повержен: {name} (+{m.xp_value} опыта).", (135, 245, 160))
            drop_tx, drop_ty = int(m.x), int(m.y)
            if getattr(m, "is_boss", False):
                # За босса выдаём платину и снаряжение повышенной редкости.
                plat = self.make_item("coin_platinum")
                boss_gear = self.roll_item_by_rarity(allowed_types=["equipment"], luck=self.player.luck + 4)
                self.objects.append(Interactable(drop_tx, drop_ty, "loot", plat))
                self.objects.append(Interactable(max(1, drop_tx - 1), drop_ty, "loot", boss_gear))
                self.sfx.play("coin_drop")
            else:
                # С обычных мобов деньги падают нечасто, а самоцветы — в 10 раз реже!
                drop_chance = 0.44 if m.is_ranged else 0.28
                if random.random() < drop_chance:
                    loot_drop = self.roll_currency_or_gem_drop(allow_gem=True, gem_mult=0.1)
                    self.objects.append(Interactable(drop_tx, drop_ty, "loot", loot_drop))
                    self.play_spatial("coin_drop", drop_tx + 0.5, drop_ty + 0.5)
                if random.random() < (0.18 if self.dungeon.floor_num >= 2 else 0.10):
                    gear = self.roll_item_by_rarity(allowed_types=["equipment"])
                    self.objects.append(Interactable(drop_tx, drop_ty, "loot", gear))

            is_magic_mob = (getattr(m, "is_boss", False) or m.is_ranged or m.kind in ("rat_cultist", "cultist", "necromancer"))
            should_drop_shard = is_magic_mob or (random.random() < 0.28)

            if should_drop_shard:
                shard_count = 3 if getattr(m, "is_boss", False) else 1
                base_mp = 3 if getattr(m, "is_boss", False) else (2 if is_magic_mob else 1)
                for _ in range(shard_count):
                    s_ang = random.uniform(0, 6.28)
                    s_dist = random.uniform(0.35, 0.95)
                    sx_cand = m.x + math.cos(s_ang) * s_dist
                    sy_cand = m.y + math.sin(s_ang) * s_dist
                    if self.dungeon.is_blocking_move(int(sx_cand), int(sy_cand)):
                        sx_cand, sy_cand = m.x, m.y
                    self.visual_fx.append({
                        "kind": "mana_shard",
                        "x": sx_cand, "y": sy_cand,
                        "mp": base_mp,
                        "color": (85, 205, 255),
                        "timer": 4.2, "max_timer": 4.2
                    })

            if m.kind == "rat_king":
                if not self.profile.get("rat_king_defeated", False):
                    self.profile["rat_king_defeated"] = True
                    save_profile(self.profile)
                    self.add_popup(m.x, m.y - 1.25, "ОТКРЫТ КРЫСОЛЮД!", (125, 255, 155), big=True)
                defeat_pool = get_mission_texts(self.loc).get("boss_defeat", ["Крысиный Король повержен!"])
                # Победа над боссом — ВАЖНАЯ реплика!
                self.set_thought(self.pick_text(defeat_pool, "boss_defeat"), important=True)
                self.add_popup(m.x, m.y - 0.8, "БОСС ПОВЕРЖЕН!", (255, 215, 65))
                self.objects.append(Interactable(drop_tx, drop_ty, "stairs"))
            elif m.is_boss and m.jungle_home is not None:
                self.trigger_event_thought("jungle_guardian_defeated", force_important=True, enemy=name)
                gear = self.roll_item_by_rarity(allowed_types=["equipment"])
                self.objects.append(Interactable(drop_tx, drop_ty, "loot", gear))
                self.add_popup(m.x, m.y - 0.8, "СТРАЖ ПОВЕРЖЕН!", (255, 215, 65))
            else:
                # Реплика при убийстве обычного моба — ФОНОВАЯ (шанс 22%, не чаще раза в 6 сек)!
                if self.can_trigger_background_thought(chance=0.22):
                    self.set_thought(self.pick_text(self.player.thoughts["kill"], "player_kill"), important=False, chance=1.0)

            if self.player.gain_xp(m.xp_value):
                self.trigger_levelup_shine()

            for _ in range(14):
                ang = random.uniform(0, 6.28)
                spd = random.uniform(0.8, 3.2)
                self.particles.append(Particle(m.x, m.y, math.cos(ang) * spd, math.sin(ang) * spd, (220, 210, 195), 3.0, 0.45))
            if m.kind != "rat_king":
                colors = BLOOD_PALETTES[m.blood_color].particles
                for _ in range(18):
                    ang = random.uniform(0, 6.28)
                    spd = random.uniform(1.0, 3.8)
                    bcol = random.choice(colors)
                    self.particles.append(Particle(m.x, m.y, math.cos(ang) * spd, math.sin(ang) * spd, bcol, random.uniform(1.8, 3.4), random.uniform(0.22, 0.48)))


    def _execute_physical_ability(self, item, power, tx, ty, credit):
        from elenor.game.physical import execute_physical
        execute_physical(self, item, power, tx, ty, credit)
