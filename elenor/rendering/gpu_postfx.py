"""GPU post-processing: planar water reflections, wide multi-pass bloom, and GPU eye adaptation."""

import struct

from elenor.config import CANVAS_H, TILE_H, TILE_W, VIEW_H, VIEW_W


class GPUPostFX:
    def __init__(self, shader):
        self.ctx = shader.ctx
        self.gl = shader.moderngl
        ctx, gl = self.ctx, self.gl

        self.half_size = ((VIEW_W + 1) // 2, (VIEW_H + 1) // 2)
        self.quarter_size = ((self.half_size[0] + 1) // 2, (self.half_size[1] + 1) // 2)

        self.tex_refl = ctx.texture((VIEW_W, CANVAS_H), 4, dtype="f1")
        self.tex_refl.filter = (gl.NEAREST, gl.NEAREST)
        self.reflect_fbo = ctx.framebuffer([self.tex_refl])

        self.half_a = ctx.texture(self.half_size, 4, dtype="f1")
        self.half_b = ctx.texture(self.half_size, 4, dtype="f1")
        self.quarter_a = ctx.texture(self.quarter_size, 4, dtype="f1")
        self.quarter_b = ctx.texture(self.quarter_size, 4, dtype="f1")
        for tex in (self.half_a, self.half_b, self.quarter_a, self.quarter_b):
            tex.filter = (gl.LINEAR, gl.LINEAR)
            tex.repeat_x = False
            tex.repeat_y = False

        self.half_a_fbo = ctx.framebuffer([self.half_a])
        self.half_b_fbo = ctx.framebuffer([self.half_b])
        self.quarter_a_fbo = ctx.framebuffer([self.quarter_a])
        self.quarter_b_fbo = ctx.framebuffer([self.quarter_b])

        init_exp = struct.pack("4f", 1.0, 0.16, 1.0, 1.0)
        self.tex_exp = (
            ctx.texture((1, 1), 4, data=init_exp, dtype="f4"),
            ctx.texture((1, 1), 4, data=init_exp, dtype="f4"),
        )
        for tex in self.tex_exp:
            tex.filter = (gl.NEAREST, gl.NEAREST)
        self.exp_fbo = (ctx.framebuffer([self.tex_exp[0]]), ctx.framebuffer([self.tex_exp[1]]))
        self._exp_idx = 0
        self._last_time = None

        self.tex_final = ctx.texture((VIEW_W, CANVAS_H), 4, dtype="f1")
        self.tex_final.filter = (gl.NEAREST, gl.NEAREST)
        self.final_fbo = ctx.framebuffer([self.tex_final])

        vert = """#version 330 core
            in vec2 in_vert;
            out vec2 v_uv;
            void main() {
                gl_Position = vec4(in_vert, 0.0, 1.0);
                v_uv = in_vert * 0.5 + 0.5;
            }
        """

        self.reflect_prog = ctx.program(
            vertex_shader=vert,
            fragment_shader=f"""#version 330 core
                uniform sampler2D u_scene;
                uniform sampler2D u_mat;
                uniform sampler2D u_ent_y;
                uniform sampler2D u_fov;
                uniform sampler2D u_walls;
                uniform vec2 u_cam;
                uniform float u_time;
                out vec4 fragColor;

                void main() {{
                    ivec2 p = ivec2(gl_FragCoord.xy);
                    vec4 base = texelFetch(u_scene, p, 0);
                    if (p.y >= {VIEW_H}) {{
                        fragColor = base;
                        return;
                    }}
                    float fov = texelFetch(u_fov, p, 0).r;
                    if (fov <= 0.01) {{
                        fragColor = base;
                        return;
                    }}
                    vec4 mat = texelFetch(u_mat, p, 0);
                    float water = mat.b;
                    float ent_y = texelFetch(u_ent_y, p, 0).r;
                    if (water <= 0.08 || ent_y > -9000.0) {{
                        fragColor = base;
                        return;
                    }}

                    int dist_edge = 0;
                    for (int dy = 1; dy <= 24; ++dy) {{
                        int uy = p.y - dy;
                        if (uy < 0) break;
                        float u_water = texelFetch(u_mat, ivec2(p.x, uy), 0).b;
                        float u_ent = texelFetch(u_ent_y, ivec2(p.x, uy), 0).r;
                        if (u_water <= 0.08 || u_ent > -9000.0) {{
                            dist_edge = dy;
                            break;
                        }}
                    }}

                    vec3 out_rgb = base.rgb;
                    if (dist_edge > 0) {{
                        int mirror_y = p.y - dist_edge * 2;
                        if (mirror_y >= 0 && mirror_y < {VIEW_H}) {{
                            vec2 world = vec2(p) + u_cam;
                            float wave = sin(world.y * 0.55 + u_time * 3.8 + sin(world.x * 0.22 + u_time * 1.4))
                                       * (0.65 + min(float(dist_edge) * 0.055, 0.95));
                            int sx = clamp(p.x + int(round(wave)), 0, {VIEW_W - 1});
                            ivec2 sp = ivec2(sx, mirror_y);
                            float s_fov = texelFetch(u_fov, sp, 0).r;
                            vec4 s_mat = texelFetch(u_mat, sp, 0);
                            float s_ent = texelFetch(u_ent_y, sp, 0).r;
                            if (s_fov > 0.05 && (s_mat.b <= 0.08 || s_ent > -9000.0)) {{
                                vec2 s_world = vec2(sp) + u_cam;
                                ivec2 wall_sz = textureSize(u_walls, 0);
                                ivec2 st = clamp(ivec2(floor(s_world / vec2({float(TILE_W)}, {float(TILE_H)}))), ivec2(0), wall_sz - 1);
                                bool is_feature = (s_ent > -9000.0) || (s_mat.r > 0.1) || (texelFetch(u_walls, st, 0).r > 0.5);
                                float fade = is_feature
                                    ? clamp(1.0 - float(dist_edge) / 24.0, 0.0, 1.0)
                                    : clamp(1.0 - float(dist_edge) / 8.0, 0.0, 1.0);
                                float strength = fade * (is_feature ? (0.44 * water + 0.14) : (0.24 * water));
                                vec3 ref_col = texelFetch(u_scene, sp, 0).rgb * vec3(0.84, 0.94, 1.03);
                                out_rgb = mix(out_rgb, max(out_rgb * 0.65, ref_col), strength);
                            }}
                        }}
                    }}
                    fragColor = vec4(out_rgb, base.a);
                }}
            """,
        )
        for unit, name in enumerate(("u_scene", "u_mat", "u_ent_y", "u_fov", "u_walls")):
            self.reflect_prog[name].value = unit
        self._u_refl_cam = self.reflect_prog["u_cam"]
        self._u_refl_time = self.reflect_prog["u_time"]
        self.reflect_vao = ctx.simple_vertex_array(self.reflect_prog, shader.vbo, "in_vert")

        self.adapt_prog = ctx.program(
            vertex_shader=vert,
            fragment_shader=f"""#version 330 core
                uniform sampler2D u_scene;
                uniform sampler2D u_fov;
                uniform sampler2D u_prev_exp;
                uniform vec2 u_viewer;
                uniform float u_dt;
                out vec4 fragColor;

                void main() {{
                    float rad = {float(4.0 * TILE_W)};
                    float step_px = rad / 3.0;
                    float r2_max = rad * rad;
                    float sigma2 = r2_max * 0.56;
                    float log_sum = 0.0;
                    float w_sum = 0.0;
                    for (int iy = -3; iy <= 3; ++iy) {{
                        for (int ix = -3; ix <= 3; ++ix) {{
                            vec2 off = vec2(float(ix), float(iy)) * step_px;
                            float r2 = dot(off, off);
                            if (r2 > r2_max) continue;
                            ivec2 sp = ivec2(round(u_viewer + off));
                            if (sp.x < 0 || sp.y < 0 || sp.x >= {VIEW_W} || sp.y >= {VIEW_H}) continue;
                            float f = texelFetch(u_fov, sp, 0).r;
                            if (f <= 0.05) continue;
                            vec3 c = texelFetch(u_scene, sp, 0).rgb;
                            float luma = dot(c, vec3(0.299, 0.587, 0.114));
                            float peak = max(c.r, max(c.g, c.b));
                            float perceived = mix(luma, peak, 0.35);
                            float cw = exp(-r2 / sigma2);
                            float w = f * cw;
                            log_sum += log(max(perceived, 0.02)) * w;
                            w_sum += w;
                        }}
                    }}
                    float avg_lum = (w_sum > 0.01) ? exp(log_sum / w_sum) : 0.16;
                    float target_exp = clamp(pow(0.16 / max(avg_lum, 0.025), 0.47), 0.85, 1.67);
                    float prev_exp = texelFetch(u_prev_exp, ivec2(0, 0), 0).r;
                    if (prev_exp < 0.2 || prev_exp > 3.5) prev_exp = 1.0;
                    float speed = (target_exp < prev_exp) ? 3.43 : 1.45;
                    float blend = 1.0 - exp(-clamp(u_dt, 0.0, 0.1) * speed);
                    float next_exp = mix(prev_exp, target_exp, blend);
                    fragColor = vec4(next_exp, avg_lum, target_exp, 1.0);
                }}
            """,
        )
        for unit, name in enumerate(("u_scene", "u_fov", "u_prev_exp")):
            self.adapt_prog[name].value = unit
        self._u_adapt_viewer = self.adapt_prog["u_viewer"]
        self._u_adapt_dt = self.adapt_prog["u_dt"]
        self.adapt_vao = ctx.simple_vertex_array(self.adapt_prog, shader.vbo, "in_vert")

        self.extract_prog = ctx.program(
            vertex_shader=vert,
            fragment_shader=f"""#version 330 core
                uniform sampler2D u_scene;
                uniform sampler2D u_mat;
                uniform sampler2D u_fov;
                out vec4 fragColor;

                void main() {{
                    ivec2 base_p = ivec2(gl_FragCoord.xy) * 2;
                    vec3 acc = vec3(0.0);
                    for (int oy = 0; oy <= 1; ++oy) {{
                        for (int ox = 0; ox <= 1; ++ox) {{
                            ivec2 sp = clamp(base_p + ivec2(ox, oy), ivec2(0), ivec2({VIEW_W - 1}, {VIEW_H - 1}));
                            float f = texelFetch(u_fov, sp, 0).r;
                            if (f <= 0.02) continue;
                            vec3 c = texelFetch(u_scene, sp, 0).rgb;
                            float em = texelFetch(u_mat, sp, 0).r;
                            vec3 em_glow = c * em * 1.45;
                            float peak = max(c.r, max(c.g, c.b));
                            float hi = max(peak - 0.74, 0.0) * 1.35;
                            vec3 hi_glow = c * (hi / max(peak, 0.001));
                            acc += max(em_glow, hi_glow) * f;
                        }}
                    }}
                    fragColor = vec4(acc * 0.25, 1.0);
                }}
            """,
        )
        for unit, name in enumerate(("u_scene", "u_mat", "u_fov")):
            self.extract_prog[name].value = unit
        self.extract_vao = ctx.simple_vertex_array(self.extract_prog, shader.vbo, "in_vert")

        self.blur_prog = ctx.program(
            vertex_shader=vert,
            fragment_shader="""#version 330 core
                uniform sampler2D u_tex;
                uniform vec2 u_step;
                in vec2 v_uv;
                out vec4 fragColor;

                void main() {
                    vec2 d = u_step / vec2(textureSize(u_tex, 0));
                    vec3 c = texture(u_tex, v_uv).rgb * 0.227027;
                    c += (texture(u_tex, v_uv + d * 1.384615).rgb + texture(u_tex, v_uv - d * 1.384615).rgb) * 0.316216;
                    c += (texture(u_tex, v_uv + d * 3.230769).rgb + texture(u_tex, v_uv - d * 3.230769).rgb) * 0.070270;
                    fragColor = vec4(c, 1.0);
                }
            """,
        )
        self.blur_prog["u_tex"].value = 0
        self._u_blur_step = self.blur_prog["u_step"]
        self.blur_vao = ctx.simple_vertex_array(self.blur_prog, shader.vbo, "in_vert")

        self.composite_prog = ctx.program(
            vertex_shader=vert,
            fragment_shader=f"""#version 330 core
                uniform sampler2D u_src;
                uniform sampler2D u_bloom_half;
                uniform sampler2D u_bloom_quarter;
                uniform sampler2D u_fov;
                uniform sampler2D u_exp;
                uniform bool u_use_bloom;
                uniform bool u_use_adapt;
                out vec4 fragColor;

                void main() {{
                    ivec2 p = ivec2(gl_FragCoord.xy);
                    vec4 base = texelFetch(u_src, p, 0);
                    if (p.y >= {VIEW_H}) {{
                        fragColor = base;
                        return;
                    }}
                    vec3 col = base.rgb;
                    if (u_use_bloom) {{
                        float fov = texelFetch(u_fov, p, 0).r;
                        vec2 uv = (vec2(p) + 0.5) / vec2({float(VIEW_W)}, {float(VIEW_H)});
                        vec3 tight = texture(u_bloom_half, uv).rgb;
                        vec3 wide = texture(u_bloom_quarter, uv).rgb;
                        vec3 bloom = (tight * 0.50 + wide * 0.45) * fov;
                        col = col + bloom * (1.0 - col * 0.45);
                    }}
                    if (u_use_adapt) {{
                        float exp_val = texelFetch(u_exp, ivec2(0, 0), 0).r;
                        col *= exp_val;
                    }}
                    fragColor = vec4(clamp(col, 0.0, 1.0), base.a);
                }}
            """,
        )
        for unit, name in enumerate(("u_src", "u_bloom_half", "u_bloom_quarter", "u_fov", "u_exp")):
            self.composite_prog[name].value = unit
        self._u_comp_bloom = self.composite_prog["u_use_bloom"]
        self._u_comp_adapt = self.composite_prog["u_use_adapt"]
        self.composite_vao = ctx.simple_vertex_array(self.composite_prog, shader.vbo, "in_vert")

    def read_exposure(self):
        prev_idx = 1 - self._exp_idx
        try:
            raw = self.tex_exp[prev_idx].read()
            if len(raw) >= 12:
                return struct.unpack_from("3f", raw)
        except Exception:
            pass
        return None

    def render(
        self, src_tex, src_fbo, mat_tex, ent_y_tex, fov_tex, walls_tex,
        cam, time_sec, *, viewer=(VIEW_W * 0.5, VIEW_H * 0.5),
        enable_reflections=True, enable_bloom=True, enable_eye_adaptation=True,
    ):
        ctx, gl = self.ctx, self.gl
        ctx.disable(gl.BLEND)
        ctx.scissor = None

        cur_tex, cur_fbo = src_tex, src_fbo

        if enable_reflections:
            self.reflect_fbo.use()
            ctx.viewport = (0, 0, VIEW_W, CANVAS_H)
            self._u_refl_cam.value = cam
            self._u_refl_time.value = time_sec
            cur_tex.use(0)
            mat_tex.use(1)
            ent_y_tex.use(2)
            fov_tex.use(3)
            walls_tex.use(4)
            self.reflect_vao.render(gl.TRIANGLE_STRIP)
            cur_tex, cur_fbo = self.tex_refl, self.reflect_fbo

        exp_tex = self.tex_exp[self._exp_idx]
        if enable_eye_adaptation:
            dt = 0.0 if self._last_time is None else max(0.0, time_sec - self._last_time)
            self._last_time = time_sec
            next_idx = 1 - self._exp_idx
            self.exp_fbo[next_idx].use()
            ctx.viewport = (0, 0, 1, 1)
            vx, vy = viewer if viewer is not None else (VIEW_W * 0.5, VIEW_H * 0.5)
            self._u_adapt_viewer.value = (float(vx), float(vy))
            self._u_adapt_dt.value = float(dt)
            cur_tex.use(0)
            fov_tex.use(1)
            exp_tex.use(2)
            self.adapt_vao.render(gl.TRIANGLE_STRIP)
            self._exp_idx = next_idx
            exp_tex = self.tex_exp[self._exp_idx]
        else:
            self._last_time = None

        if enable_bloom:
            self.half_a_fbo.use()
            ctx.viewport = (0, 0, *self.half_size)
            cur_tex.use(0)
            mat_tex.use(1)
            fov_tex.use(2)
            self.extract_vao.render(gl.TRIANGLE_STRIP)

            self.half_b_fbo.use()
            self._u_blur_step.value = (1.0, 0.0)
            self.half_a.use(0)
            self.blur_vao.render(gl.TRIANGLE_STRIP)

            self.half_a_fbo.use()
            self._u_blur_step.value = (0.0, 1.0)
            self.half_b.use(0)
            self.blur_vao.render(gl.TRIANGLE_STRIP)

            self.quarter_b_fbo.use()
            ctx.viewport = (0, 0, *self.quarter_size)
            self._u_blur_step.value = (1.5, 0.0)
            self.half_a.use(0)
            self.blur_vao.render(gl.TRIANGLE_STRIP)

            self.quarter_a_fbo.use()
            self._u_blur_step.value = (0.0, 1.5)
            self.quarter_b.use(0)
            self.blur_vao.render(gl.TRIANGLE_STRIP)

        if enable_bloom or enable_eye_adaptation:
            self.final_fbo.use()
            ctx.viewport = (0, 0, VIEW_W, CANVAS_H)
            self._u_comp_bloom.value = bool(enable_bloom)
            self._u_comp_adapt.value = bool(enable_eye_adaptation)
            cur_tex.use(0)
            self.half_a.use(1)
            self.quarter_a.use(2)
            fov_tex.use(3)
            exp_tex.use(4)
            self.composite_vao.render(gl.TRIANGLE_STRIP)
            cur_tex, cur_fbo = self.tex_final, self.final_fbo

        return cur_tex, cur_fbo