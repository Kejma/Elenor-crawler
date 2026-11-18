import math
import random

from elenor.config import TILE_W, TYPEWRITER_SPEED


from elenor.localization import _SafeFormatDict


class NarrativeMixin:
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


    def inspect_prop(self, obj):
        pool = self.loc.get("prop_thoughts", {}).get(obj.kind)
        if pool:
            self.play_spatial("step", obj.x + 0.5, obj.y + 0.5)
            self.set_thought(self.pick_text(pool, f"prop_{obj.kind}"), on_inspect=True)

    def set_thought(self, text, important=False, chance=1.0, *, on_inspect=False):
        """
        Управляет мыслями и репликами с поддержкой очереди Важных событий:
        - Если `important=True` и предыдущая важная мысль ещё держится свои 4 секунды — новая встаёт в очередь и запустится строго после неё!
        - Если `important=False` — подчиняется настройке частоты мыслей и не перебивает важные.
        - Осмотр по запросу игрока пропускает паузу между обычными мыслями.
        """
        if not text:
            return False

        if not important:
            mult, _ = self.get_thought_freq_params()
            if mult <= 0.0 or self.important_thought_lock > 0.0 or self.important_thought_queue:
                return False
            if self.bg_thought_cd > 0.0 and not on_inspect:
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

