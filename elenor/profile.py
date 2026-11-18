from elenor.paths import PROJECT_ROOT
import json
import os
import pygame
from elenor.config import SCREEN_W, SCREEN_H


def get_profile_dir():
    # Храним сейвы в системной папке пользователя (%APPDATA%/RatCellar), отдельно от кода игры!
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    save_dir = os.path.join(appdata, "RatCellar")
    os.makedirs(save_dir, exist_ok=True)
    return save_dir


def get_profile_path():
    return os.path.join(get_profile_dir(), "save_profile.json")


WINDOW_MODES_LIST = [
    ("windowed",   "В окне"),
    ("borderless", "Без рамки (Оконный)"),
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
    try:
        sizes = pygame.display.get_desktop_sizes()
        max_w, max_h = sizes[0]
    except Exception:
        info = pygame.display.Info()
        max_w = getattr(info, "current_w", 1920) or 1920
        max_h = getattr(info, "current_h", 1080) or 1080

    filtered = [r for r in ALL_SUPPORTED_RESOLUTIONS if r[0] <= max_w and r[1] <= max_h]
    return filtered if filtered else [(1280, 720, "1280 x 720 (HD 16:9)")]

RESOLUTIONS_LIST = ALL_SUPPORTED_RESOLUTIONS

DEFAULT_PROFILE = {
    "bank_copper": 0,
    "rat_king_defeated": False,
    "hero_type": "male",
    "skin_idx": 0,
    "head_idx": 0,
    "outfit_idx": 0,
    "volume": 0.85,
    "typewriter_mode": 1,
    "thought_freq_mode": 2,
    "show_minimap": True,
    "window_mode": "windowed",
    "resolution_idx": 0,
    "fullscreen": False,
}


def load_profile():
    path = get_profile_path()
    legacy_path = os.path.join(str(PROJECT_ROOT), "save_profile.json")
    prof = dict(DEFAULT_PROFILE)

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
    return prof


def save_profile(prof):
    path = get_profile_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(prof, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def reset_profile_progress(prof):
    keep_keys = (
        "volume", "typewriter_mode", "thought_freq_mode", "show_minimap",
        "window_mode", "resolution_idx", "fullscreen",
    )
    saved_settings = {k: prof.get(k, DEFAULT_PROFILE[k]) for k in keep_keys}
    prof.clear()
    prof.update(DEFAULT_PROFILE)
    prof.update(saved_settings)
    save_profile(prof)


def apply_display_mode(prof, game=None):
    """
    Применяет выбранное разрешение и режим (В окне / Без рамки / Полный экран)
    с принудительным Nearest-Neighbor масштабированием без размытия пикселей!
    """
    os.environ["SDL_RENDER_SCALE_QUALITY"] = "0"
    os.environ["SDL_VIDEO_CENTERED"] = "1"

    w_mode = prof.get("window_mode", "windowed")
    avail = get_available_resolutions()
    r_idx = int(prof.get("resolution_idx", 0))
    if r_idx >= len(avail):
        r_idx = 0
        prof["resolution_idx"] = 0
    target_w, target_h, _ = avail[r_idx]

    flags = 0
    if w_mode == "borderless":
        flags = pygame.NOFRAME
    elif w_mode == "fullscreen":
        flags = pygame.FULLSCREEN

    try:
        disp_surf = pygame.display.set_mode((target_w, target_h), flags, vsync=1)
    except Exception:
        try:
            disp_surf = pygame.display.set_mode((target_w, target_h), flags)
        except Exception:
            disp_surf = pygame.display.set_mode((SCREEN_W, SCREEN_H))

    real_w, real_h = disp_surf.get_size()
    # Считаем вписывание 1152x858 в реальное окно с сохранением пропорций (чёткие пиксели без мыла!)
    scale_factor = min(real_w / float(SCREEN_W), real_h / float(SCREEN_H))
    scaled_w = max(1, int(round(SCREEN_W * scale_factor)))
    scaled_h = max(1, int(round(SCREEN_H * scale_factor)))
    off_x = (real_w - scaled_w) // 2
    off_y = (real_h - scaled_h) // 2

    if game is not None:
        game.display_surface = disp_surf
        game.viewport_rect = (off_x, off_y, scaled_w, scaled_h)
    return disp_surf, (off_x, off_y, scaled_w, scaled_h)


def map_window_to_logical(pos, viewport_rect):
    """Переводит физические координаты мыши окна в логические координаты игры (1152x858)."""
    ox, oy, sw, sh = viewport_rect
    lx = int((pos[0] - ox) * SCREEN_W / max(1, sw))
    ly = int((pos[1] - oy) * SCREEN_H / max(1, sh))
    return (max(0, min(SCREEN_W - 1, lx)), max(0, min(SCREEN_H - 1, ly)))


def present_logical_canvas(display_surf, logical_surf, viewport_rect):
    """Выводит логический холст 1152x858 на экран с бритвенно-резким Nearest-Neighbor скейлом."""
    ox, oy, sw, sh = viewport_rect
    if sw == SCREEN_W and sh == SCREEN_H and ox == 0 and oy == 0:
        display_surf.blit(logical_surf, (0, 0))
    else:
        display_surf.fill((8, 6, 12))
        # pygame.transform.scale всегда использует строгий Nearest-Neighbor без билинейного мыла!
        sharp_scaled = pygame.transform.scale(logical_surf, (sw, sh))
        display_surf.blit(sharp_scaled, (ox, oy))


