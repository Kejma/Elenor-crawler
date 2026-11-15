import math
import random
from config import (
    PLAYER_BASE_SPEED, TORCH_BASE_RADIUS, DARK_VISION_RADIUS,
    TORCH_BURN_RATE, RARITY_COLORS
)


class Item:
    def __init__(self, item_id, data):
        self.id = item_id
        self.name = data["name"]
        self.type = data["type"]
        self.slot = data.get("slot", None)
        self.two_handed = data.get("two_handed", False)
        self.weap_style = data.get("weap_style", "fist")
        self.atk_cd = float(data.get("atk_cd", 0.36))
        self.reach = float(data.get("reach", 1.55))
        self.arc_deg = float(data.get("arc_deg", 55.0))
        self.max_targets = int(data.get("max_targets", 99 if data.get("cleave", False) else 1))
        self.armor_pierce = int(data.get("armor_pierce", 0))
        self.cleave = data.get("cleave", False) or (self.max_targets > 1)
        self.life_steal = data.get("life_steal", 0)
        self.cooldown = float(data.get("cooldown", 1.5))
        self.skill_kind = data.get("skill_kind", "spell")
        self.god = data.get("god", "")
        self.windup = float(data.get("windup", 0.0))
        self.knockback = float(data.get("knockback", 0.35))
        self.cast_type = data.get("cast_type", "projectile")
        self.proj_speed = float(data.get("proj_speed", 9.2))
        self.aoe_radius = float(data.get("aoe_radius", 2.0))
        self.duration = float(data.get("duration", 0.0))
        self.bounces = int(data.get("bounces", 1))
        self.status = data.get("status", None)
        self.status_dur = float(data.get("status_dur", 0.0))
        self.upgradable_stats = list(data.get("upgradable_stats", ["power", "cooldown"]))
        self.base_stats = {
            "power": float(data.get("power", 0)),
            "cooldown": float(data.get("cooldown", 1.5)),
            "duration": float(data.get("duration", 0.0)),
            "status_dur": float(data.get("status_dur", 0.0)),
            "aoe_radius": float(data.get("aoe_radius", 2.0)),
            "bounces": float(data.get("bounces", 1)),
        }
        self.stat_bonuses_pct = {k: 0.0 for k in self.base_stats}

        self.rarity = data.get("rarity", "common")
        self.rarity_color = RARITY_COLORS.get(self.rarity, (215, 215, 220))
        self.icon = data["icon"]
        raw_desc = data.get("desc", "")
        self.desc = random.choice(raw_desc) if isinstance(raw_desc, list) and raw_desc else str(raw_desc)
        self.copper_value = int(data.get("copper_value", 0))

        self.is_torch = data.get("is_torch", False)
        self.max_fuel = float(data.get("max_fuel", 100.0))
        self.fuel = self.max_fuel

        self.power = data.get("power", 0)
        self.heal_hp = int(data.get("heal_hp", self.power if item_id.startswith("potion_hp") else 0))
        self.mp_cost = data.get("mp_cost", 0)
        self.phys_bonus = data.get("phys_bonus", 0)
        self.mag_bonus = data.get("mag_bonus", 0)
        self.phys_def = data.get("phys_def", 0)
        self.mag_def = data.get("mag_def", 0)
        self.noise_mod = data.get("noise_mod", 0.0)
        self.vision_bonus = data.get("vision_bonus", 0)
        self.mp_regen = float(data.get("mp_regen", 0.0))
        self.armor_class = data.get("armor_class", "none")

        self.active_spell = data.get("active_spell", None)
        self.color = tuple(data.get("color", [110, 225, 255]))
        self.slots = data.get("slots", 2)


class Particle:
    def __init__(self, wx, wy, vx, vy, color, size=2.5, life=0.45):
        self.wx = wx
        self.wy = wy
        self.vx = vx
        self.vy = vy
        self.color = color
        self.size = size
        self.life = life
        self.max_life = life

    def update(self, dt):
        self.wx += self.vx * dt
        self.wy += self.vy * dt
        self.life -= dt
        return self.life > 0


