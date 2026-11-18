import unittest
from collections import Counter
import pygame
from test_mirror_puzzles import HeadlessGame, empty_dungeon
from elenor.localization import load_modular_locales
from elenor.entities import Item, Enemy
from elenor.rendering.ability_icons import draw_ability_icon


class AbilityTests(unittest.TestCase):
    def test_spell_defaults_to_common_and_upgrade_rarity_is_independent(self):
        game = HeadlessGame(empty_dungeon())
        key = "stratos_chain_lightning"
        base = game.loc["perks"][key]

        game.player.apply_perk(key, game.loc["perks"])
        spell = game.player.ability_slots[0]
        self.assertEqual(spell.rarity, "common")
        self.assertEqual(spell.bounces, base["bounces"])

        game.player.apply_perk(key, {key: dict(base, rarity="legendary")}, {"power": 0.48})
        self.assertEqual(spell.rarity, "common")
        self.assertEqual(spell.name, base["name"])
        self.assertAlmostEqual(spell.power, base["power"] * 1.48, places=2)

    def test_rare_first_spell_card_previews_the_acquired_stats(self):
        from elenor.ui.renderer import UIRendererMixin

        game = HeadlessGame(empty_dungeon())
        key = "pyro_firebolt"
        offer = dict(game.loc["perks"][key], rarity="rare")
        lines = UIRendererMixin()._get_perk_progression_lines(game.player, key, offer, 0, 1)
        game.player.apply_perk(key, {key: offer})
        spell = game.player.ability_slots[0]
        self.assertEqual(spell.rarity, "rare")
        self.assertIn(f"Перезарядка: {spell.cooldown:.2f}с", lines)

    def test_equal_rosters_and_distinct_icons(self):
        data = load_modular_locales()["perks"]
        counts = Counter()
        images = set()
        for key, v in data.items():
            if v.get("type") != "active":
                continue
            counts[v["branch"]] += 1
            canvas = pygame.Surface((32, 32), pygame.SRCALPHA)
            self.assertTrue(draw_ability_icon(canvas, v["icon"], 0, 0, 32))
            images.add(pygame.image.tobytes(canvas, "RGBA"))
        self.assertEqual(counts, dict(body=6, cunning=6, mind=6))
        self.assertEqual(len(images), 18)

    def test_each_physical_skill_can_be_learned_upgraded_and_hit(self):
        for key, v in load_modular_locales()["perks"].items():
            if v.get("skill_kind") != "combat":
                continue
            with self.subTest(skill=key):
                d = empty_dungeon()
                d._carve_rect(pygame.Rect(5, 5, 20, 20), 0)
                g = HeadlessGame(d)
                g.player.apply_perk(key, g.loc["perks"])
                item = g.player.ability_slots[0]
                self.assertEqual(item.type, "combat_skill")
                self.assertEqual(g._get_perk_branch(key, v), v["branch"])
                g.player.apply_perk(key, g.loc["perks"])
                m = Enemy(11, 10)
                m.hp = m.max_hp = 100
                m.phys_def = 0
                g.mobs = [m]
                g._execute_skill_or_spell(item, 11.5, 10.5)
                from elenor.game.physical import update_physical

                if item.shape in ("knife", "flask", "charge"):
                    for _ in range(20):
                        update_physical(g, 0.05)
                if item.shape == "flask":
                    g.fx.add_gas_cloud.assert_called_once()
                elif item.shape == "guard":
                    self.assertGreater(g.player.guard_timer, 0)
                elif item.shape == "stealth":
                    self.assertGreater(g.player.stealth_timer, 0)
                elif item.shape == "evade":
                    self.assertGreater(g.player.evade_timer, 0)
                elif item.shape == "trap":
                    m.x, m.y = g.player.x, g.player.y
                    update_physical(g, 0.5)
                    self.assertLess(m.hp, 100)
                else:
                    self.assertLess(m.hp, 100)

    def test_cone_excludes_rear_and_wall_blocks_damage(self):
        d = empty_dungeon()
        d._carve_rect(pygame.Rect(5, 5, 20, 20), 0)
        g = HeadlessGame(d)
        v = g.loc["perks"]["earth_slam"]
        item = Item("earth_slam", dict(v, type="combat_skill"))
        front, rear = Enemy(12, 10), Enemy(9, 10)
        front.hp = rear.hp = 100
        g.mobs = [front, rear]
        g._execute_skill_or_spell(item, 13, 10.5)
        self.assertLess(front.hp, 100)
        self.assertEqual(rear.hp, 100)
        front.hp = 100
        d.grid[10][11] = 1
        g._execute_skill_or_spell(item, 13, 10.5)
        self.assertEqual(front.hp, 100)

    def test_equipped_weapon_raises_a_physical_skill_above_its_normal_hit(self):
        d = empty_dungeon()
        d._carve_rect(pygame.Rect(5, 5, 20, 20), 0)
        game = HeadlessGame(d)
        weapon = game.make_item("rusty_dagger", rarity="legendary")
        game.player.equipment["right_hand"] = weapon
        item = Item("heavy_strike", dict(game.loc["perks"]["heavy_strike"], type="combat_skill"))
        enemy = Enemy(11, 10)
        enemy.hp = enemy.max_hp = 250
        enemy.phys_def = 3
        game.mobs = [enemy]

        game._execute_skill_or_spell(item, enemy.x, enemy.y)

        normal_max = game.player.melee_damage_range()[1] - max(0, enemy.phys_def - weapon.armor_pierce)
        self.assertGreater(250 - enemy.hp, normal_max)


