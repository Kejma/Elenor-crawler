"""Show an enemy's committed attack where it will land."""

import math
import pygame

from elenor.config import SCALE, TILE_W, TILE_H, VIEW_W, VIEW_H
from elenor.rendering.visibility import mask_overlay, overlay_visibility


def render_jungle_attacks(screen, mobs, cam_x, cam_y, fov, lights, cache):
    layer = cache.get("_jungle_attack_layer")
    if layer is None:
        layer = pygame.Surface((VIEW_W * SCALE, VIEW_H * SCALE), pygame.SRCALPHA)
        cache["_jungle_attack_layer"] = layer
    layer.fill((0, 0, 0, 0))

    def pixel(x, y):
        return round((x * TILE_W - cam_x) * SCALE), round((y * TILE_H - cam_y) * SCALE)

    for mob in mobs:
        if mob.jungle_impact_timer > 0.0:
            (x, y), radius, color = mob.jungle_impact
            alpha = round(195 * mob.jungle_impact_timer / 0.22)
            pygame.draw.circle(layer, (*color, alpha), pixel(x, y), round(radius * TILE_W * SCALE), 4)
        if not mob.jungle_windup:
            continue
        attack, target = mob.jungle_windup
        if attack.form in ("strike", "sweep", "lunge"):
            continue
        progress = 1.0 - mob.cast_windup_timer / attack.windup
        color = attack.color
        start = pixel(mob.x, mob.y)
        if attack.form == "heal":
            end = pixel(target.x, target.y)
            pygame.draw.line(layer, (*color, 100), start, end, 2)
            pygame.draw.circle(layer, (*color, 205), end, 19 + round(6 * progress), 3)
            continue

        if attack.form in ("spell", "dart"):
            angle = math.atan2(target[1] - mob.y, target[0] - mob.x)
            for spread in attack.spread:
                end = pixel(mob.x + math.cos(angle + spread) * attack.reach,
                            mob.y + math.sin(angle + spread) * attack.reach)
                pygame.draw.line(layer, (*color, 95 + round(70 * progress)), start, end, 2)
            pygame.draw.circle(layer, (*color, 210), (start[0], start[1] - 23), 7 + round(6 * progress), 3)
            continue

        end = pixel(*target)
        radius = round(attack.radius * TILE_W * SCALE)
        pygame.draw.circle(layer, (*color, 25 + round(29 * progress)), end, radius)
        pygame.draw.circle(layer, (*color, 190), end, radius, 2)
        pygame.draw.arc(layer, (*color, 255), (end[0] - radius, end[1] - radius, 2 * radius, 2 * radius),
                        math.pi / 2, math.pi / 2 + progress * math.tau, 4)

    mask_overlay(layer, overlay_visibility(fov, lights, cam_x, cam_y), cache)
    screen.blit(layer, (0, 0))
