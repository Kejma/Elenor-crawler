from elenor.paths import PROJECT_ROOT
import json
import os
import pygame

PALETTE_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz@#$%&*+=~^"

ASSET_CATALOG = {
    "tiles": {
        "title": "Тайлы окружения (16x16)",
        "items": {
            "floor_0": ("Каменная плита подвала", (16, 16)),
            "floor_2": ("Подземная вода", (16, 16)),
            "floor_3": ("Лесной мох / Трава", (16, 16)),
            "floor_4": ("Дощатый настил таверны", (16, 16)),
            "floor_5": ("Пещерный грунт", (16, 16)),
            "floor_6": ("Лесная дорога", (16, 16)),
            "floor_jungle_grass": ("Джунгли: Густая трава", (16, 16)),
            "floor_jungle_mud": ("Джунгли: Влажная грязь", (16, 16)),
            "floor_jungle_soil": ("Джунгли: Подстилка и корни", (16, 16)),
            "floor_jungle_swamp": ("Джунгли: Болото с ряской", (16, 16)),
            "floor_jungle_cobble": ("Джунгли: Древняя брусчатка", (16, 16)),
            "floor_river_sand": ("Джунгли: Речной песок", (16, 16)),
            "floor_cave_basalt": ("Пещера: Тёмный базальт", (16, 16)),
            "floor_tribal_wood": ("Хижина: Бамбуковый пол", (16, 16)),
            "floor_tribal_mat": ("Хижина: Тростниковая циновка", (16, 16)),
            "floor_marble_white": ("Храм: Белый мрамор", (16, 16)),
            "floor_marble_dark": ("Храм: Тёмный мрамор", (16, 16)),
            "floor_marble_mosaic": ("Храм: Солнечная мозаика", (16, 16)),
            "floor_marble_checker": ("Храм: Шахматный мрамор", (16, 16)),
            "floor_marble_rose": ("Храм: Розовый кварц", (16, 16)),
            "floor_marble_jade": ("Храм: Полированный нефрит", (16, 16)),
            "floor_temple_gold": ("Храм: Золотая дорожка", (16, 16)),
            "floor_temple_water": ("Храм: Вода сенота (3 кадра)", (16, 16)),
            "wall": ("Каменная стена подвала", (16, 16)),
            "wall_wood": ("Бревенчатая стена", (16, 16)),
            "wall_cave": ("Скальный свод пещеры", (16, 16)),
            "wall_cave_crystal": ("Пещера: Стена с кристаллами", (16, 16)),
            "wall_mud_rock": ("Джунгли: Грязь и валуны", (16, 16)),
            "wall_tribal_wood": ("Хижина: Стена аборигенов", (16, 16)),
            "wall_bamboo_weave": ("Хижина: Плетёный тростник", (16, 16)),
            "wall_marble_temple": ("Храм: Мраморная стена", (16, 16)),
            "wall_marble_ruined": ("Храм: Мрамор в лианах", (16, 16)),
            "wall_marble_obsidian": ("Храм: Обсидиан и золото", (16, 16)),
            "wall_temple_relief": ("Храм: Барельеф Змея", (16, 16)),
            "tree": ("Вековая ель", (16, 16)),
            "tree_jungle": ("Дерево джунглей (иконка)", (16, 16)),
            "tree_palm": ("Кокосовая пальма (иконка)", (16, 16)),
            "door_closed": ("Дверь (Закрыта)", (16, 16)),
            "door_open": ("Дверь (Открыта)", (16, 16)),
            "door_locked": ("Кованая решётка", (16, 16)),
            "carpet_c": ("Ковёр: Центр", (16, 16)),
            "carpet_n": ("Ковёр: Верх", (16, 16)),
            "carpet_s": ("Ковёр: Низ", (16, 16)),
            "carpet_w": ("Ковёр: Лево", (16, 16)),
            "carpet_e": ("Ковёр: Право", (16, 16)),
            "carpet_nw": ("Ковёр: Угол С-З", (16, 16)),
            "carpet_ne": ("Ковёр: Угол С-В", (16, 16)),
            "carpet_sw": ("Ковёр: Угол Ю-З", (16, 16)),
            "carpet_se": ("Ковёр: Угол Ю-В", (16, 16)),
            "carpet_h": ("Ковёр: Полоса гор.", (16, 16)),
            "carpet_v": ("Ковёр: Полоса верт.", (16, 16)),
            "carpet_single": ("Ковёр: Одиночный", (16, 16)),
            "moss_c": ("Мох-автотайл: Центр", (16, 16)),
            "moss_n": ("Мох-автотайл: Верх", (16, 16)),
            "moss_s": ("Мох-автотайл: Низ", (16, 16)),
            "moss_w": ("Мох-автотайл: Лево", (16, 16)),
            "moss_e": ("Мох-автотайл: Право", (16, 16)),
            "moss_nw": ("Мох-автотайл: Внеш. С-З", (16, 16)),
            "moss_ne": ("Мох-автотайл: Внеш. С-В", (16, 16)),
            "moss_sw": ("Мох-автотайл: Внеш. Ю-З", (16, 16)),
            "moss_se": ("Мох-автотайл: Внеш. Ю-В", (16, 16)),
            "moss_in_nw": ("Мох-автотайл: Внутр. С-З", (16, 16)),
            "moss_in_ne": ("Мох-автотайл: Внутр. С-В", (16, 16)),
            "moss_in_sw": ("Мох-автотайл: Внутр. Ю-З", (16, 16)),
            "moss_in_se": ("Мох-автотайл: Внутр. Ю-В", (16, 16)),
            "moss_h": ("Мох-автотайл: Полоса гор.", (16, 16)),
            "moss_v": ("Мох-автотайл: Полоса верт.", (16, 16)),
            "moss_single": ("Мох-автотайл: Островок", (16, 16)),
            "floor_lake_shallow": ("Озеро: Мелководье (3 кадра)", (16, 16)),
            "floor_lake_deep": ("Озеро: Глубокая вода (3 кадра)", (16, 16)),
            "floor_wet_sand": ("Берег: Мокрый песок", (16, 16)),
            "floor_pebble_shore": ("Берег: Речная галька", (16, 16)),
            "floor_reed_mud": ("Берег: Ил и корни камыша", (16, 16)),
            "floor_wooden_pier": ("Берег: Доски рыбацкого пирса", (16, 16)),
            "floor_tar_pit": ("Костяные джунгли: Кипящая смола (3 кадра)", (16, 16)),
            "floor_acid_pool": ("Пещера: Кислотная лужа (3 кадра)", (16, 16)),
            "floor_bone_grass": ("Костяные джунгли: Мёртвая трава", (16, 16)),
            "floor_bone_grave": ("Костяные джунгли: Костяная крошка", (16, 16)),
            "floor_blood_marsh": ("Костяные джунгли: Кровавая трясина", (16, 16)),
            "floor_bone_bridge": ("Костяные джунгли: Мост из костей", (16, 16)),
            "floor_cave_fungus": ("Пещера: Грибной мицелий", (16, 16)),
            "floor_cave_obsidian": ("Пещера: Колотый обсидиан", (16, 16)),
            "wall_bone_ribs": ("Костяные джунгли: Стена из рёбер", (16, 16)),
            "wall_skull_catacomb": ("Костяные джунгли: Стена черепов", (16, 16)),
            "wall_corrupted_wood": ("Костяные джунгли: Гнилой частокол", (16, 16)),
            "wall_cave_web": ("Пещера: Скала в паутине", (16, 16)),
            "wall_cave_magma": ("Пещера: Магмовая порода", (16, 16)),
            "tree_bone": ("Костяное дерево (иконка)", (16, 16)),
            "tree_dead_mangrove": ("Мёртвый мангр (иконка)", (16, 16)),
            
        }
    },
    "overlays": {
        "title": "Накладываемые оверлеи (16x16)",
        "items": {
            "ov_pebbles": ("Россыпь камушков", (16, 16)),
            "ov_moss": ("Пятна мха", (16, 16)),
            "ov_cracks": ("Трещины и сколы", (16, 16)),
            "ov_planks_wear": ("Щепки и потёртости", (16, 16)),
            "ov_fern": ("Джунгли: Розетка папоротника", (16, 16)),
            "ov_flowers_red": ("Джунгли: Алые гибискусы", (16, 16)),
            "ov_flowers_blue": ("Джунгли: Лазурные орхидеи", (16, 16)),
            "ov_jungle_vines": ("Джунгли: Ползучие лианы", (16, 16)),
            "ov_fallen_leaves": ("Джунгли: Опавшие листья", (16, 16)),
            "ov_marble_cracks": ("Храм: Трещины в мраморе", (16, 16)),
            "ov_water_lily": ("Вода: Кувшинки и лотос", (16, 16)),
            "ov_glow_shrooms": ("Пещера: Неоновые грибы", (16, 16)),
            "ov_petals_gold": ("Храм: Золотые лепестки", (16, 16)),
            "ov_bamboo_leaves": ("Джунгли: Листья бамбука", (16, 16)),
            "ov_mangrove_roots": ("Джунгли: Корни мангров", (16, 16)),
            "ov_bones": ("Джунгли: Череп и кости", (16, 16)),
            "ov_mud_puddle": ("Джунгли: Дождевая лужа", (16, 16)),
            "ov_gold_filigree": ("Храм: Золотая филигрань", (16, 16)),
            "ov_shore_foam": ("Озеро: Пена прибоя", (16, 16)),
            "ov_shells_starfish": ("Берег: Ракушки на песке", (16, 16)),
            "ov_duckweed": ("Озеро: Пятна ряски", (16, 16)),
            "ov_fish_shadows": ("Озеро: Тени косяка рыб", (16, 16)),
            "ov_bobber_ripples": ("Озеро: Поплавок на воде", (16, 16)),
            "ov_ribcage_remains": ("Костяные джунгли: Грудная клетка", (16, 16)),
            "ov_blood_vines": ("Костяные джунгли: Кровавые лозы", (16, 16)),
            "ov_spider_web": ("Пещера: Густая паутина", (16, 16)),
            "ov_guano_droppings": ("Пещера: Следы нетопырей", (16, 16)),
            "ov_sulfur_cracks": ("Пещера: Серные трещины", (16, 16)),
            "ov_bone_spikes_floor": ("Костяные джунгли: Костяные шипы", (16, 16)),
            "ov_corrupted_spores": ("Костяные джунгли: Пятна гнили", (16, 16)),
            "ov_shattered_skulls": ("Костяные джунгли: Битые черепа", (16, 16)),
        }
    },
    "mobs": {
        "title": "Бестиарий и NPC",
        "items": {
            "rat": ("Погребная крыса", (16, 20)),
            "rat_cultist": ("Две крысы под плащом", (16, 20)),
            "rat_king": ("Крысиный Король (Босс 2x2)", (32, 36)),
            "npc_innkeeper": ("Трактирщик Гуго (NPC)", (16, 20)),
            "wolf": ("Лесной волк", (16, 20)),
            "skeleton": ("Скелет-воин", (16, 20)),
            "cultist": ("Тёмный культист", (16, 20)),
            "necromancer": ("Архи-некромант", (16, 20)),
            "brute": ("Костяной громила", (16, 20)),
            "tribal_warrior": ("Абориген: Воин с макуауитлем", (16, 20)),
            "tribal_hunter": ("Абориген: Охотник с трубкой", (16, 20)),
            "tribal_shaman": ("Абориген: Шаман духов", (16, 20)),
            "croc_warrior": ("Рептилия: Воин-полукрокодил", (16, 20)),
            "croc_juggernaut": ("Рептилия: Крокодил-Джаггернаут (2x2)", (32, 36)),
            "vedalken_mage": ("Ведалкен: Хрономаг", (16, 20)),
            "vedalken_four_armed": ("Ведалкен: Четырёхрукий архонт", (16, 20)),
            "vedalken_arbiter": ("Ведалкен: Верховный Демиург (Босс 2x2)", (32, 36)),
            "swamp_lurker": ("Дикие: Трясинный болотник", (16, 20)),
            "jungle_gremlin": ("Дикие: Джунглевый гремлин", (16, 20)),
            "jungle_viper": ("Дикие: Изумрудная кобра", (16, 20)),
            "giant_scorpion": ("Дикие: Гигантский скорпион", (16, 20)),
            "myconid_shambler": ("Дикие: Гриболюд-миконид", (16, 20)),
            "thorn_treant": ("Дикие: Древолюд-шиповик", (16, 20)),
            "giant_wasp": ("Дикие: Огромная шершень-пчела", (16, 20)),
            "rust_monster": ("Пещера: Ржавник (D&D)", (16, 20)),
            "cave_piercer": ("Пещера: Пронзатель (D&D)", (16, 20)),
            "cave_angler": ("Пещера: Глубинный удильщик", (16, 20)),
            "marble_golem": ("Храм: Мраморный голем-страж", (16, 20)),
            "jade_scarab": ("Храм: Нефритовый скарабей", (16, 20)),
            "skull_spider": ("Костяные джунгли: Черепопаук", (16, 20)),
            "bone_jaguar": ("Костяные джунгли: Костяной ягуар", (16, 20)),
            "bone_constrictor": ("Костяные джунгли: Костяной удав", (16, 20)),
            "ossuary_behemoth": ("Костяные джунгли: Исполин Оссуария (Босс 2x2)", (32, 36)),
        }
    },
    "props": {
        "title": "Объекты данжа, Джунглей и Храмов",
        "items": {
            "jungle_bush": ("Джунгли: Густой куст", (16, 20)),
            "jungle_bush_flowers": ("Джунгли: Цветущий куст", (16, 20)),
            "giant_fern": ("Джунгли: Высокий папоротник", (16, 20)),
            "venus_flytrap": ("Джунгли: Венерина мухоловка", (16, 20)),
            "bamboo_clump": ("Джунгли: Побеги бамбука", (16, 20)),
            "rafflesia_flower": ("Джунгли: Цветок раффлезии", (16, 20)),
            "banana_plant": ("Джунгли: Банановая пальма", (16, 20)),
            "termite_mound": ("Джунгли: Высокий термитник", (16, 20)),
            "tree_stump": ("Джунгли: Пень с грибами", (16, 20)),
            "hollow_log": ("Джунгли: Бревно во мху", (16, 20)),
            "jungle_boulder": ("Джунгли: Замшелый валун", (16, 20)),
            "crystal_cluster": ("Пещера: Светящиеся кристаллы", (16, 20)),
            "cave_stalagmite": ("Пещера: Каменный сталагмит", (16, 20)),
            "ancient_waystone": ("Джунгли: Рунный камень", (16, 20)),
            "giant_stone_head": ("Джунгли: Голова колосса", (16, 20)),
            "snake_shed_skin": ("Джунгли: Змеиная выползка", (16, 20)),
            "tall_jungle_tree": ("Джунгли: Высокое дерево (24x38)", (24, 38)),
            "tall_palm_tree": ("Джунгли: Высокая пальма (24x38)", (24, 38)),
            "tribal_totem": ("Аборигены: Тотем духов", (16, 20)),
            "tribal_table": ("Аборигены: Плетёный стол", (16, 20)),
            "tribal_stool": ("Аборигены: Табурет со шкурой", (16, 20)),
            "tribal_bed": ("Аборигены: Циновка для сна", (16, 20)),
            "tribal_hammock": ("Аборигены: Подвесной гамак", (16, 20)),
            "tribal_rack": ("Аборигены: Стойка копий", (16, 20)),
            "tribal_bow_stand": ("Аборигены: Стойка луков", (16, 20)),
            "tribal_drum": ("Аборигены: Боевой барабан", (16, 20)),
            "tribal_pot": ("Аборигены: Глиняная амфора", (16, 20)),
            "tribal_skull_pole": ("Аборигены: Шест с черепом", (16, 20)),
            "tribal_chest": ("Аборигены: Плетёный ларь", (16, 20)),
            "shaman_cauldron": ("Аборигены: Котёл шамана", (16, 20)),
            "fish_drying_rack": ("Аборигены: Сушилка рыбы", (16, 20)),
            "skull_brazier": ("Аборигены: Череп-жаровня", (16, 20)),
            "blowgun_trap": ("Аборигены: Духовая ловушка", (16, 20)),
            "bamboo_cage": ("Аборигены: Бамбуковая клетка", (16, 20)),
            "fruit_basket": ("Аборигены: Корзина фруктов", (16, 20)),
            "tribal_mask_shield": ("Аборигены: Маска вождя", (16, 20)),
            "shaman_gong": ("Аборигены: Бубен духов", (16, 20)),
            "marble_pillar": ("Храм: Мраморная колонна", (16, 20)),
            "marble_pillar_broken": ("Храм: Разбитая колонна", (16, 20)),
            "marble_altar": ("Храм: Солнечный алтарь", (16, 20)),
            "marble_brazier": ("Храм: Золотая жаровня", (16, 20)),
            "marble_statue": ("Храм: Статуя стража", (16, 20)),
            "serpent_statue": ("Храм: Пернатый Змей", (16, 20)),
            "sun_gong": ("Храм: Солнечный гонг", (16, 20)),
            "marble_bench": ("Храм: Мраморная скамья", (16, 20)),
            "marble_lectern": ("Храм: Пюпитр со скрижалью", (16, 20)),
            "incense_burner": ("Храм: Золотая курильница", (16, 20)),
            "marble_obelisk": ("Храм: Рунный обелиск", (16, 20)),
            "marble_chest": ("Храм: Мраморный ковчег", (16, 20)),
            "temple_sundial": ("Храм: Солнечные часы", (16, 20)),
            "holy_fire_bowl": ("Храм: Чаша святого огня", (16, 20)),
            "fallen_colossus": ("Храм: Обломки колосса", (16, 20)),
            "marble_fountain": ("Храм: Купель с лотосом", (16, 20)),
            "marble_sarcophagus": ("Храм: Мраморный саркофаг", (16, 20)),
            "marble_urn": ("Храм: Золочёная ваза", (16, 20)),
            "tavern_table": ("Трактирный стол", (16, 20)),
            "bar_counter": ("Барная стойка", (16, 20)),
            "wine_cask": ("Большая винная бочка", (16, 20)),
            "bed": ("Кровать с тюфяком", (16, 20)),
            "fireplace": ("Каменный камин", (16, 20)),
            "shelf_bottles": ("Полка с бутылками", (16, 20)),
            "chair_bench": ("Деревянная скамья", (16, 20)),
            "coat_rack": ("Вешалка с плащом", (16, 20)),
            "cauldron": ("Котёл с похлёбкой", (16, 20)),
            "woven_rug": ("Домотканый ковёр", (16, 20)),
            "crate_stack": ("Деревянные ящики", (16, 20)),
            "grandfather_clock": ("Напольные часы с маятником", (16, 20)),
            "mounted_boar": ("Трофейная голова вепря", (16, 20)),
            "notice_board": ("Доска заказов и розыска", (16, 20)),
            "lute_stand": ("Забытая лютня барда", (16, 20)),
            "wash_basin": ("Бадья для умывания", (16, 20)),
            "meat_rack": ("Вешала с окороками", (16, 20)),
            "firewood_pile": ("Поленница берёзовых дров", (16, 20)),
            "armor_stand": ("Старый рыцарский доспех", (16, 20)),
            "merchant_counter": ("Прилавок скупщика", (16, 20)),
            "merchant_shelves": ("Полки скупщика", (16, 20)),
            "merchant_goods": ("Витрина самоцветов", (16, 20)),
            "merchant_sign": ("Вывеска с весами", (16, 20)),
            "barrel": ("Винная бочка", (16, 20)),
            "ritual_altar": ("Кровавый алтарь", (16, 20)),
            "chest": ("Сундук с хабаром", (16, 20)),
            "idol": ("Древний идол", (16, 20)),
            "campfire": ("Походный костёр", (16, 20)),
            "brazier": ("Напольная жаровня", (16, 20)),
            "bookshelf": ("Книжный шкаф", (16, 20)),
            "alchemy": ("Алхимический стол", (16, 20)),
            "rack": ("Оружейная стойка", (16, 20)),
            "trap": ("Напольные шипы", (16, 20)),
            "stairs": ("Лестница вниз", (16, 20)),
            "lever_off": ("Рычаг (Выкл)", (16, 20)),
            "lever_on": ("Рычаг (Вкл)", (16, 20)),
            "loot": ("Мешочек с лутом", (16, 20)),
            "tall_bone_tree": ("Костяные джунгли: Костяное дерево (24x38)", (24, 38)),
            "tall_dead_mangrove": ("Костяные джунгли: Мёртвый мангр (24x38)", (24, 38)),
            "bone_totem_altar": ("Костяные джунгли: Тотем черепов", (16, 20)),
            "leviathan_rib_arch": ("Костяные джунгли: Рёбра левиафана (2x1)", (32, 20)),
            "giant_beast_skull": ("Костяные джунгли: Череп чудовища (2x1)", (32, 20)),
            "spine_pillar": ("Костяные джунгли: Столб позвонков", (16, 20)),
            "bone_throne": ("Костяные джунгли: Костяной трон", (16, 20)),
            "bone_cage_hanging": ("Костяные джунгли: Клетка из рёбер", (16, 20)),
            "blood_thorn_bush": ("Костяные джунгли: Кровавый терновник", (16, 20)),
            "corpse_pitcher_plant": ("Костяные джунгли: Хищный кувшиночник", (16, 20)),
            "impaled_skeleton": ("Костяные джунгли: Скелет на пиках", (16, 20)),
            "bone_spike_barricade": ("Костяные джунгли: Костяные колья", (16, 20)),
            "necrotic_brazier": ("Костяные джунгли: Некро-жаровня", (16, 20)),
            "ossuary_chest": ("Костяные джунгли: Сундук-оссуарий", (16, 20)),
            "sacrificial_bone_table": ("Костяные джунгли: Стол из лопатки", (16, 20)),
            "bone_wind_chimes": ("Костяные джунгли: Ловцы душ", (16, 20)),
            "spider_cocoon": ("Пещера: Паучий кокон с жертвой", (16, 20)),
            "spider_egg_sac": ("Пещера: Кладка яиц паука", (16, 20)),
            "giant_cave_mushroom": ("Пещера: Гигантский светящийся гриб", (16, 20)),
            "amethyst_geode": ("Пещера: Аметистовая жеода", (16, 20)),
            "sulfur_geyser": ("Пещера: Серный гейзер", (16, 20)),
            "stalagnate_column": ("Пещера: Колонна-сталагнат", (16, 20)),
            "minecart_wreck": ("Пещера: Разбитая вагонетка", (16, 20)),
            "miner_skeleton": ("Пещера: Скелет рудокопа", (16, 20)),
            "bat_roost_rock": ("Пещера: Гнездо нетопырей", (16, 20)),
            "abyssal_fissure": ("Пещера: Разлом бездны (2x1)", (32, 20)),
        }
    },
    "hero": {
        "title": "Персонаж (16x20)",
        "items": {
            "hero_base": ("Герой (Базовый)", (16, 20)),
        }
    }
}

