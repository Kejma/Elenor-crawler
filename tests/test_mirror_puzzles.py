"""Headless regression tests: python -m unittest discover -s tests -v."""
import itertools
import os
import random
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from elenor.config import MAP_COLS, MAP_ROWS, TILE_W, TILE_H
from elenor.world.dungeon import Door, Dungeon
from elenor.entities import Enemy, Interactable, Player
from elenor.data.items import BASE_ITEMS_DB
from elenor.game.controller import GameController
from elenor.localization import load_modular_locales
from elenor.missions.rats import populate_mission_floor
import elenor.puzzles.mirrors as puzzles


class HeadlessGame(GameController):
    def __init__(self, dungeon):
        self.loc = load_modular_locales()
        self.dungeon = dungeon
        adj_key, adj = next(iter(self.loc["adjectives"].items()))
        noun_key, noun = next(iter(self.loc["nouns"].items()))
        self.player = Player(*dungeon.start_pos, adj_key, adj, noun_key, noun, self.loc["items"])
        self.objects, self.mobs, self.mirror_puzzles = [], [], []
        self.particles, self.visual_fx, self.projectiles = [], [], []
        self.current_visible_tiles = set()
        self.sfx, self.fx = Mock(), Mock()
        self.add_popup, self.set_thought, self.add_log = Mock(), Mock(), Mock()
        self.play_spatial, self.emit_noise = Mock(), Mock()
        self.trigger_event_thought = Mock()
        self.balance_data = {}


def empty_dungeon():
    d = Dungeon(puzzle_chance=0)
    d.grid = [[1] * MAP_COLS for _ in range(MAP_ROWS)]
    d.rooms, d.doors, d.levers, d.braziers = [], {}, {}, []
    d.solid_props, d.overlays = set(), {}
    d.invisible_bounds = set()
    d.boss_room = None
    d.start_pos = (10, 10)
    d.floor_num = 3
    d.invalidate_light_cache()
    return d


def visible_now(game):
    _, tiles, _ = game.dungeon.compute_nox_fov(
        game.player.x * TILE_W, game.player.y * TILE_H, 0, 0)
    game.current_visible_tiles = tiles
    return tiles


class MirrorPuzzleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_lens_registry_localization_and_random_loot(self):
        g = HeadlessGame(Dungeon())
        self.assertNotIn("name", BASE_ITEMS_DB["focusing_lens"])
        self.assertEqual(g.make_item("focusing_lens").name, "Фокусирующая линза")
        for _ in range(300):
            self.assertNotEqual(g.roll_item_by_rarity().type, "quest_key")
        # Even the no-matching-rarity fallback must exclude quest keys.
        g.loc["items"] = {key: value for key, value in g.loc["items"].items()
                          if key in ("focusing_lens", "potion_hp")}
        with patch("elenor.game.inventory.random.choices", return_value=["legendary"]):
            self.assertNotEqual(g.roll_item_by_rarity(allowed_types=["consumable"]).type, "quest_key")

    def test_campaign_keeps_its_introduction(self):
        d = Dungeon(puzzle_profile="rats")
        g = HeadlessGame(d)
        for floor in (1, 2, 3, 4):
            d.generate(floor)
            g.player.x, g.player.y = (v + 0.5 for v in d.start_pos)
            g.objects, g.mobs, g.mirror_puzzles = [], [], []
            populate_mission_floor(g, floor, Enemy, Interactable)
            self.assertEqual(len(g.mirror_puzzles), int(floor == 4))
            if floor == 4:
                ctrl = g.mirror_puzzles[0]
                self.assertEqual(ctrl.room_rect.size, (11, 9))
                self.assertEqual(ctrl.emitter_state, "ready")
                self.assertFalse(ctrl.ambush_enabled)
                self.assertTrue(any(m.is_boss for m in g.mobs))

    def test_procedural_chance_size_and_floor_reset(self):
        d = Dungeon(puzzle_chance=0)
        for floor in (2, 3, 4, 8):
            d.generate(floor)
            self.assertIsNone(d.mirror_puzzle_info)
        d.puzzle_chance = 1
        sizes = []
        for floor in (2, 3, 4, 5):
            d.generate(floor)
            self.assertIsNone(d.boss_room)
            self.assertIsNone(d.pre_boss_puzzle_info)
            sizes.append(d.mirror_puzzle_info["puzzle_rect"].width)
        self.assertEqual(sizes, [11, 13, 15, 17])
        d.generate(1)
        self.assertIsNone(d.mirror_puzzle_info)
        self.assertIsNone(d.pre_boss_puzzle_info)

    def test_generated_gates_have_no_bypass_and_solutions_work(self):
        # All four orientations, different biomes, large rooms and movable mirrors.
        directions = set()
        original = puzzles._try_generate_procedural_layout
        for profile, floor, seed in itertools.product(("rats", "procedural"), (2, 3, 4, 7), range(30)):
            if profile == "rats" and floor < 4:
                continue
            with self.subTest(profile=profile, floor=floor, seed=seed):
                random.seed(seed)
                d = Dungeon(puzzle_profile=profile, puzzle_chance=1)
                d.generate(floor)
                info = d.mirror_puzzle_info
                directions.add(info["dir"])
                # Open ordinary doors through their reachable levers, never the puzzle gate.
                reachable = puzzles.reachable_floor_tiles(d, d.start_pos)
                for lever in d.levers.values():
                    self.assertIn((lever.x, lever.y), reachable)
                    for door in lever.target_doors:
                        door.locked = False
                reachable = puzzles.reachable_floor_tiles(d, d.start_pos)
                self.assertTrue(any(info["puzzle_rect"].collidepoint(pt) for pt in reachable))
                self.assertFalse(any(info["sealed_rect"].collidepoint(pt) for pt in reachable))
                g = HeadlessGame(d)
                layouts = []

                def capture(*args):
                    layout = original(*args)
                    if layout:
                        layouts.append(layout)
                    return layout

                with patch.object(puzzles, "_try_generate_procedural_layout", side_effect=capture):
                    ctrl = puzzles.spawn_floor_mirror_puzzle(g, Interactable, emitter_mode="need_lens")
                self.assertFalse(ctrl.solved)
                reachable = puzzles.reachable_floor_tiles(d, d.start_pos)
                for obj in ctrl.emitters + [ctrl.receiver] + ctrl.mirrors:
                    self.assertTrue(any((obj.x + dx, obj.y + dy) in reachable
                                        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))))
                for obj in g.objects:
                    if obj.item or getattr(obj, "is_puzzle_emitter_lever", False):
                        self.assertIn((obj.x, obj.y), reachable)
                        self.assertFalse(info["sealed_rect"].collidepoint(obj.x, obj.y))
                # Set the known generated solution and trace it through the real world.
                if layouts:
                    for mirror, spec in zip(ctrl.mirrors, layouts[-1]["mirrors"]):
                        d.solid_props.discard((mirror.x, mirror.y))
                        mirror.x, mirror.y = spec["pos"]
                        mirror.mirror_ori = spec["ori"]
                        d.solid_props.add((mirror.x, mirror.y))
                        puzzles._sync_mirror_kind(mirror)
                else:
                    # Deterministic one-mirror fallback.
                    ctrl.mirrors[0].mirror_ori = puzzles.get_required_single_ori((0, -1), (1, 0))
                ctrl.emitter_state = "ready"
                puzzles.recalculate_mirror_puzzle(g, ctrl)
                self.assertTrue(ctrl.solved)
                gate = d.doors[info["gate_door"]]
                self.assertTrue(gate.is_open)
                self.assertFalse(gate.locked)
                reachable = puzzles.reachable_floor_tiles(d, d.start_pos)
                self.assertIn(info["sealed_rect"].center, reachable)
                # Solving is latched; rotating a mirror cannot shut the gate again.
                ctrl.mirrors[0].mirror_ori = (ctrl.mirrors[0].mirror_ori + 1) % 4
                puzzles.recalculate_mirror_puzzle(g, ctrl)
                self.assertTrue(gate.is_open)
        self.assertEqual(directions, {"east", "west", "north", "south"})

    def test_procedural_puzzle_guards_optional_area_not_stairs(self):
        for floor in (2, 3, 4, 7):
            d = Dungeon(puzzle_chance=1)
            d.generate(floor)
            g = HeadlessGame(d)
            populate_mission_floor(g, floor, Enemy, Interactable)
            sealed = d.mirror_puzzle_info["sealed_rect"]
            stairs = [o for o in g.objects if o.kind == "stairs"]
            self.assertEqual(len(stairs), 1)
            self.assertFalse(sealed.collidepoint(stairs[0].x, stairs[0].y))
            self.assertTrue(any(o.kind == "chest" and sealed.collidepoint(o.x, o.y) for o in g.objects))

    def test_no_unsafe_key_fallback(self):
        d = empty_dungeon()
        d._carve_rect(pygame.Rect(10, 10, 1, 1), 0)
        d._carve_rect(pygame.Rect(14, 10, 3, 3), 0)  # nearby but disconnected
        g = HeadlessGame(d)
        self.assertIsNone(puzzles.find_safe_accessible_tile_for_puzzle_item(g, pygame.Rect(30, 10, 11, 9)))
        ctrl = puzzles.setup_mirror_puzzle_in_room(
            g, pygame.Rect(30, 10, 11, 9), [], Interactable, emitter_mode="need_lens")
        self.assertEqual(ctrl.emitter_state, "ready")

    def test_key_search_can_cross_unlocked_but_not_locked_doors(self):
        d = empty_dungeon()
        d._carve_rect(pygame.Rect(10, 10, 7, 1), 0)
        d.rooms = [pygame.Rect(14, 9, 3, 3)]
        d.doors[(11, 10)] = Door(11, 10)
        d.doors[(14, 10)] = Door(14, 10, locked_by_lever=True)
        g = HeadlessGame(d)
        tile = puzzles.find_safe_accessible_tile_for_puzzle_item(g, pygame.Rect(30, 10, 11, 9))
        self.assertIn(tile, ((12, 10), (13, 10)))

    def test_lens_and_lever_interactions(self):
        for mode in ("need_lens", "need_lever"):
            with self.subTest(mode=mode):
                d = Dungeon(puzzle_chance=1)
                d.generate(3)
                g = HeadlessGame(d)
                ctrl = puzzles.spawn_floor_mirror_puzzle(g, Interactable, emitter_mode=mode)
                self.assertEqual(ctrl.emitter_state, mode)
                self.assertEqual(ctrl.beam_segments, [])
                emitter = ctrl.emitters[0]
                puzzles.handle_mirror_puzzle_interaction(g, emitter)
                self.assertEqual(ctrl.emitter_state, mode)
                if mode == "need_lens":
                    # Check the quickbar too, and consume the item only once.
                    lens = g.make_item("focusing_lens")
                    g.player.hotbar[0] = lens
                    puzzles.handle_mirror_puzzle_interaction(g, emitter)
                    self.assertIsNone(g.player.hotbar[0])
                else:
                    lever = next(o for o in g.objects if getattr(o, "is_puzzle_emitter_lever", False))
                    puzzles.handle_mirror_puzzle_interaction(g, lever)
                    self.assertEqual(lever.kind, "lever_on")
                    puzzles.handle_mirror_puzzle_interaction(g, lever)
                self.assertEqual(ctrl.emitter_state, "ready")
                self.assertTrue(ctrl.beam_segments)

    def ambush_game(self):
        d = empty_dungeon()
        room = pygame.Rect(8, 8, 8, 8)
        d._carve_rect(room, 0)
        d._carve_rect(pygame.Rect(16, 14, 7, 1), 0)
        d._carve_rect(pygame.Rect(22, 8, 1, 7), 0)
        g = HeadlessGame(d)
        ctrl = puzzles.MirrorPuzzleController(room, [], Interactable(9, 9, "light_receiver_off"), [], [],
                                              ambush_enabled=True)
        g.mirror_puzzles = [ctrl]
        visible_now(g)
        return g, ctrl

    def spawn_ambush(self, g, ctrl):
        ctrl.ambush_timer = -1
        puzzles._update_puzzle_ambush_spawner(g, ctrl, 0.1)

    def test_ambush_unseen_reachable_and_reward_limit_survives_reentry(self):
        g, ctrl = self.ambush_game()
        for count in range(1, 7):
            self.spawn_ambush(g, ctrl)
            self.assertEqual(len(g.mobs), 1)
            mob = g.mobs.pop()
            tile = int(mob.x), int(mob.y)
            self.assertNotIn(tile, g.current_visible_tiles)
            self.assertFalse(g.dungeon.has_line_of_sight(g.player.x, g.player.y, mob.x, mob.y, 18))
            path = g.dungeon.find_path(tile, (int(g.player.x), int(g.player.y)), max_expanded=3000)
            self.assertEqual(tuple(map(int, path[-1])), (10, 10))
            self.assertEqual(getattr(mob, "no_rewards", False), count >= 4)
            if count >= 4:
                self.assertEqual(mob.xp_value, 0)
            g.player.x = 40
            self.spawn_ambush(g, ctrl)
            self.assertEqual(g.mobs, [])
            g.player.x = 10.5
        self.assertEqual(ctrl.ambush_spawned_count, 6)

    def test_ambush_cap_visibility_occupancy_and_stop(self):
        g, ctrl = self.ambush_game()
        for _ in range(3):
            self.spawn_ambush(g, ctrl)
        self.assertEqual(len(g.mobs), 3)
        self.assertEqual(len({(m.x, m.y) for m in g.mobs}), 3)
        self.spawn_ambush(g, ctrl)
        self.assertEqual(len(g.mobs), 3)
        g.mobs.clear()
        g.current_visible_tiles = {(x, y) for x in range(MAP_COLS) for y in range(MAP_ROWS)}
        self.spawn_ambush(g, ctrl)
        self.assertFalse(g.mobs)
        visible_now(g)
        ctrl.solved = True
        self.spawn_ambush(g, ctrl)
        self.assertFalse(g.mobs)

    def test_pause_and_death_do_not_tick_puzzles(self):
        g, ctrl = self.ambush_game()
        before = ctrl.ambush_timer
        puzzles.update_mirror_puzzles(g, 0)
        self.assertEqual(ctrl.ambush_timer, before)
        g.player.hp = 0
        puzzles.update_mirror_puzzles(g, 1)
        self.assertEqual(ctrl.ambush_timer, before)

    def test_unrewarded_death_has_no_xp_loot_or_shards(self):
        g, _ = self.ambush_game()
        mob = Enemy(12, 10, kind="rat_cultist")
        mob.hp, mob.no_rewards = 0, True
        g.mobs = [mob]
        before = g.player.xp
        g._check_mob_death(mob)
        self.assertNotIn(mob, g.mobs)
        self.assertEqual(g.player.xp, before)
        self.assertEqual(g.objects, [])
        self.assertEqual(g.visual_fx, [])
        # Rechecking a corpse cannot grant a reward either.
        g._check_mob_death(mob)
        self.assertEqual(g.player.xp, before)

    def test_growth_credit_skips_unrewarded_target_and_counts_cast_once(self):
        g, _ = self.ambush_game()
        g.player.record_build_action = Mock()
        credit = {"action": ("mind", 0.35), "awarded": False}
        g.record_combat_growth(SimpleNamespace(no_rewards=True), credit)
        g.player.record_build_action.assert_not_called()
        g.record_combat_growth(SimpleNamespace(), credit)
        g.record_combat_growth(SimpleNamespace(), credit)
        g.player.record_build_action.assert_called_once_with("mind", 0.35)

    def test_spell_hits_and_enemy_dodges_respect_no_rewards(self):
        for rewarded in (False, True):
            g, _ = self.ambush_game()
            g.player.record_build_action = Mock()
            mob = Enemy(11, 10)
            mob.no_rewards = not rewarded
            g.mobs = [mob]
            spell = SimpleNamespace(type="spell", power=1, life_steal=0, cast_type="frost_nova",
                                    color=(100, 200, 255), aoe_radius=2.4, status_dur=1)
            g._execute_skill_or_spell(spell, 11, 10)
            self.assertEqual(g.player.record_build_action.call_count, int(rewarded))
            g.player.record_build_action.reset_mock()
            g.player.perk_dodge = 0.55
            with patch("elenor.game.combat.random.random", return_value=0):
                g.on_player_hit(1, source=mob)
            self.assertEqual(g.player.record_build_action.call_count, int(rewarded))


