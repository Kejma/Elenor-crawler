"""The float, strike and reeling state for one cast."""

from dataclasses import dataclass
import random


@dataclass(frozen=True)
class FishProfile:
    # Small float movements, measured in seconds before the full bite.
    taps: tuple
    bite_window: float
    pull: float
    surge_every: float
    surge_length: float
    reel_speed: float


FINISHED = frozenset(("early", "missed", "snapped", "escaped", "caught"))


PROFILES = {
    "shell": FishProfile((), 1.9, 0.10, 3.0, 0, 0.39),
    "shoal": FishProfile((1.0, 0.72, 0.42), 1.35, 0.24, 2.1, 0.7, 0.26),
    "dart": FishProfile((0.28,), 0.95, 0.28, 1.50, 0.76, 0.24),
    "deep": FishProfile((1.25, 0.55), 1.20, 0.43, 2.5, 1.22, 0.23),
    "trophy": FishProfile((0.95, 0.3), 1.12, 0.46, 2.15, 1.0, 0.20),
}

# The first catch in each stretch is characteristic of that water. Other
# entries keep the full supplied catalogue discoverable at this test location.
POOLS = {
    "eddy": (
        (
            "shoal",
            "bitterling striped_perch redfin_roach young_roach peled bigeye_sprat "
            "toothless_male toothless_female young_drunkard",
        ),
        ("shell", "closed_shell"),
        (
            "deep",
            "scaly_goby brown_rotan green_rotan tiger_crayfish fermented_drunkard",
        ),
        ("trophy", "alpha_roach river_firefly"),
    ),
    "snag": (
        (
            "deep",
            "big_catfish young_catfish mud_armored stone_sterlet swamp_sterlet "
            "yellow_burbot big_burbot young_paddlefish coal_wolffish silver_carp",
        ),
        ("dart", "wriggling_pike searing_eel"),
        (
            "trophy",
            "aradon_paddlefish big_swamp_pike deep_water_snake giant_fierce_catfish albino_paddlefish",
        ),
    ),
    "current": (
        (
            "dart",
            "flame_piranha neon_chub slippery_mackerel kelp_mackerel scad "
            "rainbow_trout silver_coho moon_herring",
        ),
        ("deep", "snow_char"),
        ("trophy", "big_coho sabrefish big_sabrefish angel_snapper"),
    ),
}


def choose_catch(spot):
    options = []
    weights = []
    for behavior, names in POOLS[spot]:
        for name in names.split():
            options.append((f"fish_{name}", PROFILES[behavior]))
            weights.append(1 if behavior == "trophy" else 4)
    weights[0] = 14
    return random.choices(options, weights, k=1)[0]


class FishingCast:
    def __init__(self, spot, origin, target, fish_id, profile, delay):
        self.spot = spot
        self.origin = origin
        self.target = target
        self.fish_id = fish_id
        self.profile = profile
        self.delay = delay
        self.phase = "cast"
        self.elapsed = 0.0
        self.tension = 0.22
        self.progress = 0.0
        self.reeling = False

    @property
    def surging(self):
        return (
            self.phase == "reel"
            and 1.05 <= self.elapsed
            and (
                (self.elapsed - 1.05) % self.profile.surge_every
                < self.profile.surge_length
            )
        )

    @property
    def bob(self):
        if self.phase == "bite":
            return 1.0
        if self.phase == "wait":
            until_bite = self.delay - self.elapsed
            return max(
                (
                    max(0, 1 - abs(until_bite - tap) / 0.13) * 0.43
                    for tap in self.profile.taps
                ),
                default=0,
            )
        return 0.0

    def press(self):
        if self.phase == "bite":
            self.phase, self.elapsed = "reel", 0.0
            self.reeling = True
        elif self.phase == "wait":
            self.phase = "early"
        elif self.phase == "reel":
            self.reeling = True

    def update(self, dt):
        if self.phase in FINISHED:
            return
        self.elapsed += dt
        if self.phase == "cast" and self.elapsed >= 0.36:
            self.phase, self.elapsed = "wait", 0.0
        elif self.phase == "wait" and self.elapsed >= self.delay:
            self.phase, self.elapsed = "bite", 0.0
        elif self.phase == "bite" and self.elapsed > self.profile.bite_window:
            self.phase = "missed"
        elif self.phase == "reel":
            pull = self.profile.pull + (0.57 if self.surging else 0.0)
            change = pull if self.reeling else -0.67
            self.tension = max(0.06, self.tension + change * dt)
            if self.reeling:
                pace = self.profile.reel_speed * (0.45 if self.surging else 1.0)
                self.progress += pace * dt
            if self.tension >= 1.0:
                self.phase = "snapped"
            elif self.progress >= 1:
                self.phase = "caught"
            elif self.elapsed >= 20:
                self.phase = "escaped"


def start_fishing(game, stand):
    if (
        game.player.pending_action
        or game.player.hp <= 0
        or game.inv_open
        or game.levelup_choices
    ):
        return
    cast_at(game, stand.fishing_spot, stand.fishing_target)


def cast_at(game, spot, target):
    fish_id, profile = choose_catch(spot)
    game.fishing_cast = FishingCast(
        spot,
        (game.player.x, game.player.y),
        target,
        fish_id,
        profile,
        random.uniform(2.1, 3.8),
    )
    game.player.is_moving = False


def update_fishing(game, dt):
    cast = game.fishing_cast
    previous = cast.phase
    cast.update(dt)
    if cast.phase == previous:
        return
    if cast.phase in ("wait", "bite"):
        game.play_spatial("step_water", *cast.target)
    elif cast.phase == "caught":
        game.fishing_catches[cast.fish_id] = (
            game.fishing_catches.get(cast.fish_id, 0) + 1
        )
        from elenor.rendering.fishing import FISH_CATALOG_SPECS

        name = FISH_CATALOG_SPECS[cast.fish_id][0].removeprefix("Улов: ")
        game.add_log("event", game.loc["fishing"]["catch_log"].format(fish=name))
        game.sfx.play("coin_pickup")
    elif cast.phase in ("missed", "snapped", "escaped"):
        game.sfx.play("step_water")
