"""Show an enemy's committed attack where it will land."""

import math

from elenor.config import SCALE, TILE_W, TILE_H
from elenor.rendering.visibility import overlay_visibility
from elenor.rendering.pixel_fx import PixelLayer


def render_jungle_attacks(screen, mobs, cam_x, cam_y, fov, lights, cache, *, layer=None):
    own_layer = layer is None
    if own_layer:
        layer = cache.get("_jungle_attack_layer")
        if layer is None:
            layer = cache["_jungle_attack_layer"] = PixelLayer()

    def pixel(x, y):
        return round((x * TILE_W - cam_x) * SCALE), round((y * TILE_H - cam_y) * SCALE)

    for mob in mobs:
        if mob.jungle_impact_timer > 0.0:
            (x, y), radius, color = mob.jungle_impact
            alpha = round(195 * mob.jungle_impact_timer / 0.22)
            layer.broken_ring((*color, alpha), pixel(x, y), round(radius * TILE_W * SCALE))
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
            layer.line((*color, 100), start, end, 2)
            layer.circle((*color, 205), end, 19 + round(6 * progress), 3)
            continue

        if attack.form in ("spell", "dart"):
            angle = math.atan2(target[1] - mob.y, target[0] - mob.x)
            for spread in attack.spread:
                end = pixel(mob.x + math.cos(angle + spread) * attack.reach,
                            mob.y + math.sin(angle + spread) * attack.reach)
                for tick in range(2, 13):
                    weight = tick / 12
                    dx = start[0] + (end[0] - start[0]) * weight
                    dy = start[1] + (end[1] - start[1]) * weight
                    layer.rect((*color, 100 + round(70 * progress)), (dx, dy, SCALE, SCALE))
            layer.circle((*color, 210), (start[0], start[1] - 23), 7 + round(6 * progress), 3)
            continue

        end = pixel(*target)
        radius = round(attack.radius * TILE_W * SCALE)
        layer.circle((*color, 25 + round(29 * progress)), end, radius)
        layer.circle((*color, 190), end, radius, 2)
        layer.arc((*color, 255), (end[0] - radius, end[1] - radius, 2 * radius, 2 * radius),
                        math.pi / 2, math.pi / 2 + progress * math.tau, 4)

    if own_layer:
        layer.flush(screen, overlay_visibility(fov, lights, cam_x, cam_y))
