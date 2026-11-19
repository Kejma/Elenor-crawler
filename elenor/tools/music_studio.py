from elenor.paths import PROJECT_ROOT
import json
import math
import os
import tkinter as tk
from tkinter import filedialog
import numpy as np
import pygame

from elenor.audio.music import NOTE_LIST, SCALES, INSTRUMENT_CATEGORIES, INSTRUMENT_CATALOG, DEFAULT_SYNTH_PARAMS, TrackStep, PatternData, SongData, MusicLoopCompiler, load_preset_into_song

WIN_W = 1280
WIN_H = 840

BG_DARK = (18, 16, 24)
PANEL_BG = (28, 25, 36)
SLOT_BG = (22, 19, 28)
BORDER_COL = (82, 68, 95)
HIGHLIGHT_COL = (230, 190, 95)
TEXT_MAIN = (235, 228, 215)
TEXT_DIM = (150, 142, 160)


def build_dancing_ratfolk_frames():
    """Генерирует 4 кадра честного пиксель-арта пляшущего крысолюда (16x20 -> 48x60)."""
    frames = []
    for f_i in range(4):
        surf = pygame.Surface((16, 20), pygame.SRCALPHA)
        bob_y = 1 if f_i in (1, 3) else 0
        lean_x = -1 if f_i == 1 else (1 if f_i == 3 else 0)

        # Круглые крысиные уши
        for ex, ey in ((4 + lean_x, 2 + bob_y), (10 + lean_x, 2 + bob_y)):
            pygame.draw.rect(surf, (130, 115, 110), (ex, ey, 3, 3))
            surf.set_at((ex + 1, ey + 1), (215, 145, 155))

        # Голова и вытянутая мордочка
        for y in range(4 + bob_y, 9 + bob_y):
            for x in range(4 + lean_x, 12 + lean_x):
                surf.set_at((x, y), (155, 140, 132))
        # Розовый нос и усы
        surf.set_at((3 + lean_x, 6 + bob_y), (245, 120, 140))
        surf.set_at((4 + lean_x, 6 + bob_y), (225, 110, 130))
        # Яркие жёлто-красные глаза
        surf.set_at((6 + lean_x, 5 + bob_y), (255, 225, 65))
        surf.set_at((9 + lean_x, 5 + bob_y), (255, 225, 65))

        # Плащ и торс
        for y in range(9 + bob_y, 16):
            for x in range(4, 12):
                is_edge = x in (4, 11) or y == 15
                col = (165, 38, 52) if not is_edge else (115, 24, 36)
                if y == 12 and 5 <= x <= 10:
                    col = (215, 175, 70)  # Золотой пояс
                surf.set_at((x, y), col)

        # Танцующие лапы (вразнобой по фазам бита)
        arm_l_y = 8 if f_i in (1, 2) else 11
        arm_r_y = 8 if f_i in (3, 0) else 11
        pygame.draw.line(surf, (155, 140, 132), (3, 10 + bob_y), (2, arm_l_y), 2)
        pygame.draw.line(surf, (155, 140, 132), (12, 10 + bob_y), (14, arm_r_y), 2)

        # Переступающие ноги в сапогах
        l_foot_y = 17 if f_i == 1 else 18
        r_foot_y = 17 if f_i == 3 else 18
        pygame.draw.rect(surf, (75, 50, 36), (5, 16, 2, l_foot_y - 14))
        pygame.draw.rect(surf, (75, 50, 36), (9, 16, 2, r_foot_y - 14))

        # Виляющий розовый хвост
        tail_pts = [(11, 15), (13, 14 + (f_i % 2)), (14, 12 + (1 if f_i < 2 else -1)), (15, 10 + (f_i % 3))]
        pygame.draw.lines(surf, (215, 135, 145), False, tail_pts, 1)

        frames.append(pygame.transform.scale(surf, (48, 60)))
    return frames


