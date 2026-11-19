"""GPU post-processing: planar water reflections and wide multi-pass bloom."""

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
                out vec4 fragColor;

                void main() {{
                    ivec2 p = ivec2(gl_FragCoord.xy);
                    vec4 base = texelFetch(u_src, p, 0);
                    if (p.y >= {VIEW_H}) {{
                        fragColor = base;
                        return;
                    }}
                    float fov = texelFetch(u_fov, p, 0).r;
                    vec2 uv = (vec2(p) + 0.5) / vec2({float(VIEW_W)}, {float(VIEW_H)});
                    vec3 tight = texture(u_bloom_half, uv).rgb;
                    vec3 wide = texture(u_bloom_quarter, uv).rgb;
                    vec3 bloom = (tight * 0.50 + wide * 0.45) * fov;
                    vec3 col = base.rgb + bloom * (1.0 - base.rgb * 0.45);
                    fragColor = vec4(clamp(col, 0.0, 1.0), base.a);
                }}
            """,
        )
        for unit, name in enumerate(("u_src", "u_bloom_half", "u_bloom_quarter", "u_fov")):
            self.composite_prog[name].value = unit
        self.composite_vao = ctx.simple_vertex_array(self.composite_prog, shader.vbo, "in_vert")

    def render(
        self, src_tex, src_fbo, mat_tex, ent_y_tex, fov_tex, walls_tex,
        cam, time_sec, *, enable_reflections=True, enable_bloom=True,
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

            self.final_fbo.use()
            ctx.viewport = (0, 0, VIEW_W, CANVAS_H)
            cur_tex.use(0)
            self.half_a.use(1)
            self.quarter_a.use(2)
            fov_tex.use(3)
            self.composite_vao.render(gl.TRIANGLE_STRIP)
            cur_tex, cur_fbo = self.tex_final, self.final_fbo

        return cur_tex, cur_fbo