from elenor.rendering.fishing import FISH_CATALOG_SPECS

ASSET_CATALOG["fishing"] = {
    "title": "Рыбалка, Снасти и Улов (47 видов)",
    "items": {
        "prop_reeds_tall": ("Берег: Высокий камыш с рогозом", (16, 20)),
        "prop_fishing_rod_stand": ("Берег: Удочка на рогатине", (16, 20)),
        "prop_tackle_box": ("Берег: Ящик со снастями", (16, 20)),
        "prop_fish_trap_net": ("Берег: Плетёная верша", (16, 20)),
        "prop_bait_bucket": ("Берег: Ведро с уловом", (16, 20)),
        "prop_fish_drying_line": ("Берег: Вяленая рыба на вешалах", (16, 20)),
        "prop_fisherman_stool": ("Берег: Складной стульчик", (16, 20)),
        "prop_wooden_rowboat": ("Берег: Рыбацкая лодка (2x1)", (32, 20)),
        **{k: (ru_title, sz) for k, (ru_title, sz, _) in FISH_CATALOG_SPECS.items()},
    },
}

DEFAULT_RANDOM_ROT_ROLES = {
    "floor_3", "floor_5",
    "floor_jungle_grass", "floor_jungle_mud", "floor_jungle_soil",
    "floor_jungle_swamp", "floor_river_sand", "floor_cave_basalt",
    "ov_pebbles", "ov_moss", "ov_cracks", "ov_planks_wear",
    "ov_fern", "ov_flowers_red", "ov_flowers_blue", "ov_jungle_vines",
    "ov_fallen_leaves", "ov_marble_cracks", "ov_water_lily", "ov_glow_shrooms",
    "ov_petals_gold", "ov_bamboo_leaves", "ov_mangrove_roots", "ov_bones",
    "ov_mud_puddle", "ov_gold_filigree", "floor_wet_sand", "floor_pebble_shore", "floor_reed_mud",
    "ov_shells_starfish", "ov_duckweed",
    "floor_bone_grass", "floor_bone_grave", "floor_blood_marsh",
    "floor_cave_fungus", "floor_cave_obsidian",
    "ov_blood_vines", "ov_spider_web", "ov_guano_droppings",
    "ov_sulfur_cracks", "ov_corrupted_spores", "ov_shattered_skulls",
}


