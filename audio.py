import numpy as np
import pygame
import math


class SoundSynth:
    def __init__(self):
        self.enabled = False
        self.volume = 0.85
        self.sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            pygame.mixer.set_num_channels(16)
            self.freq, _, self.channels = pygame.mixer.get_init()
            self.enabled = True
            self.disco_channel = None
            self.disco_sound = None
            self.disco_cur_dry = [0.0, 0.0]
            self.disco_cur_muff = [0.0, 0.0]
            self._build_bank()
        except Exception:
            self.enabled = False

    def _make_sound(self, wave_float):
        clipped = np.clip(wave_float * 32767.0, -32768, 32767).astype(np.int16)
        if self.channels == 2:
            stereo = np.column_stack((clipped, clipped))
            return pygame.sndarray.make_sound(stereo)
        return pygame.sndarray.make_sound(clipped)

    def _build_bank(self):
        sr = self.freq

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
        self.sounds["coin_drop"] = self._make_sound(np.concatenate(d_chunks) * 0.26)

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

        # 9. Magic Cast
        t = np.linspace(0, 0.18, int(sr * 0.18), False)
        carrier = np.sin(2 * np.pi * np.linspace(380, 920, len(t)) * t)
        mod = np.sin(2 * np.pi * 55 * t)
        env = np.exp(-t * 11.0)
        self.sounds["magic"] = self._make_sound(carrier * mod * env * 0.32)

        # 10. Door / Lever
        t = np.linspace(0, 0.12, int(sr * 0.12), False)
        clunk = (np.sin(2 * np.pi * 95 * t) + np.random.uniform(-0.4, 0.4, len(t))) * np.exp(-t * 22.0)
        self.sounds["door"] = self._make_sound(clunk * 0.38)

        # 11. Alert (!)
        t = np.linspace(0, 0.16, int(sr * 0.16), False)
        al = np.sign(np.sin(2 * np.pi * np.linspace(440, 880, len(t)) * t)) * np.exp(-t * 12.0)
        self.sounds["alert"] = self._make_sound(al * 0.28)

        # 12. Torch toggle & quieter ignition spark
        t = np.linspace(0, 0.12, int(sr * 0.12), False)
        wh = np.random.uniform(-1, 1, len(t)) * np.sin(np.pi * t / 0.12)
        self.sounds["torch"] = self._make_sound(wh * 0.26)

        t_sp = np.linspace(0, 0.09, int(sr * 0.09), False)
        wh_sp = np.random.uniform(-1, 1, len(t_sp)) * np.sin(np.pi * t_sp / 0.09)
        self.sounds["torch_spark"] = self._make_sound(wh_sp * 0.14)

        # 13. UI click
        t = np.linspace(0, 0.035, int(sr * 0.035), False)
        click = np.sign(np.sin(2 * np.pi * 420 * t)) * np.exp(-t * 60.0)
        self.sounds["ui"] = self._make_sound(click * 0.24)

        # 14. Unobtrusive Monster Murmur / Chatter sound (soft low rattle)
        t = np.linspace(0, 0.085, int(sr * 0.085), False)
        murmur = (
            np.sin(2 * np.pi * np.linspace(135, 82, len(t)) * t) * 0.6
            + np.sin(2 * np.pi * 28 * t) * np.random.uniform(-0.35, 0.35, len(t))
        ) * np.exp(-t * 32.0)
        self.sounds["mob_talk"] = self._make_sound(murmur * 0.09)

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
        self.sounds["spell_windup"] = self._make_sound(charge * env * 0.13)

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

    def play(self, name):
        if self.enabled and name in self.sounds and self.volume > 0.01:
            snd = self.sounds[name]
            snd.set_volume(self.volume)
            snd.play()

    def _synth_sax_note(self, freq, dur, sr, bend_from=None):
        """Синтез тёплого аналогового саксофона с формантами, вибрато и дыханием."""
        n_samples = int(sr * dur)
        t = np.linspace(0, dur, n_samples, False)

        # Подтяжка высоты тона на атаке (характерный джазовый scoop)
        if bend_from:
            pitch_env = np.ones(n_samples)
            scoop_len = min(n_samples, int(sr * 0.045))
            pitch_env[:scoop_len] = np.linspace(bend_from / freq, 1.0, scoop_len)
        else:
            pitch_env = 1.0

        # Вибрато, плавно нарастающее после атаки ноты
        vibrato_lfo = np.sin(2 * np.pi * 5.2 * t)
        vibrato_depth = np.clip((t - 0.08) / 0.15, 0.0, 1.0) * 0.022
        inst_freq = freq * pitch_env * (1.0 + vibrato_lfo * vibrato_depth)
        phase = 2 * np.pi * np.cumsum(inst_freq) / sr

        # Богатые нечётные и чётные гармоники трости саксофона
        wave = (
            np.sin(phase) * 0.65
            + np.sin(phase * 2.0) * 0.40
            + np.sin(phase * 3.0) * 0.50
            + np.sin(phase * 4.0) * 0.22
            + np.sin(phase * 5.0) * 0.28
        )
        # Шум выдоха через трость (дыхание инструмента)
        breath = np.random.uniform(-0.12, 0.12, n_samples)
        wave = wave * 0.90 + breath * 0.10

        # Огибающая громкости с мягким спадом
        att = min(n_samples, int(sr * 0.025))
        rel = min(n_samples, int(sr * 0.065))
        env = np.ones(n_samples, dtype=np.float32)
        env[:att] = np.linspace(0.0, 1.0, att)
        env[-rel:] = np.linspace(1.0, 0.0, rel)
        return wave * env * 0.42

    def _generate_disco_loop(self):
        """Процедурный бесшовный 4-тактовый луп с саксофоном и физическим Low-Pass фильтром (128 BPM)."""
        sr = self.freq
        bpm = 128.0
        beat_len = 60.0 / bpm
        total_beats = 8
        total_dur = beat_len * total_beats
        n_samples = int(sr * total_dur)
        mix = np.zeros(n_samples, dtype=np.float32)

        # 1. Прямая бочка (4-on-the-floor kick) со сглаженной атакой щелчка
        kick_dur = 0.16
        n_k = int(sr * kick_dur)
        t_k = np.linspace(0, kick_dur, n_k, False)
        f_k = np.linspace(155.0, 42.0, n_k)
        kick_wave = np.sin(2 * np.pi * f_k * t_k) * np.exp(-t_k * 24.0)

        # Мягкая микро-рампа на щелчок (сэмпл 0 строго равен 0.0, убирает щелчок при цикле)
        n_click = min(n_k, int(sr * 0.015))
        click_env = np.sin(np.linspace(0.0, np.pi, n_click)) ** 1.5
        click_noise = np.random.uniform(-0.30, 0.30, n_click) * click_env
        kick_wave[:n_click] += click_noise

        for b in range(total_beats):
            idx0 = int(b * beat_len * sr)
            idx1 = min(n_samples, idx0 + n_k)
            mix[idx0:idx1] += kick_wave[: idx1 - idx0] * 0.65

        # 2. Синкопированный открытый хэт (Offbeat Hi-Hat)
        hat_dur = 0.09
        n_h = int(sr * hat_dur)
        t_h = np.linspace(0, hat_dur, n_h, False)
        noise = np.random.uniform(-1.0, 1.0, n_h)
        hat_wave = noise * np.sin(2 * np.pi * 7500.0 * t_h) * np.exp(-t_h * 42.0)
        for b in range(total_beats):
            idx0 = int((b + 0.5) * beat_len * sr)
            idx1 = min(n_samples, idx0 + n_h)
            mix[idx0:idx1] += hat_wave[: idx1 - idx0] * 0.28

        # 3. Аналоговый фанк-бас (D-минорный кач)
        bass_notes = [73.42, 73.42, 87.31, 98.0, 73.42, 110.0, 98.0, 87.31]
        for i, freq in enumerate(bass_notes):
            t_b0 = i * beat_len
            idx0 = int(t_b0 * sr)
            dur_b = beat_len * 0.82
            n_b = int(dur_b * sr)
            idx1 = min(n_samples, idx0 + n_b)
            t_b = np.linspace(0, dur_b, n_b, False)
            b_synth = (
                np.sin(2 * np.pi * freq * t_b) * 0.70
                + np.sin(2 * np.pi * freq * 2.0 * t_b) * 0.35
                + np.sin(2 * np.pi * freq * 3.0 * t_b) * 0.15
            )
            env_b = np.sin(np.pi * (t_b / dur_b) ** 0.5) * np.exp(-t_b * 3.8)
            mix[idx0:idx1] += (b_synth * env_b)[: idx1 - idx0] * 0.45

        # 4. СОЛЬНЫЙ ЗАПИЛ НА САКСОФОНЕ (80s D-Minor Riff)
        sax_riff = [
            (0.00, 293.66, 0.40, 261.63),  # D4
            (0.50, 349.23, 0.40, None),    # F4
            (1.00, 392.00, 0.35, None),    # G4
            (1.50, 440.00, 0.85, 392.00),  # A4 (протяжная нота с вибрато)
            (2.50, 523.25, 0.42, None),    # C5
            (3.00, 440.00, 0.40, None),    # A4
            (3.50, 392.00, 0.40, None),    # G4
            (4.00, 349.23, 0.75, 293.66),  # F4
            (5.00, 392.00, 0.38, None),    # G4
            (5.50, 440.00, 0.85, None),    # A4
            (6.50, 349.23, 0.38, None),    # F4
            (7.00, 293.66, 0.80, 261.63),  # D4
        ]
        for start_beat, n_freq, n_len, b_from in sax_riff:
            s_wave = self._synth_sax_note(n_freq, n_len * beat_len, sr, bend_from=b_from)
            i0 = int(start_beat * beat_len * sr)
            i1 = min(n_samples, i0 + len(s_wave))
            mix[i0:i1] += s_wave[: i1 - i0] * 0.78

        # 5. ТРЮК ТРОЙНОГО ТАЙЛИНГА (Бесшовный переход хвоста трека в начало)
        tiled_mix = np.concatenate([mix, mix, mix])
        mastered_dry_tiled = np.tanh(tiled_mix * 1.30) * 0.75

        # Глухой Low-Pass фильтр через тройной массив (срез выше ~220 Гц)
        kernel_sz = max(7, int(sr / 220.0))
        box_kernel = np.ones(kernel_sz, dtype=np.float32) / kernel_sz
        muff_tiled = mastered_dry_tiled.copy()
        for _ in range(4):
            muff_tiled = np.convolve(muff_tiled, box_kernel, mode="same")
        mastered_muff_tiled = np.tanh(muff_tiled * 2.8) * 0.95

        # Вырезаем центральный 4-тактовый фрагмент
        dry_loop = mastered_dry_tiled[n_samples : 2 * n_samples].copy()
        muff_loop = mastered_muff_tiled[n_samples : 2 * n_samples].copy()

        # 6. Микро-кроссфейд шва (4 миллисекунды) для 100% бесшумного цикла
        xf_len = int(sr * 0.005)
        t_xf = np.linspace(0.0, 1.0, xf_len)
        for loop in (dry_loop, muff_loop):
            loop[:xf_len] = loop[:xf_len] * t_xf + loop[-xf_len:] * (1.0 - t_xf)
            loop[-xf_len:] = loop[:xf_len]

        return self._make_sound(dry_loop), self._make_sound(muff_loop)

    def start_disco_track(self):
        if not self.enabled:
            return
        if not hasattr(self, "disco_sound_dry") or self.disco_sound_dry is None:
            self.disco_sound_dry, self.disco_sound_muff = self._generate_disco_loop()
        if not hasattr(self, "disco_ch_dry") or self.disco_ch_dry is None:
            self.disco_ch_dry = pygame.mixer.Channel(14)
            self.disco_ch_muff = pygame.mixer.Channel(15)

        if not self.disco_ch_dry.get_busy():
            self.disco_ch_dry.set_volume(0.0, 0.0)
            self.disco_ch_muff.set_volume(0.0, 0.0)
            self.disco_ch_dry.play(self.disco_sound_dry, loops=-1)
            self.disco_ch_muff.play(self.disco_sound_muff, loops=-1)

    def stop_disco_track(self):
        if hasattr(self, "disco_ch_dry") and self.disco_ch_dry is not None:
            self.disco_ch_dry.stop()
        if hasattr(self, "disco_ch_muff") and self.disco_ch_muff is not None:
            self.disco_ch_muff.stop()

    def update_disco_spatial(self, px, py, disco_x, disco_y, dungeon=None, max_dist=32.0, dt=0.016):
        """Пространственный кроссфейд с плавным сглаживанием громкости без щелчков и хрипа."""
        if not self.enabled or not hasattr(self, "disco_ch_dry") or self.disco_ch_dry is None:
            return
        dist = math.hypot(disco_x - px, disco_y - py)

        if dist >= max_dist:
            target_vl_dry = target_vr_dry = 0.0
            target_vl_muff = target_vr_muff = 0.0
        else:
            # 1. Затухание по воздуху
            atten = ((max_dist - dist) / max_dist) ** 1.15

            # 2. Физический акустический луч: слои стен (переходы пол -> стена -> пол)
            wall_layers = 0
            if dungeon is not None:
                steps = int(dist * 3.5) + 1
                in_wall = False
                for step_i in range(1, steps):
                    t_step = step_i / float(steps)
                    cx_t = int(px + (disco_x - px) * t_step)
                    cy_t = int(py + (disco_y - py) * t_step)
                    is_w = dungeon.is_blocking_sight(cx_t, cy_t)
                    if is_w and not in_wall:
                        wall_layers += 1
                        in_wall = True
                    elif not is_w:
                        in_wall = False

            # 3. Баланс частот в зависимости от препятствий
            if wall_layers == 0:
                dry_factor = 1.0
                muff_factor = 0.0
            elif wall_layers == 1:
                dry_factor = 0.05
                muff_factor = 0.88
            elif wall_layers == 2:
                dry_factor = 0.0
                muff_factor = 0.58
            else:
                dry_factor = 0.0
                muff_factor = max(0.06, 0.32 * (0.70 ** (wall_layers - 3)))

            # 4. Стерео-панорама по X
            pan = max(-1.0, min(1.0, (disco_x - px) / 8.0))
            left_pan = 1.0 - max(0.0, pan * 0.75)
            right_pan = 1.0 - max(0.0, -pan * 0.75)

            base_master = self.volume * 0.75
            target_vl_dry = max(0.0, min(1.0, atten * dry_factor * left_pan * base_master))
            target_vr_dry = max(0.0, min(1.0, atten * dry_factor * right_pan * base_master))
            target_vl_muff = max(0.0, min(1.0, atten * muff_factor * left_pan * base_master))
            target_vr_muff = max(0.0, min(1.0, atten * muff_factor * right_pan * base_master))

        # 5. Мягкое аналоговое сглаживание громкости (Slew Limiter): убирает щелчки и треск
        lerp_speed = 7.5  # Время адаптации ~130 мс
        alpha = min(1.0, max(0.01, lerp_speed * max(0.001, dt)))

        self.disco_cur_dry[0] += (target_vl_dry - self.disco_cur_dry[0]) * alpha
        self.disco_cur_dry[1] += (target_vr_dry - self.disco_cur_dry[1]) * alpha
        self.disco_cur_muff[0] += (target_vl_muff - self.disco_cur_muff[0]) * alpha
        self.disco_cur_muff[1] += (target_vr_muff - self.disco_cur_muff[1]) * alpha

        # Отсекаем микро-шумы около нуля
        for arr in (self.disco_cur_dry, self.disco_cur_muff):
            if arr[0] < 0.0005: arr[0] = 0.0
            if arr[1] < 0.0005: arr[1] = 0.0

        self.disco_ch_dry.set_volume(self.disco_cur_dry[0], self.disco_cur_dry[1])
        self.disco_ch_muff.set_volume(self.disco_cur_muff[0], self.disco_cur_muff[1])