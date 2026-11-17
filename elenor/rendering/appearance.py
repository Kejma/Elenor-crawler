import pygame
from elenor.rendering.normals import quantize_normal_surface


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


