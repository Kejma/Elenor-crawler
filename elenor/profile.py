from elenor.paths import PROJECT_ROOT
import json
import os
import sys
import pygame
from elenor.config import SCREEN_W, SCREEN_H

_DPI_ENABLED = False
_DESKTOP_SIZE = None


def enable_dpi_awareness():
    global _DPI_ENABLED
    if _DPI_ENABLED or sys.platform != "win32":
        return
    _DPI_ENABLED = True
    try:
        import ctypes
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def get_desktop_size():
    global _DESKTOP_SIZE
    if _DESKTOP_SIZE is not None:
        return _DESKTOP_SIZE
    try:
        sizes = pygame.display.get_desktop_sizes()
        if sizes and sizes[0][0] > 0 and sizes[0][1] > 0:
            _DESKTOP_SIZE = tuple(sizes[0])
            return _DESKTOP_SIZE
    except Exception:
        pass
    info = pygame.display.Info()
    max_w = getattr(info, "current_w", 0) or 1920
    max_h = getattr(info, "current_h", 0) or 1080
    _DESKTOP_SIZE = (max_w, max_h)
    return _DESKTOP_SIZE


def get_profile_dir():
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    save_dir = os.path.join(appdata, "RatCellar")
    os.makedirs(save_dir, exist_ok=True)
    return save_dir


def get_profile_path():
    return os.path.join(get_profile_dir(), "save_profile.json")


WINDOW_MODES_LIST = [
    ("windowed",   "В окне"),
    ("borderless", "Без рамки (На весь экран)"),
    ("fullscreen", "Полный экран"),
]

ALL_SUPPORTED_RESOLUTIONS = [
    (3840, 2160, "3840 x 2160 (4K UHD — Целочисленное x2)"),
    (2560, 1440, "2560 x 1440 (2K QHD 16:9)"),
    (1920, 1080, "1920 x 1080 (Full HD — Родное x1)"),
    (1600, 900,  "1600 x 900 (HD+ 16:9)"),
    (1366, 768,  "1366 x 768 (Ноутбук 16:9)"),
    (1280, 720,  "1280 x 720 (HD 16:9)"),
]


def get_available_resolutions():
    max_w, max_h = get_desktop_size()
    filtered = [r for r in ALL_SUPPORTED_RESOLUTIONS if r[0] <= max_w and r[1] <= max_h]
    return filtered if filtered else [(1280, 720, "1280 x 720 (HD 16:9)")]


RESOLUTIONS_LIST = ALL_SUPPORTED_RESOLUTIONS

DEFAULT_PROFILE = {
    "bank_copper": 0,
    "rat_king_defeated": False,
    "strongbox_level": 0,
    "strongbox_enabled": True,
    "collected_fish": [],
    "collected_paintings": [],
    "hero_type": "male",
    "skin_idx": 0,
    "head_idx": 0,
    "outfit_idx": 0,
    "volume": 0.85,
    "typewriter_mode": 1,
    "thought_freq_mode": 2,
    "show_minimap": True,
    "show_performance": False,
    "window_mode": "windowed",
    "resolution_idx": None,
    "fullscreen": False,
}


def _fresh_default_profile():
    return {k: (list(v) if isinstance(v, list) else v) for k, v in DEFAULT_PROFILE.items()}


def load_profile():
    path = get_profile_path()
    legacy_path = os.path.join(str(PROJECT_ROOT), "save_profile.json")
    prof = _fresh_default_profile()

    if not os.path.isfile(path) and os.path.isfile(legacy_path):
        try:
            with open(legacy_path, "r", encoding="utf-8") as f:
                prof.update(json.load(f))
            save_profile(prof)
        except Exception:
            pass

    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                prof.update(data)
        except Exception:
            pass
    prof.pop("direct_gl", None)  # Legacy display setting.
    return prof


def save_profile(prof):
    path = get_profile_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            data = dict(prof)
            data.pop("direct_gl", None)
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def reset_profile_progress(prof):
    keep_keys = (
        "volume", "typewriter_mode", "thought_freq_mode", "show_minimap", "show_performance",
        "window_mode", "resolution_idx", "fullscreen",
    )
    saved_settings = {k: prof.get(k, DEFAULT_PROFILE[k]) for k in keep_keys}
    prof.clear()
    prof.update(_fresh_default_profile())
    prof.update(saved_settings)
    save_profile(prof)


def resolution_index(profile, available):
    saved = profile.get("resolution_idx")
    if isinstance(saved, int) and 0 <= saved < len(available):
        return saved
    return next((i for i, (w, h, _) in enumerate(available) if w <= SCREEN_W and h <= SCREEN_H), 0)


def _display_window_spec(mode, target, desktop):
    if mode == "fullscreen":
        return target, pygame.FULLSCREEN
    if mode == "borderless":
        return desktop, pygame.NOFRAME
    return target, 0


