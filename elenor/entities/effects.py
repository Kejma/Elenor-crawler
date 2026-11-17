import math
import random




class Particle:
    def __init__(self, wx, wy, vx, vy, color, size=2.5, life=0.45):
        self.wx = wx
        self.wy = wy
        self.vx = vx
        self.vy = vy
        self.color = color
        self.size = size
        self.life = life
        self.max_life = life

    def update(self, dt):
        self.wx += self.vx * dt
        self.wy += self.vy * dt
        self.life -= dt
        return self.life > 0


class Projectile:
    def __init__(
        self, wx, wy, dir_x, dir_y, speed, mag_dmg, color,
        from_player=True, status=None, status_dur=0.0, knockback=0.0,
        visual_kind="orb", emits_light=True, is_weapon_proj=False,
        armor_pierce=0, shatter_armor=0, bounces=0, crit_chance=0.0,
        status_chance=1.0, life_steal=0, max_dist=None
    ):
        self.wx = wx
        self.wy = wy
        self.speed = speed
        self.vx = dir_x * speed
        self.vy = dir_y * speed
        self.mag_dmg = mag_dmg
        self.color = color
        self.from_player = from_player
        self.status = status
        self.status_dur = status_dur
        self.status_chance = status_chance
        self.knockback = knockback
        self.visual_kind = visual_kind
        self.emits_light = emits_light
        self.is_weapon_proj = is_weapon_proj
        self.armor_pierce = armor_pierce
        self.shatter_armor = shatter_armor
        self.bounces = bounces
        self.crit_chance = crit_chance
        self.life_steal = life_steal
        self.hit_mobs = set()
        self.angle = math.atan2(dir_y, dir_x)
        self.life = (max_dist / max(1.0, speed)) if max_dist else 4.5
        self.spawn_timer = 0.0

    def update(self, dt, dungeon, particles):
        self.wx += self.vx * dt
        self.wy += self.vy * dt
        self.life -= dt
        self.spawn_timer += dt

        spinning_kinds = ("spinning_dagger", "thrown_axe", "thrown_chakram", "thrown_bolas")
        physical_kinds = spinning_kinds + ("thrown_javelin", "sling_stone")

        if self.visual_kind in spinning_kinds:
            self.angle += 24.0 * dt
        elif self.visual_kind in ("thrown_javelin", "sling_stone"):
            self.angle = math.atan2(self.vy, self.vx)
        elif self.spawn_timer >= 0.025:
            self.spawn_timer = 0.0
            for _ in range(2):
                ang = random.uniform(0, 6.28)
                spd = random.uniform(0.4, 1.6)
                particles.append(Particle(
                    self.wx, self.wy,
                    math.cos(ang) * spd - self.vx * 0.15,
                    math.sin(ang) * spd - self.vy * 0.15,
                    self.color, size=random.uniform(2.0, 3.5), life=random.uniform(0.2, 0.4)
                ))

        tx, ty = int(self.wx), int(self.wy)
        if dungeon.is_blocking_move(tx, ty):
            spark_col = (200, 205, 215) if self.visual_kind in physical_kinds else self.color
            spark_cnt = 5 if self.visual_kind in physical_kinds else 10
            for _ in range(spark_cnt):
                ang = random.uniform(0, 6.28)
                spd = random.uniform(1.0, 3.2)
                particles.append(Particle(self.wx, self.wy, math.cos(ang) * spd, math.sin(ang) * spd, spark_col, 2.5, 0.25))
            return False

        return self.life > 0


class FloatingPopup:
    def __init__(self, world_x, world_y, text, color, icon=None, big=False):
        self.wx = world_x + random.uniform(-0.15, 0.15)
        self.wy = world_y - 0.35
        self.text = text
        self.color = color
        self.icon = icon
        self.big = big
        self.timer = 0.0
        self.duration = 1.05 if big else 0.90

    def update(self, dt):
        self.timer += dt
        self.wy -= 0.9 * dt
        return self.timer < self.duration
