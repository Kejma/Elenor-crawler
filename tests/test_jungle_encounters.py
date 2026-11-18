import math
import random
import unittest
from unittest.mock import Mock

import pygame

from elenor.entities import Enemy
from elenor.entities.jungle_combat import ATTACKS, HEAL, POUNCE, STOMP
from elenor.missions.jungle_encounters import EARLY_STATS, GUARDIANS, HABITATS
from elenor.puzzles.mirrors import reachable_floor_tiles
from elenor.world.dungeon import Dungeon
from test_mirror_puzzles import HeadlessGame, empty_dungeon


class JungleEncountersTests(unittest.TestCase):
    def test_first_valley_has_local_enemies_and_reachable_equipment_cache(self):
        random.seed(19)
        dungeon = Dungeon(puzzle_chance=1)
        dungeon.generate(campaign="jungle")
        game = HeadlessGame(dungeon)
        game.campaign = "jungle"
        game._populate_floor(1)

        self.assertTrue(game.mobs)
        self.assertGreaterEqual(len(game.mobs), 30)
        self.assertEqual(
            set(ATTACKS), {kind for group in HABITATS.values() for _, kind in group}
            | {kind for _, kind in GUARDIANS.values()},
        )
        self.assertTrue(all(m.kind in EARLY_STATS and m.phys_def == 0 for m in game.mobs))
        self.assertTrue(all(math.dist((m.x, m.y), dungeon.start_pos) > 12 for m in game.mobs))
        near_start = reachable_floor_tiles(dungeon, dungeon.start_pos, max_distance=5)
        self.assertFalse(any(o.kind == "loot" and (o.x, o.y) in near_start for o in game.objects))
        self.assertTrue(any(o.kind == "campfire" and (o.x, o.y) in near_start for o in game.objects))
        self.assertIn(dungeon.jungle_starter_cache, reachable_floor_tiles(dungeon, dungeon.start_pos))
        self.assertNotIn(dungeon.jungle_starter_cache, near_start)

        game.inv_open = False
        x, y = dungeon.jungle_bag_cache
        self.assertNotEqual((x, y), dungeon.jungle_starter_cache)
        game.player.x, game.player.y = x + 0.5, y + 0.5
        game.try_interact_or_melee(game.player.x, game.player.y)
        loot = next(o for o in game.objects if o.kind == "loot" and o.item.id == "small_pouch")
        game._pickup_loot_object(loot)
        self.assertEqual(game.player.unlocked_slots, game.player.pocket_slots + 2)

    def arena(self):
        dungeon = empty_dungeon()
        for y in range(8, 17):
            for x in range(8, 17):
                dungeon.grid[y][x] = 0
        return dungeon, HeadlessGame(dungeon)

    def test_alerted_enemy_keeps_chasing_far_from_spawn(self):
        dungeon, game = self.arena()
        dungeon._carve_rect(pygame.Rect(5, 8, 22, 6), 10)
        mob = Enemy(6, 10, "jungle_gremlin", state="combat")
        mob.x = 17.5
        game.player.x = 22.5
        mob.update_ai(.10, game.player, dungeon, [mob], [], game.sfx, game.add_popup, Mock())
        self.assertEqual(mob.state, "combat")
        self.assertGreater(mob.x, 17.5)

    def test_shaman_channels_a_bounded_heal_for_a_tribal_ally(self):
        dungeon, game = self.arena()
        shaman = Enemy(10, 10, "tribal_shaman", state="combat")
        warrior = Enemy(11, 10, "tribal_warrior", state="combat")
        unrelated = Enemy(10, 11, "croc_warrior", state="combat")
        warrior.hp, unrelated.hp = 8, 1
        mobs = [shaman, warrior, unrelated]
        on_hit = Mock()
        shaman.update_ai(0.05, game.player, dungeon, mobs, [], game.sfx, game.add_popup, on_hit)
        self.assertEqual(shaman.jungle_windup, (HEAL, warrior))
        shaman.update_ai(HEAL.windup, game.player, dungeon, mobs, [], game.sfx, game.add_popup, on_hit)
        self.assertEqual(warrior.hp, 8 + round(warrior.max_hp * 0.25))
        self.assertEqual(unrelated.hp, 1)
        self.assertGreater(shaman.attack_cd, 0)
        on_hit.assert_not_called()

    def test_golem_commits_to_a_stomp_the_hero_can_leave(self):
        dungeon, game = self.arena()
        golem = Enemy(10, 10, "marble_golem", state="combat")
        game.player.x, game.player.y = 12.0, 10.5
        on_hit = Mock()
        golem.update_ai(0.05, game.player, dungeon, [golem], [], game.sfx, game.add_popup, on_hit)
        self.assertEqual(golem.jungle_windup, (STOMP, (10.5, 10.5)))
        game.player.x = 13
        golem.update_ai(STOMP.windup, game.player, dungeon, [golem], [], game.sfx, game.add_popup, on_hit)
        self.assertIsNone(golem.jungle_windup)
        on_hit.assert_not_called()

    def test_guardian_kill_drops_gear_without_granting_rat_campaign_reward(self):
        _, game = self.arena()
        game.profile = {"rat_king_defeated": False}
        game.visual_fx = []
        guardian = Enemy(10, 10, "ossuary_behemoth")
        guardian.hp = guardian.xp_value = 0
        game.mobs.append(guardian)

        game._check_mob_death(guardian)

        self.assertFalse(game.mobs)
        self.assertFalse(game.profile["rat_king_defeated"])
        self.assertTrue(all(obj.kind == "loot" for obj in game.objects))
        self.assertTrue(any(obj.item.type == "equipment" for obj in game.objects))
        game.trigger_event_thought.assert_called_once()
        self.assertEqual(game.trigger_event_thought.call_args.args[0], "jungle_guardian_defeated")

    def test_wasp_lunge_moves_across_frames(self):
        dungeon, game = self.arena()
        wasp = Enemy(10, 10, "giant_wasp", state="combat")
        game.player.x, game.player.y = 12.6, 10.5
        on_hit = Mock()
        args = (game.player, dungeon, [wasp], [], game.sfx, game.add_popup, on_hit)

        wasp.update_ai(0.05, *args)
        wasp.update_ai(POUNCE.windup, *args)
        self.assertEqual(wasp.x, 10.5)
        wasp.update_ai(0.05, *args)
        self.assertGreater(wasp.x, 10.5)
        self.assertLess(wasp.x, 11.3)
        self.assertIsNotNone(wasp.jungle_dash)
        for _ in range(5):
            wasp.update_ai(0.05, *args)
        on_hit.assert_called_once()

    def test_hunter_commits_to_melee_at_close_range(self):
        dungeon, game = self.arena()
        hunter = Enemy(10, 10, "tribal_hunter", state="combat")
        game.player.x, game.player.y = 11.7, 10.5
        on_hit = Mock()
        args = (game.player, dungeon, [hunter], [], game.sfx, game.add_popup, on_hit)
        hunter.update_ai(0.05, *args)
        self.assertEqual(hunter.jungle_windup[0].form, "strike")
        hunter.update_ai(0.12, *args)
        on_hit.assert_called_once()
