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


def _draw_specific_torso(h_diff, h_norm, torso_id, x, y, bob_y, cloak_color, cloak_dark):
    if torso_id == "cloth_tunic":
        if x in (7, 8) or y == 12:
            return (218, 178, 72)
        return (86, 64, 142) if (x + y) % 3 != 0 else (62, 44, 108)
    if torso_id == "leather_brigandine":
        if x in (5, 8, 10) and y in (9 + bob_y, 12, 14):
            return (215, 192, 118)
        return (132, 82, 46) if (x + y) % 2 == 0 else (104, 62, 34)
    if torso_id == "knight_cuirass":
        if x in (7, 8) and y <= 13:
            return (225, 184, 78)
        if y == 13:
            return (92, 98, 114)
        return (202, 212, 228) if y <= 10 + bob_y else (152, 162, 180)
    if torso_id == "shadowweave_cloak":
        if y == 8 + bob_y and x in (6, 7, 8, 9):
            return (180, 192, 212)
        return (44, 40, 62) if (x + y) % 3 != 0 else (30, 26, 46)
    if torso_id == "padded_gambeson":
        if y == 12:
            return (110, 62, 38) if x != 7 else (218, 178, 74)
        if x in (6, 9):
            return (118, 92, 62)
        return (172, 144, 104)
    if torso_id == "pack_jerkin":
        if y == 12 and x in (7, 8):
            return (230, 188, 78)
        if (y in (10 + bob_y, 11 + bob_y) and x in (5, 6, 9, 10)) or (y in (13, 14) and 6 <= x <= 9):
            return (174, 130, 70)
        return (112, 80, 48)
    if torso_id == "scale_hauberk":
        return (148, 190, 180) if (x + y) % 2 == 0 else (82, 118, 112)
    if torso_id == "alchemist_coat":
        if y == 12:
            return (152, 108, 62)
        if y in (13, 14) and x == 5:
            return (85, 220, 248)
        if y in (13, 14) and x == 10:
            return (228, 74, 82)
        return (58, 98, 74) if (x + y) % 3 != 0 else (42, 72, 54)
    if torso_id == "duelist_doublet":
        if x in (7, 8) and y % 2 == 0:
            return (235, 195, 85)
        if y == 12:
            return (82, 34, 40)
        return (156, 48, 58) if x < 8 else (132, 38, 48)
    return None