if __name__ == "__main__":
    unittest.main()

class OpticalCacheTests(unittest.TestCase):
    def test_cache_invalidates_for_mirror_geometry_and_blocking_props(self):
        d = Dungeon(puzzle_profile='rats')
        d.generate(4)
        g = HeadlessGame(d)
        ctrl = puzzles.spawn_floor_mirror_puzzle(g, Interactable)
        puzzles.recalculate_mirror_puzzle(g, ctrl)
        with patch.object(d, 'is_blocking_sight', wraps=d.is_blocking_sight) as trace:
            puzzles.recalculate_mirror_puzzle(g, ctrl)
            trace.assert_not_called()
            ctrl.mirrors[0].mirror_ori = (ctrl.mirrors[0].mirror_ori + 1) % 4
            puzzles.recalculate_mirror_puzzle(g, ctrl)
            self.assertGreater(trace.call_count, 0)
            trace.reset_mock()
            d.invalidate_light_cache()
            puzzles.recalculate_mirror_puzzle(g, ctrl)
            self.assertGreater(trace.call_count, 0)
            trace.reset_mock()
            g.objects.append(Interactable(1, 1, 'barrel'))
            puzzles.recalculate_mirror_puzzle(g, ctrl)
            self.assertGreater(trace.call_count, 0)