class MusicStudioApp:
    def __init__(self):
        pygame.init()
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        pygame.mixer.set_num_channels(16)

        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        pygame.display.set_caption("Dungeon Sound Studio — Процедурный Синтезатор и Трекер")
        self.clock = pygame.time.Clock()

        self.font_title = pygame.font.SysFont("consolas", 16, bold=True)
        self.font_ui = pygame.font.SysFont("consolas", 13, bold=True)
        self.font_small = pygame.font.SysFont("consolas", 11, bold=True)

        self.compiler = MusicLoopCompiler(sample_rate=44100)
        self.song = SongData(bpm=120.0)
        self.current_file_path = None

        self.active_tab = "sequencer"
        self.cur_pat_idx = 0
        self.pat_scroll_offset = 0
        self.step_page = 0
        self.auto_follow_page = True
        self.pl_bar_scroll = 0

        self.selected_ch_idx = 0
        self.selected_synth_cat = "drive"
        self.selected_synth_inst = "dist_guitar"

        self.picker_ch_idx = None
        self.picker_cat = "drive"

        # Воспроизведение
        self.editor_volume = 0.50
        self.loop_channel = pygame.mixer.Channel(0)
        self.preview_channel = pygame.mixer.Channel(1)
        self.loop_channel.set_volume(self.editor_volume)
        self.preview_channel.set_volume(self.editor_volume)
        self.is_playing = False
        self.play_mode = "pattern"
        self.play_start_tick = 0
        self.current_sound = None
        self.playback_step = 0
        self.playback_bar = 0
        self.active_bars_count = 1
        self.muffled_mode = False
        self.audio_dirty = False
        self.audio_rebuild_timer = 0.0

        self.selected_scale_name = "D Dorian (Драйв / Таверна)"
        self.available_scales = list(SCALES.keys())

        # Ручной ввод с клавиатуры: None, "bpm", или "steps"
        self.active_input = None
        self.bpm_input_str = str(int(self.song.bpm))
        self.steps_input_str = "16"

        self.dragging_step = None
        self.dragging_slider = None
        self.piano_base_oct_idx = 12

        self.scope_surf = pygame.Surface((124, 52))
        self.rat_frames = build_dancing_ratfolk_frames()
        self.status_msg = "Студия готова! Колесо над громкостью = ±5% сразу для всех паттернов | [Загрузить] открывает выбор файла."
        self.status_timer = 6.0
        self.ui_hitboxes = []

    @property
    def cur_pattern(self):
        if not self.song.patterns:
            self.song.patterns = [PatternData(name="Паттерн 1", steps_count=16)]
        self.cur_pat_idx = max(0, min(len(self.song.patterns) - 1, self.cur_pat_idx))
        return self.song.patterns[self.cur_pat_idx]

    @property
    def cur_channel(self):
        self.selected_ch_idx = max(0, min(7, self.selected_ch_idx))
        return self.cur_pattern.channels[self.selected_ch_idx]

    def set_status(self, msg):
        self.status_msg = msg
        self.status_timer = 5.0

    def _ensure_cur_pattern_visible(self):
        max_vis = 9
        if self.cur_pat_idx < self.pat_scroll_offset:
            self.pat_scroll_offset = self.cur_pat_idx
        elif self.cur_pat_idx >= self.pat_scroll_offset + max_vis:
            self.pat_scroll_offset = self.cur_pat_idx - max_vis + 1

    def _change_pattern_steps(self, new_cnt):
        new_cnt = max(4, min(64, int(new_cnt)))
        self.cur_pattern.resize_steps(new_cnt)
        self.steps_input_str = str(new_cnt)
        max_page = max(0, (new_cnt - 1) // 16)
        self.step_page = min(self.step_page, max_page)
        self.schedule_audio_rebuild()
        self.set_status(f"Длина «{self.cur_pattern.name}» установлена на {new_cnt} шагов.")

    def _commit_active_input(self):
        if self.active_input == "bpm":
            try:
                val = float(self.bpm_input_str)
                self._change_bpm_preserving_phase(val)
                self.set_status(f"Темп установлен: {int(self.song.bpm)} BPM")
            except ValueError:
                pass
            self.bpm_input_str = str(int(self.song.bpm))
        elif self.active_input == "steps":
            try:
                val = int(self.steps_input_str)
                self._change_pattern_steps(val)
            except ValueError:
                pass
            self.steps_input_str = str(self.cur_pattern.steps_count)
        self.active_input = None

    def _change_bpm_preserving_phase(self, new_bpm):
        new_bpm = max(40.0, min(300.0, float(new_bpm)))
        if self.is_playing and new_bpm != self.song.bpm:
            now_t = pygame.time.get_ticks()
            elapsed = (now_t - self.play_start_tick) / 1000.0
            scaled_elapsed = elapsed * (self.song.bpm / new_bpm)
            self.play_start_tick = now_t - int(scaled_elapsed * 1000.0)
        self.song.bpm = new_bpm
        self.bpm_input_str = str(int(self.song.bpm))
        self.schedule_audio_rebuild()

    def _find_covering_step(self, steps_list, target_idx):
        if not steps_list:
            return 0, TrackStep()
        target_idx = max(0, min(len(steps_list) - 1, target_idx))
        for i in range(target_idx, -1, -1):
            st = steps_list[i]
            if st.active and (i + st.length > target_idx):
                return i, st
        return target_idx, steps_list[target_idx]

    def _shift_note_in_scale(self, cur_note, delta):
        scale_notes = SCALES.get(self.selected_scale_name, NOTE_LIST)
        if cur_note in scale_notes:
            idx = scale_notes.index(cur_note)
            return scale_notes[max(0, min(len(scale_notes) - 1, idx + delta))]
        if cur_note in NOTE_LIST:
            idx = NOTE_LIST.index(cur_note)
            return NOTE_LIST[max(0, min(len(NOTE_LIST) - 1, idx + delta))]
        return cur_note

    def play_note_preview(self, inst_id, note_str, length_steps=2):
        dur = min(0.65, (60.0 / self.song.bpm / 4.0) * length_steps)
        params = self.song.synth_params.get(inst_id)
        snd = self.compiler.preview_single_note(inst_id, note_str, dur_sec=dur, params=params)
        self.preview_channel.set_volume(self.editor_volume)
        self.preview_channel.play(snd)

    def start_playback(self, mode=None):
        if mode:
            self.play_mode = mode
        elif self.active_tab == "playlist":
            self.play_mode = "song"
        else:
            self.play_mode = "pattern"

        if self.play_mode == "pattern":
            self.current_sound = self.compiler.compile_pattern(
                self.cur_pattern, self.song.bpm, self.song.synth_params, make_muffled=self.muffled_mode
            )
            self.active_bars_count = 1
        else:
            self.current_sound, self.active_bars_count = self.compiler.compile_song(
                self.song, make_muffled=self.muffled_mode
            )

        self.loop_channel.set_volume(self.editor_volume)
        self.loop_channel.play(self.current_sound, loops=-1)
        self.is_playing = True
        self.play_start_tick = pygame.time.get_ticks()
        self.audio_dirty = False

    def hot_reload_playback(self):
        if not self.is_playing:
            return
        if self.play_mode == "pattern":
            self.compiler.compile_pattern(
                self.cur_pattern, self.song.bpm, self.song.synth_params, make_muffled=self.muffled_mode
            )
            self.active_bars_count = 1
        else:
            _, self.active_bars_count = self.compiler.compile_song(
                self.song, make_muffled=self.muffled_mode
            )

        raw_wave = self.compiler.last_compiled_wave
        if len(raw_wave) > 0:
            elapsed = (pygame.time.get_ticks() - self.play_start_tick) / 1000.0
            offset_samples = int(elapsed * self.compiler.sr) % len(raw_wave)
            shifted_wave = np.roll(raw_wave, -offset_samples)
            self.current_sound = self.compiler.make_pygame_sound(shifted_wave)
            self.loop_channel.set_volume(self.editor_volume)
            self.loop_channel.play(self.current_sound, loops=-1, fade_ms=5)

        self.audio_dirty = False

    def stop_playback(self):
        self.loop_channel.stop()
        self.is_playing = False
        self.playback_step = 0
        self.playback_bar = 0
        self.audio_dirty = False

    def schedule_audio_rebuild(self):
        if self.is_playing:
            self.audio_dirty = True
            self.audio_rebuild_timer = 0.08

    def _default_music_dir(self):
        music_dir = os.path.join(str(PROJECT_ROOT), "music")
        return music_dir if os.path.isdir(music_dir) else str(PROJECT_ROOT)

    def save_song_dialog(self):
        """Открывает диалоговое окно сохранения файла Windows."""
        self.dragging_step = None
        self.dragging_slider = None
        initial_dir = os.path.dirname(self.current_file_path) if self.current_file_path else self._default_music_dir()
        initial_file = os.path.basename(self.current_file_path) if self.current_file_path else "custom_track.json"
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            fpath = filedialog.asksaveasfilename(
                parent=root,
                title="Сохранить трек как JSON",
                initialdir=initial_dir,
                initialfile=initial_file,
                defaultextension=".json",
                filetypes=[("JSON Track Files", "*.json"), ("All Files", "*.*")]
            )
            root.destroy()
        except Exception:
            fpath = os.path.join(initial_dir, initial_file)

        pygame.event.clear()
        if not fpath:
            return
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(self.song.to_dict(), f, ensure_ascii=False, indent=2)
        self.current_file_path = fpath
        self.set_status(f"Сохранено в файл: {os.path.basename(fpath)}")

    def load_song_dialog(self):
        """Открывает диалоговое окно выбора любого .json файла."""
        self.dragging_step = None
        self.dragging_slider = None
        initial_dir = os.path.dirname(self.current_file_path) if self.current_file_path else self._default_music_dir()
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            fpath = filedialog.askopenfilename(
                parent=root,
                title="Выбери JSON-файл трека для загрузки",
                initialdir=initial_dir,
                filetypes=[("JSON Track Files", "*.json"), ("All Files", "*.*")]
            )
            root.destroy()
        except Exception:
            fpath = os.path.join(initial_dir, "custom_track.json")

        pygame.event.clear()
        if not fpath or not os.path.isfile(fpath):
            return
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                self.song = SongData.from_dict(json.load(f))
            self.current_file_path = fpath
            self.cur_pat_idx = 0
            self.pat_scroll_offset = 0
            self.step_page = 0
            self.bpm_input_str = str(int(self.song.bpm))
            self.steps_input_str = str(self.cur_pattern.steps_count)
            self.compiler.synth.invalidate_cache()
            self.schedule_audio_rebuild()
            self.set_status(f"Загружен трек: {os.path.basename(fpath)} (паттернов: {len(self.song.patterns)})")
        except Exception as e:
            self.set_status(f"Ошибка чтения файла: {e}")

    def draw_button(self, rect, text, active=False, accent_col=None, font=None):
        mx, my = pygame.mouse.get_pos()
        hov = rect.collidepoint((mx, my))
        bg = (62, 50, 78) if active else ((44, 38, 56) if hov else SLOT_BG)
        bd = HIGHLIGHT_COL if (active or hov) else (accent_col or BORDER_COL)
        pygame.draw.rect(self.screen, bg, rect, border_radius=4)
        pygame.draw.rect(self.screen, bd, rect, 2 if active else 1, border_radius=4)
        f_use = font or self.font_ui
        lbl = f_use.render(text, True, HIGHLIGHT_COL if active else TEXT_MAIN)
        self.screen.blit(lbl, (rect.x + (rect.width - lbl.get_width()) // 2, rect.y + (rect.height - lbl.get_height()) // 2))
        return rect

    def render_oscilloscope_and_ratfolk(self, now_sec):
        # 1. Осциллограф
        self.scope_surf.fill((14, 12, 18))
        w, h = self.scope_surf.get_size()
        cy = h // 2
        pygame.draw.line(self.scope_surf, (40, 35, 52), (0, cy), (w, cy), 1)

        wave = self.compiler.last_compiled_wave
        if len(wave) > w and (self.is_playing or self.preview_channel.get_busy()):
            if self.is_playing:
                elapsed = (pygame.time.get_ticks() - self.play_start_tick) / 1000.0
                idx0 = int(elapsed * self.compiler.sr) % len(wave)
            else:
                idx0 = 0
            pts = []
            step_s = max(1, (self.compiler.sr // 80) // w)
            for x in range(0, w, 2):
                val = wave[(idx0 + x * step_s) % len(wave)]
                y = int(cy - max(-1.0, min(1.0, val)) * (cy - 4))
                pts.append((x, y))
            if len(pts) >= 2:
                col = (95, 245, 170) if not self.muffled_mode else (95, 155, 255)
                pygame.draw.lines(self.scope_surf, col, False, pts, 2)

        pygame.draw.rect(self.scope_surf, BORDER_COL, (0, 0, w, h), 1)
        self.screen.blit(self.scope_surf, (984, 18))

        # 2. Пляшущий пиксельный Крысолюд (справа вверху)
        rat_box = pygame.Rect(1114, 14, 146, 62)
        pygame.draw.rect(self.screen, SLOT_BG, rat_box, border_radius=5)
        pygame.draw.rect(self.screen, HIGHLIGHT_COL if self.is_playing else BORDER_COL, rat_box, 1, border_radius=5)

        if self.is_playing:
            beat_dur = 60.0 / max(40.0, self.song.bpm)
            frame_idx = int((now_sec / (beat_dur * 0.25))) % 4
            jump_y = -abs(int(math.sin((now_sec / beat_dur) * math.pi) * 4))
        else:
            frame_idx = int(now_sec * 1.5) % 2 * 2
            jump_y = 0

        rat_surf = self.rat_frames[frame_idx]
        if (int(now_sec * (self.song.bpm / 60.0)) % 2 == 1) and self.is_playing:
            rat_surf = pygame.transform.flip(rat_surf, True, False)

        self.screen.blit(rat_surf, (rat_box.x + 8, rat_box.y + 2 + jump_y))


    def run(self):
        running = True
        try:
            while running:
                dt = self.clock.tick(60) / 1000.0
                now_sec = pygame.time.get_ticks() * 0.001
                if self.status_timer > 0:
                    self.status_timer = max(0.0, self.status_timer - dt)

                if self.audio_dirty:
                    self.audio_rebuild_timer -= dt
                    if self.audio_rebuild_timer <= 0.0:
                        self.hot_reload_playback()

                if self.is_playing:
                    beat_len = 60.0 / self.song.bpm
                    step_len = beat_len / 4.0
                    elapsed = (pygame.time.get_ticks() - self.play_start_tick) / 1000.0
                    if self.play_mode == "pattern":
                        steps_cnt = max(1, self.cur_pattern.steps_count)
                        self.playback_step = int(elapsed / step_len) % steps_cnt
                        if self.auto_follow_page and steps_cnt > 16:
                            self.step_page = self.playback_step // 16
                    else:
                        bar_dur = step_len * 16
                        total_dur = bar_dur * max(1, self.active_bars_count)
                        cur_t = elapsed % total_dur
                        self.playback_bar = int(cur_t / bar_dur)
                        self.playback_step = int((cur_t % bar_dur) / step_len)

                mx, my = pygame.mouse.get_pos()

                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False

                    elif event.type == pygame.KEYDOWN:
                        if self.active_input is not None:
                            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                                self._commit_active_input()
                            elif event.key == pygame.K_ESCAPE:
                                self.bpm_input_str = str(int(self.song.bpm))
                                self.steps_input_str = str(self.cur_pattern.steps_count)
                                self.active_input = None
                            elif event.key == pygame.K_BACKSPACE:
                                if self.active_input == "bpm":
                                    self.bpm_input_str = self.bpm_input_str[:-1]
                                elif self.active_input == "steps":
                                    self.steps_input_str = self.steps_input_str[:-1]
                            else:
                                ch = event.unicode
                                if ch and ch.isdigit():
                                    if self.active_input == "bpm" and len(self.bpm_input_str) < 3:
                                        self.bpm_input_str += ch
                                    elif self.active_input == "steps" and len(self.steps_input_str) < 2:
                                        self.steps_input_str += ch
                            continue

                        if event.key == pygame.K_ESCAPE:
                            if self.picker_ch_idx is not None:
                                self.picker_ch_idx = None
                            else:
                                self.stop_playback()
                        elif event.key == pygame.K_SPACE:
                            if self.is_playing:
                                self.stop_playback()
                            else:
                                self.start_playback()
                        elif event.key == pygame.K_1:
                            self.active_tab = "sequencer"
                        elif event.key == pygame.K_2:
                            self.active_tab = "pianoroll"
                        elif event.key == pygame.K_3:
                            self.active_tab = "synth"
                        elif event.key == pygame.K_4:
                            self.active_tab = "playlist"

                    elif event.type == pygame.MOUSEWHEEL:
                        self._handle_mouse_wheel(event.y, mx, my)

                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        if self.active_input is not None:
                            self._commit_active_input()
                        if event.button in (1, 2, 3):
                            self._handle_mouse_down(event.button, mx, my)

                    elif event.type == pygame.MOUSEBUTTONUP:
                        if event.button == 1:
                            self.dragging_step = None
                            self.dragging_slider = None

                    elif event.type == pygame.MOUSEMOTION:
                        self._handle_mouse_drag(mx, my)

                self._render_frame(dt, (mx, my), now_sec)
                pygame.display.flip()
        finally:
            self.stop_playback()
            pygame.quit()

    def _handle_mouse_wheel(self, wheel_y, mx, my):
        if wheel_y == 0 or self.picker_ch_idx is not None:
            return
        mods = pygame.key.get_mods()
        shift_held = bool(mods & pygame.KMOD_SHIFT)

        # 0. Колесо мыши над ползунком общей громкости редактора (шаг 5%)
        for item in self.ui_hitboxes:
            if item[0] == "editor_vol_slider" and item[2].inflate(12, 20).collidepoint((mx, my)):
                self.editor_volume = round(max(0.0, min(1.0, self.editor_volume + wheel_y * 0.05)), 2)
                self.loop_channel.set_volume(self.editor_volume)
                self.preview_channel.set_volume(self.editor_volume)
                self.set_status(f"Громкость редактора: {int(self.editor_volume * 100)}%")
                return

        # 1. Прокрутка списка паттернов колесом мыши над полкой паттернов
        if 132 <= my <= 168 and mx < 860:
            max_off = max(0, len(self.song.patterns) - 9)
            self.pat_scroll_offset = max(0, min(max_off, self.pat_scroll_offset - wheel_y))
            return

        # 2. Колесо над ползунком громкости дорожки меняет громкость ровно по 5% во всём треке!
        for item in self.ui_hitboxes:
            if item[0] == "mix_vol_slider" and item[2].inflate(12, 16).collidepoint((mx, my)):
                _, ch_idx, _ = item
                cur_v = self.cur_pattern.channels[ch_idx]["volume"]
                new_v = round(max(0.0, min(1.0, cur_v + wheel_y * 0.05)), 2)
                self.song.set_channel_volume_globally(ch_idx, new_v)
                self.schedule_audio_rebuild()
                tname = INSTRUMENT_CATALOG[self.cur_pattern.channels[ch_idx]["inst_id"]]["name"]
                self.set_status(f"Громкость «{tname}» (во всех паттернах): {int(new_v * 100)}%")
                return

        # 3. В Плейлисте колесо прокручивает такты по горизонтали
        if self.active_tab == "playlist" and my > 175:
            max_b_off = max(0, self.song.playlist_bars - 16)
            self.pl_bar_scroll = max(0, min(max_b_off, self.pl_bar_scroll - wheel_y * 2))
            return

        # 4. В Пиано-Ролле колесо прокручивает клавиатуру вверх/вниз
        if self.active_tab == "pianoroll" and my > 210:
            self.piano_base_oct_idx = max(0, min(len(NOTE_LIST) - 18, self.piano_base_oct_idx + wheel_y * 2))
            return

        # 5. В Секвенсоре колесо над шагом меняет ноту (а с Shift — длину ноты)
        for item in self.ui_hitboxes:
            if item[0] == "step" and item[3].collidepoint((mx, my)):
                _, ch_idx, s_idx, _ = item
                ch = self.cur_pattern.channels[ch_idx]
                steps_list = ch["steps"]
                root_idx, st = self._find_covering_step(steps_list, s_idx)
                st.active = True
                if shift_held:
                    st.length = max(1, min(len(steps_list) - root_idx, st.length + wheel_y))
                    self.set_status(f"Дорожка {ch_idx+1}: длина ноты = {st.length} шаг.")
                else:
                    st.note = self._shift_note_in_scale(st.note, wheel_y)
                    self.set_status(f"Дорожка {ch_idx+1}: нота {st.note} (Shift+Колесо — длина)")
                self.schedule_audio_rebuild()
                return

    def _handle_mouse_down(self, button, mx, my):
        if self.picker_ch_idx is not None:
            for item in self.ui_hitboxes:
                kind = item[0]
                rect = item[-1]
                if not rect.collidepoint((mx, my)):
                    continue
                if kind == "picker_cat":
                    self.picker_cat = item[1]
                    return
                elif kind == "picker_inst":
                    new_iid = item[1]
                    self.song.set_channel_instrument_globally(self.picker_ch_idx, new_iid)
                    self.selected_synth_inst = new_iid
                    self.selected_synth_cat = INSTRUMENT_CATALOG[new_iid]["cat"]
                    self.schedule_audio_rebuild()
                    self.set_status(f"На дорожку {self.picker_ch_idx+1} назначен инструмент: «{INSTRUMENT_CATALOG[new_iid]['name']}»")
                    self.picker_ch_idx = None
                    return
                elif kind == "picker_close":
                    self.picker_ch_idx = None
                    return
            self.picker_ch_idx = None
            return

        for item in self.ui_hitboxes:
            kind = item[0]
            rect = item[-1]
            if not rect.collidepoint((mx, my)):
                continue

            if kind == "play_pat":
                if self.is_playing and self.play_mode == "pattern":
                    self.stop_playback()
                else:
                    self.start_playback("pattern")
                return
            elif kind == "play_song":
                if self.is_playing and self.play_mode == "song":
                    self.stop_playback()
                else:
                    self.start_playback("song")
                return
            elif kind == "stop":
                self.stop_playback()
                return
            elif kind == "muff":
                self.muffled_mode = not self.muffled_mode
                self.schedule_audio_rebuild()
                return
            elif kind == "bpm_box":
                self.active_input = "bpm"
                self.bpm_input_str = ""
                self.set_status("Введи BPM с клавиатуры (40..300) и нажми Enter...")
                return
            elif kind == "bpm_minus":
                self._change_bpm_preserving_phase(self.song.bpm - 2.0)
                return
            elif kind == "bpm_plus":
                self._change_bpm_preserving_phase(self.song.bpm + 2.0)
                return
            elif kind == "steps_box":
                self.active_input = "steps"
                self.steps_input_str = ""
                self.set_status("Введи длину паттерна в шагах (4..64) и нажми Enter...")
                return
            elif kind == "steps_delta":
                delta = item[1]
                self._change_pattern_steps(self.cur_pattern.steps_count + delta)
                return
            elif kind == "step_page":
                self.step_page = item[1]
                self.auto_follow_page = False
                return
            elif kind == "toggle_follow":
                self.auto_follow_page = not self.auto_follow_page
                return
            elif kind == "scale_cycle":
                idx = (self.available_scales.index(self.selected_scale_name) + 1) % len(self.available_scales)
                self.selected_scale_name = self.available_scales[idx]
                self.set_status(f"Гамма: {self.selected_scale_name}")
                return
            elif kind == "tab":
                self.active_tab = item[1]
                if self.active_tab == "synth":
                    cur_iid = self.cur_channel["inst_id"]
                    self.selected_synth_inst = cur_iid
                    self.selected_synth_cat = INSTRUMENT_CATALOG[cur_iid]["cat"]
                return
            elif kind == "pat_sel":
                self.cur_pat_idx = item[1]
                self.steps_input_str = str(self.cur_pattern.steps_count)
                max_page = max(0, (self.cur_pattern.steps_count - 1) // 16)
                self.step_page = min(self.step_page, max_page)
                self._ensure_cur_pattern_visible()
                if self.is_playing and self.play_mode == "pattern":
                    self.schedule_audio_rebuild()
                return
            elif kind == "pat_scroll":
                delta = item[1]
                max_off = max(0, len(self.song.patterns) - 9)
                self.pat_scroll_offset = max(0, min(max_off, self.pat_scroll_offset + delta))
                return
            elif kind == "pat_add":
                self.cur_pat_idx = self.song.add_new_pattern(copy_from_idx=None)
                self.steps_input_str = str(self.cur_pattern.steps_count)
                self._ensure_cur_pattern_visible()
                self.schedule_audio_rebuild()
                self.set_status(f"Создан чистый «{self.cur_pattern.name}» (всего: {len(self.song.patterns)}).")
                return
            elif kind == "pat_dup":
                self.cur_pat_idx = self.song.add_new_pattern(copy_from_idx=self.cur_pat_idx)
                self.steps_input_str = str(self.cur_pattern.steps_count)
                self._ensure_cur_pattern_visible()
                self.schedule_audio_rebuild()
                self.set_status(f"Скопирован в «{self.cur_pattern.name}»!")
                return
            elif kind == "pat_del":
                if len(self.song.patterns) > 1:
                    del_idx = self.cur_pat_idx
                    self.song.patterns.pop(del_idx)
                    # Корректируем индексы в плейлисте
                    for tr in range(4):
                        for b in range(self.song.playlist_bars):
                            v = self.song.playlist_tracks[tr][b]
                            if v == del_idx:
                                self.song.playlist_tracks[tr][b] = None
                            elif v is not None and v > del_idx:
                                self.song.playlist_tracks[tr][b] = v - 1
                    self.cur_pat_idx = max(0, self.cur_pat_idx - 1)
                    self._ensure_cur_pattern_visible()
                    self.schedule_audio_rebuild()
                    self.set_status("Паттерн удалён.")
                return
            elif kind == "clear_pat":
                self.cur_pattern.clear()
                self.schedule_audio_rebuild()
                self.set_status("Текущий паттерн очищен.")
                return
            elif kind == "ch_select":
                self.selected_ch_idx = item[1]
                iid = self.cur_channel["inst_id"]
                self.selected_synth_inst = iid
                self.selected_synth_cat = INSTRUMENT_CATALOG[iid]["cat"]
                if button == 3:
                    self.active_tab = "pianoroll"
                return
            elif kind == "open_picker":
                ch_i = item[1]
                self.selected_ch_idx = ch_i
                self.picker_ch_idx = ch_i
                cur_iid = self.cur_pattern.channels[ch_i]["inst_id"]
                self.picker_cat = INSTRUMENT_CATALOG[cur_iid]["cat"]
                return
            elif kind == "vol_step":
                _, ch_i, delta_v, _ = item
                cur_v = self.cur_pattern.channels[ch_i]["volume"]
                new_v = round(max(0.0, min(1.0, cur_v + delta_v)), 2)
                self.song.set_channel_volume_globally(ch_i, new_v)
                self.schedule_audio_rebuild()
                return
            elif kind == "mute":
                ch_i = item[1]
                new_m = not self.cur_pattern.channels[ch_i]["mute"]
                self.song.set_channel_mute_globally(ch_i, new_m)
                self.schedule_audio_rebuild()
                return
            elif kind == "solo":
                ch_i = item[1]
                new_s = not self.cur_pattern.channels[ch_i]["solo"]
                self.song.set_channel_solo_globally(ch_i, new_s)
                self.schedule_audio_rebuild()
                return
            elif kind == "step":
                _, ch_idx, s_idx, _ = item
                self.selected_ch_idx = ch_idx
                ch = self.cur_pattern.channels[ch_idx]
                steps_list = ch["steps"]
                if s_idx >= len(steps_list):
                    return
                root_idx, st = self._find_covering_step(steps_list, s_idx)

                if button == 1:
                    if st.active and root_idx == s_idx:
                        self.dragging_step = ("seq_toggle_or_drag", ch_idx, root_idx, st.length)
                    elif st.active and root_idx < s_idx:
                        st.length = s_idx - root_idx + 1
                        self.dragging_step = ("seq_drag", ch_idx, root_idx)
                        self.schedule_audio_rebuild()
                    else:
                        target_st = steps_list[s_idx]
                        target_st.active = True
                        target_st.length = 1
                        self.dragging_step = ("seq_drag", ch_idx, s_idx)
                        self.schedule_audio_rebuild()
                elif button == 2:
                    st.active = True
                    st.slide = not st.slide
                    self.set_status(f"Слайд: {'ВКЛ ~' if st.slide else 'ВЫКЛ'}")
                    self.schedule_audio_rebuild()
                elif button == 3:
                    st.active = False
                    st.length = 1
                    st.slide = False
                    st.extra_notes.clear()
                    self.schedule_audio_rebuild()
                return

            elif kind == "pr_cell":
                _, ch_idx, s_idx, note_str, _ = item
                ch = self.cur_pattern.channels[ch_idx]
                if s_idx >= len(ch["steps"]):
                    return
                st = ch["steps"][s_idx]
                if button == 1:
                    added = st.toggle_piano_note(note_str, default_len=1)
                    if added:
                        self.dragging_step = ("pr_drag", ch_idx, s_idx, note_str)
                    self.schedule_audio_rebuild()
                elif button == 2:
                    st.slide = not st.slide
                    self.schedule_audio_rebuild()
                elif button == 3:
                    if st.active and st.note == note_str:
                        st.toggle_piano_note(note_str)
                    elif note_str in st.extra_notes:
                        del st.extra_notes[note_str]
                    self.schedule_audio_rebuild()
                return

            elif kind == "piano_key":
                _, iid, note_str, _ = item
                self.play_note_preview(iid, note_str, 3)
                return

            elif kind == "synth_cat":
                self.selected_synth_cat = item[1]
                first_iid = next(k for k, v in INSTRUMENT_CATALOG.items() if v["cat"] == self.selected_synth_cat)
                self.selected_synth_inst = first_iid
                return

            elif kind == "synth_inst":
                self.selected_synth_inst = item[1]
                return

            elif kind == "synth_reset_default":
                iid = self.selected_synth_inst
                self.song.reset_instrument_to_default(iid)
                self.compiler.synth.invalidate_cache()
                self.schedule_audio_rebuild()
                self.set_status(f"Настройки «{INSTRUMENT_CATALOG[iid]['name']}» сброшены по умолчанию.")
                return

            elif kind == "synth_assign_to_track":
                iid = self.selected_synth_inst
                self.song.set_channel_instrument_globally(self.selected_ch_idx, iid)
                self.schedule_audio_rebuild()
                self.set_status(f"Инструмент «{INSTRUMENT_CATALOG[iid]['name']}» установлен на Дорожку {self.selected_ch_idx+1}.")
                return

            elif kind == "synth_slider":
                _, param_key, s_rect = item
                self.dragging_slider = ("synth", param_key, s_rect)
                self._update_slider(mx)
                return

            elif kind == "mix_vol_slider":
                _, ch_idx, s_rect = item
                self.dragging_slider = ("mix_vol", ch_idx, s_rect)
                self._update_slider(mx)
                return

            elif kind == "editor_vol_slider":
                _, _, s_rect = item
                self.dragging_slider = ("editor_vol", None, s_rect)
                self._update_slider(mx)
                return

            elif kind == "pl_cell":
                _, tr_idx, b_idx, _ = item
                self.song.ensure_playlist_length(b_idx + 1)
                cur = self.song.playlist_tracks[tr_idx][b_idx]
                if button == 1:
                    max_p = len(self.song.patterns)
                    # Если клетка пустая — ставим текущий выбранный паттерн, если занята — переключаем по кругу
                    self.song.playlist_tracks[tr_idx][b_idx] = self.cur_pat_idx if cur is None else ((cur + 1) % max_p)
                else:
                    self.song.playlist_tracks[tr_idx][b_idx] = None
                self.schedule_audio_rebuild()
                return

            elif kind == "pl_scroll":
                delta = item[1]
                if self.pl_bar_scroll + delta + 16 > self.song.playlist_bars:
                    self.song.ensure_playlist_length(self.pl_bar_scroll + delta + 16)
                self.pl_bar_scroll = max(0, self.pl_bar_scroll + delta)
                return

            elif kind == "preset":
                load_preset_into_song(self.song, item[1])
                self.cur_pat_idx = 0
                self.pat_scroll_offset = 0
                self.step_page = 0
                self.bpm_input_str = str(int(self.song.bpm))
                self.steps_input_str = str(self.cur_pattern.steps_count)
                self.compiler.synth.invalidate_cache()
                self.schedule_audio_rebuild()
                self.set_status(f"Загружен пресет: {item[2]}!")
                return

            elif kind == "save_json":
                self.save_song_dialog()
                return
            elif kind == "load_json":
                self.load_song_dialog()
                return

    def _handle_mouse_drag(self, mx, my):
        if self.dragging_slider:
            self._update_slider(mx)
            return

        if not self.dragging_step:
            return

        mode = self.dragging_step[0]
        page_offset = self.step_page * 16

        if mode in ("seq_drag", "seq_toggle_or_drag"):
            ch_idx = self.dragging_step[1]
            root_idx = self.dragging_step[2]
            grid_start_x = 248
            step_w, step_gap = 60, 4
            steps_list = self.cur_pattern.channels[ch_idx]["steps"]
            max_s = len(steps_list)
            vis_col = max(0, min(15, (mx - grid_start_x) // (step_w + step_gap)))
            hover_step = min(max_s - 1, page_offset + vis_col)
            new_len = max(1, hover_step - root_idx + 1)
            st = steps_list[root_idx]

            if mode == "seq_toggle_or_drag" and hover_step == root_idx:
                st.active = False
                st.length = 1
                self.dragging_step = None
                self.schedule_audio_rebuild()
                return

            self.dragging_step = ("seq_drag", ch_idx, root_idx)
            if st.length != new_len:
                st.length = new_len
                for cov_i in range(root_idx + 1, min(max_s, root_idx + new_len)):
                    steps_list[cov_i].active = False
                self.schedule_audio_rebuild()

        elif mode == "pr_drag":
            _, ch_idx, root_idx, note_str = self.dragging_step
            grid_start_x = 180
            step_w = 66
            steps_list = self.cur_pattern.channels[ch_idx]["steps"]
            max_s = len(steps_list)
            vis_col = max(0, min(15, (mx - grid_start_x) // step_w))
            hover_step = min(max_s - 1, page_offset + vis_col)
            new_len = max(1, hover_step - root_idx + 1)
            st = steps_list[root_idx]
            st.set_note_length(note_str, new_len)
            self.schedule_audio_rebuild()

    def _update_slider(self, mx):
        kind, key, rect = self.dragging_slider
        val = max(0.0, min(1.0, (mx - rect.x) / float(max(1, rect.width))))
        if kind == "synth":
            self.song.synth_params[self.selected_synth_inst][key] = round(val, 2)
            self.compiler.synth.invalidate_cache()
            self.schedule_audio_rebuild()
        elif kind == "mix_vol":
            self.song.set_channel_volume_globally(key, val)
            self.schedule_audio_rebuild()
        elif kind == "editor_vol":
            self.editor_volume = round(val, 2)
            self.loop_channel.set_volume(self.editor_volume)
            self.preview_channel.set_volume(self.editor_volume)

    def _render_frame(self, dt, mouse_pos, now_sec):
        self.screen.fill(BG_DARK)
        self.ui_hitboxes = []

        # ======================================================================
        # ЗОНА 1: ВЕРХНИЙ ТРАНСПОРТНЫЙ БАР (y = 8..84)
        # ======================================================================
        top_bar = pygame.Rect(12, 8, WIN_W - 24, 76)
        pygame.draw.rect(self.screen, PANEL_BG, top_bar, border_radius=6)
        pygame.draw.rect(self.screen, BORDER_COL, top_bar, 2, border_radius=6)

        is_pat_play = (self.is_playing and self.play_mode == "pattern")
        is_sng_play = (self.is_playing and self.play_mode == "song")

        self.ui_hitboxes.append(("play_pat", self.draw_button(pygame.Rect(20, 18, 112, 54), "⏸ ПАТТЕРН" if is_pat_play else "▶ ПАТТЕРН", is_pat_play, (100, 230, 145))))
        self.ui_hitboxes.append(("play_song", self.draw_button(pygame.Rect(138, 18, 102, 54), "⏸ ПЕСНЯ" if is_sng_play else "▶ ПЕСНЯ", is_sng_play, (110, 205, 255))))
        self.ui_hitboxes.append(("stop", self.draw_button(pygame.Rect(246, 18, 60, 54), "⏹ СТОП")))
        self.ui_hitboxes.append(("muff", self.draw_button(pygame.Rect(312, 18, 114, 54), "СТЕНА: ВКЛ" if self.muffled_mode else "СТЕНА: ВЫКЛ", self.muffled_mode, (90, 150, 255))))

        # Ручной ввод BPM
        bpm_rect = pygame.Rect(432, 18, 104, 54)
        is_bpm_active = (self.active_input == "bpm")
        pygame.draw.rect(self.screen, (42, 34, 56) if is_bpm_active else SLOT_BG, bpm_rect, border_radius=4)
        pygame.draw.rect(self.screen, HIGHLIGHT_COL if is_bpm_active else BORDER_COL, bpm_rect, 2 if is_bpm_active else 1, border_radius=4)
        self.screen.blit(self.font_small.render("BPM [Ввод]", True, TEXT_DIM), (bpm_rect.x + 8, bpm_rect.y + 5))
        disp_bpm = (self.bpm_input_str + "|") if is_bpm_active else str(int(self.song.bpm))
        self.screen.blit(self.font_title.render(disp_bpm, True, HIGHLIGHT_COL), (bpm_rect.x + 8, bpm_rect.y + 25))
        self.ui_hitboxes.append(("bpm_box", bpm_rect))
        self.ui_hitboxes.append(("bpm_minus", self.draw_button(pygame.Rect(540, 18, 24, 25), "-")))
        self.ui_hitboxes.append(("bpm_plus", self.draw_button(pygame.Rect(540, 47, 24, 25), "+")))

        # Гамма
        sc_rect = pygame.Rect(570, 18, 178, 54)
        pygame.draw.rect(self.screen, SLOT_BG, sc_rect, border_radius=4)
        pygame.draw.rect(self.screen, BORDER_COL, sc_rect, 1, border_radius=4)
        self.screen.blit(self.font_small.render("ГАММА НОТ", True, TEXT_DIM), (sc_rect.x + 8, sc_rect.y + 5))
        self.screen.blit(self.font_ui.render(self.selected_scale_name[:14], True, (130, 230, 255)), (sc_rect.x + 8, sc_rect.y + 27))
        self.ui_hitboxes.append(("scale_cycle", self.draw_button(pygame.Rect(sc_rect.right - 26, sc_rect.y + 8, 20, 38), ">")))

        # Локальный ползунок громкости редактора (работает только внутри студии!)
        ev_box = pygame.Rect(754, 18, 110, 54)
        pygame.draw.rect(self.screen, SLOT_BG, ev_box, border_radius=4)
        pygame.draw.rect(self.screen, BORDER_COL, ev_box, 1, border_radius=4)
        self.screen.blit(self.font_small.render(f"СТУДИЯ: {int(self.editor_volume * 100)}%", True, HIGHLIGHT_COL), (ev_box.x + 8, ev_box.y + 6))
        ev_bar = pygame.Rect(ev_box.x + 8, ev_box.y + 30, ev_box.width - 16, 14)
        pygame.draw.rect(self.screen, (14, 12, 18), ev_bar, border_radius=3)
        pygame.draw.rect(self.screen, (100, 225, 155), (ev_bar.x, ev_bar.y, int(ev_bar.width * self.editor_volume), ev_bar.height), border_radius=3)
        knob_x = ev_bar.x + int(ev_bar.width * self.editor_volume)
        pygame.draw.rect(self.screen, (245, 245, 250), (knob_x - 3, ev_bar.y - 2, 6, ev_bar.height + 4), border_radius=2)
        pygame.draw.rect(self.screen, BORDER_COL, ev_bar, 1, border_radius=3)
        self.ui_hitboxes.append(("editor_vol_slider", None, ev_bar))

        # Кнопки сохранения и загрузки через проводник Windows
        self.ui_hitboxes.append(("save_json", self.draw_button(pygame.Rect(870, 18, 108, 25), "💾 Сохранить", False, (100, 220, 140), self.font_small)))
        self.ui_hitboxes.append(("load_json", self.draw_button(pygame.Rect(870, 47, 108, 25), "📂 Загрузить", False, (110, 195, 255), self.font_small)))

        self.render_oscilloscope_and_ratfolk(now_sec)

        # ======================================================================
        # ЗОНА 2: ГЛАВНЫЕ ВКЛАДКИ И ПРЕСЕТЫ (y = 88..126)
        # ======================================================================
        nav_bar = pygame.Rect(12, 88, WIN_W - 24, 38)
        pygame.draw.rect(self.screen, PANEL_BG, nav_bar, border_radius=5)
        pygame.draw.rect(self.screen, BORDER_COL, nav_bar, 1, border_radius=5)

        tabs = [
            ("sequencer", "[1] СЕКВЕНСОР"),
            ("pianoroll", "[2] ПИАНО-РОЛЛ"),
            ("synth",     "[3] СИНТЕЗАТОР"),
            ("playlist",  "[4] ПЛЕЙЛИСТ"),
        ]
        tx = 18
        for t_id, t_lbl in tabs:
            w_t = 156
            r_t = self.draw_button(pygame.Rect(tx, 93, w_t, 28), t_lbl, self.active_tab == t_id)
            self.ui_hitboxes.append(("tab", t_id, r_t))
            tx += w_t + 6

        # Быстрые пресеты и очистка справа во 2-й зоне
        self.ui_hitboxes.append(("preset", "bard_ballad",    "Баллада Барда", self.draw_button(pygame.Rect(680, 93, 110, 28), "Пресет: Бард", False, (245, 185, 80), self.font_small)))
        self.ui_hitboxes.append(("preset", "medieval_march", "Марш Медивал",  self.draw_button(pygame.Rect(796, 93, 115, 28), "Пресет: Лира", False, (235, 120, 75), self.font_small)))
        self.ui_hitboxes.append(("preset", "grunge_drive",   "Гранж-Драйв",   self.draw_button(pygame.Rect(917, 93, 115, 28), "Пресет: Рок", False, (230, 90, 170), self.font_small)))
        self.ui_hitboxes.append(("preset", "boss_metal",     "Босс-Метал",    self.draw_button(pygame.Rect(1038, 93, 110, 28), "Пресет: Босс", False, (240, 80, 80), self.font_small)))
        self.ui_hitboxes.append(("clear_pat", self.draw_button(pygame.Rect(1154, 93, 104, 28), "Очистить П.", False, (205, 85, 85), self.font_small)))

        # ======================================================================
        # ЗОНА 3: ПОЛКА ПАТТЕРНОВ С ПРОКРУТКОЙ + ДЛИНА ПАТТЕРНА (y = 130..168)
        # ======================================================================
        pat_shelf = pygame.Rect(12, 130, WIN_W - 24, 38)
        pygame.draw.rect(self.screen, (22, 19, 30), pat_shelf, border_radius=5)
        pygame.draw.rect(self.screen, BORDER_COL, pat_shelf, 1, border_radius=5)

        total_pats = len(self.song.patterns)
        self.screen.blit(self.font_small.render(f"ПАТТЕРНЫ ({self.cur_pat_idx+1}/{total_pats}):", True, HIGHLIGHT_COL), (20, 143))

        # Кнопка прокрутки паттернов влево [<]
        self.ui_hitboxes.append(("pat_scroll", -1, self.draw_button(pygame.Rect(148, 135, 24, 28), "<", False, None, self.font_small)))

        max_vis_pats = 8
        px_cur = 176
        for vis_i in range(max_vis_pats):
            p_i = self.pat_scroll_offset + vis_i
            if p_i >= total_pats:
                break
            p_r = self.draw_button(pygame.Rect(px_cur, 135, 54, 28), f"П{p_i+1}", self.cur_pat_idx == p_i, None, self.font_small)
            self.ui_hitboxes.append(("pat_sel", p_i, p_r))
            px_cur += 58

        # Кнопка прокрутки паттернов вправо [>]
        self.ui_hitboxes.append(("pat_scroll", 1, self.draw_button(pygame.Rect(px_cur, 135, 24, 28), ">", False, None, self.font_small)))
        px_cur += 28

        # Управление списком паттернов: [+ Новый], [Копия], [- Удал]
        self.ui_hitboxes.append(("pat_add", self.draw_button(pygame.Rect(px_cur, 135, 64, 28), "+ Новый", False, (100, 220, 140), self.font_small)))
        self.ui_hitboxes.append(("pat_dup", self.draw_button(pygame.Rect(px_cur + 68, 135, 58, 28), "Копия", False, (110, 200, 255), self.font_small)))
        if total_pats > 1:
            self.ui_hitboxes.append(("pat_del", self.draw_button(pygame.Rect(px_cur + 130, 135, 32, 28), "-", False, (220, 95, 95), self.font_small)))

        # Правая часть Зоны 3: Длина паттерна (ручной ввод + кнопки -4, -1, +1, +4)
        self.screen.blit(self.font_small.render("ШАГОВ В ПАТТЕРНЕ:", True, TEXT_DIM), (885, 143))
        st_box = pygame.Rect(1010, 135, 64, 28)
        is_st_act = (self.active_input == "steps")
        pygame.draw.rect(self.screen, (42, 34, 56) if is_st_act else SLOT_BG, st_box, border_radius=4)
        pygame.draw.rect(self.screen, HIGHLIGHT_COL if is_st_act else BORDER_COL, st_box, 2 if is_st_act else 1, border_radius=4)
        disp_steps = (self.steps_input_str + "|") if is_st_act else str(self.cur_pattern.steps_count)
        self.screen.blit(self.font_ui.render(disp_steps, True, HIGHLIGHT_COL), (st_box.x + 14, st_box.y + 6))
        self.ui_hitboxes.append(("steps_box", st_box))

        self.ui_hitboxes.append(("steps_delta", -4, self.draw_button(pygame.Rect(1080, 135, 40, 28), "-4", False, (215, 95, 95), self.font_small)))
        self.ui_hitboxes.append(("steps_delta", -1, self.draw_button(pygame.Rect(1124, 135, 36, 28), "-1", False, (215, 135, 95), self.font_small)))
        self.ui_hitboxes.append(("steps_delta", 1,  self.draw_button(pygame.Rect(1164, 135, 36, 28), "+1", False, (115, 220, 145), self.font_small)))
        self.ui_hitboxes.append(("steps_delta", 4,  self.draw_button(pygame.Rect(1204, 135, 44, 28), "+4", False, (100, 230, 140), self.font_small)))

        # ======================================================================
        # ЗОНА 4: СОДЕРЖИМОЕ АКТИВНОЙ ВКЛАДКИ (СТРОГО y >= 174, НИКАКИХ НАЕЗДОВ!)
        # ======================================================================
        if self.active_tab == "sequencer":
            self._render_sequencer_tab()
        elif self.active_tab == "pianoroll":
            self._render_pianoroll_tab()
        elif self.active_tab == "synth":
            self._render_synth_tab()
        elif self.active_tab == "playlist":
            self._render_playlist_tab()

        if self.picker_ch_idx is not None:
            self._render_instrument_picker_modal()

        # ======================================================================
        # ЗОНА 5: СТАТУС-БАР ВНИЗУ (y = 804..832)
        # ======================================================================
        bot_bar = pygame.Rect(12, WIN_H - 36, WIN_W - 24, 28)
        pygame.draw.rect(self.screen, PANEL_BG, bot_bar, border_radius=4)
        pygame.draw.rect(self.screen, BORDER_COL, bot_bar, 1, border_radius=4)
        self.screen.blit(self.font_small.render(self.status_msg, True, HIGHLIGHT_COL if self.status_timer > 0 else TEXT_DIM), (22, WIN_H - 28))

    def _render_step_pagination_bar(self, y_pos):
        """Если в паттерне больше 16 шагов, рисует удобные вкладки страниц по 16 шагов."""
        steps_cnt = self.cur_pattern.steps_count
        total_pages = math.ceil(steps_cnt / 16.0)
        self.step_page = max(0, min(total_pages - 1, self.step_page))
        if total_pages <= 1:
            return y_pos

        bar_r = pygame.Rect(248, y_pos, WIN_W - 260, 26)
        pygame.draw.rect(self.screen, (24, 20, 32), bar_r, border_radius=4)
        pygame.draw.rect(self.screen, BORDER_COL, bar_r, 1, border_radius=4)

        self.screen.blit(self.font_small.render("СТРАНИЦЫ ШАГОВ:", True, TEXT_DIM), (258, y_pos + 7))
        for pg in range(total_pages):
            s_start = pg * 16 + 1
            s_end = min(steps_cnt, (pg + 1) * 16)
            pr = self.draw_button(
                pygame.Rect(380 + pg * 145, y_pos + 2, 138, 22),
                f"Стр.{pg+1} [{s_start}..{s_end}]", self.step_page == pg, None, self.font_small
            )
            self.ui_hitboxes.append(("step_page", pg, pr))

        flw_txt = "Авто-скролл: ВКЛ" if self.auto_follow_page else "Авто-скролл: ВЫКЛ"
        fr = self.draw_button(pygame.Rect(WIN_W - 175, y_pos + 2, 155, 22), flw_txt, self.auto_follow_page, None, self.font_small)
        self.ui_hitboxes.append(("toggle_follow", fr))
        return y_pos + 30

    def _render_sequencer_tab(self):
        matrix_y = self._render_step_pagination_bar(174)
        avail_h = (WIN_H - 42) - matrix_y
        row_h = max(62, min(72, (avail_h // 8) - 4))
        row_gap = 4
        grid_start_x = 248
        step_w = 60
        step_gap = 4

        steps_cnt = self.cur_pattern.steps_count
        page_start = self.step_page * 16
        page_end = min(steps_cnt, page_start + 16)

        for ch_idx, ch in enumerate(self.cur_pattern.channels):
            tid = ch["inst_id"]
            tdef = INSTRUMENT_CATALOG.get(tid, INSTRUMENT_CATALOG["dist_guitar"])
            ry = matrix_y + ch_idx * (row_h + row_gap)
            is_sel_ch = (self.selected_ch_idx == ch_idx)

            # Левая плашка дорожки
            c_box = pygame.Rect(12, ry, 226, row_h)
            pygame.draw.rect(self.screen, (38, 33, 50) if is_sel_ch else PANEL_BG, c_box, border_radius=4)
            pygame.draw.rect(self.screen, tdef["color"], (c_box.x + 3, c_box.y + 3, 5, row_h - 6), border_radius=2)
            pygame.draw.rect(self.screen, HIGHLIGHT_COL if is_sel_ch else BORDER_COL, c_box, 2 if is_sel_ch else 1, border_radius=4)

            swap_r = self.draw_button(pygame.Rect(c_box.x + 10, c_box.y + 6, 26, 24), "⇄", False, tdef["color"], self.font_small)
            self.ui_hitboxes.append(("open_picker", ch_idx, swap_r))

            name_rect = pygame.Rect(c_box.x + 40, c_box.y + 6, 114, 24)
            self.screen.blit(self.font_ui.render(tdef["name"][:13], True, HIGHLIGHT_COL if is_sel_ch else TEXT_MAIN), (name_rect.x, name_rect.y + 3))
            self.ui_hitboxes.append(("ch_select", ch_idx, name_rect))

            # Удобный глобальный регулятор громкости дорожки + кнопки - / +
            v_minus = self.draw_button(pygame.Rect(c_box.x + 10, c_box.y + 35, 18, 22), "-", False, None, self.font_small)
            v_bar = pygame.Rect(c_box.x + 31, c_box.y + 36, 98, 20)
            v_plus = self.draw_button(pygame.Rect(c_box.x + 132, c_box.y + 35, 18, 22), "+", False, None, self.font_small)

            pygame.draw.rect(self.screen, (14, 12, 18), v_bar, border_radius=3)
            pygame.draw.rect(self.screen, tdef["color"], (v_bar.x, v_bar.y, int(v_bar.width * ch["volume"]), v_bar.height), border_radius=3)
            pygame.draw.rect(self.screen, BORDER_COL, v_bar, 1, border_radius=3)
            v_lbl = self.font_small.render(f"{int(ch['volume']*100)}%", True, (255, 255, 255))
            self.screen.blit(v_lbl, (v_bar.centerx - v_lbl.get_width() // 2, v_bar.y + 4))

            self.ui_hitboxes.append(("vol_step", ch_idx, -0.05, v_minus))
            self.ui_hitboxes.append(("mix_vol_slider", ch_idx, v_bar))
            self.ui_hitboxes.append(("vol_step", ch_idx, 0.05, v_plus))

            m_col = (230, 75, 75) if ch["mute"] else BORDER_COL
            s_col = (240, 200, 60) if ch["solo"] else BORDER_COL
            r_m = self.draw_button(pygame.Rect(c_box.x + 156, c_box.y + 10, 30, row_h - 20), "M", ch["mute"], m_col)
            r_s = self.draw_button(pygame.Rect(c_box.x + 190, c_box.y + 10, 30, row_h - 20), "S", ch["solo"], s_col)
            self.ui_hitboxes.append(("mute", ch_idx, r_m))
            self.ui_hitboxes.append(("solo", ch_idx, r_s))

            # ПРОХОД 1: Ячейки текущей страницы (до 16 штук)
            for s_idx in range(page_start, page_end):
                vis_col = s_idx - page_start
                sx = grid_start_x + vis_col * (step_w + step_gap)
                btn_rect = pygame.Rect(sx, ry, step_w, row_h)
                is_beat = (s_idx % 4 == 0)
                bg_step = (35, 30, 46) if is_beat else SLOT_BG
                pygame.draw.rect(self.screen, bg_step, btn_rect, border_radius=3)
                pygame.draw.rect(self.screen, (105, 92, 125) if is_beat else BORDER_COL, btn_rect, 1, border_radius=3)
                self.screen.blit(self.font_small.render(str(s_idx + 1), True, (85, 78, 100)), (sx + 4, ry + 3))
                self.ui_hitboxes.append(("step", ch_idx, s_idx, btn_rect))

            # ПРОХОД 2: Цельные полосы активных нот на текущей странице
            for s_idx in range(steps_cnt):
                st = ch["steps"][s_idx]
                if not st.active:
                    continue
                note_end = min(steps_cnt, s_idx + st.length)
                if note_end <= page_start or s_idx >= page_end:
                    continue

                vis_start = max(page_start, s_idx) - page_start
                vis_end = min(page_end, note_end) - page_start
                eff_len = max(1, vis_end - vis_start)

                sx = grid_start_x + vis_start * (step_w + step_gap)
                span_w = eff_len * step_w + (eff_len - 1) * step_gap - 4
                note_bar = pygame.Rect(sx + 2, ry + 16, span_w, row_h - 20)

                pygame.draw.rect(self.screen, tdef["color"], note_bar, border_radius=4)
                pygame.draw.rect(self.screen, (255, 255, 255), note_bar, 1, border_radius=4)
                pygame.draw.rect(self.screen, (30, 24, 38), (note_bar.right - 7, note_bar.y + 5, 4, note_bar.height - 10), border_radius=2)

                lbl_txt = st.note
                if len(st.extra_notes) > 0:
                    lbl_txt += f"+{len(st.extra_notes)}"
                if st.length > 1:
                    lbl_txt += f" [{st.length}ш]"
                if st.slide:
                    lbl_txt += " ~"
                n_surf = self.font_ui.render(lbl_txt, True, (18, 14, 22))
                self.screen.blit(n_surf, (note_bar.x + 8, note_bar.centery - n_surf.get_height() // 2))

        if self.is_playing and page_start <= self.playback_step < page_end:
            vis_head = self.playback_step - page_start
            head_x = grid_start_x + vis_head * (step_w + step_gap) + step_w // 2
            pygame.draw.line(self.screen, (255, 235, 110), (head_x, matrix_y - 2), (head_x, matrix_y + 8 * (row_h + row_gap)), 3)

    def _render_instrument_picker_modal(self):
        ov = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        ov.fill((10, 8, 16, 185))
        self.screen.blit(ov, (0, 0))

        cat_insts = [(k, v) for k, v in INSTRUMENT_CATALOG.items() if v["cat"] == self.picker_cat]
        rows_cnt = max(3, math.ceil(len(cat_insts) / 2.0))
        mw = 760
        mh = max(390, 168 + rows_cnt * 68)
        mx0, my0 = (WIN_W - mw) // 2, (WIN_H - mh) // 2
        m_rect = pygame.Rect(mx0, my0, mw, mh)
        pygame.draw.rect(self.screen, PANEL_BG, m_rect, border_radius=8)
        pygame.draw.rect(self.screen, HIGHLIGHT_COL, m_rect, 2, border_radius=8)

        title = f"ВЫБОР ИНСТРУМЕНТА ДЛЯ ДОРОЖКИ {self.picker_ch_idx + 1}"
        self.screen.blit(self.font_title.render(title, True, HIGHLIGHT_COL), (mx0 + 24, my0 + 18))
        close_r = self.draw_button(pygame.Rect(mx0 + mw - 110, my0 + 14, 90, 28), "Закрыть", False, (215, 85, 85), self.font_small)
        self.ui_hitboxes.append(("picker_close", close_r))

        self.screen.blit(self.font_small.render("1. ВЫБЕРИ ТИП ИНСТРУМЕНТА:", True, TEXT_DIM), (mx0 + 24, my0 + 56))
        n_cats = max(1, len(INSTRUMENT_CATEGORIES))
        cat_gap = 8
        cat_w = (mw - 48 - (n_cats - 1) * cat_gap) // n_cats
        cat_font = self.font_small if cat_w < 130 else self.font_ui
        for c_i, (cat_id, cat_name) in enumerate(INSTRUMENT_CATEGORIES):
            cr = self.draw_button(pygame.Rect(mx0 + 24 + c_i * (cat_w + cat_gap), my0 + 76, cat_w, 36), cat_name, self.picker_cat == cat_id, font=cat_font)
            self.ui_hitboxes.append(("picker_cat", cat_id, cr))

        self.screen.blit(self.font_small.render("2. ВЫБЕРИ ТЕМБР:", True, TEXT_DIM), (mx0 + 24, my0 + 128))
        cur_iid = self.cur_pattern.channels[self.picker_ch_idx]["inst_id"]
        col_gap = 12
        col_w = (mw - 48 - col_gap) // 2

        for idx, (iid, idef) in enumerate(cat_insts):
            col = idx % 2
            row = idx // 2
            ir = pygame.Rect(mx0 + 24 + col * (col_w + col_gap), my0 + 152 + row * 68, col_w, 56)
            r_btn = self.draw_button(ir, idef["name"], cur_iid == iid, idef["color"])
            pygame.draw.rect(self.screen, idef["color"], (ir.x + 6, ir.y + 6, 8, ir.height - 12), border_radius=3)
            self.ui_hitboxes.append(("picker_inst", iid, r_btn))

    def _render_pianoroll_tab(self):
        # Начинается строго на y = 174 (под полкой паттернов!)
        top_y = self._render_step_pagination_bar(174)
        for ch_i, ch in enumerate(self.cur_pattern.channels):
            idef = INSTRUMENT_CATALOG[ch["inst_id"]]
            r = self.draw_button(
                pygame.Rect(12 + ch_i * 158, top_y, 152, 28),
                f"{ch_i+1}:{idef['name'][:11]}", self.selected_ch_idx == ch_i, idef["color"], self.font_small
            )
            self.ui_hitboxes.append(("ch_select", ch_i, r))

        ch = self.cur_channel
        tdef = INSTRUMENT_CATALOG[ch["inst_id"]]
        scale_set = set(SCALES.get(self.selected_scale_name, NOTE_LIST))
        steps_cnt = self.cur_pattern.steps_count
        page_start = self.step_page * 16
        page_end = min(steps_cnt, page_start + 16)

        pr_y = top_y + 34
        rows_count = 18
        row_h = max(26, min(31, (WIN_H - 44 - pr_y) // rows_count))
        key_w = 160
        grid_start_x = 180
        step_w = 66

        vis_notes = list(reversed(NOTE_LIST[self.piano_base_oct_idx:self.piano_base_oct_idx + rows_count]))

        for r_i, note_str in enumerate(vis_notes):
            ry = pr_y + r_i * row_h
            is_sharp = "#" in note_str
            in_scale = note_str in scale_set

            k_rect = pygame.Rect(12, ry, key_w, row_h - 1)
            k_bg = (30, 26, 40) if is_sharp else (215, 210, 200)
            k_txt_col = HIGHLIGHT_COL if is_sharp else (24, 20, 30)
            pygame.draw.rect(self.screen, k_bg, k_rect, border_radius=3)
            if in_scale:
                pygame.draw.rect(self.screen, tdef["color"], (k_rect.right - 10, k_rect.y + 4, 6, row_h - 9), border_radius=2)
            self.screen.blit(self.font_ui.render(note_str, True, k_txt_col), (k_rect.x + 12, k_rect.y + 5))
            self.ui_hitboxes.append(("piano_key", ch["inst_id"], note_str, k_rect))

            for s_idx in range(page_start, page_end):
                vis_col = s_idx - page_start
                sx = grid_start_x + vis_col * step_w
                c_rect = pygame.Rect(sx, ry, step_w - 1, row_h - 1)
                bg = (34, 30, 46) if in_scale else (20, 17, 26)
                if s_idx % 4 == 0:
                    bg = (bg[0] + 8, bg[1] + 8, bg[2] + 10)
                pygame.draw.rect(self.screen, bg, c_rect)
                pygame.draw.rect(self.screen, (48, 42, 62), c_rect, 1)
                self.ui_hitboxes.append(("pr_cell", self.selected_ch_idx, s_idx, note_str, c_rect))

        for s_idx in range(steps_cnt):
            st = ch["steps"][s_idx]
            notes_map = st.get_all_notes()
            for n_str, n_len in notes_map.items():
                if n_str not in vis_notes:
                    continue
                note_end = min(steps_cnt, s_idx + n_len)
                if note_end <= page_start or s_idx >= page_end:
                    continue
                vis_start = max(page_start, s_idx) - page_start
                vis_end = min(page_end, note_end) - page_start
                eff_len = max(1, vis_end - vis_start)

                r_i = vis_notes.index(n_str)
                ry = pr_y + r_i * row_h
                sx = grid_start_x + vis_start * step_w
                bar_r = pygame.Rect(sx + 2, ry + 2, eff_len * step_w - 5, row_h - 5)
                pygame.draw.rect(self.screen, tdef["color"], bar_r, border_radius=4)
                pygame.draw.rect(self.screen, (255, 255, 255), bar_r, 1, border_radius=4)
                lbl = f"{n_str} {'~' if st.slide else ''}"
                self.screen.blit(self.font_small.render(lbl, True, (18, 14, 24)), (bar_r.x + 6, bar_r.y + 5))

        if self.is_playing and page_start <= self.playback_step < page_end:
            vis_head = self.playback_step - page_start
            head_x = grid_start_x + vis_head * step_w + step_w // 2
            pygame.draw.line(self.screen, (255, 235, 110), (head_x, pr_y), (head_x, pr_y + rows_count * row_h), 3)

    def _render_synth_tab(self):
        # Начинается строго на y = 176 (под полкой паттернов!)
        self.screen.blit(self.font_small.render("ТИП ИНСТРУМЕНТА:", True, TEXT_DIM), (16, 184))
        n_cats = max(1, len(INSTRUMENT_CATEGORIES))
        cat_gap = 8
        cat_w = min(148, (WIN_W - 165 - (n_cats - 1) * cat_gap) // n_cats)
        for c_i, (cat_id, cat_name) in enumerate(INSTRUMENT_CATEGORIES):
            cr = self.draw_button(pygame.Rect(145 + c_i * (cat_w + cat_gap), 176, cat_w, 28), cat_name, self.selected_synth_cat == cat_id)
            self.ui_hitboxes.append(("synth_cat", cat_id, cr))

        cat_insts = [(k, v) for k, v in INSTRUMENT_CATALOG.items() if v["cat"] == self.selected_synth_cat]
        n_inst = max(1, len(cat_insts))
        inst_gap = 8
        inst_w = min(200, (WIN_W - 24 - (n_inst - 1) * inst_gap) // n_inst)
        inst_font = self.font_small if inst_w < 170 else self.font_ui
        for idx, (iid, idef) in enumerate(cat_insts):
            ir = self.draw_button(
                pygame.Rect(12 + idx * (inst_w + inst_gap), 210, inst_w, 30),
                idef["name"], self.selected_synth_inst == iid, idef["color"], inst_font
            )
            self.ui_hitboxes.append(("synth_inst", iid, ir))

        tdef = INSTRUMENT_CATALOG[self.selected_synth_inst]
        params = self.song.synth_params[self.selected_synth_inst]

        box = pygame.Rect(12, 246, WIN_W - 24, 382)
        pygame.draw.rect(self.screen, PANEL_BG, box, border_radius=6)
        pygame.draw.rect(self.screen, tdef["color"], box, 2, border_radius=6)

        self.screen.blit(self.font_title.render(f"НАСТРОЙКИ ТЕМБРА: {tdef['name'].upper()}", True, tdef["color"]), (32, 260))

        assign_r = self.draw_button(
            pygame.Rect(560, 254, 310, 30),
            f"Назначить на Дорожку {self.selected_ch_idx + 1}", False, (110, 215, 255), self.font_small
        )
        self.ui_hitboxes.append(("synth_assign_to_track", assign_r))

        reset_r = self.draw_button(
            pygame.Rect(882, 254, 360, 30),
            "↺ ВОССТАНОВИТЬ НАСТРОЙКИ ПО УМОЛЧАНИЮ", False, (245, 185, 80), self.font_small
        )
        self.ui_hitboxes.append(("synth_reset_default", reset_r))

        sliders_cfg = [
            ("drive",  "Насыщение / Перегруз (Drive)",         "Добавляет теплоту деки или ламповый перегруз"),
            ("cutoff", "Яркость Тембра (Filter Cutoff)",       "Открывает звонкие верха или делает звук мягче"),
            ("punch",  "Атака / Щипок Струны (Punch)",         "Сила удара медиатора, пера лютни или смычка лиры"),
            ("detune", "Хорус / Парные Струны (Detune)",       "Расстройка парных струн и глубина вибрато"),
            ("decay",  "Сустейн и Длина Хвоста (Decay)",       "Длительность затухания струны, колокола или меха"),
            ("fifth",  "Бурдон / Квинта (+7 полутонов)",       "Подмешивает бурдон волынки/лиры или рок-квинту"),
        ]

        for idx, (p_key, p_title, p_desc) in enumerate(sliders_cfg):
            sy = 296 + idx * 52
            val = params.get(p_key, 0.5)
            def_val = DEFAULT_SYNTH_PARAMS[self.selected_synth_inst].get(p_key, 0.5)

            self.screen.blit(self.font_ui.render(f"{p_title}: {int(val * 100)}% (по умолч. {int(def_val * 100)}%)", True, TEXT_MAIN), (34, sy))
            self.screen.blit(self.font_small.render(p_desc, True, TEXT_DIM), (34, sy + 18))

            s_rect = pygame.Rect(560, sy + 6, 480, 20)
            pygame.draw.rect(self.screen, (14, 12, 18), s_rect, border_radius=4)
            pygame.draw.rect(self.screen, tdef["color"], (s_rect.x, s_rect.y, int(s_rect.width * val), s_rect.height), border_radius=4)
            def_x = s_rect.x + int(s_rect.width * def_val)
            pygame.draw.line(self.screen, HIGHLIGHT_COL, (def_x, s_rect.y - 3), (def_x, s_rect.bottom + 3), 2)
            pygame.draw.rect(self.screen, (250, 250, 255), (s_rect.x + int(s_rect.width * val) - 4, s_rect.y - 2, 8, s_rect.height + 4), border_radius=2)
            pygame.draw.rect(self.screen, BORDER_COL, s_rect, 1, border_radius=4)
            self.ui_hitboxes.append(("synth_slider", p_key, s_rect))

        self.screen.blit(self.font_title.render("ТЕСТОВЫЕ КЛАВИШИ (КЛИКАЙ ДЛЯ ПРОВЕРКИ ТЕМБРА):", True, HIGHLIGHT_COL), (32, 636))
        test_notes = ["D2", "F2", "G2", "A2", "C3", "D3", "F3", "G3", "A3", "C4", "D4", "F4", "G4", "A4", "C5", "D5"]
        for k_i, n_str in enumerate(test_notes):
            kr = self.draw_button(pygame.Rect(24 + k_i * 77, 664, 72, 124), n_str, False, tdef["color"])
            self.ui_hitboxes.append(("piano_key", self.selected_synth_inst, n_str, kr))

    def _render_playlist_tab(self):
        # Начинается строго на y = 178 (под полкой паттернов!)
        pl_y = 178
        self.screen.blit(self.font_title.render("ПЛЕЙЛИСТ АРАНЖИРОВКИ (ЛКМ — поставить паттерн, ПКМ — очистить такт):", True, HIGHLIGHT_COL), (18, pl_y))

        # Кнопки прокрутки тактов плейлиста (бесконечное расширение трека вправо)
        self.ui_hitboxes.append(("pl_scroll", -4, self.draw_button(pygame.Rect(820, pl_y - 4, 90, 28), "<< Такты", False, None, self.font_small)))
        self.ui_hitboxes.append(("pl_scroll", 4,  self.draw_button(pygame.Rect(916, pl_y - 4, 105, 28), "Такты >> (+)", False, (100, 220, 140), self.font_small)))

        bar_w = 64
        bar_gap = 4
        track_h = 132
        grid_start_x = 180
        p_colors = [(240, 85, 95), (85, 165, 255), (90, 235, 165), (225, 130, 255), (245, 195, 70), (120, 230, 240)]

        for tr in range(4):
            ty = pl_y + 34 + tr * (track_h + 10)
            t_box = pygame.Rect(12, ty, 156, track_h)
            pygame.draw.rect(self.screen, PANEL_BG, t_box, border_radius=4)
            pygame.draw.rect(self.screen, BORDER_COL, t_box, 1, border_radius=4)
            self.screen.blit(self.font_ui.render(f"Дорожка {tr + 1}", True, HIGHLIGHT_COL), (t_box.x + 16, t_box.y + 16))
            self.screen.blit(self.font_small.render("Слой микса", True, TEXT_DIM), (t_box.x + 16, t_box.y + 40))

            for vis_b in range(16):
                b = self.pl_bar_scroll + vis_b
                bx = grid_start_x + vis_b * (bar_w + bar_gap)
                b_rect = pygame.Rect(bx, ty, bar_w, track_h)
                p_val = self.song.playlist_tracks[tr][b] if b < self.song.playlist_bars else None
                is_cur = (self.is_playing and self.play_mode == "song" and self.playback_bar == b)

                pygame.draw.rect(self.screen, (38, 34, 52) if b % 4 == 0 else SLOT_BG, b_rect, border_radius=3)
                pygame.draw.rect(self.screen, (255, 235, 110) if is_cur else BORDER_COL, b_rect, 2 if is_cur else 1, border_radius=3)
                self.screen.blit(self.font_small.render(f"Т{b+1}", True, (90, 82, 105)), (bx + 4, ty + 4))

                if p_val is not None and 0 <= p_val < len(self.song.patterns):
                    blk = pygame.Rect(bx + 3, ty + 24, bar_w - 6, track_h - 30)
                    pygame.draw.rect(self.screen, p_colors[p_val % len(p_colors)], blk, border_radius=4)
                    pygame.draw.rect(self.screen, (255, 255, 255), blk, 1, border_radius=4)
                    ps = self.font_ui.render(f"П{p_val+1}", True, (20, 16, 24))
                    self.screen.blit(ps, (blk.centerx - ps.get_width() // 2, blk.centery - ps.get_height() // 2))

                self.ui_hitboxes.append(("pl_cell", tr, b, b_rect))

        if self.is_playing and self.play_mode == "song":
            if self.pl_bar_scroll <= self.playback_bar < self.pl_bar_scroll + 16:
                vis_b = self.playback_bar - self.pl_bar_scroll
                head_x = grid_start_x + vis_b * (bar_w + bar_gap) + int((self.playback_step / 16.0) * bar_w)
                pygame.draw.line(self.screen, (255, 235, 110), (head_x, pl_y + 30), (head_x, pl_y + 34 + 4 * (track_h + 10)), 3)


if __name__ == "__main__":
    app = MusicStudioApp()
    app.run()