def apply_display_mode(prof, game=None):
    enable_dpi_awareness()
    os.environ["SDL_RENDER_SCALE_QUALITY"] = "0"
    os.environ["SDL_VIDEO_CENTERED"] = "1"

    w_mode = prof.get("window_mode", "windowed")
    desktop = get_desktop_size()
    avail = get_available_resolutions()
    r_idx = resolution_index(prof, avail)
    prof["resolution_idx"] = r_idx
    prof["fullscreen"] = (w_mode == "fullscreen")
    target = avail[r_idx][:2]
    size, flags = _display_window_spec(w_mode, target, desktop)
    spec = size, flags
    if game is not None and getattr(game, "display_spec", None) == spec:
        return game.display_surface, game.viewport_rect

    gl_window = None
    if game is not None:
        if game.gl_window is not None:
            game.gl_window.collect(game.dungeon)
            game.gl_window.close()
        elif game.renderer.gpu_shader is not None:
            game.renderer.gpu_shader.ctx.release()
        game.gl_window = None
        game.renderer.gpu_shader = None

        if getattr(game, "display_surface", None) is not None:
            game.display_surface = None
            game.display_spec = None
            pygame.display.quit()
            pygame.display.init()
        try:
            disp_surf, gl_window = _open_gl_window(size, flags)
            game.renderer.gpu_shader = gl_window.shader
        except Exception as exc:
            print(f"[GL] Прямой вывод недоступен ({exc}).")
            pygame.display.quit()
            pygame.display.init()
    if gl_window is None:
        try:
            disp_surf = pygame.display.set_mode(size, flags)
        except pygame.error:
            size, flags = _display_window_spec("windowed", (SCREEN_W, SCREEN_H), desktop)
            disp_surf = pygame.display.set_mode(size, flags)
            spec = size, flags
            prof["window_mode"] = "windowed"
            prof["fullscreen"] = False
        if game is not None:
            game.renderer.init_standalone_shader()
    pygame.display.set_caption("Elenor-crawler")

    real_w, real_h = disp_surf.get_size()
    if gl_window is not None:
        gl_window.window_size = (real_w, real_h)
    scale_factor = min(real_w / float(SCREEN_W), real_h / float(SCREEN_H))
    scaled_w = max(1, int(round(SCREEN_W * scale_factor)))
    scaled_h = max(1, int(round(SCREEN_H * scale_factor)))
    off_x = (real_w - scaled_w) // 2
    off_y = (real_h - scaled_h) // 2

    if game is not None:
        game.display_spec = spec
        game.display_surface = disp_surf
        game.gl_window = gl_window
        game.viewport_rect = (off_x, off_y, scaled_w, scaled_h)
    return disp_surf, (off_x, off_y, scaled_w, scaled_h)


def _open_gl_window(size, flags):
    import moderngl
    from _moderngl import DefaultLoader

    from elenor.rendering.lighting import GPULightShader
    from elenor.rendering.window import GLWindow

    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)
    display = pygame.display.set_mode(size, flags | pygame.OPENGL | pygame.DOUBLEBUF, vsync=0)
    loader = DefaultLoader()
    moderngl.init_context(loader)
    ctx = moderngl.get_context()
    try:
        if ctx.version_code < 330:
            raise RuntimeError("OpenGL 3.3 is required")
        return display, GLWindow(ctx, loader, GPULightShader(ctx))
    except Exception:
        ctx.release()
        raise


def map_window_to_logical(pos, viewport_rect):
    """Переводит физические координаты мыши окна в логические координаты игры (1920x1080)."""
    ox, oy, sw, sh = viewport_rect
    lx = int((pos[0] - ox) * SCREEN_W / max(1, sw))
    ly = int((pos[1] - oy) * SCREEN_H / max(1, sh))
    return (max(0, min(SCREEN_W - 1, lx)), max(0, min(SCREEN_H - 1, ly)))


_scaled_canvas = None


def present_logical_canvas(display_surf, logical_surf, viewport_rect):
    """Выводит логический холст 1920x1080 на экран с бритвенно-резким Nearest-Neighbor скейлом."""
    global _scaled_canvas
    ox, oy, sw, sh = viewport_rect
    if sw == SCREEN_W and sh == SCREEN_H and ox == 0 and oy == 0:
        display_surf.blit(logical_surf, (0, 0))
    else:
        width, height = display_surf.get_size()
        bar_color = (8, 6, 12)
        if ox:
            display_surf.fill(bar_color, (0, 0, ox, height))
        if ox + sw < width:
            display_surf.fill(bar_color, (ox + sw, 0, width - ox - sw, height))
        if oy:
            display_surf.fill(bar_color, (ox, 0, sw, oy))
        if oy + sh < height:
            display_surf.fill(bar_color, (ox, oy + sh, sw, height - oy - sh))
        mask = logical_surf.get_masks()
        depth = logical_surf.get_bitsize()
        if display_surf.get_masks() == mask and display_surf.get_bitsize() == depth:
            viewport = display_surf.subsurface((ox, oy, sw, sh))
            pygame.transform.scale(logical_surf, (sw, sh), viewport)
        else:
            if (_scaled_canvas is None or _scaled_canvas.get_size() != (sw, sh)
                    or _scaled_canvas.get_masks() != mask or _scaled_canvas.get_bitsize() != depth):
                _scaled_canvas = pygame.Surface((sw, sh), 0, logical_surf)
            pygame.transform.scale(logical_surf, (sw, sh), _scaled_canvas)
            display_surf.blit(_scaled_canvas, (ox, oy))


