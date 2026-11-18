import random
import unittest

import numpy as np
import pygame

from elenor.config import CANVAS_H, VIEW_H, VIEW_W
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

    def test_furniture_casts_a_surface_shadow_and_updates_when_removed(self):
        dungeon = Dungeon()
        dungeon.grid = [[0] * 12 for _ in range(12)]
        dungeon.doors.clear()
        dungeon.thickets.clear()
        dungeon.solid_props = {(5, 5)}
        renderer = LightOcclusion()
        renderer.update(dungeon)
        x = np.array([[111.]])
        y = np.array([[88., 103.]])
        args = (60 - x, 88 - y, x, y, 60, 88, 130, (60, 88))
        visibility = renderer.surface_visibility(*args)
        self.assertLess(visibility[0, 0], .05)
        self.assertGreater(visibility[0, 1], .85)
        dungeon.solid_props.clear()
        renderer.update(dungeon)
        self.assertGreater(renderer.surface_visibility(*args)[0, 0], .85)

    def test_penumbra_keeps_a_lit_core_and_softens_the_shadow_boundary(self):
        stops = np.full(720, 150, dtype=np.float32)
        stops[:360] = 15
        angles = np.array([350.0, 359.0, 360.0, 370.0], dtype=np.float32)
        transmission = LightOcclusion().penumbra(stops, angles, np.full_like(angles, 46.0))
        self.assertEqual(transmission[0], 0)
        self.assertEqual(transmission[-1], 1)
        self.assertTrue(np.all(np.diff(transmission) > 0))
