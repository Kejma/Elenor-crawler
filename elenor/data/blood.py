"""Shared color palettes for blood particles and decals."""

from typing import NamedTuple


class BloodPalette(NamedTuple):
    floor: tuple
    wall: tuple
    bounce: tuple
    trail: tuple
    settled: tuple
    particles: tuple
    limb: tuple
    meat: tuple


_RED_BLOOD = BloodPalette(
    floor=((142, 14, 22, 230), (178, 20, 28, 240), (102, 10, 16, 220), (205, 24, 32, 235)),
    wall=((148, 12, 20, 240), (188, 18, 28, 245), (108, 8, 14, 235), (218, 24, 34, 240)),
    bounce=(152, 16, 24, 225),
    trail=((158, 16, 24, 220), (195, 22, 30, 230)),
    settled=(125, 12, 18, 220),
    particles=((185, 18, 26), (135, 12, 20), (225, 28, 36)),
    limb=((135, 34, 40), (112, 22, 28)),
    meat=((172, 22, 30), (140, 14, 22), (195, 32, 38)),
)
_GREEN_BLOOD = BloodPalette(
    floor=((31, 123, 22, 230), (42, 153, 28, 240), (24, 88, 16, 220), (48, 176, 32, 235)),
    wall=((33, 128, 20, 240), (44, 162, 28, 245), (25, 93, 14, 235), (50, 187, 34, 240)),
    bounce=(34, 132, 24, 225),
    trail=((37, 137, 24, 220), (45, 168, 30, 230)),
    settled=(29, 108, 18, 220),
    particles=((44, 160, 26), (32, 117, 20), (52, 194, 36)),
    limb=((45, 113, 40), (34, 97, 28)),
    meat=((40, 149, 30), (35, 121, 22), (50, 169, 38)),
)

BLOOD_PALETTES = {"red": _RED_BLOOD, "green": _GREEN_BLOOD}
