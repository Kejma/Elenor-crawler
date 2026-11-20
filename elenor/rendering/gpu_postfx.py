"""GPU post-processing: planar water reflections, wide multi-pass bloom, and GPU eye adaptation."""

import math
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
        self._grade_cur = None
        self.active_grade_name = ""

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
                uniform sampler2D u_outdoor;
                uniform sampler2D u_diffuse;
                uniform vec2 u_cam;
                uniform float u_time;
                uniform float u_rain_wetness;
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
                    bool is_puddle = false;
                    if (water <= 0.08 && u_rain_wetness > 0.05 && ent_y <= -9000.0) {{
                        vec2 wp_r = vec2(p) + u_cam;
                        ivec2 w_sz = textureSize(u_walls, 0);
                        ivec2 rt = clamp(ivec2(floor(wp_r / vec2({float(TILE_W)}, {float(TILE_H)}))), ivec2(0), w_sz - 1);
                        if (texelFetch(u_walls, rt, 0).r < 0.5 && texelFetch(u_outdoor, rt, 0).r > 0.5) {{
                            float p1 = sin(wp_r.x * 0.085 + sin(wp_r.y * 0.065) * 1.4);
                            float p2 = cos(wp_r.y * 0.095 - cos(wp_r.x * 0.075) * 1.2);
                            float puddle = smoothstep(0.24, 0.68, (p1 * p2) * 0.5 + 0.5);
                            water = puddle * u_rain_wetness * 0.65;
                            is_puddle = water > 0.08;
                        }}
                    }}
                    if (water <= 0.08 || ent_y > -9000.0) {{
                        fragColor = base;
                        return;
                    }}

                    int dist_edge = 0;
                    int max_dy = is_puddle ? 16 : 24;
                    ivec2 wall_sz = textureSize(u_walls, 0);
                    for (int dy = 1; dy <= max_dy; ++dy) {{
                        int uy = p.y - dy;
                        if (uy < 0) break;
                        float u_ent = texelFetch(u_ent_y, ivec2(p.x, uy), 0).r;
                        if (is_puddle) {{
                            vec2 uw = vec2(float(p.x), float(uy)) + u_cam;
                            ivec2 ut = clamp(ivec2(floor(uw / vec2({float(TILE_W)}, {float(TILE_H)}))), ivec2(0), wall_sz - 1);
                            if (u_ent > -9000.0 || texelFetch(u_walls, ut, 0).r > 0.5) {{
                                dist_edge = dy;
                                break;
                            }}
                        }} else {{
                            float u_water = texelFetch(u_mat, ivec2(p.x, uy), 0).b;
                            if (u_water <= 0.08 || u_ent > -9000.0) {{
                                dist_edge = dy;
                                break;
                            }}
                        }}
                    }}

                    vec3 out_rgb = base.rgb;
                    if (dist_edge > 0) {{
                        int mirror_y = p.y - dist_edge * 2;
                        if (mirror_y >= 0 && mirror_y < {VIEW_H}) {{
                            bool is_blood = !is_puddle && (water < 0.45);
                            vec2 world = vec2(p) + u_cam;
                            float wave = (is_blood || is_puddle)
                                ? 0.0
                                : sin(world.y * 0.55 + u_time * 3.8 + sin(world.x * 0.22 + u_time * 1.4))
                                  * (0.65 + min(float(dist_edge) * 0.055, 0.95));
                            int sx = clamp(p.x + int(round(wave)), 0, {VIEW_W - 1});
                            ivec2 sp = ivec2(sx, mirror_y);
                            float s_fov = texelFetch(u_fov, sp, 0).r;
                            vec4 s_mat = texelFetch(u_mat, sp, 0);
                            float s_ent = texelFetch(u_ent_y, sp, 0).r;
                            if (s_fov > 0.05 && (s_mat.b <= 0.08 || s_ent > -9000.0)) {{
                                vec2 s_world = vec2(sp) + u_cam;
                                ivec2 st = clamp(ivec2(floor(s_world / vec2({float(TILE_W)}, {float(TILE_H)}))), ivec2(0), wall_sz - 1);
                                bool is_feature = (s_ent > -9000.0) || (s_mat.r > 0.1) || (texelFetch(u_walls, st, 0).r > 0.5);
                                float fade = is_feature
                                    ? clamp(1.0 - float(dist_edge) / float(max_dy), 0.0, 1.0)
                                    : clamp(1.0 - float(dist_edge) / 8.0, 0.0, 1.0);
                                float eff_w = is_blood ? 0.80 : water;
                                float strength = fade * (is_feature ? (0.44 * eff_w + 0.12) : (0.22 * eff_w));
                                vec3 ref_tint = vec3(0.84, 0.94, 1.03);
                                if (is_blood) {{
                                    vec3 albedo = texelFetch(u_diffuse, p, 0).rgb;
                                    if (albedo.b > max(albedo.r, albedo.g)) {{
                                        ref_tint = mix(vec3(0.62), vec3(0.96), albedo / albedo.b);
                                    }} else {{
                                        ref_tint = albedo.g > albedo.r ? vec3(0.62, 0.96, 0.66) : vec3(0.96, 0.62, 0.66);
                                    }}
                                }}
                                vec3 ref_col = texelFetch(u_scene, sp, 0).rgb * ref_tint;
                                out_rgb = mix(out_rgb, max(out_rgb * 0.65, ref_col), strength);
                            }}
                        }}
                    }}
                    fragColor = vec4(out_rgb, base.a);
                }}
            """,
        )
        for unit, name in enumerate(("u_scene", "u_mat", "u_ent_y", "u_fov", "u_walls", "u_outdoor", "u_diffuse")):
            self.reflect_prog[name].value = unit
        self._u_refl_cam = self.reflect_prog["u_cam"]
        self._u_refl_time = self.reflect_prog["u_time"]
        self._u_refl_wet = self.reflect_prog["u_rain_wetness"]
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
                uniform sampler2D u_mat;
                uniform bool u_use_bloom;
                uniform bool u_use_adapt;
                uniform bool u_use_grade;
                uniform vec3 u_grade_sh;
                uniform vec3 u_grade_mid;
                uniform vec3 u_grade_hi;
                uniform vec3 u_grade_params;
                uniform vec2 u_cam;
                uniform float u_time;
                uniform bool u_use_heat;
                uniform vec2 u_combat_fx;
                uniform float u_rain_amt;
                uniform sampler2D u_outdoor;
                out vec4 fragColor;

                void main() {{
                    ivec2 p = ivec2(gl_FragCoord.xy);
                    if (p.y >= {VIEW_H}) {{
                        fragColor = texelFetch(u_src, p, 0);
                        return;
                    }}

                    ivec2 sp = p;
                    if (u_use_heat) {{
                        float heat = 0.0;
                        for (int dy = 2; dy <= 14; dy += 3) {{
                            int sy = min(p.y + dy, {VIEW_H - 1});
                            float em_b = texelFetch(u_mat, ivec2(p.x, sy), 0).r;
                            if (em_b > 0.20) {{
                                vec3 cb = texelFetch(u_src, ivec2(p.x, sy), 0).rgb;
                                if (cb.r > cb.b * 1.35) {{
                                    heat = max(heat, (1.0 - float(dy) / 16.0) * em_b);
                                }}
                            }}
                        }}
                        if (heat > 0.05) {{
                            vec2 wp_h = vec2(p) + u_cam;
                            float wv = sin(wp_h.y * 0.65 + u_time * 11.0 + wp_h.x * 0.35);
                            sp.x = clamp(p.x + int(round(wv * heat * 1.15)), 0, {VIEW_W - 1});
                        }}
                    }}

                    vec4 base = texelFetch(u_src, sp, 0);
                    vec3 col = base.rgb;
                    if (u_combat_fx.x > 0.01) {{
                        int ca = max(1, int(round(u_combat_fx.x * 2.5)));
                        float r_ch = texelFetch(u_src, ivec2(clamp(sp.x + ca, 0, {VIEW_W - 1}), sp.y), 0).r;
                        float b_ch = texelFetch(u_src, ivec2(clamp(sp.x - ca, 0, {VIEW_W - 1}), sp.y), 0).b;
                        col.r = mix(col.r, r_ch, u_combat_fx.x);
                        col.b = mix(col.b, b_ch, u_combat_fx.x);
                    }}

                    if (u_use_bloom) {{
                        float fov = texelFetch(u_fov, p, 0).r;
                        vec2 uv = (vec2(sp) + 0.5) / vec2({float(VIEW_W)}, {float(VIEW_H)});
                        vec3 tight = texture(u_bloom_half, uv).rgb;
                        vec3 wide = texture(u_bloom_quarter, uv).rgb;
                        vec3 bloom = (tight * 0.50 + wide * 0.45) * fov;
                        col = col + bloom * (1.0 - col * 0.45);
                    }}
                    if (u_use_adapt) {{
                        float exp_val = texelFetch(u_exp, ivec2(0, 0), 0).r;
                        col *= exp_val;
                    }}
                    if (u_use_grade) {{
                        float luma = dot(col, vec3(0.299, 0.587, 0.114));
                        float w_sh = smoothstep(0.008, 0.06, luma) * (1.0 - smoothstep(0.16, 0.48, luma));
                        float w_hi = smoothstep(0.45, 0.88, luma);
                        float w_mid = smoothstep(0.08, 0.36, luma) * (1.0 - smoothstep(0.55, 0.88, luma));
                        vec3 tint = vec3(1.0)
                                  + (u_grade_sh - vec3(1.0)) * w_sh
                                  + (u_grade_mid - vec3(1.0)) * w_mid
                                  + (u_grade_hi - vec3(1.0)) * w_hi;
                        vec3 sh_lift = (u_grade_sh - vec3(1.0)) * (0.045 * smoothstep(0.01, 0.14, luma) * (1.0 - smoothstep(0.14, 0.42, luma)));
                        col = max(col * tint + sh_lift, vec3(0.0));
                        float c_amt = u_grade_params.x - 1.0;
                        if (abs(c_amt) > 0.001) {{
                            col = max(col + (col - 0.36) * c_amt * smoothstep(0.0, 0.16, luma), vec3(0.0));
                        }}
                        float l2 = dot(col, vec3(0.299, 0.587, 0.114));
                        col = max(mix(vec3(l2), col, u_grade_params.y), vec3(0.0));
                        if (u_grade_params.z > 0.001) {{
                            vec2 vp = ((vec2(p) + 0.5) / vec2({float(VIEW_W)}, {float(VIEW_H)})) * 2.0 - 1.0;
                            float vr2 = dot(vp * vec2(0.88, 1.0), vp * vec2(0.88, 1.0));
                            col *= 1.0 - smoothstep(0.42, 1.65, vr2) * u_grade_params.z;
                        }}
                    }}
                    if (u_rain_amt > 0.01) {{
                        float fov_r = texelFetch(u_fov, p, 0).r;
                        vec2 wp = vec2(p) + u_cam;
                        ivec2 out_sz = textureSize(u_outdoor, 0);
                        ivec2 ot = clamp(ivec2(floor(wp / vec2({float(TILE_W)}, {float(TILE_H)}))), ivec2(0), out_sz - 1);
                        if (fov_r > 0.05 && texelFetch(u_outdoor, ot, 0).r > 0.5) {{
                            float slant = wp.x + wp.y * 0.28;
                            float col_id = floor(slant / 5.0);
                            float h1 = fract(sin(col_id * 127.1) * 43758.5453);
                            float spd = 145.0 + h1 * 80.0;
                            float y_flow = wp.y - u_time * spd + h1 * 240.0;
                            float drop_cell = floor(y_flow / 38.0);
                            float h2 = fract(sin(dot(vec2(col_id, drop_cell), vec2(127.1, 311.7))) * 43758.5453);
                            float local_x = fract(slant / 5.0);
                            float local_y = fract(y_flow / 38.0);
                            float thresh = mix(0.95, 0.52, clamp(u_rain_amt, 0.0, 1.0));
                            if (h2 > thresh && local_x < 0.20 && local_y < 0.22) {{
                                float lum_bg = dot(col, vec3(0.299, 0.587, 0.114));
                                col += vec3(0.14, 0.20, 0.28) * (0.35 + lum_bg * 1.30) * fov_r * (0.45 + 0.55 * u_rain_amt);
                            }}
                        }}
                    }}
                    if (u_combat_fx.y > 0.01) {{
                        vec2 vp = ((vec2(p) + 0.5) / vec2({float(VIEW_W)}, {float(VIEW_H)})) * 2.0 - 1.0;
                        float vr = length(vp * vec2(0.85, 1.0));
                        float edge = smoothstep(0.55, 1.28, vr);
                        float pulse = 0.65 + 0.35 * sin(u_time * 5.2);
                        col = mix(col, vec3(0.45, 0.02, 0.04), clamp(edge * u_combat_fx.y * pulse * 0.72, 0.0, 0.72));
                    }}
                    col = clamp(col, 0.0, 1.0);
                    fragColor = vec4(col, base.a);
                }}
            """,
        )
        for unit, name in enumerate(("u_src", "u_bloom_half", "u_bloom_quarter", "u_fov", "u_exp", "u_mat", "u_outdoor")):
            self.composite_prog[name].value = unit
        self._u_comp_bloom = self.composite_prog["u_use_bloom"]
        self._u_comp_adapt = self.composite_prog["u_use_adapt"]
        self._u_comp_grade = self.composite_prog["u_use_grade"]
        self._u_grade_sh = self.composite_prog["u_grade_sh"]
        self._u_grade_mid = self.composite_prog["u_grade_mid"]
        self._u_grade_hi = self.composite_prog["u_grade_hi"]
        self._u_grade_params = self.composite_prog["u_grade_params"]
        self._u_comp_cam = self.composite_prog["u_cam"]
        self._u_comp_time = self.composite_prog["u_time"]
        self._u_comp_heat = self.composite_prog["u_use_heat"]
        self._u_comp_combat = self.composite_prog["u_combat_fx"]
        self._u_comp_rain = self.composite_prog["u_rain_amt"]
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
        cam, time_sec, *, diffuse_tex, viewer=(VIEW_W * 0.5, VIEW_H * 0.5),
        enable_reflections=True, enable_bloom=True, enable_eye_adaptation=True,
        enable_color_grade=True, color_grade=None,
        enable_heat_combat=True, combat_fx=(0.0, 0.0), rain_amt=0.0, outdoor_tex=None,
    ):
        ctx, gl = self.ctx, self.gl
        ctx.disable(gl.BLEND)
        ctx.scissor = None

        dt = 0.0 if self._last_time is None else max(0.0, time_sec - self._last_time)
        self._last_time = time_sec
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
            self._u_refl_wet.value = float(rain_amt)
            (outdoor_tex or walls_tex).use(5)
            diffuse_tex.use(6)
            self.reflect_vao.render(gl.TRIANGLE_STRIP)
            cur_tex, cur_fbo = self.tex_refl, self.reflect_fbo

        exp_tex = self.tex_exp[self._exp_idx]
        if enable_eye_adaptation:
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

        if enable_color_grade:
            if color_grade is not None:
                g_name, sh, mid, hi, prm = color_grade
                self.active_grade_name = g_name
                target = (*sh, *mid, *hi, *prm)
            else:
                self.active_grade_name = "Нейтральный"
                target = (1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0)
            if self._grade_cur is None:
                self._grade_cur = list(target)
            else:
                k = 1.0 - math.exp(-min(dt, 0.1) * 2.8)
                cur = self._grade_cur
                for i in range(12):
                    cur[i] += (target[i] - cur[i]) * k

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

        need_comp = (
            enable_bloom or enable_eye_adaptation or enable_color_grade
            or enable_heat_combat or rain_amt > 0.01
        )
        if need_comp:
            self.final_fbo.use()
            ctx.viewport = (0, 0, VIEW_W, CANVAS_H)
            self._u_comp_bloom.value = bool(enable_bloom)
            self._u_comp_adapt.value = bool(enable_eye_adaptation)
            self._u_comp_grade.value = bool(enable_color_grade)
            self._u_comp_cam.value = cam
            self._u_comp_time.value = float(time_sec)
            self._u_comp_heat.value = bool(enable_heat_combat)
            self._u_comp_combat.value = combat_fx if enable_heat_combat else (0.0, 0.0)
            self._u_comp_rain.value = float(rain_amt)
            if enable_color_grade and self._grade_cur is not None:
                g = self._grade_cur
                self._u_grade_sh.value = (g[0], g[1], g[2])
                self._u_grade_mid.value = (g[3], g[4], g[5])
                self._u_grade_hi.value = (g[6], g[7], g[8])
                self._u_grade_params.value = (g[9], g[10], g[11])
            cur_tex.use(0)
            self.half_a.use(1)
            self.quarter_a.use(2)
            fov_tex.use(3)
            exp_tex.use(4)
            mat_tex.use(5)
            (outdoor_tex or walls_tex).use(6)
            self.composite_vao.render(gl.TRIANGLE_STRIP)
            cur_tex, cur_fbo = self.tex_final, self.final_fbo

        return cur_tex, cur_fbo