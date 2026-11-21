"""Dedicated merchant room generation, decoration and existing trade contract."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import random
import unittest
from unittest.mock import patch
import pygame
from test_mirror_puzzles import HeadlessGame
from elenor.world.dungeon import Dungeon
from elenor.world.merchant import reachable_tiles
from elenor.entities import Enemy, Interactable, SOLID_INTERACTABLE_KINDS
from elenor.missions.rats import populate_mission_floor
from elenor.puzzles.optics import MIRROR_SOLID_KINDS


class MerchantTests(unittest.TestCase):
    def test_disabled_chance_and_reset_on_tavern(self):
        d = Dungeon(merchant_chance=0)
        for floor in (2, 3, 4):
            d.generate(floor)
            g = HeadlessGame(d)
            populate_mission_floor(g, floor, Enemy, Interactable)
            self.assertIsNone(d.merchant_room)
            self.assertFalse(any(o.kind == "npc_merchant" for o in g.objects))
        d.merchant_chance = 1
        d.generate(3)
        self.assertIsNotNone(d.merchant_room)
        d.generate(1)
        self.assertIsNone(d.merchant_room)

    def test_many_layouts_keep_merchant_accessible_and_exclude_encounters(self):
        count = 0
        positions = set()
        for profile in ("rats", "procedural"):
            for floor in (2, 3, 4, 7):
                for seed in range(35):
                    with self.subTest(profile=profile, floor=floor, seed=seed):
                        random.seed(seed)
                        d = Dungeon(
                            puzzle_profile=profile, puzzle_chance=1, merchant_chance=1
                        )
                        d.generate(floor)
                        g = HeadlessGame(d)
                        populate_mission_floor(g, floor, Enemy, Interactable)
                        room = d.merchant_room
                        merchants = [o for o in g.objects if o.kind == "npc_merchant"]
                        if room is None:
                            self.assertFalse(merchants)
                            continue
                        count += 1
                        positions.add(room.topleft)
                        self.assertEqual(len(merchants), 1)
                        self.assertNotEqual(room, d.rooms[0])
                        self.assertNotEqual(room, d.rooms[-1])
                        if d.mirror_puzzle_info:
                            for key in ("puzzle_rect", "sealed_rect"):
                                self.assertFalse(
                                    room.colliderect(d.mirror_puzzle_info[key])
                                )
                        d.solid_props = {
                            (o.x, o.y)
                            for o in g.objects
                            if o.kind in SOLID_INTERACTABLE_KINDS | MIRROR_SOLID_KINDS
                        }
                        reach = reachable_tiles(d, d.start_pos)
                        npc = merchants[0]
                        self.assertIn((npc.x, npc.y), reach)
                        self.assertTrue(
                            any(
                                (npc.x + dx, npc.y + dy) in reach
                                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                            )
                        )
                        for x in range(room.left, room.right):
                            for y in (room.top, room.bottom - 1):
                                self.assertFalse(d.is_blocking_move(x, y))
                        self.assertFalse(
                            any(room.collidepoint(int(m.x), int(m.y)) for m in g.mobs)
                        )
                        inside = [o for o in g.objects if room.collidepoint(o.x, o.y)]
                        self.assertFalse(
                            any(
                                o.kind in ("trap", "chest", "loot", "stairs")
                                for o in inside
                            )
                        )
                        self.assertTrue(any(o.kind == "merchant_sign" for o in inside))
                        self.assertTrue(any(room.collidepoint(pt) for pt in d.carpets))
        self.assertGreater(count, 200)
        self.assertGreater(len(positions), 40)

    def test_default_spawn_is_rare(self):
        random.seed(2026)
        d = Dungeon(puzzle_profile="rats")
        count = 0
        for _ in range(400):
            d.generate(3)
            count += d.merchant_room is not None
        self.assertTrue(140 < count < 290, count)

    def test_counter_sells_gems_without_consuming_decoration(self):
        from elenor.ui.shop import _sell_all_gems_to_run_wallet
        random.seed(1)
        d = Dungeon(merchant_chance=1)
        d.generate(3)
        g = HeadlessGame(d)
        g.profile = {}
        g._last_picked_line = {}
        g.shop_state = None
        populate_mission_floor(g, 3, Enemy, Interactable)
        counter = next(
            o
            for o in g.objects
            if o.kind == "merchant_counter" and o.x == d.merchant_room.centerx
        )
        g.player.x, g.player.y = counter.x + 0.5, counter.y + 1.5
        gem = g.make_item("gem_ruby")
        g.player.inventory[0] = gem
        self.assertTrue(
            g._try_precise_interaction(counter.x + 0.5, counter.y + 0.5, 1.0)
        )
        self.assertIsNotNone(g.shop_state)
        stock_ids = [itm.id for itm in g.shop_state["npc"].shop_stock]
        self.assertTrue(any(i.startswith("potion_hp") or i == "herbal_salve" for i in stock_ids))
        self.assertIn("potion_mp", stock_ids)
        _sell_all_gems_to_run_wallet(g, g.shop_state)
        self.assertIsNone(g.player.inventory[0])
        self.assertEqual(g.player.gold, gem.copper_value)
        self.assertFalse(counter.used)
        self.assertFalse(counter.merchant_owner.used)