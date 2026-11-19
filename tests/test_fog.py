import random
import unittest
from unittest.mock import patch

import numpy as np
import pygame

from elenor.config import CANVAS_H, VIEW_H, VIEW_W
from elenor.entities.objects import Interactable
from elenor.rendering.fog import FogRenderer
from elenor.rendering.occlusion import LightOcclusion
from elenor.world.dungeon import Door, Dungeon
from elenor.world.run_seed import generation_random


class FogTests(unittest.TestCase):
    def test_rat_dungeon_uses_a_seeded_half_chance_for_one_or_two_rooms(self):
        counts = []
        dungeon = Dungeon(puzzle_profile="rats")
        for seed in range(96):
            with generation_random(seed):
                dungeon.generate(2 + seed % 5)
            zones = dungeon.fog_zones
            counts.append(len(zones))
            self.assertLessEqual(len(zones), 2)
            self.assertEqual(len({zone["bounds"] for zone in zones}), len(zones))
            for zone in zones:
                self.assertIn(pygame.Rect(zone["bounds"]), dungeon.rooms[1:])
        self.assertGreater(counts.count(0), 32)
        self.assertLess(counts.count(0), 64)
        self.assertIn(1, counts)
        self.assertIn(2, counts)

    def test_room_mist_roll_does_not_consume_gameplay_rng(self):
        dungeon = Dungeon(puzzle_profile="rats")
        with generation_random(226):
            dungeon.generate(3)
            state = random.getstate()
            dungeon._place_cellar_mist()
            self.assertEqual(random.getstate(), state)

    def test_light_through_grate_is_split_and_a_wooden_door_blocks_it(self):
        dungeon = Dungeon()
        dungeon.grid = [[0] * 10 for _ in range(10)]
        for x in range(10):
            dungeon.grid[4][x] = 1
        dungeon.grid[4][4] = 0
        door = dungeon.doors[(4, 4)] = Door(4, 4, locked_by_lever=True)
        renderer = LightOcclusion()

        renderer.update(dungeon)
        grate = renderer.distances(72, 49, 115)
        self.assertTrue((grate[163:196] < 35).any())
        self.assertTrue((grate[163:196] > 50).any())
        door.locked = False
        renderer.update(dungeon)
        solid = renderer.distances(72, 49, 115)
        self.assertTrue((solid[163:196] < 45).all())

        door.is_open = True
        renderer.update(dungeon)
        opened = renderer.distances(72, 49, 115)
        self.assertGreater((opened[163:196] > 50).sum(), (grate[163:196] > 50).sum())

    def test_fog_composite_respects_view_and_opaque_wall_pixels(self):
        game_view = pygame.Surface((VIEW_W, CANVAS_H))
        dungeon = Dungeon()
        dungeon.grid = [[0] * 12 for _ in range(12)]
        dungeon.grid[4][4] = 1
        dungeon.doors.clear()
        dungeon.thickets.clear()
        mask = np.zeros((VIEW_W, CANVAS_H), dtype=np.float32)
        mask[:95, :VIEW_H] = 1
        depth = np.full((VIEW_W, CANVAS_H), -9999.0, dtype=np.float32)
        cloud = dict(wx=4.5, wy=4.5, radius=4, kind="mist", color=(.7, .8, .9), density=.8)
        light = dict(pos=(63, 84, 24), color=(1.2, .9, .7), radius=90)
        FogRenderer().render(game_view, dungeon, [cloud], [light], mask, depth, 0, 0, 3.0)
        self.assertGreater(sum(game_view.get_at((59, 76))[:3]), 0)
        self.assertEqual(game_view.get_at((72, 72))[:3], (0, 0, 0))
        self.assertEqual(game_view.get_at((97, 72))[:3], (0, 0, 0))
        self.assertEqual(game_view.get_at((59, VIEW_H))[:3], (0, 0, 0))

    def test_dry_room_never_gets_a_fog_overlay(self):
        game_view = pygame.Surface((VIEW_W, CANVAS_H))
        dungeon = Dungeon()
        dungeon.grid = [[0] * 12 for _ in range(12)]
        for y in range(12):
            dungeon.grid[y][5] = 1
        dungeon.doors.clear()
        dungeon.thickets.clear()
        mask = np.ones((VIEW_W, CANVAS_H), dtype=np.float32)
        depth = np.full_like(mask, -9999.0)
        light = dict(pos=(63, 80, 16), color=(1.0, .5, .2), radius=80)
        FogRenderer().render(game_view, dungeon, [], [light], mask, depth, 0, 0, 0)
        self.assertEqual(game_view.get_at((66, 80))[:3], (0, 0, 0))

    def test_low_furniture_partly_shades_the_floor_and_the_shadow_ends_nearby(self):
        dungeon = Dungeon()
        dungeon.grid = [[0] * 12 for _ in range(12)]
        dungeon.doors.clear()
        dungeon.thickets.clear()
        dungeon.solid_props.clear()
        renderer = LightOcclusion()
        bench = Interactable(5, 5, "chair_bench")
        renderer.update(dungeon, [bench])
        x = np.array([[94.], [122.]])
        y = np.array([[88.]])
        query = (52 - x, 88 - y, x, y, 52, 88, 130, (52, 88))
        visibility = renderer.surface_visibility(*query)
        self.assertGreater(visibility[0, 0], .82)
        self.assertLess(visibility[0, 0], .97)
        with patch("elenor.rendering.occlusion.PROP_SHADOW_STRENGTH", 1):
            original = renderer.surface_visibility(*query)
        np.testing.assert_allclose(1 - visibility, (1 - original) * 4 / 3)
        np.testing.assert_allclose(renderer.surface_visibility(*query, ground=False), 1)
        self.assertAlmostEqual(visibility[1, 0], 1)
        overhead = renderer.surface_visibility(*query, light_z=60.0)
        self.assertGreater(overhead[0, 0], visibility[0, 0])

        renderer.update(dungeon, [Interactable(5, 5, "bookshelf")])
        cabinet = renderer.surface_visibility(*query)
        self.assertLess(cabinet[0, 0], visibility[0, 0])
        self.assertGreater(cabinet[0, 0], .25)

        bench.used = True
        renderer.update(dungeon, [bench])
        self.assertTrue(np.allclose(renderer.surface_visibility(*query), 1))

    def test_continuous_wall_face_has_no_tile_seam_shadows(self):
        dungeon = Dungeon()
        dungeon.grid = [[0] * 15 for _ in range(12)]
        for col in range(2, 13):
            dungeon.grid[4][col] = 1
        dungeon.doors.clear()
        dungeon.thickets.clear()
        dungeon.solid_props.clear()
        renderer = LightOcclusion()
        renderer.update(dungeon)
        x = np.arange(54.0, 166.0)[:, None]
        y = np.array([[67., 72., 77.]])
        light = 178, 120
        query = (light[0] - x, light[1] - y, x, y, *light, 170)
        front = renderer.surface_visibility(*query, light)
        self.assertGreater(front.min(), .83)
        back = renderer.surface_visibility(*query, (120, 45))
        self.assertLess(back[:, 0].max(), .05)

    def test_door_receives_light_on_the_room_side_without_lighting_the_floor_beyond(self):
        dungeon = Dungeon()
        dungeon.grid = [[0] * 12 for _ in range(12)]
        dungeon.doors.clear()
        dungeon.thickets.clear()
        dungeon.solid_props.clear()
        dungeon.doors[(4, 4)] = Door(4, 4)
        occlusion = LightOcclusion()
        occlusion.update(dungeon)
        x, y = np.array([[72.]]), np.array([[58., 73.]])
        result = occlusion.surface_visibility(72 - x, 106 - y, x, y, 72, 106, 120, (72, 110))
        self.assertLess(result[0, 0], .05)
        self.assertGreater(result[0, 1], .9)
        back = occlusion.surface_visibility(72 - x, 106 - y, x, y, 72, 106, 120, (72, 50))
        self.assertEqual(back[0, 1], 0)

    def test_corner_face_is_selected_from_the_viewer_side(self):
        dungeon = Dungeon()
        dungeon.grid = [[0] * 12 for _ in range(12)]
        dungeon.doors.clear()
        dungeon.thickets.clear()
        dungeon.solid_props.clear()
        dungeon.grid[4][5] = dungeon.grid[3][5] = 1
        occlusion = LightOcclusion()
        occlusion.update(dungeon)
        x, y = np.array([[86.]]), np.array([[71.]])
        viewer = (49, 82)
        south = occlusion.surface_visibility(92 - x, 105 - y, x, y, 92, 105, 110, viewer)
        west = occlusion.surface_visibility(54 - x, 74 - y, x, y, 54, 74, 110, viewer)
        self.assertEqual(south[0, 0], 0)
        self.assertGreater(west[0, 0], .9)

    def test_penumbra_keeps_a_lit_core_and_softens_the_shadow_boundary(self):
        stops = np.full(720, 150, dtype=np.float32)
        stops[:360] = 15
        angles = np.array([350.0, 359.0, 360.0, 370.0], dtype=np.float32)
        transmission = LightOcclusion().penumbra(stops, angles, np.full_like(angles, 46.0))
        self.assertEqual(transmission[0], 0)
        self.assertEqual(transmission[-1], 1)
        self.assertTrue(np.all(np.diff(transmission) > 0))
