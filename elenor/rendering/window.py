"""Window OpenGL presentation and a small, non-blocking exploration readback."""
from collections import deque
import ctypes
import sys
from time import perf_counter

import numpy as np
import pygame

from elenor.config import (
    CANVAS_H, SCALE, SCREEN_H, SCREEN_W, THOUGHT_BOX_BG, THOUGHT_BOX_X, THOUGHT_BOX_Y,
    TILE_H, TILE_W, VIEW_H, VIEW_W,
)
from elenor.world.exploration import remember_tiles


_QUAD = """#version 330 core
    void main() {
        vec2 pos = vec2(gl_VertexID % 2, gl_VertexID / 2);
        gl_Position = vec4(pos * 2.0 - 1.0, 0.0, 1.0);
    }
"""
_PROBE_WIDTH = VIEW_W // TILE_W + 2
_PROBE_ROWS = VIEW_H // TILE_H + 2
_PROBE_SIZE = (_PROBE_WIDTH, _PROBE_ROWS + 1)


class _Fences:
    def __init__(self, loader):
        prototype = ctypes.WINFUNCTYPE if sys.platform == "win32" else ctypes.CFUNCTYPE

        def bind(name, result, *parameters):
            address = loader.load_opengl_function(name)
            if not address or address <= 3 or address == ctypes.c_void_p(-1).value:
                raise RuntimeError(f"OpenGL function unavailable: {name}")
            return prototype(result, *parameters)(address)

        self.create = bind("glFenceSync", ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint)
        self.wait = bind("glClientWaitSync", ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint64)
        self.delete = bind("glDeleteSync", None, ctypes.c_void_p)

    def ready(self, fence):
        # GL_ALREADY_SIGNALED or GL_CONDITION_SATISFIED. A zero timeout never waits.
        return self.wait(fence, 0, 0) in (0x911A, 0x911C)


class _ProbeSlot:
    def __init__(self, ctx):
        self.buffer = ctx.buffer(reserve=_PROBE_SIZE[0] * _PROBE_SIZE[1] * 4, dynamic=True)
        self.fence = None
        self.timers = None
        self.survey = None
        self.timed = False
        self.fog = False
        self.profile_key = None


