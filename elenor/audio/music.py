import math
import numpy as np
import pygame

# Частоты нот от C2 до B5
NOTE_LIST = [
    "C2", "C#2", "D2", "D#2", "E2", "F2", "F#2", "G2", "G#2", "A2", "A#2", "B2",
    "C3", "C#3", "D3", "D#3", "E3", "F3", "F#3", "G3", "G#3", "A3", "A#3", "B3",
    "C4", "C#4", "D4", "D#4", "E4", "F4", "F#4", "G4", "G#4", "A4", "A#4", "B4",
    "C5", "C#5", "D5", "D#5", "E5", "F5", "F#5", "G5", "G#5", "A5", "A#5", "B5",
]

NOTE_FREQS = {
    n: 65.406 * (2.0 ** (i / 12.0)) for i, n in enumerate(NOTE_LIST)
}

SCALES = {
    "D Dorian (Драйв / Таверна)": ["D2", "E2", "F2", "G2", "A2", "B2", "C3", "D3", "E3", "F3", "G3", "A3", "B3", "C4", "D4", "E4", "F4", "G4", "A4", "C5", "D5"],
    "D Minor (Ритуал / Босс)":    ["D2", "E2", "F2", "G2", "A2", "A#2", "C3", "D3", "E3", "F3", "G3", "A3", "A#3", "C4", "D4", "E4", "F4", "G4", "A4", "A#4", "D5"],
    "D Blues / Гранж-Рок":        ["D2", "F2", "G2", "G#2", "A2", "C3", "D3", "F3", "G3", "G#3", "A3", "C4", "D4", "F4", "G4", "G#4", "A4", "C5", "D5"],
    "Кельтская Пентатоника":      ["D2", "F2", "G2", "A2", "C3", "D3", "F3", "G3", "A3", "C4", "D4", "F4", "G4", "A4", "C5", "D5"],
    "Chromatic (Все 12 нот)":     NOTE_LIST,
}

INSTRUMENT_CATEGORIES = [
    ("drums",    "Ударные"),
    ("acoustic", "Акустика"),
    ("medieval", "Медивал"),
    ("drive",    "16-Бит Рок"),
]

INSTRUMENT_CATALOG = {
    # --- 1. УДАРНЫЕ И ПЕРКУССИЯ ---
    "rock_kick":      {"name": "Рок-Бочка",       "cat": "drums",    "type": "drum",  "color": (240, 70, 70),   "def_note": "C2"},
    "rock_snare":     {"name": "Рок-Малый",       "cat": "drums",    "type": "drum",  "color": (250, 140, 55),  "def_note": "D3"},
    "hihat":          {"name": "Хэт Металл",      "cat": "drums",    "type": "drum",  "color": (240, 215, 75),  "def_note": "F#4"},
    "crash":          {"name": "Крэш / Том",      "cat": "drums",    "type": "drum",  "color": (255, 175, 120), "def_note": "C4"},
    "war_drum":       {"name": "Ратный Бубен",    "cat": "drums",    "type": "drum",  "color": (205, 105, 65),  "def_note": "D2"},
    "tambourine":     {"name": "Тамбурин",        "cat": "drums",    "type": "drum",  "color": (235, 225, 130), "def_note": "A4"},

    # --- 2. АКУСТИЧЕСКИЕ ГИТАРЫ И СТРУННЫЕ ---
    "acoustic_steel": {"name": "Акустика Сталь",  "cat": "acoustic", "type": "synth", "color": (245, 185, 80),  "def_note": "D3"},
    "acoustic_nylon": {"name": "Акустика Нейлон", "cat": "acoustic", "type": "synth", "color": (225, 150, 95),  "def_note": "D3"},
    "bard_lute":      {"name": "Лютня Барда",     "cat": "acoustic", "type": "synth", "color": (165, 225, 105), "def_note": "D4"},
    "celtic_harp":    {"name": "Кельтская Арфа",  "cat": "acoustic", "type": "synth", "color": (120, 240, 195), "def_note": "A3"},

    # --- 3. ИСТОРИЧЕСКИЕ СРЕДНЕВЕКОВЫЕ ИНСТРУМЕНТЫ ---
    "hurdy_gurdy":    {"name": "Колёсная Лира",   "cat": "medieval", "type": "synth", "color": (235, 120, 75),  "def_note": "D3"},
    "bagpipes":       {"name": "Волынка",         "cat": "medieval", "type": "synth", "color": (215, 85, 105),  "def_note": "D4"},
    "wood_flute":     {"name": "Блокфлейта",      "cat": "medieval", "type": "synth", "color": (135, 225, 245), "def_note": "D4"},
    "war_horn":       {"name": "Боевой Рог",      "cat": "medieval", "type": "synth", "color": (195, 145, 95),  "def_note": "D2"},
    "chapel_bell":    {"name": "Чумной Колокол",  "cat": "medieval", "type": "synth", "color": (185, 160, 245), "def_note": "D4"},

    # --- 4. 16-БИТНЫЙ ДРАЙВ И БАС ---
    "slap_bass":      {"name": "Слэп-Бас FM",     "cat": "drive",    "type": "synth", "color": (65, 165, 255),  "def_note": "D2"},
    "dist_guitar":    {"name": "Ритм-Гитара",     "cat": "drive",    "type": "synth", "color": (230, 75, 165),  "def_note": "D3"},
    "screamer_lead":  {"name": "Соло-Запил",      "cat": "drive",    "type": "synth", "color": (80, 240, 165),  "def_note": "D4"},
    "grunge_organ":   {"name": "Гранж-Орган",     "cat": "drive",    "type": "synth", "color": (160, 115, 255), "def_note": "D3"},
}

DEFAULT_CHANNEL_INSTS = [
    "rock_kick", "rock_snare", "hihat", "crash",
    "slap_bass", "dist_guitar", "screamer_lead", "grunge_organ"
]

DEFAULT_SYNTH_PARAMS = {
    "rock_kick":      {"drive": 0.45, "cutoff": 0.60, "punch": 0.80, "detune": 0.10, "decay": 0.45, "fifth": 0.00},
    "rock_snare":     {"drive": 0.40, "cutoff": 0.75, "punch": 0.75, "detune": 0.20, "decay": 0.45, "fifth": 0.00},
    "hihat":          {"drive": 0.25, "cutoff": 0.90, "punch": 0.70, "detune": 0.40, "decay": 0.22, "fifth": 0.00},
    "crash":          {"drive": 0.35, "cutoff": 0.80, "punch": 0.65, "detune": 0.50, "decay": 0.75, "fifth": 0.00},
    "war_drum":       {"drive": 0.35, "cutoff": 0.48, "punch": 0.82, "detune": 0.25, "decay": 0.65, "fifth": 0.00},
    "tambourine":     {"drive": 0.20, "cutoff": 0.92, "punch": 0.75, "detune": 0.55, "decay": 0.40, "fifth": 0.00},

    "acoustic_steel": {"drive": 0.18, "cutoff": 0.82, "punch": 0.80, "detune": 0.28, "decay": 0.72, "fifth": 0.20},
    "acoustic_nylon": {"drive": 0.10, "cutoff": 0.58, "punch": 0.65, "detune": 0.18, "decay": 0.65, "fifth": 0.10},
    "bard_lute":      {"drive": 0.22, "cutoff": 0.76, "punch": 0.85, "detune": 0.38, "decay": 0.58, "fifth": 0.45},
    "celtic_harp":    {"drive": 0.08, "cutoff": 0.85, "punch": 0.55, "detune": 0.32, "decay": 0.88, "fifth": 0.25},

    "hurdy_gurdy":    {"drive": 0.52, "cutoff": 0.68, "punch": 0.80, "detune": 0.48, "decay": 0.85, "fifth": 0.75},
    "bagpipes":       {"drive": 0.58, "cutoff": 0.74, "punch": 0.70, "detune": 0.42, "decay": 0.92, "fifth": 0.80},
    "wood_flute":     {"drive": 0.12, "cutoff": 0.64, "punch": 0.55, "detune": 0.25, "decay": 0.78, "fifth": 0.00},
    "war_horn":       {"drive": 0.48, "cutoff": 0.52, "punch": 0.45, "detune": 0.35, "decay": 0.90, "fifth": 0.50},
    "chapel_bell":    {"drive": 0.25, "cutoff": 0.80, "punch": 0.85, "detune": 0.50, "decay": 0.92, "fifth": 0.30},

    "slap_bass":      {"drive": 0.55, "cutoff": 0.65, "punch": 0.85, "detune": 0.20, "decay": 0.60, "fifth": 0.00},
    "dist_guitar":    {"drive": 0.82, "cutoff": 0.62, "punch": 0.75, "detune": 0.45, "decay": 0.85, "fifth": 0.75},
    "screamer_lead":  {"drive": 0.75, "cutoff": 0.78, "punch": 0.65, "detune": 0.55, "decay": 0.90, "fifth": 0.25},
    "grunge_organ":   {"drive": 0.40, "cutoff": 0.70, "punch": 0.40, "detune": 0.60, "decay": 0.85, "fifth": 0.45},
}


