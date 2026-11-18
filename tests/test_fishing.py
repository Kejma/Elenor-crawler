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
from elenor.config import DEEP_WATER, FALLEN_LOG, SHALLOW_WATER
from elenor.missions.jungle import populate_jungle_floor
from elenor.rendering.fishing import FISH_CATALOG_SPECS
from elenor.world.dungeon import Dungeon
from elenor.world.jungle_sites import CARDINAL, Plan, offset, village
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

    def _cast_direction(self, dungeon, point):
        for direction in CARDINAL:
            x, y = offset(point, direction)
            dx, dy = offset(point, direction, 3)
            if (
                dungeon.grid[y][x] == SHALLOW_WATER
                and dungeon.grid[dy][dx] == DEEP_WATER
            ):
                return direction
        self.fail(f"No shallow-to-deep approach at {point}")

    def test_shallow_and_deep_casts_stay_in_water_until_landed(self):
        for seed in range(12):
            random.seed(seed)
            dungeon = Dungeon()
            dungeon.generate(campaign="jungle")
            reachable = reachable_floor_tiles(dungeon, dungeon.start_pos)
            for (x, y), spot in dungeon.fishing_edges.items():
                self.assertIn((x, y), reachable)
                dx, dy = self._cast_direction(dungeon, (x, y))
                origin = (x + 0.5, y + 0.5)
                for distance, tile in ((1, SHALLOW_WATER), (3, DEEP_WATER)):
                    aim = (origin[0] + distance * dx, origin[1] + distance * dy)
                    self.assertEqual(dungeon.grid[int(aim[1])][int(aim[0])], tile)
                    self.assertIsNone(
                        cast_route(dungeon, (origin[0] + dx, origin[1] + dy), aim)
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
        dx, dy = self._cast_direction(dungeon, (x, y))
        game.player.x, game.player.y = x + 0.5, y + 0.5
        for _ in range(80):
            game.player.move_realtime(dx, dy, 0.05, dungeon)
        wx, wy = int(game.player.x), int(game.player.y)
        self.assertNotEqual((wx, wy), (x, y))
        self.assertEqual(dungeon.grid[wy][wx], SHALLOW_WATER)
        deep_x, deep_y = wx + dx, wy + dy
        self.assertTrue(dungeon.is_blocking_move(deep_x, deep_y))
        self.assertFalse(dungeon.is_blocking_sight(deep_x, deep_y))

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
        self.assertEqual((dungeon.width, dungeon.height), (132, 84))
        self.assertFalse(
            any(tile in (45, 46, 47, 56, 57) for row in dungeon.grid for tile in row)
        )
        dungeon.explored_tiles[dungeon.start_pos] = "trail"
        for action in ("temple", "cave"):
            game.travel_jungle(action)
            inside = game.dungeon
            self.assertFalse(inside.explored_tiles)
            inside.explored_tiles[inside.start_pos] = "floor"
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
            self.assertEqual(inside.explored_tiles, {inside.start_pos: "floor"})
            self.assertIn(treasure, game.objects)
            self.assertTrue(treasure.used)
            game.travel_jungle("up")
        game.travel_jungle("forward")
        self.assertEqual(game.dungeon.floor_num, 2)
        game.travel_jungle("back")
        self.assertIs(game.dungeon, dungeon)
        self.assertEqual(dungeon.explored_tiles, {dungeon.start_pos: "trail"})

    def test_underground_vault_does_not_gate_the_return_or_main_treasure(self):
        for interior in ("temple", "cave"):
            with self.subTest(interior=interior):
                random.seed(35)
                dungeon = Dungeon(puzzle_chance=1)
                dungeon.generate(2, campaign="jungle", interior=interior)
                game = HeadlessGame(dungeon)
                game.campaign = "jungle"
                game._populate_floor(2)
                seen = reachable_floor_tiles(dungeon, dungeon.start_pos)
                self.assertTrue(dungeon.passages.keys() <= seen)
                self.assertTrue(
                    any(
                        (obj.x, obj.y) in seen
                        for obj in game.objects
                        if obj.kind == "chest"
                    )
                )
                info = dungeon.mirror_puzzle_info
                self.assertIsNotNone(info)
                self.assertIn(info["entry_door"], seen)
                self.assertNotIn(info["sealed_rect"].center, seen)
                dungeon.doors[info["gate_door"]].is_open = True
                self.assertIn(
                    info["sealed_rect"].center,
                    reachable_floor_tiles(dungeon, dungeon.start_pos),
                )

    def test_river_has_fords_in_separate_reaches_and_a_walkable_log(self):
        random.seed(1)
        dungeon = Dungeon(puzzle_chance=0)
        dungeon.generate(campaign="jungle")
        seen = reachable_floor_tiles(dungeon, dungeon.start_pos)
        shallows = [
            y
            for y in range(8, dungeon.height - 8)
            if dungeon.grid[y][50:100].count(SHALLOW_WATER) >= 5
            and DEEP_WATER not in dungeon.grid[y][50:100]
        ]
        ford_heads = [y for y in shallows if y - 1 not in shallows]
        self.assertIn(len(ford_heads), (2, 3))
        self.assertGreaterEqual(
            min(b - a for a, b in zip(ford_heads, ford_heads[1:])), 14
        )
        for y in ford_heads:
            cross_section = {
                (x, y) for x in range(50, 100) if dungeon.grid[y][x] == SHALLOW_WATER
            }
            self.assertTrue(cross_section <= seen)
        logs = {
            (x, y)
            for y, line in enumerate(dungeon.grid)
            for x, tile in enumerate(line)
            if tile == FALLEN_LOG
        }
        self.assertGreater(len(logs), 5)
        self.assertTrue(logs <= seen)
        self.assertEqual(len({y for _, y in logs}), 1)

    def test_temple_turns_toward_an_atrium_with_jungle_intrusion(self):
        random.seed(35)
        dungeon = Dungeon(puzzle_chance=0)
        dungeon.generate(2, campaign="jungle", interior="temple")
        start = dungeon.start_pos
        exit_tile = next(iter(dungeon.passages))
        treasure = next(
            (x, y) for x, y, kind in dungeon.jungle_props if kind == "chest"
        )
        screen_axis = 1 if exit_tile[0] != start[0] else 0
        self.assertGreater(abs(treasure[screen_axis] - start[screen_axis]), 25)
        self.assertTrue(any(22 in row for row in dungeon.grid))
        self.assertTrue(any(SHALLOW_WATER in row for row in dungeon.grid))
        self.assertIn("ov_mangrove_roots", dungeon.overlays.values())
        self.assertIn("ov_jungle_vines", dungeon.overlays.values())
        self.assertIn(treasure, reachable_floor_tiles(dungeon, start))

    def test_settlement_houses_vary_in_shape_count_and_furnishings(self):
        counts = set()
        footprints = set()
        kinds = set()
        for seed in range(12):
            dungeon = Dungeon(puzzle_chance=0)
            dungeon.grid = [[21] * dungeon.width for _ in range(dungeon.height)]
            dungeon.jungle_props, dungeon.rooms = [], []
            plan = Plan(dungeon, random.Random(seed))
            center = (dungeon.width // 2, dungeon.height // 2)
            contacts = village(plan, center, (1, 0))
            reached = reachable_floor_tiles(dungeon, contacts[0])
            self.assertIn(contacts[1], reached)
            self.assertTrue(plan.hut_entries <= reached)
            self.assertTrue(2 <= len(plan.hut_entries) <= 5)
            counts.add(len(plan.hut_entries))
            footprints.update(tuple(sorted(room.size)) for room in dungeon.rooms[:-1])
            kinds.update(kind for _, _, kind in dungeon.jungle_props)
        self.assertGreaterEqual(len(counts), 3)
        self.assertGreaterEqual(len(footprints), 5)
        self.assertTrue(
            {"tribal_bed", "tribal_bow_stand", "shaman_cauldron", "tribal_chest"}
            <= kinds
        )

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

    def test_clicking_scenery_uses_localized_inspection_and_leaves_it_in_place(self):
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
            pool = game.loc["prop_thoughts"][kind]
            self.assertGreaterEqual(len(set(pool)), 5)
            args, kwargs = game.set_thought.call_args
            self.assertIn(args[0], pool)
            self.assertEqual(kwargs, {"on_inspect": True})
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
