"""Short, distinct cues for preparing and releasing player abilities."""

import numpy as np


# Timbre, length, start and end frequencies, gain.
RELEASES = {
    "whirlwind": ("air", .23, 1180, 350, .18),
    "earth_slam": ("ground", .34, 105, 37, .30),
    "heavy_strike": ("ground", .16, 173, 66, .33),
    "shield_bash": ("metal", .24, 420, 290, .26),
    "cleave": ("edge", .22, 430, 930, .24),
    "war_stomp": ("air", .29, 460, 91, .27),
    "throw_knife": ("edge", .095, 1630, 910, .23),
    "poison_flask": ("glass", .16, 960, 520, .18),
    "piercing_shot": ("edge", .145, 1040, 460, .25),
    "hamstring": ("air", .13, 1590, 840, .18),
    "fan_blades": ("metal", .115, 580, 490, .23),
    "venom_strike": ("whisper", .22, 410, 190, .13),
    "pyro_firebolt": ("fire", .21, 610, 116, .27),
    "pyro_ignite": ("fire", .37, 112, 420, .23),
    "stratos_frost_nova": ("glass", .30, 1380, 840, .22),
    "stratos_chain_lightning": ("spark", .27, 660, 1620, .24),
    "persephone_rejuvenation": ("bell", .39, 395, 630, .23),
    "persephone_entangle": ("ground", .25, 216, 92, .23),
    "scroll_spark": ("spark", .18, 1230, 420, .23),
    "scroll_fireball": ("fire", .32, 270, 69, .29),
}

IMPACTS = {
    "ability_trap_snap": ("metal", .20, 325, 206, .32),
    "ability_flask_break": ("glass", .25, 1700, 525, .20),
}


def ability_sound(item_id):
    return f"ability_{item_id}" if item_id in RELEASES else "magic"


def ability_waves(rate):
    rng = np.random.default_rng(1732)
    cues = {f"ability_{pid}": recipe for pid, recipe in RELEASES.items()} | IMPACTS
    cues["ability_prepare"] = ("click", .034, 950, 570, .065)
    for key, (timbre, duration, start, end, gain) in cues.items():
        t = np.arange(int(rate * duration)) / rate
        progress = t / duration
        phase = np.cumsum(start + (end - start) * progress) * (2 * np.pi / rate)
        sine, overtone = np.sin(phase), np.sin(phase * 2.37)
        noise = rng.uniform(-1, 1, len(t))
        soft_noise = np.convolve(noise, np.ones(7) / 7, mode="same")
        attack = 95
        decay = 5
        if timbre == "click":
            wave = .56 * sine + .44 * noise
            attack, decay = 750, 7
        elif timbre == "air":
            wave = soft_noise * 1.9 + .28 * sine
            attack, decay = 23, 3
        elif timbre == "ground":
            wave = .75 * sine + .56 * soft_noise * np.exp(-progress * 2.5)
            attack, decay = 170, 4
        elif timbre == "metal":
            wave = .30 * sine + .50 * overtone + .18 * np.sin(phase * 4.12)
            wave *= .72 + .28 * np.cos(t * 189)
        elif timbre == "edge":
            wave = .50 * sine + .30 * overtone + .28 * soft_noise
            attack, decay = 115, 4
        elif timbre == "glass":
            wave = .29 * sine + .47 * overtone + .22 * np.sin(phase * 3.64)
            wave += noise * .24 * np.exp(-progress * 9)
        elif timbre == "spark":
            wave = (.48 * sine + .43 * noise) * (.30 + .70 * np.cos(155 * t) ** 2)
        elif timbre == "fire":
            grain = (rng.random(len(t)) > .965) * noise
            wave = 1.32 * soft_noise + .41 * sine + .30 * grain
            attack, decay = 52, 3
        elif timbre == "bell":
            wave = .56 * sine + .23 * np.sin(phase * 1.51) + .24 * overtone
            attack, decay = 31, 2.7
        else:
            wave = (noise - soft_noise) * .35 + sine * .30
            attack, decay = 24, 4

        envelope = np.minimum(1, t * attack) * (1 - progress) * np.exp(-progress * decay)
        yield key, wave * envelope * gain
