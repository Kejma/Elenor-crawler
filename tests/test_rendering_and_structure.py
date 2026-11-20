from collections import deque
import importlib
import os
import pkgutil
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, call, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import numpy as np
import pygame
import elenor
from elenor.config import VIEW_W, VIEW_H, CANVAS_H, SCALE, SCREEN_H, SCREEN_W
from elenor.rendering.visibility import overlay_visibility, mask_overlay
from elenor.rendering.mirrors import render_mirror_puzzles_beams
from elenor.profile import apply_display_mode, present_logical_canvas, reset_profile_progress, resolution_index
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
            direct_gl=True,
        )
        with patch("elenor.profile.save_profile"):
            reset_profile_progress(profile)
        self.assertEqual(profile["bank_copper"], 0)
        self.assertFalse(profile["rat_king_defeated"])
        self.assertEqual(profile["window_mode"], "borderless")
        self.assertEqual(profile["resolution_idx"], 3)
        self.assertNotIn("direct_gl", profile)

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

    def test_windowed_modes_keep_the_requested_client_resolution(self):
        from elenor.profile import _display_window_spec

        for target, desktop in (
            ((2560, 1440), (2560, 1440)),
            ((2560, 1440), (3840, 2160)),
            ((3840, 2160), (3840, 2160)),
        ):
            with self.subTest(target=target, desktop=desktop):
                self.assertEqual(_display_window_spec("windowed", target, desktop), (target, 0))
                self.assertEqual(_display_window_spec("borderless", target, desktop), (target, pygame.NOFRAME))
                self.assertEqual(_display_window_spec("fullscreen", target, desktop), (desktop, pygame.NOFRAME))

    def test_unavailable_direct_gl_recovers_software_window(self):
        profile = {}
        renderer = Mock(gpu_shader=None)
        game = SimpleNamespace(renderer=renderer, gl_window=None)
        display = pygame.Surface((1280, 720))
        with (
            patch("elenor.profile.get_available_resolutions", return_value=[(1280, 720, "")]),
            patch("elenor.profile._open_gl_window", side_effect=pygame.error("no GL")),
            patch("pygame.display.set_mode", return_value=display),
            patch("pygame.display.quit"),
            patch("pygame.display.init"),
            patch("pygame.display.set_caption"),
        ):
            apply_display_mode(profile, game)
        self.assertIs(game.display_surface, display)
        self.assertIsNone(game.gl_window)
        renderer.init_standalone_shader.assert_called_once()

    def test_old_profile_cannot_disable_default_opengl_output(self):
        from elenor.profile import load_profile, save_profile

        renderer = Mock(gpu_shader=None)
        game = SimpleNamespace(renderer=renderer, gl_window=None)
        display = pygame.Surface((1280, 720))
        gl_window = Mock()
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "save_profile.json")
            with open(path, "w", encoding="utf-8") as file:
                file.write('{"direct_gl": false, "volume": 0.42}')
            with (
                patch("elenor.profile.get_profile_path", return_value=path),
                patch("elenor.profile.get_available_resolutions", return_value=[(1280, 720, "")]),
                patch("elenor.profile._open_gl_window", return_value=(display, gl_window)) as open_gl,
                patch("pygame.display.set_caption"),
            ):
                profile = load_profile()
                apply_display_mode(profile, game)
                save_profile(profile)
            with open(path, encoding="utf-8") as file:
                self.assertNotIn("direct_gl", file.read())
        open_gl.assert_called_once()
        self.assertEqual(profile["volume"], 0.42)
        self.assertIs(game.gl_window, gl_window)
        self.assertIs(renderer.gpu_shader, gl_window.shader)

    def test_window_exploration_does_not_read_an_unfinished_gpu_transfer(self):
        from elenor.rendering import window

        presenter = window.GLWindow.__new__(window.GLWindow)
        dungeon = SimpleNamespace(geometry_revision=3)
        presenter.thought_location = dungeon
        presenter.fences = Mock()
        presenter.fences.ready.return_value = False
        data = np.zeros((window._PROBE_SIZE[1], window._PROBE_WIDTH, 4), np.uint8)
        data[2, 1, 0] = 255
        data[-1, 0, :3] = (24, 42, 61)
        slot = SimpleNamespace(fence=1, buffer=Mock(), timed=False,
                               survey=(dungeon, 3, (4, 5), frozenset({(5, 7)}), ()))
        slot.buffer.read.return_value = data.tobytes()
        presenter.pending = deque([slot])
        with patch.object(window, "remember_tiles") as remember:
            presenter.collect(dungeon)
            slot.buffer.read.assert_not_called()
            remember.assert_not_called()
            presenter.fences.ready.return_value = True
            presenter.collect(dungeon)
            remember.assert_called_once_with(dungeon, {(5, 7)}, ())
        self.assertEqual(presenter.thought_color, (24, 42, 61))
        self.assertFalse(presenter.pending)

    def test_ui_upload_retains_hud_until_a_menu_overwrites_it(self):
        from elenor.rendering import window

        ctx = MagicMock()
        viewport = (0, 0, SCREEN_W, SCREEN_H)
        ctx.screen.size = (SCREEN_W, SCREEN_H)
        with patch.object(window, "_Fences"):
            presenter = window.GLWindow(ctx, Mock(), Mock())
        hud = object()
        for gameplay in (True, True, False, True, True):
            presenter.begin_ui_frame()
            presenter.hud_surface = hud
            presenter.present(viewport, ctx.screen.size, gameplay)

        # First frame, menu and the return to the game each replace the texture.
        self.assertEqual(presenter.ui.write.call_args_list, [call(presenter.ui_pixels)] * 3)

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
                def use_or_equip_item(self, item, *args, **kwargs):
                    calls.append(item.id)

            configure_display = loop.apply_display_mode

            def configure_and_post_input(profile, game):
                configure_display(profile, game)
                for key in (pygame.K_q, pygame.K_e, pygame.K_r, pygame.K_f):
                    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))
                pygame.event.post(
                    pygame.event.Event(
                        pygame.MOUSEBUTTONDOWN, button=3, pos=(500, 200)
                    )
                )

            original = loop.present_logical_canvas

            def present(*args):
                original(*args)
                pygame.event.post(pygame.event.Event(pygame.QUIT))

            with (
                patch.object(loop, "GameController", KeyGame),
                patch.object(loop, "apply_display_mode", configure_and_post_input),
                patch.object(loop, "present_logical_canvas", present),
            ):
                loop.main()
            self.assertEqual(
                calls, ["whirlwind", "heavy_strike", "throw_knife", "poison_flask"]
            )
