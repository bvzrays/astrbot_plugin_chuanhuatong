"""Rendering pipeline mixin for 传话筒 plugin.

Pillow-based rendering: canvas, character, textbox, overlays, merging.
"""

import asyncio
import os
import re
import tempfile
import unicodedata
from pathlib import Path
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from astrbot.core.message.message_event_result import MessageChain
import astrbot.api.message_components as Comp
from PIL import Image, ImageDraw, ImageFont

from mixin_config import IMAGE_SUFFIXES


class RenderMixin:
    """Mixin providing the Pillow rendering pipeline."""

    # ------------------------------------------------------------------
    # Render entry points
    # ------------------------------------------------------------------

    async def _render_with_fallback(
        self,
        text: str,
        emotion: str,
        session_id: Optional[str] = None,
        persona_id: Optional[str] = None,
    ) -> Optional[str]:
        try:
            return await asyncio.to_thread(self._render_pillow_panel, text, emotion, session_id, persona_id)
        except Exception as exc:
            logger.error("[传话筒] Pillow 渲染异常: %s", exc, exc_info=True)
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

    # ------------------------------------------------------------------
    # Pillow panel rendering
    # ------------------------------------------------------------------

    def _render_pillow_panel(
        self,
        text: str,
        emotion: str,
        session_id: Optional[str] = None,
        persona_id: Optional[str] = None,
    ) -> Optional[str]:
        layout = self._layout(session_id, persona_id)
        width = int(layout.get("canvas_width", 1280))
        height = int(layout.get("canvas_height", 720))
        bg_color = self._hex_or_rgba(layout.get("background_color", "#05060A"))
        canvas = Image.new("RGBA", (width, height), bg_color)

        bg_group = layout.get("background_group")
        bg_path = self._resolve_background_asset(layout.get("background_asset"), bg_group)
        if bg_path:
            try:
                bg_img = Image.open(bg_path).convert("RGBA").resize((width, height), Image.LANCZOS)
                canvas.alpha_composite(bg_img)
            except Exception:
                logger.debug("[传话筒] 背景加载失败", exc_info=True)

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

        # Save as JPEG with compression
        tmp = tempfile.NamedTemporaryFile(prefix="tranhua_", suffix=".jpeg", delete=False)
        quality = int(self.cfg().get("image_quality", 85) or 85)
        quality = max(1, min(100, quality))
        canvas.convert("RGB").save(tmp.name, format="JPEG", quality=quality, optimize=False)

        return tmp.name

    # ------------------------------------------------------------------
    # Layer drawing
    # ------------------------------------------------------------------

    def _draw_character_layer(self, canvas: Image.Image, path: Optional[str], layout: Dict[str, Any]):
        if not path:
            return
        try:
            img = Image.open(path).convert("RGBA")
            fit_mode = str(layout.get("character_fit_mode", "fixed_width")).lower()
            align_bottom = layout.get("character_align_bottom", True)

            if fit_mode == "uniform_height":
                target_h = max(1, int(layout.get("character_uniform_height", 620)))
                ratio = target_h / max(1, img.height)
                target_w = max(1, int(img.width * ratio))
            else:
                target_w = max(1, int(layout.get("character_width", 520)))
                ratio = target_w / max(1, img.width)
                target_h = max(1, int(img.height * ratio))

            img = img.resize((target_w, target_h), Image.LANCZOS)

            anchor = layout.get("character_anchor", "left-top")
            left_raw = int(layout.get("character_left", 40))

            if align_bottom:
                bottom_raw = int(layout.get("character_bottom", 0))
                if anchor == "center":
                    final_x = canvas.width // 2 + left_raw
                    final_y = canvas.height // 2 - target_h // 2 - bottom_raw
                elif anchor == "right-bottom":
                    final_x = canvas.width - target_w + left_raw
                    final_y = canvas.height - target_h - bottom_raw
                else:
                    final_x = canvas.width + left_raw if left_raw < 0 else left_raw
                    if bottom_raw >= 0:
                        final_y = canvas.height - target_h - bottom_raw
                    else:
                        final_y = canvas.height - target_h + abs(bottom_raw)
            else:
                top_raw = int(layout.get("character_top", 0))
                if anchor == "center":
                    final_x = canvas.width // 2 + left_raw
                    final_y = canvas.height // 2 - target_h // 2 + top_raw
                elif anchor == "right-bottom":
                    final_x = canvas.width - target_w + left_raw
                    final_y = canvas.height - target_h + top_raw
                else:
                    final_x = canvas.width + left_raw if left_raw < 0 else left_raw
                    if top_raw >= 0:
                        final_y = top_raw
                    else:
                        final_y = top_raw

            canvas.alpha_composite(img, (final_x, final_y))
        except Exception:
            logger.debug("[传话筒] 立绘渲染失败", exc_info=True)

    def _draw_textbox_layer(self, canvas: Image.Image, layout: Dict[str, Any], text: str):
        anchor = layout.get("box_anchor", "left-top")
        box_left = int(layout.get("box_left", 520))
        box_top = int(layout.get("box_top", 160))
        box_width = max(20, int(layout.get("box_width", 640)))
        box_height = max(20, int(layout.get("box_height", 340)))
        padding = max(0, int(layout.get("padding", 28)))
        stroke_width = max(0, int(layout.get("text_stroke_width", 0)))
        stroke_color = self._hex_or_rgba(layout.get("text_stroke_color", "#000000"))

        if anchor == "center":
            final_left = canvas.width // 2 + box_left
            final_top = canvas.height // 2 + box_top
        elif anchor == "right-bottom":
            final_left = canvas.width - box_width + box_left
            final_top = canvas.height - box_height + box_top
        else:
            final_left = canvas.width + box_left if box_left < 0 else box_left
            final_top = canvas.height + box_top if box_top < 0 else box_top

        font = self._load_font(layout.get("font_size", 30), preferred=layout.get("body_font"))
        text_area_w = max(10, box_width - padding * 2)
        wrapped = self._wrap_text(text, font, max(10, text_area_w))
        spacing = max(0, int(font.size * (float(layout.get("line_height", 1.6)) - 1)))
        self._draw_rich_text(
            canvas,
            (final_left + padding, final_top + padding),
            wrapped,
            font,
            self._hex_or_rgba(layout.get("text_color", "#FFFFFF")),
            stroke_width=stroke_width,
            stroke_fill=stroke_color,
            spacing=spacing,
        )

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
        draw = ImageDraw.Draw(canvas)
        fallback_fonts = self._system_font_candidates(getattr(font, "size", 30))
        x, y = position
        line_gap = max(0, int(spacing))
        for line in text.replace("\r", "").split("\n"):
            if line:
                line_height = self._draw_text_line(
                    draw,
                    (x, y),
                    line,
                    font,
                    fallback_fonts,
                    fill,
                    stroke_width=stroke_width,
                    stroke_fill=stroke_fill,
                )
            else:
                ascent, descent = self._font_metrics(font)
                line_height = ascent + descent
            y += line_height + line_gap

    def _draw_overlay_text(self, canvas: Image.Image, overlay: Optional[Dict[str, Any]]):
        if not overlay or not overlay.get("visible", True):
            return
        text_val = overlay.get("text", "")
        if not text_val:
            return
        left = int(overlay.get("left", 0))
        top = int(overlay.get("top", 0))
        font_size = max(8, int(overlay.get("font_size", 28)))
        stroke_width = max(0, int(overlay.get("stroke_width", 0)))
        stroke_color = self._hex_or_rgba(overlay.get("stroke_color", "#000000"))
        bold = bool(overlay.get("bold", True))
        font_name = str(overlay.get("font") or "").strip()

        font = self._load_font(font_size, preferred=font_name, bold=bold)

        try:
            opacity = float(overlay.get("opacity", 1.0))
        except Exception:
            opacity = 1.0
        opacity = max(0.0, min(1.0, opacity))
        fill_color = self._hex_or_rgba(overlay.get("color", "#FFFFFF"))
        fill = (fill_color[0], fill_color[1], fill_color[2], int(fill_color[3] * opacity))
        stroke = (stroke_color[0], stroke_color[1], stroke_color[2], int(stroke_color[3] * opacity))

        draw = ImageDraw.Draw(canvas)
        fallback_fonts = self._system_font_candidates(font_size)

        lines = text_val.replace("\r", "").split("\n")
        y = top
        for line_text in lines:
            if line_text:
                height = self._draw_text_line(
                    draw,
                    (left, y),
                    line_text,
                    font,
                    fallback_fonts,
                    fill,
                    stroke_width=stroke_width,
                    stroke_fill=stroke,
                )
            else:
                ascent, descent = self._font_metrics(font)
                height = ascent + descent
            y += height

    def _draw_overlay_image(self, canvas: Image.Image, overlay: Optional[Dict[str, Any]]):
        if not overlay or not overlay.get("visible", True):
            return
        image_name = str(overlay.get("image") or "").strip()
        if not image_name:
            return
        path = self._resolve_component_path(image_name)
        if not path:
            logger.debug("[传话筒] 未找到贴图资源: %s", image_name)
            return
        try:
            img = Image.open(path).convert("RGBA")
            w = max(10, int(overlay.get("width", img.width)))
            h = max(10, int(overlay.get("height", img.height)))
            img = img.resize((w, h), Image.LANCZOS)
            left = int(overlay.get("left", 0))
            top = int(overlay.get("top", 0))
            try:
                opacity = float(overlay.get("opacity", 1.0))
            except Exception:
                opacity = 1.0
            opacity = max(0.0, min(1.0, opacity))
            if opacity < 1.0:
                alpha = img.split()[3]
                alpha = alpha.point(lambda p: int(p * opacity))
                img.putalpha(alpha)
            canvas.alpha_composite(img, (left, top))
        except Exception:
            logger.debug("[传话筒] 贴图渲染失败", exc_info=True)

    def _draw_glass_layer(self, canvas: Image.Image, overlay: Optional[Dict[str, Any]]):
        if not overlay or not overlay.get("visible", True):
            return
        left = int(overlay.get("left", 0))
        top = int(overlay.get("top", 0))
        w = max(10, int(overlay.get("width", 200)))
        h = max(10, int(overlay.get("height", 60)))
        try:
            opacity = float(overlay.get("opacity", 1.0))
        except Exception:
            opacity = 1.0
        opacity = max(0.0, min(1.0, opacity))
        glass = Image.new("RGBA", (w, h), (255, 255, 255, int(20 * opacity)))
        canvas.alpha_composite(glass, (left, top))

    # ------------------------------------------------------------------
    # Color parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_rgba(value: str) -> tuple[int, int, int, int]:
        value = (value or "").strip().lower()
        if value.startswith("rgba"):
            nums = value[value.find("(") + 1:value.find(")")].split(",")
            r, g, b = [int(float(nums[i])) for i in range(3)]
            a = float(nums[3]) if len(nums) > 3 else 1
            return (r, g, b, int(a * 255))
        return RenderMixin._hex_or_rgba(value)

    @staticmethod
    def _hex_or_rgba(value: str) -> tuple[int, int, int, int]:
        value = (value or "#FFFFFF").strip()
        if value.startswith("#") and len(value) in {4, 7}:
            if len(value) == 4:
                value = "#" + "".join(ch * 2 for ch in value[1:])
            r = int(value[1:3], 16)
            g = int(value[3:5], 16)
            b = int(value[5:7], 16)
            return (r, g, b, 255)
        return (255, 255, 255, 255)

    @staticmethod
    def _parse_shadow(shadow_str: str) -> Optional[Dict[str, Any]]:
        """Parse CSS-like text-shadow string.

        Example: "0 3px 12px rgba(0,0,0,0.55)"
        """
        if not shadow_str:
            return None
        s = shadow_str.strip()
        try:
            parts = s.split()
            offset_x = 0
            offset_y = 0
            blur = 0
            color = None
            idx = 0
            while idx < len(parts):
                token = parts[idx]
                if token.lower().startswith("rgba") or token.lower().startswith("rgb"):
                    color = RenderMixin._parse_rgba(token)
                    idx += 1
                elif token.startswith("#"):
                    color = RenderMixin._hex_or_rgba(token)
                    idx += 1
                elif "px" in token.lower():
                    val = float(token.lower().replace("px", ""))
                    if idx == 0:
                        offset_x = val
                    elif idx == 1:
                        offset_y = val
                    else:
                        blur = val
                    idx += 1
                else:
                    try:
                        val = float(token)
                        if idx == 0:
                            offset_x = val
                        elif idx == 1:
                            offset_y = val
                        else:
                            blur = val
                    except ValueError:
                        pass
                    idx += 1
            return {
                "offset_x": int(offset_x),
                "offset_y": int(offset_y),
                "blur": max(0, int(blur)),
                "color": color or (0, 0, 0, 140),
            }
        except Exception:
            return None

    @staticmethod
    def _draw_text_shadow(
        draw: ImageDraw.ImageDraw,
        text: str,
        position: tuple[int, int],
        font: ImageFont.ImageFont,
        shadow: Dict[str, Any],
    ):
        blur = shadow.get("blur", 0)
        color = shadow.get("color", (0, 0, 0, 140))
        ox = shadow.get("offset_x", 0)
        oy = shadow.get("offset_y", 0)
        sx = position[0] + ox
        sy = position[1] + oy
        if blur <= 1:
            draw.text((sx, sy), text, font=font, fill=color)
        else:
            # Simple blur by drawing multiple offset copies
            steps = min(blur, 6)
            for i in range(steps):
                angle = 2 * 3.14159 * i / steps
                dx = int(blur * 0.5 * __import__("math").cos(angle))
                dy = int(blur * 0.5 * __import__("math").sin(angle))
                draw.text((sx + dx, sy + dy), text, font=font, fill=color)

    # ------------------------------------------------------------------
    # Font helpers
    # ------------------------------------------------------------------

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
                "C:/Windows/Fonts/msyh.ttf",
                "C:/Windows/Fonts/simhei.ttf",
                "C:/Windows/Fonts/seguiemj.ttf",
            ])
        else:
            candidates.extend([
                "/System/Library/Fonts/PingFang.ttc",
                "/System/Library/Fonts/Hiragino Sans GB.ttc",
                "/System/Library/Fonts/Apple Color Emoji.ttc",
                "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
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

    @lru_cache(maxsize=16)
    def _system_font_candidates(self, size: int) -> tuple[ImageFont.ImageFont, ...]:
        candidates: list[ImageFont.ImageFont] = []
        if os.name == "nt":
            paths = [
                "C:/Windows/Fonts/seguiemj.ttf",
                "C:/Windows/Fonts/msyh.ttc",
                "C:/Windows/Fonts/simhei.ttf",
                "C:/Windows/Fonts/msgothic.ttc",
            ]
        else:
            paths = [
                "/System/Library/Fonts/Apple Color Emoji.ttc",
                "/System/Library/Fonts/PingFang.ttc",
                "/System/Library/Fonts/Hiragino Sans GB.ttc",
                "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ]
        for path in paths:
            try:
                candidates.append(ImageFont.truetype(path, size=size))
            except Exception:
                continue
        if not candidates:
            candidates.append(ImageFont.load_default())
        return tuple(candidates)

    @staticmethod
    def _glyph_uses_font(font: ImageFont.ImageFont, char: str) -> bool:
        if not char or char.isspace():
            return True
        try:
            bbox = font.getbbox(char)
            if not bbox:
                return False
            return (bbox[2] - bbox[0]) > 0 and (bbox[3] - bbox[1]) > 0
        except Exception:
            try:
                return bool(font.getmask(char).getbbox())
            except Exception:
                return False

    def _font_for_char(self, primary: ImageFont.ImageFont, char: str, fallback_fonts: tuple[ImageFont.ImageFont, ...]) -> ImageFont.ImageFont:
        if self._glyph_uses_font(primary, char):
            return primary
        for fallback in fallback_fonts:
            if fallback is primary:
                continue
            if self._glyph_uses_font(fallback, char):
                return fallback
        return primary

    @staticmethod
    def _text_clusters(text: str) -> list[str]:
        clusters: list[str] = []
        if not text:
            return clusters

        current = ""
        join_next = False
        for char in text:
            if not current:
                current = char
                join_next = char == "‍"
                continue

            if join_next:
                current += char
                join_next = char == "‍"
                continue

            category = unicodedata.category(char)
            if char == "‍" or category in {"Mn", "Me", "Cf"} or "︀" <= char <= "️" or "\U0001F3FB" <= char <= "\U0001F3FF":
                current += char
                join_next = char == "‍"
                continue

            clusters.append(current)
            current = char
            join_next = char == "‍"

        if current:
            clusters.append(current)
        return clusters

    @staticmethod
    def _font_metrics(font: ImageFont.ImageFont) -> tuple[int, int]:
        try:
            ascent, descent = font.getmetrics()
            return int(ascent), int(descent)
        except Exception:
            size = int(getattr(font, "size", 30) or 30)
            return size, max(1, size // 4)

    def _split_text_runs(
        self,
        text: str,
        primary: ImageFont.ImageFont,
        fallback_fonts: tuple[ImageFont.ImageFont, ...],
    ) -> list[tuple[str, ImageFont.ImageFont]]:
        runs: list[tuple[str, ImageFont.ImageFont]] = []
        if not text:
            return runs

        current_font: Optional[ImageFont.ImageFont] = None
        current_text = ""
        for cluster in self._text_clusters(text):
            char_font = self._font_for_char(primary, cluster, fallback_fonts)
            if current_font is char_font:
                current_text += cluster
                continue
            if current_text:
                runs.append((current_text, current_font or primary))
            current_font = char_font
            current_text = cluster
        if current_text:
            runs.append((current_text, current_font or primary))
        return runs

    def _draw_text_line(
        self,
        draw: ImageDraw.ImageDraw,
        position: tuple[int, int],
        text: str,
        primary: ImageFont.ImageFont,
        fallback_fonts: tuple[ImageFont.ImageFont, ...],
        fill: tuple[int, int, int, int],
        stroke_width: int = 0,
        stroke_fill: tuple[int, int, int, int] = (0, 0, 0, 255),
    ) -> int:
        runs = self._split_text_runs(text, primary, fallback_fonts)
        if not runs:
            return 0

        metrics = [self._font_metrics(font) for _, font in runs]
        line_ascent = max(ascent for ascent, _ in metrics)
        line_descent = max(descent for _, descent in metrics)
        x, y = position
        cursor_x = x
        for (run_text, run_font), (ascent, _) in zip(runs, metrics):
            run_y = y + (line_ascent - ascent)
            draw.text(
                (cursor_x, run_y),
                run_text,
                font=run_font,
                fill=fill,
                stroke_width=stroke_width,
                stroke_fill=stroke_fill,
            )
            cursor_x += int(round(self._measure_text_width(draw, run_text, run_font)))
        return line_ascent + line_descent

    @staticmethod
    def _measure_text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> float:
        if not text:
            return 0.0
        try:
            return float(draw.textlength(text, font=font))
        except Exception:
            try:
                bbox = draw.textbbox((0, 0), text, font=font)
                return float(bbox[2] - bbox[0]) if bbox else 0.0
            except Exception:
                return 0.0

    def _wrap_text(self, text: str, font: ImageFont.ImageFont, max_width: int) -> str:
        if not text:
            return ""
        fallback_fonts = self._system_font_candidates(getattr(font, "size", 30))
        draw = ImageDraw.Draw(Image.new("RGBA", (max_width, 10)))
        lines: list[str] = []
        for paragraph in text.splitlines():
            if not paragraph:
                lines.append("")
                continue
            current = ""
            current_width = 0.0
            for char in paragraph:
                char_font = self._font_for_char(font, char, fallback_fonts)
                char_width = self._measure_text_width(draw, char, char_font)
                if current and current_width + char_width > max_width:
                    lines.append(current)
                    current = char
                    current_width = self._measure_text_width(draw, char, char_font)
                else:
                    current += char
                    current_width += char_width
            if current:
                lines.append(current)
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Text splitting (for long text)
    # ------------------------------------------------------------------

    @staticmethod
    def _count_visible_chars(text: str) -> int:
        if not text:
            return 0
        return len(text.replace("\r", "").replace("\n", "").strip())

    @staticmethod
    def _smart_split_text(text: str, max_chars: int) -> list[str]:
        if not text or len(text) <= max_chars:
            return [text] if text else []

        chunks = []
        paragraphs = text.split('\n\n')
        current_chunk = ""

        for para in paragraphs:
            test_chunk = current_chunk + ('\n\n' if current_chunk else '') + para
            if len(test_chunk) <= max_chars:
                current_chunk = test_chunk
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""

                if len(para) > max_chars:
                    chunks.extend(RenderMixin._sentence_split(para, max_chars))
                else:
                    current_chunk = para

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    @staticmethod
    def _sentence_split(text: str, max_chars: int) -> list[str]:
        if not text or max_chars <= 0:
            return [text] if text else []

        pattern = r'([。！？\n])\s*'
        parts = re.split(pattern, text)

        chunks = []
        current = ""

        i = 0
        while i < len(parts):
            sentence = parts[i]
            punctuation = parts[i+1] if i+1 < len(parts) else ""
            full_sentence = sentence + punctuation

            if len(current) + len(full_sentence) <= max_chars:
                current += full_sentence
            else:
                if current:
                    chunks.append(current.strip())
                if len(full_sentence) > max_chars:
                    chunks.extend(RenderMixin._hard_split(full_sentence, max_chars))
                    current = ""
                else:
                    current = full_sentence

            i += 2

        if current:
            chunks.append(current.strip())

        return [c for c in chunks if c]

    @staticmethod
    def _hard_split(text: str, max_chars: int) -> list[str]:
        if not text or len(text) <= max_chars:
            return [text] if text else []
        return [text[i:i+max_chars] for i in range(0, len(text), max_chars)]

    def _split_text_with_emotion(
        self,
        text: str,
        max_chars: int,
        default_emotion: str
    ) -> list[Tuple[str, str]]:
        mapping = self._emotion_meta()
        emotion_positions: list[Tuple[int, str]] = []

        for match in self.EMOTION_PATTERN.finditer(text):
            emotion_key = match.group(1).lower()
            if emotion_key in mapping:
                emotion_positions.append((match.start(), emotion_key))

        clean_text = self._remove_emotion_tags(text)
        clean_text = self._remove_markdown_syntax(clean_text)
        clean_text = re.sub(r'\n{2,}', '\n', clean_text)
        lines = clean_text.split('\n')
        lines = [line.rstrip() for line in lines]
        clean_text = '\n'.join(lines)
        clean_text = clean_text.strip()

        chunks = self._smart_split_text(clean_text, max_chars)

        result = []
        current_emotion = default_emotion or next(iter(mapping.keys()), "neutral")
        char_offset = 0

        for chunk in chunks:
            chunk_start = char_offset
            chunk_end = char_offset + len(chunk)

            chunk_emotion = None
            for pos, emo in emotion_positions:
                if chunk_start <= pos < chunk_end:
                    chunk_emotion = emo
                    break

            if chunk_emotion:
                current_emotion = chunk_emotion

            result.append((chunk, current_emotion))
            char_offset = chunk_end

        return result

    async def _send_fallback_texts(
        self,
        fallback_texts: list[Tuple[int, str]],
        event: AstrMessageEvent
    ) -> None:
        for idx, chunk_text in fallback_texts:
            try:
                chain = MessageChain()
                chain.message(f"{chunk_text}\n")
                await event.send(chain)
            except Exception:
                logger.warning("[传话筒] 发送降级文本失败", exc_info=True)

    async def _render_split_text(
        self,
        text: str,
        emotion: str,
        event: AstrMessageEvent,
        session_id: Optional[str] = None,
        persona_id: Optional[str] = None,
    ) -> bool:
        split_page_limit = int(self.cfg().get("split_page_char_limit", 200) or 0)
        if split_page_limit <= 0:
            split_page_limit = 200

        chunks_with_emotion = self._split_text_with_emotion(text, split_page_limit, emotion)

        if not chunks_with_emotion:
            return False

        if len(chunks_with_emotion) <= 1:
            clean_text = chunks_with_emotion[0][0]
            chunk_emotion = chunks_with_emotion[0][1] if chunks_with_emotion[0][1] else emotion
            image_path = await self._render_with_fallback(clean_text, chunk_emotion, session_id, persona_id)
            if image_path:
                try:
                    chain = MessageChain()
                    chain.file_image(image_path)
                    await event.send(chain)
                    self._schedule_cleanup(image_path, delay=90.0)
                    return True
                except Exception:
                    logger.error("[传话筒] 单块路径发送图片失败", exc_info=True)
                    return False
            return False

        logger.info("[传话筒] 分割文本为 %s 个片段进行渲染", len(chunks_with_emotion))

        rendered_images: list[str] = []
        fallback_texts: list[Tuple[int, str]] = []

        for idx, (chunk_text, chunk_emotion) in enumerate(chunks_with_emotion, 1):
            try:
                image_path = await self._render_with_fallback(chunk_text, chunk_emotion, session_id, persona_id)
                if image_path:
                    rendered_images.append(image_path)
                else:
                    fallback_texts.append((idx, chunk_text))
            except Exception as exc:
                logger.error("[传话筒] 渲染第 %s 段失败: %s", idx, exc, exc_info=True)
                fallback_texts.append((idx, chunk_text))

        if not rendered_images:
            await self._send_fallback_texts(fallback_texts, event)
            return False

        enable_merge = self._cfg_bool("merge_split_images", True)

        if enable_merge and len(rendered_images) > 1:
            max_per_batch = int(self.cfg().get("merge_max_images", 5) or 5)
            if max_per_batch <= 0:
                max_per_batch = 5

            batches = [
                rendered_images[i:i + max_per_batch]
                for i in range(0, len(rendered_images), max_per_batch)
            ]

            logger.info("[传话筒] 分 %s 批合并图片（每批最多 %s 张）", len(batches), max_per_batch)

            success_count = 0
            for batch_idx, batch in enumerate(batches, 1):
                if len(batch) == 1:
                    try:
                        chain = MessageChain()
                        chain.file_image(batch[0])
                        await event.send(chain)
                        self._schedule_cleanup(batch[0], delay=90.0)
                        success_count += 1
                    except Exception:
                        logger.error("[传话筒] 第 %s 批单图发送失败", batch_idx, exc_info=True)
                else:
                    merged_path = await asyncio.to_thread(self._merge_images_vertical, batch)

                    if merged_path:
                        try:
                            chain = MessageChain()
                            chain.file_image(merged_path)
                            await event.send(chain)

                            for path in batch:
                                self._schedule_cleanup(path, delay=5.0)
                            self._schedule_cleanup(merged_path, delay=90.0)
                            success_count += 1
                        except Exception:
                            logger.error("[传话筒] 第 %s 批合并图发送失败", batch_idx, exc_info=True)
                    else:
                        logger.warning("[传话筒] 第 %s 批合并失败，逐张发送", batch_idx)
                        for path in batch:
                            try:
                                chain = MessageChain()
                                chain.file_image(path)
                                await event.send(chain)
                                self._schedule_cleanup(path, delay=90.0)
                                success_count += 1
                            except Exception:
                                logger.error("[传话筒] 第 %s 批逐图发送失败", batch_idx, exc_info=True)

            await self._send_fallback_texts(fallback_texts, event)
            logger.info("[传话筒] 合并图片发送完成")
            return success_count > 0

        # merge_split_images=false：使用合并转发发送多张图片
        if len(rendered_images) > 1:
            from astrbot.api.message_components import Node, Nodes

            nodes_list = []
            for image_path in rendered_images:
                node = Node(
                    name="传话筒",
                    uin="0",
                    content=[Comp.Image.fromFileSystem(image_path)]
                )
                nodes_list.append(node)

            try:
                nodes = Nodes(nodes=nodes_list)
                chain = MessageChain([nodes])
                await event.send(chain)
                for path in rendered_images:
                    self._schedule_cleanup(path, delay=90.0)
                await self._send_fallback_texts(fallback_texts, event)
                logger.info("[传话筒] 合并转发发送完成，共 %s 张图片", len(rendered_images))
                return True
            except Exception:
                logger.error("[传话筒] 合并转发发送失败，降级为逐图发送", exc_info=True)
                # 降级为逐图发送
                for image_path in rendered_images:
                    try:
                        chain = MessageChain()
                        chain.file_image(image_path)
                        await event.send(chain)
                        self._schedule_cleanup(image_path, delay=90.0)
                    except Exception:
                        logger.error("[传话筒] 逐图发送失败", exc_info=True)

                await self._send_fallback_texts(fallback_texts, event)
                return len(rendered_images) > 0

        # 单张图片直接发送
        for image_path in rendered_images:
            try:
                chain = MessageChain()
                chain.file_image(image_path)
                await event.send(chain)
                self._schedule_cleanup(image_path, delay=90.0)
            except Exception:
                logger.error("[传话筒] 逐图发送失败", exc_info=True)

        await self._send_fallback_texts(fallback_texts, event)
        return len(rendered_images) > 0

    def _merge_images_vertical(
        self,
        image_paths: list[str],
        gap: int = 10,
        background_color: Optional[str] = None
    ) -> Optional[str]:
        if not image_paths:
            return None

        if len(image_paths) == 1:
            return image_paths[0]

        images = []
        try:
            for p in image_paths:
                images.append(Image.open(p))

            max_width = max(img.width for img in images)
            total_height = sum(img.height for img in images) + gap * (len(images) - 1)

            if background_color:
                bg_color = self._hex_or_rgba(background_color)[:3]
            else:
                bg_color = (0, 0, 0)

            merged = Image.new("RGB", (max_width, total_height), bg_color)

            y_offset = 0
            for img in images:
                if img.mode != "RGB":
                    img_converted = img.convert("RGB")
                else:
                    img_converted = img

                x_offset = (max_width - img_converted.width) // 2
                merged.paste(img_converted, (x_offset, y_offset))
                y_offset += img.height + gap

            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpeg") as f:
                out_path = f.name

            quality = int(self.cfg().get("image_quality", 85) or 85)
            quality = max(1, min(100, quality))
            merged.save(out_path, "JPEG", quality=quality, optimize=False)

            logger.debug("[传话筒] 图片合并完成: %s 张 -> %s", len(images), out_path)
            return out_path

        except Exception as exc:
            logger.error("[传话筒] 图片合并失败: %s", exc)
            return None
        finally:
            for img in images:
                try:
                    img.close()
                except Exception:
                    pass