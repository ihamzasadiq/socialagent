#!/usr/bin/env python3
"""Compose a social media post image: crop, tint, scrim, typography and branding."""

import argparse
import colorsys
import json
import time
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

BASE_DIR = Path(__file__).resolve().parent
RATIOS = {"1:1": (1080, 1080), "4:5": (1080, 1350), "9:16": (1080, 1920), "16:9": (1200, 675)}
LAYOUTS = ("bold-bottom", "centered-card", "minimal-corner", "full-gradient")
STYLES = ("modern", "editorial", "minimal")
RULES = ("none", "above", "below")
STYLE_FONTS = {
    "modern": {"headline": "Montserrat[wght].ttf", "body": "Inter[opsz,wght].ttf"},
    "editorial": {"headline": "PlayfairDisplay[wght].ttf", "body": "Inter[opsz,wght].ttf"},
    "minimal": {"headline": "Inter[opsz,wght].ttf", "body": "Inter[opsz,wght].ttf"},
}
STYLE_WEIGHTS = {
    "modern": {"headline": "ExtraBold", "body": "Medium"},
    "editorial": {"headline": "Bold", "body": "Medium"},
    "minimal": {"headline": "SemiBold", "body": "Regular"},
}
FALLBACK_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]
DEFAULT_ACCENT = (255, 107, 53)
DEFAULT_TEXT = (255, 255, 255)
DARK_TEXT = (17, 17, 17)
DEFAULT_SCRIMS = {
    "bold-bottom": 62,
    "centered-card": 42,
    "minimal-corner": 36,
    "full-gradient": 72,
}
DEFAULT_CARD_ALPHA = 62


class ComposeError(Exception):
    pass


def load_brand(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def hex_to_rgb(value, fallback):
    if not value:
        return fallback
    value = value.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return fallback


def rgb_to_hex(color):
    return "#%02X%02X%02X" % color


def luminance(color):
    return 0.2126 * color[0] + 0.7152 * color[1] + 0.0722 * color[2]


def load_font(path, size, weight_name=None):
    font = None
    if path:
        try:
            font = ImageFont.truetype(str(path), size)
        except OSError:
            font = None
    if font is None:
        for fallback in FALLBACK_FONTS:
            try:
                font = ImageFont.truetype(fallback, size)
                break
            except OSError:
                continue
    if font is None:
        return ImageFont.load_default()
    if weight_name:
        try:
            font.set_variation_by_name(weight_name)
        except Exception:
            pass
    return font


def resolve_font(brand, role, style, override=None):
    if override:
        return override
    candidate = BASE_DIR / "assets" / "fonts" / STYLE_FONTS[style][role]
    if candidate.exists():
        return str(candidate)
    brand_key = brand.get(f"font_{role}")
    if brand_key:
        path = Path(brand_key)
        if not path.is_absolute():
            path = BASE_DIR / path
        if path.exists():
            return str(path)
    return None


def line_width(draw, text, font, tracking):
    if tracking:
        return sum(draw.textlength(ch, font=font) for ch in text) + tracking * max(0, len(text) - 1)
    return draw.textlength(text, font=font)


def _balanced_lines(words, draw, font, max_width, tracking):
    count = len(words)
    widths = [line_width(draw, word, font, tracking) for word in words]
    space = line_width(draw, " ", font, tracking)
    best = [float("inf")] * (count + 1)
    breaks = [count] * (count + 1)
    best[count] = 0.0
    for i in range(count - 1, -1, -1):
        total = 0.0
        for j in range(i, count):
            total += widths[j] + (space if j > i else 0)
            if total > max_width:
                break
            slack = max_width - total
            cost = slack * slack + best[j + 1]
            if cost < best[i]:
                best[i] = cost
                breaks[i] = j + 1
    if best[0] == float("inf"):
        return None
    lines = []
    i = 0
    while i < count:
        j = breaks[i]
        lines.append(" ".join(words[i:j]))
        i = j
    return lines


def wrap_text(text, draw, font, max_width, tracking=0, max_lines=None, balance=True):
    lines = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        wrapped = None
        if balance and len(words) <= 30:
            wrapped = _balanced_lines(words, draw, font, max_width, tracking)
            if wrapped and len(wrapped) > 6:
                wrapped = None
        if wrapped is None:
            wrapped = []
            current = words[0]
            for word in words[1:]:
                candidate = current + " " + word
                if line_width(draw, candidate, font, tracking) <= max_width:
                    current = candidate
                else:
                    wrapped.append(current)
                    current = word
            wrapped.append(current)
        lines.extend(wrapped)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1].rstrip()
        while last and line_width(draw, last + "\u2026", font, tracking) > max_width:
            last = last[:-1].rstrip()
        lines[-1] = (last + "\u2026") if last else "\u2026"
    return lines


