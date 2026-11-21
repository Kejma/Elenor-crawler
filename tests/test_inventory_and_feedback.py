import unittest
from unittest.mock import Mock, patch

import numpy as np
import pygame

from elenor.audio.voices import VOICES, enemy_voice_waves
from elenor.config import COIN_TEXT_COLOR, SCREEN_H, SCREEN_W, SCALE, VIEW_H
from elenor.data.items import BAG_CAPACITIES
from elenor.entities import Enemy, Interactable
from elenor.entities.enemies import MOB_PROFILES
from elenor.rendering.visibility import CanopyVisibility, canopy_opacity
from elenor.ui.renderer import UIRendererMixin
from test_mirror_puzzles import HeadlessGame, empty_dungeon


class InventoryFeedbackTests(unittest.TestCase):
    def setUp(self):
        dungeon = empty_dungeon()
        dungeon._carve_rect(pygame.Rect(5, 5, 20, 20), 0)
        self.game = HeadlessGame(dungeon)
        self.player = self.game.player

    def test_all_world_coin_cards_are_gold_and_above_the_thought_strip(self):
        font_was_ready = pygame.font.get_init()
        pygame.font.init()
        try:
            ui = UIRendererMixin()
            ui.font_ui = ui.font_small = pygame.font.Font(None, 14)
            ui.draw_pixel_frame = Mock()
            ui.wrap_text = lambda text, font, width: [text]
            screen = pygame.Surface((SCREEN_W, SCREEN_H))
            for denom in ("copper", "silver", "gold", "platinum"):
                coin = self.game.make_item(f"coin_{denom}")
                lines = ui._build_item_stat_lines(self.player, coin, self.game.loc["ui"])
                self.assertEqual({color for _, color in lines}, {COIN_TEXT_COLOR})
                ui._render_item_tooltip(screen, self.player, coin, self.game.loc["ui"], (800, 200), world_item=True)
                x, y, _, height = ui.draw_pixel_frame.call_args.args[1]
                self.assertEqual(x, 16)
                self.assertEqual(y + height, VIEW_H * SCALE - 16)
        finally:
            if not font_was_ready:
                pygame.font.quit()

    def test_bag_slots_stack_and_two_best_bags_maximize_capacity(self):
        capacities = sorted(BAG_CAPACITIES.values())
        self.assertTrue(set(range(2, 10)).issubset(capacities))
        for index in range(2):
            bag = self.game.make_item("small_pouch")
            loot = Interactable(10, 10, "loot", bag)
            self.game._pickup_loot_object(loot)
            self.assertTrue(loot.used)
            self.assertIs(self.player.bag_slots[index], bag)
        self.assertEqual(self.player.unlocked_slots, self.player.pocket_slots + 4)

        best = self.game.make_item("void_chest_bag")
        self.assertTrue(self.player.change_bag(0, best))
        self.assertLess(self.player.unlocked_slots, self.player.max_possible_slots)
        self.assertTrue(self.player.change_bag(1, self.game.make_item("void_chest_bag")))
        self.assertEqual(self.player.unlocked_slots, self.player.pocket_slots + 18)

    def test_full_bag_removal_is_atomic_and_repacking_preserves_hotbar(self):
        bag = self.game.make_item("small_pouch")
        self.assertTrue(self.player.change_bag(0, bag))
        potions = [self.game.make_item("potion_hp") for _ in range(self.player.unlocked_slots)]
        for item in potions:
            self.assertTrue(self.player.add_item_to_inventory(item))
        self.assertFalse(self.player.change_bag(0))
        self.assertFalse(self.player.remove_item_everywhere(bag))
        self.assertEqual(self.player.inventory[:len(potions)], potions)

        # Leave one potion in the highest slot. Taking the bag off moves both
        # the potion and bag to pockets without making a copy.
        for item in potions[:-1]:
            self.player.remove_item_everywhere(item)
        potion = potions[-1]
        self.player.hotbar[0] = potion
        self.assertTrue(self.player.change_bag(0))
        self.assertEqual({item for item in self.player.inventory if item}, {potion, bag})
        self.assertIs(self.player.hotbar[0], potion)
        self.assertTrue(all(item is None for item in self.player.inventory[self.player.unlocked_slots:]))

    def test_quest_items_fit_when_pockets_are_full(self):
        for _ in range(self.player.unlocked_slots):
            self.player.add_item_to_inventory(self.game.make_item("potion_mp"))
        lens = self.game.make_item("focusing_lens")
        self.assertTrue(self.game._pickup_loot_object(Interactable(10, 10, "loot", lens)))
        self.assertIs(self.player.find_quest_item(lens.id), lens)
        self.assertNotIn(lens, self.player.inventory)
        self.player.remove_item_everywhere(lens)
        self.assertIsNone(self.player.find_quest_item(lens.id))

    def test_upgrades_can_roll_before_all_slots_are_filled(self):
        skill = "whirlwind"
        self.player.apply_perk(skill, self.game.loc["perks"])
        with patch("elenor.game.progression.random.random", return_value=0.0):
            self.game.roll_perk_choices()
        first, *others = self.game.levelup_choices["choices"]
        self.assertEqual(first["id"], skill)
        self.assertIn("upgrade_roll", first)
        self.assertTrue(others)
        self.assertTrue(all("upgrade_roll" not in item for item in others))

    def test_surprise_gives_only_a_small_crit_bonus(self):
        chance = self.player.crit_chance
        with patch("elenor.entities.player.random.random", return_value=chance + 0.035):
            self.assertFalse(self.player.roll_physical_crit(chance))
            self.assertTrue(self.player.roll_physical_crit(chance, unaware=True))
        with patch("elenor.entities.player.random.random", return_value=0.9):
            target = Enemy(11, 10, state="patrolling")
            self.game.mobs = [target]
            self.game._execute_melee_swing(target.x, target.y - .22)
            self.assertFalse(target.hit_flash_crit)
            self.assertLess(target.hp, target.max_hp)

    def test_brief_los_spike_only_softly_changes_tree_visibility(self):
        visibility = CanopyVisibility()
        floor = []
        visibility.begin_frame(floor, 0)
        self.assertEqual(visibility.sample((2, 2), 0), 0)
        visibility.begin_frame(floor, .016)
        peak = visibility.sample((2, 2), 1)
        self.assertGreater(peak, 0)
        self.assertLess(peak, .2)
        visibility.begin_frame(floor, .032)
        self.assertLess(visibility.sample((2, 2), 0), peak)
        self.assertTrue(105 < canopy_opacity(2, 2, 1.45, 1.0) < 255)

    def test_every_enemy_has_two_nonempty_voice_samples(self):
        self.assertEqual(set(VOICES), set(MOB_PROFILES))
        waves = list(enemy_voice_waves(22050))
        self.assertEqual(len(waves), 2 * len(VOICES))
        self.assertEqual(len({name for name, _, _ in waves}), len(waves))
        self.assertTrue(all(0.01 < np.max(np.abs(wave)) < 1 for _, wave, _ in waves))
