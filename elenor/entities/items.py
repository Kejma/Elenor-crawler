import random
from elenor.config import RARITY_COLORS




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

        # Определяем редкость экземпляра (для оружия она динамическая!)
        is_weapon = (self.type == "equipment" and self.slot == "right_hand" and not self.is_torch)
        if rarity_override in self.RARITY_ORDER:
            self.rarity = rarity_override
        else:
            self.rarity = data.get("rarity", "common")
        if self.rarity not in self.RARITY_ORDER:
            self.rarity = "common"

        self.tier_idx = self.RARITY_ORDER.index(self.rarity)
        self.rarity_color = RARITY_COLORS.get(self.rarity, (215, 215, 220))
        self.name = f"{self.base_name}{self.RARITY_ROMAN[self.tier_idx]}" if is_weapon else self.base_name

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
        self.life_steal = (base_ls + (2 if self.tier_idx == 4 else (1 if self.tier_idx >= 2 else 0))) if (is_weapon and base_ls > 0) else base_ls

        # Исторические фишечки оружия с масштабированием от редкости экземпляра
        base_crit = float(data.get("crit_bonus", 0.0))
        self.crit_bonus = round(base_crit + (0.02 * self.tier_idx if is_weapon else 0.0), 2)

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

        self.phys_bonus = int(data.get("phys_bonus", 0))

        base_mag = int(data.get("mag_bonus", 0))
        self.mag_bonus = (base_mag + self.tier_idx) if (is_weapon and base_mag > 0) else base_mag

        self.phys_def = data.get("phys_def", 0)
        self.mag_def = data.get("mag_def", 0)
        self.noise_mod = data.get("noise_mod", 0.0)
        self.vision_bonus = data.get("vision_bonus", 0)
        self.mp_regen = float(data.get("mp_regen", 0.0))
        self.armor_class = data.get("armor_class", "none")

        self.active_spell = data.get("active_spell", None)
        self.color = tuple(data.get("color", [110, 225, 255]))
        self.slots = data.get("slots", 2)
