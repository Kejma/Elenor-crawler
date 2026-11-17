import unittest

from elenor.minigames.fishing import (
    FINISHED,
    POOLS,
    PROFILES,
    FishingCast,
    cast_route,
    press_fishing,
    update_fishing,
)
from test_mirror_puzzles import HeadlessGame, Interactable
from elenor.missions.jungle import (
    DEEP_WATER,
    SHALLOW_WATER,
    PIER,
    SPOTS,
    shoreline,
    populate_jungle_bank,
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

    def test_player_can_wade_but_cannot_enter_deep_water(self):
        dungeon = Dungeon()
        dungeon.generate(campaign="jungle")
        game = HeadlessGame(dungeon)
        x = SPOTS[0][0]
        boundary = shoreline(x) + 3
        game.player.x, game.player.y = x + 0.5, boundary - 0.6
        self.assertFalse(dungeon.is_blocking_move(x, boundary - 1))
        self.assertTrue(dungeon.is_blocking_move(x, boundary))
        self.assertFalse(dungeon.is_blocking_sight(x, boundary))
        for _ in range(20):
            game.player.move_realtime(0, 1, 0.05, dungeon)
        self.assertGreater(game.player.y, boundary - 0.6)
        self.assertLess(game.player.y, boundary)
        self.assertEqual(len(dungeon.braziers), len(SPOTS))

    def test_clicking_scenery_leaves_it_in_place(self):
        dungeon = Dungeon()
        dungeon.generate(campaign="jungle")
        game = HeadlessGame(dungeon)
        populate_jungle_bank(game, Interactable)
        game.inv_open = False
        for kind in (
            "prop_reeds_tall",
            "prop_wooden_rowboat",
            "prop_fishing_rod_stand",
        ):
            obj = next(obj for obj in game.objects if obj.kind == kind)
            game.player.x, game.player.y = obj.x + 0.5, obj.y - 0.5
            game.try_interact_or_melee(obj.x + 0.5, obj.y + 0.5, via_mouse=True)
            self.assertFalse(obj.used)

    def test_results_release_controls_and_use_the_thought_channel(self):
        game = HeadlessGame(Dungeon())
        game.fishing_catches = {}
        for result in ("early", "missed", "snapped", "escaped", "caught"):
            with self.subTest(result=result):
                cast = game.fishing_cast = make_cast("shoal")
                if result == "early":
                    cast.phase = "wait"
                    press_fishing(game)
                else:
                    cast.phase = "bite" if result == "missed" else "reel"
                    cast.elapsed = {"missed": 2, "escaped": 20}.get(result, 0)
                    cast.tension = 1.1 if result == "snapped" else 0.2
                    cast.progress = 1.0 if result == "caught" else 0.1
                    update_fishing(game, 0.01)
                self.assertIsNone(game.fishing_cast)
                (thought,) = game.set_thought.call_args.args
                self.assertEqual(game.set_thought.call_args.kwargs, {"important": True})
                self.assertEqual(
                    thought, game.loc["fishing"][result].format(fish="Горчак Стайный")
                )
        self.assertEqual(game.fishing_catches, {"fish_bitterling": 1})
