"""Directional weapon motion, thrown objects, traps and timed stances."""

import math
import pygame
from elenor.config import TILE_W, TILE_H, VIEW_W, VIEW_H, SCALE
from elenor.rendering.visibility import mask_overlay


def render_physical(screen, game, cam_x, cam_y, visibility):
    states = getattr(game, "physical_effects", [])
    if not states:
        return
    surface = getattr(game, "_physical_surface", None)
    if surface is None:
        surface = pygame.Surface((VIEW_W * SCALE, VIEW_H * SCALE), pygame.SRCALPHA)
        game._physical_surface = surface
    surface.fill((0, 0, 0, 0))

    def point(x, y):
        return (int((x * TILE_W - cam_x) * SCALE), int((y * TILE_H - cam_y) * SCALE))

    for state in states:
        kind = state["kind"]
        item = state["item"]
        progress = 1 - state["timer"] / state["max_timer"]
        x, y = state["x"], state["y"]
        angle = math.atan2(state["ny"], state["nx"])
        if kind in ("guard", "stealth", "evade", "charge"):
            x, y = game.player.x, game.player.y
        cx, cy = point(x, y - 0.2)
        color = (*item.color, 210)
        if kind == "knife":
            dx, dy = state["nx"] * 15, state["ny"] * 15
            pygame.draw.line(
                surface, (225, 225, 235, 255), (cx - dx, cy - dy), (cx + dx, cy + dy), 4
            )
            pygame.draw.line(
                surface,
                (135, 85, 45, 255),
                (cx - dx, cy - dy),
                (cx - dx * 1.6, cy - dy * 1.6),
                5,
            )
        elif kind == "flask":
            cy -= int(
                18
                * math.sin(
                    (
                        1
                        - state["remaining"]
                        / max(0.001, state.get("total_distance", 6))
                    )
                    * math.pi
                )
            )
            pygame.draw.circle(surface, (100, 215, 100, 230), (cx, cy), 8)
            pygame.draw.rect(surface, (185, 145, 85, 255), (cx - 3, cy - 12, 6, 6))
        elif kind == "trap":
            pygame.draw.arc(
                surface, (175, 180, 190, 255), (cx - 15, cy - 8, 30, 16), 0, math.pi, 3
            )
            for offset in (-12, -6, 0, 6, 12):
                pygame.draw.line(
                    surface,
                    (210, 210, 215, 255),
                    (cx + offset, cy),
                    (cx + offset, cy - 6),
                    2,
                )
        elif kind == "guard":
            pygame.draw.polygon(
                surface,
                (225, 190, 110, 190),
                [
                    (cx - 22, cy - 30),
                    (cx + 22, cy - 30),
                    (cx + 18, cy + 7),
                    (cx, cy + 25),
                    (cx - 18, cy + 7),
                ],
                3,
            )
        elif kind == "stealth":
            pygame.draw.arc(
                surface,
                (105, 145, 190, 140),
                (cx - 23, cy - 40, 46, 64),
                0.2,
                math.pi - 0.2,
                4,
            )
            pygame.draw.line(
                surface, (105, 145, 190, 150), (cx - 22, cy + 17), (cx + 22, cy + 17), 2
            )
        elif kind in ("charge", "evade"):
            for offset in (12, 24, 36):
                pygame.draw.line(
                    surface,
                    color,
                    (cx - state["nx"] * offset - 5, cy - state["ny"] * offset),
                    (cx - state["nx"] * offset + 5, cy - state["ny"] * offset),
                    3,
                )
        elif item.id == "earth_slam":
            for side in (-0.4, 0, 0.4):
                points = [(cx, cy)]
                for step in range(1, 6):
                    a = angle + side + (0.08 if step % 2 else -0.08)
                    points.append(
                        (
                            cx + math.cos(a) * step * 23 * progress,
                            cy + math.sin(a) * step * 23 * progress,
                        )
                    )
                pygame.draw.lines(surface, color, False, points, 3)
        elif kind in ("target", "execute"):
            reach = 28 + 60 * progress
            end = (cx + math.cos(angle) * reach, cy + math.sin(angle) * reach)
            pygame.draw.line(
                surface, color, (cx, cy), end, 8 if kind == "target" else 3
            )
            pygame.draw.circle(
                surface,
                (255, 230, 170, 180),
                (int(end[0]), int(end[1])),
                8 if kind == "target" else 3,
            )
        else:
            radius = int(item.aoe_radius * TILE_W * SCALE)
            span = math.tau if kind == "sweep" else math.pi * 0.65
            start = angle - span * 0.5
            points = [
                (
                    cx + math.cos(start + span * progress * t / 12) * radius,
                    cy + math.sin(start + span * progress * t / 12) * radius,
                )
                for t in range(13)
            ]
            pygame.draw.lines(surface, color, False, points, 4)
    mask_overlay(surface, visibility, game.__dict__)
    screen.blit(surface, (0, 0))
