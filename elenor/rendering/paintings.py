"""24 procedural 42x62 / 62x42 pixel-art character cards with rim-lighting and 8 distinct poses."""

from functools import lru_cache
import math
import pygame


# Формат записи:
# id: (name, rarity, value, orient, frame, bg, skin, hair, hair_style, outfit, eye, species, pose, rim_side, desc)
_SPECS = {
    # ОБЫЧНЫЕ (8)
    "paint_tavern_maid": (
        "Трактирщица после смены", "common", 65, "v", "wood", "tavern",
        "warm", "auburn", "braid", "corset_red", (72, 168, 92), "human", "seated_kneel", "right",
        "Расшнурованный корсет и кружка пенного эля. Гуго клянётся, что это портрет его кузины."
    ),
    "paint_goblin_hut": (
        "Благолепная гоблинша", "common", 75, "v", "wood", "jungle",
        "goblin", "black", "wild", "jungle_wrap", (245, 192, 48), "goblin", "s_curve", "left",
        "Ограбил хижину в джунглях — а там такое. Уши длинные, взгляд хитрый, талия осиная."
    ),
    "paint_hayloft": (
        "Полдень на сеновале", "common", 60, "h", "wood", "hay",
        "peach", "blonde", "long", "chemise", (78, 152, 224), "human", "prone_glance", "top",
        "Солома, солнечный луч и минимум одежды. Классика деревенской живописи."
    ),
    "paint_wash_river": (
        "Прачка у ручья", "common", 70, "h", "wood", "river",
        "tan", "chestnut", "ponytail", "bath_water", (92, 148, 86), "human", "bath_mist", "right",
        "Вода прохладная, но позировать это нисколько не мешает."
    ),
    "paint_rat_barmaid": (
        "Крысолюдка из таверны", "common", 78, "v", "bronze", "tavern",
        "rat_grey", "silver", "bob", "corset_plum", (235, 68, 76), "ratfolk", "over_shoulder", "right",
        "Хвост колечком, усы топорщатся, а взгляд через плечо сводит с ума весь подвал."
    ),
    "paint_herbalist": (
        "Травница в теплице", "common", 80, "v", "bronze", "jungle",
        "pale", "ginger", "long", "leaf_dress", (82, 198, 118), "human", "closeup_bust", "left",
        "Собирает ночной мох в одном фартуке. Говорит, так травы лучше растут."
    ),
    "paint_inn_bed": (
        "Утро в постоялом дворе", "common", 82, "h", "bronze", "boudoir",
        "warm", "brown", "long", "sheet_white", (128, 86, 54), "human", "recline_diag", "top",
        "Смятая простыня и довольная улыбка. За эту комнату явно заплатили щедро."
    ),
    "paint_scout_camp": (
        "Разведчица у костра", "common", 88, "v", "bronze", "fire",
        "tan", "black", "ponytail", "leather_strap", (215, 148, 52), "human", "seated_kneel", "left",
        "Сняла кирасу просушить у пламени. Комары не рискуют подлетать."
    ),

    # НЕОБЫЧНЫЕ (6)
    "paint_goblin_bath": (
        "Гоблинша в горячем ключе", "uncommon", 175, "h", "bronze", "hotspring",
        "goblin", "ginger", "wild", "bath_water", (255, 212, 68), "goblin", "bath_mist", "top",
        "Пар над болотной заводью и хищная ухмылка. Выносить из пещеры строго бережно."
    ),
    "paint_dryad_vines": (
        "Дриада в лианах", "uncommon", 190, "v", "silver", "jungle",
        "moss", "emerald", "wild", "leaf_dress", (238, 224, 92), "elf", "s_curve", "right",
        "Одета исключительно в цветущий плющ и собственное обаяние."
    ),
    "paint_cat_burglar": (
        "Кошка-форточница", "uncommon", 205, "v", "silver", "moon",
        "warm", "black", "bob", "leather_strap", (105, 232, 118), "cat", "over_shoulder", "right",
        "Залезла в спальню за серебром, а оставила на стене свой портрет."
    ),
    "paint_pirate_deck": (
        "Корсарка на бочонке", "uncommon", 220, "v", "silver", "sea",
        "tan", "crimson", "wild", "corset_red", (72, 182, 226), "human", "s_curve", "left",
        "Сабля на бедре, рубашка нараспашку. Команда слушается её с полуслова."
    ),
    "paint_sauna_nord": (
        "Северянка в бане", "uncommon", 235, "h", "silver", "hotspring",
        "pale", "blonde", "braid", "towel", (98, 192, 245), "human", "prone_glance", "left",
        "Жаркий пар, берёзовый веник и полотенце, держащееся на честном слове."
    ),
    "paint_alchemist_girl": (
        "Ученица алхимика", "uncommon", 245, "v", "silver", "alchemy",
        "peach", "violet", "ponytail", "chemise", (178, 112, 248), "human", "closeup_bust", "right",
        "Опыт пошёл не по плану, и половина халата бесследно испарилась."
    ),

    # РЕДКИЕ (5)
    "paint_dark_elf": (
        "Тёмная эльфийка у камина", "rare", 420, "h", "gold", "fire",
        "drow", "silver", "long", "silk_crimson", (245, 68, 92), "elf", "recline_diag", "right",
        "Серебряные волосы, пепельная кожа и алый шёлк на шкуре медведя."
    ),
    "paint_mermaid_rock": (
        "Сирена на лунном камне", "rare", 455, "h", "gold", "moon",
        "aqua", "teal", "long", "bath_water", (255, 228, 112), "elf", "bath_mist", "right",
        "Моряки клянутся, что слышали пение. Судя по картине — пела она не главное."
    ),
    "paint_noble_lady": (
        "Баронесса в алом бархате", "rare", 490, "v", "gold", "boudoir",
        "pale", "black", "long", "silk_crimson", (92, 165, 232), "human", "closeup_bust", "left",
        "Платье с таким вырезом, что на балу три дуэли случились ещё до ужина."
    ),
    "paint_witch_cauldron": (
        "Ведьма у полночного котла", "rare", 525, "v", "gold", "alchemy",
        "pale", "emerald", "wild", "corset_plum", (145, 248, 118), "human", "arms_arch", "right",
        "Варит приворотное зелье. Хотя, глядя на неё, зелье — явное излишество."
    ),
    "paint_rat_duchess": (
        "Крысолюдка-маркиза", "rare", 560, "v", "gold", "boudoir",
        "rat_white", "blonde", "braid", "silk_gold", (252, 62, 86), "ratfolk", "seated_kneel", "right",
        "Белоснежная шёрстка, жемчуг и корсет из дворцового сундука."
    ),

    # ЭПИЧЕСКИЕ (3)
    "paint_fire_sorceress": (
        "Жрица пламени Пиро", "epic", 1080, "v", "gold", "volcano",
        "tan", "crimson", "wild", "silk_gold", (255, 198, 52), "human", "arms_arch", "left",
        "Одета в золотые цепочки и живые искры. Дотронуться хочется, но горячо."
    ),
    "paint_succubus_couch": (
        "Суккуб на бархатных подушках", "epic", 1220, "h", "gold", "boudoir",
        "demon", "black", "long", "leather_strap", (255, 218, 62), "demon", "recline_diag", "left",
        "Рожки, хвостик и взгляд, от которого наёмники забывают, зачем пришли в данж."
    ),
    "paint_valkyrie_rest": (
        "Валькирия после сечи", "epic", 1360, "v", "gold", "aurora",
        "pale", "blonde", "braid", "fur_cloak", (112, 212, 255), "human", "over_shoulder", "left",
        "Меховая накидка небрежно сползла с плеча. Даже северный ветер стих."
    ),

    # ЛЕГЕНДАРНЫЕ (2)
    "paint_moon_goddess": (
        "Купание Лунной Девы", "legendary", 2600, "h", "obsidian", "moon",
        "pale", "silver", "long", "bath_water", (145, 232, 255), "elf", "bath_mist", "right",
        "Запретный шедевр старого мастера. Серебряная вода скрывает лишь самую малость."
    ),
    "paint_queen_cushions": (
        "Фаворитка Эленора", "legendary", 3100, "h", "obsidian", "boudoir",
        "warm", "auburn", "long", "silk_gold", (112, 224, 152), "human", "recline_diag", "top",
        "То самое легендарное полотно, за которым охотятся все коллекционеры королевства."
    ),
}

