"""Derive independent, stable seeds for synchronous world generation."""

from contextlib import contextmanager
from hashlib import blake2b
import random

MAX_RUN_SEED = (1 << 64) - 1


def parse_run_seed(text):
    text = text.strip()
    if not text:
        return None
    if len(text) > 20 or not text.isascii() or not text.isdecimal():
        raise ValueError("Expected an unsigned 64-bit decimal seed")
    seed = int(text)
    if seed > MAX_RUN_SEED:
        raise ValueError("Seed is larger than 64 bits")
    return seed


def derived_seed(seed, campaign, phase, depth=0, interior=None):
    parts = f"{seed}:{campaign}:{phase}:{depth}:{interior or ''}"
    return int.from_bytes(blake2b(parts.encode("ascii"), digest_size=8).digest(), "big")


@contextmanager
def generation_random(seed):
    """Isolate legacy generators that draw from the module-level RNG."""
    if seed is None:
        yield
        return
    previous = random.getstate()
    random.seed(seed)
    try:
        yield
    finally:
        random.setstate(previous)
