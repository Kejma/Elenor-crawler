"""Bounded cache for repeated tooltip and journal text measurements."""
from functools import lru_cache


@lru_cache(maxsize=256)
def wrap_lines(text, font, max_width):
    lines = []
    current = ''
    for word in text.split(' '):
        candidate = (current + ' ' + word).strip()
        if font.size(candidate)[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return tuple(lines)
