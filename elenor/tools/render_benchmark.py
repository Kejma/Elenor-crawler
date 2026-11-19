"""Compare direct window output with a synchronous readback of the same scene."""
import argparse
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

import numpy as np
import pygame

from elenor.config import CANVAS_H, SCALE, SCREEN_H, SCREEN_W, TILE_H, TILE_W, VIEW_H, VIEW_W
from elenor.game.controller import GameController
from elenor.profile import get_profile_dir
from elenor.rendering.lighting import GPULightShader


def capture_scene(game, campaign):
    game.reset_run(campaign, seed=807)
    if campaign == "rats":
        game.player.x, game.player.y = 23.5, 21.1
    dungeon = game.dungeon
    x, y = game.player.x * TILE_W, game.player.y * TILE_H
    cam_x, cam_y = round(x - VIEW_W / 2), round(y - VIEW_H / 2)
    mask, tiles, _ = dungeon.compute_nox_fov(x, y, cam_x, cam_y)
    lights = [
        dict(pos=(light["x"] * TILE_W + 8 - cam_x, light["y"] * TILE_H + 7 - cam_y, 23),
             radius=light["radius"], color=light["color"])
        for light in dungeon.braziers + dungeon.room_lights
    ]
    lights.append(dict(pos=(x - cam_x + 12, y - cam_y - 22, 24),
                       radius=115, color=(1.2, .72, .32)))
    screen = pygame.Surface((SCREEN_W, SCREEN_H))
    ui = dict(game.loc["ui"], _game_ref=game, _fx_mgr=game.fx, _perks_db=game.loc["perks"])
    fog = pygame.Surface((VIEW_W, CANVAS_H), pygame.SRCALPHA)
    # Capture the inputs at the normal lighting call without advancing the scene.
    with patch.object(game.renderer.gpu_shader, "render_lit_surface",
                      return_value=pygame.Surface((VIEW_W, CANVAS_H))) as lighting:
        game.renderer.render_frame(screen, dungeon, game.player, [], game.objects, [], [], [],
                                   cam_x, cam_y, mask, tiles, lights, "", ui, False, (0, 0), None)
    if campaign == "jungle":
        cloud = dict(wx=game.player.x, wy=game.player.y, radius=5, density=.4,
                     color=(.55, .7, .65), timer=None)
        game.renderer.fog_renderer.render(fog, dungeon, [cloud], lights, mask,
                                          game.renderer.entity_y_canvas, cam_x, cam_y, 0)
    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    overlay.blit(pygame.transform.scale_by(fog, SCALE), (0, 0))
    hud = screen.subsurface((0, CANVAS_H * SCALE, SCREEN_W, SCREEN_H - CANVAS_H * SCALE))
    overlay.blit(hud, (0, CANVAS_H * SCALE))
    return lighting.call_args, overlay


def compare(game, ctx, campaign, frames):
    shader = game.renderer.gpu_shader
    call, overlay = capture_scene(game, campaign)
    overlay_tex = ctx.texture(overlay.get_size(), 4, pygame.image.tobytes(overlay, "RGBA"))
    copied_tex = ctx.texture((VIEW_W, CANVAS_H), 3)
    for tex in (overlay_tex, copied_tex, shader.tex_out):
        tex.filter = (shader.moderngl.NEAREST, shader.moderngl.NEAREST)
    program = ctx.program(
        vertex_shader="""#version 330
            out vec2 uv;
            void main() {
                vec2 p = vec2(gl_VertexID % 2, gl_VertexID / 2);
                gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
                uv = vec2(p.x, 1.0 - p.y);
            }""",
        fragment_shader=f"""#version 330
            uniform sampler2D world;
            uniform sampler2D overlay;
            in vec2 uv;
            out vec4 color;
            void main() {{
                vec4 top = texture(overlay, uv);
                vec3 base = texture(world, vec2(uv.x, min(uv.y * {SCREEN_H / (CANVAS_H * SCALE)}, 1.0))).rgb;
                color = vec4(mix(base, top.rgb, top.a), 1.0);
            }}""",
    )
    program["world"].value = 0
    program["overlay"].value = 1
    quad = ctx.vertex_array(program, [])
    samples = {False: [], True: []}

    def draw(readback):
        lit = shader.render_lit_surface(*call.args, **call.kwargs, readback=readback)
        if readback:
            copied_tex.write(pygame.image.tobytes(lit, "RGB"), alignment=1)
            lit = copied_tex
        ctx.screen.use()
        ctx.viewport = (0, 0, *ctx.screen.size)
        lit.use(0)
        overlay_tex.use(1)
        quad.render(shader.moderngl.TRIANGLE_STRIP, vertices=4)

    try:
        draw(True)
        reference = ctx.screen.read(components=3)
        draw(False)
        if reference != ctx.screen.read(components=3):
            raise RuntimeError("The two presentation paths produced different pixels.")
        for block in range(4):
            for readback in (True, False) if block % 2 == 0 else (False, True):
                for index in range(frames // 4 + 5):
                    if any(event.type == pygame.QUIT for event in pygame.event.get()):
                        return None
                    start = perf_counter()
                    draw(readback)
                    pygame.display.flip()
                    if index >= 5:
                        samples[readback].append((perf_counter() - start) * 1000)
    finally:
        for resource in (quad, program, copied_tex, overlay_tex):
            resource.release()

    def summary(readback):
        median, p95 = np.percentile(samples[readback], [50, 95])
        return f"{median:.2f}/{p95:.2f}"

    return f"{campaign} n={len(samples[True])} readback={summary(True)} direct={summary(False)}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=120, help="Samples per scene and path (default 120)")
    args = parser.parse_args()
    if args.frames < 20:
        parser.error("--frames must be at least 20")

    import moderngl

    pygame.init()
    try:
        # Set up the game with its normal Pygame surfaces before opening the GL window.
        game = GameController()
        pygame.display.quit()
        pygame.display.init()
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
        pygame.display.set_mode((960, 540), pygame.OPENGL | pygame.DOUBLEBUF, vsync=0)
        pygame.display.set_caption("Elenor · GPU presentation benchmark")
        ctx = moderngl.create_context(require=330)
        game.renderer.gpu_shader = GPULightShader(ctx)
        rows = [f"{ctx.info['GL_RENDERER']} · milliseconds, median/p95"]
        for campaign in ("rats", "jungle"):
            result = compare(game, ctx, campaign, args.frames)
            if result is None:
                break
            rows.append(result)
        report = "\n".join(rows) + "\n"
        path = Path(get_profile_dir()) / "performance-prototype.log"
        path.write_text(report, encoding="utf-8")
        print(report, end="")
        print(path)
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
