from collections import deque
import math
import random
import pygame
from config import TILE_W, TILE_H, VIEW_W, VIEW_H, SCALE, MAP_COLS, MAP_ROWS
from entities import Enemy, Particle
from renderer import make_pair, enforce_crisp_rim_normals

MIRROR_SOLID_KINDS = {
    "light_emitter",
    "light_emitter_off",
    "light_receiver_off",
    "light_receiver_on",
    "mirror_rot_0", "mirror_rot_1", "mirror_rot_2", "mirror_rot_3",
    "mirror_move_0", "mirror_move_1", "mirror_move_2", "mirror_move_3",
    "mirror_double_0", "mirror_double_1",
}

SINGLE_REFLECT_MAP = {
    0: {(0, 1): (1, 0),   (-1, 0): (0, -1)},
    1: {(0, -1): (1, 0),  (-1, 0): (0, 1)},
    2: {(0, -1): (-1, 0), (1, 0): (0, 1)},
    3: {(0, 1): (-1, 0),  (1, 0): (0, -1)},
}

SINGLE_FRONT_NORMAL = {
    0: (1, -1),   # NE ↗
    1: (1, 1),    # SE ↘
    2: (-1, 1),   # SW ↙
    3: (-1, -1),  # NW ↖
}

DOUBLE_REFLECT_MAP = {
    0: {(0, 1): (1, 0), (-1, 0): (0, -1), (0, -1): (-1, 0), (1, 0): (0, 1)},
    1: {(0, -1): (1, 0), (-1, 0): (0, 1), (0, 1): (-1, 0), (1, 0): (0, -1)},
}


def get_required_single_ori(in_dir, out_dir):
    for ori, rmap in SINGLE_REFLECT_MAP.items():
        if rmap.get(in_dir) == out_dir:
            return ori
    return 0


def get_biome_tiles(dungeon):
    fl = getattr(dungeon, "floor_num", 3)
    if fl in (1, 2):
        return 6, 4
    if fl == 3:
        return 1, 0
    return 7, 8


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


class MirrorPuzzleController:
    def __init__(
        self, room_rect, emitters, receiver_obj, mirror_objs, target_doors,
        beam_color=(255, 45, 55), emitter_state="ready", ambush_enabled=False
    ):
        self.room_rect = room_rect
        self.emitters = emitters if isinstance(emitters, list) else [emitters]
        self.receiver = receiver_obj
        self.mirrors = mirror_objs
        self.target_doors = list(target_doors or [])
        self.beam_color = tuple(beam_color)
        # Состояния излучателя: "ready", "need_lever" (выключен), "need_lens" (рассеян без линзы)
        self.emitter_state = emitter_state
        self.solved = False
        self.beam_segments = []
        self.hit_points = []
        self.burn_tick_timer = 0.0

        # Параметры засады мобов во время решения головоломки
        self.ambush_enabled = bool(ambush_enabled)
        self.player_entered_puzzle = False
        self.ambush_timer = random.uniform(5.5, 8.5)
        self.ambush_spawned_count = 0


def _sync_mirror_kind(obj):
    if getattr(obj, "is_double", False):
        obj.mirror_ori %= 2
        obj.kind = f"mirror_double_{obj.mirror_ori}"
    elif getattr(obj, "is_movable", False):
        obj.mirror_ori %= 4
        obj.kind = f"mirror_move_{obj.mirror_ori}"
    else:
        obj.mirror_ori %= 4
        obj.kind = f"mirror_rot_{obj.mirror_ori}"


def _create_mirror_interactable(InteractableCls, x, y, ori, is_movable=False, is_double=False, rail_tiles=None):
    obj = InteractableCls(x, y, "mirror_rot_0")
    obj.is_mirror = True
    obj.is_movable = bool(is_movable)
    obj.is_double = bool(is_double)
    obj.mirror_ori = int(ori) % (2 if is_double else 4)
    obj.rail_tiles = list(rail_tiles) if rail_tiles else [(x, y)]
    obj.push_charge = 0.0
    obj.push_cd = 0.0
    _sync_mirror_kind(obj)
    return obj


def _bfs_reachable(room_rect, blocked_set, start_xy):
    if start_xy in blocked_set:
        return set()
    visited = {start_xy}
    q = deque([start_xy])
    while q:
        cx, cy = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = cx + dx, cy + dy
            if room_rect.collidepoint(nx, ny) and (nx, ny) not in blocked_set and (nx, ny) not in visited:
                visited.add((nx, ny))
                q.append((nx, ny))
    return visited


def find_safe_accessible_tile_for_puzzle_item(game, puzzle_rect, forbidden_rects=None):
    """
    Находит клетку в обычных комнатах этажа, до которой игрок ГАРАНТИРОВАННО может дойти
    от своей стартовой позиции при ЗАПЕРТОЙ двери головоломки!
    Исключает появление рычага или линзы за закрытой дверью головоломки.
    """
    dungeon = game.dungeon
    px, py = int(game.player.x), int(game.player.y)
    forb = list(forbidden_rects or []) + [puzzle_rect.inflate(2, 2)]
    if getattr(dungeon, "boss_room", None):
        forb.append(dungeon.boss_room.inflate(2, 2))

    occupied_objs = {(o.x, o.y) for o in game.objects if not o.used}
    occupied_objs.update(dungeon.doors.keys())
    occupied_objs.update(dungeon.levers.keys())

    cand_rooms = [
        r for r in dungeon.rooms
        if not any(r.colliderect(fr) for fr in forb)
    ]
    random.shuffle(cand_rooms)

    # Предпочитаем комнаты подальше от старта (но строго достижимые по A*!)
    cand_rooms.sort(key=lambda r: math.hypot(r.centerx - px, r.centery - py), reverse=True)

    for room in cand_rooms:
        room_tiles = [
            (tx, ty)
            for ty in range(room.top + 1, room.bottom - 1)
            for tx in range(room.left + 1, room.right - 1)
            if not dungeon.is_blocking_move(tx, ty) and (tx, ty) not in occupied_objs
        ]
        random.shuffle(room_tiles)
        for tx, ty in room_tiles[:6]:
            if (tx, ty) == (px, py):
                continue
            path = dungeon.find_path((px, py), (tx, ty), max_expanded=900)
            # Проверяем, что найденный путь реально дошёл до (tx, ty)
            if path and int(path[-1][0]) == tx and int(path[-1][1]) == ty:
                return (tx, ty)

    # Резерв: любая достижимая клетка рядом с входом в зал головоломки
    for r_dist in range(2, 8):
        for dy in range(-r_dist, r_dist + 1):
            for dx in range(-r_dist, r_dist + 1):
                tx, ty = px + dx, py + dy
                if 1 <= tx < MAP_COLS - 1 and 1 <= ty < MAP_ROWS - 1:
                    if not dungeon.is_blocking_move(tx, ty) and (tx, ty) not in occupied_objs:
                        if not any(fr.collidepoint(tx, ty) for fr in forb):
                            return (tx, ty)
    return (px, py)


