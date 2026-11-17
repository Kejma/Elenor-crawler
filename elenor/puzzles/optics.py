MIRROR_SOLID_KINDS = {
    "light_emitter",
    "light_emitter_off",
    "light_receiver_off",
    "light_receiver_on",
    "mirror_rot_0", "mirror_rot_1", "mirror_rot_2", "mirror_rot_3",
    "mirror_move_0", "mirror_move_1", "mirror_move_2", "mirror_move_3",
    "mirror_double_0", "mirror_double_1",
}

SINGLE_REFLECT_MAP = {
    0: {(0, 1): (1, 0),   (-1, 0): (0, -1)},
    1: {(0, -1): (1, 0),  (-1, 0): (0, 1)},
    2: {(0, -1): (-1, 0), (1, 0): (0, 1)},
    3: {(0, 1): (-1, 0),  (1, 0): (0, -1)},
}

SINGLE_FRONT_NORMAL = {
    0: (1, -1),   # NE ↗
    1: (1, 1),    # SE ↘
    2: (-1, 1),   # SW ↙
    3: (-1, -1),  # NW ↖
}

DOUBLE_REFLECT_MAP = {
    0: {(0, 1): (1, 0), (-1, 0): (0, -1), (0, -1): (-1, 0), (1, 0): (0, 1)},
    1: {(0, -1): (1, 0), (-1, 0): (0, 1), (0, 1): (-1, 0), (1, 0): (0, -1)},
}


