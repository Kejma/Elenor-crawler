import math
import random

from elenor.config import get_rarity_weights
from elenor.entities import Item, Interactable
from elenor.profile import save_profile
from elenor.data.economy import format_copper_Trigger




class InventoryMixin:
    def make_item(self, item_id, rarity=None):
        itm = Item(item_id, self.loc["items"][item_id], rarity_override=rarity)
        # Слегка варьируем количество монет в горсти для живости!
        if item_id == "coin_copper":
            itm.copper_value = random.randint(4, 9)
        elif item_id == "coin_silver":
            itm.copper_value = random.randint(1, 4) * 10 + random.randint(0, 5)
        elif item_id == "coin_gold":
            itm.copper_value = random.randint(1, 2) * 100 + random.randint(0, 4) * 10
        return itm


    def roll_weapon_drop(self, force_rarity=None):
        """Выбирает любой вид оружия на равных правах и присваивает ему сгенерированную редкость экземпляра."""
        tiers = ["common", "uncommon", "rare", "epic", "legendary"]
        if force_rarity in tiers:
            chosen_rarity = force_rarity
        else:
            luck_val = getattr(getattr(self, "player", None), "luck", 1)
            chosen_rarity = random.choices(tiers, weights=get_rarity_weights(luck_val), k=1)[0]

        weap_pool = [
            iid for iid, data in self.loc["items"].items()
            if data.get("type") == "equipment" and data.get("slot") == "right_hand" and not data.get("is_torch", False)
        ]
        if not weap_pool:
            return self.make_item("rusty_dagger", rarity=chosen_rarity)
        return self.make_item(random.choice(weap_pool), rarity=chosen_rarity)


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


    def roll_item_by_rarity(self, allowed_types=None, *, luck=None):
        """Rolls an item using Luck-scaled weights; any weapon can roll at any rarity!"""
        tiers = ["common", "uncommon", "rare", "epic", "legendary"]
        if luck is None:
            luck = getattr(getattr(self, "player", None), "luck", 1)
        weights = get_rarity_weights(luck)
        chosen_rarity = random.choices(tiers, weights=weights, k=1)[0]

        can_drop_weapon = (allowed_types is None or "equipment" in allowed_types)
        non_weapon_candidates = [
            item_id for item_id, data in self.loc["items"].items()
            if not (data.get("type") == "equipment" and data.get("slot") == "right_hand")
            and data.get("type") not in ("currency_coin", "gem", "quest_key")
            and not data.get("is_torch", False)
            and data.get("rarity", "common") == chosen_rarity
            and (allowed_types is None or data.get("type") in allowed_types)
        ]

        if can_drop_weapon:
            weap_chance = 0.62 if allowed_types == ["equipment"] else 0.35
            if not non_weapon_candidates or random.random() < weap_chance:
                return self.roll_weapon_drop(force_rarity=chosen_rarity)

        if not non_weapon_candidates:
            non_weapon_candidates = [
                item_id for item_id, data in self.loc["items"].items()
                if data.get("type") not in ("currency_coin", "gem", "quest_key")
                and not data.get("is_torch", False)
                and (allowed_types is None or data.get("type") in allowed_types)
            ]
        picked_id = random.choice(non_weapon_candidates)
        return self.make_item(picked_id, rarity=chosen_rarity)


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


    def drop_item_on_floor(self, item):
        if not item:
            return
        self.player.remove_item_everywhere(item)
        tx, ty = int(self.player.x), int(self.player.y)
        self.objects.append(Interactable(tx, ty, "loot", item))
        self.sfx.play("step")
        self.trigger_event_thought("drop_item", item=item.name)
        self.add_popup(self.player.x, self.player.y, f"Выброшено: {item.name}", (185, 175, 165))


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


    def use_or_equip_item(self, item, target_wx=None, target_wy=None, from_hotbar=False):
        if not item or self.player.hp <= 0:
            return
        pending = self.player.pending_action
        cd_rem = self.player.cooldowns.get(item.id, 0.0)
        is_ability = item.type in ("consumable_spell", "combat_skill", "spell", "permanent_spell")
        if from_hotbar and is_ability and not self.inv_open:
            wait = max(cd_rem, pending["timer"] if pending is not None else 0.0)
            if self.buffer_combat_input(wait, target_wx, target_wy, item):
                return
        if pending is not None:
            return
        ev = self.loc["events"]

        # 1. Сначала проверяем ману: если не хватает — короткий грустный звук без надписей "КД"!
        if item.type in ("spell", "permanent_spell") and self.player.mp < item.mp_cost:
            self.sfx.play("no_mana")
            return

        # 2. Если способность на перезарядке — тихий отклик без мусорных всплывашек "КД 0.3с"
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

        if is_ability:
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
            self.player.buffered_combat = None
            self.world_active = True
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

