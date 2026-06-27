import os
import io
import requests
import textwrap
import re
from telethon import events
from PIL import Image, ImageDraw, ImageFont
from core.utils import safe_register

# libs
try:
    from pilmoji import Pilmoji
    from pilmoji.source import GoogleEmojiSource
    PILMOJI_AVAILABLE = True
except ImportError:
    PILMOJI_AVAILABLE = False
    print("missing pilmoji")

# setup dirs
FONTS_DIR = "resources/global_fonts"
if not os.path.exists(FONTS_DIR):
    os.makedirs(FONTS_DIR)

# font config
FONT_DEFINITIONS = {
    "ethiopic": {
        "url": "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansEthiopic/NotoSansEthiopic-Bold.ttf",
        "path": os.path.join(FONTS_DIR, "ethiopic_bold.ttf"),
        "regex": r'[\u1200-\u137F]'
    },
    "arabic": {
        "url": "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansArabic/NotoSansArabic-Bold.ttf",
        "path": os.path.join(FONTS_DIR, "arabic_bold.ttf"),
        "regex": r'[\u0600-\u06FF\u0750-\u077F]'
    },
    "devanagari": { 
        "url": "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansDevanagari/NotoSansDevanagari-Bold.ttf",
        "path": os.path.join(FONTS_DIR, "hindi_bold.ttf"),
        "regex": r'[\u0900-\u097F]'
    },
    "chinese": { 
        "url": "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Bold.otf",
        "path": os.path.join(FONTS_DIR, "chinese_bold.otf"),
        "regex": r'[\u4E00-\u9FFF]'
    },
    "cyrillic": { 
        "url": "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSans/NotoSans-Bold.ttf",
        "path": os.path.join(FONTS_DIR, "global_bold.ttf"),
        "regex": r'[\u0400-\u04FF]'
    },
    "latin": { 
        "url": "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSans/NotoSans-Bold.ttf",
        "path": os.path.join(FONTS_DIR, "global_bold.ttf"),
        "regex": r'[a-zA-Z0-9\s\.\,\!\?]'
    }
}

# dl fonts
def ensure_fonts_exist():
    for lang, data in FONT_DEFINITIONS.items():
        if not os.path.exists(data["path"]):
            try:
                r = requests.get(data["url"], timeout=30)
                with open(data["path"], 'wb') as f:
                    f.write(r.content)
            except Exception as e:
                pass

ensure_fonts_exist()

# lang detect
def detect_script(char):
    for lang, data in FONT_DEFINITIONS.items():
        if lang == "latin": continue 
        if re.match(data["regex"], char):
            return lang
    return "latin"

# split text by lang
def get_smart_segments(text, font_size):
    loaded_fonts = {}
    try:
        for lang, data in FONT_DEFINITIONS.items():
            if os.path.exists(data["path"]):
                loaded_fonts[lang] = ImageFont.truetype(data["path"], font_size)
            else:
                loaded_fonts[lang] = ImageFont.load_default()
    except:
        pass 

    segments = []
    current_text = ""
    current_lang = None

    # heavy loop but needed
    for char in text:
        char_lang = detect_script(char)

        if char == " " and current_lang:
            char_lang = current_lang

        if char_lang != current_lang:
            if current_text:
                segments.append({
                    "text": current_text,
                    "font": loaded_fonts.get(current_lang, loaded_fonts["latin"]),
                    "lang": current_lang
                })
            current_text = char
            current_lang = char_lang
        else:
            current_text += char

    if current_text:
        segments.append({
            "text": current_text,
            "font": loaded_fonts.get(current_lang, loaded_fonts["latin"]),
            "lang": current_lang
        })

    return segments

# calc dims
def measure_segments(segments, dummy_draw):
    total_width = 0
    max_height = 0
    for seg in segments:
        bbox = dummy_draw.textbbox((0, 0), seg["text"], font=seg["font"])
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        seg["width"] = w
        seg["height"] = h
        total_width += w
        if h > max_height: max_height = h
    return total_width, max_height

