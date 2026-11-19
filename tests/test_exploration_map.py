import unittest
from unittest.mock import patch

import numpy as np
import pygame

from elenor.config import TILE_H, TILE_W, VIEW_H, VIEW_W
from elenor.entities import Interactable
from elenor.rendering.visibility import CanopyVisibility, canopy_visibility, visible_lit_tiles
from elenor.ui.exploration_map import INK, TERRAIN, chart_surface, discovered_landmarks
from elenor.world.dungeon import Door, Dungeon
from elenor.world.exploration import remember_tiles


class ExplorationMapTests(unittest.TestCase):
    def test_exposed_canopies_stay_visible_along_a_straight_corridor(self):
        dungeon = Dungeon()
        dungeon._carve_rect(pygame.Rect(4, 7, 26, 6), 10)
        for row in (8, 10):
            for x in range(5, 29):
                dungeon.grid[row][x] = 21
                dungeon.thickets.add((x, row))

        for player_x in (9.1, 9.35, 9.6, 9.85, 10.1, 10.35):
            for row in (8, 10):
                for x in range(7, 16):
                    self.assertEqual(canopy_visibility(dungeon, player_x, 9.5, x, row), 1.0,
                                     (player_x, x, row))

    def test_wall_and_other_trees_can_occlude_a_crown(self):
        dungeon = Dungeon()
        dungeon._carve_rect(pygame.Rect(5, 5, 15, 10), 10)
        for x in range(5, 20):
            dungeon.grid[9][x] = 1
        self.assertEqual(canopy_visibility(dungeon, 9.5, 7.5, 9, 11), 0.0)
        for x in range(5, 20):
            dungeon.grid[9][x] = 21
            dungeon.thickets.add((x, 9))
        self.assertEqual(canopy_visibility(dungeon, 9.5, 7.5, 9, 11), 0.0)
        self.assertEqual(canopy_visibility(dungeon, 9.5, 7.5, 9, 9), 1.0)

    def test_canopy_cache_refreshes_when_viewer_moves_or_geometry_changes(self):
        dungeon = Dungeon()
        cache = CanopyVisibility()
        tree = (9, 11)
        with patch("elenor.rendering.visibility.canopy_visibility", side_effect=(1.0, .32, 0.0)) as trace:
            cache.begin_frame(dungeon.grid, 1.0)
            cache.set_view(dungeon, 9.5, 7.5)
            self.assertEqual(cache.target(tree), 1.0)
            cache.begin_frame(dungeon.grid, 1.1)
            cache.set_view(dungeon, 9.5, 7.5)
            self.assertEqual(cache.target(tree), 1.0)
            self.assertEqual(trace.call_count, 1)

            cache.set_view(dungeon, 9.6, 7.5)
            self.assertEqual(cache.target(tree), .32)
            dungeon.invalidate_light_cache()
            cache.set_view(dungeon, 9.6, 7.5)
            self.assertEqual(cache.target(tree), 0.0)

    def test_cached_canopy_obstacles_match_scalar_rays_when_a_door_opens(self):
        dungeon = Dungeon()
        dungeon.grid = [[0] * 22 for _ in range(14)]
        dungeon.thickets = {(14, 6), (15, 6), (14, 7), (15, 7)}
        door = Door(10, 5)
        dungeon.doors = {(10, 5): door}
        dungeon.invalidate_light_cache()

        cache = CanopyVisibility()
        for is_open in (False, True):
            door.is_open = is_open
            for x, y in ((7.5, 5.5), (8.33, 5.23), (9.2, 3.8), (13.2, 6.5)):
                cache.set_view(dungeon, x, y)
                for tree in dungeon.thickets:
                    self.assertEqual(cache.target(tree), canopy_visibility(dungeon, x, y, *tree))

    def test_fov_cache_refreshes_on_camera_door_and_geometry_changes(self):
        dungeon = Dungeon()
        dungeon.grid = [[1] * 15 for _ in range(12)]
        dungeon.thickets.clear()
        dungeon._carve_rect(pygame.Rect(1, 5, 12, 1), 4)
        door = Door(5, 5)
        dungeon.doors = {(5, 5): door}
        dungeon.invalidate_light_cache()
        viewer = (2.5 * TILE_W, 5.5 * TILE_H)

        closed = dungeon.compute_nox_fov(*viewer, 0, 0)
        self.assertIs(closed, dungeon.compute_nox_fov(*viewer, 0, 0))
        self.assertFalse(closed[0].flags.writeable)
        self.assertNotIn((8, 5), closed[2])

        door.is_open = True
        opened = dungeon.compute_nox_fov(*viewer, 0, 0)
        self.assertIn((8, 5), opened[2])
        before_pan = opened[0].copy()
        with patch.object(dungeon, "_trace_floor_rays", wraps=dungeon._trace_floor_rays) as trace:
            panned = dungeon.compute_nox_fov(*viewer, TILE_W, 0)
            trace.assert_not_called()
        self.assertFalse(np.array_equal(before_pan, panned[0]))
        self.assertEqual(opened[2], panned[2])

        dungeon.grid[5][5] = 1
        dungeon.invalidate_light_cache()
        self.assertNotIn((8, 5), dungeon.compute_nox_fov(*viewer, TILE_W, 0)[2])

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
        self.assertEqual(observed, {seen})

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

    def test_minimap_uses_local_memory_and_dynamic_landmarks_require_sight(self):
        dungeon = Dungeon()
        stairs = Interactable(8, 20, "stairs")
        dungeon.grid[20][8] = 3
        dungeon.grid[20][9] = 4
        remember_tiles(dungeon, {(8, 20)})
        remember_tiles(dungeon, {(9, 20)}, [stairs])
        self.assertEqual(list(discovered_landmarks(dungeon)), [])

        remember_tiles(dungeon, {(8, 20)}, [stairs])
        self.assertEqual(list(discovered_landmarks(dungeon)), [((8, 20), "down")])
        chart = chart_surface(dungeon, pygame.Rect(7, 20, 3, 2))
        self.assertEqual(chart.get_size(), (3, 2))
        self.assertEqual(chart.get_at((1, 0))[:3], TERRAIN["grass"])
        self.assertEqual(chart.get_at((2, 0))[:3], TERRAIN["wood"])
        self.assertEqual(chart.get_at((0, 0))[:3], INK)
        self.assertEqual(chart.get_at((1, 1))[:3], INK)

        dungeon.generate(floor_num=2)
        self.assertFalse(dungeon.explored_tiles)
        self.assertEqual(list(discovered_landmarks(dungeon)), [])