class TrackStep:
    """Шаг секвенсора с поддержкой длины (1..64), слайда (portamento) и полифонии (аккордов)."""
    def __init__(self, active=False, note="D3", volume=0.85, length=1, slide=False, extra_notes=None):
        self.active = active
        self.note = note
        self.volume = volume
        self.length = max(1, min(64, int(length)))
        self.slide = bool(slide)
        self.extra_notes = dict(extra_notes) if extra_notes else {}

    def copy(self):
        return TrackStep(
            active=self.active,
            note=self.note,
            volume=self.volume,
            length=self.length,
            slide=self.slide,
            extra_notes=dict(self.extra_notes),
        )

    def get_all_notes(self):
        res = {}
        if self.active:
            res[self.note] = self.length
        for k, v in self.extra_notes.items():
            res[k] = v
        return res

    def toggle_piano_note(self, note_str, default_len=2):
        if self.active and self.note == note_str:
            if self.extra_notes:
                new_main, new_len = self.extra_notes.popitem()
                self.note = new_main
                self.length = new_len
            else:
                self.active = False
            return False
        elif note_str in self.extra_notes:
            del self.extra_notes[note_str]
            return False
        else:
            if not self.active:
                self.active = True
                self.note = note_str
                self.length = default_len
            else:
                self.extra_notes[note_str] = default_len
            return True

    def set_note_length(self, note_str, new_len):
        new_len = max(1, min(64, int(new_len)))
        if self.active and self.note == note_str:
            self.length = new_len
        elif note_str in self.extra_notes:
            self.extra_notes[note_str] = new_len

    def to_dict(self):
        return {
            "a": self.active, "n": self.note, "v": round(self.volume, 2),
            "l": self.length, "s": self.slide, "ex": self.extra_notes
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            active=d.get("a", False), note=d.get("n", "D3"), volume=d.get("v", 0.85),
            length=d.get("l", 1), slide=d.get("s", False), extra_notes=d.get("ex", {})
        )


class PatternData:
    """Паттерн из 8 дорожек произвольной длины (4..64 шага)."""
    def __init__(self, name="Паттерн 1", steps_count=16, channel_insts=None):
        self.name = name
        self.steps_count = max(4, min(64, int(steps_count)))
        inst_list = channel_insts or DEFAULT_CHANNEL_INSTS
        self.channels = []
        for ch_idx in range(8):
            iid = inst_list[ch_idx % len(inst_list)]
            def_n = INSTRUMENT_CATALOG.get(iid, INSTRUMENT_CATALOG["dist_guitar"])["def_note"]
            self.channels.append({
                "inst_id": iid,
                "mute": False,
                "solo": False,
                "volume": 0.80,
                "steps": [TrackStep(active=False, note=def_n, length=1) for _ in range(self.steps_count)]
            })

    def resize_steps(self, new_count):
        """Безопасно меняет длину паттерна (4..64 шага), синхронизируя все 8 дорожек."""
        new_count = max(4, min(64, int(new_count)))
        self.steps_count = new_count
        for ch in self.channels:
            def_n = INSTRUMENT_CATALOG.get(ch["inst_id"], INSTRUMENT_CATALOG["dist_guitar"])["def_note"]
            cur_len = len(ch["steps"])
            if cur_len < new_count:
                for _ in range(new_count - cur_len):
                    ch["steps"].append(TrackStep(active=False, note=def_n, length=1))
            elif cur_len > new_count:
                ch["steps"] = ch["steps"][:new_count]

    def clone(self, new_name):
        p = PatternData(name=new_name, steps_count=self.steps_count)
        for idx, ch in enumerate(self.channels):
            p.channels[idx]["inst_id"] = ch["inst_id"]
            p.channels[idx]["mute"] = ch["mute"]
            p.channels[idx]["solo"] = ch["solo"]
            p.channels[idx]["volume"] = ch["volume"]
            p.channels[idx]["steps"] = [st.copy() for st in ch["steps"]]
        return p

    def clear(self):
        for ch in self.channels:
            def_n = INSTRUMENT_CATALOG.get(ch["inst_id"], INSTRUMENT_CATALOG["dist_guitar"])["def_note"]
            for st in ch["steps"]:
                st.active = False
                st.slide = False
                st.length = 1
                st.note = def_n
                st.extra_notes.clear()

    def to_dict(self):
        return {
            "name": self.name,
            "steps": self.steps_count,
            "channels": [
                {
                    "inst_id": ch["inst_id"],
                    "mute": ch["mute"],
                    "solo": ch["solo"],
                    "volume": round(ch["volume"], 2),
                    "steps": [s.to_dict() for s in ch["steps"]]
                }
                for ch in self.channels
            ]
        }

    @classmethod
    def from_dict(cls, d):
        raw_steps = d.get("steps", 16)
        pat = cls(name=d.get("name", "Паттерн"), steps_count=raw_steps)
        if "channels" in d:
            for idx, ch_d in enumerate(d["channels"][:8]):
                iid = ch_d.get("inst_id", DEFAULT_CHANNEL_INSTS[idx])
                if iid not in INSTRUMENT_CATALOG:
                    iid = DEFAULT_CHANNEL_INSTS[idx]
                pat.channels[idx]["inst_id"] = iid
                pat.channels[idx]["mute"] = ch_d.get("mute", False)
                pat.channels[idx]["solo"] = ch_d.get("solo", False)
                pat.channels[idx]["volume"] = ch_d.get("volume", 0.80)
                loaded_steps = [TrackStep.from_dict(s) for s in ch_d.get("steps", [])]
                if loaded_steps:
                    pat.channels[idx]["steps"] = loaded_steps
        pat.resize_steps(pat.steps_count)
        return pat