class GLWindow:
    def __init__(self, ctx, loader, shader):
        self.ctx = ctx
        self.shader = shader
        self.gl = shader.moderngl
        self.fences = _Fences(loader)
        # SDL draws UI in straight RGBA. The backing bytes upload without conversion.
        self.ui_pixels = bytearray(SCREEN_W * SCREEN_H * 4)
        self.canvas = pygame.image.frombuffer(self.ui_pixels, (SCREEN_W, SCREEN_H), "RGBA")
        self.ui = ctx.texture((SCREEN_W, SCREEN_H), 4)
        self.software_fog = ctx.texture((VIEW_W, VIEW_H), 4)
        self.visibility = ctx.texture((VIEW_W, CANVAS_H), 1, dtype="f4")
        self.last_visibility = None
        self.probe = ctx.texture(_PROBE_SIZE, 4, dtype="f1")
        self.probe_fbo = ctx.framebuffer([self.probe])
        self.pending = deque()
        self.slots = [_ProbeSlot(ctx) for _ in range(3)]
        self.scene = None
        self.upload_fog = None
        self.thought_color = THOUGHT_BOX_BG
        self.thought_location = None
        self.drawable = ctx.screen.size

        self.present_program = ctx.program(vertex_shader=_QUAD, fragment_shader=f"""#version 330 core
            uniform sampler2D world;
            uniform sampler2D fog;
            uniform sampler2D overlay;
            uniform ivec3 viewport;
            uniform vec2 logical_scale;
            uniform bool has_scene;
            uniform bool has_fog;
            out vec4 color;

            void main() {{
                ivec2 p = ivec2(gl_FragCoord.xy) - viewport.xy;
                p.y = viewport.z - p.y - 1;
                // Both layers derive their coordinates from the same logical pixel.
                ivec2 logical = ivec2(vec2(p) * logical_scale);
                ivec2 native_px = logical / {SCALE};
                vec3 base = vec3(0.0);
                if (has_scene && logical.y < {CANVAS_H * SCALE}) {{
                    base = texelFetch(world, native_px, 0).rgb;
                    if (has_fog && native_px.y < {VIEW_H}) {{
                        vec4 mist = texelFetch(fog, native_px, 0);
                        base = mix(base, mist.rgb, mist.a);
                    }}
                }}
                vec4 ui = texelFetch(overlay, logical, 0);
                color = vec4(mix(base, ui.rgb, ui.a), 1.0);
            }}
        """)
        for unit, name in enumerate(("world", "fog", "overlay")):
            self.present_program[name].value = unit
        self.quad = ctx.vertex_array(self.present_program, [])

        self.probe_program = ctx.program(vertex_shader=_QUAD, fragment_shader=f"""#version 330 core
            uniform sampler2D world;
            uniform sampler2D visibility;
            uniform ivec2 camera;
            uniform ivec2 origin;
            uniform bool survey;
            out vec4 result;

            void main() {{
                ivec2 tile = ivec2(gl_FragCoord.xy);
                if (tile.y == {_PROBE_ROWS}) {{
                    result = vec4(texelFetch(world, ivec2({THOUGHT_BOX_X + 8}, {THOUGHT_BOX_Y + 8}), 0).rgb, 1.0);
                    return;
                }}
                int count = 0;
                if (survey) {{
                    ivec2 center = (tile + origin) * ivec2({TILE_W}, {TILE_H})
                                  + ivec2({TILE_W // 2}, {TILE_H // 2}) - camera;
                    for (int x = -4; x <= 4; x += 4) {{
                        for (int y = -4; y <= 4; y += 4) {{
                            ivec2 pixel = center + ivec2(x, y);
                            if (any(lessThan(pixel, ivec2(0)))
                                || any(greaterThanEqual(pixel, ivec2({VIEW_W}, {VIEW_H})))) continue;
                            if (texelFetch(visibility, pixel, 0).r <= .5) continue;
                            vec3 rgb = round(texelFetch(world, pixel, 0).rgb * 255.0);
                            if (rgb.r + rgb.g + rgb.b >= 39.0) count++;
                        }}
                    }}
                }}
                result = vec4(count >= 2 ? 1.0 : 0.0, 0.0, 0.0, 1.0);
            }}
        """)
        self.probe_program["world"].value = 0
        self.probe_program["visibility"].value = 1
        self.probe_quad = ctx.vertex_array(self.probe_program, [])

    def collect(self, dungeon, timings=None, profile_key=None):
        if self.thought_location is not dungeon:
            self.thought_color = THOUGHT_BOX_BG
            self.thought_location = dungeon
        started = perf_counter() if timings is not None else 0.0
        while self.pending and self.fences.ready(self.pending[0].fence):
            slot = self.pending.popleft()
            self.fences.delete(slot.fence)
            slot.fence = None
            pixels = np.frombuffer(slot.buffer.read(), np.uint8).reshape(_PROBE_SIZE[1], _PROBE_WIDTH, 4)
            location, revision, origin, tiles, objects = slot.survey
            if location is dungeon:
                self.thought_color = tuple(int(c) for c in pixels[-1, 0, :3])
            if tiles and revision == location.geometry_revision:
                levels, columns = np.nonzero(pixels[:-1, :, 0])
                x, y = origin
                seen = {(int(col) + x, int(row) + y) for row, col in zip(levels, columns)} & tiles
                remember_tiles(location, seen, objects)
            if timings is not None and slot.timed and slot.profile_key == profile_key and location is dungeon:
                shadow, light, fog = slot.timers
                elapsed = shadow.elapsed, light.elapsed, fog.elapsed if slot.fog else 0
                if 0xFFFFFFFF not in elapsed:
                    timings["gpu"] = sum(elapsed) / 1e6
                    if slot.fog:
                        timings["fog_gpu"] = elapsed[2] / 1e6
            slot.survey = None

        if timings is not None:
            timings["probe"] = (perf_counter() - started) * 1000

    def begin_world(self, dungeon, timings, profile_key):
        self.collect(dungeon, timings, profile_key)
        slot = next((entry for entry in self.slots if entry.fence is None), None)
        if slot is not None:
            slot.timed = timings is not None
            slot.profile_key = profile_key
            if slot.timed and slot.timers is None:
                slot.timers = tuple(self.ctx.query(time=True) for _ in range(3))
        return slot

    def capture_survey(self, slot, shader, dungeon, objects, tiles, fov, lit_fov, cam_x, cam_y, gpu_fog):
        if slot is None:
            return
        camera = round(cam_x), round(cam_y)
        origin = camera[0] // TILE_W, camera[1] // TILE_H
        visibility = shader.tex_fov
        if fov is not lit_fov and tiles:
            if gpu_fog:
                visibility = shader.fog.visibility
            else:
                if fov is not self.last_visibility or fov.flags.writeable:
                    self.visibility.write(np.ascontiguousarray(fov.T, dtype=np.float32))
                    self.last_visibility = None if fov.flags.writeable else fov
                visibility = self.visibility
        self.probe_fbo.use()
        self.ctx.viewport = (0, 0, *_PROBE_SIZE)
        self.probe_program["camera"].value = camera
        self.probe_program["origin"].value = origin
        self.probe_program["survey"].value = bool(tiles)
        shader.tex_out.use(0)
        visibility.use(1)
        self.probe_quad.render(self.gl.TRIANGLE_STRIP, vertices=4)
        self.probe_fbo.read_into(slot.buffer, components=4)
        slot.fence = self.fences.create(0x9117, 0)  # GL_SYNC_GPU_COMMANDS_COMPLETE.
        if slot.fence is not None:
            slot.survey = dungeon, dungeon.geometry_revision, origin, tiles, tuple(objects) if tiles else ()
            slot.fog = gpu_fog
            self.pending.append(slot)

    def present(self, viewport_rect, window_size, gameplay, timings=None):
        started = perf_counter() if timings is not None else 0.0
        self.ui.write(self.ui_pixels)
        if gameplay and self.upload_fog is not None:
            self.software_fog.write(pygame.image.tobytes(self.upload_fog, "RGBA"))
        if timings is not None:
            timings["ui_upload"] = (perf_counter() - started) * 1000
        self.ctx.screen.use()
        x, y, width, height = viewport_rect
        if window_size != self.drawable:
            sx, sy = self.drawable[0] / window_size[0], self.drawable[1] / window_size[1]
            x, y, width, height = round(x * sx), round(y * sy), round(width * sx), round(height * sy)
        if (x, y, width, height) != (0, 0, *self.drawable):
            self.ctx.screen.clear(8 / 255, 6 / 255, 12 / 255, 1)
        viewport = (x, self.drawable[1] - y - height, width, height)
        self.ctx.viewport = viewport
        self.present_program["viewport"].value = (viewport[0], viewport[1], height)
        self.present_program["logical_scale"].value = (SCREEN_W / width, SCREEN_H / height)
        scene = self.scene if gameplay else None
        self.present_program["has_scene"].value = scene is not None
        self.present_program["has_fog"].value = scene is not None and self.upload_fog is not None
        (scene if scene is not None else self.probe).use(0)
        self.software_fog.use(1)
        self.ui.use(2)
        self.quad.render(self.gl.TRIANGLE_STRIP, vertices=4)

    def close(self):
        for slot in self.pending:
            self.fences.delete(slot.fence)
        self.pending.clear()
        self.ctx.release()
