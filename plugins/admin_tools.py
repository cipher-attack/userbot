import asyncio
import io
import traceback
from telethon import events, types
from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.types import ChatBannedRights
from telethon.tl.functions.users import GetFullUserRequest
from core.utils import safe_register, log_error, is_admin, create_compact_tree

# optional lib check
try:
    from deep_translator import GoogleTranslator
    HAS_TR = True
except ImportError:
    HAS_TR = False

# translation //lang
@safe_register(r"(.+?)\s+//([a-z]{2,})$")
async def inline_translator(event):
    if not HAS_TR: return

    original_text = event.pattern_match.group(1).strip()
    target_lang = event.pattern_match.group(2).strip()

    async with event.client.action(event.chat_id, 'typing'):
        try:
            translated = GoogleTranslator(source='auto', target=target_lang).translate(original_text)
            await event.edit(translated)
        except Exception as e:
            await log_error(event, str(e), "Translator")
            pass

# info fetcher
@safe_register(r"^\.whois")
async def whois_engine(event):
    async with event.client.action(event.chat_id, 'typing'):
        try:
            if event.reply_to_msg_id:
                reply = await event.get_reply_message()
                user = await event.client.get_entity(reply.sender_id)
            else:
                args = event.message.text.split(" ", 1)
                user = await event.client.get_entity(args[1]) if len(args) > 1 else await event.client.get_entity("me")

            full = await event.client(GetFullUserRequest(user.id))

            fname = user.first_name or ""
            lname = user.last_name or ""
            full_name = (fname + " " + lname).strip()

            bio = full.full_user.about.replace("\n", " ") if full.full_user.about else "Empty"
            if len(bio) > 25: bio = bio[:22] + "..."

            data = {
                "Name": full_name,
                "ID": f"<code>{user.id}</code>",
                "User": f"@{user.username}" if user.username else "N/A",
                "Bot": "Yes" if user.bot else "No",
                "Scam": "⚠️ YES" if user.scam else "No",
                "Bio": bio
            }

            output = f"<b>👤 IDENTITY SCAN</b>\n"
            output += create_compact_tree(data)

            photo = await event.client.download_profile_photo(user.id, file=bytes)

            if photo:
                f = io.BytesIO(photo)
                f.name = "profile.jpg"
                await event.client.send_file(event.chat_id, f, caption=output, parse_mode='html')
                await event.delete() 
            else:
                await event.edit(output, parse_mode='html')

        except Exception as e:
            await event.edit("❌ <b>Scan Failed</b>", parse_mode='html')
            await log_error(event, str(e), "Whois")

# nuke msgs
@safe_register(r"^\.purge")
async def purge_engine(event):
    if not await is_admin(event, "delete"):
        return await event.edit("❌ <b>Perms Denied</b>", parse_mode='html')

    reply = await event.get_reply_message()
    if not reply:
        return await event.edit("❌ <b>Reply first</b>", parse_mode='html')

    await event.delete()

    msgs = []
    count = 0
    try:
        async for msg in event.client.iter_messages(event.chat_id, min_id=reply.id - 1):
            msgs.append(msg.id)
            count += 1
            if len(msgs) >= 100:
                await event.client.delete_messages(event.chat_id, msgs)
                msgs = []
                await asyncio.sleep(1)

        if msgs:
            await event.client.delete_messages(event.chat_id, msgs)

        await log_error(event, f"Purged {count} messages in {event.chat_id}", "Purge Success")

    except Exception as e:
        await log_error(event, str(e), "Purge")

# admin tools
@safe_register(r"^\.ban (.*)")
async def ban_engine(event):
    if not await is_admin(event, "ban"):
        return await event.edit("❌ <b>Perms Denied</b>", parse_mode='html')

    try:
        input_str = event.pattern_match.group(1)
        user = await event.client.get_entity(input_str) if not event.is_reply else await event.get_reply_message().get_sender()

        if user.id == (await event.client.get_me()).id:
            return await event.edit("❌ <b>Self-Ban Blocked</b>", parse_mode='html')

        await event.client(EditBannedRequest(
            event.chat_id,
            user.id,
            ChatBannedRights(until_date=None, view_messages=True)
        ))
        await event.edit(f"⛔ <b>Banned:</b> {user.first_name}", parse_mode='html')

    except Exception as e:
        await event.edit("❌ <b>Failed</b>", parse_mode='html')
        await log_error(event, str(e), "Ban")

@safe_register(r"^\.mute (.*)")
async def mute_engine(event):
    if not await is_admin(event, "ban"):
        return await event.edit("❌ <b>Perms Denied</b>", parse_mode='html')

    try:
        input_str = event.pattern_match.group(1)
        user = await event.client.get_entity(input_str) if not event.is_reply else await event.get_reply_message().get_sender()

        await event.client(EditBannedRequest(
            event.chat_id,
            user.id,
            ChatBannedRights(until_date=None, send_messages=True)
        ))
        await event.edit(f"🔇 <b>Muted:</b> {user.first_name}", parse_mode='html')

    except Exception as e:
        await event.edit("❌ <b>Failed</b>", parse_mode='html')
        await log_error(event, str(e), "Mute")

# clean deleted accs
@safe_register(r"^\.zombies")
async def zombie_cleaner(event):
    if not await is_admin(event, "ban"):
        return await event.edit("❌ <b>Perms Denied</b>", parse_mode='html')

    msg = await event.edit("🧟 <b>Scanning...</b>", parse_mode='html')

    deleted = 0
    removed = 0
    chat = await event.get_chat()

    try:
        participants = await event.client.get_participants(chat)
        for user in participants:
            if user.deleted:
                deleted += 1
                try:
                    await event.client(EditBannedRequest(
                        event.chat_id,
                        user.id,
                        ChatBannedRights(until_date=None, view_messages=True)
                    ))
                    removed += 1
                    await asyncio.sleep(0.5)
                except: pass

        report = (
            f"<b>🧟 ZOMBIE PURGE</b>\n"
            f"├ <b>Found:</b> {deleted}\n"
            f"└ <b>Killed:</b> {removed}"
        )
        await msg.edit(report, parse_mode='html')

    except Exception as e:
        await msg.edit("❌ <b>Scan Error</b>", parse_mode='html')
        await log_error(event, str(e), "Zombie")