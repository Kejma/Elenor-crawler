import random
from elenor.config import RARITY_COLORS


def _scale_int_stat(base, tier_idx):
    if base <= 0 or tier_idx <= 0:
        return int(base)
    mult = (1.0, 1.35, 1.75, 2.20, 2.75)[tier_idx]
    val = int(round(base * mult))
    if val <= base:
        val = base + (1 if tier_idx <= 2 else 2)
    return val


class Item:
    RARITY_ORDER = ("common", "uncommon", "rare", "epic", "legendary")
    RARITY_ROMAN = ("", " [II]", " [III]", " [IV]", " [V]")

    def __init__(self, item_id, data, rarity_override=None):
        self.branch = data.get("branch", "mind")
        self.shape = data.get("shape", "target")
        self.id = item_id
        self.base_name = data["name"]
        self.type = data["type"]
        self.slot = data.get("slot", None)
        self.is_torch = data.get("is_torch", False)
        self.two_handed = data.get("two_handed", False)
        self.weap_style = data.get("weap_style", "fist")

        is_weapon = (self.type == "equipment" and self.slot == "right_hand" and not self.is_torch)
        is_gear = (self.type == "equipment" and self.slot != "right_hand" and not self.is_torch)

        if rarity_override in self.RARITY_ORDER:
            self.rarity = rarity_override
        else:
            self.rarity = data.get("rarity", "common")
        if self.rarity not in self.RARITY_ORDER:
            self.rarity = "common"

        self.tier_idx = self.RARITY_ORDER.index(self.rarity)
        self.rarity_color = RARITY_COLORS.get(self.rarity, (215, 215, 220))
        self.name = (
            f"{self.base_name}{self.RARITY_ROMAN[self.tier_idx]}"
            if (is_weapon or is_gear) else self.base_name
        )

        base_cd = float(data.get("atk_cd", 0.36))
        self.atk_cd = round(max(0.16, base_cd * (1.0 - 0.04 * self.tier_idx)), 2) if is_weapon else base_cd
        self.reach = float(data.get("reach", 1.55))
        self.arc_deg = float(data.get("arc_deg", 55.0))
        self.max_targets = int(data.get("max_targets", 99 if data.get("cleave", False) else 1))

        base_ap = int(data.get("armor_pierce", 0))
        ap_bonus = (2 if self.tier_idx == 4 else (1 if self.tier_idx >= 2 else 0)) if is_weapon else 0
        self.armor_pierce = base_ap + ap_bonus
        self.cleave = data.get("cleave", False) or (self.max_targets > 1)

        base_ls = int(data.get("life_steal", 0))
        self.life_steal = (
            base_ls + (2 if self.tier_idx == 4 else (1 if self.tier_idx >= 2 else 0))
            if ((is_weapon or is_gear) and base_ls > 0) else base_ls
        )

        base_crit = float(data.get("crit_bonus", 0.0))
        if is_weapon:
            self.crit_bonus = round(base_crit + 0.02 * self.tier_idx, 3)
        elif is_gear and base_crit > 0:
            self.crit_bonus = round(base_crit * (1.0 + 0.35 * self.tier_idx), 3)
        else:
            self.crit_bonus = base_crit

        base_bs = float(data.get("backstab_bonus", 0.0))
        self.backstab_bonus = round(base_bs + (0.25 * self.tier_idx if (is_weapon and base_bs > 0) else 0.0), 2)

        self.lunge_dist = float(data.get("lunge_dist", 0.0))
        self.sweet_spot = bool(data.get("sweet_spot", False))
        self.close_penalty = bool(data.get("close_penalty", False))
        self.hook_pull = bool(data.get("hook_pull", False))

        base_shatter = int(data.get("shatter_armor", 0))
        self.shatter_armor = (base_shatter + (1 if self.tier_idx >= 3 else 0)) if (is_weapon and base_shatter > 0) else base_shatter

        self.multi_hit = int(data.get("multi_hit", 1))
        self.reset_cd_on_kill = bool(data.get("reset_cd_on_kill", False))
        self.proj_visual = data.get("proj_visual", "spinning_dagger")
        self.feature_tag = data.get("feature_tag", "")

        self.cooldown = float(data.get("cooldown", 1.5))
        self.skill_kind = data.get("skill_kind", "spell")
        self.god = data.get("god", "")
        self.windup = float(data.get("windup", 0.0))
        self.knockback = float(data.get("knockback", 0.35))
        self.cast_type = data.get("cast_type", "projectile")
        self.proj_speed = float(data.get("proj_speed", 9.2))
        self.aoe_radius = float(data.get("aoe_radius", 2.0))
        self.duration = float(data.get("duration", 0.0))

        base_bounces = int(data.get("bounces", 0 if self.weap_style == "thrown" else 1))
        if is_weapon and self.weap_style == "thrown" and base_bounces > 0 and self.tier_idx >= 3:
            self.bounces = base_bounces + 1
        else:
            self.bounces = base_bounces

        self.status = data.get("status", None)
        base_sd = float(data.get("status_dur", 0.0))
        self.status_dur = round(base_sd * (1.0 + 0.10 * self.tier_idx), 2) if (is_weapon and base_sd > 0) else base_sd

        base_sc = float(data.get("status_chance", 1.0 if self.status else 0.0))
        self.status_chance = min(1.0, round(base_sc + (0.08 * self.tier_idx if is_weapon else 0.0), 2)) if self.status else 0.0

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

        self.icon = data["icon"]
        raw_desc = data.get("desc", "")
        self.desc = random.choice(raw_desc) if isinstance(raw_desc, list) and raw_desc else str(raw_desc)
        self.copper_value = int(data.get("copper_value", 0))

        self.max_fuel = float(data.get("max_fuel", 100.0))
        self.fuel = self.max_fuel

        self.power = data.get("power", 0)
        self.heal_hp = int(data.get("heal_hp", self.power if item_id.startswith("potion_hp") else 0))
        self.mp_cost = data.get("mp_cost", 0)

        base_dmin = int(data.get("dmg_min", 2 if is_weapon else 0))
        base_dmax = int(data.get("dmg_max", 4 if is_weapon else 0))
        if is_weapon:
            tier_mult = (0.0, 0.35, 0.75, 1.25, 1.85)
            bonus_min = int(round(base_dmin * tier_mult[self.tier_idx]))
            bonus_max = max(bonus_min + self.tier_idx, int(round(base_dmax * tier_mult[self.tier_idx])))
            self.dmg_min = base_dmin + bonus_min
            self.dmg_max = base_dmax + bonus_max
        else:
            self.dmg_min = base_dmin
            self.dmg_max = base_dmax

        base_phys = int(data.get("phys_bonus", 0))
        self.phys_bonus = _scale_int_stat(base_phys, self.tier_idx) if is_gear else base_phys

        base_mag = int(data.get("mag_bonus", 0))
        if is_weapon and base_mag > 0:
            self.mag_bonus = base_mag + self.tier_idx
        elif is_gear:
            self.mag_bonus = _scale_int_stat(base_mag, self.tier_idx)
        else:
            self.mag_bonus = base_mag

        base_pdef = int(data.get("phys_def", 0))
        base_mdef = int(data.get("mag_def", 0))
        self.phys_def = _scale_int_stat(base_pdef, self.tier_idx) if is_gear else base_pdef
        self.mag_def = _scale_int_stat(base_mdef, self.tier_idx) if is_gear else base_mdef

        base_hp = int(data.get("hp_bonus", 0))
        base_mp = int(data.get("mp_bonus", 0))
        self.hp_bonus = int(round(base_hp * (1.0 + 0.45 * self.tier_idx))) if (is_gear and base_hp > 0) else base_hp
        self.mp_bonus = int(round(base_mp * (1.0 + 0.45 * self.tier_idx))) if (is_gear and base_mp > 0) else base_mp

        base_dodge = float(data.get("dodge_bonus", 0.0))
        self.dodge_bonus = round(base_dodge * (1.0 + 0.35 * self.tier_idx), 3) if (is_gear and base_dodge > 0) else base_dodge

        base_spd = float(data.get("speed_bonus", 0.0))
        self.speed_bonus = round(base_spd * (1.0 + 0.35 * self.tier_idx), 3) if (is_gear and base_spd > 0) else base_spd

        self.hp_regen = 0.0
        self.mp_regen = 0.0
        base_hrb = float(data.get("heal_received_bonus", 0.0))
        self.heal_received_bonus = round(base_hrb * (1.0 + 0.35 * self.tier_idx), 2) if (is_gear and base_hrb > 0) else base_hrb

        base_mrb = float(data.get("mana_received_bonus", 0.0))
        self.mana_received_bonus = round(base_mrb * (1.0 + 0.35 * self.tier_idx), 2) if (is_gear and base_mrb > 0) else base_mrb

        base_noise = float(data.get("noise_mod", 0.0))
        self.noise_mod = round(base_noise * (1.0 + 0.15 * self.tier_idx), 2) if (is_gear and base_noise < 0) else base_noise

        base_vis = int(data.get("vision_bonus", 0))
        self.vision_bonus = int(round(base_vis * (1.0 + 0.18 * self.tier_idx))) if (is_gear and base_vis > 0) else base_vis

        base_glow = float(data.get("glow_radius", 0.0))
        self.glow_radius = round(base_glow * (1.0 + 0.15 * self.tier_idx), 1) if (is_gear and base_glow > 0) else base_glow
        self.glow_color = tuple(data.get("glow_color", (0.85, 0.85, 0.95)))

        self.extra_slots = int(data.get("extra_slots_per_tier", 0)) * (self.tier_idx + 1)
        self.armor_class = data.get("armor_class", "none")

        self.active_spell = data.get("active_spell", None)
        self.color = tuple(data.get("color", [110, 225, 255]))
        self.slots = data.get("slots", 2)
        self.bag_filter = data.get("bag_filter", "any")
        self.locked_bag = bool(data.get("locked_bag", False))
        self.is_collectible = bool(data.get("is_collectible", False))
        self.collection_kind = data.get("collection_kind", None)

        self.sell_value, self.buy_value = self._compute_prices(data)
        if self.copper_value <= 0:
            self.copper_value = self.sell_value

    def _compute_prices(self, data):
        if self.type == "currency_coin":
            val = int(data.get("copper_value", 0))
            return val, val
        if self.type in ("gem", "fish", "painting"):
            sell = max(1, int(data.get("copper_value", 20)))
            return sell, int(round(sell * 2.0))
        if self.type == "quest_key":
            return 0, 0
        if self.type == "bag":
            if self.locked_bag:
                return 0, 0
            tier_base = (24, 72, 185, 460, 1100)[self.tier_idx]
            sell = tier_base + self.slots * 4
            return sell, int(round(sell * 2.5))
        if self.type == "consumable":
            if self.id == "potion_hp_weak":
                sell = 12
            elif self.id == "herbal_salve":
                sell = 16
            elif self.id == "potion_hp_strong":
                sell = 58
            else:
                sell = 24
            return sell, int(round(sell * 2.5))
        if self.type == "consumable_spell":
            sell = 45
            return sell, int(round(sell * 2.5))
        if self.type == "consumable_eraser":
            return 180, 450
        if self.type == "equipment":
            if self.id == "pitch_torch":
                return 5, 15
            slot_base = {
                "right_hand": 40 if self.two_handed else 32,
                "torso": 36,
                "left_hand": 28,
                "helmet": 24,
                "boots": 24,
                "ring": 30,
                "trinket": 32,
            }.get(self.slot, 26)
            tier_mult = (1.0, 2.2, 4.5, 9.5, 20.0)[self.tier_idx]
            sell = max(5, int(round(slot_base * tier_mult)))
            return sell, int(round(sell * 2.5))
        return 0, 0