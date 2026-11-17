"""Merchant's walnut counter, jewel display, stocked shelves and scales sign."""

import pygame
from elenor.rendering.normals import quantize_normal_surface


def register_merchant_assets(assets):
    for kind in (
        "merchant_counter",
        "merchant_shelves",
        "merchant_goods",
        "merchant_sign",
    ):
        diffuse = pygame.Surface((16, 20), pygame.SRCALPHA)
        normal = pygame.Surface((16, 20), pygame.SRCALPHA)

        def rect(color, box, n=(128, 128, 255)):
            pygame.draw.rect(diffuse, color, box)
            pygame.draw.rect(normal, n, box)

        def line(color, start, end, n=(128, 218, 200)):
            pygame.draw.line(diffuse, color, start, end)
            pygame.draw.line(normal, n, start, end)

        wood, dark, gold = (110, 67, 37), (54, 33, 27), (220, 174, 76)
        if kind == "merchant_counter":
            rect(dark, (0, 9, 16, 10))
            rect(wood, (1, 11, 14, 7), (128, 38, 200))
            rect((154, 103, 57), (0, 7, 16, 5))
            line(gold, (0, 12), (15, 12))
            for x in (2, 13):
                rect(gold, (x, 15, 1, 2))
            rect((206, 189, 137), (3, 8, 6, 2))  # ledger
            rect(gold, (11, 8, 3, 2))
        elif kind == "merchant_shelves":
            rect(dark, (1, 1, 14, 18))
            for y in (6, 12, 18):
                rect(wood, (1, y, 14, 2))
            for x, color in (
                (3, (95, 155, 185)),
                (7, (160, 65, 70)),
                (11, (105, 155, 95)),
            ):
                rect(color, (x, 8, 2, 4))
                rect(gold, (x, 7, 2, 1))
                rect((161, 123, 75), (x, 3, 2, 3))
            rect((164, 134, 95), (4, 14, 8, 4))
        elif kind == "merchant_goods":
            rect(dark, (1, 8, 14, 11))
            rect((89, 52, 80), (2, 9, 12, 6))
            for x, color in (
                (4, (95, 220, 155)),
                (8, (235, 85, 95)),
                (12, (110, 180, 245)),
            ):
                rect(color, (x - 1, 10, 2, 3))
                rect((240, 240, 230), (x - 1, 10, 1, 1))
            line(gold, (1, 8), (14, 8))
            line(gold, (1, 15), (14, 15))
        else:
            rect(wood, (0, 0, 16, 2))
            line(gold, (4, 2), (4, 5))
            line(gold, (12, 2), (12, 5))
            rect(dark, (1, 5, 14, 12))
            line(gold, (8, 7), (8, 14))
            line(gold, (4, 9), (12, 9))
            for x in (4, 12):
                line(gold, (x, 9), (x - 2, 12))
                line(gold, (x, 9), (x + 2, 12))
                line(gold, (x - 2, 12), (x + 2, 12))
            line(gold, (5, 15), (11, 15))
        quantize_normal_surface(normal, diffuse)
        assets[kind] = (diffuse, normal)
