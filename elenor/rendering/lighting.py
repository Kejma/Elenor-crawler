from time import perf_counter

import pygame
import numpy as np
from elenor.config import TILE_W, TILE_H, VIEW_W, VIEW_H, CANVAS_H, MAP_COLS, MAP_ROWS
from elenor.rendering.gpu_fog import GPUFog
from elenor.rendering.occlusion import PROP_SAMPLE_STEPS, PROP_SHADOW_STRENGTH, SHADOW_RAYS


# Peak-channel compression preserves RGB ratios in warm or saturated lights.
WORLD_HIGHLIGHTS = (195.0, 60.0)
TEMPLE_HIGHLIGHTS = (164.0, 77.0)


def tone_map_world(rgb, is_entity, temple_exposure, *, temple_only=False):
    """Compress world highlights in place, in the renderer's 0–255 range."""
    knee, headroom = WORLD_HIGHLIGHTS
    if temple_exposure:
        knee = np.where(is_entity, knee, TEMPLE_HIGHLIGHTS[0])
        headroom = np.where(is_entity, headroom, TEMPLE_HIGHLIGHTS[1])
    peak = np.maximum(np.maximum(rgb[..., 0], rgb[..., 1]), rgb[..., 2])
    excess = np.maximum(peak - knee, 0.0)
    # 1 - (peak - mapped_peak) / peak, with zero change below the knee.
    scale = 1.0 - excess / (headroom + excess) * (excess / np.maximum(peak, 1.0))
    if temple_only:
        scale[is_entity] = 1.0
    rgb *= scale[..., None]


def bounce_color_for(dungeon):
    """RGB reflectance for one approximate diffuse bounce from the surroundings."""
    if dungeon.interior == "temple":
        return .12, .135, .15
    if dungeon.campaign == "rats" and dungeon.floor_num == 1:
        return .16, .115, .075
    if dungeon.campaign == "jungle" and not dungeon.interior:
        return .095, .13, .095
    return .11, .115, .125


