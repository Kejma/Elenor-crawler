from elenor.data.abilities import perk_branch
import math
import random

from elenor.config import get_rarity_weights
from elenor.entities import Item, Particle




class ProgressionMixin:
    def _is_perk_eligible(self, pid, pdata):
        ptype = pdata.get("type", "passive")
        if ptype == "active":
            return (pid in self.player.active_perks) or (len(self.player.active_perks) < 4)
        return self.player.can_learn_passive(pid)


    def _get_perk_branch(self, pid, pdata):
        declared = perk_branch(pid, pdata)
        if declared:
            return declared
        perk_tags = {
            "tough_skin": "body", "iron_grip": "body", "stone_ribs": "body",
            "titan_blood": "body", "blood_hunger": "body", "whirlwind": "body", "earth_slam": "body",
            "cat_step": "cunning", "keen_edge": "cunning", "throw_knife": "cunning", "poison_flask": "cunning",
            "clear_mind": "mind", "storm_aura": "mind",
            "pyro_firebolt": "mind", "pyro_ignite": "mind",
            "stratos_frost_nova": "mind", "stratos_chain_lightning": "mind",
            "persephone_rejuvenation": "mind", "persephone_entangle": "mind"
        }
        if pid in perk_tags:
            return perk_tags[pid]
        if pdata.get("skill_kind") == "combat":
            return "body"
        if pdata.get("type") == "active":
            return "mind"
        return "body"


    def _roll_spell_upgrade_stats(self, pdata, tier_weights_list):
        """
        Для уже изученного навыка выбирает редкость улучшения (6% / 12% / 20% / 32% / 48%)
        и делит этот процент поровну между 1..3 случайными параметрами способности!
        """
        tiers = Item.RARITY_ORDER
        pct_table = {
            "common": 0.06,
            "uncommon": 0.12,
            "rare": 0.20,
            "epic": 0.32,
            "legendary": 0.48,
        }
        max_stats_table = {
            "common": 1,
            "uncommon": 2,
            "rare": 3,
            "epic": 3,
            "legendary": 3,
        }
        upg_rarity = random.choices(tiers, weights=tier_weights_list, k=1)[0]
        total_pct = pct_table[upg_rarity]
        avail_stats = list(pdata.get("upgradable_stats", ["power", "cooldown"]))
        max_k = min(len(avail_stats), max_stats_table[upg_rarity])
        k_choose = 1 if max_k <= 1 else random.randint(1, max_k)
        chosen_stats = random.sample(avail_stats, k=k_choose)
        share_pct = total_pct / float(k_choose)
        return upg_rarity, {st: share_pct for st in chosen_stats}


    def roll_perk_choices(self):
        perks_db = self.loc.get("perks", {})
        if not perks_db:
            return
        tiers = Item.RARITY_ORDER
        tier_weights_list = get_rarity_weights(getattr(self.player, "luck", 1))

        aff = self.player.get_build_affinities()
        total_aff = sum(aff.values()) + 1.0

        chosen = []
        used_ids = set()

        for _ in range(3):
            candidates = [
                (pid, pdata) for pid, pdata in perks_db.items()
                if pid not in used_ids and self._is_perk_eligible(pid, pdata)
            ]
            if not candidates:
                break
            upgrades = [choice for choice in candidates if choice[0] in self.player.perks]
            discoveries = [choice for choice in candidates if choice[0] not in self.player.perks]
            if upgrades and discoveries:
                candidates = upgrades if random.random() < 0.25 else discoveries
            cand_weights = []
            for pid, pdata in candidates:
                branch = self._get_perk_branch(pid, pdata)
                branch_share = aff.get(branch, 0.0) / total_aff
                affinity_mult = 1.0 + 1.45 * branch_share
                cand_weights.append(affinity_mult)

            picked_pid, picked_data = random.choices(candidates, weights=cand_weights, k=1)[0]
            used_ids.add(picked_pid)
            p_copy = dict(picked_data)
            p_copy["id"] = picked_pid
            if picked_pid in self.player.perks:
                upg_rar, upg_roll = self._roll_spell_upgrade_stats(picked_data, tier_weights_list)
                p_copy["rarity"] = upg_rar
                p_copy["upgrade_roll"] = upg_roll
            else:
                p_copy["rarity"] = random.choices(tiers, weights=tier_weights_list, k=1)[0]

            chosen.append(p_copy)

        if chosen:
            self.levelup_choices = {"mode": "levelup", "choices": chosen, "lock_timer": 1.0}


    def open_oblivion_erase_modal(self, seal_item):
        perks_db = self.loc.get("perks", {})
        owned_ids = list(self.player.active_perks.keys()) + list(self.player.passive_perks.keys())
        if not owned_ids:
            self.trigger_event_thought("oblivion_empty")
            self.sfx.play("hurt")
            return
        choices = []
        for pid in owned_ids:
            if pid in perks_db:
                p_copy = dict(perks_db[pid])
                p_copy["id"] = pid
                choices.append(p_copy)
        self.inv_open = False
        self.levelup_choices = {"mode": "erase", "choices": choices, "lock_timer": 0.4, "seal_item": seal_item}
        self.sfx.play("magic")


    def select_perk_choice(self, idx):
        if not self.levelup_choices or self.levelup_choices.get("lock_timer", 0.0) > 0.0:
            return
        choices = self.levelup_choices["choices"]
        if not (0 <= idx < len(choices)):
            return
        perk = choices[idx]

        if self.levelup_choices.get("mode") == "erase":
            seal_item = self.levelup_choices.get("seal_item")
            if self.player.remove_perk(perk["id"]):
                if seal_item:
                    self.player.remove_item_everywhere(seal_item)
                self.sfx.play("crit")
                self.add_popup(self.player.x, self.player.y - 0.4, f"Стёрто: {perk['name']}", (225, 110, 255))
            self.levelup_choices = None
            return

        self.player.apply_perk(perk["id"], {perk["id"]: perk}, perk.get("upgrade_roll"))
        self.player.pending_perk_rolls = max(0, self.player.pending_perk_rolls - 1)
        self.sfx.play("heal")
        self.add_popup(self.player.x, self.player.y - 0.4, f"+{perk['name']}", (255, 225, 95))
        if self.player.pending_perk_rolls > 0:
            self.roll_perk_choices()
        else:
            self.levelup_choices = None


    def update_auto_perks(self, dt):
        p = self.player
        if p.perks.get("storm_aura", 0) > 0:
            lvl = p.perks["storm_aura"]
            p.perk_timers["storm_aura"] = p.perk_timers.get("storm_aura", 1.8) - dt
            if p.perk_timers["storm_aura"] <= 0.0:
                p.perk_timers["storm_aura"] = max(1.35, 3.0 - (lvl - 1) * 0.35)
                vis_set = getattr(self, "current_visible_tiles", set())
                nearest = min(
                    (
                        m for m in self.mobs
                        if math.hypot(m.x - p.x, m.y - p.y) <= 5.2
                        and (int(m.x), int(m.y)) in vis_set
                        and self.dungeon.has_line_of_sight(p.x, p.y, m.x, m.y, 5.2)
                    ),
                    key=lambda m: math.hypot(m.x - p.x, m.y - p.y),
                    default=None
                )
                if nearest:
                    # Auto-triggered lightning hits much softer than manual active spells!
                    auto_dmg = max(1, 1 + lvl + p.mag_attack // 4)
                    self._fire_spell_bolt(auto_dmg, (95, 230, 255), nearest.x, nearest.y)


    def trigger_levelup_shine(self):
        self.sfx.play("levelup")
        self.trigger_event_thought("level_up")
        self.add_popup(self.player.x, self.player.y - 0.65, "НОВЫЙ УРОВЕНЬ!", (255, 230, 85))
        self.player.levelup_delay_timer = 0.55
        self.player.shine_timer = 0.95
        for _ in range(24):
            ang = random.uniform(0, 6.28)
            spd = random.uniform(0.6, 2.4)
            self.particles.append(Particle(
                self.player.x + math.cos(ang) * 0.25,
                self.player.y + math.sin(ang) * 0.25,
                math.cos(ang) * spd,
                math.sin(ang) * spd - 1.4,
                (255, 225, 90), 3.2, 0.55
            ))

