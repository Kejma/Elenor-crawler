"""Short procedural enemy calls, with a different pitch and timbre per species."""

import random

import numpy as np


# Timbre, pitch in Hz, duration in seconds.
VOICES = {
    "rat": ("squeak", 1170, .125),
    "rat_cultist": ("squeak", 820, .19),
    "rat_king": ("growl", 98, .41),
    "wolf": ("growl", 147, .35),
    "skeleton": ("rattle", 525, .29),
    "cultist": ("vowel", 125, .31),
    "necromancer": ("vowel", 93, .43),
    "brute": ("growl", 71, .45),
    "tribal_warrior": ("tribal", 136, .30),
    "tribal_hunter": ("tribal", 181, .28),
    "tribal_shaman": ("tribal", 110, .37),
    "croc_warrior": ("growl", 84, .34),
    "croc_juggernaut": ("growl", 62, .47),
    "vedalken_mage": ("vowel", 202, .37),
    "vedalken_four_armed": ("vowel", 157, .34),
    "vedalken_arbiter": ("vowel", 118, .52),
    "swamp_lurker": ("growl", 102, .32),
    "jungle_gremlin": ("squeak", 470, .22),
    "jungle_viper": ("hiss", 1560, .31),
    "giant_scorpion": ("rattle", 770, .23),
    "myconid_shambler": ("vowel", 76, .48),
    "thorn_treant": ("rattle", 198, .47),
    "giant_wasp": ("buzz", 195, .27),
    "rust_monster": ("buzz", 122, .30),
    "cave_piercer": ("rattle", 654, .20),
    "cave_angler": ("hiss", 950, .34),
    "marble_golem": ("rattle", 123, .44),
    "jade_scarab": ("buzz", 267, .21),
    "skull_spider": ("rattle", 890, .25),
    "bone_jaguar": ("growl", 123, .39),
    "bone_constrictor": ("hiss", 1250, .41),
    "ossuary_behemoth": ("growl", 52, .57),
}

_voice_rng = random.Random()


def voice_name(kind, variant):
    return f"voice_{kind if kind in VOICES else 'rat'}_{variant}"


def choose_voice(kind):
    return voice_name(kind, _voice_rng.randrange(2))


def next_call_delay(kind, *, initial=False):
    if initial:
        return _voice_rng.uniform(5, 27)
    low, high = (27, 52) if kind.startswith("tribal_") else (15, 32)
    return _voice_rng.uniform(low, high)


def _vowel(rate, pitch, duration, formants, noise, rising):
    t = np.arange(int(rate * duration)) / rate
    progress = t / duration
    pitch_curve = pitch * np.interp(progress, (0, .22, .65, 1), (.84, 1.11, 1.04, rising))
    phase = np.cumsum(pitch_curve) * (2 * np.pi / rate)
    wave = np.zeros_like(t)
    for harmonic in range(1, 22):
        frequency = pitch_curve * harmonic
        if harmonic >= 3 and harmonic * pitch > rate * .46:
            break
        emphasis = .08
        for center, width in zip(formants, (115, 160, 230)):
            emphasis = emphasis + np.exp(-.5 * ((frequency - center) / width) ** 2)
        wave += np.sin(phase * harmonic) * emphasis / harmonic ** .50
    breath = noise[:len(t)] * np.exp(-progress * 4) * .28
    envelope = np.minimum(1, progress * 9) * np.minimum(1, (1 - progress) * 5) * np.exp(-progress * 1.2)
    return (wave * .7 + breath) * envelope


def enemy_voice_waves(rate):
    rng = np.random.default_rng(3314)
    for kind, (timbre, base_pitch, base_duration) in VOICES.items():
        for variant in range(2):
            pitch = base_pitch * (1.08 if variant else 1)
            duration = base_duration * (1.11 if variant else 1)
            noise = rng.uniform(-1, 1, int(rate * duration * 2))
            if timbre == "tribal":
                # Rounded, aspirated "huh", or a short three-syllable "bo-ya-ya".
                syllables = ([(1.0, 1.0, (530, 1050, 2400), .64)] if variant == 0 else [
                    (.37, 1.0, (475, 840, 2390), .97),
                    (.30, 1.22, (690, 1680, 2520), 1.05),
                    (.33, .93, (745, 1420, 2490), .66),
                ])
                wave = np.concatenate([_vowel(rate, pitch * bend, duration * length, bands, noise, end)
                                       for length, bend, bands, end in syllables])
            elif timbre == "vowel":
                bands = (390 + pitch * 1.15, 990 + pitch * 3, 2460)
                wave = _vowel(rate, pitch, duration, bands, noise, .72 if not variant else .96)
            else:
                t = np.arange(int(rate * duration)) / rate
                progress = t / duration
                noise = noise[:len(t)]
                phase = np.cumsum(pitch * (1.0 - .28 * progress + .08 * np.sin(47 * t))) * (2 * np.pi / rate)
                wave = np.sin(phase)
                if timbre == "squeak":
                    wave = (wave + .21 * np.sin(phase * 2.0)) * (0.72 + .28 * np.cos(53 * t))
                elif timbre == "hiss":
                    wave = (noise - np.roll(noise, 2)) * .42 + wave * .12
                elif timbre == "rattle":
                    wave = (.44 * wave + noise * .56) * np.exp(-((progress * (4 + variant)) % 1) * 7)
                elif timbre == "buzz":
                    wave = (wave * .65 + .34 * np.sin(phase * 3) + noise * .16) * (1 + .42 * np.sin(155 * t))
                else:
                    wave = (wave * .37 + .36 * np.sin(phase * 2) + .17 * np.sin(phase * 5) + noise * .27)
                    wave *= .76 + .24 * np.cos(109 * t)
                wave *= np.minimum(1, progress * 16) * (1.0 - progress) ** 1.7
            yield voice_name(kind, variant), wave * .24, 530 if pitch >= 450 else 360
