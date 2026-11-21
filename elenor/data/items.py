BAG_CAPACITIES = {
    "small_pouch": 2,
    "waxed_pouch": 3,
    "pouch_bag": 4,
    "reed_satchel": 5,
    "scout_satchel": 6,
    "frame_pack": 7,
    "travel_backpack": 8,
    "void_chest_bag": 9,
    # Ювелирные сумки (в ~2.5 раза больше, только драгоценности и коллекционки)
    "velvet_gem_pouch": 5,
    "jeweler_satchel": 10,
    "antiquary_case": 15,
    "collector_trunk": 18,
    "treasury_vault_bag": 20,
    # Пояса и перевязи (только зелья, свитки и расходники)
    "herb_belt": 5,
    "alchemist_bandolier": 8,
    "apothecary_rig": 12,
    "master_bandolier": 16,
}

BASE_ITEMS_DB = {
    # Ключи головоломок не участвуют в случайном луте. Тексты — в locales.
    "focusing_lens": {"type": "quest_key", "rarity": "rare", "icon": "trinket"},

    # ИСТОЧНИКИ СВЕТА, ЩИТЫ И ФОКУСЫ (ЛЕВАЯ РУКА)
    "pitch_torch": {
        "type": "equipment", "slot": "left_hand", "is_torch": True,
        "max_fuel": 120.0, "icon": "torch"
    },
    "dwarven_lantern": {
        "type": "equipment", "slot": "left_hand", "is_torch": True,
        "max_fuel": 260.0, "vision_bonus": 32, "icon": "offhand_lantern"
    },
    "buckler_shield": {
        "type": "equipment", "slot": "left_hand", "phys_def": 2, "dodge_bonus": 0.04,
        "crit_bonus": 0.03, "icon": "shield_buckler"
    },
    "heater_shield": {
        "type": "equipment", "slot": "left_hand", "phys_def": 3, "hp_bonus": 6,
        "noise_mod": 0.12, "icon": "shield_heater"
    },
    "spiked_targe": {
        "type": "equipment", "slot": "left_hand", "phys_def": 2, "phys_bonus": 2,
        "noise_mod": 0.08, "icon": "shield_spiked"
    },
    "pavise_wall": {
        "type": "equipment", "slot": "left_hand", "phys_def": 4, "mag_def": 1,
        "speed_bonus": -0.06, "noise_mod": 0.22, "icon": "shield_pavise"
    },
    "glowing_orb": {
        "type": "equipment", "slot": "left_hand", "mag_bonus": 2, "vision_bonus": 28,
        "glow_radius": 56, "glow_color": [0.55, 0.95, 0.78], "icon": "offhand_orb"
    },
    "iron_censer": {
        "type": "equipment", "slot": "left_hand", "mag_def": 2, "heal_received_bonus": 0.16,
        "glow_radius": 44, "glow_color": [1.05, 0.65, 0.30], "icon": "offhand_censer"
    },
    "parrying_gauntlet": {
        "type": "equipment", "slot": "left_hand", "phys_def": 1, "crit_bonus": 0.06,
        "dodge_bonus": 0.05, "noise_mod": -0.05, "icon": "offhand_gauntlet"
    },
    "runic_tablet": {
        "type": "equipment", "slot": "left_hand", "mag_bonus": 2, "mp_bonus": 4,
        "mana_received_bonus": 0.16, "icon": "offhand_tablet"
    },
    # КОРОТКОЕ ОДНОРУЧНОЕ ОРУЖИЕ
    "rusty_dagger": {
        "type": "equipment", "slot": "right_hand", "two_handed": False, "weap_style": "dagger",
        "dmg_min": 2, "dmg_max": 4, "atk_cd": 0.24, "windup": 0.0, "reach": 1.45, "arc_deg": 32.0,
        "max_targets": 1, "crit_bonus": 0.08, "backstab_bonus": 2.2, "knockback": 0.15, "icon": "weapon_dagger"
    },
    "scramasax": {
        "type": "equipment", "slot": "right_hand", "two_handed": False, "weap_style": "curved",
        "dmg_min": 3, "dmg_max": 5, "atk_cd": 0.30, "windup": 0.02, "reach": 1.45, "arc_deg": 70.0,
        "max_targets": 2, "knockback": 0.20, "status": "poison", "status_dur": 2.4, "status_chance": 0.35, "icon": "weapon_curved"
    },
    "rondel_dagger": {
        "type": "equipment", "slot": "right_hand", "two_handed": False, "weap_style": "dagger",
        "dmg_min": 2, "dmg_max": 4, "atk_cd": 0.25, "windup": 0.0, "reach": 1.32, "arc_deg": 28.0,
        "max_targets": 1, "armor_pierce": 2, "crit_bonus": 0.10, "backstab_bonus": 2.5, "knockback": 0.10, "noise_mod": -0.10, "icon": "weapon_dagger"
    },
    "katar_dagger": {
        "type": "equipment", "slot": "right_hand", "two_handed": False, "weap_style": "dagger",
        "dmg_min": 2, "dmg_max": 3, "atk_cd": 0.38, "windup": 0.0, "reach": 1.38, "arc_deg": 35.0,
        "max_targets": 1, "armor_pierce": 1, "crit_bonus": 0.06, "multi_hit": 2, "knockback": 0.15, "icon": "weapon_katar"
    },
    "cinquedea": {
        "type": "equipment", "slot": "right_hand", "two_handed": False, "weap_style": "sword",
        "dmg_min": 3, "dmg_max": 5, "atk_cd": 0.32, "windup": 0.02, "reach": 1.54, "arc_deg": 60.0,
        "max_targets": 2, "crit_bonus": 0.10, "life_steal": 1, "reset_cd_on_kill": True, "knockback": 0.22, "icon": "weapon_dagger"
    },
    "vampiric_rapier": {
        "type": "equipment", "slot": "right_hand", "two_handed": False, "weap_style": "dagger",
        "dmg_min": 3, "dmg_max": 5, "atk_cd": 0.26, "windup": 0.0, "reach": 1.75, "arc_deg": 28.0,
        "max_targets": 1, "life_steal": 1, "crit_bonus": 0.08, "knockback": 0.20, "icon": "weapon_dagger"
    },

    # СРЕДНЕЕ ОДНОРУЧНОЕ ОРУЖИЕ 
    "wooden_club": {
        "type": "equipment", "slot": "right_hand", "two_handed": False, "weap_style": "mace",
        "dmg_min": 4, "dmg_max": 7, "atk_cd": 0.44, "windup": 0.08, "reach": 1.60, "arc_deg": 55.0,
        "max_targets": 1, "armor_pierce": 1, "status": "stun", "status_dur": 0.75, "status_chance": 0.30, "knockback": 0.85, "icon": "weapon_mace"
    },
    "serrated_cleaver": {
        "type": "equipment", "slot": "right_hand", "two_handed": False, "weap_style": "sword",
        "dmg_min": 4, "dmg_max": 6, "atk_cd": 0.36, "windup": 0.04, "reach": 1.68, "arc_deg": 80.0,
        "max_targets": 2, "lunge_dist": 0.35, "knockback": 0.35, "icon": "weapon_sword"
    },
    "gladius_mainz": {
        "type": "equipment", "slot": "right_hand", "two_handed": False, "weap_style": "sword",
        "dmg_min": 4, "dmg_max": 6, "phys_def": 1, "atk_cd": 0.34, "windup": 0.03, "reach": 1.52, "arc_deg": 55.0,
        "max_targets": 2, "lunge_dist": 0.35, "knockback": 0.30, "icon": "weapon_sword"
    },
    "khopesh": {
        "type": "equipment", "slot": "right_hand", "two_handed": False, "weap_style": "curved",
        "dmg_min": 4, "dmg_max": 6, "atk_cd": 0.38, "windup": 0.04, "reach": 1.60, "arc_deg": 85.0,
        "max_targets": 2, "shatter_armor": 1, "status": "slow", "status_dur": 1.8, "status_chance": 0.45, "knockback": 0.25, "icon": "weapon_curved"
    },
    "falcata": {
        "type": "equipment", "slot": "right_hand", "two_handed": False, "weap_style": "cleaver",
        "dmg_min": 4, "dmg_max": 7, "atk_cd": 0.40, "windup": 0.05, "reach": 1.58, "arc_deg": 80.0,
        "max_targets": 2, "armor_pierce": 1, "shatter_armor": 1, "lunge_dist": 0.38, "knockback": 0.38, "icon": "weapon_curved"
    },
    "flanged_mace": {
        "type": "equipment", "slot": "right_hand", "two_handed": False, "weap_style": "mace",
        "dmg_min": 5, "dmg_max": 8, "atk_cd": 0.46, "windup": 0.06, "reach": 1.55, "arc_deg": 75.0,
        "max_targets": 2, "armor_pierce": 2, "status": "stun", "status_dur": 0.85, "status_chance": 0.32, "knockback": 0.55, "icon": "weapon_mace"
    },
    "war_mace": {
        "type": "equipment", "slot": "right_hand", "two_handed": False, "weap_style": "mace",
        "dmg_min": 4, "dmg_max": 7, "atk_cd": 0.48, "windup": 0.08, "reach": 1.60, "arc_deg": 55.0,
        "max_targets": 1, "armor_pierce": 3, "shatter_armor": 1, "knockback": 0.75, "icon": "weapon_mace"
    },
    "runic_longsword": {
        "type": "equipment", "slot": "right_hand", "two_handed": False, "weap_style": "sword",
        "dmg_min": 4, "dmg_max": 7, "atk_cd": 0.40, "windup": 0.05, "reach": 1.85, "arc_deg": 105.0,
        "max_targets": 3, "mag_bonus": 2, "vision_bonus": 12, "knockback": 0.50, "icon": "weapon_sword"
    },
    "boar_spear": {
        "type": "equipment", "slot": "right_hand", "two_handed": False, "weap_style": "spear",
        "dmg_min": 4, "dmg_max": 6, "atk_cd": 0.38, "windup": 0.05, "reach": 2.15, "arc_deg": 35.0,
        "max_targets": 2, "knockback": 0.75, "icon": "weapon_spear"
    },
    "guard_spear": {
        "type": "equipment", "slot": "right_hand", "two_handed": False, "weap_style": "spear",
        "dmg_min": 4, "dmg_max": 6, "atk_cd": 0.38, "windup": 0.05, "reach": 2.25, "arc_deg": 28.0,
        "max_targets": 2, "sweet_spot": True, "knockback": 0.65, "icon": "weapon_spear"
    },

    # ТЯЖЁЛОЕ ДВУРУЧНОЕ ОРУЖИЕ 
    "goedendag": {
        "type": "equipment", "slot": "right_hand", "two_handed": True, "weap_style": "spear",
        "dmg_min": 7, "dmg_max": 11, "atk_cd": 0.48, "windup": 0.08, "reach": 2.05, "arc_deg": 50.0,
        "max_targets": 2, "armor_pierce": 2, "status": "stun", "status_dur": 0.80, "status_chance": 0.35, "knockback": 0.70, "icon": "weapon_mace"
    },
    "billhook": {
        "type": "equipment", "slot": "right_hand", "two_handed": True, "weap_style": "halberd",
        "dmg_min": 7, "dmg_max": 10, "atk_cd": 0.48, "windup": 0.06, "reach": 2.25, "arc_deg": 65.0,
        "max_targets": 2, "shatter_armor": 1, "hook_pull": True, "status": "root", "status_dur": 0.85, "status_chance": 0.55, "knockback": 0.60, "icon": "weapon_halberd"
    },
    "falx_dacian": {
        "type": "equipment", "slot": "right_hand", "two_handed": True, "weap_style": "cleaver",
        "dmg_min": 8, "dmg_max": 12, "atk_cd": 0.48, "windup": 0.08, "reach": 2.10, "arc_deg": 95.0,
        "max_targets": 3, "armor_pierce": 2, "sweet_spot": True, "knockback": 0.35, "icon": "weapon_curved"
    },
    "estoc": {
        "type": "equipment", "slot": "right_hand", "two_handed": True, "weap_style": "spear",
        "dmg_min": 7, "dmg_max": 11, "phys_def": 1, "atk_cd": 0.42, "windup": 0.05, "reach": 2.38, "arc_deg": 26.0,
        "max_targets": 3, "armor_pierce": 4, "crit_bonus": 0.08, "lunge_dist": 0.50, "knockback": 0.45, "icon": "weapon_2h"
    },
    "lucerne_hammer": {
        "type": "equipment", "slot": "right_hand", "two_handed": True, "weap_style": "halberd",
        "dmg_min": 8, "dmg_max": 12, "atk_cd": 0.52, "windup": 0.10, "reach": 2.30, "arc_deg": 75.0,
        "max_targets": 2, "armor_pierce": 2, "shatter_armor": 1, "sweet_spot": True, "status": "stun", "status_dur": 0.90, "status_chance": 0.35, "knockback": 0.55, "icon": "weapon_halberd"
    },
    "berdysh": {
        "type": "equipment", "slot": "right_hand", "two_handed": True, "weap_style": "cleaver",
        "dmg_min": 8, "dmg_max": 13, "atk_cd": 0.54, "windup": 0.12, "reach": 2.15, "arc_deg": 155.0,
        "max_targets": 99, "cleave": True, "armor_pierce": 1, "status": "poison", "status_dur": 2.8, "status_chance": 0.40, "knockback": 0.60, "icon": "weapon_halberd"
    },
    "sarissa_pike": {
        "type": "equipment", "slot": "right_hand", "two_handed": True, "weap_style": "spear",
        "dmg_min": 7, "dmg_max": 11, "atk_cd": 0.46, "windup": 0.06, "reach": 2.95, "arc_deg": 24.0,
        "max_targets": 3, "armor_pierce": 2, "sweet_spot": True, "close_penalty": True, "knockback": 0.85, "icon": "weapon_spear"
    },
    "flamberge_zweihander": {
        "type": "equipment", "slot": "right_hand", "two_handed": True, "weap_style": "cleaver",
        "dmg_min": 9, "dmg_max": 14, "phys_def": 1, "atk_cd": 0.56, "windup": 0.14, "reach": 2.30, "arc_deg": 200.0,
        "max_targets": 99, "cleave": True, "armor_pierce": 1, "lunge_dist": 0.38, "status": "poison", "status_dur": 3.2, "status_chance": 0.55, "knockback": 0.65, "icon": "weapon_flamberge"
    },
    "halberd_guard": {
        "type": "equipment", "slot": "right_hand", "two_handed": True, "weap_style": "halberd",
        "dmg_min": 8, "dmg_max": 12, "atk_cd": 0.52, "windup": 0.12, "reach": 2.25, "arc_deg": 135.0,
        "max_targets": 99, "cleave": True, "sweet_spot": True, "armor_pierce": 2, "knockback": 0.95, "icon": "weapon_halberd"
    },
    "two_handed_claymore": {
        "type": "equipment", "slot": "right_hand", "two_handed": True, "weap_style": "cleaver",
        "dmg_min": 9, "dmg_max": 14, "atk_cd": 0.56, "windup": 0.14, "reach": 2.15, "arc_deg": 160.0,
        "max_targets": 99, "cleave": True, "shatter_armor": 1, "knockback": 1.15, "icon": "weapon_2h"
    },
    "reaper_scythe": {
        "type": "equipment", "slot": "right_hand", "two_handed": True, "weap_style": "cleaver",
        "dmg_min": 8, "dmg_max": 13, "atk_cd": 0.54, "windup": 0.12, "reach": 2.25, "arc_deg": 180.0,
        "max_targets": 99, "cleave": True, "life_steal": 1, "status": "poison", "status_dur": 2.8, "status_chance": 0.40, "mag_bonus": 2, "knockback": 0.85, "icon": "weapon_2h"
    },

    # МЕТАТЕЛЬНОЕ ОРУЖИЕ 
    "balearic_sling": {
        "type": "equipment", "slot": "right_hand", "two_handed": False, "weap_style": "thrown",
        "dmg_min": 3, "dmg_max": 5, "atk_cd": 0.38, "reach": 5.5, "proj_visual": "sling_stone",
        "proj_speed": 11.5, "color": [200, 208, 220], "armor_pierce": 1, "status": "stun",
        "status_dur": 0.65, "status_chance": 0.30, "knockback": 0.40, "icon": "weapon_sling"
    },
    "plumbata": {
        "type": "equipment", "slot": "right_hand", "two_handed": False, "weap_style": "thrown",
        "dmg_min": 3, "dmg_max": 5, "atk_cd": 0.40, "reach": 5.2, "proj_visual": "thrown_javelin",
        "proj_speed": 10.8, "color": [210, 220, 235], "armor_pierce": 2, "crit_bonus": 0.12, "knockback": 0.25, "icon": "weapon_thrown_jav"
    },
    "roman_pilum": {
        "type": "equipment", "slot": "right_hand", "two_handed": False, "weap_style": "thrown",
        "dmg_min": 4, "dmg_max": 7, "atk_cd": 0.54, "reach": 5.4, "proj_visual": "thrown_javelin",
        "proj_speed": 9.6, "color": [225, 210, 175], "armor_pierce": 2, "shatter_armor": 1, "status": "slow", "status_dur": 3.0, "status_chance": 0.85, "knockback": 0.50, "icon": "weapon_thrown_jav"
    },
    "hunting_bolas": {
        "type": "equipment", "slot": "right_hand", "two_handed": False, "weap_style": "thrown",
        "dmg_min": 2, "dmg_max": 4, "atk_cd": 0.50, "reach": 5.0, "proj_visual": "thrown_bolas",
        "proj_speed": 8.8, "color": [185, 165, 130], "status": "root", "status_dur": 2.0, "status_chance": 0.35, "knockback": 0.10, "icon": "weapon_bolas"
    },
    "francisca_axe": {
        "type": "equipment", "slot": "right_hand", "two_handed": False, "weap_style": "thrown",
        "dmg_min": 4, "dmg_max": 7, "atk_cd": 0.48, "reach": 5.0, "proj_visual": "thrown_axe",
        "proj_speed": 9.4, "color": [235, 195, 120], "armor_pierce": 1, "bounces": 1, "knockback": 0.45, "icon": "weapon_thrown_axe"
    },
    "steel_chakram": {
        "type": "equipment", "slot": "right_hand", "two_handed": False, "weap_style": "thrown",
        "dmg_min": 3, "dmg_max": 5, "atk_cd": 0.42, "reach": 5.8, "proj_visual": "thrown_chakram",
        "proj_speed": 11.2, "color": [155, 235, 255], "armor_pierce": 1, "crit_bonus": 0.08, "bounces": 2, "status": "poison", "status_dur": 2.2, "status_chance": 0.45, "knockback": 0.20, "icon": "weapon_chakram"
    },
    "hunga_munga": {
        "type": "equipment", "slot": "right_hand", "two_handed": False, "weap_style": "thrown",
        "dmg_min": 3, "dmg_max": 6, "atk_cd": 0.46, "reach": 5.4, "proj_visual": "thrown_axe",
        "proj_speed": 10.4, "color": [255, 165, 75], "armor_pierce": 1, "crit_bonus": 0.10, "bounces": 1, "life_steal": 1, "status": "poison", "status_dur": 2.4, "status_chance": 0.50, "knockback": 0.35, "icon": "weapon_thrown_axe"
    },

    # ШЛЕМЫ, КАПЮШОНЫ И ВЕНЦЫ
    "tattered_hood": {
        "type": "equipment", "slot": "helmet", "mag_def": 1, "vision_bonus": 16,
        "dodge_bonus": 0.03, "noise_mod": -0.15, "icon": "helm_hood"
    },
    "iron_sallet": {
        "type": "equipment", "slot": "helmet", "phys_def": 2, "hp_bonus": 5,
        "vision_bonus": -4, "noise_mod": 0.10, "icon": "helm_sallet"
    },
    "crown_of_ashes": {
        "type": "equipment", "slot": "helmet", "mag_bonus": 2, "mag_def": 2,
        "vision_bonus": 18, "glow_radius": 48, "glow_color": [1.10, 0.52, 0.28], "icon": "helm_crown"
    },
    "kettle_hat": {
        "type": "equipment", "slot": "helmet", "phys_def": 2, "mag_def": 1,
        "vision_bonus": 6, "noise_mod": 0.05, "icon": "helm_kettle"
    },
    "padded_coif": {
        "type": "equipment", "slot": "helmet", "phys_def": 1, "hp_bonus": 8,
        "noise_mod": -0.05, "icon": "helm_coif"
    },
    "bone_mask": {
        "type": "equipment", "slot": "helmet", "crit_bonus": 0.05, "mag_bonus": 1,
        "noise_mod": -0.10, "icon": "helm_mask"
    },
    "scholar_circlet": {
        "type": "equipment", "slot": "helmet", "mp_bonus": 4, "mana_received_bonus": 0.16,
        "vision_bonus": 12, "icon": "helm_circlet"
    },
    "horned_bascinet": {
        "type": "equipment", "slot": "helmet", "phys_def": 2, "phys_bonus": 2,
        "noise_mod": 0.16, "icon": "helm_bascinet"
    },
    "lantern_cap": {
        "type": "equipment", "slot": "helmet", "phys_def": 1, "vision_bonus": 24,
        "glow_radius": 52, "glow_color": [1.05, 0.82, 0.45], "icon": "helm_miner"
    },

    # НАГРУДНИКИ, КУРТКИ И МАНТИИ
    "cloth_tunic": {
        "type": "equipment", "slot": "torso", "armor_class": "cloth", "phys_def": 1,
        "mag_def": 2, "mp_bonus": 3, "noise_mod": -0.20, "icon": "armor_robe"
    },
    "leather_brigandine": {
        "type": "equipment", "slot": "torso", "armor_class": "leather", "phys_def": 2,
        "mag_def": 1, "dodge_bonus": 0.04, "noise_mod": -0.05, "icon": "armor_brigandine"
    },
    "knight_cuirass": {
        "type": "equipment", "slot": "torso", "armor_class": "plate", "phys_def": 4,
        "hp_bonus": 8, "speed_bonus": -0.04, "noise_mod": 0.35, "icon": "armor_cuirass"
    },
    "shadowweave_cloak": {
        "type": "equipment", "slot": "torso", "armor_class": "cloth", "phys_def": 1,
        "mag_def": 2, "dodge_bonus": 0.05, "vision_bonus": 14, "noise_mod": -0.35, "icon": "armor_cloak"
    },
    "padded_gambeson": {
        "type": "equipment", "slot": "torso", "armor_class": "leather", "phys_def": 2,
        "hp_bonus": 10, "heal_received_bonus": 0.14, "noise_mod": -0.05, "icon": "armor_gambeson"
    },
    "pack_jerkin": {
        "type": "equipment", "slot": "torso", "armor_class": "leather", "phys_def": 1,
        "extra_slots_per_tier": 1, "speed_bonus": 0.03, "noise_mod": 0.05, "icon": "armor_jerkin"
    },
    "scale_hauberk": {
        "type": "equipment", "slot": "torso", "armor_class": "plate", "phys_def": 3,
        "mag_def": 2, "noise_mod": 0.20, "icon": "armor_scale"
    },
    "alchemist_coat": {
        "type": "equipment", "slot": "torso", "armor_class": "cloth", "phys_def": 1,
        "mag_def": 2, "mana_received_bonus": 0.16, "extra_slots_per_tier": 1, "icon": "armor_coat"
    },
    "duelist_doublet": {
        "type": "equipment", "slot": "torso", "armor_class": "leather", "phys_def": 2,
        "crit_bonus": 0.05, "speed_bonus": 0.05, "noise_mod": -0.15, "icon": "armor_doublet"
    },

    # САПОГИ И ПОНОЖИ
    "plated_greaves": {
        "type": "equipment", "slot": "boots", "phys_def": 2, "hp_bonus": 5,
        "noise_mod": 0.15, "icon": "boots_greaves"
    },
    "silent_moccasins": {
        "type": "equipment", "slot": "boots", "phys_def": 1, "dodge_bonus": 0.04,
        "noise_mod": -0.30, "icon": "boots_soft"
    },
    "courier_boots": {
        "type": "equipment", "slot": "boots", "phys_def": 1, "speed_bonus": 0.08,
        "noise_mod": -0.05, "icon": "boots_courier"
    },
    "iron_sabatons": {
        "type": "equipment", "slot": "boots", "phys_def": 2, "phys_bonus": 1,
        "mag_def": 1, "noise_mod": 0.20, "icon": "boots_sabatons"
    },
    "swamp_waders": {
        "type": "equipment", "slot": "boots", "phys_def": 1, "mag_def": 1,
        "heal_received_bonus": 0.14, "speed_bonus": 0.04, "icon": "boots_waders"
    },
    "ritual_sandals": {
        "type": "equipment", "slot": "boots", "mag_def": 2, "mana_received_bonus": 0.16,
        "noise_mod": -0.10, "icon": "boots_sandals"
    },
    "spurred_boots": {
        "type": "equipment", "slot": "boots", "phys_def": 1, "crit_bonus": 0.04,
        "speed_bonus": 0.05, "noise_mod": 0.10, "icon": "boots_spurred"
    },

    # КОЛЬЦА И ПЕЧАТКИ
    "ring_cat_eye": {
        "type": "equipment", "slot": "ring", "vision_bonus": 24, "crit_bonus": 0.04, "icon": "ring_amber"
    },
    "ring_blood_pact": {
        "type": "equipment", "slot": "ring", "phys_bonus": 1, "mag_bonus": 1, "life_steal": 1, "icon": "ring_blood"
    },
    "ring_iron_band": {
        "type": "equipment", "slot": "ring", "phys_def": 1, "hp_bonus": 8, "icon": "ring_iron"
    },
    "ring_ether_loop": {
        "type": "equipment", "slot": "ring", "mp_bonus": 4, "mana_received_bonus": 0.18, "icon": "ring_sapphire"
    },
    "ring_quicksilver": {
        "type": "equipment", "slot": "ring", "speed_bonus": 0.06, "dodge_bonus": 0.04, "icon": "ring_silver"
    },
    "ring_ember_signet": {
        "type": "equipment", "slot": "ring", "mag_bonus": 2, "glow_radius": 42,
        "glow_color": [1.10, 0.58, 0.24], "icon": "ring_ember"
    },
    "ring_bone_knuckle": {
        "type": "equipment", "slot": "ring", "phys_bonus": 2, "crit_bonus": 0.03, "icon": "ring_bone"
    },
    "ring_moss_stone": {
        "type": "equipment", "slot": "ring", "heal_received_bonus": 0.18, "mag_def": 1, "icon": "ring_emerald"
    },
    "ring_shadow_glass": {
        "type": "equipment", "slot": "ring", "noise_mod": -0.22, "dodge_bonus": 0.05, "icon": "ring_onyx"
    },

    # АМУЛЕТЫ И ТАЛИСМАНЫ
    "trinket_ancient_eye": {
        "type": "equipment", "slot": "trinket", "mag_bonus": 2, "vision_bonus": 26,
        "glow_radius": 46, "glow_color": [0.55, 0.85, 1.10], "icon": "trinket_eye"
    },
    "trinket_iron_heart": {
        "type": "equipment", "slot": "trinket", "hp_bonus": 12, "phys_def": 1,
        "heal_received_bonus": 0.16, "icon": "trinket_heart"
    },
    "trinket_lucky_tooth": {
        "type": "equipment", "slot": "trinket", "crit_bonus": 0.06, "dodge_bonus": 0.04,
        "speed_bonus": 0.04, "icon": "trinket_fang"
    },
    "trinket_mana_prism": {
        "type": "equipment", "slot": "trinket", "mag_bonus": 2, "mp_bonus": 5,
        "mana_received_bonus": 0.16, "icon": "trinket_prism"
    },
    "trinket_ward_bell": {
        "type": "equipment", "slot": "trinket", "mag_def": 2, "phys_def": 1,
        "noise_mod": 0.12, "icon": "trinket_bell"
    },
    "trinket_smuggler_buckle": {
        "type": "equipment", "slot": "trinket", "extra_slots_per_tier": 1,
        "noise_mod": -0.15, "icon": "trinket_buckle"
    },
    "trinket_war_trophy": {
        "type": "equipment", "slot": "trinket", "phys_bonus": 2, "hp_bonus": 6, "icon": "trinket_medal"
    },
    "trinket_glow_jar": {
        "type": "equipment", "slot": "trinket", "vision_bonus": 22, "mana_received_bonus": 0.14,
        "glow_radius": 62, "glow_color": [0.75, 1.05, 0.45], "icon": "trinket_jar"
    },

    # РАСХОДНИКИ, СВИТКИ И СУМКИ
    "potion_hp": {"type": "consumable", "power": 15, "cooldown": 1.0, "icon": "potion_red"},
    "potion_mp": {"type": "consumable", "power": 14, "cooldown": 1.0, "icon": "potion_blue"},
    "scroll_spark": {"type": "consumable_spell", "cast_type": "beam", "status": "stun", "status_dur": 1.5, "cooldown": 1.2, "power": 10, "color": [90, 235, 255], "icon": "skill_zap"},
    "scroll_fireball": {"type": "consumable_spell", "cast_type": "aoe_cursor", "aoe_radius": 2.1, "status": "poison", "status_dur": 5.0, "cooldown": 1.5, "power": 12, "color": [110, 245, 95], "icon": "bomb"},
    "oblivion_seal": {"type": "consumable_eraser", "icon": "trinket"},
    "family_strongbox": {"type": "bag", "slots": 1, "rarity": "legendary", "icon": "bag_strongbox", "bag_filter": "any", "locked_bag": True},
    **{
        item_id: {
            "type": "bag",
            "slots": BAG_CAPACITIES[item_id],
            "rarity": rarity,
            "icon": icon,
            "bag_filter": bag_filter,
        }
        for item_id, rarity, icon, bag_filter in (
            ("small_pouch", "common", "bag_small", "any"),
            ("waxed_pouch", "common", "bag_waxed", "any"),
            ("pouch_bag", "uncommon", "bag_leather", "any"),
            ("reed_satchel", "uncommon", "bag_reed", "any"),
            ("scout_satchel", "rare", "bag_scout", "any"),
            ("frame_pack", "rare", "bag_frame", "any"),
            ("travel_backpack", "epic", "bag_big", "any"),
            ("void_chest_bag", "legendary", "bag_void", "any"),
            ("velvet_gem_pouch", "common", "bag_gem_velvet", "treasure"),
            ("jeweler_satchel", "uncommon", "bag_gem_satchel", "treasure"),
            ("antiquary_case", "rare", "bag_gem_case", "treasure"),
            ("collector_trunk", "epic", "bag_gem_trunk", "treasure"),
            ("treasury_vault_bag", "legendary", "bag_gem_vault", "treasure"),
            ("herb_belt", "common", "bag_belt_herb", "consumable"),
            ("alchemist_bandolier", "uncommon", "bag_belt_alch", "consumable"),
            ("apothecary_rig", "rare", "bag_belt_apoth", "consumable"),
            ("master_bandolier", "epic", "bag_belt_master", "consumable"),
        )
    },
}
