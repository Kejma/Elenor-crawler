"""Read and write the clipboard through the SDL video backend used by pygame."""

import ctypes
from functools import lru_cache
from pathlib import Path
import sys

import pygame
import pygame.base


@lru_cache(maxsize=1)
def _clipboard_sdl():
    # POSIX resolves SDL symbols through the loaded extension's dependencies.
    # On Windows the pygame wheel contains SDL2.dll alongside that extension.
    path = Path(pygame.base.__file__)
    if sys.platform == "win32":
        path = path.with_name("SDL2.dll")
    try:
        sdl = ctypes.CDLL(str(path))
        sdl.SDL_SetClipboardText.argtypes = [ctypes.c_char_p]
        sdl.SDL_SetClipboardText.restype = ctypes.c_int
        sdl.SDL_GetClipboardText.argtypes = []
        sdl.SDL_GetClipboardText.restype = ctypes.c_void_p
        sdl.SDL_free.argtypes = [ctypes.c_void_p]
        sdl.SDL_free.restype = None
    except (OSError, AttributeError):
        return None
    return sdl


def copy_text(text):
    data = text.encode("utf-8")
    sdl = _clipboard_sdl()
    if sdl is not None and sdl.SDL_SetClipboardText(data) == 0:
        return True
    try:
        if not pygame.scrap.get_init():
            pygame.scrap.init()
        pygame.scrap.set_mode(pygame.SCRAP_CLIPBOARD)
        pygame.scrap.put(pygame.SCRAP_TEXT, data + b"\x00")
    except pygame.error:
        return False
    return True


def paste_text():
    sdl = _clipboard_sdl()
    if sdl is not None:
        text = sdl.SDL_GetClipboardText()
        if not text:
            return ""
        try:
            return ctypes.string_at(text).decode("utf-8", errors="replace")
        finally:
            sdl.SDL_free(text)
    try:
        if not pygame.scrap.get_init():
            pygame.scrap.init()
        pygame.scrap.set_mode(pygame.SCRAP_CLIPBOARD)
        data = pygame.scrap.get(pygame.SCRAP_TEXT)
        return data.decode("utf-8", errors="replace").rstrip("\x00") if data else ""
    except pygame.error:
        return ""
