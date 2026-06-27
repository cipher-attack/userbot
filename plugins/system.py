import sys
import os
import time
import asyncio
import json
import random
import logging
from collections import deque
from datetime import datetime
from telethon import events
from config import Config
from core.utils import safe_register

# init
logging.basicConfig(
    format='%(asctime)s - [INFINITY+] - %(levelname)s - %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("InfinityPlus")

START_TIME = datetime.now()
CONFIG_FILE = "infinity_plus_config.json"

try:
    import google.generativeai as genai
    HAS_AI = True
except ImportError:
    HAS_AI = False
    logger.critical("❌ google-generativeai missing")

# db
class InfinityDatabase:
    def __init__(self):
        self.filename = CONFIG_FILE
        self.db = self._load_db()

    def _load_db(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"DB Load Error: {e}")

        return {
            "system_status": "off",      
            "context_mode": "default",   
            "static_message": "🤖 I'm unavailable. Message saved.",
            "vip_list": [],              
            "blacklist": [],             
            "cooldowns": {},             
            "metrics": {"total_replies": 0, "ai_errors": 0}
        }

    def save(self):
        try:
            with open(self.filename, "w") as f:
                json.dump(self.db, f, indent=4)
        except Exception: pass

    def get(self, key):
        return self.db.get(key)

    def set(self, key, value):
        self.db[key] = value
        self.save()

    def update_metric(self, metric):
        if metric in self.db["metrics"]:
            self.db["metrics"][metric] += 1
            self.save()

DB = InfinityDatabase()

# ai
class NeuralEngine:
    def __init__(self):
        self.api_keys = [k for k in Config.GEMINI_KEYS if k]
        self.current_key_index = 0
        self.request_timestamps = []

        self.chat_memory = {}

        self.models = [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-3.1-flash-lite-preview",
            "gemini-2.0-flash",
            "gemini-1.5-flash-8b"
        ]

    def _check_rpm(self):
        now = time.time()
        self.request_timestamps = [t for t in self.request_timestamps if now - t < 60]
        if len(self.request_timestamps) >= 14:
            return 60 - (now - self.request_timestamps[0]) + 1
        return 0

    def _update_memory(self, user_id, role, text):
        if user_id not in self.chat_memory:
            self.chat_memory[user_id] = deque(maxlen=4) 
        self.chat_memory[user_id].append(f"{role}: {text}")

    async def generate_response(self, user_id, user_msg, context_mode):
        if not HAS_AI or not self.api_keys: return None

        # limit
        wait = self._check_rpm()
        if wait > 0: await asyncio.sleep(wait)

        history = ""
        if user_id in self.chat_memory:
            history = "\n".join(list(self.chat_memory[user_id]))

        personas = {
            "sleep": "STATUS: Sleeping. Reply lazily.",
            "work": "STATUS: Working. Reply professionally but short.",
            "gaming": "STATUS: Gaming. Reply annoyed/short.",
            "default": "STATUS: Busy. Reply friendly."
        }

        system_prompt = f"""
        YOU ARE A REAL USER (HUMAN). NOT AN AI.
        {personas.get(context_mode, personas['default'])}
        
        CONVERSATION HISTORY:
        {history}
        
        CURRENT MESSAGE: "{user_msg}"
        
        INSTRUCTIONS:
        - Reply to the CURRENT MESSAGE naturally.
        - Keep the flow of conversation.
        - Short (1-2 sentences). Lowercase preferred.
        - NEVER say "I am an AI".
        """

        # rotate
        key = self.api_keys[self.current_key_index]
        genai.configure(api_key=key)

        for model_name in self.models:
            try:
                model = genai.GenerativeModel(model_name)
                response = await asyncio.to_thread(
                    model.generate_content,
                    system_prompt
                )

                if response.text:
                    self.request_timestamps.append(time.time())
                    self._update_memory(user_id, "User", user_msg)
                    self._update_memory(user_id, "You", response.text)
                    return response.text

            except Exception as e:
                err = str(e)
                if "429" in err or "Quota" in err:
                    if self.api_keys:
                        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
                        genai.configure(api_key=self.api_keys[self.current_key_index])
                    continue
                continue

        return None

AI = NeuralEngine()

# sim
async def simulate_human_presence(event, reply_text):
    chat_id = event.chat_id

    await asyncio.sleep(random.randint(1, 3))

    await event.client.send_read_acknowledge(chat_id)

    char_count = len(reply_text)
    typing_time = min(char_count / 6, 5) 
    if typing_time < 1: typing_time = 1

    async with event.client.action(chat_id, 'typing'):
        await asyncio.sleep(typing_time)
        await event.reply(reply_text)

    # metrics
    DB.update_metric("total_replies")

# cmds

@safe_register(r"^\.ping")
async def ping_cmd(event):
    start = datetime.now()
    msg = await event.edit("`📶 Ping...`")
    end = datetime.now()
    ms = (end - start).microseconds / 1000

    status = DB.get("system_status")
    replies = DB.get("metrics")['total_replies']

    text = (
        f"<b>♾️ INFINITY PLUS v10</b>\n"
        f"════════════════\n"
        f"📶 <b>Ping:</b> `{ms}ms`\n"
        f"🤖 <b>Auto:</b> `{status.upper()}`\n"
        f"💬 <b>Replies:</b> `{replies}`\n"
        f"🧠 <b>Memory:</b> `Active`\n"
        f"════════════════"
    )
    await msg.edit(text, parse_mode='html')

@safe_register(r"^\.auto ?(.*)")
async def auto_cmd(event):
    arg = event.pattern_match.group(1).strip().lower()

    if not arg:
        return await event.edit(
            "<b>♾️ CONTROLS</b>\n"
            "`.auto ai` - Continuous AI Chat\n"
            "`.auto static` - Fixed Message\n"
            "`.auto off` - Stop",
            parse_mode='html'
        )

    if arg == "off":
        DB.set("system_status", "off")
        await event.edit("🔴 <b>Auto-Pilot Stopped.</b>", parse_mode='html')
    elif arg == "ai":
        if HAS_AI:
            DB.set("system_status", "ai")
            await event.edit("🧠 <b>AI Chat Mode Enabled.</b>\n<i>Conversations will flow naturally.</i>", parse_mode='html')
        else:
            await event.edit("❌ <b>Error:</b> AI Missing.")
    elif arg == "static":
        DB.set("system_status", "static")
        await event.edit("🟢 <b>Static Mode Enabled.</b>", parse_mode='html')
    else:
        DB.set("system_status", "static")
        DB.set("static_message", event.pattern_match.group(1))
        await event.edit(f"📝 <b>Static Message Set:</b>\n`{arg}`", parse_mode='html')

@safe_register(r"^\.mode ?(.*)")
async def mode_cmd(event):
    arg = event.pattern_match.group(1).strip().lower()
    modes = ["sleep", "work", "gaming", "default"]
    if arg in modes:
        DB.set("context_mode", arg)
        await event.edit(f"🎭 <b>Mood:</b> `{arg.upper()}`", parse_mode='html')
    else:
        await event.edit(f"❌ <b>Modes:</b> `{', '.join(modes)}`")

@safe_register(r"^\.vip (add|rem|list)")
async def vip_cmd(event):
    arg = event.pattern_match.group(1)
    vips = DB.get("vip_list")

    if arg == "list": return await event.edit(f"🌟 VIPs: {len(vips)}")

    reply = await event.get_reply_message()
    if not reply: return await event.edit("❌ Reply to user")
    uid = reply.sender_id

    if arg == "add":
        if uid not in vips:
            vips.append(uid)
            DB.set("vip_list", vips)
            await event.edit("🌟 Added to VIP")
        else: await event.edit("⚠️ Already VIP")
    else:
        if uid in vips:
            vips.remove(uid)
            DB.set("vip_list", vips)
            await event.edit("🗑️ Removed VIP")
        else: await event.edit("⚠️ Not VIP")

@safe_register(r"^\.restart")
async def restart_cmd(event):
    await event.edit("⚡ Rebooting...")
    await asyncio.sleep(1)
    os.execl(sys.executable, sys.executable, "main.py")

# main
@safe_register(incoming=True)
async def infinity_listener(event):
    if not event.is_private: return
    sender = await event.get_sender()

    # safety: ignore self and bots
    if not sender or sender.bot or sender.is_self: return

    status = DB.get("system_status")
    if status == "off": return

    user_id = event.sender_id
    user_id_str = str(user_id)

    if user_id in DB.get("blacklist"): return

    # smart cooldown
    cooldowns = DB.get("cooldowns")
    now = time.time()
    last_msg_time = cooldowns.get(user_id_str, 0)

    # cooldown logic
    limit = 2
    if status == "static":
        is_vip = user_id in DB.get("vip_list")
        limit = 60 if is_vip else 300 

    if now - last_msg_time < limit: return

    cooldowns[user_id_str] = now
    DB.set("cooldowns", cooldowns)

    logger.info(f"📨 Msg from {user_id} | Mode: {status}")

    reply_text = None

    if status == "ai":
        ctx = DB.get("context_mode")
        reply_text = await AI.generate_response(user_id, event.text, ctx)

        if not reply_text:
            reply_text = DB.get("static_message")
    else:
        reply_text = DB.get("static_message")

    if reply_text:
        await simulate_human_presence(event, reply_text)