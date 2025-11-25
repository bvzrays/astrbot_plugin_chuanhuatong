import asyncio
import base64
import copy
import json
import mimetypes
import os
import random
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

import astrbot.api.message_components as Comp
from aiohttp import web
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import LLMResponse, ProviderRequest
from astrbot.api.star import Context, Star, register
from PIL import Image, ImageDraw, ImageFilter, ImageFont

PLAIN_COMPONENT_TYPES = tuple(
    getattr(Comp, name)
    for name in ("Plain", "Text")
    if hasattr(Comp, name)
)
LINEBREAK_COMPONENT = getattr(Comp, "LineBreak", None)


@dataclass
class EmotionMeta:
    key: str
    folder: str
    label: str
    color: str
    enabled: bool = True


@register(
    "astrbot_plugin_chuanhuatong",
    "bvzrays",
    "传话筒：将 Bot 的文字回复渲染为 Gal 风立绘对话框",
    "1.3.0",
    "https://github.com/bvzrays/astrbot_plugin_chuanhuatong",
)
class ChuanHuaTongPlugin(Star):
    """传话筒——拦截所有文本回复并渲染立绘对话框。"""

    EMOTION_PATTERN = re.compile(r"&([a-zA-Z0-9_]+)&")

    DEFAULT_EMOTIONS: list[dict[str, Any]] = [
        {"key": "neutral", "folder": "shy", "label": "平静", "color": "#A9C5FF", "enabled": True},
        {"key": "happy", "folder": "happy", "label": "开心", "color": "#FFC857", "enabled": True},
        {"key": "sad", "folder": "sad", "label": "低落", "color": "#7DA1FF", "enabled": True},
        {"key": "shy", "folder": "shy", "label": "害羞", "color": "#F9C5D1", "enabled": True},
        {"key": "surprise", "folder": "surprise", "label": "惊讶", "color": "#F5E960", "enabled": True},
        {"key": "angry", "folder": "sad", "label": "生气", "color": "#FF8A8A", "enabled": True},
    ]

    DEFAULT_PROMPT_TEMPLATE = (
        "请在回答正文中就近插入一个情绪标签，例如 {tags}。"
        "标签写在对应句子旁即可，便于渲染立绘。标签仅包含字母、数字或下划线。"
    )

    DEFAULT_LAYOUT: Dict[str, Any] = {
        "canvas_width": 1600,
        "canvas_height": 600,
        "background_color": "#05060a",
        "background_asset": "__auto__",
        "box_left": 372.987132257021,
        "box_top": 284.43201385917496,
        "box_width": 1227.1886120996442,
        "box_height": 317.58007117437717,
        "padding": 28,
        "font_size": 56,
        "line_height": 1.1,
        "align": "left",
        "radius": 26,
        "text_color": "#ffffff",
        "text_stroke_width": 1,
        "text_stroke_color": "#ffffff",
        "text_bg": "rgba(0,0,0,0.52)",
        "text_shadow": "0 3px 12px rgba(0,0,0,0.55)",
        "body_font": "方正风雅宋简体.ttf",
        "textbox_z_index": 130,
        "character_asset": "__auto__",
        "character_left": 1.0676156583630245,
        "character_bottom": 0,
        "character_width": 499.72719967439286,
        "character_z_index": 140,
        "character_shadow": "drop-shadow(0 12px 36px rgba(0,0,0,0.6))",
        "text_overlays": [
            {
                "id": "ov_1764055391684",
                "type": "glass",
                "text": "",
                "image": "",
                "font": "",
                "left": 283,
                "top": 282,
                "width": 1317,
                "height": 354,
                "font_size": 28,
                "color": "#ffffff",
                "stroke_width": 0,
                "stroke_color": "#000000",
                "bold": True,
                "z_index": 100,
                "visible": True,
                "opacity": 1.0,
            },
            {
                "id": "ov_1764055442570",
                "type": "image",
                "text": "",
                "image": "名称框.png",
                "font": "",
                "left": 410,
                "top": 166,
                "width": 150,
                "height": 164,
                "font_size": 28,
                "color": "#FFFFFF",
                "stroke_width": 0,
                "stroke_color": "#000000",
                "bold": True,
                "z_index": 110,
                "visible": True,
                "opacity": 1.0,
            },
            {
                "id": "ov_1764055449125",
                "type": "image",
                "text": "",
                "image": "底框.png",
                "font": "",
                "left": -18,
                "top": 169,
                "width": 1632,
                "height": 495,
                "font_size": 24,
                "color": "#ffffff",
                "stroke_width": 0,
                "stroke_color": "#000000",
                "bold": True,
                "z_index": 120,
                "visible": True,
                "opacity": 1.0,
            },
            {
                "id": "ov_1764055563203",
                "type": "text",
                "text": "樱",
                "image": "",
                "font": "方正风雅宋简体.ttf",
                "left": 450,
                "top": 201,
                "width": 90,
                "height": 72,
                "font_size": 72,
                "color": "#b66363",
                "stroke_width": 1,
                "stroke_color": "#763737",
                "bold": True,
                "z_index": 180,
                "visible": True,
                "opacity": 1.0,
            },
            {
                "id": "ov_1764055643818",
                "type": "text",
                "text": "羽",
                "image": "",
                "font": "方正风雅宋简体.ttf",
                "left": 525,
                "top": 222,
                "width": 56,
                "height": 41,
                "font_size": 50,
                "color": "#ffffff",
                "stroke_width": 1,
                "stroke_color": "#d6d6d6",
                "bold": True,
                "z_index": 170,
                "visible": True,
                "opacity": 1.0,
            },
            {
                "id": "ov_1764055668857",
                "type": "text",
                "text": "艾",
                "image": "",
                "font": "方正风雅宋简体.ttf",
                "left": 579,
                "top": 206,
                "width": 69,
                "height": 68,
                "font_size": 64,
                "color": "#ffffff",
                "stroke_width": 1,
                "stroke_color": "#d9d9d9",
                "bold": True,
                "z_index": 160,
                "visible": True,
                "opacity": 1.0,
            },
            {
                "id": "ov_1764055669272",
                "type": "text",
                "text": "玛",
                "image": "",
                "font": "方正风雅宋简体.ttf",
                "left": 652,
                "top": 221,
                "width": 50,
                "height": 48,
                "font_size": 50,
                "color": "#ffffff",
                "stroke_width": 1,
                "stroke_color": "#c7c7c7",
                "bold": True,
                "z_index": 150,
                "visible": True,
                "opacity": 1.0,
            },
            {
                "id": "ov_1764057760732",
                "type": "image",
                "text": "",
                "image": "线索.png",
                "font": "",
                "left": 1382,
                "top": 0,
                "width": 104,
                "height": 105,
                "font_size": 24,
                "color": "#ffffff",
                "stroke_width": 0,
                "stroke_color": "#000000",
                "bold": True,
                "z_index": 200,
                "visible": True,
                "opacity": 1.0,
            },
            {
                "id": "ov_1764057771825",
                "type": "image",
                "text": "",
                "image": "设置.png",
                "font": "",
                "left": 1486,
                "top": 3,
                "width": 100,
                "height": 100,
                "font_size": 24,
                "color": "#ffffff",
                "stroke_width": 0,
                "stroke_color": "#000000",
                "bold": True,
                "z_index": 190,
                "visible": True,
                "opacity": 1.0,
            },
        ],
    }

    WEB_INDEX_PATH = Path(__file__).with_name("webui").joinpath("index.html")

    def __init__(self, context: Context, config: Optional[AstrBotConfig] = None):
        super().__init__(context)
        self._cfg_obj: AstrBotConfig | dict | None = config
        self._base_dir = Path(__file__).resolve().parent
        self._bg_dir = self._base_dir / str(self.cfg().get("background_dir", "background"))
        self._char_dir = self._base_dir / str(self.cfg().get("character_root", "renwulihui"))
        self._bg_dir.mkdir(parents=True, exist_ok=True)
        self._char_dir.mkdir(parents=True, exist_ok=True)
        self._builtin_component_dir = self._base_dir / "zujian"
        self._builtin_component_dir.mkdir(parents=True, exist_ok=True)
        self._builtin_font_dir = self._base_dir / "ziti"
        self._builtin_font_dir.mkdir(parents=True, exist_ok=True)

        self._data_dir = Path(os.getcwd()) / "data" / "plugin_data" / "astrbot_plugin_chuanhuatong"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._component_dir = self._data_dir / "zujian"
        self._component_dir.mkdir(parents=True, exist_ok=True)
        self._font_dir = self._data_dir / "fonts"
        self._font_dir.mkdir(parents=True, exist_ok=True)
        self._layout_file = self._data_dir / "layout_state.json"
        self._layout_lock = asyncio.Lock()
        self._layout_state = self._load_layout_state()
        self._web_runner: Optional[web.AppRunner] = None
        self._web_site: Optional[web.TCPSite] = None
        self._web_app: Optional[web.Application] = None
        self._web_lock = asyncio.Lock()
        self._render_semaphore = asyncio.Semaphore(3)
        self._cached_emotions: Dict[str, EmotionMeta] = {}
        self._ensure_prompt_template()
        self._last_background_path: str = ""
        self._last_character_path: str = ""

    def cfg(self) -> Dict[str, Any]:
        try:
            return self._cfg_obj if isinstance(self._cfg_obj, dict) else (self._cfg_obj or {})
        except Exception:
            return {}

    def _cfg_bool(self, key: str, default: bool) -> bool:
        val = self.cfg().get(key, default)
        return bool(val) if not isinstance(val, str) else val.lower() in {"1", "true", "yes", "on"}

    def _layout(self) -> Dict[str, Any]:
        return copy.deepcopy(self._layout_state)

    def _load_layout_state(self) -> Dict[str, Any]:
        if self._layout_file.exists():
            try:
                data = json.loads(self._layout_file.read_text(encoding="utf-8"))
                return self._normalize_layout(data)
            except Exception:
                logger.warning("[传话筒] 无法读取自定义布局，使用默认布局。")
        legacy = self.cfg().get("text_layout") or {}
        state = self._normalize_layout(self._convert_legacy_layout(legacy))
        self._save_layout_state(state)
        return state

    def _save_layout_state(self, layout: Dict[str, Any]):
        try:
            self._layout_file.write_text(json.dumps(layout, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.error("[传话筒] 写入布局文件失败: %s", exc)

    def _reset_layout_state(self) -> Dict[str, Any]:
        state = self._normalize_layout(copy.deepcopy(self.DEFAULT_LAYOUT))
        self._save_layout_state(state)
        self._layout_state = state
        return state

    def _set_layout_state(self, layout: Dict[str, Any]):
        normalized = self._normalize_layout(layout)
        self._layout_state = normalized
        self._save_layout_state(normalized)

    def _normalize_layout(self, layout: Dict[str, Any]) -> Dict[str, Any]:
        data = copy.deepcopy(self.DEFAULT_LAYOUT)
        for key, value in (layout or {}).items():
            if key == "text_overlays":
                continue
            if key in data and value is not None:
                data[key] = value
        data["text_overlays"] = self._normalize_overlays((layout or {}).get("text_overlays"))
        return data

    def _convert_legacy_layout(self, legacy: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(legacy, dict) or not legacy:
            return copy.deepcopy(self.DEFAULT_LAYOUT)
        data = copy.deepcopy(self.DEFAULT_LAYOUT)
        for key in data.keys():
            if key in legacy and legacy[key] is not None:
                data[key] = legacy[key]
        data["text_overlays"] = legacy.get("text_overlays", [])
        return data

    def _normalize_overlays(self, overlays_raw) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        if not isinstance(overlays_raw, list):
            overlays_raw = []
        for item in overlays_raw:
            if not isinstance(item, dict):
                continue
            overlay_id = str(item.get("id") or uuid4().hex)
            layer_type = str(item.get("type", "text")).lower()
            if layer_type == "converted_text":
                layer_type = "text"
            if layer_type not in {"text", "image", "glass"}:
                layer_type = "text"
            try:
                left = int(float(item.get("left", 0)))
                top = int(float(item.get("top", 0)))
                width = max(20, int(float(item.get("width", 200))))
                height = max(20, int(float(item.get("height", 60))))
                font_size = max(8, int(float(item.get("font_size", 28))))
                stroke_width = max(0, int(float(item.get("stroke_width", 0))))
                z_index = int(item.get("z_index", 300))
            except Exception:
                left, top, width, height, font_size, stroke_width, z_index = 0, 0, 200, 60, 28, 0, 300
            color = str(item.get("color") or "#FFFFFF")
            stroke_color = str(item.get("stroke_color") or "#000000")
            bold = bool(item.get("bold", True))
            visible = bool(item.get("visible", True))
            opacity = float(item.get("opacity", 1.0))
            image_name = str(item.get("image") or "").strip()
            font_name = str(item.get("font") or "").strip()
            normalized.append(
                {
                    "id": overlay_id,
                    "type": layer_type,
                    "text": str(item.get("text", "")).strip(),
                    "image": image_name,
                    "font": font_name,
                    "left": left,
                    "top": top,
                    "width": width,
                    "height": height,
                    "font_size": font_size,
                    "color": color,
                    "stroke_width": stroke_width,
                    "stroke_color": stroke_color,
                    "bold": bold,
                    "z_index": z_index,
                    "visible": visible,
                    "opacity": max(0.0, min(1.0, opacity)),
                }
            )
        return normalized

    def _list_components(self) -> list[str]:
        names: Dict[str, Path] = {}
        for directory in [self._component_dir, self._builtin_component_dir]:
            try:
                for f in directory.iterdir():
                    if f.is_file() and f.suffix.lower() in {".png", ".webp", ".gif"}:
                        if f.name not in names:
                            names[f.name] = f
            except Exception:
                continue
        return sorted(names.keys())

    def _resolve_component_path(self, name: str) -> str:
        if not name:
            return ""
        safe_name = Path(name).name
        for directory in [self._component_dir, self._builtin_component_dir]:
            candidate = directory / safe_name
            if candidate.exists():
                return str(candidate)
        return ""

    def _list_fonts(self) -> list[str]:
        names: Dict[str, Path] = {}
        for directory in [self._font_dir, self._builtin_font_dir]:
            try:
                for f in directory.iterdir():
                    if f.is_file() and f.suffix.lower() in {".ttf", ".ttc", ".otf"}:
                        if f.name not in names:
                            names[f.name] = f
            except Exception:
                continue
        return sorted(names.keys())

    def _list_characters(self) -> list[str]:
        """列出所有立绘文件（从renwulihui文件夹的所有子文件夹中）"""
        names: Dict[str, Path] = {}
        try:
            if not self._char_dir.exists():
                return []
            # 遍历所有情绪文件夹
            for emotion_dir in self._char_dir.iterdir():
                if not emotion_dir.is_dir():
                    continue
                for f in emotion_dir.iterdir():
                    if f.is_file() and f.suffix.lower() in {".png", ".webp"}:
                        if f.name not in names:
                            names[f.name] = f
        except Exception:
            pass
        return sorted(names.keys())

    def _resolve_font_path(self, name: str) -> Optional[str]:
        if not name:
            return None
        if os.path.isabs(name) and Path(name).exists():
            return name
        safe_name = Path(name).name
        for directory in [self._font_dir, self._builtin_font_dir]:
            candidate = directory / safe_name
            if candidate.exists():
                return str(candidate)
        return None

    def _list_backgrounds(self) -> list[str]:
        try:
            return sorted([
                f.name for f in self._bg_dir.iterdir()
                if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
            ])
        except Exception:
            return []

    def _load_emotion_sets(self) -> Dict[str, EmotionMeta]:
        src = self.cfg().get("emotion_sets")
        records: list[dict[str, Any]] = []
        if isinstance(src, list):
            records = src
        else:
            records = self.DEFAULT_EMOTIONS
        prepared: Dict[str, EmotionMeta] = {}
        enabled_keys: list[str] = []
        for item in records:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or "").strip()
            if not key:
                continue
            folder = str(item.get("folder") or "").strip() or key
            meta = EmotionMeta(
                key=key,
                folder=folder,
                label=str(item.get("label") or key),
                color=str(item.get("color") or "#FFFFFF"),
                enabled=bool(item.get("enabled", True)),
            )
            prepared[key] = meta
            if meta.enabled:
                enabled_keys.append(key)
        if not prepared:
            for item in self.DEFAULT_EMOTIONS:
                meta = EmotionMeta(**item)
                prepared[meta.key] = meta
                if meta.enabled:
                    enabled_keys.append(meta.key)
        if not enabled_keys:
            first_key = next(iter(prepared))
            meta = prepared[first_key]
            prepared[first_key] = EmotionMeta(
                key=meta.key,
                folder=meta.folder,
                label=meta.label,
                color=meta.color,
                enabled=True,
            )
        return {k: v for k, v in prepared.items() if v.enabled}

    def _emotion_meta(self) -> Dict[str, EmotionMeta]:
        if not self._cached_emotions:
            self._cached_emotions = self._load_emotion_sets()
        return self._cached_emotions.copy()

    def _emotion_from_text(self, text: str) -> Tuple[str, str]:
        mapping = self._emotion_meta()
        matches = self.EMOTION_PATTERN.findall(text)
        selected: Optional[str] = None
        cleaned = text
        if matches:
            for raw in matches:
                cleaned = cleaned.replace(f"&{raw}&", "")
                key = raw.lower()
                if selected is None and key in mapping:
                    selected = key
        default_key = str(self.cfg().get("default_emotion", "")).lower()
        if not default_key or default_key not in mapping:
            default_key = next(iter(mapping.keys()))
        return (selected or default_key), cleaned.strip()

    def _file_to_data_url(self, file_path: Path) -> str:
        if not file_path.exists():
            return ""
        try:
            mime, _ = mimetypes.guess_type(str(file_path))
            mime = mime or "image/png"
            data = file_path.read_bytes()
            return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
        except Exception as exc:
            logger.error(f"[传话筒] 读取文件失败: {exc}")
            return ""

    def _path_to_data_url(self, path: str) -> str:
        if not path:
            return ""
        return self._file_to_data_url(Path(path))

    def _random_background_data(self) -> str:
        path = self._pick_random_asset(self._bg_dir, {".png", ".jpg", ".jpeg", ".webp"})
        self._last_background_path = path or ""
        return self._path_to_data_url(path)

    def _random_character_data(self, emotion_key: str) -> str:
        path = self._pick_character_path(emotion_key)
        return self._path_to_data_url(path)

    def _pick_character_path(self, emotion_key: str) -> str:
        mapping = self._emotion_meta()
        meta = mapping.get(emotion_key)
        if not meta and mapping:
            meta = next(iter(mapping.values()))
        if not meta:
            return ""
        target_dir = self._char_dir / meta.folder
        if not target_dir.exists():
            target_dir.mkdir(parents=True, exist_ok=True)
        path = self._pick_random_asset(target_dir, {".png", ".webp"})
        self._last_character_path = path or ""
        return path or ""

    def _pick_random_asset(self, directory: Path, suffixes: set[str]) -> str:
        try:
            files = [
                str(f) for f in directory.iterdir()
                if f.is_file() and f.suffix.lower() in suffixes
            ]
        except Exception:
            files = []
        if not files:
            return ""
        return random.choice(files)

    def _resolve_background_asset(self, asset: str | None) -> str:
        name = str(asset or "").strip()
        if name and name not in {"__auto__", "__random__"}:
            path = self._resolve_background_file(name)
            if path:
                return path
        path = self._pick_random_asset(self._bg_dir, {".png", ".jpg", ".jpeg", ".webp"})
        self._last_background_path = path or ""
        return path or ""

    def _resolve_background_file(self, name: str) -> str:
        safe = Path(name).name
        candidate = self._bg_dir / safe
        if candidate.exists():
            return str(candidate)
        for directory in [self._component_dir, self._builtin_component_dir]:
            candidate = directory / safe
            if candidate.exists():
                return str(candidate)
        return ""

    def _resolve_character_file(self, name: str) -> str:
        """解析立绘文件路径（从renwulihui文件夹的所有子文件夹中查找）"""
        if not name:
            return ""
        safe = Path(name).name
        try:
            if not self._char_dir.exists():
                return ""
            # 遍历所有情绪文件夹查找文件
            for emotion_dir in self._char_dir.iterdir():
                if not emotion_dir.is_dir():
                    continue
                candidate = emotion_dir / safe
                if candidate.exists():
                    return str(candidate)
        except Exception:
            pass
        return ""

    def _resolve_character_asset(self, asset: str | None, emotion: str) -> str:
        name = str(asset or "").strip()
        if name and name not in {"__auto__", "__random__"}:
            custom = self._resolve_character_file(name)
            if custom:
                self._last_character_path = custom
                return custom
        path = self._pick_character_path(emotion)
        return path

    def _preview_character(self) -> str:
        emotions = self._emotion_meta()
        if not emotions:
            return ""
        first_key = next(iter(emotions.keys()))
        return self._random_character_data(first_key)

    def _bot_name(self) -> str:
        try:
            layout = self._layout()
            name = layout.get("bot_name")
        except Exception:
            name = None
        name = str(name or "传话筒").strip()
        return name or "传话筒"

    def _image_type(self) -> str:
        t = str(self.cfg().get("image_type", "png")).lower()
        return "jpeg" if t == "jpeg" else "png"

    async def _render_with_fallback(self, text: str, emotion: str) -> Optional[str]:
        try:
            return await asyncio.to_thread(self._render_pillow_panel, text, emotion)
        except Exception as exc:
            logger.error("[传话筒] Pillow 合成失败: %s", exc)
            return None

    def _render_pillow_panel(self, text: str, emotion: str) -> Optional[str]:
        layout = self._layout()
        width = int(layout.get("canvas_width", 1280))
        height = int(layout.get("canvas_height", 720))
        bg_color = self._hex_or_rgba(layout.get("background_color", "#05060A"))
        canvas = Image.new("RGBA", (width, height), bg_color)

        bg_path = self._resolve_background_asset(layout.get("background_asset"))
        if bg_path:
            try:
                bg_img = Image.open(bg_path).convert("RGBA").resize((width, height), Image.LANCZOS)
                canvas.alpha_composite(bg_img)
            except Exception:
                logger.debug("[传话筒] 背景加载失败", exc_info=True)

        draw = ImageDraw.Draw(canvas)

        layers: list[tuple[int, dict[str, Any]]] = []
        char_path = self._resolve_character_asset(layout.get("character_asset"), emotion)
        if char_path:
            layers.append((int(layout.get("character_z_index", 150)), {"kind": "character", "path": char_path}))
        layers.append((int(layout.get("textbox_z_index", 200)), {"kind": "textbox", "text": text}))
        for overlay in layout.get("text_overlays", []):
            layers.append((int(overlay.get("z_index", 300)), {"kind": overlay.get("type", "text"), "overlay": overlay}))
        layers.sort(key=lambda item: item[0])

        for _, layer in layers:
            kind = layer.get("kind")
            if kind == "character":
                self._draw_character_layer(canvas, layer.get("path"), layout)
            elif kind == "textbox":
                self._draw_textbox_layer(canvas, draw, layout, layer.get("text", ""))
            elif kind == "text":
                self._draw_overlay_text(draw, layer.get("overlay"))
            elif kind == "glass":
                self._draw_glass_layer(canvas, layer.get("overlay"))
            elif kind == "image":
                self._draw_overlay_image(canvas, layer.get("overlay"))

        tmp = tempfile.NamedTemporaryFile(prefix="tranhua_", suffix=".png", delete=False)
        canvas.convert("RGB").save(tmp.name, format="PNG")
        return tmp.name

    def _draw_character_layer(self, canvas: Image.Image, path: Optional[str], layout: Dict[str, Any]):
        if not path:
            return
        try:
            img = Image.open(path).convert("RGBA")
            target_w = max(1, int(layout.get("character_width", 520)))
            ratio = target_w / max(1, img.width)
            target_h = max(1, int(img.height * ratio))
            img = img.resize((target_w, target_h), Image.LANCZOS)
            left = int(layout.get("character_left", 40))
            bottom = int(layout.get("character_bottom", 0))
            top = max(0, canvas.height - target_h - bottom)
            canvas.alpha_composite(img, (left, top))
        except Exception:
            logger.debug("[传话筒] 立绘渲染失败", exc_info=True)

    def _draw_textbox_layer(self, canvas: Image.Image, draw: ImageDraw.ImageDraw, layout: Dict[str, Any], text: str):
        box_left = int(layout.get("box_left", 520))
        box_top = int(layout.get("box_top", 160))
        box_width = max(20, int(layout.get("box_width", 640)))
        box_height = max(20, int(layout.get("box_height", 340)))
        padding = max(0, int(layout.get("padding", 28)))
        stroke_width = max(0, int(layout.get("text_stroke_width", 0)))
        stroke_color = self._hex_or_rgba(layout.get("text_stroke_color", "#000000"))

        font = self._load_font(layout.get("font_size", 30), preferred=layout.get("body_font"))
        text_area_w = max(10, box_width - padding * 2)
        wrapped = self._wrap_text(text, font, max(10, text_area_w))
        draw.multiline_text(
            (box_left + padding, box_top + padding),
            wrapped,
            font=font,
            fill=self._hex_or_rgba(layout.get("text_color", "#FFFFFF")),
            spacing=int(font.size * (layout.get("line_height", 1.6) - 1)),
            stroke_width=stroke_width,
            stroke_fill=stroke_color,
        )

    def _draw_overlay_text(self, draw: ImageDraw.ImageDraw, overlay: Optional[Dict[str, Any]]):
        if not overlay or not overlay.get("visible", True):
            return
        text_val = overlay.get("text", "")
        if not text_val:
            return
        left = int(overlay.get("left", 0))
        top = int(overlay.get("top", 0))
        width_o = max(10, int(overlay.get("width", 200)))
        font = self._load_font(overlay.get("font_size", 26), preferred=overlay.get("font"), bold=overlay.get("bold", True))
        text_tip = self._wrap_text(text_val, font, width_o)
        stroke_width = max(0, int(overlay.get("stroke_width", 0)))
        stroke_color = self._hex_or_rgba(overlay.get("stroke_color", "#000000"))
        draw.multiline_text(
            (left, top),
            text_tip,
            font=font,
            fill=self._hex_or_rgba(overlay.get("color", "#FFFFFF")),
            stroke_width=stroke_width,
            stroke_fill=stroke_color,
        )

    def _draw_glass_layer(self, canvas: Image.Image, overlay: Optional[Dict[str, Any]]):
        """绘制毛玻璃层：独立的毛玻璃效果图层"""
        if not overlay or not overlay.get("visible", True):
            return
        left = int(overlay.get("left", 0))
        top = int(overlay.get("top", 0))
        width_o = max(20, int(overlay.get("width", 200)))
        height_o = max(20, int(overlay.get("height", 60)))
        radius_raw = int(overlay.get("radius", 8))
        radius = max(0, min(radius_raw, min(width_o, height_o) // 2))
        blur_strength = max(2, int(overlay.get("glass_strength", 12)))
        opacity = float(overlay.get("opacity", 1.0))
        bg_color = self._parse_rgba(overlay.get("bg_color", "rgba(255,255,255,0.1)"))
        rect = (left, top, left + width_o, top + height_o)
        # 裁剪背景区域并应用模糊
        region = canvas.crop(rect)
        region = region.filter(ImageFilter.GaussianBlur(blur_strength))
        # 创建半透明覆盖层
        overlay_img = Image.new("RGBA", (width_o, height_o), bg_color)
        region = Image.alpha_composite(region, overlay_img)
        # 应用圆角遮罩
        mask = Image.new("L", (width_o, height_o), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle((0, 0, width_o, height_o), radius=radius, fill=255)
        if opacity < 1.0:
            alpha = region.split()[3].point(lambda a: int(a * max(0.0, min(1.0, opacity))))
            region.putalpha(alpha)
        canvas.paste(region, (left, top), mask)

    def _draw_overlay_image(self, canvas: Image.Image, overlay: Optional[Dict[str, Any]]):
        if not overlay or not overlay.get("visible", True):
            return
        image_name = overlay.get("image")
        path = self._resolve_component_path(image_name)
        if not path:
            return
        try:
            img = Image.open(path).convert("RGBA")
            width_o = int(overlay.get("width", img.width))
            height_o = int(overlay.get("height", img.height))
            if width_o > 0 and height_o > 0:
                img = img.resize((width_o, height_o), Image.LANCZOS)
            opacity = float(overlay.get("opacity", 1.0))
            if opacity < 1.0:
                alpha = img.split()[3].point(lambda a: int(a * max(0.0, min(1.0, opacity))))
                img.putalpha(alpha)
            left = int(overlay.get("left", 0))
            top = int(overlay.get("top", 0))
            canvas.alpha_composite(img, (left, top))
        except Exception:
            logger.debug("[传话筒] 自定义组件渲染失败", exc_info=True)

    def _load_font(self, size: int, preferred: Optional[str] = None, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        font_path = str(self.cfg().get("font_path") or "").strip()
        candidates: list[str] = []
        if preferred:
            resolved = self._resolve_font_path(preferred)
            if resolved:
                candidates.append(resolved)
        if font_path:
            resolved = self._resolve_font_path(font_path)
            if resolved:
                candidates.append(resolved)
        if os.name == "nt":
            candidates.extend([
                "C:/Windows/Fonts/msyh.ttc",
                "C:/Windows/Fonts/simhei.ttf",
            ])
        else:
            candidates.extend([
                "/System/Library/Fonts/PingFang.ttc",
                "/System/Library/Fonts/Hiragino Sans GB.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ])
        for path in candidates:
            if not path:
                continue
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _wrap_text(self, text: str, font: ImageFont.ImageFont, max_width: int) -> str:
        if not text:
            return ""
        draw = ImageDraw.Draw(Image.new("RGBA", (max_width, 10)))
        lines: list[str] = []
        for paragraph in text.splitlines():
            if not paragraph:
                lines.append("")
                continue
            current = ""
            for char in paragraph:
                test = current + char
                if draw.textlength(test, font=font) <= max_width:
                    current = test
                else:
                    lines.append(current)
                    current = char
            if current:
                lines.append(current)
        return "\n".join(lines)

    def _count_visible_chars(self, text: str) -> int:
        if not text:
            return 0
        return len(text.replace("\r", "").replace("\n", "").strip())

    def _parse_rgba(self, value: str) -> tuple[int, int, int, int]:
        value = (value or "").strip().lower()
        if value.startswith("rgba"):
            nums = value[value.find("(") + 1:value.find(")")].split(",")
            r, g, b = [int(float(nums[i])) for i in range(3)]
            a = float(nums[3]) if len(nums) > 3 else 1
            return (r, g, b, int(a * 255))
        return self._hex_or_rgba(value)

    def _hex_or_rgba(self, value: str) -> tuple[int, int, int, int]:
        value = (value or "#FFFFFF").strip()
        if value.startswith("#") and len(value) in {4, 7}:
            if len(value) == 4:
                value = "#" + "".join(ch * 2 for ch in value[1:])
            r = int(value[1:3], 16)
            g = int(value[3:5], 16)
            b = int(value[5:7], 16)
            return (r, g, b, 255)
        return (255, 255, 255, 255)

    def _chain_to_plain_text(self, chain: list[Any]) -> Optional[str]:
        if not chain:
            return None
        builder: list[str] = []
        for seg in chain:
            if PLAIN_COMPONENT_TYPES and isinstance(seg, PLAIN_COMPONENT_TYPES):
                builder.append(getattr(seg, "text", "") or "")
            elif LINEBREAK_COMPONENT and isinstance(seg, LINEBREAK_COMPONENT):
                builder.append("\n")
            elif hasattr(seg, "text") and seg.__class__.__name__.lower() in {"plain", "text"}:
                builder.append(getattr(seg, "text", "") or "")
            else:
                # 遇到图片/其他类型时放弃转换
                return None
        text = "".join(builder).strip()
        return text if text else None

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
                    web.get("/api/config", self._handle_get_layout),
                    web.post("/api/config", self._handle_update_layout),
                    web.post("/api/layout/reset", self._handle_reset_layout),
                    web.get("/api/preview-assets", self._handle_preview_assets),
                    web.post("/api/preview/generate", self._handle_generate_preview),
                    web.get("/api/components", self._handle_list_components_api),
                    web.post("/api/components/upload", self._handle_upload_component),
                    web.get("/api/components/raw/{name}", self._handle_component_file),
                    web.get("/api/backgrounds/raw/{name}", self._handle_background_file),
                    web.get("/api/characters/raw/{name}", self._handle_character_file),
                    web.get("/api/fonts/raw/{name}", self._handle_font_file),
                ]
            )
            self._web_app = app
            self._web_runner = web.AppRunner(app)
            await self._web_runner.setup()
            self._web_site = web.TCPSite(self._web_runner, host, port)
            await self._web_site.start()
            logger.info("[传话筒] WebUI 已启动: http://%s:%s", host, port)

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

    async def _handle_web_index(self, request: web.Request):
        await self._authorize(request)
        if not self.WEB_INDEX_PATH.exists():
            return web.Response(text="WebUI 索引缺失，请重新部署。", content_type="text/plain")
        return web.FileResponse(path=self.WEB_INDEX_PATH)

    async def _handle_get_layout(self, request: web.Request):
        await self._authorize(request)
        emotions = self._emotion_meta()
        layout = self._layout()
        payload = {
            "layout": layout,
            "components": self._list_components(),
            "characters": self._list_characters(),  # 添加立绘列表
            "fonts": self._list_fonts(),
            "backgrounds": self._list_backgrounds(),
            "bot_name": self._bot_name(),
            "emotion_sets": [
                {
                    "key": key,
                    "folder": meta.folder,
                    "label": meta.label,
                    "color": meta.color,
                    "enabled": meta.enabled,
                }
                for key, meta in emotions.items()
            ],
            "canvas": {
                "width": layout["canvas_width"],
                "height": layout["canvas_height"],
            },
        }
        return web.json_response(payload)

    async def _handle_preview_assets(self, request: web.Request):
        await self._authorize(request)
        preview = {
            "background": self._random_background_data(),
            "character": self._preview_character(),
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
            os.unlink(image_path)  # 清理临时文件
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
        return web.json_response({"ok": True, "layout": state})

    async def _handle_list_components_api(self, request: web.Request):
        await self._authorize(request)
        return web.json_response({"components": self._list_components(), "fonts": self._list_fonts()})

    async def _handle_upload_component(self, request: web.Request):
        await self._authorize(request)
        try:
            payload = await request.json()
        except Exception:
            raise web.HTTPBadRequest(text="invalid json")
        filename = str(payload.get("filename") or "").strip()
        data = payload.get("data")
        kind = str(payload.get("kind") or "component").lower()
        if not filename or not data:
            raise web.HTTPBadRequest(text="filename/data required")
        if kind == "font":
            allowed = (".ttf", ".ttc", ".otf")
            target_dir = self._font_dir
        else:
            allowed = (".png", ".webp", ".gif")
            target_dir = self._component_dir
        if not filename.lower().endswith(allowed):
            raise web.HTTPBadRequest(text=f"only {'/'.join(allowed)} allowed")
        try:
            content = base64.b64decode(data.split(",")[-1])
            safe_name = Path(filename).name
            target = target_dir / safe_name
            with open(target, "wb") as fp:
                fp.write(content)
        except Exception as exc:
            raise web.HTTPBadRequest(text=f"upload failed: {exc}")
        return web.json_response({
            "ok": True,
            "components": self._list_components(),
            "fonts": self._list_fonts(),
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

    @filter.on_llm_request()
    async def inject_emotion_prompt(self, event: AstrMessageEvent, req: ProviderRequest):
        if not self._cfg_bool("enable_emotion_prompt", False):
            return
        emotions = self._emotion_meta()
        tags = [f"&{tag}&" for tag in emotions.keys()]
        template = str(self.cfg().get("emotion_prompt_template", self.DEFAULT_PROMPT_TEMPLATE))
        instruction = template.replace("{tags}", ", ".join(tags))
        req.system_prompt = (req.system_prompt or "") + "\n" + instruction

    @filter.on_llm_response()
    async def handle_llm_response(self, event: AstrMessageEvent, resp: LLMResponse):
        if not self._cfg_bool("enable_render", True):
            return
        text = self._extract_llm_text(resp)
        if not text:
            return
        emotion, cleaned_text = self._emotion_from_text(text)
        if not cleaned_text:
            return
        char_limit = int(self.cfg().get("render_char_threshold", 60) or 0)
        if char_limit > 0:
            text_len = self._count_visible_chars(cleaned_text)
            if text_len > char_limit:
                logger.debug("[传话筒] 文本长度 %s 超过阈值 %s，跳过渲染。", text_len, char_limit)
                event.set_result(event.plain_result(cleaned_text))
                return
        image_path = await self._render_with_fallback(cleaned_text, emotion)
        if not image_path:
            logger.warning("[传话筒] 渲染失败，退回纯文本。")
            event.set_result(event.plain_result(cleaned_text))
            return
        try:
            event.set_result(event.image_result(image_path))
            event.stop_event()
        except Exception as exc:
            logger.error(f"[传话筒] 设置图片结果失败: {exc}")

    def _ensure_prompt_template(self):
        if not isinstance(self._cfg_obj, dict):
            return
        template = self._cfg_obj.get("emotion_prompt_template")
        if template:
            return
        self._cfg_obj["emotion_prompt_template"] = self.DEFAULT_PROMPT_TEMPLATE
        saver = getattr(self._cfg_obj, "save_config", None)
        if callable(saver):
            try:
                saver()
            except Exception as exc:
                logger.debug("[传话筒] 写入默认情绪提示失败: %s", exc)

    def _extract_llm_text(self, resp: LLMResponse) -> str:
        for attr in ("text", "output_text", "content"):
            value = getattr(resp, attr, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
        result_chain = getattr(resp, "result_chain", None)
        if result_chain and getattr(result_chain, "chain", None):
            text = self._chain_to_plain_text(result_chain.chain)
            if text:
                return text
        return ""
