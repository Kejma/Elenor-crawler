import math
import random

from elenor.config import COIN_TEXT_COLOR, get_rarity_weights
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
        if force_gem or (allow_gem and random.random() < (0.14 + luck * 0.015) * gem_mult):
            pools = {}
            for item_id, data in self.loc["items"].items():
                if data.get("type") in ("gem", "painting"):
                    pools.setdefault(data.get("rarity", "common"), []).append(item_id)
            weights = get_rarity_weights(luck + max(0, fl - 2))
            rarities = [r for r in Item.RARITY_ORDER if r in pools]
            if rarities:
                r_weights = [weights[Item.RARITY_ORDER.index(r)] for r in rarities]
                chosen_rarity = random.choices(rarities, weights=r_weights, k=1)[0]
                return self.make_item(random.choice(pools[chosen_rarity]))
        coin_ids = ["coin_copper", "coin_silver", "coin_gold", "coin_platinum"]
        c_weights = [max(25.0, 75.0 - fl * 12.0), 20.0 + fl * 6.0, 4.0 + fl * 3.0, 0.4 + (fl - 2) * 0.4]
        return self.make_item(random.choices(coin_ids, weights=c_weights, k=1)[0])


    def roll_bag_drop(self, luck):
        depth = getattr(self.dungeon, "floor_num", 1)
        luck = max(0, luck - 1)
        weights = [58, 26, 11 + luck, 4 + depth * .6, 1 + min(7, (depth - 1) * .8) + luck * .25]
        pools = {}
        for item_id, data in self.loc["items"].items():
            if data.get("type") == "bag" and not data.get("locked_bag", False):
                pools.setdefault(data["rarity"], []).append(item_id)
        if not pools:
            return None
        rarities = [rarity for rarity in Item.RARITY_ORDER if rarity in pools]
        rarity = random.choices(rarities, weights=[weights[Item.RARITY_ORDER.index(r)] for r in rarities], k=1)[0]
        return self.make_item(random.choice(pools[rarity]))


    def roll_gear_drop(self, force_rarity=None):
        """Выбирает любой предмет снаряжения (кроме оружия и стартового факела) в заданной редкости."""
        tiers = ["common", "uncommon", "rare", "epic", "legendary"]
        if force_rarity in tiers:
            chosen_rarity = force_rarity
        else:
            luck_val = getattr(getattr(self, "player", None), "luck", 1)
            chosen_rarity = random.choices(tiers, weights=get_rarity_weights(luck_val), k=1)[0]

        gear_pool = [
            iid for iid, data in self.loc["items"].items()
            if data.get("type") == "equipment"
            and data.get("slot") != "right_hand"
            and iid != "pitch_torch"
        ]
        if not gear_pool:
            return self.make_item("buckler_shield", rarity=chosen_rarity)
        return self.make_item(random.choice(gear_pool), rarity=chosen_rarity)

    def roll_item_by_rarity(self, allowed_types=None, *, luck=None):
        """Rolls an item using Luck-scaled weights; any weapon or gear can roll at any rarity!"""
        tiers = ["common", "uncommon", "rare", "epic", "legendary"]
        if luck is None:
            luck = getattr(getattr(self, "player", None), "luck", 1)
        if allowed_types and set(allowed_types) == {"bag"}:
            return self.roll_bag_drop(luck)
        if (allowed_types is None or "bag" in allowed_types) and random.random() < 0.16:
            bag = self.roll_bag_drop(luck)
            if bag:
                return bag
        weights = get_rarity_weights(luck)
        chosen_rarity = random.choices(tiers, weights=weights, k=1)[0]

        can_drop_equip = (allowed_types is None or "equipment" in allowed_types)
        if can_drop_equip:
            equip_chance = 1.0 if allowed_types == ["equipment"] else 0.65
            if random.random() < equip_chance:
                if random.random() < 0.45:
                    return self.roll_weapon_drop(force_rarity=chosen_rarity)
                return self.roll_gear_drop(force_rarity=chosen_rarity)

        consumable_candidates = [
            item_id for item_id, data in self.loc["items"].items()
            if data.get("type") not in ("equipment", "currency_coin", "gem", "quest_key", "bag")
            and (allowed_types is None or data.get("type") in allowed_types)
        ]
        if consumable_candidates:
            return self.make_item(random.choice(consumable_candidates), rarity=chosen_rarity)
        return self.roll_gear_drop(force_rarity=chosen_rarity)


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


    def inventory_slot_at(self, pos):
        renderer = self.renderer
        for kind, rects in (
            ("ability", enumerate(renderer.ability_rects)),
            ("hotbar", enumerate(renderer.hotbar_rects)),
            ("bag", enumerate(renderer.bag_slot_rects)),
            ("equip", renderer.equip_slot_rects.items()),
            ("pocket", enumerate(renderer.inv_slot_rects[:self.player.unlocked_slots])),
        ):
            for key, rect in rects:
                if rect.collidepoint(pos):
                    return kind, key
        return None

    def _cursor_container(self, kind):
        player = self.player
        return {
            "ability": player.ability_slots,
            "bag": player.bag_slots,
            "equip": player.equipment,
            "pocket": player.inventory,
            "hotbar": player.hotbar,
        }[kind]

    def pick_inventory_cursor(self, pos, aim):
        slot = self.inventory_slot_at(pos)
        if slot is None:
            return
        kind, key = slot
        player = self.player
        if kind == "hotbar":
            self.use_or_equip_item(player.hotbar[key], *aim, from_hotbar=True)
            return
        if kind == "equip" and key == "left_hand":
            weapon = player.equipment["right_hand"]
            if weapon is not None and weapon.two_handed:
                key = "right_hand"

        item = self._cursor_container(kind)[key]
        if getattr(item, "locked_bag", False):
            self.sfx.play("hurt")
        elif item is not None:
            self.drag_item = item
            self.drag_source = kind, key

    def place_inventory_cursor(self, pos):
        item, source = self.drag_item, self.drag_source
        self.drag_item = self.drag_source = None
        if item is None:
            return
        source_kind, source_key = source
        if self._cursor_container(source_kind)[source_key] is not item:
            return
        target = self.inventory_slot_at(pos)
        if target is not None and target != source and self._move_inventory_cursor(item, source, target):
            self.sfx.play("ui")

    def discard_inventory_item(self, pos):
        slot = self.inventory_slot_at(pos)
        if slot is not None and slot[0] == "pocket":
            self.drop_item_on_floor(self.player.inventory[slot[1]])

    def _move_inventory_cursor(self, item, source, target):
        source_kind, source_key = source
        kind, key = target
        player = self.player
        if source_kind == "ability":
            if kind != "ability":
                return False
            player.swap_ability_slots(source_key, key)
            return True
        if kind == "hotbar":
            if not player.item_fits_filter(item, "consumable"):
                return False
            player.hotbar[key] = item
            return True
        if kind == "equip":
            if not player.equip_item(item, key):
                return False
            self._flush_overflow_drops(int(player.x), int(player.y))
            return True
        if kind == "bag" and item.type == "bag":
            if source_kind == "bag":
                return player.swap_bag_slots()
            if not player.change_bag(key, item):
                self.report_bag_space()
                return False
            self.trigger_event_thought("bag_upgrade", item=item.name)
            return True
        if kind != "pocket":
            return False
        if source_kind == "pocket":
            return player.swap_inventory_slots(source_key, key)
        if source_kind == "bag":
            replacement = player.inventory[key]
            if replacement is not None and replacement.type != "bag":
                return False
            if not player.change_bag(source_key, replacement, pocket_index=key):
                self.report_bag_space()
                return False
            return True
        if not player.move_equipment_to_inventory(source_key, key):
            return False
        self._flush_overflow_drops(int(player.x), int(player.y))
        return True

    def drop_item_on_floor(self, item):
        if not item:
            return False
        player = self.player
        equipped = item in player.equipment.values()
        old_capacity = player.pocket_capacity if equipped else None
        if not player.remove_item_everywhere(item):
            self.report_bag_space()
            return False
        tx, ty = int(player.x), int(player.y)
        if equipped:
            player.refresh_equipment_limits(old_capacity)
            self._flush_overflow_drops(tx, ty)
        self.objects.append(Interactable(tx, ty, "loot", item))
        self.sfx.play("step")
        self.trigger_event_thought("drop_item", item=item.name)
        self.add_popup(self.player.x, self.player.y, f"Выброшено: {item.name}", (185, 175, 165))
        return True


    def cash_in_gems(self):
        """Convert carried gems at their normal sale value."""
        gems_sold = 0
        total_cp_earned = 0
        for idx in range(self.player.max_possible_slots):
            itm = self.player.inventory[idx]
            if itm and itm.type == "gem":
                gems_sold += 1
                total_cp_earned += itm.copper_value
                self.player.remove_item_everywhere(itm)

        if gems_sold:
            self.profile["bank_copper"] = self.profile.get("bank_copper", 0) + total_cp_earned
            save_profile(self.profile)
        return gems_sold, total_cp_earned

    def cash_in_strongbox_on_death(self):
        """Converts all items inside the Family Strongbox to coins on death."""
        if getattr(self, "strongbox_settled", False):
            return 0, 0
        self.strongbox_settled = True
        saved_count = 0
        total_cp = 0
        for sec in self.player.inventory_sections():
            bag = sec.get("bag")
            if bag is not None and getattr(bag, "locked_bag", False):
                for idx in range(sec["start"], sec["start"] + sec["count"]):
                    itm = self.player.inventory[idx]
                    if itm is not None:
                        val = getattr(itm, "sell_value", 0) or getattr(itm, "copper_value", 0)
                        if val > 0:
                            total_cp += val
                            saved_count += 1
                        self.player.inventory[idx] = None
        if total_cp > 0:
            self.player.gold += total_cp
            self.profile["bank_copper"] = self.profile.get("bank_copper", 0) + total_cp
            save_profile(self.profile)
            val_str = format_copper_Trigger(total_cp)
            self.add_log("event", f"Семейная шкатулка спасла добычу ({saved_count} шт.): +{val_str} в казну!", COIN_TEXT_COLOR)
            self.add_popup(self.player.x, self.player.y - 0.5, f"ШКАТУЛКА: +{val_str}", COIN_TEXT_COLOR, big=True)
        return saved_count, total_cp

    def try_sell_gems_to_npc(self, obj, speaker_name="Скупщик Шнырь"):
        gems_sold, total_cp_earned = self.cash_in_gems()
        if not gems_sold:
            return False
        val_str = format_copper_Trigger(total_cp_earned)
        self.sfx.play("coin_pickup")
        self.add_log("event", f"Продано самоцветов: {gems_sold} шт. Выручка +{val_str} отправлена в казну!", COIN_TEXT_COLOR)
        line = self.get_event_text("npc_sell_gems", speaker=speaker_name, count=gems_sold, val=val_str)
        obj.speech_text = line
        obj.speech_timer = 5.5
        self.set_thought(line, important=True)
        self.add_popup(obj.x + 0.5, obj.y + 0.5, f"+{val_str} В БАНК!", COIN_TEXT_COLOR, big=True)
        return True


    def open_merchant_shop(self, npc):
        from elenor.ui.shop import open_merchant_shop
        open_merchant_shop(self, npc)

    def interact_with_merchant(self, obj):
        """Открывает полноценную лавку Шныря для покупки, продажи и угощения пивом."""
        self.open_merchant_shop(obj)


    def report_bag_space(self):
        self.sfx.play("hurt")
        self.add_popup(self.player.x, self.player.y, self.loc["ui"]["bag_space_needed"], (255, 165, 120))

    def equip_bag(self, item, index):
        if not self.player.change_bag(index, item):
            self.report_bag_space()
            return False
        self.trigger_event_thought("bag_upgrade", item=item.name)
        self.sfx.play("ui")
        return True

    def _pickup_loot_object(self, obj):
        if obj.item.type == "currency_coin":
            obj.used = True
            self.add_log("event", f"Подобрано: {obj.item.name}.", COIN_TEXT_COLOR)
            cp_gain = obj.item.copper_value
            self.player.gold += cp_gain
            val_str = format_copper_Trigger(cp_gain)
            self.sfx.play("coin_pickup")
            self.trigger_event_thought("pickup_coin", item=obj.item.name.lower(), val=val_str)
            self.add_popup(obj.x + 0.5, obj.y + 0.5, f"+{val_str}", COIN_TEXT_COLOR)
            return True
        if obj.item.type == "quest_key":
            obj.used = self.player.add_item_to_inventory(obj.item)
            if obj.used:
                self.add_log("event", f"Подобрано: {obj.item.name}.")
                self.sfx.play("ui")
                self.trigger_event_thought("pickup", item=obj.item.name)
                self.add_popup(obj.x + 0.5, obj.y + 0.5, f"+{obj.item.name}", obj.item.rarity_color)
            return True
        if obj.item.type == "bag" and None in self.player.bag_slots:
            obj.used = self.equip_bag(obj.item, self.player.bag_slots.index(None))
            if obj.used:
                self.add_log("event", f"Подобрано: {obj.item.name}.")
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
        if obj.used:
            self.add_log("event", f"Подобрано: {obj.item.name}.")
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
        mana_cost = self.player.ability_mana_cost(item) if item.type in ("spell", "permanent_spell") else 0.0

        # 1. Сначала проверяем ману: если не хватает — короткий грустный звук без надписей "КД"!
        if self.player.mp < mana_cost:
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
                mp_val = int(round(self.player.scale_mana(item.power)))
                self.player.mp = min(float(self.player.max_mp), self.player.mp + mp_val)
                self.add_log("event", f"Использовано «{item.name}»: восстановлено +{mp_val} МП.", (110, 205, 255))
                self.add_popup(self.player.x, self.player.y, f"+{mp_val}", (95, 195, 255), "mana")
                self.sfx.play("magic")
                self.player.remove_item_everywhere(item)
            return

        if is_ability:
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

            self.player.mp -= mana_cost
            self.player.buffered_combat = None
            self.world_active = True
            self.player.cooldowns[item.id] = item.cooldown

            if item.windup > 0.0:
                self.sfx.play("ability_prepare")
                self.player.cast_glow_color = item.color
                self.player.pending_action = {
                    "kind": "spell",
                    "item": item,
                    "mana_paid": mana_cost,
                    "timer": item.windup,
                    "max_timer": item.windup,
                    "tx": tx,
                    "ty": ty
                }
            else:
                self._execute_skill_or_spell(item, tx, ty, mana_paid=mana_cost)
            return

        elif item.type == "equipment":
            if self.player.equip_item(item):
                self._flush_overflow_drops(int(self.player.x), int(self.player.y))
                self.sfx.play("ui")
            else:
                self.trigger_event_thought("bag_full", force_important=True)
                self.sfx.play("hurt")

        elif item.type == "bag" and item not in self.player.bag_slots:
            slots = self.player.bag_slots
            if None in slots:
                self.equip_bag(item, slots.index(None))
            else:
                unlocked = [i for i, b in enumerate(slots) if not getattr(b, "locked_bag", False)]
                if not unlocked:
                    self.sfx.play("hurt")
                    return
                target = min(unlocked, key=lambda i: slots[i].slots)
                if item.slots > slots[target].slots:
                    self.equip_bag(item, target)
                else:
                    self.sfx.play("ui")
                    self.add_popup(self.player.x, self.player.y, self.loc["ui"]["bag_equip_hint"], (215, 205, 190))


    def _flush_overflow_drops(self, drop_tx, drop_ty):
        while getattr(self.player, "overflow_drops", None):
            dropped_itm = self.player.overflow_drops.pop(0)
            self.objects.append(Interactable(int(drop_tx), int(drop_ty), "loot", dropped_itm))
            self.add_popup(drop_tx + 0.5, drop_ty + 0.5, f"На пол: {dropped_itm.name}", (200, 190, 175))

