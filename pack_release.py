import json
import lzma
import os
import sys

from elenor.audio.music import load_song_file, save_song_file
from elenor.data.textures import compact_dtex_dict, get_assets_root
from elenor.paths import PROJECT_ROOT


def _iter_dtex_files(assets_root):
    for dirpath, _, filenames in os.walk(assets_root):
        for fname in sorted(filenames):
            if fname.endswith(".dtex"):
                full = os.path.join(dirpath, fname)
                rel = os.path.relpath(full, assets_root).replace("\\", "/")
                yield full, rel


def _iter_music_files(music_root):
    if not os.path.isdir(music_root):
        return
    for fname in sorted(os.listdir(music_root)):
        if fname.endswith(".json"):
            yield os.path.join(music_root, fname), fname


def shrink_dev_files():
    assets_root = get_assets_root()
    music_root = os.path.join(str(PROJECT_ROOT), "music")

    a_before = a_after = a_cnt = 0
    m_path = os.path.join(assets_root, "manifest.json")
    if os.path.isfile(m_path):
        a_before += os.path.getsize(m_path)
        with open(m_path, "r", encoding="utf-8") as f:
            m_data = json.load(f)
        with open(m_path, "w", encoding="utf-8") as f:
            json.dump(m_data, f, ensure_ascii=False, separators=(",", ":"))
        a_after += os.path.getsize(m_path)

    for full, _ in _iter_dtex_files(assets_root):
        a_before += os.path.getsize(full)
        with open(full, "r", encoding="utf-8") as f:
            data = json.load(f)
        compact = compact_dtex_dict(data)
        with open(full, "w", encoding="utf-8") as f:
            json.dump(compact, f, ensure_ascii=False, separators=(",", ":"))
        a_after += os.path.getsize(full)
        a_cnt += 1

    m_before = m_after = m_cnt = 0
    for full, _ in _iter_music_files(music_root):
        m_before += os.path.getsize(full)
        song = load_song_file(full)
        if song is not None:
            save_song_file(song, full)
        m_after += os.path.getsize(full)
        m_cnt += 1

    print(f"assets/ ({a_cnt} .dtex): {a_before / 1024:.1f} КБ -> {a_after / 1024:.1f} КБ (-{(1 - a_after / max(1, a_before)) * 100:.1f}%)")
    print(f"music/  ({m_cnt} .json): {m_before / 1024:.1f} КБ -> {m_after / 1024:.1f} КБ (-{(1 - m_after / max(1, m_before)) * 100:.1f}%)")
    tot_b = a_before + m_before
    tot_a = a_after + m_after
    print(f"ИТОГО:  {tot_b / 1024:.1f} КБ -> {tot_a / 1024:.1f} КБ (сжатие в {tot_b / max(1, tot_a):.1f}x)")


def build_release_pack():
    assets_root = get_assets_root()
    music_root = os.path.join(str(PROJECT_ROOT), "music")

    raw_total = 0
    manifest = {}
    m_path = os.path.join(assets_root, "manifest.json")
    if os.path.isfile(m_path):
        raw_total += os.path.getsize(m_path)
        with open(m_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    dtex_map = {}
    for full, rel in _iter_dtex_files(assets_root):
        raw_total += os.path.getsize(full)
        with open(full, "r", encoding="utf-8") as f:
            dtex_map[rel] = compact_dtex_dict(json.load(f))

    music_map = {}
    for full, fname in _iter_music_files(music_root):
        raw_total += os.path.getsize(full)
        song = load_song_file(full)
        if song is not None:
            music_map[fname] = song.to_dict()

    bundle = {"manifest": manifest, "dtex": dtex_map, "music": music_map}
    raw_json = json.dumps(bundle, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = lzma.compress(raw_json, format=lzma.FORMAT_XZ, preset=9 | lzma.PRESET_EXTREME)

    out_dir = os.path.join(str(PROJECT_ROOT), "dist_pack")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "data.epk")
    with open(out_path, "wb") as f:
        f.write(compressed)

    print(f"Упаковано: {len(dtex_map)} текстур + {len(music_map)} треков")
    print(f"Исходный вес на диске: {raw_total / 1024:.1f} КБ")
    print(f"Вес dist_pack/data.epk: {len(compressed) / 1024:.1f} КБ (сжатие в {raw_total / max(1, len(compressed)):.1f}x!)")
    print("\nКоманда сборки релизного билда (без редакторов, tkinter и сырых папок assets/music):")
    print(
        'pyinstaller --noconfirm --windowed --name Elenor '
        '--add-data "dist_pack/data.epk;." '
        '--add-data "locales;locales" '
        '--exclude-module tkinter '
        '--exclude-module elenor.tools.music_studio '
        '--exclude-module elenor.tools.texture_studio '
        '--exclude-module elenor.tools.balance '
        '--exclude-module elenor.tools.balance_audit '
        'main.py'
    )


if __name__ == "__main__":
    if "--shrink-dev" in sys.argv:
        shrink_dev_files()
    else:
        build_release_pack()