import math
import random


from elenor.audio.voices import choose_voice, next_call_delay
from elenor.data.blood import choose_blood_color
from elenor.entities.effects import Projectile
from elenor.entities.jungle_combat import ATTACKS, TRIBE, update_jungle_combat


MOB_PROFILES = {
    "rat": {
        "sprite": "rat", "hp": 15, "speed": 3.20, "dmg_min": 4, "dmg_max": 7,
        "phys_def": 1, "mag_def": 0, "detect_range": 5.2, "perception": 1.05,
        "is_ranged": False, "is_boss": False, "size_tiles": 1, "xp": 14,
    },
    "rat_cultist": {
        "sprite": "rat_cultist", "hp": 28, "speed": 2.65, "dmg_min": 6, "dmg_max": 10,
        "phys_def": 2, "mag_def": 3, "detect_range": 6.4, "perception": 1.15,
        "is_ranged": True, "proj_color": (235, 50, 70), "is_boss": False, "size_tiles": 1, "xp": 24,
    },
    "rat_king": {
        "sprite": "rat_king", "hp": 240, "speed": 2.35, "dmg_min": 11, "dmg_max": 16,
        "phys_def": 5, "mag_def": 5, "detect_range": 8.5, "perception": 1.45,
        "is_ranged": True, "proj_color": (255, 40, 60), "is_boss": True, "size_tiles": 2, "xp": 160,
    },
    "wolf": {
        "sprite": "wolf", "hp": 14, "speed": 2.95, "dmg_min": 3, "dmg_max": 6,
        "phys_def": 0, "mag_def": 0, "detect_range": 5.2, "perception": 1.05,
        "is_ranged": False, "is_boss": False, "size_tiles": 1, "xp": 12,
    },
    "skeleton": {
        "sprite": "skeleton", "hp": 22, "speed": 2.50, "dmg_min": 5, "dmg_max": 8,
        "phys_def": 2, "mag_def": 0, "detect_range": 5.2, "perception": 0.95,
        "is_ranged": False, "is_boss": False, "size_tiles": 1, "xp": 16,
    },
    "cultist": {
        "sprite": "cultist", "hp": 20, "speed": 2.30, "dmg_min": 5, "dmg_max": 9,
        "phys_def": 1, "mag_def": 3, "detect_range": 6.0, "perception": 1.10,
        "is_ranged": True, "proj_color": (215, 75, 255), "is_boss": False, "size_tiles": 1, "xp": 18,
    },
    "necromancer": {
        "sprite": "necromancer", "hp": 28, "speed": 2.00, "dmg_min": 6, "dmg_max": 10,
        "phys_def": 2, "mag_def": 5, "detect_range": 6.5, "perception": 1.20,
        "is_ranged": True, "proj_color": (85, 255, 130), "is_boss": False, "size_tiles": 1, "xp": 26,
    },
    "brute": {
        "sprite": "brute", "hp": 36, "speed": 1.85, "dmg_min": 7, "dmg_max": 11,
        "phys_def": 4, "mag_def": 1, "detect_range": 4.8, "perception": 0.85,
        "is_ranged": False, "is_boss": False, "size_tiles": 1, "xp": 24,
    },
    "tribal_warrior": {
        "sprite": "tribal_warrior", "hp": 26, "speed": 2.85, "dmg_min": 6, "dmg_max": 10,
        "phys_def": 2, "mag_def": 1, "detect_range": 5.8, "perception": 1.10,
        "is_ranged": False, "is_boss": False, "size_tiles": 1, "xp": 20,
    },
    "tribal_hunter": {
        "sprite": "tribal_hunter", "hp": 20, "speed": 3.05, "dmg_min": 5, "dmg_max": 9,
        "phys_def": 1, "mag_def": 1, "detect_range": 6.8, "perception": 1.25,
        "is_ranged": True, "proj_color": (95, 245, 125), "is_boss": False, "size_tiles": 1, "xp": 22,
    },
    "tribal_shaman": {
        "sprite": "tribal_shaman", "hp": 28, "speed": 2.35, "dmg_min": 7, "dmg_max": 12,
        "phys_def": 1, "mag_def": 4, "detect_range": 6.5, "perception": 1.20,
        "is_ranged": True, "proj_color": (85, 250, 165), "is_boss": False, "size_tiles": 1, "xp": 28,
    },
    "croc_warrior": {
        "sprite": "croc_warrior", "hp": 42, "speed": 2.25, "dmg_min": 8, "dmg_max": 13,
        "phys_def": 4, "mag_def": 2, "detect_range": 5.2, "perception": 0.95,
        "is_ranged": False, "is_boss": False, "size_tiles": 1, "xp": 30,
    },
    "croc_juggernaut": {
        "sprite": "croc_juggernaut", "hp": 185, "speed": 2.10, "dmg_min": 13, "dmg_max": 19,
        "phys_def": 6, "mag_def": 3, "detect_range": 7.2, "perception": 1.15,
        "is_ranged": False, "is_boss": True, "size_tiles": 2, "xp": 135,
    },
    "vedalken_mage": {
        "blood_color": "vedalken",
        "sprite": "vedalken_mage", "hp": 26, "speed": 2.40, "dmg_min": 7, "dmg_max": 12,
        "phys_def": 2, "mag_def": 5, "detect_range": 6.8, "perception": 1.25,
        "is_ranged": True, "proj_color": (110, 235, 255), "is_boss": False, "size_tiles": 1, "xp": 28,
    },
    "vedalken_four_armed": {
        "blood_color": "vedalken",
        "sprite": "vedalken_four_armed", "hp": 36, "speed": 2.60, "dmg_min": 9, "dmg_max": 14,
        "phys_def": 3, "mag_def": 6, "detect_range": 7.0, "perception": 1.30,
        "is_ranged": True, "proj_color": (185, 115, 255), "is_boss": False, "size_tiles": 1, "xp": 36,
    },
    "vedalken_arbiter": {
        "blood_color": "vedalken",
        "sprite": "vedalken_arbiter", "hp": 280, "speed": 2.30, "dmg_min": 13, "dmg_max": 19,
        "phys_def": 5, "mag_def": 8, "detect_range": 8.8, "perception": 1.50,
        "is_ranged": True, "proj_color": (115, 245, 255), "is_boss": True, "size_tiles": 2, "xp": 190,
    },
    "swamp_lurker": {
        "sprite": "swamp_lurker", "hp": 30, "speed": 2.30, "dmg_min": 6, "dmg_max": 10,
        "phys_def": 3, "mag_def": 2, "detect_range": 5.0, "perception": 0.95,
        "is_ranged": False, "is_boss": False, "size_tiles": 1, "xp": 22,
    },
    "jungle_gremlin": {
        "blood_color": "green",
        "sprite": "jungle_gremlin", "hp": 16, "speed": 3.45, "dmg_min": 4, "dmg_max": 8,
        "phys_def": 1, "mag_def": 1, "detect_range": 6.0, "perception": 1.25,
        "is_ranged": False, "is_boss": False, "size_tiles": 1, "xp": 16,
    },
    "jungle_viper": {
        "sprite": "jungle_viper", "hp": 18, "speed": 3.25, "dmg_min": 5, "dmg_max": 9,
        "phys_def": 1, "mag_def": 1, "detect_range": 5.5, "perception": 1.15,
        "is_ranged": False, "is_boss": False, "size_tiles": 1, "xp": 18,
    },
    "giant_scorpion": {
        "sprite": "giant_scorpion", "hp": 32, "speed": 2.55, "dmg_min": 7, "dmg_max": 12,
        "phys_def": 4, "mag_def": 1, "detect_range": 5.2, "perception": 1.00,
        "is_ranged": False, "is_boss": False, "size_tiles": 1, "xp": 26,
    },
    "myconid_shambler": {
        "sprite": "myconid_shambler", "hp": 34, "speed": 1.95, "dmg_min": 6, "dmg_max": 11,
        "phys_def": 2, "mag_def": 4, "detect_range": 5.4, "perception": 1.00,
        "is_ranged": True, "proj_color": (195, 115, 255), "is_boss": False, "size_tiles": 1, "xp": 25,
    },
    "thorn_treant": {
        "sprite": "thorn_treant", "hp": 44, "speed": 1.80, "dmg_min": 8, "dmg_max": 13,
        "phys_def": 5, "mag_def": 3, "detect_range": 4.8, "perception": 0.90,
        "is_ranged": False, "is_boss": False, "size_tiles": 1, "xp": 30,
    },
    "giant_wasp": {
        "sprite": "giant_wasp", "hp": 18, "speed": 3.60, "dmg_min": 5, "dmg_max": 9,
        "phys_def": 1, "mag_def": 1, "detect_range": 6.4, "perception": 1.20,
        "is_ranged": False, "is_boss": False, "size_tiles": 1, "xp": 20,
    },
    "rust_monster": {
        "sprite": "rust_monster", "hp": 30, "speed": 2.75, "dmg_min": 6, "dmg_max": 10,
        "phys_def": 4, "mag_def": 2, "detect_range": 5.8, "perception": 1.15,
        "is_ranged": False, "is_boss": False, "size_tiles": 1, "xp": 26,
    },
    "cave_piercer": {
        "sprite": "cave_piercer", "hp": 28, "speed": 1.65, "dmg_min": 9, "dmg_max": 15,
        "phys_def": 5, "mag_def": 1, "detect_range": 4.5, "perception": 0.90,
        "is_ranged": False, "is_boss": False, "size_tiles": 1, "xp": 24,
    },
    "cave_angler": {
        "sprite": "cave_angler", "hp": 34, "speed": 2.50, "dmg_min": 8, "dmg_max": 13,
        "phys_def": 3, "mag_def": 2, "detect_range": 6.2, "perception": 1.20,
        "is_ranged": False, "is_boss": False, "size_tiles": 1, "xp": 28,
    },
    "marble_golem": {
        "sprite": "marble_golem", "hp": 52, "speed": 1.85, "dmg_min": 9, "dmg_max": 15,
        "phys_def": 6, "mag_def": 4, "detect_range": 5.0, "perception": 0.95,
        "is_ranged": False, "is_boss": False, "size_tiles": 1, "xp": 36,
    },
    "jade_scarab": {
        "sprite": "jade_scarab", "hp": 22, "speed": 3.15, "dmg_min": 5, "dmg_max": 9,
        "phys_def": 4, "mag_def": 3, "detect_range": 5.6, "perception": 1.05,
        "is_ranged": False, "is_boss": False, "size_tiles": 1, "xp": 22,
    },
    "skull_spider": {
        "sprite": "skull_spider", "hp": 26, "speed": 3.10, "dmg_min": 6, "dmg_max": 11,
        "phys_def": 3, "mag_def": 2, "detect_range": 6.0, "perception": 1.15,
        "is_ranged": False, "is_boss": False, "size_tiles": 1, "xp": 24,
    },
    "bone_jaguar": {
        "sprite": "bone_jaguar", "hp": 32, "speed": 3.50, "dmg_min": 8, "dmg_max": 13,
        "phys_def": 2, "mag_def": 2, "detect_range": 6.6, "perception": 1.30,
        "is_ranged": False, "is_boss": False, "size_tiles": 1, "xp": 28,
    },
    "bone_constrictor": {
        "sprite": "bone_constrictor", "hp": 34, "speed": 2.65, "dmg_min": 7, "dmg_max": 12,
        "phys_def": 3, "mag_def": 2, "detect_range": 5.6, "perception": 1.10,
        "is_ranged": False, "is_boss": False, "size_tiles": 1, "xp": 26,
    },
    "ossuary_behemoth": {
        "sprite": "ossuary_behemoth", "hp": 260, "speed": 2.15, "dmg_min": 14, "dmg_max": 20,
        "phys_def": 6, "mag_def": 5, "detect_range": 8.5, "perception": 1.40,
        "is_ranged": True, "proj_color": (95, 250, 135), "is_boss": True, "size_tiles": 2, "xp": 180,
    },
}


