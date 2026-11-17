from elenor.paths import PROJECT_ROOT
import json
import os
import random
from elenor.config import RARITY_WEIGHTS
from elenor.world.dungeon import Dungeon

SIMULATION_RUNS = 200

# Harsh survival target: a player in Common/Uncommon gear who fights 65% of the floor
# will lose 92% of their entire Effective HP budget (leaving just 8% margin!).
TARGET_SURVIVAL_MARGIN = 0.08
EXPECTED_COMBAT_ENGAGEMENT_RATIO = 0.65

RARITY_POWER_CURVE = {
    "common": 1.00,      # 50.0%
    "uncommon": 1.35,    # 24.0%
    "rare": 1.80,        # 15.5%
    "epic": 2.40,        # 7.5%
    "legendary": 3.20    # 3.0%
}

ENEMY_ARCHETYPES = {
    "wolf":        {"hp_mult": 0.55, "dmg_mult": 0.52, "phys_def": 0, "mag_def": 0, "xp": 12},
    "skeleton":    {"hp_mult": 1.00, "dmg_mult": 1.00, "phys_def": 1, "mag_def": 0, "xp": 15},
    "cultist":     {"hp_mult": 0.85, "dmg_mult": 1.05, "phys_def": 0, "mag_def": 3, "xp": 18},
    "necromancer": {"hp_mult": 1.35, "dmg_mult": 1.25, "phys_def": 1, "mag_def": 5, "xp": 26},
    "brute":       {"hp_mult": 1.65, "dmg_mult": 1.38, "phys_def": 3, "mag_def": 1, "xp": 24},
}


def simulate_dungeon_ecology(runs=SIMULATION_RUNS):
    d = Dungeon()
    total_rooms = 0
    total_mobs = 0
    total_campfires = 0
    total_chests = 0
    total_racks = 0
    total_alchemy = 0
    total_books = 0
    total_idols = 0
    total_floor_loot = 0

    for _ in range(runs):
        d.generate(floor_num=1)
        n_rooms = len(d.rooms)
        total_rooms += n_rooms

        total_campfires += 1
        total_racks += 1
        total_floor_loot += 2
        total_mobs += 1

        for idx in range(2, n_rooms):
            if idx == n_rooms - 1:
                pass
            elif idx % 9 == 0:
                total_campfires += 1
            elif idx % 8 == 0:
                total_books += 1
            elif idx % 9 == 4:
                total_alchemy += 1
            elif idx % 8 == 3:
                total_racks += 1
            elif idx % 6 == 0:
                total_chests += 1
            elif idx % 7 == 0:
                total_idols += 1
            elif random.random() < 0.16:
                total_floor_loot += 1

            if idx % 3 == 0:
                total_mobs += 2
            else:
                total_mobs += 1

    return {
        "avg_rooms": total_rooms / runs,
        "avg_mobs": total_mobs / runs,
        "avg_campfires": total_campfires / runs,
        "avg_chests": total_chests / runs,
        "avg_racks": total_racks / runs,
        "avg_alchemy": total_alchemy / runs,
        "avg_books": total_books / runs,
        "avg_idols": total_idols / runs,
        "avg_floor_loot": total_floor_loot / runs,
    }


