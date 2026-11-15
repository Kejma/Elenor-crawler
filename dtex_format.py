import json
import os
import pygame

PALETTE_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz@#$%&*+=~^"

ASSET_CATALOG = {
    "tiles": {
        "title": "Тайлы окружения (16x16)",
        "items": {
            "floor_0": ("Каменная плита подвала", (16, 16)),
            "floor_2": ("Подземная вода", (16, 16)),
            "floor_3": ("Лесной мох / Трава", (16, 16)),
            "floor_4": ("Дощатый настил таверны", (16, 16)),
            "floor_5": ("Пещерный грунт", (16, 16)),
            "floor_6": ("Лесная дорога", (16, 16)),
            "wall": ("Каменная стена подвала", (16, 16)),
            "wall_wood": ("Бревенчатая стена", (16, 16)),
            "wall_cave": ("Скальный свод пещеры", (16, 16)),
            "tree": ("Вековая ель", (16, 16)),
            "door_closed": ("Дверь (Закрыта)", (16, 16)),
            "door_open": ("Дверь (Открыта)", (16, 16)),
            "door_locked": ("Кованая решётка", (16, 16)),
            "carpet_c": ("Ковёр: Центр", (16, 16)),
            "carpet_n": ("Ковёр: Верх", (16, 16)),
            "carpet_s": ("Ковёр: Низ", (16, 16)),
            "carpet_w": ("Ковёр: Лево", (16, 16)),
            "carpet_e": ("Ковёр: Право", (16, 16)),
            "carpet_nw": ("Ковёр: Угол С-З", (16, 16)),
            "carpet_ne": ("Ковёр: Угол С-В", (16, 16)),
            "carpet_sw": ("Ковёр: Угол Ю-З", (16, 16)),
            "carpet_se": ("Ковёр: Угол Ю-В", (16, 16)),
            "carpet_h": ("Ковёр: Полоса гор.", (16, 16)),
            "carpet_v": ("Ковёр: Полоса верт.", (16, 16)),
            "carpet_single": ("Ковёр: Одиночный", (16, 16)),
        }
    },
    "overlays": {
        "title": "Накладываемые оверлеи (16x16)",
        "items": {
            "ov_pebbles": ("Россыпь камушков", (16, 16)),
            "ov_moss": ("Пятна мха", (16, 16)),
            "ov_cracks": ("Трещины и сколы", (16, 16)),
            "ov_planks_wear": ("Щепки и потёртости", (16, 16)),
        }
    },
    "mobs": {
        "title": "Бестиарий и NPC",
        "items": {
            "rat": ("Погребная крыса", (16, 20)),
            "rat_cultist": ("Две крысы под плащом", (16, 20)),
            "rat_king": ("Крысиный Король (Босс 2x2)", (32, 36)),
            "npc_innkeeper": ("Трактирщик Гуго (NPC)", (16, 20)),
            "wolf": ("Лесной волк", (16, 20)),
            "skeleton": ("Скелет-воин", (16, 20)),
            "cultist": ("Тёмный культист", (16, 20)),
            "necromancer": ("Архи-некромант", (16, 20)),
            "brute": ("Костяной громила", (16, 20)),
        }
    },
    "props": {
        "title": "Объекты данжа и Таверны (16x20)",
        "items": {
            "tavern_table": ("Трактирный стол", (16, 20)),
            "bar_counter": ("Барная стойка", (16, 20)),
            "wine_cask": ("Большая винная бочка", (16, 20)),
            "bed": ("Кровать с тюфяком", (16, 20)),
            "fireplace": ("Каменный камин", (16, 20)),
            "shelf_bottles": ("Полка с бутылками", (16, 20)),
            "chair_bench": ("Деревянная скамья", (16, 20)),
            "coat_rack": ("Вешалка с плащом", (16, 20)),
            "cauldron": ("Котёл с похлёбкой", (16, 20)),
            "woven_rug": ("Домотканый ковёр", (16, 20)),
            "crate_stack": ("Деревянные ящики", (16, 20)),
            "grandfather_clock": ("Напольные часы с маятником", (16, 20)),
            "mounted_boar": ("Трофейная голова вепря", (16, 20)),
            "notice_board": ("Доска заказов и розыска", (16, 20)),
            "lute_stand": ("Забытая лютня барда", (16, 20)),
            "wash_basin": ("Бадья для умывания", (16, 20)),
            "meat_rack": ("Вешала с окороками", (16, 20)),
            "firewood_pile": ("Поленница берёзовых дров", (16, 20)),
            "armor_stand": ("Старый рыцарский доспех", (16, 20)),
            "barrel": ("Винная бочка", (16, 20)),
            "ritual_altar": ("Кровавый алтарь", (16, 20)),
            "chest": ("Сундук с хабаром", (16, 20)),
            "idol": ("Древний идол", (16, 20)),
            "campfire": ("Походный костёр", (16, 20)),
            "brazier": ("Напольная жаровня", (16, 20)),
            "bookshelf": ("Книжный шкаф", (16, 20)),
            "alchemy": ("Алхимический стол", (16, 20)),
            "rack": ("Оружейная стойка", (16, 20)),
            "trap": ("Напольные шипы", (16, 20)),
            "stairs": ("Лестница вниз", (16, 20)),
            "lever_off": ("Рычаг (Выкл)", (16, 20)),
            "lever_on": ("Рычаг (Вкл)", (16, 20)),
            "loot": ("Мешочек с лутом", (16, 20)),
        }
    },
    "hero": {
        "title": "Персонаж (16x20)",
        "items": {
            "hero_base": ("Герой (Базовый)", (16, 20)),
        }
    }
}

