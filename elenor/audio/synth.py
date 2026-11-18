from elenor.paths import PROJECT_ROOT
import numpy as np
import pygame
import math


from elenor.audio.voices import enemy_voice_waves


MENU_MUSIC_GAIN = 0.25


class SoundSynth:
    def __init__(self):
        self.enabled = False
        self.volume = 0.85
        self.sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            pygame.mixer.set_num_channels(20)
            self.freq, _, self.channels = pygame.mixer.get_init()
            self.enabled = True
            self.disco_channel = None
            self.disco_sound = None
            self.disco_cur_dry = [0.0, 0.0]
            self.disco_cur_muff = [0.0, 0.0]
            self._build_bank()
            self._build_fishing_bank()
            for name, wave, cutoff in enemy_voice_waves(self.freq):
                self._register(name, wave, make_muff=True, cutoff=cutoff)
        except Exception:
            self.enabled = False

    def _make_sound(self, wave_float):
        clipped = np.clip(wave_float * 32767.0, -32768, 32767).astype(np.int16)
        if self.channels == 2:
            stereo = np.column_stack((clipped, clipped))
            return pygame.sndarray.make_sound(stereo)
        return pygame.sndarray.make_sound(clipped)

    def _filter_lpf(self, wave_float, cutoff_hz=320.0, passes=3):
        """Срезает высокие частоты для создания глухого звука за стеной."""
        kernel_sz = max(5, int(self.freq / cutoff_hz))
        kernel = np.ones(kernel_sz, dtype=np.float32) / kernel_sz
        w = wave_float.copy()
        for _ in range(passes):
            w = np.convolve(w, kernel, mode="same")
        return np.tanh(w * 1.6) * 0.90

    def _register(self, name, wave_float, make_muff=False, cutoff=320.0):
        if not hasattr(self, "sounds_muff"):
            self.sounds_muff = {}
        self.sounds[name] = self._make_sound(wave_float)
        if make_muff:
            muff_wave = self._filter_lpf(wave_float, cutoff_hz=cutoff)
            self.sounds_muff[name] = self._make_sound(muff_wave)
        else:
            self.sounds_muff[name] = self.sounds[name]

    def _build_fishing_bank(self):
        rng = np.random.default_rng(417)
        for name, duration, frequencies, gain, noise_mix in (
            ("cast", .23, (340, 840), .13, .8),
            ("land", .19, (570, 155), .26, .65),
            ("bite", .12, (780, 245), .34, .50),
            ("hook", .11, (450, 975), .17, .42),
            ("tug", .16, (210, 390), .22, .68),
            ("reel", .063, (1160, 420), .12, .32),
            ("snap", .105, (1530, 210), .30, .35),
            ("empty", .16, (630, 230), .16, .68),
            ("catch", .28, (310, 1030), .22, .54),
        ):
            samples = int(self.freq * duration)
            t = np.arange(samples) / self.freq
            frequency = np.linspace(*frequencies, samples)
            chirp = np.sin(2 * np.pi * np.cumsum(frequency) / self.freq)
            noise = np.convolve(rng.uniform(-1, 1, samples), np.ones(4) / 4, mode="same")
            fade = np.minimum(1, t * 550) * np.exp(-5 * t / duration)
            if name == "reel":
                fade *= .35 + .65 * np.sin(2 * np.pi * 52 * t) ** 6
            wave = ((1 - noise_mix) * chirp + noise_mix * noise) * fade * gain
            self._register(f"fishing_{name}", wave, make_muff=True, cutoff=410)

    def _build_bank(self):
        sr = self.freq
        self.sounds_muff = {}

        # 1. Surface-Specific Footsteps (Dirt, Stone, Wood, Water, Metal)
        # 1a. Dirt / Grass / Cave Earth (soft muffled crunch)
        t_d = np.linspace(0, 0.055, int(sr * 0.055), False)
        n_d = np.convolve(np.random.uniform(-1, 1, len(t_d)), np.ones(5) / 5.0, mode="same")
        env_d = np.exp(-t_d * 55.0)
        self.sounds["step_dirt"] = self._make_sound((n_d * 0.55 + np.sin(2 * np.pi * 82 * t_d) * 0.35) * env_d * 0.16)
        self.sounds["step"] = self.sounds["step_dirt"]

        # 1b. Stone / Brick (crisp resonant tap)
        t_s = np.linspace(0, 0.032, int(sr * 0.032), False)
        n_s = np.random.uniform(-1, 1, len(t_s))
        env_s = np.exp(-t_s * 115.0)
        tone_s = np.sin(2 * np.pi * 310 * t_s) * 0.5 + np.sin(2 * np.pi * 680 * t_s) * 0.3
        self.sounds["step_stone"] = self._make_sound((n_s * 0.4 + tone_s) * env_s * 0.17)

        # 1c. Wooden Planks (warm hollow board thump)
        t_w = np.linspace(0, 0.05, int(sr * 0.05), False)
        env_w = np.exp(-t_w * 65.0)
        tone_w = np.sin(2 * np.pi * 135 * t_w) * 0.65 + np.sin(2 * np.pi * 275 * t_w) * 0.25
        self.sounds["step_wood"] = self._make_sound(tone_w * env_w * 0.20)

        # 1d. Water Puddle (wet slosh / droplet splash)
        t_wa = np.linspace(0, 0.085, int(sr * 0.085), False)
        white_wa = np.random.uniform(-1, 1, len(t_wa))
        slosh = np.convolve(white_wa, np.ones(4) / 4.0, mode="same") * np.sin(2 * np.pi * np.linspace(380, 920, len(t_wa)) * t_wa)
        env_wa = np.sin(np.pi * t_wa / 0.085) * np.exp(-t_wa * 22.0)
        self.sounds["step_water"] = self._make_sound(slosh * env_wa * 0.22)

        # 1e. Metal Grate / Iron Floor (metallic clink for future floors)
        t_m = np.linspace(0, 0.045, int(sr * 0.045), False)
        env_m = np.exp(-t_m * 85.0)
        ring_m = (
            np.sin(2 * np.pi * 540 * t_m) * 0.45
            + np.sin(2 * np.pi * 1180 * t_m) * 0.35
            + np.sin(2 * np.pi * 1860 * t_m) * 0.20
        )
        self.sounds["step_metal"] = self._make_sound(ring_m * env_m * 0.16)

        # 2. Typewriter tick (2x quieter than before: 0.045 amplitude)
        t = np.linspace(0, 0.014, int(sr * 0.014), False)
        tick = np.sin(2 * np.pi * 640 * t) * np.exp(-t * 190.0)
        self.sounds["type_tick"] = self._make_sound(tick * 0.045)

        # 3. Melee Hit
        t = np.linspace(0, 0.11, int(sr * 0.11), False)
        noise = np.random.uniform(-1, 1, len(t))
        sweep = np.sin(2 * np.pi * np.linspace(260, 75, len(t)) * t)
        env = np.exp(-t * 28.0)
        self.sounds["hit"] = self._make_sound((noise * 0.5 + sweep * 0.6) * env * 0.40)

        # 4. Crit
        t = np.linspace(0, 0.20, int(sr * 0.20), False)
        noise = np.random.uniform(-1, 1, len(t))
        ring = np.sign(np.sin(2 * np.pi * 520 * t)) * 0.4 + np.sin(2 * np.pi * 140 * t) * 0.7
        env = np.exp(-t * 14.0)
        self.sounds["crit"] = self._make_sound((noise * 0.4 + ring) * env * 0.48)

        # 5. Hurt
        t = np.linspace(0, 0.14, int(sr * 0.14), False)
        wave = np.sign(np.sin(2 * np.pi * np.linspace(150, 55, len(t)) * t))
        env = np.exp(-t * 20.0)
        self.sounds["hurt"] = self._make_sound(wave * env * 0.36)

        # 6a. Coin pickup (сочный перезвон горсти монет в кошельке)
        c_chunks = []
        for freq_c, dur_c in ((1174.66, 0.045), (1567.98, 0.050), (2093.0, 0.12)):
            tc = np.linspace(0, dur_c, int(sr * dur_c), False)
            bell = (np.sin(2 * np.pi * freq_c * tc) + 0.35 * np.sin(2 * np.pi * (freq_c * 2.0) * tc)) * np.exp(-tc * 20.0)
            c_chunks.append(bell)
        self.sounds["coin_pickup"] = self._make_sound(np.concatenate(c_chunks) * 0.28)
        self.sounds["coin"] = self.sounds["coin_pickup"]

        # 6b. Coin drop on stone floor (звонкое скакание монеток по каменной плите)
        d_chunks = []
        for freq_d, dur_d, amp_d in ((1760.0, 0.032, 0.9), (1480.0, 0.038, 0.65), (1975.5, 0.065, 0.45)):
            td = np.linspace(0, dur_d, int(sr * dur_d), False)
            clink = (
                np.sin(2 * np.pi * freq_d * td) * 0.7
                + np.sin(2 * np.pi * (freq_d * 1.41) * td) * 0.3
            ) * np.exp(-td * 42.0) * amp_d
            gap = np.zeros(int(sr * 0.018))
            d_chunks.extend([clink, gap])
        self._register("coin_drop", np.concatenate(d_chunks) * 0.26, make_muff=True, cutoff=340.0)

        # 7. Heal
        notes = [330, 440, 554.37, 659.25]
        chunks = []
        for n in notes:
            tn = np.linspace(0, 0.05, int(sr * 0.05), False)
            chunks.append(np.sin(2 * np.pi * n * tn) * np.exp(-tn * 12.0))
        self.sounds["heal"] = self._make_sound(np.concatenate(chunks) * 0.30)

        # 8. Level Up fanfare
        notes_lvl = [440, 554.37, 659.25, 880.0]
        chunks_lvl = []
        for n in notes_lvl:
            tn = np.linspace(0, 0.075, int(sr * 0.075), False)
            chunks_lvl.append(np.sin(2 * np.pi * n * tn) * np.exp(-tn * 8.0))
        self.sounds["levelup"] = self._make_sound(np.concatenate(chunks_lvl) * 0.38)

        # 9. Magic Cast (звук магии и снарядов)
        t = np.linspace(0, 0.18, int(sr * 0.18), False)
        carrier = np.sin(2 * np.pi * np.linspace(380, 920, len(t)) * t)
        mod = np.sin(2 * np.pi * 55 * t)
        env = np.exp(-t * 11.0)
        self._register("magic", carrier * mod * env * 0.32, make_muff=True, cutoff=280.0)

        # 10. Door / Lever (стук дверей и рычагов)
        t = np.linspace(0, 0.12, int(sr * 0.12), False)
        clunk = (np.sin(2 * np.pi * 95 * t) + np.random.uniform(-0.4, 0.4, len(t))) * np.exp(-t * 22.0)
        self._register("door", clunk * 0.38, make_muff=True, cutoff=240.0)

        # 11. Alert (!) (враг заметил героя)
        t = np.linspace(0, 0.16, int(sr * 0.16), False)
        al = np.sign(np.sin(2 * np.pi * np.linspace(440, 880, len(t)) * t)) * np.exp(-t * 12.0)
        self._register("alert", al * 0.28, make_muff=True, cutoff=300.0)

        # 12. Torch toggle & quieter ignition spark (звуки персонажа — прямые)
        t = np.linspace(0, 0.12, int(sr * 0.12), False)
        wh = np.random.uniform(-1, 1, len(t)) * np.sin(np.pi * t / 0.12)
        self._register("torch", wh * 0.26, make_muff=False)

        t_sp = np.linspace(0, 0.09, int(sr * 0.09), False)
        wh_sp = np.random.uniform(-1, 1, len(t_sp)) * np.sin(np.pi * t_sp / 0.09)
        self._register("torch_spark", wh_sp * 0.14, make_muff=False)

        # 13. UI click (звук интерфейса — прямой)
        t = np.linspace(0, 0.035, int(sr * 0.035), False)
        click = np.sign(np.sin(2 * np.pi * 420 * t)) * np.exp(-t * 60.0)
        self._register("ui", click * 0.24, make_muff=False)

        # 14. Monster Murmur / Chatter sound (голоса мобов за стенами)
        t = np.linspace(0, 0.085, int(sr * 0.085), False)
        murmur = (
            np.sin(2 * np.pi * np.linspace(135, 82, len(t)) * t) * 0.6
            + np.sin(2 * np.pi * 28 * t) * np.random.uniform(-0.35, 0.35, len(t))
        ) * np.exp(-t * 32.0)
        self._register("mob_talk", murmur * 0.11, make_muff=True, cutoff=220.0)

        # 15. Combat Ability Windup (unobtrusive, airy breath/whoosh)
        t = np.linspace(0, 0.16, int(sr * 0.16), False)
        white = np.random.uniform(-1, 1, len(t))
        # Smooth moving-average lowpass for soft air texture
        air = np.convolve(white, np.ones(12) / 12.0, mode="same")
        breeze_tone = np.sin(2 * np.pi * np.linspace(180, 290, len(t)) * t) * 0.25
        env = np.sin(np.pi * t / 0.16)
        self.sounds["skill_windup"] = self._make_sound((air * 0.75 + breeze_tone) * env * 0.14)

        # 16. Spell Cast Windup (quiet, energetic rising harmonic charge)
        t = np.linspace(0, 0.22, int(sr * 0.22), False)
        f_sweep = np.linspace(220, 540, len(t))
        charge = (
            np.sin(2 * np.pi * f_sweep * t) * 0.6
            + np.sin(2 * np.pi * (f_sweep * 1.5) * t) * 0.35
        ) * (1.0 + 0.25 * np.sin(2 * np.pi * 32 * t))
        env = np.sin(np.pi * (t / 0.22) ** 0.8)
        self._register("spell_windup", charge * env * 0.13, make_muff=True, cutoff=260.0)

        # 17. CPU Meltdown Siren (for Exit tab)
        t_m = np.linspace(0, 0.45, int(sr * 0.45), False)
        siren = np.sign(np.sin(2 * np.pi * np.linspace(180, 620, len(t_m)) * t_m)) * np.exp(-t_m * 4.5)
        self.sounds["cpu_meltdown"] = self._make_sound(siren * 0.28)

        # 18. Sad Out-of-Mana Sound (короткий грустный нисходящий вздох без маны)
        t_nm1 = np.linspace(0, 0.065, int(sr * 0.065), False)
        t_nm2 = np.linspace(0, 0.11, int(sr * 0.11), False)
        w_nm1 = np.sin(2 * np.pi * 290.0 * t_nm1) * np.exp(-t_nm1 * 18.0)
        w_nm2 = np.sin(2 * np.pi * 195.0 * t_nm2) * np.exp(-t_nm2 * 16.0)
        self.sounds["no_mana"] = self._make_sound(np.concatenate([w_nm1, w_nm2]) * 0.26)

    def set_volume(self, vol):
        self.volume = max(0.0, min(1.0, float(vol)))
        if self.enabled:
            for snd in self.sounds.values():
                snd.set_volume(self.volume)
            menu_sound = getattr(self, "menu_music_sound", None)
            if menu_sound is not None:
                menu_sound.set_volume(self.volume * MENU_MUSIC_GAIN)

    def start_menu_music(self, track_filename="scottishe Sunshine.json"):
        """Компилирует трек из JSON при первом вызове и запускает бесконечный луп в Главном меню."""
        if not self.enabled:
            return
        if not hasattr(self, "menu_channel") or self.menu_channel is None:
            self.menu_channel = pygame.mixer.Channel(18)

        if self.menu_channel.get_busy():
            return

        # Гасим эмбиент данжа, если игрок вышел в меню через ESC
        self.stop_disco_track()

        if not hasattr(self, "menu_music_sound") or self.menu_music_sound is None:
            try:
                import json
                import os
                from elenor.audio.music import SongData, MusicLoopCompiler
                # Проверяем файл сначала в подпапке music/, а затем в корне
                fpath = os.path.join(str(PROJECT_ROOT), "music", track_filename)
                if not os.path.isfile(fpath):
                    fpath = os.path.join(str(PROJECT_ROOT), track_filename)
                if not os.path.isfile(fpath):
                    print(f"[Audio] Файл трека не найден: {track_filename}")
                    return
                with open(fpath, "r", encoding="utf-8") as f:
                    song_data = SongData.from_dict(json.load(f))
                compiler = MusicLoopCompiler(sample_rate=self.freq)
                self.menu_music_sound, _ = compiler.compile_song(song_data, make_muffled=False)
            except Exception as e:
                print(f"[Audio] Ошибка загрузки музыки меню: {e}")
                return

        if self.menu_music_sound is not None:
            # The mixer restores channel volume after a fade. Keep gain on the track.
            self.menu_music_sound.set_volume(self.volume * MENU_MUSIC_GAIN)
            self.menu_channel.set_volume(1.0)
            self.menu_channel.play(self.menu_music_sound, loops=-1, fade_ms=400)

    def stop_menu_music(self, fade_ms=500):
        """Плавно глушит музыку меню при входе в подземелье."""
        menu_ch = getattr(self, "menu_channel", None)
        if menu_ch is not None and menu_ch.get_busy():
            if fade_ms > 0:
                menu_ch.fadeout(fade_ms)
            else:
                menu_ch.stop()

    def play(self, name):
        if self.enabled and name in self.sounds and self.volume > 0.01:
            snd = self.sounds[name]
            snd.set_volume(self.volume)
            snd.play()

    @staticmethod
    def _add_wrapped(mix, wave, idx0, gain=1.0):
        """Записывает ноту или удар барабана в кольцевой буфер: хвост в конце лупа плавно перетекает в начало!"""
        n_total = len(mix)
        n_w = len(wave)
        if n_w == 0 or n_total == 0:
            return
        idx0 = int(idx0) % n_total
        w_scaled = wave * gain
        end = idx0 + n_w
        if end <= n_total:
            mix[idx0:end] += w_scaled
        else:
            first_part = n_total - idx0
            mix[idx0:n_total] += w_scaled[:first_part]
            overhang = n_w - first_part
            mix[:overhang] += w_scaled[first_part : first_part + overhang]

    @staticmethod
    def _periodic_sin(target_freq, total_dur, t_full):
        """Генерирует синусоиду со строго целым числом периодов внутри лупа (0% скачка фазы на шве)."""
        cycles = max(1, round(target_freq * total_dur))
        exact_freq = cycles / total_dur
        return np.sin(2 * np.pi * exact_freq * t_full)

    def _synth_sax_note(self, freq, dur, sr, bend_from=None):
        """Синтез тёплого аналогового саксофона с формантами, вибрато и мягкой огибающей."""
        n_samples = int(sr * dur)
        t = np.linspace(0, dur, n_samples, False)

        if bend_from:
            pitch_env = np.ones(n_samples)
            scoop_len = min(n_samples, int(sr * 0.045))
            pitch_env[:scoop_len] = np.linspace(bend_from / freq, 1.0, scoop_len)
        else:
            pitch_env = 1.0

        vibrato_lfo = np.sin(2 * np.pi * 5.2 * t)
        vibrato_depth = np.clip((t - 0.08) / 0.15, 0.0, 1.0) * 0.022
        inst_freq = freq * pitch_env * (1.0 + vibrato_lfo * vibrato_depth)
        phase = 2 * np.pi * np.cumsum(inst_freq) / sr

        wave = (
            np.sin(phase) * 0.65
            + np.sin(phase * 2.0) * 0.40
            + np.sin(phase * 3.0) * 0.50
            + np.sin(phase * 4.0) * 0.22
            + np.sin(phase * 5.0) * 0.28
        )
        breath = np.random.uniform(-0.12, 0.12, n_samples)
        wave = wave * 0.90 + breath * 0.10

        att = min(n_samples, int(sr * 0.025))
        rel = min(n_samples, int(sr * 0.065))
        env = np.ones(n_samples, dtype=np.float32)
        env[:att] = 0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, att))
        env[-rel:] = 0.5 + 0.5 * np.cos(np.linspace(0.0, np.pi, rel))
        return wave * env * 0.42

    def _finalize_seamless_pair(self, mix, n_samples, lpf_cutoff=210.0, muff_drive=2.8):
        """
        Тройной тайлинг уже замкнутого по кольцу буфера:
        фильтр низких частот проходит через границы копий без единого разрыва и без щелчков!
        """
        tiled_mix = np.concatenate([mix, mix, mix])
        mastered_dry_tiled = np.tanh(tiled_mix * 1.30) * 0.75

        kernel_sz = max(7, int(self.freq / lpf_cutoff))
        box_kernel = np.ones(kernel_sz, dtype=np.float32) / kernel_sz
        muff_tiled = mastered_dry_tiled.copy()
        for _ in range(4):
            muff_tiled = np.convolve(muff_tiled, box_kernel, mode="same")
        mastered_muff_tiled = np.tanh(muff_tiled * muff_drive) * 0.95

        dry_loop = mastered_dry_tiled[n_samples : 2 * n_samples].copy()
        muff_loop = mastered_muff_tiled[n_samples : 2 * n_samples].copy()
        return self._make_sound(dry_loop), self._make_sound(muff_loop)

    def _generate_disco_loop(self):
        """Процедурный бесшовный 4-тактовый диско-луп (128 BPM) с кольцевой склейкой хвостов."""
        sr = self.freq
        bpm = 128.0
        beat_len = 60.0 / bpm
        total_beats = 8
        total_dur = beat_len * total_beats
        n_samples = int(sr * total_dur)
        mix = np.zeros(n_samples, dtype=np.float32)

        # 1. Прямая бочка с гладким косинусным входом и выходом
        kick_dur = 0.16
        n_k = int(sr * kick_dur)
        t_k = np.linspace(0, kick_dur, n_k, False)
        f_k = np.linspace(155.0, 42.0, n_k)
        kick_wave = np.sin(2 * np.pi * f_k * t_k) * np.exp(-t_k * 24.0)
        n_click = min(n_k, int(sr * 0.015))
        click_env = np.sin(np.linspace(0.0, np.pi, n_click)) ** 2.0
        kick_wave[:n_click] += np.random.uniform(-0.28, 0.28, n_click) * click_env
        kick_wave[:32] *= np.linspace(0.0, 1.0, 32)
        kick_wave[-64:] *= np.linspace(1.0, 0.0, 64)

        for b in range(total_beats):
            self._add_wrapped(mix, kick_wave, int(b * beat_len * sr), gain=0.65)

        # 2. Синкопированный открытый хэт
        hat_dur = 0.09
        n_h = int(sr * hat_dur)
        t_h = np.linspace(0, hat_dur, n_h, False)
        noise = np.random.uniform(-1.0, 1.0, n_h)
        hat_wave = noise * np.sin(2 * np.pi * 7500.0 * t_h) * np.exp(-t_h * 42.0)
        hat_wave[:24] *= np.linspace(0.0, 1.0, 24)
        hat_wave[-48:] *= np.linspace(1.0, 0.0, 48)
        for b in range(total_beats):
            self._add_wrapped(mix, hat_wave, int((b + 0.5) * beat_len * sr), gain=0.28)

        # 3. Аналоговый фанк-бас
        bass_notes = [73.42, 73.42, 87.31, 98.0, 73.42, 110.0, 98.0, 87.31]
        for i, freq in enumerate(bass_notes):
            dur_b = beat_len * 0.85
            n_b = int(dur_b * sr)
            t_b = np.linspace(0, dur_b, n_b, False)
            b_synth = (
                np.sin(2 * np.pi * freq * t_b) * 0.70
                + np.sin(2 * np.pi * freq * 2.0 * t_b) * 0.35
                + np.sin(2 * np.pi * freq * 3.0 * t_b) * 0.15
            )
            env_b = np.sin(np.pi * (t_b / dur_b) ** 0.5) * np.exp(-t_b * 3.8)
            env_b[:48] *= np.linspace(0.0, 1.0, 48)
            env_b[-96:] *= np.linspace(1.0, 0.0, 96)
            self._add_wrapped(mix, b_synth * env_b, int(i * beat_len * sr), gain=0.45)

        # 4. Сольный запил на саксофоне (хвост последней ноты плавно перетекает в начало лупа!)
        sax_riff = [
            (0.00, 293.66, 0.40, 261.63),
            (0.50, 349.23, 0.40, None),
            (1.00, 392.00, 0.35, None),
            (1.50, 440.00, 0.85, 392.00),
            (2.50, 523.25, 0.42, None),
            (3.00, 440.00, 0.40, None),
            (3.50, 392.00, 0.40, None),
            (4.00, 349.23, 0.75, 293.66),
            (5.00, 392.00, 0.38, None),
            (5.50, 440.00, 0.85, None),
            (6.50, 349.23, 0.38, None),
            (7.00, 293.66, 0.85, 261.63),
        ]
        for start_beat, n_freq, n_len, b_from in sax_riff:
            s_wave = self._synth_sax_note(n_freq, n_len * beat_len, sr, bend_from=b_from)
            self._add_wrapped(mix, s_wave, int(start_beat * beat_len * sr), gain=0.78)

        return self._finalize_seamless_pair(mix, n_samples, lpf_cutoff=220.0, muff_drive=2.8)

    def _generate_ritual_loop(self, combat=False):
        """
        Генерирует идеально синхронизированный стем ритуала (96 BPM, 5.0 сек):
        Все непрерывные дроны имеют целое число периодов, а хвосты ударных завернуты по кольцу!
        """
        sr = self.freq
        bpm = 96.0
        beat_len = 60.0 / bpm
        total_beats = 8
        total_dur = beat_len * total_beats
        n_samples = int(sr * total_dur)
        t_full = np.linspace(0, total_dur, n_samples, False)
        mix = np.zeros(n_samples, dtype=np.float32)

        # 1. ГОРЛОВОЕ ПЕНИЕ / РИТУАЛЬНЫЙ ДРОН (Целое число периодов = 0% щелчков на шве!)
        f_root = 73.42
        f_second = 103.83 if combat else 110.0
        lfo_rate = 1.6 if combat else 0.4
        lfo = 0.55 + 0.45 * self._periodic_sin(lfo_rate, total_dur, t_full)
        drone = (
            self._periodic_sin(f_root, total_dur, t_full) * 0.55
            + self._periodic_sin(f_second, total_dur, t_full) * 0.35
            + self._periodic_sin(f_root * 3.0, total_dur, t_full) * 0.22 * lfo
        )
        mix += drone * (0.34 if combat else 0.25)

        # 2. РИТУАЛЬНЫЕ БАРАБАНЫ (С кольцевым переносом хвоста последнего удара в начало!)
        if not combat:
            drum_hits = [
                (0.0, 1.0), (0.75, 0.55), (1.5, 0.70), (2.0, 0.90), (3.0, 0.60),
                (4.0, 1.0), (4.75, 0.55), (5.5, 0.70), (6.0, 0.90), (7.0, 0.65), (7.5, 0.50)
            ]
        else:
            drum_hits = [(b * 0.5, 1.0 if b % 2 == 0 else 0.72) for b in range(16)]
            drum_hits.extend([(3.25, 0.65), (3.75, 0.80), (7.25, 0.75), (7.75, 0.88)])

        tom_dur = 0.24 if not combat else 0.20
        n_tom = int(sr * tom_dur)
        t_tom = np.linspace(0, tom_dur, n_tom, False)
        f_tom = np.linspace(118.0 if combat else 96.0, 40.0, n_tom)
        tom_skin = (
            np.sin(2 * np.pi * f_tom * t_tom) * 0.80
            + np.sin(2 * np.pi * (f_tom * 1.58) * t_tom) * 0.25
        ) * np.exp(-t_tom * (18.0 if combat else 14.0))

        n_thump = min(n_tom, int(sr * 0.012))
        tom_skin[:n_thump] += np.random.uniform(-0.22, 0.22, n_thump) * (np.sin(np.linspace(0, np.pi, n_thump)) ** 2.0)
        tom_skin[:32] *= np.linspace(0.0, 1.0, 32)
        tom_skin[-64:] *= np.linspace(1.0, 0.0, 64)

        for beat_pos, amp in drum_hits:
            self._add_wrapped(mix, tom_skin, int(beat_pos * beat_len * sr), gain=amp * 0.68)

        # 3. МЕЛОДИКА РИТУАЛА
        if not combat:
            melody = [
                (0.0, 293.66), (0.5, 349.23), (1.0, 415.30), (1.5, 440.00),
                (2.5, 349.23), (3.0, 293.66), (3.5, 277.18),
                (4.0, 293.66), (4.5, 349.23), (5.0, 440.00), (5.5, 415.30),
                (6.5, 349.23), (7.0, 277.18), (7.5, 293.66),
            ]
            note_dur = 0.30
            n_m = int(sr * note_dur)
            t_m = np.linspace(0, note_dur, n_m, False)
            att = min(n_m, int(sr * 0.010))
            rel = min(n_m, int(sr * 0.050))
            for beat_pos, nf in melody:
                bone_tone = (
                    np.sin(2 * np.pi * nf * t_m) * 0.70
                    + np.sin(2 * np.pi * (nf * 2.76) * t_m) * 0.30 * np.exp(-t_m * 35.0)
                ) * np.exp(-t_m * 11.0)
                bone_tone[:att] *= 0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, att))
                bone_tone[-rel:] *= 0.5 + 0.5 * np.cos(np.linspace(0.0, np.pi, rel))
                self._add_wrapped(mix, bone_tone, int(beat_pos * beat_len * sr), gain=0.36)
        else:
            horns = [
                (0.0, 146.83, 1.85),
                (2.0, 207.65, 1.85),
                (4.0, 233.08, 1.85),
                (6.0, 220.00, 1.85),
            ]
            for beat_pos, hf, h_beats in horns:
                h_dur = h_beats * beat_len
                n_h = int(sr * h_dur)
                t_h = np.linspace(0, h_dur, n_h, False)
                vib = 1.0 + 0.015 * np.sin(2 * np.pi * 6.5 * t_h)
                ph = 2 * np.pi * np.cumsum(hf * vib) / sr
                brass = (
                    np.sin(ph) * 0.50
                    + np.sin(ph * 2.0) * 0.45
                    + np.sin(ph * 3.0) * 0.40
                    + np.sin(ph * 4.0) * 0.25
                    + np.sin(ph * 5.0) * 0.20
                )
                env_h = np.sin(np.pi * (t_h / h_dur) ** 0.6) * np.exp(-t_h * 1.2)
                att_h = min(n_h, int(sr * 0.030))
                rel_h = min(n_h, int(sr * 0.080))
                env_h[:att_h] *= 0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, att_h))
                env_h[-rel_h:] *= 0.5 + 0.5 * np.cos(np.linspace(0.0, np.pi, rel_h))
                self._add_wrapped(mix, brass * env_h, int(beat_pos * beat_len * sr), gain=0.44)

            bell_notes = [587.33, 622.25, 587.33, 554.37, 587.33, 698.46, 622.25, 554.37] * 2
            b_dur = 0.18
            n_bl = int(sr * b_dur)
            t_bl = np.linspace(0, b_dur, n_bl, False)
            att = min(n_bl, int(sr * 0.008))
            rel = min(n_bl, int(sr * 0.040))
            for i, bf in enumerate(bell_notes):
                bell_w = (
                    np.sin(2 * np.pi * bf * t_bl) * 0.65
                    + np.sin(2 * np.pi * (bf * 2.41) * t_bl) * 0.35
                ) * np.exp(-t_bl * 20.0)
                bell_w[:att] *= 0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, att))
                bell_w[-rel:] *= 0.5 + 0.5 * np.cos(np.linspace(0.0, np.pi, rel))
                self._add_wrapped(mix, bell_w, int(i * 0.5 * beat_len * sr), gain=0.28)

        return self._finalize_seamless_pair(mix, n_samples, lpf_cutoff=195.0, muff_drive=3.0)

    def _ensure_loop_bank(self):
        if not hasattr(self, "loop_bank"):
            self.loop_bank = {}
        if not hasattr(self, "active_loop_group"):
            self.active_loop_group = None
        if not hasattr(self, "ritual_combat_blend"):
            self.ritual_combat_blend = 0.0
        if not hasattr(self, "disco_ch_dry") or self.disco_ch_dry is None:
            self.disco_ch_dry = pygame.mixer.Channel(14)
            self.disco_ch_muff = pygame.mixer.Channel(15)
            self.comb_ch_dry = pygame.mixer.Channel(16)
            self.comb_ch_muff = pygame.mixer.Channel(17)

    def _get_loop_pair(self, theme):
        self._ensure_loop_bank()
        if theme not in self.loop_bank:
            if theme == "disco":
                self.loop_bank[theme] = self._generate_disco_loop()
            elif theme == "ritual_idle":
                self.loop_bank[theme] = self._generate_ritual_loop(combat=False)
            elif theme == "ritual_combat":
                self.loop_bank[theme] = self._generate_ritual_loop(combat=True)
        return self.loop_bank.get(theme)

    def start_disco_track(self):
        self.start_ambient_loop("disco")

    def start_ambient_loop(self, theme):
        """
        Запускает либо одиночную тему (disco), либо 4-канальный синхронный стем-микшер (ritual),
        где спокойная и боевая фазы идут такт-в-такт с первой миллисекунды!
        """
        if not self.enabled:
            return
        self._ensure_loop_bank()

        if theme in ("ritual_idle", "ritual_combat"):
            idle_pair = self._get_loop_pair("ritual_idle")
            comb_pair = self._get_loop_pair("ritual_combat")
            if self.active_loop_group != "ritual" or not self.disco_ch_dry.get_busy():
                self.stop_disco_track()
                self.active_loop_group = "ritual"
                self.ritual_combat_blend = 1.0 if theme == "ritual_combat" else 0.0
                for ch in (self.disco_ch_dry, self.disco_ch_muff, self.comb_ch_dry, self.comb_ch_muff):
                    ch.set_volume(0.0, 0.0)
                # Одновременный старт всех 4 дорожек гарантирует побитовую синхронизацию ритма!
                self.disco_ch_dry.play(idle_pair[0], loops=-1)
                self.disco_ch_muff.play(idle_pair[1], loops=-1)
                self.comb_ch_dry.play(comb_pair[0], loops=-1)
                self.comb_ch_muff.play(comb_pair[1], loops=-1)
        elif theme == "disco":
            disco_pair = self._get_loop_pair("disco")
            if self.active_loop_group != "disco" or not self.disco_ch_dry.get_busy():
                self.stop_disco_track()
                self.active_loop_group = "disco"
                self.disco_ch_dry.set_volume(0.0, 0.0)
                self.disco_ch_muff.set_volume(0.0, 0.0)
                self.disco_ch_dry.play(disco_pair[0], loops=-1)
                self.disco_ch_muff.play(disco_pair[1], loops=-1)

    def stop_disco_track(self):
        for attr in ("disco_ch_dry", "disco_ch_muff", "comb_ch_dry", "comb_ch_muff"):
            ch = getattr(self, attr, None)
            if ch is not None:
                ch.stop()
        self.active_loop_group = None
        self.ritual_combat_blend = 0.0
        self.disco_cur_dry = [0.0, 0.0]
        self.disco_cur_muff = [0.0, 0.0]

    def _calc_two_path_acoustics(self, px, py, sx, sy, dungeon=None, max_dist=32.0, max_air_dist=22.0):
        """Единое ядро двухпутевой акустики: возвращает (vl_dry, vr_dry, vl_muff, vr_muff)."""
        dist = math.hypot(sx - px, sy - py)
        if dist >= max_dist:
            return 0.0, 0.0, 0.0, 0.0

        itx_p, ity_p = int(px), int(py)
        itx_s, ity_s = int(sx), int(sy)

        has_los = dungeon.has_line_of_sight(px, py, sx, sy, dist + 0.5) if dungeon else True

        wall_layers = 0
        if dungeon is not None:
            steps = int(dist * 3.0) + 1
            in_wall = False
            for step_i in range(1, steps):
                t_step = step_i / float(steps)
                cx_t = int(px + (sx - px) * t_step)
                cy_t = int(py + (sy - py) * t_step)
                if (cx_t, cy_t) in ((itx_p, ity_p), (itx_s, ity_s)):
                    continue
                is_w = dungeon.is_blocking_sight(cx_t, cy_t)
                if is_w and not in_wall:
                    wall_layers += 1
                    in_wall = True
                elif not is_w:
                    in_wall = False

        if has_los or wall_layers == 0:
            dry_vol = max(0.0, 1.0 - dist / max_dist) ** 1.2
            muff_vol = 0.0
            pan_dry_x = sx - px
            pan_muff_x = pan_dry_x
        else:
            if not hasattr(self, "_acoustic_cache"):
                self._acoustic_cache = {}

            cache_key = (itx_p, ity_p, itx_s, ity_s)
            if cache_key in self._acoustic_cache:
                path = self._acoustic_cache[cache_key]
            else:
                if len(self._acoustic_cache) > 32:
                    self._acoustic_cache.clear()
                path = dungeon.find_path((itx_p, ity_p), (itx_s, ity_s), max_expanded=120) if dungeon else []
                self._acoustic_cache[cache_key] = path

            if path and len(path) < max_air_dist:
                air_path_len = len(path)
                air_atten = max(0.0, 1.0 - air_path_len / max_air_dist) ** 1.70
                extra_bend = max(0.0, air_path_len - dist)
                bend_diffraction = 1.0 / (1.0 + extra_bend * 0.80)
                dry_vol = air_atten * bend_diffraction
                first_node = path[0]
                pan_dry_x = first_node[0] - px
            else:
                dry_vol = 0.0
                pan_dry_x = sx - px

            wall_punch = max(0.0, 1.0 - dist / max_dist) ** 1.05
            wall_loss_curve = [1.0, 0.85, 0.45, 0.18]
            trans_k = wall_loss_curve[min(3, wall_layers)] if wall_layers < 4 else max(0.04, 0.18 * (0.55 ** (wall_layers - 3)))
            muff_vol = wall_punch * trans_k
            pan_muff_x = sx - px

        pan_dry = max(-1.0, min(1.0, pan_dry_x / 7.5))
        lp_dry = 1.0 - max(0.0, pan_dry * 0.75)
        rp_dry = 1.0 - max(0.0, -pan_dry * 0.75)

        pan_muff = max(-1.0, min(1.0, pan_muff_x / 8.0))
        lp_muff = 1.0 - max(0.0, pan_muff * 0.75)
        rp_muff = 1.0 - max(0.0, -pan_muff * 0.75)

        return (
            dry_vol * lp_dry,
            dry_vol * rp_dry,
            muff_vol * lp_muff,
            muff_vol * rp_muff,
        )

    def update_ambient_spatial(self, theme, px, py, sx, sy, dungeon=None, max_dist=36.0, max_air_dist=22.0, dt=0.016):
        """
        Управляет пространственным звуком и вертикальным ремиксингом стемов:
        спокойный и боевой ритуалы перетекают друг в друга без потери ритма и без пауз!
        """
        if not self.enabled:
            return
        self._ensure_loop_bank()

        if theme is None:
            if not self.disco_ch_dry.get_busy():
                return
            target_vl_dry = target_vr_dry = target_vl_muff = target_vr_muff = 0.0
            lerp_speed = 6.0
        else:
            self.start_ambient_loop(theme)
            d_l, d_r, m_l, m_r = self._calc_two_path_acoustics(
                px, py, sx, sy, dungeon, max_dist=max_dist, max_air_dist=max_air_dist
            )
            master = self.volume * 0.75
            target_vl_dry = max(0.0, min(1.0, d_l * master))
            target_vr_dry = max(0.0, min(1.0, d_r * master))
            target_vl_muff = max(0.0, min(1.0, m_l * master))
            target_vr_muff = max(0.0, min(1.0, m_r * master))
            lerp_speed = 7.5

        alpha = min(1.0, max(0.01, lerp_speed * max(0.001, dt)))
        self.disco_cur_dry[0] += (target_vl_dry - self.disco_cur_dry[0]) * alpha
        self.disco_cur_dry[1] += (target_vr_dry - self.disco_cur_dry[1]) * alpha
        self.disco_cur_muff[0] += (target_vl_muff - self.disco_cur_muff[0]) * alpha
        self.disco_cur_muff[1] += (target_vr_muff - self.disco_cur_muff[1]) * alpha

        for arr in (self.disco_cur_dry, self.disco_cur_muff):
            if arr[0] < 0.0005: arr[0] = 0.0
            if arr[1] < 0.0005: arr[1] = 0.0

        if self.active_loop_group == "ritual":
            # Плавный морфинг между Спокойным (0.0) и Боевым (1.0) стемами с сохранением ритма!
            target_comb = 1.0 if theme == "ritual_combat" else (0.0 if theme == "ritual_idle" else self.ritual_combat_blend)
            blend_step = min(1.0, max(0.005, 2.2 * max(0.001, dt)))
            self.ritual_combat_blend += (target_comb - self.ritual_combat_blend) * blend_step

            # Кривая равной мощности (Equal-Power Crossfade), чтобы громкость не проседала в середине перехода
            b = max(0.0, min(1.0, self.ritual_combat_blend))
            w_idle = math.cos(b * math.pi * 0.5)
            w_comb = math.sin(b * math.pi * 0.5)

            self.disco_ch_dry.set_volume(self.disco_cur_dry[0] * w_idle, self.disco_cur_dry[1] * w_idle)
            self.disco_ch_muff.set_volume(self.disco_cur_muff[0] * w_idle, self.disco_cur_muff[1] * w_idle)
            self.comb_ch_dry.set_volume(self.disco_cur_dry[0] * w_comb, self.disco_cur_dry[1] * w_comb)
            self.comb_ch_muff.set_volume(self.disco_cur_muff[0] * w_comb, self.disco_cur_muff[1] * w_comb)
        else:
            self.disco_ch_dry.set_volume(self.disco_cur_dry[0], self.disco_cur_dry[1])
            self.disco_ch_muff.set_volume(self.disco_cur_muff[0], self.disco_cur_muff[1])

        if theme is None and max(self.disco_cur_dry + self.disco_cur_muff) <= 0.001:
            self.stop_disco_track()

    def update_disco_spatial(self, px, py, disco_x, disco_y, dungeon=None, max_dist=32.0, dt=0.016):
        self.update_ambient_spatial("disco", px, py, disco_x, disco_y, dungeon=dungeon, max_dist=max_dist, max_air_dist=22.0, dt=dt)

    def play_spatial(self, name, sx, sy, px=None, py=None, dungeon=None, max_dist=18.0, base_gain=1.0):
        """Разовые звуки окружения с двухпутевой акустикой."""
        if not self.enabled or self.volume <= 0.01:
            return
        if px is None or py is None:
            self.play(name)
            return

        d_l, d_r, m_l, m_r = self._calc_two_path_acoustics(
            px, py, sx, sy, dungeon=dungeon, max_dist=max_dist, max_air_dist=min(15.0, max_dist * 0.85)
        )
        master = base_gain * self.volume

        pairs_to_play = []
        if max(d_l, d_r) * master > 0.015 and name in self.sounds:
            pairs_to_play.append((self.sounds[name], min(1.0, d_l * master), min(1.0, d_r * master)))
        if max(m_l, m_r) * master > 0.015 and name in getattr(self, "sounds_muff", {}):
            pairs_to_play.append((self.sounds_muff[name], min(1.0, m_l * master), min(1.0, m_r * master)))

        for snd, vl, vr in pairs_to_play:
            for ch_idx in range(12):
                ch = pygame.mixer.Channel(ch_idx)
                if not ch.get_busy():
                    ch.set_volume(vl, vr)
                    ch.play(snd)
                    break