class GPULightShader:
    """Аппаратный 2.5D-шейдер освещения, нормалей, AO и точечного Emissive Bloom."""
    MAX_LIGHTS = 48
    MAX_HUD_LIGHTS = 32

    def __init__(self, context=None):
        import moderngl
        self.moderngl = moderngl
        self.ctx = context if context is not None else moderngl.create_standalone_context()
        self.timers = None
        self.uploaded_structure = None
        self.uploaded_fov = None

        self.tex_diff = self.ctx.texture((VIEW_W, CANVAS_H), 4, dtype="f1")
        self.tex_norm = self.ctx.texture((VIEW_W, CANVAS_H), 4, dtype="f1")
        self.tex_ent_y = self.ctx.texture((VIEW_W, CANVAS_H), 1, dtype="f4")
        self.tex_fov = self.ctx.texture((VIEW_W, CANVAS_H), 1, dtype="f4")
        self.tex_masks = self.ctx.texture((MAP_COLS, MAP_ROWS * self.MAX_LIGHTS), 1, dtype="f4")
        self.tex_walls = self.ctx.texture((MAP_COLS, MAP_ROWS), 1, dtype="f4")
        self.tex_emissive = self.ctx.texture((VIEW_W, CANVAS_H), 4, dtype="f1")
        self.tex_out = self.ctx.texture((VIEW_W, CANVAS_H), 4, dtype="f1")

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
            uniform vec2 u_viewer;
            uniform sampler2D u_shadows;
            uniform sampler2D u_props;
            uniform bool u_has_props;
            uniform bool u_temple_exposure;
            uniform bool u_tonemap;
            uniform bool u_reflected_light;
            uniform vec3 u_bounce_color;
            uniform vec2 u_fx_flags; // x = enable_ao, y = enable_bloom
            uniform bool u_enable_specular;
            uniform float u_time;
            uniform int u_num_lights;
            uniform vec4 u_light_pos_rad[{self.MAX_LIGHTS}];
            uniform vec4 u_light_col_foot[{self.MAX_LIGHTS}];
            uniform vec4 u_light_flags[{self.MAX_LIGHTS}];

            uniform int u_num_hud_lights;
            uniform vec4 u_hud_pos_rad[{self.MAX_HUD_LIGHTS}];
            uniform vec4 u_hud_col[{self.MAX_HUD_LIGHTS}];

            out vec4 fragColor;

            float sample_light_mask_smooth(int light_idx, float wx_px, float wy_px) {{
                float gx = wx_px / {float(TILE_W)} - 0.5;
                float gy = wy_px / {float(TILE_H)} - 0.5;
                int x0 = clamp(int(floor(gx)), 0, textureSize(u_walls, 0).x - 1);
                int y0 = clamp(int(floor(gy)), 0, textureSize(u_walls, 0).y - 1);
                int x1 = clamp(x0 + 1, 0, textureSize(u_walls, 0).x - 1);
                int y1 = clamp(y0 + 1, 0, textureSize(u_walls, 0).y - 1);
                float fx = fract(gx);
                float fy = fract(gy);
                int base_y = light_idx * textureSize(u_walls, 0).y;
                float m00 = texelFetch(u_light_masks, ivec2(x0, base_y + y0), 0).r;
                float m10 = texelFetch(u_light_masks, ivec2(x1, base_y + y0), 0).r;
                float m01 = texelFetch(u_light_masks, ivec2(x0, base_y + y1), 0).r;
                float m11 = texelFetch(u_light_masks, ivec2(x1, base_y + y1), 0).r;
                return mix(mix(m00, m10, fx), mix(m01, m11, fx), fy);
            }}

            float shadow_coverage(int index, float ray, float distance) {{
                float whole = floor(ray);
                int bin = int(mod(whole, {float(SHADOW_RAYS)}));
                float first = texelFetch(u_shadows, ivec2(bin, index), 0).r;
                float next = texelFetch(u_shadows, ivec2((bin + 1) % {SHADOW_RAYS}, index), 0).r;
                return mix(smoothstep(-1.8, 1.8, first - distance),
                           smoothstep(-1.8, 1.8, next - distance), fract(ray));
            }}

            bool open_wall_face(vec2 point) {{
                ivec2 cell = ivec2(floor(point / vec2({float(TILE_W)}, {float(TILE_H)})));
                cell = clamp(cell, ivec2(0), textureSize(u_walls, 0) - 1);
                return texelFetch(u_walls, cell, 0).r == 0.0;
            }}

            float wall_face_distance(vec2 pixel, vec2 world, vec2 to_light, float distance) {{
                vec2 tile_size = vec2({float(TILE_W)}, {float(TILE_H)});
                vec2 local = mod(world, tile_size);
                vec2 viewer_world = u_viewer + world - pixel;
                vec2 view = viewer_world - (world - local + tile_size * .5);
                bvec2 positive = greaterThan(view, vec2(0.0));
                vec2 side = mix(vec2(-1.0), vec2(1.0), positive);
                vec2 edge = world - local + mix(vec2(0.0), tile_size, positive);
                vec2 exits = abs(edge - world) * distance / max(abs(to_light), vec2(.001));
                vec2 direction = to_light / distance;
                vec2 near = edge + side * .75;
                bool face_x = (viewer_world.x - edge.x) * side.x >= 0.0 && open_wall_face(vec2(near.x, world.y));
                bool face_y = (viewer_world.y - edge.y) * side.y >= 0.0 && open_wall_face(vec2(world.x, near.y));
                if (face_x && (!face_y || abs(view.x) > abs(view.y))) {{
                    if (to_light.x * side.x <= 0.0 || exits.x > distance
                        || !open_wall_face(vec2(near.x, world.y + direction.y * (exits.x + .75)))) return -1.0;
                    return exits.x + 2.4 * distance / max(abs(to_light.x), .001);
                }}
                if (face_y && to_light.y * side.y > 0.0 && exits.y <= distance
                    && open_wall_face(vec2(world.x + direction.x * (exits.y + .75), near.y)))
                    return exits.y + 2.4 * distance / max(abs(to_light.y), .001);
                return -1.0;
            }}

            float prop_visibility(vec2 world, vec2 to_light, float distance, float light_height) {{
                const float steps[{len(PROP_SAMPLE_STEPS)}] =
                    float[]({", ".join(str(step) for step in PROP_SAMPLE_STEPS)});
                vec2 direction = to_light / distance;
                ivec2 size = textureSize(u_props, 0);
                float shade = 0.0;
                for (int i = 0; i < {len(PROP_SAMPLE_STEPS)}; ++i) {{
                    float step_px = steps[i];
                    if (distance <= step_px + 4.0) break;
                    ivec2 sample_px = ivec2(floor(world + direction * step_px));
                    if (any(lessThan(sample_px, ivec2(0))) || any(greaterThanEqual(sample_px, size))) continue;
                    float height = texelFetch(u_props, sample_px, 0).r * 25.5;
                    float depth = clamp((height - light_height * step_px / distance) * .34, 0.0, 1.0);
                    float reach = clamp((distance - step_px - 4.0) / 6.0, 0.0, 1.0);
                    shade = max(shade, depth * min(.55, height * .045) * (1.0 - step_px / 22.0) * reach);
                }}
                return 1.0 - shade * {PROP_SHADOW_STRENGTH};
            }}

            float surface_shadow(int index, vec2 pixel, vec2 world, vec2 to_light, bool wall, bool ground, float light_height) {{
                float distance = length(to_light);
                if (distance < 0.5) return 1.0;
                float angle = atan(-to_light.y, -to_light.x) * {SHADOW_RAYS / (2 * np.pi)};
                float receiver = distance - 1.0;
                if (wall) {{
                    float face = wall_face_distance(pixel, world, to_light, distance);
                    if (face < 0.0) return 0.0;
                    receiver -= face;
                }}
                float spread = (.60 + min(distance * .013, 1.50)) * {SHADOW_RAYS / (2 * np.pi)} / max(distance, 7.0);
                float visibility = .58 * shadow_coverage(index, angle, receiver)
                    + .21 * (shadow_coverage(index, angle - spread, receiver)
                           + shadow_coverage(index, angle + spread, receiver));
                if (u_has_props && ground && !wall && visibility > .008)
                    visibility *= prop_visibility(world, to_light, distance, light_height);
                return visibility;
            }}

            void main() {{
                ivec2 p = ivec2(gl_FragCoord.xy);
                vec3 diff = texelFetch(u_diff, p, 0).rgb;
                vec3 norm_raw = texelFetch(u_norm, p, 0).rgb * 255.0;
                vec3 N = (norm_raw - 128.0) / 127.0;

                if (p.y < {VIEW_H}) {{
                    float ent_y = texelFetch(u_ent_y, p, 0).r;
                    float fov = texelFetch(u_fov, p, 0).r;
                    if (fov <= .001) {{
                        fragColor = vec4(0.0);
                        return;
                    }}

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
                    int tx = clamp(int(floor(wx_px / {float(TILE_W)})), 0, textureSize(u_walls, 0).x - 1);
                    int ty = clamp(int(floor(wy_px / {float(TILE_H)})), 0, textureSize(u_walls, 0).y - 1);

                    float is_wall_tile = texelFetch(u_walls, ivec2(tx, ty), 0).r;

                    vec3 mat_px = texelFetch(u_emissive, p, 0).rgb;
                    float self_em = mat_px.r;
                    float gloss = mat_px.g;
                    float water_mask = mat_px.b;
                    if (u_enable_specular && water_mask > 0.1 && ent_y <= -9000.0) {{
                        float wx_w = wx_px * 0.18;
                        float wy_w = wy_px * 0.28;
                        float rip1 = sin(wx_w + u_time * 2.6 + cos(wy_w * 0.8 - u_time * 1.7));
                        float rip2 = cos(wy_w * 1.3 - u_time * 3.1 + sin(wx_w * 0.7 + u_time * 1.2));
                        N = normalize(N + vec3(rip1 * 0.22, rip2 * 0.24, 0.0) * water_mask);
                    }}

                    // 1. FAKE AMBIENT OCCLUSION
                    float ao_mult = 1.0;
                    if (u_fx_flags.x > 0.5 && ent_y <= -9000.0 && is_wall_tile < 0.5) {{
                        float lx_t = mod(wx_px, {float(TILE_W)});
                        float ly_t = mod(wy_px, {float(TILE_H)});
                        float occ = 0.0;
                        if (ty > 0 && texelFetch(u_walls, ivec2(tx, ty - 1), 0).r > 0.5 && ly_t < 4.5) {{
                            occ = max(occ, (4.5 - ly_t) / 4.5 * 0.42);
                        }}
                        if (ty < textureSize(u_walls, 0).y - 1 && texelFetch(u_walls, ivec2(tx, ty + 1), 0).r > 0.5 && ly_t > 12.5) {{
                            occ = max(occ, (ly_t - 12.5) / 3.5 * 0.28);
                        }}
                        if (tx > 0 && texelFetch(u_walls, ivec2(tx - 1, ty), 0).r > 0.5 && lx_t < 3.5) {{
                            occ = max(occ, (3.5 - lx_t) / 3.5 * 0.32);
                        }}
                        if (tx < textureSize(u_walls, 0).x - 1 && texelFetch(u_walls, ivec2(tx + 1, ty), 0).r > 0.5 && lx_t > 12.5) {{
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

                    vec3 mult = vec3(0.0);
                    vec3 rim_add = vec3(0.0);
                    float ov_lum = 0.0;
                    vec3 spec_add = vec3(0.0);

                    for (int i = 0; i < u_num_lights; ++i) {{
                        vec4 pos_rad = u_light_pos_rad[i];
                        float rad = pos_rad.w;
                        float dx = pos_rad.x - float(p.x);
                        float dy = -(pos_rad.y - float(p.y));
                        if (abs(dx) > rad + 2.0 || abs(dy) > rad + 2.0) continue;

                        vec4 flags = u_light_flags[i];
                        float mask_w = 1.0;
                        if (flags.y > 0.5) {{
                            mask_w = sample_light_mask_smooth(i, wx_px, wy_px);
                            if (mask_w < 0.02) continue;
                        }}

                        float lz = pos_rad.z;
                        float dist = sqrt(dx * dx + dy * dy + lz * lz);
                        if (dist >= rad) continue;
                        vec4 col_foot = u_light_col_foot[i];
                        float base_atten = clamp(1.0 - pow(dist / rad, 1.65), 0.0, 1.0);
                        ov_lum += base_atten * mask_w * max(col_foot.r, max(col_foot.g, col_foot.b));
                        if (flags.z > .5) {{
                            mask_w *= surface_shadow(i, vec2(p), vec2(wx_px, wy_px), vec2(dx, -dy), is_wall_tile > 0.0, ent_y <= -9000.0, lz);
                            if (mask_w < .008) continue;
                        }}

                        float behind_ratio = 0.0;
                        if (flags.x < 0.5 && ent_y > -9000.0) {{
                            behind_ratio = clamp((ent_y - col_foot.w) / 4.5, 0.0, 1.0);
                        }}

                        float inv_dist = 1.0 / max(dist, 0.001);
                        float raw_dot = N.x * (dx * inv_dist) + N.y * (dy * inv_dist) + N.z * (lz * inv_dist);
                        float z_wrap = max(0.0, N.z * (lz * inv_dist)) * 0.65;
                        float ndotl = max(z_wrap, raw_dot);
                        float atten = base_atten * mask_w;

                        float front_shade = 1.0 - behind_ratio * (1.0 - sub_rim) * 0.65;
                        float intensity = ndotl * atten * 1.45 * front_shade;
                        // Approximate diffuse fill with the same occlusion and range as its source.
                        mult += intensity * col_foot.rgb;
                        if (u_reflected_light && flags.w > 0.5)
                            mult += u_bounce_color * (atten * max(1.0 - ndotl, 0.0)) * col_foot.rgb;
                        if (u_enable_specular && gloss > 0.04 && flags.w > 0.5) {{
                         vec3 H = normalize(vec3(dx, dy, lz) * inv_dist + vec3(0.0, -0.32, 0.947));
                         float ndoth = max(0.0, dot(N, H));
                         float shininess = mix(12.0, 68.0, gloss);
                         float spec = pow(ndoth, shininess) * gloss * atten * front_shade * (0.45 + 0.65 * gloss);
                         spec_add += spec * col_foot.rgb;
                     }}

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
                        if (self_em > 0.1) {{
                            mult = max(mult, vec3(1.35 * self_em));
                        }}
                        if (u_fx_flags.y > 1.5 && p.x > 2 && p.x < {VIEW_W - 3} && p.y > 2 && p.y < {VIEW_H - 3}) {{
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
                    spec_add *= fov * ao_mult;
                    rim_add *= fov;
                    vec3 base_c = diff * mult + spec_add + bloom_add;
                    vec3 lit_out = vec3(
                        rim_add.r > (0.5 / 255.0) ? min(228.0 / 255.0, base_c.r * 1.25 + rim_add.r) : base_c.r,
                        rim_add.g > (0.5 / 255.0) ? min(222.0 / 255.0, base_c.g * 1.25 + rim_add.g) : base_c.g,
                        rim_add.b > (0.5 / 255.0) ? min(220.0 / 255.0, base_c.b * 1.25 + rim_add.b) : base_c.b
                    );

                    bool temple_ground = u_temple_exposure && ent_y <= -9000.0;
                    float knee = (temple_ground ? {TEMPLE_HIGHLIGHTS[0]} : {WORLD_HIGHLIGHTS[0]}) / 255.0;
                    float headroom = (temple_ground ? {TEMPLE_HIGHLIGHTS[1]} : {WORLD_HIGHLIGHTS[1]}) / 255.0;
                    float peak = max(lit_out.r, max(lit_out.g, lit_out.b));
                    float excess = max(peak - knee, 0.0);
                    if (u_tonemap || temple_ground) lit_out *= 1.0 - excess / (headroom + excess) * (excess / max(peak, 1.0 / 255.0));
                    fragColor = vec4(clamp(lit_out, 0.0, 1.0), clamp(ov_lum, 0.0, 1.0));
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
                    fragColor = vec4(clamp(diff * mult + hud_glow, 0.0, 1.0), 1.0);
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
        self.prog["u_shadows"].value = 7
        self.prog["u_props"].value = 8
        self._u_cam = self.prog["u_cam"]
        self._u_viewer = self.prog["u_viewer"]
        self._u_has_props = self.prog["u_has_props"]
        self._u_temple_exposure = self.prog["u_temple_exposure"]
        self._u_bounce_color = self.prog["u_bounce_color"]
        self._u_reflected_light = self.prog["u_reflected_light"]
        self._u_tonemap = self.prog["u_tonemap"]
        self._u_fx_flags = self.prog["u_fx_flags"]
        self._u_num_lights = self.prog["u_num_lights"]
        self._u_light_pos_rad = self.prog["u_light_pos_rad"]
        self._u_light_col_foot = self.prog["u_light_col_foot"]
        self._u_light_flags = self.prog["u_light_flags"]
        self._u_num_hud_lights = self.prog["u_num_hud_lights"]
        self._u_hud_pos_rad = self.prog["u_hud_pos_rad"]
        self._u_hud_col = self.prog["u_hud_col"]
        self._u_enable_specular = self.prog["u_enable_specular"]
        self._u_time = self.prog["u_time"]

        quad = np.array([-1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0], dtype=np.float32)
        self.vbo = self.ctx.buffer(quad.tobytes())
        self.vao = self.ctx.simple_vertex_array(self.prog, self.vbo, "in_vert")

        self.tex_shadows = self.ctx.texture((SHADOW_RAYS, self.MAX_LIGHTS), 1, dtype="f4")
        self.shadow_fbo = self.ctx.framebuffer(color_attachments=[self.tex_shadows])
        self.shadow_program = self.ctx.program(
            vertex_shader="""
                #version 330 core
                in vec2 in_vert;
                void main() { gl_Position = vec4(in_vert, 0.0, 1.0); }
            """,
            fragment_shader=f"""
                #version 330 core
                uniform sampler2D u_blockers;
                uniform vec3 u_source;
                out float stop;

                bool blocked(ivec2 point) {{
                    return texelFetch(u_blockers, point, 0).r > .5;
                }}
                bool inside(ivec2 point, ivec2 size) {{
                    return all(greaterThanEqual(point, ivec2(0))) && all(lessThan(point, size));
                }}
                void main() {{
                    float angle = floor(gl_FragCoord.x) * {2 * np.pi / SHADOW_RAYS};
                    vec2 heading = vec2(cos(angle), sin(angle));
                    ivec2 size = textureSize(u_blockers, 0);
                    ivec2 origin = ivec2(u_source.xy);
                    bool left_source = !inside(origin, size) || !blocked(origin);
                    stop = u_source.z + 2.0;
                    for (float distance = 1.0; distance <= u_source.z; distance += 1.0) {{
                        ivec2 point = ivec2(floor(u_source.xy + heading * distance));
                        if (!inside(point, size)) {{ stop = distance; break; }}
                        if (!blocked(point)) left_source = true;
                        else if (left_source) {{ stop = distance; break; }}
                    }}
                }}
            """,
        )
        self.shadow_program["u_blockers"].value = 0
        self.shadow_vao = self.ctx.simple_vertex_array(self.shadow_program, self.vbo, "in_vert")
        self.shadow_positions = [None] * self.MAX_LIGHTS
        self.shadow_geometry = None
        self.tex_blockers = None
        self.tex_props = None

        self.pos_rad_buf = np.zeros((self.MAX_LIGHTS, 4), dtype=np.float32)
        self.col_foot_buf = np.zeros((self.MAX_LIGHTS, 4), dtype=np.float32)
        self.flags_buf = np.zeros((self.MAX_LIGHTS, 4), dtype=np.float32)
        self.masks_buf = np.zeros((self.MAX_LIGHTS, MAP_ROWS, MAP_COLS), dtype=np.float32)


        self.hud_pos_buf = np.zeros((self.MAX_HUD_LIGHTS, 4), dtype=np.float32)
        self.hud_col_buf = np.zeros((self.MAX_HUD_LIGHTS, 4), dtype=np.float32)

        self.survey_brightness = None
        try:
            self.fog = GPUFog(self.ctx, self.MAX_LIGHTS, self.vbo, moderngl.LINEAR, moderngl.NEAREST)
        except moderngl.Error as exc:
            print(f"[GL] Туман использует CPU ({exc})")
            self.fog = None
        try:
            from elenor.rendering.gpu_scene import GPUSceneRenderer
            self.scene = GPUSceneRenderer(self)
        except Exception as exc:
            print(f"[GL] 2D-сцена использует CPU ({exc})")
            self.scene = None
        try:
            from elenor.rendering.gpu_fov import GPUFov
            self.fov = GPUFov(self)
        except Exception as exc:
            print(f"[GL] FOV использует CPU ({exc})")
            self.fov = None
        try:
            from elenor.rendering.gpu_postfx import GPUPostFX
            self.postfx = GPUPostFX(self)
        except Exception as exc:
            print(f"[GL] PostFX отключён ({exc})")
            self.postfx = None

    def _render_shadows(self, occlusion, lights, cam_x, cam_y, radius_scale):
        geometry = occlusion, occlusion.version
        if self.shadow_geometry != geometry:
            self.shadow_geometry = geometry
            self.shadow_positions[:] = [None] * self.MAX_LIGHTS
            size = occlusion.blockers.shape
            if self.tex_blockers is None or self.tex_blockers.size != size:
                if self.tex_blockers is not None:
                    self.tex_blockers.release()
                    self.tex_props.release()
                self.tex_blockers = self.ctx.texture(size, 1, dtype="f1")
                self.tex_props = self.ctx.texture(size, 1, dtype="f1")
            self.tex_blockers.write(np.ascontiguousarray(occlusion.blockers.T, dtype=np.uint8) * 255)
            if occlusion.has_props:
                self.tex_props.write(np.ascontiguousarray(occlusion.prop_heights.T))
        self.shadow_fbo.use()
        self.tex_blockers.use(0)
        for row, light in enumerate(lights[:self.MAX_LIGHTS]):
            if light.get("ambient", False) or light["radius"] <= 0:
                continue
            x, y, _ = light["pos"]
            reach = light.get("shadow_radius", light["radius"]) * radius_scale
            key = occlusion.light_key(x + cam_x, y + cam_y, reach)
            if self.shadow_positions[row] == key:
                continue
            self.shadow_positions[row] = key
            self.shadow_program["u_source"].value = key
            self.ctx.viewport = (0, row, SHADOW_RAYS, 1)
            self.shadow_vao.render(self.moderngl.TRIANGLE_STRIP)

    def upload_fov(self, fov_mask):
        if fov_mask is not self.uploaded_fov or fov_mask.flags.writeable:
            self.tex_fov.write(np.ascontiguousarray(fov_mask.T, dtype=np.float32))
            self.uploaded_fov = None if fov_mask.flags.writeable else fov_mask

    def render_lit_surface(self, diff_canvas, norm_canvas, entity_y_canvas, fov_mask, cam_x, cam_y, lights, hud_lights, wall_grid_np=None, emissive_canvas=None, enable_ao=True, enable_bloom=True, temple_exposure=False, *, occlusion=None, viewer=(0.0, 0.0), bounce_color=(0.0, 0.0, 0.0), tonemap=True,
                           timings=None, readback=True, fog=None, timer_queries=None, raw_buffers=None, scene_on_gpu=False, gpu_scene_fov=None, fov_on_gpu=False,
                           time_sec=0.0, enable_specular=True, enable_reflections=True):
        self.survey_brightness = None
        if timings is not None and self.timers is None:
            self.timers = tuple(self.ctx.query(time=True) for _ in range(3))
        timers = self.timers if timings is not None else timer_queries
        if not scene_on_gpu:
            self.tex_diff.write(pygame.image.tobytes(diff_canvas, "RGBA"))
            self.tex_norm.write(pygame.image.tobytes(norm_canvas, "RGBA"))
            self.tex_ent_y.write(np.ascontiguousarray(entity_y_canvas.T, dtype=np.float32))
        if not fov_on_gpu:
            self.upload_fov(fov_mask)
        if occlusion is not None:
            wall_grid_np = occlusion.structure
        if wall_grid_np is not None and (occlusion is None or wall_grid_np is not self.uploaded_structure):
            if wall_grid_np.shape != self.tex_walls.size:
                width, height = wall_grid_np.shape
                self.tex_walls.release()
                self.tex_masks.release()
                self.tex_walls = self.ctx.texture((width, height), 1, dtype="f4")
                self.tex_masks = self.ctx.texture((width, height*self.MAX_LIGHTS), 1, dtype="f4")
                self.masks_buf = np.zeros((self.MAX_LIGHTS, height, width), dtype=np.float32)
            self.tex_walls.write(np.ascontiguousarray(wall_grid_np.T, dtype=np.float32))
            self.uploaded_structure = wall_grid_np if occlusion is not None else None
        if not scene_on_gpu and enable_bloom and emissive_canvas is not None:
            self.tex_emissive.write(pygame.image.tobytes(emissive_canvas, "RGBA"))

        n_lgt = min(len(lights), self.MAX_LIGHTS)
        self.pos_rad_buf.fill(0.0)
        self.col_foot_buf.fill(0.0)
        self.flags_buf.fill(0.0)

        shadow_timer = None
        radius_scale = 1.08 if fog is not None else 1.0
        if occlusion is not None:
            if timers is None:
                self._render_shadows(occlusion, lights, cam_x, cam_y, radius_scale)
            else:
                shadow_timer = timers[0]
                with shadow_timer:
                    self._render_shadows(occlusion, lights, cam_x, cam_y, radius_scale)
        any_masks = False
        for i in range(n_lgt):
            lgt = lights[i]
            lx, ly, lz = lgt["pos"]
            cr, cg, cb = lgt["color"]
            self.pos_rad_buf[i] = (lx, ly, lz, lgt["radius"])
            self.col_foot_buf[i] = (cr, cg, cb, lgt.get("foot_y", ly + 4.0))
            ign_d = 1.0 if lgt.get("ignore_depth", False) else 0.0
            allowed = lgt.get("allowed_tiles")
            local = not lgt.get("ambient", False)
            shadows = occlusion is not None and local
            self.flags_buf[i] = (ign_d, isinstance(allowed, np.ndarray), shadows, local)
            if isinstance(allowed, np.ndarray):
                self.masks_buf[i] = allowed.T
                any_masks = True

        if any_masks:
            self.tex_masks.write(self.masks_buf[:n_lgt], viewport=(0, 0, self.tex_walls.width, n_lgt*self.tex_walls.height))

        n_hud = min(len(hud_lights), self.MAX_HUD_LIGHTS)
        self.hud_pos_buf.fill(0.0)
        self.hud_col_buf.fill(0.0)
        for j in range(n_hud):
            hl = hud_lights[j]
            hx, hy, hz = hl["pos"]
            hcr, hcg, hcb = hl["color"]
            self.hud_pos_buf[j] = (hx, hy, hz, hl["radius"])
            self.hud_col_buf[j] = (hcr, hcg, hcb, 1.0)

        self._u_cam.value = (float(cam_x), float(cam_y))
        self._u_viewer.value = viewer
        self._u_has_props.value = occlusion is not None and occlusion.has_props
        self._u_temple_exposure.value = temple_exposure
        self._u_bounce_color.value = bounce_color
        self._u_reflected_light.value = any(bounce_color)
        self._u_tonemap.value = tonemap
        bloom_mode = 1.0 if (enable_bloom and self.postfx is not None) else (2.0 if enable_bloom else 0.0)
        self._u_fx_flags.value = (1.0 if enable_ao else 0.0, bloom_mode)
        self._u_enable_specular.value = bool(enable_specular)
        self._u_time.value = float(time_sec)
        self._u_num_lights.value = n_lgt
        self._u_light_pos_rad.write(self.pos_rad_buf)
        self._u_light_col_foot.write(self.col_foot_buf)
        self._u_light_flags.write(self.flags_buf)

        self._u_num_hud_lights.value = n_hud
        self._u_hud_pos_rad.write(self.hud_pos_buf)
        self._u_hud_col.write(self.hud_col_buf)

        self.fbo.use()
        self.ctx.viewport = (0, 0, VIEW_W, CANVAS_H)
        self.tex_diff.use(0)
        self.tex_norm.use(1)
        self.tex_ent_y.use(2)
        (gpu_scene_fov if gpu_scene_fov is not None else self.tex_fov).use(3)
        self.tex_masks.use(4)
        self.tex_walls.use(5)
        self.tex_emissive.use(6)
        self.tex_shadows.use(7)
        if self.tex_props is not None:
            self.tex_props.use(8)
        if timers is None:
            self.vao.render(self.moderngl.TRIANGLE_STRIP)
        else:
            with timers[1]:
                self.vao.render(self.moderngl.TRIANGLE_STRIP)
        fog_timer = None
        if fog is not None:
            clouds, time, original_fov = fog
            args = self, lights, clouds, time, (cam_x, cam_y), original_fov, fov_mask
            if timers is None:
                self.fog.render(*args)
            else:
                fog_timer = timers[2]
                with fog_timer:
                    self.fog.render(*args)
        src_tex = self.fog.composite if fog is not None else self.tex_out
        src_fbo = self.fog.fbo if fog is not None else self.fbo
        if self.postfx is not None and (enable_reflections or enable_bloom):
            fov_for_post = gpu_scene_fov if gpu_scene_fov is not None else self.tex_fov
            out_tex, out_fbo = self.postfx.render(
                src_tex, src_fbo, self.tex_emissive, self.tex_ent_y, fov_for_post, self.tex_walls,
                (float(cam_x), float(cam_y)), float(time_sec),
                enable_reflections=enable_reflections, enable_bloom=enable_bloom,
            )
        else:
            out_tex, out_fbo = src_tex, src_fbo
        if not readback:
            return out_tex

        read_start = perf_counter() if timings is not None else 0.0
        if fog is None:
            raw = out_fbo.read(components=3, alignment=1)
            pixel_format = "RGB"
        else:
            raw = out_fbo.read(components=4, alignment=1)
            self.survey_brightness = np.frombuffer(raw, dtype=np.uint8).reshape(CANVAS_H, VIEW_W, 4)[..., 3].T
            pixel_format = "RGBX"
        if timings is not None:
            # The read already synchronises the draws, so reading the timers adds no GPU wait.
            timings["read"] = (perf_counter() - read_start) * 1000
            fog_elapsed = fog_timer.elapsed if fog_timer is not None else 0
            elapsed = (timers[1].elapsed, shadow_timer.elapsed if shadow_timer is not None else 0, fog_elapsed)
            if 0xFFFFFFFF not in elapsed:
                timings["gpu"] = sum(elapsed) / 1e6
                if fog_timer is not None:
                    timings["fog_gpu"] = fog_elapsed / 1e6
        return pygame.image.frombuffer(raw, (VIEW_W, CANVAS_H), pixel_format)
