import random
import unittest

from elenor.world.dungeon import Dungeon
from elenor.world.run_seed import MAX_RUN_SEED, generation_random, parse_run_seed
from test_mirror_puzzles import HeadlessGame


def snapshot(game):
    d = game.dungeon
    return (
        tuple(tuple(row) for row in d.grid),
        dict(d.passages),
        dict(d.fishing_edges),
        d.jungle_starter_cache,
        d.jungle_bag_cache,
        sorted((pos, door.locked, door.key_color) for pos, door in d.doors.items()),
        [(o.x, o.y, o.kind, getattr(o, "mirror_ori", None),
          getattr(o.item, "id", None), getattr(o.item, "rarity", None)) for o in game.objects],
        [(m.x, m.y, m.kind, m.state) for m in game.mobs],
        [(p.emitter_state, p.receiver.x, p.receiver.y) for p in game.mirror_puzzles],
    )


class RunSeedTests(unittest.TestCase):
    def make_game(self, campaign, seed):
        game = HeadlessGame(Dungeon(puzzle_profile="rats", puzzle_chance=1))
        game.profile = {}
        game.reset_run(campaign=campaign, seed=seed)
        return game

    def test_optional_unsigned_64_bit_seed(self):
        self.assertIsNone(parse_run_seed("  "))
        self.assertEqual(parse_run_seed("0"), 0)
        self.assertEqual(parse_run_seed(f" {MAX_RUN_SEED} "), MAX_RUN_SEED)
        for invalid in ("-1", "2.7", "123abc", str(MAX_RUN_SEED + 1), "١"):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                parse_run_seed(invalid)

    def test_jungle_interior_order_does_not_change_seeded_generation(self):
        def explore(order):
            game = self.make_game("jungle", 139532)
            levels = {"surface": snapshot(game)}
            for interior in order:
                for _ in range(101):
                    random.random()
                game.travel_jungle(interior)
                self.assertTrue(game.mirror_puzzles)
                levels[interior] = snapshot(game)
                game.travel_jungle("up")
            self.assertEqual(game.run_seed, 139532)
            return levels

        self.assertEqual(explore(("cave", "temple")), explore(("temple", "cave")))

    def test_rat_floor_is_independent_of_previous_rng_use(self):
        a = self.make_game("rats", 0)
        b = self.make_game("rats", 0)
        self.assertEqual(a.player.full_name, b.player.full_name)
        for depth in range(2, 5):
            a.descend_to_next_floor()
            for _ in range(depth * 47):
                random.random()
            b.player.luck = 10
            b.descend_to_next_floor()
            self.assertEqual(snapshot(a), snapshot(b))

    def test_generation_restores_ambient_rng_after_failure(self):
        previous = random.getstate()
        with self.assertRaises(ValueError), generation_random(123):
            random.random()
            raise ValueError("assembly failed")
        self.assertEqual(random.getstate(), previous)
