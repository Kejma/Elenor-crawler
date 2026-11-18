"""Enemy attacks for the jungle bestiary."""

from dataclasses import dataclass
import math
import random

from elenor.entities.effects import Projectile


@dataclass(frozen=True)
class Attack:
    form: str
    reach: float
    windup: float
    cooldown: float
    damage: float = 1.0
    radius: float = 0.64
    color: tuple[int, int, int] = (250, 144, 92)
    spread: tuple[float, ...] = (0.0,)


BITE = Attack("strike", 1.23, 0.14, 0.95)
QUICK = Attack("strike", 1.23, 0.10, 0.90, 0.85)
POUNCE = Attack("lunge", 2.45, 0.12, 1.65, 1.1, 0.68)
CRUSH = Attack("sweep", 1.65, 0.21, 1.65, 1.2, 1.65)
STOMP = Attack("sweep", 2.05, 0.30, 2.25, 1.2, 2.05)
DART = Attack("dart", 6.0, 0.52, 2.0, color=(235, 211, 137))
SPORES = Attack("spell", 4.8, 0.62, 2.5, 0.9, color=(185, 156, 235), spread=(-0.23, 0.23))
BOLT = Attack("spell", 6.0, 0.65, 2.2, color=(114, 225, 250))
FAN = Attack("spell", 6.4, 0.83, 3.25, 0.78, color=(164, 155, 250), spread=(-0.30, 0.0, 0.30))
SIGIL = Attack("sigil", 5.1, 0.89, 2.8, 1.14, 1.02, (179, 147, 254))
HEAL = Attack("heal", 5.0, 0.82, 4.4, color=(120, 239, 151))
ATTACKS = {
    "jungle_gremlin": (QUICK,),
    "jungle_viper": (BITE, POUNCE),
    "giant_wasp": (QUICK, POUNCE),
    "thorn_treant": (BITE, CRUSH),
    "swamp_lurker": (BITE, POUNCE),
    "myconid_shambler": (BITE, SPORES),
    "croc_warrior": (BITE, CRUSH),
    "croc_juggernaut": (POUNCE, STOMP),
    "tribal_warrior": (QUICK, CRUSH),
    "tribal_hunter": (QUICK, DART),
    "tribal_shaman": (BITE, BOLT, HEAL),
    "giant_scorpion": (QUICK, CRUSH),
    "rust_monster": (QUICK, POUNCE),
    "jade_scarab": (QUICK,),
    "cave_piercer": (BITE, CRUSH),
    "cave_angler": (BITE, POUNCE),
    "skull_spider": (QUICK, POUNCE),
    "bone_constrictor": (BITE, CRUSH),
    "bone_jaguar": (QUICK, POUNCE),
    "marble_golem": (BITE, STOMP),
    "vedalken_mage": (BITE, SIGIL),
    "vedalken_four_armed": (QUICK, BOLT, FAN),
    "vedalken_arbiter": (CRUSH, FAN, SIGIL),
    "ossuary_behemoth": (STOMP, FAN),
}
TRIBE = frozenset(("tribal_hunter", "tribal_warrior", "tribal_shaman"))
RANGED = frozenset(("dart", "spell", "sigil"))


def _in_ranged_band(attack, distance):
    minimum = 2.5 if len(attack.spread) > 1 else 1.55
    return minimum <= distance <= attack.reach


def _ally_to_heal(mob, allies, dungeon):
    return min(
        (
            other for other in allies
            if other is not mob and other.kind in TRIBE and 0 < other.hp < other.max_hp * 0.72
            and dungeon.has_line_of_sight(mob.x, mob.y, other.x, other.y, HEAL.reach)
        ),
        key=lambda other: other.hp / other.max_hp,
        default=None,
    )