class Projectile:
    def __init__(self, wx, wy, dir_x, dir_y, speed, mag_dmg, color, from_player=True, status=None, status_dur=0.0, knockback=0.0, visual_kind="orb", emits_light=True):
        self.wx = wx
        self.wy = wy
        self.vx = dir_x * speed
        self.vy = dir_y * speed
        self.mag_dmg = mag_dmg
        self.color = color
        self.from_player = from_player
        self.status = status
        self.status_dur = status_dur
        self.knockback = knockback
        self.visual_kind = visual_kind
        self.emits_light = emits_light
        self.angle = math.atan2(dir_y, dir_x)
        self.life = 4.5
        self.spawn_timer = 0.0

    def update(self, dt, dungeon, particles):
        self.wx += self.vx * dt
        self.wy += self.vy * dt
        self.life -= dt
        self.spawn_timer += dt

        if self.visual_kind == "spinning_dagger":
            self.angle += 24.0 * dt
        elif self.spawn_timer >= 0.025:
            self.spawn_timer = 0.0
            for _ in range(2):
                ang = random.uniform(0, 6.28)
                spd = random.uniform(0.4, 1.6)
                particles.append(Particle(
                    self.wx, self.wy,
                    math.cos(ang) * spd - self.vx * 0.15,
                    math.sin(ang) * spd - self.vy * 0.15,
                    self.color, size=random.uniform(2.0, 3.5), life=random.uniform(0.2, 0.4)
                ))

        tx, ty = int(self.wx), int(self.wy)
        if dungeon.is_blocking_move(tx, ty):
            spark_col = (200, 205, 215) if self.visual_kind == "spinning_dagger" else self.color
            spark_cnt = 5 if self.visual_kind == "spinning_dagger" else 10
            for _ in range(spark_cnt):
                ang = random.uniform(0, 6.28)
                spd = random.uniform(1.0, 3.2)
                particles.append(Particle(self.wx, self.wy, math.cos(ang) * spd, math.sin(ang) * spd, spark_col, 2.5, 0.25))
            return False

        return self.life > 0


class Player:
    def __init__(self, x, y, adj_key, adj_data, noun_key, noun_data, items_db, appearance=None):
        self.x = float(x) + 0.5
        self.y = float(y) + 0.5
        self.bump_x = 0.0
        self.bump_y = 0.0
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
        self.active_perks = {}       # perk_id -> level (max 2 keys)
        self.passive_perks = {}      # perk_id -> level (max 5 keys)
        self.perk_timers = {"storm_aura": 1.5}
        self.cooldowns = {}          # item_or_perk_id -> remaining cooldown seconds
        self.pending_action = None   # Holds windup action dict before strike/cast fires!
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
        self.ability_slots = [None, None]
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
        return min(0.65, self.cunning * 0.05 + self.perk_crit)

    def gain_xp(self, amount):
        self.xp += amount
        leveled = False
        while self.xp >= self.max_xp:
            self.xp -= self.max_xp
            self.level += 1
            self.max_xp = int(self.max_xp * 1.55)
            self.pending_perk_rolls += 1
            self.hp = min(float(self.max_hp), self.hp + 6.0)
            self.mp = min(float(self.max_mp), self.mp + 4.0)
            leveled = True
        return leveled

    @property
    def mp_on_hit(self):
        """Мана, выбиваемая каждым попаданием в ближнем бою (Комбо А)."""
        gain = 1.0 + self.perk_mp_regen
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
        if branch in self.action_affinity:
            self.action_affinity[branch] += amount

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
            if itm.armor_class == "plate" or itm.two_handed or itm.weap_style in ("mace", "cleaver", "axe"):
                scores["body"] += 2.5
            if itm.armor_class == "leather" or itm.weap_style in ("dagger", "spear") or itm.noise_mod < 0:
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
            tag = perk_tags.get(pid, "body")
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
                self.recalculate_spell_from_base(sp_item)
                if self.ability_slots[0] is None:
                    self.ability_slots[0] = sp_item
                elif self.ability_slots[1] is None:
                    self.ability_slots[1] = sp_item
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

        for i in range(2):
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
        self.is_moving = True
        length = math.hypot(dx, dy)
        nx, ny = dx / length, dy / length

        cur_tile = dungeon.grid[int(self.y)][int(self.x)]
        spd_mult = 0.75 if cur_tile == 2 else 1.0
        if self.quirk == "nyctophobe" and not self.has_lit_torch:
            spd_mult *= 1.15
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

        return True

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

    def roll_melee_damage(self):
        base = random.randint(1, 3) + self.phys_attack
        is_crit = random.random() < self.crit_chance
        if is_crit:
            return int(base * 1.75), True
        return base, False

    def trigger_bump(self, dx, dy):
        if abs(dx) > 0.05:
            self.facing = 1 if dx > 0 else -1
        self.bump_x = dx * 0.35
        self.bump_y = dy * 0.35

    def update_timers(self, dt):
        self.anim_timer += dt
        fps = 8.0 if self.is_moving else 2.0
        if self.anim_timer >= 1.0 / fps:
            self.anim_timer = 0.0
            self.anim_frame = (self.anim_frame + 1) % 4
        self.attack_cd = max(0.0, self.attack_cd - dt)
        self.step_sound_cd = max(0.0, self.step_sound_cd - dt)
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


