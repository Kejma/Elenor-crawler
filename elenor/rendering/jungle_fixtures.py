"""Pixel art for jungle route fixtures and persistent ceramic shards."""

import pygame

from elenor.entities.objects import JUNGLE_KEY_COLORS


def register_jungle_fixtures(assets, make_pair):
    for kind, direction in (("up", -1), ("down", 1)):
        diffuse, normals = make_pair(16, 16)
        pygame.draw.rect(diffuse, (26, 31, 31), (1, 1, 14, 14))
        pygame.draw.rect(diffuse, (139, 130, 101), (1, 1, 14, 14), 1)
        pygame.draw.rect(normals, (128, 128, 255), (1, 1, 14, 14))
        for y, length in ((4, 6), (7, 8), (10, 10)):
            pygame.draw.line(diffuse, (109 + y * 5, 101 + y * 4, 81 + y * 3),
                             (8 - length // 2, y), (7 + length // 2, y), 2)
            pygame.draw.line(normals, (128, 197, 210), (8 - length // 2, y), (7 + length // 2, y))
        point = 8 + direction * 4
        pygame.draw.polygon(diffuse, (241, 219, 147),
                            [(8, point), (5, point - direction * 4), (11, point - direction * 4)])
        assets[f"jungle_passage_{kind}"] = (diffuse, normals)

    for color, tint in JUNGLE_KEY_COLORS.items():
        diffuse, normals = make_pair(16, 16)
        pygame.draw.circle(diffuse, tint, (5, 7), 3, 2)
        pygame.draw.line(diffuse, tint, (7, 8), (13, 12), 2)
        pygame.draw.line(diffuse, tint, (11, 10), (11, 13), 2)
        pygame.draw.circle(normals, (128, 128, 255), (5, 7), 3, 2)
        pygame.draw.line(normals, (128, 128, 255), (7, 8), (13, 12), 2)
        pygame.draw.line(normals, (128, 128, 255), (11, 10), (11, 13), 2)
        assets[f"jungle_key_{color}"] = (diffuse, normals)

    diffuse, normals = make_pair(16, 16)
    for shade, points in (
        ((173, 97, 59), [(2, 8), (6, 6), (5, 11)]),
        ((222, 167, 112), [(9, 4), (13, 7), (8, 7)]),
        ((188, 117, 72), [(9, 10), (14, 9), (12, 13)]),
        ((129, 74, 55), [(5, 13), (8, 11), (7, 14)]),
    ):
        pygame.draw.polygon(diffuse, shade, points)
        pygame.draw.polygon(normals, (128, 171, 228), points)
    assets["ceramic_shards"] = (diffuse, normals)
