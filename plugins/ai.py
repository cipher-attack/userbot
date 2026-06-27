import io
import random
import asyncio
import logging
import warnings
import time
from telethon import events
from config import Config
import PIL.Image
from core.utils import safe_register

warnings.filterwarnings("ignore")
logger = logging.getLogger("EliteAI")

try:
    import google.generativeai as genai
except ImportError:
    pass 

try:
    from duckduckgo_search import DDGS
except ImportError:
    pass

SYSTEM_PROMPT = """
You are a real, elite tech enthusiast on Telegram.
- NEVER say you are an AI, Google Gemini, or a bot.
- If asked, say you are just a user running a custom script.
- Keep responses chill, short (max 3 sentences), and witty.
- Dont use bullet points unless asked. Speak naturally.
"""

async def download_image(session, url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://google.com"
        }
        async with session.get(url, headers=headers, timeout=5) as resp:
            if resp.status == 200:
                data = await resp.read()
                return io.BytesIO(data)
    except:
        return None

@safe_register(r"^\.ai ?(.*)")
async def ai_core(event):
    user_input = event.pattern_match.group(1)
    reply = await event.get_reply_message()

    if not user_input and not reply:
        return await event.edit("❌ <b>Usage:</b> `.ai <text>`")

    await event.edit("`⚡`") 

    content_payload = []

    if reply and reply.media and reply.photo:
        if hasattr(reply.media, 'ttl_seconds') and reply.media.ttl_seconds:
            return await event.edit("❌ <b>Security:</b> View-Once media blocked.")

        try:
            photo_data = await reply.download_media(file=bytes)
            pil_image = PIL.Image.open(io.BytesIO(photo_data))
            content_payload.append(pil_image)
            if not user_input: user_input = "Analyze this."
        except Exception as e:
            return await event.edit(f"❌ Image Error: {e}")

    if user_input:
        content_payload.append(user_input)

    raw_keys = getattr(Config, "GEMINI_KEYS", [])
    valid_keys = [k for k in raw_keys if k]
    
    if not valid_keys:
        await event.client.send_message("me", f"⚠️ **AI SYSTEM ALERT**\nNo API Keys found in Config.\nLoaded Data: `{str(raw_keys)}`")
        return await event.edit("❌ No API Keys.")

    random.shuffle(valid_keys)
    final_response = None

    models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']

    for model_name in models_to_try:
        if final_response: break

        for api_key in valid_keys:
            try:
                genai.configure(api_key=api_key)

                model = genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=SYSTEM_PROMPT
                )

                response = await asyncio.to_thread(
                    model.generate_content,
                    content_payload
                )

                if response.text:
                    final_response = response.text
                    break 

            except Exception as e:
                err = str(e)
                await event.client.send_message("me", f"⚠️ **AI DEBUG**\nModel: `{model_name}`\nKey: `...{api_key[-6:]}`\nError: `{err}`")
                
                if "429" in err: continue 
                if "404" in err: break 
                continue

    if final_response:
        clean_text = final_response.replace("Gemini", "Me").replace("Google", "My source")
        clean_text = clean_text.replace("**", "<b>").replace("**", "</b>")
        await event.edit(clean_text, parse_mode='html')
    else:
        await event.edit("❌ <b>System Busy:</b> All AI servers are overloaded.")


@safe_register(r"^\.img (.*)")
async def single_image(event):
    query = event.pattern_match.group(1)
    if not query: return await event.edit("❌ Usage: `.img <text>`")

    await event.edit(f"🔎 <b>Searching:</b> {query}...")
    try:
        import aiohttp
        results = []
        try:
            results = list(DDGS().images(keywords=query, region="wt-wt", safesearch="off", max_results=5))
        except Exception:
            await asyncio.sleep(1.5) 
            try:
                results = list(DDGS().images(keywords=query, region="wt-wt", safesearch="off", max_results=3))
            except: pass

        if results:
            url = random.choice(results)['image']
            async with aiohttp.ClientSession() as session:
                img_data = await download_image(session, url)
                if img_data:
                    img_data.name = "img.jpg"
                    await event.client.send_file(event.chat_id, img_data, caption=f"🖼 <b>{query}</b>", parse_mode='html')
                    await event.delete()
                else:
                    await event.edit("❌ Download blocked by server.")
        else:
            await event.edit("❌ No images found (Server busy).")
    except Exception as e:
        await event.edit(f"❌ Error: {e}")

@safe_register(r"^\.imgs (.*)")
async def gallery_image(event):
    query = event.pattern_match.group(1)
    if not query: return await event.edit("❌ Usage: `.imgs <text>`")

    await event.edit(f"📚 <b>Curating:</b> {query}...")
    try:
        import aiohttp

        results = []
        try:
            results = list(DDGS().images(keywords=query, region="wt-wt", safesearch="off", max_results=10))
        except Exception as e:
            await asyncio.sleep(2)
            try:
                results = list(DDGS().images(keywords=query, region="wt-wt", safesearch="off", max_results=5))
            except: pass

        if not results: return await event.edit("❌ Search limit reached. Try again later.")

        top_results = results[:9]
        tasks = []
        valid_files = []

        async with aiohttp.ClientSession() as session:
            for res in top_results:
                tasks.append(download_image(session, res['image']))
                await asyncio.sleep(0.2)

            files = await asyncio.gather(*tasks)

            for i, f in enumerate(files):
                if f:
                    f.name = f"gallery_{i}.jpg"
                    valid_files.append(f)

        if valid_files:
            await event.client.send_file(event.chat_id, valid_files, caption=f"📚 <b>Gallery:</b> {query}", parse_mode='html')
            await event.delete()
        else:
            await event.edit("❌ Failed to download images (Anti-bot protection).")

    except Exception as e:
        await event.edit(f"❌ Critical Error: {e}")