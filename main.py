import json
import math
import os
import random
import pygame

from config import (
    SCREEN_W, SCREEN_H, TILE_W, TILE_H, VIEW_W, VIEW_H, CANVAS_H,
    MAP_COLS, MAP_ROWS, SCALE,
    THOUGHT_BOX_X, THOUGHT_BOX_Y, THOUGHT_BOX_W, THOUGHT_BOX_H,
    TORCH_Z_HEIGHT, TYPEWRITER_SPEED, RARITY_WEIGHTS, get_rarity_weights
)
from audio import SoundSynth
from dungeon import Dungeon
from entities import Item, Player, Enemy, Interactable, Projectile, Particle, FloatingPopup
from renderer import Renderer
from dev_panel import DevPanel
from mission_rats import (
    get_mission_texts, populate_mission_floor, handle_mission_object_interaction
)
from menu_and_profile import (
    load_profile, save_profile, format_copper_Trigger,
    CURRENCY_AND_GEMS_DB, MainMenuController
)
from fx_lab import FXManager


class _SafeFormatDict(dict):
    """Позволяет безопасно форматировать строки из JSON, даже если пользователь не указал {переменную} или опечатался."""
    def __missing__(self, key):
        return "{" + key + "}"


def load_modular_locales():
    base_dir = os.path.dirname(__file__)
    ru_dir = os.path.join(base_dir, "locales", "ru")
    merged = {"items": dict(CURRENCY_AND_GEMS_DB)}
    if os.path.isdir(ru_dir):
        for fname in sorted(os.listdir(ru_dir)):
            if fname.endswith(".json"):
                fpath = os.path.join(ru_dir, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if fname == "items.json" and "items" not in data:
                        merged["items"].update(data)
                    else:
                        for k, v in data.items():
                            if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
                                merged[k].update(v)
                            else:
                                merged[k] = v
    if "perks" in merged:
        if "pyro_ignite" in merged["perks"]:
            merged["perks"]["pyro_ignite"]["mp_cost"] = 8
        if "clear_mind" in merged["perks"]:
            merged["perks"]["clear_mind"]["desc"] = "ПАССИВНО: Повышает магическую мощь (+2) и запас маны (+3)."
    return merged


def dungeon_los_ok(dungeon, x0, y0, x1, y1):
    return dungeon.has_line_of_sight(x0, y0, x1, y1, 4.0)


def is_cursor_on_mob(mob, wx, wy):
    """Checks if world cursor (wx, wy) is over the mob's sprite (supports 1x1 mobs and 2x2 bosses!)."""
    if getattr(mob, "size_tiles", 1) >= 2:
        return abs(wx - mob.x) <= 1.08 and (mob.y - 1.55) <= wy <= (mob.y + 0.95)
    return abs(wx - mob.x) <= 0.55 and (mob.y - 1.02) <= wy <= (mob.y + 0.52)


class GameController:
    def __init__(self):
        self.loc = load_modular_locales()
        self.balance_data = self._load_balance_table()
        self.profile = load_profile()
        self.sfx = SoundSynth()
        self.dungeon = Dungeon()
        self.renderer = Renderer()
        self.dev_panel = DevPanel()
        self.inv_open = False
        self.drag_item = None
        self.drag_source = None
        self.world_active = False
        self.fx = FXManager(self)
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

    def add_log(self, cat, text, color=None):
        """Добавляет запись в Журнал похода (хранит последние 100 записей)."""
        if not text:
            return
        default_cols = {
            "combat": (235, 165, 155),
            "event":  (240, 215, 125),
            "speech": (185, 225, 250),
        }
        self.journal_logs.append({
            "cat": cat,
            "text": str(text),
            "color": color or default_cols.get(cat, (220, 220, 220))
        })
        if len(self.journal_logs) > 100:
            self.journal_logs = self.journal_logs[-100:]

    def get_thought_freq_params(self):
        """Возвращает (множитель_шанса, базовый_кулдаун_сек) из ползунка 'Частота мыслей' в Настройках."""
        mode = self.profile.get("thought_freq_mode", 2)
        if mode == 0:
            return 0.0, 999.0   # Только важные
        if mode == 1:
            return 0.5, 10.0    # Редко
        if mode == 3:
            return 1.75, 3.5    # Часто
        return 1.0, 6.0         # Обычная (по умолчанию: не чаще раза в 6 секунд)

    def pick_text(self, pool, key_id="default", **kwargs):
        if isinstance(pool, list):
            if not pool:
                raw = ""
            elif len(pool) == 1:
                raw = str(pool[0])
            else:
                last = self._last_picked_line.get(key_id)
                candidates = [s for s in pool if s != last] or pool
                raw = str(random.choice(candidates))
                self._last_picked_line[key_id] = raw
        else:
            raw = str(pool)
        if kwargs:
            return raw.format_map(_SafeFormatDict(kwargs))
        return raw

    def can_trigger_background_thought(self, chance=0.25):
        mult, _ = self.get_thought_freq_params()
        if mult <= 0.0:
            return False
        if self.bg_thought_cd > 0.0 or self.important_thought_lock > 0.0 or self.important_thought_queue:
            return False
        return random.random() <= min(1.0, chance * mult)

    def get_event_text(self, event_key, **kwargs):
        ev_db = self.loc.get("events", {})
        pool = ev_db.get(event_key, "")
        return self.pick_text(pool, f"ev_{event_key}", **kwargs)

    def trigger_event_thought(self, event_key, force_important=None, **kwargs):
        rules_db = self.loc.get("event_rules", {})
        rule = rules_db.get(event_key, {})
        is_imp = force_important if force_important is not None else bool(rule.get("important", False))
        chance = 1.0 if is_imp else float(rule.get("chance", 0.25))

        if not is_imp and not self.can_trigger_background_thought(chance=chance):
            return False

        text = self.get_event_text(event_key, **kwargs)
        if not text:
            return False
        return self.set_thought(text, important=is_imp, chance=1.0)

    def _load_balance_table(self):
        b_path = os.path.join(os.path.dirname(__file__), "locales", "ru", "balance_table.json")
        if os.path.isfile(b_path):
            with open(b_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def make_item(self, item_id):
        itm = Item(item_id, self.loc["items"][item_id])
        # Слегка варьируем количество монет в горсти для живости!
        if item_id == "coin_copper":
            itm.copper_value = random.randint(4, 9)
        elif item_id == "coin_silver":
            itm.copper_value = random.randint(1, 4) * 10 + random.randint(0, 5)
        elif item_id == "coin_gold":
            itm.copper_value = random.randint(1, 2) * 100 + random.randint(0, 4) * 10
        return itm

    def roll_currency_or_gem_drop(self, allow_gem=True, force_gem=False, gem_mult=1.0):
        fl = getattr(self.dungeon, "floor_num", 2)
        luck = getattr(getattr(self, "player", None), "luck", 1)
        if force_gem or (allow_gem and random.random() < (0.28 + luck * 0.03) * gem_mult):
            gem_ids = ["gem_malachite", "gem_garnet", "gem_sapphire", "gem_ruby", "gem_diamond"]
            weights = get_rarity_weights(luck + max(0, fl - 2))
            return self.make_item(random.choices(gem_ids, weights=weights, k=1)[0])
        coin_ids = ["coin_copper", "coin_silver", "coin_gold", "coin_platinum"]
        c_weights = [max(25.0, 75.0 - fl * 12.0), 20.0 + fl * 6.0, 4.0 + fl * 3.0, 0.4 + (fl - 2) * 0.4]
        return self.make_item(random.choices(coin_ids, weights=c_weights, k=1)[0])

    def roll_item_by_rarity(self, allowed_types=None):
        """Rolls an item using Luck-scaled weights (78% Common at Luck = 1!)."""
        tiers = ["common", "uncommon", "rare", "epic", "legendary"]
        luck_val = getattr(getattr(self, "player", None), "luck", 1)
        weights = get_rarity_weights(luck_val)
        chosen_rarity = random.choices(tiers, weights=weights, k=1)[0]

        candidates = [
            item_id for item_id, data in self.loc["items"].items()
            if data.get("rarity", "common") == chosen_rarity
            and (allowed_types is None or data.get("type") in allowed_types)
        ]
        if not candidates:
            candidates = [
                item_id for item_id, data in self.loc["items"].items()
                if allowed_types is None or data.get("type") in allowed_types
            ]
        return self.make_item(random.choice(candidates))

    def _is_perk_eligible(self, pid, pdata):
        ptype = pdata.get("type", "passive")
        if ptype == "active":
            return (pid in self.player.active_perks) or (len(self.player.active_perks) < 2)
        return (pid in self.player.passive_perks) or (len(self.player.passive_perks) < 5)

    def _get_perk_branch(self, pid, pdata):
        perk_tags = {
            "tough_skin": "body", "iron_grip": "body", "stone_ribs": "body",
            "titan_blood": "body", "blood_hunger": "body", "whirlwind": "body", "earth_slam": "body",
            "cat_step": "cunning", "keen_edge": "cunning", "throw_knife": "cunning", "poison_flask": "cunning",
            "clear_mind": "mind", "storm_aura": "mind",
            "pyro_firebolt": "mind", "pyro_ignite": "mind",
            "stratos_frost_nova": "mind", "stratos_chain_lightning": "mind",
            "persephone_rejuvenation": "mind", "persephone_entangle": "mind"
        }
        if pid in perk_tags:
            return perk_tags[pid]
        if pdata.get("skill_kind") == "combat":
            return "body"
        if pdata.get("type") == "active":
            return "mind"
        return "body"

    def _roll_spell_upgrade_stats(self, pdata, tier_weights_list):
        """
        Для уже изученного заклинания выбирает редкость апгрейда (12% / 24% / 48% / 96% / 192%)
        и делит этот процент поровну между 1..3 случайными параметрами способности!
        """
        tiers = ["common", "uncommon", "rare", "epic", "legendary"]
        pct_table = {
            "common": 0.12,
            "uncommon": 0.24,
            "rare": 0.48,
            "epic": 0.96,
            "legendary": 1.92,
        }
        max_stats_table = {
            "common": 1,
            "uncommon": 2,
            "rare": 3,
            "epic": 3,
            "legendary": 3,
        }
        upg_rarity = random.choices(tiers, weights=tier_weights_list, k=1)[0]
        total_pct = pct_table[upg_rarity]
        avail_stats = list(pdata.get("upgradable_stats", ["power", "cooldown"]))
        max_k = min(len(avail_stats), max_stats_table[upg_rarity])
        k_choose = 1 if max_k <= 1 else random.randint(1, max_k)
        chosen_stats = random.sample(avail_stats, k=k_choose)
        share_pct = total_pct / float(k_choose)
        return upg_rarity, {st: share_pct for st in chosen_stats}

    def roll_perk_choices(self):
        perks_db = self.loc.get("perks", {})
        if not perks_db:
            return
        tiers = ["common", "uncommon", "rare", "epic", "legendary"]
        tier_weights_list = get_rarity_weights(getattr(self.player, "luck", 1))
        r_weights = dict(zip(tiers, tier_weights_list))

        aff = self.player.get_build_affinities()
        total_aff = sum(aff.values()) + 1.0

        chosen = []
        used_ids = set()

        for _ in range(3):
            candidates = [
                (pid, pdata) for pid, pdata in perks_db.items()
                if pid not in used_ids and self._is_perk_eligible(pid, pdata)
            ]
            if not candidates:
                break
            cand_weights = []
            for pid, pdata in candidates:
                base_w = r_weights.get(pdata.get("rarity", "common"), 10.0)
                branch = self._get_perk_branch(pid, pdata)
                branch_share = aff.get(branch, 0.0) / total_aff
                affinity_mult = 1.0 + 1.45 * branch_share
                owned_mult = 1.25 if pid in self.player.perks else 1.0
                cand_weights.append(base_w * affinity_mult * owned_mult)

            picked_pid, picked_data = random.choices(candidates, weights=cand_weights, k=1)[0]
            used_ids.add(picked_pid)
            p_copy = dict(picked_data)
            p_copy["id"] = picked_pid

            if picked_pid in self.player.perks and picked_data.get("type") == "active":
                upg_rar, upg_roll = self._roll_spell_upgrade_stats(picked_data, tier_weights_list)
                p_copy["rarity"] = upg_rar
                p_copy["upgrade_roll"] = upg_roll

            chosen.append(p_copy)

        if chosen:
            self.levelup_choices = {"mode": "levelup", "choices": chosen, "lock_timer": 1.0}

    def open_oblivion_erase_modal(self, seal_item):
        perks_db = self.loc.get("perks", {})
        owned_ids = list(self.player.active_perks.keys()) + list(self.player.passive_perks.keys())
        if not owned_ids:
            self.trigger_event_thought("oblivion_empty")
            self.sfx.play("hurt")
            return
        choices = []
        for pid in owned_ids:
            if pid in perks_db:
                p_copy = dict(perks_db[pid])
                p_copy["id"] = pid
                choices.append(p_copy)
        self.inv_open = False
        self.levelup_choices = {"mode": "erase", "choices": choices, "lock_timer": 0.4, "seal_item": seal_item}
        self.sfx.play("magic")

    def select_perk_choice(self, idx):
        if not self.levelup_choices or self.levelup_choices.get("lock_timer", 0.0) > 0.0:
            return
        choices = self.levelup_choices["choices"]
        if not (0 <= idx < len(choices)):
            return
        perk = choices[idx]

        if self.levelup_choices.get("mode") == "erase":
            seal_item = self.levelup_choices.get("seal_item")
            if self.player.remove_perk(perk["id"]):
                if seal_item:
                    self.player.remove_item_everywhere(seal_item)
                self.sfx.play("crit")
                self.add_popup(self.player.x, self.player.y - 0.4, f"Стёрто: {perk['name']}", (225, 110, 255))
            self.levelup_choices = None
            return

        self.player.apply_perk(perk["id"], self.loc.get("perks", {}), perk.get("upgrade_roll"))
        self.player.pending_perk_rolls = max(0, self.player.pending_perk_rolls - 1)
        self.sfx.play("heal")
        self.add_popup(self.player.x, self.player.y - 0.4, f"+{perk['name']}", (255, 225, 95))
        if self.player.pending_perk_rolls > 0:
            self.roll_perk_choices()
        else:
            self.levelup_choices = None

    def update_auto_perks(self, dt):
        p = self.player
        if p.perks.get("storm_aura", 0) > 0:
            lvl = p.perks["storm_aura"]
            p.perk_timers["storm_aura"] = p.perk_timers.get("storm_aura", 1.8) - dt
            if p.perk_timers["storm_aura"] <= 0.0:
                p.perk_timers["storm_aura"] = max(1.35, 3.0 - (lvl - 1) * 0.35)
                vis_set = getattr(self, "current_visible_tiles", set())
                nearest = min(
                    (
                        m for m in self.mobs
                        if math.hypot(m.x - p.x, m.y - p.y) <= 5.2
                        and (int(m.x), int(m.y)) in vis_set
                        and self.dungeon.has_line_of_sight(p.x, p.y, m.x, m.y, 5.2)
                    ),
                    key=lambda m: math.hypot(m.x - p.x, m.y - p.y),
                    default=None
                )
                if nearest:
                    # Auto-triggered lightning hits much softer than manual active spells!
                    auto_dmg = max(1, 1 + lvl + p.mag_attack // 4)
                    self._fire_spell_bolt(auto_dmg, (95, 230, 255), nearest.x, nearest.y)

    def emit_noise(self, wx, wy, base_radius):
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

    def player_owns_any_torch(self):
        for eq in self.player.equipment.values():
            if eq and eq.is_torch:
                return True
        for inv_itm in self.player.inventory:
            if inv_itm and inv_itm.is_torch:
                return True
        return False

    def trigger_torch_toggle(self):
        if self.player.hp <= 0 or self.player.pending_action is not None:
            return
        torch = self.player.get_active_torch()
        if torch is None:
            self.sfx.play("hurt")
            self.trigger_event_thought("torch_no_item")
            return

        # Turning OFF is instant and silent!
        if self.player.torch_on:
            self.player.torch_on = False
            self.sfx.play("step")
            self.trigger_event_thought("torch_off")
            return

        # Lighting the torch: 0.25s for Pyromaniac, 1.15s for trembling Nyctophobe, 0.70s default!
        self.sfx.play("torch_spark")
        q = getattr(self.player, "quirk", "none")
        light_time = 0.25 if q == "pyromaniac" else (1.15 if q == "nyctophobe" else 0.70)
        self.player.pending_action = {
            "kind": "light_torch",
            "timer": light_time,
            "max_timer": light_time
        }

    def reset_run(self):
        self.inv_open = False
        self.journal_open = False
        self.journal_scroll = 0
        self.journal_logs = []
        self.important_thought_queue = []
        self.drag_item = None
        self.drag_source = None
        self.levelup_choices = None

        adj_key = random.choice(list(self.loc["adjectives"].keys()))
        noun_key = random.choice(list(self.loc["nouns"].keys()))
        adj_data = self.loc["adjectives"][adj_key]
        noun_data = self.loc["nouns"][noun_key]

        self.dungeon.generate(floor_num=1)
        start_x, start_y = self.dungeon.rooms[0].center
        appearance = {
            "hero_type": self.profile.get("hero_type", "male"),
            "skin_idx": self.profile.get("skin_idx", 0),
            "head_idx": self.profile.get("head_idx", 0),
            "outfit_idx": self.profile.get("outfit_idx", 0),
        }
        self.player = Player(start_x - 2, start_y, adj_key, adj_data, noun_key, noun_data, self.loc["items"], appearance=appearance)

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
        self.set_thought(intro_text, important=True)
        self.sfx.play("ui")

    def check_hypochondriac_panic(self):
        p = self.player
        if p.hp <= 0 or getattr(p, "quirk", "none") != "hypochondriac":
            return
        if p.hp < p.max_hp * 0.5:
            candidates = list(p.hotbar) + [p.inventory[i] for i in range(p.unlocked_slots)]
            for itm in candidates:
                if itm and getattr(itm, "heal_hp", 0) > 0 and p.cooldowns.get(itm.id, 0.0) <= 0.0:
                    heal_val = p.get_heal_amount(itm)
                    p.cooldowns[itm.id] = itm.cooldown
                    p.hp = min(float(p.max_hp), p.hp + heal_val)
                    p.remove_item_everywhere(itm)
                    self.sfx.play("heal")
                    self.add_popup(p.x, p.y, f"+{heal_val} (ПАНИКА!)", (110, 255, 145), "heart", big=True)
                    self.trigger_event_thought("hypochondriac_panic", item=itm.name, val=heal_val)
                    break

    def descend_to_next_floor(self):
        next_fl = self.dungeon.floor_num + 1
        self.dungeon.generate(floor_num=next_fl)
        sx, sy = getattr(self.dungeon, "start_pos", self.dungeon.rooms[0].center)
        self.player.x, self.player.y = float(sx) + 0.5, float(sy) + 0.5
        self._populate_floor(floor_num=next_fl)
        self.sfx.play("door")

    def _populate_floor(self, floor_num):
        self.world_active = False
        self.popups = []
        self.projectiles = []
        self.particles = []
        self.visual_fx = []
        self.mobs = []
        self.objects = []
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

        populate_mission_floor(self, floor_num, Enemy, Interactable)

        solid_kinds = {
            "tavern_table", "bar_counter", "wine_cask", "bed",
            "fireplace", "shelf_bottles", "cauldron", "crate_stack",
            "grandfather_clock", "wash_basin", "meat_rack", "firewood_pile", "armor_stand"
        }
        self.dungeon.solid_props = {
            (obj.x, obj.y) for obj in self.objects if obj.kind in solid_kinds
        }

    def _apply_thought_immediately(self, text, is_important):
        _, base_cd = self.get_thought_freq_params()
        if is_important:
            self.important_thought_lock = 4.0
            self.bg_thought_cd = max(6.0, base_cd)
            self.add_log("speech", text, (255, 225, 125))
        else:
            self.bg_thought_cd = base_cd
            self.add_log("speech", text, (175, 220, 250))

        if text != self.target_thought:
            self.target_thought = text
            self.shown_chars = 0.0
            self.last_tick_char = 0

    def set_thought(self, text, important=False, chance=1.0):
        """
        Управляет мыслями и репликами с поддержкой очереди Важных событий:
        - Если `important=True` и предыдущая важная мысль ещё держится свои 4 секунды — новая встаёт в очередь и запустится строго после неё!
        - Если `important=False` — подчиняется настройке частоты мыслей и не перебивает важные.
        """
        if not text:
            return False

        if not important:
            mult, _ = self.get_thought_freq_params()
            if mult <= 0.0 or self.bg_thought_cd > 0.0 or self.important_thought_lock > 0.0 or self.important_thought_queue:
                return False
            if chance < 1.0 and random.random() > min(1.0, chance * mult):
                return False
            self._apply_thought_immediately(text, is_important=False)
            return True

        # Если сейчас уже идёт показ важной записи (таймер 4.0 с не истёк) — ставим новую важную запись в очередь!
        if self.important_thought_lock > 0.0 and self.target_thought:
            if text != self.target_thought and text not in self.important_thought_queue:
                self.important_thought_queue.append(text)
            return True

        self._apply_thought_immediately(text, is_important=True)
        return True

    def update_typewriter(self, dt):
        self.bg_thought_cd = max(0.0, self.bg_thought_cd - dt)
        self.low_hp_thought_cd = max(0.0, self.low_hp_thought_cd - dt)

        if self.important_thought_lock > 0.0:
            self.important_thought_lock = max(0.0, self.important_thought_lock - dt)
            # Как только прошли обязательные 4 секунды прошлой важной мысли — запускаем следующую из очереди!
            if self.important_thought_lock <= 0.0 and self.important_thought_queue:
                next_imp_text = self.important_thought_queue.pop(0)
                self._apply_thought_immediately(next_imp_text, is_important=True)

        if self.shown_chars < len(self.target_thought):
            t_mode = self.profile.get("typewriter_mode", 1)
            if t_mode == 2:
                self.shown_chars = float(len(self.target_thought))
                return
            spd_mult = 2.0 if t_mode == 1 else 1.0
            self.shown_chars = min(float(len(self.target_thought)), self.shown_chars + TYPEWRITER_SPEED * spd_mult * dt)
            cur_idx = int(self.shown_chars)
            if cur_idx >= self.last_tick_char + 4:
                self.last_tick_char = cur_idx
                self.sfx.play("type_tick")

    def update_world_reactions(self, dt, moved=False):
        """Отслеживает то, что видит и ощущает герой (враги в свете, лужи, туман, темнота, огонь)."""
        px, py = self.player.x, self.player.y
        vis_tiles = getattr(self, "current_visible_tiles", set())

        # 1. Зрительные реакции на врагов и объекты, попавшие в освещённую зону (1 раз на объект!)
        light_reach = (self.player.torch_light_radius if self.player.has_lit_torch else self.player.dark_vision_radius) / TILE_W + 0.8
        for m in self.mobs:
            m_id = id(m)
            if m_id in self.seen_entities:
                continue
            if (int(m.x), int(m.y)) in vis_tiles and math.hypot(m.x - px, m.y - py) <= light_reach:
                self.seen_entities.add(m_id)
                if getattr(m, "is_boss", False):
                    # Первая встреча с Боссом — ВАЖНАЯ реплика (100% перебивает всё)!
                    self.trigger_event_thought("spot_boss", force_important=True)
                    return
                elif m.kind == "rat_cultist":
                    if self.trigger_event_thought("spot_cultist"):
                        return
                elif m.state == "sleeping":
                    if self.trigger_event_thought("spot_sleeping_mob"):
                        return
                elif m.state == "chatting":
                    if self.trigger_event_thought("spot_chatting_mobs"):
                        return

        for obj in self.objects:
            if obj.used or obj.kind != "chest":
                continue
            o_id = id(obj)
            if o_id not in self.seen_entities and (obj.x, obj.y) in vis_tiles and math.hypot((obj.x + 0.5) - px, (obj.y + 0.5) - py) <= light_reach:
                self.seen_entities.add(o_id)
                if self.trigger_event_thought("spot_chest"):
                    return

        # 2. Реакции на среду при движении (шаг в холодную лужу, вход в туман/яд, костёр, темнота)
        cur_tile = self.dungeon.grid[int(py)][int(px)]
        if cur_tile == 2 and self._prev_tile_id != 2:
            self.trigger_event_thought("step_water")
        self._prev_tile_id = cur_tile

        if hasattr(self, "fx") and self.fx:
            in_fog_kind = None
            for cld in self.fx.active_clouds:
                if math.hypot(px - cld["wx"], py - cld["wy"]) <= cld["radius"] * 0.85:
                    in_fog_kind = cld.get("kind", "mist")
                    break
            if in_fog_kind and in_fog_kind != self._was_in_fog_kind:
                self.trigger_event_thought("enter_poison_fog" if in_fog_kind == "poison" else "enter_mist")
            self._was_in_fog_kind = in_fog_kind

        near_fire = any(math.hypot(px - (br["x"] + 0.5), py - (br["y"] + 0.5)) <= 2.5 for br in self.dungeon.braziers)
        if not near_fire:
            near_fire = any(o.kind in ("campfire", "fireplace") and math.hypot(px - (o.x + 0.5), py - (o.y + 0.5)) <= 2.5 for o in self.objects)
        if near_fire and not self._was_near_fire:
            self.trigger_event_thought("warm_by_fire")
        self._was_near_fire = near_fire

        if moved and not self.player.has_lit_torch and self.player.illumination < 0.22:
            self._dark_walk_timer += dt
            if self._dark_walk_timer >= 9.0:
                self._dark_walk_timer = 0.0
                self.trigger_event_thought("walk_in_dark")
        else:
            self._dark_walk_timer = 0.0

    def add_popup(self, wx, wy, text, color, icon=None, big=False):
        self.popups.append(FloatingPopup(wx, wy, text, color, icon, big=big))

    def drop_item_on_floor(self, item):
        if not item:
            return
        self.player.remove_item_everywhere(item)
        tx, ty = int(self.player.x), int(self.player.y)
        self.objects.append(Interactable(tx, ty, "loot", item))
        self.sfx.play("step")
        self.trigger_event_thought("drop_item", item=item.name)
        self.add_popup(self.player.x, self.player.y, f"Выброшено: {item.name}", (185, 175, 165))

    def on_player_hit(self, raw_dmg, is_magic=False):
        if getattr(self.player, "god_mode", False):
            self.add_popup(self.player.x, self.player.y, "БЕССМЕРТИЕ", (255, 225, 90))
            return
        if random.random() < self.player.dodge_chance:
            self.player.record_build_action("cunning", 0.25)
            self.add_popup(self.player.x, self.player.y, "УВОРОТ", (140, 230, 255))
            self.add_log("combat", "Уклонение от вражеской атаки!", (140, 230, 255))
            self.trigger_event_thought("combat_dodge")
            return

        if getattr(self.player, "ignite_timer", 0.0) > 0.0 and not is_magic:
            for m in self.mobs:
                if math.hypot(m.x - self.player.x, m.y - self.player.y) <= 1.95:
                    m.apply_status("burn", 2.8, self.add_popup, dmg_val=self.player.ignite_burn_dmg)

        defense = self.player.mag_defense if is_magic else self.player.phys_defense
        dmg = max(1, int(math.floor(raw_dmg - defense)))
        self.player.hp = max(0.0, self.player.hp - dmg)
        self.sfx.play("hurt")
        self.add_log("combat", f"Получен урон: -{dmg} ХП ({'магия' if is_magic else 'физ. удар'}).", (255, 110, 110))
        col = (205, 110, 255) if is_magic else (255, 85, 85)
        self.add_popup(self.player.x, self.player.y, f"-{dmg}", col)

        if self.player.hp <= 0:
            self.trigger_event_thought("death", force_important=True)
        else:
            self.check_hypochondriac_panic()
            if self.player.hp <= 7 and self.low_hp_thought_cd <= 0.0:
                self.low_hp_thought_cd = 14.0
                self.trigger_event_thought("low_hp", force_important=True)

    def get_precision_hover_target(self, target_wx, target_wy):
        px, py = self.player.x, self.player.y
        weap = self.player.equipment["right_hand"]
        reach = (weap.reach if weap else 1.55) + 0.35

        for m in self.mobs:
            if is_cursor_on_mob(m, target_wx, target_wy) and math.hypot(m.x - px, m.y - py) <= reach:
                return ("enemy", m.x, m.y, "Атака [ЛКМ]")

        for (dx, dy), door in self.dungeon.doors.items():
            cx, cy = dx + 0.5, dy + 0.5
            if math.hypot(target_wx - cx, target_wy - cy) <= 0.60 and math.hypot(px - cx, py - cy) <= 1.75:
                return ("door", cx, cy, "Дверь [ЛКМ]")

        for (lx, ly), lev in self.dungeon.levers.items():
            cx, cy = lx + 0.5, ly + 0.5
            if not lev.pulled and math.hypot(target_wx - cx, target_wy - cy) <= 0.60 and math.hypot(px - cx, py - cy) <= 1.75:
                return ("lever", cx, cy, "Рычаг [ЛКМ]")

        for obj in self.objects:
            if not obj.used and obj.kind != "trap":
                cx, cy = obj.x + 0.5, obj.y + 0.5
                if math.hypot(target_wx - cx, target_wy - cy) <= 0.58 and math.hypot(px - cx, py - cy) <= 1.70:
                    return ("object", cx, cy, "")

        return None

    def try_interact_or_melee(self, target_wx, target_wy, via_mouse=True):
        if self.player.hp <= 0 or self.inv_open:
            return
        px, py = self.player.x, self.player.y

        if via_mouse:
            enemy_under_cursor = any(
                is_cursor_on_mob(m, target_wx, target_wy)
                for m in self.mobs
            )
            if not enemy_under_cursor:
                if self._try_precise_interaction(target_wx, target_wy, max_cursor_dist=0.58):
                    return
            self._perform_melee_attack(target_wx, target_wy)
        else:
            if not self._try_precise_interaction(px, py, max_cursor_dist=1.65):
                self._perform_melee_attack(target_wx, target_wy)

    def _try_precise_interaction(self, ref_wx, ref_wy, max_cursor_dist):
        px, py = self.player.x, self.player.y

        nearby_loot = [
            obj for obj in self.objects
            if not obj.used and obj.kind == "loot"
            and math.hypot(px - (obj.x + 0.5), py - (obj.y + 0.5)) <= 1.85
            and math.hypot(ref_wx - (obj.x + 0.5), ref_wy - (obj.y + 0.5)) <= max_cursor_dist
        ]
        if nearby_loot:
            nearby_loot.sort(key=lambda o: math.hypot(ref_wx - (o.x + 0.5), ref_wy - (o.y + 0.5)))
            return self._pickup_loot_object(nearby_loot[0])

        nearby_doors = [
            ((dx, dy), door)
            for (dx, dy), door in self.dungeon.doors.items()
            if math.hypot(px - (dx + 0.5), py - (dy + 0.5)) <= 1.70
            and math.hypot(ref_wx - (dx + 0.5), ref_wy - (dy + 0.5)) <= max_cursor_dist
        ]
        if nearby_doors:
            nearby_doors.sort(key=lambda pair: math.hypot(ref_wx - (pair[0][0] + 0.5), ref_wy - (pair[0][1] + 0.5)))
            (dx, dy), door = nearby_doors[0]
            if door.locked:
                self.sfx.play("hurt")
                self.emit_noise(dx + 0.5, dy + 0.5, 4.5)
                self.trigger_event_thought("door_locked")
                self.add_popup(dx + 0.5, dy + 0.5, "ЗАПЕРТО", (255, 120, 100))
            else:
                if door.is_open:
                    if (int(px) == dx and int(py) == dy) or any(int(m.x) == dx and int(m.y) == dy for m in self.mobs):
                        self.sfx.play("step")
                        self.add_popup(dx + 0.5, dy + 0.5, "Проём занят!", (255, 195, 95))
                        return True
                    if abs(px - (dx + 0.5)) < 0.80 and abs(py - (dy + 0.5)) < 0.80:
                        if abs(px - (dx + 0.5)) >= abs(py - (dy + 0.5)):
                            self.player.x = (dx + 1.30) if px > (dx + 0.5) else (dx - 0.30)
                        else:
                            self.player.y = (dy + 1.30) if py > (dy + 0.5) else (dy - 0.30)

                door.is_open = not door.is_open
                self.dungeon.invalidate_light_cache()
                self.sfx.play("door")
                self.emit_noise(dx + 0.5, dy + 0.5, 3.8)
                if door.is_open:
                    self.trigger_event_thought("door_open")
            return True

        for (lx, ly), lev in self.dungeon.levers.items():
            cx, cy = lx + 0.5, ly + 0.5
            if not lev.pulled and math.hypot(px - cx, py - cy) <= 1.70 and math.hypot(ref_wx - cx, ref_wy - cy) <= max_cursor_dist:
                lev.pulled = True
                for d in lev.target_doors:
                    d.locked = False
                    d.is_open = True
                self.dungeon.invalidate_light_cache()
                self.sfx.play("door")
                self.emit_noise(cx, cy, 7.0)
                self.trigger_event_thought("lever_pull")
                self.add_popup(cx, cy, "ОТКРЫТО!", (130, 245, 160))
                return True

        cand_objs = [
            obj for obj in self.objects
            if not obj.used and obj.kind != "trap"
            and math.hypot(px - (obj.x + 0.5), py - (obj.y + 0.5)) <= (2.65 if obj.kind in ("npc_innkeeper", "npc_merchant") else 1.85)
            and math.hypot(ref_wx - (obj.x + 0.5), ref_wy - (obj.y + 0.5)) <= max_cursor_dist
        ]
        if not cand_objs:
            return False

        cand_objs.sort(key=lambda o: math.hypot(ref_wx - (o.x + 0.5), ref_wy - (o.y + 0.5)))
        obj = cand_objs[0]

        if obj.kind == "npc_merchant":
            self.interact_with_merchant(obj)
            return True

        if handle_mission_object_interaction(self, obj, Enemy, Interactable):
            return True

        if obj.kind == "stairs":
            danger_nearby = any(m.state == "combat" and math.hypot(m.x - px, m.y - py) <= 3.2 for m in self.mobs)
            if danger_nearby:
                self.sfx.play("hurt")
                self.trigger_event_thought("stairs_combat")
                self.add_popup(obj.x + 0.5, obj.y + 0.5, "В БОЮ!", (255, 95, 95))
                return True
            self.descend_to_next_floor()
            return True

        if obj.kind == "campfire":
            if not self.player_owns_any_torch():
                new_torch = self.make_item("pitch_torch")
                if not self.player.try_auto_equip_if_slot_empty(new_torch):
                    if not self.player.add_item_to_inventory(new_torch):
                        self.objects.append(Interactable(obj.x, obj.y, "loot", new_torch))
                self.sfx.play("torch")
                self.trigger_event_thought("campfire_take_torch")
                self.add_popup(obj.x + 0.5, obj.y + 0.5, "+Смоляной факел", (255, 200, 80))
            else:
                self.sfx.play("step")
                self.trigger_event_thought("campfire_has_torch")
            return True

        if obj.kind == "loot":
            return self._pickup_loot_object(obj)

        obj.used = True
        if obj.kind == "bookshelf":
            self.sfx.play("magic")
            self.emit_noise(obj.x + 0.5, obj.y + 0.5, 3.5)
            self.trigger_event_thought("bookshelf_read")
            if self.player.gain_xp(15):
                self.trigger_levelup_shine()
            scroll = self.roll_item_by_rarity(allowed_types=["consumable_spell"])
            if not self.player.add_item_to_inventory(scroll):
                self.objects.append(Interactable(obj.x, obj.y, "loot", scroll))
            self.add_popup(obj.x + 0.5, obj.y + 0.5, "+15 ОПЫТ / Свиток", (130, 220, 255))

        elif obj.kind == "alchemy":
            self.player.hp_bonus += 4
            self.player.hp = min(float(self.player.max_hp), self.player.hp + 10)
            pot = self.roll_item_by_rarity(allowed_types=["consumable"])
            if not self.player.add_item_to_inventory(pot):
                self.objects.append(Interactable(obj.x, obj.y, "loot", pot))
            self.sfx.play("heal")
            self.emit_noise(obj.x + 0.5, obj.y + 0.5, 4.0)
            self.trigger_event_thought("alchemy_use")
            self.add_popup(obj.x + 0.5, obj.y + 0.5, "+4 Макс.ХП / Зелье", (120, 245, 155))

        elif obj.kind == "rack":
            gear = self.roll_item_by_rarity(allowed_types=["equipment"])
            self.objects.append(Interactable(obj.x, obj.y, "loot", gear))
            self.sfx.play("ui")
            self.emit_noise(obj.x + 0.5, obj.y + 0.5, 4.5)
            self.trigger_event_thought("rack_loot", item=gear.name)
            self.add_popup(obj.x + 0.5, obj.y + 0.5, f"Выпало: {gear.name}", gear.rarity_color)

        elif obj.kind == "chest":
            # Успех взлома/выбивания — ФОНОВАЯ мысль (игрок и так видит выпавший лут!),
            # а ПРОВАЛ (`chest_fail`) — ВАЖНАЯ (объясняет, почему сундук пропал и ранил героя)!
            if random.randint(1, 20) + self.player.cunning >= 11:
                treasure = self.roll_currency_or_gem_drop(allow_gem=True, force_gem=(random.random() < 0.55))
                self.objects.append(Interactable(obj.x, obj.y, "loot", treasure))
                self.sfx.play("coin_drop")
                self.emit_noise(obj.x + 0.5, obj.y + 0.5, 4.0)
                self.trigger_event_thought("chest_pick_ok", item=treasure.name)
                self.add_popup(obj.x + 0.5, obj.y + 0.5, f"В сундуке: {treasure.name}", treasure.rarity_color)
            elif self.player.body >= 3:
                coin_drop = self.roll_currency_or_gem_drop(allow_gem=False)
                self.objects.append(Interactable(obj.x, obj.y, "loot", coin_drop))
                self.sfx.play("crit")
                self.emit_noise(obj.x + 0.5, obj.y + 0.5, 8.5)
                self.trigger_event_thought("chest_smash", item=coin_drop.name)
                self.add_popup(obj.x + 0.5, obj.y + 0.5, f"Выпало: {coin_drop.name}", coin_drop.rarity_color)
            else:
                self.player.hp = max(1.0, self.player.hp - 2)
                self.sfx.play("hurt")
                self.emit_noise(obj.x + 0.5, obj.y + 0.5, 6.0)
                self.trigger_event_thought("chest_fail", force_important=True)
                self.add_popup(obj.x + 0.5, obj.y + 0.5, "СЛОМАНО (-2 ХП)", (255, 95, 95))

        elif obj.kind == "idol":
            if self.player.mind >= 3:
                self.player.hp = min(float(self.player.max_hp), self.player.hp + 12)
                self.player.mp = min(float(self.player.max_mp), self.player.mp + 10)
                self.player.trait_vision_mod += 10
                self.sfx.play("magic")
                self.trigger_event_thought("idol_smart")
                self.add_popup(obj.x + 0.5, obj.y + 0.5, "+12 ХП / +Обзор", (110, 245, 190))
            else:
                self.sfx.play("step")
                self.trigger_event_thought("idol_dumb")
        return True

    def try_sell_gems_to_npc(self, obj, speaker_name="Скупщик Шнырь"):
        """Универсальная механика продажи всех самоцветов из инвентаря любому торговцу/NPC."""
        gems_sold = 0
        total_cp_earned = 0
        for idx in range(self.player.max_possible_slots):
            itm = self.player.inventory[idx]
            if itm and itm.type == "gem":
                gems_sold += 1
                total_cp_earned += itm.copper_value
                self.player.remove_item_everywhere(itm)

        if gems_sold <= 0:
            return False

        self.player.gold += total_cp_earned
        self.profile["bank_copper"] = self.profile.get("bank_copper", 0) + total_cp_earned
        save_profile(self.profile)
        val_str = format_copper_Trigger(total_cp_earned)
        self.sfx.play("coin_pickup")
        self.add_log("event", f"Продано самоцветов: {gems_sold} шт. Выручка +{val_str} отправлена в казну!")
        line = self.get_event_text("npc_sell_gems", speaker=speaker_name, count=gems_sold, val=val_str)
        obj.speech_text = line
        obj.speech_timer = 5.5
        self.set_thought(line, important=True)
        self.add_popup(obj.x + 0.5, obj.y + 0.5, f"+{val_str} В БАНК!", (255, 225, 80), big=True)
        return True

    def interact_with_merchant(self, obj):
        """Универсальный диалог и скупка камней у подземельного Скупщика на любом этаже и в любой кампании."""
        speaker = self.loc.get("events", {}).get("npc_merchant_name", "Скупщик Шнырь")
        if isinstance(speaker, list):
            speaker = speaker[0]
        if self.try_sell_gems_to_npc(obj, speaker_name=speaker):
            return
        lines = self.loc.get("events", {}).get("npc_merchant_greeting", ["Тащи сюда любые самоцветы!"])
        line = lines[obj.talk_index % len(lines)] if isinstance(lines, list) and lines else str(lines)
        obj.talk_index += 1
        obj.speech_text = line
        obj.speech_timer = 5.5
        self.sfx.play("mob_talk")
        self.set_thought(line, important=True)

    def _pickup_loot_object(self, obj):
        self.add_log("event", f"Подобрано: {obj.item.name}.")
        if obj.item.type == "currency_coin":
            obj.used = True
            cp_gain = obj.item.copper_value
            self.player.gold += cp_gain
            self.profile["bank_copper"] = self.profile.get("bank_copper", 0) + cp_gain
            save_profile(self.profile)
            val_str = format_copper_Trigger(cp_gain)
            self.sfx.play("coin_pickup")
            self.trigger_event_thought("pickup_coin", item=obj.item.name.lower(), val=val_str)
            self.add_popup(obj.x + 0.5, obj.y + 0.5, f"+{val_str}", (255, 215, 75))
            return True
        if obj.item.type == "bag" and obj.item.slots > self.player.unlocked_slots:
            obj.used = True
            self.use_or_equip_item(obj.item)
            self.add_popup(obj.x + 0.5, obj.y + 0.5, f"+{obj.item.name}", obj.item.rarity_color)
            return True
        if obj.item.type == "equipment" and self.player.try_auto_equip_if_slot_empty(obj.item):
            obj.used = True
            self._flush_overflow_drops(obj.x, obj.y)
            self.sfx.play("ui")
            self.trigger_event_thought("auto_equip", item=obj.item.name)
            self.add_popup(obj.x + 0.5, obj.y + 0.5, f"Надето: {obj.item.name}", obj.item.rarity_color)
        elif self.player.add_item_to_inventory(obj.item):
            obj.used = True
            self.sfx.play("coin_pickup" if obj.item.type == "gem" else "ui")
            used_cnt = sum(1 for i in range(self.player.unlocked_slots) if self.player.inventory[i] is not None)
            if obj.item.type == "gem":
                val_str = format_copper_Trigger(obj.item.copper_value)
                self.trigger_event_thought("pickup_gem", item=obj.item.name, val=val_str)
            elif used_cnt >= self.player.unlocked_slots:
                self.trigger_event_thought("bag_almost_full")
            else:
                self.trigger_event_thought("pickup", item=obj.item.name)
            self.add_popup(obj.x + 0.5, obj.y + 0.5, f"+{obj.item.name}", obj.item.rarity_color)
            self.check_hypochondriac_panic()
        else:
            # Переполненная сумка — ВАЖНАЯ реплика!
            self.trigger_event_thought("bag_full", force_important=True)
            self.sfx.play("hurt")
        return True

    def _perform_melee_attack(self, target_wx, target_wy):
        if self.player.attack_cd > 0.0 or self.player.pending_action is not None:
            return
        weap = self.player.equipment["right_hand"]
        windup = weap.windup if weap else 0.0
        atk_cd = weap.atk_cd if weap else 0.30
        self.player.attack_cd = atk_cd + windup

        if windup > 0.0:
            self.player.pending_action = {
                "kind": "melee",
                "timer": windup,
                "max_timer": windup,
                "tx": target_wx,
                "ty": target_wy
            }
        else:
            self._execute_melee_swing(target_wx, target_wy)

    def _execute_melee_swing(self, target_wx, target_wy):
        px, py = self.player.x, self.player.y
        self.emit_noise(px, py, 5.2)
        weap = self.player.equipment["right_hand"]

        style = weap.weap_style if weap else "fist"
        reach = weap.reach if weap else 1.38
        arc_deg = weap.arc_deg if weap else 50.0
        max_targets = weap.max_targets if weap else 1
        armor_pierce = weap.armor_pierce if weap else 0
        knockback = weap.knockback if weap else 0.25
        life_steal = (weap.life_steal if weap else 0) + self.player.perk_lifesteal

        origin_y = py - 0.22
        dx = target_wx - px
        dy = target_wy - origin_y
        dist = max(0.001, math.hypot(dx, dy))
        nx, ny = dx / dist, dy / dist
        base_ang = math.atan2(ny, nx)
        self.player.trigger_bump(
            nx * (0.48 if style in ("dagger", "spear") else 0.32),
            ny * (0.48 if style in ("dagger", "spear") else 0.32)
        )

        half_arc_rad = math.radians(arc_deg * 0.5)
        if style in ("dagger", "spear", "fist"):
            steps = 9 if style == "spear" else 6
            col = (180, 240, 255) if style == "spear" else (240, 240, 250)
            for i in range(1, steps + 1):
                r_step = (i / steps) * reach * 0.88
                self.particles.append(Particle(
                    px + nx * r_step, origin_y + ny * r_step,
                    nx * 2.8, ny * 2.8, col, 2.6, 0.14
                ))
        else:
            spark_count = 16 if arc_deg >= 120 else 10
            col = (255, 195, 110) if arc_deg >= 100 else (230, 240, 255)
            for i in range(spark_count):
                frac = (i / max(1, spark_count - 1)) * 2.0 - 1.0
                ang = base_ang + frac * half_arc_rad
                r_dist = reach * 0.75
                self.particles.append(Particle(
                    px + math.cos(ang) * r_dist, origin_y + math.sin(ang) * r_dist,
                    math.cos(ang) * 2.2, math.sin(ang) * 2.2, col, 3.0, 0.18
                ))

        cos_threshold = math.cos(half_arc_rad + 0.18)
        candidates = []
        for m in self.mobs:
            size_pad = 0.55 if getattr(m, "size_tiles", 1) >= 2 else 0.0
            foot_dist = math.hypot(m.x - px, m.y - py)
            torso_dist = math.hypot(m.x - px, (m.y - 0.32) - origin_y)
            md = max(0.0, min(foot_dist, torso_dist) - size_pad)
            if md <= reach + 0.25 and dungeon_los_ok(self.dungeon, px, py, m.x, m.y):
                hit_model = False
                if is_cursor_on_mob(m, target_wx, target_wy):
                    hit_model = True
                else:
                    for sample_y in (m.y, m.y - 0.30, m.y - 0.62):
                        vx_m = m.x - px
                        vy_m = sample_y - origin_y
                        proj = max(0.0, min(reach, vx_m * nx + vy_m * ny))
                        perp_dist = math.hypot(vx_m - nx * proj, vy_m - ny * proj)
                        if perp_dist <= 0.52:
                            hit_model = True
                            break
                        s_len = max(0.001, math.hypot(vx_m, vy_m))
                        if (vx_m * nx + vy_m * ny) / s_len >= cos_threshold:
                            hit_model = True
                            break

                if hit_model:
                    candidates.append((md, m))

        candidates.sort(key=lambda pair: pair[0])
        targets_to_hit = [pair[1] for pair in candidates[:max_targets]]

        for m in targets_to_hit:
            dmg, is_crit = self.player.roll_melee_damage()
            if m.state != "combat":
                dmg = int(dmg * self.player.backstab_mult)
                is_crit = True
                m.alert_to_combat(self.sfx, self.add_popup)

            eff_def = max(0, m.phys_def - armor_pierce)
            final_dmg = max(1, dmg - eff_def)
            m.hp -= final_dmg

            k_dx = m.x - px
            k_dy = m.y - py
            k_len = max(0.001, math.hypot(k_dx, k_dy))
            m.apply_knockback(k_dx / k_len, k_dy / k_len, knockback)

            if life_steal > 0:
                self.player.hp = min(float(self.player.max_hp), self.player.hp + life_steal)
                self.add_popup(self.player.x, self.player.y, f"+{life_steal}", (120, 245, 140))

            # Комбо А: каждый удар оружием в ближнем бою выбивает ману!
            if self.player.mp < self.player.max_mp:
                mp_gain = self.player.mp_on_hit * (1.5 if is_crit else 1.0)
                self.player.mp = min(float(self.player.max_mp), self.player.mp + mp_gain)

            m.hit_flash_timer = 0.12
            m.hit_flash_crit = is_crit
            self.fx.add_blood_splatter(m.x, m.y, count=6 if is_crit else 3, is_kill=False)

            if is_crit:
                self.player.record_build_action("cunning", 0.22)
                self.sfx.play("crit")
                self.fx.trigger_shake(2.0, 0.14)
                self.add_log("combat", f"Критический удар по врагу ({m.kind}): -{final_dmg} ХП!", (255, 230, 95))
                self.add_popup(m.x, m.y, f"-{final_dmg}", (255, 230, 75), big=True)
            else:
                self.player.record_build_action("body", 0.15)
                self.sfx.play("hit")
                self.add_log("combat", f"Удар по врагу ({m.kind}): -{final_dmg} ХП.")
                self.add_popup(m.x, m.y, f"-{final_dmg}", (255, 245, 230))

            self._check_mob_death(m)

        if not targets_to_hit:
            self.sfx.play("step")

    def use_or_equip_item(self, item, target_wx=None, target_wy=None, from_hotbar=False):
        if not item or self.player.hp <= 0 or self.player.pending_action is not None:
            return
        ev = self.loc["events"]

        # 1. Сначала проверяем ману: если не хватает — короткий грустный звук без надписей "КД"!
        if item.type in ("spell", "permanent_spell") and self.player.mp < item.mp_cost:
            self.sfx.play("no_mana")
            return

        # 2. Если способность на перезарядке — тихий отклик без мусорных всплывашек "КД 0.3с"
        cd_rem = self.player.cooldowns.get(item.id, 0.0)
        if cd_rem > 0.0 and item.type in ("consumable", "consumable_spell", "permanent_spell", "combat_skill"):
            self.sfx.play("ui")
            return

        if item.type == "consumable_eraser":
            self.open_oblivion_erase_modal(item)
            return

        if item.type == "consumable":
            self.player.cooldowns[item.id] = item.cooldown
            if getattr(item, "heal_hp", 0) > 0:
                heal_val = self.player.get_heal_amount(item)
                self.player.hp = min(float(self.player.max_hp), self.player.hp + heal_val)
                self.add_log("event", f"Использовано «{item.name}»: восстановлено +{heal_val} ХП.", (120, 245, 145))
                self.add_popup(self.player.x, self.player.y, f"+{heal_val}", (110, 245, 130), "heart")
                self.sfx.play("heal")
                self.player.remove_item_everywhere(item)
            elif item.id == "potion_mp":
                self.player.mp = min(float(self.player.max_mp), self.player.mp + item.power)
                self.add_log("event", f"Использовано «{item.name}»: восстановлено +{item.power} МП.", (110, 205, 255))
                self.add_popup(self.player.x, self.player.y, f"+{item.power}", (95, 195, 255), "mana")
                self.sfx.play("magic")
                self.player.remove_item_everywhere(item)
            return

        if item.type in ("consumable_spell", "combat_skill", "spell", "permanent_spell"):
            if item.type in ("spell", "permanent_spell") and self.player.mp < item.mp_cost:
                self.set_thought(ev["no_mana"])
                self.sfx.play("ui")
                return

            tx = target_wx if target_wx is not None else (self.player.x + 1.0)
            ty = target_wy if target_wy is not None else self.player.y

            if item.cast_type in ("targeted", "chain_lightning"):
                px, py = self.player.x, self.player.y
                valid_t = min(
                    (
                        m for m in self.mobs
                        if math.hypot(m.x - tx, (m.y - 0.3) - ty) <= 2.6
                        and self.dungeon.has_line_of_sight(px, py, m.x, m.y, 8.5)
                        and not self.dungeon.is_blocking_move(int(m.x), int(m.y))
                    ),
                    key=lambda m: math.hypot(m.x - tx, (m.y - 0.3) - ty),
                    default=None
                )
                if not valid_t:
                    self.add_popup(tx, ty, "Нет цели!", (195, 195, 210))
                    return

            if item.type in ("spell", "permanent_spell"):
                self.player.mp -= item.mp_cost
            self.player.cooldowns[item.id] = item.cooldown

            if item.type == "combat_skill":
                self.sfx.play("skill_windup")
            else:
                self.sfx.play("spell_windup")

            if item.windup > 0.0:
                self.player.cast_glow_color = item.color
                self.player.pending_action = {
                    "kind": "spell",
                    "item": item,
                    "timer": item.windup,
                    "max_timer": item.windup,
                    "tx": tx,
                    "ty": ty
                }
            else:
                self._execute_skill_or_spell(item, tx, ty)
            return

        elif item.type == "equipment":
            if self.player.equip_item(item):
                self._flush_overflow_drops(int(self.player.x), int(self.player.y))
                self.sfx.play("ui")
            else:
                self.trigger_event_thought("bag_full", force_important=True)
                self.sfx.play("hurt")

        elif item.type == "bag":
            if item.slots > self.player.unlocked_slots:
                self.player.unlocked_slots = item.slots
                self.player.bag_name = f"{item.name} ({item.slots} яч.)"
                self.player.remove_item_everywhere(item)
                self.trigger_event_thought("bag_upgrade", item=item.name)
                self.sfx.play("heal")

    def _flush_overflow_drops(self, drop_tx, drop_ty):
        while getattr(self.player, "overflow_drops", None):
            dropped_itm = self.player.overflow_drops.pop(0)
            self.objects.append(Interactable(int(drop_tx), int(drop_ty), "loot", dropped_itm))
            self.add_popup(drop_tx + 0.5, drop_ty + 0.5, f"На пол: {dropped_itm.name}", (200, 190, 175))

    def _has_clear_shot(self, x0, y0, x1, y1):
        """Checks both wall sightline AND solid furniture/obstacles for spells that don't ignore obstacles."""
        dist = math.hypot(x1 - x0, y1 - y0)
        steps = int(dist * 3.0) + 1
        for i in range(1, steps):
            t = i / steps
            cx, cy = int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t)
            if self.dungeon.is_blocking_move(cx, cy):
                return False
        return True

    def _execute_skill_or_spell(self, item, target_wx, target_wy):
        self.player.cast_glow_color = None
        px, py = self.player.x, self.player.y
        self.emit_noise(px, py, 7.2)
        is_combat = (item.type == "combat_skill")
        if item.type == "consumable_spell":
            total_pwr = int(math.floor(item.power * 1.65 + self.player.mag_attack * 1.5))
            self.player.record_build_action("mind", 0.30)
        elif is_combat:
            total_pwr = int(math.floor(item.power + self.player.phys_attack))
            self.player.record_build_action("cunning" if item.id in ("throw_knife", "poison_flask") else "body", 0.30)
        else:
            total_pwr = int(math.floor(item.power + self.player.mag_attack))
            self.player.record_build_action("mind", 0.35)
        c_type = getattr(item, "cast_type", "projectile")

        if item.life_steal > 0:
            self.player.hp = min(float(self.player.max_hp), self.player.hp + item.life_steal)

        if item.type == "consumable_spell":
            self.player.remove_item_everywhere(item)

        # 1. БОГ ПИРО: Воспламенение (бафф на себя + огненный след + поджог атакующих)
        if c_type == "self_ignite":
            self.sfx.play("torch")
            dur = max(1.5, float(getattr(item, "duration", 5.0)))
            self.player.ignite_timer = dur
            self.player.ignite_burn_dmg = max(1, int(math.floor(item.power + self.player.mag_attack * 0.45)))
            self.visual_fx.append({
                "kind": "fire_trail",
                "x": px, "y": py, "radius": 0.85,
                "dmg": self.player.ignite_burn_dmg,
                "color": (255, 110, 35), "timer": 2.6, "max_timer": 2.6
            })
            return

        # 2. БОГ СТРАТОС: Кольцо холода (мгновенная ледяная волна вокруг героя, игнорирует мебель, но не стены; root -> slow)
        if c_type == "frost_nova":
            self.sfx.play("magic")
            rad = float(getattr(item, "aoe_radius", 2.4))
            root_d = float(getattr(item, "status_dur", 1.2))
            self.visual_fx.append({
                "kind": "frost_nova",
                "x": px, "y": py, "radius": rad,
                "color": item.color, "timer": 0.40, "max_timer": 0.40
            })
            for m in list(self.mobs):
                if math.hypot(m.x - px, m.y - py) <= rad and self.dungeon.has_line_of_sight(px, py, m.x, m.y, rad + 0.5):
                    m.alert_to_combat(self.sfx, self.add_popup)
                    dmg = max(1, int(math.floor(total_pwr - m.mag_def)))
                    m.hp -= dmg
                    m.apply_status("root", root_d, self.add_popup)
                    m.chill_after_root = max(1.5, root_d * 1.6)
                    m.glow_timer = root_d
                    m.glow_color = (110, 225, 255)
                    self.add_popup(m.x, m.y, f"-{dmg}", item.color)
                    self._check_mob_death(m)
            return

        # 3. БОГ СТРАТОС: Удар молнии (цепочка искр по всем видимым целям с возвратом на 2-й круг!)
        if c_type == "chain_lightning":
            target_mob = min(
                (
                    m for m in self.mobs
                    if math.hypot(m.x - target_wx, (m.y - 0.3) - target_wy) <= 2.6
                    and self._has_clear_shot(px, py, m.x, m.y)
                ),
                key=lambda m: math.hypot(m.x - target_wx, (m.y - 0.3) - target_wy),
                default=None
            )
            if not target_mob:
                if item.type in ("spell", "permanent_spell"):
                    self.player.mp = min(float(self.player.max_mp), self.player.mp + item.mp_cost)
                self.player.cooldowns.pop(item.id, None)
                self.add_popup(target_wx, target_wy, "Нет цели!", (195, 195, 210))
                return

            self.sfx.play("crit")
            max_bounces = int(getattr(item, "bounces", 1))
            jump_range = float(getattr(item, "aoe_radius", 4.5))
            hit_sequence = [target_mob]
            visited_in_round = {target_mob}
            curr_m = target_mob

            for _ in range(max_bounces):
                # Ищем ближайшего ещё не поражённого в этом круге врага в прямой видимости без препятствий
                unvisited = [
                    m for m in self.mobs
                    if m is not curr_m and m not in visited_in_round and m.hp > 0
                    and math.hypot(m.x - curr_m.x, m.y - curr_m.y) <= jump_range
                    and self._has_clear_shot(curr_m.x, curr_m.y, m.x, m.y)
                ]
                if not unvisited:
                    # Все доступные цели поражены по разу — начинаем новый круг по живым соседям (если цель не одна!)
                    visited_in_round = {curr_m}
                    unvisited = [
                        m for m in self.mobs
                        if m is not curr_m and m.hp > 0
                        and math.hypot(m.x - curr_m.x, m.y - curr_m.y) <= jump_range
                        and self._has_clear_shot(curr_m.x, curr_m.y, m.x, m.y)
                    ]
                if not unvisited:
                    break
                nxt_m = min(unvisited, key=lambda m: math.hypot(m.x - curr_m.x, m.y - curr_m.y))
                hit_sequence.append(nxt_m)
                visited_in_round.add(nxt_m)
                curr_m = nxt_m

            chain_pts = [(px, py - 0.25)] + [(m.x, m.y - 0.3) for m in hit_sequence]
            self.visual_fx.append({
                "kind": "chain_lightning",
                "points": chain_pts,
                "color": item.color,
                "timer": 0.36, "max_timer": 0.36
            })
            for m in hit_sequence:
                if m in self.mobs:
                    m.alert_to_combat(self.sfx, self.add_popup)
                    dmg = max(1, int(math.floor(total_pwr - m.mag_def)))
                    m.hp -= dmg
                    m.glow_timer = 0.85
                    m.glow_color = (150, 240, 255)
                    self.add_popup(m.x, m.y, f"-{dmg}", item.color)
                    self._check_mob_death(m)
            return

        # 4. БОГ ПЕРСЕФОНА: Омоложение (мгновенный хил + ускоряющаяся регенерация со светлячками)
        if c_type == "self_rejuvenation":
            self.sfx.play("heal")
            dur = max(1.0, float(getattr(item, "duration", 5.0)))
            instant_heal = max(2, int(math.floor(total_pwr * 0.38)))
            rem_heal = max(2.0, float(total_pwr - instant_heal))
            self.player.hp = min(float(self.player.max_hp), self.player.hp + instant_heal)
            self.player.rejuv_timer = dur
            self.player.rejuv_rate = rem_heal / dur
            self.add_popup(px, py, f"+{instant_heal}", (115, 245, 145), "heart")
            return

        # 5. БОГ ПЕРСЕФОНА: Опутывание (корни в области курсора, враги стоят, но могут бить/стрелять)
        if c_type == "entangle_cursor":
            self.sfx.play("magic")
            rad = float(getattr(item, "aoe_radius", 2.1))
            root_d = float(getattr(item, "status_dur", 2.2))
            self.visual_fx.append({
                "kind": "entangle_zone",
                "x": target_wx, "y": target_wy, "radius": rad,
                "color": item.color, "timer": 0.45, "max_timer": 0.45
            })
            for m in list(self.mobs):
                if math.hypot(m.x - target_wx, (m.y - 0.2) - target_wy) <= rad:
                    m.alert_to_combat(self.sfx, self.add_popup)
                    dmg = max(1, int(math.floor(total_pwr - m.mag_def)))
                    m.hp -= dmg
                    m.apply_status("root", root_d, self.add_popup)
                    self.add_popup(m.x, m.y, f"-{dmg}", item.color)
                    self._check_mob_death(m)
            return

        if c_type == "aoe_self":
            self.sfx.play("crit")
            self.visual_fx.append({
                "kind": "whirlwind_slash",
                "x": px, "y": py, "radius": 2.15,
                "color": item.color, "timer": 0.28, "max_timer": 0.28
            })
            for m in list(self.mobs):
                if math.hypot(m.x - px, m.y - py) <= 2.25:
                    m.alert_to_combat(self.sfx, self.add_popup)
                    dmg = max(1, int(math.floor(total_pwr - m.phys_def)))
                    m.hp -= dmg
                    k_dx, k_dy = m.x - px, m.y - py
                    kl = max(0.001, math.hypot(k_dx, k_dy))
                    m.apply_knockback(k_dx / kl, k_dy / kl, item.knockback)
                    m.apply_status(item.status, item.status_dur, self.add_popup)
                    self.add_popup(m.x, m.y, f"-{dmg}", item.color)
                    self._check_mob_death(m)
            return

        if c_type == "slam_cone":
            self.sfx.play("crit")
            dx, dy = target_wx - px, target_wy - (py - 0.2)
            base_a = math.atan2(dy, dx)
            self.visual_fx.append({
                "kind": "slam_wave",
                "x": px, "y": py - 0.15, "angle": base_a,
                "color": item.color, "timer": 0.30, "max_timer": 0.30
            })
            for m in list(self.mobs):
                if math.hypot(m.x - px, m.y - py) <= 2.55:
                    m.alert_to_combat(self.sfx, self.add_popup)
                    m.hp -= total_pwr
                    k_dx, k_dy = m.x - px, m.y - py
                    kl = max(0.001, math.hypot(k_dx, k_dy))
                    m.apply_knockback(k_dx / kl, k_dy / kl, item.knockback)
                    m.apply_status(item.status, item.status_dur, self.add_popup)
                    self.add_popup(m.x, m.y, f"-{total_pwr}", item.color)
                    self._check_mob_death(m)
            return

        if c_type == "beam":
            self.sfx.play("magic")
            origin_y = py - 0.22
            dx, dy = target_wx - px, target_wy - origin_y
            d = max(0.001, math.hypot(dx, dy))
            nx, ny = dx / d, dy / d
            end_x, end_y = px, origin_y
            for step_i in range(1, 40):
                cx = px + nx * (step_i * 0.22)
                cy = origin_y + ny * (step_i * 0.22)
                if self.dungeon.is_blocking_move(int(cx), int(cy)):
                    end_x, end_y = cx, cy
                    break
                end_x, end_y = cx, cy

            self.visual_fx.append({
                "kind": "beam",
                "x0": px, "y0": origin_y, "x1": end_x, "y1": end_y,
                "color": item.color, "timer": 0.32, "max_timer": 0.32
            })
            beam_len = math.hypot(end_x - px, end_y - origin_y)
            for m in list(self.mobs):
                vx_m, vy_m = m.x - px, (m.y - 0.25) - origin_y
                proj = max(0.0, min(beam_len, vx_m * nx + vy_m * ny))
                if math.hypot(vx_m - nx * proj, vy_m - ny * proj) <= 0.62:
                    m.alert_to_combat(self.sfx, self.add_popup)
                    dmg = max(1, int(math.floor(total_pwr - m.mag_def)))
                    m.hp -= dmg
                    m.apply_status(item.status, item.status_dur, self.add_popup)
                    self.add_popup(m.x, m.y, f"-{dmg}", item.color)
                    self._check_mob_death(m)
            return

        if c_type == "targeted":
            target_mob = min(
                (m for m in self.mobs if math.hypot(m.x - target_wx, (m.y - 0.3) - target_wy) <= 2.4 and dungeon_los_ok(self.dungeon, px, py, m.x, m.y)),
                key=lambda m: math.hypot(m.x - target_wx, (m.y - 0.3) - target_wy),
                default=None
            )
            if not target_mob:
                if item.type in ("spell", "permanent_spell"):
                    self.player.mp = min(float(self.player.max_mp), self.player.mp + item.mp_cost)
                self.player.cooldowns.pop(item.id, None)
                self.add_popup(target_wx, target_wy, "Нет цели!", (195, 195, 210))
                return
            self.sfx.play("magic")
            target_mob.alert_to_combat(self.sfx, self.add_popup)
            dmg = max(1, int(math.floor(total_pwr - target_mob.mag_def)))
            target_mob.hp -= dmg
            target_mob.apply_status(item.status, item.status_dur, self.add_popup)
            self._check_mob_death(target_mob)
            return

        if c_type == "aoe_cursor":
            self.sfx.play("magic")
            rad = item.aoe_radius
            if item.status == "poison" and hasattr(self, "fx") and self.fx:
                self.fx.add_gas_cloud(target_wx, target_wy, radius=rad + 0.35, duration=max(4.5, item.status_dur + 1.5), kind="poison", dmg=max(2, total_pwr // 3))
            self.visual_fx.append({
                "kind": "aoe_ring",
                "x": target_wx, "y": target_wy, "radius": rad,
                "color": item.color, "timer": 0.35, "max_timer": 0.35
            })
            for m in list(self.mobs):
                if math.hypot(m.x - target_wx, (m.y - 0.2) - target_wy) <= rad:
                    m.alert_to_combat(self.sfx, self.add_popup)
                    dmg = max(1, int(math.floor(total_pwr - m.mag_def)))
                    m.hp -= dmg
                    m.apply_status(item.status, item.status_dur, self.add_popup, dmg_val=max(2, total_pwr // 3))
                    self.add_popup(m.x, m.y, f"-{dmg}", item.color)
                    self._check_mob_death(m)
            return

        is_dagger = (item.id == "throw_knife" or is_combat or item.icon in ("weapon_cleaver", "weapon_sword"))
        self._fire_spell_bolt(
            total_pwr, item.color, target_wx, target_wy,
            speed=item.proj_speed, status=item.status, status_dur=item.status_dur, knockback=item.knockback,
            visual_kind="spinning_dagger" if is_dagger else "orb",
            emits_light=not is_dagger
        )

    def _fire_spell_bolt(self, mag_dmg, color, target_wx, target_wy, speed=9.2, status=None, status_dur=0.0, knockback=0.0, visual_kind="orb", emits_light=True):
        if target_wx is None or target_wy is None:
            target_wx, target_wy = self.player.x + 1.0, self.player.y
        dx = target_wx - self.player.x
        dy = target_wy - (self.player.y - 0.2)
        d = max(0.001, math.hypot(dx, dy))
        self.sfx.play("hit" if visual_kind == "spinning_dagger" else "magic")
        self.projectiles.append(Projectile(
            self.player.x, self.player.y - 0.2, dx / d, dy / d,
            speed=speed, mag_dmg=mag_dmg, color=color, from_player=True,
            status=status, status_dur=status_dur, knockback=knockback,
            visual_kind=visual_kind, emits_light=emits_light
        ))

    def _check_mob_death(self, m):
        if m.hp <= 0 and m in self.mobs:
            self.mobs.remove(m)
            self.add_log("combat", f"Враг повержен: {m.kind} (+{m.xp_value} опыта).", (135, 245, 160))
            self.fx.add_blood_splatter(m.x, m.y, count=10, is_kill=True)
            drop_tx, drop_ty = int(m.x), int(m.y)
            if getattr(m, "is_boss", False):
                # С Босса высыпается платина и редкий самоцвет!
                plat = self.make_item("coin_platinum")
                gem_boss = self.make_item(random.choice(["gem_ruby", "gem_diamond"]))
                self.objects.append(Interactable(drop_tx, drop_ty, "loot", plat))
                self.objects.append(Interactable(max(1, drop_tx - 1), drop_ty, "loot", gem_boss))
                self.sfx.play("coin_drop")
            else:
                # С обычных мобов деньги падают нечасто, а самоцветы — в 10 раз реже!
                drop_chance = 0.44 if m.is_ranged else 0.28
                if random.random() < drop_chance:
                    loot_drop = self.roll_currency_or_gem_drop(allow_gem=True, gem_mult=0.1)
                    self.objects.append(Interactable(drop_tx, drop_ty, "loot", loot_drop))
                    self.sfx.play("coin_drop")

            # Комбо Б: из убитого врага на пол вылетает эфирный осколок маны (живёт 4 секунды!)
            shard_count = 3 if getattr(m, "is_boss", False) else 1
            for _ in range(shard_count):
                s_ang = random.uniform(0, 6.28)
                s_dist = random.uniform(0.35, 0.95)
                sx_cand = m.x + math.cos(s_ang) * s_dist
                sy_cand = m.y + math.sin(s_ang) * s_dist
                if self.dungeon.is_blocking_move(int(sx_cand), int(sy_cand)):
                    sx_cand, sy_cand = m.x, m.y
                self.visual_fx.append({
                    "kind": "mana_shard",
                    "x": sx_cand, "y": sy_cand,
                    "mp": 2 + (1 if m.is_ranged else 0),
                    "color": (85, 205, 255),
                    "timer": 4.2, "max_timer": 4.2
                })

            if getattr(m, "is_boss", False):
                if not self.profile.get("rat_king_defeated", False):
                    self.profile["rat_king_defeated"] = True
                    save_profile(self.profile)
                    self.add_popup(m.x, m.y - 1.25, "ОТКРЫТ КРЫСОЛЮД!", (125, 255, 155), big=True)
                defeat_pool = get_mission_texts(self.loc).get("boss_defeat", ["Крысиный Король повержен!"])
                # Победа над боссом — ВАЖНАЯ реплика!
                self.set_thought(self.pick_text(defeat_pool, "boss_defeat"), important=True)
                self.add_popup(m.x, m.y - 0.8, "БОСС ПОВЕРЖЕН!", (255, 215, 65))
                self.objects.append(Interactable(int(m.x), int(m.y), "stairs"))
            else:
                # Реплика при убийстве обычного моба — ФОНОВАЯ (шанс 22%, не чаще раза в 6 сек)!
                if self.can_trigger_background_thought(chance=0.22):
                    self.set_thought(self.pick_text(self.player.thoughts["kill"], "player_kill"), important=False, chance=1.0)

            if self.player.gain_xp(m.xp_value):
                self.trigger_levelup_shine()

            for _ in range(14):
                ang = random.uniform(0, 6.28)
                spd = random.uniform(0.8, 3.2)
                self.particles.append(Particle(m.x, m.y, math.cos(ang) * spd, math.sin(ang) * spd, (220, 210, 195), 3.0, 0.45))

    def trigger_levelup_shine(self):
        self.sfx.play("levelup")
        self.trigger_event_thought("level_up")
        self.add_popup(self.player.x, self.player.y - 0.65, "НОВЫЙ УРОВЕНЬ!", (255, 230, 85))
        self.player.levelup_delay_timer = 0.55
        self.player.shine_timer = 0.95
        for _ in range(24):
            ang = random.uniform(0, 6.28)
            spd = random.uniform(0.6, 2.4)
            self.particles.append(Particle(
                self.player.x + math.cos(ang) * 0.25,
                self.player.y + math.sin(ang) * 0.25,
                math.cos(ang) * spd,
                math.sin(ang) * spd - 1.4,
                (255, 225, 90), 3.2, 0.55
            ))


def main():
    pygame.init()
    try:
        screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), vsync=1)
    except Exception:
        screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Dungeon Crawler — Mission 1: The Rat Cellar")
    clock = pygame.time.Clock()

    game = GameController()
    running = True

    while running:
        dt = min(0.05, clock.tick(0) / 1000.0)
        t = pygame.time.get_ticks() * 0.005
        mouse_pos = pygame.mouse.get_pos()

        if game.in_main_menu:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                else:
                    game.main_menu.handle_event(event, mouse_pos)
            if not running:
                break
            game.main_menu.update(dt)
            game.main_menu.render(screen, dt, mouse_pos)
            pygame.display.flip()
            continue

        world_mx = (mouse_pos[0] / SCALE + game.cam_x) / TILE_W
        world_my = (mouse_pos[1] / SCALE + game.cam_y) / TILE_H

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if hasattr(game, "fx") and game.fx:
                if game.fx.handle_event(event, Enemy, Interactable):
                    continue

            if hasattr(game, "dev_panel") and game.dev_panel:
                if game.dev_panel.handle_event(event, game, world_mx, world_my):
                    continue

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if game.inv_open:
                        game.inv_open = False
                    else:
                        game.in_main_menu = True
                    game.sfx.play("ui")
                    continue
                elif event.key == pygame.K_r:
                    game.reset_run()
                elif event.key in (pygame.K_i, pygame.K_TAB):
                    game.inv_open = not game.inv_open
                    if not game.inv_open:
                        game.journal_open = False
                    game.drag_item = None
                    game.drag_source = None
                    game.sfx.play("ui")
                elif event.key == pygame.K_j:
                    if not game.inv_open:
                        game.inv_open = True
                        game.journal_open = True
                    else:
                        game.journal_open = not game.journal_open
                    game.drag_item = None
                    game.drag_source = None
                    game.sfx.play("ui")
                elif event.key == pygame.K_f:
                    game.trigger_torch_toggle()
                elif event.key == pygame.K_SPACE:
                    game.try_interact_or_melee(world_mx, world_my, via_mouse=False)
                elif event.key in (pygame.K_q, pygame.K_e):
                    if not game.inv_open and not game.levelup_choices:
                        ab_idx = 0 if event.key == pygame.K_q else 1
                        game.use_or_equip_item(game.player.ability_slots[ab_idx], world_mx, world_my, from_hotbar=True)
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                    slot_idx = event.key - pygame.K_1
                    if game.levelup_choices and slot_idx < len(game.levelup_choices["choices"]):
                        game.select_perk_choice(slot_idx)
                        continue
                    if slot_idx < 4:
                        assigned = False
                        if game.inv_open:
                            for i, sr in enumerate(game.renderer.inv_slot_rects):
                                if i < game.player.unlocked_slots and sr.collidepoint(mouse_pos):
                                    itm = game.player.inventory[i]
                                    if itm and itm.type in ("consumable", "consumable_spell", "consumable_eraser"):
                                        game.player.hotbar[slot_idx] = itm
                                        game.sfx.play("ui")
                                        assigned = True
                                    break
                        if not assigned and not game.inv_open:
                            game.use_or_equip_item(game.player.hotbar[slot_idx], world_mx, world_my, from_hotbar=True)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if game.levelup_choices:
                        for idx, card_r in enumerate(game.renderer.perk_card_rects):
                            if card_r.collidepoint(mouse_pos):
                                game.select_perk_choice(idx)
                                break
                        continue
                    if game.renderer.bag_btn_rect.collidepoint(mouse_pos):
                        game.inv_open = not game.inv_open
                        game.drag_item = None
                        game.drag_source = None
                        game.sfx.play("ui")
                    else:
                        clicked_ui = False
                        for i, ar in enumerate(game.renderer.ability_rects):
                            if ar.collidepoint(mouse_pos):
                                game.use_or_equip_item(game.player.ability_slots[i], world_mx, world_my, from_hotbar=True)
                                clicked_ui = True
                                break
                        for i, hr in enumerate(game.renderer.hotbar_rects):
                            if hr.collidepoint(mouse_pos):
                                game.use_or_equip_item(game.player.hotbar[i], world_mx, world_my, from_hotbar=True)
                                clicked_ui = True
                                break
                        if game.inv_open:
                            clicked_ui = True
                            if game.renderer.journal_btn_rect.collidepoint(mouse_pos):
                                game.journal_open = not game.journal_open
                                game.journal_scroll = 0
                                game.drag_item = None
                                game.drag_source = None
                                game.sfx.play("ui")
                            elif game.journal_open:
                                for f_key, f_rect in game.renderer.journal_filter_rects.items():
                                    if f_rect.collidepoint(mouse_pos):
                                        game.journal_filters[f_key] = not game.journal_filters.get(f_key, True)
                                        game.journal_scroll = 0
                                        game.sfx.play("ui")
                                        break
                            else:
                                for s_key, s_rect in game.renderer.equip_slot_rects.items():
                                    if s_key != "bag" and s_rect.collidepoint(mouse_pos):
                                        itm = game.player.equipment.get(s_key)
                                        if itm:
                                            game.drag_item = itm
                                            game.drag_source = ("equip", s_key)
                                        break
                                for i, sr in enumerate(game.renderer.inv_slot_rects):
                                    if i < game.player.unlocked_slots and sr.collidepoint(mouse_pos):
                                        itm = game.player.inventory[i]
                                        if itm:
                                            game.drag_item = itm
                                            game.drag_source = ("pocket", i)
                                        break
                        if not clicked_ui and mouse_pos[1] < VIEW_H * SCALE:
                            game.try_interact_or_melee(world_mx, world_my, via_mouse=True)

                elif event.button == 3:
                    if game.levelup_choices and game.levelup_choices.get("mode") == "erase":
                        game.levelup_choices = None
                        game.sfx.play("ui")
                    elif game.inv_open:
                        for i, sr in enumerate(game.renderer.inv_slot_rects):
                            if i < game.player.unlocked_slots and sr.collidepoint(mouse_pos):
                                itm = game.player.inventory[i]
                                if itm:
                                    game.drop_item_on_floor(itm)
                                break
                    elif game.player.ability_slots[0]:
                        game.use_or_equip_item(game.player.ability_slots[0], world_mx, world_my, from_hotbar=True)

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if game.drag_item:
                    dropped = False
                    for i, hr in enumerate(game.renderer.hotbar_rects):
                        if hr.collidepoint(mouse_pos) and game.drag_item.type in ("consumable", "consumable_spell", "consumable_eraser"):
                            game.player.hotbar[i] = game.drag_item
                            game.sfx.play("ui")
                            dropped = True
                            break

                    if not dropped and game.inv_open:
                        if not game.renderer.modal_rect.collidepoint(mouse_pos):
                            game.drop_item_on_floor(game.drag_item)
                            dropped = True
                        else:
                            for s_key, s_rect in game.renderer.equip_slot_rects.items():
                                if s_key != "bag" and s_rect.collidepoint(mouse_pos):
                                    if game.drag_source == ("equip", s_key):
                                        game.player.unequip_slot(s_key)
                                        game.sfx.play("ui")
                                    elif game.drag_item.type == "equipment":
                                        slot_match = (game.drag_item.slot == s_key) or (game.drag_item.slot == "ring" and s_key in ("ring_1", "ring_2"))
                                        if slot_match:
                                            game.use_or_equip_item(game.drag_item)
                                    dropped = True
                                    break

                            if not dropped:
                                for i, sr in enumerate(game.renderer.inv_slot_rects):
                                    if i < game.player.unlocked_slots and sr.collidepoint(mouse_pos):
                                        if game.drag_source == ("pocket", i):
                                            game.use_or_equip_item(game.drag_item)
                                        elif game.drag_source and game.drag_source[0] == "pocket":
                                            src_i = game.drag_source[1]
                                            game.player.swap_inventory_slots(src_i, i)
                                            game.sfx.play("ui")
                                        elif game.drag_source and game.drag_source[0] == "equip":
                                            eq_slot = game.drag_source[1]
                                            target_itm = game.player.inventory[i]
                                            if target_itm is None:
                                                game.player.inventory[i] = game.drag_item
                                                game.player.equipment[eq_slot] = None
                                                game.sfx.play("ui")
                                            elif target_itm.type == "equipment" and (target_itm.slot == eq_slot or (target_itm.slot == "ring" and eq_slot in ("ring_1", "ring_2"))):
                                                game.player.equipment[eq_slot] = target_itm
                                                game.player.inventory[i] = game.drag_item
                                                game.sfx.play("ui")
                                        break
                    game.drag_item = None
                    game.drag_source = None

            elif event.type == pygame.MOUSEWHEEL:
                if game.inv_open and game.journal_open:
                    game.journal_scroll = max(0, game.journal_scroll + event.y * 3)

        # --- REALTIME UPDATE ---
        game.update_typewriter(dt)

        if game.levelup_choices and game.levelup_choices.get("lock_timer", 0.0) > 0.0:
            game.levelup_choices["lock_timer"] = max(0.0, game.levelup_choices["lock_timer"] - dt)

        if game.player.levelup_delay_timer > 0.0:
            game.player.levelup_delay_timer = max(0.0, game.player.levelup_delay_timer - dt)
            if random.random() < 0.65:
                rx = game.player.x + random.uniform(-0.35, 0.35)
                ry = game.player.y + random.uniform(-0.2, 0.2)
                game.particles.append(Particle(rx, ry, 0.0, -2.2, (255, 235, 110), 2.8, 0.35))
            if game.player.levelup_delay_timer <= 0.0 and not game.levelup_choices and game.player.pending_perk_rolls > 0:
                game.roll_perk_choices()

        for obj in game.objects:
            if getattr(obj, "speech_timer", 0.0) > 0.0:
                obj.speech_timer = max(0.0, obj.speech_timer - dt)
                if obj.speech_timer <= 0.0:
                    obj.speech_text = None

        dev_open = getattr(getattr(game, "dev_panel", None), "is_open", False)

        if game.player.hp > 0 and not game.inv_open and not game.levelup_choices and not dev_open:
            keys = pygame.key.get_pressed()
            dx = (1 if (keys[pygame.K_d] or keys[pygame.K_RIGHT]) else 0) - (1 if (keys[pygame.K_a] or keys[pygame.K_LEFT]) else 0)
            dy = (1 if (keys[pygame.K_s] or keys[pygame.K_DOWN]) else 0) - (1 if (keys[pygame.K_w] or keys[pygame.K_UP]) else 0)

            moved = game.player.move_realtime(dx, dy, dt, game.dungeon)
            if moved:
                game.world_active = True
                if game.player.step_sound_cd <= 0.0:
                    game.player.step_sound_cd = 0.28
                    t_step = game.dungeon.grid[int(game.player.y)][int(game.player.x)]
                    if t_step == 2:
                        game.sfx.play("step_water")
                        game.fx.add_water_ripple(game.player.x, game.player.y)
                        for _ in range(3):
                            ang = random.uniform(0, 6.28)
                            game.particles.append(Particle(game.player.x, game.player.y, math.cos(ang) * 1.4, math.sin(ang) * 1.4 - 0.8, (115, 200, 245), 2.2, 0.22))
                    elif t_step == 4:
                        game.sfx.play("step_wood")
                    elif t_step == 0:
                        game.sfx.play("step_stone")
                    else:
                        game.sfx.play("step_dirt")

                # Воспламенение Пиро: при ходьбе за спиной игрока остаётся горящий след!
                if getattr(game.player, "ignite_timer", 0.0) > 0.0:
                    game.player.ignite_trail_tick -= dt
                    if game.player.ignite_trail_tick <= 0.0:
                        game.player.ignite_trail_tick = 0.18
                        game.visual_fx.append({
                            "kind": "fire_trail",
                            "x": game.player.x, "y": game.player.y,
                            "radius": 0.72,
                            "dmg": game.player.ignite_burn_dmg,
                            "color": (255, 110, 35),
                            "timer": 2.4, "max_timer": 2.4
                        })

        if game.player.hp > 0 and not game.inv_open and not game.levelup_choices and not dev_open:
            if game.player.pending_action is not None:
                pa = game.player.pending_action
                pa["timer"] -= dt
                if pa["timer"] <= 0.0:
                    game.player.pending_action = None
                    game.world_active = True
                    if pa["kind"] == "melee":
                        game._execute_melee_swing(pa["tx"], pa["ty"])
                    elif pa["kind"] == "spell":
                        game._execute_skill_or_spell(pa["item"], pa["tx"], pa["ty"])
                    elif pa["kind"] == "light_torch":
                        game.player.torch_on = True
                        game.sfx.play("torch")
                        game.emit_noise(game.player.x, game.player.y, 6.8)
                        for _ in range(10):
                            ang = random.uniform(0, 6.28)
                            game.particles.append(Particle(
                                game.player.x, game.player.y - 0.25,
                                math.cos(ang) * 1.8, math.sin(ang) * 1.8 - 1.0,
                                (255, 200, 75), 2.8, 0.28
                            ))

        if game.player.hp > 0 and not game.inv_open and not game.levelup_choices and not dev_open and game.world_active:
            game.update_auto_perks(dt)

            # Бонус Пиромана: рядом с костром, камином или жаровней кулдауны тикают на 30% быстрее!
            if getattr(game.player, "quirk", "none") == "pyromaniac" and game.player.cooldowns:
                near_fire = any(math.hypot(game.player.x - (br["x"] + 0.5), game.player.y - (br["y"] + 0.5)) <= 3.5 for br in game.dungeon.braziers)
                if not near_fire:
                    near_fire = any(o.kind in ("campfire", "fireplace") and math.hypot(game.player.x - (o.x + 0.5), game.player.y - (o.y + 0.5)) <= 3.5 for o in game.objects)
                if near_fire:
                    for ck in list(game.player.cooldowns.keys()):
                        game.player.cooldowns[ck] = max(0.0, game.player.cooldowns[ck] - dt * 0.30)

            game.update_world_reactions(dt, moved=moved)

            for obj in game.objects:
                if not obj.used and obj.kind == "trap":
                    if math.hypot(game.player.x - (obj.x + 0.5), game.player.y - (obj.y + 0.5)) <= 0.55:
                        obj.used = True
                        myopic_bonus = 4 if getattr(game.player, "quirk", "none") == "myopic" else 0
                        if random.randint(1, 20) + game.player.cunning + myopic_bonus >= 13:
                            game.sfx.play("ui")
                            if game.player.gain_xp(8):
                                game.trigger_levelup_shine()
                            # Успех обезвреживания — ФОНОВАЯ мысль (шанс 30%, не чаще раза в 6 сек)
                            game.trigger_event_thought("trap_disarm")
                            game.add_popup(obj.x + 0.5, obj.y + 0.5, "ОБЕЗВРЕЖЕНО (+8 XP)", (130, 240, 175))
                        else:
                            game.on_player_hit(random.randint(5, 8), is_magic=False)
                            game.emit_noise(obj.x + 0.5, obj.y + 0.5, 6.0)
                            # Провал на ловушке — ВАЖНАЯ мысль (100% объясняет, откуда прилетел урон!)
                            game.trigger_event_thought("trap_hit", force_important=True)

            game.ambient_timer -= dt
            if game.ambient_timer <= 0.0:
                game.ambient_timer = random.uniform(45.0, 75.0)
                if game.can_trigger_background_thought(chance=0.55):
                    game.set_thought(game.pick_text(game.player.thoughts["ambient"], "player_ambient"), important=False, chance=1.0)

            for m in list(game.mobs):
                m.update_ai(dt, game.player, game.dungeon, game.mobs, game.projectiles, game.sfx, game.add_popup, game.on_player_hit)
                # Если враг наступил в огненный след Воспламенения Пиро — он поджигается!
                for vfx in game.visual_fx:
                    if vfx["kind"] == "fire_trail" and math.hypot(m.x - vfx["x"], m.y - vfx["y"]) <= vfx["radius"]:
                        m.apply_status("burn", 2.4, game.add_popup, dmg_val=vfx["dmg"])
                        break
                if getattr(m, "pending_pentagram", False):
                    m.pending_pentagram = False
                    p_dmg = random.randint(m.dmg_min + 3, m.dmg_max + 5)
                    game.sfx.play("magic")
                    game.visual_fx.append({
                        "kind": "blood_pentagram",
                        "x": game.player.x,
                        "y": game.player.y,
                        "radius": 1.15 if not m.is_boss else 1.40,
                        "dmg": p_dmg,
                        "color": (245, 40, 65),
                        "timer": 0.50,
                        "max_timer": 0.50
                    })
                if m.hp <= 0:
                    game._check_mob_death(m)

            for pr in list(game.projectiles):
                if not pr.update(dt, game.dungeon, game.particles):
                    game.projectiles.remove(pr)
                    continue

                if pr.from_player:
                    for m in list(game.mobs):
                        if is_cursor_on_mob(m, pr.wx, pr.wy):
                            m.alert_to_combat(game.sfx, game.add_popup)
                            dmg = max(1, int(math.floor(pr.mag_dmg - m.mag_def)))
                            m.hp -= dmg
                            m.hit_flash_timer = 0.11
                            m.hit_flash_crit = False
                            game.fx.add_blood_splatter(m.x, m.y, count=3, is_kill=False)
                            if pr.knockback > 0:
                                v_len = max(0.001, math.hypot(pr.vx, pr.vy))
                                m.apply_knockback(pr.vx / v_len, pr.vy / v_len, pr.knockback)
                            if pr.status:
                                m.apply_status(pr.status, pr.status_dur, game.add_popup, dmg_val=max(2, dmg // 3))
                            game.sfx.play("hit")
                            game.add_popup(m.x, m.y, f"-{dmg}", pr.color)
                            game._check_mob_death(m)
                            if pr in game.projectiles:
                                game.projectiles.remove(pr)
                            break
                else:
                    if math.hypot(game.player.x - pr.wx, game.player.y - pr.wy) <= 0.55:
                        game.on_player_hit(pr.mag_dmg, is_magic=True)
                        if pr in game.projectiles:
                            game.projectiles.remove(pr)

        evt_code = game.player.update_timers(dt)
        if evt_code == "torch_burned_out":
            game.sfx.play("hurt")
            game.trigger_event_thought("torch_burned_out", force_important=True)

        game.fx.update(dt, game.player, game.dungeon, game.mobs, game.add_popup)
        sh_x, sh_y = game.fx.shake_offset
        target_cam_x = max(0.0, min(float(MAP_COLS * TILE_W - VIEW_W), game.player.x * TILE_W - VIEW_W * 0.5)) + sh_x
        target_cam_y = max(0.0, min(float(MAP_ROWS * TILE_H - VIEW_H), game.player.y * TILE_H - VIEW_H * 0.5)) + sh_y
        game.cam_x += (target_cam_x - game.cam_x) * min(1.0, 10.0 * dt)
        game.cam_y += (target_cam_y - game.cam_y) * min(1.0, 10.0 * dt)

        world_ox = game.player.x * TILE_W
        world_oy = game.player.y * TILE_H
        fov_mask, visible_tiles, player_open_tiles = game.dungeon.compute_nox_fov(world_ox, world_oy, game.cam_x, game.cam_y)
        game.current_visible_tiles = visible_tiles
        game.player.update_illumination(game.dungeon.braziers, game.dungeon.room_lights, game.objects, player_open_tiles)

        game.particles = [pt for pt in game.particles if pt.update(dt)]
        game.popups = [p for p in game.popups if p.update(dt)]
        for vfx in list(game.visual_fx):
            if vfx["kind"] in ("blood_pentagram", "mana_shard") and (game.inv_open or game.levelup_choices or dev_open):
                continue
            if vfx["kind"] == "mana_shard" and game.player.hp > 0:
                d_sh = math.hypot(game.player.x - vfx["x"], game.player.y - vfx["y"])
                magnet_r = 1.45 if game.player.mp_shard_bonus > 0 else 1.05
                if d_sh <= magnet_r and d_sh > 0.01:
                    # Плавное притягивание осколка к герою на близкой дистанции
                    vfx["x"] += ((game.player.x - vfx["x"]) / d_sh) * 5.5 * dt
                    vfx["y"] += ((game.player.y - vfx["y"]) / d_sh) * 5.5 * dt
                if d_sh <= 0.58:
                    mp_restore = int(vfx["mp"] + game.player.mp_shard_bonus)
                    game.player.mp = min(float(game.player.max_mp), game.player.mp + mp_restore)
                    game.sfx.play("magic")
                    for _ in range(7):
                        ang = random.uniform(0, 6.28)
                        game.particles.append(Particle(vfx["x"], vfx["y"], math.cos(ang) * 1.8, math.sin(ang) * 1.8, (95, 225, 255), 2.5, 0.28))
                    game.visual_fx.remove(vfx)
                    continue
            vfx["timer"] -= dt
            if vfx["timer"] <= 0.0:
                game.visual_fx.remove(vfx)
                if vfx["kind"] == "fire_trail":
                    game.fx.add_scorch_mark(vfx["x"], vfx["y"], 0.42)
                elif vfx["kind"] == "blood_pentagram" and game.player.hp > 0:
                    game.fx.add_scorch_mark(vfx["x"], vfx["y"], 0.85)
                    game.fx.trigger_shake(2.4, 0.18)
                    game.sfx.play("crit")
                    game.visual_fx.append({
                        "kind": "aoe_ring",
                        "x": vfx["x"], "y": vfx["y"], "radius": vfx["radius"],
                        "color": (255, 75, 55), "timer": 0.26, "max_timer": 0.26
                    })
                    for _ in range(18):
                        ang = random.uniform(0, 6.28)
                        spd = random.uniform(1.2, 4.2)
                        game.particles.append(Particle(
                            vfx["x"] + math.cos(ang) * 0.25,
                            vfx["y"] + math.sin(ang) * 0.25,
                            math.cos(ang) * spd, math.sin(ang) * spd - 1.2,
                            random.choice([(255, 50, 65), (255, 165, 50), (190, 25, 45)]),
                            3.2, 0.38
                        ))
                    if math.hypot(game.player.x - vfx["x"], game.player.y - vfx["y"]) <= vfx["radius"]:
                        game.on_player_hit(vfx["dmg"], is_magic=True)

        flicker = math.sin(t * 3.2) * 3.5 + math.cos(t * 6.7) * 1.8
        p_sx = world_ox - game.cam_x
        p_sy = world_oy - game.cam_y
        p_foot_sy = (game.player.y + 0.05) * TILE_H - game.cam_y

        lights = [
            {
                "pos": (p_sx, p_sy, TORCH_Z_HEIGHT),
                "foot_y": p_foot_sy + 2.0,
                "ignore_depth": True,
                "radius": game.player.dark_vision_radius,
                "color": (0.38, 0.48, 0.72)
            }
        ]
        if game.player.has_lit_torch:
            lights.append({
                "pos": (p_sx + 4, p_sy - 2, TORCH_Z_HEIGHT),
                "foot_y": p_foot_sy + 1.5,
                "radius": game.player.torch_light_radius + flicker,
                "color": (1.15, 0.80, 0.40)
            })

        # Свечение игрока во время подготовки каста, Воспламенения Пиро или Омоложения Персефоны!
        if getattr(game.player, "cast_glow_color", None) and game.player.pending_action:
            gc = game.player.cast_glow_color
            lights.append({
                "pos": (p_sx, p_sy - 3, 24.0),
                "foot_y": p_foot_sy + 2.0,
                "ignore_depth": True,
                "radius": 68.0,
                "color": (gc[0] / 190.0, gc[1] / 190.0, gc[2] / 190.0)
            })
        if getattr(game.player, "ignite_timer", 0.0) > 0.0:
            lights.append({
                "pos": (p_sx, p_sy - 2, 24.0),
                "foot_y": p_foot_sy + 2.0,
                "ignore_depth": True,
                "radius": 92.0 + flicker,
                "color": (1.35, 0.62, 0.22)
            })
        if getattr(game.player, "rejuv_timer", 0.0) > 0.0:
            lights.append({
                "pos": (p_sx, p_sy - 2, 24.0),
                "foot_y": p_foot_sy + 2.0,
                "ignore_depth": True,
                "radius": 64.0,
                "color": (0.42, 1.05, 0.55)
            })

        if game.player.shine_timer > 0.0:
            sh_ratio = game.player.shine_timer / 0.95
            lights.append({
                "pos": (p_sx, p_sy - 4, 28.0),
                "foot_y": p_foot_sy + 4.0,
                "ignore_depth": True,
                "radius": 95.0 * sh_ratio,
                "color": (1.65 * sh_ratio, 1.35 * sh_ratio, 0.50 * sh_ratio)
            })

        hud_cx = VIEW_W * 0.5
        hud_cy = VIEW_H + (CANVAS_H - VIEW_H) * 0.5
        hud_lights = []
        if game.player.has_lit_torch or getattr(game.player, "ignite_timer", 0.0) > 0.0:
            hud_lights.append({
                "pos": (THOUGHT_BOX_X + THOUGHT_BOX_W - 22.0, hud_cy, 22.0),
                "radius": 115.0 + flicker * 0.5,
                "color": (0.45, 0.32, 0.16)
            })
        if game.player.shine_timer > 0.0:
            hud_lights.append({
                "pos": (hud_cx, hud_cy, 24.0),
                "radius": 240.0,
                "color": (1.4, 1.15, 0.45)
            })

        def register_world_and_hud_light(wx_px, wy_px, foot_wy_px, z_h, rad, col, allowed_set, ignore_d=False):
            sx, sy = wx_px - game.cam_x, wy_px - game.cam_y
            if -rad <= sx <= VIEW_W + rad and -rad <= sy <= VIEW_H + rad:
                lights.append({
                    "pos": (sx, sy, z_h),
                    "foot_y": foot_wy_px - game.cam_y,
                    "ignore_depth": ignore_d,
                    "radius": rad,
                    "color": col,
                    "allowed_tiles": allowed_set
                })
            rel_dx = wx_px - world_ox
            rel_dy = wy_px - world_oy
            dist_to_player = math.hypot(rel_dx, rel_dy)
            max_sense = rad * 1.45
            if dist_to_player <= max_sense:
                prox = (1.0 - dist_to_player / max_sense) ** 1.25
                if dist_to_player > 2.0:
                    cos_a = rel_dx / dist_to_player
                    sin_a = rel_dy / dist_to_player
                else:
                    cos_a, sin_a = 0.0, 0.0

                reach_factor = min(1.0, dist_to_player / 18.0)
                hud_lx = hud_cx + cos_a * (THOUGHT_BOX_W * 0.48) * reach_factor
                hud_ly = hud_cy + sin_a * ((CANVAS_H - VIEW_H) * 0.46) * reach_factor

                spot_rad = 45.0 + 80.0 * prox
                inten = (0.18 + 0.32 * prox)
                hud_lights.append({
                    "pos": (hud_lx, hud_ly, 18.0),
                    "radius": spot_rad,
                    "color": (col[0] * inten, col[1] * inten, col[2] * inten)
                })

        if getattr(game.dev_panel, "reveal_map", False):
            fov_mask[:, :] = 1.0
            visible_tiles = {(c, r) for r in range(MAP_ROWS) for c in range(MAP_COLS)}
            lights.append({"pos": (VIEW_W * 0.5, VIEW_H * 0.5, 180.0), "foot_y": 9999.0, "ignore_depth": True, "radius": 600.0, "color": (0.85, 0.85, 0.95)})

        for br in game.dungeon.braziers:
            lx_w, ly_w = br["x"] * TILE_W + 8, br["y"] * TILE_H + 6
            foot_w = (br["y"] + 0.5) * TILE_H
            rad = br["radius"] + flicker * 0.5
            l_open = game.dungeon.get_light_open_tiles(br["x"], br["y"], br["radius"])
            allowed = game.dungeon.build_shared_light_Allowed_tiles(player_open_tiles, l_open)
            if allowed is not None:
                register_world_and_hud_light(lx_w, ly_w, foot_w, 22.0, rad, br["color"], allowed)

        for rl in game.dungeon.room_lights:
            lx_w, ly_w = rl["x"] * TILE_W + 8, rl["y"] * TILE_H + 8
            foot_w = (rl["y"] + 0.5) * TILE_H
            rad = rl["radius"]
            l_open = game.dungeon.get_light_open_tiles(rl["x"], rl["y"], rad)
            allowed = game.dungeon.build_shared_light_Allowed_tiles(player_open_tiles, l_open)
            if allowed is not None:
                register_world_and_hud_light(lx_w, ly_w, foot_w, 32.0, rad, rl["color"], allowed, ignore_d=True)

        for obj in game.objects:
            if obj.kind in ("campfire", "fireplace"):
                lx_w, ly_w = obj.x * TILE_W + 8, obj.y * TILE_H + 8
                foot_w = (obj.y + 0.5) * TILE_H
                rad = 115.0 + flicker * 0.8
                l_open = game.dungeon.get_light_open_tiles(obj.x, obj.y, 115.0)
                allowed = game.dungeon.build_shared_light_Allowed_tiles(player_open_tiles, l_open)
                if allowed is not None:
                    register_world_and_hud_light(lx_w, ly_w, foot_w, 24.0, rad, (1.20, 0.72, 0.32), allowed)

        for pr in game.projectiles:
            if getattr(pr, "emits_light", True) and (int(pr.wx), int(pr.wy)) in player_open_tiles:
                wx_p, wy_p = pr.wx * TILE_W, pr.wy * TILE_H
                register_world_and_hud_light(
                    wx_p, wy_p, wy_p, 16.0, 56.0,
                    (pr.color[0] / 220.0, pr.color[1] / 220.0, pr.color[2] / 220.0), None
                )

        # Свечение от огненных следов (берём только 2 самых свежих очага, чтобы не грузить проц!), Кольца холода и Молнии
        fire_lights_added = 0
        for vfx in reversed(game.visual_fx):
            if vfx["kind"] == "fire_trail":
                if fire_lights_added < 2 and (int(vfx["x"]), int(vfx["y"])) in player_open_tiles:
                    fire_lights_added += 1
                    sx_f, sy_f = vfx["x"] * TILE_W - game.cam_x, vfx["y"] * TILE_H - game.cam_y
                    lights.append({
                        "pos": (sx_f, sy_f, 14.0),
                        "foot_y": sy_f,
                        "ignore_depth": True,
                        "radius": 34.0,
                        "color": (0.85, 0.40, 0.15),
                        "allowed_tiles": None
                    })
            elif vfx["kind"] == "mana_shard" and (int(vfx["x"]), int(vfx["y"])) in player_open_tiles:
                wx_s, wy_s = vfx["x"] * TILE_W, vfx["y"] * TILE_H
                register_world_and_hud_light(wx_s, wy_s, wy_s, 14.0, 38.0, (0.35, 0.85, 1.25), None, ignore_d=True)
            elif vfx["kind"] == "frost_nova":
                wx_n, wy_n = vfx["x"] * TILE_W, vfx["y"] * TILE_H
                register_world_and_hud_light(wx_n, wy_n, wy_n, 20.0, vfx["radius"] * TILE_W * 1.25, (0.55, 1.15, 1.45), None, ignore_d=True)
            elif vfx["kind"] == "chain_lightning":
                pts = vfx["points"]
                for i in range(len(pts) - 1):
                    mx_l = (pts[i][0] + pts[i + 1][0]) * 0.5 * TILE_W
                    my_l = (pts[i][1] + pts[i + 1][1]) * 0.5 * TILE_H
                    register_world_and_hud_light(mx_l, my_l, my_l, 22.0, 72.0, (0.75, 1.35, 1.65), None, ignore_d=True)

        for m in game.mobs:
            if getattr(m, "glow_timer", 0.0) > 0.0 and (int(m.x), int(m.y)) in player_open_tiles:
                gc = getattr(m, "glow_color", (255, 120, 40))
                wx_m, wy_m = m.x * TILE_W, m.y * TILE_H
                register_world_and_hud_light(
                    wx_m, wy_m, wy_m, 18.0, 54.0,
                    (gc[0] / 200.0, gc[1] / 200.0, gc[2] / 200.0), None, ignore_d=True
                )

        world_hover_item = None
        if not game.inv_open and not game.levelup_choices and not dev_open:
            for obj in game.objects:
                if not obj.used and obj.kind == "loot" and obj.item and (obj.x, obj.y) in visible_tiles:
                    if math.hypot(world_mx - (obj.x + 0.5), world_my - (obj.y + 0.5)) <= 0.65:
                        world_hover_item = obj.item
                        break

        ui_bundle = dict(game.loc["ui"])
        ui_bundle["_perks_db"] = game.loc.get("perks", {})
        ui_bundle["_world_hover_item"] = world_hover_item
        ui_bundle["_visual_fx"] = game.visual_fx
        ui_bundle["_fx_mgr"] = game.fx
        ui_bundle["_journal_open"] = game.journal_open
        ui_bundle["_journal_logs"] = game.journal_logs
        ui_bundle["_journal_filters"] = game.journal_filters
        ui_bundle["_journal_scroll"] = game.journal_scroll

        hover_target = game.get_precision_hover_target(world_mx, target_wy=world_my)
        shown_str = game.target_thought[:int(game.shown_chars)]
        game.renderer.render_frame(
            screen=screen,
            dungeon=game.dungeon,
            player=game.player,
            mobs=game.mobs,
            objects=game.objects,
            projectiles=game.projectiles,
            particles=game.particles,
            popups=game.popups,
            cam_x=game.cam_x,
            cam_y=game.cam_y,
            fov_mask=fov_mask,
            visible_tiles=visible_tiles,
            lights=lights,
            shown_thought=shown_str,
            ui_texts=ui_bundle,
            inv_open=game.inv_open,
            hover_pos=mouse_pos,
            drag_item=game.drag_item,
            hover_target=hover_target,
            levelup_choices=game.levelup_choices,
            hud_lights=hud_lights
        )

        if hasattr(game, "fx") and game.fx:
            game.fx.render_panel(screen, mouse_pos)

        if hasattr(game, "dev_panel") and game.dev_panel:
            game.dev_panel.render(screen, game, mouse_pos)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()