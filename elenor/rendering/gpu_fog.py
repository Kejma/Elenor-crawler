"""Half-resolution fog lit by the same angular shadow atlas as the world."""
import numpy as np

from elenor.config import CANVAS_H, TILE_H, TILE_W, VIEW_H, VIEW_W
from elenor.rendering.occlusion import SHADOW_RAYS


class GPUFog:
    MAX_CLOUDS = 32

    def __init__(self, ctx, max_lights, vbo, linear, nearest):
        self.ctx = ctx
        self.half_size = ((VIEW_W + 1) // 2, (VIEW_H + 1) // 2)
        self.half = ctx.texture(self.half_size, 4, dtype="f1")
        self.half.filter = (linear, linear)
        self.half_fbo = ctx.framebuffer([self.half])
        self.composite = ctx.texture((VIEW_W, CANVAS_H), 4, dtype="f1")
        self.composite.filter = (nearest, nearest)
        self.fbo = ctx.framebuffer([self.composite])
        self.visibility = ctx.texture((VIEW_W, CANVAS_H), 1, dtype="f4")
        self.uploaded_visibility = None
        self.data = np.zeros((3, self.MAX_CLOUDS, 4), dtype=np.float32)
        vertex = """#version 330 core
            in vec2 in_vert;
            void main() { gl_Position = vec4(in_vert, 0.0, 1.0); }
        """
        self.volume = ctx.program(vertex_shader=vertex, fragment_shader=f"""#version 330 core
            uniform vec2 cam;
            uniform int cloud_count;
            uniform vec4 shapes[{self.MAX_CLOUDS}];
            uniform vec4 colors[{self.MAX_CLOUDS}];
            uniform vec4 bounds[{self.MAX_CLOUDS}];
            uniform sampler2D feet_y;
            uniform sampler2D shadows;
            uniform int light_count;
            uniform vec4 positions[{max_lights}];
            uniform vec4 light_colors[{max_lights}];
            uniform vec4 flags[{max_lights}];
            uniform float time;
            out vec4 fog;

            float coverage(int light, float ray, float dist) {{
                float bin = floor(ray);
                int index = int(mod(bin, {float(SHADOW_RAYS)}));
                float a = texelFetch(shadows, ivec2(index, light), 0).r;
                float b = texelFetch(shadows, ivec2((index + 1) % {SHADOW_RAYS}, light), 0).r;
                vec2 t = clamp(vec2(a, b) * .30 + (.5 - dist * .30), 0.0, 1.0);
                return mix(t.x, t.y, fract(ray));
            }}

            void main() {{
                ivec2 sample_px = ivec2(gl_FragCoord.xy) * 2;
                vec2 pixel = vec2(sample_px) + .5;
                vec2 world = pixel + cam;
                float low = 0.0, upper = 0.0;
                vec3 tint = vec3(0.0);
                float floor_noise = .69 + .17 * sin(world.x * .085 + time * .47 + cos(world.y * .13 - time * .31))
                    + .13 * cos(world.y * .20 - time * .6 + sin(world.x * .071 + time * .23));
                float drift = sin(world.x * .057 - time * .32 + cos(world.y * .101 + time * .26))
                    + .60 * cos((world.x - world.y) * .104 + time * .43);
                for (int i = 0; i < cloud_count; ++i) {{
                    vec4 zone = shapes[i];
                    vec2 delta = (world - zone.xy) / zone.z;
                    float radial = 1.0 - dot(delta, delta);
                    if (radial <= 0.0) continue;
                    float density = pow(radial, 1.35) * zone.w;
                    if (colors[i].a > .5) {{
                        vec4 box = bounds[i];
                        vec2 edge = min(world - box.xy, box.zw - world);
                        density *= clamp(min(edge.x, edge.y) / 9.0, 0.0, 1.0);
                    }}
                    float ground = density * floor_noise;
                    float loft = density * clamp((drift - .03) * .39, 0.0, .55);
                    low += ground;
                    upper += loft;
                    tint += (ground + loft) * colors[i].rgb;
                }}
                if (low + upper <= .001) {{ fog = vec4(0.0); return; }}

                vec3 illumination = vec3(0.0);
                for (int i = 0; i < light_count; ++i) {{
                    if (flags[i].z < .5) continue;
                    vec4 light = positions[i];
                    vec2 delta = pixel - light.xy;
                    float radius = light.w * 1.08;
                    float dist = length(delta);
                    if (dist >= radius) continue;
                    float angle = atan(delta.y, delta.x) * {SHADOW_RAYS / (2 * np.pi)};
                    float spread = (.60 + min(dist * .013, 1.50))
                        * {SHADOW_RAYS / (2 * np.pi)} / max(dist, 7.0);
                    float visible = .58 * coverage(i, angle, dist)
                        + .21 * (coverage(i, angle - spread, dist) + coverage(i, angle + spread, dist));
                    float falloff = clamp(1.0 - length(vec2(dist, light.z * .43)) / radius, 0.0, 1.0);
                    float edge = min(1.0, falloff * 5.0);
                    edge *= edge * (3.0 - 2.0 * edge);
                    illumination += (falloff * .77 + falloff * falloff * .23) * edge * visible
                                  * min(1.0, .62 + dist * .017) * light_colors[i].rgb;
                }}
                float clearance = texelFetch(feet_y, sample_px, 0).r - pixel.y;
                float thickness = low * clamp(1.0 - clearance / 13.0, .12, 1.0)
                                + upper * clamp(1.0 - clearance / 26.0, .28, 1.0);
                vec3 color = tint / (low + upper) * (vec3(40.0, 47.0, 59.0) + illumination * 400.0);
                fog = vec4(clamp(color / 255.0, 0.0, 1.0), min(.57, 1.0 - exp(-thickness * 1.9)));
            }}
        """)
        self.mix = ctx.program(vertex_shader=vertex, fragment_shader=f"""#version 330 core
            uniform sampler2D world;
            uniform sampler2D fog;
            uniform sampler2D visibility;
            uniform sampler2D blockers;
            uniform vec2 cam;
            out vec4 result;
            void main() {{
                ivec2 pixel = ivec2(gl_FragCoord.xy);
                vec3 lit = texelFetch(world, pixel, 0).rgb;
                // Preserve the pre-fog brightness test for exploration in the unused alpha channel.
                vec3 rgb_bytes = round(lit * 255.0);
                float surveyed = step(39.0, rgb_bytes.r + rgb_bytes.g + rgb_bytes.b);
                if (pixel.y < {VIEW_H}) {{
                    vec2 size = vec2(textureSize(fog, 0));
                    vec2 uv = (vec2(pixel) * ((size - 1.0) / vec2({VIEW_W}.0, {VIEW_H}.0)) + .5) / size;
                    vec4 mist = texture(fog, uv);
                    ivec2 point = clamp(ivec2(vec2(pixel) + cam), ivec2(0), textureSize(blockers, 0) - 1);
                    float mask = texelFetch(visibility, pixel, 0).r
                               * (1.0 - step(.5, texelFetch(blockers, point, 0).r));
                    lit = mix(lit, mist.rgb, mist.a * mask);
                }}
                result = vec4(lit, surveyed);
            }}
        """)
        self.volume["feet_y"].value = 0
        self.volume["shadows"].value = 1
        for unit, name in enumerate(("world", "fog", "visibility", "blockers")):
            self.mix[name].value = unit
        self.volume_vao = ctx.simple_vertex_array(self.volume, vbo, "in_vert")
        self.mix_vao = ctx.simple_vertex_array(self.mix, vbo, "in_vert")

    def render(self, gl, lights, clouds, time, cam, fov, lit_fov):
        self.data.fill(0)
        count = 0
        for cloud in clouds:
            radius = cloud["radius"] * TILE_W
            if radius <= 0:
                continue
            timer = cloud.get("timer")
            fade = 1.0 if timer is None else max(0.0, min(1.0, timer / min(1.2, cloud["max_timer"])))
            self.data[0, count] = (cloud["wx"] * TILE_W, cloud["wy"] * TILE_H, radius, cloud["density"] * fade)
            box = cloud.get("bounds")
            self.data[1, count] = (*cloud["color"], bool(box))
            if box:
                x, y, w, h = box
                self.data[2, count] = (x * TILE_W, y * TILE_H, (x + w) * TILE_W, (y + h) * TILE_H)
            count += 1

        self.half_fbo.use()
        self.ctx.viewport = (0, 0, *self.half_size)
        self.volume["cam"].value = cam
        self.volume["time"].value = time
        self.volume["cloud_count"].value = count
        self.volume["light_count"].value = len(lights)
        for name, data in zip(("shapes", "colors", "bounds"), self.data):
            self.volume[name].write(data)
        self.volume["positions"].write(gl.pos_rad_buf)
        self.volume["light_colors"].write(gl.col_foot_buf)
        self.volume["flags"].write(gl.flags_buf)
        gl.tex_ent_y.use(0)
        gl.tex_shadows.use(1)
        self.volume_vao.render(gl.moderngl.TRIANGLE_STRIP)

        visibility = gl.tex_fov
        if fov is not lit_fov:
            if fov is not self.uploaded_visibility or fov.flags.writeable:
                self.visibility.write(np.ascontiguousarray(fov.T, dtype=np.float32))
                self.uploaded_visibility = None if fov.flags.writeable else fov
            visibility = self.visibility
        self.fbo.use()
        self.ctx.viewport = (0, 0, VIEW_W, CANVAS_H)
        self.mix["cam"].value = cam
        gl.tex_out.use(0)
        self.half.use(1)
        visibility.use(2)
        gl.tex_blockers.use(3)
        self.mix_vao.render(gl.moderngl.TRIANGLE_STRIP)
