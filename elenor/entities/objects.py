



SOLID_INTERACTABLE_KINDS = {
    "merchant_counter", "merchant_shelves", "merchant_goods",
    "tavern_table", "bar_counter", "wine_cask", "bed", "fireplace",
    "shelf_bottles", "cauldron", "crate_stack", "grandfather_clock",
    "wash_basin", "meat_rack", "firewood_pile", "armor_stand",
    "tree_stump", "hollow_log", "jungle_boulder",
    "bamboo_clump", "banana_plant", "termite_mound", "crystal_cluster",
    "cave_stalagmite", "ancient_waystone", "giant_stone_head",
    "tribal_totem", "tribal_table", "tribal_bed", "tribal_hammock",
    "tribal_rack", "tribal_bow_stand", "tribal_drum", "tribal_skull_pole",
    "shaman_cauldron", "fish_drying_rack", "skull_brazier", "blowgun_trap",
    "bamboo_cage", "tribal_mask_shield", "shaman_gong",
    "marble_pillar", "marble_pillar_broken", "marble_altar", "marble_brazier",
    "marble_statue", "serpent_statue", "sun_gong", "marble_bench",
    "marble_lectern", "incense_burner", "marble_obelisk", "temple_sundial",
    "holy_fire_bowl", "fallen_colossus", "marble_fountain", "marble_sarcophagus",
}


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
