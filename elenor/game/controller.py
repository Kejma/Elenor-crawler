from elenor.paths import PROJECT_ROOT
import json
import math
import os
import random
import pygame

from elenor.config import SCREEN_W, SCREEN_H, TILE_W, TILE_H, VIEW_W, VIEW_H
from elenor.audio.synth import SoundSynth
from elenor.audio.voices import next_call_delay
from elenor.world.dungeon import Dungeon
from elenor.world.run_seed import derived_seed, generation_random
from elenor.entities import Player, Enemy, Interactable, FloatingPopup
from elenor.rendering.renderer import Renderer
from elenor.tools.dev_panel import DevPanel
from elenor.missions.rats import populate_mission_floor
from elenor.profile import load_profile
from elenor.ui.menu import MainMenuController
from elenor.rendering.effects import FXManager


from elenor.localization import load_modular_locales

from elenor.game.narrative import NarrativeMixin
from elenor.game.inventory import InventoryMixin
from elenor.game.progression import ProgressionMixin
from elenor.game.combat import CombatMixin

class GameController(NarrativeMixin, InventoryMixin, ProgressionMixin, CombatMixin):
    def __init__(self):
        self.loc = load_modular_locales()
        self.balance_data = self._load_balance_table()
        self.profile = load_profile()
        self.sfx = SoundSynth()
        self._sfx_last_played = {}
        _orig_play = self.sfx.play
        def _throttled_play(name, *args, **kwargs):
            now_t = pygame.time.get_ticks()
            min_gap = 85 if name in ("spell_windup", "alert", "mob_talk") else 45
            if now_t - self._sfx_last_played.get(name, -999) < min_gap:
                return
            self._sfx_last_played[name] = now_t
            _orig_play(name, *args, **kwargs)
        self.sfx.play = _throttled_play
        self.dungeon = Dungeon(puzzle_profile="rats")
        self.renderer = Renderer()
        self.dev_panel = DevPanel()
        self.inv_open = False
        self.drag_item = None
        self.drag_source = None
        self.world_active = False
        self.fx = FXManager(self)
        self.display_surface = None
        self.gl_window = None
        self.viewport_rect = (0, 0, SCREEN_W, SCREEN_H)
        self.in_main_menu = True
        self.main_menu = MainMenuController(self)
        self.main_menu.sync_audio_and_display()
        self._last_picked_line = {}
        self.bg_thought_cd = 0.0
        self.important_thought_lock = 0.0
        self.important_thought_queue = []
        self.low_hp_thought_cd = 0.0
        self.seen_entities = set()
        self._prev_tile_id = 0
        self._was_near_fire = False
        self._was_in_fog_kind = None
        self._dark_walk_timer = 0.0
        self.journal_open = False
        self.journal_scroll = 0
        self.journal_logs = []
        self.journal_filters = {"combat": True, "event": True, "speech": True}
        self.reset_run()


    def play_spatial(self, name, sx, sy, max_dist=18.0, base_gain=1.0):
        """Удобный хелпер для запуска пространственного звука окружения."""
        if hasattr(self, "sfx") and hasattr(self.sfx, "play_spatial"):
            px = getattr(self.player, "x", None)
            py = getattr(self.player, "y", None)
            dungeon = getattr(self, "dungeon", None)
            self.sfx.play_spatial(name, sx, sy, px, py, dungeon=dungeon, max_dist=max_dist, base_gain=base_gain)
        else:
            self.sfx.play(name)


    def update_enemy_voices(self, dt):
        self.enemy_voice_cooldown = max(0.0, self.enemy_voice_cooldown - dt)
        nearby = []
        for mob in self.mobs:
            if mob.hp <= 0 or mob.state == "sleeping" or mob.stun_timer > 0:
                continue
            distance = math.hypot(mob.x - self.player.x, mob.y - self.player.y)
            if distance > 12.0:
                continue
            mob.voice_timer = max(0.0, mob.voice_timer - dt)
            if mob.voice_timer == 0.0:
                nearby.append((distance, mob))
        if self.enemy_voice_cooldown == 0.0 and nearby:
            _, mob = min(nearby, key=lambda entry: entry[0])
            mob.voice_timer = next_call_delay(mob.kind)
            self.enemy_voice_cooldown = 4.0
            mob.play_voice(self.sfx, self.player, self.dungeon)

    def _load_balance_table(self):
        b_path = os.path.join(str(PROJECT_ROOT), "locales", "ru", "balance_table.json")
        if os.path.isfile(b_path):
            with open(b_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}


    def emit_noise(self, wx, wy, base_radius):
        if getattr(self.player,"stealth_timer",0)>0:
            base_radius *= .15
        """
        Global Noise System: Actions (attacks, lighting torch, lockpicking, levers, barrels)
        emit a sound wave that wakes sleeping mobs and alerts nearby enemies!
        """
        eff_rad = base_radius * (0.65 + 0.35 * self.player.noise_factor)
        for m in self.mobs:
            d = math.hypot(m.x - wx, m.y - wy)
            if d <= eff_rad:
                has_los = self.dungeon.has_line_of_sight(wx, wy, m.x, m.y, eff_rad)
                if has_los or d <= eff_rad * 0.60:
                    if m.state == "sleeping":
                        m.state = "patrolling"
                        m.current_speech = None
                        self.add_popup(m.x, m.y, "?!", (255, 215, 90))
                    elif m.state != "combat" and d <= eff_rad * 0.82:
                        m.alert_to_combat(self.sfx, self.add_popup)


    def reset_run(self, campaign=None, *, seed=None):
        self.campaign = campaign or getattr(self, "campaign", "rats")
        self.run_seed = random.SystemRandom().getrandbits(64) if seed is None else seed
        self.jungle_locations = {}
        self.fishing_catches = {}
        self.enemy_voice_cooldown = 0.0
        if hasattr(self, "fx") and self.fx:
            self.fx.disco_active = False
        self.sfx.stop_disco_track()
        self.inv_open = False
        self.journal_open = False
        self.journal_scroll = 0
        self.journal_logs = []
        self.seed_copy_message = ""
        self.seed_copy_until = 0
        self.important_thought_queue = []
        self.drag_item = None
        self.drag_source = None
        self.levelup_choices = None

        hero_rng = random.Random(self._run_generation_seed("hero"))
        adj_key = hero_rng.choice(sorted(self.loc["adjectives"]))
        noun_key = hero_rng.choice(sorted(self.loc["nouns"]))
        adj_data = self.loc["adjectives"][adj_key]
        noun_data = self.loc["nouns"][noun_key]

        variant = self._run_generation_seed("routes") % 6 if self.campaign == "jungle" else 0
        self._generate_run_floor(1, variant=variant)
        if self.campaign == "jungle":
            start_x, start_y = self.dungeon.start_pos
        else:
            center_x, start_y = self.dungeon.rooms[0].center
            start_x = center_x - 2
        appearance = {
            "hero_type": self.profile.get("hero_type", "male"),
            "skin_idx": self.profile.get("skin_idx", 0),
            "head_idx": self.profile.get("head_idx", 0),
            "outfit_idx": self.profile.get("outfit_idx", 0),
        }
        self.player = Player(start_x, start_y, adj_key, adj_data, noun_key, noun_data, self.loc["items"], appearance=appearance)
        if self.campaign == "jungle":
            self.player.equipment["left_hand"] = None

        self._populate_floor(floor_num=1)
        self.target_thought = ""
        self.shown_chars = 0.0
        self.last_tick_char = 0
        self.ambient_timer = random.uniform(90.0, 140.0)

        # Стартовая мысль при появлении в мире — всегда ВАЖНАЯ!
        q_info = f" ({self.player.quirk_desc})" if getattr(self.player, "quirk_desc", "") else ""
        spawn_line = self.pick_text(self.player.thoughts["spawn"], "player_spawn")
        intro_text = f"{self.player.full_name}{q_info} {spawn_line}"
        self.bg_thought_cd = 0.0
        self.important_thought_lock = 0.0
        if self.campaign == "jungle":
            intro_text = self.loc["fishing"]["intro"]
        self.set_thought(intro_text, important=True)
        self.sfx.play("ui")

    def _run_generation_seed(self, phase, depth=0, interior=None):
        seed = getattr(self, "run_seed", None)
        return derived_seed(seed, self.campaign, phase, depth, interior) if seed is not None else None

    def _generate_run_floor(self, depth, interior=None, *, variant=0):
        with generation_random(self._run_generation_seed("layout", depth, interior)):
            self.dungeon.generate(depth, campaign=self.campaign, interior=interior, route_variant=variant)

    def travel_jungle(self, action):
        from elenor.world.jungle_routes import route_kind

        current = self.dungeon
        depth, interior = current.floor_num, current.interior
        if action == "up":
            destination, arrival = (depth, None), interior
        elif action in ("cave", "temple"):
            destination, arrival = (depth, action), "up"
        elif action == "onward" and current.jungle_gate is not None:
            if current.doors[current.jungle_gate].locked:
                return
            destination, arrival = (depth + 1, None), "back"
        elif action == "back" and depth > 1:
            destination, arrival = (depth - 1, route_kind(depth - 1, current.jungle_route_variant)), "onward"
        else:
            return

        self.jungle_locations[(depth, interior)] = (current, self.objects, self.mirror_puzzles, self.seen_entities, self.mobs)
        for mob in self.mobs:
            mob.jungle_windup = None
            mob.jungle_dash = None
            mob.jungle_impact_timer = mob.cast_windup_timer = 0.0
        current._light_cache.clear()
        cached = self.jungle_locations.pop(destination, None)
        if cached:
            self.dungeon = cached[0]
        else:
            self.dungeon = Dungeon(puzzle_chance=current.puzzle_chance)
            self._generate_run_floor(*destination, variant=current.jungle_route_variant)
        xy = next(pos for pos, passage in self.dungeon.passages.items() if passage == arrival)
        self.player.x, self.player.y = xy[0]+0.5, xy[1]+0.5
        self.player.pending_action = None
        self.player.lunge_vx = self.player.lunge_vy = 0.0
        self._populate_floor(destination[0], cached)
        self.sfx.play("door" if interior or destination[1] else "step_dirt")

    def descend_to_next_floor(self):
        if self.campaign == "jungle":
            from elenor.world.jungle_routes import route_kind
            self.travel_jungle("up" if self.dungeon.interior else route_kind(
                self.dungeon.floor_num, self.dungeon.jungle_route_variant
            ))
            return
        if hasattr(self, "fx") and self.fx:
            self.fx.disco_active = False
        self.sfx.stop_disco_track()
        next_fl = self.dungeon.floor_num + 1
        self._generate_run_floor(next_fl)
        sx, sy = getattr(self.dungeon, "start_pos", self.dungeon.rooms[0].center)
        self.player.x, self.player.y = float(sx) + 0.5, float(sy) + 0.5
        self._populate_floor(floor_num=next_fl)
        self.sfx.play("door")


    def _populate_floor(self, floor_num, cached=None):
        self.world_active = False
        self.player.buffered_combat = None
        self.popups = []
        self.fishing_cast = None
        self.catch_display = None
        self.physical_effects = []
        self.projectiles = []
        self.particles = []
        self.visual_fx = []
        self.mobs = []
        self.objects = []
        self.mirror_puzzles = []
        self.current_visible_tiles = set()
        self.map_open = False
        self.seen_entities = set()
        self._prev_tile_id = self.dungeon.grid[int(self.player.y)][int(self.player.x)]
        self._was_near_fire = True
        self._was_in_fog_kind = None
        self._dark_walk_timer = 0.0
        if hasattr(self, "fx") and self.fx:
            self.fx.clear_floor_decals()
            self.fx.rebuild_wall_grid(self.dungeon)

        self.cam_x = self.player.x * TILE_W - VIEW_W * 0.5
        self.cam_y = self.player.y * TILE_H - VIEW_H * 0.5

        if cached:
            _, self.objects, self.mirror_puzzles, self.seen_entities, self.mobs = cached
        else:
            seed = self._run_generation_seed("population", floor_num, self.dungeon.interior)
            with generation_random(seed):
                if self.campaign == "jungle":
                    from elenor.missions.jungle import populate_jungle_floor
                    populate_jungle_floor(self, Interactable)
                else:
                    populate_mission_floor(self, floor_num, Enemy, Interactable)

        from elenor.puzzles.optics import MIRROR_SOLID_KINDS
        from elenor.entities import SOLID_INTERACTABLE_KINDS
        solid_kinds = SOLID_INTERACTABLE_KINDS | MIRROR_SOLID_KINDS
        self.dungeon.solid_props = {
            (obj.x, obj.y) for obj in self.objects if obj.kind in solid_kinds
        }
        renderer = getattr(self, "renderer", None)
        if renderer is not None:
            renderer.terrain.warm(self.dungeon)


    def add_popup(self, wx, wy, text, color, icon=None, big=False):
        self.popups.append(FloatingPopup(wx, wy, text, color, icon, big=big))

