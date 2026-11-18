"""Semantic pixel glyphs for abilities; cached at each requested size."""

import math
import pygame

from elenor.data.abilities import PASSIVES

CACHE = {}


def draw_ability_icon(surface, name, x, y, size):
    if not name.startswith("ability_"):
        return False
    key = (name, size)
    if key not in CACHE:
        icon = pygame.Surface((32, 32), pygame.SRCALPHA)
        glyph = name[8:]

        # Палитры
        dark = (14, 12, 20)
        steel_d = (120, 130, 150)
        steel = (195, 208, 225)
        steel_hi = (245, 250, 255)
        wood = (135, 85, 45)
        gold = (245, 195, 70)
        warm_d = (180, 65, 30)
        warm = (245, 140, 50)
        warm_hi = (255, 235, 130)
        crimson = (225, 55, 65)
        green_d = (35, 125, 70)
        green = (90, 225, 130)
        green_hi = (195, 255, 200)
        teal = (80, 220, 195)
        cold_d = (40, 115, 185)
        cold = (95, 210, 255)
        cold_hi = (225, 250, 255)
        shadow_d = (45, 38, 75)
        shadow = (115, 105, 185)
        shadow_hi = (185, 195, 245)

        passive_branch = PASSIVES.get(glyph, {}).get("branch")
        if passive_branch == "body" or glyph in ("whirlwind", "earth_slam", "heavy_strike", "shield_bash", "cleave", "war_stomp"):
            bg_col, rim_col = (42, 24, 22, 220), (110, 58, 38, 240)
        elif passive_branch == "cunning" or glyph in ("throw_knife", "poison_flask", "piercing_shot", "hamstring", "fan_blades", "venom_strike"):
            bg_col, rim_col = (20, 36, 34, 220), (52, 105, 88, 240)
        else:
            bg_col, rim_col = (22, 26, 46, 220), (62, 84, 135, 240)

        pygame.draw.circle(icon, bg_col, (16, 16), 14)
        pygame.draw.circle(icon, rim_col, (16, 16), 14, 1)

        def line(col, pts, w=2, closed=False):
            pygame.draw.lines(icon, col, closed, pts, w)

        def outlined_line(col, pts, w=2):
            pygame.draw.lines(icon, dark, False, pts, w + 2)
            pygame.draw.lines(icon, col, False, pts, w)

        def poly(col, pts, outline=True):
            if outline:
                pygame.draw.polygon(icon, dark, pts, 3)
            pygame.draw.polygon(icon, col, pts, 0)

        def dagger_shape(p_base, p_tip, blade_col=steel, hilt_col=gold):
            bx, by = p_base
            tx, ty = p_tip
            dx, dy = tx - bx, ty - by
            ln = max(1.0, math.hypot(dx, dy))
            nx, ny = dx / ln, dy / ln
            px, py = -ny, nx
            gx, gy = bx + nx * 5, by + ny * 5
            # Рукоять и гарда
            outlined_line(wood, [(bx, by), (gx, gy)], 3)
            outlined_line(hilt_col, [(gx - px * 4, gy - py * 4), (gx + px * 4, gy + py * 4)], 2)
            # Клинок
            b_pts = [
                (gx - px * 2.5, gy - py * 2.5),
                (tx, ty),
                (gx + px * 2.5, gy + py * 2.5),
            ]
            poly(blade_col, b_pts)
            line(steel_hi, [(gx, gy), (tx, ty)], 1)

        # --- ВЕТКА СИЛЫ (BODY) ---
        if glyph == "whirlwind":
            for r, a0, a1, col, w in (
                (12, 0.2, 2.9, warm_d, 4),
                (12, 3.3, 6.0, warm_d, 4),
                (11, 0.3, 2.8, warm, 3),
                (11, 3.4, 5.9, warm, 3),
                (8, 0.8, 3.5, warm_hi, 2),
                (8, 4.0, 6.5, warm_hi, 2),
            ):
                pygame.draw.arc(icon, col, (16 - r, 16 - r, r * 2, r * 2), a0, a1, w)
            dagger_shape((9, 23), (24, 8), steel_hi, gold)
            for sx, sy in ((6, 9), (26, 22), (23, 6), (8, 25)):
                pygame.draw.rect(icon, warm_hi, (sx, sy, 2, 2))

        elif glyph == "earth_slam":
            # Трещины расколотой земли снизу
            outlined_line(warm_d, [(3, 25), (10, 22), (16, 26), (22, 22), (29, 25)], 3)
            line(warm_hi, [(4, 25), (10, 22), (16, 26), (22, 22), (28, 25)], 1)
            line(warm, [(16, 22), (12, 29)], 2)
            line(warm, [(16, 22), (21, 29)], 2)
            # Падающий сверху молот
            outlined_line(wood, [(16, 3), (16, 19)], 3)
            poly(steel_d, [(9, 12), (23, 12), (24, 19), (8, 19)])
            poly(steel, [(10, 13), (22, 13), (22, 17), (10, 17)], outline=False)
            pygame.draw.circle(icon, warm_hi, (16, 21), 3)
            # Взлетающие камни
            poly(warm, [(5, 18), (8, 16), (7, 20)], outline=False)
            poly(warm, [(24, 17), (27, 19), (25, 21)], outline=False)

        elif glyph == "heavy_strike":
            # Яркая вспышка сокрушающего удара в верхнем правом углу
            cx, cy = 21, 11
            for ang in range(0, 360, 45):
                rad = math.radians(ang)
                r_len = 9 if ang % 90 == 0 else 6
                line(warm, [(cx, cy), (cx + math.cos(rad) * r_len, cy + math.sin(rad) * r_len)], 2)
            pygame.draw.circle(icon, crimson, (cx, cy), 6)
            pygame.draw.circle(icon, warm_hi, (cx, cy), 3)
            # Массивная палица/кувалда по диагонали
            outlined_line(wood, [(6, 26), (19, 13)], 3)
            poly(steel, [(15, 7), (25, 7), (25, 17), (15, 17)])
            line(steel_hi, [(17, 9), (23, 9), (23, 15)], 1)

        elif glyph == "shield_bash":
            # Энергетические золотые дуги по бокам
            pygame.draw.arc(icon, warm_hi, (2, 4, 28, 24), 2.3, 4.0, 2)
            pygame.draw.arc(icon, warm_hi, (2, 4, 28, 24), -0.8, 0.9, 2)
            # Рыцарский башенный щит
            sh_pts = [(8, 5), (24, 5), (23, 19), (16, 28), (9, 19)]
            poly(gold, sh_pts)
            in_pts = [(10, 7), (22, 7), (21, 18), (16, 25), (11, 18)]
            poly(steel_d, in_pts, outline=False)
            # Крест и умбон на щите
            line(gold, [(16, 8), (16, 24)], 2)
            line(gold, [(11, 14), (21, 14)], 2)
            pygame.draw.circle(icon, warm_hi, (16, 14), 3)

        elif glyph == "cleave":
            # Широкая багрово-оранжевая волна рассечения
            pygame.draw.arc(icon, crimson, (3, 3, 26, 26), -0.4, 2.3, 6)
            pygame.draw.arc(icon, warm, (4, 4, 24, 24), -0.3, 2.2, 4)
            pygame.draw.arc(icon, warm_hi, (5, 5, 22, 22), -0.2, 2.0, 2)
            # Лезвие топора/тесака
            outlined_line(wood, [(7, 25), (21, 11)], 3)
            poly(steel, [(15, 6), (25, 8), (26, 18), (18, 15)])
            line(steel_hi, [(16, 7), (24, 9), (25, 17)], 1)

        elif glyph == "war_stomp":
            # Реактивные линии рывка слева
            for sy, lx in ((9, 11), (15, 9), (21, 12)):
                outlined_line(warm, [(4, sy), (lx, sy)], 2)
            # Бронированный таран / латный сапог, бьющий вперёд
            poly(steel, [(11, 7), (20, 7), (20, 18), (26, 21), (26, 25), (11, 25)])
            line(gold, [(12, 9), (19, 9)], 2)
            line(steel_hi, [(13, 11), (13, 22), (24, 22)], 2)
            # Лобовая ударная волна справа
            pygame.draw.arc(icon, warm_hi, (14, 5, 16, 22), -1.1, 1.1, 3)

        # --- ВЕТКА ЛОВКОСТИ (CUNNING) ---
        elif glyph == "throw_knife":
            # Потоки рассекаемого воздуха
            line(teal, [(4, 18), (14, 8)], 2)
            line(teal, [(12, 26), (22, 16)], 2)
            line(green_hi, [(5, 23), (11, 17)], 1)
            # Кунай с кольцом на рукояти
            pygame.draw.circle(icon, dark, (7, 25), 4, 3)
            pygame.draw.circle(icon, gold, (7, 25), 3, 2)
            dagger_shape((9, 23), (26, 6), steel_hi, teal)

        elif glyph == "poison_flask":
            # Горлышко и пробка
            poly(wood, [(13, 4), (19, 4), (18, 8), (14, 8)])
            pygame.draw.rect(icon, steel, (12, 7, 8, 3))
            # Колба
            pygame.draw.circle(icon, dark, (16, 19), 10)
            pygame.draw.circle(icon, (30, 65, 45), (16, 19), 8)
            # Ядовитая жидкость внутри
            pygame.draw.arc(icon, green, (8, 11, 16, 16), 3.14, 6.28, 8)
            pygame.draw.ellipse(icon, green_hi, (10, 17, 12, 5))
            pygame.draw.circle(icon, steel_hi, (16, 19), 8, 2)
            # Пузырьки яда и блик стекла
            pygame.draw.circle(icon, green_hi, (14, 14), 2)
            pygame.draw.circle(icon, green, (18, 12), 1)
            pygame.draw.circle(icon, green_hi, (20, 5), 2)
            line(steel_hi, [(10, 16), (10, 20)], 1)

        elif glyph == "piercing_shot":
            # Багровая метка прицела (уязвимая точка)
            pygame.draw.circle(icon, crimson, (19, 13), 7, 2)
            line(crimson, [(10, 13), (28, 13)], 2)
            line(crimson, [(19, 4), (19, 22)], 2)
            # Пронзающий метку кинжал
            dagger_shape((6, 26), (26, 6), steel_hi, crimson)
            pygame.draw.circle(icon, warm_hi, (19, 13), 3)

        elif glyph == "hamstring":
            # Изумрудная дуга акробатического отскока
            pygame.draw.arc(icon, green, (4, 10, 24, 18), 0.3, 2.9, 3)
            pygame.draw.arc(icon, green_hi, (6, 12, 20, 14), 0.5, 2.7, 1)
            # Лёгкий сапог ловкача с крылышком
            poly(wood, [(13, 6), (20, 6), (19, 16), (25, 19), (24, 23), (12, 21)])
            line(teal, [(14, 8), (19, 8)], 2)
            # Крылышко скорости на пятке
            poly(green_hi, [(12, 13), (5, 9), (8, 15), (4, 17), (12, 18)], outline=False)

        elif glyph == "fan_blades":
            # Дуги раскрытого стального капкана
            pygame.draw.arc(icon, dark, (3, 9, 26, 16), 0, math.pi, 5)
            pygame.draw.arc(icon, steel, (4, 10, 24, 14), 0, math.pi, 3)
            pygame.draw.arc(icon, dark, (3, 11, 26, 15), math.pi, math.tau, 5)
            pygame.draw.arc(icon, steel_d, (4, 12, 24, 13), math.pi, math.tau, 3)
            # Нажимная педаль в центре
            pygame.draw.circle(icon, gold, (16, 18), 3)
            # Острые зубья с каплями зелёного яда
            for px in (6, 11, 16, 21, 26):
                poly(steel_hi, [(px - 2, 17), (px, 10), (px + 2, 17)])
                pygame.draw.rect(icon, green, (px - 1, 10, 2, 3))

        elif glyph == "venom_strike":
            # Клубы ночного дыма снизу
            for cx_s, cy_s, r_s in ((9, 25, 5), (23, 25, 5), (16, 26, 6)):
                pygame.draw.circle(icon, shadow_d, (cx_s, cy_s), r_s)
            # Очертания глубокого капюшона тени
            hood = [(16, 4), (7, 11), (5, 25), (27, 25), (25, 11)]
            poly(shadow, hood)
            inner_void = [(16, 8), (10, 13), (9, 23), (23, 23), (22, 13)]
            poly(dark, inner_void, outline=False)
            # Светящиеся из темноты хищные глаза
            line(teal, [(11, 15), (14, 16)], 2)
            line(teal, [(21, 15), (18, 16)], 2)
            pygame.draw.rect(icon, green_hi, (12, 15, 2, 2))
            pygame.draw.rect(icon, green_hi, (19, 15, 2, 2))

        # --- ВЕТКА РАЗУМА (MIND) ---
        elif glyph == "firebolt":
            # Хвост кометы и угли
            poly(crimson, [(4, 28), (10, 14), (24, 6), (18, 22)])
            poly(warm, [(7, 25), (12, 14), (25, 7), (18, 20)], outline=False)
            # Ядро огненного снаряда
            pygame.draw.circle(icon, crimson, (20, 12), 8)
            pygame.draw.circle(icon, warm, (20, 12), 6)
            pygame.draw.circle(icon, warm_hi, (21, 11), 4)
            pygame.draw.circle(icon, (255, 255, 240), (22, 10), 2)
            for sx, sy in ((5, 20), (13, 27), (8, 12)):
                pygame.draw.rect(icon, warm_hi, (sx, sy, 2, 2))

        elif glyph == "ignite":
            # Огненное кольцо у подножия
            pygame.draw.ellipse(icon, crimson, (4, 20, 24, 8), 3)
            pygame.draw.ellipse(icon, warm_hi, (6, 21, 20, 6), 1)
            # Взмывающая корона пламени
            outer_fl = [(8, 24), (5, 14), (11, 17), (16, 4), (21, 17), (27, 14), (24, 24)]
            inner_fl = [(11, 24), (10, 16), (16, 8), (22, 16), (21, 24)]
            core_fl = [(13, 24), (16, 13), (19, 24)]
            poly(crimson, outer_fl)
            poly(warm, inner_fl, outline=False)
            poly(warm_hi, core_fl, outline=False)

        elif glyph == "frost":
            # Внешнее ледяное кольцо
            pygame.draw.circle(icon, cold_d, (16, 16), 11, 2)
            # 6 кристаллических лучей снежинки
            for a in range(0, 360, 60):
                rad = math.radians(a)
                dx, dy = math.cos(rad), math.sin(rad)
                px, py = -dy, dx
                outlined_line(cold, [(16, 16), (16 + dx * 13, 16 + dy * 13)], 2)
                for sign in (-1, 1):
                    bx, by = 16 + dx * 8, 16 + dy * 8
                    tx, ty = bx + dx * 3 + px * sign * 4, by + dy * 3 + py * sign * 4
                    line(cold_hi, [(bx, by), (tx, ty)], 2)
            # Центральный ледяной кристалл
            poly(cold_hi, [(16, 11), (21, 16), (16, 21), (11, 16)])

        elif glyph == "lightning":
            # Боковые ветви разряда
            line(cold, [(15, 14), (6, 19), (4, 24)], 2)
            line(cold, [(19, 16), (27, 21)], 2)
            # Главный зигзаг молнии
            bolt = [(20, 3), (8, 16), (16, 16), (10, 29), (25, 13), (17, 13)]
            poly(cold, bolt)
            line(cold_hi, [(19, 5), (10, 15), (17, 15), (12, 26)], 2)
            pygame.draw.circle(icon, cold_hi, (11, 27), 3)

        elif glyph == "renewal":
            # Изумрудный целительный крест на фоне
            poly(green_d, [(13, 6), (19, 6), (19, 26), (13, 26)])
            poly(green_d, [(6, 13), (26, 13), (26, 19), (6, 19)])
            pygame.draw.rect(icon, green, (14, 7, 4, 18))
            pygame.draw.rect(icon, green, (7, 14, 18, 4))
            # Сияющий росток/лист в центре и спираль светлячков
            pygame.draw.arc(icon, green_hi, (4, 4, 24, 24), 0.4, 4.8, 2)
            poly(green_hi, [(16, 10), (21, 16), (16, 22), (11, 16)], outline=False)
            for fx, fy in ((8, 8), (24, 9), (7, 23), (24, 23)):
                pygame.draw.circle(icon, warm_hi, (fx, fy), 2)

        elif glyph == "roots":
            # Переплетённые шипастые корни
            r1 = [(7, 28), (11, 20), (9, 12), (14, 5)]
            r2 = [(16, 29), (15, 19), (19, 11), (17, 4)]
            r3 = [(25, 28), (21, 20), (24, 12), (20, 6)]
            for pts_r in (r1, r2, r3):
                outlined_line(wood, pts_r, 3)
                line(green_d, pts_r, 1)
            # Поперечные путы и изумрудные листья/шипы
            outlined_line(green, [(6, 18), (16, 15), (26, 18)], 2)
            for lx, ly in ((9, 12), (19, 11), (14, 5), (23, 13), (11, 21)):
                poly(green_hi, [(lx, ly - 3), (lx + 3, ly), (lx, ly + 2), (lx - 2, ly)], outline=False)

        elif glyph == "firm_stance":
            # Copper-rimmed shield dug into the earth.
            poly((104, 61, 54), [(4, 26), (10, 24), (13, 25), (21, 24), (28, 27), (24, 29), (7, 29)])
            line((192, 110, 63), [(6, 27), (12, 26), (15, 27), (22, 25), (26, 27)], 1)
            poly(gold, [(8, 7), (16, 4), (24, 7), (24, 16), (21, 22), (16, 26), (11, 22), (8, 16)])
            poly((100, 120, 151), [(10, 9), (16, 7), (22, 9), (22, 16), (19, 21), (16, 24), (12, 20), (10, 16)], False)
            poly(steel, [(10, 9), (16, 7), (16, 23), (12, 20), (10, 16)], False)
            poly((91, 51, 49), [(16, 10), (20, 14), (16, 20), (12, 14)], False)
            poly(warm_hi, [(16, 11), (18, 14), (16, 17), (14, 14)], False)
            line(steel_hi, [(9, 9), (9, 15)], 1)

        elif glyph == "wide_swing":
            # Broad axe and a graduated crescent of motion.
            poly(warm_d, [(4, 23), (9, 12), (17, 6), (24, 5), (29, 8), (23, 8), (15, 13), (8, 21), (7, 27)])
            poly(warm, [(5, 24), (10, 14), (18, 8), (25, 6), (29, 8), (24, 8), (17, 11), (11, 17)], False)
            line(warm_hi, [(6, 20), (10, 14), (17, 9), (24, 7)], 1)
            outlined_line(wood, [(10, 27), (24, 13)], 3)
            line(gold, [(12, 25), (19, 18)], 1)
            poly(steel_d, [(19, 12), (25, 10), (29, 15), (28, 20), (24, 22), (22, 17), (18, 15)])
            poly(steel, [(25, 11), (29, 15), (28, 20), (24, 22), (26, 17)], False)
            line(steel_hi, [(28, 15), (27, 19), (25, 21)], 1)
            icon.set_at((8, 10), warm_hi)
            icon.set_at((14, 5), warm)

        elif glyph == "armor_breaker":
            # A split breastplate, backlit by the blow.
            poly(steel_d, [(7, 8), (12, 5), (15, 8), (18, 8), (21, 5), (26, 8), (25, 14),
                           (22, 16), (22, 24), (18, 27), (10, 26), (10, 17), (7, 14)])
            poly(steel, [(8, 9), (12, 6), (15, 9), (12, 14), (10, 16), (8, 13)], False)
            poly(steel, [(19, 9), (21, 6), (25, 9), (23, 13), (18, 15), (17, 12)], False)
            poly((163, 174, 193), [(13, 17), (16, 19), (20, 19), (20, 24), (17, 26), (11, 25), (11, 21)], False)
            outlined_line(crimson, [(18, 8), (14, 14), (18, 16), (13, 21), (17, 23), (15, 28)], 2)
            line(warm_hi, [(18, 9), (15, 14), (18, 16), (14, 21), (17, 23)], 1)
            line(warm, [(5, 16), (8, 18)], 1)
            line(warm_hi, [(24, 18), (27, 16)], 1)

        elif glyph == "sidestep":
            # A boot cutting diagonally across two fading trails.
            line(green_d, [(4, 23), (13, 23), (4, 28)], 2)
            line(teal, [(5, 18), (13, 18), (7, 21)], 1)
            poly((73, 117, 93), [(16, 6), (25, 8), (24, 13), (20, 18),
                                  (21, 21), (27, 22), (27, 25), (16, 26), (12, 23), (14, 17)])
            poly((135, 193, 132), [(17, 7), (24, 9), (21, 14), (15, 16)], False)
            line(green_hi, [(17, 8), (22, 10)], 2)
            line((35, 67, 59), [(13, 22), (17, 24), (25, 24)], 2)
            line(green_hi, [(16, 17), (19, 18)], 1)
            line(green_hi, [(15, 20), (18, 20)], 1)

        elif glyph == "quiet_work":
            # A dagger silhouetted against a crescent, in deep teal shadow.
            poly((57, 112, 109), [(19, 4), (11, 5), (7, 9), (5, 15), (6, 21), (10, 25), (16, 27),
                                   (21, 24), (15, 23), (11, 18), (10, 13), (13, 8)], False)
            line(green_hi, [(18, 4), (11, 6), (8, 10), (6, 15), (7, 20), (10, 23)], 1)
            dagger_shape((12, 25), (26, 9), (123, 191, 181), (116, 188, 120))
            line(shadow, [(16, 27), (22, 26), (26, 23)], 1)
            for point in ((23, 6), (27, 17), (22, 20)):
                icon.set_at(point, teal)

        elif glyph == "change_target":
            # Two targets linked by a bent arrow.
            pygame.draw.circle(icon, (44, 103, 85), (10, 20), 5, 1)
            pygame.draw.circle(icon, teal, (10, 20), 2, 1)
            pygame.draw.circle(icon, green_d, (22, 10), 6, 2)
            pygame.draw.circle(icon, green_hi, (22, 10), 5, 1)
            pygame.draw.circle(icon, (230, 253, 181), (22, 10), 2)
            outlined_line(green, [(10, 24), (16, 26), (22, 24), (26, 20), (27, 16)], 2)
            poly(green_hi, [(24, 18), (27, 14), (29, 19), (27, 18)], False)
            line(teal, [(6, 14), (10, 10), (14, 9)], 1)
            icon.set_at((19, 24), green_hi)

        elif glyph == "divine_pact":
            # Three schools meet around a shared center.
            centers = ((16, 7, warm_d, warm, warm_hi), (8, 21, green_d, green, green_hi),
                       (24, 21, cold_d, cold, cold_hi))
            outlined_line(shadow, [(16, 7), (8, 21), (24, 21), (16, 7)], 3)
            line(shadow_hi, [(16, 7), (8, 21), (24, 21), (16, 7)], 1)
            for cx, cy, low, mid, high in centers:
                pygame.draw.circle(icon, dark, (cx, cy), 6)
                pygame.draw.circle(icon, low, (cx, cy), 5)
                pygame.draw.circle(icon, mid, (cx - 1, cy - 1), 3)
                line(high, [(cx - 2, cy), (cx - 2, cy - 2), (cx, cy - 3)], 1)
            poly(cold_hi, [(16, 13), (18, 17), (16, 19), (14, 17)], False)

        elif glyph == "spell_focus":
            # Glass hourglass and a returning arc.
            pygame.draw.arc(icon, cold_d, (3, 3, 26, 26), 0.10, 4.7, 2)
            pygame.draw.arc(icon, cold, (4, 4, 24, 24), 0.22, 2.8, 1)
            poly(cold_hi, [(15, 26), (10, 29), (16, 30)], False)
            poly((43, 72, 130), [(10, 7), (22, 7), (21, 12), (17, 16), (21, 20),
                                   (22, 25), (10, 25), (11, 20), (15, 16), (11, 12)])
            line(cold_hi, [(11, 8), (12, 12), (16, 16), (12, 20), (11, 24)], 1)
            line(cold, [(21, 8), (20, 12), (16, 16), (20, 20), (21, 24)], 1)
            poly(warm_hi, [(13, 11), (19, 11), (16, 15)], False)
            poly(gold, [(16, 20), (20, 24), (12, 24)], False)
            line(shadow_hi, [(10, 7), (22, 7)], 2)
            line(shadow_hi, [(10, 25), (22, 25)], 2)

        elif glyph == "warding_pulse":
            # Descending rings under a ward crystal.
            for bounds, color in (((3, 13, 26, 13), cold_d), ((5, 12, 22, 12), shadow),
                                  ((8, 13, 16, 8), cold)):
                pygame.draw.ellipse(icon, color, bounds, 1)
            line(cold_hi, [(5, 22), (10, 25), (16, 26), (22, 25), (27, 22)], 1)
            poly((82, 125, 198), [(16, 4), (22, 10), (21, 16), (16, 21), (11, 16), (10, 10)])
            poly(cold, [(16, 5), (16, 19), (12, 15), (11, 11)], False)
            poly(shadow_hi, [(16, 7), (20, 11), (16, 15), (13, 11)], False)
            line(cold_hi, [(16, 6), (12, 11), (16, 14)], 1)
            for sx, sy in ((7, 11), (25, 11), (4, 17), (28, 17), (16, 28)):
                icon.set_at((sx, sy), cold_hi)

        CACHE[key] = pygame.transform.scale(icon, (size, size))
    surface.blit(CACHE[key], (x, y))
    return True