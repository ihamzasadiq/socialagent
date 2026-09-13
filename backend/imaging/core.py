#!/usr/bin/env python3
"""OpenRouter client: LLM copywriting + image generation for the social post app."""

import base64
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CHAT_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
IMAGES_ENDPOINT = "https://openrouter.ai/api/v1/images"
TAVILY_ENDPOINT = "https://api.tavily.com/search"
EXT_BY_MEDIA_TYPE = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/svg+xml": ".svg"}
DEFAULT_TEXT_MODEL = "deepseek/deepseek-v4-flash"
DEFAULT_IMAGE_MODEL = "google/gemini-3.1-flash-image"
DEFAULT_VISION_MODEL = "google/gemini-3.1-flash-lite"
VISION_MODELS = {
    "google/gemini-3.8-flash",
    "google/gemini-3.1-flash-lite",
    "google/gemini-3.1-flash-lite-preview",
    "qwen/qwen3.8-flash",
    "openai/gpt-5-mini",
    "openai/gpt-5-nano",
    "inclusionai/ling-3.0-flash-vl",
    "deepseek/deepseek-v4-flash-vision-exp",
}
REFERENCE_MODELS = {
    "google/gemini-3.1-flash-image",
    "google/gemini-3.1-flash-image-preview",
    "google/gemini-2.5-flash-image",
    "google/gemini-3-pro-image",
    "google/gemini-3-pro-image-preview",
}
LAYOUT_WORDS = {
    "bold-bottom": "large headline anchored toward the bottom",
    "centered-card": "centered text layout",
    "minimal-corner": "small text block in a corner",
    "full-gradient": "bold color-washed full-bleed design",
}
STYLE_WORDS = {
    "modern": "bold geometric sans-serif typography",
    "editorial": "elegant high-contrast serif typography",
    "minimal": "clean understated sans-serif typography",
}
MODEL_RATIO_OVERRIDES = {
    "black-forest-labs/flux.2-klein-4b": {"4:5": "3:4"},
}

COPY_SYSTEM = (
    "You are an expert social media art director and copywriter. "
    "Respond with a single JSON object and nothing else. Keys: "
    "image_prompt (string), headline (string), subhead (string), caption (string), "
    "hashtags (array of strings), alt_text (string). Rules: "
    "image_prompt is an English art-direction prompt for a text-to-image model: subject, setting, "
    "style, lighting, color mood, camera/composition; reserve clean negative space where a headline "
    "can be placed; never include text, words, letters, watermarks or logos in the image. "
    "headline: max 6 words, punchy, no trailing period. "
    "subhead: max 10 words, adds information, never repeats the headline. "
    "caption: a scroll-stopping hook sentence, then 1-3 short paragraphs, then a call to action, "
    "as plain text with \\n line breaks. "
    "hashtags: 5-12 short tags without the # symbol. "
    "alt_text: under 125 characters, describes the image, no hashtags."
)

DESIGN_SYSTEM = (
    " A reference image is provided: copy the same style as the image referenced. Also include a "
    "\"design\" object describing how to style the "
    "finished post so it matches the reference image's design language (typography character, layout "
    "structure, palette). Keys: "
    "layout (one of bold-bottom, centered-card, minimal-corner, full-gradient), "
    "style (one of modern, editorial, minimal: serif or elegant -> editorial, bold geometric sans -> "
    "modern, clean understated -> minimal), "
    "accent (#RRGGBB distinctive color from the reference used for rules/bars, avoid black/white/gray), "
    "text_color (#RRGGBB of the TEXT/foreground in the reference, NOT the background; if the reference "
    "shows light text on a dark background return a light color; it must stay readable over the scrim), "
    "scrim (0-100 overlay darkness), "
    "card_alpha (0-100 opacity of a card/panel behind the text; use 0 when the reference puts text directly "
    "on the image with no card), "
    "tint (#RRGGBB dominant background color of the reference to wash the photo with, or null when there is "
    "no strong color cast), tint_alpha (0-60 strength of that wash), "
    "rule (none, above or below: where the accent divider sits relative to the headline), "
    "align (left or center), subhead_scale (0.7-1.3 relative subhead size), "
    "position (one of auto, top, center, bottom), uppercase (true/false), "
    "tracking (letter spacing in px between -2 and 12), accent_strength (0-100). "
    "If the reference contains text, never copy its wording; write fresh copy for the topic. "
    "The image_prompt must describe a new background inspired by the reference's visual style and "
    "subject, and must not contain text, words, letters, watermarks or logos."
)


class CoreError(Exception):
    pass


