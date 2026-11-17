import math
import unittest

from elenor.minigames.fishing import FINISHED, POOLS, PROFILES, FishingCast
from elenor.missions.jungle import (
    DEEP_WATER,
    SHALLOW_WATER,
    SPOTS,
    populate_jungle_bank,
)
from elenor.rendering.fishing import FISH_CATALOG_SPECS
from elenor.world.dungeon import Dungeon
from elenor.world.merchant import reachable_tiles

from test_mirror_puzzles import HeadlessGame, Interactable


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

    def test_three_stands_accessible_from_spawn_and_cast_into_water(self):
        dungeon = Dungeon()
        dungeon.generate(campaign="jungle")
        game = HeadlessGame(dungeon)
        populate_jungle_bank(game, Interactable)
        reachable = reachable_tiles(dungeon, dungeon.start_pos)
        stands = [obj for obj in game.objects if hasattr(obj, "fishing_spot")]
        self.assertCountEqual(
            [obj.fishing_spot for obj in stands], [spot for _, spot in SPOTS]
        )
        for stand in stands:
            self.assertIn((stand.x, stand.y), reachable)
            wx, wy = stand.fishing_target
            self.assertIn(dungeon.grid[int(wy)][int(wx)], (SHALLOW_WATER, DEEP_WATER))
            self.assertLess(
                math.dist((stand.x + 0.5, stand.y + 0.5), stand.fishing_target), 4
            )
        self.assertTrue(dungeon.is_blocking_move(30, 28))
        dungeon.generate()
        self.assertEqual(dungeon.ambient_light, (0, 0, 0))
