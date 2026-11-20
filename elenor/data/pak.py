import json
import lzma
import os

from elenor.paths import PROJECT_ROOT

PACK_FILENAME = "data.epk"
_PACK_CACHE = False


def get_pack_path():
    return os.path.join(str(PROJECT_ROOT), PACK_FILENAME)


def get_pack():
    global _PACK_CACHE
    if _PACK_CACHE is False:
        path = get_pack_path()
        if os.path.isfile(path):
            try:
                with open(path, "rb") as f:
                    raw = lzma.decompress(f.read())
                _PACK_CACHE = json.loads(raw.decode("utf-8"))
            except Exception as exc:
                print(f"[PAK] Не удалось прочитать {PACK_FILENAME}: {exc}")
                _PACK_CACHE = None
        else:
            _PACK_CACHE = None
    return _PACK_CACHE


def has_pack():
    return get_pack() is not None


def get_pack_manifest():
    pack = get_pack()
    return pack.get("manifest") if pack else None


def get_pack_dtex(rel_path):
    pack = get_pack()
    if not pack:
        return None
    norm = rel_path.replace("\\", "/")
    return pack.get("dtex", {}).get(norm)


def get_pack_music(filename):
    pack = get_pack()
    if not pack:
        return None
    return pack.get("music", {}).get(os.path.basename(filename))