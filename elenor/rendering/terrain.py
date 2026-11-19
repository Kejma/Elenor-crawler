"""Bake terrain layers in world space while keeping doors and tree crowns live."""

from collections import OrderedDict
from dataclasses import dataclass
from weakref import WeakKeyDictionary

import pygame

from elenor.config import DEEP_WATER, FALLEN_LOG, PEBBLE_SHORE, PIER, SHALLOW_WATER, TILE_H, TILE_W
from elenor.entities.objects import JUNGLE_KEY_COLORS
from elenor.rendering.assets import get_carpet_autotile_key
from elenor.rendering.jungle import get_moss_autotile_key
from elenor.rendering.normals import rotate_normal_pair


CHUNK_TILES = 16
MAX_CHUNKS = 64
DIFFUSE_CLEAR = (12, 10, 16)
NORMAL_CLEAR = (128, 128, 255)

TILE_ROLE_MAP = {
    # Базовые тайлы
    1: "wall",
    6: "wall_wood",
    7: "wall_cave",
    8: "floor_5",
    9: "floor_6",
    # Джунгли, Хижины и Мраморный Храм (Пак 1: 10..20)
    10: "floor_jungle_grass",
    11: "floor_jungle_mud",
    12: "floor_jungle_soil",
    13: "floor_tribal_wood",
    14: "floor_marble_white",
    15: "floor_marble_dark",
    16: "floor_marble_mosaic",
    17: "wall_mud_rock",
    18: "wall_tribal_wood",
    19: "wall_marble_temple",
    20: "wall_marble_ruined",
    # Джунгли и Мраморный Храм (Пак 2: 23..36)
    23: "floor_jungle_swamp",
    24: "floor_jungle_cobble",
    25: "floor_river_sand",
    26: "floor_cave_basalt",
    27: "floor_tribal_mat",
    28: "floor_marble_checker",
    29: "floor_marble_rose",
    30: "floor_marble_jade",
    31: "floor_temple_gold",
    32: "floor_temple_water",
    33: "wall_bamboo_weave",
    34: "wall_cave_crystal",
    35: "wall_marble_obsidian",
    36: "wall_temple_relief",
    # Озеро и Рыбалка (37..42)
    SHALLOW_WATER: "floor_lake_shallow",
    DEEP_WATER: "floor_lake_deep",
    PIER: "floor_wooden_pier",
    PEBBLE_SHORE: "floor_pebble_shore",
    41: "floor_wet_sand",
    42: "floor_reed_mud",
    # Костяные Джунгли и Глубокие Пещеры (43..55)
    43: "floor_tar_pit",
    44: "floor_acid_pool",
    45: "floor_bone_grass",
    46: "floor_bone_grave",
    47: "floor_blood_marsh",
    48: "floor_bone_bridge",
    49: "floor_cave_fungus",
    50: "floor_cave_obsidian",
    51: "wall_bone_ribs",
    52: "wall_skull_catacomb",
    53: "wall_corrupted_wood",
    54: "wall_cave_web",
    55: "wall_cave_magma",
}
TALL_TREE_MAP = {
    5: ("floor_3", "tall_tree", "tall_tree"),
    21: ("floor_jungle_grass", "tall_jungle_tree", "tree_jungle"),
    22: ("floor_jungle_grass", "tall_palm_tree", "tree_palm"),
    56: ("floor_bone_grass", "tall_bone_tree", "tree_bone"),
    57: ("floor_blood_marsh", "tall_dead_mangrove", "tree_dead_mangrove"),
}


@dataclass(slots=True)
class _Chunk:
    tiles: pygame.Rect
    pixels: pygame.Rect
    diffuse: pygame.Surface
    normals: pygame.Surface
    trees: list
    animated_tiles: list
    roles: tuple
    frames: tuple