def _env_value(name):
    value = os.environ.get(name)
    if value:
        return value.strip()
    candidates = (
        BASE_DIR.parent / ".env",  # backend/.env — the app's single config file
        BASE_DIR / ".env",  # optional imaging-local override
        Path.home() / ".config" / "opencode" / ".env",
    )
    for path in candidates:
        try:
            for line in path.read_text().splitlines():
                line = line.strip()
                if line.startswith(f"{name}="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            continue
    return None


def load_api_key():
    key = _env_value("OPENROUTER_API_KEY")
    if not key:
        raise CoreError("OPENROUTER_API_KEY not found in environment or .env")
    return key


def load_tavily_key():
    key = _env_value("TAVILY_API_KEY")
    if not key:
        raise CoreError("TAVILY_API_KEY not found in environment or .env")
    return key


def load_brand():
    try:
        return json.loads((BASE_DIR / "brand.json").read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _request(url, payload, api_key, timeout=300, retries=2):
    last_error = "unknown error"
    for attempt in range(retries + 1):
        request = urllib.request.Request(url, method="POST")
        request.add_header("Authorization", f"Bearer {api_key}")
        request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, data=json.dumps(payload).encode(), timeout=timeout) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")[:800]
            last_error = f"HTTP {error.code}: {detail}"
            if error.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            raise CoreError(last_error)
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = str(error)
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            raise CoreError(last_error)
    raise CoreError(last_error)


def _parse_json_object(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise CoreError("model did not return JSON")
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as error:
        raise CoreError(f"could not parse model JSON: {error}")


def complete_json(
    system: str,
    user_text: str,
    *,
    model: str | None = None,
    temperature: float = 0.8,
    timeout: int = 180,
    image_url: str | None = None,
) -> dict:
    """One chat completion that must return a JSON object.

    Public entry point reused by templates/generate.py — keeps the OpenRouter
    request/parse/retry logic in a single place. When ``image_url`` (a data
    URL) is given, the call becomes multimodal and defaults to the brand's
    vision model; used for the reference-image style pass.
    """
    brand = load_brand()
    if model:
        chosen = model
    elif image_url:
        chosen = brand.get("vision_model") or DEFAULT_VISION_MODEL
    else:
        chosen = brand.get("text_model") or DEFAULT_TEXT_MODEL
    if image_url:
        user_content: object = [
            {"type": "text", "text": user_text},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]
    else:
        user_content = user_text
    payload = {
        "model": chosen,
        "temperature": temperature,
        "usage": {"include": True},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
    }
    result = _request(CHAT_ENDPOINT, payload, load_api_key(), timeout=timeout)
    choices = result.get("choices") or []
    if not choices:
        raise CoreError("model returned no choices")
    parsed = _parse_json_object(choices[0].get("message", {}).get("content", ""))
    parsed["_model"] = chosen
    parsed["_cost_usd"] = (result.get("usage") or {}).get("cost")
    return parsed


def extract_design(parsed: dict) -> dict | None:
    """Public wrapper around the design-token cleaning/contrast logic."""
    design = _clean_design(parsed.get("design"))
    return _ensure_contrast(design) if design else None


def _clean_hashtag(tag):
    tag = str(tag).strip().lstrip("#").strip()
    return re.sub(r"\s+", "", tag)


def _clean_design(design):
    if not isinstance(design, dict):
        return None
    cleaned = {}
    if design.get("layout") in ("bold-bottom", "centered-card", "minimal-corner", "full-gradient"):
        cleaned["layout"] = design["layout"]
    if design.get("style") in ("modern", "editorial", "minimal"):
        cleaned["style"] = design["style"]
    if design.get("position") in ("auto", "top", "center", "bottom"):
        cleaned["position"] = design["position"]
    for key in ("accent", "text_color", "tint"):
        value = str(design.get(key, "") or "").strip()
        if re.fullmatch(r"#?[0-9a-fA-F]{6}", value):
            cleaned[key] = value if value.startswith("#") else "#" + value
    for key in ("scrim", "accent_strength", "card_alpha", "tint_alpha"):
        try:
            cleaned[key] = max(0, min(100, int(design.get(key))))
        except (TypeError, ValueError):
            pass
    if design.get("rule") in ("none", "above", "below"):
        cleaned["rule"] = design["rule"]
    if design.get("align") in ("left", "center"):
        cleaned["align"] = design["align"]
    if isinstance(design.get("uppercase"), bool):
        cleaned["uppercase"] = design["uppercase"]
    try:
        cleaned["tracking"] = max(-2.0, min(12.0, float(design.get("tracking"))))
    except (TypeError, ValueError):
        pass
    try:
        cleaned["subhead_scale"] = max(0.6, min(1.4, float(design.get("subhead_scale"))))
    except (TypeError, ValueError):
        pass
    return cleaned or None


def _hex_luminance(value):
    value = value.lstrip("#")
    r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _ensure_contrast(design):
    text = design.get("text_color")
    if not text:
        return design
    layout = design.get("layout") or "bold-bottom"
    scrim = design.get("scrim")
    card_alpha = design.get("card_alpha")
    tint = design.get("tint")
    tint_alpha = design.get("tint_alpha") or 0
    dark_backdrop = False
    if layout == "centered-card":
        dark_backdrop = card_alpha is None or card_alpha >= 40
    elif layout in ("bold-bottom", "full-gradient"):
        dark_backdrop = scrim is None or scrim >= 45
    if tint and tint_alpha >= 30 and _hex_luminance(tint) < 100:
        dark_backdrop = True
    if dark_backdrop and _hex_luminance(text) < 150:
        design["text_color"] = "#FFFFFF"
    return design


def search_topic_images(query, max_results=5, timeout=45):
    payload = {
        "query": query,
        "search_depth": "basic",
        "include_images": True,
        "include_image_descriptions": True,
        "max_results": max_results,
    }
    key = load_tavily_key()
    result = _request(TAVILY_ENDPOINT, payload, key, timeout=timeout)
    images = []
    for item in result.get("images") or []:
        if isinstance(item, dict):
            url = str(item.get("url") or "").strip()
            description = str(item.get("description") or "").strip()
        else:
            url = str(item or "").strip()
            description = ""
        if re.match(r"^https?://", url):
            images.append({"url": url, "description": description})

    def rank(image):
        if re.search(r"\.(jpe?g|png|webp)(\?|$)", image["url"], re.I):
            return 0
        return 1

    images.sort(key=rank)
    results = []
    for item in result.get("results") or []:
        if isinstance(item, dict):
            results.append({
                "title": str(item.get("title") or "").strip(),
                "url": str(item.get("url") or "").strip(),
                "content": str(item.get("content") or "").strip()[:400],
            })
    return {"query": query, "images": images, "results": results}


def _image_media_type(data):
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"GIF8"):
        return "image/gif"
    return None


def fetch_image_as_data_url(url, max_bytes=12 * 1024 * 1024, timeout=45):
    request = urllib.request.Request(url)
    request.add_header("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36")
    request.add_header("Accept", "image/*,*/*;q=0.8")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read(max_bytes + 1)
        media_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if len(data) > max_bytes:
        raise CoreError(f"image at {url} is larger than {max_bytes // (1024 * 1024)}MB")
    if media_type not in EXT_BY_MEDIA_TYPE:
        media_type = _image_media_type(data)
    if media_type not in ("image/png", "image/jpeg", "image/webp"):
        try:
            import io

            from PIL import Image

            with Image.open(io.BytesIO(data)) as image:
                converted = io.BytesIO()
                image.convert("RGB").save(converted, format="PNG")
                data = converted.getvalue()
                media_type = "image/png"
        except Exception as error:
            raise CoreError(f"could not decode image at {url}: {error}")
    encoded = base64.b64encode(data).decode()
    return {"data_url": f"data:{media_type};base64,{encoded}", "media_type": media_type, "bytes": len(data)}


def with_scene_reference(prompt):
    return (
        f"{prompt}\n\n"
        "Use the attached web reference photo as guidance for the subject, setting and mood of the scene. "
        "Do not copy any text, words, letters, watermarks or logos from it."
    )


def write_copy(topic, tone="bold", ratio="4:5", model=None, reference=None):
    brand = load_brand()
    has_reference = bool(reference)
    if has_reference:
        chosen = model if model in VISION_MODELS else (brand.get("vision_model") or DEFAULT_VISION_MODEL)
    else:
        chosen = model or brand.get("text_model") or DEFAULT_TEXT_MODEL
    system = COPY_SYSTEM + (DESIGN_SYSTEM if has_reference else "")
    user_text = f"Topic: {topic}\nTone: {tone}\nFormat: {ratio} social media post."
    if has_reference:
        content = [
            {"type": "text", "text": user_text},
            {"type": "image_url", "image_url": {"url": reference}},
        ]
    else:
        content = user_text
    payload = {
        "model": chosen,
        "temperature": 0.8,
        "usage": {"include": True},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
    }
    result = _request(CHAT_ENDPOINT, payload, load_api_key(), timeout=120)
    choices = result.get("choices") or []
    if not choices:
        raise CoreError("model returned no choices")
    parsed = _parse_json_object(choices[0].get("message", {}).get("content", ""))
    hashtags = parsed.get("hashtags") or []
    if isinstance(hashtags, str):
        hashtags = re.split(r"[\s,]+", hashtags)
    parsed["hashtags"] = [_clean_hashtag(tag) for tag in hashtags if _clean_hashtag(tag)]
    for key in ("image_prompt", "headline", "subhead", "caption", "alt_text"):
        parsed[key] = str(parsed.get(key, "")).strip()
    design = _clean_design(parsed.get("design")) if has_reference else None
    parsed["design"] = _ensure_contrast(design) if design else None
    parsed["text_model"] = chosen
    parsed["cost_usd"] = (result.get("usage") or {}).get("cost")
    return parsed


def build_reference_prompt(topic, tone, ratio, copy, design, handle, scene_ref=False):
    lines = [
        f"Create a finished {ratio} social media post image about: {topic}.",
        "Copy the same style as the image referenced: match its typography style, color palette, layout "
        "structure and graphic accents so the new post looks like part of the same brand system. Do not "
        "reuse its wording.",
    ]
    if scene_ref:
        lines.append(
            "The guide image attached after the style reference is a real photo found online about the topic. "
            "Use its subject, setting and mood as the basis for the new background; copy its scene style, not "
            "any text or watermark."
        )
    else:
        lines.append(
            "Do NOT reuse the reference's background, scene, subjects or its text. Invent a completely new "
            "background that suits the topic."
        )
    if copy.get("image_prompt"):
        lines.append(f"Background scene to create: {copy['image_prompt']}")
    style_bits = []
    if design:
        if design.get("style") in STYLE_WORDS:
            style_bits.append(STYLE_WORDS[design["style"]])
        if design.get("layout") in LAYOUT_WORDS:
            style_bits.append(LAYOUT_WORDS[design["layout"]])
        if design.get("align"):
            style_bits.append(f"{design['align']}-aligned text")
        if design.get("accent"):
            style_bits.append(f"accent color {design['accent']}")
        if design.get("text_color"):
            style_bits.append(f"text color {design['text_color']}")
        card = design.get("card_alpha")
        if card == 0:
            style_bits.append("no card or panel behind the text")
        elif card:
            style_bits.append("translucent card behind the text")
        if design.get("tint") and (design.get("tint_alpha") or 0) > 0:
            style_bits.append(f"a subtle {design['tint']} color wash over the photo")
        rule = design.get("rule")
        if rule == "above":
            style_bits.append("thin accent divider above the headline")
        elif rule == "below":
            style_bits.append("thin accent divider below the headline")
        elif rule == "none":
            style_bits.append("no divider")
        if design.get("uppercase"):
            style_bits.append("uppercase headline")
    if style_bits:
        lines.append("Style notes: " + "; ".join(style_bits) + ".")
    lines.append("Render this text exactly, correctly spelled, sharp and legible with generous safe margins:")
    if copy.get("headline"):
        lines.append(f'Headline: "{copy["headline"]}"')
    if copy.get("subhead"):
        lines.append(f'Subhead: "{copy["subhead"]}"')
    if handle:
        lines.append(f'Small corner watermark: "{handle}"')
    lines.append(f"Tone: {tone}. Do not add any other words, letters or gibberish text anywhere.")
    return "\n".join(lines)


def generate_image(prompt, output_path, model=None, aspect_ratio="4:5", resolution=None, quality=None, reference=None, references=None, timeout=300):
    brand = load_brand()
    model = model or brand.get("image_model") or DEFAULT_IMAGE_MODEL
    ratio = aspect_ratio or "4:5"
    override = MODEL_RATIO_OVERRIDES.get(model, {}).get(ratio)
    ratio_used = override or ratio
    ratio_note = f"model does not support {ratio}; used {ratio_used}" if override else None
    payload = {"model": model, "prompt": prompt}
    if ratio_used and ratio_used != "auto":
        payload["aspect_ratio"] = ratio_used
    if resolution:
        payload["resolution"] = resolution
    if quality:
        payload["quality"] = quality
    all_references = [ref for ref in ([reference] if reference else []) + list(references or []) if ref]
    if all_references:
        payload["input_references"] = [{"type": "image_url", "image_url": {"url": ref}} for ref in all_references]
    try:
        result = _request(IMAGES_ENDPOINT, payload, load_api_key(), timeout=timeout)
    except CoreError as error:
        if "aspect_ratio" in str(error) and "aspect_ratio" in payload:
            payload.pop("aspect_ratio")
            ratio_note = f"{ratio_used} rejected by provider; let the model choose and cropped to {ratio}"
            result = _request(IMAGES_ENDPOINT, payload, load_api_key(), timeout=timeout)
        else:
            raise
    items = result.get("data") or []
    if not items:
        raise CoreError("no images returned")
    item = items[0]
    encoded = item.get("b64_json")
    if not encoded:
        raise CoreError("response contained no image data")
    target = Path(output_path)
    ext = EXT_BY_MEDIA_TYPE.get(item.get("media_type", ""), target.suffix or ".png")
    if target.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
        target = target.with_suffix(ext)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(base64.b64decode(encoded))
    usage = result.get("usage") or {}
    return {
        "path": str(target),
        "model": model,
        "ratio": ratio,
        "ratio_note": ratio_note,
        "cost_usd": usage.get("cost"),
    }
