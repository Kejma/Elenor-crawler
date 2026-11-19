"""Screen-space 2D Global Illumination: HDR raymarched directional bounce with wall-aware blur."""

from elenor.config import CANVAS_H, TILE_H, TILE_W, VIEW_H, VIEW_W


class GPUGlobalIllumination:
    def __init__(self, shader):
        self.ctx = shader.ctx
        self.gl = shader.moderngl
        ctx, gl = self.ctx, self.gl

        self.half_size = ((VIEW_W + 1) // 2, (VIEW_H + 1) // 2)

        self.tex_rad = ctx.texture(self.half_size, 4, dtype="f2")
        self.tex_gi_a = ctx.texture(self.half_size, 4, dtype="f2")
        self.tex_gi_b = ctx.texture(self.half_size, 4, dtype="f2")
        self.tex_dir_a = ctx.texture(self.half_size, 4, dtype="f2")
        self.tex_dir_b = ctx.texture(self.half_size, 4, dtype="f2")
        for tex in (self.tex_rad, self.tex_gi_a, self.tex_gi_b, self.tex_dir_a, self.tex_dir_b):
            tex.filter = (gl.LINEAR, gl.LINEAR)
            tex.repeat_x = False
            tex.repeat_y = False

        self.rad_fbo = ctx.framebuffer([self.tex_rad])
        self.gi_a_fbo = ctx.framebuffer([self.tex_gi_a, self.tex_dir_a])
        self.gi_b_fbo = ctx.framebuffer([self.tex_gi_b, self.tex_dir_b])

        self.tex_out = ctx.texture((VIEW_W, CANVAS_H), 4, dtype="f1")
        self.tex_out.filter = (gl.NEAREST, gl.NEAREST)
        self.out_fbo = ctx.framebuffer([self.tex_out])

        vert = """#version 330 core
            in vec2 in_vert;
            void main() { gl_Position = vec4(in_vert, 0.0, 1.0); }
        """

        self.rad_prog = ctx.program(
            vertex_shader=vert,
            fragment_shader=f"""#version 330 core
                uniform sampler2D u_scene;
                uniform sampler2D u_mat;
                uniform sampler2D u_fov;
                uniform sampler2D u_walls;
                uniform vec2 u_cam;
                out vec4 fragColor;

                void main() {{
                    ivec2 bp = ivec2(gl_FragCoord.xy) * 2;
                    ivec2 w_sz = textureSize(u_walls, 0);
                    vec3 rad_acc = vec3(0.0);
                    float wall_acc = 0.0;
                    for (int oy = 0; oy <= 1; ++oy) {{
                        for (int ox = 0; ox <= 1; ++ox) {{
                            ivec2 sp = min(bp + ivec2(ox, oy), ivec2({VIEW_W - 1}, {VIEW_H - 1}));
                            vec2 sw = vec2(sp) + 0.5 + u_cam;
                            ivec2 t = ivec2(floor(sw / vec2({float(TILE_W)}, {float(TILE_H)})));
                            bool is_w = (t.x < 0 || t.y < 0 || t.x >= w_sz.x || t.y >= w_sz.y)
                                        || (texelFetch(u_walls, t, 0).r > 0.5);
                            if (is_w) wall_acc += 0.25;
                            float f = texelFetch(u_fov, sp, 0).r;
                            if (f > 0.02) {{
                                vec3 c = texelFetch(u_scene, sp, 0).rgb;
                                float em = texelFetch(u_mat, sp, 0).r;
                                float luma = dot(c, vec3(0.299, 0.587, 0.114));
                                float peak = max(c.r, max(c.g, c.b));
                                vec3 vivid = max(mix(vec3(luma), c, 1.40), vec3(0.0));
                                float surf_e = smoothstep(0.18, 0.65, peak) * (is_w ? 1.65 : 1.15);
                                rad_acc += vivid * (surf_e + em * 3.8) * f;
                            }}
                        }}
                    }}
                    fragColor = vec4(rad_acc * 0.25, wall_acc);
                }}
            """,
        )
        for unit, name in enumerate(("u_scene", "u_mat", "u_fov", "u_walls")):
            self.rad_prog[name].value = unit
        self._u_rad_cam = self.rad_prog["u_cam"]
        self.rad_vao = ctx.simple_vertex_array(self.rad_prog, shader.vbo, "in_vert")

        self.gi_prog = ctx.program(
            vertex_shader=vert,
            fragment_shader=f"""#version 330 core
                uniform sampler2D u_rad;
                uniform sampler2D u_fov;
                uniform sampler2D u_walls;
                uniform sampler2D u_blockers;
                uniform vec2 u_cam;
                uniform bool u_has_blockers;
                layout(location = 0) out vec4 out_gi;
                layout(location = 1) out vec4 out_dir;

                bool is_wall_at(vec2 world) {{
                    ivec2 sz = textureSize(u_walls, 0);
                    ivec2 t = ivec2(floor(world / vec2({float(TILE_W)}, {float(TILE_H)})));
                    if (t.x < 0 || t.y < 0 || t.x >= sz.x || t.y >= sz.y) return true;
                    return texelFetch(u_walls, t, 0).r > 0.5;
                }}

                bool is_blocked_at(vec2 world) {{
                    if (u_has_blockers) {{
                        ivec2 sz = textureSize(u_blockers, 0);
                        ivec2 p = ivec2(floor(world));
                        if (p.x < 0 || p.y < 0 || p.x >= sz.x || p.y >= sz.y) return true;
                        return texelFetch(u_blockers, p, 0).r > 0.5;
                    }}
                    return is_wall_at(world);
                }}

                void main() {{
                    ivec2 hp = ivec2(gl_FragCoord.xy);
                    ivec2 bp = hp * 2;
                    ivec2 vmax = ivec2({VIEW_W - 1}, {VIEW_H - 1});
                    float fov = max(
                        max(texelFetch(u_fov, min(bp, vmax), 0).r,
                            texelFetch(u_fov, min(bp + ivec2(1, 0), vmax), 0).r),
                        max(texelFetch(u_fov, min(bp + ivec2(0, 1), vmax), 0).r,
                            texelFetch(u_fov, min(bp + ivec2(1, 1), vmax), 0).r)
                    );
                    vec2 origin_px = vec2(bp) + 1.0;
                    vec2 origin_world = origin_px + u_cam;
                    float wall_flag = is_wall_at(origin_world) ? 1.0 : 0.0;
                    if (fov <= 0.01) {{
                        out_gi = vec4(0.0, 0.0, 0.0, wall_flag);
                        out_dir = vec4(0.0, 0.0, 1.0, wall_flag);
                        return;
                    }}

                    bool origin_blocked = is_blocked_at(origin_world);
                    vec2 tile_local = fract(origin_world / vec2({float(TILE_W)}, {float(TILE_H)})) - 0.5;
                    bool has_local_dir = length(tile_local) > 0.06;

                    vec2 whp = floor(origin_world * 0.5);
                    float jitter = fract(52.9829189 * fract(dot(whp, vec2(0.06711056, 0.00583715))));

                    vec3 gi_sum = vec3(0.0);
                    vec3 dir_sum = vec3(0.0);
                    float luma_sum = 0.0;
                    const int N_RAYS = 32;
                    const int N_STEPS = 18;
                    vec2 inv_view = 1.0 / vec2({float(VIEW_W)}, {float(VIEW_H)});
                    for (int r = 0; r < N_RAYS; ++r) {{
                        float angle = (float(r) + jitter) * (6.2831853 / float(N_RAYS));
                        vec2 dir = vec2(cos(angle), sin(angle));

                        bool left_blk = !origin_blocked;
                        if (origin_blocked && has_local_dir && dot(dir, tile_local) < -0.10) {{
                            continue;
                        }}

                        vec3 ray_acc = vec3(0.0);
                        float d = 2.0;
                        vec2 prev_uv = origin_px * inv_view;
                        for (int s = 0; s < N_STEPS; ++s) {{
                            float step_len = mix(2.6, 8.2, float(s) / float(N_STEPS - 1));
                            d += step_len;
                            vec2 sp = origin_px + dir * d;
                            if (sp.x < 0.0 || sp.y < 0.0 || sp.x >= {float(VIEW_W)} || sp.y >= {float(VIEW_H)}) break;
                            vec2 suv = sp * inv_view;
                            bool blk = is_blocked_at(sp + u_cam);
                            float atten = 1.0 / (1.0 + (d * d) / 680.0);
                            float near_skip = smoothstep(2.0, 7.0, d);

                            if (blk) {{
                                if (!left_blk) {{
                                    if (d > 11.5) break;
                                    prev_uv = suv;
                                    continue;
                                }}
                                vec3 hit_rad = max(texture(u_rad, suv).rgb, texture(u_rad, prev_uv).rgb * 0.85);
                                ray_acc += hit_rad * atten * (0.45 + 0.55 * near_skip) * 1.10;
                                break;
                            }} else {{
                                left_blk = true;
                                ray_acc += texture(u_rad, suv).rgb * atten * near_skip * (step_len * 0.055);
                            }}
                            prev_uv = suv;
                        }}
                        float rl = dot(ray_acc, vec3(0.299, 0.587, 0.114));
                        gi_sum += ray_acc;
                        dir_sum += vec3(dir.x, -dir.y, 0.42) * rl;
                        luma_sum += rl;
                    }}
                    vec3 gi_avg = gi_sum / float(N_RAYS);
                    vec3 dir_avg = (luma_sum > 0.0005) ? (dir_sum / luma_sum) : vec3(0.0, 0.0, 1.0);
                    out_gi = vec4(gi_avg, wall_flag);
                    out_dir = vec4(dir_avg, wall_flag);
                }}
            """,
        )
        for unit, name in enumerate(("u_rad", "u_fov", "u_walls", "u_blockers")):
            self.gi_prog[name].value = unit
        self._u_gi_cam = self.gi_prog["u_cam"]
        self._u_gi_has_blockers = self.gi_prog["u_has_blockers"]
        self.gi_vao = ctx.simple_vertex_array(self.gi_prog, shader.vbo, "in_vert")

        self.blur_prog = ctx.program(
            vertex_shader=vert,
            fragment_shader="""#version 330 core
                uniform sampler2D u_gi;
                uniform sampler2D u_dir;
                uniform ivec2 u_step;
                layout(location = 0) out vec4 out_gi;
                layout(location = 1) out vec4 out_dir;

                void main() {
                    ivec2 p = ivec2(gl_FragCoord.xy);
                    ivec2 sz = textureSize(u_gi, 0) - 1;
                    vec4 cg = texelFetch(u_gi, p, 0);
                    vec4 cd = texelFetch(u_dir, p, 0);
                    const float weights[4] = float[](0.26, 0.21, 0.12, 0.04);
                    vec3 ag = cg.rgb * weights[0];
                    vec3 ad = cd.rgb * weights[0];
                    float wsum = weights[0];
                    for (int k = 1; k <= 3; ++k) {
                        ivec2 p1 = clamp(p + u_step * k, ivec2(0), sz);
                        ivec2 p2 = clamp(p - u_step * k, ivec2(0), sz);
                        vec4 g1 = texelFetch(u_gi, p1, 0);
                        vec4 g2 = texelFetch(u_gi, p2, 0);
                        vec4 d1 = texelFetch(u_dir, p1, 0);
                        vec4 d2 = texelFetch(u_dir, p2, 0);
                        float w1 = weights[k] * (abs(g1.a - cg.a) < 0.5 ? 1.0 : 0.02);
                        float w2 = weights[k] * (abs(g2.a - cg.a) < 0.5 ? 1.0 : 0.02);
                        ag += g1.rgb * w1 + g2.rgb * w2;
                        ad += d1.rgb * w1 + d2.rgb * w2;
                        wsum += w1 + w2;
                    }
                    float inv_w = 1.0 / max(wsum, 0.001);
                    out_gi = vec4(ag * inv_w, cg.a);
                    out_dir = vec4(ad * inv_w, cg.a);
                }
            """,
        )
        self.blur_prog["u_gi"].value = 0
        self.blur_prog["u_dir"].value = 1
        self._u_blur_step = self.blur_prog["u_step"]
        self.blur_vao = ctx.simple_vertex_array(self.blur_prog, shader.vbo, "in_vert")

        self.comp_prog = ctx.program(
            vertex_shader=vert,
            fragment_shader=f"""#version 330 core
                uniform sampler2D u_scene;
                uniform sampler2D u_diff;
                uniform sampler2D u_norm;
                uniform sampler2D u_gi;
                uniform sampler2D u_dir;
                uniform sampler2D u_fov;
                uniform sampler2D u_walls;
                uniform vec2 u_cam;
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

                    ivec2 w_sz = textureSize(u_walls, 0);
                    vec2 sw = vec2(p) + 0.5 + u_cam;
                    ivec2 t = ivec2(floor(sw / vec2({float(TILE_W)}, {float(TILE_H)})));
                    float wall_self = ((t.x < 0 || t.y < 0 || t.x >= w_sz.x || t.y >= w_sz.y)
                                       || (texelFetch(u_walls, t, 0).r > 0.5)) ? 1.0 : 0.0;

                    vec2 hpos = (vec2(p) + 0.5) * 0.5 - 0.5;
                    ivec2 h0 = ivec2(floor(hpos));
                    vec2 f = clamp(hpos - vec2(h0), 0.0, 1.0);
                    ivec2 hmax = ivec2({self.half_size[0] - 1}, {self.half_size[1] - 1});

                    ivec2 c00 = clamp(h0, ivec2(0), hmax);
                    ivec2 c10 = clamp(h0 + ivec2(1, 0), ivec2(0), hmax);
                    ivec2 c01 = clamp(h0 + ivec2(0, 1), ivec2(0), hmax);
                    ivec2 c11 = clamp(h0 + ivec2(1, 1), ivec2(0), hmax);

                    vec4 g00 = texelFetch(u_gi, c00, 0);
                    vec4 g10 = texelFetch(u_gi, c10, 0);
                    vec4 g01 = texelFetch(u_gi, c01, 0);
                    vec4 g11 = texelFetch(u_gi, c11, 0);

                    float w00 = (1.0 - f.x) * (1.0 - f.y) * (abs(g00.a - wall_self) < 0.5 ? 1.0 : 0.02);
                    float w10 = f.x * (1.0 - f.y) * (abs(g10.a - wall_self) < 0.5 ? 1.0 : 0.02);
                    float w01 = (1.0 - f.x) * f.y * (abs(g01.a - wall_self) < 0.5 ? 1.0 : 0.02);
                    float w11 = f.x * f.y * (abs(g11.a - wall_self) < 0.5 ? 1.0 : 0.02);
                    float wsum = w00 + w10 + w01 + w11;

                    vec3 gi_rgb;
                    vec3 gi_dir;
                    if (wsum > 0.001) {{
                        float inv_w = 1.0 / wsum;
                        gi_rgb = (g00.rgb * w00 + g10.rgb * w10 + g01.rgb * w01 + g11.rgb * w11) * inv_w;
                        gi_dir = (texelFetch(u_dir, c00, 0).rgb * w00
                                + texelFetch(u_dir, c10, 0).rgb * w10
                                + texelFetch(u_dir, c01, 0).rgb * w01
                                + texelFetch(u_dir, c11, 0).rgb * w11) * inv_w;
                    }} else {{
                        gi_rgb = mix(mix(g00.rgb, g10.rgb, f.x), mix(g01.rgb, g11.rgb, f.x), f.y);
                        gi_dir = vec3(0.0, 0.0, 1.0);
                    }}

                    vec3 n_raw = texelFetch(u_norm, p, 0).rgb * 255.0;
                    vec3 N = normalize((n_raw - 128.0) / 127.0 + vec3(0.0, 0.0, 0.001));
                    vec3 L_gi = normalize(gi_dir + vec3(0.0, 0.0, 0.18));
                    float ndotl_gi = clamp(dot(N, L_gi) * 0.85 + 0.22, 0.15, 1.25);

                    gi_rgb = gi_rgb / (1.0 + gi_rgb * 1.10);

                    float side_face = smoothstep(0.08, 0.45, length(N.xy));
                    float surface_gain = mix(0.62, 1.35, max(wall_self, side_face));

                    vec3 diff = texelFetch(u_diff, p, 0).rgb;
                    float direct_luma = dot(base.rgb, vec3(0.299, 0.587, 0.114));
                    float direct_peak = max(base.r, max(base.g, base.b));
                    float direct_bright = max(direct_luma, direct_peak * 0.85);
                    float shadow_boost = mix(1.15, 0.10, smoothstep(0.12, 0.62, direct_bright));
                    vec3 bounce_albedo = max(diff, vec3(0.05));
                    vec3 gi_light = gi_rgb * bounce_albedo * ndotl_gi * surface_gain * shadow_boost * fov * 1.25;
                    vec3 out_rgb = base.rgb + gi_light * (1.0 - base.rgb * 0.75);
                    fragColor = vec4(clamp(out_rgb, 0.0, 1.0), base.a);
                }}
            """,
        )
        for unit, name in enumerate(("u_scene", "u_diff", "u_norm", "u_gi", "u_dir", "u_fov", "u_walls")):
            self.comp_prog[name].value = unit
        self._u_comp_cam = self.comp_prog["u_cam"]
        self.comp_vao = ctx.simple_vertex_array(self.comp_prog, shader.vbo, "in_vert")

    def render(self, src_tex, diff_tex, norm_tex, mat_tex, fov_tex, walls_tex, blockers_tex, cam):
        ctx, gl = self.ctx, self.gl
        ctx.disable(gl.BLEND)
        ctx.scissor = None

        ctx.viewport = (0, 0, *self.half_size)
        self.rad_fbo.use()
        self._u_rad_cam.value = cam
        src_tex.use(0)
        mat_tex.use(1)
        fov_tex.use(2)
        walls_tex.use(3)
        self.rad_vao.render(gl.TRIANGLE_STRIP)

        self.gi_a_fbo.use()
        self._u_gi_cam.value = cam
        has_blk = blockers_tex is not None
        self._u_gi_has_blockers.value = has_blk
        self.tex_rad.use(0)
        fov_tex.use(1)
        walls_tex.use(2)
        (blockers_tex if has_blk else walls_tex).use(3)
        self.gi_vao.render(gl.TRIANGLE_STRIP)

        self.gi_b_fbo.use()
        self._u_blur_step.value = (1, 0)
        self.tex_gi_a.use(0)
        self.tex_dir_a.use(1)
        self.blur_vao.render(gl.TRIANGLE_STRIP)

        self.gi_a_fbo.use()
        self._u_blur_step.value = (0, 1)
        self.tex_gi_b.use(0)
        self.tex_dir_b.use(1)
        self.blur_vao.render(gl.TRIANGLE_STRIP)

        ctx.viewport = (0, 0, VIEW_W, CANVAS_H)
        self.out_fbo.use()
        self._u_comp_cam.value = cam
        src_tex.use(0)
        diff_tex.use(1)
        norm_tex.use(2)
        self.tex_gi_a.use(3)
        self.tex_dir_a.use(4)
        fov_tex.use(5)
        walls_tex.use(6)
        self.comp_vao.render(gl.TRIANGLE_STRIP)

        return self.tex_out, self.out_fbo