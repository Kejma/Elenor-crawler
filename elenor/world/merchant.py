"""Rare dedicated merchant rooms; no ordinary encounter population inside."""

from collections import deque
import random

from elenor.config import MAP_COLS, MAP_ROWS


def reachable_tiles(dungeon, start):
    """Starting component with openable doors, but no locked gates."""
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pt = nx, ny = x + dx, y + dy
            if not (0 <= nx < MAP_COLS and 0 <= ny < MAP_ROWS) or pt in seen:
                continue
            if dungeon.grid[ny][nx] in (1, 5, 6, 7) or pt in dungeon.solid_props:
                continue
            door = dungeon.doors.get(pt)
            if door and door.locked and not door.is_open:
                continue
            seen.add(pt)
            queue.append(pt)
    return seen


def reserve_merchant_room(dungeon):
    """Convert one reachable ordinary room, leaving its perimeter walkable."""
    if dungeon.floor_num < 2 or random.random() >= dungeon.merchant_chance:
        return
    info = dungeon.mirror_puzzle_info
    forbidden = []
    if info:
        forbidden = [
            info["puzzle_rect"].inflate(2, 2),
            info["sealed_rect"].inflate(2, 2),
        ]
    reachable = reachable_tiles(dungeon, dungeon.start_pos)
    # Start, exit and optional reward/boss area remain mission-owned.
    excluded = dungeon.rooms[:1] + dungeon.rooms[-1:]
    if info and not info["tutorial"]:
        excluded += dungeon.rooms[-2:-1]
    candidates = [
        r
        for r in dungeon.rooms
        if r not in excluded
        and r.width >= 7
        and r.height >= 6
        and r.center in reachable
        and not any(r.colliderect(f) for f in forbidden)
        and not any(r.collidepoint(pt) for pt in dungeon.levers)
    ]
    if not candidates:
        return  # An unlucky layout simply has no merchant; don't force a bad room.
    room = random.choice(candidates)
    dungeon.merchant_room = room
    dungeon._carve_rect(room, 4)
    for y in range(room.top, room.bottom):
        for x in range(room.left, room.right):
            dungeon.overlays.pop((x, y), None)
    rug = room.inflate(-4, -4)
    for y in range(rug.top, rug.bottom):
        for x in range(rug.left, rug.right):
            dungeon.carpets.add((x, y))
    dungeon.atmo_zones = [
        z for z in dungeon.atmo_zones if not z["rect"].colliderect(room)
    ]
    dungeon.fog_zones = [
        z for z in dungeon.fog_zones if not room.collidepoint(z["wx"], z["wy"])
    ]
    dungeon.room_lights.append(
        dict(x=room.centerx, y=room.centery, color=(1.15, 0.88, 0.50), radius=130.0)
    )
    for x in (room.left + 1, room.right - 2):
        dungeon.braziers.append(
            dict(x=x, y=room.bottom - 2, color=(1.15, 0.72, 0.30), radius=72.0)
        )
    dungeon.invalidate_light_cache()


def populate_merchant_room(game, InteractableCls):
    room = game.dungeon.merchant_room
    if room is None:
        return
    npc = InteractableCls(room.centerx, room.top + 2, "npc_merchant")
    game.objects.append(npc)
    furniture = [
        (room.left + 1, room.top + 2, "merchant_shelves"),
        (room.right - 2, room.top + 2, "merchant_goods"),
        (room.centerx, room.top, "merchant_sign"),
    ]
    furniture += [
        (room.centerx + offset, room.top + 3, "merchant_counter")
        for offset in (-1, 0, 1)
    ]
    for x, y, kind in furniture:
        obj = InteractableCls(x, y, kind)
        obj.merchant_owner = npc
        game.objects.append(obj)