def get_assets_root():
    return os.path.join(str(PROJECT_ROOT), "assets")


def get_manifest_path():
    return os.path.join(get_assets_root(), "manifest.json")


def load_manifest():
    m_path = get_manifest_path()
    if os.path.isfile(m_path):
        try:
            with open(m_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_manifest(manifest_data):
    os.makedirs(get_assets_root(), exist_ok=True)
    with open(get_manifest_path(), "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, ensure_ascii=False, indent=2)


def surface_to_encoded_grid(surf, is_normal=False):
    w, h = surf.get_size()
    color_to_char = {}
    palette = {}
    rows = []

    if not is_normal:
        color_to_char[(0, 0, 0, 0)] = "."
        palette["."] = [0, 0, 0, 0]
    else:
        color_to_char[(128, 128, 255, 255)] = "."
        palette["."] = [128, 128, 255, 255]

    char_idx = 0
    for y in range(h):
        row_str = []
        for x in range(w):
            c = tuple(surf.get_at((x, y)))
            if not is_normal and c[3] == 0:
                c = (0, 0, 0, 0)
            elif is_normal:
                from elenor.rendering.normals import snap_normal_rgb
                sr, sg, sb = snap_normal_rgb(c[0], c[1], c[2])
                c = (sr, sg, sb, 255)

            if c not in color_to_char:
                if char_idx < len(PALETTE_CHARS):
                    ch = PALETTE_CHARS[char_idx]
                else:
                    ch = chr(160 + (char_idx - len(PALETTE_CHARS)))
                char_idx += 1
                color_to_char[c] = ch
                palette[ch] = list(c)

            row_str.append(color_to_char[c])
        rows.append("".join(row_str))

    return palette, rows


def encoded_grid_to_surface(palette, rows, size, is_normal=False):
    w, h = size
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    if is_normal:
        surf.fill((128, 128, 255, 255))
    else:
        surf.fill((0, 0, 0, 0))

    for y, row in enumerate(rows[:h]):
        for x, ch in enumerate(row[:w]):
            rgba = palette.get(ch)
            if rgba:
                surf.set_at((x, y), tuple(rgba))
    return surf


def save_dtex_frames(filepath, role_id, file_stem, name, category, frames_list, fps=4, random_rot=False):
    """
    Saves 1 to 3 animation frames [(diff_surf, norm_surf), ...] and FPS into a .dtex v2 file.
    Also keeps top-level diffuse_palette/grid of frame 0 for backward compatibility.
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    w, h = frames_list[0][0].get_size()
    encoded_frames = []

    for d_surf, n_surf in frames_list[:3]:
        d_pal, d_rows = surface_to_encoded_grid(d_surf, is_normal=False)
        n_pal, n_rows = surface_to_encoded_grid(n_surf, is_normal=True)
        encoded_frames.append({
            "diffuse_palette": d_pal,
            "diffuse_grid": d_rows,
            "normal_palette": n_pal,
            "normal_grid": n_rows
        })

    payload = {
        "dtex_version": 2,
        "role_id": role_id,
        "id": file_stem,
        "name": name,
        "category": category,
        "size": [w, h],
        "fps": int(fps),
        "random_rot": bool(random_rot),
        "frame_count": len(encoded_frames),
        "frames": encoded_frames,
        # Frame 0 mirrored at top level so v1 readers never break
        "diffuse_palette": encoded_frames[0]["diffuse_palette"],
        "diffuse_grid": encoded_frames[0]["diffuse_grid"],
        "normal_palette": encoded_frames[0]["normal_palette"],
        "normal_grid": encoded_frames[0]["normal_grid"],
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_dtex_frames(filepath):
    """Loads a .dtex v1 or v2 file and returns (meta_dict, [(diff_0, norm_0), ...], fps)."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    size = tuple(data["size"])
    fps = int(data.get("fps", 4))
    frames_out = []

    if "frames" in data and isinstance(data["frames"], list) and len(data["frames"]) > 0:
        for fr in data["frames"][:3]:
            d_s = encoded_grid_to_surface(fr["diffuse_palette"], fr["diffuse_grid"], size, is_normal=False)
            n_s = encoded_grid_to_surface(fr["normal_palette"], fr["normal_grid"], size, is_normal=True)
            frames_out.append((d_s, n_s))
    else:
        d_s = encoded_grid_to_surface(data["diffuse_palette"], data["diffuse_grid"], size, is_normal=False)
        n_s = encoded_grid_to_surface(data["normal_palette"], data["normal_grid"], size, is_normal=True)
        frames_out.append((d_s, n_s))

    # Mask normal alpha with diffuse alpha AND snap all normal pixels strictly to the 10-color compass!
    from elenor.rendering.normals import snap_normal_rgb
    masked_frames = []
    for d_s, n_s in frames_out:
        w, h = d_s.get_size()
        for y in range(h):
            for x in range(w):
                n_col = n_s.get_at((x, y))
                sr, sg, sb = snap_normal_rgb(n_col[0], n_col[1], n_col[2])
                if d_s.get_at((x, y))[3] <= 10:
                    n_s.set_at((x, y), (sr, sg, sb, 0))
                else:
                    n_s.set_at((x, y), (sr, sg, sb, 255))
        masked_frames.append((d_s, n_s))

    return data, masked_frames, fps


def _is_dtex_empty_blank(filepath):
    """Проверяет, не является ли .dtex файл пустой прозрачной заглушкой из одних точек '.'."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        pal = data.get("diffuse_palette", {})
        return len(pal) <= 1 and "." in pal
    except Exception:
        return True


def bootstrap_assets_if_needed(procedural_assets, hero_builder_fn=None):
    root = get_assets_root()
    os.makedirs(root, exist_ok=True)
    manifest = load_manifest()
    changed = False

    rev3_roles = {
        "floor_0", "floor_3", "floor_4", "floor_5", "floor_6", "wall", "wall_wood", "wall_cave",
        "ov_pebbles", "ov_moss", "ov_cracks", "ov_planks_wear",
        "rat_cultist", "rat_king", "wolf", "tavern_table", "bar_counter", "bed", "woven_rug"
    }

    for cat_key, cat_data in ASSET_CATALOG.items():
        cat_dir = os.path.join(root, cat_key)
        os.makedirs(cat_dir, exist_ok=True)
        for role_id, (ru_name, sz) in cat_data["items"].items():
            default_rrot = (role_id in DEFAULT_RANDOM_ROT_ROLES)
            if role_id not in manifest:
                manifest[role_id] = {
                    "file": role_id,
                    "name": ru_name,
                    "cat": cat_key,
                    "size": list(sz),
                    "random_rot": default_rrot,
                    "rev": 5
                }
                changed = True
            elif "random_rot" not in manifest[role_id]:
                manifest[role_id]["random_rot"] = default_rrot
                changed = True

            rrot_flag = bool(manifest[role_id].get("random_rot", default_rrot))
            file_stem = manifest[role_id]["file"]
            dtex_path = os.path.join(cat_dir, f"{file_stem}.dtex")

            if role_id in rev3_roles and manifest[role_id].get("rev", 1) < 5 and role_id in procedural_assets:
                manifest[role_id]["size"] = list(sz)
                manifest[role_id]["name"] = ru_name
                manifest[role_id]["rev"] = 5
                d_s, n_s = procedural_assets[role_id]
                save_dtex_frames(dtex_path, role_id, file_stem, ru_name, cat_key, [(d_s, n_s)], fps=4, random_rot=rrot_flag)
                changed = True
                continue

            # Если файла нет ИЛИ он оказался пустой заглушкой из точек "." — запекаем реальную процедурную текстуру!
            need_bake = (not os.path.isfile(dtex_path)) or (
                role_id in procedural_assets and _is_dtex_empty_blank(dtex_path)
            )
            if need_bake:
                if role_id == "floor_2" and "_water_frames" in procedural_assets:
                    save_dtex_frames(dtex_path, role_id, file_stem, manifest[role_id]["name"], cat_key, procedural_assets["_water_frames"], fps=4, random_rot=rrot_flag)
                    changed = True
                    continue
                elif role_id == "floor_tar_pit" and "_tar_pit_frames" in procedural_assets:
                    save_dtex_frames(dtex_path, role_id, file_stem, manifest[role_id]["name"], cat_key, procedural_assets["_tar_pit_frames"], fps=4, random_rot=rrot_flag)
                    changed = True
                    continue
                elif role_id == "floor_acid_pool" and "_acid_pool_frames" in procedural_assets:
                    save_dtex_frames(dtex_path, role_id, file_stem, manifest[role_id]["name"], cat_key, procedural_assets["_acid_pool_frames"], fps=4, random_rot=rrot_flag)
                    changed = True
                    continue
                elif role_id == "floor_lake_shallow" and "_lake_shallow_frames" in procedural_assets:
                    save_dtex_frames(dtex_path, role_id, file_stem, manifest[role_id]["name"], cat_key, procedural_assets["_lake_shallow_frames"], fps=4, random_rot=rrot_flag)
                    changed = True
                    continue
                elif role_id == "floor_lake_deep" and "_lake_deep_frames" in procedural_assets:
                    save_dtex_frames(dtex_path, role_id, file_stem, manifest[role_id]["name"], cat_key, procedural_assets["_lake_deep_frames"], fps=4, random_rot=rrot_flag)
                    changed = True
                    continue
                elif role_id == "floor_temple_water" and "_temple_water_frames" in procedural_assets:
                    save_dtex_frames(dtex_path, role_id, file_stem, manifest[role_id]["name"], cat_key, procedural_assets["_temple_water_frames"], fps=4, random_rot=rrot_flag)
                    changed = True
                    continue
                elif role_id == "campfire" and "_campfire_frames" in procedural_assets:
                    save_dtex_frames(dtex_path, role_id, file_stem, manifest[role_id]["name"], cat_key, procedural_assets["_campfire_frames"], fps=6, random_rot=rrot_flag)
                    changed = True
                    continue
                elif role_id in procedural_assets:
                    d_s, n_s = procedural_assets[role_id]
                elif role_id == "hero_base" and hero_builder_fn is not None:
                    d_s, n_s = hero_builder_fn((200, 70, 75), "leather", False, True, True)
                else:
                    d_s = pygame.Surface(sz, pygame.SRCALPHA)
                    n_s = pygame.Surface(sz, pygame.SRCALPHA)
                    n_s.fill((128, 128, 255, 0))
                save_dtex_frames(dtex_path, role_id, file_stem, manifest[role_id]["name"], cat_key, [(d_s, n_s)], fps=4, random_rot=rrot_flag)
                changed = True

    if not manifest.get("_normals_10_strict", False):
        for cat_key, cat_data in ASSET_CATALOG.items():
            cat_dir = os.path.join(root, cat_key)
            for role_id in cat_data["items"]:
                m_info = manifest.get(role_id)
                if not isinstance(m_info, dict):
                    continue
                dtex_path = os.path.join(cat_dir, f"{m_info['file']}.dtex")
                if os.path.isfile(dtex_path):
                    try:
                        meta, fr_list, fps = load_dtex_frames(dtex_path)
                        rrot = bool(meta.get("random_rot", m_info.get("random_rot", role_id in DEFAULT_RANDOM_ROT_ROLES)))
                        save_dtex_frames(dtex_path, role_id, m_info["file"], m_info["name"], cat_key, fr_list, fps=fps, random_rot=rrot)
                    except Exception:
                        pass
        manifest["_normals_10_strict"] = True
        changed = True

    if changed:
        save_manifest(manifest)


def load_custom_dtex_animations(assets_dict):
    root = get_assets_root()
    manifest = load_manifest()
    anim_bank = {}

    for cat_key, cat_data in ASSET_CATALOG.items():
        cat_dir = os.path.join(root, cat_key)
        for role_id in cat_data["items"]:
            default_rrot = (role_id in DEFAULT_RANDOM_ROT_ROLES)
            m_info = manifest.get(role_id, {"file": role_id, "name": cat_data["items"][role_id][0], "random_rot": default_rrot})
            fpath = os.path.join(cat_dir, f"{m_info['file']}.dtex")
            if not os.path.isfile(fpath):
                fpath = os.path.join(cat_dir, f"{role_id}.dtex")

            if os.path.isfile(fpath):
                try:
                    meta, frames_list, fps = load_dtex_frames(fpath)
                    rrot = bool(meta.get("random_rot", m_info.get("random_rot", default_rrot)))
                    assets_dict[role_id] = frames_list[0]
                    anim_bank[role_id] = {
                        "frames": frames_list,
                        "fps": max(1, fps),
                        "name": meta.get("name", m_info["name"]),
                        "file": m_info["file"],
                        "random_rot": rrot
                    }
                except Exception:
                    pass
    return anim_bank