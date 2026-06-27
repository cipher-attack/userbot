from telethon import events

async def log_error(event, error_msg, module_name):
    try:
        error_report = f"<b>⚠️ INFINITY SYSTEM ALERT</b>\n<b>Module:</b> {module_name}\n<b>Chat:</b> {event.chat_id}\n<b>Error:</b> <code>{error_msg}</code>"
        await event.client.send_message("me", error_report, parse_mode='html')
    except:
        pass 

def create_compact_tree(data):
    tree = ""
    keys = list(data.keys())
    for i, key in enumerate(keys):
        is_last = (i == len(keys) - 1)
        prefix = "└" if is_last else "├"
        value = data[key]
        tree += f"{prefix} <b>{key}:</b> {value}\n"
    return tree

async def is_admin(event, permission_type):
    if event.is_private: return True
    try:
        participant = await event.client.get_permissions(event.chat_id, 'me')
        if not participant.is_admin: return False
        if permission_type == "ban": return participant.ban_users
        if permission_type == "delete": return participant.delete_messages
        return True
    except: return False

def safe_register(pattern=None, **kwargs):
    def decorator(func):
        if pattern:
            kwargs['pattern'] = pattern
        
        if 'incoming' not in kwargs and 'outgoing' not in kwargs:
            kwargs['outgoing'] = True

        event_filter = events.NewMessage(**kwargs)
        wrapper = events.register(event_filter)(func)
        wrapper.event = event_filter
        func.event = event_filter 
        return wrapper
    return decorator