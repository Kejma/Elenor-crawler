"""Physical actions, finite-speed throws and persistent single-use traps."""

import math
import random
from elenor.entities import Particle


def effects(game):
    if not hasattr(game, "physical_effects"):
        game.physical_effects = []
    return game.physical_effects


def _spawn_particles(game, wx, wy, count, colors, spd_range=(1.0, 3.0), size=2.6, life=0.28, base_vx=0.0, base_vy=0.0):
    plist = getattr(game, "particles", None)
    if not isinstance(plist, list):
        return
    for _ in range(count):
        ang = random.uniform(0.0, math.tau)
        spd = random.uniform(*spd_range)
        plist.append(
            Particle(
                wx + random.uniform(-0.12, 0.12),
                wy + random.uniform(-0.12, 0.12),
                base_vx + math.cos(ang) * spd,
                base_vy + math.sin(ang) * spd,
                random.choice(colors),
                size=size,
                life=life,
            )
        )


def hit(game, mob, item, power, credit, nx, ny):
    was_unaware = mob.state != "combat"
    mob.alert_to_combat(game.sfx, game.add_popup)
    weapon = game.player.equipment["right_hand"]
    damage = game._physical_hit_damage(mob, power, getattr(weapon, "armor_pierce", 0), was_unaware, credit)
    mob.hp -= damage
    if item.shape not in ("knife", "trap"):
        game._trigger_firm_stance()
    mob.apply_knockback(nx, ny, item.knockback)
    mob.apply_status(
        item.status, item.status_dur, game.add_popup, dmg_val=max(1, int(power) // 4)
    )
    mob.hit_flash_timer = 0.12
    fx = getattr(game, "fx", None)
    if fx is not None:
        fx.add_blood_splatter(mob.x, mob.y, count=4, is_kill=False)
    _spawn_particles(
        game,
        mob.x,
        mob.y - 0.25,
        7,
        [tuple(item.color), (255, 240, 190), (225, 70, 70)],
        spd_range=(1.2, 3.2),
        size=2.7,
        life=0.24,
        base_vx=nx * 1.2,
        base_vy=ny * 1.2,
    )
    game.add_popup(mob.x, mob.y, f"-{damage}", item.color)
    game.record_combat_growth(mob, credit)
    game._check_mob_death(mob, credit)


def move_step(game, nx, ny, distance):
    p = game.player
    moved = 0
    for _ in range(math.ceil(distance / 0.08)):
        step = min(0.08, distance - moved)
        x, y = p.x + nx * step, p.y + ny * step
        if any(
            game.dungeon.is_blocking_move(int(x + dx), int(y + dy))
            for dx in (-0.28, 0.28)
            for dy in (-0.28, 0.28)
        ):
            break
        p.x, p.y = x, y
        moved += step
    return moved


def execute_physical(game, item, power, tx, ty, credit):
    p = game.player
    dx, dy = tx - p.x, ty - p.y
    length = math.hypot(dx, dy)
    nx, ny = (dx / length, dy / length) if length > 0.001 else (p.facing, 0)
    shape = item.shape
    fx = getattr(game, "fx", None)
    state = dict(
        kind=shape,
        x=p.x,
        y=p.y,
        nx=nx,
        ny=ny,
        item=item,
        power=power,
        credit=credit,
        timer=0.3,
        max_timer=0.3,
    )
    if shape == "guard":
        p.guard_timer = item.duration
        state.update(timer=item.duration, max_timer=item.duration)
        _spawn_particles(
            game, p.x, p.y - 0.2, 12, [(245, 195, 80), (255, 240, 180), (200, 210, 225)], (0.8, 2.2), 2.6, 0.35, 0.0, -0.8
        )
    elif shape == "stealth":
        p.stealth_timer = item.duration
        for mob in game.mobs:
            if math.hypot(mob.x - p.x, mob.y - p.y) > 8:
                continue
            mob.state = "patrolling"
            mob.awareness = 0
            mob.path = []
        state.update(timer=item.duration, max_timer=item.duration)
        _spawn_particles(
            game, p.x, p.y - 0.2, 14, [(75, 95, 155), (110, 165, 215), (45, 50, 85)], (0.6, 2.0), 2.8, 0.38, 0.0, -0.6
        )
    elif shape in ("evade", "charge"):
        state.update(
            timer=0.22,
            max_timer=0.22,
            remaining=2 if shape == "evade" else item.aoe_radius,
            hits=set(),
        )
        if shape == "evade":
            p.evade_timer = item.duration
            _spawn_particles(
                game, p.x, p.y, 10, [(110, 235, 180), (210, 255, 235)], (1.0, 2.6), 2.4, 0.25, -nx * 1.5, -ny * 1.5
            )
        else:
            if fx is not None:
                fx.trigger_shake(1.4, 0.14)
            _spawn_particles(
                game, p.x, p.y, 12, [(245, 155, 65), (255, 225, 130)], (1.2, 3.0), 2.8, 0.28, -nx * 1.8, -ny * 1.8
            )
    elif shape == "trap":
        effects(game)[:] = [v for v in effects(game) if v["kind"] != "trap"]
        state.update(timer=item.duration, max_timer=item.duration, armed=0.4)
        _spawn_particles(game, p.x, p.y, 6, [(190, 200, 215), (110, 225, 165)], (0.5, 1.4), 2.2, 0.22)
    elif shape in ("knife", "flask"):
        state.update(
            timer=2,
            max_timer=2,
            remaining=min(6, length) if shape == "flask" else 7,
            speed=item.proj_speed,
            total_distance=min(6, length) if shape == "flask" else 7,
        )
    else:
        if item.id == "earth_slam":
            if fx is not None:
                fx.trigger_shake(2.2, 0.18)
                fx.add_scorch_mark(p.x + nx * 1.1, p.y + ny * 1.1, 0.65)
            _spawn_particles(
                game, p.x + nx * 1.2, p.y + ny * 1.2, 16, [(245, 140, 50), (255, 225, 120), (155, 125, 95)], (1.4, 3.6), 3.0, 0.34, nx * 1.5, ny * 1.5
            )
        elif shape == "sweep":
            if fx is not None:
                fx.trigger_shake(1.4, 0.12)
            _spawn_particles(game, p.x, p.y - 0.2, 16, [(245, 160, 70), (255, 235, 175)], (2.0, 4.0), 2.7, 0.24)
        elif shape == "target":
            if fx is not None:
                fx.trigger_shake(1.8, 0.15)
            _spawn_particles(
                game, p.x + nx * 1.1, p.y + ny * 1.1 - 0.2, 14, [(255, 180, 75), (255, 245, 195), (235, 85, 55)], (1.5, 3.5), 2.9, 0.26
            )
        elif shape == "execute":
            _spawn_particles(
                game, p.x + nx * 1.1, p.y + ny * 1.1 - 0.2, 12, [(235, 55, 75), (110, 240, 180), (255, 240, 240)], (1.5, 3.4), 2.6, 0.24
            )
        else:
            _spawn_particles(
                game, p.x + nx * 1.0, p.y + ny * 1.0 - 0.2, 12, [(245, 155, 65), (255, 235, 175)], (1.4, 3.2), 2.6, 0.22, nx * 1.2, ny * 1.2
            )

        targets = []
        for mob in game.mobs:
            vx, vy = mob.x - p.x, mob.y - p.y
            dist = math.hypot(vx, vy)
            if (
                mob.hp > 0
                and dist <= item.aoe_radius
                and game.dungeon.has_line_of_sight(
                    p.x, p.y, mob.x, mob.y, item.aoe_radius + 0.5
                )
                and (shape == "sweep" or vx * nx + vy * ny >= dist * 0.5)
            ):
                targets.append(mob)
        if shape in ("target", "execute"):
            targets = sorted(targets, key=lambda m: math.hypot(m.x - p.x, m.y - p.y))[
                :1
            ]
        for mob in targets:
            multiplier = 1.5 if shape == "execute" and mob.hp / mob.max_hp < 0.35 else 1
            hit(game, mob, item, power * multiplier, credit, nx, ny)
    effects(game).append(state)
    game.sfx.play("step" if shape in ("stealth", "trap", "evade") else "skill_windup")


def burst(game, state):
    item = state["item"]
    game.fx.add_gas_cloud(
        state["x"],
        state["y"],
        radius=item.aoe_radius,
        duration=item.duration,
        kind="poison",
        dmg=max(1, state["power"] // 3),
    )
    # Attribution is shared across every tick and target, including unrewarded ambushes.
    if (
        isinstance(getattr(game.fx, "active_clouds", None), list)
        and game.fx.active_clouds
    ):
        game.fx.active_clouds[-1]["growth_credit"] = state["credit"]
    _spawn_particles(
        game,
        state["x"],
        state["y"],
        16,
        [(95, 240, 115), (175, 255, 185), (215, 245, 255)],
        spd_range=(1.0, 3.4),
        size=2.7,
        life=0.34,
    )
    game.sfx.play("hit")


def update_physical(game, dt):
    if dt <= 0 or game.player.hp <= 0:
        return
    for state in list(effects(game)):
        state["timer"] -= dt
        kind = state["kind"]
        item = state["item"]
        if kind in ("knife", "flask"):
            travel = min(state["speed"] * dt, state["remaining"])
            for _ in range(math.ceil(travel / 0.08)):
                step = min(0.08, travel)
                travel -= step
                x, y = state["x"] + state["nx"] * step, state["y"] + state["ny"] * step
                if game.dungeon.is_blocking_projectile(int(x), int(y)):
                    state["timer"] = 0
                    if kind == "knife":
                        _spawn_particles(game, x, y, 6, [(210, 220, 235), (255, 225, 130)], (1.0, 2.6), 2.2, 0.2)
                    break
                state["x"], state["y"] = x, y
                state["remaining"] -= step
                if kind == "knife":
                    target = next(
                        (
                            m
                            for m in game.mobs
                            if m.hp > 0 and math.hypot(m.x - x, m.y - y) < 0.5
                        ),
                        None,
                    )
                    if target:
                        hit(
                            game,
                            target,
                            item,
                            state["power"],
                            state["credit"],
                            state["nx"],
                            state["ny"],
                        )
                        state["timer"] = 0
                        break
            if state["remaining"] <= 0.001:
                state["timer"] = 0
            if state["timer"] <= 0 and kind == "flask":
                burst(game, state)
        elif kind in ("charge", "evade"):
            moved = move_step(
                game, state["nx"], state["ny"], min(state["remaining"], 14 * dt)
            )
            state["remaining"] -= moved
            if kind == "charge":
                for mob in list(game.mobs):
                    if (
                        mob not in state["hits"]
                        and math.hypot(mob.x - game.player.x, mob.y - game.player.y) < 1
                        and game.dungeon.has_line_of_sight(
                            game.player.x, game.player.y, mob.x, mob.y, 1.5
                        )
                    ):
                        state["hits"].add(mob)
                        hit(
                            game,
                            mob,
                            item,
                            state["power"],
                            state["credit"],
                            state["nx"],
                            state["ny"],
                        )
            if moved == 0 or state["remaining"] <= 0.001:
                state["timer"] = 0
        elif kind == "trap":
            state["armed"] -= dt
            if state["armed"] <= 0:
                target = next(
                    (
                        m
                        for m in game.mobs
                        if m.hp > 0
                        and math.hypot(m.x - state["x"], m.y - state["y"]) < 0.65
                    ),
                    None,
                )
                if target:
                    _spawn_particles(
                        game, state["x"], state["y"], 12, [(220, 230, 245), (95, 240, 135), (235, 70, 70)], (1.2, 3.0), 2.6, 0.28
                    )
                    hit(game, target, item, state["power"], state["credit"], 0, 0)
                    state["timer"] = 0
        if state["timer"] <= 0:
            effects(game).remove(state)
