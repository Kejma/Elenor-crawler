"""GPU 2D scene renderer: draws terrain chunks, decals, shadows, sprites, depth, and canopy FOV directly into GPULightShader textures."""

from collections import OrderedDict
import math
import struct
from time import perf_counter

import pygame

from elenor.config import CANVAS_H, TILE_H, TILE_W, VIEW_H, VIEW_W
from elenor.entities.objects import JUNGLE_KEY_COLORS
from elenor.rendering.terrain import DIFFUSE_CLEAR, NORMAL_CLEAR
from elenor.rendering.visibility import canopy_opacity, misted_actor


_PACK_INST = struct.Struct("12f").pack_into
_INST_STRIDE = 48
_MAX_TERRAIN_TEX = 64

_QUAD_VERT = """#version 330 core
in vec2 in_corner;
uniform vec4 u_dest;
uniform vec4 u_src;
uniform vec2 u_canvas;
out vec2 v_uv;
void main() {
    vec2 px = u_dest.xy + in_corner * u_dest.zw;
    gl_Position = vec4((px / u_canvas) * 2.0 - 1.0, 0.0, 1.0);
    v_uv = u_src.xy + in_corner * u_src.zw;
}
"""

_SPRITE_VERT = """#version 330 core
in vec2 in_corner;
in vec4 in_dest;
in vec4 in_src;
in vec4 in_params;
uniform vec2 u_canvas;
uniform int u_require_flag;
out vec2 v_uv;
flat out ivec4 v_bounds;
flat out float v_opacity;
flat out float v_sole_sy;
flat out float v_canopy_vis;
flat out int v_flags;
void main() {
    int flags = int(in_params.w + 0.5);
    if (u_require_flag != 0 && (flags & u_require_flag) == 0) {
        gl_Position = vec4(-2.0, -2.0, 0.0, 1.0);
        return;
    }
    vec2 px = in_dest.xy + in_corner * in_dest.zw;
    gl_Position = vec4((px / u_canvas) * 2.0 - 1.0, 0.0, 1.0);
    v_uv = in_src.xy + in_corner * in_src.zw;
    v_bounds = ivec4(int(in_src.x), int(in_src.y), int(in_src.x + in_src.z) - 1, int(in_src.y + in_src.w) - 1);
    v_opacity = in_params.x;
    v_sole_sy = in_params.y;
    v_canopy_vis = in_params.z;
    v_flags = flags;
}
"""


class _SpriteAtlas:
    WIDTH = 2048
    HEIGHT = 1024

    def __init__(self, ctx, gl):
        self.diff = ctx.texture((self.WIDTH, self.HEIGHT), 4, dtype="f1")
        self.norm = ctx.texture((self.WIDTH, self.HEIGHT), 4, dtype="f1")
        self.em = ctx.texture((self.WIDTH, self.HEIGHT), 4, dtype="f1")
        for tex in (self.diff, self.norm, self.em):
            tex.filter = (gl.NEAREST, gl.NEAREST)
        self.entries = {}
        self.refs = []
        self.x = 0
        self.y = 0
        self.row_h = 0

    def reset(self):
        self.entries.clear()
        self.refs.clear()
        self.x = 0
        self.y = 0
        self.row_h = 0

    def get(self, d_surf, n_surf=None, em_surf=None):
        key = (id(d_surf), id(n_surf) if n_surf is not None else 0, id(em_surf) if em_surf is not None else 0)
        rect = self.entries.get(key)
        if rect is not None:
            return rect
        w, h = d_surf.get_size()
        if self.x + w > self.WIDTH:
            self.x = 0
            self.y += self.row_h
            self.row_h = 0
        if self.y + h > self.HEIGHT:
            self.reset()
        ax, ay = self.x, self.y
        self.x += w
        if h > self.row_h:
            self.row_h = h
        vp = (ax, ay, w, h)
        self.diff.write(pygame.image.tobytes(d_surf, "RGBA"), viewport=vp)
        if n_surf is not None:
            self.norm.write(pygame.image.tobytes(n_surf, "RGBA"), viewport=vp)
        if em_surf is not None:
            self.em.write(pygame.image.tobytes(em_surf, "RGBA"), viewport=vp)
        rect = (ax, ay, w, h)
        self.entries[key] = rect
        self.refs.append((d_surf, n_surf, em_surf))
        return rect