DEFAULT_RANDOM_ROT_ROLES = {
    "floor_3", "floor_5", "ov_pebbles", "ov_moss", "ov_cracks", "ov_planks_wear"
}


def get_assets_root():
    return os.path.join(os.path.dirname(__file__), "assets")


def get_manifest_path():
    return os.path.join(get_assets_root(), "manifest.json")


def load_manifest():
    m_path = get_manifest_path()
    if os.path.isfile(m_path):
        try:
            with open(m_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_manifest(manifest_data):
    os.makedirs(get_assets_root(), exist_ok=True)
    with open(get_manifest_path(), "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, ensure_ascii=False, indent=2)


def surface_to_encoded_grid(surf, is_normal=False):
    w, h = surf.get_size()
    color_to_char = {}
    palette = {}
    rows = []

    if not is_normal:
        color_to_char[(0, 0, 0, 0)] = "."
        palette["."] = [0, 0, 0, 0]
    else:
        color_to_char[(128, 128, 255, 255)] = "."
        palette["."] = [128, 128, 255, 255]

    char_idx = 0
    for y in range(h):
        row_str = []
        for x in range(w):
            c = tuple(surf.get_at((x, y)))
            if not is_normal and c[3] == 0:
                c = (0, 0, 0, 0)
            elif is_normal:
                from studio_core import snap_normal_rgb
                sr, sg, sb = snap_normal_rgb(c[0], c[1], c[2])
                c = (sr, sg, sb, 255)

            if c not in color_to_char:
                if char_idx < len(PALETTE_CHARS):
                    ch = PALETTE_CHARS[char_idx]
                else:
                    ch = chr(160 + (char_idx - len(PALETTE_CHARS)))
                char_idx += 1
                color_to_char[c] = ch
                palette[ch] = list(c)

            row_str.append(color_to_char[c])
        rows.append("".join(row_str))

    return palette, rows


def encoded_grid_to_surface(palette, rows, size, is_normal=False):
    w, h = size
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    if is_normal:
        surf.fill((128, 128, 255, 255))
    else:
        surf.fill((0, 0, 0, 0))

    for y, row in enumerate(rows[:h]):
        for x, ch in enumerate(row[:w]):
            rgba = palette.get(ch)
            if rgba:
                surf.set_at((x, y), tuple(rgba))
    return surf


def save_dtex_frames(filepath, role_id, file_stem, name, category, frames_list, fps=4, random_rot=False):
    """
    Saves 1 to 3 animation frames [(diff_surf, norm_surf), ...] and FPS into a .dtex v2 file.
    Also keeps top-level diffuse_palette/grid of frame 0 for backward compatibility.
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    w, h = frames_list[0][0].get_size()
    encoded_frames = []

    for d_surf, n_surf in frames_list[:3]:
        d_pal, d_rows = surface_to_encoded_grid(d_surf, is_normal=False)
        n_pal, n_rows = surface_to_encoded_grid(n_surf, is_normal=True)
        encoded_frames.append({
            "diffuse_palette": d_pal,
            "diffuse_grid": d_rows,
            "normal_palette": n_pal,
            "normal_grid": n_rows
        })

    payload = {
        "dtex_version": 2,
        "role_id": role_id,
        "id": file_stem,
        "name": name,
        "category": category,
        "size": [w, h],
        "fps": int(fps),
        "random_rot": bool(random_rot),
        "frame_count": len(encoded_frames),
        "frames": encoded_frames,
        # Frame 0 mirrored at top level so v1 readers never break
        "diffuse_palette": encoded_frames[0]["diffuse_palette"],
        "diffuse_grid": encoded_frames[0]["diffuse_grid"],
        "normal_palette": encoded_frames[0]["normal_palette"],
        "normal_grid": encoded_frames[0]["normal_grid"],
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_dtex_frames(filepath):
    """Loads a .dtex v1 or v2 file and returns (meta_dict, [(diff_0, norm_0), ...], fps)."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    size = tuple(data["size"])
    fps = int(data.get("fps", 4))
    frames_out = []

    if "frames" in data and isinstance(data["frames"], list) and len(data["frames"]) > 0:
        for fr in data["frames"][:3]:
            d_s = encoded_grid_to_surface(fr["diffuse_palette"], fr["diffuse_grid"], size, is_normal=False)
            n_s = encoded_grid_to_surface(fr["normal_palette"], fr["normal_grid"], size, is_normal=True)
            frames_out.append((d_s, n_s))
    else:
        d_s = encoded_grid_to_surface(data["diffuse_palette"], data["diffuse_grid"], size, is_normal=False)
        n_s = encoded_grid_to_surface(data["normal_palette"], data["normal_grid"], size, is_normal=True)
        frames_out.append((d_s, n_s))

    # Mask normal alpha with diffuse alpha AND snap all normal pixels strictly to the 10-color compass!
    from studio_core import snap_normal_rgb
    masked_frames = []
    for d_s, n_s in frames_out:
        w, h = d_s.get_size()
        for y in range(h):
            for x in range(w):
                n_col = n_s.get_at((x, y))
                sr, sg, sb = snap_normal_rgb(n_col[0], n_col[1], n_col[2])
                if d_s.get_at((x, y))[3] <= 10:
                    n_s.set_at((x, y), (sr, sg, sb, 0))
                else:
                    n_s.set_at((x, y), (sr, sg, sb, 255))
        masked_frames.append((d_s, n_s))

    return data, masked_frames, fps


def bootstrap_assets_if_needed(procedural_assets, hero_builder_fn=None):
    root = get_assets_root()
    os.makedirs(root, exist_ok=True)
    manifest = load_manifest()
    changed = False

    rev3_roles = {
        "floor_0", "floor_3", "floor_4", "floor_5", "floor_6", "wall", "wall_wood", "wall_cave",
        "ov_pebbles", "ov_moss", "ov_cracks", "ov_planks_wear",
        "rat_cultist", "rat_king", "wolf", "tavern_table", "bar_counter", "bed", "woven_rug"
    }

    for cat_key, cat_data in ASSET_CATALOG.items():
        cat_dir = os.path.join(root, cat_key)
        os.makedirs(cat_dir, exist_ok=True)
        for role_id, (ru_name, sz) in cat_data["items"].items():
            default_rrot = (role_id in DEFAULT_RANDOM_ROT_ROLES)
            if role_id not in manifest:
                manifest[role_id] = {
                    "file": role_id,
                    "name": ru_name,
                    "cat": cat_key,
                    "size": list(sz),
                    "random_rot": default_rrot,
                    "rev": 5
                }
                changed = True
            elif "random_rot" not in manifest[role_id]:
                manifest[role_id]["random_rot"] = default_rrot
                changed = True

            rrot_flag = bool(manifest[role_id].get("random_rot", default_rrot))
            file_stem = manifest[role_id]["file"]
            dtex_path = os.path.join(cat_dir, f"{file_stem}.dtex")

            if role_id in rev3_roles and manifest[role_id].get("rev", 1) < 5 and role_id in procedural_assets:
                manifest[role_id]["size"] = list(sz)
                manifest[role_id]["name"] = ru_name
                manifest[role_id]["rev"] = 5
                d_s, n_s = procedural_assets[role_id]
                save_dtex_frames(dtex_path, role_id, file_stem, ru_name, cat_key, [(d_s, n_s)], fps=4, random_rot=rrot_flag)
                changed = True
                continue

            if not os.path.isfile(dtex_path):
                if role_id == "floor_2" and "_water_frames" in procedural_assets:
                    save_dtex_frames(dtex_path, role_id, file_stem, manifest[role_id]["name"], cat_key, procedural_assets["_water_frames"], fps=4, random_rot=rrot_flag)
                    continue
                elif role_id == "campfire" and "_campfire_frames" in procedural_assets:
                    save_dtex_frames(dtex_path, role_id, file_stem, manifest[role_id]["name"], cat_key, procedural_assets["_campfire_frames"], fps=6, random_rot=rrot_flag)
                    continue
                elif role_id in procedural_assets:
                    d_s, n_s = procedural_assets[role_id]
                elif role_id == "hero_base" and hero_builder_fn is not None:
                    d_s, n_s = hero_builder_fn((200, 70, 75), "leather", False, True, True)
                else:
                    d_s = pygame.Surface(sz, pygame.SRCALPHA)
                    n_s = pygame.Surface(sz, pygame.SRCALPHA)
                    n_s.fill((128, 128, 255, 0))
                save_dtex_frames(dtex_path, role_id, file_stem, manifest[role_id]["name"], cat_key, [(d_s, n_s)], fps=4, random_rot=rrot_flag)

    if not manifest.get("_normals_10_strict", False):
        for cat_key, cat_data in ASSET_CATALOG.items():
            cat_dir = os.path.join(root, cat_key)
            for role_id in cat_data["items"]:
                m_info = manifest.get(role_id)
                if not isinstance(m_info, dict):
                    continue
                dtex_path = os.path.join(cat_dir, f"{m_info['file']}.dtex")
                if os.path.isfile(dtex_path):
                    try:
                        meta, fr_list, fps = load_dtex_frames(dtex_path)
                        rrot = bool(meta.get("random_rot", m_info.get("random_rot", role_id in DEFAULT_RANDOM_ROT_ROLES)))
                        save_dtex_frames(dtex_path, role_id, m_info["file"], m_info["name"], cat_key, fr_list, fps=fps, random_rot=rrot)
                    except Exception:
                        pass
        manifest["_normals_10_strict"] = True
        changed = True

    if changed:
        save_manifest(manifest)


def load_custom_dtex_animations(assets_dict):
    root = get_assets_root()
    manifest = load_manifest()
    anim_bank = {}

    for cat_key, cat_data in ASSET_CATALOG.items():
        cat_dir = os.path.join(root, cat_key)
        for role_id in cat_data["items"]:
            default_rrot = (role_id in DEFAULT_RANDOM_ROT_ROLES)
            m_info = manifest.get(role_id, {"file": role_id, "name": cat_data["items"][role_id][0], "random_rot": default_rrot})
            fpath = os.path.join(cat_dir, f"{m_info['file']}.dtex")
            if not os.path.isfile(fpath):
                fpath = os.path.join(cat_dir, f"{role_id}.dtex")

            if os.path.isfile(fpath):
                try:
                    meta, frames_list, fps = load_dtex_frames(fpath)
                    rrot = bool(meta.get("random_rot", m_info.get("random_rot", default_rrot)))
                    assets_dict[role_id] = frames_list[0]
                    anim_bank[role_id] = {
                        "frames": frames_list,
                        "fps": max(1, fps),
                        "name": meta.get("name", m_info["name"]),
                        "file": m_info["file"],
                        "random_rot": rrot
                    }
                except Exception:
                    pass
    return anim_bank