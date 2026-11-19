import importlib
import os
import pkgutil
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import numpy as np
import pygame
import elenor
from elenor.config import VIEW_W, VIEW_H, CANVAS_H, SCALE
from elenor.rendering.visibility import overlay_visibility, mask_overlay
from elenor.rendering.mirrors import render_mirror_puzzles_beams
from elenor.profile import present_logical_canvas, reset_profile_progress, resolution_index
from elenor.paths import PROJECT_ROOT


class RenderingTests(unittest.TestCase):
    def test_all_modules_import_from_another_working_directory(self):
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as folder:
            try:
                os.chdir(folder)
                for module in pkgutil.walk_packages(elenor.__path__, "elenor."):
                    importlib.import_module(module.name)
                from elenor.localization import load_modular_locales

                self.assertIn("focusing_lens", load_modular_locales()["items"])
                from elenor.data.textures import get_assets_root

                self.assertEqual(get_assets_root(), str(PROJECT_ROOT / "assets"))
            finally:
                os.chdir(previous)

    def test_profile_reset_keeps_display_settings(self):
        profile = dict(
            bank_copper=200,
            rat_king_defeated=True,
            window_mode="borderless",
            resolution_idx=3,
        )
        with patch("elenor.profile.save_profile"):
            reset_profile_progress(profile)
        self.assertEqual(profile["bank_copper"], 0)
        self.assertFalse(profile["rat_king_defeated"])
        self.assertEqual(profile["window_mode"], "borderless")
        self.assertEqual(profile["resolution_idx"], 3)

    def test_default_resolution_and_software_scaling(self):
        available = [(3840, 2160, ""), (2560, 1440, ""), (1920, 1080, ""), (1280, 720, "")]
        self.assertEqual(resolution_index({"resolution_idx": None}, available), 2)
        self.assertEqual(resolution_index({"resolution_idx": 0}, available), 0)
        source = pygame.Surface((8, 4))
        source.fill((10, 20, 30))
        source.fill((100, 20, 30), (2, 2, 3, 2))
        destination = pygame.Surface((20, 14))
        present_logical_canvas(destination, source, (2, 2, 16, 8))
        expected = pygame.Surface(destination.get_size())
        expected.fill((8, 6, 12))
        expected.blit(pygame.transform.scale(source, (16, 8)), (2, 2))
        self.assertEqual(pygame.image.tobytes(destination, "RGB"), pygame.image.tobytes(expected, "RGB"))

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
        surface = pygame.Surface((VIEW_W * SCALE, VIEW_H * SCALE), pygame.SRCALPHA)
        surface.fill((255, 40, 40, 200))
        mask_overlay(surface, mask, cache)
        self.assertEqual(surface.get_at((5 * SCALE, 40 * SCALE)).a, 0)
        self.assertEqual(surface.get_at((85 * SCALE, 40 * SCALE)).a, 0)
        self.assertGreater(
            surface.get_at((40 * SCALE, 40 * SCALE)).a,
            surface.get_at((75 * SCALE, 40 * SCALE)).a,
        )
        previous = cache["_visibility_scaled"]
        mask_overlay(surface, mask, cache)
        self.assertIs(previous, cache["_visibility_scaled"])

    def test_visible_beam_middle_does_not_require_visible_source_or_endpoint(self):
        ctrl = SimpleNamespace(
            emitter_state="ready",
            emitters=[],
            mirrors=[],
            hit_points=[],
            beam_segments=[((1.5, 4.5), (20.5, 4.5), (1, 0), (255, 45, 55))],
        )
        game = SimpleNamespace(mirror_puzzles=[ctrl])
        screen = pygame.Surface((VIEW_W * SCALE, VIEW_H * SCALE))
        screen.fill((0, 0, 0))
        mask = np.zeros((VIEW_W, VIEW_H), dtype=np.float32)
        mask[100:160] = 1
        render_mirror_puzzles_beams(screen, game, 0, 0, {(8, 4)}, mask)
        rgb = pygame.surfarray.array3d(screen)
        self.assertTrue(rgb[100 * SCALE : 160 * SCALE].any())
        self.assertFalse(rgb[: 100 * SCALE].any())
        self.assertFalse(rgb[160 * SCALE :].any())

    def test_real_game_loop_renders_puzzle_inventory_and_journal(self):
        from elenor.game import loop
        from elenor.game.controller import GameController

        with (
            tempfile.TemporaryDirectory() as profile_dir,
            patch.dict(os.environ, APPDATA=profile_dir),
        ):
            frames = []
            games = []

            class SmokeGame(GameController):
                def __init__(self):
                    super().__init__()
                    for _ in range(3):
                        self.descend_to_next_floor()
                    self.in_main_menu = False
                    self.world_active = True
                    self.player.x, self.player.y = self.mirror_puzzles[
                        0
                    ].room_rect.center
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

            with (
                patch.object(loop, "GameController", SmokeGame),
                patch.object(loop, "present_logical_canvas", render_frame),
            ):
                loop.main()
            self.assertEqual(len(frames), 4)

    def test_text_cache_is_bounded_and_keys_include_font_and_width(self):
        from elenor.ui.text import wrap_lines

        pygame.font.init()
        font = pygame.font.Font(None, 20)
        wrap_lines.cache_clear()
        first = wrap_lines("a sentence with several words", font, 60)
        self.assertIs(first, wrap_lines("a sentence with several words", font, 60))
        self.assertNotEqual(
            first, wrap_lines("a sentence with several words", font, 300)
        )
        for i in range(300):
            wrap_lines(str(i), font, 60)
        self.assertLessEqual(wrap_lines.cache_info().currsize, 256)

    def test_keyboard_routes_four_slots_and_right_click_does_not_cast(self):
        from elenor.game import loop
        from elenor.game.controller import GameController

        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict(os.environ, APPDATA=folder),
        ):
            calls = []

            class KeyGame(GameController):
                def __init__(self):
                    super().__init__()
                    self.in_main_menu = False
                    self.player.god_mode = True
                    for key in (
                        "whirlwind",
                        "heavy_strike",
                        "throw_knife",
                        "poison_flask",
                    ):
                        self.player.apply_perk(key, self.loc["perks"])
                    for key in (pygame.K_q, pygame.K_e, pygame.K_r, pygame.K_f):
                        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))
                    pygame.event.post(
                        pygame.event.Event(
                            pygame.MOUSEBUTTONDOWN, button=3, pos=(500, 200)
                        )
                    )

                def use_or_equip_item(self, item, *args, **kwargs):
                    calls.append(item.id)

            original = loop.present_logical_canvas

            def present(*args):
                original(*args)
                pygame.event.post(pygame.event.Event(pygame.QUIT))

            with (
                patch.object(loop, "GameController", KeyGame),
                patch.object(loop, "present_logical_canvas", present),
            ):
                loop.main()
            self.assertEqual(
                calls, ["whirlwind", "heavy_strike", "throw_knife", "poison_flask"]
            )
