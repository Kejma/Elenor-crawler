from collections import deque
import math
import random
import pygame
from elenor.config import TILE_W, TILE_H
from elenor.entities import Enemy, Particle

from elenor.puzzles.optics import SINGLE_REFLECT_MAP, DOUBLE_REFLECT_MAP

def get_required_single_ori(in_dir, out_dir):
    for ori, rmap in SINGLE_REFLECT_MAP.items():
        if rmap.get(in_dir) == out_dir:
            return ori
    return 0


def get_biome_tiles(dungeon):
    info = getattr(dungeon, "mirror_puzzle_info", None)
    if info and "tiles" in info:
        return info["tiles"]
    fl = getattr(dungeon, "floor_num", 3)
    if fl in (1, 2):
        return 6, 4
    if fl == 3:
        return 1, 0
    return 7, 8


def _puzzle_text(game, key):
    return game.loc.get("mirror_puzzle", {}).get(key, key)


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


def reachable_floor_tiles(dungeon, start_xy, extra_blocked=(), max_distance=None):
    """Walkable component; closed unlocked doors can be opened by the player.

    Locked gates remain blocked. Unlike find_path(), this never returns a partial
    path and has no search budget that could turn a valid location into a fallback.
    """
    blocked = set(extra_blocked)
    start = tuple(map(int, start_xy))
    seen = {start}
    q = deque([(start, 0)])
    while q:
        (x, y), distance = q.popleft()
        if max_distance is not None and distance >= max_distance:
            continue
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pt = tx, ty = x + dx, y + dy
            if not (0 <= tx < dungeon.width and 0 <= ty < dungeon.height) or pt in seen or pt in blocked:
                continue
            door = dungeon.doors.get(pt)
            if door and door.locked and not door.is_open:
                continue
            if door and not door.locked:
                if dungeon.grid[ty][tx] in (1, 5, 6, 7) or pt in dungeon.solid_props:
                    continue
            elif dungeon.is_blocking_move(tx, ty):
                continue
            seen.add(pt)
            q.append((pt, distance + 1))
    return seen


def find_safe_accessible_tile_for_puzzle_item(game, puzzle_rect, forbidden_rects=None):
    """Return a reachable unoccupied key tile, or None; never guess a fallback."""
    from elenor.entities import SOLID_INTERACTABLE_KINDS
    dungeon = game.dungeon
    start = int(game.player.x), int(game.player.y)
    forbidden = list(forbidden_rects or []) + [puzzle_rect.inflate(2, 2)]
    merchant_room = getattr(dungeon, "merchant_room", None)
    if merchant_room is not None:
        forbidden.append(merchant_room)
    occupied = {(o.x, o.y) for o in game.objects if not o.used}
    occupied.update(dungeon.doors)
    occupied.update(dungeon.levers)
    occupied.update((int(m.x), int(m.y)) for m in game.mobs if m.hp > 0)
    occupied.update((br["x"], br["y"]) for br in dungeon.braziers)
    solids = {(o.x, o.y) for o in game.objects
              if not o.used and o.kind in SOLID_INTERACTABLE_KINDS}
    reachable = reachable_floor_tiles(dungeon, start, solids)
    candidates = [pt for pt in sorted(reachable) if pt != start and pt not in occupied
                  and not any(r.collidepoint(pt) for r in forbidden)]
    if not candidates:
        return None
    # Prefer a different room, keeping the fallback in the same proven component.
    other_rooms = [pt for pt in candidates if any(r.collidepoint(pt) and not r.collidepoint(start)
                                                for r in dungeon.rooms)]
    return random.choice(other_rooms or candidates)