class Enemy:
    def __init__(self, x, y, kind="rat", state="patrolling", chat_lines=None):
        from mission_rats import MOB_PROFILES
        self.x = float(x) + 0.5
        self.y = float(y) + 0.5
        self.bump_x = 0.0
        self.bump_y = 0.0
        self.kind = kind
        self.state = state

        prof = MOB_PROFILES.get(kind, MOB_PROFILES["rat"])
        self.sprite = prof["sprite"]
        self.max_hp = prof["hp"]
        self.hp = self.max_hp
        self.speed = prof["speed"]
        self.dmg_min = prof["dmg_min"]
        self.dmg_max = prof["dmg_max"]
        self.phys_def = prof["phys_def"]
        self.mag_def = prof["mag_def"]
        self.detect_range = prof["detect_range"]
        self.perception = prof["perception"]
        self.is_ranged = prof["is_ranged"]
        self.proj_color = prof.get("proj_color", (215, 75, 255))
        self.is_boss = prof.get("is_boss", False)
        self.size_tiles = prof.get("size_tiles", 2 if self.is_boss else 1)
        self.xp_value = prof["xp"]

        self.awareness = 0.0
        self.facing = -1
        self.alert_bang_timer = 0.0
        self.attack_cd = 0.0
        self.cast_windup_timer = 0.0
        self.cast_windup_max = 0.65
        self.pending_pentagram = False
        self.patrol_dir = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
        self.patrol_timer = random.uniform(1.2, 2.8)

        self.chat_lines = chat_lines or []
        self.chat_partner = None
        self.chat_timer = random.uniform(1.0, 3.0)
        self.chat_index = 0
        self.current_speech = None

        self.solo_lines = []
        self.solo_timer = random.uniform(1.8, 4.0)
        self.solo_show_timer = 0.0

        self.path = []
        self.path_timer = 0.0
        self.kb_vx = 0.0
        self.kb_vy = 0.0
        self.poison_timer = 0.0
        self.poison_tick = 0.0
        self.poison_dmg = 2
        self.burn_timer = 0.0
        self.burn_tick = 0.0
        self.burn_dmg = 3
        self.slow_timer = 0.0
        self.stun_timer = 0.0
        self.root_timer = 0.0
        self.chill_after_root = 0.0
        self.glow_timer = 0.0
        self.glow_color = (255, 255, 255)
        self.hit_flash_timer = 0.0
        self.hit_flash_crit = False
        self.last_lit_pos = None

    def apply_balance_profile(self, profile, floor_num=1):
        if not profile:
            return
        fl_mult_hp = 1.0 + (floor_num - 1) * profile.get("floor_hp_growth", 0.22)
        fl_mult_dmg = 1.0 + (floor_num - 1) * profile.get("floor_dmg_growth", 0.18)
        self.max_hp = max(1, int(round(profile["hp"] * fl_mult_hp)))
        self.hp = self.max_hp
        self.phys_def = int(round(profile["phys_def"] + (floor_num - 1) * 0.5))
        self.mag_def = int(round(profile["mag_def"] + (floor_num - 1) * 0.5))
        self.dmg_min = max(1, int(round(profile["dmg_min"] * fl_mult_dmg)))
        self.dmg_max = max(self.dmg_min, int(round(profile["dmg_max"] * fl_mult_dmg)))
        self.xp_value = int(round(profile["xp"] * (1.0 + (floor_num - 1) * 0.20)))

    def trigger_bump(self, dx, dy):
        self.bump_x = dx * 0.35
        self.bump_y = dy * 0.35

    def apply_knockback(self, dir_x, dir_y, force):
        if force <= 0.0:
            return
        resist = 0.45 if (self.kind == "brute" or self.is_boss) else 1.0
        self.kb_vx = dir_x * force * 6.5 * resist
        self.kb_vy = dir_y * force * 6.5 * resist

    def apply_status(self, status_name, duration, add_popup, dmg_val=3):
        if not status_name or duration <= 0.0:
            return
        if status_name == "poison":
            self.poison_timer = max(self.poison_timer, duration)
            self.poison_dmg = max(1, int(math.floor(dmg_val)))
        elif status_name == "burn":
            self.burn_timer = max(self.burn_timer, duration)
            self.burn_dmg = max(1, int(math.floor(dmg_val)))
            self.glow_timer = max(self.glow_timer, duration)
            self.glow_color = (255, 115, 35)
        elif status_name == "slow":
            self.slow_timer = max(self.slow_timer, duration)
        elif status_name == "stun":
            self.stun_timer = max(self.stun_timer, duration)
        elif status_name == "root":
            self.root_timer = max(self.root_timer, duration)

    def alert_to_combat(self, sfx, add_popup):
        if self.state != "combat":
            self.state = "combat"
            self.awareness = 100.0
            self.alert_bang_timer = 0.38
            self.current_speech = None
            self.path_timer = 0.0
            sfx.play("alert")
            if self.chat_partner and self.chat_partner.state != "combat":
                self.chat_partner.state = "combat"
                self.chat_partner.awareness = 100.0
                self.chat_partner.alert_bang_timer = 0.38
                self.chat_partner.current_speech = None
                self.chat_partner.path_timer = 0.0

    def update_ai(self, dt, player, dungeon, all_mobs, projectiles, sfx, add_popup, on_player_hit):
        self.bump_x *= max(0.0, 1.0 - 14.0 * dt)
        self.bump_y *= max(0.0, 1.0 - 14.0 * dt)
        self.attack_cd = max(0.0, self.attack_cd - dt)
        self.path_timer = max(0.0, self.path_timer - dt)
        self.alert_bang_timer = max(0.0, self.alert_bang_timer - dt)

        # 1. Process Smooth Knockback Displacement
        if math.hypot(self.kb_vx, self.kb_vy) > 0.15:
            rad = 0.25
            ktx = self.x + self.kb_vx * dt
            if not (dungeon.is_blocking_move(int(ktx - rad), int(self.y - rad)) or dungeon.is_blocking_move(int(ktx + rad), int(self.y + rad))):
                self.x = ktx
            kty = self.y + self.kb_vy * dt
            if not (dungeon.is_blocking_move(int(self.x - rad), int(kty - rad)) or dungeon.is_blocking_move(int(self.x + rad), int(kty + rad))):
                self.y = kty
            self.kb_vx *= max(0.0, 1.0 - 10.0 * dt)
            self.kb_vy *= max(0.0, 1.0 - 10.0 * dt)

        # 2. Process Status Effects
        self.glow_timer = max(0.0, self.glow_timer - dt)
        self.hit_flash_timer = max(0.0, self.hit_flash_timer - dt)
        if self.poison_timer > 0.0:
            self.poison_timer = max(0.0, self.poison_timer - dt)
            self.poison_tick += dt
            if self.poison_tick >= 0.65:
                self.poison_tick = 0.0
                self.hp -= self.poison_dmg
                add_popup(self.x, self.y, f"-{int(self.poison_dmg)}", (110, 245, 95))

        if self.burn_timer > 0.0:
            self.burn_timer = max(0.0, self.burn_timer - dt)
            self.burn_tick += dt
            if self.burn_tick >= 0.55:
                self.burn_tick = 0.0
                self.hp -= self.burn_dmg
                add_popup(self.x, self.y, f"-{int(self.burn_dmg)}", (255, 135, 45))

        if self.slow_timer > 0.0:
            self.slow_timer = max(0.0, self.slow_timer - dt)
        if self.root_timer > 0.0:
            self.root_timer = max(0.0, self.root_timer - dt)
            if self.root_timer <= 0.0 and self.chill_after_root > 0.0:
                self.slow_timer = max(self.slow_timer, self.chill_after_root)
                self.chill_after_root = 0.0
        if self.stun_timer > 0.0:
            self.stun_timer = max(0.0, self.stun_timer - dt)
            self.cast_windup_timer = 0.0
            return

        dx = player.x - self.x
        dy = player.y - self.y
        dist = math.hypot(dx, dy)

        if self.state != "combat":
            state_mult = {
                "sleeping": 0.28,
                "eating": 0.60,
                "chatting": 0.70,
                "patrolling": 1.15
            }.get(self.state, 1.0)

            p_tile = dungeon.grid[int(player.y)][int(player.x)]
            surface_noise = 1.5 if p_tile == 2 else (0.55 if p_tile == 3 else 1.0)

            eff_range = self.detect_range * (0.45 + player.illumination * 0.85) * state_mult
            can_sense = False

            hear_range = 2.8 * player.noise_factor * surface_noise
            if dist <= hear_range:
                can_sense = True
            elif dist <= eff_range and dungeon.has_line_of_sight(self.x, self.y, player.x, player.y, eff_range):
                can_sense = True

            if can_sense:
                prox = max(0.25, (max(eff_range, hear_range) - dist) / max(1.0, eff_range))
                gain = (62.0 * self.perception * state_mult * (0.40 + player.illumination * 1.2) * player.noise_factor * surface_noise * (prox ** 1.1))
                if dist < 1.85:
                    gain += 130.0
                self.awareness = min(100.0, self.awareness + gain * dt)
                if self.awareness >= 100.0:
                    self.alert_to_combat(sfx, add_popup)
            else:
                self.awareness = max(0.0, self.awareness - 12.0 * dt)

            if self.state == "chatting" and self.chat_lines:
                self.chat_timer -= dt
                if self.chat_timer <= 0.0:
                    if self.chat_index < len(self.chat_lines):
                        self.chat_timer = 3.4
                        line = self.chat_lines[self.chat_index]
                        if self.chat_index % 2 == 0:
                            self.current_speech = line
                            if self.chat_partner:
                                self.chat_partner.current_speech = None
                        else:
                            self.current_speech = None
                            if self.chat_partner:
                                self.chat_partner.current_speech = line
                        self.chat_index += 1
                        if dist <= 7.5:
                            sfx.play("mob_talk")
                    else:
                        self.current_speech = None
                        self.state = "patrolling"
                        if self.chat_partner and self.chat_partner.state == "chatting":
                            self.chat_partner.current_speech = None
                            self.chat_partner.state = "eating"

            if self.state != "chatting" and self.solo_lines:
                if self.solo_show_timer > 0.0:
                    self.solo_show_timer -= dt
                    if self.solo_show_timer <= 0.0:
                        self.current_speech = None
                else:
                    self.solo_timer -= dt
                    if self.solo_timer <= 0.0:
                        self.solo_timer = random.uniform(4.5, 8.0)
                        self.solo_show_timer = 4.0
                        self.current_speech = random.choice(self.solo_lines)
                        if dist <= 8.5:
                            sfx.play("mob_talk")

            if self.state == "patrolling":
                self.patrol_timer -= dt
                if self.patrol_timer <= 0.0:
                    self.patrol_dir = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1), (0, 0)])
                    self.patrol_timer = random.uniform(1.5, 3.2)
                if self.patrol_dir != (0, 0):
                    if self.patrol_dir[0] != 0:
                        self.facing = 1 if self.patrol_dir[0] > 0 else -1
                    old_x, old_y = self.x, self.y
                    self._step_with_collision(self.patrol_dir[0], self.patrol_dir[1], dt * 0.45, dungeon, all_mobs)
                    if math.hypot(self.x - old_x, self.y - old_y) < 0.001:
                        self.patrol_dir = (-self.patrol_dir[0], -self.patrol_dir[1])
            return

        # --- COMBAT AI WITH FULL A* PATHFINDING, PENTAGRAM CASTING & BOSS CRIES ---
        if self.is_boss and self.solo_lines:
            if self.solo_show_timer > 0.0:
                self.solo_show_timer -= dt
                if self.solo_show_timer <= 0.0:
                    self.current_speech = None
            else:
                self.solo_timer -= dt
                if self.solo_timer <= 0.0:
                    self.solo_timer = random.uniform(5.0, 8.5)
                    self.solo_show_timer = 3.2
                    self.current_speech = random.choice(self.solo_lines)
                    sfx.play("mob_talk")

        if abs(dx) > 0.08:
            self.facing = 1 if dx > 0 else -1

        # 1. If currently channeling a dark spell (windup before pentagram appears!)
        if self.cast_windup_timer > 0.0:
            self.cast_windup_timer -= dt
            if self.cast_windup_timer <= 0.0:
                self.cast_windup_timer = 0.0
                self.pending_pentagram = True
                if dist > 0.001:
                    self.trigger_bump((dx / dist) * 0.35, (dy / dist) * 0.35)
            return

        if dist < 0.001:
            return
        nx, ny = dx / dist, dy / dist

        if self.is_ranged:
            has_los = dungeon.has_line_of_sight(self.x, self.y, player.x, player.y, 9.5)
            if dist > 5.8 or not has_los:
                self._follow_astar_path(player.x, player.y, dt, dungeon, all_mobs)
            elif dist < 2.3 and not self.is_boss:
                self._step_with_collision(-nx, -ny, dt, dungeon, all_mobs)
            elif self.is_boss and dist > 1.35:
                self._follow_astar_path(player.x, player.y, dt, dungeon, all_mobs)

            boss_reach = 1.75 if self.size_tiles >= 2 else 1.25
            if self.is_boss and dist <= boss_reach and self.attack_cd <= 0.0:
                self.attack_cd = 0.95
                self.trigger_bump(nx, ny)
                on_player_hit(random.randint(self.dmg_min, self.dmg_max), is_magic=False)
            elif has_los and dist <= 8.2 and self.attack_cd <= 0.0:
                if self.kind in ("rat_cultist", "rat_king"):
                    self.cast_windup_max = 0.58 if self.is_boss else 0.68
                    self.cast_windup_timer = self.cast_windup_max
                    self.attack_cd = 1.85 if self.is_boss else 2.55
                    sfx.play("spell_windup")
                else:
                    self.attack_cd = 1.55
                    self.trigger_bump(nx * 0.5, ny * 0.5)
                    sfx.play("magic")
                    dmg = random.randint(self.dmg_min, self.dmg_max)
                    projectiles.append(Projectile(
                        self.x, self.y, nx, ny,
                        speed=6.5, mag_dmg=dmg,
                        color=self.proj_color, from_player=False
                    ))
        else:
            if dist > 1.05:
                self._follow_astar_path(player.x, player.y, dt, dungeon, all_mobs)
            elif self.attack_cd <= 0.0:
                self.attack_cd = 0.80 if self.kind in ("rat", "wolf") else (1.05 if self.kind == "skeleton" else 1.35)
                self.trigger_bump(nx, ny)
                raw_phys = random.randint(self.dmg_min, self.dmg_max)
                on_player_hit(raw_phys, is_magic=False)

    def _follow_astar_path(self, target_x, target_y, dt, dungeon, all_mobs):
        if self.path_timer <= 0.0 or not self.path:
            self.path_timer = random.uniform(0.24, 0.36)
            self.path = dungeon.find_path((int(self.x), int(self.y)), (int(target_x), int(target_y)))

        while self.path and math.hypot(self.path[0][0] - self.x, self.path[0][1] - self.y) < 0.22:
            self.path.pop(0)

        if self.path:
            wx, wy = self.path[0]
            dx, dy = wx - self.x, wy - self.y
        else:
            dx, dy = target_x - self.x, target_y - self.y

        d = math.hypot(dx, dy)
        if d > 0.001:
            self._step_with_collision(dx / d, dy / d, dt, dungeon, all_mobs)

    def _step_with_collision(self, dir_x, dir_y, dt, dungeon, all_mobs):
        if abs(dir_x) > 0.15:
            self.facing = 1 if dir_x > 0 else -1
        sep_x, sep_y = 0.0, 0.0
        for other in all_mobs:
            if other is not self:
                odx = self.x - other.x
                ody = self.y - other.y
                od = math.hypot(odx, ody)
                if 0.001 < od < 0.65:
                    push = (0.65 - od) / 0.65
                    sep_x += (odx / od) * push * 0.8
                    sep_y += (ody / od) * push * 0.8

        vx = dir_x + sep_x
        vy = dir_y + sep_y
        v_len = math.hypot(vx, vy)
        if v_len > 0.001:
            vx /= v_len
            vy /= v_len

        if self.root_timer > 0.0:
            return
        spd_mult = 0.45 if self.slow_timer > 0.0 else 1.0
        step = self.speed * spd_mult * dt
        rad = 0.25

        moved_any = False
        tx = self.x + vx * step
        if not (
            dungeon.is_blocking_move(int(tx - rad), int(self.y - rad))
            or dungeon.is_blocking_move(int(tx + rad), int(self.y - rad))
            or dungeon.is_blocking_move(int(tx - rad), int(self.y + rad))
            or dungeon.is_blocking_move(int(tx + rad), int(self.y + rad))
        ):
            self.x = tx
            moved_any = True

        ty = self.y + vy * step
        if not (
            dungeon.is_blocking_move(int(self.x - rad), int(ty - rad))
            or dungeon.is_blocking_move(int(self.x + rad), int(ty - rad))
            or dungeon.is_blocking_move(int(self.x - rad), int(ty + rad))
            or dungeon.is_blocking_move(int(self.x + rad), int(ty + rad))
        ):
            self.y = ty
            moved_any = True

        if not moved_any:
            cx, cy = int(self.x) + 0.5, int(self.y) + 0.5
            self.x += (cx - self.x) * min(1.0, 8.0 * dt)
            self.y += (cy - self.y) * min(1.0, 8.0 * dt)


class Interactable:
    def __init__(self, x, y, kind, item=None):
        self.x = x
        self.y = y
        self.kind = kind
        self.item = item
        self.used = False
        self.talk_index = 0
        self.speech_text = None
        self.speech_timer = 0.0


class FloatingPopup:
    def __init__(self, world_x, world_y, text, color, icon=None, big=False):
        self.wx = world_x + random.uniform(-0.15, 0.15)
        self.wy = world_y - 0.35
        self.text = text
        self.color = color
        self.icon = icon
        self.big = big
        self.timer = 0.0
        self.duration = 1.05 if big else 0.90

    def update(self, dt):
        self.timer += dt
        self.wy -= 0.9 * dt
        return self.timer < self.duration