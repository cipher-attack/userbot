import os
import asyncio
import re
import random
import time
from telethon import events
from config import Config
from core.utils import safe_register

# deps
try:
    import edge_tts
    HAS_TTS = True
except ImportError:
    HAS_TTS = False

class VoiceConfig:
    # am
    AM_MALE = "am-ET-AmehaNeural"
    AM_FEMALE = "am-ET-MekdesNeural"
    # en
    EN_MALE = "en-US-GuyNeural"
    EN_FEMALE = "en-US-JennyNeural"
    DEFAULT_LANG = "am"
    DEFAULT_GENDER = "m" 

# fx
async def apply_audio_effects(input_file, output_file, effects):
    if not effects:
        cmd = f'ffmpeg -i "{input_file}" -c:a libopus "{output_file}" -y'
    else:
        filters = []
        if "echo" in effects: filters.append("aecho=0.8:0.9:1000:0.3")
        if "radio" in effects: filters.append("highpass=f=200,lowpass=f=3000")
        if "demon" in effects: filters.append("asetrate=44100*0.8,aresample=44100") 
        if "kid" in effects: filters.append("asetrate=44100*1.25,aresample=44100") 
        if "fast" in effects: filters.append("atempo=1.5") 
        if "slow" in effects: filters.append("atempo=0.7") 

        filter_str = ",".join(filters)
        cmd = f'ffmpeg -i "{input_file}" -af "{filter_str}" -c:a libopus -b:a 64k "{output_file}" -y'

    process = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
    )
    await process.communicate()

# lang det
def detect_language(text):
    if re.search(r'[\u1200-\u137F]', text): return "am"
    return "en"

# flags
def parse_command(text):
    options = { "gender": None, "effects": [] }
    flags = {
        r'\.f\b': ('gender', 'f'),
        r'\.m\b': ('gender', 'm'),
        r'\.echo\b': ('effect', 'echo'),
        r'\.radio\b': ('effect', 'radio'),
        r'\.demon\b': ('effect', 'demon'),
        r'\.kid\b': ('effect', 'kid'),
        r'\.fast\b': ('effect', 'fast'),
        r'\.slow\b': ('effect', 'slow'),
    }
    clean_text = text
    for pattern, (type_, value) in flags.items():
        if re.search(pattern, clean_text, re.IGNORECASE):
            if type_ == 'gender': options['gender'] = value
            elif type_ == 'effect': options['effects'].append(value)
            clean_text = re.sub(pattern, '', clean_text, flags=re.IGNORECASE)

    return clean_text.strip(), options

# main tts
@safe_register(r"^\.say (.*)")
async def voice_master_engine(event, text_override=None):
    if not HAS_TTS: return await event.edit("❌ edge-tts missing")

    raw_text = text_override if text_override else event.pattern_match.group(1)

    if len(raw_text) > 500:
        return await event.edit("❌ <b>Text too long!</b> Max 500 chars.", parse_mode='html')

    text, options = parse_command(raw_text)

    if not text:
        return await event.edit("❌ Usage: .say [flags] text")

    await event.edit(f"🎙️ <b>Recording...</b>", parse_mode='html')

    lang = detect_language(text)
    gender = options['gender'] or VoiceConfig.DEFAULT_GENDER

    voice = ""
    if lang == "am":
        voice = VoiceConfig.AM_FEMALE if gender == 'f' else VoiceConfig.AM_MALE
    else:
        voice = VoiceConfig.EN_FEMALE if gender == 'f' else VoiceConfig.EN_MALE

    temp_raw = f"raw_{event.id}.mp3"
    temp_final = f"voice_{event.id}.ogg"

    try:
        # gen
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(temp_raw)

        await event.edit("🎛️ <b>Mastering...</b>", parse_mode='html')
        await apply_audio_effects(temp_raw, temp_final, options['effects'])

        # upload
        await event.edit("⬆️ <b>Uploading...</b>", parse_mode='html')
        await event.client.send_file(
            event.chat_id,
            temp_final,
            voice_note=True, 
            reply_to=event.reply_to_msg_id
        )
        await event.delete() 

    except Exception as e:
        await event.edit(f"❌ Error: {str(e)}", parse_mode='html')

    finally:
        # clean
        if os.path.exists(temp_raw): os.remove(temp_raw)
        if os.path.exists(temp_final): os.remove(temp_final)

@safe_register(r"^\.yell (.*)")
async def yell_mode(event):
    text = event.pattern_match.group(1)
    new_text = f"{text}!"
    await voice_master_engine(event, text_override=new_text) 

@safe_register(r"^\.whisper (.*)")
async def whisper_mode(event):
    text = event.pattern_match.group(1)
    new_text = f".slow {text}"
    await voice_master_engine(event, text_override=new_text)