import os
import asyncio
from telethon import events
from core.utils import safe_register

# ⚠️ SECURITY CONFIG
# By default, this is disabled to prevent account bans.
# Change to True only if you understand the risks.
ENABLE_VIEW_ONCE = False 

# view once saver
@safe_register(incoming=True)
async def vault_guardian(event):
    # Safety Switch
    if not ENABLE_VIEW_ONCE: return

    # check media
    if not event.media or not event.message: return

    is_view_once = False
    ttl_time = 0

    # check ttl
    if hasattr(event.message, 'ttl_period') and event.message.ttl_period:
        is_view_once = True
        ttl_time = event.message.ttl_period
    elif hasattr(event.media, 'ttl_seconds') and event.media.ttl_seconds:
        is_view_once = True
        ttl_time = event.media.ttl_seconds

    if is_view_once:
        try:
            sender = await event.get_sender()
            name = sender.first_name if sender else "Unknown"

            if not os.path.exists("downloads"):
                os.makedirs("downloads")

            # dl media
            path = await event.download_media(file="downloads/")
            if not path: return 

            # fwd to saved msgs
            await event.client.send_file(
                "me", 
                path, 
                caption=f"🔓 <b>VAULT CAPTURE</b>\n👤 <b>Target:</b> {name}\n⏳ <b>TTL:</b> {ttl_time}s",
                parse_mode='html'
            )

            # cleanup
            if os.path.exists(path): 
                os.remove(path)

            print(f"[INFO] Captured from {name}")

        except Exception as e:
            print(f"[ERROR] Vault Failed: {e}")

# fake hack
@safe_register(r"^\.hack")
async def hack_sim(event):
    reply = await event.get_reply_message()
    target = "System"

    if reply:
        u = await reply.get_sender()
        target = u.first_name if u else "Target"

    await event.edit(f"💻 <b>TARGET LOCK: {target}</b>", parse_mode='html')
    await asyncio.sleep(2) 

    steps = [
        "🔄 Handshake Protocol...",
        "🔓 Brute-forcing 2FA Keys...",
        "💉 SQL Injection: <b>SUCCESS</b>",
        f"📂 Dumping {target}'s Chat History...",
        "📡 Bypassing Firewall...",
        f"✅ <b>{target} PWNED.</b>"
    ]

    for step in steps:
        try:
            await event.edit(f"<code>{step}</code>", parse_mode='html')
            # anti flood
            await asyncio.sleep(1.5) 
        except Exception:
            break