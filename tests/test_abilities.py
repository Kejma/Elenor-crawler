import unittest
from collections import Counter
import pygame
from test_mirror_puzzles import HeadlessGame, empty_dungeon
from elenor.localization import load_modular_locales
from elenor.entities import Item, Enemy
from elenor.rendering.ability_icons import draw_ability_icon


class AbilityTests(unittest.TestCase):
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