# main drawer
def draw_world_text(img, text, y_pos, is_bottom=False):
    width, height = img.size
    draw = ImageDraw.Draw(img)

    # auto size
    font_size = int(width / 11) 
    if font_size < 24: font_size = 24

    avg_char_width = font_size * 0.6
    max_chars = int((width * 0.95) / avg_char_width)
    lines = textwrap.wrap(text, width=max_chars)

    processed_lines = []
    total_block_height = 0

    for line in lines:
        segs = get_smart_segments(line, font_size)
        w, h = measure_segments(segs, draw)
        processed_lines.append({"segments": segs, "width": w, "height": h})
        total_block_height += h + 15

    current_y = y_pos
    if is_bottom:
        current_y = height - total_block_height - 30

    # render
    if PILMOJI_AVAILABLE:
        with Pilmoji(img, source=GoogleEmojiSource) as pilmoji:
            for line_data in processed_lines:
                current_x = (width - line_data["width"]) / 2

                for seg in line_data["segments"]:
                    # shadow
                    shadow_color = "black"
                    for ox in [-2, 0, 2]:
                        for oy in [-2, 0, 2]:
                            if ox==0 and oy==0: continue
                            pilmoji.text((current_x+ox, current_y+oy), seg["text"], font=seg["font"], fill=shadow_color, emoji_scale_factor=1.2)

                    # text
                    pilmoji.text((current_x, current_y), seg["text"], font=seg["font"], fill="white", emoji_scale_factor=1.2)
                    current_x += seg["width"]

                current_y += line_data["height"] + 15
    else:
        # fallback
        for line_data in processed_lines:
            current_x = (width - line_data["width"]) / 2
            for seg in line_data["segments"]:
                draw.text((current_x, current_y), seg["text"], font=seg["font"], fill="white", stroke_width=3, stroke_fill="black")
                current_x += seg["width"]
            current_y += line_data["height"] + 15

# sticker stealer
@safe_register(r"^\.kang")
async def kang_sticker(event):
    reply = await event.get_reply_message()
    if not reply or not reply.media: return await event.edit("❌ Reply to a photo!")

    if hasattr(reply.media, 'ttl_seconds') and reply.media.ttl_seconds:
        return await event.edit("❌ <b>Security:</b> View-Once blocked.")

    # size check
    if reply.file.size > 5 * 1024 * 1024:
        return await event.edit("❌ <b>Too Big:</b> File > 5MB", parse_mode='html')

    await event.edit("🎭 <b>Kang...</b>", parse_mode='html')
    try:
        image = await reply.download_media(file=bytes)
        f = io.BytesIO(image)
        f.name = "sticker.webp"
        await event.client.send_file(event.chat_id, f, reply_to=reply.id)
        await event.delete()
    except Exception as e: await event.edit(f"❌ Error: {e}")

# meme gen
@safe_register(r"^\.meme (.*)")
async def meme_engine(event):
    text_input = event.pattern_match.group(1)
    reply = await event.get_reply_message()

    if not reply or not reply.media:
        return await event.edit("❌ Reply to a photo!")

    if hasattr(reply.media, 'ttl_seconds') and reply.media.ttl_seconds:
        return await event.edit("❌ <b>Security:</b> View-Once blocked.")

    if ";" in text_input:
        parts = text_input.split(";", 1)
        top_text = parts[0].strip()
        bottom_text = parts[1].strip()
    else:
        top_text = text_input.strip()
        bottom_text = ""

    await event.edit("🌍 <b>World Engine Processing...</b>", parse_mode='html')

    photo_path = None
    try:
        photo_path = await reply.download_media()
        img = Image.open(photo_path).convert("RGBA")

        if top_text:
            draw_world_text(img, top_text, 10, is_bottom=False)
        if bottom_text:
            draw_world_text(img, bottom_text, 0, is_bottom=True)

        img = img.convert("RGB")
        out = io.BytesIO()
        img.save(out, format='JPEG', quality=95)
        out.seek(0)
        out.name = "meme_world.jpg"

        await event.client.send_file(
            event.chat_id,
            out,
            reply_to=reply.id
        )
        await event.delete()

    except Exception as e:
        import traceback
        traceback.print_exc()
        await event.edit(f"❌ <b>Global Error:</b> {e}")

    finally:
        if photo_path and os.path.exists(photo_path):
            os.remove(photo_path)