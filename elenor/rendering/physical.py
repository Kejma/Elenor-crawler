"""Directional weapon motion, thrown objects, traps and timed stances."""

import math
import pygame
from elenor.config import TILE_W, TILE_H, VIEW_W, VIEW_H, SCALE
from elenor.rendering.visibility import mask_overlay


def render_physical(screen, game, cam_x, cam_y, visibility):
    states = getattr(game, "physical_effects", [])
    if not states:
        return
    surface = getattr(game, "_physical_surface", None)
    if surface is None:
        surface = pygame.Surface((VIEW_W * SCALE, VIEW_H * SCALE), pygame.SRCALPHA)
        game._physical_surface = surface
    surface.fill((0, 0, 0, 0))

    now_sec = pygame.time.get_ticks() * 0.001

    def point(x, y):
        return (int((x * TILE_W - cam_x) * SCALE), int((y * TILE_H - cam_y) * SCALE))

    for state in states:
        kind = state["kind"]
        item = state["item"]
        progress = max(0.0, min(1.0, 1.0 - state["timer"] / max(0.001, state["max_timer"])))
        fade = max(0.15, 1.0 - progress * 0.75)
        x, y = state["x"], state["y"]
        nx, ny = state["nx"], state["ny"]
        angle = math.atan2(ny, nx)
        px_perp, py_perp = -ny, nx

        if kind in ("guard", "stealth", "evade", "charge"):
            x, y = game.player.x, game.player.y
        cx, cy = point(x, y - 0.2)
        foot_cx, foot_cy = point(x, y + 0.05)

        r_c, g_c, b_c = item.color

        if kind == "knife":
            # Длинный бирюзовый воздушный след + детальный кунай
            trail_len = 36
            tail_pt = (int(cx - nx * trail_len), int(cy - ny * trail_len))
            pygame.draw.line(surface, (90, 235, 195, 135), tail_pt, (cx, cy), 6)
            pygame.draw.line(surface, (215, 255, 245, 210), (int(cx - nx * 22), int(cy - ny * 22)), (cx, cy), 2)

            tip = (int(cx + nx * 16), int(cy + ny * 16))
            guard = (int(cx - nx * 4), int(cy - ny * 4))
            pommel = (int(cx - nx * 13), int(cy - ny * 13))
            g1 = (int(guard[0] + px_perp * 6), int(guard[1] + py_perp * 6))
            g2 = (int(guard[0] - px_perp * 6), int(guard[1] - py_perp * 6))
            blade_poly = [
                tip,
                (int(guard[0] + px_perp * 4), int(guard[1] + py_perp * 4)),
                (int(guard[0] - px_perp * 4), int(guard[1] - py_perp * 4)),
            ]
            pygame.draw.line(surface, (140, 85, 45, 255), pommel, guard, 4)
            pygame.draw.circle(surface, (240, 195, 75, 255), pommel, 4, 2)
            pygame.draw.line(surface, (240, 195, 75, 255), g1, g2, 3)
            pygame.draw.polygon(surface, (20, 18, 28, 255), blade_poly, 3)
            pygame.draw.polygon(surface, (220, 235, 250, 255), blade_poly, 0)
            pygame.draw.line(surface, (255, 255, 255, 255), guard, tip, 2)

        elif kind == "flask":
            # Тень на полу + параболическая дуга полёта склянки со шлейфом пузырьков
            flight_p = 1.0 - state["remaining"] / max(0.001, state.get("total_distance", 6.0))
            arc_h = int(28 * math.sin(flight_p * math.pi))
            pygame.draw.ellipse(surface, (15, 20, 18, 120), (cx - 8, cy + 4, 16, 7))
            fy = cy - arc_h
            # Шлейф ядовитых капель позади
            for b_i in range(1, 4):
                bx = int(cx - nx * b_i * 8 + math.sin(now_sec * 12 + b_i) * 3)
                by = int(fy - ny * b_i * 8 + b_i * 2)
                pygame.draw.circle(surface, (95, 235, 115, 190 - b_i * 45), (bx, by), 4 - b_i // 2)
            # Сама колба
            pygame.draw.circle(surface, (20, 35, 25, 255), (cx, fy), 10)
            pygame.draw.circle(surface, (75, 215, 95, 240), (cx, fy), 8)
            pygame.draw.circle(surface, (185, 255, 190, 255), (cx - 2, fy - 2), 3)
            pygame.draw.circle(surface, (210, 240, 230, 255), (cx, fy), 9, 2)
            pygame.draw.rect(surface, (165, 115, 65, 255), (cx - 3, fy - 13, 6, 5))

        elif kind == "trap":
            # Стальной медвежий капкан на полу
            tx_p, ty_p = point(x, y)
            is_armed = state.get("armed", 0.0) <= 0.0
            pygame.draw.ellipse(surface, (25, 28, 36, 210), (tx_p - 17, ty_p - 10, 34, 20))
            pygame.draw.ellipse(surface, (155, 165, 180, 255), (tx_p - 15, ty_p - 8, 30, 16), 3)
            # Центральная нажимная пластина
            plate_col = (95, 235, 145, 245) if is_armed else (235, 155, 70, 220)
            pygame.draw.circle(surface, (55, 60, 72, 255), (tx_p, ty_p), 5)
            pygame.draw.circle(surface, plate_col, (tx_p, ty_p), 3)
            # Острые зубья с ядом
            for offset in (-11, -5, 0, 5, 11):
                pygame.draw.polygon(
                    surface,
                    (225, 235, 245, 255),
                    [(tx_p + offset - 2, ty_p - 5), (tx_p + offset, ty_p - 12), (tx_p + offset + 2, ty_p - 5)],
                )
                pygame.draw.polygon(
                    surface,
                    (200, 210, 225, 255),
                    [(tx_p + offset - 2, ty_p + 5), (tx_p + offset, ty_p + 11), (tx_p + offset + 2, ty_p + 5)],
                )
                if is_armed and offset in (-5, 5):
                    pygame.draw.circle(surface, (95, 245, 125, 240), (tx_p + offset, ty_p - 11), 2)

        elif kind == "guard":
            # Железная стойка: руническое кольцо у ног + 3 парящих щита вокруг героя
            pulse = int(math.sin(now_sec * 6.0) * 3)
            pygame.draw.ellipse(surface, (245, 185, 75, 155), (foot_cx - 28 - pulse, foot_cy - 10, 56 + pulse * 2, 20), 3)
            pygame.draw.ellipse(surface, (255, 235, 165, 120), (foot_cx - 22, foot_cy - 7, 44, 14), 1)
            for s_i in range(3):
                a_sh = now_sec * 2.8 + s_i * (math.tau / 3.0)
                sx_sh = cx + int(math.cos(a_sh) * 26)
                sy_sh = cy + int(math.sin(a_sh) * 14)
                sh_poly = [
                    (sx_sh - 7, sy_sh - 9),
                    (sx_sh + 7, sy_sh - 9),
                    (sx_sh + 6, sy_sh + 2),
                    (sx_sh, sy_sh + 10),
                    (sx_sh - 6, sy_sh + 2),
                ]
                pygame.draw.polygon(surface, (70, 55, 35, 185), sh_poly, 0)
                pygame.draw.polygon(surface, (245, 195, 85, 235), sh_poly, 2)
                pygame.draw.line(surface, (255, 245, 200, 210), (sx_sh, sy_sh - 6), (sx_sh, sy_sh + 6), 2)
                pygame.draw.line(surface, (255, 245, 200, 210), (sx_sh - 4, sy_sh - 2), (sx_sh + 4, sy_sh - 2), 2)

        elif kind == "stealth":
            # Уход в тень: кольцо мрака у ног + вращающиеся серпы теневого дыма
            pygame.draw.ellipse(surface, (45, 55, 95, 155), (foot_cx - 26, foot_cy - 9, 52, 18), 4)
            for w_i in range(4):
                a_w = now_sec * 3.2 + w_i * (math.pi * 0.5)
                wx_s = cx + int(math.cos(a_w) * 18)
                wy_s = cy + int(math.sin(a_w * 1.5) * 14) - 4
                pygame.draw.arc(
                    surface,
                    (95, 135, 195, 165),
                    (wx_s - 14, wy_s - 14, 28, 28),
                    a_w,
                    a_w + 2.1,
                    4,
                )
            # Призрачный контур капюшона над головой
            pygame.draw.arc(surface, (140, 210, 235, 145), (cx - 20, cy - 36, 40, 52), 0.35, math.pi - 0.35, 3)

        elif kind == "charge":
            # Таран: мощный лобовой клин ударной волны + реактивные шлейфы сзади
            front_x, front_y = cx + nx * 22, cy + ny * 22
            wing1 = (int(front_x - nx * 24 + px_perp * 26), int(front_y - ny * 24 + py_perp * 26))
            wing2 = (int(front_x - nx * 24 - px_perp * 26), int(front_y - ny * 24 - py_perp * 26))
            apex = (int(front_x + nx * 10), int(front_y + ny * 10))
            pygame.draw.lines(surface, (245, 135, 45, 220), False, [wing1, apex, wing2], 7)
            pygame.draw.lines(surface, (255, 240, 165, 245), False, [wing1, apex, wing2], 3)
            for idx_t, offset in enumerate((14, 28, 42)):
                spread = (idx_t - 1) * 10
                p0 = (int(cx - nx * offset + px_perp * spread), int(cy - ny * offset + py_perp * spread))
                p1 = (int(p0[0] - nx * 18), int(p0[1] - ny * 18))
                pygame.draw.line(surface, (245, 165, 70, 210 - idx_t * 45), p0, p1, 4)

        elif kind == "evade":
            # Отскок: призрачные силуэты-фантомы позади + спиральные потоки ветра
            for g_i in (1, 2, 3):
                gx = int(cx - nx * g_i * 16)
                gy = int(cy - ny * g_i * 16)
                alpha_g = max(35, 165 - g_i * 42)
                pygame.draw.ellipse(surface, (95, 235, 175, alpha_g), (gx - 10, gy - 18, 20, 34), 2)
                w1 = (int(gx + px_perp * 12), int(gy + py_perp * 12))
                w2 = (int(gx - px_perp * 12), int(gy - py_perp * 12))
                pygame.draw.line(surface, (185, 255, 225, alpha_g), w1, w2, 2)

        elif item.id == "earth_slam":
            # Раскол земли: 5 зубчатых трещин с лавой внутри + дуговая волна + осколки камней
            max_r = item.aoe_radius * TILE_W * SCALE * (0.25 + 0.75 * progress)
            for side in (-0.52, -0.26, 0.0, 0.26, 0.52):
                pts = [(cx, cy)]
                for step in range(1, 6):
                    frac = step / 5.0
                    jag = (0.09 if (step + int(side * 10)) % 2 == 0 else -0.09) * (1.0 - frac * 0.3)
                    a = angle + side + jag
                    pts.append((int(cx + math.cos(a) * max_r * frac), int(cy + math.sin(a) * max_r * frac)))
                pygame.draw.lines(surface, (55, 28, 18, int(230 * fade)), False, pts, 7)
                pygame.draw.lines(surface, (245, 130, 40, int(245 * fade)), False, pts, 4)
                pygame.draw.lines(surface, (255, 235, 140, int(255 * fade)), False, pts, 2)
                # Каменные глыбы на концах разломов
                rx_end, ry_end = pts[-1]
                rock_sz = max(3, int(6 * (1.0 - progress * 0.4)))
                pygame.draw.polygon(
                    surface,
                    (145, 115, 90, int(240 * fade)),
                    [
                        (rx_end - rock_sz, ry_end),
                        (rx_end, ry_end - rock_sz - 3),
                        (rx_end + rock_sz, ry_end - 1),
                        (rx_end, ry_end + rock_sz),
                    ],
                )
            # Дуговая ударная волна по фронту раскола
            arc_pts = [
                (
                    int(cx + math.cos(angle - 0.6 + 1.2 * i / 10.0) * max_r),
                    int(cy + math.sin(angle - 0.6 + 1.2 * i / 10.0) * max_r),
                )
                for i in range(11)
            ]
            pygame.draw.lines(surface, (255, 195, 85, int(210 * fade)), False, arc_pts, 3)

        elif kind == "target":
            # Сокрушение: мощный след удара + взрывной кратер с лучами в точке попадания
            reach = (0.55 + 0.55 * min(1.0, progress * 1.6)) * item.aoe_radius * TILE_W * SCALE * 0.72
            ex, ey = int(cx + math.cos(angle) * reach), int(cy + math.sin(angle) * reach)
            pygame.draw.line(surface, (245, 135, 45, int(220 * fade)), (cx, cy), (ex, ey), 10)
            pygame.draw.line(surface, (255, 240, 170, int(245 * fade)), (cx, cy), (ex, ey), 4)
            ring_r = int(10 + 26 * progress)
            pygame.draw.circle(surface, (245, 125, 35, int(225 * fade)), (ex, ey), ring_r, 4)
            pygame.draw.circle(surface, (255, 245, 190, int(240 * fade)), (ex, ey), max(4, int(14 * (1.0 - progress * 0.5))))
            for r_i in range(6):
                ra = angle + r_i * (math.tau / 6.0)
                r_out = ring_r + 8
                pygame.draw.line(
                    surface,
                    (255, 220, 110, int(235 * fade)),
                    (int(ex + math.cos(ra) * 5), int(ey + math.sin(ra) * 5)),
                    (int(ex + math.cos(ra) * r_out), int(ey + math.sin(ra) * r_out)),
                    3,
                )

        elif kind == "execute":
            # Добивание: стремительный выпад + ало-изумрудная X-образная метка казни на цели
            reach = (0.5 + 0.5 * min(1.0, progress * 1.8)) * item.aoe_radius * TILE_W * SCALE * 0.78
            ex, ey = int(cx + math.cos(angle) * reach), int(cy + math.sin(angle) * reach)
            pygame.draw.line(surface, (85, 235, 175, int(220 * fade)), (cx, cy), (ex, ey), 5)
            pygame.draw.line(surface, (235, 255, 245, int(250 * fade)), (cx, cy), (ex, ey), 2)
            slash_r = int(14 + 12 * math.sin(progress * math.pi))
            for diag in (-0.78, 0.78):
                da = angle + diag
                p0 = (int(ex - math.cos(da) * slash_r), int(ey - math.sin(da) * slash_r))
                p1 = (int(ex + math.cos(da) * slash_r), int(ey + math.sin(da) * slash_r))
                pygame.draw.line(surface, (225, 45, 65, int(240 * fade)), p0, p1, 6)
                pygame.draw.line(surface, (255, 230, 235, int(255 * fade)), p0, p1, 2)
            pygame.draw.circle(surface, (255, 245, 200, int(245 * fade)), (ex, ey), 5)

        elif kind == "sweep":
            # Вихрь: двойная спиральная волна лезвий на 360 градусов
            radius = int(item.aoe_radius * TILE_W * SCALE)
            head_a = angle + progress * math.tau * 1.25
            for blade_off in (0.0, math.pi):
                outer_pts = []
                core_pts = []
                for step in range(15):
                    frac = step / 14.0
                    a = head_a + blade_off - frac * math.pi * 0.92
                    r_cur = radius * (0.98 - frac * 0.24)
                    pt = (int(cx + math.cos(a) * r_cur), int(cy + math.sin(a) * r_cur))
                    outer_pts.append(pt)
                    if step < 9:
                        core_pts.append(pt)
                pygame.draw.lines(surface, (195, 70, 25, int(195 * fade)), False, outer_pts, 11)
                pygame.draw.lines(surface, (r_c, g_c, b_c, int(235 * fade)), False, outer_pts, 6)
                pygame.draw.lines(surface, (255, 248, 215, int(255 * fade)), False, core_pts, 3)

        else:
            # Рассечение (cone): многослойный полумесяц широкого взмаха секиры
            radius = int(item.aoe_radius * TILE_W * SCALE * (0.65 + 0.35 * progress))
            span = math.pi * 0.72
            start = angle - span * 0.5
            Sweep_steps = max(4, int(14 * min(1.0, progress * 1.4)))
            outer_pts = []
            inner_pts = []
            for t_i in range(Sweep_steps + 1):
                a = start + span * (t_i / 14.0)
                outer_pts.append((int(cx + math.cos(a) * radius), int(cy + math.sin(a) * radius)))
                inner_pts.append((int(cx + math.cos(a) * (radius * 0.76)), int(cy + math.sin(a) * (radius * 0.76))))
            if len(outer_pts) >= 2:
                pygame.draw.lines(surface, (185, 50, 30, int(190 * fade)), False, inner_pts, 10)
                pygame.draw.lines(surface, (r_c, g_c, b_c, int(235 * fade)), False, outer_pts, 8)
                pygame.draw.lines(surface, (255, 245, 210, int(255 * fade)), False, outer_pts, 3)
                # Скоростные линии от героя к краям дуги
                pygame.draw.line(surface, (r_c, g_c, b_c, int(150 * fade)), (cx, cy), outer_pts[0], 2)
                pygame.draw.line(surface, (255, 240, 195, int(210 * fade)), (cx, cy), outer_pts[-1], 3)

    mask_overlay(surface, visibility, game.__dict__)
    screen.blit(surface, (0, 0))