def format_copper_Trigger(total_cp, compact=False):
    total_cp = int(max(0, total_cp))
    pp = total_cp // 1000
    rem = total_cp % 1000
    gp = rem // 100
    rem = rem % 100
    sp = rem // 10
    cp = rem % 10
    if compact:
        if pp > 0:
            return f"{pp}пм {gp}зм"
        if gp > 0:
            return f"{gp}зм {sp}см"
        if sp > 0:
            return f"{sp}см {cp}мм"
        return f"{cp}мм"
    parts = []
    if pp > 0:
        parts.append(f"{pp}пм")
    if gp > 0:
        parts.append(f"{gp}зм")
    if sp > 0:
        parts.append(f"{sp}см")
    if cp > 0 or not parts:
        parts.append(f"{cp}мм")
    return ", ".join(parts)


CURRENCY_AND_GEMS_DB = {
    "coin_copper": {
        "name": "Медные монеты",
        "type": "currency_coin",
        "rarity": "common",
        "icon": "coin_copper",
        "copper_value": 6,
        "desc": "\"Пахнут крысиной шерстью и дешёвым пивом.\""
    },
    "coin_silver": {
        "name": "Серебряные монеты",
        "type": "currency_coin",
        "rarity": "uncommon",
        "icon": "coin_silver",
        "copper_value": 25,
        "desc": "\"Приятно холодят ладонь. На кружку эля точно хватит.\""
    },
    "coin_gold": {
        "name": "Золотые монеты",
        "type": "currency_coin",
        "rarity": "rare",
        "icon": "coin_gold",
        "copper_value": 120,
        "desc": "\"Попробовал на зуб — вроде не крашеный свинец!\""
    },
    "coin_platinum": {
        "name": "Платиновые монеты",
        "type": "currency_coin",
        "rarity": "epic",
        "icon": "coin_platinum",
        "copper_value": 1000,
        "desc": "\"За такую монетку в порту перережут глотку дважды.\""
    },
    "gem_malachite": {
        "name": "Узорчатый малахит",
        "type": "gem",
        "rarity": "common",
        "icon": "gem_green",
        "copper_value": 45,
        "desc": "\"Надеюсь, это не стёклышко от пивной бутылки...\""
    },
    "gem_garnet": {
        "name": "Кровавый гранат",
        "type": "gem",
        "rarity": "uncommon",
        "icon": "gem_red",
        "copper_value": 145,
        "desc": "\"Смахивает на замёрзшую каплю вишнёвой наливки.\""
    },
    "gem_sapphire": {
        "name": "Сапфир Стратоса",
        "type": "gem",
        "rarity": "rare",
        "icon": "gem_blue",
        "copper_value": 380,
        "desc": "\"Холодный, как взгляд трактирщика, когда просишь в долг.\""
    },
    "gem_ruby": {
        "name": "Огненный рубин Пиро",
        "type": "gem",
        "rarity": "epic",
        "icon": "gem_orange",
        "copper_value": 950,
        "desc": "\"Греет карман лучше печки. Главное — штаны не прожечь.\""
    },
    "gem_diamond": {
        "name": "Чёрный алмаз Персефоны",
        "type": "gem",
        "rarity": "legendary",
        "icon": "gem_purple",
        "copper_value": 2500,
        "desc": "\"Смотришь в грани — а оттуда на тебя смотрит пенсия.\""
    },
    # Разные виды лечебных средств (для универсального хила и Ипохондрика)
    "potion_hp_weak": {
        "name": "Разбавленный отвар",
        "type": "consumable",
        "rarity": "common",
        "icon": "potion_red",
        "heal_hp": 8,
        "power": 8,
        "cooldown": 1.2,
        "desc": "Мутная микстура на коре дуба. Восстанавливает 8 ХП."
    },
    "herbal_salve": {
        "name": "Травяная припарка",
        "type": "consumable",
        "rarity": "common",
        "icon": "potion_red",
        "heal_hp": 11,
        "power": 11,
        "cooldown": 1.4,
        "desc": "Пахучая мазь из подземного мха. Восстанавливает 11 ХП."
    },
    "potion_hp_strong": {
        "name": "Густой эликсир жизни",
        "type": "consumable",
        "rarity": "rare",
        "icon": "potion_red",
        "heal_hp": 26,
        "power": 26,
        "cooldown": 1.8,
        "desc": "Алхимический концентрат. Восстанавливает 26 ХП."
    }
}