def _draw_specific_helmet(h_diff, h_norm, helmet_id, hy0, cloak_color, cloak_dark):
    def put(px, py, col, norm=(128, 218, 200, 255)):
        if 0 <= px < 16 and 0 <= py < 20:
            h_diff.set_at((px, py), col)
            h_norm.set_at((px, py), norm)

    if helmet_id == "tattered_hood":
        for y in range(hy0, hy0 + 6):
            for x in range(4, 12):
                if y >= hy0 + 2 and 6 <= x <= 9 and y <= hy0 + 4:
                    continue
                col = (94, 124, 82) if y <= hy0 + 1 else (66, 90, 60)
                if y == hy0 + 5:
                    col = (155, 120, 68)
                put(x, y, col, (45 if x < 7 else (210 if x > 8 else 128), 218 if y <= hy0 + 1 else 128, 200, 255))
    elif helmet_id == "crown_of_ashes":
        for x in range(5, 11):
            put(x, hy0 + 1, (225, 174, 62))
        for x in (5, 7, 8, 10):
            put(x, hy0, (245, 202, 88))
        put(7, hy0 + 1, (255, 92, 42))
        put(8, hy0 + 1, (255, 218, 105))
    elif helmet_id == "kettle_hat":
        for y in range(hy0, hy0 + 3):
            for x in range(5, 11):
                put(x, y, (198, 206, 220) if y == hy0 else (150, 158, 172))
        for x in range(3, 13):
            put(x, hy0 + 2, (128, 136, 152))
    elif helmet_id == "padded_coif":
        for y in range(hy0, hy0 + 6):
            for x in range(5, 11):
                if y in (hy0 + 2, hy0 + 3, hy0 + 4) and 6 <= x <= 9:
                    continue
                put(x, y, (192, 166, 124) if y <= hy0 + 1 else (154, 128, 92))
    elif helmet_id == "bone_mask":
        for y in range(hy0 + 1, hy0 + 6):
            for x in range(5, 11):
                col = (224, 214, 192) if y < hy0 + 5 else (182, 170, 148)
                if y == hy0 + 3 and x in (6, 9):
                    col = (24, 18, 26)
                elif y == hy0 + 1 and x in (7, 8):
                    col = (195, 45, 52)
                put(x, y, col)
    elif helmet_id == "scholar_circlet":
        for x in range(5, 11):
            put(x, hy0 + 1, (215, 152, 82))
        put(7, hy0 + 1, (90, 215, 255))
        put(8, hy0 + 1, (175, 242, 255))
    elif helmet_id == "horned_bascinet":
        for y in range(hy0, hy0 + 6):
            for x in range(5, 11):
                col = (195, 202, 218) if y <= hy0 + 1 else (136, 144, 160)
                if y == hy0 + 3 and x in (6, 9):
                    col = (24, 20, 30)
                put(x, y, col)
        for hx, hy in ((4, hy0 + 1), (3, hy0), (4, hy0), (11, hy0 + 1), (12, hy0), (11, hy0)):
            put(hx, hy, (232, 224, 204))
    elif helmet_id == "lantern_cap":
        for y in range(hy0, hy0 + 3):
            for x in range(4, 12):
                put(x, y, (198, 148, 78) if y == hy0 else (152, 108, 52))
        put(7, hy0 - 1, (255, 225, 95))
        put(8, hy0 - 1, (255, 250, 205))
        put(7, hy0, (255, 165, 52))
    else:
        # iron_sallet и запасной шлем
        for y in range(hy0, hy0 + 6):
            for x in range(5, 11):
                col = (220, 230, 242) if y <= hy0 + 1 else (164, 176, 194)
                if y == hy0 + 3 and 6 <= x <= 9:
                    col = (26, 28, 38)
                put(x, y, col, (45 if x < 7 else (210 if x > 8 else 128), 218 if y <= hy0 + 1 else 128, 200, 255))
        put(4, hy0 + 4, (132, 142, 158))
        put(11, hy0 + 4, (132, 142, 158))


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
    helmet_id=None,
    torso_id=None,
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

    # 1. Хвост Крысолюда
    if hero_type == "ratfolk":
        tail_pts = [(11, 15), (12, 16), (13, 16 + tail_wag), (14, 15 + tail_wag)]
        for tx, ty in tail_pts:
            if 0 <= tx < 16 and 0 <= ty < 20:
                h_diff.set_at((tx, ty), (205, 135, 142))
                h_norm.set_at((tx, ty), (190, 195, 195, 255))

    # 2. Торс и конкретный доспех (y = 8..15)
    is_female = (hero_type == "female")
    for y in range(8 + bob_y, 16):
        for x in range(4, 12):
            if is_female and y in (11, 12) and x in (4, 11) and outfit_style != "cloak" and not torso_id:
                continue
            if not torso_id and outfit_style == "rags" and ((x == 4 and y >= 13) or (x == 11 and y == 15)):
                continue

            spec_col = _draw_specific_torso(h_diff, h_norm, torso_id, x, y, bob_y, cloak_color, cloak_dark) if torso_id else None
            if spec_col is not None:
                col = spec_col
                if x in (4, 11) and torso_id not in ("shadowweave_cloak", "alchemist_coat", "cloth_tunic", "knight_cuirass"):
                    col = cloak_color if y < 14 else cloak_dark
            elif x in (4, 11):
                col = cloak_color if y < 14 else cloak_dark
            else:
                col = chest_col if (x + y) % 3 != 0 else chest_dark

            if not torso_id and armor_class == "none":
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

    # Подол длинных мантий/плащей на y=16
    if (not torso_id and armor_class == "none" and outfit_style == "robe") or torso_id in ("cloth_tunic", "shadowweave_cloak", "alchemist_coat"):
        for x in range(5, 11):
            if torso_id == "cloth_tunic":
                col = (218, 178, 72) if x in (7, 8) else (62, 44, 108)
            elif torso_id == "shadowweave_cloak":
                col = (34, 30, 50)
            elif torso_id == "alchemist_coat":
                col = (44, 76, 58)
            else:
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

    # 4. Голова (y = 2..7 + bob_y) + наложение конкретного шлема поверх
    hy0 = 2 + bob_y
    full_cover_helm = has_helmet and (helmet_id in (None, "iron_sallet", "horned_bascinet"))
    if not full_cover_helm:
        if hero_type == "ratfolk":
            ear_places = [(5, hy0), (6, hy0), (9, hy0), (10, hy0)]
            for ex, ey in ear_places:
                if head_style == "ears_torn" and ex == 5:
                    continue
                col_e = (205, 130, 138) if ex in (6, 9) else skin_main
                h_diff.set_at((ex, ey), col_e)
                h_norm.set_at((ex, ey), (128, 218, 200, 255))

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
            elif head_style == "bone_crown" and not has_helmet:
                for cx in range(5, 10):
                    h_diff.set_at((cx, hy0 + 1), (235, 230, 210) if cx % 2 == 1 else (185, 175, 155))
        else:
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

            if hero_type == "male":
                if head_idx == 1 and head_style:
                    for bx in range(5, 11):
                        h_diff.set_at((bx, hy0 + 4), head_style)
                        h_diff.set_at((bx, hy0 + 5), head_style)
                    for bx in range(6, 10):
                        h_diff.set_at((bx, hy0 + 6), head_style)
                elif head_idx == 2 and head_style:
                    for py in range(hy0 + 1, hy0 + 5):
                        h_diff.set_at((4, py), head_style)
                        h_diff.set_at((11, py), head_style)
                elif head_idx == 3:
                    h_diff.set_at((8, hy0 + 1), (190, 95, 95))
                    h_diff.set_at((8, hy0 + 2), (190, 95, 95))
            elif hero_type == "female":
                if head_style:
                    for py in range(hy0 + 1, hy0 + 6):
                        h_diff.set_at((11, py), head_style)
                    if head_idx in (0, 2):
                        h_diff.set_at((4, hy0 + 2), head_style)
                        h_diff.set_at((4, hy0 + 3), head_style)
                        h_diff.set_at((11, hy0 + 6), head_style)

    if has_helmet or helmet_id:
        _draw_specific_helmet(h_diff, h_norm, helmet_id, hy0, cloak_color, cloak_dark)

    # 5. Факел в левой руке
    if has_torch:
        for y in range(8 + bob_y, 12 + bob_y):
            if 0 <= y < 20:
                h_diff.set_at((13, y), (120, 80, 45))
                h_norm.set_at((13, y), (210, 128, 200, 255))
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

    # 6. Оружие в правой руке
    if has_weapon:
        for y in range(4 + bob_y, 13 + bob_y):
            if 0 <= y < 20:
                col = (205, 215, 230) if y < 11 + bob_y else (140, 95, 45)
                h_diff.set_at((2, y), col)
                h_norm.set_at((2, y), (45, 218, 200, 255))

    quantize_normal_surface(h_norm, h_diff)
    return h_diff, h_norm