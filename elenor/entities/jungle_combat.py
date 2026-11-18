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


BITE = Attack("strike", 1.18, 0.42, 1.25)
QUICK = Attack("strike", 1.18, 0.28, 1.25, 0.85)
POUNCE = Attack("lunge", 2.45, 0.57, 2.1, 1.1, 0.68)
CRUSH = Attack("sweep", 1.65, 0.73, 2.2, 1.2, 1.65)
STOMP = Attack("sweep", 2.05, 0.94, 2.8, 1.2, 2.05)
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
WARDEN_LEASH = 9


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
    pending = mob.jungle_windup
    if pending:
        attack, target = pending
        mob.cast_windup_timer = max(0.0, mob.cast_windup_timer - dt)
        if mob.cast_windup_timer <= 0:
            mob.jungle_windup = None
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
            if distance <= 9.0:
                sfx.play_spatial("spell_windup" if attack.form in RANGED or ally else "skill_windup",
                                 *here, *hero, dungeon, max_dist=9.0)
            return

    can_shoot = any(a.form in RANGED and _in_ranged_band(a, distance) for a in attacks)
    if can_see and can_shoot and distance > 2.0:
        return
    if can_see and mob.is_ranged and distance < 1.65 and mob.attack_cd > 0.3:
        mob._step_with_collision((here[0] - hero[0]) / max(distance, .01),
                                 (here[1] - hero[1]) / max(distance, .01), dt * .7, dungeon, allies)
    elif distance > 0.9:
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

    if attack.form == "lunge":
        distance = math.dist(here, target)
        steps = max(1, math.ceil(distance / 0.2))
        for _ in range(steps):
            old = (mob.x, mob.y)
            dx, dy = target[0] - mob.x, target[1] - mob.y
            remaining = math.hypot(dx, dy)
            if remaining <= 0.17:
                break
            mob._step_with_collision(dx / remaining, dy / remaining, min(0.2, remaining) / mob.speed, dungeon, allies)
            if math.dist(old, (mob.x, mob.y)) < 0.01:
                break
        here = (mob.x, mob.y)
        target = here
        hit_radius = attack.radius + 0.14
    else:
        hit_radius = attack.radius
    if attack.form in ("sigil", "sweep"):
        mob.jungle_impact = (target, hit_radius, attack.color)
        mob.jungle_impact_timer = 0.22
    if math.dist(target, hero) <= hit_radius and dungeon.has_line_of_sight(*here, *hero, attack.reach + 0.18):
        mob.trigger_bump((hero[0] - here[0]) * 0.22, (hero[1] - here[1]) * 0.22)
        on_hit(damage, is_magic=attack.form == "sigil")
