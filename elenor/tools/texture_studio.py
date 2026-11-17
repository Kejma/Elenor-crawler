import os
import re
import pygame

from elenor.data.textures import ASSET_CATALOG, get_assets_root, load_manifest, save_manifest, load_dtex_frames, save_dtex_frames, bootstrap_assets_if_needed
from elenor.rendering.normals import NORMAL_COMPASS, MIRROR_X_COMPASS_IDX, RPG_PALETTE, rgb_to_hex, hex_to_rgb, auto_bevel_normals, CanvasHistory, flood_fill_surface, LiveLightPreview
from elenor.rendering.assets import create_placeholder_assets, build_hero_sprite

WIN_W = 1280
WIN_H = 840

BG_DARK = (18, 16, 24)
PANEL_BG = (28, 25, 36)
SLOT_BG = (22, 19, 28)
BORDER_COL = (82, 68, 95)
HIGHLIGHT_COL = (230, 190, 95)
TEXT_MAIN = (235, 228, 215)
TEXT_DIM = (150, 142, 160)


class TextureStudio:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        pygame.display.set_caption("DTEX Texture & Animation Studio — Тайлы, Нормали и Кадры (1-3)")
        self.clock = pygame.time.Clock()
        try:
            pygame.scrap.init()
        except Exception:
            pass

        self.font_title = pygame.font.SysFont("consolas", 16, bold=True)
        self.font_ui = pygame.font.SysFont("consolas", 14, bold=True)
        self.font_small = pygame.font.SysFont("consolas", 12, bold=True)

        proc_assets = create_placeholder_assets()
        bootstrap_assets_if_needed(proc_assets, build_hero_sprite)

        self.manifest = load_manifest()
        self.tree_items = []
        self.thumbnails = {}
        self.scroll_y = 0
        self._build_explorer_tree()

        # Painting & Layer state
        self.active_layer = "diffuse"
        self.onion_skin = False
        self.tool = "brush"
        self.mirror_x = False
        self.show_grid = True

        self.active_color = [195, 145, 75]
        self.hex_text = rgb_to_hex(self.active_color)
        self.active_normal_idx = 1

        # Animation state (1..3 frames)
        self.frames = []         # List of (diff_surf, norm_surf)
        self.cur_frame_idx = 0
        self.fps = 4
        self.anim_timer = 0.0

        # Text input & Slider Dragging states
        self.active_input = None  # None, "hex", "rename_title", "rename_file"
        self.edit_title_str = ""
        self.edit_file_str = ""
        self.dragging_slider = None  # None, ("rgb", ch_i, x, w), or ("fps", x, w)

        self.is_painting = False
        self.paint_button = 1     # Fixes mouse-release erase bug!

        self.history = CanvasHistory()
        self.preview = LiveLightPreview(preview_w=216, preview_h=216)

        self.status_msg = "Готово! Тяни ползунки RGB/FPS мышкой, добавляй до 3 кадров анимации или переименовывай файлы."
        self.status_timer = 0.0

        first_entry = next(item for item in self.tree_items if item["type"] == "asset")
        self.load_asset_entry(first_entry)

    @property
    def diff_surf(self):
        return self.frames[self.cur_frame_idx][0]

    @property
    def norm_surf(self):
        return self.frames[self.cur_frame_idx][1]

    def _build_explorer_tree(self):
        self.tree_items.clear()
        root = get_assets_root()
        self.manifest = load_manifest()

        for cat_key, cat_data in ASSET_CATALOG.items():
            self.tree_items.append({
                "type": "header",
                "title": cat_data["title"],
                "cat": cat_key
            })
            for role_id, (default_name, sz) in cat_data["items"].items():
                m_info = self.manifest.get(role_id, {
                    "file": role_id,
                    "name": default_name,
                    "cat": cat_key,
                    "size": list(sz)
                })
                file_stem = m_info["file"]
                fpath = os.path.join(root, cat_key, f"{file_stem}.dtex")
                entry = {
                    "type": "asset",
                    "role_id": role_id,
                    "file_stem": file_stem,
                    "name": m_info["name"],
                    "cat": cat_key,
                    "size": sz,
                    "random_rot": bool(m_info.get("random_rot", False)),
                    "path": fpath
                }
                self.tree_items.append(entry)
                self._refresh_thumbnail(entry)

    def _refresh_thumbnail(self, entry):
        if os.path.isfile(entry["path"]):
            try:
                _, fr_list, _ = load_dtex_frames(entry["path"])
                self.thumbnails[entry["role_id"]] = pygame.transform.scale(fr_list[0][0], (24, 24))
            except Exception:
                pass

    def set_status(self, msg):
        self.status_msg = msg
        self.status_timer = 5.0

    def load_asset_entry(self, entry):
        self.current_entry = entry
        self.cur_frame_idx = 0
        self.active_input = None
        self.random_rot = bool(entry.get("random_rot", False))

        if os.path.isfile(entry["path"]):
            meta, fr_list, fps = load_dtex_frames(entry["path"])
            self.frames = fr_list
            self.fps = fps
            if "random_rot" in meta:
                self.random_rot = bool(meta["random_rot"])
        else:
            w, h = entry["size"]
            d_s = pygame.Surface((w, h), pygame.SRCALPHA)
            n_s = pygame.Surface((w, h), pygame.SRCALPHA)
            n_s.fill((128, 128, 255, 255))
            self.frames = [(d_s, n_s)]
            self.fps = 4

        self.edit_title_str = entry["name"]
        self.edit_file_str = entry["file_stem"]
        self.history = CanvasHistory()
        self.preview.tile_3x3 = (entry["cat"] in ("tiles", "overlays"))
        self.preview.random_rot = self.random_rot
        self.set_status(f"Загружен слот [{entry['role_id']}] -> {entry['name']} ({entry['file_stem']}.dtex, кадров: {len(self.frames)})")

    def apply_rename_and_save(self):
        e = self.current_entry
        clean_file = re.sub(r"[^a-zA-Z0-9_\-]", "", self.edit_file_str.strip())
        if not clean_file:
            clean_file = e["role_id"]
        clean_title = self.edit_title_str.strip() or e["name"]

        old_path = e["path"]
        new_path = os.path.join(get_assets_root(), e["cat"], f"{clean_file}.dtex")

        if old_path != new_path and os.path.isfile(old_path):
            try:
                os.replace(old_path, new_path)
            except Exception:
                pass

        e["file_stem"] = clean_file
        e["name"] = clean_title
        e["path"] = new_path
        e["random_rot"] = self.random_rot
        self.edit_file_str = clean_file
        self.edit_title_str = clean_title

        self.manifest[e["role_id"]] = {
            "file": clean_file,
            "name": clean_title,
            "cat": e["cat"],
            "size": list(e["size"]),
            "random_rot": self.random_rot,
            "rev": 3
        }
        save_manifest(self.manifest)
        save_dtex_frames(new_path, e["role_id"], clean_file, clean_title, e["cat"], self.frames, fps=self.fps, random_rot=self.random_rot)
        self._refresh_thumbnail(e)
        rot_str = " | Случ.поворот ВКЛ" if self.random_rot else ""
        self.set_status(f"СОХРАНЕНО: «{clean_title}» ({clean_file}.dtex, {len(self.frames)} кадр. @ {self.fps} FPS{rot_str})")

    def export_to_png(self):
        e = self.current_entry
        out_dir = os.path.join(get_assets_root(), "png_export")
        os.makedirs(out_dir, exist_ok=True)
        for idx, (d_s, n_s) in enumerate(self.frames):
            suffix = f"_f{idx+1}" if len(self.frames) > 1 else ""
            pygame.image.save(d_s, os.path.join(out_dir, f"{e['file_stem']}{suffix}_diff.png"))
            pygame.image.save(n_s, os.path.join(out_dir, f"{e['file_stem']}{suffix}_norm.png"))
        self.set_status(f"Экспортировано ({len(self.frames)} кадр.) в assets/png_export/{e['file_stem']}*.png")

    def import_from_png(self):
        e = self.current_entry
        in_dir = os.path.join(get_assets_root(), "png_export")
        suffix = f"_f{self.cur_frame_idx+1}" if len(self.frames) > 1 else ""
        d_path = os.path.join(in_dir, f"{e['file_stem']}{suffix}_diff.png")
        n_path = os.path.join(in_dir, f"{e['file_stem']}{suffix}_norm.png")
        if not os.path.isfile(d_path):
            d_path = os.path.join(in_dir, f"{e['file_stem']}_diff.png")
            n_path = os.path.join(in_dir, f"{e['file_stem']}_norm.png")
        if not os.path.isfile(d_path):
            self.set_status(f"Не найден PNG в assets/png_export/ для {e['file_stem']}!")
            return

        self.history.push(self.frames)
        w, h = e["size"]
        new_d = pygame.transform.scale(pygame.image.load(d_path).convert_alpha(), (w, h))
        new_n = self.norm_surf.copy()
        if os.path.isfile(n_path):
            new_n = pygame.transform.scale(pygame.image.load(n_path).convert_alpha(), (w, h))
        self.frames[self.cur_frame_idx] = (new_d, new_n)
        self.set_status(f"Импортирован PNG в Кадр {self.cur_frame_idx + 1}!")

    def get_canvas_geometry(self):
        w, h = self.diff_surf.get_size()
        zoom = min(23, 556 // max(1, w), 460 // max(1, h))
        cw, ch = w * zoom, h * zoom
        cx = 310 + (580 - cw) // 2
        cy = 132 + (480 - ch) // 2
        return pygame.Rect(cx, cy, cw, ch), zoom

    def apply_paint_at(self, px, py, button=1):
        w, h = self.diff_surf.get_size()
        if not (0 <= px < w and 0 <= py < h):
            return

        target_surf = self.diff_surf if self.active_layer == "diffuse" else self.norm_surf

        if self.tool == "picker":
            col = target_surf.get_at((px, py))
            if self.active_layer == "diffuse":
                if col[3] > 0:
                    self.active_color = [col[0], col[1], col[2]]
                    self.hex_text = rgb_to_hex(self.active_color)
                    self.set_status(f"Пипетка: #{self.hex_text} RGB({col[0]}, {col[1]}, {col[2]})")
            else:
                best_i = min(range(len(NORMAL_COMPASS)), key=lambda i: sum((col[k] - NORMAL_COMPASS[i][3][k]) ** 2 for k in range(3)))
                self.active_normal_idx = best_i
                self.set_status(f"Пипетка нормали: {NORMAL_COMPASS[best_i][1]}")
            self.tool = "brush"
            return

        if button == 3 or self.tool == "eraser":
            draw_col = (0, 0, 0, 0) if self.active_layer == "diffuse" else (128, 128, 255, 255)
        else:
            if self.active_layer == "diffuse":
                draw_col = (self.active_color[0], self.active_color[1], self.active_color[2], 255)
            else:
                n_rgb = NORMAL_COMPASS[self.active_normal_idx][3]
                draw_col = (n_rgb[0], n_rgb[1], n_rgb[2], 255)

        if self.tool == "bucket" and button == 1:
            flood_fill_surface(target_surf, (px, py), draw_col)
            return

        target_surf.set_at((px, py), draw_col)
        if self.mirror_x:
            mx = w - 1 - px
            if self.active_layer == "normal" and button == 1 and self.tool != "eraser":
                mir_idx = MIRROR_X_COMPASS_IDX.get(self.active_normal_idx, self.active_normal_idx)
                m_rgb = NORMAL_COMPASS[mir_idx][3]
                target_surf.set_at((mx, py), (m_rgb[0], m_rgb[1], m_rgb[2], 255))
            else:
                target_surf.set_at((mx, py), draw_col)

    def _update_dragged_slider(self, mx):
        if not self.dragging_slider:
            return
        kind = self.dragging_slider[0]
        if kind == "rgb":
            _, ch_i, bar_x, bar_w = self.dragging_slider
            val = int(round(max(0.0, min(1.0, (mx - bar_x) / float(bar_w))) * 255))
            self.active_color[ch_i] = val
            self.hex_text = rgb_to_hex(self.active_color)
        elif kind == "fps":
            _, bar_x, bar_w = self.dragging_slider
            val = int(round(1 + max(0.0, min(1.0, (mx - bar_x) / float(bar_w))) * 11))
            self.fps = max(1, min(12, val))

    def draw_button(self, rect, text, active=False, accent_col=None):
        mx, my = pygame.mouse.get_pos()
        hov = rect.collidepoint((mx, my))
        bg = (58, 48, 72) if active else ((42, 36, 54) if hov else SLOT_BG)
        bd = HIGHLIGHT_COL if (active or hov) else (accent_col or BORDER_COL)
        pygame.draw.rect(self.screen, bg, rect, border_radius=4)
        pygame.draw.rect(self.screen, bd, rect, 2 if active else 1, border_radius=4)
        lbl = self.font_small.render(text, True, HIGHLIGHT_COL if active else TEXT_MAIN)
        self.screen.blit(lbl, (rect.x + (rect.width - lbl.get_width()) // 2, rect.y + (rect.height - lbl.get_height()) // 2))
        return rect

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(60) / 1000.0
            self.anim_timer += dt
            if self.status_timer > 0:
                self.status_timer = max(0.0, self.status_timer - dt)

            mx, my = pygame.mouse.get_pos()
            canvas_rect, zoom = self.get_canvas_geometry()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.MOUSEWHEEL:
                    if mx < 290:
                        max_scroll = max(520, len(self.tree_items) * 32 - (WIN_H - 140))
                        self.scroll_y = max(-max_scroll, min(0, self.scroll_y + event.y * 28))

                elif event.type == pygame.KEYDOWN:
                    mods = pygame.key.get_mods()

                    # Handle active text box typing (HEX, Rename Title, Rename File)
                    if self.active_input is not None:
                        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                            if self.active_input in ("rename_title", "rename_file"):
                                self.apply_rename_and_save()
                            self.active_input = None
                        elif event.key == pygame.K_ESCAPE:
                            self.active_input = None
                        elif event.key == pygame.K_BACKSPACE:
                            if self.active_input == "hex":
                                self.hex_text = self.hex_text[:-1]
                            elif self.active_input == "rename_title":
                                self.edit_title_str = self.edit_title_str[:-1]
                            elif self.active_input == "rename_file":
                                self.edit_file_str = self.edit_file_str[:-1]
                        elif (mods & pygame.KMOD_CTRL) and event.key == pygame.K_v:
                            # Paste support for HEX or names
                            try:
                                clip = pygame.scrap.get(pygame.SCRAP_TEXT).decode("utf-8").strip("\x00").strip()
                                if self.active_input == "hex":
                                    clean = re.sub(r"[^0-9a-fA-F]", "", clip)[:6].upper()
                                    if clean:
                                        self.hex_text = clean
                                        rgb = hex_to_rgb(self.hex_text)
                                        if rgb:
                                            self.active_color = rgb
                            except Exception:
                                pass
                        else:
                            ch = event.unicode
                            if ch and ch.isprintable():
                                if self.active_input == "hex" and ch in "0123456789abcdefABCDEF" and len(self.hex_text) < 6:
                                    self.hex_text += ch.upper()
                                    if len(self.hex_text) == 6:
                                        rgb = hex_to_rgb(self.hex_text)
                                        if rgb:
                                            self.active_color = rgb
                                elif self.active_input == "rename_title" and len(self.edit_title_str) < 26:
                                    self.edit_title_str += ch
                                elif self.active_input == "rename_file" and re.match(r"[a-zA-Z0-9_\-]", ch) and len(self.edit_file_str) < 20:
                                    self.edit_file_str += ch
                        continue

                    # Hotkeys when not typing in a text field
                    if (mods & pygame.KMOD_CTRL) and event.key == pygame.K_s:
                        self.apply_rename_and_save()
                    elif (mods & pygame.KMOD_CTRL) and event.key == pygame.K_z:
                        res = self.history.undo(self.frames)
                        if res:
                            self.frames = res
                            self.cur_frame_idx = min(self.cur_frame_idx, len(self.frames) - 1)
                            self.set_status("Отмена действия (Ctrl+Z)")
                    elif (mods & pygame.KMOD_CTRL) and event.key == pygame.K_y:
                        res = self.history.redo(self.frames)
                        if res:
                            self.frames = res
                            self.cur_frame_idx = min(self.cur_frame_idx, len(self.frames) - 1)
                            self.set_status("Повтор действия (Ctrl+Y)")
                    elif event.key == pygame.K_1:
                        self.active_layer = "diffuse"
                    elif event.key == pygame.K_2:
                        self.active_layer = "normal"
                    elif event.key == pygame.K_b:
                        self.tool = "brush"
                    elif event.key == pygame.K_e:
                        self.tool = "eraser"
                    elif event.key == pygame.K_g:
                        self.tool = "bucket"
                    elif event.key == pygame.K_i:
                        self.tool = "picker"
                    elif event.key == pygame.K_m:
                        self.mirror_x = not self.mirror_x

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self.active_input = None
                    if event.button in (1, 3):
                        if canvas_rect.collidepoint((mx, my)):
                            self.history.push(self.frames)
                            self.is_painting = True
                            self.paint_button = event.button  # Fixed! Remember exact mouse button pressed
                            px = (mx - canvas_rect.x) // zoom
                            py = (my - canvas_rect.y) // zoom
                            self.apply_paint_at(px, py, self.paint_button)

                        elif mx < 290 and 50 <= my <= WIN_H - 40:
                            self._handle_tree_click(mx, my)

                        elif event.button == 1:
                            self._handle_ui_clicks(mx, my)

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button in (1, 3):
                        self.is_painting = False
                        self.dragging_slider = None

                elif event.type == pygame.MOUSEMOTION:
                    if self.dragging_slider is not None:
                        self._update_dragged_slider(mx)
                    elif self.is_painting and canvas_rect.collidepoint((mx, my)):
                        px = (mx - canvas_rect.x) // zoom
                        py = (my - canvas_rect.y) // zoom
                        self.apply_paint_at(px, py, self.paint_button)

            self._render_studio(dt, (mx, my), canvas_rect, zoom)
            pygame.display.flip()

        pygame.quit()

    def _handle_tree_click(self, mx, my):
        y_cursor = 58 + self.scroll_y
        for item in self.tree_items:
            if item["type"] == "header":
                y_cursor += 28
            else:
                r = pygame.Rect(14, y_cursor, 262, 30)
                if r.collidepoint((mx, my)):
                    self.load_asset_entry(item)
                    return
                y_cursor += 32

    def _handle_ui_clicks(self, mx, my):
        for btn_id, rect in getattr(self, "ui_hitboxes", []):
            if rect.collidepoint((mx, my)):
                if btn_id == "input_title":
                    self.active_input = "rename_title"
                elif btn_id == "input_file":
                    self.active_input = "rename_file"
                elif btn_id == "input_hex":
                    self.active_input = "hex"
                elif btn_id == "layer_diff":
                    self.active_layer = "diffuse"
                elif btn_id == "layer_norm":
                    self.active_layer = "normal"
                elif btn_id == "toggle_onion":
                    self.onion_skin = not self.onion_skin
                elif btn_id == "tool_brush":
                    self.tool = "brush"
                elif btn_id == "tool_eraser":
                    self.tool = "eraser"
                elif btn_id == "tool_bucket":
                    self.tool = "bucket"
                elif btn_id == "tool_picker":
                    self.tool = "picker"
                elif btn_id == "toggle_mirror":
                    self.mirror_x = not self.mirror_x
                elif btn_id == "toggle_grid":
                    self.show_grid = not self.show_grid
                elif btn_id == "auto_bevel":
                    self.history.push(self.frames)
                    new_n = auto_bevel_normals(self.diff_surf)
                    self.frames[self.cur_frame_idx] = (self.diff_surf, new_n)
                    self.set_status(f"Авто-рельеф построен для Кадра {self.cur_frame_idx + 1}!")
                elif btn_id == "clear_layer":
                    self.history.push(self.frames)
                    if self.active_layer == "diffuse":
                        self.diff_surf.fill((0, 0, 0, 0))
                    else:
                        self.norm_surf.fill((128, 128, 255, 255))
                elif btn_id.startswith("frame_sel_"):
                    self.cur_frame_idx = int(btn_id.split("_")[-1])
                elif btn_id == "frame_add":
                    if len(self.frames) < 3:
                        self.history.push(self.frames)
                        d_copy, n_copy = self.diff_surf.copy(), self.norm_surf.copy()
                        self.frames.append((d_copy, n_copy))
                        self.cur_frame_idx = len(self.frames) - 1
                        self.set_status(f"Добавлен Кадр {len(self.frames)} (копия текущего)!")
                elif btn_id == "frame_del":
                    if len(self.frames) > 1:
                        self.history.push(self.frames)
                        self.frames.pop(self.cur_frame_idx)
                        self.cur_frame_idx = max(0, self.cur_frame_idx - 1)
                        self.set_status("Кадр удалён.")
                elif btn_id == "toggle_anim_play":
                    self.preview.play_anim = not self.preview.play_anim
                elif btn_id == "prev_orbit":
                    self.preview.auto_orbit = not self.preview.auto_orbit
                elif btn_id == "prev_3x3":
                    self.preview.tile_3x3 = not self.preview.tile_3x3
                elif btn_id == "prev_warm":
                    self.preview.torch_warmth = not self.preview.torch_warmth
                elif btn_id == "toggle_rand_rot":
                    self.random_rot = not self.random_rot
                    self.preview.random_rot = self.random_rot
                    self.set_status("Случайный поворот тайла (0/90/180/270°): " + ("ВКЛЮЧЁН (не забудь Ctrl+S)" if self.random_rot else "ВЫКЛЮЧЕН"))
                elif btn_id == "save_dtex":
                    self.apply_rename_and_save()
                elif btn_id == "export_png":
                    self.export_to_png()
                elif btn_id == "import_png":
                    self.import_from_png()
                elif btn_id.startswith("pal_"):
                    idx = int(btn_id.split("_")[1])
                    self.active_color = list(RPG_PALETTE[idx])
                    self.hex_text = rgb_to_hex(self.active_color)
                    self.active_layer = "diffuse"
                elif btn_id.startswith("comp_"):
                    idx = int(btn_id.split("_")[1])
                    self.active_normal_idx = idx
                    self.active_layer = "normal"
                elif btn_id.startswith("rgb_"):
                    _, ch_idx, click_x, bar_w = btn_id.split("_")
                    self.dragging_slider = ("rgb", int(ch_idx), int(click_x), int(bar_w))
                    self._update_dragged_slider(mx)
                elif btn_id.startswith("fps_"):
                    _, click_x, bar_w = btn_id.split("_")
                    self.dragging_slider = ("fps", int(click_x), int(bar_w))
                    self._update_dragged_slider(mx)
                return

    def _render_studio(self, dt, mouse_pos, canvas_rect, zoom):
        self.screen.fill(BG_DARK)
        self.ui_hitboxes = []
        mx, my = mouse_pos

        # ======================================================================
        # 1. LEFT PANEL: ASSET EXPLORER TREE
        # ======================================================================
        pygame.draw.rect(self.screen, PANEL_BG, (10, 10, 280, WIN_H - 52), border_radius=6)
        pygame.draw.rect(self.screen, BORDER_COL, (10, 10, 280, WIN_H - 52), 2, border_radius=6)
        self.screen.blit(self.font_title.render("ПРОВОДНИК (.DTEX)", True, HIGHLIGHT_COL), (24, 20))

        tree_clip = pygame.Rect(12, 50, 276, WIN_H - 96)
        self.screen.set_clip(tree_clip)
        y_cur = 58 + self.scroll_y

        for item in self.tree_items:
            if item["type"] == "header":
                pygame.draw.rect(self.screen, (38, 32, 48), (16, y_cur, 260, 24), border_radius=3)
                self.screen.blit(self.font_small.render(item["title"], True, HIGHLIGHT_COL), (22, y_cur + 5))
                y_cur += 28
            else:
                is_sel = (item["role_id"] == self.current_entry["role_id"])
                r = pygame.Rect(16, y_cur, 260, 28)
                hov = r.collidepoint((mx, my)) and tree_clip.collidepoint((mx, my))
                bg = (68, 52, 82) if is_sel else ((40, 35, 52) if hov else SLOT_BG)
                pygame.draw.rect(self.screen, bg, r, border_radius=4)
                if is_sel:
                    pygame.draw.rect(self.screen, HIGHLIGHT_COL, r, 1, border_radius=4)

                thumb = self.thumbnails.get(item["role_id"])
                if thumb:
                    self.screen.blit(thumb, (r.x + 6, r.y + 2))
                lbl = self.font_small.render(f"{item['name']} [{item['file_stem']}]", True, TEXT_MAIN if is_sel else TEXT_DIM)
                self.screen.blit(lbl, (r.x + 36, r.y + 7))
                y_cur += 32

        self.screen.set_clip(None)

        # ======================================================================
        # 2. CENTER PANEL: RENAME BAR, TOOLS, CANVAS & ANIMATION TIMELINE
        # ======================================================================
        pygame.draw.rect(self.screen, PANEL_BG, (300, 10, 600, WIN_H - 52), border_radius=6)
        pygame.draw.rect(self.screen, BORDER_COL, (300, 10, 600, WIN_H - 52), 2, border_radius=6)

        # Row 1: Editable Asset Name & Filename (.dtex)
        self.screen.blit(self.font_small.render("Имя:", True, TEXT_DIM), (314, 22))
        title_box = pygame.Rect(350, 16, 200, 26)
        t_act = (self.active_input == "rename_title")
        pygame.draw.rect(self.screen, (16, 14, 22), title_box, border_radius=3)
        pygame.draw.rect(self.screen, HIGHLIGHT_COL if t_act else BORDER_COL, title_box, 2 if t_act else 1, border_radius=3)
        t_str = self.edit_title_str + ("|" if t_act else "")
        self.screen.blit(self.font_small.render(t_str, True, TEXT_MAIN), (title_box.x + 8, title_box.y + 6))
        self.ui_hitboxes.append(("input_title", title_box))

        self.screen.blit(self.font_small.render("Файл:", True, TEXT_DIM), (562, 22))
        file_box = pygame.Rect(606, 16, 145, 26)
        f_act = (self.active_input == "rename_file")
        pygame.draw.rect(self.screen, (16, 14, 22), file_box, border_radius=3)
        pygame.draw.rect(self.screen, HIGHLIGHT_COL if f_act else BORDER_COL, file_box, 2 if f_act else 1, border_radius=3)
        f_str = self.edit_file_str + ("|" if f_act else "")
        self.screen.blit(self.font_small.render(f_str, True, (135, 220, 255)), (file_box.x + 8, file_box.y + 6))
        self.screen.blit(self.font_small.render(f".dtex (слот: {self.current_entry['role_id']})", True, TEXT_DIM), (756, 22))
        self.ui_hitboxes.append(("input_file", file_box))

        # Row 2: Layers & Auto-Bevel
        self.ui_hitboxes.append(("layer_diff", self.draw_button(pygame.Rect(314, 48, 155, 28), "[1] Слой: ЦВЕТ", self.active_layer == "diffuse")))
        self.ui_hitboxes.append(("layer_norm", self.draw_button(pygame.Rect(476, 48, 165, 28), "[2] Слой: НОРМАЛИ", self.active_layer == "normal")))
        self.ui_hitboxes.append(("toggle_onion", self.draw_button(pygame.Rect(648, 48, 115, 28), "Луковица", self.onion_skin)))
        self.ui_hitboxes.append(("auto_bevel", self.draw_button(pygame.Rect(770, 48, 118, 28), "⚡ Авто-Рельеф", False, (100, 210, 140))))

        # Row 3: Drawing Tools
        tools_row = [
            ("tool_brush", "[B] Кисть", self.tool == "brush", 88),
            ("tool_eraser", "[E] Ластик", self.tool == "eraser", 92),
            ("tool_bucket", "[G] Заливка", self.tool == "bucket", 98),
            ("tool_picker", "[I] Пипетка", self.tool == "picker", 98),
            ("toggle_mirror", "[M] Симм.X", self.mirror_x, 92),
            ("toggle_grid", "Сетка", self.show_grid, 64),
        ]
        tx = 314
        for b_id, b_txt, b_act, bw in tools_row:
            self.ui_hitboxes.append((b_id, self.draw_button(pygame.Rect(tx, 82, bw, 26), b_txt, b_act)))
            tx += bw + 6

        # Main Pixel Canvas
        w, h = self.diff_surf.get_size()
        pygame.draw.rect(self.screen, (12, 10, 16), canvas_rect.inflate(8, 8))
        pygame.draw.rect(self.screen, HIGHLIGHT_COL if self.active_layer == "diffuse" else (110, 205, 255), canvas_rect.inflate(8, 8), 2)

        prev_frame_diff = self.frames[self.cur_frame_idx - 1][0] if (len(self.frames) > 1 and self.cur_frame_idx > 0) else None

        for py in range(h):
            for px in range(w):
                cell_r = pygame.Rect(canvas_rect.x + px * zoom, canvas_rect.y + py * zoom, zoom, zoom)
                chk = (32, 29, 40) if (px + py) % 2 == 0 else (24, 22, 30)
                pygame.draw.rect(self.screen, chk, cell_r)

                d_col = self.diff_surf.get_at((px, py))
                n_col = self.norm_surf.get_at((px, py))

                if self.active_layer == "diffuse":
                    # If onion skin is ON and we are on Frame 2 or 3, show ghost of previous frame!
                    if self.onion_skin and prev_frame_diff is not None and d_col[3] == 0:
                        p_col = prev_frame_diff.get_at((px, py))
                        if p_col[3] > 0:
                            s = pygame.Surface((zoom, zoom), pygame.SRCALPHA)
                            s.fill((p_col[0], p_col[1], p_col[2], 85))
                            self.screen.blit(s, cell_r.topleft)

                    if d_col[3] > 0:
                        pygame.draw.rect(self.screen, d_col[:3], cell_r)
                    if self.onion_skin:
                        s = pygame.Surface((zoom, zoom), pygame.SRCALPHA)
                        s.fill((n_col[0], n_col[1], n_col[2], 85))
                        self.screen.blit(s, cell_r.topleft)
                else:
                    if d_col[3] > 0 or n_col[:3] != (128, 128, 255):
                        pygame.draw.rect(self.screen, n_col[:3], cell_r)
                    else:
                        pygame.draw.rect(self.screen, (65, 65, 135), cell_r)

                if self.show_grid:
                    pygame.draw.rect(self.screen, (45, 42, 58), cell_r, 1)

        if self.mirror_x:
            mid_x = canvas_rect.x + (w // 2) * zoom
            pygame.draw.line(self.screen, (255, 195, 70), (mid_x, canvas_rect.top), (mid_x, canvas_rect.bottom), 2)

        if h == 20:
            head_line_y = canvas_rect.y + 4 * zoom
            pygame.draw.line(self.screen, (110, 220, 140), (canvas_rect.left, head_line_y), (canvas_rect.right, head_line_y), 1)

        # --- ANIMATION TIMELINE (1..3 FRAMES + FPS SLIDER) BELOW CANVAS ---
        anim_y = 618
        pygame.draw.rect(self.screen, (22, 19, 30), (314, anim_y, 572, 78), border_radius=5)
        pygame.draw.rect(self.screen, BORDER_COL, (314, anim_y, 572, 78), 1, border_radius=5)

        for idx in range(len(self.frames)):
            fr_rect = pygame.Rect(324 + idx * 86, anim_y + 8, 80, 30)
            self.ui_hitboxes.append((f"frame_sel_{idx}", self.draw_button(fr_rect, f"Кадр {idx+1}", self.cur_frame_idx == idx)))

        if len(self.frames) < 3:
            self.ui_hitboxes.append(("frame_add", self.draw_button(pygame.Rect(324 + len(self.frames) * 86, anim_y + 8, 92, 30), "+ Кадр (Коп)", False, (100, 210, 140))))
        if len(self.frames) > 1:
            self.ui_hitboxes.append(("frame_del", self.draw_button(pygame.Rect(686, anim_y + 8, 90, 30), "- Удалить", False, (215, 95, 95))))

        self.ui_hitboxes.append(("toggle_anim_play", self.draw_button(pygame.Rect(784, anim_y + 8, 92, 30), "▶ Тест ВКЛ" if self.preview.play_anim else "⏸ Пауза", self.preview.play_anim)))

        # Draggable FPS Slider
        self.screen.blit(self.font_small.render(f"Скорость анимации: {self.fps} кадр/сек", True, HIGHLIGHT_COL), (324, anim_y + 48))
        fps_bar = pygame.Rect(555, anim_y + 46, 220, 20)
        pygame.draw.rect(self.screen, (14, 12, 18), fps_bar, border_radius=3)
        fps_fill = int(((self.fps - 1) / 11.0) * fps_bar.width)
        pygame.draw.rect(self.screen, (110, 195, 255), (fps_bar.x, fps_bar.y, fps_fill, fps_bar.height), border_radius=3)
        pygame.draw.rect(self.screen, BORDER_COL, fps_bar, 1, border_radius=3)
        self.ui_hitboxes.append((f"fps_{fps_bar.x}_{fps_bar.width}", fps_bar))

        # Bottom Save & Clear Row
        bottom_cy = 708
        mini_sc = 2 if (w > 16 or h > 20) else 3
        self.screen.blit(self.font_small.render("Слой Цвета:", True, TEXT_DIM), (320, bottom_cy))
        self.screen.blit(pygame.transform.scale(self.diff_surf, (w * mini_sc, h * mini_sc)), (320, bottom_cy + 16))

        self.screen.blit(self.font_small.render("Нормаль:", True, TEXT_DIM), (430, bottom_cy))
        self.screen.blit(pygame.transform.scale(self.norm_surf, (w * mini_sc, h * mini_sc)), (430, bottom_cy + 16))

        self.ui_hitboxes.append(("clear_layer", self.draw_button(pygame.Rect(545, bottom_cy + 22, 135, 34), "Очистить слой")))
        self.ui_hitboxes.append(("save_dtex", self.draw_button(pygame.Rect(690, bottom_cy + 22, 194, 34), "💾 Сохранить .DTEX [Ctrl+S]", False, (100, 220, 130))))

        # ======================================================================
        # 3. RIGHT PANEL: LIVE 3D TORCH SHADER + DRAGGABLE RGB & HEX INPUT
        # ======================================================================
        pygame.draw.rect(self.screen, PANEL_BG, (910, 10, 360, WIN_H - 52), border_radius=6)
        pygame.draw.rect(self.screen, BORDER_COL, (910, 10, 360, WIN_H - 52), 2, border_radius=6)

        self.screen.blit(self.font_title.render("3D-ПРЕВЬЮ С ФАКЕЛОМ", True, HIGHLIGHT_COL), (926, 20))

        prev_rect = pygame.Rect(982, 48, 216, 216)
        rel_mouse = None
        if prev_rect.collidepoint((mx, my)):
            rel_mouse = ((mx - prev_rect.x) / float(prev_rect.width), (my - prev_rect.y) / float(prev_rect.height))
            self.preview.auto_orbit = False

        # Choose animated frame or active frame for 3D Preview
        if self.preview.play_anim and len(self.frames) > 1:
            anim_idx = int(self.anim_timer * self.fps) % len(self.frames)
            p_diff, p_norm = self.frames[anim_idx]
        else:
            p_diff, p_norm = self.diff_surf, self.norm_surf

        lit_preview_surf = self.preview.render(p_diff, p_norm, dt, rel_mouse)
        self.screen.blit(lit_preview_surf, prev_rect.topleft)
        pygame.draw.rect(self.screen, BORDER_COL, prev_rect, 2)

        self.ui_hitboxes.append(("prev_orbit", self.draw_button(pygame.Rect(920, 272, 82, 26), "Орбита", self.preview.auto_orbit)))
        self.ui_hitboxes.append(("prev_3x3", self.draw_button(pygame.Rect(1006, 272, 74, 26), "Сетка 3x3", self.preview.tile_3x3)))
        self.ui_hitboxes.append(("prev_warm", self.draw_button(pygame.Rect(1084, 272, 68, 26), "Факел", self.preview.torch_warmth)))
        chk_mark = "[✓] Поворот" if self.random_rot else "[ ] Поворот"
        self.ui_hitboxes.append(("toggle_rand_rot", self.draw_button(pygame.Rect(1156, 272, 104, 26), chk_mark, self.random_rot, (110, 215, 145))))

        if self.active_layer == "normal":
            self.screen.blit(self.font_title.render("КОМПАС ГРАНЕЙ (НОРМАЛИ)", True, (120, 215, 255)), (926, 314))
            self.screen.blit(self.font_small.render("Выбери, куда смотрит грань пикселя:", True, TEXT_DIM), (926, 336))

            compass_grid = [
                (5, 0, 0), (1, 1, 0), (6, 2, 0),
                (3, 0, 1), (0, 1, 1), (4, 2, 1),
                (7, 0, 2), (2, 1, 2), (8, 2, 2),
            ]
            for c_idx, gx, gy in compass_grid:
                _, short_lbl, _, n_rgb = NORMAL_COMPASS[c_idx]
                cr = pygame.Rect(926 + gx * 112, 360 + gy * 48, 104, 42)
                is_act = (self.active_normal_idx == c_idx)
                pygame.draw.rect(self.screen, n_rgb, (cr.x + 4, cr.y + 4, 22, 34), border_radius=3)
                self.ui_hitboxes.append(("comp_" + str(c_idx), self.draw_button(cr, "   " + short_lbl, is_act, n_rgb)))

            _, short_lbl, _, n_rgb = NORMAL_COMPASS[9]
            cr_deep = pygame.Rect(926, 508, 328, 36)
            self.ui_hitboxes.append(("comp_9", self.draw_button(cr_deep, short_lbl + " (Тёмный шов)", self.active_normal_idx == 9, n_rgb)))

            _, cur_lbl, cur_desc, cur_rgb = NORMAL_COMPASS[self.active_normal_idx]
            pygame.draw.rect(self.screen, SLOT_BG, (926, 554, 328, 64), border_radius=4)
            pygame.draw.rect(self.screen, cur_rgb, (926, 554, 328, 64), 2, border_radius=4)
            self.screen.blit(self.font_ui.render(f"{cur_lbl}  RGB{cur_rgb}", True, cur_rgb), (938, 562))
            self.screen.blit(self.font_small.render(cur_desc, True, TEXT_MAIN), (938, 588))

        else:
            self.screen.blit(self.font_title.render("ПАЛИТРА И КАНАЛЫ ЦВЕТА", True, HIGHLIGHT_COL), (926, 312))
            for idx, col in enumerate(RPG_PALETTE):
                gx = idx % 8
                gy = idx // 8
                sr = pygame.Rect(926 + gx * 41, 340 + gy * 35, 36, 29)
                pygame.draw.rect(self.screen, col, sr, border_radius=3)
                is_sel = (list(col) == self.active_color)
                pygame.draw.rect(self.screen, HIGHLIGHT_COL if is_sel else (15, 12, 20), sr, 2 if is_sel else 1, border_radius=3)
                self.ui_hitboxes.append((f"pal_{idx}", sr))

            # Draggable RGB Sliders (Hold & Drag smoothly!)
            channels = [("R", 0, (230, 75, 75)), ("G", 1, (75, 220, 110)), ("B", 2, (80, 155, 245))]
            for c_label, c_i, c_col in channels:
                sy = 490 + c_i * 32
                self.screen.blit(self.font_small.render(f"{c_label}: {self.active_color[c_i]}", True, c_col), (926, sy + 4))
                bar_r = pygame.Rect(985, sy, 210, 22)
                pygame.draw.rect(self.screen, SLOT_BG, bar_r, border_radius=3)
                fill_w = int((self.active_color[c_i] / 255.0) * bar_r.width)
                pygame.draw.rect(self.screen, c_col, (bar_r.x, bar_r.y, fill_w, bar_r.height), border_radius=3)
                # Slider handle knob
                knob_x = bar_r.x + fill_w
                pygame.draw.rect(self.screen, (245, 245, 250), (knob_x - 3, bar_r.y - 2, 6, bar_r.height + 4), border_radius=2)
                pygame.draw.rect(self.screen, BORDER_COL, bar_r, 1, border_radius=3)
                self.ui_hitboxes.append((f"rgb_{c_i}_{bar_r.x}_{bar_r.width}", bar_r))

            # Color Swatch
            pygame.draw.rect(self.screen, tuple(self.active_color), (1208, 490, 46, 86), border_radius=4)
            pygame.draw.rect(self.screen, HIGHLIGHT_COL, (1208, 490, 46, 86), 2, border_radius=4)

            # Manual HEX Input Box (#RRGGBB)
            self.screen.blit(self.font_ui.render("HEX код: #", True, TEXT_MAIN), (926, 598))
            hex_box = pygame.Rect(1018, 592, 120, 28)
            h_act = (self.active_input == "hex")
            pygame.draw.rect(self.screen, (16, 14, 22), hex_box, border_radius=4)
            pygame.draw.rect(self.screen, HIGHLIGHT_COL if h_act else BORDER_COL, hex_box, 2 if h_act else 1, border_radius=4)
            disp_hex = self.hex_text + ("|" if h_act else "")
            self.screen.blit(self.font_ui.render(disp_hex, True, HIGHLIGHT_COL), (hex_box.x + 10, hex_box.y + 6))
            self.screen.blit(self.font_small.render("[Кликни для ввода]", True, TEXT_DIM), (1146, 599))
            self.ui_hitboxes.append(("input_hex", hex_box))

        # PNG Export / Import bridge buttons
        self.ui_hitboxes.append(("export_png", self.draw_button(pygame.Rect(926, 696, 158, 34), "Экспорт в PNG")))
        self.ui_hitboxes.append(("import_png", self.draw_button(pygame.Rect(1096, 696, 158, 34), "Импорт из PNG")))

        # ======================================================================
        # 4. BOTTOM STATUS BAR
        # ======================================================================
        pygame.draw.rect(self.screen, (14, 12, 18), (10, WIN_H - 34, WIN_W - 20, 26), border_radius=4)
        self.screen.blit(self.font_small.render(self.status_msg, True, HIGHLIGHT_COL if self.status_timer > 0 else TEXT_DIM), (20, WIN_H - 28))


if __name__ == "__main__":
    studio = TextureStudio()
    studio.run()