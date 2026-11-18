from elenor.config import SHALLOW_WATER
from elenor.data.abilities import perk_branch
import math
import random
from elenor.config import PLAYER_BASE_SPEED, TORCH_BASE_RADIUS, DARK_VISION_RADIUS


from elenor.entities.items import Item


class Player:
    def __init__(self, x, y, adj_key, adj_data, noun_key, noun_data, items_db, appearance=None):
        self.x = float(x) + 0.5
        self.y = float(y) + 0.5
        self.bump_x = 0.0
        self.bump_y = 0.0
        self.lunge_vx = 0.0
        self.lunge_vy = 0.0
        self.throw_slowdown_timer = 0.0
        self.facing = -1
        self.is_moving = False
        self.anim_timer = 0.0
        self.anim_frame = 0
        self.appearance = appearance or {"hero_type": "male", "skin_idx": 0, "head_idx": 0, "outfit_idx": 0}

        self.full_name = f"{adj_data['title']} {noun_data['title']}"
        self.cloak_color = tuple(adj_data["color"])
        self.trait_vision_mod = adj_data.get("vision_mod", 0)
        self.quirk = adj_data.get("quirk", "none")
        self.quirk_desc = adj_data.get("quirk_desc", "")

        self.thoughts = {}
        for category in ("spawn", "ambient", "kill"):
            self.thoughts[category] = adj_data.get(category, []) + noun_data.get(category, [])

        s_adj = adj_data["stats"]
        s_noun = noun_data["stats"]
        self.body = 1 + s_adj["body"] + s_noun["body"]
        self.cunning = 1 + s_adj["cunning"] + s_noun["cunning"]
        self.mind = 1 + s_adj["mind"] + s_noun["mind"]

        self.level = 1
        self.xp = 0
        self.max_xp = 48
        self.stat_points = 0
        self.pending_perk_rolls = 0

        # Max 2 Active abilities ([Q], [E]) and max 5 Passive perks!
        self.perks = {}              # perk_id -> level
        self.active_perks = {}       # perk_id -> level (max 4 keys)
        self.passive_perks = {}      # perk_id -> level (disabled)
        self.perk_timers = {"storm_aura": 1.5}
        self.cooldowns = {}          # item_or_perk_id -> remaining cooldown seconds
        self.pending_action = None   # Holds windup action dict before strike/cast fires!
        self.buffered_combat = None
        self.overflow_drops = []     # Items displaced by 2H weapons when pockets are full
        self.levelup_delay_timer = 0.0
        self.shine_timer = 0.0
        self.cast_glow_color = None
        # Pyro Ignite buff state
        self.ignite_timer = 0.0
        self.ignite_burn_dmg = 4.0
        self.ignite_trail_tick = 0.0
        # Persephone Rejuvenation buff state
        self.rejuv_timer = 0.0
        self.rejuv_rate = 0.0
        self.god_mode = False        # Used by Dev Cheat Panel

        # Cumulative action points for Adaptive Build Affinity (Силач / Ловкач / Маг)
        self.action_affinity = {"body": 0.0, "cunning": 0.0, "mind": 0.0}

        self.hp_bonus = 0
        self.mp_bonus = 0
        self.perk_phys_atk = 0
        self.perk_mag_atk = 0
        self.perk_phys_def = 0
        self.perk_mag_def = 0
        self.perk_crit = 0.0
        self.perk_dodge = 0.0
        self.perk_noise = 0.0
        self.perk_lifesteal = 0
        self.hp_regen = 0.0
        self.perk_mp_regen = 0.0
        self.backstab_mult = 1.8

        self.luck = 1
        self.hp = float(self.max_hp)
        self.mp = float(self.max_mp)
        self.gold = 0

        # Start every run with the torch extinguished!
        self.torch_on = False
        self.illumination = 0.25
        self.attack_cd = 0.0
        self.step_sound_cd = 0.0

        # Expanded to 24 max slots (starts with 2 pockets, or 4 for Hoarder!)
        self.max_possible_slots = 24
        self.unlocked_slots = 4 if self.quirk == "hoarder" else 2
        self.bag_name = f"Карманы ({self.unlocked_slots} яч.)"
        self.inventory = [None] * self.max_possible_slots

        self.equipment = {
            "right_hand": None,
            "left_hand": Item("pitch_torch", items_db["pitch_torch"]),
            "helmet": None,
            "torso": None,
            "boots": None,
            "ring_1": None,
            "ring_2": None,
            "trinket": None,
        }

        # Q and E slots for Active Abilities; 1..4 slots for Consumables!
        self.ability_slots = [None] * 4
        self.guard_timer = self.evade_timer = self.stealth_timer = 0.0
        self.hotbar = [None] * 4

    @property
    def max_hp(self):
        return 18 + self.body * 6 + (self.level - 1) * 4 + self.hp_bonus

    @property
    def max_mp(self):
        return max(4, 4 + self.mind * 2 + (self.level - 1) * 1 + self.mp_bonus)

    def get_active_torch(self):
        for hand in ("left_hand", "right_hand"):
            itm = self.equipment[hand]
            if itm and itm.is_torch and itm.fuel > 0:
                return itm
        return None

    @property
    def has_lit_torch(self):
        return self.torch_on and (self.get_active_torch() is not None)

    def _sum_equip(self, attr):
        total = 0
        for itm in self.equipment.values():
            if itm:
                total += getattr(itm, attr, 0)
        return total

    @property
    def dark_vision_radius(self):
        return max(30.0, DARK_VISION_RADIUS + self.trait_vision_mod + self._sum_equip("vision_bonus"))

    @property
    def torch_light_radius(self):
        torch = self.get_active_torch()
        if self.torch_on and torch:
            base_r = TORCH_BASE_RADIUS * (1.22 if self.quirk == "pyromaniac" else 1.0)
            return base_r + self._sum_equip("vision_bonus")
        return self.dark_vision_radius

    def get_heal_amount(self, item):
        base_h = getattr(item, "heal_hp", 0)
        if base_h <= 0:
            return 0
        if self.quirk == "hypochondriac":
            return int(math.ceil(base_h * 1.25))
        return int(base_h)

    @property
    def phys_attack(self):
        return self.body + self._sum_equip("phys_bonus") + self.perk_phys_atk

    @property
    def mag_attack(self):
        return self.mind + self._sum_equip("mag_bonus") + self.perk_mag_atk

    @property
    def phys_defense(self):
        return self._sum_equip("phys_def") + self.perk_phys_def

    @property
    def mag_defense(self):
        return (self.mind // 2) + self._sum_equip("mag_def") + self.perk_mag_def

    @property
    def noise_factor(self):
        hoarder_noise = 0.0
        if self.quirk == "hoarder":
            filled = sum(1 for i in range(self.unlocked_slots) if self.inventory[i] is not None)
            hoarder_noise = filled * 0.03
        return max(0.20, 1.0 + self._sum_equip("noise_mod") + self.perk_noise + hoarder_noise)

    @property
    def dodge_chance(self):
        return min(0.55, self.cunning * 0.04 + self.perk_dodge)

    @property
    def crit_chance(self):
        return min(0.75, self.cunning * 0.05 + self.perk_crit + self._sum_equip("crit_bonus"))

    def gain_xp(self, amount):
        self.xp += amount
        leveled = False
        while self.xp >= self.max_xp:
            self.xp -= self.max_xp
            self.level += 1
            self.max_xp = 120 if self.level == 2 else int(self.max_xp * 1.55)
            self.pending_perk_rolls += 1
            self.hp = min(float(self.max_hp), self.hp + 6.0)
            self.mp = min(float(self.max_mp), self.mp + 4.0)
            leveled = True
        return leveled

    @property
    def mp_on_hit(self):
        """Мана, выбиваемая каждым попаданием в ближнем бою (Комбо А)."""
        gain = 0.3 + self.perk_mp_regen
        for itm in self.equipment.values():
            if itm and getattr(itm, "armor_class", "") == "cloth":
                gain += 1.0
            elif itm and getattr(itm, "mag_bonus", 0) >= 2:
                gain += 0.5
        return gain

    @property
    def mp_shard_bonus(self):
        """Дополнительная мана при подборе эфирного осколка с убитого врага (Комбо Б)."""
        bonus = int(self.perk_mp_regen * 2.0)
        for itm in self.equipment.values():
            if itm and getattr(itm, "armor_class", "") == "cloth":
                bonus += 1
        return bonus

    def record_build_action(self, branch, amount=0.25):
        """
        Механика «Трёхплечевых весов»:
        - Чем сильнее плечо X оторвалось от двух других, тем сильнее противовес гасит дальнейший рост (сопротивление).
        - Если плечо отстаёт, сопротивления нет и оно догоняет быстрее.
        - Общее затухание по мере роста (dampener) исключает бесконечный разгон цифр.
        """
        if branch not in self.action_affinity:
            return
        cur_score = self.action_affinity[branch]
        other_scores = [v for k, v in self.action_affinity.items() if k != branch]
        avg_other = sum(other_scores) / max(1, len(other_scores))
        delta_lead = cur_score - avg_other

        if delta_lead > 0.0:
            scale_friction = 1.0 / (1.0 + delta_lead * 0.22)
        else:
            scale_friction = 1.0 + min(0.85, abs(delta_lead) * 0.12)

        global_damp = 25.0 / (25.0 + cur_score)
        effective_gain = amount * scale_friction * global_damp
        self.action_affinity[branch] += effective_gain

    def get_build_affinities(self):
        """Computes cumulative player build leanings: {'body': float, 'cunning': float, 'mind': float}."""
        scores = {
            "body": max(0.0, (self.body - 1) * 1.5) + self.action_affinity["body"],
            "cunning": max(0.0, (self.cunning - 1) * 1.5) + self.action_affinity["cunning"],
            "mind": max(0.0, (self.mind - 1) * 1.5) + self.action_affinity["mind"],
        }
        # 1. Count equipped gear
        for itm in self.equipment.values():
            if not itm or itm.is_torch:
                continue
            if itm.armor_class == "plate" or itm.two_handed or itm.weap_style in ("mace", "cleaver", "axe", "halberd"):
                scores["body"] += 2.5
            if itm.armor_class == "leather" or itm.weap_style in ("dagger", "spear", "thrown", "curved") or itm.noise_mod < 0:
                scores["cunning"] += 2.5
            if itm.armor_class == "cloth" or itm.mag_bonus > 0 or itm.mp_regen > 0:
                scores["mind"] += 2.8
            scores["body"] += itm.phys_bonus * 0.7 + itm.phys_def * 0.5
            scores["mind"] += itm.mag_bonus * 1.1 + itm.mag_def * 0.6

        # 2. Count learned perks
        perk_tags = {
            "tough_skin": "body", "iron_grip": "body", "stone_ribs": "body",
            "titan_blood": "body", "blood_hunger": "body", "whirlwind": "body", "earth_slam": "body",
            "cat_step": "cunning", "keen_edge": "cunning", "throw_knife": "cunning", "poison_flask": "cunning",
            "clear_mind": "mind", "storm_aura": "mind",
            "pyro_firebolt": "mind", "pyro_ignite": "mind",
            "stratos_frost_nova": "mind", "stratos_chain_lightning": "mind",
            "persephone_rejuvenation": "mind", "persephone_entangle": "mind"
        }
        for pid, lvl in self.perks.items():
            tag = perk_branch(pid) or perk_tags.get(pid, "body")
            scores[tag] += lvl * 3.0
        return scores

    def swap_inventory_slots(self, idx_a, idx_b):
        if 0 <= idx_a < self.unlocked_slots and 0 <= idx_b < self.unlocked_slots:
            self.inventory[idx_a], self.inventory[idx_b] = self.inventory[idx_b], self.inventory[idx_a]
            return True
        return False

    def try_auto_equip_if_slot_empty(self, item):
        """Equips ground equipment directly ONLY if its target equipment slot is currently empty!"""
        if not item or item.type != "equipment":
            return False
        slot = item.slot
        if slot == "ring":
            if self.equipment["ring_1"] is None:
                self.equipment["ring_1"] = item
                return True
            if self.equipment["ring_2"] is None:
                self.equipment["ring_2"] = item
                return True
            return False

        if slot == "right_hand":
            if self.equipment["right_hand"] is None:
                if item.two_handed and self.equipment["left_hand"] is not None:
                    old_off = self.equipment["left_hand"]
                    self.equipment["left_hand"] = None
                    if not self.add_item_to_inventory(old_off):
                        self.overflow_drops.append(old_off)
                self.equipment["right_hand"] = item
                return True
            return False

        if slot == "left_hand":
            main_w = self.equipment["right_hand"]
            if self.equipment["left_hand"] is None and not (main_w and main_w.two_handed):
                self.equipment["left_hand"] = item
                return True
            return False

        if slot in self.equipment and self.equipment[slot] is None:
            self.equipment[slot] = item
            return True
        return False

    @staticmethod
    def eval_stat_with_pct(spell_id, stat_key, base_val, total_pct):
        """
        Пересчитывает параметр способности строго от базового значения (base_val)
        по сумме всех накопленных процентов (total_pct).
        Пример: база 10, +12% и +24% -> сумма +36% -> 10 * 1.36 = 13.6 (в бою math.floor -> 13).
        """
        if stat_key == "cooldown":
            return max(0.30, round(base_val / (1.0 + total_pct), 2))
        if stat_key == "duration" and spell_id == "persephone_rejuvenation":
            # Для Омоложения Персефоны улучшение СНИЖАЕТ длительность, чтобы регенерировать быстрее!
            return max(1.0, round(base_val / (1.0 + total_pct), 2))
        if stat_key == "bounces":
            # Каждые накопленные +12%..+24% дают ощутимый прирост отскоков (минимум +1 за каждый апгрейд отскоков)
            return int(base_val + math.ceil(total_pct * 4.0 - 1e-6)) if total_pct > 0 else int(base_val)
        return round(base_val * (1.0 + total_pct), 2)

    def recalculate_spell_from_base(self, sp_item):
        for st_key, base_v in sp_item.base_stats.items():
            pct = sp_item.stat_bonuses_pct.get(st_key, 0.0)
            new_v = self.eval_stat_with_pct(sp_item.id, st_key, base_v, pct)
            setattr(sp_item, st_key, new_v)

    def apply_perk(self, perk_id, perks_db, upgrade_roll=None):
        p_data = perks_db.get(perk_id, {})
        p_type = p_data.get("type", "passive")
        if p_type != "active" or (perk_id not in self.active_perks and all(self.ability_slots)):
            return

        new_lvl = self.perks.get(perk_id, 0) + 1
        self.perks[perk_id] = new_lvl

        if p_type == "active":
            self.active_perks[perk_id] = new_lvl
            existing_spell = next((h for h in self.ability_slots if h and h.id == perk_id), None)
            if existing_spell:
                # Суммируем новые проценты с уже накопленными и пересчитываем от БАЗЫ!
                if upgrade_roll:
                    for st_k, add_pct in upgrade_roll.items():
                        existing_spell.stat_bonuses_pct[st_k] = existing_spell.stat_bonuses_pct.get(st_k, 0.0) + add_pct
                else:
                    for st_k in existing_spell.upgradable_stats[:1]:
                        existing_spell.stat_bonuses_pct[st_k] = existing_spell.stat_bonuses_pct.get(st_k, 0.0) + 0.12
                self.recalculate_spell_from_base(existing_spell)
                existing_spell.name = f"{p_data['name']} (Ур.{new_lvl})"
            else:
                s_kind = p_data.get("skill_kind", "spell")
                spell_item_data = dict(p_data)
                spell_item_data["name"] = f"{p_data['name']} (Ур.{new_lvl})"
                spell_item_data["type"] = "combat_skill" if s_kind == "combat" else "permanent_spell"
                sp_item = Item(perk_id, spell_item_data)
                budget = {"common":0,"uncommon":.12,"rare":.24,"epic":.4,"legendary":.6}[sp_item.rarity]
                for stat in sp_item.upgradable_stats:
                    sp_item.stat_bonuses_pct[stat] = budget / len(sp_item.upgradable_stats)
                self.recalculate_spell_from_base(sp_item)
                for index, slot in enumerate(self.ability_slots):
                    if slot is None:
                        self.ability_slots[index] = sp_item
                        break
        else:
            self.passive_perks[perk_id] = new_lvl
            if perk_id == "tough_skin":
                self.hp_bonus += 8
                self.hp = min(float(self.max_hp), self.hp + 10.0)
            elif perk_id == "iron_grip":
                self.perk_phys_atk += 2
            elif perk_id == "clear_mind":
                self.perk_mag_atk += 2
                self.mp_bonus += 3
                self.mp = min(float(self.max_mp), self.mp + 3.0)
            elif perk_id == "cat_step":
                self.perk_noise -= 0.18
                self.perk_dodge += 0.05
            elif perk_id == "keen_edge":
                self.perk_crit += 0.08
                self.body += 1
            elif perk_id == "stone_ribs":
                self.perk_phys_def += 3
                self.perk_mag_def += 3
            elif perk_id == "blood_hunger":
                self.perk_lifesteal += 2
            elif perk_id == "titan_blood":
                self.hp_bonus += 18
                self.hp = min(float(self.max_hp), self.hp + 18.0)
                self.perk_phys_def += 3
                self.hp_regen += 1.2

    def remove_perk(self, perk_id):
        """Completely erases an active or passive perk and all its stacks without compensation."""
        lvl = self.perks.pop(perk_id, 0)
        if lvl <= 0:
            return False
        self.active_perks.pop(perk_id, None)
        self.passive_perks.pop(perk_id, None)

        for i in range(len(self.ability_slots)):
            if self.ability_slots[i] and self.ability_slots[i].id == perk_id:
                self.ability_slots[i] = None

        if perk_id == "tough_skin":
            self.hp_bonus -= 8 * lvl
            self.hp = min(self.hp, float(self.max_hp))
        elif perk_id == "iron_grip":
            self.perk_phys_atk -= 2 * lvl
        elif perk_id == "clear_mind":
            self.perk_mag_atk -= 2 * lvl
            self.mp_bonus -= 3 * lvl
            self.mp = min(self.mp, float(self.max_mp))
        elif perk_id == "cat_step":
            self.perk_noise += 0.18 * lvl
            self.perk_dodge -= 0.05 * lvl
        elif perk_id == "keen_edge":
            self.perk_crit -= 0.08 * lvl
            self.body = max(1, self.body - lvl)
        elif perk_id == "stone_ribs":
            self.perk_phys_def -= 3 * lvl
            self.perk_mag_def -= 3 * lvl
        elif perk_id == "blood_hunger":
            self.perk_lifesteal -= 2 * lvl
        elif perk_id == "titan_blood":
            self.hp_bonus -= 18 * lvl
            self.perk_phys_def -= 3 * lvl
            self.hp_regen = max(0.0, self.hp_regen - 1.2 * lvl)
            self.hp = min(self.hp, float(self.max_hp))
        return True

    def get_comparison_item(self, hover_item):
        if not hover_item or hover_item.type != "equipment":
            return None
        slot = hover_item.slot
        if slot == "ring":
            return self.equipment["ring_1"] or self.equipment["ring_2"]
        return self.equipment.get(slot)

    def equip_item(self, item):
        slot = item.slot
        if slot == "ring":
            target_slot = "ring_1" if self.equipment["ring_1"] is None else ("ring_2" if self.equipment["ring_2"] is None else "ring_1")
        else:
            target_slot = slot

        src_pocket_idx = None
        for i in range(self.max_possible_slots):
            if self.inventory[i] is item:
                self.inventory[i] = None
                src_pocket_idx = i
                break

        old_main = self.equipment.get(target_slot)
        old_off = None

        if target_slot == "right_hand" and item.two_handed:
            old_off = self.equipment["left_hand"]
            self.equipment["left_hand"] = None
        elif target_slot == "left_hand":
            main_itm = self.equipment["right_hand"]
            if main_itm and main_itm.two_handed:
                old_off = main_itm
                self.equipment["right_hand"] = None

        self.equipment[target_slot] = item

        if old_main is not None:
            if src_pocket_idx is not None and self.inventory[src_pocket_idx] is None:
                self.inventory[src_pocket_idx] = old_main
            elif not self.add_item_to_inventory(old_main):
                self.overflow_drops.append(old_main)

        if old_off is not None:
            if not self.add_item_to_inventory(old_off):
                self.overflow_drops.append(old_off)

        return True

    def unequip_slot(self, slot_key):
        itm = self.equipment.get(slot_key)
        if itm and self.add_item_to_inventory(itm):
            self.equipment[slot_key] = None
            return True
        return False

    def update_illumination(self, braziers, room_lights, objects, visible_tiles):
        light_val = 0.85 if self.has_lit_torch else 0.14
        if self._sum_equip("vision_bonus") >= 15:
            light_val = max(light_val, 0.35)
        for br in braziers:
            if (br["x"], br["y"]) in visible_tiles:
                d = math.hypot(self.x - (br["x"] + 0.5), self.y - (br["y"] + 0.5))
                if d < 5.5:
                    light_val += max(0.0, (5.5 - d) / 5.5) * 0.75
        for rl in room_lights:
            if (rl["x"], rl["y"]) in visible_tiles:
                r_tiles = rl["radius"] / 16.0
                d = math.hypot(self.x - (rl["x"] + 0.5), self.y - (rl["y"] + 0.5))
                if d < r_tiles:
                    light_val += max(0.0, (r_tiles - d) / r_tiles) * 0.85
        for obj in objects:
            if obj.kind in ("campfire", "fireplace") and (obj.x, obj.y) in visible_tiles:
                d = math.hypot(self.x - (obj.x + 0.5), self.y - (obj.y + 0.5))
                if d < 6.5:
                    light_val += max(0.0, (6.5 - d) / 6.5) * 0.90
        self.illumination = min(1.0, light_val)

    def move_realtime(self, dx, dy, dt, dungeon):
        if dx == 0 and dy == 0:
            self.is_moving = False
            return False
        if abs(dx) > 0.05:
            self.facing = 1 if dx > 0 else -1
        start_x, start_y = self.x, self.y
        length = math.hypot(dx, dy)
        nx, ny = dx / length, dy / length

        cur_tile = dungeon.grid[int(self.y)][int(self.x)]
        spd_mult = 0.75 if cur_tile in (2, SHALLOW_WATER) else 1.0
        if self.quirk == "nyctophobe" and not self.has_lit_torch:
            spd_mult *= 1.15
        if self.throw_slowdown_timer > 0.0:
            spd_mult *= 0.50
        if self.evade_timer > 0:
            spd_mult *= 1.3
        step = PLAYER_BASE_SPEED * spd_mult * dt

        rad = 0.28
        target_x = self.x + nx * step
        if not (
            dungeon.is_blocking_move(int(target_x - rad), int(self.y - rad))
            or dungeon.is_blocking_move(int(target_x + rad), int(self.y - rad))
            or dungeon.is_blocking_move(int(target_x - rad), int(self.y + rad))
            or dungeon.is_blocking_move(int(target_x + rad), int(self.y + rad))
        ):
            self.x = target_x

        target_y = self.y + ny * step
        if not (
            dungeon.is_blocking_move(int(self.x - rad), int(target_y - rad))
            or dungeon.is_blocking_move(int(self.x + rad), int(target_y - rad))
            or dungeon.is_blocking_move(int(self.x - rad), int(target_y + rad))
            or dungeon.is_blocking_move(int(self.x + rad), int(target_y + rad))
        ):
            self.y = target_y

        self.is_moving = (self.x, self.y) != (start_x, start_y)
        return self.is_moving

    def add_item_to_inventory(self, item):
        placed = False
        for i in range(self.unlocked_slots):
            if self.inventory[i] is None:
                self.inventory[i] = item
                placed = True
                break
        if not placed:
            return False

        # Only consumable items jump into the 4 quickbar slots [1..4]!
        if item.type in ("consumable", "consumable_spell", "consumable_eraser"):
            if item not in self.hotbar:
                for h in range(4):
                    if self.hotbar[h] is None:
                        self.hotbar[h] = item
                        break
        return True

    def remove_item_from_pockets(self, item):
        for i in range(self.max_possible_slots):
            if self.inventory[i] is item:
                self.inventory[i] = None
                break

    def remove_item_everywhere(self, item):
        self.remove_item_from_pockets(item)
        for k, v in self.equipment.items():
            if v is item:
                self.equipment[k] = None
        for h in range(len(self.hotbar)):
            if self.hotbar[h] is item:
                self.hotbar[h] = None
        for a in range(len(self.ability_slots)):
            if self.ability_slots[a] is item:
                self.ability_slots[a] = None

    def melee_damage_range(self):
        weap = self.equipment.get("right_hand")
        w_min = getattr(weap, "dmg_min", 1) if weap else 1
        w_max = getattr(weap, "dmg_max", 3) if weap else 3
        # Двуручники получают повышенную отдачу от вложенной Силы!
        stat_scale = 1.35 if (weap and weap.two_handed) else 1.0
        stat_add = int(round(self.phys_attack * stat_scale))
        return w_min + stat_add, w_max + stat_add

    def roll_melee_damage(self):
        weap = self.equipment.get("right_hand")
        base = random.randint(*self.melee_damage_range())
        is_crit = random.random() < self.crit_chance
        crit_mult = 1.75 + (getattr(weap, "crit_bonus", 0.0) * 1.5)
        if is_crit:
            return int(base * crit_mult), True
        return base, False

    def trigger_bump(self, dx, dy):
        if abs(dx) > 0.05:
            self.facing = 1 if dx > 0 else -1
        self.bump_x = dx * 0.35
        self.bump_y = dy * 0.35

    def trigger_lunge(self, nx, ny, dist):
        if abs(nx) > 0.05:
            self.facing = 1 if nx > 0 else -1
        # Начальный импульс расходуется с затуханием 14.0*dt и плавно провозит ровно на dist тайлов
        self.lunge_vx = nx * dist * 11.5
        self.lunge_vy = ny * dist * 11.5

    def update_lunge(self, dt, dungeon):
        if math.hypot(self.lunge_vx, self.lunge_vy) <= 0.12:
            self.lunge_vx = 0.0
            self.lunge_vy = 0.0
            return
        rad = 0.28
        # Разбиваем смещение на микрошаги со строгой проверкой всех 4 углов хитбокса
        steps = 2
        sub_dt = dt / steps
        for _ in range(steps):
            tx = self.x + self.lunge_vx * sub_dt
            if not (
                dungeon.is_blocking_move(int(tx - rad), int(self.y - rad))
                or dungeon.is_blocking_move(int(tx + rad), int(self.y - rad))
                or dungeon.is_blocking_move(int(tx - rad), int(self.y + rad))
                or dungeon.is_blocking_move(int(tx + rad), int(self.y + rad))
            ):
                self.x = tx
            else:
                self.lunge_vx = 0.0

            ty = self.y + self.lunge_vy * sub_dt
            if not (
                dungeon.is_blocking_move(int(self.x - rad), int(ty - rad))
                or dungeon.is_blocking_move(int(self.x + rad), int(ty - rad))
                or dungeon.is_blocking_move(int(self.x - rad), int(ty + rad))
                or dungeon.is_blocking_move(int(self.x + rad), int(ty + rad))
            ):
                self.y = ty
            else:
                self.lunge_vy = 0.0

        decay = max(0.0, 1.0 - 14.0 * dt)
        self.lunge_vx *= decay
        self.lunge_vy *= decay

    def update_timers(self, dt):
        for name in ("guard_timer", "evade_timer", "stealth_timer"):
            setattr(self, name, max(0, getattr(self,name,0)-dt))
        self.anim_timer += dt
        fps = 8.0 if self.is_moving else 2.0
        if self.anim_timer >= 1.0 / fps:
            self.anim_timer = 0.0
            self.anim_frame = (self.anim_frame + 1) % 4
        self.attack_cd = max(0.0, self.attack_cd - dt)
        self.step_sound_cd = max(0.0, self.step_sound_cd - dt)
        self.throw_slowdown_timer = max(0.0, self.throw_slowdown_timer - dt)
        self.shine_timer = max(0.0, self.shine_timer - dt)
        for k in list(self.cooldowns.keys()):
            self.cooldowns[k] = max(0.0, self.cooldowns[k] - dt)
            if self.cooldowns[k] <= 0.0:
                del self.cooldowns[k]
        if self.ignite_timer > 0.0:
            self.ignite_timer = max(0.0, self.ignite_timer - dt)
        if self.rejuv_timer > 0.0 and self.hp > 0:
            step_t = min(dt, self.rejuv_timer)
            self.rejuv_timer = max(0.0, self.rejuv_timer - dt)
            self.hp = min(float(self.max_hp), self.hp + self.rejuv_rate * step_t)
        if self.hp_regen > 0.0 and self.hp > 0:
            self.hp = min(float(self.max_hp), self.hp + self.hp_regen * dt)
        self.bump_x *= max(0.0, 1.0 - 14.0 * dt)
        self.bump_y *= max(0.0, 1.0 - 14.0 * dt)
        return None
