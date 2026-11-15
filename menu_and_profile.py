import json
import math
import os
import random
import pygame
from config import (
    SCREEN_W, SCREEN_H, UI_BG_DARK, UI_PANEL_BG, UI_SLOT_BG,
    UI_BORDER_OUTER, UI_BORDER_WOOD, UI_BORDER_GOLD, UI_BORDER_HIGHLIGHT,
    UI_TEXT_MAIN, UI_TEXT_DIM
)
from studio_core import quantize_normal_surface, flip_normal_pair_x, LiveLightPreview


def get_profile_dir():
    # Храним сейвы в системной папке пользователя (%APPDATA%/RatCellar), отдельно от кода игры!
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    save_dir = os.path.join(appdata, "RatCellar")
    os.makedirs(save_dir, exist_ok=True)
    return save_dir


def get_profile_path():
    return os.path.join(get_profile_dir(), "save_profile.json")


DEFAULT_PROFILE = {
    "bank_copper": 0,
    "rat_king_defeated": False,
    "hero_type": "male",
    "skin_idx": 0,
    "head_idx": 0,
    "outfit_idx": 0,
    "volume": 0.85,
    "typewriter_mode": 1,
    "thought_freq_mode": 2,
    "fullscreen": False,
}


def load_profile():
    path = get_profile_path()
    legacy_path = os.path.join(os.path.dirname(__file__), "save_profile.json")
    prof = dict(DEFAULT_PROFILE)

    # Если в папке игры остался старый сейв — аккуратно переносим его в AppData
    if not os.path.isfile(path) and os.path.isfile(legacy_path):
        try:
            with open(legacy_path, "r", encoding="utf-8") as f:
                prof.update(json.load(f))
            save_profile(prof)
        except Exception:
            pass

    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                prof.update(data)
        except Exception:
            pass
    return prof


