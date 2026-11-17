from elenor.paths import PROJECT_ROOT
import json
import os
from elenor.data.items import BASE_ITEMS_DB
from elenor.data.abilities import ABILITIES
from elenor.data.economy import CURRENCY_AND_GEMS_DB


class _SafeFormatDict(dict):
    """Позволяет безопасно форматировать строки из JSON, даже если пользователь не указал {переменную} или опечатался."""

    def __missing__(self, key):
        return "{" + key + "}"


def load_modular_locales():
    base_dir = str(PROJECT_ROOT)
    ru_dir = os.path.join(base_dir, "locales", "ru")
    # Базовый реестр характеристик оружия и предметов
    merged = {
        "items": {k: dict(v) for k, v in BASE_ITEMS_DB.items()},
        "perks": {k: dict(v) for k, v in ABILITIES.items()},
    }
    merged["items"].update(CURRENCY_AND_GEMS_DB)

    if os.path.isdir(ru_dir):
        for fname in sorted(os.listdir(ru_dir)):
            if fname.endswith(".json"):
                fpath = os.path.join(ru_dir, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if fname == "items.json":
                        raw_dict = data if "items" not in data else data["items"]
                        # Локализация накладывает только названия и художественные тексты поверх характеристик!
                        for itm_id, text_fields in raw_dict.items():
                            if itm_id in merged["items"]:
                                merged["items"][itm_id].update(text_fields)
                            else:
                                merged["items"][itm_id] = text_fields
                    else:
                        for k, v in data.items():
                            if (
                                k in merged
                                and isinstance(merged[k], dict)
                                and isinstance(v, dict)
                            ):
                                for entry, fields in v.items():
                                    if entry in merged[k] and isinstance(
                                        merged[k][entry], dict
                                    ):
                                        merged[k][entry].update(fields)
                                    else:
                                        merged[k][entry] = fields
                            else:
                                merged[k] = v
    if "perks" in merged:
        if "clear_mind" in merged["perks"]:
            merged["perks"]["clear_mind"]["desc"] = (
                "ПАССИВНО: Повышает магическую мощь (+2) и запас маны (+3)."
            )
    if "adjectives" in merged:
        for adj_data in merged["adjectives"].values():
            if adj_data.get("quirk") == "pyromaniac":
                adj_data["quirk_desc"] = (
                    "Мгновенно зажигает факел (+22% к радиусу света)."
                )
    return merged
