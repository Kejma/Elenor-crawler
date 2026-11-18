import unittest
import random

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
from elenor.config import DEEP_WATER, PIER, SHALLOW_WATER
from elenor.missions.jungle import populate_jungle_floor
from elenor.rendering.fishing import FISH_CATALOG_SPECS
from elenor.world.dungeon import Dungeon
from elenor.puzzles.mirrors import reachable_floor_tiles


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
        for seed in range(12):
            random.seed(seed)
            dungeon = Dungeon()
            dungeon.generate(campaign="jungle")
            reachable = reachable_floor_tiles(dungeon, dungeon.start_pos)
            for (x, y), spot in dungeon.fishing_edges.items():
                self.assertIn((x, y), reachable)
                direct = 1 if dungeon.grid[y - 1][x] == PIER else -1
                origin = (x + 0.5, y + 0.5)
                for distance, tile in ((1, SHALLOW_WATER), (3, DEEP_WATER)):
                    aim = (origin[0], origin[1] + distance * direct)
                    self.assertEqual(dungeon.grid[int(aim[1])][x], tile)
                    self.assertIsNone(
                        cast_route(dungeon, (origin[0], origin[1] - direct), aim)
                    )
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

    def test_player_can_wade_but_cannot_enter_deep_water(self):
        dungeon = Dungeon()
        dungeon.generate(campaign="jungle")
        game = HeadlessGame(dungeon)
        x, y = next(iter(dungeon.fishing_edges))
        dy = 1 if dungeon.grid[y - 1][x] == PIER else -1
        game.player.x, game.player.y = x + 0.5, y + 0.5
        for _ in range(80):
            game.player.move_realtime(0, dy, 0.05, dungeon)
        self.assertNotEqual(int(game.player.y), y)
        self.assertEqual(dungeon.grid[int(game.player.y)][x], SHALLOW_WATER)
        deep_y = int(game.player.y) + dy
        self.assertTrue(dungeon.is_blocking_move(x, deep_y))
        self.assertFalse(dungeon.is_blocking_sight(x, deep_y))

    def test_jungle_landmarks_and_optional_vault(self):
        for seed in range(24):
            with self.subTest(seed=seed):
                random.seed(seed)
                dungeon = Dungeon(puzzle_chance=seed % 2)
                dungeon.generate(floor_num=seed + 1, campaign="jungle")
                game = HeadlessGame(dungeon)
                game.campaign = "jungle"
                game._populate_floor(seed + 1)
                seen = reachable_floor_tiles(dungeon, dungeon.start_pos)
                self.assertTrue(dungeon.passages.keys() <= seen)
                self.assertTrue(
                    {"forward", "temple", "cave"} <= set(dungeon.passages.values())
                )
                self.assertTrue(dungeon.fishing_edges.keys() <= seen)
                self.assertFalse(game.mobs)
                self.assertEqual(len(game.mirror_puzzles), seed % 2)
                if game.mirror_puzzles:
                    info = dungeon.mirror_puzzle_info
                    self.assertIn(info["entry_door"], seen)
                    self.assertNotIn(info["sealed_rect"].center, seen)
                    self.assertFalse(game.mirror_puzzles[0].ambush_enabled)
                    dungeon.doors[info["gate_door"]].is_open = True
                    self.assertIn(
                        info["sealed_rect"].center,
                        reachable_floor_tiles(dungeon, dungeon.start_pos),
                    )

    def test_return_to_the_same_surface_and_interiors(self):
        dungeon = Dungeon(puzzle_chance=0)
        dungeon.generate(campaign="jungle")
        game = HeadlessGame(dungeon)
        game.campaign, game.jungle_locations = "jungle", {}
        game._populate_floor(1)
        self.assertEqual((dungeon.width, dungeon.height), (198, 126))
        self.assertFalse(
            any(tile in (45, 46, 47, 56, 57) for row in dungeon.grid for tile in row)
        )
        for action in ("temple", "cave"):
            game.travel_jungle(action)
            inside = game.dungeon
            self.assertFalse(inside.fishing_edges)
            self.assertEqual(set(inside.passages.values()), {"up"})
            treasure = next(obj for obj in game.objects if obj.kind == "chest")
            treasure.used = True
            game.travel_jungle("up")
            self.assertIs(game.dungeon, dungeon)
            self.assertEqual(
                dungeon.passages[int(game.player.x), int(game.player.y)], action
            )
            game.travel_jungle(action)
            self.assertIs(game.dungeon, inside)
            self.assertIn(treasure, game.objects)
            self.assertTrue(treasure.used)
            game.travel_jungle("up")
        game.travel_jungle("forward")
        self.assertEqual(game.dungeon.floor_num, 2)
        game.travel_jungle("back")
        self.assertIs(game.dungeon, dungeon)

    def test_touching_jungle_trees_occlude_the_view(self):
        random.seed(12)
        d = Dungeon()
        d.generate(campaign="jungle")
        trees = {21, 22, 56, 57}
        self.assertTrue(d.thickets)
        for x, y in d.thickets:
            self.assertTrue(d.is_blocking_sight(x, y))
        # Four consecutive tiles: viewer, two trunks, destination.
        for y in range(1, d.height - 1):
            for x in range(1, d.width - 4):
                if (
                    (x + 1, y) in d.thickets
                    and (x + 2, y) in d.thickets
                    and not any(d.is_blocking_move(tx, y) for tx in (x, x + 3))
                ):
                    self.assertFalse(
                        d.has_line_of_sight(x + 0.5, y + 0.5, x + 3.5, y + 0.5, 5)
                    )
                    _, _, visible = d.compute_nox_fov(
                        (x + 0.5) * 16, (y + 0.5) * 16, x * 16 - 100, y * 16 - 80
                    )
                    self.assertNotIn((x + 3, y), visible)
                    break
            else:
                continue
            break
        else:
            self.fail("Missing stand of trees")
        isolated = [
            (x, y)
            for y, row in enumerate(d.grid)
            for x, t in enumerate(row)
            if t in trees and (x, y) not in d.thickets
        ]
        self.assertTrue(isolated)
        self.assertFalse(d.is_blocking_sight(*isolated[0]))

    def test_clicking_scenery_leaves_it_in_place(self):
        dungeon = Dungeon()
        dungeon.generate(campaign="jungle")
        game = HeadlessGame(dungeon)
        populate_jungle_floor(game, Interactable)
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