def _layout_hits_receiver(room_rect, layout, solved):
    """Validate the optical route before changing the world or opening a gate."""
    mirrors = {(m["pos"] if solved else m["start_pos"]): m for m in layout["mirrors"]}
    x, y = layout["em_pos"]
    dx, dy = layout["em_dir"]
    visited = set()
    while (x, y, dx, dy) not in visited:
        visited.add((x, y, dx, dy))
        x, y = x + dx, y + dy
        if not room_rect.collidepoint(x, y) or (x, y) in layout["walls"] or (x, y) == layout["em_pos"]:
            return False
        if (x, y) == layout["rec_pos"]:
            return True
        m = mirrors.get((x, y))
        if m:
            ori = m["ori"] if solved else m["start_ori"]
            direction = (DOUBLE_REFLECT_MAP if m["is_double"] else SINGLE_REFLECT_MAP)[ori].get((dx, dy))
            if direction is None:
                return False
            dx, dy = direction
    return False


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
        num_bounces = random.randint(3, 5) + max(0, (rw - 11) // 2)
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

    if rw >= 13:
        nodes = {em_pos, rec_pos} | {m["pos"] for m in mirrors_spec}
        partition = {(rx0 + rw // 2, y) for y in range(ry0, ry0 + rh)}
        passage = {(rx0 + rw // 2, ry0 + rh // 2 + dy) for dy in (-1, 0, 1)}
        walls.update(partition - beam_path_tiles - nodes - protected_porch - passage)

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

    for ox, oy in (em_pos, rec_pos):
        if not any((ox + dx, oy + dy) in reachable for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
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

    layout = {
        "walls": walls,
        "em_pos": em_pos,
        "em_dir": d_in if use_double else em_dir,
        "rec_pos": rec_pos,
        "mirrors": mirrors_spec,
    }
    if not _layout_hits_receiver(room_rect, layout, solved=True) or _layout_hits_receiver(room_rect, layout, solved=False):
        return None
    return layout


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
    if emitter_mode == "random":
        emitter_mode = random.choice(["ready", "need_lever", "need_lens"])
    if emitter_mode not in ("ready", "need_lever", "need_lens"):
        raise ValueError("Unknown emitter mode")

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

    dungeon.invalidate_terrain(room_rect)
    if hasattr(game, "fx") and game.fx:
        game.fx.rebuild_wall_grid(dungeon)

    ctrl = MirrorPuzzleController(
        room_rect, [emitter_obj], receiver_obj, mirror_objs, target_doors,
        beam_color=beam_color, emitter_state=emitter_mode, ambush_enabled=ambush_enabled
    )

    # Если излучателю нужен рычаг или фокусирующая линза — спавним их строго в ДОСТУПНОЙ зоне этажа!
    key_tile = None
    if emitter_mode != "ready":
        key_tile = find_safe_accessible_tile_for_puzzle_item(game, room_rect, forbidden_key_rects)
        if key_tile is None:
            # An unlucky floor must never require an unreachable key.
            ctrl.emitter_state = "ready"
            emitter_obj.kind = "light_emitter"
    if key_tile is not None and emitter_mode == "need_lever":
        kx, ky = key_tile
        p_lev = InteractableCls(kx, ky, "lever_off")
        p_lev.is_puzzle_emitter_lever = True
        p_lev.puzzle_ctrl = ctrl
        game.objects.append(p_lev)
    elif key_tile is not None and emitter_mode == "need_lens":
        kx, ky = key_tile
        lens_itm = game.make_item("focusing_lens")
        game.objects.append(InteractableCls(kx, ky, "loot", lens_itm))

    game.mirror_puzzles.append(ctrl)
    recalculate_mirror_puzzle(game, ctrl)
    return ctrl


def spawn_floor_mirror_puzzle(
    game, InteractableCls, beam_color=(255, 45, 55), spawn_chance=1.0,
    emitter_mode="random", ambush_enabled=None
):
    dungeon = game.dungeon
    info = getattr(dungeon, "mirror_puzzle_info", None)
    if info is None:
        return None

    tutorial = info.get("tutorial", False)
    if tutorial:
        emitter_mode, ambush_enabled = "ready", False
    elif ambush_enabled is None:
        ambush_enabled = dungeon.floor_num >= 3 and random.random() < 0.35
    p_rect = info["puzzle_rect"]
    bd_x, bd_y = info["gate_door"]
    ed_x, ed_y = info["entry_door"]
    gate_door = dungeon.doors.get((bd_x, bd_y))

    if random.random() > float(spawn_chance):
        if gate_door is not None:
            gate_door.locked = False
        return None

    game.mobs = [m for m in game.mobs if not p_rect.inflate(2, 2).collidepoint(int(m.x), int(m.y))]
    clear_area = p_rect.inflate(2, 2)
    game.objects = [
        o for o in game.objects
        if (o.x, o.y) in dungeon.jungle_controls or not clear_area.collidepoint(o.x, o.y)
    ]

    cr, cg, cb = beam_color
    dungeon.room_lights.append({
        "x": p_rect.centerx, "y": p_rect.centery,
        "color": (0.18 + cr / 1700.0, 0.18 + cg / 1700.0, 0.23 + cb / 1700.0),
        "radius": 126.0
    })

    target_doors = [gate_door] if gate_door is not None else []
    return setup_mirror_puzzle_in_room(
        game, p_rect, target_doors, InteractableCls,
        beam_color=beam_color, spawn_chance=1.0,
        protected_doors=[(ed_x, ed_y), (bd_x, bd_y)],
        emitter_mode=emitter_mode, ambush_enabled=ambush_enabled,
        forbidden_key_rects=[info["sealed_rect"]]
    )


def spawn_pre_boss_mirror_puzzle(game, InteractableCls, **kwargs):
    """Compatibility entry point for the rat campaign introduction."""
    return spawn_floor_mirror_puzzle(game, InteractableCls, **kwargs)


def recalculate_mirror_puzzle(game, ctrl: MirrorPuzzleController):
    dungeon = game.dungeon
    # Optical geometry is static between interactions. Keep the traced segments
    # for burn ticks and rendering instead of walking every beam each frame.
    signature = (
        getattr(dungeon, "geometry_revision", 0), ctrl.emitter_state,
        tuple((m.x, m.y, m.mirror_ori, m.used) for m in ctrl.mirrors),
        tuple((em.x, em.y, em.beam_dir, em.beam_color) for em in ctrl.emitters),
        tuple((o.x, o.y) for o in game.objects
              if not o.used and o.kind in ("barrel", "chest", "crate_stack")),
    )
    if signature == getattr(ctrl, "_optical_signature", None):
        return
    ctrl._optical_signature = signature
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

        for _ in range(dungeon.width * dungeon.height * 4):
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
        game.add_popup(ctrl.receiver.x + 0.5, ctrl.receiver.y + 0.5, _puzzle_text(game, "passage_open"), (255, 110, 125), big=True)
        game.set_thought(
            _puzzle_text(game, "puzzle_solved"),
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
            game.add_popup(obj.x + 0.5, obj.y + 0.5, _puzzle_text(game, "emitter_powered"), (255, 220, 95), big=True)
            game.set_thought(_puzzle_text(game, "power_restored"), important=True)
        else:
            game.play_spatial("step", obj.x + 0.5, obj.y + 0.5)
            game.set_thought(_puzzle_text(game, "lever_already_on"), important=False, chance=0.8)
        return True

    # 2. Осмотр или установка Фокусирующей Линзы в Излучатель
    if obj.kind in ("light_emitter", "light_emitter_off"):
        ctrl = next((c for c in getattr(game, "mirror_puzzles", []) if obj in c.emitters), None)
        if ctrl and ctrl.emitter_state == "need_lever":
            game.play_spatial("hurt", obj.x + 0.5, obj.y + 0.5)
            game.add_popup(obj.x + 0.5, obj.y + 0.5, _puzzle_text(game, "no_power"), (255, 115, 95))
            game.set_thought(_puzzle_text(game, "find_lever"), important=True)
            return True

        if ctrl and ctrl.emitter_state == "need_lens":
            lens_itm = game.player.find_quest_item("focusing_lens")
            if lens_itm is not None:
                game.player.remove_item_everywhere(lens_itm)
                ctrl.emitter_state = "ready"
                recalculate_mirror_puzzle(game, ctrl)
                game.sfx.play("magic")
                game.add_popup(obj.x + 0.5, obj.y + 0.5, _puzzle_text(game, "lens_installed"), (130, 255, 195), big=True)
                game.set_thought(_puzzle_text(game, "lens_fitted"), important=True)
            else:
                game.play_spatial("ui", obj.x + 0.5, obj.y + 0.5)
                game.add_popup(obj.x + 0.5, obj.y + 0.5, _puzzle_text(game, "need_lens"), (255, 200, 90))
                game.set_thought(_puzzle_text(game, "find_lens"), important=True)
            return True

        game.play_spatial("magic", obj.x + 0.5, obj.y + 0.5)
        game.set_thought(_puzzle_text(game, "emitter_examine"), important=False, chance=0.85)
        return True

    if obj.kind in ("light_receiver_off", "light_receiver_on"):
        game.play_spatial("ui", obj.x + 0.5, obj.y + 0.5)
        if obj.kind == "light_receiver_on":
            game.set_thought(_puzzle_text(game, "receiver_on"), important=False, chance=0.85)
        else:
            game.set_thought(_puzzle_text(game, "receiver_off"), important=False, chance=0.85)
        return True

    if not getattr(obj, "is_mirror", False):
        return False

    if getattr(obj, "is_movable", False):
        game.play_spatial("step_stone", obj.x + 0.5, obj.y + 0.5)
        game.set_thought(_puzzle_text(game, "movable_mirror"), important=False, chance=0.9)
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
    alive_ambush = sum(1 for m in game.mobs if m.hp > 0 and getattr(m, "puzzle_ambush_owner", None) is ctrl)
    if alive_ambush >= 3:
        return

    ctrl.ambush_timer -= dt
    if ctrl.ambush_timer > 0.0:
        return
    ctrl.ambush_timer = random.uniform(7.0, 10.5)

    dungeon = game.dungeon
    vis_tiles = getattr(game, "current_visible_tiles", None)
    if vis_tiles is None:
        return  # Visibility has not been calculated for this floor yet.
    boss_r = getattr(dungeon, "boss_room", None)
    occupied = {(o.x, o.y) for o in game.objects if not o.used}
    occupied.update((int(m.x), int(m.y)) for m in game.mobs if m.hp > 0)
    occupied.update(dungeon.doors)
    occupied.update(dungeon.levers)
    # AI cannot open even unlocked doors: use actual movement blockers here.
    reachable = _bfs_reachable(
        pygame.Rect(0, 0, dungeon.width, dungeon.height),
        {(x, y) for y in range(dungeon.height) for x in range(dungeon.width)
         if dungeon.is_blocking_move(x, y)},
        (int(px), int(py))
    )
    candidates = []
    for tx, ty in sorted(reachable - occupied):
        merchant_room = getattr(dungeon, "merchant_room", None)
        if merchant_room is not None and merchant_room.collidepoint(tx, ty):
            continue
        # Check neighbouring tiles as well: a sprite may extend into a visible tile.
        if any((tx + dx, ty + dy) in vis_tiles for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
            continue
        if boss_r and boss_r.inflate(2, 2).collidepoint(tx, ty):
            continue
        dist = math.hypot(tx + 0.5 - px, ty + 0.5 - py)
        if not 5.5 <= dist <= 14.5:
            continue
        # Conservative direct LOS check also protects against gaps between FOV rays.
        if dungeon.has_line_of_sight(px, py, tx + 0.5, ty + 0.5, 18.0):
            continue
        path = dungeon.find_path((tx, ty), (int(px), int(py)), max_expanded=dungeon.width * dungeon.height)
        if path and len(path) <= 22 and tuple(map(int, path[-1])) == (int(px), int(py)):
            candidates.append((tx, ty))
    if not candidates:
        return
    spawn_xy = random.choice(candidates)

    fl = getattr(dungeon, "floor_num", 3)
    mob_kind = "rat_cultist" if (fl >= 3 and random.random() < 0.35) else "rat"
    amb_mob = Enemy(spawn_xy[0], spawn_xy[1], kind=mob_kind, state="combat")
    if hasattr(game, "balance_data"):
        amb_mob.apply_balance_profile(game.balance_data.get("enemies", {}).get(mob_kind), floor_num=fl)
    amb_mob.awareness = 100.0
    amb_mob.from_puzzle_ambush = True
    amb_mob.puzzle_ambush_owner = ctrl

    ctrl.ambush_spawned_count += 1
    if ctrl.ambush_spawned_count >= 4:
        # Анти-абуз: начиная с 4-го моба засады — 0 опыта, 0 лута, 0 осколков маны и 0 прокачки векторов!
        amb_mob.no_rewards = True
        amb_mob.xp_value = 0

    game.mobs.append(amb_mob)
    game.play_spatial("alert", amb_mob.x, amb_mob.y, max_dist=18.0)


def update_mirror_puzzles(game, dt):
    puzzles = getattr(game, "mirror_puzzles", [])
    if not puzzles or dt <= 0.0 or game.player.hp <= 0:
        return

    for ctrl in puzzles:
        _update_body_pushing_mirrors(game, ctrl, dt)
        recalculate_mirror_puzzle(game, ctrl)
        _update_puzzle_ambush_spawner(game, ctrl, dt)

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
    """Add local light from the crystals and reflected beam."""
    for ctrl in getattr(game, "mirror_puzzles", []):
        if ctrl.emitter_state == "need_lever":
            continue

        for em in ctrl.emitters:
            if (em.x, em.y) in player_open_tiles:
                ex_w, ey_w = (em.x + 0.5) * TILE_W, (em.y + 0.5) * TILE_H
                bc = getattr(em, "beam_color", ctrl.beam_color)
                mult = 0.20 if ctrl.emitter_state == "need_lens" else 0.34
                l_col = tuple(channel / 255.0 * mult for channel in bc)
                rad = 38.0 if ctrl.emitter_state == "need_lens" else 52.0
                register_light_fn(ex_w, ey_w, ey_w, 22.0, rad, l_col, None, ignore_d=True)

        if ctrl.solved and (ctrl.receiver.x, ctrl.receiver.y) in player_open_tiles:
            rx_w, ry_w = (ctrl.receiver.x + 0.5) * TILE_W, (ctrl.receiver.y + 0.5) * TILE_H
            bc = ctrl.beam_color
            l_col = tuple(0.06 + channel / 710.0 for channel in bc)
            register_light_fn(rx_w, ry_w, ry_w, 24.0, 49.0, l_col, None, ignore_d=True)

        lights_added = 0
        for (x0, y0), (x1, y1), _, b_col in ctrl.beam_segments:
            if lights_added >= 4:
                break
            mx, my = (x0 + x1) * 0.5, (y0 + y1) * 0.5
            if (int(mx), int(my)) in player_open_tiles:
                lights_added += 1
                l_col = tuple(channel / 1500.0 for channel in b_col)
                register_light_fn(mx * TILE_W, my * TILE_H, my * TILE_H, 18.0, 36.0, l_col, None, ignore_d=True)


