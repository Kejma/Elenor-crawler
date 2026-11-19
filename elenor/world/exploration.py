"""The player's terrain notes for one location."""

from elenor.config import (
    DEEP_WATER,
    FALLEN_LOG,
    OPAQUE_WALL_TILES,
    PEBBLE_SHORE,
    PIER,
    SHALLOW_WATER,
)

OBJECT_LANDMARKS = {"stairs": "down", "npc_merchant": "merchant"}


def terrain_kind(tile):
    if tile in (5, 21, 22, 56, 57):
        return "trees"
    if tile in OPAQUE_WALL_TILES:
        return "wall"
    if tile == DEEP_WATER:
        return "deep"
    if tile in (2, 32, SHALLOW_WATER):
        return "water"
    if tile in (4, 13, 27, PIER, FALLEN_LOG):
        return "wood"
    if tile in (9, 11, 12, 25, PEBBLE_SHORE, 41, 42):
        return "trail"
    if tile in (3, 10, 23, 45, 47, 49):
        return "grass"
    return "floor"


def remember_tiles(dungeon, seen, objects=()):
    """Snapshot terrain, including the state of doors when last seen."""
    changed = False
    explored = dungeon.explored_tiles
    for x, y in seen:
        position = (x, y)
        door = dungeon.doors.get(position)
        kind = "door" if door and not door.is_open else terrain_kind(dungeon.grid[y][x])
        if explored.get(position) != kind:
            explored[position] = kind
            changed = True
    if seen:
        for obj in objects:
            kind = OBJECT_LANDMARKS.get(obj.kind)
            if kind is None or obj.used:
                continue
            position = obj.x, obj.y
            if position in seen and dungeon.map_landmarks.get(position) != kind:
                dungeon.map_landmarks[position] = kind
                changed = True
    if changed:
        dungeon.exploration_revision += 1