PAINTING_SPECS = _SPECS

PAINTINGS_DB = {
    pid: {
        "name": name,
        "type": "painting",
        "rarity": rarity,
        "icon": pid,
        "copper_value": value,
        "is_collectible": True,
        "collection_kind": "painting",
        "orientation": orient,
        "desc": f"\"{desc}\"",
    }
    for pid, (name, rarity, value, orient, *_, desc) in _SPECS.items()
}

_FRAMES = {
    "wood":     ((44, 26, 16),  (124, 78, 44),  (178, 122, 68)),
    "bronze":   ((56, 36, 18),  (162, 112, 54), (222, 172, 98)),
    "silver":   ((58, 66, 82),  (166, 178, 198),(238, 246, 255)),
    "gold":     ((98, 66, 16),  (218, 172, 48), (255, 234, 128)),
    "obsidian": ((18, 14, 28),  (68, 54, 98),   (246, 196, 70)),
}

# (deep_shadow, shadow, base, highlight, blush)
_SKINS = {
    "pale":      ((148, 108, 108), (194, 150, 144), (242, 214, 202), (255, 240, 232), (236, 134, 144)),
    "peach":     ((144, 96, 82),   (190, 136, 114), (238, 196, 168), (255, 228, 204), (236, 126, 130)),
    "warm":      ((132, 84, 66),   (178, 122, 92),  (228, 180, 144), (252, 214, 182), (226, 118, 114)),
    "tan":       ((102, 62, 46),   (144, 92, 64),   (196, 140, 100), (228, 178, 136), (208, 104, 94)),
    "goblin":    ((48, 86, 44),    (76, 126, 62),   (126, 186, 94),  (176, 226, 134), (186, 152, 102)),
    "moss":      ((52, 96, 66),    (84, 138, 96),   (138, 198, 142), (188, 236, 184), (198, 148, 136)),
    "drow":      ((44, 38, 66),    (70, 62, 98),    (112, 102, 146), (156, 146, 192), (154, 82, 126)),
    "demon":     ((92, 28, 44),    (138, 48, 66),   (196, 78, 98),   (238, 128, 144), (244, 84, 108)),
    "aqua":      ((58, 104, 124),  (92, 152, 174),  (148, 208, 224), (202, 242, 252), (186, 146, 178)),
    "rat_grey":  ((68, 60, 62),    (104, 94, 94),   (156, 144, 140), (198, 188, 184), (228, 134, 148)),
    "rat_white": ((136, 126, 134), (184, 174, 180), (236, 228, 232), (254, 250, 254), (244, 146, 162)),
}

# (dark, base, highlight)
_HAIRS = {
    "black":    ((16, 14, 24),   (38, 34, 54),   (94, 90, 128)),
    "brown":    ((48, 26, 18),   (98, 58, 34),   (156, 104, 64)),
    "chestnut": ((62, 26, 18),   (124, 58, 38),  (186, 104, 68)),
    "auburn":   ((82, 24, 18),   (162, 54, 34),  (228, 112, 64)),
    "ginger":   ((118, 42, 18),  (212, 94, 34),  (254, 168, 82)),
    "blonde":   ((142, 98, 34),  (224, 182, 76), (255, 238, 156)),
    "silver":   ((108, 120, 146),(190, 206, 228),(248, 252, 255)),
    "crimson":  ((86, 14, 28),   (176, 32, 52),  (242, 92, 108)),
    "emerald":  ((18, 68, 46),   (44, 146, 88),  (116, 222, 148)),
    "teal":     ((18, 72, 88),   (48, 156, 176), (132, 230, 242)),
    "violet":   ((54, 26, 92),   (122, 64, 184), (194, 138, 248)),
}

# (dark, main, accent)
_OUTFITS = {
    "corset_red":    ((86, 16, 28),   (168, 34, 48),   (242, 202, 112)),
    "corset_plum":   ((48, 20, 68),   (106, 44, 138),  (228, 186, 94)),
    "jungle_wrap":   ((26, 66, 32),   (62, 130, 56),   (232, 174, 68)),
    "leaf_dress":    ((22, 62, 36),   (54, 134, 64),   (246, 198, 98)),
    "chemise":       ((146, 138, 164),(222, 216, 234), (250, 248, 255)),
    "sheet_white":   ((138, 132, 158),(218, 212, 232), (250, 248, 255)),
    "towel":         ((148, 134, 122),(226, 214, 196), (250, 246, 236)),
    "leather_strap": ((34, 22, 28),   (76, 46, 46),    (226, 184, 74)),
    "silk_crimson":  ((90, 14, 30),   (182, 30, 52),   (252, 210, 88)),
    "silk_gold":     ((124, 80, 18),  (224, 170, 48),  (255, 240, 148)),
    "fur_cloak":     ((104, 94, 88),  (188, 178, 172), (246, 242, 238)),
    "bath_water":    ((28, 76, 104),  (64, 144, 176),  (204, 244, 255)),
}

_BG_RIM_COLORS = {
    "tavern":    (255, 196, 98),
    "jungle":    (176, 236, 118),
    "hay":       (255, 226, 128),
    "river":     (186, 236, 255),
    "boudoir":   (255, 168, 132),
    "fire":      (255, 154, 62),
    "hotspring": (218, 236, 246),
    "moon":      (162, 214, 255),
    "sea":       (176, 224, 250),
    "alchemy":   (126, 248, 176),
    "volcano":   (255, 138, 52),
    "aurora":    (132, 248, 212),
}


def _px(s, x, y, col):
    ix, iy = int(round(x)), int(round(y))
    if 0 <= ix < s.get_width() and 0 <= iy < s.get_height():
        s.set_at((ix, iy), col)


def _blend(c1, c2, t):
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def _vgrad(s, x0, y0, w, h, top_c, bot_c, dither=True):
    for dy in range(h):
        t = dy / max(1, h - 1)
        c = _blend(top_c, bot_c, t)
        pygame.draw.line(s, c, (x0, y0 + dy), (x0 + w - 1, y0 + dy))
        if dither and dy % 2 == 1 and dy + 1 < h:
            c2 = _blend(top_c, bot_c, min(1.0, (dy + 1) / max(1, h - 1)))
            for dx in range(dy % 2, w, 2):
                s.set_at((x0 + dx, y0 + dy), c2)


def _glow(s, cx, cy, rad, col, max_alpha=120):
    g = pygame.Surface((rad * 2 + 2, rad * 2 + 2), pygame.SRCALPHA)
    for r in range(rad, 0, -2):
        a = int(max_alpha * ((1.0 - r / (rad + 1)) ** 1.6))
        if a > 2:
            pygame.draw.circle(g, (*col, a), (rad + 1, rad + 1), r)
    s.blit(g, (int(cx - rad - 1), int(cy - rad - 1)))


def _limb(s, pts, r0, r1, dk, mn, hi, ldx=-1, ldy=-1):
    """Draws an organic tapered limb along polyline pts with volume shading."""
    total_segs = max(1, len(pts) - 1)
    for si in range(total_segs):
        x0, y0 = pts[si]
        x1, y1 = pts[si + 1]
        dist = max(1, int(math.hypot(x1 - x0, y1 - y0) * 2))
        for k in range(dist + 1):
            frac = k / dist
            gfrac = (si + frac) / total_segs
            x = x0 + (x1 - x0) * frac
            y = y0 + (y1 - y0) * frac
            rad = max(1, int(round(r0 + (r1 - r0) * gfrac)))
            pygame.draw.circle(s, dk, (int(round(x)), int(round(y))), rad)
    for si in range(total_segs):
        x0, y0 = pts[si]
        x1, y1 = pts[si + 1]
        dist = max(1, int(math.hypot(x1 - x0, y1 - y0) * 2))
        for k in range(dist + 1):
            frac = k / dist
            gfrac = (si + frac) / total_segs
            x = x0 + (x1 - x0) * frac
            y = y0 + (y1 - y0) * frac
            rad = max(1, int(round(r0 + (r1 - r0) * gfrac)) - 1)
            if rad >= 1:
                pygame.draw.circle(s, mn, (int(round(x + ldx * 0.4)), int(round(y + ldy * 0.4))), rad)
            if rad >= 2 and k % 2 == 0:
                _px(s, x + ldx * 0.8, y + ldy * 0.8, hi)