class TerrainCache:
    def __init__(self, assets, anim_bank, log_sections):
        self.assets = assets
        self.log_sections = log_sections
        self.anim_bank = anim_bank
        self.rotations = {}
        self.animations = {key: entry["frames"] for key, entry in anim_bank.items() if len(entry["frames"]) > 1}
        self.chunks = OrderedDict()
        self.maps = WeakKeyDictionary()
        self.fitting_roles = {}
        tile_prefixes = ("floor_", "wall", "ov_", "moss_", "carpet_", "door_")
        self.fitting_tiles = all(
            self._fits_role(key) for key in assets if key.startswith(tile_prefixes)
        ) and all(self._fits_pair(pair) for pair in log_sections.values())

    @staticmethod
    def _fits_pair(pair):
        return all(surface.get_width() <= TILE_W and surface.get_height() <= TILE_H for surface in pair)

    def _fits_role(self, key):
        if key not in self.fitting_roles:
            frames = self.animations.get(key, (self.assets[key],))
            # Rotated artwork must fit in both orientations.
            self.fitting_roles[key] = all(self._fits_pair(pair) and all(
                surface.get_height() <= TILE_W and surface.get_width() <= TILE_H for surface in pair
            ) for pair in frames)
        return self.fitting_roles[key]

    def _refresh_map(self, dungeon):
        previous = self.maps.get(dungeon)
        grid = dungeon.grid
        revision = dungeon.terrain_revision
        if previous is not None and previous[0] is grid and previous[1] == revision:
            return previous[2]

        dirty = dungeon.terrain_dirty_area
        if (previous is None or previous[0] is not grid or revision != previous[1] + 1
                or dirty is None):
            dirty = None
        else:
            # Moss, carpet edges and log endings depend on neighbouring tiles.
            dirty = dirty.inflate(2, 2)
        for key, chunk in list(self.chunks.items()):
            if key[0] is dungeon and (dirty is None or dirty.colliderect(chunk.tiles)):
                del self.chunks[key]

        # Custom art that extends beyond a tile needs the original painter's order.
        fits = self.fitting_tiles and all(
            self._fits_role(key) for key in set(dungeon.overlays.values()) if key in self.assets
        )
        self.maps[dungeon] = grid, revision, fits
        return fits

    def _layer(self, key, x, y, salt=0):
        if key in self.animations:
            return key
        if key not in self.assets and "floor_0" in self.animations:
            return "floor_0"
        base = self.assets.get(key, self.assets["floor_0"])
        meta = self.anim_bank.get(key)
        rotates = meta.get("random_rot", False) if meta else key in (
            "floor_3", "floor_5", "ov_pebbles", "ov_moss", "ov_cracks", "ov_planks_wear",
        )
        if not rotates:
            return base
        turn = ((x * 73 + y * 151 + (x ^ y) * 31 + salt * 19) >> 1) & 3
        if turn == 0:
            return base
        cache_key = key, turn
        if cache_key not in self.rotations:
            self.rotations[cache_key] = rotate_normal_pair(*base, turn)
        return self.rotations[cache_key]

    def _tile_layers(self, dungeon, x, y, width):
        grid = dungeon.grid
        row = grid[y]
        tile = row[x]
        tree = None
        log = tile == FALLEN_LOG
        if log:
            left = x > 0 and row[x - 1] == FALLEN_LOG
            right = x + 1 < width and row[x + 1] == FALLEN_LOG
            role = "floor_pebble_shore" if left != right else "floor_lake_deep"
        elif tile in TALL_TREE_MAP:
            role, crown, alternate = TALL_TREE_MAP[tile]
            tree = x, y, alternate if (x * 17 + y * 23) % 9 == 0 else crown
        else:
            role = TILE_ROLE_MAP.get(tile) or f"floor_{tile}"

        layers = [self._layer(role, x, y)]
        if log:
            layers.append(self.log_sections[left, right])
        point = x, y
        if point in dungeon.moss_tiles:
            key = get_moss_autotile_key(dungeon.moss_tiles, x, y)
            if key in self.assets:
                layers.append(key if key in self.animations else self.assets[key])
        overlay = dungeon.overlays.get(point)
        if overlay and overlay in self.assets:
            layers.append(self._layer(overlay, x, y, salt=77))
        if point in dungeon.carpets:
            key = get_carpet_autotile_key(dungeon.carpets, x, y)
            if key in self.assets:
                layers.append(key if key in self.animations else self.assets[key])
        return layers, tree

    def _paint(self, diffuse, normals, position, layers):
        for layer in layers:
            color, normal = self.assets[layer] if isinstance(layer, str) else layer
            diffuse.blit(color, position)
            normals.blit(normal, position)

    def _bake(self, dungeon, left, top, width, height):
        tiles = pygame.Rect(left, top, min(CHUNK_TILES, width - left), min(CHUNK_TILES, height - top))
        pixels = pygame.Rect(tiles.x * TILE_W, tiles.y * TILE_H, tiles.width * TILE_W, tiles.height * TILE_H)
        diffuse = pygame.Surface(pixels.size, depth=32)
        normals = pygame.Surface(pixels.size, depth=32)
        diffuse.fill(DIFFUSE_CLEAR)
        normals.fill(NORMAL_CLEAR)
        trees, animated = [], []
        color_blits, normal_blits = [], []
        animation_roles = set()
        for y in range(tiles.top, tiles.bottom):
            for x in range(tiles.left, tiles.right):
                position = (x - left) * TILE_W, (y - top) * TILE_H
                layers, tree = self._tile_layers(dungeon, x, y, width)
                is_animated = False
                for layer in layers:
                    if isinstance(layer, str):
                        pair = self.assets[layer]
                        animation_roles.add(layer)
                        is_animated = True
                    else:
                        pair = layer
                    color_blits.append((pair[0], position))
                    normal_blits.append((pair[1], position))
                if tree is not None:
                    trees.append(tree)
                if is_animated:
                    animated.append((pygame.Rect(*position, TILE_W, TILE_H), layers))
        diffuse.blits(color_blits, doreturn=False)
        normals.blits(normal_blits, doreturn=False)
        roles = tuple(sorted(animation_roles))
        frames = tuple(self.assets[key] for key in roles)
        return _Chunk(tiles, pixels, diffuse, normals, trees, animated, roles, frames)

    def _animate(self, chunk):
        if not chunk.roles:
            return
        frames = tuple(self.assets[key] for key in chunk.roles)
        if frames == chunk.frames:
            return
        chunk.frames = frames
        for rect, layers in chunk.animated_tiles:
            chunk.diffuse.fill(DIFFUSE_CLEAR, rect)
            chunk.normals.fill(NORMAL_CLEAR, rect)
            self._paint(chunk.diffuse, chunk.normals, rect.topleft, layers)

    def _draw_door(self, door, diffuse, normals, position):
        key = "door_open" if door.is_open else ("door_locked" if door.locked else "door_closed")
        color, normal = self.assets[key]
        diffuse.blit(color, position)
        normals.blit(normal, position)
        if door.locked and door.key_color:
            x, y = position
            pygame.draw.rect(diffuse, JUNGLE_KEY_COLORS[door.key_color], (x + 10, y + 8, 3, 4))

    def _get_chunk(self, dungeon, x, y, width, height):
        key = dungeon, x, y
        chunk = self.chunks.get(key)
        if chunk is None:
            chunk = self._bake(dungeon, x, y, width, height)
            self.chunks[key] = chunk
            if len(self.chunks) > MAX_CHUNKS:
                self.chunks.popitem(last=False)
        else:
            self.chunks.move_to_end(key)
        return chunk

    def warm(self, dungeon):
        """Fill the cache after the location's final terrain edits."""
        width, height = dungeon.width, dungeon.height
        columns = range(0, width, CHUNK_TILES)
        rows = range(0, height, CHUNK_TILES)
        if len(columns) * len(rows) <= MAX_CHUNKS and self._refresh_map(dungeon):
            for y in rows:
                for x in columns:
                    self._get_chunk(dungeon, x, y, width, height)

    def collect_visible(self, dungeon, left, top, right, bottom):
        if left >= right or top >= bottom:
            return [], [], []
        width, height = dungeon.width, dungeon.height
        if not self._refresh_map(dungeon):
            return None
        visible_pixels = pygame.Rect(left * TILE_W, top * TILE_H, (right - left) * TILE_W, (bottom - top) * TILE_H)
        chunks = []
        trees = []
        for y in range(top // CHUNK_TILES * CHUNK_TILES, bottom, CHUNK_TILES):
            for x in range(left // CHUNK_TILES * CHUNK_TILES, right, CHUNK_TILES):
                chunk = self._get_chunk(dungeon, x, y, width, height)
                self._animate(chunk)
                visible = visible_pixels.clip(chunk.pixels)
                chunks.append((chunk, visible))
                trees.extend(tree for tree in chunk.trees if left <= tree[0] < right and top <= tree[1] < bottom)
        doors = [
            (x, y, door)
            for (x, y), door in dungeon.doors.items()
            if left <= x < right and top <= y < bottom
        ]
        return chunks, doors, trees

    def draw(self, dungeon, left, top, right, bottom, cam_x, cam_y, diffuse, normals):
        trees = []
        if left >= right or top >= bottom:
            return trees
        width, height = dungeon.width, dungeon.height
        if not self._refresh_map(dungeon):
            for y in range(top, bottom):
                for x in range(left, right):
                    position = x * TILE_W - cam_x, y * TILE_H - cam_y
                    layers, tree = self._tile_layers(dungeon, x, y, width)
                    self._paint(diffuse, normals, position, layers)
                    door = dungeon.doors.get((x, y))
                    if door is not None:
                        self._draw_door(door, diffuse, normals, position)
                    if tree is not None:
                        trees.append(tree)
            return trees

        visible_pixels = pygame.Rect(left * TILE_W, top * TILE_H, (right - left) * TILE_W, (bottom - top) * TILE_H)
        for y in range(top // CHUNK_TILES * CHUNK_TILES, bottom, CHUNK_TILES):
            for x in range(left // CHUNK_TILES * CHUNK_TILES, right, CHUNK_TILES):
                chunk = self._get_chunk(dungeon, x, y, width, height)
                self._animate(chunk)

                visible = visible_pixels.clip(chunk.pixels)
                position = visible.x - cam_x, visible.y - cam_y
                area = visible.move(-chunk.pixels.x, -chunk.pixels.y)
                diffuse.blit(chunk.diffuse, position, area)
                normals.blit(chunk.normals, position, area)
                trees.extend(tree for tree in chunk.trees if left <= tree[0] < right and top <= tree[1] < bottom)

        for (x, y), door in dungeon.doors.items():
            if left <= x < right and top <= y < bottom:
                self._draw_door(door, diffuse, normals, (x * TILE_W - cam_x, y * TILE_H - cam_y))
        return trees
