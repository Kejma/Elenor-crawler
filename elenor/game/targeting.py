def dungeon_los_ok(dungeon, x0, y0, x1, y1):
    return dungeon.has_line_of_sight(x0, y0, x1, y1, 4.0)


def is_cursor_on_mob(mob, wx, wy):
    """Checks if world cursor (wx, wy) is over the mob's sprite (supports 1x1 mobs and 2x2 bosses!)."""
    if getattr(mob, "size_tiles", 1) >= 2:
        return abs(wx - mob.x) <= 1.08 and (mob.y - 1.55) <= wy <= (mob.y + 0.95)
    return abs(wx - mob.x) <= 0.55 and (mob.y - 1.02) <= wy <= (mob.y + 0.52)


