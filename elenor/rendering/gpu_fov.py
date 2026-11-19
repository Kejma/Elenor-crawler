"""GPU 720-ray FOV shader writing directly into GPULightShader.tex_fov."""

import math
import numpy as np

from elenor.config import CANVAS_H, LOS_MAX_RADIUS, TILE_H, TILE_W, VIEW_H, VIEW_W


class GPUFov:
    RAYS = 720

    def __init__(self, shader):
        self.shader = shader
        self.ctx = shader.ctx
        self.gl = shader.moderngl
        ctx, gl = self.ctx, self.gl

        self.tex_rays = ctx.texture((self.RAYS, 1), 1, dtype="f4")
        self.tex_rays.filter = (gl.NEAREST, gl.NEAREST)
        self.ray_fbo = ctx.framebuffer([self.tex_rays])
        self.fov_fbo = ctx.framebuffer([shader.tex_fov])

        self.tex_sight = None
        self._sight_key = None
        self._last_key = None

        vert = """#version 330 core
            in vec2 in_vert;
            void main() { gl_Position = vec4(in_vert, 0.0, 1.0); }
        """

        self.ray_prog = ctx.program(
            vertex_shader=vert,
            fragment_shader=f"""#version 330 core
                uniform sampler2D u_sight;
                uniform vec2 u_origin;
                uniform ivec2 u_start_tile;
                out float stop;

                int tile_flag(ivec2 t, ivec2 sz) {{
                    if (t == u_start_tile) return 0;
                    if (t.x < 0 || t.y < 0 || t.x >= sz.x || t.y >= sz.y) return 32;
                    return int(round(texelFetch(u_sight, t, 0).r * 255.0));
                }}

                void main() {{
                    float angle = floor(gl_FragCoord.x) * {2.0 * math.pi / self.RAYS};
                    vec2 heading = vec2(cos(angle), sin(angle));
                    ivec2 sz = textureSize(u_sight, 0);
                    ivec2 prev = u_start_tile;
                    stop = {float(LOS_MAX_RADIUS)};
                    for (float d = 1.0; d <= {float(LOS_MAX_RADIUS)}; d += 1.0) {{
                        vec2 pos = u_origin + heading * d;
                        ivec2 t = ivec2(floor(pos / vec2({float(TILE_W)}, {float(TILE_H)})));
                        if (t.x < 0 || t.y < 0 || t.x >= sz.x || t.y >= sz.y) {{
                            stop = d;
                            break;
                        }}
                        if (t.x != prev.x && t.y != prev.y) {{
                            int f1 = tile_flag(ivec2(t.x, prev.y), sz);
                            int f2 = tile_flag(ivec2(prev.x, t.y), sz);
                            if ((f1 & 32) != 0 && (f2 & 32) != 0) {{
                                stop = d;
                                break;
                            }}
                        }}
                        int fl = tile_flag(t, sz);
                        if ((fl & 32) != 0) {{
                            stop = d;
                            break;
                        }}
                        if ((fl & 31) != 0) {{
                            vec2 o = pos / vec2({float(TILE_W)}, {float(TILE_H)}) - vec2(t) - 0.5;
                            bool trunk = dot(o, o) <= 0.0484;
                            bool bx = abs(o.y) <= 0.15 && ((fl & (o.x > 0.0 ? 2 : 4)) != 0);
                            bool by = abs(o.x) <= 0.15 && ((fl & (o.y > 0.0 ? 8 : 16)) != 0);
                            if (trunk || bx || by) {{
                                stop = d;
                                break;
                            }}
                        }}
                        prev = t;
                    }}
                }}
            """,
        )
        self.ray_prog["u_sight"].value = 0
        self.ray_vao = ctx.simple_vertex_array(self.ray_prog, shader.vbo, "in_vert")

        self.fov_prog = ctx.program(
            vertex_shader=vert,
            fragment_shader=f"""#version 330 core
                uniform sampler2D u_sight;
                uniform sampler2D u_rays;
                uniform vec2 u_origin;
                uniform vec2 u_cam;
                uniform ivec2 u_start_tile;
                out float out_fov;

                bool in_fan(vec2 pt, float bias) {{
                    vec2 d = pt - u_origin;
                    float dist = length(d);
                    if (dist < 1.0) return true;
                    if (dist > {float(LOS_MAX_RADIUS)}) return false;
                    float ang = atan(d.y, d.x);
                    if (ang < 0.0) ang += {2.0 * math.pi};
                    float fbin = ang * {self.RAYS / (2.0 * math.pi)};
                    int b0 = int(floor(fbin)) % {self.RAYS};
                    if (b0 < 0) b0 += {self.RAYS};
                    int b1 = (b0 + 1) % {self.RAYS};
                    float s0 = texelFetch(u_rays, ivec2(b0, 0), 0).r;
                    float s1 = texelFetch(u_rays, ivec2(b1, 0), 0).r;
                    float lim = mix(s0, s1, fract(fbin));
                    return dist <= lim + bias;
                }}

                void main() {{
                    ivec2 p = ivec2(gl_FragCoord.xy);
                    if (p.y >= {VIEW_H}) {{
                        out_fov = 1.0;
                        return;
                    }}
                    vec2 world = vec2(p) + 0.5 + u_cam;
                    ivec2 sz = textureSize(u_sight, 0);
                    ivec2 tile = ivec2(floor(world / vec2({float(TILE_W)}, {float(TILE_H)})));
                    if (tile.x < 0 || tile.y < 0 || tile.x >= sz.x || tile.y >= sz.y) {{
                        out_fov = 0.0;
                        return;
                    }}
                    int fl = (tile == u_start_tile) ? 0 : int(round(texelFetch(u_sight, tile, 0).r * 255.0));
                    if ((fl & 32) == 0) {{
                        out_fov = in_fan(world, 1.0) ? 1.0 : 0.0;
                        return;
                    }}
                    for (int dy = -1; dy <= 1; ++dy) {{
                        for (int dx = -1; dx <= 1; ++dx) {{
                            if (dx == 0 && dy == 0) continue;
                            ivec2 nb = tile + ivec2(dx, dy);
                            if (nb.x < 0 || nb.y < 0 || nb.x >= sz.x || nb.y >= sz.y) continue;
                            if (nb == u_start_tile) {{
                                out_fov = 1.0;
                                return;
                            }}
                            int nfl = int(round(texelFetch(u_sight, nb, 0).r * 255.0));
                            if ((nfl & 32) != 0) continue;
                            vec2 nb_min = vec2(nb) * vec2({float(TILE_W)}, {float(TILE_H)}) + 1.5;
                            vec2 nb_max = vec2(nb + 1) * vec2({float(TILE_W)}, {float(TILE_H)}) - 1.5;
                            vec2 c = (vec2(nb) + 0.5) * vec2({float(TILE_W)}, {float(TILE_H)});
                            if (in_fan(c, -0.5) || in_fan(clamp(u_origin, nb_min, nb_max), -0.5)) {{
                                out_fov = 1.0;
                                return;
                            }}
                        }}
                    }}
                    out_fov = 0.0;
                }}
            """,
        )
        self.fov_prog["u_sight"].value = 0
        self.fov_prog["u_rays"].value = 1
        self.fov_vao = ctx.simple_vertex_array(self.fov_prog, shader.vbo, "in_vert")

        self._u_ray_origin = self.ray_prog["u_origin"]
        self._u_ray_start = self.ray_prog["u_start_tile"]
        self._u_fov_origin = self.fov_prog["u_origin"]
        self._u_fov_cam = self.fov_prog["u_cam"]
        self._u_fov_start = self.fov_prog["u_start_tile"]

    def render(self, dungeon, world_ox, world_oy, cam_x, cam_y):
        ox = float(round(world_ox))
        oy = float(round(world_oy))
        cx = float(round(cam_x))
        cy = float(round(cam_y))
        closed_doors = tuple(point for point, door in dungeon.doors.items() if not door.is_open)
        key = (dungeon, dungeon.geometry_revision, closed_doors, ox, oy, cx, cy)
        if key == self._last_key and self.shader.uploaded_fov is None:
            return

        sight_key = (dungeon, dungeon.geometry_revision, closed_doors)
        if sight_key != self._sight_key:
            walls, roots = dungeon.sight_geometry(closed_doors)
            packed = (roots | (walls.astype(np.uint8) << 5))
            size = packed.shape
            if self.tex_sight is None or self.tex_sight.size != size:
                if self.tex_sight is not None:
                    self.tex_sight.release()
                self.tex_sight = self.ctx.texture(size, 1, dtype="f1")
                self.tex_sight.filter = (self.gl.NEAREST, self.gl.NEAREST)
            self.tex_sight.write(np.ascontiguousarray(packed.T))
            self._sight_key = sight_key

        w, h = self.tex_sight.size
        sx = max(0, min(w - 1, int(ox) // TILE_W))
        sy = max(0, min(h - 1, int(oy) // TILE_H))

        ctx, gl = self.ctx, self.gl
        ctx.disable(gl.BLEND)
        ctx.scissor = None

        self.ray_fbo.use()
        ctx.viewport = (0, 0, self.RAYS, 1)
        self._u_ray_origin.value = (ox, oy)
        self._u_ray_start.value = (sx, sy)
        self.tex_sight.use(0)
        self.ray_vao.render(gl.TRIANGLE_STRIP)

        self.fov_fbo.use()
        ctx.viewport = (0, 0, VIEW_W, CANVAS_H)
        self._u_fov_origin.value = (ox, oy)
        self._u_fov_cam.value = (cx, cy)
        self._u_fov_start.value = (sx, sy)
        self.tex_sight.use(0)
        self.tex_rays.use(1)
        self.fov_vao.render(gl.TRIANGLE_STRIP)

        self.shader.uploaded_fov = None
        self._last_key = key