class GPUSceneRenderer:
    def __init__(self, shader):
        self.shader = shader
        self.ctx = shader.ctx
        self.gl = shader.moderngl
        ctx, gl = self.ctx, self.gl

        self.atlas = _SpriteAtlas(ctx, gl)
        self.tex_scene_fov = ctx.texture((VIEW_W, CANVAS_H), 1, dtype="f1")
        self.tex_scene_fov.filter = (gl.NEAREST, gl.NEAREST)

        self.fbo_diff = ctx.framebuffer([shader.tex_diff])
        self.fbo_norm = ctx.framebuffer([shader.tex_norm])
        self.fbo_em = ctx.framebuffer([shader.tex_emissive])
        self.fbo_dn = ctx.framebuffer([shader.tex_diff, shader.tex_norm])
        self.fbo_color = ctx.framebuffer([shader.tex_diff, shader.tex_norm, shader.tex_emissive])
        self.fbo_ent_y = ctx.framebuffer([shader.tex_ent_y])
        self.fbo_fov = ctx.framebuffer([self.tex_scene_fov])

        unit = struct.pack("8f", 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 1.0)
        self.unit_vbo = ctx.buffer(unit)

        self._inst_cap = 512
        self._inst_buf = bytearray(self._inst_cap * _INST_STRIDE)
        self.inst_vbo = ctx.buffer(reserve=len(self._inst_buf), dynamic=True)

        self.quad_dn_prog = ctx.program(
            vertex_shader=_QUAD_VERT,
            fragment_shader="""#version 330 core
                uniform sampler2D u_tex0;
                uniform sampler2D u_tex1;
                in vec2 v_uv;
                layout(location = 0) out vec4 out_diff;
                layout(location = 1) out vec4 out_norm;
                void main() {
                    ivec2 uv = ivec2(floor(v_uv));
                    ivec2 sz = textureSize(u_tex0, 0);
                    if (uv.x < 0 || uv.y < 0 || uv.x >= sz.x || uv.y >= sz.y) discard;
                    out_diff = texelFetch(u_tex0, uv, 0);
                    out_norm = texelFetch(u_tex1, uv, 0);
                }
            """,
        )
        self.quad_dn_prog["u_tex0"].value = 0
        self.quad_dn_prog["u_tex1"].value = 1
        self.quad_dn_prog["u_canvas"].value = (float(VIEW_W), float(CANVAS_H))
        self.quad_dn_vao = ctx.simple_vertex_array(self.quad_dn_prog, self.unit_vbo, "in_corner")

        self.quad_d_prog = ctx.program(
            vertex_shader=_QUAD_VERT,
            fragment_shader="""#version 330 core
                uniform sampler2D u_tex0;
                in vec2 v_uv;
                layout(location = 0) out vec4 out_diff;
                void main() {
                    ivec2 uv = ivec2(floor(v_uv));
                    ivec2 sz = textureSize(u_tex0, 0);
                    if (uv.x < 0 || uv.y < 0 || uv.x >= sz.x || uv.y >= sz.y) discard;
                    out_diff = texelFetch(u_tex0, uv, 0);
                }
            """,
        )
        self.quad_d_prog["u_tex0"].value = 0
        self.quad_d_prog["u_canvas"].value = (float(VIEW_W), float(CANVAS_H))
        self.quad_d_vao = ctx.simple_vertex_array(self.quad_d_prog, self.unit_vbo, "in_corner")

        self.clear_ent_y_prog = ctx.program(
            vertex_shader="""#version 330 core
                in vec2 in_corner;
                void main() { gl_Position = vec4(in_corner * 2.0 - 1.0, 0.0, 1.0); }
            """,
            fragment_shader="""#version 330 core
                layout(location = 0) out float out_y;
                void main() { out_y = -9999.0; }
            """,
        )
        self.clear_ent_y_vao = ctx.simple_vertex_array(self.clear_ent_y_prog, self.unit_vbo, "in_corner")

        self.copy_fov_prog = ctx.program(
            vertex_shader="""#version 330 core
                in vec2 in_corner;
                void main() { gl_Position = vec4(in_corner * 2.0 - 1.0, 0.0, 1.0); }
            """,
            fragment_shader="""#version 330 core
                uniform sampler2D u_floor_fov;
                layout(location = 0) out float out_fov;
                void main() { out_fov = texelFetch(u_floor_fov, ivec2(gl_FragCoord.xy), 0).r; }
            """,
        )
        self.copy_fov_prog["u_floor_fov"].value = 0
        self.copy_fov_vao = ctx.simple_vertex_array(self.copy_fov_prog, self.unit_vbo, "in_corner")

        self.sprite_color_prog = ctx.program(
            vertex_shader=_SPRITE_VERT,
            fragment_shader="""#version 330 core
                uniform sampler2D u_atlas_diff;
                uniform sampler2D u_atlas_norm;
                uniform sampler2D u_atlas_em;
                in vec2 v_uv;
                flat in ivec4 v_bounds;
                flat in float v_opacity;
                flat in int v_flags;
                layout(location = 0) out vec4 out_diff;
                layout(location = 1) out vec4 out_norm;
                layout(location = 2) out vec4 out_em;
                void main() {
                    ivec2 uv = clamp(ivec2(v_uv), v_bounds.xy, v_bounds.zw);
                    vec4 d = texelFetch(u_atlas_diff, uv, 0);
                    d.a *= v_opacity;
                    out_diff = d;
                    if ((v_flags & 1) != 0) {
                        vec4 n = texelFetch(u_atlas_norm, uv, 0);
                        n.a *= v_opacity;
                        out_norm = n;
                    } else {
                        out_norm = vec4(0.0);
                    }
                    if ((v_flags & 2) != 0) {
                        out_em = texelFetch(u_atlas_em, uv, 0);
                    } else {
                        out_em = vec4(0.0);
                    }
                }
            """,
        )
        self.sprite_color_prog["u_atlas_diff"].value = 0
        self.sprite_color_prog["u_atlas_norm"].value = 1
        self.sprite_color_prog["u_atlas_em"].value = 2
        self.sprite_color_prog["u_canvas"].value = (float(VIEW_W), float(CANVAS_H))
        self.sprite_color_prog["u_require_flag"].value = 0

        self.sprite_ent_y_prog = ctx.program(
            vertex_shader=_SPRITE_VERT,
            fragment_shader="""#version 330 core
                uniform sampler2D u_atlas_diff;
                in vec2 v_uv;
                flat in ivec4 v_bounds;
                flat in float v_sole_sy;
                layout(location = 0) out float out_y;
                void main() {
                    ivec2 uv = clamp(ivec2(v_uv), v_bounds.xy, v_bounds.zw);
                    if (texelFetch(u_atlas_diff, uv, 0).a <= 15.0 / 255.0) discard;
                    out_y = v_sole_sy;
                }
            """,
        )
        self.sprite_ent_y_prog["u_atlas_diff"].value = 0
        self.sprite_ent_y_prog["u_canvas"].value = (float(VIEW_W), float(CANVAS_H))
        self.sprite_ent_y_prog["u_require_flag"].value = 4

        self.sprite_fov_prog = ctx.program(
            vertex_shader=_SPRITE_VERT,
            fragment_shader="""#version 330 core
                uniform sampler2D u_atlas_diff;
                uniform sampler2D u_floor_fov;
                in vec2 v_uv;
                flat in ivec4 v_bounds;
                flat in float v_opacity;
                flat in float v_canopy_vis;
                flat in int v_flags;
                layout(location = 0) out vec4 out_fov;
                void main() {
                    ivec2 uv = clamp(ivec2(v_uv), v_bounds.xy, v_bounds.zw);
                    float a = texelFetch(u_atlas_diff, uv, 0).a;
                    if ((v_flags & 8) != 0) {
                        if (a <= 220.0 / 255.0) discard;
                        out_fov = vec4(v_canopy_vis, 0.0, 0.0, v_opacity);
                    } else {
                        if (a <= 15.0 / 255.0) discard;
                        float f = texelFetch(u_floor_fov, ivec2(gl_FragCoord.xy), 0).r;
                        out_fov = vec4(f, 0.0, 0.0, 1.0);
                    }
                }
            """,
        )
        self.sprite_fov_prog["u_atlas_diff"].value = 0
        self.sprite_fov_prog["u_floor_fov"].value = 1
        self.sprite_fov_prog["u_canvas"].value = (float(VIEW_W), float(CANVAS_H))
        self.sprite_fov_prog["u_require_flag"].value = 16

        self._bind_inst_vaos()

        self._chunk_tex = OrderedDict()
        self._door_key_cache = {}
        self._tz_key = None
        self._tz_tex = None
        self._decal_key = None
        self._decal_tex = None
        self._misted_tex = None
        self._dyn_diff_surf = None
        self._dyn_norm_surf = None
        self._dyn_diff_tex = None
        self._dyn_norm_tex = None

    def _bind_inst_vaos(self):
        layout = [
            (self.unit_vbo, "2f", "in_corner"),
            (self.inst_vbo, "4f 4f 4f /i", "in_dest", "in_src", "in_params"),
        ]
        self.sprite_color_vao = self.ctx.vertex_array(self.sprite_color_prog, layout)
        self.sprite_ent_y_vao = self.ctx.vertex_array(self.sprite_ent_y_prog, layout)
        self.sprite_fov_vao = self.ctx.vertex_array(self.sprite_fov_prog, layout)

    def _ensure_inst_cap(self, needed):
        if needed <= self._inst_cap:
            return
        while self._inst_cap < needed:
            self._inst_cap *= 2
        old = self._inst_buf
        self._inst_buf = bytearray(self._inst_cap * _INST_STRIDE)
        self._inst_buf[:len(old)] = old
        self.inst_vbo.release()
        self.inst_vbo = self.ctx.buffer(reserve=len(self._inst_buf), dynamic=True)
        self._bind_inst_vaos()

    def _chunk_textures(self, chunk):
        cid = id(chunk)
        entry = self._chunk_tex.get(cid)
        if entry is None:
            size = chunk.diffuse.get_size()
            td = self.ctx.texture(size, 4, dtype="f1")
            tn = self.ctx.texture(size, 4, dtype="f1")
            td.filter = (self.gl.NEAREST, self.gl.NEAREST)
            tn.filter = (self.gl.NEAREST, self.gl.NEAREST)
            td.write(pygame.image.tobytes(chunk.diffuse, "RGBA"))
            tn.write(pygame.image.tobytes(chunk.normals, "RGBA"))
            self._chunk_tex[cid] = (chunk, td, tn, chunk.frames)
            if len(self._chunk_tex) > _MAX_TERRAIN_TEX:
                _, (_, old_d, old_n, _) = self._chunk_tex.popitem(last=False)
                old_d.release()
                old_n.release()
            return td, tn
        self._chunk_tex.move_to_end(cid)
        _, td, tn, frames = entry
        if frames != chunk.frames:
            td.write(pygame.image.tobytes(chunk.diffuse, "RGBA"))
            tn.write(pygame.image.tobytes(chunk.normals, "RGBA"))
            self._chunk_tex[cid] = (chunk, td, tn, chunk.frames)
        return td, tn

    def _door_pair(self, assets, door):
        key = "door_open" if door.is_open else ("door_locked" if door.locked else "door_closed")
        pair = assets[key]
        if not (door.locked and door.key_color):
            return pair
        ck = (id(pair[0]), door.key_color)
        cached = self._door_key_cache.get(ck)
        if cached is None:
            d = pair[0].copy()
            pygame.draw.rect(d, JUNGLE_KEY_COLORS[door.key_color], (10, 8, 3, 4))
            cached = (d, pair[1])
            self._door_key_cache[ck] = cached
        return cached

    def _ensure_dyn_layer(self):
        if self._dyn_diff_surf is None:
            self._dyn_diff_surf = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
            self._dyn_norm_surf = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
            self._dyn_diff_tex = self.ctx.texture((VIEW_W, VIEW_H), 4, dtype="f1")
            self._dyn_norm_tex = self.ctx.texture((VIEW_W, VIEW_H), 4, dtype="f1")
            self._dyn_diff_tex.filter = (self.gl.NEAREST, self.gl.NEAREST)
            self._dyn_norm_tex.filter = (self.gl.NEAREST, self.gl.NEAREST)

    def _draw_dyn_layer(self, draw_norm=True):
        self._dyn_diff_tex.write(pygame.image.tobytes(self._dyn_diff_surf, "RGBA"))
        self.ctx.enable(self.gl.BLEND)
        if draw_norm:
            self._dyn_norm_tex.write(pygame.image.tobytes(self._dyn_norm_surf, "RGBA"))
            self.fbo_dn.use()
            self._dyn_diff_tex.use(0)
            self._dyn_norm_tex.use(1)
            self.quad_dn_prog["u_dest"].value = (0.0, 0.0, float(VIEW_W), float(VIEW_H))
            self.quad_dn_prog["u_src"].value = (0.0, 0.0, float(VIEW_W), float(VIEW_H))
            self.quad_dn_vao.render(self.gl.TRIANGLE_STRIP)
        else:
            self.fbo_diff.use()
            self._dyn_diff_tex.use(0)
            self.quad_d_prog["u_dest"].value = (0.0, 0.0, float(VIEW_W), float(VIEW_H))
            self.quad_d_prog["u_src"].value = (0.0, 0.0, float(VIEW_W), float(VIEW_H))
            self.quad_d_vao.render(self.gl.TRIANGLE_STRIP)

    def _draw_misted(self, d_surf, draw_x, draw_y, ew, eh):
        if self._misted_tex is None or self._misted_tex.size != (ew, eh):
            if self._misted_tex is not None:
                self._misted_tex.release()
            self._misted_tex = self.ctx.texture((ew, eh), 4, dtype="f1")
            self._misted_tex.filter = (self.gl.NEAREST, self.gl.NEAREST)
        self._misted_tex.write(pygame.image.tobytes(d_surf, "RGBA"))
        self.fbo_diff.use()
        self._misted_tex.use(0)
        self.quad_d_prog["u_dest"].value = (float(draw_x), float(draw_y), float(ew), float(eh))
        self.quad_d_prog["u_src"].value = (0.0, 0.0, float(ew), float(eh))
        self.quad_d_vao.render(self.gl.TRIANGLE_STRIP)

    def _thought_textures(self, tz_diff, tz_norm):
        key = (id(tz_diff), id(tz_norm))
        if self._tz_key != key:
            if self._tz_tex is not None:
                self._tz_tex[0].release()
                self._tz_tex[1].release()
            size = tz_diff.get_size()
            td = self.ctx.texture(size, 4, dtype="f1")
            tn = self.ctx.texture(size, 4, dtype="f1")
            td.filter = (self.gl.NEAREST, self.gl.NEAREST)
            tn.filter = (self.gl.NEAREST, self.gl.NEAREST)
            td.write(pygame.image.tobytes(tz_diff, "RGBA"))
            tn.write(pygame.image.tobytes(tz_norm, "RGBA"))
            self._tz_tex = (td, tn)
            self._tz_key = key
        return self._tz_tex

    def render_world(
        self, renderer, dungeon, player, mobs, objects, cam_x, cam_y, fov_mask,
        visible_tiles, fx_mgr, physical_states, cast, reveal_map, now_sec,
        timings, terrain_pack,
    ):
        chunks, doors, trees = terrain_pack
        if self.atlas.y > self.atlas.HEIGHT - 128:
            self.atlas.reset()

        if timings is not None:
            canopy_start = perf_counter()
        if not reveal_map and trees:
            renderer.canopy_visibility.prefetch(trees, visible_tiles=visible_tiles)
        tall_trees = []
        for c, r, tree_asset_key in trees:
            tile = (c, r)
            target = 1.0 if reveal_map else renderer.canopy_visibility.target(tile)
            visible_base = renderer.canopy_visibility.sample(tile, target)
            if visible_base > .006:
                tall_trees.append((c, r, tree_asset_key, visible_base))
        if timings is not None:
            timings["canopy"] = (perf_counter() - canopy_start) * 1000

        has_trees = bool(tall_trees)
        assets = renderer.assets
        flags_map = fx_mgr.flags if fx_mgr else {}
        use_hit_flash = flags_map.get("hit_flash", True)
        use_shadows = flags_map.get("drop_shadows", True)

        # Собираем плоские объекты пола и объёмные сущности для Y-сортировки
        ground_items = []
        hero_pair = renderer.get_hero_pair(player)
        misted = player.stealth_timer > 0
        if misted:
            hero_pair = (misted_actor(hero_pair[0], now_sec, min(1.0, player.stealth_timer / .24)), hero_pair[1])
        render_list = [{
            "wx": player.x - 0.5 + player.bump_x,
            "wy": player.y - 0.5 + player.bump_y,
            "actor_wx": player.x,
            "actor_wy": player.y,
            "is_player": True,
            "is_actor": True,
            "emissive_role": "hero" if player.has_lit_torch and not misted else None,
            "pair": hero_pair,
            "misted": misted,
            "alpha": 255,
        }]

        for tc, tr, tree_asset_key, visible_base in tall_trees:
            render_list.append({
                "wx": float(tc),
                "wy": float(tr),
                "is_tree": True,
                "canopy_visibility": visible_base,
                "pair": assets.get(tree_asset_key, assets["tall_tree"]),
                "alpha": canopy_opacity(tc, tr, player.x, player.y),
            })

        for (lx, ly), lev in dungeon.levers.items():
            if (lx, ly) in visible_tiles:
                render_list.append({
                    "wx": float(lx), "wy": float(ly),
                    "pair": assets["lever_on" if lev.pulled else "lever_off"],
                    "alpha": 255,
                })
        for br in dungeon.braziers:
            if (br["x"], br["y"]) in visible_tiles:
                render_list.append({
                    "wx": float(br["x"]), "wy": float(br["y"]),
                    "is_light_source": True,
                    "emissive_role": "fire_prop",
                    "pair": assets["brazier"], "alpha": 255,
                })
        for obj in objects:
            if not obj.used and (obj.x, obj.y) in visible_tiles:
                passage = dungeon.passages.get((obj.x, obj.y))
                ground_key = {"up": "jungle_passage_up", "onward": "jungle_passage_up",
                              "back": "jungle_passage_down"}.get(passage, obj.kind)
                if ground_key in ("jungle_passage_up", "jungle_passage_down", "ceramic_shards"):
                    ground_items.append((assets[ground_key], int(obj.x * TILE_W - cam_x), int(obj.y * TILE_H - cam_y)))
                    continue
                if obj.kind in ("woven_rug", "stairs", "trap", "mirror_rail_h", "mirror_rail_v"):
                    ground_items.append((assets[obj.kind], int(obj.x * TILE_W - cam_x), int(obj.y * TILE_H - cam_y - 4)))
                    continue
                pair = renderer.get_world_loot_pair(obj.item) if obj.kind == "loot" else assets.get(obj.kind, assets["loot"])
                is_npc = obj.kind in ("npc_innkeeper", "npc_merchant")
                is_fire = obj.kind in ("campfire", "fireplace", "light_emitter", "light_receiver_on")
                render_list.append({
                    "wx": float(obj.x), "wy": float(obj.y),
                    "actor_wx": obj.x + 0.5, "actor_wy": obj.y + 0.5,
                    "is_actor": is_npc,
                    "is_light_source": is_fire,
                    "emissive_role": "fire_prop" if is_fire else None,
                    "pair": pair, "alpha": 255,
                })

        for m in mobs:
            mx_i, my_i = int(m.x), int(m.y)
            if getattr(m, "size_tiles", 1) >= 2:
                mob_vis = any((mx_i + dx, my_i + dy) in visible_tiles for dx in (-1, 0, 1) for dy in (-1, 0, 1))
            else:
                mob_vis = (mx_i, my_i) in visible_tiles
            if mob_vis:
                chilled = getattr(m, "slow_timer", 0.0) > 0.0
                f_mode = None
                if use_hit_flash and getattr(m, "hit_flash_timer", 0.0) > 0.0:
                    f_mode = "crit" if getattr(m, "hit_flash_crit", False) else "hit"
                render_list.append({
                    "wx": m.x - 0.5 + m.bump_x,
                    "wy": m.y - 0.5 + m.bump_y,
                    "actor_wx": m.x,
                    "actor_wy": m.y,
                    "is_actor": True,
                    "emissive_role": "mob",
                    "pair": renderer.get_mob_pair(m.sprite, getattr(m, "facing", -1), is_chilled=chilled, flash_mode=f_mode),
                    "alpha": 255,
                })

        render_list.sort(key=lambda item: item["wy"])

        world_shadow_lights = [(br["x"] + 0.5, br["y"] + 0.5, br["radius"] / TILE_W) for br in dungeon.braziers]
        for obj in objects:
            if obj.kind in ("campfire", "fireplace"):
                world_shadow_lights.append((obj.x + 0.5, obj.y + 0.5, 7.2))

        atlas = self.atlas
        cam_ix, cam_iy = int(cam_x), int(cam_y)
        any_emissive = False

        # Заранее упаковываем буфер инстансов (плоские объекты + тени + спрайты)
        self._ensure_inst_cap(len(ground_items) + len(render_list) * 2 + 8)
        buf = self._inst_buf
        pack = _PACK_INST
        count = 0
        misted_draw = None

        for (fd, fn), gx, gy in ground_items:
            ax, ay, aw, ah = atlas.get(fd, fn)
            pack(buf, count * _INST_STRIDE,
                 float(gx), float(gy), float(aw), float(ah),
                 float(ax), float(ay), float(aw), float(ah),
                 1.0, -9999.0, 0.0, 1.0)
            count += 1

        shadow_small_rect = atlas.get(renderer._shadow_small)
        shadow_big_rect = atlas.get(renderer._shadow_big)

        for ent in render_list:
            d_surf, n_surf = ent["pair"]
            ew, eh = d_surf.get_size()
            draw_x = int(round(ent["wx"] * TILE_W - cam_x - (ew - TILE_W) // 2))
            draw_y = int(round(ent["wy"] * TILE_H - cam_y - (eh - TILE_H)))
            if draw_y + eh <= 0 or draw_y >= VIEW_H:
                continue
            sole_sy = float(draw_y + eh - 2)

            if use_shadows and ent.get("is_actor", False) and not ent.get("misted", False):
                awx = ent.get("actor_wx", ent["wx"] + 0.5)
                awy = ent.get("actor_wy", ent["wy"] + 0.5)
                vec_x = vec_y = w_sum = 0.0
                for lwx, lwy, lrad in world_shadow_lights:
                    dx_w = awx - lwx
                    dy_w = awy - lwy
                    dist_w = math.hypot(dx_w, dy_w)
                    if 0.1 < dist_w < lrad:
                        w_l = (1.0 - dist_w / lrad) ** 1.5
                        vec_x += (dx_w / dist_w) * w_l
                        vec_y += (dy_w / dist_w) * w_l
                        w_sum += w_l
                if not ent.get("is_player", False) and player.has_lit_torch:
                    dx_p = awx - player.x
                    dy_p = awy - player.y
                    dist_p = math.hypot(dx_p, dy_p)
                    if 0.1 < dist_p < 7.5:
                        w_p = (1.0 - dist_p / 7.5) ** 1.4 * 1.5
                        vec_x += (dx_p / dist_p) * w_p
                        vec_y += (dy_p / dist_p) * w_p
                        w_sum += w_p
                if w_sum > 0.01:
                    sh_dx = max(-3.5, min(3.5, (vec_x / w_sum) * 3.0))
                    sh_dy = max(-2.0, min(2.5, (vec_y / w_sum) * 1.8))
                else:
                    sh_dx, sh_dy = 0.0, 0.5
                sx_r, sy_r, sh_w, sh_h = shadow_big_rect if ew > 20 else shadow_small_rect
                foot_cx = draw_x + ew * 0.5
                pack(buf, count * _INST_STRIDE,
                     float(int(round(foot_cx - sh_w * 0.5 + sh_dx))),
                     float(int(round(sole_sy - sh_h * 0.5 + sh_dy))),
                     float(sh_w), float(sh_h),
                     float(sx_r), float(sy_r), float(sh_w), float(sh_h),
                     1.0, -9999.0, 0.0, 0.0)
                count += 1

            if ent.get("misted", False):
                misted_draw = (count, d_surf, draw_x, draw_y, ew, eh)
                continue

            if ent.get("is_tree", False):
                ax, ay, aw, ah = atlas.get(d_surf, n_surf)
                opacity = ent["alpha"] / 255.0
                pack(buf, count * _INST_STRIDE,
                     float(draw_x), float(draw_y), float(ew), float(eh),
                     float(ax), float(ay), float(aw), float(ah),
                     opacity, -9999.0, float(ent["canopy_visibility"]), 25.0)
                count += 1
                continue

            opacity = ent["alpha"] / 255.0
            if ent["alpha"] < 255:
                ax, ay, aw, ah = atlas.get(d_surf)
                pack(buf, count * _INST_STRIDE,
                     float(draw_x), float(draw_y), float(ew), float(eh),
                     float(ax), float(ay), float(aw), float(ah),
                     opacity, -9999.0, 0.0, 0.0)
                count += 1
                continue

            em_role = ent.get("emissive_role")
            em_s = renderer._get_entity_emissive_surf(d_surf, em_role) if em_role else None
            if em_s is not None:
                any_emissive = True
            ax, ay, aw, ah = atlas.get(d_surf, n_surf, em_s)
            fl = 1
            if em_s is not None:
                fl |= 2
            if not ent.get("is_light_source", False):
                fl |= 4
            if has_trees:
                fl |= 16
            pack(buf, count * _INST_STRIDE,
                 float(draw_x), float(draw_y), float(ew), float(eh),
                 float(ax), float(ay), float(aw), float(ah),
                 1.0, sole_sy, 0.0, float(fl))
            count += 1

        # Отрисовка всех проходов на GPU
        ctx, gl = self.ctx, self.gl
        try:
            ctx.viewport = (0, 0, VIEW_W, CANVAS_H)
            ctx.scissor = None
            ctx.disable(gl.BLEND)
            ctx.blend_func = (gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA)

            # 1. Очистка рабочих текстур
            self.fbo_diff.clear(DIFFUSE_CLEAR[0] / 255.0, DIFFUSE_CLEAR[1] / 255.0, DIFFUSE_CLEAR[2] / 255.0, 1.0)
            self.fbo_norm.clear(NORMAL_CLEAR[0] / 255.0, NORMAL_CLEAR[1] / 255.0, NORMAL_CLEAR[2] / 255.0, 1.0)
            self.fbo_em.clear(0.0, 0.0, 0.0, 0.0)
            self.fbo_ent_y.use()
            self.clear_ent_y_vao.render(gl.TRIANGLE_STRIP)

            ctx.scissor = (0, 0, VIEW_W, VIEW_H)

            # 2. Чанки пола (непрозрачные, 2-6 квадов)
            self.fbo_dn.use()
            for chunk, visible in chunks:
                td, tn = self._chunk_textures(chunk)
                td.use(0)
                tn.use(1)
                self.quad_dn_prog["u_dest"].value = (
                    float(visible.x - cam_ix), float(visible.y - cam_iy),
                    float(visible.width), float(visible.height),
                )
                self.quad_dn_prog["u_src"].value = (
                    float(visible.x - chunk.pixels.x), float(visible.y - chunk.pixels.y),
                    float(visible.width), float(visible.height),
                )
                self.quad_dn_vao.render(gl.TRIANGLE_STRIP)

            # 3. Двери (с альфой поверх пола, но до декалей и сущностей)
            if doors:
                ctx.enable(gl.BLEND)
                d_buf = bytearray(len(doors) * _INST_STRIDE)
                for i, (dx, dy, door) in enumerate(doors):
                    dd, dn = self._door_pair(assets, door)
                    ax, ay, aw, ah = atlas.get(dd, dn)
                    pack(d_buf, i * _INST_STRIDE,
                         float(dx * TILE_W - cam_ix), float(dy * TILE_H - cam_iy), float(aw), float(ah),
                         float(ax), float(ay), float(aw), float(ah),
                         1.0, -9999.0, 0.0, 1.0)
                self.inst_vbo.write(d_buf)
                self.fbo_color.use()
                atlas.diff.use(0)
                atlas.norm.use(1)
                atlas.em.use(2)
                self.sprite_color_vao.render(gl.TRIANGLE_STRIP, instances=len(doors))

            # 4. Декали боя (кровь, обломки, копоть — заливаются только при изменении)
            if fx_mgr and flags_map.get("battle_memory", True) and fx_mgr.has_decals:
                d_key = (id(fx_mgr.decal_surf), fx_mgr.decal_revision)
                if self._decal_key != d_key:
                    sz = fx_mgr.decal_surf.get_size()
                    if self._decal_tex is None or self._decal_tex.size != sz:
                        if self._decal_tex is not None:
                            self._decal_tex.release()
                        self._decal_tex = ctx.texture(sz, 4, dtype="f1")
                        self._decal_tex.filter = (gl.NEAREST, gl.NEAREST)
                    self._decal_tex.write(pygame.image.tobytes(fx_mgr.decal_surf, "RGBA"))
                    self._decal_key = d_key
                ctx.enable(gl.BLEND)
                self.fbo_diff.use()
                self._decal_tex.use(0)
                self.quad_d_prog["u_dest"].value = (0.0, 0.0, float(VIEW_W), float(VIEW_H))
                self.quad_d_prog["u_src"].value = (float(cam_ix), float(cam_iy), float(VIEW_W), float(VIEW_H))
                self.quad_d_vao.render(gl.TRIANGLE_STRIP)

            # 5. Редкие динамические слои пола (круги на воде и капканы)
            has_ripples = bool(fx_mgr and flags_map.get("water_ripples", True) and fx_mgr.ripples)
            has_traps = bool(physical_states and any(s["kind"] in ("trap", "trap_snap") for s in physical_states))
            if has_ripples or has_traps:
                self._ensure_dyn_layer()
                self._dyn_diff_surf.fill((0, 0, 0, 0))
                if has_traps:
                    self._dyn_norm_surf.fill((0, 0, 0, 0))
                if has_ripples:
                    for rp in fx_mgr.ripples:
                        prog_r = 1.0 - (rp["timer"] / rp["max_timer"])
                        rx_s = int(rp["wx"] * TILE_W - cam_x)
                        ry_s = int(rp["wy"] * TILE_H - cam_y)
                        rad_w = max(2, int(2 + prog_r * 7))
                        rad_h = max(1, int(1 + prog_r * 4))
                        palette = ((128, 214, 102), (62, 137, 70)) if rp["green"] else ((85, 165, 210), (50, 110, 150))
                        pygame.draw.ellipse(self._dyn_diff_surf, palette[prog_r >= 0.5],
                                            (rx_s - rad_w, ry_s - rad_h, rad_w * 2, rad_h * 2), 1)
                if has_traps:
                    from elenor.rendering.physical import render_ground_traps
                    render_ground_traps(self._dyn_diff_surf, self._dyn_norm_surf, physical_states, cam_x, cam_y)
                self._draw_dyn_layer(draw_norm=has_traps)

            # 6. Инстанс-батч всех спрайтов, теней, деревьев и свечения
            if count > 0 or misted_draw is not None:
                ctx.enable(gl.BLEND)
                atlas.diff.use(0)
                atlas.norm.use(1)
                atlas.em.use(2)
                if misted_draw is None:
                    self.inst_vbo.write(memoryview(buf)[:count * _INST_STRIDE])
                    self.fbo_color.use()
                    self.sprite_color_vao.render(gl.TRIANGLE_STRIP, instances=count)
                else:
                    split_idx, md_surf, mx, my, mw, mh = misted_draw
                    if split_idx > 0:
                        self.inst_vbo.write(memoryview(buf)[:split_idx * _INST_STRIDE])
                        self.fbo_color.use()
                        self.sprite_color_vao.render(gl.TRIANGLE_STRIP, instances=split_idx)
                    self._draw_misted(md_surf, mx, my, mw, mh)
                    rem = count - split_idx
                    if rem > 0:
                        self.inst_vbo.write(memoryview(buf)[split_idx * _INST_STRIDE:count * _INST_STRIDE])
                        self.fbo_color.use()
                        atlas.diff.use(0)
                        atlas.norm.use(1)
                        atlas.em.use(2)
                        self.sprite_color_vao.render(gl.TRIANGLE_STRIP, instances=rem)
                    if count > 0:
                        self.inst_vbo.write(memoryview(buf)[:count * _INST_STRIDE])

                # 7. Буфер глубины entity_y (без смешивания)
                if count > 0:
                    ctx.disable(gl.BLEND)
                    self.fbo_ent_y.use()
                    atlas.diff.use(0)
                    self.sprite_ent_y_vao.render(gl.TRIANGLE_STRIP, instances=count)

                # 8. Маска крон scene_fov (только если в кадре есть высокие деревья)
                if has_trees:
                    self.fbo_fov.use()
                    ctx.scissor = None
                    ctx.disable(gl.BLEND)
                    self.shader.tex_fov.use(0)
                    self.copy_fov_vao.render(gl.TRIANGLE_STRIP)
                    if count > 0:
                        ctx.scissor = (0, 0, VIEW_W, VIEW_H)
                        ctx.enable(gl.BLEND)
                        atlas.diff.use(0)
                        self.shader.tex_fov.use(1)
                        self.sprite_fov_vao.render(gl.TRIANGLE_STRIP, instances=count)

            # 9. Удочка и поплавок (только во время рыбалки)
            if cast is not None:
                from elenor.rendering.fishing_cast import draw_fishing_cast
                self._ensure_dyn_layer()
                self._dyn_diff_surf.fill((0, 0, 0, 0))
                self._dyn_norm_surf.fill((0, 0, 0, 0))
                draw_fishing_cast(self._dyn_diff_surf, self._dyn_norm_surf, cast, cam_x, cam_y, now_sec)
                ctx.scissor = (0, 0, VIEW_W, VIEW_H)
                self._draw_dyn_layer(draw_norm=True)

            # 10. Плашка зоны мыслей снизу холста
            ctx.scissor = None
            ctx.disable(gl.BLEND)
            tz_d, tz_n = self._thought_textures(*assets["thought_zone"])
            self.fbo_dn.use()
            tz_d.use(0)
            tz_n.use(1)
            tz_w, tz_h = assets["thought_zone"][0].get_size()
            self.quad_dn_prog["u_dest"].value = (0.0, float(VIEW_H), float(tz_w), float(tz_h))
            self.quad_dn_prog["u_src"].value = (0.0, 0.0, float(tz_w), float(tz_h))
            self.quad_dn_vao.render(gl.TRIANGLE_STRIP)
        finally:
            ctx.scissor = None
            ctx.disable(gl.BLEND)

        return (self.tex_scene_fov if has_trees else None), any_emissive