class RedesignTests(unittest.TestCase):
    def make_game(self):
        d = empty_dungeon()
        d._carve_rect(pygame.Rect(5, 5, 20, 20), 0)
        return HeadlessGame(d)

    def cast(self, g, key, x=15.5, y=10.5):
        item = Item(key, dict(g.loc["perks"][key], type="combat_skill"))
        g._execute_skill_or_spell(item, x, y)
        return item

    def test_four_slots_and_no_passives_and_all_rarities(self):
        g = self.make_game()
        self.assertEqual(len(g.player.ability_slots), 4)
        self.assertFalse(g._is_perk_eligible("old", dict(type="passive")))
        for k in ("whirlwind", "heavy_strike", "throw_knife", "poison_flask"):
            g.player.apply_perk(k, g.loc["perks"])
        self.assertTrue(all(g.player.ability_slots))
        self.assertFalse(
            g._is_perk_eligible("earth_slam", g.loc["perks"]["earth_slam"])
        )
        for rarity in Item.RARITY_ORDER:
            h = self.make_game()
            v = dict(h.loc["perks"]["throw_knife"], rarity=rarity, id="throw_knife")
            h.levelup_choices = dict(choices=[v], lock_timer=0)
            h.select_perk_choice(0)
            self.assertEqual(h.player.ability_slots[0].rarity, rarity)
            self.assertEqual(h.player.passive_perks, {})

    def test_knife_requires_travel_and_walls_stop_it(self):
        from elenor.game.physical import update_physical

        for wall in (False, True):
            g = self.make_game()
            m = Enemy(14, 10)
            m.hp = 100
            g.mobs = [m]
            if wall:
                g.dungeon.grid[10][12] = 1
            self.cast(g, "throw_knife")
            self.assertEqual(m.hp, 100)
            update_physical(g, 0.05)
            self.assertEqual(m.hp, 100)
            for _ in range(20):
                update_physical(g, 0.05)
            self.assertEqual(m.hp == 100, wall)

    def test_flask_travels_then_creates_poison_cloud(self):
        from elenor.game.physical import update_physical

        g = self.make_game()
        self.cast(g, "poison_flask")
        g.fx.add_gas_cloud.assert_not_called()
        update_physical(g, 0.05)
        g.fx.add_gas_cloud.assert_not_called()
        for _ in range(30):
            update_physical(g, 0.05)
        g.fx.add_gas_cloud.assert_called_once()
        self.assertEqual(g.fx.add_gas_cloud.call_args.kwargs["kind"], "poison")

    def test_trap_hits_once_and_guard_does_not_heal(self):
        from elenor.game.physical import update_physical

        g = self.make_game()
        m = Enemy(10, 10)
        m.hp = 100
        g.mobs = [m]
        self.cast(g, "fan_blades")
        update_physical(g, 0.2)
        self.assertEqual(m.hp, 100)
        update_physical(g, 0.3)
        health = m.hp
        self.assertLess(health, 100)
        update_physical(g, 0.5)
        self.assertEqual(m.hp, health)
        hp = g.player.hp
        self.cast(g, "shield_bash")
        self.assertEqual(g.player.hp, hp)
        self.assertGreater(g.player.guard_timer, 0)

    def test_sokrusenie_uses_direction_not_precise_cursor(self):
        g = self.make_game()
        front = Enemy(12, 10)
        rear = Enemy(9, 10)
        front.hp = rear.hp = 100
        g.mobs = [front, rear]
        self.cast(g, "heavy_strike", 25, 10.5)
        self.assertLess(front.hp, 100)
        self.assertEqual(rear.hp, 100)

    def test_motion_cannot_cross_wall(self):
        from elenor.game.physical import update_physical

        g = self.make_game()
        g.dungeon.grid[10][11] = 1
        self.cast(g, "hamstring")
        for _ in range(10):
            update_physical(g, 0.03)
        self.assertLess(g.player.x, 11)

    def test_every_new_effect_renders(self):
        import numpy as np
        from elenor.rendering.physical import render_physical

        g = self.make_game()
        for k, v in g.loc["perks"].items():
            if v.get("skill_kind") == "combat":
                self.cast(g, k)
        canvas = pygame.Surface((1920, 832), pygame.SRCALPHA)
        render_physical(canvas, g, 0, 0, np.ones((480, 208)))
        self.assertTrue(pygame.surfarray.array_alpha(canvas).any())

    def test_guard_reduces_damage_and_stealth_is_temporary(self):
        from unittest.mock import patch
        g=self.make_game();g.player.hp=100
        with patch('elenor.game.combat.random.random',return_value=.99):
            g.on_player_hit(10);baseline=100-g.player.hp
            g.player.hp=100;self.cast(g,'shield_bash');g.on_player_hit(10)
        self.assertLess(100-g.player.hp,baseline)
        self.cast(g,'venom_strike');self.assertGreater(g.player.stealth_timer,0)
        g.player.update_timers(10);self.assertEqual(g.player.stealth_timer,0)

    def test_poison_cloud_deals_no_damage_through_wall(self):
        from elenor.rendering.effects import FXManager
        g=self.make_game();g.fx=FXManager(g)
        m=Enemy(12,10);m.hp=100;g.mobs=[m]
        g.dungeon.grid[10][11]=1
        g.fx.add_gas_cloud(10.5,10.5,radius=3,duration=3,kind='poison',dmg=3)
        g.fx.active_clouds[-1]['growth_credit']={'action':('cunning',.3),'awarded':False}
        g.fx.update(.1,g.player,g.dungeon,g.mobs,g.add_popup)
        self.assertEqual(m.hp,100)
        g.dungeon.grid[10][11]=0
        g.fx.update(.7,g.player,g.dungeon,g.mobs,g.add_popup)
        self.assertLess(m.hp,100)
