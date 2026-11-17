"""Physical ability targeting; every hit respects walls and physical armour."""

import math


def execute_physical(game, item, power, tx, ty, credit):
    px, py = game.player.x, game.player.y
    dx, dy = tx - px, ty - py
    length = math.hypot(dx, dy)
    nx, ny = (dx / length, dy / length) if length > 0.001 else (game.player.facing, 0)
    if item.shape == "area":
        distance = min(length, 6)
        cx, cy = px + nx * distance, py + ny * distance
        if not game.dungeon.has_line_of_sight(px, py, cx, cy, 6.1):
            game.player.cooldowns.pop(item.id, None)
            return
    else:
        cx, cy = px, py
    targets = []
    for mob in game.mobs:
        vx, vy = mob.x - px, mob.y - py
        dist = math.hypot(vx, vy)
        projection = vx * nx + vy * ny
        if mob.hp <= 0 or not game.dungeon.has_line_of_sight(px, py, mob.x, mob.y, 9):
            continue
        if item.shape == "area":
            hit = math.hypot(mob.x - cx, mob.y - cy) <= item.aoe_radius
        elif item.shape == "line":
            hit = 0 <= projection <= item.aoe_radius and abs(vx * ny - vy * nx) <= 0.45
        elif item.shape == "cone":
            hit = dist <= item.aoe_radius and projection >= dist * 0.5
        elif item.shape == "target":
            hit = dist <= item.aoe_radius and math.hypot(mob.x - tx, mob.y - ty) <= 1.5
        else:
            hit = dist <= item.aoe_radius
        if hit:
            targets.append(mob)
    if item.id == "throw_knife":
        targets = sorted(targets, key=lambda m: (m.x - px) * nx + (m.y - py) * ny)[:1]
    if item.shape == "target":
        targets = sorted(targets, key=lambda m: math.hypot(m.x - tx, m.y - ty))[:1]
    game.sfx.play("skill_windup")
    if item.shape == "line":
        game.visual_fx.append(
            dict(
                kind="beam",
                x0=px,
                y0=py - 0.22,
                x1=px + nx * item.aoe_radius,
                y1=py + ny * item.aoe_radius,
                color=item.color,
                timer=0.18,
                max_timer=0.18,
            )
        )
    else:
        game.visual_fx.append(
            dict(
                kind="aoe_ring",
                x=cx,
                y=cy,
                radius=item.aoe_radius,
                color=item.color,
                timer=0.25,
                max_timer=0.25,
            )
        )
    for mob in targets:
        mob.alert_to_combat(game.sfx, game.add_popup)
        damage = max(1, power - mob.phys_def)
        mob.hp -= damage
        mob.apply_knockback(nx, ny, item.knockback)
        if item.status:
            mob.apply_status(
                item.status, item.status_dur, game.add_popup, dmg_val=max(1, power // 4)
            )
        game.add_popup(mob.x, mob.y, f"-{damage}", item.color)
        game.record_combat_growth(mob, credit)
        game._check_mob_death(mob)
