"""WebUI server and handlers mixin for 传话筒 plugin."""

import asyncio
import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from aiohttp import web
from astrbot.api import logger


class WebUIMixin:
    """Mixin providing the built-in WebUI server and API handlers."""

    WEB_INDEX_PATH: Path = Path()  # set in main
    WEBUI_DIR: Path = Path()       # webui directory

    def _get_token(self) -> str:
        return str(self.cfg().get("webui_token", "")).strip()

    async def _authorize(self, request: web.Request):
        token = self._get_token()
        if not token:
            return
        provided = ""
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            provided = auth_header[7:].strip()
        elif "token" in request.query:
            provided = request.query["token"]
        if provided != token:
            raise web.HTTPUnauthorized(text=json.dumps({"message": "Token mismatch"}), content_type="application/json")

    # ------------------------------------------------------------------
    # WebUI lifecycle
    # ------------------------------------------------------------------

    async def _ensure_webui(self):
        if not self._cfg_bool("webui_enabled", True):
            return
        async with self._web_lock:
            if self._web_runner:
                return
            host = str(self.cfg().get("webui_host", "127.0.0.1"))
            port = int(self.cfg().get("webui_port", 18765))
            app = web.Application()
            app.add_routes(
                [
                    web.get("/", self._handle_web_index),
                    web.get("/styles.css", self._handle_static_css),
                    web.get("/app.js", self._handle_static_js),
                    web.get("/api/config", self._handle_get_layout),
                    web.post("/api/config", self._handle_update_layout),
                    web.post("/api/layout/reset", self._handle_reset_layout),
                    web.get("/api/presets", self._handle_list_presets_api),
                    web.post("/api/presets/save", self._handle_save_preset),
                    web.post("/api/presets/load", self._handle_load_preset),
                    web.get("/api/preview-assets", self._handle_preview_assets),
                    web.post("/api/preview/generate", self._handle_generate_preview),
                    web.get("/api/components", self._handle_list_components_api),
                    web.post("/api/components/upload", self._handle_upload_component),
                    web.get("/api/components/raw/{name}", self._handle_component_file),
                    web.get("/api/backgrounds/raw/{name}", self._handle_background_file),
                    web.get("/api/characters/raw/{name}", self._handle_character_file),
                    web.get("/api/fonts/raw/{name}", self._handle_font_file),
                    web.post("/api/emotions/save", self._handle_save_emotions),
                    web.post("/api/emotions/reset", self._handle_reset_emotions),
                    web.get("/api/personas", self._handle_list_personas),
                    web.get("/api/persona-bindings", self._handle_list_persona_bindings),
                    web.post("/api/persona-bindings/save", self._handle_save_persona_binding),
                    web.post("/api/persona-bindings/delete", self._handle_delete_persona_binding),
                ]
            )
            self._web_app = app
            self._web_runner = web.AppRunner(app)
            await self._web_runner.setup()
            self._web_site = web.TCPSite(self._web_runner, host, port)
            try:
                await self._web_site.start()
                logger.info("[传话筒] WebUI 已启动: http://%s:%s", host, port)
            except OSError as exc:
                bind_errnos = {10048, 98, 48}
                if exc.errno in bind_errnos or getattr(exc, "winerror", None) in bind_errnos:
                    logger.warning("[传话筒] WebUI 端口 %s 已被占用，跳过启动", port)
                    self._web_site = None
                    self._web_runner = None
                    self._web_app = None
                else:
                    raise

    async def initialize(self):
        await self._ensure_webui()
        self._emotion_meta()

    async def terminate(self):
        async with self._web_lock:
            if self._web_site:
                await self._web_site.stop()
                self._web_site = None
            if self._web_runner:
                await self._web_runner.cleanup()
                self._web_runner = None
            self._web_app = None

    # ------------------------------------------------------------------
    # WebUI Handlers - Config & Layout
    # ------------------------------------------------------------------

    async def _handle_web_index(self, request: web.Request):
        await self._authorize(request)
        if not self.WEB_INDEX_PATH.exists():
            return web.Response(text="WebUI 索引缺失，请重新部署。", content_type="text/plain")
        return web.FileResponse(path=self.WEB_INDEX_PATH)

    async def _handle_static_css(self, request: web.Request):
        css_path = self.WEBUI_DIR / "styles.css"
        if not css_path.exists():
            return web.Response(status=404, text="styles.css not found")
        return web.FileResponse(path=css_path, headers={"Content-Type": "text/css; charset=utf-8"})

    async def _handle_static_js(self, request: web.Request):
        js_path = self.WEBUI_DIR / "app.js"
        if not js_path.exists():
            return web.Response(status=404, text="app.js not found")
        return web.FileResponse(path=js_path, headers={"Content-Type": "application/javascript; charset=utf-8"})

    async def _handle_get_layout(self, request: web.Request):
        await self._authorize(request)
        emotions = self._emotion_meta()
        emotion_payload = self._emotion_payload()
        layout = self._layout()
        payload = {
            "layout": layout,
            "components": self._list_components(),
            "characters": self._list_characters(),
            "character_roles": self._list_character_roles(),
            "fonts": self._list_fonts(),
            "backgrounds": self._list_backgrounds(),
            "background_groups": self._list_background_groups(),
            "presets": self._list_presets(),
            "bot_name": self._bot_name(),
            "emotion_sets": emotion_payload,
            "canvas": {
                "width": layout["canvas_width"],
                "height": layout["canvas_height"],
            },
        }
        return web.json_response(payload)

    async def _handle_preview_assets(self, request: web.Request):
        await self._authorize(request)
        role = str(request.query.get("role", "")).strip() or None
        bg_group = str(request.query.get("bg_group", "")).strip() or None
        preview = {
            "background": self._random_background_data(bg_group),
            "character": self._preview_character(role),
        }
        return web.json_response(preview)

    async def _handle_generate_preview(self, request: web.Request):
        await self._authorize(request)
        try:
            body = await request.json()
        except Exception:
            raise web.HTTPBadRequest(text="invalid json")
        text = str(body.get("text", "这是一段示例文本，用于预览对话框效果。")).strip()
        emotion = str(body.get("emotion", "happy")).strip()
        if not text:
            raise web.HTTPBadRequest(text="text required")
        try:
            image_path = await self._render_with_fallback(text, emotion)
            if not image_path:
                raise web.HTTPInternalServerError(text="render failed")
            with open(image_path, "rb") as fp:
                image_data = fp.read()
            os.unlink(image_path)
            return web.Response(
                body=image_data,
                content_type="image/png",
                headers={"Cache-Control": "no-cache"}
            )
        except Exception as exc:
            logger.error("[传话筒] 预览生成失败: %s", exc)
            raise web.HTTPInternalServerError(text=f"preview generation failed: {exc}")

    async def _handle_update_layout(self, request: web.Request):
        await self._authorize(request)
        try:
            body = await request.json()
        except Exception:
            raise web.HTTPBadRequest(text="invalid json")
        if not isinstance(body, dict):
            raise web.HTTPBadRequest(text="invalid payload")
        layout = body.get("layout")
        if not isinstance(layout, dict):
            raise web.HTTPBadRequest(text="layout invalid")
        self._set_layout_state(layout)
        return web.json_response({"ok": True})

    async def _handle_reset_layout(self, request: web.Request):
        await self._authorize(request)
        state = self._reset_layout_state()
        self._remember_current_preset(None)
        self._cached_emotions.clear()
        self._emotion_meta()
        return web.json_response({"ok": True, "layout": state})

    # ------------------------------------------------------------------
    # WebUI Handlers - Presets
    # ------------------------------------------------------------------

    async def _handle_list_presets_api(self, request: web.Request):
        await self._authorize(request)
        return web.json_response({"presets": self._list_presets()})

    async def _handle_save_preset(self, request: web.Request):
        await self._authorize(request)
        try:
            body = await request.json()
        except Exception:
            raise web.HTTPBadRequest(text="invalid json")
        name = str(body.get("name", "")).strip()
        layout = body.get("layout")
        if not name:
            raise web.HTTPBadRequest(text="name required")
        if not isinstance(layout, dict):
            raise web.HTTPBadRequest(text="layout invalid")
        record = self._save_preset(name, layout)
        self._set_layout_state(record["layout"])
        self._remember_current_preset(record)
        self._cached_emotions.clear()
        self._emotion_meta()
        return web.json_response({
            "ok": True,
            "preset": {k: record.get(k) for k in ("name", "slug", "saved_at")},
            "layout": record["layout"],
            "presets": self._list_presets(),
            "character_roles": self._list_character_roles(),
        })

    async def _handle_load_preset(self, request: web.Request):
        await self._authorize(request)
        try:
            body = await request.json()
        except Exception:
            raise web.HTTPBadRequest(text="invalid json")
        identifier = str(body.get("name", "")).strip()
        if not identifier:
            raise web.HTTPBadRequest(text="name required")
        record = self._load_preset(identifier)
        if not record:
            raise web.HTTPNotFound(text="preset not found")
        self._set_layout_state(record["layout"])
        self._remember_current_preset(record)
        self._cached_emotions.clear()
        self._emotion_meta()
        return web.json_response({
            "ok": True,
            "preset": {k: record.get(k) for k in ("name", "slug", "saved_at")},
            "layout": record["layout"],
            "presets": self._list_presets(),
            "character_roles": self._list_character_roles(),
        })

    # ------------------------------------------------------------------
    # WebUI Handlers - Upload & Assets
    # ------------------------------------------------------------------

    async def _handle_list_components_api(self, request: web.Request):
        await self._authorize(request)
        return web.json_response({"components": self._list_components(), "fonts": self._list_fonts()})

    async def _handle_upload_component(self, request: web.Request):
        await self._authorize(request)
        content_type = request.content_type or ""
        payload: dict[str, Any] = {}
        binary_data: bytes | None = None
        kind = "component"
        emotion_from_form = ""
        role_from_form = ""
        bg_group_from_form = ""
        if "multipart/form-data" in content_type:
            form = await request.post()
            file_field = form.get("file")
            if not file_field or not getattr(file_field, "file", None):
                raise web.HTTPBadRequest(text="file required")
            filename = str(form.get("filename") or getattr(file_field, "filename", "") or "").strip()
            kind = str(form.get("kind") or "component").lower()
            emotion_from_form = str(form.get("emotion") or "").strip()
            role_from_form = str(form.get("role") or "").strip()
            bg_group_from_form = str(form.get("background_group") or "").strip()
            binary_data = file_field.file.read()
        else:
            try:
                payload = await request.json()
            except Exception:
                raise web.HTTPBadRequest(text="invalid json")
            filename = str(payload.get("filename") or "").strip()
            data = payload.get("data")
            kind = str(payload.get("kind") or "component").lower()
            if not filename or not data:
                raise web.HTTPBadRequest(text="filename/data required")
            try:
                binary_data = base64.b64decode(str(data).split(",")[-1])
            except Exception:
                raise web.HTTPBadRequest(text="invalid data")
            emotion_from_form = str((payload or {}).get("emotion") or "").strip()
            role_from_form = str((payload or {}).get("role") or "").strip()
            bg_group_from_form = str((payload or {}).get("background_group") or "").strip()
        if kind == "font":
            allowed = (".ttf", ".ttc", ".otf")
            target_dir = self._font_dir
        elif kind == "character":
            allowed = (".png", ".webp")
            emotion_folder = self._sanitize_folder_name(emotion_from_form or "custom", "custom")
            role_folder = self._sanitize_role_name(role_from_form or "general", "general")
            target_dir = self._user_char_dir / role_folder / emotion_folder
            target_dir.mkdir(parents=True, exist_ok=True)
        elif kind == "background":
            allowed = (".png", ".jpg", ".jpeg", ".webp")
            group_folder = self._sanitize_folder_name(bg_group_from_form or "default", "default")
            target_dir = self._user_bg_dir / group_folder
            target_dir.mkdir(parents=True, exist_ok=True)
        else:
            allowed = (".png", ".webp", ".gif")
            target_dir = self._component_dir
        if not filename.lower().endswith(allowed):
            raise web.HTTPBadRequest(text=f"only {'/'.join(allowed)} allowed")
        try:
            safe_name = Path(filename).name
            target = target_dir / safe_name
            if not binary_data:
                raise ValueError("empty payload")
            with open(target, "wb") as fp:
                fp.write(binary_data)
        except Exception as exc:
            raise web.HTTPBadRequest(text=f"upload failed: {exc}")
        return web.json_response({
            "ok": True,
            "components": self._list_components(),
            "fonts": self._list_fonts(),
            "characters": self._list_characters(),
            "backgrounds": self._list_backgrounds(),
            "background_groups": self._list_background_groups(),
        })

    async def _handle_component_file(self, request: web.Request):
        await self._authorize(request)
        name = request.match_info.get("name", "")
        path = self._resolve_component_path(name)
        if not path:
            raise web.HTTPNotFound()
        return web.FileResponse(path)

    async def _handle_background_file(self, request: web.Request):
        await self._authorize(request)
        name = request.match_info.get("name", "")
        path = self._resolve_background_file(name)
        if not path:
            raise web.HTTPNotFound()
        return web.FileResponse(path)

    async def _handle_character_file(self, request: web.Request):
        await self._authorize(request)
        name = request.match_info.get("name", "")
        path = self._resolve_character_file(name)
        if not path:
            raise web.HTTPNotFound()
        return web.FileResponse(path)

    async def _handle_font_file(self, request: web.Request):
        await self._authorize(request)
        name = request.match_info.get("name", "")
        path = self._resolve_font_path(name)
        if not path:
            raise web.HTTPNotFound()
        suffix = Path(path).suffix.lower()
        if suffix == ".otf":
            content_type = "font/otf"
        elif suffix == ".ttc":
            content_type = "font/collection"
        else:
            content_type = "font/ttf"
        return web.FileResponse(path, headers={"Content-Type": content_type})

    # ------------------------------------------------------------------
    # WebUI Handlers - Emotions
    # ------------------------------------------------------------------

    async def _handle_save_emotions(self, request: web.Request):
        await self._authorize(request)
        try:
            body = await request.json()
        except Exception:
            raise web.HTTPBadRequest(text="invalid json")
        records = body.get("emotions")
        if not isinstance(records, list):
            raise web.HTTPBadRequest(text="emotions required")
        normalized = self._persist_emotion_sets(records)
        self._emotion_records = normalized
        self._cached_emotions.clear()
        logger.info("[传话筒] WebUI 已保存情绪配置")
        return web.json_response({
            "ok": True,
            "emotion_sets": self._emotion_payload(),
        })

    async def _handle_reset_emotions(self, request: web.Request):
        await self._authorize(request)
        from models import DEFAULT_EMOTIONS
        import copy
        normalized = self._persist_emotion_sets(copy.deepcopy(DEFAULT_EMOTIONS))
        self._emotion_records = normalized
        self._cached_emotions.clear()
        logger.info("[传话筒] WebUI 请求恢复默认情绪配置")
        return web.json_response({
            "ok": True,
            "emotion_sets": self._emotion_payload(),
        })

    # ------------------------------------------------------------------
    # WebUI Handlers - Personas
    # ------------------------------------------------------------------

    async def _handle_list_personas(self, request: web.Request):
        await self._authorize(request)
        return web.json_response({"personas": self._list_personas()})

    async def _handle_list_persona_bindings(self, request: web.Request):
        await self._authorize(request)
        return web.json_response({
            "bindings": self._persona_binding_records(),
            "presets": self._list_presets(),
            "personas": self._list_personas(),
        })

    async def _handle_save_persona_binding(self, request: web.Request):
        await self._authorize(request)
        try:
            body = await request.json()
        except Exception:
            raise web.HTTPBadRequest(text="invalid json")
        persona_ref = str(body.get("persona_id", "") or "").strip()
        preset_identifier = str(body.get("preset_name") or body.get("preset_slug") or body.get("name") or "").strip()
        if not persona_ref or not preset_identifier:
            raise web.HTTPBadRequest(text="persona_id and preset_name required")
        ok, message, _ = self._set_persona_preset_binding(persona_ref, preset_identifier)
        if not ok:
            raise web.HTTPBadRequest(text=message)
        logger.info("[传话筒] WebUI 已添加人格预设绑定：%s", persona_ref)
        return web.json_response({
            "ok": True,
            "message": message,
            "bindings": self._persona_binding_records(),
        })

    async def _handle_delete_persona_binding(self, request: web.Request):
        await self._authorize(request)
        try:
            body = await request.json()
        except Exception:
            raise web.HTTPBadRequest(text="invalid json")
        persona_ref = str(body.get("persona_id", "") or "").strip()
        if not persona_ref:
            raise web.HTTPBadRequest(text="persona_id required")
        ok, message = self._clear_persona_preset_binding(persona_ref)
        if not ok:
            raise web.HTTPNotFound(text=message)
        logger.info("[传话筒] WebUI 已解除人格预设绑定：%s", persona_ref)
        return web.json_response({
            "ok": True,
            "message": message,
            "bindings": self._persona_binding_records(),
        })