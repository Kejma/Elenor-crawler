import math
import pygame
from elenor.config import TILE_W, TILE_H, VIEW_W, VIEW_H, SCALE
from elenor.rendering.assets import make_pair, enforce_crisp_rim_normals

from elenor.puzzles.optics import SINGLE_FRONT_NORMAL

def _build_mirror_sprite(ori, is_movable=False, is_double=False):
    d_s, n_s = make_pair(16, 20)

    if is_movable:
        for y in range(14, 18):
            for x in range(2, 14):
                col = (110, 118, 135) if y == 14 else (65, 70, 82)
                d_s.set_at((x, y), col)
                n_s.set_at((x, y), (128, 218 if y == 14 else 128, 200, 255))
        for wx in (3, 4, 11, 12):
            d_s.set_at((wx, 18), (35, 38, 46))
            n_s.set_at((wx, 18), (128, 38, 200, 255))
    else:
        for y in range(14, 19):
            for x in range(4, 12):
                if y == 15:
                    col = (225, 180, 70) if x % 2 == 0 else (140, 100, 35)
                else:
                    col = (86, 80, 96) if x < 8 else (62, 58, 72)
                d_s.set_at((x, y), col)
                n_s.set_at((x, y), (45 if x < 6 else (210 if x > 9 else 128), 218 if y == 14 else 128, 200, 255))

    is_backslash = (ori % 2 == 0)

    if is_double:
        for y in range(4, 14):
            rel_y = y - 4
            diag_x = (3 + rel_y) if is_backslash else (12 - rel_y)
            for off in range(-2, 3):
                px = diag_x + off
                if not (2 <= px <= 13):
                    continue
                if abs(off) == 2:
                    col = (245, 200, 70)
                    n_col = (128, 218, 200, 255)
                elif abs(off) == 1:
                    col = (135, 235, 255)
                    n_col = (190, 195, 195, 255) if off > 0 else (65, 195, 195, 255)
                else:
                    col = (250, 255, 255)
                    n_col = (128, 218, 200, 255)
                d_s.set_at((px, y), col)
                n_s.set_at((px, y), n_col)
        for px, py in ((7, 2), (8, 2), (6, 3), (7, 3), (8, 3), (9, 3)):
            d_s.set_at((px, py), (255, 225, 85))
            n_s.set_at((px, py), (128, 218, 200, 255))
    else:
        fnx, fny = SINGLE_FRONT_NORMAL[ori]
        for y in range(4, 14):
            for x in range(3, 13):
                rx = x - 7.5
                ry = y - 8.5
                signed_d = rx * fnx + ry * fny

                if -1.5 <= signed_d <= 2.2:
                    col = (250, 255, 255) if signed_d >= 0.4 else (120, 230, 255)
                    n_col = (190 if fnx > 0 else 65, 195 if fny < 0 else 60, 195, 255)
                    d_s.set_at((x, y), col)
                    n_s.set_at((x, y), n_col)
                elif -6.8 <= signed_d < -1.5:
                    is_rivet = ((x + y) % 3 == 0 and signed_d < -3.0)
                    col = (28, 22, 26) if is_rivet else (56, 38, 32)
                    n_col = (65 if fnx > 0 else 190, 60 if fny < 0 else 195, 195, 255)
                    d_s.set_at((x, y), col)
                    n_s.set_at((x, y), n_col)

    return enforce_crisp_rim_normals(d_s, n_s)