class SongData:
    def __init__(self, bpm=120.0):
        self.bpm = bpm
        self.synth_params = {k: dict(v) for k, v in DEFAULT_SYNTH_PARAMS.items()}
        self.patterns = [
            PatternData(name="Паттерн 1", steps_count=16)
        ]
        self.playlist_bars = 32
        self.playlist_tracks = [[None for _ in range(self.playlist_bars)] for _ in range(4)]

    def ensure_playlist_length(self, min_bars):
        if min_bars > self.playlist_bars:
            add_n = min_bars - self.playlist_bars
            for tr in range(4):
                self.playlist_tracks[tr].extend([None] * add_n)
            self.playlist_bars = min_bars

    def reset_instrument_to_default(self, inst_id: str):
        if inst_id in DEFAULT_SYNTH_PARAMS:
            self.synth_params[inst_id] = dict(DEFAULT_SYNTH_PARAMS[inst_id])

    def set_channel_instrument_globally(self, ch_idx: int, new_inst_id: str):
        if new_inst_id not in INSTRUMENT_CATALOG:
            return
        new_def_note = INSTRUMENT_CATALOG[new_inst_id]["def_note"]
        for pat in self.patterns:
            ch = pat.channels[ch_idx]
            old_iid = ch["inst_id"]
            ch["inst_id"] = new_inst_id
            for st in ch["steps"]:
                if not st.active or INSTRUMENT_CATALOG.get(old_iid, {}).get("type") != INSTRUMENT_CATALOG[new_inst_id]["type"]:
                    st.note = new_def_note

    def set_channel_volume_globally(self, ch_idx: int, new_vol: float):
        """Устанавливает единую громкость дорожки сразу во всех паттернах трека."""
        v = round(max(0.0, min(1.0, float(new_vol))), 2)
        for pat in self.patterns:
            pat.channels[ch_idx]["volume"] = v

    def set_channel_mute_globally(self, ch_idx: int, mute_val: bool):
        for pat in self.patterns:
            pat.channels[ch_idx]["mute"] = bool(mute_val)

    def set_channel_solo_globally(self, ch_idx: int, solo_val: bool):
        for pat in self.patterns:
            pat.channels[ch_idx]["solo"] = bool(solo_val)

    def add_new_pattern(self, copy_from_idx=None):
        new_idx = len(self.patterns) + 1
        if copy_from_idx is not None and 0 <= copy_from_idx < len(self.patterns):
            new_p = self.patterns[copy_from_idx].clone(f"Паттерн {new_idx}")
        else:
            ref = self.patterns[0] if self.patterns else None
            steps_c = ref.steps_count if ref else 16
            new_p = PatternData(name=f"Паттерн {new_idx}", steps_count=steps_c)
            if ref:
                for i in range(8):
                    new_p.channels[i]["inst_id"] = ref.channels[i]["inst_id"]
                    new_p.channels[i]["volume"] = ref.channels[i]["volume"]
                    new_p.channels[i]["mute"] = ref.channels[i]["mute"]
                    new_p.channels[i]["solo"] = ref.channels[i]["solo"]
                    def_n = INSTRUMENT_CATALOG[new_p.channels[i]["inst_id"]]["def_note"]
                    for st in new_p.channels[i]["steps"]:
                        st.note = def_n
        self.patterns.append(new_p)
        return len(self.patterns) - 1

    def to_dict(self):
        return {
            "bpm": self.bpm,
            "synth_params": self.synth_params,
            "patterns": [p.to_dict() for p in self.patterns],
            "playlist_tracks": self.playlist_tracks,
        }

    @classmethod
    def from_dict(cls, d):
        song = cls(bpm=d.get("bpm", 120.0))
        if "synth_params" in d:
            for k, v in d["synth_params"].items():
                if k in song.synth_params:
                    song.synth_params[k].update(v)
        if "patterns" in d and d["patterns"]:
            song.patterns = [PatternData.from_dict(p) for p in d["patterns"]]
            # Выравниваем глобальные громкости и инструменты дорожек по Паттерну 1
            p0 = song.patterns[0]
            for ch_i in range(8):
                vol0 = p0.channels[ch_i]["volume"]
                song.set_channel_volume_globally(ch_i, vol0)
        if "playlist_tracks" in d:
            raw_pl = d["playlist_tracks"]
            max_b = max(32, max((len(row) for row in raw_pl), default=32))
            song.playlist_bars = max_b
            song.playlist_tracks = []
            for tr in range(4):
                row = list(raw_pl[tr]) if tr < len(raw_pl) else []
                while len(row) < max_b:
                    row.append(None)
                song.playlist_tracks.append(row)
        return song


