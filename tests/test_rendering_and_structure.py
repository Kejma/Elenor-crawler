import importlib
import os
import pkgutil
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import numpy as np
import pygame
import elenor
from elenor.config import VIEW_W, VIEW_H, CANVAS_H, SCALE
from elenor.rendering.visibility import overlay_visibility, mask_overlay
from elenor.rendering.mirrors import render_mirror_puzzles_beams
from elenor.profile import reset_profile_progress
from elenor.paths import PROJECT_ROOT


class RenderingTests(unittest.TestCase):
    def test_all_modules_import_from_another_working_directory(self):
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as folder:
            try:
                os.chdir(folder)
                for module in pkgutil.walk_packages(elenor.__path__, 'elenor.'):
                    importlib.import_module(module.name)
                from elenor.localization import load_modular_locales
                self.assertIn('focusing_lens', load_modular_locales()['items'])
                from elenor.data.textures import get_assets_root
                self.assertEqual(get_assets_root(), str(PROJECT_ROOT / 'assets'))
            finally:
                os.chdir(previous)

    def test_profile_reset_keeps_display_settings(self):
        profile = dict(bank_copper=200, rat_king_defeated=True, window_mode='borderless', resolution_idx=3)
        with patch('elenor.profile.save_profile'):
            reset_profile_progress(profile)
        self.assertEqual(profile['bank_copper'], 0)
        self.assertFalse(profile['rat_king_defeated'])
        self.assertEqual(profile['window_mode'], 'borderless')
        self.assertEqual(profile['resolution_idx'], 3)

    def test_visibility_masks_occlusion_and_soft_dark_edges(self):
        fov = np.ones((VIEW_W, CANVAS_H), dtype=np.float32)
        fov[0:10] = 0
        lights = [dict(pos=(40, 40, 0), radius=40, color=(1, 1, 1))]
        mask = overlay_visibility(fov, lights, 0, 0)
        self.assertEqual(mask[5, 40], 0)
        self.assertEqual(mask[40, 40], 1)
        self.assertGreater(mask[60, 40], mask[75, 40])
        self.assertEqual(mask[85, 40], 0)
        cache = {}
        surface = pygame.Surface((VIEW_W*SCALE, VIEW_H*SCALE), pygame.SRCALPHA)
        surface.fill((255, 40, 40, 200))
        mask_overlay(surface, mask, cache)
        self.assertEqual(surface.get_at((5*SCALE, 40*SCALE)).a, 0)
        self.assertEqual(surface.get_at((85*SCALE, 40*SCALE)).a, 0)
        self.assertGreater(surface.get_at((40*SCALE, 40*SCALE)).a, surface.get_at((75*SCALE, 40*SCALE)).a)
        previous = cache['_visibility_scaled']
        mask_overlay(surface, mask, cache)
        self.assertIs(previous, cache['_visibility_scaled'])

    def test_visible_beam_middle_does_not_require_visible_source_or_endpoint(self):
        ctrl = SimpleNamespace(emitter_state='ready', emitters=[], mirrors=[], hit_points=[],
                               beam_segments=[((1.5, 4.5), (20.5, 4.5), (1, 0), (255, 45, 55))])
        game = SimpleNamespace(mirror_puzzles=[ctrl])
        screen = pygame.Surface((VIEW_W*SCALE, VIEW_H*SCALE))
        screen.fill((0,0,0))
        mask = np.zeros((VIEW_W, VIEW_H), dtype=np.float32)
        mask[100:160] = 1
        render_mirror_puzzles_beams(screen, game, 0, 0, {(8,4)}, mask)
        rgb = pygame.surfarray.array3d(screen)
        self.assertTrue(rgb[100*SCALE:160*SCALE].any())
        self.assertFalse(rgb[:100*SCALE].any())
        self.assertFalse(rgb[160*SCALE:].any())

    def test_real_game_loop_renders_puzzle_inventory_and_journal(self):
        from elenor.game import loop
        from elenor.game.controller import GameController
        with tempfile.TemporaryDirectory() as profile_dir, patch.dict(os.environ, APPDATA=profile_dir):
            frames = []
            games = []

            class SmokeGame(GameController):
                def __init__(self):
                    super().__init__()
                    for _ in range(3):
                        self.descend_to_next_floor()
                    self.in_main_menu = False
                    self.world_active = True
                    self.player.x, self.player.y = self.mirror_puzzles[0].room_rect.center
                    self.player.god_mode = True
                    games.append(self)

            present = loop.present_logical_canvas

            def render_frame(*args):
                present(*args)
                frames.append(1)
                game = games[0]
                if len(frames) == 1:
                    game.inv_open = True
                elif len(frames) == 2:
                    game.journal_open = True
                elif len(frames) == 3:
                    game.inv_open = False
                    game.in_main_menu = True
                elif len(frames) == 4:
                    pygame.event.post(pygame.event.Event(pygame.QUIT))

            with patch.object(loop, 'GameController', SmokeGame), patch.object(loop, 'present_logical_canvas', render_frame):
                loop.main()
            self.assertEqual(len(frames), 4)

    def test_text_cache_is_bounded_and_keys_include_font_and_width(self):
        from elenor.ui.text import wrap_lines
        pygame.font.init()
        font = pygame.font.Font(None, 20)
        wrap_lines.cache_clear()
        first = wrap_lines('a sentence with several words', font, 60)
        self.assertIs(first, wrap_lines('a sentence with several words', font, 60))
        self.assertNotEqual(first, wrap_lines('a sentence with several words', font, 300))
        for i in range(300):
            wrap_lines(str(i), font, 60)
        self.assertLessEqual(wrap_lines.cache_info().currsize, 256)