def register_mirror_puzzle_assets(assets):
    # 1. Излучатель Света (активный и выключенный)
    for key, is_lit in (("light_emitter", True), ("light_emitter_off", False)):
        em_d, em_n = make_pair(16, 20)
        for y in range(3, 19):
            w_h = 5 if y >= 15 else (4 if y >= 8 else 3)
            for x in range(8 - w_h, 8 + w_h):
                if 5 <= y <= 9 and 6 <= x <= 9:
                    if is_lit:
                        col = (255, 245, 245) if (x in (7, 8) and y in (6, 7)) else (255, 80, 95)
                    else:
                        col = (52, 46, 58) if (x in (7, 8) and y in (6, 7)) else (36, 32, 42)
                    n_col = (128, 218, 200, 255)
                elif y in (4, 10, 15):
                    col = (205, 165, 70) if is_lit else (115, 95, 55)
                    n_col = (128, 218, 200, 255)
                else:
                    col = (92, 86, 102) if x < 8 else (68, 62, 78)
                    n_col = (45 if x < 6 else (210 if x > 9 else 128), 128, 200, 255)
                em_d.set_at((x, y), col)
                em_n.set_at((x, y), n_col)
        assets[key] = enforce_crisp_rim_normals(em_d, em_n)

    # 2. Приёмник Света
    for state_key, is_on in (("light_receiver_off", False), ("light_receiver_on", True)):
        rc_d, rc_n = make_pair(16, 20)
        for y in range(4, 19):
            w_h = 5 if y >= 14 else 4
            for x in range(8 - w_h, 8 + w_h):
                if 5 <= y <= 10 and 5 <= x <= 10:
                    dist_c = math.hypot(x - 7.5, y - 7.5)
                    if dist_c <= 2.6:
                        if is_on:
                            col = (255, 255, 255) if dist_c <= 1.2 else (255, 95, 110)
                        else:
                            col = (75, 48, 62) if dist_c <= 1.2 else (45, 28, 38)
                        rc_d.set_at((x, y), col)
                        rc_n.set_at((x, y), (128, 218, 200, 255))
                        continue
                col = (195, 155, 65) if y in (11, 15) else ((85, 80, 96) if x < 8 else (62, 58, 72))
                rc_d.set_at((x, y), col)
                rc_n.set_at((x, y), (45 if x < 6 else (210 if x > 9 else 128), 128, 200, 255))
        assets[state_key] = enforce_crisp_rim_normals(rc_d, rc_n)

    # 3. Зеркала
    for ori in range(4):
        assets[f"mirror_rot_{ori}"] = _build_mirror_sprite(ori, is_movable=False, is_double=False)
        assets[f"mirror_move_{ori}"] = _build_mirror_sprite(ori, is_movable=True, is_double=False)
    for ori in range(2):
        assets[f"mirror_double_{ori}"] = _build_mirror_sprite(ori, is_movable=False, is_double=True)

    # 4. Напольные рельсы
    for rail_key, is_horiz in (("mirror_rail_h", True), ("mirror_rail_v", False)):
        rl_d, rl_n = make_pair(16, 20)
        for y in range(4, 20):
            py_tile = y - 4
            for x in range(16):
                if is_horiz:
                    if py_tile in (5, 10):
                        rl_d.set_at((x, y), (135, 142, 160))
                        rl_n.set_at((x, y), (128, 218, 200, 255))
                    elif 5 < py_tile < 10 and x % 4 == 1:
                        rl_d.set_at((x, y), (78, 52, 32))
                        rl_n.set_at((x, y), (128, 128, 155, 255))
                else:
                    if x in (5, 10):
                        rl_d.set_at((x, y), (135, 142, 160))
                        rl_n.set_at((x, y), (128, 218, 200, 255))
                    elif 5 < x < 10 and py_tile % 4 == 1:
                        rl_d.set_at((x, y), (78, 52, 32))
                        rl_n.set_at((x, y), (128, 128, 155, 255))
        assets[rail_key] = (rl_d, rl_n)


