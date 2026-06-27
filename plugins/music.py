import os
import asyncio
import yt_dlp
from telethon import events, types
from core.utils import safe_register

SEARCH_STATE = {}

async def run_sync(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

@safe_register(r"^\.song (.*)")
async def song_engine(event):
    query = event.pattern_match.group(1)

    if not query: 
        return await event.edit("❌ <b>Syntax:</b> `.song <Title>`", parse_mode='html')

    await event.edit(f"🎹 <b>Searching SoundCloud:</b>\n🔎 <i>{query}</i>...", parse_mode='html')

    def search_soundcloud():
        opts = {
            'quiet': True, 
            'noplaylist': True, 
            'extract_flat': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                return ydl.extract_info(f"scsearch5:{query}", download=False).get('entries', [])
            except Exception as e:
                return []

    results = await run_sync(search_soundcloud)

    if not results:
        return await event.edit("❌ <b>Not Found.</b>", parse_mode='html')

    SEARCH_STATE[event.chat_id] = results

    menu = f"🎧 <b>CIPHER MUSIC SYSTEM</b>\n\n"
    for i, track in enumerate(results):
        title = track.get('title', 'Unknown Track')
        artist = track.get('uploader', 'Unknown Artist')
        duration = int(track.get('duration', 0))
        mins, secs = divmod(duration, 60)
        time_str = f"{mins}:{secs:02d}"

        menu += f"<b>{i+1}.</b> {title}\n    👤 <i>{artist}</i> ({time_str})\n"

    menu += "\n👇 <b>Reply with 1-5 to download.</b>"
    await event.edit(menu, parse_mode='html')

@safe_register() 
async def song_downloader(event):
    if event.chat_id not in SEARCH_STATE: return

    text = event.text.strip()
    if not text.isdigit(): return 

    choice = int(text)
    results = SEARCH_STATE[event.chat_id]

    if choice < 1 or choice > len(results): return

    track = results[choice - 1]

    del SEARCH_STATE[event.chat_id]

    msg = await event.reply(f"⬇️ <b>Downloading:</b> {track.get('title')}...", parse_mode='html')

    def download_process():
        if not os.path.exists("downloads"): os.makedirs("downloads")

        opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'downloads/%(id)s.%(ext)s', 
            'quiet': True, 
            'noplaylist': True,
            'max_filesize': 50 * 1024 * 1024,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(track['url'], download=True)
            filename = ydl.prepare_filename(info)
            base, _ = os.path.splitext(filename)
            return info, base + ".mp3"

    try:
        info, final_path = await run_sync(download_process)

        if not os.path.exists(final_path):
            return await msg.edit("❌ <b>Error:</b> File too large or failed.", parse_mode='html')

        await msg.edit("⬆️ <b>Uploading...</b>", parse_mode='html')

        attrs = types.DocumentAttributeAudio(
            duration=int(info.get('duration', 0)),
            title=info.get('title', 'Unknown'),
            performer=info.get('uploader', 'Unknown')
        )

        await event.client.send_file(
            event.chat_id, 
            final_path,
            caption=f"🎧 <b>{info.get('title')}</b>\n👤 {info.get('uploader')}",
            attributes=[attrs],
            supports_streaming=True
        )

        await msg.delete()
        await event.delete() 
        if os.path.exists(final_path): os.remove(final_path)

    except Exception as e:
        await msg.edit(f"❌ <b>Error:</b> {str(e)}")
        if 'final_path' in locals() and os.path.exists(final_path):
            os.remove(final_path)