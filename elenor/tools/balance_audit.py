"""Reproducible baseline audit, not a substitute for combat playtesting."""

import math
from elenor.localization import load_modular_locales
from elenor.entities import Item, Enemy
from elenor.missions.rats import _scale_mob_for_floor
from elenor.paths import PROJECT_ROOT


def build_report():
    data = load_modular_locales()
    lines = [
        "# Баланс: исходные оценки",
        "",
        "Урон до защиты, характеристика ветки = 3, без экипировки и улучшений. DPS оружия учитывает windup, но не шанс попадания, крит, пробитие, контроль и число целей. Показатели не означают одинаковую боевую эффективность.",
        "",
        "## Активные способности",
        "",
        "| Способность | Вектор | Сила | КД с замахом | Мана | Тип / область |",
        "|---|---|---:|---:|---:|---|",
    ]
    for key, v in data["perks"].items():
        if v.get("type") != "active":
            continue
        lines.append(
            f"| {v['name']} | {v['branch']} | {v['power']} | {v['cooldown'] + v.get('windup', 0):.2f} | {v.get('mp_cost', 0)} | {v.get('shape', v['cast_type'])} |"
        )
    lines += [
        "",
        "## Оружие — обычная редкость",
        "",
        "| Оружие | Средний урон с характеристикой 3 | Потенциальный DPS | Целей | Пробитие |",
        "|---|---:|---:|---:|---:|",
    ]
    for key, v in data["items"].items():
        if v.get("slot") != "right_hand":
            continue
        i = Item(key, v, rarity_override="common")
        damage = ((i.dmg_min + i.dmg_max) / 2 + 3) * i.multi_hit
        lines.append(
            f"| {i.name} | {damage:.1f} | {damage / (i.atk_cd + i.windup):.1f} | {i.max_targets} | {i.armor_pierce} |"
        )
    lines += [
        "",
        "## Кампания — реальные параметры врагов после масштабирования",
        "",
        "| Враг | Этаж | HP | Урон | Физ./маг. защита | Ударов для победы при уроне 10 |",
        "|---|---:|---:|---|---|---:|",
    ]
    for floor, kinds in [
        (2, ["rat"]),
        (3, ["rat", "rat_cultist"]),
        (4, ["rat", "rat_cultist", "rat_king"]),
    ]:
        for kind in kinds:
            m = Enemy(0, 0, kind=kind)
            _scale_mob_for_floor(m, floor)
            lines.append(
                f"| {kind} | {floor} | {m.max_hp} | {m.dmg_min}–{m.dmg_max} | {m.phys_def}/{m.mag_def} | {math.ceil(m.max_hp / max(1, 10 - m.phys_def))} |"
            )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    (PROJECT_ROOT / "docs" / "balance-audit.md").write_text(
        build_report(), encoding="utf-8"
    )