def render_mirror_puzzles_beams(screen, game, cam_x, cam_y, visible_tiles, visibility, *, layer=None):
    """
    Рисует широкий (52 px) полупрозрачный поток света повышенной интенсивности,
    либо рассеянный конус света (если в излучателе нет фокусирующей линзы),
    а также контрастные грани зеркал.
    """
    puzzles = getattr(game, "mirror_puzzles", [])
    if not puzzles:
        return

    if layer is None:
        beam_surf = getattr(game, "_mirror_beam_surf", None)
        target_size = (VIEW_W * SCALE, VIEW_H * SCALE)
        if beam_surf is None or beam_surf.get_size() != target_size:
            beam_surf = pygame.Surface(target_size, pygame.SRCALPHA)
            game._mirror_beam_surf = beam_surf
        beam_surf.fill((0, 0, 0, 0))
        draw_line = lambda col, a, b, w=1: pygame.draw.line(beam_surf, col, a, b, w)
        draw_circle = lambda col, c, r, w=0: pygame.draw.circle(beam_surf, col, c, r, w)
        draw_poly = lambda col, pts, w=0: pygame.draw.polygon(beam_surf, col, pts, w)
    else:
        draw_line = layer.line
        draw_circle = layer.circle
        draw_poly = layer.polygon

    now_sec = pygame.time.get_ticks() * 0.001
    pulse = 0.93 + 0.07 * math.sin(now_sec * 4.5)
    any_drawn = False

    # 1. Если излучатель в режиме "need_lens" — рисуем широкий рассеянный веер света на 1.5 тайла вперёд
    for ctrl in puzzles:
        if ctrl.emitter_state == "need_lens":
            for em in ctrl.emitters:
                if (em.x, em.y) not in visible_tiles:
                    continue
                any_drawn = True
                cr, cg, cb = getattr(em, "beam_color", ctrl.beam_color)
                dx, dy = getattr(em, "beam_dir", (1, 0))
                px_x, px_y = -dy, dx
                ox = int(((em.x + 0.5) * TILE_W - cam_x) * SCALE)
                oy = int(((em.y + 0.28) * TILE_H - cam_y) * SCALE)
                for step_cone, (dist_px, span_px, alpha_c) in enumerate(((88, 56, 26), (62, 38, 46), (36, 22, 75))):
                    p1 = (ox + dx * dist_px + px_x * span_px, oy + dy * dist_px + px_y * span_px)
                    p2 = (ox + dx * dist_px - px_x * span_px, oy + dy * dist_px - px_y * span_px)
                    col_c = (cr, cg, cb, int(alpha_c * pulse)) if step_cone < 2 else (255, 220, 220, int(alpha_c * pulse))
                    draw_poly(col_c, [(ox, oy), p1, p2])

    # 2. Собираем видимые сегменты сфокусированного потока света
    vis_segs = []
    for ctrl in puzzles:
        for (x0, y0), (x1, y1), (dx, dy), b_col in ctrl.beam_segments:
            sx0 = int((x0 * TILE_W - cam_x) * SCALE)
            sy0 = int(((y0 - 0.22) * TILE_H - cam_y) * SCALE)
            sx1 = int((x1 * TILE_W - cam_x) * SCALE)
            sy1 = int(((y1 - 0.22) * TILE_H - cam_y) * SCALE)
            if max(sy0, sy1) < -56 or min(sy0, sy1) >= VIEW_H * SCALE + 56:
                continue
            vis_segs.append(((sx0, sy0), (sx1, sy1), b_col))

    if vis_segs:
        any_drawn = True
        layers = [
            (52, 0.00, int(25 * pulse)),
            (40, 0.05, int(46 * pulse)),
            (28, 0.25, int(68 * pulse)),
            (20, 0.60, int(92 * pulse)),
            (14, 0.94, int(122 * pulse)),
        ]
        for width_px, white_mix, alpha_val in layers:
            rad_joint = width_px // 2
            for p0, p1, (cr, cg, cb) in vis_segs:
                lr = min(255, int(cr * (1.0 - white_mix) + 255 * white_mix))
                lg = min(255, int(cg * (1.0 - white_mix) + 255 * white_mix))
                lb = min(255, int(cb * (1.0 - white_mix) + 255 * white_mix))
                rgba = (lr, lg, lb, alpha_val)
                draw_line(rgba, p0, p1, width_px)
                draw_circle(rgba, p0, rad_joint)
                draw_circle(rgba, p1, rad_joint)

    for ctrl in puzzles:
        for wx, wy, h_kind, b_col in ctrl.hit_points:
            if (int(wx), int(wy)) not in visible_tiles:
                continue
            hx = int((wx * TILE_W - cam_x) * SCALE)
            hy = int(((wy - 0.22) * TILE_H - cam_y) * SCALE)
            if not (-30 <= hy < VIEW_H * SCALE + 30):
                continue
            any_drawn = True
            cr, cg, cb = b_col
            if h_kind == "receiver":
                r_p = 22 + int(math.sin(now_sec * 6.0) * 3)
                draw_circle((cr, cg, cb, 60), (hx, hy), r_p + 8)
                draw_circle((cr, cg, cb, 115), (hx, hy), r_p)
                draw_circle((255, 255, 255, 155), (hx, hy), 10)
            elif h_kind in ("back_blocked", "wall", "blocked"):
                draw_circle((cr, cg, cb, 70), (hx, hy), 18)

    # Чёткая отрисовка рабочей грани и глухой спинки каждого видимого зеркала
    for ctrl in puzzles:
        for m in ctrl.mirrors:
            if (m.x, m.y) not in visible_tiles:
                continue
            mcx = int(((m.x + 0.5) * TILE_W - cam_x) * SCALE)
            mcy = int(((m.y + 0.26) * TILE_H - cam_y) * SCALE)
            if not (0 <= mcy < VIEW_H * SCALE):
                continue
            any_drawn = True

            is_bs = (m.mirror_ori % 2 == 0)
            if is_bs:
                p_a, p_b = (mcx - 15, mcy - 15), (mcx + 15, mcy + 15)
            else:
                p_a, p_b = (mcx - 15, mcy + 15), (mcx + 15, mcy - 15)

            if getattr(m, "is_double", False):
                draw_line((235, 185, 60), p_a, p_b, 8)
                draw_line((140, 240, 255), p_a, p_b, 5)
                draw_line((255, 255, 255), p_a, p_b, 2)
                for sgn in (-1, 1):
                    nx = sgn * 7
                    ny = sgn * (-1 if is_bs else 1) * 7
                    draw_circle((185, 248, 255), (mcx + nx, mcy + ny), 3)
            else:
                fnx, fny = SINGLE_FRONT_NORMAL[m.mirror_ori % 4]
                back_apex = (mcx - fnx * 15, mcy - fny * 15)
                draw_poly((42, 28, 26), [p_a, p_b, back_apex])
                draw_poly((22, 16, 18), [p_a, p_b, back_apex], 2)

                f_a = (p_a[0] + fnx * 2, p_a[1] + fny * 2)
                f_b = (p_b[0] + fnx * 2, p_b[1] + fny * 2)
                draw_line((110, 225, 255), f_a, f_b, 5)
                draw_line((250, 255, 255), f_a, f_b, 2)

                glint_c = (mcx + fnx * 8, mcy + fny * 8)
                draw_line((150, 240, 255), glint_c, (glint_c[0] + fnx * 4, glint_c[1]), 2)
                draw_line((150, 240, 255), glint_c, (glint_c[0], glint_c[1] + fny * 4), 2)

    if layer is not None or not any_drawn:
        return
    from elenor.rendering.visibility import mask_overlay
    mask_overlay(beam_surf, visibility, game.__dict__)
    screen.blit(beam_surf, (0, 0))