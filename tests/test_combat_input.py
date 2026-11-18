import unittest
from unittest.mock import Mock, call

from elenor.audio.abilities import RELEASES, ability_waves
from elenor.entities import Item
from test_mirror_puzzles import HeadlessGame, empty_dungeon


class CombatInputTests(unittest.TestCase):
    def setUp(self):
        self.game = HeadlessGame(empty_dungeon())
        self.game.inv_open = False
        self.game.world_active = False
        self.game._execute_melee_swing = Mock()

    def tick_input(self, dt):
        self.game.player.update_timers(dt)
        self.game.update_buffered_combat(dt)

    def test_melee_remembers_a_click_close_to_the_end_of_recovery(self):
        game = self.game
        game.player.attack_cd = 0.30
        game._perform_melee_attack(11.5, 10.5)
        self.assertIsNone(game.player.buffered_combat)
        game.player.attack_cd = 0.09

        game._perform_melee_attack(12.5, 10.5)
        self.tick_input(0.04)
        game._execute_melee_swing.assert_not_called()
        self.tick_input(0.06)
        game._execute_melee_swing.assert_called_once_with(12.5, 10.5)
        self.assertTrue(game.world_active)
        self.assertIsNone(game.player.buffered_combat)
        self.tick_input(0.04)
        game._execute_melee_swing.assert_called_once()

    def test_ability_pressed_just_before_cooldown_ends(self):
        game = self.game
        ability = Item("heavy_strike", dict(game.loc["perks"]["heavy_strike"], type="combat_skill"))
        game.player.ability_slots[0] = ability
        game.player.cooldowns[ability.id] = 0.08

        game.use_or_equip_item(ability, 15.5, 10.5, from_hotbar=True)
        self.assertIsNone(game.player.pending_action)
        self.tick_input(0.09)
        self.assertEqual(game.player.pending_action["item"], ability)
        self.assertEqual((game.player.pending_action["tx"], game.player.pending_action["ty"]), (15.5, 10.5))
        self.assertTrue(game.world_active)

    def test_ability_audio_distinguishes_prepare_release_and_instant_cast(self):
        game = self.game
        sword = Item("heavy_strike", dict(game.loc["perks"]["heavy_strike"], type="combat_skill"))
        game.use_or_equip_item(sword, 15, 10)
        game.sfx.play.assert_called_once_with("ability_prepare")

        pending = game.player.pending_action
        game.player.pending_action = None
        game._execute_skill_or_spell(sword, pending["tx"], pending["ty"], mana_paid=pending["mana_paid"])
        self.assertEqual(game.sfx.play.call_args_list, [call("ability_prepare"), call("ability_heavy_strike")])

        game.sfx.play.reset_mock()
        spell = Item("persephone_rejuvenation", dict(game.loc["perks"]["persephone_rejuvenation"], type="permanent_spell"))
        game.use_or_equip_item(spell)
        game.sfx.play.assert_called_once_with("ability_persephone_rejuvenation")

    def test_every_active_ability_has_a_distinct_release_wave(self):
        active_ids = {key for key, data in self.game.loc["perks"].items() if data["type"] == "active"}
        self.assertTrue(active_ids <= RELEASES.keys())
        waves = dict(ability_waves(22050))
        self.assertEqual(len({waves[f"ability_{pid}"].tobytes() for pid in active_ids}), len(active_ids))
        self.assertLess(len(waves["ability_prepare"]), min(len(waves[f"ability_{pid}"]) for pid in active_ids))

    def test_first_upgrade_still_costs_48_xp(self):
        player = self.game.player
        self.assertFalse(player.gain_xp(47))
        self.assertTrue(player.gain_xp(1))
        self.assertEqual((player.level, player.max_xp), (2, 120))
        self.assertFalse(player.gain_xp(119))
        self.assertTrue(player.gain_xp(1))
        self.assertEqual((player.level, player.max_xp), (3, 186))

    def test_wall_does_not_start_a_run_animation(self):
        dungeon = self.game.dungeon
        player = self.game.player
        dungeon.grid[int(player.y)][int(player.x)] = 0
        player.x = 10.28
        self.assertFalse(player.move_realtime(-1, 0, 0.05, dungeon))
        self.assertFalse(player.is_moving)
