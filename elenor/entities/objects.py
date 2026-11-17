



SOLID_INTERACTABLE_KINDS = {
    "merchant_counter", "merchant_shelves", "merchant_goods",
    "tavern_table", "bar_counter", "wine_cask", "bed", "fireplace",
    "shelf_bottles", "cauldron", "crate_stack", "grandfather_clock",
    "wash_basin", "meat_rack", "firewood_pile", "armor_stand",
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
