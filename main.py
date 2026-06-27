"""传话筒——将 Bot 的文字回复渲染为 Gal 风立绘对话框。

模块化重构：核心逻辑分散到 mixin_*.py 和 models.py，main.py 仅保留
初始化、事件钩子、命令和插件注册。
"""

import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Ensure the plugin directory is on sys.path so absolute imports work
# both under AstrBot's import_module() and standard Python.
_PLUGIN_DIR = Path(os.path.abspath(__file__)).parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

# 静态路径（类属性，供 WebUIMixin 使用）
WEB_INDEX_PATH = _PLUGIN_DIR / "webui" / "index.html"
WEBUI_DIR = _PLUGIN_DIR / "webui"

import yaml
from aiohttp import web
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import LLMResponse, ProviderRequest
from astrbot.api.star import Context, Star, register

from models import EmotionMeta, DEFAULT_LAYOUT, DEFAULT_PROMPT_TEMPLATE
from mixin_config import ConfigMixin
from mixin_emotions import EmotionMixin
from mixin_text import TextMixin
from mixin_assets import AssetMixin
from mixin_render import RenderMixin
from mixin_layout import LayoutMixin
from mixin_webui import WebUIMixin

# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

_META_PATH = Path(__file__).with_name("metadata.yaml")
try:
    with open(_META_PATH, "r", encoding="utf-8") as f:
        _META = yaml.safe_load(f) or {}
except Exception:
    _META = {}

_PLUGIN_ID = _META.get("name", "astrbot_plugin_chuanhuatong")
_PLUGIN_AUTHOR = _META.get("author", "bvzrays")
_PLUGIN_DESC = _META.get("desc", "传话筒：将 Bot 的文字回复渲染为 Gal 风立绘对话框")
_PLUGIN_VERSION = str(_META.get("version", "2.4.5")).lstrip("vV")
_PLUGIN_REPO = _META.get("repo", "https://github.com/bvzrays/astrbot_plugin_chuanhuatong")


# ---------------------------------------------------------------------------
# Plugin class
# ---------------------------------------------------------------------------

