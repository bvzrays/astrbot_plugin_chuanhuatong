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
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

import astrbot.api.message_components as Comp
from aiohttp import web
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import LLMResponse, ProviderRequest
from astrbot.api.star import Context, Star, register, StarTools
from PIL import Image, ImageDraw, ImageFilter, ImageFont

try:
    from pilmoji import Pilmoji
    from pilmoji.source import Twemoji
except Exception:
    Pilmoji = None
    Twemoji = None

PLAIN_COMPONENT_TYPES = tuple(
    getattr(Comp, name)
    for name in ("Plain", "Text")
    if hasattr(Comp, name)
)
LINEBREAK_COMPONENT = getattr(Comp, "LineBreak", None)

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


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
    "2.0.0",
    "https://github.com/bvzrays/astrbot_plugin_chuanhuatong",
)
class ChuanHuaTongPlugin(Star):
    """传话筒——拦截所有文本回复并渲染立绘对话框。"""

    EMOTION_PATTERN = re.compile(r"&([a-zA-Z0-9_]+)&")
    ROLE_AUTO = "__auto__"
    ROLE_BUILTIN = "__builtin__"
    ROLE_LEGACY = "__legacy__"
    PLUGIN_ID = "astrbot_plugin_chuanhuatong"

    DEFAULT_EMOTIONS: list[dict[str, Any]] = [
        {"key": "neutral", "folder": "shy", "label": "平静", "color": "#A9C5FF", "enabled": True},
        {"key": "happy", "folder": "happy", "label": "开心", "color": "#FFC857", "enabled": True},
        {"key": "sad", "folder": "sad", "label": "低落", "color": "#7DA1FF", "enabled": True},
        {"key": "shy", "folder": "shy", "label": "害羞", "color": "#F9C5D1", "enabled": True},
        {"key": "surprise", "folder": "surprise", "label": "惊讶", "color": "#F5E960", "enabled": True},
        {"key": "angry", "folder": "angry", "label": "生气", "color": "#FF8A8A", "enabled": True},
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
        "character_fit_mode": "fixed_width",
        "character_uniform_height": 620,
        "character_align_bottom": True,
        "character_top": 0,
        "character_role": "__auto__",
        "character_shadow": "drop-shadow(0 12px 36px rgba(0,0,0,0.6))",
        "background_group": "__auto__",
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

        self._data_dir = self._resolve_data_dir()
        self._component_dir = self._data_dir / "zujian"
        self._component_dir.mkdir(parents=True, exist_ok=True)
        self._font_dir = self._data_dir / "fonts"
        self._font_dir.mkdir(parents=True, exist_ok=True)
        self._user_char_dir = self._data_dir / "characters"
        self._user_char_dir.mkdir(parents=True, exist_ok=True)
        self._user_bg_dir = self._data_dir / "backgrounds"
        self._user_bg_dir.mkdir(parents=True, exist_ok=True)
        self._presets_dir = self._data_dir / "presets"
        self._presets_dir.mkdir(parents=True, exist_ok=True)
        self._current_preset_file = self._data_dir / "current_preset.json"
        self._current_preset_meta: dict[str, Any] = self._load_current_preset_meta()
        self._layout_file = self._data_dir / "layout_state.json"
        self._emotion_file = self._data_dir / "emotion_sets.json"
        self._layout_lock = asyncio.Lock()
        self._layout_state = self._load_layout_state()
        self._web_runner: Optional[web.AppRunner] = None
        self._web_site: Optional[web.TCPSite] = None
        self._web_app: Optional[web.Application] = None
        self._web_lock = asyncio.Lock()
        self._render_semaphore = asyncio.Semaphore(3)
        self._cached_emotions: Dict[str, EmotionMeta] = {}
        self._emotion_records: list[dict[str, Any]] = []
        self._ensure_prompt_template()
        self._last_background_path: str = ""
        self._last_character_path: str = ""
        self._cleanup_tasks: set[asyncio.Task] = set()

        logger.info("[传话筒] 数据目录：%s", self._data_dir)
        logger.info("[传话筒] 布局文件：%s", self._layout_file)
        logger.info("[传话筒] 情绪配置：%s", self._emotion_file)

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
                normalized = self._normalize_layout(data)
                logger.info("[传话筒] 已载入自定义布局（包含 %s 个覆盖字段）", len(data.keys()))
                return normalized
            except Exception:
                logger.warning("[传话筒] 无法读取自定义布局，使用默认布局。")
        legacy = self.cfg().get("text_layout") or {}
        state = self._normalize_layout(self._convert_legacy_layout(legacy))
        self._save_layout_state(state)
        logger.info("[传话筒] 使用默认布局并写入到 %s", self._layout_file)
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
        logger.info("[传话筒] 布局已重置为默认值")
        return state

    def _set_layout_state(self, layout: Dict[str, Any]):
        normalized = self._normalize_layout(layout)
        self._layout_state = normalized
        self._save_layout_state(normalized)
        logger.info("[传话筒] 布局已更新并持久化，文本层数：%s", len(normalized.get("text_overlays", [])))

    def _sanitize_preset_name(self, name: str) -> str:
        name = str(name or "").strip()
        return re.sub(r"\s+", " ", name)

    def _sanitize_folder_name(self, name: str, default: str = "custom") -> str:
        name = str(name or "").strip()
        if not name:
            return default
        slug = re.sub(r"[^0-9a-zA-Z_-]+", "_", name).strip("_")
        if not slug:
            return default
        return slug[:50]

    def _sanitize_role_name(self, name: str, default: str = "role") -> str:
        return self._sanitize_folder_name(name, default)

    @staticmethod
    def _dir_has_image(directory: Path) -> bool:
        try:
            for f in directory.iterdir():
                if f.is_file() and f.suffix.lower() in {".png", ".webp"}:
                    return True
        except Exception:
            return False
        return False

    def _discover_user_roles(self) -> dict[str, dict[str, Any]]:
        roles: dict[str, dict[str, Any]] = {}
        if not self._user_char_dir.exists():
            return roles
        legacy_emotions: set[str] = set()
        try:
            for entry in self._user_char_dir.iterdir():
                if entry.is_dir():
                    sub_emotions: set[str] = set()
                    has_images = False
                    for child in entry.iterdir():
                        if child.is_dir():
                            if self._dir_has_image(child):
                                sub_emotions.add(child.name)
                        elif child.is_file() and child.suffix.lower() in {".png", ".webp"}:
                            has_images = True
                    if sub_emotions:
                        roles[entry.name] = {"label": entry.name, "emotions": sub_emotions}
                        continue
                    if has_images:
                        legacy_emotions.add(entry.name)
                elif entry.is_file() and entry.suffix.lower() in {".png", ".webp"}:
                    legacy_emotions.add("default")
        except Exception:
            logger.debug("[传话筒] 枚举用户立绘角色失败", exc_info=True)
        if legacy_emotions:
            roles[self.ROLE_LEGACY] = {"label": "旧版上传", "emotions": legacy_emotions, "source": "legacy"}
        return roles

    def _list_character_roles(self) -> list[dict[str, Any]]:
        roles: list[dict[str, Any]] = []
        builtin_emotions: set[str] = set()
        try:
            if self._char_dir.exists():
                for emotion_dir in self._char_dir.iterdir():
                    if emotion_dir.is_dir() and self._dir_has_image(emotion_dir):
                        builtin_emotions.add(emotion_dir.name)
        except Exception:
            pass
        if builtin_emotions:
            roles.append({
                "id": self.ROLE_BUILTIN,
                "label": "内置立绘",
                "source": "builtin",
                "emotions": sorted(builtin_emotions),
            })
        user_roles = self._discover_user_roles()
        for role_id, meta in user_roles.items():
            roles.append({
                "id": role_id,
                "label": meta.get("label", role_id),
                "source": meta.get("source", "user"),
                "emotions": sorted(meta.get("emotions", [])),
            })
        return roles

    def _resolve_data_dir(self) -> Path:
        """优先使用 StarTools 数据目录，失败时退回到 AstrBot/data/plugin_data 下。"""
        fallback_dir = self._base_dir.parent.parent / "plugin_data" / self.PLUGIN_ID
        try:
            preferred_raw = StarTools.get_data_dir(self.PLUGIN_ID)
        except Exception:
            preferred_raw = None
        if preferred_raw:
            preferred_path = Path(preferred_raw)
            try:
                preferred_path.mkdir(parents=True, exist_ok=True)
                return preferred_path
            except Exception as exc:
                logger.warning("[传话筒] 创建数据目录失败(%s)，退回 fallback：%s", exc, fallback_dir)
        fallback_dir.mkdir(parents=True, exist_ok=True)
        return fallback_dir

    def _preset_slug(self, name: str) -> str:
        base = re.sub(r"[^0-9a-zA-Z_-]+", "-", name.strip().lower())
        base = base.strip("-_")[:60]
        return base or uuid4().hex

    def _preset_file(self, slug: str) -> Path:
        safe = re.sub(r"[^0-9a-zA-Z_-]+", "-", slug.strip().lower()) or uuid4().hex
        return self._presets_dir / f"{safe}.json"

    def _read_preset_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return None
            if not isinstance(data.get("layout"), dict):
                return None
            data.setdefault("name", file_path.stem)
            data.setdefault("slug", file_path.stem)
            data["_path"] = file_path
            return data
        except Exception:
            logger.warning("[传话筒] 读取预设文件失败: %s", file_path)
            return None

    def _list_presets(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        try:
            for file_path in sorted(self._presets_dir.glob("*.json")):
                record = self._read_preset_file(file_path)
                if not record:
                    continue
                records.append({
                    "name": record.get("name"),
                    "slug": record.get("slug"),
                    "saved_at": record.get("saved_at"),
                })
        except Exception as exc:
            logger.debug("[传话筒] 列出预设失败: %s", exc)
        return records

    def _find_preset(self, identifier: str) -> Optional[Dict[str, Any]]:
        key = str(identifier or "").strip().lower()
        if not key:
            return None
        # 先尝试直接匹配文件名
        direct = self._preset_file(key)
        if direct.exists():
            record = self._read_preset_file(direct)
            if record:
                return record
        for file_path in self._presets_dir.glob("*.json"):
            record = self._read_preset_file(file_path)
            if not record:
                continue
            slug = str(record.get("slug") or "").lower()
            name = str(record.get("name") or "").lower()
            if key in {slug, name}:
                return record
        return None

    def _save_preset(self, name: str, layout: Dict[str, Any]) -> dict[str, Any]:
        cleaned_name = self._sanitize_preset_name(name)
        normalized = self._normalize_layout(layout)
        existing = self._find_preset(cleaned_name)
        slug = (existing or {}).get("slug") or self._preset_slug(cleaned_name or uuid4().hex)
        path = self._preset_file(slug)
        payload = {
            "name": cleaned_name or slug,
            "slug": slug,
            "saved_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "layout": normalized,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def _load_preset(self, identifier: str) -> Optional[Dict[str, Any]]:
        record = self._find_preset(identifier)
        if not record:
            return None
        layout = self._normalize_layout(record.get("layout") or {})
        return {
            "name": record.get("name"),
            "slug": record.get("slug"),
            "saved_at": record.get("saved_at"),
            "layout": layout,
        }

    def _load_current_preset_meta(self) -> dict[str, Any]:
        if not self._current_preset_file.exists():
            return {}
        try:
            return json.loads(self._current_preset_file.read_text(encoding="utf-8"))
        except Exception:
            logger.debug("[传话筒] 读取当前预设记录失败", exc_info=True)
            return {}

    def _remember_current_preset(self, record: Optional[dict[str, Any]]):
        if not record:
            self._current_preset_meta = {}
            try:
                if self._current_preset_file.exists():
                    self._current_preset_file.unlink()
            except Exception:
                logger.debug("[传话筒] 清理当前预设记录失败", exc_info=True)
            return
        payload = {
            "name": record.get("name"),
            "slug": record.get("slug"),
            "saved_at": record.get("saved_at"),
        }
        self._current_preset_meta = payload
        try:
            self._current_preset_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            logger.debug("[传话筒] 写入当前预设记录失败", exc_info=True)

    def _current_preset_name(self) -> str:
        return str(self._current_preset_meta.get("name") or "")

    def _format_preset_list_message(self) -> str:
        presets = self._list_presets()
        current_name = self._current_preset_name()
        current_slug = str(self._current_preset_meta.get("slug") or "")
        lines: list[str] = []
        if current_name:
            lines.append(f"当前预设：{current_name}")
        else:
            lines.append("当前预设：自定义布局（未绑定预设）")
        if not presets:
            lines.append("暂未保存任何预设。")
            return "\n".join(lines)
        lines.append("可用预设：")
        for idx, info in enumerate(presets, start=1):
            name = info.get("name") or info.get("slug") or f"未命名-{idx}"
            saved = info.get("saved_at") or "未知时间"
            marker = ""
            if current_name and (info.get("name") == current_name):
                marker = " <- 当前"
            elif current_slug and (info.get("slug") == current_slug):
                marker = " <- 当前"
            lines.append(f"{idx}. {name}（保存于 {saved}）{marker}")
        lines.append("使用 /切换预设 预设名称 即可切换。")
        return "\n".join(lines)

    @staticmethod
    def _is_event_admin(event: AstrMessageEvent) -> bool:
        checker = getattr(event, "is_admin", None)
        if callable(checker):
            try:
                return bool(checker())
            except Exception:
                logger.debug("[传话筒] 检查管理员权限失败", exc_info=True)
        role = getattr(event, "role", None)
        return str(role).lower() == "admin"

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
        """列出所有立绘文件（内置 + 用户自定义）"""
        entries: set[str] = set()
        try:
            if self._char_dir.exists():
                for emotion_dir in self._char_dir.iterdir():
                    if not emotion_dir.is_dir():
                        continue
                    for f in emotion_dir.iterdir():
                        if f.is_file() and f.suffix.lower() in {".png", ".webp"}:
                            entries.add(f.name)
        except Exception:
            pass
        try:
            if self._user_char_dir.exists():
                for folder in self._user_char_dir.iterdir():
                    if folder.is_file():
                        if folder.suffix.lower() in {".png", ".webp"}:
                            entries.add(f"user::custom::{folder.name}")
                        continue
                    if not folder.is_dir():
                        continue
                    subdirs = [d for d in folder.iterdir() if d.is_dir()]
                    if subdirs:
                        for emo_dir in subdirs:
                            if not emo_dir.is_dir():
                                continue
                            for f in emo_dir.iterdir():
                                if f.is_file() and f.suffix.lower() in {".png", ".webp"}:
                                    entries.add(f"user::{folder.name}::{emo_dir.name}::{f.name}")
                        continue
                    for f in folder.iterdir():
                        if f.is_file() and f.suffix.lower() in {".png", ".webp"}:
                            entries.add(f"user::{self.ROLE_LEGACY}::{folder.name}::{f.name}")
                # 处理直接位于根目录的文件
                for f in self._user_char_dir.iterdir():
                    if f.is_file() and f.suffix.lower() in {".png", ".webp"}:
                        entries.add(f"user::{self.ROLE_LEGACY}::default::{f.name}")
        except Exception:
            pass
        return sorted(entries)

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

    def _count_images_in_dir(self, directory: Path) -> int:
        try:
            return sum(1 for f in directory.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_SUFFIXES)
        except Exception:
            return 0

    def _list_background_groups(self) -> list[dict[str, Any]]:
        groups: list[dict[str, Any]] = []
        builtin_count = self._count_images_in_dir(self._bg_dir)
        if builtin_count:
            groups.append({"id": "builtin", "label": "内置背景", "count": builtin_count})
        try:
            for folder in sorted(self._user_bg_dir.iterdir()):
                if not folder.is_dir():
                    continue
                count = self._count_images_in_dir(folder)
                if count:
                    groups.append({
                        "id": f"user::{folder.name}",
                        "label": folder.name,
                        "count": count,
                    })
        except Exception:
            logger.debug("[传话筒] 列出背景分组失败", exc_info=True)
        return groups

    def _list_backgrounds(self) -> list[str]:
        entries: list[str] = []
        try:
            for f in self._bg_dir.iterdir():
                if f.is_file() and f.suffix.lower() in IMAGE_SUFFIXES:
                    entries.append(f"builtin::{f.name}")
        except Exception:
            pass
        try:
            for folder in self._user_bg_dir.iterdir():
                if not folder.is_dir():
                    continue
                for f in folder.iterdir():
                    if f.is_file() and f.suffix.lower() in IMAGE_SUFFIXES:
                        entries.append(f"user::{folder.name}::{f.name}")
        except Exception:
            logger.debug("[传话筒] 列出背景资源失败", exc_info=True)
        return sorted(entries)

    def _pick_background_path(self, group: Optional[str] = None) -> str:
        target = (group or "__auto__").strip()
        if target and target not in {"__auto__", "__random__"}:
            if target == "builtin":
                path = self._pick_random_asset(self._bg_dir, IMAGE_SUFFIXES)
                if path:
                    return path
            elif target.startswith("user::"):
                slug = self._sanitize_folder_name(target.split("::", 1)[1] if "::" in target else target, "default")
                directory = self._user_bg_dir / slug
                if directory.exists():
                    path = self._pick_random_asset(directory, IMAGE_SUFFIXES)
                    if path:
                        return path
        user_dirs: list[Path] = []
        try:
            for folder in self._user_bg_dir.iterdir():
                if folder.is_dir() and self._count_images_in_dir(folder):
                    user_dirs.append(folder)
        except Exception:
            pass
        if user_dirs:
            directory = random.choice(user_dirs)
            path = self._pick_random_asset(directory, IMAGE_SUFFIXES)
            if path:
                return path
        return self._pick_random_asset(self._bg_dir, IMAGE_SUFFIXES)

    def _read_emotion_file(self) -> Optional[list[dict[str, Any]]]:
        if not self._emotion_file.exists():
            return None
        try:
            data = json.loads(self._emotion_file.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else None
        except Exception:
            logger.debug("[传话筒] 读取情绪配置失败，使用默认配置。", exc_info=True)
            return None

    def _write_emotion_file(self, records: list[dict[str, Any]]):
        try:
            self._emotion_file.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.error("[传话筒] 写入情绪配置失败: %s", exc)

    def _normalize_emotion_records(self, records: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        source = records or []
        for item in source:
            if not isinstance(item, dict):
                continue
            raw_key = str(item.get("key") or "").strip()
            key = re.sub(r"[^0-9a-zA-Z_]+", "_", raw_key).lower()
            if not key or key in seen:
                continue
            seen.add(key)
            folder = self._sanitize_folder_name(str(item.get("folder") or key), key or "neutral")
            label = str(item.get("label") or raw_key or key).strip() or key
            color = str(item.get("color") or "#FFFFFF").strip() or "#FFFFFF"
            enabled = bool(item.get("enabled", True))
            normalized.append({
                "key": key,
                "folder": folder,
                "label": label,
                "color": color,
                "enabled": enabled,
            })
        if not normalized:
            normalized = copy.deepcopy(self.DEFAULT_EMOTIONS)
        if not any(entry.get("enabled") for entry in normalized):
            normalized[0]["enabled"] = True
        return normalized

    def _persist_emotion_sets(self, records: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        normalized = self._normalize_emotion_records(records)
        self._write_emotion_file(normalized)
        logger.info(
            "[传话筒] 情绪配置已写入，共 %s 个标签（启用 %s 个）",
            len(normalized),
            sum(1 for item in normalized if item.get("enabled")),
        )
        return normalized

    def _load_emotion_sets(self) -> Dict[str, EmotionMeta]:
        records = self._read_emotion_file()
        if records is None:
            src = self.cfg().get("emotion_sets")
            if isinstance(src, list) and src:
                records = src
                logger.info("[传话筒] 从配置加载 %s 个情绪标签", len(records))
            else:
                records = copy.deepcopy(self.DEFAULT_EMOTIONS)
                logger.info("[传话筒] 使用内置默认情绪标签")
        records = self._persist_emotion_sets(records)
        self._emotion_records = records
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

    def _emotion_payload(self) -> list[dict[str, Any]]:
        if not self._emotion_records:
            self._emotion_meta()
        return copy.deepcopy(self._emotion_records)

    def _remove_emotion_tags(self, text: str) -> str:
        """移除文本中的情绪标签（&xxx&格式），参考 meme_manager_lite 的实现"""
        if not text:
            return text
        # 使用正则表达式替换所有 &xxx& 标签
        cleaned = self.EMOTION_PATTERN.sub("", text)
        # 清理标签移除后可能留下的多余空格（但保留换行符）
        # 将多个连续空格替换为单个空格，但保留换行符
        cleaned = re.sub(r"[ \t]+", " ", cleaned)  # 只替换空格和制表符，不替换换行
        # 清理行首行尾的空格（但保留换行符结构）
        lines = cleaned.split("\n")
        cleaned_lines = [line.strip() for line in lines]
        while cleaned_lines and not cleaned_lines[0]:
            cleaned_lines.pop(0)
        while cleaned_lines and not cleaned_lines[-1]:
            cleaned_lines.pop()
        cleaned = "\n".join(cleaned_lines)
        return cleaned

    def _emotion_from_text(self, text: str) -> Tuple[str, str]:
        """从文本中提取情绪标签并返回清理后的文本"""
        mapping = self._emotion_meta()
        matches = self.EMOTION_PATTERN.findall(text)
        selected: Optional[str] = None
        if matches:
            for raw in matches:
                key = raw.lower()
                if selected is None and key in mapping:
                    selected = key
        # 清理标签
        cleaned = self._remove_emotion_tags(text)
        default_key = str(self.cfg().get("default_emotion", "")).lower()
        if not default_key or default_key not in mapping:
            default_key = next(iter(mapping.keys()))
        return (selected or default_key), cleaned

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

    def _random_background_data(self, group: Optional[str] = None) -> str:
        path = self._pick_background_path(group)
        self._last_background_path = path or ""
        return self._path_to_data_url(path)

    def _random_character_data(self, emotion_key: str, role: Optional[str] = None) -> str:
        path = self._pick_character_path(emotion_key, role)
        return self._path_to_data_url(path)

    def _pick_character_path(self, emotion_key: str, role: Optional[str] = None) -> str:
        role = (role or "").strip() or self.ROLE_AUTO
        if role in {self.ROLE_AUTO, "__random__"}:
            path = self._pick_auto_character(emotion_key)
            self._last_character_path = path or ""
            return path or ""
        if role == self.ROLE_BUILTIN:
            path = self._pick_builtin_character(emotion_key)
            if path:
                self._last_character_path = path
                return path
            return self._pick_auto_character(emotion_key)
        if role == self.ROLE_LEGACY:
            path = self._pick_user_role_character(self.ROLE_LEGACY, emotion_key)
            if path:
                return path
            return self._pick_auto_character(emotion_key)
        path = self._pick_user_role_character(role, emotion_key)
        if path:
            return path
        return self._pick_auto_character(emotion_key)

    def _pick_auto_character(self, emotion_key: str) -> str:
        user_roles = self._discover_user_roles()
        for role_id in user_roles.keys():
            if role_id == self.ROLE_LEGACY:
                continue
            path = self._pick_user_role_character(role_id, emotion_key)
            if path:
                return path
        legacy_path = self._pick_user_role_character(self.ROLE_LEGACY, emotion_key)
        if legacy_path:
            return legacy_path
        return self._pick_builtin_character(emotion_key)

    def _pick_user_role_character(self, role: str, emotion_key: str) -> str:
        if not self._user_char_dir.exists():
            return ""
        mapping = self._emotion_meta()
        meta = mapping.get(emotion_key)
        if not meta and mapping:
            meta = next(iter(mapping.values()))
        preferred_folder = meta.folder if meta else ""
        if role == self.ROLE_LEGACY:
            if preferred_folder:
                legacy_dir = self._user_char_dir / preferred_folder
                if legacy_dir.exists():
                    path = self._pick_random_asset(legacy_dir, {".png", ".webp"})
                    if path:
                        self._last_character_path = path
                        return path
            path = self._pick_random_asset(self._user_char_dir, {".png", ".webp"})
            if path:
                self._last_character_path = path
            return path or ""
        role_dir = self._user_char_dir / role
        if not role_dir.exists():
            return ""
        candidate_dirs: list[Path] = []
        if preferred_folder:
            candidate_dirs.append(role_dir / preferred_folder)
        try:
            for sub in role_dir.iterdir():
                if sub.is_dir() and sub.name != preferred_folder:
                    candidate_dirs.append(sub)
        except Exception:
            pass
        for directory in candidate_dirs:
            if directory.exists():
                path = self._pick_random_asset(directory, {".png", ".webp"})
                if path:
                    self._last_character_path = path
                    return path
        path = self._pick_random_asset(role_dir, {".png", ".webp"})
        if path:
            self._last_character_path = path
        return path or ""

    def _pick_builtin_character(self, emotion_key: str) -> str:
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

    def _resolve_background_asset(self, asset: str | None, group: Optional[str] = None) -> str:
        name = str(asset or "").strip()
        if name and name not in {"__auto__", "__random__"}:
            path = self._resolve_background_file(name)
            if path:
                self._last_background_path = path
                return path
        path = self._pick_background_path(group)
        self._last_background_path = path or ""
        return path or ""

    def _resolve_background_file(self, name: str) -> str:
        if not name:
            return ""
        if name.startswith("user::"):
            parts = name.split("::", 2)
            if len(parts) >= 3:
                group = self._sanitize_folder_name(parts[1], "default")
                filename = Path(parts[2]).name
                target = self._user_bg_dir / group / filename
                if target.exists():
                    return str(target)
        elif name.startswith("builtin::"):
            safe = Path(name.split("::", 1)[1]).name
            candidate = self._bg_dir / safe
            if candidate.exists():
                return str(candidate)
        safe = Path(name).name
        candidate = self._bg_dir / safe
        if candidate.exists():
            return str(candidate)
        for directory in [self._component_dir, self._builtin_component_dir]:
            candidate = directory / safe
            if candidate.exists():
                return str(candidate)
        candidate = self._user_bg_dir / safe
        if candidate.exists():
            return str(candidate)
        return ""

    def _resolve_character_file(self, name: str) -> str:
        """解析立绘文件路径（支持内置与用户上传）"""
        if not name:
            return ""
        marker = "user::"
        if name.startswith(marker):
            trimmed = name[len(marker):].strip()
            parts = [p for p in trimmed.split("::") if p is not None]
            role = self.ROLE_LEGACY
            emotion = "default"
            filename = ""
            if len(parts) == 1:
                filename = parts[0]
            elif len(parts) == 2:
                emotion, filename = parts
            elif len(parts) >= 3:
                role, emotion, filename = parts[0], parts[1], parts[2]
            role_slug = self._sanitize_role_name(role or self.ROLE_LEGACY, self.ROLE_LEGACY)
            emotion_slug = self._sanitize_folder_name(emotion or "default", "default")
            filename = Path(filename or "").name
            if role_slug == self.ROLE_LEGACY:
                legacy_target = self._user_char_dir / emotion_slug / filename
                if legacy_target.exists():
                    return str(legacy_target)
                legacy_flat = self._user_char_dir / filename
                if legacy_flat.exists():
                    return str(legacy_flat)
            else:
                target = self._user_char_dir / role_slug / emotion_slug / filename
                if target.exists():
                    return str(target)
            return ""
        safe = Path(name).name
        try:
            if self._char_dir.exists():
                for emotion_dir in self._char_dir.iterdir():
                    if not emotion_dir.is_dir():
                        continue
                    candidate = emotion_dir / safe
                    if candidate.exists():
                        return str(candidate)
        except Exception:
            pass
        user_candidate = self._user_char_dir / safe
        if user_candidate.exists():
            return str(user_candidate)
        return ""

    def _resolve_character_asset(self, asset: str | None, emotion: str, role: Optional[str]) -> str:
        name = str(asset or "").strip()
        if name and name not in {"__auto__", "__random__"}:
            custom = self._resolve_character_file(name)
            if custom:
                self._last_character_path = custom
                return custom
        path = self._pick_character_path(emotion, role)
        return path

    def _preview_character(self, role: Optional[str] = None) -> str:
        emotions = self._emotion_meta()
        if not emotions:
            return ""
        first_key = next(iter(emotions.keys()))
        return self._random_character_data(first_key, role)

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

    def _cleanup_temp_file(self, path: Optional[str]):
        if not path:
            return
        try:
            os.remove(path)
        except FileNotFoundError:
            return
        except Exception as exc:
            logger.debug("[传话筒] 删除临时文件失败: %s", exc)

    async def _delayed_cleanup(self, path: str, delay: float = 30.0):
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return
        self._cleanup_temp_file(path)

    def _schedule_cleanup(self, path: Optional[str], delay: float = 30.0):
        if not path:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self._cleanup_temp_file(path)
            return
        task = loop.create_task(self._delayed_cleanup(path, delay))
        self._cleanup_tasks.add(task)

        def _remove(_):
            self._cleanup_tasks.discard(task)

        task.add_done_callback(_remove)

    def _render_pillow_panel(self, text: str, emotion: str) -> Optional[str]:
        layout = self._layout()
        width = int(layout.get("canvas_width", 1280))
        height = int(layout.get("canvas_height", 720))
        bg_color = self._hex_or_rgba(layout.get("background_color", "#05060A"))
        canvas = Image.new("RGBA", (width, height), bg_color)

        bg_path = self._resolve_background_asset(
            layout.get("background_asset"),
            layout.get("background_group"),
        )
        if bg_path:
            try:
                bg_img = Image.open(bg_path).convert("RGBA").resize((width, height), Image.LANCZOS)
                canvas.alpha_composite(bg_img)
            except Exception:
                logger.debug("[传话筒] 背景加载失败", exc_info=True)

        draw = ImageDraw.Draw(canvas)

        layers: list[tuple[int, dict[str, Any]]] = []
        char_path = self._resolve_character_asset(
            layout.get("character_asset"),
            emotion,
            layout.get("character_role"),
        )
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
                self._draw_textbox_layer(canvas, layout, layer.get("text", ""))
            elif kind == "text":
                self._draw_overlay_text(canvas, layer.get("overlay"))
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
            fit_mode = str(layout.get("character_fit_mode", "fixed_width"))
            if fit_mode == "uniform_height":
                target_h = max(1, int(layout.get("character_uniform_height", img.height)))
                ratio = target_h / max(1, img.height)
                target_w = max(1, int(img.width * ratio))
            else:
                target_w = max(1, int(layout.get("character_width", 520)))
                ratio = target_w / max(1, img.width)
                target_h = max(1, int(img.height * ratio))
            img = img.resize((target_w, target_h), Image.LANCZOS)
            left = int(layout.get("character_left", 40))
            if layout.get("character_align_bottom", True):
                bottom = int(layout.get("character_bottom", 0))
                top = max(0, canvas.height - target_h - bottom)
            else:
                top = max(0, int(layout.get("character_top", 0)))
            canvas.alpha_composite(img, (left, top))
        except Exception:
            logger.debug("[传话筒] 立绘渲染失败", exc_info=True)

    def _draw_rich_text(
        self,
        canvas: Image.Image,
        position: tuple[int, int],
        text: str,
        font: ImageFont.ImageFont,
        fill: tuple[int, int, int, int],
        stroke_width: int = 0,
        stroke_fill: tuple[int, int, int, int] = (0, 0, 0, 255),
        spacing: int = 0,
    ):
        if not text:
            return
        if Pilmoji and Twemoji:
            try:
                with Pilmoji(canvas, source=Twemoji) as pilmoji:
                    pilmoji.text(
                        position,
                        text,
                        font=font,
                        fill=fill,
                        stroke_width=stroke_width,
                        stroke_fill=stroke_fill,
                        spacing=spacing,
                    )
                    return
            except Exception:
                logger.debug("[传话筒] Pilmoji 渲染失败，回退到 Pillow。", exc_info=True)
        draw = ImageDraw.Draw(canvas)
        draw.multiline_text(
            position,
            text,
            font=font,
            fill=fill,
            spacing=spacing,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )

    def _draw_textbox_layer(self, canvas: Image.Image, layout: Dict[str, Any], text: str):
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
        spacing = max(0, int(font.size * (float(layout.get("line_height", 1.6)) - 1)))
        self._draw_rich_text(
            canvas,
            (box_left + padding, box_top + padding),
            wrapped,
            font,
            self._hex_or_rgba(layout.get("text_color", "#FFFFFF")),
            stroke_width=stroke_width,
            stroke_fill=stroke_color,
            spacing=spacing,
        )

    def _draw_overlay_text(self, canvas: Image.Image, overlay: Optional[Dict[str, Any]]):
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
        self._draw_rich_text(
            canvas,
            (left, top),
            text_tip,
            font,
            self._hex_or_rgba(overlay.get("color", "#FFFFFF")),
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
            logger.info("[传话筒] WebUI 被禁用，跳过启动。")
            return
        async with self._web_lock:
            if self._web_runner:
                return
            # 默认使用 0.0.0.0 以支持 Docker/远程访问，用户可在配置中改为 127.0.0.1 限制本地访问
            default_host = "0.0.0.0"
            host = str(self.cfg().get("webui_host", default_host))
            port = int(self.cfg().get("webui_port", 18765))
            app = web.Application()
            app.add_routes(
                [
                    web.get("/", self._handle_web_index),
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
                ]
            )
            self._web_app = app
            self._web_runner = web.AppRunner(app)
            await self._web_runner.setup()
            self._web_site = web.TCPSite(self._web_runner, host, port)
            await self._web_site.start()
            token = self._get_token()
            access_url = f"http://{host}:{port}"
            if token:
                access_url += f"?token={token}"
            logger.info("[传话筒] WebUI 已启动: %s", access_url)
            if host == "0.0.0.0":
                logger.info("[传话筒] 监听所有网络接口，可通过服务器 IP 地址访问（如: http://<服务器IP>:%s）", port)
                logger.info("[传话筒] 如需限制为仅本地访问，请在配置中将 webui_host 设置为 127.0.0.1")
            elif host == "127.0.0.1":
                logger.info("[传话筒] 仅监听本地回环接口，无法从外部访问")
                logger.info("[传话筒] 如需允许远程访问（Docker/云服务器），请在配置中将 webui_host 设置为 0.0.0.0")
            if token:
                logger.info("[传话筒] 已启用 Token 验证，访问时需携带 token 参数或 Authorization 头")
            else:
                logger.warning("[传话筒] 未设置 webui_token，WebUI 可在无验证的情况下访问，公网环境建议设置 token")

    async def initialize(self):
        await self._ensure_webui()
        self._emotion_meta()
        logger.info("[传话筒] 插件初始化完成，已准备情绪与布局。")

    async def terminate(self):
        async with self._web_lock:
            if self._web_site:
                await self._web_site.stop()
                self._web_site = None
            if self._web_runner:
                await self._web_runner.cleanup()
                self._web_runner = None
            self._web_app = None
        logger.info("[传话筒] 插件已终止，WebUI 关闭。")

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
        emotion_payload = self._emotion_payload()
        layout = self._layout()
        payload = {
            "layout": layout,
            "components": self._list_components(),
            "characters": self._list_characters(),  # 添加立绘列表
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
        # 重置时清除当前预设记录，恢复到默认布局
        self._remember_current_preset(None)
        # 刷新缓存
        self._cached_emotions.clear()
        self._emotion_meta()  # 重新加载情绪配置
        return web.json_response({"ok": True, "layout": state})

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
        # 刷新缓存，确保立绘正确显示
        self._cached_emotions.clear()
        self._emotion_meta()  # 重新加载情绪配置
        return web.json_response({
            "ok": True,
            "preset": {k: record.get(k) for k in ("name", "slug", "saved_at")},
            "layout": record["layout"],
            "presets": self._list_presets(),
            "character_roles": self._list_character_roles(),  # 刷新角色列表
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
        # 刷新缓存，确保立绘正确显示
        self._cached_emotions.clear()
        self._emotion_meta()  # 重新加载情绪配置
        return web.json_response({
            "ok": True,
            "preset": {k: record.get(k) for k in ("name", "slug", "saved_at")},
            "layout": record["layout"],
            "presets": self._list_presets(),
            "character_roles": self._list_character_roles(),  # 刷新角色列表
        })

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
        normalized = self._persist_emotion_sets(copy.deepcopy(self.DEFAULT_EMOTIONS))
        self._emotion_records = normalized
        self._cached_emotions.clear()
        logger.info("[传话筒] WebUI 请求恢复默认情绪配置")
        return web.json_response({
            "ok": True,
            "emotion_sets": self._emotion_payload(),
        })

    if hasattr(filter, "on_message"):

        @filter.on_message(priority=-10)  # 降低优先级，确保在其他插件之后处理
        async def handle_message_events(
            self,
            event: AstrMessageEvent,
            req: Optional[ProviderRequest] = None,
        ):
            await self._handle_preset_command(event, req)

    @filter.on_llm_request(priority=-10)  # 降低优先级，确保在其他插件之后处理
    async def inject_emotion_prompt(self, event: AstrMessageEvent, req: ProviderRequest):
        handled = await self._handle_preset_command(event, req)
        if handled:
            return
        if not self._cfg_bool("enable_emotion_prompt", False):
            return
        emotions = self._emotion_meta()
        tags = [f"&{tag}&" for tag in emotions.keys()]
        template = str(self.cfg().get("emotion_prompt_template", self.DEFAULT_PROMPT_TEMPLATE))
        instruction = template.replace("{tags}", ", ".join(tags))
        req.system_prompt = (req.system_prompt or "") + "\n" + instruction

    async def _update_conversation_history(self, event: AstrMessageEvent, cleaned_text: str):
        """更新对话历史，移除表情标签"""
        try:
            umo = event.unified_msg_origin
            conv_mgr = self.context.conversation_manager
            curr_cid = await conv_mgr.get_curr_conversation_id(umo)
            if not curr_cid:
                return
            conversation = await conv_mgr.get_conversation(umo, curr_cid, create_if_not_exists=False)
            if not conversation or not conversation.history:
                return
            try:
                history = json.loads(conversation.history) if isinstance(conversation.history, str) else conversation.history
                if not isinstance(history, list) or not history:
                    return
                # 更新最后一条助手消息，移除表情标签
                last_msg = history[-1]
                if isinstance(last_msg, dict) and last_msg.get("role") == "assistant":
                    original_content = last_msg.get("content", "")
                    # 如果内容不同，更新历史
                    if original_content != cleaned_text:
                        last_msg["content"] = cleaned_text
                        await conv_mgr.update_conversation(umo, curr_cid, history=history)
                        logger.debug("[传话筒] 已更新对话历史，移除表情标签")
            except Exception as e:
                logger.debug("[传话筒] 更新对话历史失败: %s", e)
        except Exception as e:
            logger.debug("[传话筒] 清理对话历史中的表情标签失败: %s", e)

    @filter.on_llm_response(priority=-10)  # 降低优先级，确保在其他插件之后处理
    async def handle_llm_response(self, event: AstrMessageEvent, resp: LLMResponse):
        """保存响应对象，供 on_decorating_result 使用"""
        if not self._cfg_bool("enable_render", True):
            return
        # 保存响应对象，供后续钩子使用
        event.set_extra("llm_resp", resp)

    @filter.on_decorating_result(priority=-10)  # 降低优先级，确保在其他插件之后处理
    async def on_decorating_result(self, event: AstrMessageEvent):
        """在装饰结果时清理表情标签，参考 meme_manager_lite 的实现"""
        if not self._cfg_bool("enable_render", True):
            return
        
        render_scope = str(self.cfg().get("render_scope", "llm_only")).lower()
        allow_non_llm = render_scope == "all_text"

        # 获取保存的响应对象
        resp = event.get_extra("llm_resp")
        resp_obj = resp if isinstance(resp, LLMResponse) else None
        if resp_obj is None and not allow_non_llm:
            return
        if resp_obj:
            # 清理响应文本中的表情标签（参考 meme_manager_lite）
            if hasattr(resp_obj, "completion_text") and resp_obj.completion_text:
                resp_obj.completion_text = self._remove_emotion_tags(resp_obj.completion_text)
            elif hasattr(resp_obj, "text") and resp_obj.text:
                resp_obj.text = self._remove_emotion_tags(resp_obj.text)
            elif hasattr(resp_obj, "content") and resp_obj.content:
                resp_obj.content = self._remove_emotion_tags(resp_obj.content)
        
        # 获取当前结果并清理消息链中的文本
        result = event.get_result()
        if not result:
            return
        chain = result.chain
        if not chain:
            return
        
        # 提取完整文本用于判断和渲染
        raw_text_parts = []
        new_chain = []
        has_non_text = False
        
        for item in chain:
            if isinstance(item, PLAIN_COMPONENT_TYPES):
                original_text = getattr(item, "text", "") or ""
                raw_text_parts.append(original_text)
                cleaned_text = self._remove_emotion_tags(original_text)
                if cleaned_text:
                    new_item = type(item)(cleaned_text)
                    new_chain.append(new_item)
            else:
                has_non_text = True
                new_chain.append(item)
        
        # 更新消息链
        result.chain = new_chain
        
        # 如果只有文本组件，尝试渲染
        if not has_non_text and raw_text_parts:
            raw_full_text = "".join(raw_text_parts)
            emotion, cleaned_full_text = self._emotion_from_text(raw_full_text)
            full_text = cleaned_full_text.strip()
            if full_text:
                logger.debug("[传话筒] 触发渲染，情绪=%s，长度=%s", emotion, len(full_text))
                if resp_obj is not None:
                    await self._update_conversation_history(event, full_text)
                
                # 检查字符限制
                char_limit = int(self.cfg().get("render_char_threshold", 60) or 0)
                if char_limit > 0:
                    text_len = self._count_visible_chars(full_text)
                    if text_len > char_limit:
                        logger.info("[传话筒] 文本长度 %s 超过阈值 %s，跳过渲染。", text_len, char_limit)
                        return
                
                # 尝试渲染
                image_path = await self._render_with_fallback(full_text, emotion)
                if image_path:
                    try:
                        result.chain = [Comp.Image.fromFileSystem(image_path)]
                        self._schedule_cleanup(image_path, delay=90.0)
                    except Exception as exc:
                        logger.error(f"[传话筒] 设置图片结果失败: {exc}")
                else:
                    logger.warning("[传话筒] 渲染失败，退回纯文本。")

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

    def _extract_user_plaintext(self, event: AstrMessageEvent, req: Optional[ProviderRequest]) -> str:
        candidates: list[str] = []
        for attr in ("plain_text", "text", "message", "content"):
            val = getattr(event, attr, None)
            if isinstance(val, str):
                candidates.append(val)
        chain = getattr(event, "message_chain", None)
        if isinstance(chain, list):
            parsed = self._chain_to_plain_text(chain)
            if parsed:
                candidates.append(parsed)
        if req:
            for attr in ("input_text", "user_input", "query", "prompt", "text"):
                val = getattr(req, attr, None)
                if isinstance(val, str):
                    candidates.append(val)
        for text in candidates:
            if text and text.strip():
                return text.strip()
        return ""

    def _switch_preset(self, target: str) -> tuple[bool, str, Optional[str]]:
        normalized = str(target or "").strip()
        if not normalized:
            return False, self._format_preset_list_message(), None
        record = self._load_preset(normalized)
        if not record:
            return False, f"未找到名为「{normalized}」的预设。\n\n{self._format_preset_list_message()}", None
        self._set_layout_state(record["layout"])
        self._remember_current_preset(record)
        # 刷新缓存，确保立绘正确显示
        self._cached_emotions.clear()
        self._emotion_meta()  # 重新加载情绪配置
        return True, f"已切换到预设「{record['name']}」。", record.get("name") or normalized

    async def _handle_preset_command(
        self,
        event: AstrMessageEvent,
        req: Optional[ProviderRequest],
    ) -> bool:
        """处理预设切换命令（用于事件钩子，不用于 @filter.command）"""
        if hasattr(event, "is_stopped") and event.is_stopped():
            return False
        # 检查是否是指令消息（通过 message_str 判断，框架会自动处理命令符）
        text = event.message_str or ""
        stripped = text.strip()
        # 移除可能的命令符前缀（框架可能已经处理，但为了兼容性保留）
        if stripped and stripped[0] in {"/", "*", "／", "＊"}:
            stripped = stripped[1:].lstrip()
        if not stripped.startswith("切换预设"):
            return False
        target = stripped[len("切换预设"):].strip()
        if not self._is_event_admin(event):
            denial = "只有管理员可以切换预设。"
            event.set_result(event.plain_result(denial))
            event.stop_event()
            return True
        success, message, preset_name = self._switch_preset(target)
        event.set_result(event.plain_result(message))
        event.stop_event()
        if success:
            logger.info("[传话筒] 通过指令切换预设: %s", preset_name)
        return True

    @filter.command("切换预设")
    async def command_switch_preset(self, event: AstrMessageEvent, *preset_tokens: str):
        if not self._is_event_admin(event):
            yield event.plain_result("只有管理员可以切换预设。")
            event.stop_event()
            return
        target = " ".join(preset_tokens).strip()
        success, message, preset_name = self._switch_preset(target)
        yield event.plain_result(message)
        event.stop_event()
        if success:
            logger.info("[传话筒] 通过命令切换预设: %s", preset_name)

    @filter.command("预设列表")
    async def command_list_presets(self, event: AstrMessageEvent):
        message = self._format_preset_list_message()
        yield event.plain_result(message)
        event.stop_event()
