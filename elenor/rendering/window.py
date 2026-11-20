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
_TOP_BAND_H = 212
_THOUGHT_Y = VIEW_H * SCALE
_HUD_Y = CANVAS_H * SCALE
_ROW_BYTES = SCREEN_W * 4
_TOP_WIDGET_RECTS = (
    pygame.Rect(0, 0, 270, _TOP_BAND_H),
    pygame.Rect(600, 0, 720, 48),
    pygame.Rect(1520, 0, SCREEN_W - 1520, 42),
)


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
        # Match SDL's 32-bit font and alpha surfaces so blits stay on their fast path.
        # OpenGL swizzles the same backing bytes when sampling the texture.
        self.ui_pixels = bytearray(SCREEN_W * SCREEN_H * 4)
        self.canvas = pygame.image.frombuffer(self.ui_pixels, (SCREEN_W, SCREEN_H), "BGRA")
        self.ui = ctx.texture((SCREEN_W, SCREEN_H), 4)
        self.ui.swizzle = "BGRA"
        view = memoryview(self.ui_pixels)
        self.ui_view = view
        self.ui_top = view[:_TOP_BAND_H * _ROW_BYTES]
        self.ui_thought = view[_THOUGHT_Y * _ROW_BYTES:_HUD_Y * _ROW_BYTES]
        self.ui_hud = view[_HUD_Y * _ROW_BYTES:]
        self.hud_surface = None
        self.uploaded_hud = None
        self.middle_dirty = False
        self.top_dirty = True
        self.thought_dirty = True
        self.full_dirty = True
        self.prev_full_dirty = True
        self.world_rects = []
        self.prev_world_rects = []
        self.dev_pixels = bytearray(SCREEN_W * _THOUGHT_Y * 4)
        self.dev_view = memoryview(self.dev_pixels)
        self.dev_canvas = pygame.image.frombuffer(self.dev_pixels, (SCREEN_W, _THOUGHT_Y), "BGRA")
        self.dev_ui = ctx.texture((SCREEN_W, _THOUGHT_Y), 4)
        self.dev_ui.swizzle = "BGRA"
        self._dev_next = []
        self._dev_prev = []
        self.has_dev_ui = False
        self._last_probe_time = 0.0
        self._probe_dungeon = None
        self._probe_revision = -1
        self.native_fx = ctx.texture((VIEW_W, VIEW_H), 4)
        self.native_fx.swizzle = "BGRA"
        self.native_fx.filter = (self.gl.NEAREST, self.gl.NEAREST)
        self.native_fx_pixels = None
        self.native_fx_fov_mask = False
        self.lit_fx = ctx.texture((VIEW_W, VIEW_H), 4)
        self.lit_fx.swizzle = "BGRA"
        self.lit_fx.filter = (self.gl.NEAREST, self.gl.NEAREST)
        self.lit_fx_pixels = None
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
            uniform sampler2D native_fx;
            uniform sampler2D overlay;
            uniform sampler2D fov_tex;
            uniform sampler2D lit_fx;
            uniform sampler2D light_vis;
            uniform sampler2D dev_ui;
            uniform ivec3 viewport;
            uniform vec2 logical_scale;
            uniform bool has_scene;
            uniform bool has_fog;
            uniform bool has_lit_fx;
            uniform bool has_native_fx;
            uniform bool mask_native_fx;
            uniform bool has_dev_ui;
            out vec4 color;

            vec4 ui_tap(sampler2D layer, ivec2 coord) {{
                ivec2 end = ivec2({SCREEN_W - 1}, {SCREEN_H - 1});
                vec4 tap = texelFetch(layer, clamp(coord, ivec2(0), end), 0);
                return vec4(tap.rgb * tap.a, tap.a);
            }}

            vec4 sample_ui(sampler2D layer, ivec2 physical, ivec2 logical) {{
                if (logical_scale.x >= 1.0 && logical_scale.y >= 1.0) {{
                    vec4 tap = texelFetch(layer, logical, 0);
                    return vec4(tap.rgb * tap.a, tap.a);
                }}
                // Sharpen the bilinear weights while retaining subpixel edge coverage.
                vec2 point = (vec2(physical) + 0.5) * logical_scale - 0.5;
                ivec2 corner = ivec2(floor(point));
                vec2 weight = smoothstep(vec2(0.10), vec2(0.90), fract(point));
                vec4 top = mix(ui_tap(layer, corner), ui_tap(layer, corner + ivec2(1, 0)), weight.x);
                vec4 bottom = mix(ui_tap(layer, corner + ivec2(0, 1)), ui_tap(layer, corner + ivec2(1, 1)), weight.x);
                return mix(top, bottom, weight.y);
            }}

            void main() {{
                ivec2 p = ivec2(gl_FragCoord.xy) - viewport.xy;
                p.y = viewport.z - p.y - 1;
                ivec2 logical = ivec2(vec2(p) * logical_scale);
                ivec2 native_px = logical / {SCALE};
                vec3 base = vec3(0.0);
                if (has_scene && logical.y < {CANVAS_H * SCALE}) {{
                    base = texelFetch(world, native_px, 0).rgb;
                    if (has_fog && native_px.y < {VIEW_H}) {{
                        vec4 mist = texelFetch(fog, native_px, 0);
                        base = mix(base, mist.rgb, mist.a);
                    }}
                    if (has_lit_fx && native_px.y < {VIEW_H}) {{
                        vec4 lfx = texelFetch(lit_fx, native_px, 0);
                        float vis = texelFetch(fov_tex, native_px, 0).r * texelFetch(light_vis, native_px, 0).a;
                        base = mix(base, lfx.rgb, lfx.a * vis);
                    }}
                    if (has_native_fx && native_px.y < {VIEW_H}) {{
                        vec4 fx = texelFetch(native_fx, native_px, 0);
                        if (mask_native_fx) fx.a *= texelFetch(fov_tex, native_px, 0).r;
                        base = mix(base, fx.rgb, fx.a);
                    }}
                }}
                vec4 ui = sample_ui(overlay, p, logical);
                vec3 out_col = base * (1.0 - ui.a) + ui.rgb;
                if (has_dev_ui && logical.y < {_THOUGHT_Y}) {{
                    vec4 dev = sample_ui(dev_ui, p, logical);
                    out_col = out_col * (1.0 - dev.a) + dev.rgb;
                }}
                color = vec4(out_col, 1.0);
            }}
        """)
        for unit, name in enumerate(("world", "fog", "native_fx", "overlay", "fov_tex", "lit_fx", "light_vis", "dev_ui")):
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
        if self.pending or self.thought_location is not dungeon:
            self.collect(dungeon, timings, profile_key)
        elif timings is not None:
            timings["probe"] = 0.0
        now = perf_counter()
        if (dungeon is self._probe_dungeon
                and dungeon.geometry_revision == self._probe_revision
                and now - self._last_probe_time < 0.05):
            return None
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
        self._last_probe_time = perf_counter()
        self._probe_dungeon = dungeon
        self._probe_revision = dungeon.geometry_revision
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

    def mark_world_rect(self, x, y, w, h):
        r = pygame.Rect(int(x), int(y), int(w), int(h)).clip((0, 0, SCREEN_W, _THOUGHT_Y))
        if r.width > 0 and r.height > 0:
            self.world_rects.append(r)
            if r.top < _TOP_BAND_H and any(r.colliderect(tw) for tw in _TOP_WIDGET_RECTS):
                self.top_dirty = True

    def mark_world_y(self, y0, y1):
        self.mark_world_rect(0, y0, SCREEN_W, int(y1) - int(y0))

    def set_dev_panel(self, name, rect, key, surface):
        self._dev_next.append((name, rect, key, surface))

    def begin_ui_frame(self, full_clear=False):
        self._dev_next = []
        if self.prev_full_dirty or full_clear:
            self.canvas.fill((0, 0, 0, 0))
            self.uploaded_hud = None
            self.thought_dirty = True
            self.top_dirty = True
            self.prev_world_rects = []
            if full_clear:
                self.prev_full_dirty = True
        else:
            self.top_dirty = False
            for r in self.prev_world_rects:
                self.canvas.fill((0, 0, 0, 0), r)
                if r.top < _TOP_BAND_H and any(r.colliderect(tw) for tw in _TOP_WIDGET_RECTS):
                    self.top_dirty = True
        self.world_rects = []
        self.middle_dirty = False
        self.full_dirty = bool(full_clear)
        self.native_fx_pixels = None
        self.native_fx_fov_mask = False
        self.lit_fx_pixels = None

    def present(self, viewport_rect, window_size, gameplay, timings=None):
        started = perf_counter() if timings is not None else 0.0
        hud = self.hud_surface if gameplay else None
        if not gameplay:
            self.ui.write(self.ui_pixels)
            self.uploaded_hud = None
            self.prev_full_dirty = True
            self.prev_world_rects = []
            self.thought_dirty = True
        elif self.full_dirty or self.prev_full_dirty:
            self.ui.write(self.ui_pixels)
            self.uploaded_hud = hud if not self.full_dirty else None
            self.prev_world_rects = self.world_rects
            self.prev_full_dirty = self.full_dirty
            self.thought_dirty = False
        else:
            if self.middle_dirty:
                self.mark_world_y(0, _THOUGHT_Y)
            if self.top_dirty:
                self.ui.write(self.ui_top, viewport=(0, 0, SCREEN_W, _TOP_BAND_H))
            dirty_rects = []
            for r in (*self.prev_world_rects, *self.world_rects):
                if self.top_dirty:
                    r = r.clip((0, _TOP_BAND_H, SCREEN_W, _THOUGHT_Y - _TOP_BAND_H))
                if r.width > 0 and r.height > 0:
                    dirty_rects.append(r)
            if len(dirty_rects) > 1:
                merged = []
                for r in dirty_rects:
                    for i, m in enumerate(merged):
                        if m.colliderect(r):
                            merged[i] = m.union(r)
                            break
                    else:
                        merged.append(r)
                dirty_rects = [merged[0].unionall(merged[1:])] if len(merged) > 6 else merged
            for r in dirty_rects:
                if r.width == SCREEN_W:
                    self.ui.write(
                        self.ui_view[r.y * _ROW_BYTES:(r.y + r.height) * _ROW_BYTES],
                        viewport=(0, r.y, SCREEN_W, r.height),
                    )
                else:
                    self.ui.write(
                        pygame.image.tobytes(self.canvas.subsurface(r), "BGRA"),
                        viewport=(r.x, r.y, r.width, r.height),
                    )
            if self.thought_dirty:
                self.ui.write(self.ui_thought, viewport=(0, _THOUGHT_Y, SCREEN_W, _HUD_Y - _THOUGHT_Y))
            if hud is None:
                self.ui.write(self.ui_hud, viewport=(0, _HUD_Y, SCREEN_W, SCREEN_H - _HUD_Y))
                self.uploaded_hud = None
            elif hud is not self.uploaded_hud:
                self.ui.write(self.ui_hud, viewport=(0, _HUD_Y, SCREEN_W, SCREEN_H - _HUD_Y))
                self.uploaded_hud = hud
            self.prev_world_rects = self.world_rects
            self.prev_full_dirty = False
            self.thought_dirty = False
        if gameplay:
            next_sig = [(n, r, k) for n, r, k, _ in self._dev_next]
            if next_sig != self._dev_prev:
                rects = [r for _, r, _ in self._dev_prev] + [r for _, r, _, _ in self._dev_next]
                if rects:
                    dirty = rects[0].unionall(rects[1:]).clip((0, 0, SCREEN_W, _THOUGHT_Y))
                    if dirty.width > 0 and dirty.height > 0:
                        self.dev_canvas.fill((0, 0, 0, 0), dirty)
                        for _, rect, _, surf in self._dev_next:
                            self.dev_canvas.blit(surf, rect.topleft)
                        if dirty.width == SCREEN_W:
                            self.dev_ui.write(
                                self.dev_view[dirty.y * _ROW_BYTES:(dirty.y + dirty.height) * _ROW_BYTES],
                                viewport=(0, dirty.y, SCREEN_W, dirty.height),
                            )
                        else:
                            self.dev_ui.write(
                                pygame.image.tobytes(self.dev_canvas.subsurface(dirty), "BGRA"),
                                viewport=(dirty.x, dirty.y, dirty.width, dirty.height),
                            )
                self._dev_prev = [(n, r.copy(), k) for n, r, k in next_sig]
            self.has_dev_ui = bool(self._dev_next)
        if gameplay and self.upload_fog is not None:
            self.software_fog.write(pygame.image.tobytes(self.upload_fog, "RGBA"))
        has_nfx = gameplay and self.native_fx_pixels is not None
        if has_nfx:
            self.native_fx.write(self.native_fx_pixels)
        has_lfx = gameplay and self.lit_fx_pixels is not None
        if has_lfx:
            self.lit_fx.write(self.lit_fx_pixels)
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
        self.present_program["has_lit_fx"].value = scene is not None and has_lfx
        self.present_program["has_native_fx"].value = scene is not None and has_nfx
        self.present_program["mask_native_fx"].value = self.native_fx_fov_mask
        self.present_program["has_dev_ui"].value = gameplay and self.has_dev_ui
        (scene if scene is not None else self.probe).use(0)
        self.software_fog.use(1)
        self.native_fx.use(2)
        self.ui.use(3)
        self.shader.tex_fov.use(4)
        self.lit_fx.use(5)
        self.shader.tex_out.use(6)
        self.dev_ui.use(7)
        self.quad.render(self.gl.TRIANGLE_STRIP, vertices=4)

    def close(self):
        for slot in self.pending:
            self.fences.delete(slot.fence)
        self.pending.clear()
        self.ctx.release()