def save_profile(prof):
    path = get_profile_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(prof, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def reset_profile_progress(prof):
    # Сбрасывает весь игровой прогресс (золото, открытых персонажей), сохраняя базовые настройки звука и экрана
    vol = prof.get("volume", 0.85)
    tw = prof.get("typewriter_mode", 1)
    tf = prof.get("thought_freq_mode", 2)
    fs = prof.get("fullscreen", False)
    prof.clear()
    prof.update(DEFAULT_PROFILE)
    prof["volume"] = vol
    prof["typewriter_mode"] = tw
    prof["thought_freq_mode"] = tf
    prof["fullscreen"] = fs
    save_profile(prof)


def format_copper_Trigger(total_cp, compact=False):
    total_cp = int(max(0, total_cp))
    pp = total_cp // 1000
    rem = total_cp % 1000
    gp = rem // 100
    rem = rem % 100
    sp = rem // 10
    cp = rem % 10
    if compact:
        if pp > 0:
            return f"{pp}пм {gp}зм"
        if gp > 0:
            return f"{gp}зм {sp}см"
        if sp > 0:
            return f"{sp}см {cp}мм"
        return f"{cp}мм"
    parts = []
    if pp > 0:
        parts.append(f"{pp}пм")
    if gp > 0:
        parts.append(f"{gp}зм")
    if sp > 0:
        parts.append(f"{sp}см")
    if cp > 0 or not parts:
        parts.append(f"{cp}мм")
    return ", ".join(parts)


CURRENCY_AND_GEMS_DB = {
    "coin_copper": {
        "name": "Медные монеты",
        "type": "currency_coin",
        "rarity": "common",
        "icon": "coin_copper",
        "copper_value": 6,
        "desc": "\"Пахнут крысиной шерстью и дешёвым пивом.\""
    },
    "coin_silver": {
        "name": "Серебряные монеты",
        "type": "currency_coin",
        "rarity": "uncommon",
        "icon": "coin_silver",
        "copper_value": 25,
        "desc": "\"Приятно холодят ладонь. На кружку эля точно хватит.\""
    },
    "coin_gold": {
        "name": "Золотые монеты",
        "type": "currency_coin",
        "rarity": "rare",
        "icon": "coin_gold",
        "copper_value": 120,
        "desc": "\"Попробовал на зуб — вроде не крашеный свинец!\""
    },
    "coin_platinum": {
        "name": "Платиновые монеты",
        "type": "currency_coin",
        "rarity": "epic",
        "icon": "coin_platinum",
        "copper_value": 1000,
        "desc": "\"За такую монетку в порту перережут глотку дважды.\""
    },
    "gem_malachite": {
        "name": "Узорчатый малахит",
        "type": "gem",
        "rarity": "common",
        "icon": "gem_green",
        "copper_value": 45,
        "desc": "\"Надеюсь, это не стёклышко от пивной бутылки...\""
    },
    "gem_garnet": {
        "name": "Кровавый гранат",
        "type": "gem",
        "rarity": "uncommon",
        "icon": "gem_red",
        "copper_value": 145,
        "desc": "\"Смахивает на замёрзшую каплю вишнёвой наливки.\""
    },
    "gem_sapphire": {
        "name": "Сапфир Стратоса",
        "type": "gem",
        "rarity": "rare",
        "icon": "gem_blue",
        "copper_value": 380,
        "desc": "\"Холодный, как взгляд трактирщика, когда просишь в долг.\""
    },
    "gem_ruby": {
        "name": "Огненный рубин Пиро",
        "type": "gem",
        "rarity": "epic",
        "icon": "gem_orange",
        "copper_value": 950,
        "desc": "\"Греет карман лучше печки. Главное — штаны не прожечь.\""
    },
    "gem_diamond": {
        "name": "Чёрный алмаз Персефоны",
        "type": "gem",
        "rarity": "legendary",
        "icon": "gem_purple",
        "copper_value": 2500,
        "desc": "\"Смотришь в грани — а оттуда на тебя смотрит пенсия.\""
    },
    # Разные виды лечебных средств (для универсального хила и Ипохондрика)
    "potion_hp_weak": {
        "name": "Разбавленный отвар",
        "type": "consumable",
        "rarity": "common",
        "icon": "potion_red",
        "heal_hp": 8,
        "power": 8,
        "cooldown": 1.2,
        "desc": "Мутная микстура на коре дуба. Восстанавливает 8 ХП."
    },
    "herbal_salve": {
        "name": "Травяная припарка",
        "type": "consumable",
        "rarity": "common",
        "icon": "potion_red",
        "heal_hp": 11,
        "power": 11,
        "cooldown": 1.4,
        "desc": "Пахучая мазь из подземного мха. Восстанавливает 11 ХП."
    },
    "potion_hp_strong": {
        "name": "Густой эликсир жизни",
        "type": "consumable",
        "rarity": "rare",
        "icon": "potion_red",
        "heal_hp": 26,
        "power": 26,
        "cooldown": 1.8,
        "desc": "Алхимический концентрат. Восстанавливает 26 ХП."
    }
}


HERO_TYPES_ORDER = ["male", "female", "ratfolk"]

HERO_CUSTOMIZATION_DB = {
    "male": {
        "title": "Мужской",
        "skins": [
            ("Телесный", (225, 185, 155), (185, 145, 118)),
            ("Бледный северный", (240, 215, 200), (198, 170, 155)),
            ("Смуглый южный", (188, 138, 102), (148, 104, 74)),
            ("Оливковый степной", (195, 168, 128), (155, 130, 96)),
            ("Пепельный проклятый", (165, 160, 172), (125, 120, 132)),
        ],
        "heads": [
            ("Короткий ёжик", (95, 65, 45)),
            ("Густая борода", (115, 72, 38)),
            ("Светлые патлы", (215, 180, 95)),
            ("Шрам и лысина", None),
            ("Седой ветеран", (185, 190, 200)),
        ],
    },
    "female": {
        "title": "Женский",
        "skins": [
            ("Телесный", (232, 192, 162), (192, 150, 124)),
            ("Бледный северный", (244, 220, 206), (204, 176, 162)),
            ("Смуглый южный", (194, 144, 108), (154, 108, 78)),
            ("Оливковый степной", (200, 174, 134), (160, 136, 100)),
            ("Пепельный проклятый", (172, 166, 180), (132, 126, 140)),
        ],
        "heads": [
            ("Длинная коса", (135, 58, 42)),
            ("Высокий хвост", (75, 52, 38)),
            ("Серебряное каре", (210, 218, 230)),
            ("Золотая диадема", (205, 165, 75)),
            ("Боевой ирокез", (175, 45, 65)),
        ],
    },
    "ratfolk": {
        "title": "Крысолюд",
        "skins": [
            ("Погребной серый", (118, 105, 98), (84, 74, 68), (245, 55, 55)),
            ("Белый альбинос", (235, 228, 225), (190, 180, 178), (255, 35, 65)),
            ("Ржаво-бурый", (142, 88, 54), (102, 60, 36), (255, 195, 50)),
            ("Капюшонный пегий", (195, 182, 168), (78, 68, 64), (240, 70, 50)),
            ("Сажевый чёрный", (56, 52, 60), (36, 33, 40), (255, 215, 55)),
        ],
        "heads": [
            ("Круглые уши", "ears_normal"),
            ("Рваное ухо и шрам", "ears_torn"),
            ("Повязка на глаз", "eyepatch"),
            ("Костяной венец", "bone_crown"),
            ("Капюшон изгоя", "hood"),
        ],
    },
    "outfits": [
        ("Рубаха вольника", "tunic"),
        ("Рваные лохмотья", "rags"),
        ("Дорожный плащ", "cloak"),
        ("Ряса послушника", "robe"),
    ]
}


def build_custom_hero_sprite(
    cloak_color=(200, 70, 75),
    armor_class="none",
    has_helmet=False,
    has_torch=True,
    has_weapon=False,
    hero_type="male",
    skin_idx=0,
    head_idx=0,
    outfit_idx=0,
    anim_frame=0,
    is_moving=False,
):
    h_diff = pygame.Surface((16, 20), pygame.SRCALPHA)
    h_norm = pygame.Surface((16, 20), pygame.SRCALPHA)
    h_norm.fill((128, 128, 255, 0))

    if hero_type not in HERO_CUSTOMIZATION_DB:
        hero_type = "male"
    type_db = HERO_CUSTOMIZATION_DB[hero_type]
    skins = type_db["skins"]
    heads = type_db["heads"]
    outfits = HERO_CUSTOMIZATION_DB["outfits"]

    skin_tuple = skins[skin_idx % len(skins)]
    skin_main, skin_dark = skin_tuple[1], skin_tuple[2]
    eye_col = skin_tuple[3] if len(skin_tuple) > 3 else (25, 30, 40)
    _, head_style = heads[head_idx % len(heads)]
    _, outfit_style = outfits[outfit_idx % len(outfits)]

    cr, cg, cb = cloak_color
    cloak_dark = (max(15, cr - 45), max(15, cg - 45), max(15, cb - 45))
    cloak_bright = (min(255, cr + 25), min(255, cg + 25), min(255, cb + 25))

    if armor_class == "plate":
        chest_col = (190, 200, 215)
        chest_dark = (135, 145, 162)
    elif armor_class == "leather":
        chest_col = (145, 95, 55)
        chest_dark = (105, 68, 38)
    elif armor_class == "cloth":
        chest_col = (max(20, cr - 25), max(20, cg - 25), max(20, cb - 25))
        chest_dark = cloak_dark
    else:
        if outfit_style == "tunic":
            chest_col = (165, 138, 108)
            chest_dark = (122, 98, 74)
        elif outfit_style == "rags":
            chest_col = (128, 112, 96)
            chest_dark = (88, 76, 64)
        elif outfit_style == "cloak":
            chest_col = cloak_color
            chest_dark = cloak_dark
        else:
            chest_col = (72, 68, 86)
            chest_dark = (48, 44, 60)

    bob_y = 0
    l_leg_dy = 0
    r_leg_dy = 0
    tail_wag = 0
    if is_moving:
        step_phase = anim_frame % 4
        if step_phase == 1:
            bob_y = 1
            l_leg_dy = -1
            tail_wag = -1
        elif step_phase == 3:
            bob_y = 1
            r_leg_dy = -1
            tail_wag = 1
    else:
        if (anim_frame % 2) == 1:
            bob_y = 1
            tail_wag = 1

    # 1. Хвост Крысолюда (сзади справа у ног)
    if hero_type == "ratfolk":
        tail_pts = [(11, 15), (12, 16), (13, 16 + tail_wag), (14, 15 + tail_wag)]
        for tx, ty in tail_pts:
            if 0 <= tx < 16 and 0 <= ty < 20:
                h_diff.set_at((tx, ty), (205, 135, 142))
                h_norm.set_at((tx, ty), (190, 195, 195, 255))

    # 2. Торс и одеяние (y = 8..15)
    is_female = (hero_type == "female")
    for y in range(8 + bob_y, 16):
        for x in range(4, 12):
            if is_female and y in (11, 12) and x in (4, 11) and outfit_style != "cloak":
                continue
            if outfit_style == "rags" and ((x == 4 and y >= 13) or (x == 11 and y == 15)):
                continue

            if x in (4, 11):
                col = cloak_color if y < 14 else cloak_dark
            else:
                col = chest_col if (x + y) % 3 != 0 else chest_dark

            if armor_class == "none":
                if outfit_style == "tunic" and y == 12 and 5 <= x <= 10:
                    col = (95, 62, 36) if x != 7 else (225, 185, 75)
                elif outfit_style == "tunic" and y in (8, 9) and x in (7, 8):
                    col = skin_main
                elif outfit_style == "rags" and y in (8, 9) and x in (5, 6):
                    col = skin_main
                elif outfit_style == "cloak" and y in (8, 9) and 5 <= x <= 10:
                    col = cloak_bright if y == 8 else cloak_color
                elif outfit_style == "robe" and x in (7, 8) and 8 <= y <= 15:
                    col = cloak_bright if x == 7 else cloak_color

            nx = 45 if x <= 6 else (210 if x >= 9 else 128)
            ny = 218 if y == 8 + bob_y else 128
            h_diff.set_at((x, y), col)
            h_norm.set_at((x, y), (nx, ny, 255 if nx == 128 and ny == 128 else 200, 255))

    # Подол длинной рясы на y=16
    if armor_class == "none" and outfit_style == "robe":
        for x in range(5, 11):
            col = cloak_color if x in (7, 8) else chest_dark
            h_diff.set_at((x, 16), col)
            h_norm.set_at((x, 16), (128, 38, 200, 255))

    # 3. Ноги / сапоги (y = 16..18)
    boot_col = (70, 50, 40) if outfit_style != "rags" else skin_dark
    for lx in (5, 6):
        for ly in range(16, 19 + l_leg_dy):
            if 0 <= ly < 20:
                h_diff.set_at((lx, ly), boot_col)
                h_norm.set_at((lx, ly), (45, 128, 200, 255))
    for rx in (9, 10):
        for ry in range(16, 19 + r_leg_dy):
            if 0 <= ry < 20:
                h_diff.set_at((rx, ry), boot_col)
                h_norm.set_at((rx, ry), (210, 128, 200, 255))

    # 4. Голова (y = 2..7 + bob_y)
    hy0 = 2 + bob_y
    if has_helmet:
        for y in range(hy0, hy0 + 6):
            for x in range(5, 11):
                col = (225, 235, 245) if y <= hy0 + 1 else (180, 192, 208)
                if y == hy0 + 3 and x in (6, 9):
                    col = (25, 30, 40)
                nx = 45 if x < 7 else (210 if x > 8 else 128)
                ny = 218 if y <= hy0 + 1 else 128
                h_diff.set_at((x, y), col)
                h_norm.set_at((x, y), (nx, ny, 200, 255))
    elif hero_type == "ratfolk":
        # Уши крысолюда на макушке
        ear_places = [(5, hy0), (6, hy0), (9, hy0), (10, hy0)]
        for ex, ey in ear_places:
            if head_style == "ears_torn" and ex == 5:
                continue
            col_e = (205, 130, 138) if ex in (6, 9) else skin_main
            h_diff.set_at((ex, ey), col_e)
            h_norm.set_at((ex, ey), (128, 218, 200, 255))

        # Вытянутая мордочка крысолюда (x=3..10)
        for y in range(hy0 + 1, hy0 + 6):
            x_start = 3 if y in (hy0 + 3, hy0 + 4) else 5
            for x in range(x_start, 11):
                is_hood = (head_style == "hood" and (y <= hy0 + 2 or x >= 9))
                if is_hood:
                    col = cloak_color if y == hy0 + 1 else cloak_dark
                elif skin_idx == 3 and (y <= hy0 + 2 or x >= 8):
                    col = skin_dark
                else:
                    col = skin_main if y < hy0 + 5 else skin_dark
                nx = 45 if x <= 5 else (210 if x >= 9 else 128)
                ny = 218 if y == hy0 + 1 else 128
                h_diff.set_at((x, y), col)
                h_norm.set_at((x, y), (nx, ny, 200, 255))

        # Розовый нос на кончике морды и глаза
        h_diff.set_at((3, hy0 + 3), (230, 135, 145))
        h_norm.set_at((3, hy0 + 3), (45, 128, 200, 255))
        h_diff.set_at((6, hy0 + 3), eye_col)
        if head_style == "eyepatch":
            h_diff.set_at((6, hy0 + 3), (25, 22, 30))
            h_diff.set_at((7, hy0 + 2), (25, 22, 30))
            h_diff.set_at((8, hy0 + 2), (25, 22, 30))
        else:
            h_diff.set_at((8, hy0 + 3), eye_col)

        if head_style == "ears_torn":
            h_diff.set_at((5, hy0 + 2), (235, 195, 195))
            h_diff.set_at((5, hy0 + 3), (235, 195, 195))
        elif head_style == "bone_crown":
            for cx in range(5, 10):
                h_diff.set_at((cx, hy0 + 1), (235, 230, 210) if cx % 2 == 1 else (185, 175, 155))
    else:
        # Человеческая голова (Мужская / Женская)
        for y in range(hy0, hy0 + 6):
            for x in range(5, 11):
                col = skin_main if y < hy0 + 5 else skin_dark
                if head_style is not None and y <= hy0 + 1:
                    col = head_style
                if y == hy0 + 3 and x in (6, 9):
                    col = eye_col
                nx = 45 if x < 7 else (210 if x > 8 else 128)
                ny = 218 if y <= hy0 + 1 else 128
                h_diff.set_at((x, y), col)
                h_norm.set_at((x, y), (nx, ny, 200, 255))

        # Детали причёсок
        if hero_type == "male":
            if head_idx == 1 and head_style:  # Густая борода
                for bx in range(5, 11):
                    h_diff.set_at((bx, hy0 + 4), head_style)
                    h_diff.set_at((bx, hy0 + 5), head_style)
                for bx in range(6, 10):
                    h_diff.set_at((bx, hy0 + 6), head_style)
            elif head_idx == 2 and head_style:  # Длинные патлы по бокам
                for py in range(hy0 + 1, hy0 + 5):
                    h_diff.set_at((4, py), head_style)
                    h_diff.set_at((11, py), head_style)
            elif head_idx == 3:  # Шрам на лбу/щеке
                h_diff.set_at((8, hy0 + 1), (190, 95, 95))
                h_diff.set_at((8, hy0 + 2), (190, 95, 95))
        elif hero_type == "female":
            if head_style:
                for py in range(hy0 + 1, hy0 + 6):
                    h_diff.set_at((11, py), head_style)
                if head_idx in (0, 2):  # Длинная коса / каре
                    h_diff.set_at((4, hy0 + 2), head_style)
                    h_diff.set_at((4, hy0 + 3), head_style)
                    h_diff.set_at((11, hy0 + 6), head_style)

    # 5. Факел в левой руке (справа на спрайте, древко строго вертикальное на x=13!)
    if has_torch:
        for y in range(8 + bob_y, 12 + bob_y):
            if 0 <= y < 20:
                h_diff.set_at((13, y), (120, 80, 45))
                h_norm.set_at((13, y), (210, 128, 200, 255))
        # Ядро пламени строго над древком + живой верхний язычок огня
        fy_core = 7 + bob_y
        fy_tip = 6 + bob_y
        if 0 <= fy_core < 20:
            h_diff.set_at((13, fy_core), (255, 145, 40) if (anim_frame % 2 == 0) else (255, 180, 55))
            h_norm.set_at((13, fy_core), (210, 218, 200, 255))
        if 0 <= fy_tip < 20:
            h_diff.set_at((13, fy_tip), (255, 235, 110) if (anim_frame % 2 == 0) else (255, 195, 65))
            h_norm.set_at((13, fy_tip), (128, 218, 200, 255))
        if (anim_frame % 2 == 1) and 0 <= fy_tip - 1 < 20:
            h_diff.set_at((13, fy_tip - 1), (245, 120, 35))
            h_norm.set_at((13, fy_tip - 1), (128, 218, 200, 255))

    # 6. Оружие в правой руке (слева на спрайте)
    if has_weapon:
        for y in range(4 + bob_y, 13 + bob_y):
            if 0 <= y < 20:
                col = (205, 215, 230) if y < 11 + bob_y else (140, 95, 45)
                h_diff.set_at((2, y), col)
                h_norm.set_at((2, y), (45, 218, 200, 255))

    quantize_normal_surface(h_norm, h_diff)
    return h_diff, h_norm


class MainMenuController:
    def __init__(self, game):
        self.game = game
        self.active_tab = 0
        self.scroll_x = 0.0
        self.preview_3d = LiveLightPreview(200, 240)
        self.preview_walk = False
        self.preview_cloak_color = [200, 70, 75]
        self.anim_timer = 0.0
        self.anim_frame = 0
        self.meltdown_timer = 0.0
        self.meltdown_active = False
        self.confirm_reset_timer = 0.0

        self.nav_rects = [pygame.Rect(42, 180 + i * 74, 224, 56) for i in range(4)]
        self.btn_rects = {}

    def sync_audio_and_display(self):
        prof = self.game.profile
        if hasattr(self.game, "sfx") and self.game.sfx:
            self.game.sfx.set_volume(prof.get("volume", 0.85))

    def handle_event(self, event, mouse_pos):
        prof = self.game.profile

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE and self.meltdown_active:
                self.meltdown_active = False
                self.active_tab = 0
                return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # 1. Клик по левому сайдбару
            for i, nr in enumerate(self.nav_rects):
                if nr.collidepoint(mouse_pos):
                    self.active_tab = i
                    self.game.sfx.play("ui")
                    if i == 3:
                        self.meltdown_active = True
                        self.meltdown_timer = 0.0
                        self.game.sfx.play("cpu_meltdown")
                    else:
                        self.meltdown_active = False
                    return True

            # 2. Кнопки внутри текущей открытой вкладки (когда карусель доехала)
            if abs(self.scroll_x - self.active_tab * 840.0) > 120.0:
                return True

            for b_key, b_rect in self.btn_rects.items():
                if b_rect.collidepoint(mouse_pos):
                    self._trigger_button(b_key, prof)
                    return True

        return False

    def _trigger_button(self, b_key, prof):
        self.game.sfx.play("ui")
        h_type = prof.get("hero_type", "male")

        if b_key == "type_prev":
            idx = (HERO_TYPES_ORDER.index(h_type) - 1) % len(HERO_TYPES_ORDER)
            new_t = HERO_TYPES_ORDER[idx]
            if new_t == "ratfolk" and not prof.get("rat_king_defeated", False):
                self.game.sfx.play("hurt")
                return
            prof["hero_type"] = new_t
            prof["skin_idx"] = 0
            prof["head_idx"] = 0
            save_profile(prof)

        elif b_key == "type_next":
            idx = (HERO_TYPES_ORDER.index(h_type) + 1) % len(HERO_TYPES_ORDER)
            new_t = HERO_TYPES_ORDER[idx]
            if new_t == "ratfolk" and not prof.get("rat_king_defeated", False):
                self.game.sfx.play("hurt")
                return
            prof["hero_type"] = new_t
            prof["skin_idx"] = 0
            prof["head_idx"] = 0
            save_profile(prof)

        elif b_key == "unlock_ratfolk_dev":
            prof["rat_king_defeated"] = True
            prof["hero_type"] = "ratfolk"
            save_profile(prof)
            self.game.sfx.play("levelup")

        elif b_key in ("skin_prev", "skin_next"):
            skins = HERO_CUSTOMIZATION_DB[h_type]["skins"]
            step = -1 if b_key.endswith("prev") else 1
            prof["skin_idx"] = (prof.get("skin_idx", 0) + step) % len(skins)
            save_profile(prof)

        elif b_key in ("head_prev", "head_next"):
            heads = HERO_CUSTOMIZATION_DB[h_type]["heads"]
            step = -1 if b_key.endswith("prev") else 1
            prof["head_idx"] = (prof.get("head_idx", 0) + step) % len(heads)
            save_profile(prof)

        elif b_key in ("outfit_prev", "outfit_next"):
            outfits = HERO_CUSTOMIZATION_DB["outfits"]
            step = -1 if b_key.endswith("prev") else 1
            prof["outfit_idx"] = (prof.get("outfit_idx", 0) + step) % len(outfits)
            save_profile(prof)

        elif b_key == "toggle_preview_walk":
            self.preview_walk = not self.preview_walk

        elif b_key == "roll_preview_color":
            adjs = list(self.game.loc.get("adjectives", {}).values())
            if adjs:
                self.preview_cloak_color = list(random.choice(adjs).get("color", [200, 70, 75]))

        elif b_key == "start_run":
            self.game.in_main_menu = False
            self.game.reset_run()

        elif b_key == "vol_down":
            prof["volume"] = round(max(0.0, prof.get("volume", 0.85) - 0.10), 2)
            save_profile(prof)
            self.sync_audio_and_display()

        elif b_key == "vol_up":
            prof["volume"] = round(min(1.0, prof.get("volume", 0.85) + 0.10), 2)
            save_profile(prof)
            self.sync_audio_and_display()

        elif b_key == "speed_cycle":
            prof["typewriter_mode"] = (prof.get("typewriter_mode", 1) + 1) % 3
            save_profile(prof)

        elif b_key in ("freq_prev", "freq_next"):
            step = -1 if b_key.endswith("prev") else 1
            prof["thought_freq_mode"] = (prof.get("thought_freq_mode", 2) + step) % 4
            save_profile(prof)

        elif b_key == "fullscreen_toggle":
            prof["fullscreen"] = not prof.get("fullscreen", False)
            save_profile(prof)
            flags = pygame.FULLSCREEN if prof["fullscreen"] else 0
            try:
                pygame.display.set_mode((SCREEN_W, SCREEN_H), flags, vsync=1)
            except Exception:
                pygame.display.set_mode((SCREEN_W, SCREEN_H), flags)

        elif b_key == "reset_progress":
            if self.confirm_reset_timer <= 0.0:
                self.confirm_reset_timer = 4.0
                self.game.sfx.play("alert")
            else:
                self.confirm_reset_timer = 0.0
                reset_profile_progress(prof)
                self.game.reset_run()
                self.game.sfx.play("crit")

        elif b_key == "cancel_meltdown":
            self.meltdown_active = False
            self.active_tab = 0

        elif b_key == "quit_now":
            pygame.quit()
            raise SystemExit

    def update(self, dt):
        target_x = self.active_tab * 840.0
        self.scroll_x += (target_x - self.scroll_x) * min(1.0, 12.0 * dt)
        self.confirm_reset_timer = max(0.0, self.confirm_reset_timer - dt)

        self.anim_timer += dt
        fps = 7.0 if self.preview_walk else 2.2
        if self.anim_timer >= 1.0 / fps:
            self.anim_timer = 0.0
            self.anim_frame = (self.anim_frame + 1) % 4

        if self.meltdown_active:
            self.meltdown_timer += dt
            if self.meltdown_timer >= 3.2:
                pygame.quit()
                raise SystemExit

    def render(self, screen, dt, mouse_pos):
        r = self.game.renderer
        prof = self.game.profile
        screen.fill((12, 10, 16))
        self.btn_rects = {}

        # 1. ЛЕВАЯ КОЛОНКА МЕНЮ (ВСЕГДА НА МЕСТЕ)
        left_rect = pygame.Rect(24, 24, 260, SCREEN_H - 48)
        r.draw_pixel_frame(screen, left_rect, UI_PANEL_BG, UI_BORDER_GOLD, False, 1.0)

        title_1 = r.font_title.render("КРЫСИНЫЙ", True, UI_BORDER_HIGHLIGHT)
        title_2 = r.font_title.render("ПОГРЕБ", True, (225, 95, 85))
        screen.blit(title_1, (left_rect.centerx - title_1.get_width() // 2, 56))
        screen.blit(title_2, (left_rect.centerx - title_2.get_width() // 2, 82))
        r.draw_item_icon(screen, "torch", left_rect.centerx - 16, 114, 32)

        labels = ["ИГРАТЬ", "УЛУЧШИТЬ", "НАСТРОЙКИ", "ВЫХОД"]
        for i, nr in enumerate(self.nav_rects):
            is_sel = (self.active_tab == i)
            is_hov = nr.collidepoint(mouse_pos)
            if i == 3 and (is_hov or is_sel):
                bg = (75, 22, 28)
                bd = (255, 80, 80)
            else:
                bg = (52, 42, 38) if (is_sel or is_hov) else UI_SLOT_BG
                bd = UI_BORDER_HIGHLIGHT if is_sel else UI_BORDER_WOOD
            r.draw_pixel_frame(screen, nr, bg, bd, is_hov or is_sel, 1.0)
            lbl_s = r.font_title.render(labels[i], True, UI_TEXT_MAIN if (is_sel or is_hov) else UI_TEXT_DIM)
            screen.blit(lbl_s, (nr.centerx - lbl_s.get_width() // 2, nr.centery - lbl_s.get_height() // 2))

        # Кошелёк игрока внизу левой панели
        bank_rect = pygame.Rect(40, left_rect.bottom - 112, 228, 88)
        r.draw_pixel_frame(screen, bank_rect, UI_SLOT_BG, UI_BORDER_WOOD, False, 1.0)
        b_lbl = r.font_small.render("КАЗНА НАЁМНИКА:", True, UI_TEXT_DIM)
        screen.blit(b_lbl, (bank_rect.centerx - b_lbl.get_width() // 2, bank_rect.y + 14))
        cp_val = prof.get("bank_copper", 0)
        cp_str = format_copper_Trigger(cp_val)
        cp_s = r.font_ui.render(cp_str, True, (255, 215, 80))
        screen.blit(cp_s, (bank_rect.centerx - cp_s.get_width() // 2, bank_rect.y + 38))
        raw_s = r.font_small.render(f"(Всего: {cp_val} медяков)", True, UI_TEXT_DIM)
        screen.blit(raw_s, (bank_rect.centerx - raw_s.get_width() // 2, bank_rect.y + 62))

        # 2. ПРАВАЯ ОБЛАСТЬ С ЛИСТАЮЩИМИСЯ ОКНАМИ (КАРУСЕЛЬ)
        viewport_rect = pygame.Rect(304, 24, 824, SCREEN_H - 48)
        old_clip = screen.get_clip()
        screen.set_clip(viewport_rect)

        for tab_i in range(4):
            panel_x = int(304 + tab_i * 840 - self.scroll_x)
            if panel_x + 824 < 304 or panel_x > 304 + 824:
                continue
            p_rect = pygame.Rect(panel_x, 24, 824, SCREEN_H - 48)
            r.draw_pixel_frame(screen, p_rect, UI_PANEL_BG, UI_BORDER_GOLD, False, 1.0)

            if tab_i == 0:
                self._render_play_tab(screen, p_rect, dt, mouse_pos, prof)
            elif tab_i == 1:
                self._render_upgrade_tab(screen, p_rect, prof)
            elif tab_i == 2:
                self._render_settings_tab(screen, p_rect, mouse_pos, prof)
            elif tab_i == 3:
                self._render_exit_tab(screen, p_rect, mouse_pos)

        screen.set_clip(old_clip)

    def _draw_selector_row(self, screen, x, y, w, label, val_text, prev_key, next_key, mouse_pos, locked=False):
        r = self.game.renderer
        lbl_s = r.font_small.render(label, True, UI_TEXT_DIM)
        screen.blit(lbl_s, (x + (w - lbl_s.get_width()) // 2, y))

        row_y = y + 20
        b_prev = pygame.Rect(x, row_y, 38, 36)
        b_next = pygame.Rect(x + w - 38, row_y, 38, 36)
        val_box = pygame.Rect(x + 44, row_y, w - 88, 36)

        self.btn_rects[prev_key] = b_prev
        self.btn_rects[next_key] = b_next

        for br, sym in ((b_prev, "<"), (b_next, ">")):
            hov = br.collidepoint(mouse_pos)
            r.draw_pixel_frame(screen, br, (52, 42, 38) if hov else UI_SLOT_BG, UI_BORDER_WOOD, hov, 1.0)
            s = r.font_title.render(sym, True, UI_TEXT_MAIN)
            screen.blit(s, (br.centerx - s.get_width() // 2, br.centery - s.get_height() // 2))

        r.draw_pixel_frame(screen, val_box, UI_SLOT_BG, (140, 65, 65) if locked else UI_BORDER_WOOD, False, 1.0)
        col = (255, 130, 120) if locked else UI_BORDER_HIGHLIGHT
        vs = r.font_ui.render(val_text, True, col)
        screen.blit(vs, (val_box.centerx - vs.get_width() // 2, val_box.centery - vs.get_height() // 2))

    def _render_play_tab(self, screen, p_rect, dt, mouse_pos, prof):
        r = self.game.renderer
        h_type = prof.get("hero_type", "male")
        if h_type == "ratfolk" and not prof.get("rat_king_defeated", False):
            h_type = "male"
            prof["hero_type"] = "male"

        type_db = HERO_CUSTOMIZATION_DB[h_type]
        skins = type_db["skins"]
        heads = type_db["heads"]
        outfits = HERO_CUSTOMIZATION_DB["outfits"]

        s_idx = prof.get("skin_idx", 0) % len(skins)
        h_idx = prof.get("head_idx", 0) % len(heads)
        o_idx = prof.get("outfit_idx", 0) % len(outfits)

        # ЛЕВАЯ ПОЛОВИНА: РЕДАКТОР ПЕРСОНАЖА
        ed_rect = pygame.Rect(p_rect.x + 22, p_rect.y + 22, 380, p_rect.height - 44)
        r.draw_pixel_frame(screen, ed_rect, UI_SLOT_BG, UI_BORDER_WOOD, False, 1.0)

        hdr = r.font_title.render("ОБЛИК ГЕРОЯ", True, UI_BORDER_HIGHLIGHT)
        screen.blit(hdr, (ed_rect.centerx - hdr.get_width() // 2, ed_rect.y + 16))

        # 2.5D стенд с живым светом факела
        prev_box = pygame.Rect(ed_rect.centerx - 104, ed_rect.y + 48, 208, 248)
        r.draw_pixel_frame(screen, prev_box, (16, 14, 22), UI_BORDER_GOLD, False, 1.0)

        d_hero, n_hero = build_custom_hero_sprite(
            cloak_color=tuple(self.preview_cloak_color),
            armor_class="none",
            has_helmet=False,
            has_torch=True,
            has_weapon=True,
            hero_type=h_type,
            skin_idx=s_idx,
            head_idx=h_idx,
            outfit_idx=o_idx,
            anim_frame=self.anim_frame,
            is_moving=self.preview_walk,
        )
        lit_surf = self.preview_3d.render(d_hero, n_hero, dt)
        screen.blit(lit_surf, (prev_box.x + 4, prev_box.y + 4))

        # Кнопки под превью: [Покой/Бег] и [Примерить цвет плаща]
        b_walk = pygame.Rect(ed_rect.x + 24, prev_box.bottom + 8, 160, 32)
        b_col = pygame.Rect(ed_rect.right - 184, prev_box.bottom + 8, 160, 32)
        self.btn_rects["toggle_preview_walk"] = b_walk
        self.btn_rects["roll_preview_color"] = b_col

        for br, txt in ((b_walk, "Анимация: БЕГ" if self.preview_walk else "Анимация: ПОКОЙ"), (b_col, "Цвет характера")):
            hov = br.collidepoint(mouse_pos)
            r.draw_pixel_frame(screen, br, (48, 38, 36) if hov else UI_PANEL_BG, UI_BORDER_WOOD, hov, 1.0)
            ts = r.font_small.render(txt, True, UI_TEXT_MAIN)
            screen.blit(ts, (br.centerx - ts.get_width() // 2, br.centery - ts.get_height() // 2))

        # Ползунки выбора
        sel_x = ed_rect.x + 24
        sel_w = ed_rect.width - 48
        cur_y = b_walk.bottom + 14

        self._draw_selector_row(screen, sel_x, cur_y, sel_w, "ТИП ПЕРСОНАЖА:", type_db["title"], "type_prev", "type_next", mouse_pos)
        cur_y += 66
        skin_label = "ОКРАС ШЕРСТИ:" if h_type == "ratfolk" else "ЦВЕТ КОЖИ:"
        self._draw_selector_row(screen, sel_x, cur_y, sel_w, skin_label, skins[s_idx][0], "skin_prev", "skin_next", mouse_pos)
        cur_y += 66
        head_label = "ОСОБЕННОСТЬ ГОЛОВЫ:" if h_type == "ratfolk" else "ПРИЧЁСКА И ЛИЦО:"
        self._draw_selector_row(screen, sel_x, cur_y, sel_w, head_label, heads[h_idx][0], "head_prev", "head_next", mouse_pos)
        cur_y += 66
        self._draw_selector_row(screen, sel_x, cur_y, sel_w, "БАЗОВОЕ ОДЕЯНИЕ:", outfits[o_idx][0], "outfit_prev", "outfit_next", mouse_pos)

        # Статус открытия Крысолюда
        if not prof.get("rat_king_defeated", False):
            lock_txt = r.font_small.render("Крысолюд: убейте Крысиного Короля!", True, (235, 145, 115))
            screen.blit(lock_txt, (ed_rect.centerx - lock_txt.get_width() // 2, ed_rect.bottom - 56))
            dev_unlock = pygame.Rect(ed_rect.centerx - 95, ed_rect.bottom - 36, 190, 26)
            self.btn_rects["unlock_ratfolk_dev"] = dev_unlock
            hov_u = dev_unlock.collidepoint(mouse_pos)
            pygame.draw.rect(screen, (55, 38, 48) if hov_u else (32, 24, 34), dev_unlock, border_radius=4)
            pygame.draw.rect(screen, UI_BORDER_GOLD, dev_unlock, 1, border_radius=4)
            ut = r.font_small.render("[Открыть сейчас (Тест)]", True, (255, 220, 95))
            screen.blit(ut, (dev_unlock.centerx - ut.get_width() // 2, dev_unlock.y + 5))
        else:
            ok_txt = r.font_small.render("★ Тип «Крысолюд» разблокирован!", True, (125, 240, 155))
            screen.blit(ok_txt, (ed_rect.centerx - ok_txt.get_width() // 2, ed_rect.bottom - 36))

        # ПРАВАЯ ПОЛОВИНА: ВЫБОР КАМПАНИИ И СТАРТ
        camp_rect = pygame.Rect(ed_rect.right + 18, p_rect.y + 22, 380, p_rect.height - 44)
        r.draw_pixel_frame(screen, camp_rect, UI_SLOT_BG, UI_BORDER_WOOD, False, 1.0)

        chdr = r.font_title.render("ВЫБОР КОНТРАКТА", True, UI_BORDER_HIGHLIGHT)
        screen.blit(chdr, (camp_rect.centerx - chdr.get_width() // 2, camp_rect.y + 16))

        card_1 = pygame.Rect(camp_rect.x + 20, camp_rect.y + 54, camp_rect.width - 40, 250)
        r.draw_pixel_frame(screen, card_1, (30, 25, 36), UI_BORDER_GOLD, True, 1.0)

        c_title = r.font_ui.render("I. КРЫСИНЫЙ ПОГРЕБ", True, (255, 220, 95))
        screen.blit(c_title, (card_1.x + 16, card_1.y + 16))

        status_str = "Пройдено ★" if prof.get("rat_king_defeated", False) else "Вступительный контракт"
        status_col = (120, 240, 150) if prof.get("rat_king_defeated", False) else (130, 200, 255)
        screen.blit(r.font_small.render(status_str, True, status_col), (card_1.x + 16, card_1.y + 38))

        desc_text = (
            "В погребе таверны Гуго расплодились крысы величиной с волка, "
            "а на нижних ярусах сектанты под одним плащом плетут кровавые печати. "
            "Спуститесь на 4-й ярус и сокрушите Крысиного Короля!"
        )
        for i, ln in enumerate(r.wrap_text(desc_text, r.font_small, card_1.width - 32)):
            screen.blit(r.font_small.render(ln, True, UI_TEXT_MAIN), (card_1.x + 16, card_1.y + 68 + i * 19))

        rew_s = r.font_small.render("Награда: Открытие типа «Крысолюд»", True, (255, 195, 85))
        screen.blit(rew_s, (card_1.x + 16, card_1.bottom - 32))

        # Заглушка Кампании II и Сложности
        card_2 = pygame.Rect(camp_rect.x + 20, card_1.bottom + 16, camp_rect.width - 40, 90)
        r.draw_pixel_frame(screen, card_2, (18, 15, 22), UI_BORDER_WOOD, False, 1.0)
        screen.blit(r.font_ui.render("II. СКЛЕП КОСТЯНОГО СОВЕТА", True, UI_TEXT_DIM), (card_2.x + 16, card_2.y + 18))
        screen.blit(r.font_small.render("[В разработке — откроется позже]", True, (130, 115, 125)), (card_2.x + 16, card_2.y + 46))

        diff_box = pygame.Rect(camp_rect.x + 20, card_2.bottom + 18, camp_rect.width - 40, 64)
        r.draw_pixel_frame(screen, diff_box, UI_PANEL_BG, UI_BORDER_WOOD, False, 1.0)
        screen.blit(r.font_small.render("СЛОЖНОСТЬ ПОХОДА:", True, UI_TEXT_DIM), (diff_box.x + 16, diff_box.y + 12))
        screen.blit(r.font_ui.render("Обычная (Стандартный баланс)", True, UI_TEXT_MAIN), (diff_box.x + 16, diff_box.y + 32))

        note_lines = r.wrap_text("При старте похода судьба случайно определит ваш Характер и выкрасит плащ в его цвета!", r.font_small, camp_rect.width - 44)
        for i, ln in enumerate(note_lines):
            screen.blit(r.font_small.render(ln, True, UI_TEXT_DIM), (camp_rect.x + 22, diff_box.bottom + 24 + i * 18))

        start_btn = pygame.Rect(camp_rect.x + 20, camp_rect.bottom - 86, camp_rect.width - 40, 64)
        self.btn_rects["start_run"] = start_btn
        hov_st = start_btn.collidepoint(mouse_pos)
        r.draw_pixel_frame(screen, start_btn, (46, 92, 52) if hov_st else (32, 68, 38), UI_BORDER_GOLD, hov_st, 1.0)
        st_lbl = r.font_title.render("В ПОХОД!", True, (255, 245, 200))
        screen.blit(st_lbl, (start_btn.centerx - st_lbl.get_width() // 2, start_btn.centery - st_lbl.get_height() // 2))

    def _render_upgrade_tab(self, screen, p_rect, prof):
        r = self.game.renderer
        hdr = r.font_title.render("ДОЛГАЯ ПРОКАЧКА НАЁМНИКА", True, UI_BORDER_HIGHLIGHT)
        screen.blit(hdr, (p_rect.centerx - hdr.get_width() // 2, p_rect.y + 40))

        box = pygame.Rect(p_rect.x + 60, p_rect.y + 100, p_rect.width - 120, 320)
        r.draw_pixel_frame(screen, box, UI_SLOT_BG, UI_BORDER_WOOD, False, 1.0)

        msg1 = r.font_ui.render("Раздел мета-прокачки пока пустует (Заглушка)", True, (255, 215, 95))
        screen.blit(msg1, (box.centerx - msg1.get_width() // 2, box.y + 50))

        info = (
            "Здесь за накопленные Медные Монеты (ММ) вы сможете навсегда усиливать выносливость, "
            "расширять стартовый пояс, прокачивать Удачу и открывать рероллы судеб. "
            "Собирайте монеты в данже и сдавайте драгоценные камни скупщику на этажах!"
        )
        for i, ln in enumerate(r.wrap_text(info, r.font_thought, box.width - 80)):
            s = r.font_thought.render(ln, True, UI_TEXT_MAIN)
            screen.blit(s, (box.centerx - s.get_width() // 2, box.y + 110 + i * 26))

    def _render_settings_tab(self, screen, p_rect, mouse_pos, prof):
        r = self.game.renderer
        hdr = r.font_title.render("НАСТРОЙКИ ИГРЫ", True, UI_BORDER_HIGHLIGHT)
        screen.blit(hdr, (p_rect.centerx - hdr.get_width() // 2, p_rect.y + 32))

        box = pygame.Rect(p_rect.x + 95, p_rect.y + 78, p_rect.width - 190, 560)
        r.draw_pixel_frame(screen, box, UI_SLOT_BG, UI_BORDER_WOOD, False, 1.0)

        # 1. Громкость синтезатора звука
        vol_pct = int(round(prof.get("volume", 0.85) * 100))
        self._draw_selector_row(screen, box.x + 60, box.y + 28, box.width - 120, "ГРОМКОСТЬ ЗВУКОВ:", f"{vol_pct}%", "vol_down", "vol_up", mouse_pos)

        # 2. Скорость печатной машинки мыслей
        modes = ["Обычная (Атмосферно)", "Быстрая (x2)", "Мгновенно"]
        m_idx = prof.get("typewriter_mode", 1) % 3
        self._draw_selector_row(screen, box.x + 60, box.y + 112, box.width - 120, "СКОРОСТЬ ТЕКСТА МЫСЛЕЙ:", modes[m_idx], "speed_cycle", "speed_cycle", mouse_pos)

        # 3. Частота фоновых мыслей героя
        freq_modes = [
            "Только сюжетные и важные",
            "Редко (x0.5, КД 10 сек)",
            "Обычная (x1.0, КД 6 сек)",
            "Часто (x1.75, КД 3.5 сек)"
        ]
        f_idx = prof.get("thought_freq_mode", 2) % 4
        self._draw_selector_row(screen, box.x + 60, box.y + 196, box.width - 120, "ЧАСТОТА МЫСЛЕЙ ГЕРОЯ:", freq_modes[f_idx], "freq_prev", "freq_next", mouse_pos)

        # 4. Полный экран / В окне
        fs_str = "Полный экран" if prof.get("fullscreen", False) else "В окне (1152x858)"
        self._draw_selector_row(screen, box.x + 60, box.y + 280, box.width - 120, "РЕЖИМ ОТОБРАЖЕНИЯ:", fs_str, "fullscreen_toggle", "fullscreen_toggle", mouse_pos)

        # 5. Кнопка сброса всего прогресса (с двухэтапным подтверждением)
        pygame.draw.line(screen, UI_BORDER_WOOD, (box.x + 40, box.y + 365), (box.right - 40, box.y + 365), 1)
        rst_btn = pygame.Rect(box.x + 60, box.y + 385, box.width - 120, 50)
        self.btn_rects["reset_progress"] = rst_btn
        hov_r = rst_btn.collidepoint(mouse_pos)
        if self.confirm_reset_timer > 0.0:
            r.draw_pixel_frame(screen, rst_btn, (135, 28, 34) if hov_r else (105, 20, 26), (255, 110, 110), True, 1.0)
            r_txt = r.font_ui.render("ТОЧНО СБРОСИТЬ ПРОГРЕСС? (КЛИКНИ ЕЩЁ РАЗ)", True, (255, 235, 210))
        else:
            r.draw_pixel_frame(screen, rst_btn, (68, 26, 32) if hov_r else (46, 20, 26), (175, 75, 75), hov_r, 1.0)
            r_txt = r.font_ui.render("СБРОСИТЬ ВЕСЬ ПРОГРЕСС (ЗОЛОТО И ОТКРЫТИЯ)", True, (240, 165, 165))
        screen.blit(r_txt, (rst_btn.centerx - r_txt.get_width() // 2, rst_btn.centery - r_txt.get_height() // 2))

        save_hint = r.font_small.render(f"Папка сохранений: {get_profile_dir()}", True, UI_TEXT_DIM)
        screen.blit(save_hint, (box.centerx - save_hint.get_width() // 2, box.bottom - 58))
        hint = r.font_small.render("Во время игры клавиша [ESC] возвращает в это Главное Меню.", True, UI_TEXT_DIM)
        screen.blit(hint, (box.centerx - hint.get_width() // 2, box.bottom - 32))

    def _render_exit_tab(self, screen, p_rect, mouse_pos):
        r = self.game.renderer
        box = pygame.Rect(p_rect.x + 70, p_rect.y + 90, p_rect.width - 140, 460)
        r.draw_pixel_frame(screen, box, (36, 14, 18), (255, 70, 70), True, 1.0)

        hdr = r.font_title.render("⚠ ПРОТОКОЛ СЖИГАНИЯ ПРОЦЕССОРА ⚠", True, (255, 95, 85))
        screen.blit(hdr, (box.centerx - hdr.get_width() // 2, box.y + 36))

        prog = min(1.0, self.meltdown_timer / 3.2)
        temp_c = int(65 + prog * 1450)
        t_lbl = r.font_popup_big.render(f"ТЕМПЕРАТУРА ЯДРА: {temp_c} °C", True, (255, 220, 80))
        screen.blit(t_lbl, (box.centerx - t_lbl.get_width() // 2, box.y + 100))

        bar_r = pygame.Rect(box.x + 60, box.y + 155, box.width - 120, 34)
        pygame.draw.rect(screen, (18, 8, 12), bar_r)
        pygame.draw.rect(screen, (255, int(180 * (1.0 - prog)), 40), (bar_r.x + 3, bar_r.y + 3, int((bar_r.width - 6) * prog), bar_r.height - 6))
        pygame.draw.rect(screen, (255, 90, 90), bar_r, 2)

        stages = [
            "Отключение кулеров и испарение термопасты...",
            "Скрытый майнинг КрысКоинов для Трактирщика Гуго...",
            "Призыв огненного бога Пиро прямо на материнскую плату...",
            "КРИТИЧЕСКИЙ ПЕРЕГРЕВ! Выход через пару мгновений!"
        ]
        st_txt = stages[min(len(stages) - 1, int(prog * len(stages)))]
        st_s = r.font_ui.render(st_txt, True, UI_TEXT_MAIN)
        screen.blit(st_s, (box.centerx - st_s.get_width() // 2, box.y + 215))

        b_cancel = pygame.Rect(box.x + 60, box.bottom - 95, 260, 54)
        b_quit = pygame.Rect(box.right - 320, box.bottom - 95, 260, 54)
        self.btn_rects["cancel_meltdown"] = b_cancel
        self.btn_rects["quit_now"] = b_quit

        hov_c = b_cancel.collidepoint(mouse_pos)
        r.draw_pixel_frame(screen, b_cancel, (42, 85, 52) if hov_c else (28, 58, 36), UI_BORDER_GOLD, hov_c, 1.0)
        cs = r.font_ui.render("ОЙ, ПОЩАДИ ПРОЦ!", True, (220, 255, 220))
        screen.blit(cs, (b_cancel.centerx - cs.get_width() // 2, b_cancel.centery - cs.get_height() // 2))

        hov_q = b_quit.collidepoint(mouse_pos)
        r.draw_pixel_frame(screen, b_quit, (135, 32, 38) if hov_q else (92, 22, 28), (255, 110, 110), hov_q, 1.0)
        qs = r.font_ui.render("СЖЕЧЬ МГНОВЕННО!", True, (255, 220, 210))
        screen.blit(qs, (b_quit.centerx - qs.get_width() // 2, b_quit.centery - qs.get_height() // 2))