def _try_generate_procedural_layout(room_rect, protected_porch):
    rx0, ry0 = room_rect.left, room_rect.top
    rw, rh = room_rect.width, room_rect.height
    all_room_tiles = {(x, y) for y in range(ry0, ry0 + rh) for x in range(rx0, rx0 + rw)}

    walls = set()
    shape_mode = random.choice(["octagon", "alcoves", "pillars", "asymmetric"])
    for cy_c in (ry0, ry0 + rh - 1):
        for cx_c in (rx0, rx0 + rw - 1):
            if (cx_c, cy_c) not in protected_porch:
                walls.add((cx_c, cy_c))
                if shape_mode in ("octagon", "asymmetric") and random.random() < 0.75:
                    dx_in = 1 if cx_c == rx0 else -1
                    dy_in = 1 if cy_c == ry0 else -1
                    for cand in ((cx_c + dx_in, cy_c), (cx_c, cy_c + dy_in)):
                        if cand not in protected_porch:
                            walls.add(cand)

    if shape_mode == "alcoves":
        for _ in range(random.randint(2, 4)):
            wx = random.choice([rx0, rx0 + rw - 1])
            wy = random.randint(ry0 + 2, ry0 + rh - 3)
            if (wx, wy) not in protected_porch:
                walls.add((wx, wy))

    floor_tiles = all_room_tiles - walls
    use_double = (rw >= 9 and rh >= 8 and random.random() < 0.42)
    mirrors_spec = []
    beam_path_tiles = set()

    if use_double:
        d_in = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
        dbl_ori = random.choice([0, 1])
        d1 = DOUBLE_REFLECT_MAP[dbl_ori][d_in]
        d2 = (-d_in[0], -d_in[1])
        d3 = (-d1[0], -d1[1])

        hx = random.randint(rx0 + 3, rx0 + rw - 4)
        hy = random.randint(ry0 + 3, ry0 + rh - 4)
        s_perp1 = random.randint(2, 3)
        s_perp2 = random.randint(2, 3)
        s_back = random.randint(2, 3)
        l_em = random.randint(2, 3)
        l_rec = random.randint(2, 3)

        em_pos = (hx - d_in[0] * l_em, hy - d_in[1] * l_em)
        rec_pos = (hx + d_in[0] * l_rec, hy + d_in[1] * l_rec)
        c1 = (hx + d1[0] * s_perp1, hy + d1[1] * s_perp1)
        c2 = (c1[0] + d2[0] * s_back, c1[1] + d2[1] * s_back)
        c3 = (c2[0] + d3[0] * (s_perp1 + s_perp2), c2[1] + d3[1] * (s_perp1 + s_perp2))
        c4 = (hx + d3[0] * s_perp2, hy + d3[1] * s_perp2)

        key_nodes = [em_pos, (hx, hy), c1, c2, c3, c4, rec_pos]
        if len(set(key_nodes)) != len(key_nodes):
            return None
        if any(pt not in floor_tiles or pt in protected_porch for pt in key_nodes):
            return None

        seg_pairs = [
            (em_pos, (hx, hy), d_in),
            ((hx, hy), c1, d1),
            (c1, c2, d2),
            (c2, c3, d3),
            (c3, c4, d_in),
            (c4, (hx, hy), d1),
            ((hx, hy), rec_pos, d_in),
        ]
        node_set = set(key_nodes)
        for p_start, p_end, s_dir in seg_pairs:
            cx, cy = p_start[0] + s_dir[0], p_start[1] + s_dir[1]
            while (cx, cy) != p_end:
                if (cx, cy) in node_set or (cx, cy) not in floor_tiles:
                    return None
                beam_path_tiles.add((cx, cy))
                cx += s_dir[0]
                cy += s_dir[1]

        mirrors_spec = [
            {"pos": (hx, hy), "ori": dbl_ori, "is_double": True},
            {"pos": c1, "ori": get_required_single_ori(d1, d2), "is_double": False},
            {"pos": c2, "ori": get_required_single_ori(d2, d3), "is_double": False},
            {"pos": c3, "ori": get_required_single_ori(d3, d_in), "is_double": False},
            {"pos": c4, "ori": get_required_single_ori(d_in, d1), "is_double": False},
        ]

        for step_b in range(1, s_back):
            for side_d in (d1, d3):
                bx_w = hx + d2[0] * step_b + side_d[0]
                by_w = hy + d2[1] * step_b + side_d[1]
                if (bx_w, by_w) in floor_tiles and (bx_w, by_w) not in beam_path_tiles and (bx_w, by_w) not in node_set and (bx_w, by_w) not in protected_porch:
                    walls.add((bx_w, by_w))

    else:
        num_bounces = random.randint(3, 5)
        valid_starts = [pt for pt in floor_tiles if pt not in protected_porch]
        if not valid_starts:
            return None
        em_pos = random.choice(valid_starts)
        em_dir = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])

        cur_pos = em_pos
        cur_dir = em_dir
        occupied_nodes = {em_pos}

        for _ in range(num_bounces):
            lengths = list(range(2, 7))
            random.shuffle(lengths)
            picked_next = None
            for seg_l in lengths:
                cand_x = cur_pos[0] + cur_dir[0] * seg_l
                cand_y = cur_pos[1] + cur_dir[1] * seg_l
                if (cand_x, cand_y) not in floor_tiles or (cand_x, cand_y) in protected_porch or (cand_x, cand_y) in occupied_nodes:
                    continue
                seg_cells = [(cur_pos[0] + cur_dir[0] * k, cur_pos[1] + cur_dir[1] * k) for k in range(1, seg_l)]
                if any(c not in floor_tiles or c in occupied_nodes for c in seg_cells):
                    continue
                picked_next = ((cand_x, cand_y), seg_cells)
                break

            if picked_next is None:
                return None

            m_pos, seg_cells = picked_next
            if m_pos in beam_path_tiles:
                return None

            perp_dirs = [(0, 1), (0, -1)] if cur_dir[0] != 0 else [(1, 0), (-1, 0)]
            random.shuffle(perp_dirs)
            next_dir = perp_dirs[0]
            for pd in perp_dirs:
                test_x, test_y = m_pos[0] + pd[0] * 2, m_pos[1] + pd[1] * 2
                if (test_x, test_y) in floor_tiles:
                    next_dir = pd
                    break

            beam_path_tiles.update(seg_cells)
            occupied_nodes.add(m_pos)
            mirrors_spec.append({
                "pos": m_pos,
                "ori": get_required_single_ori(cur_dir, next_dir),
                "is_double": False,
            })
            cur_pos = m_pos
            cur_dir = next_dir

        rec_pos = None
        for seg_l in random.sample(range(2, 6), 4):
            cand_x = cur_pos[0] + cur_dir[0] * seg_l
            cand_y = cur_pos[1] + cur_dir[1] * seg_l
            if (cand_x, cand_y) not in floor_tiles or (cand_x, cand_y) in protected_porch or (cand_x, cand_y) in occupied_nodes or (cand_x, cand_y) in beam_path_tiles:
                continue
            seg_cells = [(cur_pos[0] + cur_dir[0] * k, cur_pos[1] + cur_dir[1] * k) for k in range(1, seg_l)]
            if any(c not in floor_tiles or c in occupied_nodes for c in seg_cells):
                continue
            rec_pos = (cand_x, cand_y)
            beam_path_tiles.update(seg_cells)
            occupied_nodes.add(rec_pos)
            break

        if rec_pos is None:
            return None

        for check_pt in [em_pos] + [m["pos"] for m in mirrors_spec[:-1]]:
            cx, cy = check_pt
            if cx == rec_pos[0] or cy == rec_pos[1]:
                step_x = 0 if cx == rec_pos[0] else (1 if rec_pos[0] > cx else -1)
                step_y = 0 if cy == rec_pos[1] else (1 if rec_pos[1] > cy else -1)
                tx, ty = cx + step_x, cy + step_y
                blocked_line = False
                while (tx, ty) != rec_pos:
                    if (tx, ty) in walls or (tx, ty) in occupied_nodes:
                        blocked_line = True
                        break
                    if (tx, ty) not in beam_path_tiles and (tx, ty) not in protected_porch:
                        walls.add((tx, ty))
                        blocked_line = True
                        break
                    tx += step_x
                    ty += step_y
                if not blocked_line:
                    return None

        free_for_walls = list(floor_tiles - beam_path_tiles - occupied_nodes - protected_porch - walls)
        random.shuffle(free_for_walls)
        for cand_w in free_for_walls[:random.randint(2, 4)]:
            walls.add(cand_w)

    occupied_all = {em_pos, rec_pos} | {m["pos"] for m in mirrors_spec} | walls
    single_indices = [i for i, m in enumerate(mirrors_spec) if not m["is_double"]]
    random.shuffle(single_indices)
    movable_count = 0

    for idx in single_indices:
        if movable_count >= 2:
            break
        m = mirrors_spec[idx]
        mx, my = m["pos"]
        axes = [("h", (1, 0)), ("v", (0, 1))]
        random.shuffle(axes)
        placed_rail = False
        for r_kind, (ax_dx, ax_dy) in axes:
            for offset_tuple in ((-1, 0, 1), (0, 1), (-1, 0)):
                r_tiles = [(mx + ax_dx * k, my + ax_dy * k) for k in offset_tuple]
                if any(rt != (mx, my) and (rt in occupied_all or rt in protected_porch or not room_rect.collidepoint(rt[0], rt[1])) for rt in r_tiles):
                    continue
                push_before = (r_tiles[0][0] - ax_dx, r_tiles[0][1] - ax_dy)
                push_after = (r_tiles[-1][0] + ax_dx, r_tiles[-1][1] + ax_dy)
                if not (room_rect.collidepoint(push_before[0], push_before[1]) and room_rect.collidepoint(push_after[0], push_after[1])):
                    continue
                if push_before in occupied_all or push_after in occupied_all:
                    continue

                non_sol = [rt for rt in r_tiles if rt != (mx, my)]
                m["is_movable"] = True
                m["rail_kind"] = "mirror_rail_h" if r_kind == "h" else "mirror_rail_v"
                m["rail_tiles"] = r_tiles
                m["start_pos"] = random.choice(non_sol)
                for rt in r_tiles:
                    occupied_all.add(rt)
                movable_count += 1
                placed_rail = True
                break
            if placed_rail:
                break

    for m in mirrors_spec:
        if not m.get("is_movable", False):
            m["is_movable"] = False
            m["start_pos"] = m["pos"]
            m["rail_tiles"] = [m["pos"]]
            if m["is_double"]:
                m["start_ori"] = (m["ori"] + 1) % 2
            else:
                m["start_ori"] = (m["ori"] + random.choice([1, 2, 3])) % 4
        else:
            m["start_ori"] = m["ori"]

    solid_for_walk = walls | {em_pos, rec_pos} | {m["pos"] for m in mirrors_spec}
    for m in mirrors_spec:
        if m["is_movable"]:
            solid_for_walk.update(m["rail_tiles"])

    start_walk = next(iter(protected_porch))
    reachable = _bfs_reachable(room_rect, solid_for_walk, start_walk)
    if not protected_porch.issubset(reachable):
        return None

    for m in mirrors_spec:
        if m["is_movable"]:
            r_tiles = m["rail_tiles"]
            ax_dx = 1 if m["rail_kind"] == "mirror_rail_h" else 0
            ax_dy = 0 if m["rail_kind"] == "mirror_rail_h" else 1
            p_before = (r_tiles[0][0] - ax_dx, r_tiles[0][1] - ax_dy)
            p_after = (r_tiles[-1][0] + ax_dx, r_tiles[-1][1] + ax_dy)
            if p_before not in reachable or p_after not in reachable:
                return None
        else:
            mx, my = m["pos"]
            if not any((mx + dx, my + dy) in reachable for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                return None

    return {
        "walls": walls,
        "em_pos": em_pos,
        "em_dir": d_in if use_double else em_dir,
        "rec_pos": rec_pos,
        "mirrors": mirrors_spec,
    }


def setup_mirror_puzzle_in_room(
    game, room_rect, target_doors, InteractableCls,
    beam_color=(255, 45, 55), spawn_chance=1.0, protected_doors=None,
    emitter_mode="ready", ambush_enabled=False, forbidden_key_rects=None
):
    """
    Собирает процедурную головоломку в room_rect.
    Параметры:
      - emitter_mode:
          "ready"       — излучатель сразу включён и сфокусирован (вводный режим для крысиной кампании);
          "need_lever"  — излучатель обесточен, в доступной части этажа спавнится рычаг питания;
          "need_lens"   — излучатель светит рассеянно, в доступной части этажа спавнится «Фокусирующая линза»;
          "random"      — случайно выбирает один из режимов.
      - ambush_enabled: если True, пока игрок в зале решает загадку, из темноты лезут мобы (с 4-го — без наград!).
    """
    if random.random() > float(spawn_chance):
        return None

    if not hasattr(game, "mirror_puzzles"):
        game.mirror_puzzles = []

    dungeon = game.dungeon
    wall_id, floor_id = get_biome_tiles(dungeon)

    for ry in range(room_rect.top, room_rect.bottom):
        for rx in range(room_rect.left, room_rect.right):
            dungeon.grid[ry][rx] = floor_id
            dungeon.overlays.pop((rx, ry), None)

    protected_porch = set()
    doors_to_guard = list(protected_doors or [])
    for (dx, dy) in dungeon.doors.keys():
        if room_rect.inflate(2, 2).collidepoint(dx, dy):
            doors_to_guard.append((dx, dy))

    for (dx, dy) in doors_to_guard:
        for oy in range(-1, 2):
            for ox in range(-1, 2):
                tx, ty = dx + ox, dy + oy
                if room_rect.collidepoint(tx, ty):
                    protected_porch.add((tx, ty))

    if not protected_porch:
        protected_porch.add((room_rect.left, room_rect.centery))
        protected_porch.add((room_rect.right - 1, room_rect.centery))

    layout = None
    for _ in range(90):
        layout = _try_generate_procedural_layout(room_rect, protected_porch)
        if layout is not None:
            break

    if layout is None:
        layout = {
            "walls": set(),
            "em_pos": (room_rect.left + 1, room_rect.bottom - 2),
            "em_dir": (0, -1),
            "rec_pos": (room_rect.right - 2, room_rect.top + 1),
            "mirrors": [
                {
                    "pos": (room_rect.left + 1, room_rect.top + 1),
                    "start_pos": (room_rect.left + 1, room_rect.top + 1),
                    "ori": get_required_single_ori((0, -1), (1, 0)),
                    "start_ori": (get_required_single_ori((0, -1), (1, 0)) + 2) % 4,
                    "is_double": False,
                    "is_movable": False,
                    "rail_tiles": [(room_rect.left + 1, room_rect.top + 1)],
                }
            ],
        }

    for (wx, wy) in layout["walls"]:
        dungeon.grid[wy][wx] = wall_id

    if emitter_mode == "random":
        emitter_mode = random.choice(["ready", "need_lever", "need_lens"])

    em_x, em_y = layout["em_pos"]
    em_kind = "light_emitter_off" if emitter_mode == "need_lever" else "light_emitter"
    emitter_obj = InteractableCls(em_x, em_y, em_kind)
    emitter_obj.beam_dir = layout["em_dir"]
    emitter_obj.beam_color = tuple(beam_color)

    rec_x, rec_y = layout["rec_pos"]
    receiver_obj = InteractableCls(rec_x, rec_y, "light_receiver_off")

    rail_props = []
    mirror_objs = []
    for m_info in layout["mirrors"]:
        if m_info["is_movable"]:
            for (rtx, rty) in m_info["rail_tiles"]:
                rail_props.append(InteractableCls(rtx, rty, m_info["rail_kind"]))
        sx, sy = m_info["start_pos"]
        m_obj = _create_mirror_interactable(
            InteractableCls, sx, sy, m_info["start_ori"],
            is_movable=m_info["is_movable"],
            is_double=m_info["is_double"],
            rail_tiles=m_info["rail_tiles"]
        )
        mirror_objs.append(m_obj)

    game.objects.extend(rail_props)
    game.objects.append(emitter_obj)
    game.objects.append(receiver_obj)
    game.objects.extend(mirror_objs)

    for obj in [emitter_obj, receiver_obj] + mirror_objs:
        dungeon.solid_props.add((obj.x, obj.y))

    dungeon.invalidate_light_cache()
    if hasattr(game, "fx") and game.fx:
        game.fx.rebuild_wall_grid(dungeon)

    ctrl = MirrorPuzzleController(
        room_rect, [emitter_obj], receiver_obj, mirror_objs, target_doors,
        beam_color=beam_color, emitter_state=emitter_mode, ambush_enabled=ambush_enabled
    )

    # Если излучателю нужен рычаг или фокусирующая линза — спавним их строго в ДОСТУПНОЙ зоне этажа!
    if emitter_mode == "need_lever":
        kx, ky = find_safe_accessible_tile_for_puzzle_item(game, room_rect, forbidden_key_rects)
        p_lev = InteractableCls(kx, ky, "lever_off")
        p_lev.is_puzzle_emitter_lever = True
        p_lev.puzzle_ctrl = ctrl
        game.objects.append(p_lev)
    elif emitter_mode == "need_lens":
        kx, ky = find_safe_accessible_tile_for_puzzle_item(game, room_rect, forbidden_key_rects)
        lens_itm = game.make_item("focusing_lens")
        game.objects.append(InteractableCls(kx, ky, "loot", lens_itm))

    game.mirror_puzzles.append(ctrl)
    recalculate_mirror_puzzle(game, ctrl)
    return ctrl


def spawn_pre_boss_mirror_puzzle(
    game, InteractableCls, beam_color=(255, 45, 55), spawn_chance=1.0,
    emitter_mode="ready", ambush_enabled=False
):
    dungeon = game.dungeon
    info = getattr(dungeon, "pre_boss_puzzle_info", None)
    if info is None:
        return None

    p_rect = info["puzzle_rect"]
    bd_x, bd_y = info["boss_door"]
    ed_x, ed_y = info["entry_door"]
    boss_door = dungeon.doors.get((bd_x, bd_y))

    if random.random() > float(spawn_chance):
        if boss_door is not None:
            boss_door.locked = False
        return None

    game.mobs = [m for m in game.mobs if not p_rect.inflate(2, 2).collidepoint(int(m.x), int(m.y))]
    game.objects = [o for o in game.objects if not p_rect.inflate(2, 2).collidepoint(o.x, o.y)]

    cr, cg, cb = beam_color
    dungeon.room_lights.append({
        "x": p_rect.centerx, "y": p_rect.centery,
        "color": (0.48 + (cr / 255.0) * 0.52, 0.48 + (cg / 255.0) * 0.52, 0.58 + (cb / 255.0) * 0.52),
        "radius": 155.0
    })

    target_doors = [boss_door] if boss_door is not None else []
    return setup_mirror_puzzle_in_room(
        game, p_rect, target_doors, InteractableCls,
        beam_color=beam_color, spawn_chance=1.0,
        protected_doors=[(ed_x, ed_y), (bd_x, bd_y)],
        emitter_mode=emitter_mode, ambush_enabled=ambush_enabled,
        forbidden_key_rects=[info["boss_rect"]]
    )


def recalculate_mirror_puzzle(game, ctrl: MirrorPuzzleController):
    dungeon = game.dungeon
    ctrl.beam_segments.clear()
    ctrl.hit_points.clear()

    # Если излучатель обесточен или в нём нет фокусирующей линзы — сфокусированный луч не идёт!
    for em in ctrl.emitters:
        em.kind = "light_emitter_off" if ctrl.emitter_state == "need_lever" else "light_emitter"
    if ctrl.emitter_state != "ready":
        ctrl.receiver.kind = "light_receiver_on" if ctrl.solved else "light_receiver_off"
        return

    mirror_at = {(m.x, m.y): m for m in ctrl.mirrors if not m.used}
    blocker_at = {
        (o.x, o.y): o for o in game.objects
        if not o.used and o.kind in ("barrel", "chest", "crate_stack")
    }
    emitter_coords = {(em.x, em.y) for em in ctrl.emitters}

    rec_rgb = [0, 0, 0]
    hit_receiver = False

    for em in ctrl.emitters:
        cur_x, cur_y = em.x, em.y
        dx, dy = getattr(em, "beam_dir", (1, 0))
        b_col = getattr(em, "beam_color", ctrl.beam_color)
        seg_start = (cur_x + 0.5, cur_y + 0.5)
        visited_states = set()

        for _ in range(48):
            nx, ny = cur_x + dx, cur_y + dy
            state_key = (nx, ny, dx, dy)
            if state_key in visited_states:
                ctrl.beam_segments.append((seg_start, (nx + 0.5, ny + 0.5), (dx, dy), b_col))
                break
            visited_states.add(state_key)

            if nx == ctrl.receiver.x and ny == ctrl.receiver.y:
                seg_end = (nx + 0.5, ny + 0.5)
                ctrl.beam_segments.append((seg_start, seg_end, (dx, dy), b_col))
                rec_rgb[0] = min(255, rec_rgb[0] + b_col[0])
                rec_rgb[1] = min(255, rec_rgb[1] + b_col[1])
                rec_rgb[2] = min(255, rec_rgb[2] + b_col[2])
                ctrl.hit_points.append((seg_end[0], seg_end[1], "receiver", tuple(rec_rgb)))
                hit_receiver = True
                break

            if dungeon.is_blocking_sight(nx, ny) or (nx, ny) in emitter_coords:
                seg_end = (cur_x + 0.5 + dx * 0.48, cur_y + 0.5 + dy * 0.48)
                ctrl.beam_segments.append((seg_start, seg_end, (dx, dy), b_col))
                ctrl.hit_points.append((seg_end[0], seg_end[1], "wall", b_col))
                break

            if (nx, ny) in blocker_at:
                seg_end = (nx + 0.5 - dx * 0.25, ny + 0.5 - dy * 0.25)
                ctrl.beam_segments.append((seg_start, seg_end, (dx, dy), b_col))
                ctrl.hit_points.append((seg_end[0], seg_end[1], "blocked", b_col))
                break

            if (nx, ny) in mirror_at:
                m_obj = mirror_at[(nx, ny)]
                seg_end = (nx + 0.5, ny + 0.5)
                ctrl.beam_segments.append((seg_start, seg_end, (dx, dy), b_col))

                if getattr(m_obj, "is_double", False):
                    new_dir = DOUBLE_REFLECT_MAP[m_obj.mirror_ori % 2].get((dx, dy))
                else:
                    new_dir = SINGLE_REFLECT_MAP[m_obj.mirror_ori % 4].get((dx, dy))

                if new_dir is None:
                    ctrl.hit_points.append((seg_end[0], seg_end[1], "back_blocked", b_col))
                    break

                ctrl.hit_points.append((seg_end[0], seg_end[1], "reflect", b_col))
                cur_x, cur_y = nx, ny
                dx, dy = new_dir
                seg_start = seg_end
                continue

            cur_x, cur_y = nx, ny

    ctrl.receiver.kind = "light_receiver_on" if (hit_receiver or ctrl.solved) else "light_receiver_off"
    if hit_receiver and not ctrl.solved:
        ctrl.solved = True
        for d in ctrl.target_doors:
            d.locked = False
            d.is_open = True
        dungeon.invalidate_light_cache()
        game.sfx.play("levelup")
        game.add_popup(ctrl.receiver.x + 0.5, ctrl.receiver.y + 0.5, "ПРОХОД ОТКРЫТ!", (255, 110, 125), big=True)
        game.set_thought(
            "Поток света сошёлся в гранях ока! Древний засов с грохотом открыл путь.",
            important=True
        )
        for _ in range(22):
            ang = random.uniform(0, 6.28)
            spd = random.uniform(1.0, 3.2)
            game.particles.append(Particle(
                ctrl.receiver.x + 0.5, ctrl.receiver.y + 0.5,
                math.cos(ang) * spd, math.sin(ang) * spd,
                ctrl.beam_color, 3.0, 0.45
            ))


def handle_mirror_puzzle_interaction(game, obj):
    if obj.kind in ("mirror_rail_h", "mirror_rail_v"):
        return True

    # 1. Нажатие рычага, подающего питание на обесточенный излучатель головоломки
    if getattr(obj, "is_puzzle_emitter_lever", False):
        ctrl = getattr(obj, "puzzle_ctrl", None)
        if obj.kind == "lever_off":
            obj.kind = "lever_on"
            game.play_spatial("door", obj.x + 0.5, obj.y + 0.5)
            game.sfx.play("magic")
            if ctrl is not None:
                ctrl.emitter_state = "ready"
                recalculate_mirror_puzzle(game, ctrl)
            game.add_popup(obj.x + 0.5, obj.y + 0.5, "ОБЕЛИСК ЗАПИТАН!", (255, 220, 95), big=True)
            game.set_thought("В стенах загудело! На древний обелиск света пошла энергия.", important=True)
        else:
            game.play_spatial("step", obj.x + 0.5, obj.y + 0.5)
            game.set_thought("Рычаг уже опущен, питание подано на обелиск.", important=False, chance=0.8)
        return True

    # 2. Осмотр или установка Фокусирующей Линзы в Излучатель
    if obj.kind in ("light_emitter", "light_emitter_off"):
        ctrl = next((c for c in getattr(game, "mirror_puzzles", []) if obj in c.emitters), None)
        if ctrl and ctrl.emitter_state == "need_lever":
            game.play_spatial("hurt", obj.x + 0.5, obj.y + 0.5)
            game.add_popup(obj.x + 0.5, obj.y + 0.5, "НЕТ ПИТАНИЯ", (255, 115, 95))
            game.set_thought("Обелиск холоден и пуст. Нужно найти рычаг в других комнатах этажа, чтобы запустить его.", important=True)
            return True

        if ctrl and ctrl.emitter_state == "need_lens":
            # Проверяем, есть ли у игрока в сумке или на поясе «Фокусирующая линза»
            lens_itm = next(
                (itm for itm in game.player.inventory if itm and itm.id == "focusing_lens"),
                None
            )
            if lens_itm is not None:
                game.player.remove_item_everywhere(lens_itm)
                ctrl.emitter_state = "ready"
                recalculate_mirror_puzzle(game, ctrl)
                game.sfx.play("magic")
                game.add_popup(obj.x + 0.5, obj.y + 0.5, "ЛИНЗА УСТАНОВЛЕНА!", (130, 255, 195), big=True)
                game.set_thought("Линза встала в пазы со звонким щелчком — рассеянный свет собрался в мощный поток!", important=True)
            else:
                game.play_spatial("ui", obj.x + 0.5, obj.y + 0.5)
                game.add_popup(obj.x + 0.5, obj.y + 0.5, "НУЖНА ЛИНЗА", (255, 200, 90))
                game.set_thought("Из пустого гнезда бьёт мутный рассеянный свет. Нужно найти на этом ярусе Фокусирующую линзу.", important=True)
            return True

        game.play_spatial("magic", obj.x + 0.5, obj.y + 0.5)
        game.set_thought("Древний обелиск. Из его линзы льётся широкий поток багрового света.", important=False, chance=0.85)
        return True

    if obj.kind in ("light_receiver_off", "light_receiver_on"):
        game.play_spatial("ui", obj.x + 0.5, obj.y + 0.5)
        if obj.kind == "light_receiver_on":
            game.set_thought("Кристалл напитан светом, решётка поднята.", important=False, chance=0.85)
        else:
            game.set_thought("Приёмное око механизма. Нужно направить сюда поток света зеркалами.", important=False, chance=0.85)
        return True

    if not getattr(obj, "is_mirror", False):
        return False

    if getattr(obj, "is_movable", False):
        game.play_spatial("step_stone", obj.x + 0.5, obj.y + 0.5)
        game.set_thought("Тумба на рельсах. Чтобы сдвинуть её, нужно просто упереться в неё на ходу.", important=False, chance=0.9)
        return True

    obj.mirror_ori += 1
    _sync_mirror_kind(obj)
    game.play_spatial("ui", obj.x + 0.5, obj.y + 0.5)
    for _ in range(5):
        ang = random.uniform(0, 6.28)
        game.particles.append(Particle(obj.x + 0.5, obj.y + 0.3, math.cos(ang) * 1.5, math.sin(ang) * 1.5, (255, 200, 195), 2.2, 0.20))

    for ctrl in getattr(game, "mirror_puzzles", []):
        recalculate_mirror_puzzle(game, ctrl)
    return True


def _update_body_pushing_mirrors(game, ctrl, dt):
    keys = pygame.key.get_pressed()
    in_dx = (1 if (keys[pygame.K_d] or keys[pygame.K_RIGHT]) else 0) - (1 if (keys[pygame.K_a] or keys[pygame.K_LEFT]) else 0)
    in_dy = (1 if (keys[pygame.K_s] or keys[pygame.K_DOWN]) else 0) - (1 if (keys[pygame.K_w] or keys[pygame.K_UP]) else 0)

    px, py = game.player.x, game.player.y
    any_moved = False

    for m in ctrl.mirrors:
        if not getattr(m, "is_movable", False):
            continue
        m.push_cd = max(0.0, getattr(m, "push_cd", 0.0) - dt)
        if m.push_cd > 0.0:
            continue

        rails = getattr(m, "rail_tiles", [])
        if len(rails) <= 1:
            continue

        mx_c, my_c = m.x + 0.5, m.y + 0.5
        dist = math.hypot(px - mx_c, py - my_c)
        if dist > 0.92 or (in_dx == 0 and in_dy == 0):
            m.push_charge = max(0.0, getattr(m, "push_charge", 0.0) - dt * 2.0)
            continue

        vec_to_m_x = mx_c - px
        vec_to_m_y = my_c - py
        if vec_to_m_x * in_dx + vec_to_m_y * in_dy <= 0.05:
            m.push_charge = 0.0
            continue

        is_horiz = (rails[0][1] == rails[-1][1])
        step_x, step_y = 0, 0
        if is_horiz and in_dx != 0:
            step_x = 1 if in_dx > 0 else -1
        elif (not is_horiz) and in_dy != 0:
            step_y = 1 if in_dy > 0 else -1
        else:
            continue

        target_tile = (m.x + step_x, m.y + step_y)
        if target_tile not in rails or target_tile in game.dungeon.solid_props:
            continue
        if any(int(mob.x) == target_tile[0] and int(mob.y) == target_tile[1] for mob in game.mobs):
            continue

        m.push_charge = getattr(m, "push_charge", 0.0) + dt
        if m.push_charge >= 0.11:
            m.push_charge = 0.0
            m.push_cd = 0.25
            game.dungeon.solid_props.discard((m.x, m.y))
            m.x, m.y = target_tile
            game.dungeon.solid_props.add((m.x, m.y))
            game.play_spatial("door", m.x + 0.5, m.y + 0.5)
            for _ in range(6):
                ang = random.uniform(0, 6.28)
                game.particles.append(Particle(
                    m.x + 0.5, m.y + 0.85,
                    math.cos(ang) * 1.2, math.sin(ang) * 1.2,
                    (185, 180, 170), 2.2, 0.22
                ))
            any_moved = True

    if any_moved:
        recalculate_mirror_puzzle(game, ctrl)


def _update_puzzle_ambush_spawner(game, ctrl, dt):
    """
    Пока игрок решает головоломку и она ещё не открыта:
    периодически спавнит мобов строго на клетках ВНЕ поля зрения игрока (not in current_visible_tiles).
    Начиная с 4-го моба вешает на них флаг no_rewards = True (0 опыта, 0 лута, 0 прокачки векторов билда).
    """
    if not ctrl.ambush_enabled or ctrl.solved:
        return

    px, py = game.player.x, game.player.y
    if ctrl.room_rect.inflate(2, 2).collidepoint(int(px), int(py)):
        ctrl.player_entered_puzzle = True

    if not ctrl.player_entered_puzzle:
        return
    if not ctrl.room_rect.inflate(8, 8).collidepoint(int(px), int(py)):
        return

    # Ограничиваем число одновременно живых мобов засады до 3, чтобы не устраивать свалку
    alive_ambush = sum(1 for m in game.mobs if getattr(m, "from_puzzle_ambush", False))
    if alive_ambush >= 3:
        return

    ctrl.ambush_timer -= dt
    if ctrl.ambush_timer > 0.0:
        return
    ctrl.ambush_timer = random.uniform(7.0, 10.5)

    dungeon = game.dungeon
    vis_tiles = getattr(game, "current_visible_tiles", set())
    boss_r = getattr(dungeon, "boss_room", None)

    candidates = []
    for ty in range(max(1, int(py) - 14), min(MAP_ROWS - 1, int(py) + 15)):
        for tx in range(max(1, int(px) - 14), min(MAP_COLS - 1, int(px) + 15)):
            if (tx, ty) in vis_tiles:
                continue
            if dungeon.is_blocking_move(tx, ty):
                continue
            if boss_r and boss_r.inflate(2, 2).collidepoint(tx, ty):
                continue
            dist = math.hypot((tx + 0.5) - px, (ty + 0.5) - py)
            if 5.5 <= dist <= 14.5:
                candidates.append((tx, ty))

    if not candidates:
        return

    random.shuffle(candidates)
    spawn_xy = None
    for tx, ty in candidates[:12]:
        path = dungeon.find_path((tx, ty), (int(px), int(py)), max_expanded=240)
        if path and len(path) <= 22:
            spawn_xy = (tx, ty)
            break

    if spawn_xy is None:
        return

    fl = getattr(dungeon, "floor_num", 3)
    mob_kind = "rat_cultist" if (fl >= 3 and random.random() < 0.35) else "rat"
    amb_mob = Enemy(spawn_xy[0], spawn_xy[1], kind=mob_kind, state="combat")
    if hasattr(game, "balance_data"):
        amb_mob.apply_balance_profile(game.balance_data.get("enemies", {}).get(mob_kind), floor_num=fl)
    amb_mob.awareness = 100.0
    amb_mob.from_puzzle_ambush = True

    ctrl.ambush_spawned_count += 1
    if ctrl.ambush_spawned_count >= 4:
        # Анти-абуз: начиная с 4-го моба засады — 0 опыта, 0 лута, 0 осколков маны и 0 прокачки векторов!
        amb_mob.no_rewards = True
        amb_mob.xp_value = 0

    game.mobs.append(amb_mob)
    game.play_spatial("alert", amb_mob.x, amb_mob.y, max_dist=18.0)


def update_mirror_puzzles(game, dt):
    puzzles = getattr(game, "mirror_puzzles", [])
    if not puzzles:
        return

    for ctrl in puzzles:
        _update_body_pushing_mirrors(game, ctrl, dt)
        _update_puzzle_ambush_spawner(game, ctrl, dt)
        recalculate_mirror_puzzle(game, ctrl)

        ctrl.burn_tick_timer += dt
        if ctrl.burn_tick_timer >= 0.45:
            ctrl.burn_tick_timer = 0.0
            for (x0, y0), (x1, y1), _, _ in ctrl.beam_segments:
                seg_len = math.hypot(x1 - x0, y1 - y0)
                if seg_len < 0.05:
                    continue
                nx, ny = (x1 - x0) / seg_len, (y1 - y0) / seg_len
                for m in game.mobs:
                    vx, vy = m.x - x0, m.y - y0
                    proj = max(0.0, min(seg_len, vx * nx + vy * ny))
                    if math.hypot(vx - nx * proj, vy - ny * proj) <= 0.48:
                        m.apply_status("burn", 1.8, game.add_popup, dmg_val=3)


def inject_mirror_puzzle_lights(game, lights, player_open_tiles, register_light_fn):
    """Передаёт усиленное 2.5D-освещение луча и кристаллов в шейдер ModernGL."""
    for ctrl in getattr(game, "mirror_puzzles", []):
        if ctrl.emitter_state == "need_lever":
            continue

        for em in ctrl.emitters:
            if (em.x, em.y) in player_open_tiles:
                ex_w, ey_w = (em.x + 0.5) * TILE_W, (em.y + 0.5) * TILE_H
                bc = getattr(em, "beam_color", ctrl.beam_color)
                mult = 0.65 if ctrl.emitter_state == "need_lens" else 1.25
                l_col = ((bc[0] / 160.0) * mult, (bc[1] / 160.0) * mult, (bc[2] / 160.0) * mult)
                rad = 52.0 if ctrl.emitter_state == "need_lens" else 84.0
                register_light_fn(ex_w, ey_w, ey_w, 22.0, rad, l_col, None, ignore_d=True)

        if ctrl.solved and (ctrl.receiver.x, ctrl.receiver.y) in player_open_tiles:
            rx_w, ry_w = (ctrl.receiver.x + 0.5) * TILE_W, (ctrl.receiver.y + 0.5) * TILE_H
            bc = ctrl.beam_color
            l_col = (min(1.65, bc[0] / 145.0 + 0.30), min(1.65, bc[1] / 145.0 + 0.30), min(1.65, bc[2] / 145.0 + 0.30))
            register_light_fn(rx_w, ry_w, ry_w, 24.0, 102.0, l_col, None, ignore_d=True)

        lights_added = 0
        for (x0, y0), (x1, y1), _, b_col in ctrl.beam_segments:
            if lights_added >= 8:
                break
            mx, my = (x0 + x1) * 0.5, (y0 + y1) * 0.5
            if (int(mx), int(my)) in player_open_tiles:
                lights_added += 1
                l_col = (b_col[0] / 155.0, b_col[1] / 155.0, b_col[2] / 155.0)
                register_light_fn(mx * TILE_W, my * TILE_H, my * TILE_H, 18.0, 78.0, l_col, None, ignore_d=True)


def render_mirror_puzzles_beams(screen, game, cam_x, cam_y, visible_tiles):
    """
    Рисует широкий (52 px) полупрозрачный поток света повышенной интенсивности,
    либо рассеянный конус света (если в излучателе нет фокусирующей линзы),
    а также контрастные грани зеркал.
    """
    puzzles = getattr(game, "mirror_puzzles", [])
    if not puzzles:
        return

    beam_surf = getattr(game, "_mirror_beam_surf", None)
    target_size = (VIEW_W * SCALE, VIEW_H * SCALE)
    if beam_surf is None or beam_surf.get_size() != target_size:
        beam_surf = pygame.Surface(target_size, pygame.SRCALPHA)
        game._mirror_beam_surf = beam_surf
    beam_surf.fill((0, 0, 0, 0))

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
                    pygame.draw.polygon(beam_surf, col_c, [(ox, oy), p1, p2])

    # 2. Собираем видимые сегменты сфокусированного потока света
    vis_segs = []
    for ctrl in puzzles:
        for (x0, y0), (x1, y1), (dx, dy), b_col in ctrl.beam_segments:
            if (int(x0), int(y0)) not in visible_tiles and (int(x1), int(y1)) not in visible_tiles:
                continue
            sx0 = int((x0 * TILE_W - cam_x) * SCALE)
            sy0 = int(((y0 - 0.22) * TILE_H - cam_y) * SCALE)
            sx1 = int((x1 * TILE_W - cam_x) * SCALE)
            sy1 = int(((y1 - 0.22) * TILE_H - cam_y) * SCALE)
            if max(sy0, sy1) < -56 or min(sy0, sy1) >= VIEW_H * SCALE + 56:
                continue
            vis_segs.append(((sx0, sy0), (sx1, sy1), b_col))

    if vis_segs:
        any_drawn = True
        # Повышенная на ~28% интенсивность полупрозрачных слоёв широкого потока света (52 px -> 14 px)
        layers = [
            (52, 0.00, int(25 * pulse)),  # Широкое мягкое рассеивание (52 px)
            (40, 0.05, int(46 * pulse)),  # Сочная цветная кромка света (40 px)
            (28, 0.25, int(68 * pulse)),  # Основной полупрозрачный поток (28 px)
            (20, 0.60, int(92 * pulse)),  # Переходный горячий слой (20 px)
            (14, 0.94, int(122 * pulse)), # Яркая полупрозрачная белая середина (14 px)
        ]
        for width_px, white_mix, alpha_val in layers:
            rad_joint = width_px // 2
            for p0, p1, (cr, cg, cb) in vis_segs:
                lr = min(255, int(cr * (1.0 - white_mix) + 255 * white_mix))
                lg = min(255, int(cg * (1.0 - white_mix) + 255 * white_mix))
                lb = min(255, int(cb * (1.0 - white_mix) + 255 * white_mix))
                rgba = (lr, lg, lb, alpha_val)
                pygame.draw.line(beam_surf, rgba, p0, p1, width_px)
                pygame.draw.circle(beam_surf, rgba, p0, rad_joint)
                pygame.draw.circle(beam_surf, rgba, p1, rad_joint)

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
                pygame.draw.circle(beam_surf, (cr, cg, cb, 60), (hx, hy), r_p + 8)
                pygame.draw.circle(beam_surf, (cr, cg, cb, 115), (hx, hy), r_p)
                pygame.draw.circle(beam_surf, (255, 255, 255, 155), (hx, hy), 10)
            elif h_kind in ("back_blocked", "wall", "blocked"):
                pygame.draw.circle(beam_surf, (cr, cg, cb, 70), (hx, hy), 18)

    if any_drawn:
        screen.blit(beam_surf, (0, 0))

    # Чёткая отрисовка рабочей грани и глухой спинки каждого видимого зеркала
    for ctrl in puzzles:
        for m in ctrl.mirrors:
            if (m.x, m.y) not in visible_tiles:
                continue
            mcx = int(((m.x + 0.5) * TILE_W - cam_x) * SCALE)
            mcy = int(((m.y + 0.26) * TILE_H - cam_y) * SCALE)
            if not (0 <= mcy < VIEW_H * SCALE):
                continue

            is_bs = (m.mirror_ori % 2 == 0)
            if is_bs:
                p_a, p_b = (mcx - 15, mcy - 15), (mcx + 15, mcy + 15)
            else:
                p_a, p_b = (mcx - 15, mcy + 15), (mcx + 15, mcy - 15)

            if getattr(m, "is_double", False):
                pygame.draw.line(screen, (235, 185, 60), p_a, p_b, 8)
                pygame.draw.line(screen, (140, 240, 255), p_a, p_b, 5)
                pygame.draw.line(screen, (255, 255, 255), p_a, p_b, 2)
                for sgn in (-1, 1):
                    nx = sgn * 7
                    ny = sgn * (-1 if is_bs else 1) * 7
                    pygame.draw.circle(screen, (185, 248, 255), (mcx + nx, mcy + ny), 3)
            else:
                fnx, fny = SINGLE_FRONT_NORMAL[m.mirror_ori % 4]
                back_apex = (mcx - fnx * 15, mcy - fny * 15)
                pygame.draw.polygon(screen, (42, 28, 26), [p_a, p_b, back_apex])
                pygame.draw.polygon(screen, (22, 16, 18), [p_a, p_b, back_apex], 2)

                f_a = (p_a[0] + fnx * 2, p_a[1] + fny * 2)
                f_b = (p_b[0] + fnx * 2, p_b[1] + fny * 2)
                pygame.draw.line(screen, (110, 225, 255), f_a, f_b, 5)
                pygame.draw.line(screen, (250, 255, 255), f_a, f_b, 2)

                glint_c = (mcx + fnx * 8, mcy + fny * 8)
                pygame.draw.line(screen, (150, 240, 255), glint_c, (glint_c[0] + fnx * 4, glint_c[1]), 2)
                pygame.draw.line(screen, (150, 240, 255), glint_c, (glint_c[0], glint_c[1] + fny * 4), 2)