class Enemy:
    def __init__(self, x, y, kind="rat", state="patrolling", chat_lines=None):
        self.x = float(x) + 0.5
        self.y = float(y) + 0.5
        self.bump_x = 0.0
        self.bump_y = 0.0
        self.kind = kind
        self.state = state

        prof = MOB_PROFILES.get(kind, MOB_PROFILES["rat"])
        self.sprite = prof["sprite"]
        self.blood_color = choose_blood_color(prof.get("blood_color", "red"))
        self.max_hp = round(prof["hp"] * (1.06 if prof.get("is_boss") else 1.16))
        self.hp = self.max_hp
        self.speed = prof["speed"]
        self.dmg_min = prof["dmg_min"]
        self.dmg_max = prof["dmg_max"]
        self.phys_def = prof["phys_def"]
        self.mag_def = prof["mag_def"]
        self.detect_range = prof["detect_range"]
        self.perception = prof["perception"]
        self.is_ranged = prof["is_ranged"]
        self.proj_color = prof.get("proj_color", (215, 75, 255))
        self.is_boss = prof.get("is_boss", False)
        self.size_tiles = prof.get("size_tiles", 2 if self.is_boss else 1)
        self.xp_value = prof["xp"]

        self.awareness = 0.0
        self.facing = -1
        self.alert_bang_timer = 0.0
        self.attack_cd = 0.0
        self.cast_windup_timer = 0.0
        self.cast_windup_max = 0.65
        self.pending_pentagram = False
        self.jungle_home = (self.x, self.y) if kind in ATTACKS else None
        self.jungle_windup = None
        self.jungle_dash = None
        self.jungle_impact = None
        self.jungle_impact_timer = 0.0
        self.patrol_dir = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
        self.patrol_timer = random.uniform(1.2, 2.8)

        self.chat_lines = chat_lines or []
        self.chat_partner = None
        self.chat_timer = random.uniform(1.0, 3.0)
        self.chat_index = 0
        self.current_speech = None

        self.solo_lines = []
        self.solo_timer = random.uniform(1.8, 4.0)
        self.voice_timer = next_call_delay(kind, initial=True)
        self.solo_show_timer = 0.0

        self.path = []
        self.path_timer = 0.0
        self.kb_vx = 0.0
        self.kb_vy = 0.0
        self.bleed_timer = self.bleed_tick = 0.0
        self.bleed_dmg = 1
        self.poison_timer = 0.0
        self.poison_tick = 0.0
        self.poison_dmg = 2
        self.burn_timer = 0.0
        self.burn_tick = 0.0
        self.burn_dmg = 3
        self.slow_timer = 0.0
        self.armor_breaker_until = 0.0
        self.armor_breaker_ready_at = 0.0
        self.stun_timer = 0.0
        self.root_timer = 0.0
        self.chill_after_root = 0.0
        self.glow_timer = 0.0
        self.glow_color = (255, 255, 255)
        self.hit_flash_timer = 0.0
        self.hit_flash_crit = False
        self.last_lit_pos = None

    def apply_balance_profile(self, profile, floor_num=1):
        if not profile:
            return
        fl_mult_hp = 1.0 + (floor_num - 1) * profile.get("floor_hp_growth", 0.22)
        fl_mult_dmg = 1.0 + (floor_num - 1) * profile.get("floor_dmg_growth", 0.18)
        self.max_hp = max(1, round(profile["hp"] * fl_mult_hp * (1.06 if self.is_boss else 1.16)))
        self.hp = self.max_hp
        self.phys_def = int(round(profile["phys_def"] + (floor_num - 1) * 0.5))
        self.mag_def = int(round(profile["mag_def"] + (floor_num - 1) * 0.5))
        self.dmg_min = max(1, int(round(profile["dmg_min"] * fl_mult_dmg)))
        self.dmg_max = max(self.dmg_min, int(round(profile["dmg_max"] * fl_mult_dmg)))
        self.xp_value = int(round(profile["xp"] * (1.0 + (floor_num - 1) * 0.20)))

    def trigger_bump(self, dx, dy):
        self.bump_x = dx * 0.35
        self.bump_y = dy * 0.35

    def apply_knockback(self, dir_x, dir_y, force):
        if force <= 0.0:
            return
        resist = 0.45 if (self.kind == "brute" or self.is_boss) else 1.0
        self.kb_vx = dir_x * force * 6.5 * resist
        self.kb_vy = dir_y * force * 6.5 * resist

    def apply_status(self, status_name, duration, add_popup, dmg_val=3):
        if not status_name or duration <= 0.0:
            return
        if status_name == "bleed":
            self.bleed_timer = max(self.bleed_timer, duration)
            self.bleed_dmg = max(1, int(dmg_val))
        if status_name == "poison":
            self.poison_timer = max(self.poison_timer, duration)
            self.poison_dmg = max(1, int(math.floor(dmg_val)))
        elif status_name == "burn":
            self.burn_timer = max(self.burn_timer, duration)
            self.burn_dmg = max(1, int(math.floor(dmg_val)))
            self.glow_timer = max(self.glow_timer, duration)
            self.glow_color = (255, 115, 35)
        elif status_name == "slow":
            self.slow_timer = max(self.slow_timer, duration)
        elif status_name == "stun":
            self.stun_timer = max(self.stun_timer, duration)
        elif status_name == "root":
            self.root_timer = max(self.root_timer, duration)

    def alert_to_combat(self, sfx, add_popup, player=None, dungeon=None):
        if self.state != "combat":
            self.state = "combat"
            self.awareness = 100.0
            self.alert_bang_timer = 0.38
            self.current_speech = None
            self.path_timer = 0.0
            self.attack_cd = max(self.attack_cd, random.uniform(0.12, 0.45))
            if hasattr(sfx, "play_spatial") and player is not None:
                sfx.play_spatial("alert", self.x, self.y, player.x, player.y, dungeon, max_dist=16.0)
            else:
                sfx.play("alert")
            if self.chat_partner and self.chat_partner.state != "combat":
                self.chat_partner.state = "combat"
                self.chat_partner.awareness = 100.0
                self.chat_partner.alert_bang_timer = 0.38
                self.chat_partner.current_speech = None
                self.chat_partner.path_timer = 0.0
                self.chat_partner.attack_cd = max(self.chat_partner.attack_cd, random.uniform(0.35, 0.75))

    def play_voice(self, sfx, player, dungeon):
        sound = choose_voice(self.kind)
        if hasattr(sfx, "play_spatial"):
            sfx.play_spatial(sound, self.x, self.y, player.x, player.y, dungeon, max_dist=12.0, base_gain=0.82)
        elif math.hypot(self.x - player.x, self.y - player.y) < 8:
            sfx.play(sound)

    def update_ai(self, dt, player, dungeon, all_mobs, projectiles, sfx, add_popup, on_player_hit):
        self.bump_x *= max(0.0, 1.0 - 14.0 * dt)
        self.bump_y *= max(0.0, 1.0 - 14.0 * dt)
        self.attack_cd = max(0.0, self.attack_cd - dt)
        self.path_timer = max(0.0, self.path_timer - dt)
        self.alert_bang_timer = max(0.0, self.alert_bang_timer - dt)
        self.jungle_impact_timer = max(0.0, self.jungle_impact_timer - dt)

        # 1. Process Smooth Knockback Displacement
        if math.hypot(self.kb_vx, self.kb_vy) > 0.15:
            rad = 0.25
            ktx = self.x + self.kb_vx * dt
            if not (dungeon.is_blocking_move(int(ktx - rad), int(self.y - rad)) or dungeon.is_blocking_move(int(ktx + rad), int(self.y + rad))):
                self.x = ktx
            kty = self.y + self.kb_vy * dt
            if not (dungeon.is_blocking_move(int(self.x - rad), int(kty - rad)) or dungeon.is_blocking_move(int(self.x + rad), int(kty + rad))):
                self.y = kty
            self.kb_vx *= max(0.0, 1.0 - 10.0 * dt)
            self.kb_vy *= max(0.0, 1.0 - 10.0 * dt)

        # 2. Process Status Effects
        self.glow_timer = max(0.0, self.glow_timer - dt)
        self.hit_flash_timer = max(0.0, self.hit_flash_timer - dt)
        if self.bleed_timer > 0:
            self.bleed_timer = max(0, self.bleed_timer - dt)
            self.bleed_tick += dt
            if self.bleed_tick >= .65:
                self.bleed_tick = 0
                self.hp -= self.bleed_dmg
                add_popup(self.x, self.y, f"-{self.bleed_dmg}", (220, 65, 65))
        if self.poison_timer > 0.0:
            self.poison_timer = max(0.0, self.poison_timer - dt)
            self.poison_tick += dt
            if self.poison_tick >= 0.65:
                self.poison_tick = 0.0
                self.hp -= self.poison_dmg
                add_popup(self.x, self.y, f"-{int(self.poison_dmg)}", (110, 245, 95))

        if self.burn_timer > 0.0:
            self.burn_timer = max(0.0, self.burn_timer - dt)
            self.burn_tick += dt
            if self.burn_tick >= 0.55:
                self.burn_tick = 0.0
                self.hp -= self.burn_dmg
                add_popup(self.x, self.y, f"-{int(self.burn_dmg)}", (255, 135, 45))

        if self.slow_timer > 0.0:
            self.slow_timer = max(0.0, self.slow_timer - dt)
        if self.root_timer > 0.0:
            self.root_timer = max(0.0, self.root_timer - dt)
            if self.root_timer <= 0.0 and self.chill_after_root > 0.0:
                self.slow_timer = max(self.slow_timer, self.chill_after_root)
                self.chill_after_root = 0.0
        if self.stun_timer > 0.0:
            self.stun_timer = max(0.0, self.stun_timer - dt)
            self.cast_windup_timer = 0.0
            self.jungle_windup = None
            self.jungle_dash = None
            return

        if self.hp <= 0:
            return

        dx = player.x - self.x
        dy = player.y - self.y
        dist = math.hypot(dx, dy)

        if self.jungle_home is not None:
            distance_home = math.dist((self.x, self.y), self.jungle_home)
            if self.state == "returning":
                if distance_home > 0.5:
                    self._follow_astar_path(*self.jungle_home, dt, dungeon, all_mobs)
                else:
                    self.state = "guarding"
                return
            if self.kind == "tribal_shaman" and self.state != "combat":
                if any(other is not self and other.kind in TRIBE and other.state == "combat"
                       and dungeon.has_line_of_sight(self.x, self.y, other.x, other.y, 5)
                       for other in all_mobs):
                    self.alert_to_combat(sfx, add_popup, player=player, dungeon=dungeon)

        if self.state != "combat":
            state_mult = {
                "sleeping": 0.28,
                "eating": 0.60,
                "chatting": 0.70,
                "patrolling": 1.15
            }.get(self.state, 1.0)

            p_tile = dungeon.grid[int(player.y)][int(player.x)]
            surface_noise = 1.5 if p_tile == 2 else (0.55 if p_tile == 3 else 1.0)

            stealth_factor = .15 if getattr(player,"stealth_timer",0)>0 else 1
            eff_range = stealth_factor * self.detect_range * (0.45 + player.illumination * 0.85) * state_mult
            can_sense = False

            hear_range = 2.8 * player.noise_factor * surface_noise
            if dist <= hear_range:
                can_sense = True
            elif dist <= eff_range and dungeon.has_line_of_sight(self.x, self.y, player.x, player.y, eff_range):
                can_sense = True

            if can_sense:
                prox = max(0.25, (max(eff_range, hear_range) - dist) / max(1.0, eff_range))
                gain = (62.0 * self.perception * state_mult * (0.40 + player.illumination * 1.2) * player.noise_factor * surface_noise * (prox ** 1.1))
                if dist < 1.85:
                    gain += 130.0
                self.awareness = min(100.0, self.awareness + gain * dt)
                if self.awareness >= 100.0:
                    self.alert_to_combat(sfx, add_popup, player=player, dungeon=dungeon)
            else:
                self.awareness = max(0.0, self.awareness - 12.0 * dt)

            if self.state == "chatting" and self.chat_lines:
                self.chat_timer -= dt
                if self.chat_timer <= 0.0:
                    if self.chat_index < len(self.chat_lines):
                        self.chat_timer = 3.4
                        line = self.chat_lines[self.chat_index]
                        if self.chat_index % 2 == 0:
                            self.current_speech = line
                            if self.chat_partner:
                                self.chat_partner.current_speech = None
                        else:
                            self.current_speech = None
                            if self.chat_partner:
                                self.chat_partner.current_speech = line
                        speaker = self.chat_partner if self.chat_index % 2 and self.chat_partner else self
                        self.chat_index += 1
                        speaker.play_voice(sfx, player, dungeon)
                    else:
                        self.current_speech = None
                        self.state = "patrolling"
                        if self.chat_partner and self.chat_partner.state == "chatting":
                            self.chat_partner.current_speech = None
                            self.chat_partner.state = "eating"

            if self.state != "chatting" and self.solo_lines:
                if self.solo_show_timer > 0.0:
                    self.solo_show_timer -= dt
                    if self.solo_show_timer <= 0.0:
                        self.current_speech = None
                else:
                    self.solo_timer -= dt
                    if self.solo_timer <= 0.0:
                        self.solo_timer = random.uniform(4.5, 8.0)
                        self.solo_show_timer = 4.0
                        self.current_speech = random.choice(self.solo_lines)
                        self.play_voice(sfx, player, dungeon)

            if self.state == "patrolling":
                if self.jungle_home is not None and distance_home > 3.0:
                    self.state = "returning"
                    self.path_timer = 0.0
                    return
                self.patrol_timer -= dt
                if self.patrol_timer <= 0.0:
                    self.patrol_dir = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1), (0, 0)])
                    self.patrol_timer = random.uniform(1.5, 3.2)
                if self.patrol_dir != (0, 0):
                    if self.patrol_dir[0] != 0:
                        self.facing = 1 if self.patrol_dir[0] > 0 else -1
                    old_x, old_y = self.x, self.y
                    self._step_with_collision(self.patrol_dir[0], self.patrol_dir[1], dt * 0.45, dungeon, all_mobs)
                    if math.hypot(self.x - old_x, self.y - old_y) < 0.001:
                        self.patrol_dir = (-self.patrol_dir[0], -self.patrol_dir[1])
            return

        # --- COMBAT AI WITH FULL A* PATHFINDING, PENTAGRAM CASTING & BOSS CRIES ---
        if self.is_boss and self.solo_lines:
            if self.solo_show_timer > 0.0:
                self.solo_show_timer -= dt
                if self.solo_show_timer <= 0.0:
                    self.current_speech = None
            else:
                self.solo_timer -= dt
                if self.solo_timer <= 0.0:
                    self.solo_timer = random.uniform(5.0, 8.5)
                    self.solo_show_timer = 3.2
                    self.current_speech = random.choice(self.solo_lines)
                    self.play_voice(sfx, player, dungeon)

        if abs(dx) > 0.08:
            self.facing = 1 if dx > 0 else -1

        if self.jungle_home is not None:
            update_jungle_combat(self, dt, player, dungeon, all_mobs, projectiles, sfx, add_popup, on_player_hit)
            return

        # 1. If currently channeling a dark spell (windup before pentagram appears!)
        if self.cast_windup_timer > 0.0:
            self.cast_windup_timer -= dt
            if self.cast_windup_timer <= 0.0:
                self.cast_windup_timer = 0.0
                self.pending_pentagram = True
                if dist > 0.001:
                    self.trigger_bump((dx / dist) * 0.35, (dy / dist) * 0.35)
            return

        if dist < 0.001:
            return
        nx, ny = dx / dist, dy / dist

        if self.is_ranged:
            has_los = dungeon.has_line_of_sight(self.x, self.y, player.x, player.y, 9.5)
            melee_engage_dist = 1.75 if self.size_tiles >= 2 else 2.0
            melee_hit_reach = 1.75 if self.size_tiles >= 2 else 1.25

            # 1. Движение: если игрок подошёл вплотную (<= 2.0 тайла), культист идёт на сближение в рукопашную!
            if dist <= melee_engage_dist:
                if dist > melee_hit_reach * 0.88:
                    self._follow_astar_path(player.x, player.y, dt, dungeon, all_mobs)
            elif dist > 5.8 or not has_los:
                self._follow_astar_path(player.x, player.y, dt, dungeon, all_mobs)
            elif dist < 2.8 and not self.is_boss:
                self._step_with_collision(-nx, -ny, dt, dungeon, all_mobs)
            elif self.is_boss and dist > 1.35:
                self._follow_astar_path(player.x, player.y, dt, dungeon, all_mobs)

            # 2. Атака: удар в ближнем бою ИЛИ дистанционный каст с небольшим разбросом КД
            if dist <= melee_hit_reach and self.attack_cd <= 0.0:
                self.attack_cd = 0.95 if self.is_boss else 1.05
                self.trigger_bump(nx, ny)
                sfx.play("hit")
                on_player_hit(random.randint(self.dmg_min, self.dmg_max), is_magic=False)
            elif dist > melee_engage_dist and has_los and dist <= 8.2 and self.attack_cd <= 0.0:
                cd_jitter = random.uniform(-0.15, 0.30)
                if self.kind in ("rat_cultist", "rat_king"):
                    self.cast_windup_max = 0.58 if self.is_boss else 0.68
                    self.cast_windup_timer = self.cast_windup_max
                    self.attack_cd = (1.85 if self.is_boss else 2.55) + cd_jitter
                    if hasattr(sfx, "play_spatial"):
                        sfx.play_spatial("spell_windup", self.x, self.y, player.x, player.y, dungeon, max_dist=18.0)
                    else:
                        sfx.play("spell_windup")
                else:
                    self.attack_cd = 1.55 + cd_jitter
                    self.trigger_bump(nx * 0.5, ny * 0.5)
                    if hasattr(sfx, "play_spatial"):
                        sfx.play_spatial("magic", self.x, self.y, player.x, player.y, dungeon, max_dist=18.0)
                    else:
                        sfx.play("magic")
                    dmg = random.randint(self.dmg_min, self.dmg_max)
                    projectiles.append(Projectile(
                        self.x, self.y, nx, ny,
                        speed=6.5, mag_dmg=dmg,
                        color=self.proj_color, from_player=False
                    ))
                    projectiles[-1].source = self
        else:
            if dist > 1.05:
                self._follow_astar_path(player.x, player.y, dt, dungeon, all_mobs)
            elif self.attack_cd <= 0.0:
                self.attack_cd = 0.80 if self.kind in ("rat", "wolf") else (1.05 if self.kind == "skeleton" else 1.35)
                self.trigger_bump(nx, ny)
                raw_phys = random.randint(self.dmg_min, self.dmg_max)
                on_player_hit(raw_phys, is_magic=False)

    def _follow_astar_path(self, target_x, target_y, dt, dungeon, all_mobs):
        if self.path_timer <= 0.0 or not self.path:
            self.path_timer = random.uniform(0.24, 0.36)
            self.path = dungeon.find_path((int(self.x), int(self.y)), (int(target_x), int(target_y)))

        while self.path and math.hypot(self.path[0][0] - self.x, self.path[0][1] - self.y) < 0.22:
            self.path.pop(0)

        if self.path:
            wx, wy = self.path[0]
            dx, dy = wx - self.x, wy - self.y
        else:
            dx, dy = target_x - self.x, target_y - self.y

        d = math.hypot(dx, dy)
        if d > 0.001:
            self._step_with_collision(dx / d, dy / d, dt, dungeon, all_mobs)

    def _step_with_collision(self, dir_x, dir_y, dt, dungeon, all_mobs):
        if abs(dir_x) > 0.15:
            self.facing = 1 if dir_x > 0 else -1
        sep_x, sep_y = 0.0, 0.0
        for other in all_mobs:
            if other is not self:
                odx = self.x - other.x
                ody = self.y - other.y
                od = math.hypot(odx, ody)
                if 0.001 < od < 0.65:
                    push = (0.65 - od) / 0.65
                    sep_x += (odx / od) * push * 0.8
                    sep_y += (ody / od) * push * 0.8

        vx = dir_x + sep_x
        vy = dir_y + sep_y
        v_len = math.hypot(vx, vy)
        if v_len > 0.001:
            vx /= v_len
            vy /= v_len

        if self.root_timer > 0.0:
            return
        spd_mult = 0.45 if self.slow_timer > 0.0 else 1.0
        step = self.speed * spd_mult * dt
        rad = 0.25

        moved_any = False
        tx = self.x + vx * step
        if not (
            dungeon.is_blocking_move(int(tx - rad), int(self.y - rad))
            or dungeon.is_blocking_move(int(tx + rad), int(self.y - rad))
            or dungeon.is_blocking_move(int(tx - rad), int(self.y + rad))
            or dungeon.is_blocking_move(int(tx + rad), int(self.y + rad))
        ):
            self.x = tx
            moved_any = True

        ty = self.y + vy * step
        if not (
            dungeon.is_blocking_move(int(self.x - rad), int(ty - rad))
            or dungeon.is_blocking_move(int(self.x + rad), int(ty - rad))
            or dungeon.is_blocking_move(int(self.x - rad), int(ty + rad))
            or dungeon.is_blocking_move(int(self.x + rad), int(ty + rad))
        ):
            self.y = ty
            moved_any = True

        if not moved_any:
            cx, cy = int(self.x) + 0.5, int(self.y) + 0.5
            self.x += (cx - self.x) * min(1.0, 8.0 * dt)
            self.y += (cy - self.y) * min(1.0, 8.0 * dt)
