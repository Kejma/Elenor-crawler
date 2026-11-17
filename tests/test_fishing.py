import unittest

from elenor.minigames.fishing import FINISHED, POOLS, PROFILES, FishingCast, cast_route
from elenor.missions.jungle import (
    DEEP_WATER,
    SHALLOW_WATER,
    PIER,
    SPOTS,
    shoreline,
)
from elenor.rendering.fishing import FISH_CATALOG_SPECS
from elenor.world.dungeon import Dungeon
from elenor.world.merchant import reachable_tiles


def make_cast(profile):
    return FishingCast("eddy", (1, 1), (1, 4), "fish_bitterling", PROFILES[profile], 2)


def advance(cast, seconds):
    for _ in range(round(seconds * 60)):
        cast.update(1 / 60)


class FishingTests(unittest.TestCase):
    def test_brief_taps_are_not_the_hook_window(self):
        cast = make_cast("shoal")
        advance(cast, 1.38)
        self.assertGreater(cast.bob, 0)
        cast.press()
        self.assertEqual(cast.phase, "early")

        cast = make_cast("shoal")
        advance(cast, 2.5)
        self.assertEqual(cast.phase, "bite")
        advance(cast, 1.4)
        self.assertEqual(cast.phase, "missed")

    def test_modulating_tension_works_for_every_profile(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                cast = make_cast(profile)
                advance(cast, 2.5)
                cast.press()
                for _ in range(20 * 60 + 1):
                    if cast.phase in FINISHED:
                        break
                    cast.reeling = not cast.surging and cast.tension < 0.69
                    cast.update(1 / 60)
                self.assertEqual(cast.phase, "caught")

    def test_reeling_through_a_piranha_surge_snaps_the_line(self):
        cast = make_cast("dart")
        advance(cast, 2.5)
        cast.press()
        cast.press()
        advance(cast, 3)
        self.assertEqual(cast.phase, "snapped")

    def test_all_authored_species_have_one_spot(self):
        ids = [
            f"fish_{name}"
            for groups in POOLS.values()
            for _, names in groups
            for name in names.split()
        ]
        self.assertCountEqual(ids, FISH_CATALOG_SPECS.keys())

    def test_shallow_and_deep_casts_stay_in_water_until_landed(self):
        dungeon = Dungeon()
        dungeon.generate(campaign="jungle")
        reachable = reachable_tiles(dungeon, dungeon.start_pos)
        for x, spot in SPOTS:
            y = shoreline(x)
            self.assertIn((x, y + 1), reachable)
            self.assertEqual(dungeon.grid[y + 1][x], PIER)
            for depth, tile in ((2.5, SHALLOW_WATER), (5.5, DEEP_WATER)):
                origin, aim = (x + 0.5, y + 1.5), (x + 0.5, y + depth)
                self.assertEqual(dungeon.grid[int(aim[1])][int(aim[0])], tile)
                self.assertIsNone(cast_route(dungeon, (x + 0.5, y + 0.5), aim))
                self.assertIsNone(cast_route(dungeon, origin, (x + 0.5, y - 0.5)))
                selected, end = cast_route(dungeon, origin, aim)
                self.assertEqual(selected, spot)
                cast = make_cast("shoal")
                cast.phase = "reel"
                cast.target, cast.retrieve_to = aim, end
                for step in range(11):
                    cast.progress = step / 10
                    fx, fy = cast.float_position
                    self.assertIn(
                        dungeon.grid[int(fy)][int(fx)], (SHALLOW_WATER, DEEP_WATER)
                    )
        self.assertTrue(dungeon.is_blocking_move(30, 28))

    def test_daylight_keeps_range_and_canopy_shadows(self):
        dungeon = Dungeon()
        dungeon.generate(campaign="jungle")
        self.assertLess(dungeon.sunlight.min(), 0.30)
        self.assertEqual(dungeon.sunlight.max(), 1)
        # Water gives a clear view across the river. The outer view still fades
        # while the same world pixel remains geometrically visible.
        wx, wy = 500, 320
        cam_x, cam_y = wx - 240, wy - 100
        raw, _, _ = dungeon.compute_nox_fov(wx, wy, cam_x, cam_y)
        self.assertEqual(raw[420, 100], 1)
        mask, visible, _ = dungeon.compute_nox_fov(
            wx, wy, cam_x, cam_y, daylight_sight=200
        )
        self.assertEqual(mask[240, 100], 1)
        self.assertTrue(0 < mask[420, 100] < 0.25)
        self.assertEqual(mask[450, 100], 0)
        self.assertNotIn(((450 + cam_x) // 16, wy // 16), visible)
        dungeon.generate()
        self.assertIsNone(dungeon.sunlight)
        self.assertFalse(dungeon.fishing_edges)
        self.assertEqual(dungeon.ambient_light, (0, 0, 0))
