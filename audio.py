import numpy as np
import pygame


class SoundSynth:
    def __init__(self):
        self.enabled = False
        self.volume = 0.85
        self.sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            self.freq, _, self.channels = pygame.mixer.get_init()
            self.enabled = True
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