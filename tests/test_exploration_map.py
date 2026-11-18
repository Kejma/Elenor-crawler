import unittest

import numpy as np
import pygame

from elenor.config import TILE_H, TILE_W, VIEW_H, VIEW_W
from elenor.rendering.visibility import visible_lit_tiles
from elenor.ui.exploration_map import INK, TERRAIN, chart_surface
from elenor.world.dungeon import Door, Dungeon
from elenor.world.exploration import remember_tiles


class ExplorationMapTests(unittest.TestCase):
    def test_survey_requires_both_light_and_line_of_sight(self):
        scene = pygame.Surface((VIEW_W, VIEW_H))
        scene.fill((0, 0, 0))
        mask = np.zeros((VIEW_W, VIEW_H), dtype=np.float32)
        cam_x, cam_y = 2 * TILE_W, TILE_H
        seen, dark, occluded, outside_fov = ((3, 2), (4, 2), (5, 2), (6, 2))

        for x, y in (seen, occluded, outside_fov):
            scene.fill(
                (50, 50, 50), (x * TILE_W - cam_x, y * TILE_H - cam_y, TILE_W, TILE_H)
            )
        for x, y in (seen, dark, outside_fov):
            sx, sy = x * TILE_W - cam_x, y * TILE_H - cam_y
            mask[sx : sx + TILE_W, sy : sy + TILE_H] = 1

        observed = visible_lit_tiles(
            scene, mask, {seen, dark, occluded, (0, 0)}, cam_x, cam_y
        )
        self.assertEqual(observed, [seen])

    def test_chart_uses_last_seen_door_and_never_reads_undiscovered_ground(self):
        dungeon = Dungeon()
        door = Door(5, 5)
        dungeon.grid[5][5] = 13
        dungeon.doors[(5, 5)] = door
        remember_tiles(dungeon, [(5, 5)])
        door.is_open = True
        chart = chart_surface(dungeon)
        self.assertEqual(chart.get_at((5, 5))[:3], TERRAIN["door"])
        self.assertEqual(chart.get_at((6, 5))[:3], INK)

        remember_tiles(dungeon, [(5, 5)])
        self.assertEqual(chart_surface(dungeon).get_at((5, 5))[:3], TERRAIN["wood"])
        dungeon.generate()
        self.assertFalse(dungeon.explored_tiles)