def _shaded_sphere(s, cx, cy, rad, dk, mn, hi, ldx=-1, ldy=-1):
    pygame.draw.circle(s, dk, (int(cx), int(cy)), int(rad))
    if rad >= 2:
        pygame.draw.circle(s, mn, (int(round(cx + ldx * 0.5)), int(round(cy + ldy * 0.5))), max(1, int(rad) - 1))
    if rad >= 3:
        pygame.draw.circle(s, hi, (int(round(cx + ldx)), int(round(cy + ldy))), max(1, int(rad) - 2))


def _apply_outline_and_rim(char_s, outline_col, rim_col, rim_side):
    """Adds a crisp 1px dark silhouette outline and directional colored rim light."""
    w, h = char_s.get_size()
    out = char_s.copy()
    opaque = [[char_s.get_at((x, y))[3] > 20 for y in range(h)] for x in range(w)]

    rim_vec = {
        "left":  (-1, 0),
        "right": (1, 0),
        "top":   (0, -1),
    }.get(rim_side, (-1, 0))
    rvx, rvy = rim_vec

    # 1. Rim light on outer silhouette edge pixels facing the light source
    for x in range(1, w - 1):
        for y in range(1, h - 1):
            if not opaque[x][y]:
                continue
            nx, ny = x + rvx, y + rvy
            if 0 <= nx < w and 0 <= ny < h and not opaque[nx][ny]:
                r, g, b, a = char_s.get_at((x, y))
                out.set_at((x, y), (*_blend((r, g, b), rim_col, 0.48), a))

    # 2. Clean 1px tinted dark outline around transparent border
    for x in range(1, w - 1):
        for y in range(1, h - 1):
            if opaque[x][y]:
                continue
            if opaque[x - 1][y] or opaque[x + 1][y] or opaque[x][y - 1] or opaque[x][y + 1]:
                out.set_at((x, y), (*outline_col, 255))
    return out


def _make_drop_shadow(char_s, alpha=95):
    w, h = char_s.get_size()
    sh = pygame.Surface((w, h), pygame.SRCALPHA)
    for x in range(w):
        for y in range(h):
            if char_s.get_at((x, y))[3] > 20:
                sh.set_at((x, y), (12, 8, 18, alpha))
    return sh


