"""Scenery, rewards and mirror puzzles for Campaign II."""

from elenor.missions.jungle_encounters import populate_encounters

def populate_jungle_floor(game, Interactable):
    for x, y, kind in game.dungeon.jungle_props:
        game.objects.append(Interactable(x, y, kind))
    if game.dungeon.mirror_puzzle_info:
        from elenor.puzzles.mirrors import spawn_floor_mirror_puzzle

        spawn_floor_mirror_puzzle(
            game, Interactable, beam_color=(106, 224, 172), ambush_enabled=False
        )
    populate_encounters(game)