class SynthVoiceEngine:
    """Процедурный синтезатор: Ударные, Акустические струнные, Средневековье и 16-бит Рок."""
    def __init__(self, sample_rate=44100):
        self.sr = sample_rate
        self._voice_cache = {}

    def invalidate_cache(self):
        self._voice_cache.clear()

    @staticmethod
    def _saw(phase):
        return 2.0 * (phase / (2.0 * np.pi) - np.floor(0.5 + phase / (2.0 * np.pi)))

    @staticmethod
    def _pulse(phase, duty=0.25):
        return np.where(np.sin(phase) >= duty, 1.0, -1.0)

    def _cabinet_filter(self, wave, cutoff_norm=0.65):
        cutoff_hz = 850.0 + cutoff_norm * 5200.0
        k_sz = max(2, int(self.sr / cutoff_hz))
        if k_sz <= 2:
            return wave
        kernel = np.ones(k_sz, dtype=np.float32) / k_sz
        return np.convolve(wave, kernel, mode="same")

    def _apply_smooth_tail(self, wave, tail_sec=0.030):
        n = len(wave)
        tail_len = min(n // 2, int(self.sr * tail_sec))
        if tail_len > 0:
            wave[-tail_len:] *= 0.5 + 0.5 * np.cos(np.linspace(0.0, np.pi, tail_len, dtype=np.float32))
        return wave

    def render_voice(self, inst_id, note_str, dur_sec, params=None, target_note_str=None):
        p = params or DEFAULT_SYNTH_PARAMS.get(inst_id, DEFAULT_SYNTH_PARAMS["dist_guitar"])
        drive = float(p.get("drive", 0.5))
        cutoff = float(p.get("cutoff", 0.7))
        punch = float(p.get("punch", 0.7))
        detune = float(p.get("detune", 0.3))
        decay = float(p.get("decay", 0.6))
        fifth_lvl = float(p.get("fifth", 0.5))

        cache_key = (
            inst_id, note_str, target_note_str, round(dur_sec, 3),
            round(drive, 2), round(cutoff, 2), round(punch, 2),
            round(detune, 2), round(decay, 2), round(fifth_lvl, 2)
        )
        if cache_key in self._voice_cache:
            return self._voice_cache[cache_key]

        f0 = NOTE_FREQS.get(note_str, 220.0)
        f1 = NOTE_FREQS.get(target_note_str, f0) if target_note_str else f0

        if inst_id == "rock_kick":
            dur = max(0.18, 0.16 + decay * 0.24)
            n = int(self.sr * dur)
            t = np.linspace(0, dur, n, False)
            f_env = f0 * 0.7 + (160.0 + punch * 110.0) * np.exp(-t * 38.0) + 28.0 * np.exp(-t * 9.0)
            phase = 2.0 * np.pi * np.cumsum(f_env) / self.sr
            sub = np.sin(phase) * np.exp(-t * (15.5 - decay * 6.5))
            click_len = min(n, int(self.sr * 0.014))
            click = np.sin(2.0 * np.pi * 2200.0 * t[:click_len]) * np.exp(-t[:click_len] * 210.0) * punch
            sub[:click_len] += click * 0.55
            out = self._apply_smooth_tail(np.tanh(sub * (1.3 + drive * 2.4)) * 0.92, 0.035)

        elif inst_id == "rock_snare":
            dur = max(0.15, 0.12 + decay * 0.24)
            n = int(self.sr * dur)
            t = np.linspace(0, dur, n, False)
            f_body = f0 * 1.15
            body = (
                np.sin(2.0 * np.pi * f_body * t) * 0.65
                + np.sin(2.0 * np.pi * (f_body * 1.58) * t) * 0.35
            ) * np.exp(-t * (24.0 - punch * 8.0))
            noise = np.random.uniform(-1.0, 1.0, n)
            wires = self._cabinet_filter(noise, cutoff) * np.exp(-t * (18.0 - decay * 9.0))
            snap_len = min(n, int(self.sr * 0.012))
            wires[:snap_len] *= (1.0 + punch * 0.9)
            out = self._apply_smooth_tail(np.tanh((body * 0.55 + wires * 0.75) * (1.2 + drive * 2.2)) * 0.85, 0.025)

        elif inst_id == "hihat":
            dur = max(0.05, 0.04 + decay * 0.18)
            n = int(self.sr * dur)
            t = np.linspace(0, dur, n, False)
            ratios = (1.0, 1.44, 1.68, 1.92, 2.53, 3.12)
            base_f = 3100.0 + cutoff * 2400.0
            metal = sum(np.sign(np.sin(2.0 * np.pi * base_f * r * t)) for r in ratios) / 6.0
            noise = np.random.uniform(-1.0, 1.0, n)
            hp = np.diff(metal * 0.55 + noise * 0.45, prepend=0.0)
            env = np.exp(-t * (48.0 - decay * 32.0))
            out = self._apply_smooth_tail(np.tanh(hp * env * (1.4 + drive * 1.8)) * 0.55, 0.015)

        elif inst_id == "crash":
            dur = max(0.28, 0.20 + decay * 0.55)
            n = int(self.sr * dur)
            t = np.linspace(0, dur, n, False)
            if f0 < 180.0:
                f_tom = np.linspace(f0 * 1.65, f0 * 0.65, n)
                phase = 2.0 * np.pi * np.cumsum(f_tom) / self.sr
                tom = np.sin(phase) * np.exp(-t * (14.0 - decay * 6.0))
                out = self._apply_smooth_tail(np.tanh(tom * (1.4 + drive * 2.0)) * 0.85, 0.030)
            else:
                ratios = (1.0, 1.37, 1.71, 2.19, 2.87)
                cym = sum(np.sin(2.0 * np.pi * (2800.0 + cutoff * 1800.0) * r * t) for r in ratios) * 0.2
                shimmer = np.random.uniform(-1.0, 1.0, n)
                hp = np.diff(cym + shimmer * 0.7, prepend=0.0)
                out = self._apply_smooth_tail(np.tanh(hp * np.exp(-t * (9.5 - decay * 5.0)) * (1.2 + drive * 1.5)) * 0.62, 0.040)

        elif inst_id == "war_drum":
            dur = max(0.24, 0.18 + decay * 0.32)
            n = int(self.sr * dur)
            t = np.linspace(0, dur, n, False)
            f_drop = f0 * (1.0 + 0.45 * np.exp(-t * 28.0))
            ph = 2.0 * np.pi * np.cumsum(f_drop) / self.sr
            skin = (
                np.sin(ph) * 0.75
                + np.sin(ph * 1.59) * 0.28 * np.exp(-t * 18.0)
                + np.sin(ph * 2.14) * 0.16 * np.exp(-t * 26.0)
            ) * np.exp(-t * (11.0 - decay * 5.5))
            thump_len = min(n, int(self.sr * 0.018))
            skin[:thump_len] += np.random.uniform(-0.35, 0.35, thump_len) * punch * np.sin(np.linspace(0, np.pi, thump_len))
            out = self._apply_smooth_tail(np.tanh(self._cabinet_filter(skin, cutoff) * (1.3 + drive * 2.2)) * 0.88, 0.035)

        elif inst_id == "tambourine":
            dur = max(0.14, 0.10 + decay * 0.22)
            n = int(self.sr * dur)
            t = np.linspace(0, dur, n, False)
            slap = np.sin(2.0 * np.pi * 290.0 * t) * np.exp(-t * 45.0) * punch * 0.45
            jingles = np.zeros(n, dtype=np.float32)
            for j_freq in (5400.0, 6850.0, 8120.0, 9400.0):
                jingles += np.sin(2.0 * np.pi * j_freq * t + np.sin(2.0 * np.pi * 42.0 * t)) * 0.25
            burst_env = (np.exp(-t * 22.0) + 0.45 * np.exp(-((t - 0.038) ** 2) * 1800.0)) * np.exp(-t * (16.0 - decay * 8.0))
            noise_hiss = np.diff(np.random.uniform(-1.0, 1.0, n), prepend=0.0)
            raw = slap + (jingles * 0.65 + noise_hiss * 0.35) * burst_env
            out = self._apply_smooth_tail(np.tanh(raw * (1.2 + drive * 1.6)) * 0.65, 0.020)

        elif inst_id in ("acoustic_steel", "acoustic_nylon", "bard_lute"):
            dur = max(0.16, dur_sec * (1.0 + decay * 0.35))
            n = int(self.sr * dur)
            t = np.linspace(0, dur, n, False)

            freq_curve = np.ones(n, dtype=np.float32) * f0
            if f1 != f0:
                slide_start = int(n * 0.45)
                freq_curve[slide_start:] = np.linspace(f0, f1, n - slide_start)

            ph1 = 2.0 * np.pi * np.cumsum(freq_curve) / self.sr
            det_hz = 1.0 + (0.0025 + detune * 0.006)
            ph2 = 2.0 * np.pi * np.cumsum(freq_curve * det_hz) / self.sr

            base_rate = 6.5 - decay * 4.2
            if inst_id == "acoustic_nylon":
                harm_weights = [(1.0, 0.72, 1.0), (2.0, 0.38, 1.8), (3.0, 0.18, 2.8), (4.0, 0.06, 4.2)]
                pluck_ms = 0.010
            elif inst_id == "bard_lute":
                harm_weights = [(1.0, 0.55, 1.0), (2.0, 0.50, 1.4), (3.0, 0.35, 2.1), (4.0, 0.22, 3.0), (5.0, 0.14, 4.0)]
                pluck_ms = 0.016
            else:
                harm_weights = [(1.0, 0.60, 1.0), (2.0, 0.45, 1.3), (3.0, 0.32, 1.9), (4.0, 0.22, 2.6), (5.0, 0.15, 3.5), (6.0, 0.10, 4.5)]
                pluck_ms = 0.014

            string_wave = np.zeros(n, dtype=np.float32)
            for h_mult, h_amp, h_decay_mult in harm_weights:
                h_env = np.exp(-t * (base_rate * h_decay_mult))
                string_wave += (np.sin(ph1 * h_mult) * 0.6 + np.sin(ph2 * h_mult) * 0.4) * h_amp * h_env

            if fifth_lvl > 0.02:
                string_wave += np.sin(ph1 * 1.4983) * (fifth_lvl * 0.40) * np.exp(-t * (base_rate * 1.4))

            p_len = min(n, int(self.sr * pluck_ms))
            if p_len > 2:
                pluck_burst = np.random.uniform(-0.7, 0.7, p_len) * np.exp(-np.linspace(0, 5.0, p_len)) * punch
                string_wave[:p_len] += pluck_burst * 0.55

            wood_body = np.sin(2.0 * np.pi * 195.0 * t) * np.exp(-t * 38.0) * punch * 0.22
            raw = self._cabinet_filter(string_wave + wood_body, cutoff)

            att = min(n, int(self.sr * 0.005))
            raw[:att] *= np.linspace(0.0, 1.0, att)
            out = self._apply_smooth_tail(np.tanh(raw * (1.15 + drive * 2.2)) * 0.80, 0.030)

        elif inst_id == "celtic_harp":
            dur = max(0.22, dur_sec * (1.2 + decay * 0.5))
            n = int(self.sr * dur)
            t = np.linspace(0, dur, n, False)
            freq_curve = np.linspace(f0, f1, n) if f1 != f0 else np.full(n, f0, dtype=np.float32)
            ph1 = 2.0 * np.pi * np.cumsum(freq_curve) / self.sr
            ph2 = 2.0 * np.pi * np.cumsum(freq_curve * (1.0 + detune * 0.005)) / self.sr

            rate = 4.2 - decay * 2.8
            harp = (
                (np.sin(ph1) + np.sin(ph2)) * 0.45 * np.exp(-t * rate)
                + np.sin(ph1 * 2.0) * (0.30 * cutoff) * np.exp(-t * rate * 1.7)
                + np.sin(ph2 * 3.0) * (0.15 * cutoff) * np.exp(-t * rate * 2.6)
                + np.sin(ph1 * 1.4983) * (0.30 * fifth_lvl) * np.exp(-t * rate * 1.3)
            )
            att = min(n, int(self.sr * 0.006))
            harp[:att] *= np.linspace(0.0, 1.0, att)
            out = self._apply_smooth_tail(np.tanh(harp * (1.1 + drive * 1.8)) * 0.78, 0.035)

        elif inst_id == "hurdy_gurdy":
            dur = max(0.14, dur_sec)
            n = int(self.sr * dur)
            t = np.linspace(0, dur, n, False)
            freq_curve = np.ones(n, dtype=np.float32) * f0
            if f1 != f0:
                slide_start = int(n * 0.45)
                freq_curve[slide_start:] = np.linspace(f0, f1, n - slide_start)

            vib = 1.0 + np.sin(2.0 * np.pi * 5.6 * t) * (0.006 + detune * 0.008)
            ph = 2.0 * np.pi * np.cumsum(freq_curve * vib) / self.sr
            ph_det = 2.0 * np.pi * np.cumsum(freq_curve * (1.004 + detune * 0.006)) / self.sr

            drone_f = f0 * 0.5
            ph_drone = 2.0 * np.pi * drone_f * t
            drone = (self._saw(ph_drone) * 0.5 + self._saw(ph_drone * 1.4983) * 0.5) * (0.45 * fifth_lvl)

            buzz_env = np.exp(-t * 14.0) * punch
            buzz = np.sign(np.sin(2.0 * np.pi * 36.0 * t)) * self._saw(ph * 2.0) * 0.35 * buzz_env

            chanter = self._saw(ph) * 0.50 + self._saw(ph_det) * 0.35 + np.sin(ph * 2.0) * 0.30
            raw = self._cabinet_filter(chanter + drone + buzz, cutoff)

            att = min(n, int(self.sr * 0.015))
            rel = min(n, int(self.sr * 0.045))
            env = np.ones(n, dtype=np.float32) * (0.55 + decay * 0.45)
            env[:att] = np.linspace(0.0, 1.0, att)
            env[-rel:] = np.linspace(1.0, 0.0, rel)
            out = self._apply_smooth_tail(np.tanh(raw * env * (1.4 + drive * 2.8)) * 0.72, 0.030)

        elif inst_id == "bagpipes":
            dur = max(0.14, dur_sec)
            n = int(self.sr * dur)
            t = np.linspace(0, dur, n, False)
            freq_curve = np.ones(n, dtype=np.float32) * f0
            grace_len = min(n, int(self.sr * 0.022))
            if grace_len > 2 and punch > 0.2:
                freq_curve[:grace_len] = f0 * 1.122
            if f1 != f0:
                slide_start = int(n * 0.50)
                freq_curve[slide_start:] = np.linspace(f0, f1, n - slide_start)

            ph = 2.0 * np.pi * np.cumsum(freq_curve) / self.sr
            reed = (
                self._pulse(ph, duty=0.18) * 0.45
                + np.sin(ph * 2.0) * 0.35
                + np.sin(ph * 3.0) * 0.45
                + np.sin(ph * 4.0) * 0.25
                + np.sin(ph * 5.0) * 0.20
            )
            ph_d = 2.0 * np.pi * (f0 * 0.5) * t
            drone = (self._pulse(ph_d, duty=0.25) * 0.55 + self._pulse(ph_d * 1.4983, duty=0.25) * 0.45) * (0.42 * fifth_lvl)

            raw = self._cabinet_filter(reed + drone, cutoff)
            att = min(n, int(self.sr * 0.010))
            rel = min(n, int(self.sr * 0.035))
            env = np.ones(n, dtype=np.float32)
            env[:att] = np.linspace(0.0, 1.0, att)
            env[-rel:] = np.linspace(1.0, 0.0, rel)
            out = self._apply_smooth_tail(np.tanh(raw * env * (1.4 + drive * 2.4)) * 0.70, 0.025)

        elif inst_id == "wood_flute":
            dur = max(0.14, dur_sec)
            n = int(self.sr * dur)
            t = np.linspace(0, dur, n, False)
            freq_curve = np.linspace(f0, f1, n) if f1 != f0 else np.full(n, f0, dtype=np.float32)
            vib = 1.0 + np.clip((t - 0.08) / 0.14, 0.0, 1.0) * np.sin(2.0 * np.pi * 5.4 * t) * (0.010 + detune * 0.012)
            ph = 2.0 * np.pi * np.cumsum(freq_curve * vib) / self.sr

            chiff = np.random.uniform(-0.35, 0.35, n) * (np.exp(-t * 45.0) * punch + 0.08)
            flute = (
                np.sin(ph) * 0.75
                + np.sin(ph * 2.0) * (0.25 * cutoff)
                + np.sin(ph * 3.0) * (0.12 * cutoff)
                + self._cabinet_filter(chiff, 0.45)
            )
            att = min(n, int(self.sr * 0.022))
            rel = min(n, int(self.sr * 0.045))
            env = np.ones(n, dtype=np.float32) * (0.5 + decay * 0.5)
            env[:att] = np.linspace(0.0, 1.0, att)
            env[-rel:] = np.linspace(1.0, 0.0, rel)
            out = self._apply_smooth_tail(np.tanh(flute * env * (1.1 + drive * 1.5)) * 0.74, 0.030)

        elif inst_id == "war_horn":
            dur = max(0.20, dur_sec * 1.15)
            n = int(self.sr * dur)
            t = np.linspace(0, dur, n, False)
            freq_curve = np.linspace(f0, f1, n) if f1 != f0 else np.full(n, f0, dtype=np.float32)
            vib = 1.0 + np.sin(2.0 * np.pi * 4.8 * t) * (0.008 + detune * 0.010)
            ph = 2.0 * np.pi * np.cumsum(freq_curve * vib) / self.sr

            brass = (
                np.sin(ph) * 0.55
                + np.sin(ph * 2.0) * 0.48
                + np.sin(ph * 3.0) * (0.40 * cutoff)
                + np.sin(ph * 4.0) * (0.25 * cutoff)
                + np.sin(ph * 1.4983) * (0.40 * fifth_lvl)
            )
            att = min(n // 2, int(self.sr * (0.045 - punch * 0.025)))
            rel = min(n // 2, int(self.sr * 0.065))
            env = np.ones(n, dtype=np.float32) * (0.6 + decay * 0.4)
            if att > 2:
                env[:att] = np.linspace(0.0, 1.0, att)
            if rel > 2:
                env[-rel:] = np.linspace(1.0, 0.0, rel)
            out = self._apply_smooth_tail(np.tanh(brass * env * (1.3 + drive * 2.5)) * 0.78, 0.040)

        elif inst_id == "chapel_bell":
            dur = max(0.28, dur_sec * (1.3 + decay * 0.6))
            n = int(self.sr * dur)
            t = np.linspace(0, dur, n, False)
            ph = 2.0 * np.pi * f0 * t
            rate = 5.5 - decay * 3.8
            bell = (
                np.sin(ph) * 0.60 * np.exp(-t * rate)
                + np.sin(ph * 2.0) * 0.35 * np.exp(-t * rate * 1.4)
                + np.sin(ph * 2.41) * (0.40 * cutoff) * np.exp(-t * rate * 1.9)
                + np.sin(ph * 2.92) * (0.25 * cutoff) * np.exp(-t * rate * 2.6)
                + np.sin(ph * 3.85) * (0.18 * punch) * np.exp(-t * rate * 3.8)
            )
            att = min(n, int(self.sr * 0.004))
            bell[:att] *= np.linspace(0.0, 1.0, att)
            out = self._apply_smooth_tail(np.tanh(bell * (1.2 + drive * 2.0)) * 0.75, 0.040)

        elif inst_id == "slap_bass":
            dur = max(0.12, dur_sec)
            n = int(self.sr * dur)
            t = np.linspace(0, dur, n, False)
            freq_curve = np.ones(n, dtype=np.float32) * f0
            if f1 != f0:
                slide_start = int(n * 0.55)
                freq_curve[slide_start:] = np.linspace(f0, f1, n - slide_start)

            phase = 2.0 * np.pi * np.cumsum(freq_curve) / self.sr
            mod_env = np.exp(-t * (28.0 - punch * 14.0)) * (1.8 + punch * 3.5)
            mod2 = np.sin(phase * 2.0 + np.sin(phase * 4.0) * 0.7) * mod_env
            carrier = np.sin(phase + mod2) * 0.72 + self._saw(phase * 1.002) * 0.28
            sub = np.sin(phase) * 0.55
            raw = self._cabinet_filter(carrier, cutoff) + sub

            env = (0.35 + 0.65 * decay) + (1.0 - 0.35) * np.exp(-t * (10.0 - decay * 6.0))
            att = min(n, int(self.sr * 0.006))
            rel = min(n, int(self.sr * 0.032))
            env[:att] *= np.linspace(0.0, 1.0, att)
            env[-rel:] *= np.linspace(1.0, 0.0, rel)
            out = self._apply_smooth_tail(np.tanh(raw * env * (1.2 + drive * 2.6)) * 0.80, 0.025)

        elif inst_id == "dist_guitar":
            dur = max(0.12, dur_sec)
            n = int(self.sr * dur)
            t = np.linspace(0, dur, n, False)
            freq_curve = np.ones(n, dtype=np.float32) * f0
            if f1 != f0:
                slide_start = int(n * 0.50)
                freq_curve[slide_start:] = np.linspace(f0, f1, n - slide_start)

            vib = 1.0 + np.clip((t - 0.14) / 0.15, 0.0, 1.0) * np.sin(2.0 * np.pi * 5.8 * t) * 0.008
            f_inst = freq_curve * vib

            ph1 = 2.0 * np.pi * np.cumsum(f_inst) / self.sr
            ph2 = 2.0 * np.pi * np.cumsum(f_inst * (1.0 + detune * 0.012)) / self.sr
            ph_fifth = 2.0 * np.pi * np.cumsum(f_inst * 1.4983) / self.sr
            ph_oct = 2.0 * np.pi * np.cumsum(f_inst * 2.0) / self.sr

            pick_env = np.exp(-t * 95.0) * punch
            pick_noise = np.random.uniform(-0.6, 0.6, n) * pick_env

            osc_mix = (
                self._saw(ph1) * 0.55
                + self._pulse(ph2, duty=0.22) * 0.45
                + self._saw(ph_fifth) * (0.65 * fifth_lvl)
                + np.sin(ph_oct + np.sin(ph1 * 3.0) * pick_env * 2.5) * 0.30
                + pick_noise
            )
            gain = 1.8 + drive * 6.5
            driven = np.tanh(osc_mix * gain + 0.18) - np.tanh(0.18)
            cab = self._cabinet_filter(driven, cutoff)

            sustain_floor = 0.25 + decay * 0.70
            env = sustain_floor + (1.0 - sustain_floor) * np.exp(-t * 6.0)
            att = min(n, int(self.sr * 0.008))
            rel = min(n, int(self.sr * 0.038))
            env[:att] *= np.linspace(0.0, 1.0, att)
            env[-rel:] *= np.linspace(1.0, 0.0, rel)
            out = self._apply_smooth_tail(cab * env * 0.74, 0.025)

        elif inst_id == "screamer_lead":
            dur = max(0.12, dur_sec)
            n = int(self.sr * dur)
            t = np.linspace(0, dur, n, False)
            freq_curve = np.ones(n, dtype=np.float32) * f0
            scoop_len = min(n, int(self.sr * (0.035 * punch)))
            if scoop_len > 4:
                freq_curve[:scoop_len] = np.linspace(f0 * 0.91, f0, scoop_len)
            if f1 != f0:
                slide_start = int(n * 0.45)
                freq_curve[slide_start:] = np.linspace(f0, f1, n - slide_start)

            vib_depth = np.clip((t - 0.10) / 0.16, 0.0, 1.0) * (0.015 + detune * 0.018)
            vib = 1.0 + np.sin(2.0 * np.pi * 6.2 * t) * vib_depth
            f_inst = freq_curve * vib

            ph1 = 2.0 * np.pi * np.cumsum(f_inst) / self.sr
            ph2 = 2.0 * np.pi * np.cumsum(f_inst * (1.0 + 0.006 + detune * 0.012)) / self.sr
            ph3 = 2.0 * np.pi * np.cumsum(f_inst * (1.0 - 0.006 - detune * 0.012)) / self.sr

            lead_raw = (
                self._saw(ph1) * 0.50
                + self._saw(ph2) * 0.35
                + self._pulse(ph3, duty=0.35) * 0.35
                + np.sin(ph1 * 1.4983) * (0.35 * fifth_lvl)
                + np.sin(ph1 * 0.5) * 0.25
            )
            driven = np.tanh(lead_raw * (1.6 + drive * 4.5))
            cab = self._cabinet_filter(driven, min(1.0, cutoff + 0.12))

            att = min(n, int(self.sr * 0.012))
            rel = min(n, int(self.sr * 0.045))
            env = np.ones(n, dtype=np.float32) * (0.4 + decay * 0.6)
            env[:att] = np.linspace(0.0, 1.0, att)
            env[-rel:] = np.linspace(1.0, 0.0, rel)
            out = self._apply_smooth_tail(cab * env * 0.72, 0.025)

        else:  # grunge_organ
            dur = max(0.12, dur_sec)
            n = int(self.sr * dur)
            t = np.linspace(0, dur, n, False)
            freq_curve = np.linspace(f0, f1, n) if f1 != f0 else np.full(n, f0, dtype=np.float32)
            leslie = 1.0 + np.sin(2.0 * np.pi * 6.4 * t) * (0.004 + detune * 0.010)
            ph = 2.0 * np.pi * np.cumsum(freq_curve * leslie) / self.sr

            organ = (
                np.sin(ph) * 0.55
                + np.sin(ph * 2.0) * 0.40
                + np.sin(ph * 3.0) * (0.35 * cutoff)
                + np.sin(ph * 4.0) * (0.25 * cutoff)
                + np.sin(ph * 1.4983) * (0.40 * fifth_lvl)
            )
            click_env = np.exp(-t * 140.0) * punch * 0.35
            organ += np.sin(ph * 6.0) * click_env
            driven = np.tanh(organ * (1.1 + drive * 2.5))

            att = min(n, int(self.sr * 0.015))
            rel = min(n, int(self.sr * 0.050))
            env = np.ones(n, dtype=np.float32)
            env[:att] = np.linspace(0.0, 1.0, att)
            env[-rel:] = np.linspace(1.0, 0.0, rel)
            out = self._apply_smooth_tail(driven * env * 0.65, 0.025)

        out = out.astype(np.float32)
        if len(self._voice_cache) > 512:
            self._voice_cache.clear()
        self._voice_cache[cache_key] = out
        return out


class MusicLoopCompiler:
    def __init__(self, sample_rate=44100):
        if pygame.mixer.get_init():
            self.sr = pygame.mixer.get_init()[0]
        else:
            self.sr = sample_rate
        self.synth = SynthVoiceEngine(sample_rate=self.sr)
        self.last_compiled_wave = np.zeros(1024, dtype=np.float32)

    @staticmethod
    def _add_wrapped(mix, wave, idx0, gain=1.0):
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
            p1 = n_total - idx0
            mix[idx0:n_total] += w_scaled[:p1]
            rem = n_w - p1
            while rem > 0:
                chunk = min(rem, n_total)
                start_w = n_w - rem
                mix[:chunk] += w_scaled[start_w:start_w + chunk]
                rem -= chunk

    def _filter_lpf(self, wave_float, cutoff_hz=240.0, passes=3):
        kernel_sz = max(5, int(self.sr / cutoff_hz))
        kernel = np.ones(kernel_sz, dtype=np.float32) / kernel_sz
        w = wave_float.copy()
        for _ in range(passes):
            w = np.convolve(w, kernel, mode="same")
        return np.tanh(w * 2.5) * 0.92

    def make_pygame_sound(self, wave_float):
        clipped = np.clip(wave_float * 32767.0, -32768, 32767).astype(np.int16)
        channels = pygame.mixer.get_init()[2] if pygame.mixer.get_init() else 2
        if channels == 2:
            right = np.roll(clipped, 6)
            stereo = np.column_stack((clipped, right))
            return pygame.sndarray.make_sound(stereo)
        return pygame.sndarray.make_sound(clipped)

    def preview_single_note(self, inst_id, note_str, dur_sec=0.35, params=None):
        w = self.synth.render_voice(inst_id, note_str, dur_sec, params=params)
        self.last_compiled_wave = w
        return self.make_pygame_sound(w * 0.85)

    def _render_pattern_into_buffer(self, mix, pattern: PatternData, bpm: float, synth_params: dict, bar_offset_samples=0, ignore_solo=False):
        beat_len = 60.0 / bpm
        step_len = beat_len / 4.0
        n_steps = pattern.steps_count
        has_solo = (not ignore_solo) and any(ch["solo"] for ch in pattern.channels)

        for ch in pattern.channels:
            if has_solo and not ch["solo"]:
                continue
            if ch["mute"]:
                continue

            tid = ch["inst_id"]
            tr_vol = ch["volume"]
            t_params = synth_params.get(tid, DEFAULT_SYNTH_PARAMS.get(tid))
            steps_list = ch["steps"][:n_steps]

            for step_i, st in enumerate(steps_list):
                notes_dict = st.get_all_notes()
                if not notes_dict:
                    continue

                target_note = None
                if st.slide and n_steps > 0:
                    for look_ahead in range(1, st.length + 2):
                        nxt_st = steps_list[(step_i + look_ahead) % len(steps_list)]
                        if nxt_st.active:
                            target_note = nxt_st.note
                            break

                pos = bar_offset_samples + int(step_i * step_len * self.sr)
                chord_scale = 1.0 / math.sqrt(max(1, len(notes_dict)))
                for n_str, n_len in notes_dict.items():
                    note_dur = step_len * n_len
                    t_n = target_note if (n_str == st.note) else None
                    w = self.synth.render_voice(tid, n_str, note_dur, params=t_params, target_note_str=t_n)
                    self._add_wrapped(mix, w, pos, gain=st.volume * tr_vol * chord_scale)

    def compile_pattern(self, pattern: PatternData, bpm: float, synth_params: dict, make_muffled=False):
        beat_len = 60.0 / bpm
        step_len = beat_len / 4.0
        total_dur = step_len * max(4, pattern.steps_count)
        n_samples = max(64, int(self.sr * total_dur))
        mix = np.zeros(n_samples, dtype=np.float32)

        self._render_pattern_into_buffer(mix, pattern, bpm, synth_params)

        tiled = np.concatenate([mix, mix, mix])
        mastered_dry = np.tanh(tiled * 1.25) * 0.80
        processed = self._filter_lpf(mastered_dry) if make_muffled else mastered_dry
        loop_wave = processed[n_samples:2 * n_samples].copy()
        self.last_compiled_wave = loop_wave
        return self.make_pygame_sound(loop_wave)

    def compile_song(self, song: SongData, make_muffled=False):
        beat_len = 60.0 / song.bpm
        bar_len = beat_len * 4.0
        active_bars = 1
        for b in range(song.playlist_bars):
            for tr in range(4):
                p_idx = song.playlist_tracks[tr][b]
                if p_idx is not None and 0 <= p_idx < len(song.patterns):
                    pat_bars = max(1, math.ceil(song.patterns[p_idx].steps_count / 16.0))
                    active_bars = max(active_bars, b + pat_bars)

        total_dur = bar_len * active_bars
        n_samples = max(64, int(self.sr * total_dur))
        mix = np.zeros(n_samples, dtype=np.float32)

        for tr_idx in range(4):
            for b_idx in range(min(song.playlist_bars, active_bars)):
                p_idx = song.playlist_tracks[tr_idx][b_idx]
                if p_idx is not None and 0 <= p_idx < len(song.patterns):
                    pat = song.patterns[p_idx]
                    bar_offset = int(b_idx * bar_len * self.sr)
                    self._render_pattern_into_buffer(mix, pat, song.bpm, song.synth_params, bar_offset_samples=bar_offset, ignore_solo=True)

        tiled = np.concatenate([mix, mix, mix])
        mastered_dry = np.tanh(tiled * 1.25) * 0.80
        processed = self._filter_lpf(mastered_dry) if make_muffled else mastered_dry
        song_wave = processed[n_samples:2 * n_samples].copy()
        self.last_compiled_wave = song_wave
        return self.make_pygame_sound(song_wave), active_bars


def load_preset_into_song(song: SongData, preset_id: str):
    """Загружает один из 4 жанровых пресетов."""
    song.patterns = [PatternData(name=f"Паттерн {i+1}", steps_count=16) for i in range(4)]
    song.playlist_tracks = [[None for _ in range(song.playlist_bars)] for _ in range(4)]

    if preset_id == "grunge_drive":
        song.bpm = 122.0
        rack = ["rock_kick", "rock_snare", "hihat", "crash", "slap_bass", "dist_guitar", "screamer_lead", "grunge_organ"]
        for ch_i, iid in enumerate(rack):
            song.set_channel_instrument_globally(ch_i, iid)
            song.set_channel_volume_globally(ch_i, 0.80)

        p1 = song.patterns[0]
        p1.name = "П1: Бас-Грув"
        for s in (0, 3, 6, 8, 14):
            p1.channels[0]["steps"][s].active = True
        for s in (4, 12):
            p1.channels[1]["steps"][s].active = True
        for s in range(0, 16, 2):
            p1.channels[2]["steps"][s].active = True
        p1.channels[3]["steps"][0].active = True
        p1.channels[3]["steps"][0].note = "C5"

        bass_notes = [(0, "D2", 2, False), (2, "D2", 1, False), (3, "F2", 1, True), (4, "G2", 2, False),
                      (6, "G#2", 1, True), (7, "A2", 1, False), (8, "D2", 2, False), (10, "C3", 2, False),
                      (12, "A2", 2, False), (14, "G2", 2, True)]
        for s, n, l, sl in bass_notes:
            st = p1.channels[4]["steps"][s]
            st.active, st.note, st.length, st.slide = True, n, l, sl

        p2 = song.patterns[1]
        p2.name = "П2: Рок-Рифф"
        gtr = [(0, "D3", 3, False), (3, "F3", 1, True), (4, "G3", 2, False), (6, "G#3", 2, False),
               (8, "D3", 3, False), (11, "C3", 1, False), (12, "A2", 2, False), (14, "C3", 2, True)]
        for s, n, l, sl in gtr:
            st = p2.channels[5]["steps"][s]
            st.active, st.note, st.length, st.slide = True, n, l, sl

        p3 = song.patterns[2]
        p3.name = "П3: Соло-Запил"
        solo = [(0, "D4", 4, True), (4, "F4", 2, True), (6, "G4", 2, True),
                (8, "A4", 4, False), (12, "C5", 2, True), (14, "A4", 2, False)]
        for s, n, l, sl in solo:
            st = p3.channels[6]["steps"][s]
            st.active, st.note, st.length, st.slide = True, n, l, sl

        for b in range(8):
            song.playlist_tracks[0][b] = 0
            if b >= 2:
                song.playlist_tracks[1][b] = 1
            if b >= 4:
                song.playlist_tracks[2][b] = 2

    elif preset_id == "bard_ballad":
        song.bpm = 108.0
        rack = ["war_drum", "tambourine", "acoustic_steel", "acoustic_nylon", "bard_lute", "celtic_harp", "wood_flute", "hurdy_gurdy"]
        for ch_i, iid in enumerate(rack):
            song.set_channel_instrument_globally(ch_i, iid)
            song.set_channel_volume_globally(ch_i, 0.78)

        p1 = song.patterns[0]
        p1.name = "П1: Перебор"
        for s in (0, 6, 8, 12):
            p1.channels[0]["steps"][s].active = True
            p1.channels[0]["steps"][s].note = "D2" if s in (0, 8) else "A2"
        for s in (4, 12, 14):
            p1.channels[1]["steps"][s].active = True

        ac_steel = [(0, "D2", 4, {"A2": 4, "D3": 4}), (4, "F2", 4, {"C3": 4, "F3": 4}),
                    (8, "C2", 4, {"G2": 4, "E3": 4}), (12, "G2", 4, {"D3": 4, "B3": 4})]
        for s, n, l, ex in ac_steel:
            st = p1.channels[2]["steps"][s]
            st.active, st.note, st.length, st.extra_notes = True, n, l, dict(ex)

        lute_arp = [(0, "D4"), (2, "F4"), (3, "A4"), (4, "C4"), (6, "F4"), (7, "A4"),
                    (8, "C4"), (10, "E4"), (11, "G4"), (12, "B3"), (14, "D4"), (15, "G4")]
        for s, n in lute_arp:
            st = p1.channels[4]["steps"][s]
            st.active, st.note, st.length = True, n, 2

        p2 = song.patterns[1]
        p2.name = "П2: Флейта и Арфа"
        flute_mel = [(0, "A4", 3, True), (3, "G4", 1, False), (4, "F4", 4, False),
                     (8, "E4", 2, True), (10, "G4", 2, False), (12, "D4", 4, False)]
        for s, n, l, sl in flute_mel:
            st = p2.channels[6]["steps"][s]
            st.active, st.note, st.length, st.slide = True, n, l, sl

        harp_notes = [(0, "D4", 4), (4, "A4", 4), (8, "G4", 4), (12, "F4", 4)]
        for s, n, l in harp_notes:
            st = p2.channels[5]["steps"][s]
            st.active, st.note, st.length = True, n, l

        for b in range(8):
            song.playlist_tracks[0][b] = 0
            if b >= 2:
                song.playlist_tracks[1][b] = 1

    elif preset_id == "medieval_march":
        song.bpm = 114.0
        rack = ["war_drum", "tambourine", "chapel_bell", "war_horn", "hurdy_gurdy", "bagpipes", "bard_lute", "wood_flute"]
        for ch_i, iid in enumerate(rack):
            song.set_channel_instrument_globally(ch_i, iid)
            song.set_channel_volume_globally(ch_i, 0.78)

        p1 = song.patterns[0]
        p1.name = "П1: Лира и Набат"
        for s in (0, 3, 4, 8, 11, 12, 14):
            p1.channels[0]["steps"][s].active = True
            p1.channels[0]["steps"][s].note = "D2" if s % 4 == 0 else "A2"
        for s in (4, 12):
            p1.channels[1]["steps"][s].active = True
        p1.channels[2]["steps"][0].active = True
        p1.channels[2]["steps"][0].note = "D4"
        p1.channels[2]["steps"][0].length = 4

        hg_riff = [(0, "D3", 3, False), (3, "F3", 1, True), (4, "G3", 2, False), (6, "A3", 2, False),
                   (8, "A#3", 2, True), (10, "A3", 2, False), (12, "G3", 2, True), (14, "D3", 2, False)]
        for s, n, l, sl in hg_riff:
            st = p1.channels[4]["steps"][s]
            st.active, st.note, st.length, st.slide = True, n, l, sl

        p2 = song.patterns[1]
        p2.name = "П2: Волынка и Рог"
        for s, n in ((0, "D2"), (8, "A2")):
            st = p2.channels[3]["steps"][s]
            st.active, st.note, st.length = True, n, 6
        pipes = [(0, "D4", 2, False), (2, "F4", 2, True), (4, "G4", 3, False), (7, "F4", 1, False),
                 (8, "E4", 2, False), (10, "C4", 2, True), (12, "D4", 4, False)]
        for s, n, l, sl in pipes:
            st = p2.channels[5]["steps"][s]
            st.active, st.note, st.length, st.slide = True, n, l, sl

        for b in range(8):
            song.playlist_tracks[0][b] = 0
            if b >= 2:
                song.playlist_tracks[1][b] = 1

    elif preset_id == "boss_metal":
        song.bpm = 138.0
        rack = ["rock_kick", "rock_snare", "hihat", "crash", "slap_bass", "dist_guitar", "grunge_organ", "chapel_bell"]
        for ch_i, iid in enumerate(rack):
            song.set_channel_instrument_globally(ch_i, iid)
            song.set_channel_volume_globally(ch_i, 0.80)

        p1 = song.patterns[0]
        p1.name = "П1: Кардан-Бит"
        for s in (0, 2, 3, 6, 8, 10, 11, 14):
            p1.channels[0]["steps"][s].active = True
        for s in (4, 12):
            p1.channels[1]["steps"][s].active = True
        for s in range(16):
            p1.channels[2]["steps"][s].active = True
        p1.channels[3]["steps"][0].active = True
        p1.channels[7]["steps"][0].active = True
        p1.channels[7]["steps"][0].note = "D4"

        riff = [(0, "D2", 2), (2, "D2", 2), (4, "A#2", 2), (6, "A2", 2),
                (8, "D2", 2), (10, "F2", 2), (12, "G2", 2), (14, "E2", 2)]
        for s, n, l in riff:
            st_b = p1.channels[4]["steps"][s]
            st_b.active, st_b.note, st_b.length = True, n, l
            st_g = p1.channels[5]["steps"][s]
            st_g.active, st_g.note, st_g.length = True, n.replace("2", "3"), l

        p2 = song.patterns[1]
        p2.name = "П2: Орган Бездны"
        chords = [(0, "D4", 4, {"F4": 4, "A4": 4}), (4, "A#3", 4, {"D4": 4, "F4": 4}),
                  (8, "G3", 4, {"A#3": 4, "D4": 4}), (12, "A3", 4, {"C#4": 4, "E4": 4})]
        for s, n, l, ex in chords:
            st = p2.channels[6]["steps"][s]
            st.active, st.note, st.length, st.extra_notes = True, n, l, dict(ex)

        for b in range(8):
            song.playlist_tracks[0][b] = 0
            if b >= 2:
                song.playlist_tracks[1][b] = 1