def update_jungle_combat(mob, dt, player, dungeon, allies, projectiles, sfx, add_popup, on_hit):
    here, hero = (mob.x, mob.y), (player.x, player.y)
    distance = math.dist(here, hero)
    attacks = ATTACKS[mob.kind]
    if mob.jungle_dash:
        attack, point = mob.jungle_dash
        if _advance_lunge(mob, point, dt, dungeon, allies):
            mob.jungle_dash = None
            _release(mob, attack, (mob.x, mob.y), player, dungeon, allies, projectiles, sfx, add_popup, on_hit)
        return

    pending = mob.jungle_windup
    if pending:
        attack, target = pending
        mob.cast_windup_timer = max(0.0, mob.cast_windup_timer - dt)
        if mob.cast_windup_timer <= 0:
            mob.jungle_windup = None
            if attack.form == "lunge":
                mob.jungle_dash = (attack, target)
            else:
                _release(mob, attack, target, player, dungeon, allies, projectiles, sfx, add_popup, on_hit)
        return

    can_see = dungeon.has_line_of_sight(*here, *hero, max(a.reach for a in attacks) + 0.2)
    if mob.attack_cd <= 0.0:
        ally = _ally_to_heal(mob, allies, dungeon) if HEAL in attacks else None
        chosen = [
            move for move in attacks
            if move.form != "heal" and can_see and distance <= move.reach
            and (move.form != "lunge" or distance >= 1.45)
            and (move.form not in RANGED or _in_ranged_band(move, distance))
        ]
        if ally or chosen:
            attack = HEAL if ally else random.choice(chosen)
            point = here if attack.form == "sweep" else hero
            if attack.form == "lunge":
                stop = max(0.0, distance - 0.45) / max(0.001, distance)
                point = (here[0] + (hero[0] - here[0]) * stop, here[1] + (hero[1] - here[1]) * stop)
            mob.jungle_windup = (attack, ally or point)
            mob.cast_windup_max = mob.cast_windup_timer = attack.windup
            mob.attack_cd = attack.windup + attack.cooldown
            if attack.form in RANGED or ally:
                sfx.play_spatial("spell_windup", *here, *hero, dungeon, max_dist=9.0)
            elif distance > 0.001:
                mob.trigger_bump((here[0] - hero[0]) * 0.2, (here[1] - hero[1]) * 0.2)
            return

    can_shoot = any(a.form in RANGED and _in_ranged_band(a, distance) for a in attacks)
    if can_see and can_shoot:
        return
    if distance > 0.99:
        mob._follow_astar_path(*hero, dt, dungeon, allies)


def _release(mob, attack, target, player, dungeon, allies, projectiles, sfx, add_popup, on_hit):
    here, hero = (mob.x, mob.y), (player.x, player.y)
    if attack.form == "heal":
        ally = target
        if ally in allies and ally.hp > 0 and dungeon.has_line_of_sight(*here, ally.x, ally.y, attack.reach):
            amount = min(ally.max_hp - ally.hp, max(4, round(ally.max_hp * 0.25)))
            if amount:
                ally.hp += amount
                ally.glow_timer, ally.glow_color = 0.32, attack.color
                add_popup(ally.x, ally.y, f"+{amount}", attack.color)
                sfx.play_spatial("heal", ally.x, ally.y, *hero, dungeon, max_dist=10.0)
        return

    damage = max(1, round(random.randint(mob.dmg_min, mob.dmg_max) * attack.damage))
    if attack.form in ("spell", "dart"):
        angle = math.atan2(target[1] - here[1], target[0] - here[0])
        for spread in attack.spread:
            physical = attack.form == "dart"
            projectile = Projectile(
                *here, math.cos(angle + spread), math.sin(angle + spread),
                speed=7.5 if physical else 5.6, mag_dmg=damage, color=attack.color,
                from_player=False, is_weapon_proj=physical, emits_light=not physical,
                visual_kind="blowdart" if physical else "orb", max_dist=attack.reach + 0.8,
                source=mob,
            )
            projectiles.append(projectile)
        sfx.play_spatial("magic" if attack.form == "spell" else "skill_windup",
                         *here, *hero, dungeon, max_dist=11.0)
        return

    hit_radius = attack.radius + (0.14 if attack.form == "lunge" else 0)
    if attack.form == "sigil":
        mob.jungle_impact = (target, hit_radius, attack.color)
        mob.jungle_impact_timer = 0.22
    if math.dist(target, hero) <= hit_radius and dungeon.has_line_of_sight(*here, *hero, attack.reach + 0.18):
        mob.trigger_bump((hero[0] - here[0]) * 0.22, (hero[1] - here[1]) * 0.22)
        on_hit(damage, is_magic=attack.form == "sigil")


def _advance_lunge(mob, target, dt, dungeon, allies):
    """Consume this frame's movement in collision-tested steps."""
    travel = 11.0 * dt
    while travel > 0:
        dx, dy = target[0] - mob.x, target[1] - mob.y
        remaining = math.hypot(dx, dy)
        if remaining <= 0.10 or mob.root_timer > 0:
            return True
        step = min(0.16, travel, remaining)
        mob._step_with_collision(dx / remaining, dy / remaining, step / mob.speed, dungeon, allies)
        if math.dist((mob.x, mob.y), target) >= remaining - step * 0.15:
            return True
        travel -= step
    return math.dist((mob.x, mob.y), target) <= 0.10