def fit_text(text, draw, font_path, weight, max_width, max_height, max_lines, start_size, min_size, line_spacing, tracking=0):
    size = start_size
    while size >= min_size:
        font = load_font(font_path, size, weight)
        lines = wrap_text(text, draw, font, max_width, tracking)
        line_h = max(1, int(size * line_spacing))
        if len(lines) <= max_lines and len(lines) * line_h <= max_height:
            return font, lines, size, line_h
        size -= 2
    font = load_font(font_path, min_size, weight)
    lines = wrap_text(text, draw, font, max_width, tracking, max_lines=max_lines)
    return font, lines, min_size, max(1, int(min_size * line_spacing))


def draw_line(target, xy, text, font, fill, tracking=0):
    if not text:
        return
    if tracking:
        x, y = xy
        for char in text:
            target.text((x, y), char, font=font, fill=fill)
            x += target.textlength(char, font=font) + tracking
    else:
        target.text(xy, text, font=font, fill=fill)


def draw_text_layer(canvas_size, lines, font, line_h, anchor, fill, align="left", tracking=0, shadow=True, shadow_offset=None, shadow_fill=(0, 0, 0, 150)):
    layer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    y = anchor[1]
    for line in lines:
        width = line_width(draw, line, font, tracking)
        x = anchor[0] if align == "left" else (anchor[0] - width / 2 if align == "center" else anchor[0] - width)
        draw_line(draw, (x, y), line, font, fill, tracking)
        y += line_h
    if shadow:
        offset = shadow_offset if shadow_offset is not None else max(2, int(font.size * 0.035))
        blur = max(3, int(font.size * 0.05))
        shadow_layer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_layer)
        y = anchor[1] + offset
        for line in lines:
            width = line_width(shadow_draw, line, font, tracking)
            x = anchor[0] if align == "left" else (anchor[0] - width / 2 if align == "center" else anchor[0] - width)
            draw_line(shadow_draw, (x, y), line, font, shadow_fill, tracking)
            y += line_h
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(blur))
        layer = Image.alpha_composite(shadow_layer, layer)
    return layer


def cover_crop(image, size, focus):
    width, height = size
    source_w, source_h = image.size
    scale = max(width / source_w, height / source_h)
    new_size = (max(width, int(source_w * scale + 0.5)), max(height, int(source_h * scale + 0.5)))
    resized = image.resize(new_size, Image.LANCZOS)
    fx = min(max(focus[0], 0.0), 1.0)
    fy = min(max(focus[1], 0.0), 1.0)
    left = int((new_size[0] - width) * fx)
    top = int((new_size[1] - height) * fy)
    return resized.crop((left, top, left + width, top + height))


def normalize_output(path, width=1080):
    image = Image.open(path).convert("RGB")
    if image.width != width:
        height = max(1, round(image.height * width / image.width))
        image = image.resize((width, height), Image.LANCZOS)
        fmt = "JPEG" if str(path).lower().endswith((".jpg", ".jpeg")) else "PNG"
        image.save(path, fmt)
    return path