@register(
    _PLUGIN_ID,
    _PLUGIN_AUTHOR,
    _PLUGIN_DESC,
    _PLUGIN_VERSION,
    _PLUGIN_REPO,
)
class ChuanHuaTongPlugin(
    ConfigMixin,
    EmotionMixin,
    TextMixin,
    AssetMixin,
    RenderMixin,
    LayoutMixin,
    WebUIMixin,
    Star,
):
    """传话筒——拦截所有文本回复并渲染立绘对话框。"""

    PLUGIN_ID = _PLUGIN_ID

    EMOTION_PATTERN = re.compile(r"&([a-zA-Z0-9_]+)&")
    ROLE_AUTO = "__auto__"
    ROLE_BUILTIN = "__builtin__"
    ROLE_LEGACY = "__legacy__"

    WEB_INDEX_PATH = (Path(__file__).resolve().parent / "webui" / "index.html")
    WEBUI_DIR = (Path(__file__).resolve().parent / "webui")

    DEFAULT_EMOTIONS = [
        {"key": "neutral", "folder": "shy", "label": "平静", "color": "#A9C5FF", "enabled": True},
        {"key": "happy", "folder": "happy", "label": "开心", "color": "#FFC857", "enabled": True},
        {"key": "sad", "folder": "sad", "label": "低落", "color": "#7DA1FF", "enabled": True},
        {"key": "shy", "folder": "shy", "label": "害羞", "color": "#F9C5D1", "enabled": True},
        {"key": "surprise", "folder": "surprise", "label": "惊讶", "color": "#F5E960", "enabled": True},
        {"key": "angry", "folder": "sad", "label": "生气", "color": "#FF8A8A", "enabled": True},
    ]

    DEFAULT_PROMPT_TEMPLATE = DEFAULT_PROMPT_TEMPLATE
    DEFAULT_LAYOUT = DEFAULT_LAYOUT

    # ========================================================================
    # Initialization
    # ========================================================================

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
        self._session_layouts_dir = self._data_dir / "session_layouts"
        self._session_layouts_dir.mkdir(parents=True, exist_ok=True)
        self._emotion_file = self._data_dir / "emotion_sets.json"
        self._layout_lock = asyncio.Lock()
        self._layout_state = self._load_layout_state()

        # 指令强制状态（内存，不持久化，优先级最高）
        self._force_enabled_sessions: set[str] = set()
        self._force_disabled_sessions: set[str] = set()

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

    # ========================================================================
    # Prompt template init helper
    # ========================================================================

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

    # ========================================================================
    # Extract LLM / user text helpers
    # ========================================================================

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

    # ========================================================================
    # Preset switching
    # ========================================================================

    def _switch_preset(self, target: str, session_id: Optional[str] = None) -> tuple[bool, str, Optional[str]]:
        normalized = str(target or "").strip()
        if not normalized:
            return False, self._format_preset_list_message(), None
        record = self._load_preset(normalized)
        if not record:
            return False, f"未找到名为「{normalized}」的预设。\n\n{self._format_preset_list_message()}", None

        if session_id:
            preset_name = record.get("name") or normalized
            self._save_session_layout(session_id, record["layout"], preset_name)
            self._cached_emotions.clear()
            self._emotion_meta()
            logger.info("[传话筒] 切换到预设: %s (会话: %s)", preset_name, session_id)
            return True, f"已切换到预设「{preset_name}」（仅当前会话）。", preset_name

        self._set_layout_state(record["layout"])
        self._remember_current_preset(record)
        self._cached_emotions.clear()
        self._emotion_meta()
        logger.info("[传话筒] 切换到预设: %s (全局)", record.get("name") or normalized)
        return True, f"已切换到预设「{record['name']}」（全局）。", record.get("name") or normalized

    # ========================================================================
    # Core event handlers
    # ========================================================================

    if hasattr(filter, "on_message"):

        @filter.on_message(priority=-10)
        async def handle_message_events(
            self,
            event: AstrMessageEvent,
            req: Optional[ProviderRequest] = None,
        ):
            await self._handle_preset_command(event, req)

    @filter.on_llm_request(priority=-10)
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

    # ========================================================================
    # Preset command handling (used by event hooks and @filter.command)
    # ========================================================================

    async def _handle_preset_command(
        self,
        event: AstrMessageEvent,
        req: Optional[ProviderRequest],
    ) -> bool:
        if hasattr(event, "is_stopped") and event.is_stopped():
            return False
        text = event.message_str or ""
        stripped = text.strip()
        if stripped and stripped[0] in {"/", "*", "／", "＊"}:
            stripped = stripped[1:].lstrip()
        if not stripped.startswith("切换预设"):
            return False
        target = stripped[len("切换预设"):].strip()
        if not self._check_control_permission(event):
            denial = "你没有权限使用此指令。"
            event.set_result(event.plain_result(denial))
            event.stop_event()
            return True
        session_id = event.unified_msg_origin
        success, message, preset_name = self._switch_preset(target, session_id)
        event.set_result(event.plain_result(message))
        event.stop_event()
        if success:
            logger.info("[传话筒] 通过指令切换预设: %s", preset_name)
        return True

    @filter.command("切换预设")
    async def command_switch_preset(self, event: AstrMessageEvent, *preset_tokens: str):
        if not self._check_control_permission(event):
            yield event.plain_result("你没有权限使用此指令。")
            event.stop_event()
            return
        target = " ".join(preset_tokens).strip()
        if not target:
            yield event.plain_result("请提供预设名称。使用 /预设列表 查看所有可用预设。")
            event.stop_event()
            return
        session_id = event.unified_msg_origin
        success, message, preset_name = self._switch_preset(target, session_id)
        yield event.plain_result(message)
        event.stop_event()
        if success:
            logger.info("[传话筒] 通过命令切换预设: %s (会话: %s)", preset_name, session_id)

    @filter.command("预设列表")
    async def command_list_presets(self, event: AstrMessageEvent):
        message = self._format_preset_list_message()
        yield event.plain_result(message)
        event.stop_event()

    # ========================================================================
    # Conversation history cleanup
    # ========================================================================

    async def _update_conversation_history(self, event: AstrMessageEvent, cleaned_text: str):
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
                last_msg = history[-1]
                if isinstance(last_msg, dict) and last_msg.get("role") == "assistant":
                    original_content = last_msg.get("content", "")
                    if original_content != cleaned_text:
                        last_msg["content"] = cleaned_text
                        await conv_mgr.update_conversation(umo, curr_cid, history=history)
                        logger.debug("[传话筒] 已更新对话历史，移除表情标签")
            except Exception as e:
                logger.debug("[传话筒] 更新对话历史失败: %s", e)
        except Exception as e:
            logger.debug("[传话筒] 清理对话历史中的表情标签失败: %s", e)

    # ========================================================================
    # LLM response & decorating hooks
    # ========================================================================

    @filter.on_llm_response(priority=100000)
    async def get_emotion_tag(self, event: AstrMessageEvent, resp: LLMResponse):
        if not self._cfg_bool("enable_render", True):
            return

        emotion_tag = None
        raw_text = ""

        for attr in ("text", "output_text", "content", "completion_text"):
            if hasattr(resp, attr):
                value = getattr(resp, attr)
                if isinstance(value, str) and value.strip():
                    raw_text = value
                    break

        if raw_text:
            emotion_tag, cleaned_text = self._emotion_from_text(raw_text)
            for attr in ("text", "output_text", "content", "completion_text"):
                if hasattr(resp, attr):
                    setattr(resp, attr, cleaned_text)

        event.set_extra("llm_resp", resp)
        if emotion_tag:
            event.set_extra("extracted_emotion_tag", emotion_tag)

    def _debug_enabled(self) -> bool:
        return self._cfg_bool("debug", False)

    def _debug_log(self, msg: str, *args):
        if self._debug_enabled():
            logger.info(msg, *args)

    @filter.on_decorating_result(priority=-10)
    async def on_decorating_result(self, event: AstrMessageEvent):
        import astrbot.api.message_components as Comp
        PLAIN_COMPONENT_TYPES = tuple(
            getattr(Comp, name)
            for name in ("Plain", "Text", "LineBreak")
            if hasattr(Comp, name)
        )

        session_id = event.unified_msg_origin
        persona_id = await self._resolve_current_persona_id(event, None)
        self._debug_log("[传话筒][DIAG] ========== on_decorating_result 触发 ==========")
        self._debug_log("[传话筒][DIAG] 会话: %s, 人格: %s", session_id, persona_id)

        result = event.get_result()
        if not result:
            self._debug_log("[传话筒][DIAG] 步骤1: 未获取到结果对象 → 直接返回")
            return
        chain = result.chain
        if not chain:
            self._debug_log("[传话筒][DIAG] 步骤2: 消息链为空 → 直接返回")
            return

        self._debug_log("[传话筒][DIAG] 步骤3: 消息链长度: %s", len(chain))

        plain_text = self._chain_to_plain_text(chain)
        has_non_text = plain_text is None
        raw_text_parts = [plain_text] if plain_text else []

        self._debug_log("[传话筒][DIAG] 步骤4: 消息链分析 → has_non_text=%s, raw_text_parts=%s", has_non_text, len(raw_text_parts))
        if plain_text:
            self._debug_log("[传话筒][DIAG] 步骤4详情: 提取的纯文本长度=%s, 内容预览='%s'", len(plain_text), plain_text[:100])

        resp = event.get_extra("llm_resp")
        resp_obj = resp if isinstance(resp, LLMResponse) else None

        if not self._cfg_bool("enable_render", True):
            self._debug_log("[传话筒][DIAG] 步骤5: enable_render=false → 直接返回")
            return
        self._debug_log("[传话筒][DIAG] 步骤5: enable_render=true → 通过")

        if not self._is_session_enabled(event):
            self._debug_log("[传话筒][DIAG] 步骤6: 会话未启用（黑白名单）→ 直接返回")
            return
        self._debug_log("[传话筒][DIAG] 步骤6: 会话已启用 → 通过")

        render_scope = str(self.cfg().get("render_scope", "llm_only")).lower()
        allow_non_llm = render_scope == "all_text"
        self._debug_log("[传话筒][DIAG] 步骤7: render_scope=%s, allow_non_llm=%s", render_scope, allow_non_llm)

        if resp_obj is None and not allow_non_llm:
            self._debug_log("[传话筒][DIAG] 步骤8: 无LLM响应且不允许非LLM → 直接返回")
            return
        self._debug_log("[传话筒][DIAG] 步骤8: LLM响应检查通过 (resp_obj=%s)", resp_obj is not None)

        if not has_non_text and raw_text_parts:
            self._debug_log("[传话筒][DIAG] 步骤9: 进入纯文本渲染分支")
            raw_full_text = "".join(raw_text_parts)
            emotion = event.get_extra("extracted_emotion_tag")
            full_text = raw_full_text.strip()
            self._debug_log("[传话筒][DIAG] 步骤9详情: 原始长度=%s, 清洗后长度=%s, 情绪=%s", len(raw_full_text), len(full_text), emotion)
            if full_text:
                if resp_obj is not None:
                    await self._update_conversation_history(event, full_text)

                char_limit = int(self.cfg().get("render_char_threshold", 60) or 0)
                enable_split = self._cfg_bool("split_long_text", False)
                split_page_limit = int(self.cfg().get("split_page_char_limit", 200) or 0)
                if split_page_limit <= 0:
                    split_page_limit = 200
                self._debug_log("[传话筒][DIAG] 步骤10: render_char_threshold=%s, split_long_text=%s, split_page_char_limit=%s", char_limit, enable_split, split_page_limit)

                if enable_split:
                    text_len = self._count_visible_chars(full_text)
                    self._debug_log("[传话筒][DIAG] 步骤11: 可见字符数=%s, split_page_char_limit=%s, 是否超限=%s", text_len, split_page_limit, text_len > split_page_limit)
                    if text_len > split_page_limit:
                        self._debug_log("[传话筒][DIAG] 步骤12: 触发分割渲染 → 调用 _render_split_text")
                        success = await self._render_split_text(full_text, emotion, event, session_id, persona_id)
                        if success:
                            result.chain = []
                            self._debug_log("[传话筒][DIAG] 步骤13: 分割渲染成功 → 返回")
                            return
                        self._debug_log("[传话筒][DIAG] 步骤13: 分割渲染失败 → 返回")
                        return
                    else:
                        self._debug_log("[传话筒][DIAG] 步骤12: 文本未超 split_page_char_limit → 进入单图渲染")
                elif char_limit > 0:
                    text_len = self._count_visible_chars(full_text)
                    self._debug_log("[传话筒][DIAG] 步骤11: 可见字符数=%s, 阈值=%s, 是否超限=%s", text_len, char_limit, text_len > char_limit)
                    if text_len > char_limit:
                        self._debug_log("[传话筒][DIAG] 步骤12: split_long_text=false → 跳过渲染，直接返回")
                        return

                self._debug_log("[传话筒][DIAG] 步骤12: 未触发分割 → 进入单图渲染")
                image_path = await self._render_with_fallback(full_text, emotion, session_id, persona_id)
                if image_path:
                    try:
                        result.chain = [Comp.Image.fromFileSystem(image_path)]
                        self._schedule_cleanup(image_path, delay=90.0)
                        self._debug_log("[传话筒][DIAG] 步骤13: 单图渲染成功")
                    except Exception as exc:
                        logger.error("[传话筒][DIAG] 步骤13: 单图渲染异常: %s", exc, exc_info=True)
                else:
                    self._debug_log("[传话筒][DIAG] 步骤13: 单图渲染失败（无image_path）")
            else:
                self._debug_log("[传话筒][DIAG] 步骤9: full_text 为空 → 跳过渲染")
        else:
            self._debug_log("[传话筒][DIAG] 步骤9: has_non_text=%s 或 raw_text_parts为空 → 跳过渲染分支", has_non_text)

        self._debug_log("[传话筒][DIAG] ========== on_decorating_result 结束 ==========")

    # ========================================================================
    # Control commands
    # ========================================================================

    @filter.command("传话筒开启")
    async def command_chuanhuatong_enable(self, event: AstrMessageEvent):
        if not self._check_control_permission(event):
            yield event.plain_result("你没有权限使用此指令。")
            event.stop_event()
            return
        success, message = self._enable_session(event)
        yield event.plain_result(message)
        event.stop_event()

    @filter.command("传话筒关闭")
    async def command_chuanhuatong_disable(self, event: AstrMessageEvent):
        if not self._check_control_permission(event):
            yield event.plain_result("你没有权限使用此指令。")
            event.stop_event()
            return
        success, message = self._disable_session(event)
        yield event.plain_result(message)
        event.stop_event()

    @filter.command("传话筒状态")
    async def command_chuanhuatong_status(self, event: AstrMessageEvent):
        if not self._check_control_permission(event):
            yield event.plain_result("你没有权限使用此指令。")
            event.stop_event()
            return
        is_enabled = self._is_session_enabled(event)
        whitelist_mode = self._cfg_bool("whitelist_mode", False)
        mode_text = "白名单模式" if whitelist_mode else "黑名单模式"
        status_text = "已启用" if is_enabled else "已禁用"
        session_id = event.unified_msg_origin
        has_custom = self._has_session_layout(session_id)
        if has_custom:
            session_layout = self._load_session_layout(session_id)
            preset_name = session_layout.get("_preset_name") if session_layout else None
            if preset_name:
                current_preset = f"{preset_name}（会话独立配置）"
            else:
                current_preset = "自定义布局（会话独立配置）"
        else:
            current_preset = self._current_preset_name() or "自定义布局（全局配置）"
        persona_id = await self._resolve_current_persona_id(event, None)
        config_type = "会话独立配置" if has_custom else "全局配置"
        persona_binding = "未绑定"
        if persona_id:
            binding_record = self._load_persona_preset_bindings().get(self._normalize_persona_binding_id(persona_id))
            if binding_record:
                persona_binding = str(binding_record.get("name") or binding_record.get("slug") or "未命名预设")
        message = f"传话筒状态：{status_text}\n模式：{mode_text}\n配置类型：{config_type}\n当前预设：{current_preset}\n当前人格预设绑定：{persona_binding}"
        yield event.plain_result(message)
        event.stop_event()