def compute_and_bake_balance():
    base_dir = str(PROJECT_ROOT)
    items_path = os.path.join(base_dir, "locales", "ru", "items.json")
    balance_out_path = os.path.join(base_dir, "locales", "ru", "balance_table.json")

    with open(items_path, "r", encoding="utf-8") as f:
        items_db = json.load(f)

    eco = simulate_dungeon_ecology()

    total_w = sum(RARITY_WEIGHTS.values())
    probs = {k: v / total_w for k, v in RARITY_WEIGHTS.items()}
    expected_rarity_mult = sum(probs[r] * RARITY_POWER_CURVE[r] for r in probs)
    baseline_gear_mult = (probs["common"] * RARITY_POWER_CURVE["common"] + probs["uncommon"] * RARITY_POWER_CURVE["uncommon"]) / (probs["common"] + probs["uncommon"])

    # Tighter, grounded item base stats (no more spell 1-shots!)
    BASE_1H_PHYS = 2.5
    BASE_2H_PHYS = 4.5
    BASE_TORSO_DEF = 2.2
    BASE_HELM_BOOT_DEF = 1.0
    BASE_POTION_HEAL = 12.0
    BASE_SPELL_PWR = 3.5

    for item_id, data in items_db.items():
        rarity = data.get("rarity", "common")
        r_mult = RARITY_POWER_CURVE.get(rarity, 1.0)
        itype = data.get("type")
        slot = data.get("slot")

        if itype == "equipment":
            if slot == "right_hand":
                if data.get("two_handed", False):
                    data["phys_bonus"] = max(4, int(round(BASE_2H_PHYS * r_mult)))
                    if data.get("mag_bonus", 0) > 0:
                        data["mag_bonus"] = max(1, int(round(1.5 * r_mult)))
                else:
                    has_utility = (data.get("mag_bonus", 0) > 0 or data.get("life_steal", 0) > 0)
                    util_mod = 0.85 if has_utility else 1.0
                    data["phys_bonus"] = max(2, int(round(BASE_1H_PHYS * r_mult * util_mod)))
                    if data.get("mag_bonus", 0) > 0:
                        data["mag_bonus"] = max(1, int(round(1.5 * r_mult)))
                    if data.get("life_steal", 0) > 0:
                        data["life_steal"] = max(1, int(round(0.9 * r_mult)))

            elif slot == "torso":
                ac = data.get("armor_class", "leather")
                total_def = BASE_TORSO_DEF * r_mult
                if ac == "cloth":
                    data["phys_def"] = max(1, int(round(total_def * 0.25)))
                    data["mag_def"] = max(2, int(round(total_def * 0.75)))
                elif ac == "leather":
                    data["phys_def"] = max(2, int(round(total_def * 0.60)))
                    data["mag_def"] = max(1, int(round(total_def * 0.40)))
                elif ac == "plate":
                    data["phys_def"] = max(3, int(round(total_def * 0.95)))
                    data["mag_def"] = max(1, int(round(total_def * 0.25)))

            elif slot in ("helmet", "boots", "left_hand") and not data.get("is_torch", False):
                if data.get("phys_def", 0) > 0:
                    data["phys_def"] = max(1, int(round(BASE_HELM_BOOT_DEF * r_mult)))
                if data.get("mag_def", 0) > 0:
                    data["mag_def"] = max(1, int(round(BASE_HELM_BOOT_DEF * r_mult)))

            if data.get("active_spell"):
                data["active_spell"]["power"] = max(5, int(round(BASE_SPELL_PWR * r_mult)))

        elif itype == "consumable":
            if "hp" in item_id:
                data["power"] = max(10, int(round(BASE_POTION_HEAL * r_mult)))
            elif "mp" in item_id:
                data["power"] = max(8, int(round((BASE_POTION_HEAL - 2) * r_mult)))

        elif itype == "spell":
            data["power"] = max(4, int(round(BASE_SPELL_PWR * r_mult)))

    # Realistic Player EHP Pool with scarce loot
    avg_start_body = 3.0
    start_hp = 18.0 + avg_start_body * 6.0  # 36 HP
    expected_campfire_heal = eco["avg_campfires"] * 8.0 * 0.65
    expected_alchemy_heal = eco["avg_alchemy"] * 12.0 * 0.50
    expected_idol_heal = eco["avg_idols"] * 10.0 * 0.40
    expected_potions_heal = (eco["avg_floor_loot"] * 0.20 + eco["avg_chests"] * 0.25) * BASE_POTION_HEAL

    total_player_ehp = (
        start_hp
        + expected_campfire_heal
        + expected_alchemy_heal
        + expected_idol_heal
        + expected_potions_heal
    )

    allowed_damage_taken_budget = total_player_ehp * (1.0 - TARGET_SURVIVAL_MARGIN)
    fought_mobs = eco["avg_mobs"] * EXPECTED_COMBAT_ENGAGEMENT_RATIO

    # Calibrate for unarmored early-game player: Wolf/Rat ~11 HP (2-3 hits), Skeleton ~19 HP (3 hits)
    baseline_weapon_bonus = BASE_1H_PHYS * baseline_gear_mult
    baseline_hit_dmg = 2.0 + avg_start_body + baseline_weapon_bonus
    target_hits_to_kill = 2.85
    base_skeleton_hp = int(round((baseline_hit_dmg - 1.0) * target_hits_to_kill))

    # Calibrate enemy damage so Wolf/Rat hits for 2..4, Skeleton for 4..6, Brute for 6..9
    expected_player_def = 1.0
    net_dmg_per_hit = max(3.8, (allowed_damage_taken_budget / max(1.0, fought_mobs)) * 0.95)
    base_skeleton_raw_dmg = net_dmg_per_hit + expected_player_def

    enemy_table = {}
    for kind, arch in ENEMY_ARCHETYPES.items():
        e_hp = max(9, int(round(base_skeleton_hp * arch["hp_mult"])))
        e_avg_dmg = max(2.5, base_skeleton_raw_dmg * arch["dmg_mult"])
        e_min = max(2, int(round(e_avg_dmg * 0.80)))
        e_max = max(e_min + 1, int(round(e_avg_dmg * 1.20)))

        enemy_table[kind] = {
            "hp": e_hp,
            "dmg_min": e_min,
            "dmg_max": e_max,
            "phys_def": arch["phys_def"],
            "mag_def": arch["mag_def"],
            "xp": arch["xp"],
            "floor_hp_growth": 0.28,
            "floor_dmg_growth": 0.22
        }

    with open(items_path, "w", encoding="utf-8") as f:
        json.dump(items_db, f, ensure_ascii=False, indent=2)

    balance_payload = {
        "meta": {
            "simulated_runs": SIMULATION_RUNS,
            "target_survival_margin": TARGET_SURVIVAL_MARGIN,
            "expected_rarity_multiplier": round(expected_rarity_mult, 3),
            "total_player_ehp_floor1": round(total_player_ehp, 1),
        },
        "enemies": enemy_table
    }
    with open(balance_out_path, "w", encoding="utf-8") as f:
        json.dump(balance_payload, f, ensure_ascii=False, indent=2)

    print("=" * 68)
    print("  BALANCE-MASTER v2: ХАРДКОРНЫЙ РЕБАЛАНС И ДЕФИЦИТ ЛУТА")
    print("=" * 68)
    print(f" • Среднее число врагов на этаже:    {eco['avg_mobs']:.1f}")
    print(f" • Дефицитный лут: Сундуки={eco['avg_chests']:.1f}, Стойки={eco['avg_racks']:.1f}, На полу={eco['avg_floor_loot']:.1f}")
    print(f" • Бюджет выживаемости героя (EHP):  {total_player_ehp:.1f} ХП (остаток {int(TARGET_SURVIVAL_MARGIN*100)}%)")
    print("-" * 68)
    for k, v in enemy_table.items():
        print(f" • {k.ljust(12)} | ХП: {str(v['hp']).rjust(2)} | Урон: {v['dmg_min']}..{v['dmg_max']} | Защ(Ф/М): {v['phys_def']}/{v['mag_def']} | XP: {v['xp']}")
    print("=" * 68)


if __name__ == "__main__":
    compute_and_bake_balance()