def gradient_mask(size, strength, start_frac=0.0, power=1.0):
    width, height = size
    lower = start_frac * 255.0
    span = 255.0 - lower if lower < 255.0 else 1.0
    factor = strength * 2.55

    def ramp(value):
        if value <= lower:
            return 0
        return int(factor * (((value - lower) / span) ** power))

    return Image.linear_gradient("L").resize((width, height)).point(ramp)


def solid_mask(size, strength):
    return Image.new("L", size, int(strength * 2.55))


def apply_scrim(image, mask):
    black = Image.new("RGBA", image.size, (0, 0, 0, 255))
    return Image.composite(black, image, mask)


def accent_overlay(size, color, strength, start_frac, power=1.0):
    mask = gradient_mask(size, strength, start_frac, power)
    layer = Image.new("RGBA", size, tuple(color) + (255,))
    transparent = Image.new("RGBA", size, (0, 0, 0, 0))
    return Image.composite(layer, transparent, mask)


def color_overlay(size, color, strength):
    return Image.new("RGBA", size, tuple(color) + (int(max(0, min(100, strength)) * 2.55),))


def extract_accent(image):
    small = image.convert("RGB").resize((120, 120))
    quantized = small.quantize(colors=10, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette() or []
    best, best_score = None, -1.0
    for count, index in quantized.getcolors() or []:
        r, g, b = palette[index * 3:index * 3 + 3]
        _, saturation, value = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if value < 0.12 or value > 0.97 or saturation < 0.12:
            continue
        score = saturation * (count ** 0.5)
        if score > best_score:
            best_score, best = score, (r, g, b)
    if not best:
        return DEFAULT_ACCENT
    hue, saturation, value = colorsys.rgb_to_hsv(best[0] / 255, best[1] / 255, best[2] / 255)
    saturation = max(saturation, 0.62)
    value = min(max(value, 0.72), 0.96)
    r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
    return int(r * 255), int(g * 255), int(b * 255)


def paste_logo(base, logo_path, position, margin, target_height):
    try:
        logo = Image.open(logo_path).convert("RGBA")
    except OSError:
        return False
    scale = target_height / logo.height
    logo = logo.resize((max(1, int(logo.width * scale)), target_height), Image.LANCZOS)
    width, height = base.size
    x, y = margin, margin
    if "right" in position:
        x = width - margin - logo.width
    elif "center" in position:
        x = (width - logo.width) // 2
    if "bottom" in position:
        y = height - margin - logo.height
    base.alpha_composite(logo, (max(0, x), max(0, y)))
    return True


def handle_position(layout):
    return {
        "bold-bottom": "top-right",
        "minimal-corner": "top-right",
        "centered-card": "bottom-center",
        "full-gradient": "bottom-center",
    }[layout]


def flip_vertical(position):
    return position.replace("top", "tmp").replace("bottom", "top").replace("tmp", "bottom")


def block_top(position, block_height, safe_top, safe_bottom, height, margin, default):
    if position == "top":
        return safe_top + margin
    if position == "center":
        return (safe_top + (height - safe_bottom) - block_height) / 2
    if position == "bottom":
        return height - safe_bottom - margin - block_height
    return default


def parse_focus(value):
    if isinstance(value, (tuple, list)):
        if len(value) != 2:
            raise ComposeError("focus must have two values")
        return float(value[0]), float(value[1])
    try:
        parts = tuple(float(part) for part in str(value).split(","))
        if len(parts) != 2:
            raise ValueError
        return parts
    except ValueError:
        raise ComposeError("focus must look like 0.5,0.45")


def build_block(rule, rule_w, rule_h, rule_color, gap_rule, gap_sub, headline_item, sub_item):
    items = []
    if rule == "above":
        items.append({"kind": "rule", "width": rule_w, "height": rule_h, "color": rule_color, "gap": gap_rule})
    headline_item["gap"] = gap_rule if (rule == "below" and sub_item) else (gap_sub if sub_item else 0)
    items.append(headline_item)
    if rule == "below":
        items.append({"kind": "rule", "width": rule_w, "height": rule_h, "color": rule_color, "gap": gap_sub if sub_item else 0})
    if sub_item:
        sub_item["gap"] = 0
        items.append(sub_item)
    return items


def item_height(item):
    if item["kind"] == "rule":
        return item["height"]
    return len(item["lines"]) * item["line_h"]


def block_height(items):
    return sum(item_height(item) + item.get("gap", 0) for item in items)


def block_width(items, draw):
    width = 0
    for item in items:
        if item["kind"] == "rule":
            width = max(width, item["width"])
        else:
            for line in item["lines"]:
                width = max(width, line_width(draw, line, item["font"], item.get("tracking", 0)))
    return width


def draw_block(canvas_size, items, anchor_x, top, align, shadow, shadow_fill):
    layer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    y = top
    for item in items:
        if item["kind"] == "rule":
            width = item["width"]
            x = anchor_x if align == "left" else anchor_x - width / 2
            draw.rectangle([x, y, x + width, y + item["height"]], fill=item["color"])
        else:
            text_layer = draw_text_layer(
                canvas_size, item["lines"], item["font"], item["line_h"], (anchor_x, y),
                item["fill"], align, item.get("tracking", 0), shadow, None, shadow_fill)
            layer = Image.alpha_composite(layer, text_layer)
            draw = ImageDraw.Draw(layer)
        y += item_height(item) + item.get("gap", 0)
    return layer


def compose(
    image,
    headline,
    subhead=None,
    handle=None,
    logo=None,
    ratio=None,
    size=None,
    layout=None,
    position="auto",
    scrim=None,
    accent=None,
    accent_strength=78,
    text_color=None,
    style="modern",
    align=None,
    tracking=None,
    uppercase=False,
    shadow=True,
    focus="0.5,0.45",
    safe_zone=False,
    headline_font=None,
    body_font=None,
    brand_path=None,
    output=None,
    jpeg=False,
    jpeg_quality=92,
    card_alpha=None,
    card_color=None,
    tint=None,
    tint_alpha=0,
    rule=None,
    subhead_scale=1.0,
):
    brand_path = brand_path or BASE_DIR / "brand.json"
    brand = load_brand(brand_path)
    palette = brand.get("palette") or {}

    if size:
        try:
            width, height = (int(part) for part in str(size).lower().split("x"))
        except ValueError:
            raise ComposeError("size must look like 1080x1350")
    else:
        ratio = ratio or brand.get("default_ratio") or "4:5"
        if ratio not in RATIOS:
            raise ComposeError(f"unsupported ratio: {ratio}")
        width, height = RATIOS[ratio]
    ratio_name = ratio or next((name for name, dims in RATIOS.items() if dims == (width, height)), f"{width}x{height}")

    layout = layout or brand.get("default_layout") or "bold-bottom"
    if layout not in LAYOUTS:
        raise ComposeError(f"unsupported layout: {layout}")
    if style not in STYLES:
        raise ComposeError(f"unsupported style: {style}")
    rule = rule or "above"
    if rule not in RULES:
        raise ComposeError(f"unsupported rule: {rule}")
    focus = parse_focus(focus)

    try:
        background = Image.open(image).convert("RGB")
    except OSError as error:
        raise ComposeError(f"cannot open image {image}: {error}")

    story = ratio_name == "9:16"
    safe = safe_zone or story
    safe_top = round(height * (0.12 if story else 0.04)) if safe else 0
    safe_bottom = round(height * (0.17 if story else 0.04)) if safe else 0

    if accent and accent != "auto":
        resolved_accent = hex_to_rgb(accent, DEFAULT_ACCENT)
    elif accent == "auto":
        resolved_accent = extract_accent(background)
    else:
        resolved_accent = hex_to_rgb(palette.get("accent"), extract_accent(background))

    base = cover_crop(background, (width, height), focus).convert("RGBA")
    if tint and int(tint_alpha or 0) > 0:
        tint_rgb = extract_accent(background) if tint == "auto" else hex_to_rgb(tint, None)
        if tint_rgb:
            base = Image.alpha_composite(base, color_overlay((width, height), tint_rgb, int(tint_alpha)))

    margin = round(width * (0.075 if layout != "minimal-corner" else 0.065))
    max_width = width - 2 * margin

    headline_text = headline.upper() if uppercase else headline
    headline_font_path = resolve_font(brand, "headline", style, headline_font)
    body_font_path = resolve_font(brand, "body", style, body_font)
    headline_weight = STYLE_WEIGHTS[style]["headline"]
    body_weight = STYLE_WEIGHTS[style]["body"]

    scrim = DEFAULT_SCRIMS[layout] if scrim is None else max(0, min(100, int(scrim)))
    if layout == "bold-bottom":
        mask = gradient_mask((width, height), scrim, start_frac=0.18, power=1.45)
    elif layout == "minimal-corner":
        mask = gradient_mask((width, height), scrim, start_frac=0.45, power=1.6)
    elif layout == "centered-card":
        mask = ImageChops.lighter(gradient_mask((width, height), scrim, 0.25, 1.3), solid_mask((width, height), 14))
    else:
        mask = gradient_mask((width, height), scrim, 0.15, 1.25)
    base = apply_scrim(base, mask)
    if layout == "full-gradient":
        base = Image.alpha_composite(base, accent_overlay((width, height), resolved_accent, max(0, min(100, int(accent_strength))), 0.35, 1.0))
        base = apply_scrim(base, gradient_mask((width, height), 45, 0.55, 1.6))

    if text_color and text_color != "auto":
        resolved_text = hex_to_rgb(text_color, DEFAULT_TEXT)
    elif text_color == "auto":
        if position == "top":
            top_frac, bottom_frac = 0.06, 0.40
        elif position == "center":
            top_frac, bottom_frac = 0.28, 0.72
        else:
            top_frac, bottom_frac = 0.52, 0.96
        sample_top = min(height - 1, safe_top + round(height * top_frac))
        sample_bottom = max(sample_top + 1, min(height, round(height * bottom_frac) - safe_bottom))
        sample = base.crop((margin, sample_top, width - margin, sample_bottom)).convert("RGB").resize((64, 64))
        avg = sum(luminance(pixel) for pixel in sample.getdata()) / (64 * 64)
        resolved_text = DARK_TEXT if avg > 150 else DEFAULT_TEXT
    else:
        resolved_text = hex_to_rgb(palette.get("text"), DEFAULT_TEXT)
    shadow_fill = (255, 255, 255, 135) if luminance(resolved_text) < 128 else (0, 0, 0, 150)

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    summary = {}
    subhead_scale = max(0.5, min(1.5, float(subhead_scale or 1.0)))

    if layout == "bold-bottom":
        align = align or "left"
        tracking = tracking if tracking is not None else 0.0
        headline_font, headline_lines, headline_size, line_h = fit_text(
            headline_text, overlay_draw, headline_font_path, headline_weight,
            max_width, round(height * 0.44), 4, round(width * 0.115), 54, 1.06, tracking)
        sub_item = None
        if subhead:
            sub_size = max(26, round(headline_size * 0.30 * subhead_scale))
            sub_font = load_font(body_font_path, sub_size, body_weight)
            sub_lines = wrap_text(subhead, overlay_draw, sub_font, max_width, max_lines=2)
            sub_item = {"kind": "text", "lines": sub_lines, "font": sub_font, "line_h": round(sub_size * 1.35), "fill": tuple(resolved_text) + (215,)}
        bar_w, bar_h = round(width * 0.09), max(6, round(width * 0.009))
        gap_bar, gap_sub = round(headline_size * 0.24), round(headline_size * 0.20)
        items = build_block(rule, bar_w, bar_h, tuple(resolved_accent) + (255,), gap_bar, gap_sub,
                            {"kind": "text", "lines": headline_lines, "font": headline_font, "line_h": line_h, "fill": tuple(resolved_text) + (245,), "tracking": tracking}, sub_item)
        height_block = block_height(items)
        top = max(block_top(position, height_block, safe_top, safe_bottom, height, margin, height - safe_bottom - margin - height_block), safe_top + margin)
        overlay = Image.alpha_composite(overlay, draw_block((width, height), items, margin, top, align, shadow, shadow_fill))
        summary.update({"headline_size": headline_size, "headline_lines": len(headline_lines), "subhead_lines": len(sub_item["lines"]) if sub_item else 0})

    elif layout == "centered-card":
        align = align or "center"
        tracking = tracking if tracking is not None else 0.0
        card_alpha = DEFAULT_CARD_ALPHA if card_alpha is None else max(0, min(100, int(card_alpha)))
        card_pad = round(width * 0.055)
        inner_width = max_width - 2 * card_pad if card_alpha > 0 else max_width
        headline_font, headline_lines, headline_size, line_h = fit_text(
            headline_text, overlay_draw, headline_font_path, headline_weight,
            inner_width, round(height * 0.30), 3, round(width * 0.095), 50, 1.08, tracking)
        sub_item = None
        if subhead:
            sub_size = max(26, round(headline_size * 0.34 * subhead_scale))
            sub_font = load_font(body_font_path, sub_size, body_weight)
            sub_lines = wrap_text(subhead, overlay_draw, sub_font, inner_width, max_lines=2)
            sub_item = {"kind": "text", "lines": sub_lines, "font": sub_font, "line_h": round(sub_size * 1.4), "fill": tuple(resolved_text) + (220,)}
        bar_w, bar_h = round(width * 0.06), 8
        gap_bar, gap_sub = round(headline_size * 0.28), round(headline_size * 0.30)
        items = build_block(rule, bar_w, bar_h, tuple(resolved_accent) + (255,), gap_bar, gap_sub,
                            {"kind": "text", "lines": headline_lines, "font": headline_font, "line_h": line_h, "fill": tuple(resolved_text) + (248,), "tracking": tracking}, sub_item)
        content_h = block_height(items)
        if card_alpha > 0:
            content_w = block_width(items, overlay_draw)
            card_w = max(round(width * 0.55), min(max_width, int(content_w) + 2 * card_pad))
            card_h = content_h + 2 * card_pad
            default_top = round(height * 0.60) - card_h // 2
            card_top = block_top(position, card_h, safe_top, safe_bottom, height, margin, default_top)
            card_left = (width - card_w) // 2
            card_fill = card_color if card_color else palette.get("card")
            card_rgb = hex_to_rgb(card_fill, (0, 0, 0))
            overlay_draw.rounded_rectangle([card_left, card_top, card_left + card_w, card_top + card_h], radius=round(width * 0.03), fill=tuple(card_rgb) + (int(card_alpha * 2.55),))
            top = card_top + card_pad
        else:
            default_top = round(height * 0.60) - content_h // 2
            top = block_top(position, content_h, safe_top, safe_bottom, height, margin, default_top)
        overlay = Image.alpha_composite(overlay, draw_block((width, height), items, width // 2, top, align, shadow, shadow_fill))
        summary.update({"card_alpha": card_alpha, "headline_size": headline_size, "headline_lines": len(headline_lines), "subhead_lines": len(sub_item["lines"]) if sub_item else 0})

    elif layout == "minimal-corner":
        align = align or "left"
        tracking = tracking if tracking is not None else 0.6
        headline_font, headline_lines, headline_size, line_h = fit_text(
            headline_text, overlay_draw, headline_font_path, headline_weight,
            max_width, round(height * 0.22), 2, round(width * 0.064), 34, 1.12, tracking)
        sub_item = None
        if subhead:
            sub_size = max(22, round(width * 0.026 * subhead_scale))
            sub_font = load_font(body_font_path, sub_size, body_weight)
            sub_lines = wrap_text(subhead, overlay_draw, sub_font, max_width, max_lines=2)
            sub_item = {"kind": "text", "lines": sub_lines, "font": sub_font, "line_h": round(sub_size * 1.4), "fill": tuple(resolved_text) + (200,)}
        rule_w, rule_h = round(width * 0.052), 4
        gap_rule, gap_sub = round(headline_size * 0.42), round(headline_size * 0.34)
        items = build_block(rule, rule_w, rule_h, tuple(resolved_accent) + (255,), gap_rule, gap_sub,
                            {"kind": "text", "lines": headline_lines, "font": headline_font, "line_h": line_h, "fill": tuple(resolved_text) + (240,), "tracking": tracking}, sub_item)
        height_block = block_height(items)
        top = block_top(position, height_block, safe_top, safe_bottom, height, margin, height - safe_bottom - margin - height_block)
        overlay = Image.alpha_composite(overlay, draw_block((width, height), items, margin, top, align, shadow, shadow_fill))
        summary.update({"headline_size": headline_size, "headline_lines": len(headline_lines), "subhead_lines": len(sub_item["lines"]) if sub_item else 0})

    else:
        align = align or "center"
        tracking = tracking if tracking is not None else 0.0
        headline_font, headline_lines, headline_size, line_h = fit_text(
            headline_text, overlay_draw, headline_font_path, headline_weight,
            max_width, round(height * 0.34), 3, round(width * 0.10), 52, 1.08, tracking)
        sub_item = None
        if subhead:
            sub_size = max(26, round(headline_size * 0.32 * subhead_scale))
            sub_font = load_font(body_font_path, sub_size, body_weight)
            sub_lines = wrap_text(subhead, overlay_draw, sub_font, max_width, max_lines=2)
            sub_item = {"kind": "text", "lines": sub_lines, "font": sub_font, "line_h": round(sub_size * 1.4), "fill": tuple(resolved_text) + (225,)}
        bar_w, bar_h = round(width * 0.055), 6
        gap_bar, gap_sub = round(headline_size * 0.26), round(headline_size * 0.24)
        items = build_block(rule, bar_w, bar_h, tuple(resolved_accent) + (255,), gap_bar, gap_sub,
                            {"kind": "text", "lines": headline_lines, "font": headline_font, "line_h": line_h, "fill": tuple(resolved_text) + (250,), "tracking": tracking}, sub_item)
        height_block = block_height(items)
        top = block_top(position, height_block, safe_top, safe_bottom, height, margin, (height - height_block) / 2)
        overlay = Image.alpha_composite(overlay, draw_block((width, height), items, width // 2, top, align, shadow, shadow_fill))
        summary.update({"headline_size": headline_size, "headline_lines": len(headline_lines), "subhead_lines": len(sub_item["lines"]) if sub_item else 0})

    base = Image.alpha_composite(base, overlay)

    handle = brand.get("handle") if handle is None else handle
    logo = brand.get("logo") if logo is None else logo
    explicit_handle = handle not in (None, "")
    if position == "auto":
        resolved_position = handle_position(layout)
    elif position == "top":
        resolved_position = "bottom-center"
    elif position == "bottom":
        resolved_position = "top-center"
    else:
        resolved_position = handle_position(layout)
    logo_drawn = False
    if logo:
        logo_path = Path(logo)
        if not logo_path.is_absolute():
            logo_path = BASE_DIR / logo_path
        if logo_path.exists():
            logo_drawn = paste_logo(base, logo_path, resolved_position, margin, max(40, round(height * 0.045)))
            summary["logo"] = str(logo_path)
    if logo_drawn:
        if explicit_handle:
            resolved_position = flip_vertical(resolved_position)
        else:
            handle = None
    if handle:
        handle_size = max(24, round(width * 0.028))
        handle_font = load_font(body_font_path, handle_size, body_weight)
        x = width - margin
        y = margin + safe_top
        if "left" in resolved_position:
            x = margin
        elif "center" in resolved_position:
            x = width / 2
        if "bottom" in resolved_position:
            y = height - margin - safe_bottom
        centered = "center" in resolved_position
        layer = draw_text_layer((width, height), [handle], handle_font, handle_size, (x, y), tuple(resolved_text) + (200,), "center" if centered else ("left" if "left" in resolved_position else "right"), 0.4, True, None, shadow_fill)
        base = Image.alpha_composite(base, layer)
        summary["handle"] = handle

    if output:
        target = Path(output)
        if target.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            target = target / f"post-{int(time.time())}.png"
    else:
        target = Path(brand.get("output_dir", "output")) / f"post-{int(time.time())}.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    final = base.convert("RGB")
    final.save(target, "PNG")
    summary.update({
        "ok": True,
        "output": str(target),
        "width": width,
        "height": height,
        "ratio": ratio_name,
        "layout": layout,
        "style": style,
        "rule": rule,
        "accent": rgb_to_hex(resolved_accent),
        "text_color": rgb_to_hex(resolved_text),
        "scrim": scrim,
        "safe_zone": safe,
    })
    if jpeg:
        jpeg_target = target.with_suffix(".jpg")
        final.save(jpeg_target, "JPEG", quality=jpeg_quality)
        summary["jpeg"] = str(jpeg_target)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="Background image path")
    parser.add_argument("--headline", required=True, help="Main hook text")
    parser.add_argument("--subhead", default=None)
    parser.add_argument("--handle", default=None, help="Handle/watermark; pass '' to disable")
    parser.add_argument("--logo", default=None, help="Logo path; pass '' to disable")
    parser.add_argument("--ratio", choices=list(RATIOS), default=None)
    parser.add_argument("--size", default=None, help="Custom WxH canvas, overrides --ratio")
    parser.add_argument("--layout", choices=LAYOUTS, default=None)
    parser.add_argument("--position", choices=["auto", "top", "center", "bottom"], default="auto")
    parser.add_argument("--scrim", type=int, default=None)
    parser.add_argument("--accent", default=None, help="auto or #hex")
    parser.add_argument("--accent-strength", type=int, default=78)
    parser.add_argument("--text-color", default=None, help="auto or #hex")
    parser.add_argument("--style", choices=list(STYLES), default="modern")
    parser.add_argument("--align", choices=["left", "center"], default=None)
    parser.add_argument("--tracking", type=float, default=None)
    parser.add_argument("--uppercase", action="store_true")
    parser.add_argument("--no-shadow", action="store_true")
    parser.add_argument("--focus", default="0.5,0.45")
    parser.add_argument("--safe-zone", action="store_true")
    parser.add_argument("--headline-font", default=None)
    parser.add_argument("--body-font", default=None)
    parser.add_argument("--brand", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--jpeg", action="store_true")
    parser.add_argument("--jpeg-quality", type=int, default=92)
    parser.add_argument("--card-alpha", type=int, default=None, help="0-100 background card opacity for centered-card")
    parser.add_argument("--card-color", default=None, help="#hex card color")
    parser.add_argument("--tint", default=None, help="auto or #hex full-image color wash")
    parser.add_argument("--tint-alpha", type=int, default=0, help="0-100 tint strength")
    parser.add_argument("--rule", choices=list(RULES), default=None, help="accent divider: none, above or below the headline")
    parser.add_argument("--subhead-scale", type=float, default=1.0)
    args = parser.parse_args()
    options = vars(args)
    options["shadow"] = not options.pop("no_shadow")
    options["brand_path"] = options.pop("brand")
    try:
        summary = compose(**options)
    except ComposeError as error:
        print(json.dumps({"ok": False, "error": str(error)}, indent=2))
        raise SystemExit(1)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
