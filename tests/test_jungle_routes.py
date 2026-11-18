import random
import unittest
from unittest.mock import patch

from elenor.entities import Interactable, Projectile
from elenor.world.dungeon import Door, Dungeon
from elenor.world.jungle_routes import route_kind
from test_mirror_puzzles import HeadlessGame, empty_dungeon


class JungleRouteTests(unittest.TestCase):
    def test_route_control_can_be_used_and_onward_exit_takes_space(self):
        for depth in (1, 2, 3, 6):
            with self.subTest(depth=depth):
                random.seed(depth + 90)
                dungeon = Dungeon(puzzle_chance=1)
                dungeon.generate(depth, campaign="jungle", interior=route_kind(depth))
                game = HeadlessGame(dungeon)
                game.campaign = "jungle"
                game.jungle_locations = {}
                game.inv_open = False
                game._populate_floor(depth)
                gate = dungeon.doors[dungeon.jungle_gate]
                control, color = next(iter(dungeon.jungle_controls.items()))
                self.assertTrue(gate.locked)
                game.player.x, game.player.y = control[0] + 0.5, control[1] + 0.5
                game.try_interact_or_melee(game.player.x, game.player.y)
                if color != "lever":
                    self.assertIn(color, dungeon.jungle_keys)
                    gx, gy = dungeon.jungle_gate
                    game.player.x, game.player.y = gx + 0.5, gy + 0.5
                    game.try_interact_or_melee(gx + 0.5, gy + 0.5)
                self.assertFalse(gate.locked)
                self.assertTrue(gate.is_open)
                x, y = next(p for p, action in dungeon.passages.items() if action == "onward")
                game.player.x, game.player.y = x + 0.5, y + 0.5
                game.try_interact_or_melee(0, 0, via_mouse=False)
                self.assertEqual(game.dungeon.floor_num, depth + 1)
                self.assertIsNone(game.dungeon.interior)
                game.travel_jungle("back")
                self.assertIs(game.dungeon, dungeon)

    def test_projectile_passes_fixture_and_stops_at_closed_door(self):
        d = empty_dungeon()
        for x in (9, 10, 11):
            d.grid[10][x] = 0
        d.solid_props.add((10, 10))
        d.doors[(11, 10)] = Door(11, 10)
        p = Projectile(9.5, 10.5, 1, 0, speed=10, mag_dmg=4, color=(255, 255, 255))
        self.assertTrue(d.is_blocking_move(10, 10))
        self.assertTrue(p.update(0.1, d, []))
        self.assertFalse(p.update(0.1, d, []))

    def test_vase_leaves_fragments_and_frees_the_tile(self):
        d = empty_dungeon()
        game = HeadlessGame(d)
        game.inv_open = False
        vase = Interactable(10, 10, "marble_urn")
        game.objects.append(vase)
        d.solid_props.add((10, 10))
        with patch("elenor.game.combat.random.random", return_value=0.9):
            game.try_interact_or_melee(10.5, 10.5)
        self.assertEqual(game.objects, [vase])
        self.assertEqual(vase.kind, "ceramic_shards")
        self.assertNotIn((10, 10), d.solid_props)

    def test_thicket_has_narrow_trunks_and_linked_occlusion(self):
        d = empty_dungeon()
        for y in range(8, 15):
            for x in range(8, 15):
                d.grid[y][x] = 10
        d.thickets = {(10, 10), (11, 10)}
        self.assertFalse(d.has_line_of_sight(9.5, 10.5, 12.5, 10.5, 5))
        self.assertTrue(d.has_line_of_sight(9.5, 10.08, 12.5, 10.08, 5))
