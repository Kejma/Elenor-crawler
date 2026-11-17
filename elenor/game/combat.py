import math
import random

from elenor.entities import Enemy, Interactable, Projectile, Particle
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
        dmg = max(1, int(math.floor((raw_dmg - defense) * (.55 if getattr(self.player,"guard_timer",0)>0 else 1))))
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
            if not self._try_precise_interaction(px, py, max_cursor_dist=1.65):
                self._perform_melee_attack(target_wx, target_wy)


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
            if door.locked:
                self.sfx.play("hurt")
                self.emit_noise(dx + 0.5, dy + 0.5, 4.5)
                self.trigger_event_thought("door_locked")
                self.add_popup(dx + 0.5, dy + 0.5, "ЗАПЕРТО", (255, 120, 100))
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
            if not obj.used and obj.kind != "trap"
            and math.hypot(px - (obj.x + 0.5), py - (obj.y + 0.5)) <= (2.65 if obj.kind in ("npc_innkeeper", "npc_merchant") else 1.85)
            and math.hypot(ref_wx - (obj.x + 0.5), ref_wy - (obj.y + 0.5)) <= max_cursor_dist
        ]
        if not cand_objs:
            return False

        cand_objs.sort(key=lambda o: math.hypot(ref_wx - (o.x + 0.5), ref_wy - (o.y + 0.5)))
        obj = cand_objs[0]

        if obj.kind == "merchant_counter":
            self.interact_with_merchant(obj.merchant_owner)
            return True
        if obj.kind in ("merchant_shelves", "merchant_goods", "merchant_sign"):
            self.set_thought(self.loc.get("merchant_room", {}).get(obj.kind, ""), important=False)
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
            danger_nearby = any(m.state == "combat" and math.hypot(m.x - px, m.y - py) <= 3.2 for m in self.mobs)
            if danger_nearby:
                self.sfx.play("hurt")
                self.trigger_event_thought("stairs_combat")
                self.add_popup(obj.x + 0.5, obj.y + 0.5, "В БОЮ!", (255, 95, 95))
                return True
            self.descend_to_next_floor()
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
                self.sfx.play("step")
                self.trigger_event_thought("campfire_has_torch")
            return True

        if obj.kind == "loot":
            return self._pickup_loot_object(obj)

        ox_c, oy_c = obj.x + 0.5, obj.y + 0.5

        if obj.kind == "barrel":
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
            if random.randint(1, 20) + self.player.cunning >= 11:
                treasure = self.roll_currency_or_gem_drop(allow_gem=True, force_gem=(random.random() < 0.55))
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
                self.add_popup(ox_c, oy_c, f"Выпало: {coin_drop.name}", coin_drop.rarity_color)
            else:
                self.player.hp = max(1.0, self.player.hp - 2)
                self.play_spatial("hurt", ox_c, oy_c)
                self.emit_noise(ox_c, oy_c, 6.0)
                self.trigger_event_thought("chest_fail", force_important=True)
                self.add_popup(ox_c, oy_c, "СЛОМАНО (-2 ХП)", (255, 95, 95))

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
            # Consume the interaction, leaving scenery intact.
            return True

        obj.used = True
        return True


    def _perform_melee_attack(self, target_wx, target_wy):
        if self.player.attack_cd > 0.0 or self.player.pending_action is not None:
            return
        weap = self.player.equipment["right_hand"]
        windup = weap.windup if weap else 0.0
        atk_cd = weap.atk_cd if weap else 0.30
        self.player.attack_cd = atk_cd + windup

        if windup > 0.0:
            self.player.pending_action = {
                "kind": "melee",
                "timer": windup,
                "max_timer": windup,
                "tx": target_wx,
                "ty": target_wy
            }
        else:
            self._execute_melee_swing(target_wx, target_wy)


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
            return

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

        cos_threshold = math.cos(half_arc_rad + 0.18)
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

        for md, m in targets_selected:
            for hit_i in range(multi_hit):
                if m not in self.mobs or m.hp <= 0:
                    break
                dmg, is_crit = self.player.roll_melee_damage()

                bs_bonus = getattr(weap, "backstab_bonus", 0.0) if weap else 0.0
                is_vulnerable = (m.state != "combat" or m.stun_timer > 0 or m.root_timer > 0 or m.slow_timer > 0)
                if m.state != "combat":
                    dmg = int(dmg * (1 if hidden_strike else max(self.player.backstab_mult, bs_bonus)))
                    is_crit = True
                    m.alert_to_combat(self.sfx, self.add_popup)
                elif bs_bonus > 1.0 and is_vulnerable:
                    dmg = int(dmg * bs_bonus)
                    is_crit = True

                # Остриё на дистанции (Sweet Spot)
                if weap and getattr(weap, "sweet_spot", False) and md >= reach * 0.56:
                    dmg = int(dmg * 1.45)
                    for _ in range(5):
                        ang_s = random.uniform(0, 6.28)
                        self.particles.append(Particle(m.x, m.y - 0.3, math.cos(ang_s) * 2.6, math.sin(ang_s) * 2.6, (255, 215, 70), 3.0, 0.22))

                # Штраф в упор у сверхдлинной пики
                if weap and getattr(weap, "close_penalty", False) and md < 1.15:
                    dmg = max(1, int(dmg * 0.50))

                eff_def = max(0, m.phys_def - armor_pierce)
                if hidden_strike:
                    dmg = int(dmg * 1.35)
                final_dmg = max(1, dmg - eff_def)
                m.hp -= final_dmg

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
                self.fx.add_blood_splatter(m.x, m.y, count=6 if is_crit else 3, is_kill=False)

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
                self._check_mob_death(m)

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


    def _execute_skill_or_spell(self, item, target_wx, target_wy):
        self.player.cast_glow_color = None
        px, py = self.player.x, self.player.y
        if getattr(item,"shape",None) not in ("stealth","trap","evade"):
            self.emit_noise(px, py, 7.2)
        if getattr(item,"shape",None) not in ("stealth","trap","evade","guard"):
            self.player.stealth_timer = 0
        is_combat = (item.type == "combat_skill")
        if item.type == "consumable_spell":
            total_pwr = int(math.floor(item.power * 1.65 + self.player.mag_attack * 1.5))
            growth = ("mind", 0.30)
        elif is_combat:
            total_pwr = int(math.floor(item.power + (self.player.cunning + self.player.perk_phys_atk if item.branch == "cunning" else self.player.phys_attack)))
            growth = (item.branch, 0.30)
        else:
            total_pwr = int(math.floor(item.power + self.player.mag_attack))
            growth = ("mind", 0.35)
        growth_credit = {"action": growth, "awarded": False}
        c_type = getattr(item, "cast_type", "projectile")

        if c_type == "physical":
            self._execute_physical_ability(item, total_pwr, target_wx, target_wy, growth_credit)
            return

        if item.life_steal > 0:
            self.player.hp = min(float(self.player.max_hp), self.player.hp + item.life_steal)

        if item.type == "consumable_spell":
            self.player.remove_item_everywhere(item)

        # 1. БОГ ПИРО: Воспламенение (бафф на себя + огненный след + поджог атакующих)
        if c_type == "self_ignite":
            self.sfx.play("torch")
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
            self.sfx.play("magic")
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
                    self.player.mp = min(float(self.player.max_mp), self.player.mp + item.mp_cost)
                self.player.cooldowns.pop(item.id, None)
                self.add_popup(target_wx, target_wy, "Нет цели!", (195, 195, 210))
                return

            self.sfx.play("crit")
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
            self.sfx.play("heal")
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
            self.sfx.play("magic")
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
            self.sfx.play("crit")
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
            self.sfx.play("crit")
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
            self.sfx.play("magic")
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
                    self.player.mp = min(float(self.player.max_mp), self.player.mp + item.mp_cost)
                self.player.cooldowns.pop(item.id, None)
                self.add_popup(target_wx, target_wy, "Нет цели!", (195, 195, 210))
                return
            self.sfx.play("magic")
            target_mob.alert_to_combat(self.sfx, self.add_popup)
            dmg = max(1, int(math.floor(total_pwr - target_mob.mag_def)))
            target_mob.hp -= dmg
            target_mob.apply_status(item.status, item.status_dur, self.add_popup)
            self.record_combat_growth(target_mob, growth_credit)
            self._check_mob_death(target_mob)
            return

        if c_type == "aoe_cursor":
            self.sfx.play("magic")
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
            emits_light=not is_dagger
        )
        projectile.growth_credit = growth_credit


    def _fire_spell_bolt(self, mag_dmg, color, target_wx, target_wy, speed=9.2, status=None, status_dur=0.0, knockback=0.0, visual_kind="orb", emits_light=True):
        if target_wx is None or target_wy is None:
            target_wx, target_wy = self.player.x + 1.0, self.player.y
        dx = target_wx - self.player.x
        dy = target_wy - (self.player.y - 0.2)
        d = max(0.001, math.hypot(dx, dy))
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


    def _check_mob_death(self, m):
        if m.hp <= 0 and m in self.mobs:
            self.mobs.remove(m)
            self.fx.add_blood_splatter(m.x, m.y, count=10, is_kill=True)
            if getattr(m, "no_rewards", False):
                self.add_log("combat", f"Враг из засады повержен: {m.kind} (0 опыта).", (165, 165, 175))
                for _ in range(10):
                    ang = random.uniform(0, 6.28)
                    spd = random.uniform(0.8, 2.8)
                    self.particles.append(Particle(m.x, m.y, math.cos(ang) * spd, math.sin(ang) * spd, (190, 180, 170), 2.8, 0.40))
                return
            self.add_log("combat", f"Враг повержен: {m.kind} (+{m.xp_value} опыта).", (135, 245, 160))
            drop_tx, drop_ty = int(m.x), int(m.y)
            if getattr(m, "is_boss", False):
                # С Босса высыпается платина и редкий самоцвет!
                plat = self.make_item("coin_platinum")
                gem_boss = self.make_item(random.choice(["gem_ruby", "gem_diamond"]))
                self.objects.append(Interactable(drop_tx, drop_ty, "loot", plat))
                self.objects.append(Interactable(max(1, drop_tx - 1), drop_ty, "loot", gem_boss))
                self.sfx.play("coin_drop")
            else:
                # С обычных мобов деньги падают нечасто, а самоцветы — в 10 раз реже!
                drop_chance = 0.44 if m.is_ranged else 0.28
                if random.random() < drop_chance:
                    loot_drop = self.roll_currency_or_gem_drop(allow_gem=True, gem_mult=0.1)
                    self.objects.append(Interactable(drop_tx, drop_ty, "loot", loot_drop))
                    self.play_spatial("coin_drop", drop_tx + 0.5, drop_ty + 0.5)

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

            if getattr(m, "is_boss", False):
                if not self.profile.get("rat_king_defeated", False):
                    self.profile["rat_king_defeated"] = True
                    save_profile(self.profile)
                    self.add_popup(m.x, m.y - 1.25, "ОТКРЫТ КРЫСОЛЮД!", (125, 255, 155), big=True)
                defeat_pool = get_mission_texts(self.loc).get("boss_defeat", ["Крысиный Король повержен!"])
                # Победа над боссом — ВАЖНАЯ реплика!
                self.set_thought(self.pick_text(defeat_pool, "boss_defeat"), important=True)
                self.add_popup(m.x, m.y - 0.8, "БОСС ПОВЕРЖЕН!", (255, 215, 65))
                self.objects.append(Interactable(int(m.x), int(m.y), "stairs"))
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


    def _execute_physical_ability(self, item, power, tx, ty, credit):
        from elenor.game.physical import execute_physical
        execute_physical(self, item, power, tx, ty, credit)
