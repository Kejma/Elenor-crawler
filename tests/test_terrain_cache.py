import unittest

import pygame

from elenor.config import SHALLOW_WATER, TILE_H, TILE_W
from elenor.rendering.terrain import CHUNK_TILES, DIFFUSE_CLEAR, NORMAL_CLEAR, TerrainCache
from elenor.world.dungeon import Door, Dungeon


class TerrainCacheTests(unittest.TestCase):
    @staticmethod
    def pair(color, normal_color=NORMAL_CLEAR):
        diffuse = pygame.Surface((TILE_W, TILE_H))
        diffuse.fill(color)
        normal = pygame.Surface(diffuse.get_size())
        normal.fill(normal_color)
        return diffuse, normal

    def setUp(self):
        self.dungeon = Dungeon()
        self.dungeon.grid = [[0] * (CHUNK_TILES * 3) for _ in range(2)]
        self.dungeon.overlays.clear()
        self.dungeon.moss_tiles.clear()
        self.dungeon.carpets.clear()
        self.dungeon.doors.clear()
        self.water = [self.pair((20, 80, 160)), self.pair((20, 95, 170), (128, 140, 254))]
        self.assets = {
            "floor_0": self.pair((60, 50, 40)),
            "moss_single": self.pair((40, 110, 60)),
            "moss_nw": self.pair((50, 140, 60)),
            "moss_ne": self.pair((50, 100, 60)),
            "floor_lake_shallow": self.water[0],
            "door_closed": self.pair((140, 80, 25)),
            "door_open": self.pair((100, 45, 20)),
        }
        self.cache = TerrainCache(self.assets, {"floor_lake_shallow": {"frames": self.water}}, {})
        self.diffuse = pygame.Surface((self.dungeon.width * TILE_W, TILE_H * 2))
        self.normals = self.diffuse.copy()

    def draw(self):
        self.diffuse.fill(DIFFUSE_CLEAR)
        self.normals.fill(NORMAL_CLEAR)
        self.cache.draw(self.dungeon, 0, 0, self.dungeon.width, self.dungeon.height, 0, 0,
                        self.diffuse, self.normals)

    def test_warm_bakes_all_chunks_before_the_camera_uses_them(self):
        self.cache.warm(self.dungeon)
        warm_chunks = dict(self.cache.chunks)
        self.assertEqual(len(warm_chunks), 3)
        self.draw()
        self.cache.warm(self.dungeon)
        for key, chunk in warm_chunks.items():
            self.assertIs(chunk, self.cache.chunks[key])

    def test_local_edit_rebakes_both_sides_of_an_autotile_boundary(self):
        self.dungeon.moss_tiles.add((CHUNK_TILES - 1, 0))
        self.draw()
        keys = [(self.dungeon, x * CHUNK_TILES, 0) for x in range(3)]
        first, second, third = (self.cache.chunks[key] for key in keys)
        x = (CHUNK_TILES - 1) * TILE_W
        self.assertEqual(self.diffuse.get_at((x, 0))[:3], (40, 110, 60))

        self.dungeon.moss_tiles.add((CHUNK_TILES, 0))
        self.dungeon.invalidate_terrain((CHUNK_TILES, 0, 1, 1))
        self.draw()
        self.assertEqual(self.diffuse.get_at((x, 0))[:3], (50, 140, 60))
        self.assertIsNot(first, self.cache.chunks[keys[0]])
        self.assertIsNot(second, self.cache.chunks[keys[1]])
        self.assertIs(third, self.cache.chunks[keys[2]])

    def test_water_and_doors_change_without_rebuilding_the_chunk(self):
        door = self.dungeon.doors[(1, 0)] = Door(1, 0)
        self.dungeon.grid[0][0] = SHALLOW_WATER
        self.draw()
        key = self.dungeon, 0, 0
        chunk = self.cache.chunks[key]
        self.assertEqual(self.diffuse.get_at((0, 0))[:3], (20, 80, 160))
        self.assertEqual(self.diffuse.get_at((TILE_W, 0))[:3], (140, 80, 25))

        self.assets["floor_lake_shallow"] = self.water[1]
        door.is_open = True
        self.dungeon.invalidate_light_cache()
        self.draw()
        self.assertIs(chunk, self.cache.chunks[key])
        self.assertEqual(self.diffuse.get_at((0, 0))[:3], (20, 95, 170))
        self.assertEqual(self.diffuse.get_at((TILE_W, 0))[:3], (100, 45, 20))
        self.assertEqual(self.normals.get_at((0, 0))[:3], (128, 140, 254))

    def test_oversized_custom_overlay_keeps_original_paint_order(self):
        size = (TILE_W + 3, TILE_H)
        color = pygame.Surface(size)
        color.fill((150, 40, 50))
        normal = pygame.Surface(size)
        normal.fill((145, 128, 240))
        self.assets["ov_custom"] = color, normal
        self.cache = TerrainCache(self.assets, {}, {})
        self.dungeon.overlays[(0, 0)] = "ov_custom"
        self.draw()

        # The next tile is painted later and covers the overhang.
        self.assertEqual(self.diffuse.get_at((TILE_W - 1, 0))[:3], (150, 40, 50))
        self.assertEqual(self.diffuse.get_at((TILE_W, 0))[:3], (60, 50, 40))
        self.assertFalse(self.cache.chunks)