def _draw_background(s, bg, w, h, rim_side):
    ix, iy, iw, ih = 2, 2, w - 4, h - 4
    palettes = {
        "tavern":    ((44, 24, 20), (22, 12, 16)),
        "jungle":    ((18, 46, 36), (12, 26, 22)),
        "hay":       ((76, 52, 28), (154, 112, 42)),
        "river":     ((36, 72, 102),(24, 58, 72)),
        "boudoir":   ((64, 18, 34), (26, 10, 22)),
        "fire":      ((46, 18, 22), (112, 38, 22)),
        "hotspring": ((34, 52, 68), (24, 54, 62)),
        "moon":      ((14, 18, 44), (26, 40, 78)),
        "sea":       ((32, 64, 104),(18, 44, 74)),
        "alchemy":   ((22, 28, 46), (18, 52, 46)),
        "volcano":   ((44, 14, 22), (128, 36, 20)),
        "aurora":    ((14, 20, 48), (22, 68, 74)),
    }
    top_c, bot_c = palettes.get(bg, ((38, 26, 44), (20, 14, 28)))
    _vgrad(s, ix, iy, iw, ih, top_c, bot_c)

    # Атмосферное световое пятно за героиней для контраста силуэта
    lx = int(w * (0.22 if rim_side == "left" else (0.78 if rim_side == "right" else 0.50)))
    ly = int(h * (0.28 if rim_side == "top" else 0.42))
    _glow(s, lx, ly, max(w, h) // 2, _BG_RIM_COLORS.get(bg, (240, 200, 140)), max_alpha=95)

    if bg == "jungle":
        # Бамбуковые стволы / лианы на заднем плане
        for bx in (5, w - 8):
            pygame.draw.rect(s, (24, 58, 34), (bx, iy, 3, ih))
        for cx, cy, cr in ((6, 8, 8), (w - 6, 9, 8), (5, h - 12, 7)):
            pygame.draw.circle(s, (26, 72, 40), (cx, cy), cr)
            pygame.draw.circle(s, (46, 108, 54), (cx - 1, cy - 1), max(2, cr - 3))
        for fx, fy in ((9, 13), (w - 10, 16), (11, h - 18), (w - 13, 10)):
            _px(s, fx, fy, (232, 252, 134))
    elif bg == "boudoir":
        # Портьеры с золотой подвязкой и мягкая кровать
        pygame.draw.polygon(s, (98, 22, 38), [(ix, iy), (ix + 11, iy), (ix + 5, iy + ih // 2), (ix, iy + ih // 2)])
        pygame.draw.polygon(s, (98, 22, 38), [(ix + iw, iy), (ix + iw - 11, iy), (ix + iw - 5, iy + ih // 2), (ix + iw, iy + ih // 2)])
        pygame.draw.line(s, (236, 192, 76), (ix + 5, iy + ih // 2 - 2), (ix + 5, iy + ih // 2 + 5))
        pygame.draw.line(s, (236, 192, 76), (ix + iw - 5, iy + ih // 2 - 2), (ix + iw - 5, iy + ih // 2 + 5))
        pygame.draw.ellipse(s, (118, 28, 46), (ix - 3, h - 16, iw + 6, 18))
    elif bg == "moon":
        mx = w - 12 if rim_side == "right" else 12
        _glow(s, mx, 11, 14, (148, 206, 255), max_alpha=110)
        pygame.draw.circle(s, (238, 244, 226), (mx, 11), 5)
        for sx, sy in ((8, 6), (18, 5), (w - 22, 8), (11, 16), (w - 8, 19)):
            _px(s, sx, sy, (220, 236, 255))
    elif bg in ("fire", "volcano"):
        fx = 10 if rim_side == "left" else (w - 10 if rim_side == "right" else w // 2)
        _glow(s, fx, h - 8, 18, (255, 132, 42), max_alpha=155)
        pygame.draw.circle(s, (255, 198, 72), (fx, h - 5), 5)
    elif bg == "tavern":
        for gx in range(ix + 7, ix + iw, 9):
            pygame.draw.line(s, (34, 18, 16), (gx, iy), (gx, iy + ih))
        sx = w - 8 if rim_side == "right" else 8
        _glow(s, sx, 13, 12, (255, 186, 72), max_alpha=135)
        pygame.draw.circle(s, (255, 244, 182), (sx, 13), 2)
    elif bg == "hotspring":
        # Мягкие камни и клубы пара
        pygame.draw.ellipse(s, (56, 66, 76), (2, h - 18, 18, 14))
        pygame.draw.ellipse(s, (56, 66, 76), (w - 20, h - 17, 18, 13))
        for bx, by, br in ((10, 10, 6), (w - 12, 9, 7), (w // 2, 7, 7)):
            _glow(s, bx, by, br + 3, (198, 224, 236), max_alpha=68)
    elif bg == "aurora":
        for off, col in ((0, (54, 224, 152)), (2, (112, 246, 218)), (4, (132, 114, 236))):
            pygame.draw.line(s, col, (3, 7 + off), (w - 4, 13 + off), 2)
    elif bg == "alchemy":
        _glow(s, w // 2, h - 8, 18, (88, 242, 156), max_alpha=115)
        for vx, col in ((5, (82, 232, 148)), (w - 8, (176, 98, 242))):
            pygame.draw.rect(s, col, (vx, h - 14, 4, 7))
            pygame.draw.rect(s, (224, 245, 255), (vx + 1, h - 16, 2, 2))
    elif bg == "hay":
        pygame.draw.ellipse(s, (188, 142, 52), (ix - 2, h - 17, iw + 4, 19))
        for sy in (h - 11, h - 8, h - 5):
            pygame.draw.line(s, (236, 192, 86), (5, sy), (w - 6, sy + 1))
    elif bg == "sea":
        pygame.draw.rect(s, (22, 48, 78), (ix, int(h * 0.56), iw, ih))
        pygame.draw.line(s, (148, 196, 226), (ix + 4, int(h * 0.62)), (ix + 16, int(h * 0.62)))


def _draw_foreground(s, bg, pose, w, h):
    """Adds subtle foreground depth (water ripples, leaves, embers, vignette)."""
    if pose == "bath_mist":
        # Полупрозрачная гладь воды ПОВЕРХ нижней части тела + отражения и пар
        water = pygame.Surface((w, 16), pygame.SRCALPHA)
        for dy in range(16):
            a = int(155 + dy * 5)
            c = _blend((52, 128, 158), (18, 48, 72), dy / 15.0)
            pygame.draw.line(water, (*c, min(235, a)), (2, dy), (w - 3, dy))
        s.blit(water, (0, 26))
        # Светлые блики ряби на воде
        for wx, wy, wl in ((7, 27, 12), (24, 28, 16), (44, 27, 10), (14, 31, 18), (36, 33, 14), (20, 36, 15)):
            pygame.draw.line(s, (196, 240, 252), (wx, wy), (wx + wl, wy))
        # Листья кувшинки и пар на переднем плане
        pygame.draw.ellipse(s, (34, 92, 56), (4, 34, 9, 4))
        pygame.draw.ellipse(s, (56, 134, 76), (5, 34, 7, 3))
        _px(s, 9, 34, (248, 192, 212))  # цветочек лотоса
        for sx, sy in ((11, 23), (35, 19), (51, 21)):
            pygame.draw.line(s, (224, 240, 248), (sx, sy), (sx + 2, sy - 5))
    elif bg in ("fire", "volcano", "alchemy"):
        spark_c = (132, 255, 178) if bg == "alchemy" else (255, 224, 112)
        for sx, sy in ((7, h - 10), (w - 8, h - 14), (10, 18), (w - 9, 24)):
            _px(s, sx, sy, spark_c)
    elif bg == "jungle":
        # Лист папоротника в нижних углах
        pygame.draw.polygon(s, (24, 68, 36), [(2, h - 2), (11, h - 2), (6, h - 10)])
        pygame.draw.polygon(s, (48, 114, 56), [(3, h - 2), (9, h - 2), (6, h - 8)])
        pygame.draw.polygon(s, (24, 68, 36), [(w - 2, h - 2), (w - 11, h - 2), (w - 6, h - 9)])


def _draw_species_ears(s, cx, cy, r_x, r_y, skin_k, hair_k, species):
    s_dp, s_dk, s_mn, s_hi, blush = _SKINS[skin_k]
    h_dk, h_mn, _ = _HAIRS[hair_k]
    if species == "goblin":
        for side in (-1, 1):
            pts = [(cx + side * r_x, cy), (cx + side * (r_x + 8), cy - 3), (cx + side * (r_x + 1), cy + 3)]
            pygame.draw.polygon(s, s_dk, pts)
            pygame.draw.polygon(s, s_mn, [(cx + side * r_x, cy), (cx + side * (r_x + 7), cy - 2), (cx + side * (r_x + 1), cy + 2)])
            # Золотая серьга-колечко на ушке
            _px(s, cx + side * (r_x + 4), cy + 2, (248, 206, 76))
            _px(s, cx + side * (r_x + 5), cy + 3, (248, 206, 76))
    elif species == "elf":
        for side in (-1, 1):
            pygame.draw.polygon(s, s_dk, [(cx + side * r_x, cy), (cx + side * (r_x + 5), cy - 2), (cx + side * r_x, cy + 2)])
            pygame.draw.polygon(s, s_mn, [(cx + side * r_x, cy), (cx + side * (r_x + 4), cy - 1), (cx + side * r_x, cy + 1)])
    elif species == "ratfolk":
        for side in (-1, 1):
            pygame.draw.circle(s, s_dk, (cx + side * (r_x + 1), cy - r_y + 1), 4)
            pygame.draw.circle(s, s_mn, (cx + side * (r_x + 1), cy - r_y + 1), 3)
            pygame.draw.circle(s, blush, (cx + side * (r_x + 1), cy - r_y + 1), 1)
    elif species == "cat":
        for side in (-1, 1):
            pts = [(cx + side * r_x, cy - r_y + 2), (cx + side * (r_x + 2), cy - r_y - 5), (cx + side * (r_x - 3), cy - r_y)]
            pygame.draw.polygon(s, h_mn, pts)
            pygame.draw.polygon(s, blush, [(cx + side * (r_x - 1), cy - r_y + 1), (cx + side * (r_x + 1), cy - r_y - 3), (cx + side * (r_x - 2), cy - r_y)])
    elif species == "demon":
        for side in (-1, 1):
            pts = [(cx + side * (r_x - 1), cy - r_y + 1), (cx + side * (r_x + 3), cy - r_y - 3), (cx + side * (r_x + 1), cy - r_y - 7)]
            pygame.draw.lines(s, (34, 18, 28), False, pts, 3)
            pygame.draw.lines(s, (78, 36, 52), False, pts, 1)


def _draw_face(s, cx, cy, skin_k, hair_k, hair_style, eye_c, species, *, look_dir=0, large=False):
    s_dp, s_dk, s_mn, s_hi, blush = _SKINS[skin_k]
    h_dk, h_mn, h_hi = _HAIRS[hair_k]
    rx, ry = (7, 8) if large else (5, 6)

    _draw_species_ears(s, cx, cy, rx, ry, skin_k, hair_k, species)

    # Овал лица с мягким подбородком
    pygame.draw.ellipse(s, s_dk, (cx - rx, cy - ry, rx * 2 + 1, ry * 2 + 1))
    pygame.draw.ellipse(s, s_mn, (cx - rx + 1, cy - ry, rx * 2 - 1, ry * 2))
    pygame.draw.ellipse(s, s_hi, (cx - rx + 2, cy - ry + 1, rx, ry + 1))

    # Выразительные глаза (ресницы, радужка, блик)
    ex_off = 3 if large else 2
    ey = cy if large else cy
    e_left = cx - ex_off + look_dir
    e_right = cx + ex_off - (0 if large else 1) + look_dir

    if large:
        for ex in (e_left, e_right):
            # Верхняя дуга ресниц
            pygame.draw.line(s, (22, 16, 26), (ex - 2, ey - 1), (ex + 1, ey - 1))
            _px(s, ex - 2, ey, (242, 242, 248))  # белок
            _px(s, ex - 1, ey, eye_c)
            _px(s, ex, ey, eye_c)
            _px(s, ex - 1, ey + 1, _blend(eye_c, (18, 14, 24), 0.5))
            _px(s, ex, ey + 1, eye_c)
            _px(s, ex, ey, (252, 254, 255))  # яркий блик
        # Брови
        pygame.draw.line(s, h_dk, (e_left - 2, ey - 3), (e_left + 1, ey - 3))
        pygame.draw.line(s, h_dk, (e_right - 1, ey - 3), (e_right + 2, ey - 3))
        # Носик, румянец и пухлые губки
        _px(s, cx + look_dir, ey + 2, s_dk)
        _px(s, e_left - 1, ey + 3, blush)
        _px(s, e_right + 1, ey + 3, blush)
        lip = (204, 58, 78) if skin_k not in ("goblin", "drow") else (158, 48, 82)
        pygame.draw.line(s, lip, (cx - 2 + look_dir, cy + 5), (cx + 1 + look_dir, cy + 5))
        _px(s, cx - 1 + look_dir, cy + 6, blush)
        _px(s, cx + look_dir, cy + 6, blush)
    else:
        for ex in (e_left, e_right):
            pygame.draw.line(s, (22, 16, 26), (ex - 1, ey - 1), (ex + 1, ey - 1))
            _px(s, ex, ey, eye_c)
            _px(s, ex + 1, ey, (252, 254, 255))
            _px(s, ex, ey + 1, _blend(eye_c, (20, 14, 24), 0.45))
        _px(s, e_left - 1, ey + 2, blush)
        _px(s, e_right + 1, ey + 2, blush)
        _px(s, cx + look_dir, ey + 1, s_dk)
        lip = (204, 58, 78) if skin_k not in ("goblin", "drow") else (158, 48, 82)
        _px(s, cx - 1 + look_dir, cy + 4, lip)
        _px(s, cx + look_dir, cy + 4, lip)
        _px(s, cx + 1 + look_dir, cy + 4, blush)

    # Причёска и чёлка спереди (разные силуэты)
    pygame.draw.arc(s, h_dk, (cx - rx - 1, cy - ry - 2, (rx + 1) * 2 + 1, ry * 2 - 1), 0.05, 3.1, 3)
    pygame.draw.arc(s, h_mn, (cx - rx, cy - ry - 2, rx * 2 + 1, ry * 2 - 2), 0.15, 3.0, 2)
    pygame.draw.line(s, h_hi, (cx - rx + 2, cy - ry), (cx + rx - 2, cy - ry))
    # Асимметричная прядь чёлки
    pygame.draw.line(s, h_mn, (cx - rx + 1, cy - ry + 1), (cx - 1, cy - 2), 2)
    pygame.draw.line(s, h_hi, (cx - rx + 2, cy - ry + 1), (cx - 2, cy - 3), 1)
    if hair_style in ("long", "wild", "braid"):
        pygame.draw.line(s, h_dk, (cx - rx, cy - 2), (cx - rx - 1, cy + ry + 3), 2)
        pygame.draw.line(s, h_mn, (cx + rx, cy - 2), (cx + rx + 1, cy + ry + 2), 2)
    elif hair_style == "bob":
        pygame.draw.line(s, h_dk, (cx - rx, cy - 2), (cx - rx, cy + ry), 2)
        pygame.draw.line(s, h_mn, (cx + rx, cy - 2), (cx + rx, cy + ry), 2)


# ===================== 5 ВЕРТИКАЛЬНЫХ КОМПОЗИЦИЙ (42x62) =====================

def _pose_s_curve(s, skin_k, hair_k, hair_style, outfit_k, eye_c, species):
    s_dp, s_dk, s_mn, s_hi, _ = _SKINS[skin_k]
    h_dk, h_mn, h_hi = _HAIRS[hair_k]
    o_dk, o_mn, o_ac = _OUTFITS[outfit_k]
    hx, hy = 22, 13

    # Задние волосы, развевающиеся влево-вниз (асимметрия!)
    hair_blob = [(14, 8), (29, 8), (31, 20), (26, 36), (11, 34), (8, 22)]
    pygame.draw.polygon(s, h_dk, hair_blob)
    pygame.draw.polygon(s, h_mn, [(15, 9), (28, 9), (29, 19), (24, 34), (13, 32), (10, 21)])
    pygame.draw.line(s, h_hi, (12, 15), (14, 28))

    # Ноги в контрапосте (левое бедро вынесено влево, правая нога опорная)
    _limb(s, [(16, 44), (15, 59)], 5, 4, s_dk, s_mn, s_hi)
    _limb(s, [(24, 45), (25, 59)], 5, 4, s_dk, s_mn, s_hi)

    # Торс с S-изгибом: наклонённые плечи -> грудь -> тонкая талия -> пышное бедро
    torso = [(15, 22), (27, 23), (28, 30), (25, 36), (29, 45), (12, 46), (17, 36), (14, 29)]
    pygame.draw.polygon(s, s_dk, torso)
    pygame.draw.polygon(s, s_mn, [(16, 23), (26, 24), (27, 30), (24, 36), (27, 45), (14, 45), (18, 36), (15, 29)])
    # Шея и ключица
    _limb(s, [(21, 18), (21, 23)], 2, 3, s_dk, s_mn, s_hi)
    # Объём груди
    _shaded_sphere(s, 17, 29, 4, s_dk, s_mn, s_hi)
    _shaded_sphere(s, 24, 30, 4, s_dk, s_mn, s_hi)
    _px(s, 21, 30, s_dp)
    pygame.draw.ellipse(s, s_hi, (19, 35, 3, 5))
    _px(s, 20, 40, s_dk)

    # Наряд
    if outfit_k in ("jungle_wrap", "leaf_dress"):
        pygame.draw.ellipse(s, o_dk, (13, 28, 8, 5))
        pygame.draw.ellipse(s, o_dk, (21, 28, 8, 6))
        pygame.draw.ellipse(s, o_mn, (14, 28, 6, 4))
        pygame.draw.ellipse(s, o_mn, (22, 29, 6, 4))
        pygame.draw.line(s, o_ac, (18, 30), (23, 30))
        # Асимметричная набедренная повязка с высоким разрезом
        skirt = [(12, 42), (28, 43), (29, 51), (22, 49), (16, 57), (11, 53)]
        pygame.draw.polygon(s, o_dk, skirt)
        pygame.draw.polygon(s, o_mn, [(13, 43), (27, 44), (28, 50), (22, 48), (16, 55), (12, 52)])
        pygame.draw.line(s, o_ac, (13, 43), (27, 44))
    else:
        corset = [(14, 29), (21, 32), (27, 29), (25, 42), (30, 58), (12, 58), (16, 42)]
        pygame.draw.polygon(s, o_dk, corset)
        pygame.draw.polygon(s, o_mn, [(15, 30), (21, 33), (26, 30), (24, 42), (28, 58), (14, 58), (17, 42)])
        # Разрез на левом бедре
        pygame.draw.polygon(s, s_mn, [(13, 46), (19, 47), (18, 58), (14, 58)])
        pygame.draw.line(s, s_hi, (15, 48), (15, 57))
        for ly in (34, 37, 40):
            pygame.draw.line(s, o_ac, (19, ly), (23, ly))

    # Руки: левая на выгнутом бедре, правая приподнята/держит клинок или лиану
    _limb(s, [(15, 24), (9, 34), (14, 43)], 2, 2, s_dk, s_mn, s_hi)
    _limb(s, [(27, 24), (33, 32), (30, 40)], 2, 2, s_dk, s_mn, s_hi)
    if outfit_k == "corset_red":
        # Абордажная сабля в правой руке
        pygame.draw.line(s, (215, 226, 242), (30, 39), (36, 22), 2)
        pygame.draw.line(s, (238, 194, 76), (28, 39), (33, 41), 2)

    _draw_face(s, hx, hy, skin_k, hair_k, hair_style, eye_c, species, look_dir=-1)


def _pose_over_shoulder(s, skin_k, hair_k, hair_style, outfit_k, eye_c, species):
    s_dp, s_dk, s_mn, s_hi, _ = _SKINS[skin_k]
    h_dk, h_mn, h_hi = _HAIRS[hair_k]
    o_dk, o_mn, o_ac = _OUTFITS[outfit_k]
    hx, hy = 20, 14

    # Хвост (если кошка или крысолюдка) изящно уходит в левую часть кадра
    if species in ("cat", "ratfolk"):
        tail_c = h_mn if species == "cat" else (216, 138, 148)
        pygame.draw.lines(s, (34, 24, 32), False, [(16, 46), (8, 42), (6, 33), (10, 27)], 4)
        pygame.draw.lines(s, tail_c, False, [(16, 46), (8, 42), (6, 33), (10, 27)], 2)

    # Волосы перекинуты на правое плечо, оставляя левую спину и плечо открытыми!
    pygame.draw.ellipse(s, h_dk, (15, 6, 17, 28))
    pygame.draw.ellipse(s, h_mn, (17, 7, 14, 25))
    pygame.draw.line(s, h_hi, (25, 13), (27, 26))

    # Силуэт спины и пышных бёдер в три четверти сзади (очень узнаваемый силуэт!)
    back_pts = [(16, 22), (28, 24), (29, 34), (31, 45), (27, 59), (15, 59), (12, 46), (17, 35)]
    pygame.draw.polygon(s, s_dk, back_pts)
    pygame.draw.polygon(s, s_mn, [(17, 23), (27, 25), (28, 34), (29, 45), (26, 59), (16, 59), (14, 46), (18, 35)])
    # Линия позвоночника и мягкие тени ягодиц/спины
    pygame.draw.lines(s, s_dk, False, [(22, 24), (22, 34), (20, 44)], 1)
    _shaded_sphere(s, 17, 45, 6, s_dk, s_mn, s_hi)
    _shaded_sphere(s, 25, 45, 5, s_dk, s_mn, s_hi)
    _px(s, 21, 47, s_dp)
    # Светлый блик на оголённом левом плече
    _shaded_sphere(s, 17, 24, 4, s_dk, s_mn, s_hi)

    # Накидка / ремни / сползшая ткань на бёдрах
    if outfit_k == "fur_cloak":
        cloak = [(22, 23), (32, 25), (34, 58), (22, 58), (25, 40)]
        pygame.draw.polygon(s, o_dk, cloak)
        pygame.draw.polygon(s, o_mn, [(23, 24), (31, 26), (33, 58), (24, 58), (26, 40)])
        pygame.draw.line(s, o_ac, (23, 25), (30, 27), 2)
    else:
        # Низкий корсет/ремень с открытой спиной
        pygame.draw.polygon(s, o_dk, [(14, 41), (30, 42), (30, 53), (13, 52)])
        pygame.draw.polygon(s, o_mn, [(15, 42), (29, 43), (29, 52), (14, 51)])
        pygame.draw.line(s, o_ac, (15, 42), (29, 43))
        pygame.draw.line(s, o_dk, (17, 25), (27, 36), 2)  # диагональный ремешок по спине

    # Ближняя рука красиво придерживает бедро
    _limb(s, [(16, 25), (11, 34), (15, 44)], 2, 2, s_dk, s_mn, s_hi)
    # Голова повёрнута через левое плечо к зрителю
    _draw_face(s, hx, hy, skin_k, hair_k, hair_style, eye_c, species, look_dir=-1)


def _pose_closeup_bust(s, skin_k, hair_k, hair_style, outfit_k, eye_c, species):
    s_dp, s_dk, s_mn, s_hi, _ = _SKINS[skin_k]
    h_dk, h_mn, h_hi = _HAIRS[hair_k]
    o_dk, o_mn, o_ac = _OUTFITS[outfit_k]
    hx, hy = 19, 18

    # Роскошная рама из волос за головой
    pygame.draw.ellipse(s, h_dk, (5, 6, 30, 38))
    pygame.draw.ellipse(s, h_mn, (7, 7, 26, 35))
    pygame.draw.line(s, h_hi, (9, 14), (8, 32), 2)
    pygame.draw.line(s, h_hi, (30, 16), (31, 30), 1)

    # Шея, плечи и крупное декольте (y=26..59)
    _limb(s, [(19, 24), (19, 32)], 3, 4, s_dk, s_mn, s_hi)
    pygame.draw.ellipse(s, s_dk, (6, 30, 29, 14))
    pygame.draw.ellipse(s, s_mn, (7, 31, 27, 12))
    pygame.draw.line(s, s_hi, (11, 32), (26, 32))
    # Ключицы
    pygame.draw.line(s, s_dk, (12, 34), (17, 35))
    pygame.draw.line(s, s_dk, (22, 35), (27, 34))
    # Объём груди
    pygame.draw.rect(s, s_mn, (8, 37, 25, 22))
    _shaded_sphere(s, 14, 44, 7, s_dk, s_mn, s_hi)
    _shaded_sphere(s, 25, 44, 7, s_dk, s_mn, s_hi)
    pygame.draw.line(s, s_dp, (20, 42), (20, 48), 1)

    # Платье / корсет с глубоким V-вырезом и кружевом
    dress = [(7, 43), (14, 46), (20, 51), (26, 46), (34, 43), (35, 59), (6, 59)]
    pygame.draw.polygon(s, o_dk, dress)
    pygame.draw.polygon(s, o_mn, [(8, 45), (14, 48), (20, 53), (26, 48), (33, 45), (34, 59), (7, 59)])
    pygame.draw.lines(s, o_ac, False, [(8, 45), (14, 48), (20, 53), (26, 48), (33, 45)], 1)
    # Кулон на шее
    pygame.draw.lines(s, o_ac, False, [(14, 32), (20, 37), (26, 32)], 1)
    _px(s, 20, 38, (242, 62, 82))

    # Изящная рука справа со склянкой или у подбородка
    _limb(s, [(32, 42), (34, 52), (29, 43)], 3, 2, s_dk, s_mn, s_hi)
    if outfit_k in ("chemise", "leaf_dress"):
        # Светящийся флакон зелья в пальцах
        pygame.draw.circle(s, (88, 242, 168), (29, 37), 4)
        pygame.draw.circle(s, (224, 255, 242), (28, 36), 2)
        pygame.draw.rect(s, (186, 148, 86), (28, 31, 3, 3))

    # Крупное выразительное лицо
    _draw_face(s, hx, hy, skin_k, hair_k, hair_style, eye_c, species, look_dir=1, large=True)


def _pose_seated_kneel(s, skin_k, hair_k, hair_style, outfit_k, eye_c, species):
    s_dp, s_dk, s_mn, s_hi, _ = _SKINS[skin_k]
    h_dk, h_mn, h_hi = _HAIRS[hair_k]
    o_dk, o_mn, o_ac = _OUTFITS[outfit_k]
    hx, hy = 22, 14

    # Деревянный бочонок / бархатный пуф снизу справа
    seat_c = (94, 56, 34) if outfit_k != "silk_gold" else (112, 34, 52)
    pygame.draw.rect(s, seat_c, (16, 45, 20, 14), border_radius=3)
    pygame.draw.line(s, (218, 176, 72), (16, 49), (35, 49))

    # Волосы
    pygame.draw.ellipse(s, h_dk, (13, 6, 19, 26))
    pygame.draw.ellipse(s, h_mn, (15, 7, 15, 24))
    if hair_style == "braid":
        _limb(s, [(28, 16), (31, 28), (28, 39)], 2, 2, h_dk, h_mn, h_hi)

    # Торс слегка наклонён вперёд, сидя на бочонке
    torso = [(15, 23), (27, 24), (29, 37), (31, 46), (17, 46), (16, 35)]
    pygame.draw.polygon(s, s_dk, torso)
    pygame.draw.polygon(s, s_mn, [(16, 24), (26, 25), (28, 37), (29, 45), (18, 45), (17, 35)])
    _limb(s, [(22, 19), (21, 24)], 2, 3, s_dk, s_mn, s_hi)
    _shaded_sphere(s, 18, 30, 4, s_dk, s_mn, s_hi)
    _shaded_sphere(s, 24, 31, 4, s_dk, s_mn, s_hi)
    _px(s, 21, 31, s_dp)

    # Согнутое колено вынесено влево-вперёд (эффектная диагональ ног!)
    _limb(s, [(20, 44), (10, 43), (14, 58)], 5, 4, s_dk, s_mn, s_hi)
    _limb(s, [(27, 45), (23, 58)], 4, 3, s_dk, s_mn, s_hi)

    # Наряд (корсет + юбка с открытым коленом)
    pygame.draw.polygon(s, o_dk, [(16, 30), (21, 33), (27, 30), (28, 45), (17, 44)])
    pygame.draw.polygon(s, o_mn, [(17, 31), (21, 34), (26, 31), (27, 44), (18, 43)])
    pygame.draw.line(s, o_ac, (19, 35), (24, 35))
    pygame.draw.line(s, o_ac, (19, 38), (24, 38))
    # Спадающая юбка сзади
    pygame.draw.polygon(s, o_dk, [(21, 43), (32, 44), (33, 55), (22, 54)])
    pygame.draw.polygon(s, o_mn, [(22, 44), (31, 45), (32, 54), (23, 53)])

    # Руки: одна опирается на колено, другая держит кружку эля
    _limb(s, [(26, 26), (30, 36), (25, 43)], 2, 2, s_dk, s_mn, s_hi)
    _limb(s, [(16, 25), (11, 33), (12, 39)], 2, 2, s_dk, s_mn, s_hi)
    if outfit_k == "corset_red":
        pygame.draw.rect(s, (164, 102, 48), (6, 33, 6, 7))
        pygame.draw.rect(s, (246, 238, 206), (6, 31, 6, 3))

    _draw_face(s, hx, hy, skin_k, hair_k, hair_style, eye_c, species, look_dir=-1)


def _pose_arms_arch(s, skin_k, hair_k, hair_style, outfit_k, eye_c, species):
    s_dp, s_dk, s_mn, s_hi, _ = _SKINS[skin_k]
    h_dk, h_mn, h_hi = _HAIRS[hair_k]
    o_dk, o_mn, o_ac = _OUTFITS[outfit_k]
    hx, hy = 21, 15

    # Разметавшиеся вверх и в стороны волосы
    pygame.draw.polygon(s, h_dk, [(8, 12), (21, 5), (34, 11), (36, 29), (26, 38), (12, 35), (6, 24)])
    pygame.draw.polygon(s, h_mn, [(10, 13), (21, 6), (32, 12), (33, 27), (25, 35), (14, 33), (8, 23)])
    pygame.draw.line(s, h_hi, (12, 18), (9, 29))
    pygame.draw.line(s, h_hi, (30, 16), (32, 27))

    # Поднятые за голову руки (красивый ромб над плечами!)
    _limb(s, [(15, 24), (9, 16), (16, 9)], 2, 2, s_dk, s_mn, s_hi)
    _limb(s, [(27, 24), (33, 15), (26, 9)], 2, 2, s_dk, s_mn, s_hi)

    # Выгнутый стройный силуэт
    torso = [(15, 23), (27, 23), (28, 31), (24, 38), (30, 48), (28, 59), (14, 59), (12, 48), (18, 38), (14, 31)]
    pygame.draw.polygon(s, s_dk, torso)
    pygame.draw.polygon(s, s_mn, [(16, 24), (26, 24), (27, 31), (23, 38), (28, 48), (27, 59), (15, 59), (14, 48), (19, 38), (15, 31)])
    _limb(s, [(21, 20), (21, 25)], 2, 3, s_dk, s_mn, s_hi)
    _shaded_sphere(s, 17, 30, 4, s_dk, s_mn, s_hi)
    _shaded_sphere(s, 25, 30, 4, s_dk, s_mn, s_hi)
    _px(s, 21, 31, s_dp)
    pygame.draw.ellipse(s, s_hi, (19, 36, 4, 5))

    # Развевающийся шлейф и золотые цепи / корсет
    pygame.draw.ellipse(s, o_dk, (13, 29, 8, 5))
    pygame.draw.ellipse(s, o_dk, (21, 29, 8, 5))
    pygame.draw.ellipse(s, o_mn, (14, 29, 6, 4))
    pygame.draw.ellipse(s, o_mn, (22, 29, 6, 4))
    pygame.draw.lines(s, o_ac, False, [(17, 33), (21, 39), (25, 33)], 1)
    # Развевающаяся полупрозрачная юбка вправо
    skirt = [(13, 44), (29, 44), (36, 58), (24, 58), (20, 49), (12, 56)]
    pygame.draw.polygon(s, o_dk, skirt)
    pygame.draw.polygon(s, o_mn, [(14, 45), (28, 45), (34, 58), (25, 58), (20, 48), (13, 54)])
    pygame.draw.line(s, o_ac, (14, 45), (28, 45))

    _draw_face(s, hx, hy, skin_k, hair_k, hair_style, eye_c, species, look_dir=0)


# ===================== 3 ГОРИЗОНТАЛЬНЫХ КОМПОЗИЦИИ (62x42) =====================

def _pose_recline_diag(s, skin_k, hair_k, hair_style, outfit_k, eye_c, species):
    s_dp, s_dk, s_mn, s_hi, _ = _SKINS[skin_k]
    h_dk, h_mn, h_hi = _HAIRS[hair_k]
    o_dk, o_mn, o_ac = _OUTFITS[outfit_k]
    hx, hy = 15, 14

    # Роскошные подушки слева
    pygame.draw.ellipse(s, o_dk, (3, 16, 22, 17))
    pygame.draw.ellipse(s, o_mn, (5, 17, 18, 14))
    pygame.draw.line(s, o_ac, (7, 18), (18, 18))

    # Хвост суккуба за спиной
    if species == "demon":
        pygame.draw.lines(s, (34, 16, 26), False, [(39, 21), (45, 13), (52, 14)], 3)
        pygame.draw.lines(s, (164, 42, 62), False, [(39, 21), (45, 13), (52, 14)], 1)
        pygame.draw.polygon(s, (196, 48, 68), [(51, 13), (56, 12), (54, 17)])

    # Пышные волосы спадают на подушку
    pygame.draw.ellipse(s, h_dk, (5, 7, 19, 20))
    pygame.draw.ellipse(s, h_mn, (7, 8, 15, 18))
    pygame.draw.line(s, h_hi, (8, 14), (10, 22))

    # Дальняя вытянутая нога
    _limb(s, [(38, 30), (55, 33)], 4, 3, s_dk, s_mn, s_hi)

    # Диагональный торс и волна бедра (классическая «Венера»)
    body = [(16, 22), (27, 21), (34, 25), (41, 20), (47, 28), (38, 34), (24, 34), (15, 31)]
    pygame.draw.polygon(s, s_dk, body)
    pygame.draw.polygon(s, s_mn, [(17, 23), (27, 22), (34, 26), (41, 21), (46, 28), (38, 33), (24, 33), (16, 30)])
    # Грудь и блик по изгибу бедра
    _shaded_sphere(s, 23, 25, 4, s_dk, s_mn, s_hi)
    _shaded_sphere(s, 27, 26, 4, s_dk, s_mn, s_hi)
    _shaded_sphere(s, 40, 24, 5, s_dk, s_mn, s_hi)

    # Согнутая верхняя нога (отличный читаемый треугольник!)
    _limb(s, [(41, 23), (48, 18), (55, 31)], 4, 3, s_dk, s_mn, s_hi)

    # Шёлковая драпировка поверх талии и части бедра
    drape = [(29, 26), (43, 23), (48, 35), (27, 35)]
    pygame.draw.polygon(s, o_dk, drape)
    pygame.draw.polygon(s, o_mn, [(30, 27), (42, 24), (46, 34), (28, 34)])
    pygame.draw.line(s, o_ac, (31, 27), (42, 25))

    # Опорная рука под головой и вторая рука вдоль бедра
    _limb(s, [(17, 23), (11, 28), (19, 32)], 2, 2, s_dk, s_mn, s_hi)
    _limb(s, [(24, 22), (33, 24), (40, 22)], 2, 2, s_dk, s_mn, s_hi)

    _draw_face(s, hx, hy, skin_k, hair_k, hair_style, eye_c, species, look_dir=1)


def _pose_bath_mist(s, skin_k, hair_k, hair_style, outfit_k, eye_c, species):
    s_dp, s_dk, s_mn, s_hi, _ = _SKINS[skin_k]
    h_dk, h_mn, h_hi = _HAIRS[hair_k]
    hx, hy = 23, 13

    # Влажные длинные волосы, спадающие в воду
    pygame.draw.ellipse(s, h_dk, (14, 6, 18, 24))
    pygame.draw.ellipse(s, h_mn, (16, 7, 14, 22))
    pygame.draw.line(s, h_hi, (26, 12), (28, 24))

    # Обнажённые плечи, грудь и рука, облокотившаяся на камень слева
    _limb(s, [(23, 18), (23, 22)], 2, 3, s_dk, s_mn, s_hi)
    pygame.draw.ellipse(s, s_dk, (15, 20, 17, 10))
    pygame.draw.ellipse(s, s_mn, (16, 21, 15, 8))
    _shaded_sphere(s, 20, 25, 4, s_dk, s_mn, s_hi)
    _shaded_sphere(s, 27, 25, 4, s_dk, s_mn, s_hi)
    _px(s, 23, 26, s_dp)
    # Рука уходит налево на край водоёма
    _limb(s, [(17, 22), (10, 25), (8, 29)], 2, 2, s_dk, s_mn, s_hi)
    # Вторая рука тянется к воде
    _limb(s, [(30, 22), (34, 27)], 2, 2, s_dk, s_mn, s_hi)
    # Согнутое колено, грациозно выглядывающее из воды справа
    _limb(s, [(37, 29), (44, 20), (50, 29)], 4, 3, s_dk, s_mn, s_hi)

    _draw_face(s, hx, hy, skin_k, hair_k, hair_style, eye_c, species, look_dir=1)


def _pose_prone_glance(s, skin_k, hair_k, hair_style, outfit_k, eye_c, species):
    """Playful lying-on-stomach pose: chin propped up on right, kicked-up legs on left."""
    s_dp, s_dk, s_mn, s_hi, _ = _SKINS[skin_k]
    h_dk, h_mn, h_hi = _HAIRS[hair_k]
    o_dk, o_mn, o_ac = _OUTFITS[outfit_k]
    hx, hy = 45, 14

    # Задорно согнутые и поднятые ножки слева!
    _limb(s, [(22, 26), (13, 25), (10, 12)], 4, 2, s_dk, s_mn, s_hi)
    _limb(s, [(24, 28), (17, 27), (16, 15)], 4, 2, s_dk, s_mn, s_hi)

    # Пышные волосы справа-сверху
    pygame.draw.ellipse(s, h_dk, (36, 7, 18, 20))
    pygame.draw.ellipse(s, h_mn, (38, 8, 14, 18))
    pygame.draw.line(s, h_hi, (49, 12), (51, 21))

    # Изогнутая спина и бёдра (лежа на животе слева направо)
    body = [(19, 24), (27, 21), (36, 25), (46, 22), (49, 32), (35, 34), (20, 32)]
    pygame.draw.polygon(s, s_dk, body)
    pygame.draw.polygon(s, s_mn, [(20, 25), (27, 22), (36, 26), (45, 23), (48, 31), (35, 33), (21, 31)])
    _shaded_sphere(s, 25, 25, 5, s_dk, s_mn, s_hi)
    _shaded_sphere(s, 41, 26, 4, s_dk, s_mn, s_hi)

    # Простыня / полотенце, прикрывающее поясницу и бёдра
    drape = [(18, 24), (34, 24), (35, 34), (18, 33)]
    pygame.draw.polygon(s, o_dk, drape)
    pygame.draw.polygon(s, o_mn, [(19, 25), (33, 25), (34, 33), (19, 32)])
    pygame.draw.line(s, o_ac, (20, 26), (33, 26))

    # Руки согнуты под подбородком
    _limb(s, [(46, 24), (53, 29), (47, 31)], 2, 2, s_dk, s_mn, s_hi)
    _limb(s, [(40, 25), (38, 31), (44, 31)], 2, 2, s_dk, s_mn, s_hi)

    _draw_face(s, hx, hy, skin_k, hair_k, hair_style, eye_c, species, look_dir=-1)


_POSE_FUNCS = {
    "s_curve":       _pose_s_curve,
    "over_shoulder": _pose_over_shoulder,
    "closeup_bust":  _pose_closeup_bust,
    "seated_kneel":  _pose_seated_kneel,
    "arms_arch":     _pose_arms_arch,
    "recline_diag":  _pose_recline_diag,
    "bath_mist":     _pose_bath_mist,
    "prone_glance":  _pose_prone_glance,
}


def _load_painting_dtex(icon_name):
    import os
    try:
        from elenor.data.textures import get_assets_root, load_manifest, load_dtex_frames
        manifest = load_manifest()
        info = manifest.get(icon_name)
        if info:
            fpath = os.path.join(get_assets_root(), info.get("cat", "paintings"), f"{info['file']}.dtex")
        else:
            fpath = os.path.join(get_assets_root(), "paintings", f"{icon_name}.dtex")
        if os.path.isfile(fpath):
            _, frames, _ = load_dtex_frames(fpath)
            if frames:
                return frames[0][0].copy()
    except Exception:
        pass
    return None


@lru_cache(maxsize=None)
def get_painting_surface(icon_name, scale=1):
    """Returns crisp 42x62 (vertical) or 62x42 (horizontal) pixel-art card scaled by `scale`."""
    spec = _SPECS.get(icon_name)
    if spec is None:
        return None
    custom = _load_painting_dtex(icon_name)
    if custom is not None:
        w, h = custom.get_size()
        return pygame.transform.scale(custom, (int(round(w * scale)), int(round(h * scale)))) if scale != 1 else custom
    from elenor.rendering.painting_art import HIGH_QUALITY_PAINTERS
    hq_fn = HIGH_QUALITY_PAINTERS.get(icon_name)
    if hq_fn is not None:
        s = hq_fn()
        w, h = s.get_size()
        return pygame.transform.scale(s, (int(round(w * scale)), int(round(h * scale)))) if scale != 1 else s
    _, _, _, orient, frame_style, bg, skin_k, hair_k, hair_style, outfit_k, eye_c, species, pose, rim_side, _ = spec
    _, _, _, orient, frame_style, bg, skin_k, hair_k, hair_style, outfit_k, eye_c, species, pose, rim_side, _ = spec
    w, h = (42, 62) if orient == "v" else (62, 42)
    f_dk, f_mn, f_hi = _FRAMES[frame_style]

    # 1. Фон со светом
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    _draw_background(s, bg, w, h, rim_side)

    # 2. Персонаж на отдельном слое -> авто-контур и контровой свет
    char_s = pygame.Surface((w, h), pygame.SRCALPHA)
    pose_fn = _POSE_FUNCS.get(pose, _pose_s_curve)
    pose_fn(char_s, skin_k, hair_k, hair_style, outfit_k, eye_c, species)

    rim_col = _BG_RIM_COLORS.get(bg, (245, 210, 150))
    char_outlined = _apply_outline_and_rim(char_s, (22, 14, 24), rim_col, rim_side)

    # Мягкая падающая тень на фон
    sh_dx = 2 if rim_side == "left" else (-2 if rim_side == "right" else 0)
    sh_dy = 2
    s.blit(_make_drop_shadow(char_s, alpha=88), (sh_dx, sh_dy))
    s.blit(char_outlined, (0, 0))

    # 3. Передний план (вода, листья, искры)
    _draw_foreground(s, bg, pose, w, h)

    # 4. Резная рама 2 px с золотыми уголками
    pygame.draw.rect(s, (16, 12, 22), (0, 0, w, h), 1)
    pygame.draw.rect(s, f_mn, (1, 1, w - 2, h - 2), 1)
    for cx, cy in ((1, 1), (w - 3, 1), (1, h - 3), (w - 3, h - 3)):
        pygame.draw.rect(s, f_hi, (cx, cy, 2, 2))
    pygame.draw.rect(s, f_dk, (2, 2, w - 4, h - 4), 1)

    if scale != 1:
        return pygame.transform.scale(s, (int(round(w * scale)), int(round(h * scale))))
    return s


@lru_cache(maxsize=None)
def _render_painting_thumb(icon_name, size):
    base = get_painting_surface(icon_name, scale=1)
    if base is None:
        return None
    bw, bh = base.get_size()
    if bw >= bh:
        tw = size
        th = max(1, int(round(size * bh / bw)))
    else:
        th = size
        tw = max(1, int(round(size * bw / bh)))
    return pygame.transform.scale(base, (tw, th))


def draw_painting_icon(surf, icon_name, x, y, size=32):
    thumb = _render_painting_thumb(icon_name, size)
    if thumb is None:
        return False
    ox = x + (size - thumb.get_width()) // 2
    oy = y + (size - thumb.get_height()) // 2
    surf.blit(thumb, (ox, oy))
    return True