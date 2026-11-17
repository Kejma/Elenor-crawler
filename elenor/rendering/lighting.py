from elenor.rendering.daylight import SUN_X, SUN_Y, SUN_Z, SUN_COLOR
import pygame
import numpy as np
from elenor.config import TILE_W, TILE_H, VIEW_W, VIEW_H, CANVAS_H, MAP_COLS, MAP_ROWS


class GPULightShader:
    """Аппаратный 2.5D-шейдер освещения, нормалей, AO, точечного Emissive Bloom и 3D-Объёмного Тумана."""
    MAX_LIGHTS = 48
    MAX_HUD_LIGHTS = 32
    MAX_FOGS = 16

    def __init__(self):
        import moderngl
        self.moderngl = moderngl
        self.ctx = moderngl.create_standalone_context()

        self.tex_diff = self.ctx.texture((VIEW_W, CANVAS_H), 3, dtype="f1")
        self.tex_norm = self.ctx.texture((VIEW_W, CANVAS_H), 3, dtype="f1")
        self.tex_ent_y = self.ctx.texture((VIEW_W, CANVAS_H), 1, dtype="f4")
        self.tex_sunlight = self.ctx.texture((VIEW_W, VIEW_H), 1, dtype="f4")
        self.tex_fov = self.ctx.texture((VIEW_W, CANVAS_H), 1, dtype="f4")
        self.tex_masks = self.ctx.texture((MAP_COLS, MAP_ROWS * self.MAX_LIGHTS), 1, dtype="f4")
        self.tex_walls = self.ctx.texture((MAP_COLS, MAP_ROWS), 1, dtype="f4")
        self.tex_emissive = self.ctx.texture((VIEW_W, CANVAS_H), 3, dtype="f1")
        self.tex_out = self.ctx.texture((VIEW_W, CANVAS_H), 3, dtype="f1")

        for tex in (self.tex_diff, self.tex_norm, self.tex_ent_y, self.tex_fov, self.tex_masks, self.tex_walls, self.tex_emissive, self.tex_out):
            tex.filter = (moderngl.NEAREST, moderngl.NEAREST)

        self.fbo = self.ctx.framebuffer(color_attachments=[self.tex_out])

        self.prog = self.ctx.program(
            vertex_shader="""
            #version 330 core
            in vec2 in_vert;
            void main() {
                gl_Position = vec4(in_vert, 0.0, 1.0);
            }
            """,
            fragment_shader=f"""
            #version 330 core
            uniform sampler2D u_diff;
            uniform sampler2D u_norm;
            uniform sampler2D u_ent_y;
            uniform sampler2D u_fov;
            uniform sampler2D u_light_masks;
            uniform sampler2D u_walls;
            uniform sampler2D u_emissive;

            uniform vec2 u_cam;
            uniform vec3 u_ambient_light;
            uniform sampler2D u_sunlight;
            uniform bool u_daylight;
            uniform float u_time;
            uniform vec3 u_fx_flags; // x = enable_ao, y = enable_bloom, z = enable_fog
            uniform int u_num_lights;
            uniform vec4 u_light_pos_rad[{self.MAX_LIGHTS}];
            uniform vec4 u_light_col_foot[{self.MAX_LIGHTS}];
            uniform vec2 u_light_flags[{self.MAX_LIGHTS}];

            uniform int u_num_fogs;
            uniform vec4 u_fog_pos_rad[{self.MAX_FOGS}];
            uniform vec4 u_fog_col_dens[{self.MAX_FOGS}];

            uniform int u_num_hud_lights;
            uniform vec4 u_hud_pos_rad[{self.MAX_HUD_LIGHTS}];
            uniform vec4 u_hud_col[{self.MAX_HUD_LIGHTS}];

            out vec3 fragColor;

            float sample_light_mask_smooth(int light_idx, float wx_px, float wy_px) {{
                float gx = wx_px / {float(TILE_W)} - 0.5;
                float gy = wy_px / {float(TILE_H)} - 0.5;
                int x0 = clamp(int(floor(gx)), 0, {MAP_COLS - 1});
                int y0 = clamp(int(floor(gy)), 0, {MAP_ROWS - 1});
                int x1 = clamp(x0 + 1, 0, {MAP_COLS - 1});
                int y1 = clamp(y0 + 1, 0, {MAP_ROWS - 1});
                float fx = fract(gx);
                float fy = fract(gy);
                int base_y = light_idx * {MAP_ROWS};
                float m00 = texelFetch(u_light_masks, ivec2(x0, base_y + y0), 0).r;
                float m10 = texelFetch(u_light_masks, ivec2(x1, base_y + y0), 0).r;
                float m01 = texelFetch(u_light_masks, ivec2(x0, base_y + y1), 0).r;
                float m11 = texelFetch(u_light_masks, ivec2(x1, base_y + y1), 0).r;
                return mix(mix(m00, m10, fx), mix(m01, m11, fx), fy);
            }}

            float volumetric_fog_noise(vec2 wp, float t) {{
                float n1 = sin(wp.x * 0.17 + t * 1.3 + cos(wp.y * 0.14 - t * 0.9));
                float n2 = cos(wp.y * 0.23 - t * 1.1 + sin(wp.x * 0.21 + t * 0.8));
                float n3 = sin((wp.x + wp.y) * 0.31 - t * 1.7) * 0.5;
                return clamp((n1 + n2 + n3) * 0.22 + 0.58, 0.15, 1.0);
            }}

            void main() {{
                ivec2 p = ivec2(gl_FragCoord.xy);
                vec3 diff = texelFetch(u_diff, p, 0).rgb;
                vec3 norm_raw = texelFetch(u_norm, p, 0).rgb * 255.0;
                vec3 N = (norm_raw - 128.0) / 127.0;

                if (p.y < {VIEW_H}) {{
                    float ent_y = texelFetch(u_ent_y, p, 0).r;
                    float fov = texelFetch(u_fov, p, 0).r;

                    float sub_rim = 0.0;
                    if (ent_y > -9000.0 && p.x > 0 && p.x < {VIEW_W - 1} && p.y > 0 && p.y < {VIEW_H - 1}) {{
                        bool l_out = texelFetch(u_ent_y, p + ivec2(-1, 0), 0).r <= -9000.0;
                        bool r_out = texelFetch(u_ent_y, p + ivec2( 1, 0), 0).r <= -9000.0;
                        bool u_out = texelFetch(u_ent_y, p + ivec2( 0,-1), 0).r <= -9000.0;
                        bool d_out = texelFetch(u_ent_y, p + ivec2( 0, 1), 0).r <= -9000.0;
                        if (l_out || r_out || u_out || d_out) sub_rim = 1.0;
                    }}

                    float wx_px = float(p.x) + u_cam.x;
                    float wy_px = float(p.y) + u_cam.y;
                    int tx = clamp(int(floor(wx_px / {float(TILE_W)})), 0, {MAP_COLS - 1});
                    int ty = clamp(int(floor(wy_px / {float(TILE_H)})), 0, {MAP_ROWS - 1});

                    float is_wall_tile = texelFetch(u_walls, ivec2(tx, ty), 0).r;

                    // 1. FAKE AMBIENT OCCLUSION
                    float ao_mult = 1.0;
                    if (u_fx_flags.x > 0.5 && ent_y <= -9000.0 && is_wall_tile < 0.5) {{
                        float lx_t = mod(wx_px, {float(TILE_W)});
                        float ly_t = mod(wy_px, {float(TILE_H)});
                        float occ = 0.0;
                        if (ty > 0 && texelFetch(u_walls, ivec2(tx, ty - 1), 0).r > 0.5 && ly_t < 4.5) {{
                            occ = max(occ, (4.5 - ly_t) / 4.5 * 0.42);
                        }}
                        if (ty < {MAP_ROWS - 1} && texelFetch(u_walls, ivec2(tx, ty + 1), 0).r > 0.5 && ly_t > 12.5) {{
                            occ = max(occ, (ly_t - 12.5) / 3.5 * 0.28);
                        }}
                        if (tx > 0 && texelFetch(u_walls, ivec2(tx - 1, ty), 0).r > 0.5 && lx_t < 3.5) {{
                            occ = max(occ, (3.5 - lx_t) / 3.5 * 0.32);
                        }}
                        if (tx < {MAP_COLS - 1} && texelFetch(u_walls, ivec2(tx + 1, ty), 0).r > 0.5 && lx_t > 12.5) {{
                            occ = max(occ, (lx_t - 12.5) / 3.5 * 0.32);
                        }}
                        if (p.x > 1 && p.x < {VIEW_W - 2} && p.y > 2 && p.y < {VIEW_H - 2}) {{
                            float near_ent = 0.0;
                            if (texelFetch(u_ent_y, p + ivec2(0, -1), 0).r > -9000.0) near_ent = 0.26;
                            else if (texelFetch(u_ent_y, p + ivec2(0, -2), 0).r > -9000.0) near_ent = 0.14;
                            occ = max(occ, near_ent);
                        }}
                        ao_mult = 1.0 - occ;
                    }}

                    vec3 mult = u_ambient_light;
                    if (u_daylight) {{
                        float sun = texelFetch(u_sunlight, p, 0).r;
                        float facing = max(0.0, dot(N, vec3({SUN_X}, {SUN_Y}, {SUN_Z})));
                        mult += sun * facing * vec3({SUN_COLOR[0]}, {SUN_COLOR[1]}, {SUN_COLOR[2]});
                    }}
                    vec3 rim_add = vec3(0.0);

                    for (int i = 0; i < u_num_lights; ++i) {{
                        vec4 pos_rad = u_light_pos_rad[i];
                        float rad = pos_rad.w;
                        float dx = pos_rad.x - float(p.x);
                        float dy = -(pos_rad.y - float(p.y));
                        if (abs(dx) > rad + 2.0 || abs(dy) > rad + 2.0) continue;

                        vec2 flags = u_light_flags[i];
                        float mask_w = 1.0;
                        if (flags.y > 0.5) {{
                            mask_w = sample_light_mask_smooth(i, wx_px, wy_px);
                            if (mask_w < 0.02) continue;
                        }}

                        float lz = pos_rad.z;
                        float dist = sqrt(dx * dx + dy * dy + lz * lz);
                        if (dist >= rad) continue;

                        vec4 col_foot = u_light_col_foot[i];
                        float behind_ratio = 0.0;
                        if (flags.x < 0.5 && ent_y > -9000.0) {{
                            behind_ratio = clamp((ent_y - col_foot.w) / 4.5, 0.0, 1.0);
                        }}

                        float inv_dist = 1.0 / max(dist, 0.001);
                        float raw_dot = N.x * (dx * inv_dist) + N.y * (dy * inv_dist) + N.z * (lz * inv_dist);
                        float z_wrap = max(0.0, N.z * (lz * inv_dist)) * 0.65;
                        float ndotl = max(z_wrap, raw_dot);
                        float atten = clamp(1.0 - pow(dist / rad, 1.65), 0.0, 1.0) * mask_w;

                        float front_shade = 1.0 - behind_ratio * (1.0 - sub_rim) * 0.65;
                        float intensity = ndotl * atten * 1.45 * front_shade;
                        mult += intensity * col_foot.rgb;

                        if (flags.x < 0.5 && sub_rim > 0.5 && behind_ratio > 0.01) {{
                            float dist_2d = sqrt(dx * dx + dy * dy);
                            float close_fall = pow(clamp(1.0 - dist_2d / min(rad * 0.72, 48.0), 0.0, 1.0), 2.4) * mask_w;
                            float rim_boost = sub_rim * behind_ratio * close_fall * (145.0 / 255.0);
                            rim_add += rim_boost * col_foot.rgb;
                        }}
                    }}

                    // 2. СТРОГИЙ EMISSIVE BLOOM (свечение ТОЛЬКО там, где стоит метка в u_emissive: глаза мобов и огонь!)
                    vec3 bloom_add = vec3(0.0);
                    if (u_fx_flags.y > 0.5 && fov > 0.05) {{
                        float self_em = texelFetch(u_emissive, p, 0).r;
                        if (self_em > 0.1) {{
                            mult = max(mult, vec3(1.35 * self_em));
                        }}
                        if (p.x > 2 && p.x < {VIEW_W - 3} && p.y > 2 && p.y < {VIEW_H - 3}) {{
                            vec3 glow_sum = vec3(0.0);
                            for (int oy = -2; oy <= 2; oy += 1) {{
                                for (int ox = -2; ox <= 2; ox += 1) {{
                                    float em_n = texelFetch(u_emissive, p + ivec2(ox, oy), 0).r;
                                    if (em_n > 0.1) {{
                                        vec3 nc = texelFetch(u_diff, p + ivec2(ox, oy), 0).rgb;
                                        float w_d = 1.0 / (1.0 + float(ox * ox + oy * oy));
                                        glow_sum += nc * em_n * w_d;
                                    }}
                                }}
                            }}
                            bloom_add = glow_sum * 0.085 * fov;
                        }}
                    }}

                    mult *= fov * ao_mult;
                    rim_add *= fov;
                    vec3 base_c = diff * mult + bloom_add;
                    vec3 lit_out = vec3(
                        rim_add.r > (0.5 / 255.0) ? min(228.0 / 255.0, base_c.r * 1.25 + rim_add.r) : base_c.r,
                        rim_add.g > (0.5 / 255.0) ? min(222.0 / 255.0, base_c.g * 1.25 + rim_add.g) : base_c.g,
                        rim_add.b > (0.5 / 255.0) ? min(220.0 / 255.0, base_c.b * 1.25 + rim_add.b) : base_c.b
                    );

                    // 3. 3D ОБЪЁМНЫЙ ТУМАН С РАССЕИВАНИЕМ СВЕТА ПО ГРЕБНЯМ КЛУБОВ ДЫМА
                    if (u_fx_flags.z > 0.5 && fov > 0.05 && is_wall_tile < 0.5) {{
                        vec2 wp = vec2(wx_px, wy_px);
                        float wisp = volumetric_fog_noise(wp, u_time);
                        // Вычисляем 3D-нормаль каждого клуба тумана по градиенту плотности!
                        float w_rx = volumetric_fog_noise(wp + vec2(2.5, 0.0), u_time);
                        float w_uy = volumetric_fog_noise(wp - vec2(0.0, 2.5), u_time);
                        vec3 fog_N = normalize(vec3((wisp - w_rx) * 3.2, (w_uy - wisp) * 3.2, 0.52));

                        float height_mask = 1.0;
                        if (ent_y > -9000.0) {{
                            float h_above_feet = max(0.0, ent_y - float(p.y));
                            height_mask = clamp(1.0 - (h_above_feet - 3.0) / 9.0, 0.12, 1.0);
                        }}
                        for (int f = 0; f < u_num_fogs; ++f) {{
                            vec4 f_pr = u_fog_pos_rad[f];
                            float f_rad = f_pr.z;
                            float f_dist = distance(wp, f_pr.xy);
                            if (f_dist < f_rad) {{
                                vec4 f_cd = u_fog_col_dens[f];
                                float radial = pow(1.0 - f_dist / f_rad, 1.30);
                                float fog_alpha = clamp(radial * wisp * f_cd.w * height_mask, 0.0, 0.82);

                                // Считаем объёмное рассеивание света внутри тумана (гребни клубов вспыхивают со стороны факела!)
                                vec3 vol_light = (f_pr.w > 0.5) ? vec3(0.28, 0.52, 0.28) : vec3(0.10, 0.13, 0.20);
                                for (int i = 0; i < u_num_lights; ++i) {{
                                    vec4 l_pr = u_light_pos_rad[i];
                                    float l_rad = l_pr.w * 1.15;
                                    float l_dx = l_pr.x - float(p.x);
                                    float l_dy = -(l_pr.y - float(p.y));
                                    float l_d2 = sqrt(l_dx * l_dx + l_dy * l_dy);
                                    if (l_d2 < l_rad) {{
                                        float m_w = (u_light_flags[i].y > 0.5) ? sample_light_mask_smooth(i, wx_px, wy_px) : 1.0;
                                        if (m_w > 0.02) {{
                                            vec3 L_dir = normalize(vec3(l_dx, l_dy, 14.0));
                                            // Обращённый к свету край клуба дыма ярко бликует, а тыльная сторона клуба в тени!
                                            float puff_shade = clamp(dot(fog_N, L_dir) * 0.65 + 0.45, 0.15, 1.35);
                                            float scatter = pow(1.0 - l_d2 / l_rad, 1.45) * m_w;
                                            // Ореол рассеивания (Mie halo) вблизи источника света
                                            float halo = pow(clamp(1.0 - l_d2 / (l_rad * 0.55), 0.0, 1.0), 2.0) * 0.55;
                                            vol_light += u_light_col_foot[i].rgb * scatter * (puff_shade * 1.15 + halo);
                                        }}
                                    }}
                                }}
                                vec3 fog_lit = clamp(f_cd.rgb * vol_light, 0.0, 1.45);
                                lit_out = mix(lit_out, fog_lit, fog_alpha * fov);
                            }}
                        }}
                    }}

                    fragColor = clamp(lit_out, 0.0, 1.0);
                }} else {{
                    vec3 mult = vec3(0.74, 0.74, 0.80);
                    vec3 hud_glow = vec3(0.0);
                    for (int j = 0; j < u_num_hud_lights; ++j) {{
                        vec4 h_pos = u_hud_pos_rad[j];
                        float rad = h_pos.w;
                        float dx = h_pos.x - float(p.x);
                        float dy = -(h_pos.y - float(p.y));
                        if (abs(dx) > rad + 2.0) continue;
                        float dist_2d = sqrt(dx * dx + dy * dy);
                        if (dist_2d >= rad) continue;

                        float lz = h_pos.z;
                        float dist_3d = sqrt(dx * dx + dy * dy + lz * lz);
                        float inv_dist = 1.0 / max(dist_3d, 0.001);
                        float ndotl = max(0.0, N.x * (dx * inv_dist) + N.y * (dy * inv_dist) + N.z * (lz * inv_dist));
                        float atten = clamp(1.0 - pow(dist_2d / rad, 1.6), 0.0, 1.0);
                        vec3 h_col = u_hud_col[j].rgb;
                        mult += (ndotl * atten * 0.40) * h_col;
                        hud_glow += (pow(atten, 1.8) * (12.0 / 255.0)) * h_col;
                    }}
                    fragColor = clamp(diff * mult + hud_glow, 0.0, 1.0);
                }}
            }}
            """
        )

        self.prog["u_diff"].value = 0
        self.prog["u_norm"].value = 1
        self.prog["u_ent_y"].value = 2
        self.prog["u_fov"].value = 3
        self.prog["u_light_masks"].value = 4
        self.prog["u_walls"].value = 5
        self.prog["u_emissive"].value = 6
        self.prog["u_sunlight"].value = 7

        quad = np.array([-1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0], dtype=np.float32)
        self.vbo = self.ctx.buffer(quad.tobytes())
        self.vao = self.ctx.simple_vertex_array(self.prog, self.vbo, "in_vert")

        self.pos_rad_buf = np.zeros((self.MAX_LIGHTS, 4), dtype=np.float32)
        self.col_foot_buf = np.zeros((self.MAX_LIGHTS, 4), dtype=np.float32)
        self.flags_buf = np.zeros((self.MAX_LIGHTS, 2), dtype=np.float32)
        self.masks_buf = np.zeros((self.MAX_LIGHTS, MAP_ROWS, MAP_COLS), dtype=np.float32)

        self.fog_pos_buf = np.zeros((self.MAX_FOGS, 4), dtype=np.float32)
        self.fog_col_buf = np.zeros((self.MAX_FOGS, 4), dtype=np.float32)

        self.hud_pos_buf = np.zeros((self.MAX_HUD_LIGHTS, 4), dtype=np.float32)
        self.hud_col_buf = np.zeros((self.MAX_HUD_LIGHTS, 4), dtype=np.float32)

    def render_lit_surface(self, diff_canvas, norm_canvas, entity_y_canvas, fov_mask, cam_x, cam_y, lights, hud_lights, wall_grid_np=None, emissive_canvas=None, enable_ao=True, enable_bloom=True, enable_fog=True, active_clouds=None, now_sec=0.0, ambient_light=(0.0, 0.0, 0.0), sunlight=None):
        self.tex_diff.write(pygame.image.tobytes(diff_canvas, "RGB"))
        self.tex_norm.write(pygame.image.tobytes(norm_canvas, "RGB"))
        self.tex_ent_y.write(np.ascontiguousarray(entity_y_canvas.T, dtype=np.float32).tobytes())
        self.tex_fov.write(np.ascontiguousarray(fov_mask.T, dtype=np.float32).tobytes())
        if wall_grid_np is not None:
            self.tex_walls.write(np.ascontiguousarray(wall_grid_np.T, dtype=np.float32).tobytes())
        if emissive_canvas is not None:
            self.tex_emissive.write(pygame.image.tobytes(emissive_canvas, "RGB"))

        n_lgt = min(len(lights), self.MAX_LIGHTS)
        self.pos_rad_buf.fill(0.0)
        self.col_foot_buf.fill(0.0)
        self.flags_buf.fill(0.0)

        any_masks = False
        for i in range(n_lgt):
            lgt = lights[i]
            lx, ly, lz = lgt["pos"]
            cr, cg, cb = lgt["color"]
            self.pos_rad_buf[i] = (lx, ly, lz, lgt["radius"])
            self.col_foot_buf[i] = (cr, cg, cb, lgt.get("foot_y", ly + 4.0))
            ign_d = 1.0 if lgt.get("ignore_depth", False) else 0.0
            allowed = lgt.get("allowed_tiles")
            if isinstance(allowed, np.ndarray):
                self.flags_buf[i] = (ign_d, 1.0)
                self.masks_buf[i] = allowed.T
                any_masks = True
            else:
                self.flags_buf[i] = (ign_d, 0.0)

        if any_masks:
            self.tex_masks.write(self.masks_buf.tobytes())

        clouds = active_clouds or []
        n_fog = min(len(clouds), self.MAX_FOGS)
        self.fog_pos_buf.fill(0.0)
        self.fog_col_buf.fill(0.0)
        for f_i in range(n_fog):
            cld = clouds[f_i]
            fade = 1.0
            if cld.get("timer") is not None and cld.get("max_timer"):
                fade = min(1.0, cld["timer"] / min(1.2, cld["max_timer"]))
            is_p = 1.0 if cld.get("kind") == "poison" else 0.0
            self.fog_pos_buf[f_i] = (cld["wx"] * TILE_W, cld["wy"] * TILE_H, cld["radius"] * TILE_W, is_p)
            fc = cld["color"]
            self.fog_col_buf[f_i] = (fc[0], fc[1], fc[2], cld.get("density", 0.5) * fade)

        n_hud = min(len(hud_lights), self.MAX_HUD_LIGHTS)
        self.hud_pos_buf.fill(0.0)
        self.hud_col_buf.fill(0.0)
        for j in range(n_hud):
            hl = hud_lights[j]
            hx, hy, hz = hl["pos"]
            hcr, hcg, hcb = hl["color"]
            self.hud_pos_buf[j] = (hx, hy, hz, hl["radius"])
            self.hud_col_buf[j] = (hcr, hcg, hcb, 1.0)

        self.prog["u_daylight"].value = sunlight is not None
        if sunlight is not None:
            self.tex_sunlight.write(np.ascontiguousarray(sunlight.T, dtype=np.float32).tobytes())
        self.prog["u_ambient_light"].value = tuple(ambient_light)
        self.prog["u_cam"].value = (float(cam_x), float(cam_y))
        self.prog["u_time"].value = float(now_sec)
        self.prog["u_fx_flags"].value = (1.0 if enable_ao else 0.0, 1.0 if enable_bloom else 0.0, 1.0 if enable_fog else 0.0)
        self.prog["u_num_lights"].value = n_lgt
        self.prog["u_light_pos_rad"].write(self.pos_rad_buf.tobytes())
        self.prog["u_light_col_foot"].write(self.col_foot_buf.tobytes())
        self.prog["u_light_flags"].write(self.flags_buf.tobytes())

        self.prog["u_num_fogs"].value = n_fog
        self.prog["u_fog_pos_rad"].write(self.fog_pos_buf.tobytes())
        self.prog["u_fog_col_dens"].write(self.fog_col_buf.tobytes())

        self.prog["u_num_hud_lights"].value = n_hud
        self.prog["u_hud_pos_rad"].write(self.hud_pos_buf.tobytes())
        self.prog["u_hud_col"].write(self.hud_col_buf.tobytes())

        self.fbo.use()
        self.tex_diff.use(0)
        self.tex_norm.use(1)
        self.tex_ent_y.use(2)
        self.tex_fov.use(3)
        self.tex_masks.use(4)
        self.tex_walls.use(5)
        self.tex_emissive.use(6)
        self.tex_sunlight.use(7)
        self.vao.render(self.moderngl.TRIANGLE_STRIP)

        raw_rgb = self.fbo.read(components=3, alignment=1)
        return pygame.image.frombuffer(raw_rgb, (VIEW_W, CANVAS_H), "RGB")

