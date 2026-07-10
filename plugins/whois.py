import asyncio
from telethon import events
from telethon.errors import rpcerrorlist
from core.utils import safe_register, log_error, is_admin

try:
    from core.discord import log_discord_shadow
except ImportError:
    log_discord_shadow = None

try:
    from .whois_support.shadow_tracker import compile_shadow_data
except ImportError:
    compile_shadow_data = None

active_scans = set()

async def resolve_target(event, pattern_match):
    input_str = pattern_match.group(1).strip() if pattern_match else ""
    target = None

    if event.is_reply:
        reply = await event.get_reply_message()
        target = reply.sender_id
    elif input_str:
        target = input_str
    else:
        target = "me"

    try:
        return await event.client.get_entity(target)
    except (ValueError, rpcerrorlist.UsernameInvalidError):
        return None
    except Exception:
        return None

@safe_register(r"^\.shadow(?: |$)(.*)")
async def profile_dumper(event):
    if not await is_admin(event, "shadow"):
        return await event.edit("access denied.")

    if not compile_shadow_data:
        return await event.edit("module missing.")

    user = await resolve_target(event, pattern_match=event.pattern_match)
    if not user:
        return await event.edit("target missing.")

    scan_id = f"shadow_{user.id}"
    if scan_id in active_scans:
        return await event.edit("dump already running.")
    
    active_scans.add(scan_id)
    msg = await event.edit("dumping profile data...")

    try:
        report_path = await compile_shadow_data(event.client, user, event.chat_id)
        await asyncio.sleep(1.0)

        await event.client.send_message(
            "me",
            f"profile dump done | uid: {user.id}",
            file=report_path
        )
        await msg.edit("dump saved to saved messages.")

        if log_discord_shadow:
            fname = (user.first_name or "").strip()
            lname = (user.last_name or "").strip()
            full_name = f"{fname} {lname}".strip() or "unknown"
            await log_discord_shadow(full_name, str(user.id), report_path)

        await asyncio.sleep(2)
        await msg.delete()

    except Exception as e:
        await msg.edit(f"dump failed: {str(e)[:50]}")
        await log_error(event, str(e), "profile_dumper")
    finally:
        active_scans.discard(scan_id)