import unittest
from collections import Counter
from unittest.mock import patch

import pygame

from elenor.data.abilities import PASSIVES, PASSIVE_SLOT_LIMIT
from elenor.entities import Enemy
from elenor.game.controller import GameController
from elenor.rendering.ability_icons import draw_ability_icon
from elenor.ui.renderer import UIRendererMixin
from test_mirror_puzzles import HeadlessGame, empty_dungeon


class PassivePerkTests(unittest.TestCase):
    def setUp(self):
        dungeon = empty_dungeon()
        dungeon._carve_rect(pygame.Rect(5, 5, 20, 20), 0)
        self.game = HeadlessGame(dungeon)
        self.game.inv_open = False
        self.game.low_hp_thought_cd = 0
        self.game.can_trigger_background_thought = lambda **kwargs: False
        self.player = self.game.player
        self.perks = self.game.loc["perks"]

    def learn(self, *ids):
        for pid in ids:
            self.player.apply_perk(pid, self.perks)

    def test_roster_art_and_progression(self):
        self.assertEqual(Counter(data["branch"] for data in PASSIVES.values()),
                         dict(body=3, cunning=3, mind=3))
        images = set()
        for pid in PASSIVES:
            data = self.perks[pid]
            self.assertTrue(self.game._is_perk_eligible(pid, data))
            canvas = pygame.Surface((32, 32), pygame.SRCALPHA)
            self.assertTrue(draw_ability_icon(canvas, data["icon"], 0, 0, 32))
            images.add(pygame.image.tobytes(canvas, "RGBA"))
            self.assertIn("stat_label", data)
        self.assertEqual(len(images), len(PASSIVES))

        pid = "firm_stance"
        data = dict(self.perks[pid], rarity="rare")
        ui = UIRendererMixin()
        preview = ui._get_perk_progression_lines(self.player, pid, data, 0, 1)
        self.player.apply_perk(pid, {pid: data})
        self.assertEqual(preview, ui._get_perk_progression_lines(self.player, pid, self.perks[pid], 1, 1))
        upgrade = dict(data, rarity="legendary", upgrade_roll={"power": 0.48})
        self.player.apply_perk(pid, {pid: upgrade}, upgrade["upgrade_roll"])
        self.assertAlmostEqual(self.player.passive_power(pid), 0.31)
        self.learn(*[key for key in PASSIVES if key != pid])
        self.assertEqual(len(self.player.passive_perks), PASSIVE_SLOT_LIMIT)
        self.assertTrue(self.player.remove_perk(pid))
        self.assertEqual(self.player.passive_power(pid), 0)

    def test_stationary_melee_guards_and_moving_cancels_preparation(self):
        self.learn("firm_stance")
        target = Enemy(11, 10)
        target.hp = 100
        self.game.mobs = [target]
        self.player.update_timers(0.5)
        self.assertTrue(self.player.stance_ready())
        self.assertGreater(self.player.passive_flash("firm_stance"), 0)
        self.player.update_timers(0.7)
        self.assertEqual(self.player.passive_flash("firm_stance"), 0)
        self.game._execute_melee_swing(target.x, target.y - 0.22)
        self.assertTrue(self.player.passive_active("firm_stance"))
        self.assertGreater(self.player.passive_flash("firm_stance"), 0)
        hp = self.player.hp
        raw = self.player.phys_defense + 10
        with patch("elenor.game.combat.random.random", return_value=1.0):
            self.game.on_player_hit(raw)
        self.assertEqual(self.player.hp, hp - 8)
        self.player.update_timers(2.0)
        self.assertFalse(self.player.passive_active("firm_stance"))
        self.player.x += 0.1
        self.game._execute_melee_swing(target.x, target.y - 0.22)
        self.assertFalse(self.player.passive_active("firm_stance"))

    def test_multi_target_swing_charges_and_spends_wider_arc(self):
        self.learn("wide_swing")
        weapon = self.game.make_item("rusty_dagger")
        self.player.equipment["right_hand"] = weapon
        weapon.arc_deg, weapon.max_targets, weapon.reach = 70, 2, 2.4
        ax, ay = self.player.x, self.player.y
        self.game.mobs = [Enemy(11, 10), Enemy(12, 10)]
        for target in self.game.mobs:
            target.hp = 100
        self.game._execute_melee_swing(ax + 3, ay - 0.22)
        self.assertTrue(self.player.passive_active("wide_swing"))
        edge = Enemy(11, 11)
        edge.x, edge.y, edge.hp = ax + 1.3, ay + 1.9, 100
        self.game.mobs = [edge]
        self.game._execute_melee_swing(ax + 3, ay - 0.22)
        self.assertFalse(self.player.passive_active("wide_swing"))
        self.assertLess(edge.hp, 100)
        hp = edge.hp
        self.game._execute_melee_swing(ax + 3, ay - 0.22)
        self.assertEqual(edge.hp, hp)

    def test_crusher_temporarily_reduces_armor_per_enemy(self):
        self.learn("armor_breaker")
        first, second = Enemy(11, 10), Enemy(12, 10)
        first.phys_def = second.phys_def = 10
        self.assertEqual(self.game._physical_hit_damage(first, 20, 0), 12)
        self.player.update_timers(3.1)
        self.assertEqual(self.game._physical_hit_damage(first, 20, 0), 10)
        self.assertEqual(self.game._physical_hit_damage(second, 20, 0), 12)
        self.player.update_timers(5.0)
        self.assertEqual(self.game._physical_hit_damage(first, 20, 0), 12)
        self.assertEqual(first.phys_def, 10)

    def test_successful_dodge_grants_timed_speed(self):
        self.learn("sidestep")
        with patch("elenor.game.combat.random.random", return_value=-1.0):
            self.game.on_player_hit(10)
        self.assertTrue(self.player.passive_active("sidestep"))
        x = self.player.x
        self.player.move_realtime(1, 0, 0.1, self.game.dungeon)
        fast_distance = self.player.x - x
        self.player.update_timers(1.5)
        x = self.player.x
        self.player.move_realtime(1, 0, 0.1, self.game.dungeon)
        self.assertAlmostEqual(fast_distance, (self.player.x - x) * 1.2)

    def test_quiet_attack_remembers_awareness_before_its_own_noise(self):
        self.learn("quiet_work")
        first, second = Enemy(11, 10), Enemy(12, 10)
        first.state = second.state = "patrolling"
        first.phys_def = second.phys_def = 0
        self.game.mobs = [first, second]
        action = self.game._physical_attack_context()
        GameController.emit_noise(self.game, self.player.x, self.player.y, 6)
        self.assertEqual(first.state, "combat")
        self.assertEqual(self.game._physical_hit_damage(first, 10, 0, action=action), 12)
        self.assertEqual(self.game._physical_hit_damage(second, 10, 0, action=action), 10)

    def test_kill_bonus_requires_another_action_and_respects_cooldown(self):
        self.learn("change_target")
        first, second = Enemy(11, 10), Enemy(12, 10)
        first.hp = 0
        first.phys_def = second.phys_def = 0
        self.game.mobs = [first, second]
        action = {}
        self.game._check_mob_death(first, action)
        self.assertEqual(self.game._physical_hit_damage(second, 10, 0, action=action), 10)
        self.assertEqual(self.game._physical_hit_damage(second, 10, 0, action={}), 12)
        second.hp = 0
        self.game._check_mob_death(second)
        self.assertFalse(self.player.passive_active("change_target"))

    def test_magic_passives_only_record_executed_casts(self):
        self.learn("divine_pact", "spell_focus", "warding_pulse",
                   "pyro_ignite", "stratos_chain_lightning", "stratos_frost_nova")
        fire, lightning, frost, _ = self.player.ability_slots
        self.player.cooldowns = {lightning.id: 3.2, frost.id: 6}
        self.game._execute_skill_or_spell(lightning, 24, 24)
        self.assertEqual(self.player.recent_spell_schools, {})
        self.assertEqual(self.player.cooldowns[frost.id], 6)
        self.assertEqual(self.player.ability_mana_cost(frost), frost.mp_cost)

        target = Enemy(12, 10)
        target.hp = 100
        self.game.mobs = [target]
        self.game._execute_skill_or_spell(fire, 10, 10)
        self.assertGreater(target.slow_timer, 0)
        pulse = self.player.passive_ready_at["warding_pulse"]
        self.player.cooldowns[lightning.id] = 3.2
        expected_cost = frost.mp_cost * 0.85
        self.assertAlmostEqual(self.player.ability_mana_cost(frost), expected_cost)
        self.player.cooldowns.pop(frost.id)
        self.player.mp = expected_cost
        self.game.use_or_equip_item(frost)
        self.assertAlmostEqual(self.player.mp, 0)
        self.assertGreater(self.player.passive_flash("divine_pact"), 0)
        self.assertGreater(self.player.passive_flash("spell_focus"), 0)
        self.assertAlmostEqual(self.player.cooldowns[lightning.id], 3.2 * 0.85)
        self.assertAlmostEqual(self.player.ability_mana_cost(frost), expected_cost)
        self.assertAlmostEqual(self.player.cooldowns[frost.id], frost.cooldown)
        self.assertEqual(self.player.passive_ready_at["warding_pulse"], pulse)
        self.player.update_timers(5.1)
        self.assertEqual(self.player.ability_mana_cost(frost), frost.mp_cost)


    def test_cancelled_lightning_refunds_only_discounted_price(self):
        self.learn("divine_pact", "pyro_ignite", "stratos_chain_lightning")
        fire, lightning, *_ = self.player.ability_slots
        self.game._execute_skill_or_spell(fire, 10, 10)
        enemy = Enemy(12, 10)
        self.game.mobs = [enemy]
        self.player.mp = 5
        self.game.use_or_equip_item(lightning, enemy.x, enemy.y)
        pending = self.player.pending_action
        self.assertAlmostEqual(self.player.mp, 5 - lightning.mp_cost * 0.85)
        self.game.mobs.clear()
        self.game._execute_skill_or_spell(lightning, pending["tx"], pending["ty"],
                                         mana_paid=pending["mana_paid"])
        self.assertEqual(self.player.mp, 5)
        self.assertNotIn(lightning.id, self.player.cooldowns)
        self.assertEqual(set(self.player.recent_spell_schools), {"pyro"})
